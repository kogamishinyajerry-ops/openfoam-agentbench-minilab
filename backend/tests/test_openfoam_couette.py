"""Offline tests for the real-OpenFOAM Couette case generator.

These never touch Docker — they only assert the generated case dictionaries
encode the right Couette boundary conditions (fixed bottom wall, moving lid, and
the injected stationary-wall slip). The actual solver run is exercised separately
and is self-validating against the linear analytical solution.
"""
from __future__ import annotations

from ofab import config
from ofab.models import Fault
from ofab.runner import openfoam_couette as ofc


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
