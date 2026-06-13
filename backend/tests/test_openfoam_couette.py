"""Offline tests for the real-OpenFOAM Couette case generator.

These never touch Docker — they only assert the generated case dictionaries
encode the right Couette boundary conditions (fixed bottom wall, moving lid, and
the injected stationary-wall slip). The actual solver run is exercised separately
and is self-validating against the linear analytical solution.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ofab import config
from ofab.models import Fault
from ofab.runner import openfoam_couette as ofc

REPO_ROOT = Path(__file__).resolve().parents[2]
COUETTE_EVIDENCE = REPO_ROOT / "data" / "real_evidence_couette.json"


def _gen(tmp_path, fault, repaired):
    d = tmp_path / "case"
    ofc.generate_couette_case(d, fault, repaired)
    return {
        "U": (d / "0" / "U").read_text(),
        "p": (d / "0" / "p").read_text(),
        "blockMesh": (d / "system" / "blockMeshDict").read_text(),
        "control": (d / "system" / "controlDict").read_text(),
    }


def test_correct_case_has_moving_lid_and_noslip_floor(tmp_path):
    f = _gen(tmp_path, Fault.NONE, repaired=True)
    # top lid dragged at U_lid, bottom wall no-slip (the correct Couette setup)
    assert f"movingWall {{ type fixedValue; value uniform ({config.COUETTE_LID_VELOCITY} 0 0); }}" in f["U"]
    assert "fixedWall { type noSlip; }" in f["U"]
    # separate top/bottom wall patches exist
    assert "movingWall" in f["blockMesh"]
    assert "fixedWall" in f["blockMesh"]


def test_bc_fault_sets_stationary_wall_to_nonzero_velocity(tmp_path):
    f = _gen(tmp_path, Fault.BC_MISMATCH, repaired=False)
    expected = round(config.COUETTE_BC_SLIP * config.COUETTE_LID_VELOCITY, 6)
    # the no-slip violation: the *fixed* wall is given a small velocity
    assert f"fixedWall {{ type fixedValue; value uniform ({expected} 0 0); }}" in f["U"]
    # the lid is still correct
    assert f"movingWall {{ type fixedValue; value uniform ({config.COUETTE_LID_VELOCITY} 0 0); }}" in f["U"]


def test_solver_fault_stops_early(tmp_path):
    f = _gen(tmp_path, Fault.SOLVER_SETTING_ERROR, repaired=False)
    assert "endTime 0.02;" in f["control"]


def test_coarse_mesh_fault_uses_few_cells(tmp_path):
    f = _gen(tmp_path, Fault.COARSE_MESH, repaired=False)
    # ny = 4 -> blocks line "(20 4 1)"
    assert "(20 4 1)" in f["blockMesh"]


def test_case_samples_wall_normal_line(tmp_path):
    f = _gen(tmp_path, Fault.NONE, repaired=True)
    assert "type sets;" in f["control"]
    assert f"nPoints {config.N_PROFILE_POINTS};" in f["control"]
    assert "fields ( U );" in f["control"]


def test_pressure_outlet_is_fixed_zero(tmp_path):
    f = _gen(tmp_path, Fault.NONE, repaired=True)
    # no imposed streamwise pressure gradient: outlet p = 0, ends zeroGradient for U
    assert "outlet { type fixedValue; value uniform 0; }" in f["p"]
    assert "inlet { type zeroGradient; }" in f["U"]
    assert "outlet { type zeroGradient; }" in f["U"]


# --------------------------------------------------------------------------- #
# Committed real-OpenFOAM evidence (Docker-free: reads the captured JSON)      #
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def evidence() -> dict:
    assert COUETTE_EVIDENCE.is_file(), (
        f"missing {COUETTE_EVIDENCE} — run `ofab demo couette-evidence` on a live container"
    )
    return json.loads(COUETTE_EVIDENCE.read_text())


def test_real_correct_reproduces_analytical_line(evidence):
    # the real solver's correct run matches the linear analytical solution
    assert evidence["correct"]["qoi_error"] < config.QOI_L2_TOL
    assert evidence["correct"]["engineering_status"] == "pass"


def test_real_faults_are_caught_and_diagnosed(evidence):
    by = {f["fault"]: f for f in evidence["faults"]}
    # same unchanged benchmark catches real false successes on a different flow
    assert by["bc_mismatch"]["false_success_detected"] is True
    assert by["bc_mismatch"]["diagnosis"] == "BC_MISMATCH"
    assert by["solver_setting_error"]["false_success_detected"] is True
    assert by["solver_setting_error"]["diagnosis"] == "RESIDUAL_NOT_CONVERGED"


def test_real_coarse_mesh_confirms_not_applicable(evidence):
    """Empirical backing for the honest claim: coarse_mesh does not manifest as
    error in Couette — a linear profile is reconstructed exactly on any mesh."""
    cm = evidence["coarse_mesh_check"]
    assert cm["qoi_error"] < config.QOI_L2_TOL
    assert cm["overall_pass"] is True


# --------------------------------------------------------------------------- #
# Synthetic Couette run (CLI mock/replay path, no container)                  #
# --------------------------------------------------------------------------- #
def test_synthesize_couette_bc_fault_is_a_false_success():
    from ofab.demo.couette_case import synthesize_couette_run

    r = synthesize_couette_run(Fault.BC_MISMATCH, repaired=False)
    assert r.case_id == config.COUETTE_CASE_ID
    assert r.fault == Fault.BC_MISMATCH
    assert r.qoi_error == pytest.approx(config.COUETTE_BC_SLIP, abs=1e-3)  # ~18%
    assert r.engineering_status.value == "needs_repair"


def test_synthesize_couette_repaired_passes():
    from ofab.demo.couette_case import synthesize_couette_run

    r = synthesize_couette_run(Fault.BC_MISMATCH, repaired=True)
    assert r.qoi_error == pytest.approx(config.COUETTE_REPAIR_SLIP, abs=1e-3)  # ~2%
    assert r.engineering_status.value == "pass"


def test_synthesize_couette_clean_reproduces_line():
    from ofab.demo.couette_case import synthesize_couette_run

    r = synthesize_couette_run(Fault.NONE, repaired=False)
    assert r.qoi_error == pytest.approx(0.0, abs=1e-6)
    assert r.engineering_status.value == "pass"
