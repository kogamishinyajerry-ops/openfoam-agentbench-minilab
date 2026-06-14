"""Offline tests for the real-OpenFOAM pipe (axisymmetric-wedge) case generator.

These never touch Docker — they only assert the generated case dictionaries encode
the right axisymmetric-wedge geometry, boundary conditions, the injected coarse
radial mesh (the pipe's hero fault), and the wall-velocity measurement that makes the
coarse-mesh diagnosis faithful. The actual solver run is exercised separately and is
self-validating against the radial-parabola analytical solution; its captured numbers
are locked below by reading the committed evidence JSON (still Docker-free).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ofab import config
from ofab.models import Fault
from ofab.runner import openfoam_pipe as ofp

REPO_ROOT = Path(__file__).resolve().parents[2]
PIPE_EVIDENCE = REPO_ROOT / "data" / "real_evidence_pipe.json"
PIPE_EVIDENCE_FRONTEND = REPO_ROOT / "frontend" / "src" / "data" / "realEvidencePipe.json"


def _gen(tmp_path, fault, repaired):
    d = tmp_path / "case"
    ofp.generate_pipe_case(d, fault, repaired)
    return {
        "U": (d / "0" / "U").read_text(),
        "p": (d / "0" / "p").read_text(),
        "blockMesh": (d / "system" / "blockMeshDict").read_text(),
        "control": (d / "system" / "controlDict").read_text(),
    }


# --------------------------------------------------------------------------- #
# Axisymmetric-wedge geometry                                                 #
# --------------------------------------------------------------------------- #
def test_wedge_uses_collapsed_axis_edge(tmp_path):
    """The pipe is a collapsed-edge wedge: the hex repeats the two axis vertices
    (0 and 1) so the axis edge is zero-length — no degenerate faces, which is what
    makes checkMesh pass and icoFoam not crash."""
    f = _gen(tmp_path, Fault.NONE, repaired=True)
    assert "hex (0 1 2 3 0 1 4 5)" in f["blockMesh"]
    # exactly two wedge patches (front/back), and a no-slip wall patch
    assert f["blockMesh"].count("type wedge;") == 2
    assert "wall { type wall;" in f["blockMesh"]


def test_wedge_fields_have_wedge_patches(tmp_path):
    f = _gen(tmp_path, Fault.NONE, repaired=True)
    # both U and p must carry wedge BCs on front/back (axisymmetric requirement)
    assert f["U"].count("type wedge;") == 2
    assert f["p"].count("type wedge;") == 2


def test_correct_case_is_noslip_wall_and_uniform_inlet(tmp_path):
    f = _gen(tmp_path, Fault.NONE, repaired=True)
    assert "wall { type noSlip; }" in f["U"]
    # uniform inlet velocity = bulk mean (develops into the parabola)
    assert f"inlet {{ type fixedValue; value uniform ({config.PIPE_MEAN_VELOCITY} 0 0); }}" in f["U"]
    assert "outlet { type fixedValue; value uniform 0; }" in f["p"]


# --------------------------------------------------------------------------- #
# Injected faults                                                             #
# --------------------------------------------------------------------------- #
def test_coarse_mesh_fault_uses_few_radial_cells(tmp_path):
    """The hero fault: an under-resolved radial mesh. nr collapses to the small
    coarse count while the streamwise count stays full."""
    f = _gen(tmp_path, Fault.COARSE_MESH, repaired=False)
    assert f"(60 {ofp._REAL_COARSE_NR} 1)" in f["blockMesh"]
    # and a correctly-resolved case keeps the fine radial count
    fine = _gen(tmp_path, Fault.NONE, repaired=True)
    assert f"(60 {ofp._FINE_NR} 1)" in fine["blockMesh"]
    assert ofp._REAL_COARSE_NR < ofp._FINE_NR


def test_bc_fault_sets_wall_moving(tmp_path):
    f = _gen(tmp_path, Fault.BC_MISMATCH, repaired=False)
    # no-slip violated: the pipe wall is set moving downstream
    assert f"wall {{ type fixedValue; value uniform ({ofp._FAULT_WALL_SPEED} 0 0); }}" in f["U"]


def test_solver_fault_stops_early(tmp_path):
    f = _gen(tmp_path, Fault.SOLVER_SETTING_ERROR, repaired=False)
    assert "endTime 0.01;" in f["control"]


# --------------------------------------------------------------------------- #
# Sampling + faithful wall measurement                                        #
# --------------------------------------------------------------------------- #
def test_case_samples_radial_line_and_wall_patch(tmp_path):
    """Two measurements: the radial line profile (41 pts) AND the area-averaged wall
    velocity (surfaceFieldValue on the wall patch). The wall measurement is what keeps
    a coarse mesh from being mis-read as a no-slip violation."""
    f = _gen(tmp_path, Fault.NONE, repaired=True)
    assert "type sets;" in f["control"]
    assert f"nPoints {config.N_PROFILE_POINTS};" in f["control"]
    # the wall-patch area-average measurement
    assert "type surfaceFieldValue;" in f["control"]
    assert "regionType patch;" in f["control"]
    assert "name wall;" in f["control"]
    assert "operation areaAverage;" in f["control"]


def test_adaptive_time_stepping_is_on(tmp_path):
    """The tiny wedge cells next to the axis make a fixed deltaT blow up the Courant
    number; adaptive stepping is mandatory for the solve to stay stable."""
    f = _gen(tmp_path, Fault.NONE, repaired=True)
    assert "adjustTimeStep yes;" in f["control"]
    assert "maxCo 0.5;" in f["control"]


def test_parse_wall_average_reads_vector_x(tmp_path):
    """The wall-average parser pulls Ux from a surfaceFieldValue .dat line."""
    dat = tmp_path / "surfaceFieldValue.dat"
    dat.write_text(
        "# Region type : patch wall\n# Time areaAverage(U)\n"
        "0.01 (0.05 0 0)\n6 (1.2e-09 0 0)\n"
    )
    assert ofp._parse_wall_average(dat) == pytest.approx(1.2e-09)
    assert ofp._parse_wall_average(tmp_path / "missing.dat") is None


# --------------------------------------------------------------------------- #
# Committed real-OpenFOAM evidence (Docker-free: reads the captured JSON)      #
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def evidence() -> dict:
    assert PIPE_EVIDENCE.is_file(), (
        f"missing {PIPE_EVIDENCE} — run `ofab demo pipe-evidence` on a live container"
    )
    return json.loads(PIPE_EVIDENCE.read_text())


def test_real_correct_reproduces_radial_parabola(evidence):
    # the real solver's correct run matches the analytical radial parabola
    assert evidence["correct"]["qoi_error"] < config.QOI_L2_TOL
    assert evidence["correct"]["engineering_status"] == "pass"
    # axis peak ≈ 2·U_mean (the round-pipe relation, distinct from the channel's 1.5)
    assert evidence["correct"]["u_peak_sampled"] == pytest.approx(config.PIPE_U_MAX, abs=0.01)


def test_real_hero_coarse_mesh_is_caught_and_diagnosed(evidence):
    """The third case's whole point: on real hardware the SAME benchmark catches the
    coarse-mesh false success on the pipe and classifies it as MESH_TOO_COARSE — a
    different headline fault than the other two cases' BC_MISMATCH, and the mirror of
    Couette where this fault is not applicable."""
    by = {f["fault"]: f for f in evidence["faults"]}
    coarse = by["coarse_mesh"]
    assert evidence["hero_fault"] == "coarse_mesh"
    assert coarse["is_hero"] is True
    assert coarse["execution_status"] == "success"   # it RAN fine ...
    assert coarse["false_success_detected"] is True   # ... but is engineering-wrong
    assert coarse["qoi_error"] > config.QOI_L2_TOL
    assert coarse["diagnosis"] == "MESH_TOO_COARSE"
    assert coarse["diagnosis"] != "BC_MISMATCH"
    # the faithful wall measurement kept no-slip intact (not mis-read as a BC fault)
    assert coarse["features"]["wall_slip"] < config.WALL_SLIP_TOL


def test_real_other_faults_are_caught_and_diagnosed(evidence):
    by = {f["fault"]: f for f in evidence["faults"]}
    assert by["bc_mismatch"]["false_success_detected"] is True
    assert by["bc_mismatch"]["diagnosis"] == "BC_MISMATCH"
    assert by["solver_setting_error"]["false_success_detected"] is True
    assert by["solver_setting_error"]["diagnosis"] == "RESIDUAL_NOT_CONVERGED"


def test_pipe_evidence_frontend_copy_is_byte_identical(evidence):
    """The dashboard's pipe real-evidence strip reads
    frontend/src/data/realEvidencePipe.json; it must equal the backend
    data/real_evidence_pipe.json (both written from one object by
    `ofab demo pipe-evidence`). Same additive-safety mirror lock as the other cases."""
    assert PIPE_EVIDENCE_FRONTEND.is_file(), f"missing {PIPE_EVIDENCE_FRONTEND}"
    frontend = json.loads(PIPE_EVIDENCE_FRONTEND.read_text())
    assert frontend == evidence
