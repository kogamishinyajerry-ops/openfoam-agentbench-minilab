"""Tests for ofab.runner.{mock_runner, replay_runner, openfoam_runner}.

These assert *real invariants* of the runner layer — the project's own thesis is
that verification must catch false success, so the tests refuse to water down:
they bind to the fixed physics constants (config.py / physics.py), never to
"whatever the code returns". Docker is never invoked: only the pure
case-generation path of openfoam_runner is exercised.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from ofab import config, physics
from ofab.models import (
    EngineeringStatus,
    ExecutionStatus,
    Fault,
    RunMode,
    RunResult,
    Workflow,
)
from ofab.runner import mock_runner, openfoam_runner, replay_runner


# --------------------------------------------------------------------------- #
# mock_runner.run_synthetic                                                   #
# --------------------------------------------------------------------------- #
def test_run_synthetic_none_is_pass_and_zero_qoi():
    r = mock_runner.run_synthetic("t_none", Workflow.AGENT_PLUS_BENCHMARK, Fault.NONE)
    # NONE fault -> exact analytical profile -> zero error, residual below tol.
    assert r.qoi_error == pytest.approx(0.0, abs=1e-9)
    assert r.engineering_status == EngineeringStatus.PASS
    assert r.execution_status == ExecutionStatus.SUCCESS
    assert r.residual_final < config.RESIDUAL_TOL
    assert r.mode == RunMode.MOCK
    assert r.case_id == config.CASE_ID


def test_run_synthetic_bc_unrepaired_needs_repair_high_slip():
    r = mock_runner.run_synthetic("t_bc", Workflow.AGENT_PLUS_BENCHMARK, Fault.BC_MISMATCH)
    # Unrepaired bc_mismatch: qoi above tolerance, wall slip well above the slip tol.
    assert r.engineering_status == EngineeringStatus.NEEDS_REPAIR
    assert r.qoi_error > config.QOI_L2_TOL
    assert 0.17 <= r.qoi_error <= 0.20            # ~0.184
    assert r.features["wall_slip"] == pytest.approx(0.283, abs=1e-3)
    assert r.features["wall_slip"] > config.WALL_SLIP_TOL
    assert r.execution_status == ExecutionStatus.SUCCESS


def test_run_synthetic_no_benchmark_is_unknown():
    r = mock_runner.run_synthetic(
        "t_nobench", Workflow.AGENT_ONLY, Fault.BC_MISMATCH, has_benchmark=False
    )
    # Without a benchmark the agent genuinely cannot tell -> UNKNOWN, but it still ran.
    assert r.engineering_status == EngineeringStatus.UNKNOWN
    assert r.execution_status == ExecutionStatus.SUCCESS


@pytest.mark.parametrize(
    "fault, repaired, slip",
    [
        (Fault.NONE, False, None),
        (Fault.BC_MISMATCH, False, None),
        (Fault.COARSE_MESH, False, None),
        (Fault.SOLVER_SETTING_ERROR, False, None),
        (Fault.BC_MISMATCH, True, None),
        (Fault.BC_MISMATCH, False, 0.134),  # plateau slip
    ],
)
def test_run_synthetic_execution_always_success(fault, repaired, slip):
    # The whole point of the demo: execution never fails — engineering failure
    # must hide behind a clean exit code.
    r = mock_runner.run_synthetic(
        "t_exec", Workflow.AGENT_PLUS_BENCHMARK, fault, repaired=repaired, slip=slip
    )
    assert r.execution_status == ExecutionStatus.SUCCESS


def test_run_synthetic_solver_setting_error_residual_not_converged():
    r = mock_runner.run_synthetic(
        "t_solver", Workflow.AGENT_PLUS_BENCHMARK, Fault.SOLVER_SETTING_ERROR
    )
    # Solver fault (unrepaired) leaves an un-converged residual above tolerance,
    # so even though it "ran", it must be flagged NEEDS_REPAIR.
    assert r.residual_final == pytest.approx(8.0e-3, rel=1e-6)
    assert r.residual_final > config.RESIDUAL_TOL
    assert r.engineering_status == EngineeringStatus.NEEDS_REPAIR


def test_run_synthetic_repaired_bc_passes():
    r = mock_runner.run_synthetic(
        "t_rep", Workflow.AGENT_PLUS_BENCHMARK, Fault.BC_MISMATCH, repaired=True
    )
    # A good fix lands inside the acceptance band (< 5% L2) and converges.
    assert 0.02 <= r.qoi_error <= 0.025           # ~0.0211
    assert r.qoi_error < config.QOI_L2_TOL
    assert r.residual_final < config.RESIDUAL_TOL
    assert r.engineering_status == EngineeringStatus.PASS


def test_run_synthetic_solver_fault_is_deterministic():
    # failed_profile is RNG_SEED-seeded -> two synth runs must be byte-identical.
    r1 = mock_runner.run_synthetic(
        "t_d1", Workflow.AGENT_PLUS_BENCHMARK, Fault.SOLVER_SETTING_ERROR
    )
    r2 = mock_runner.run_synthetic(
        "t_d2", Workflow.AGENT_PLUS_BENCHMARK, Fault.SOLVER_SETTING_ERROR
    )
    assert r1.profile.u == r2.profile.u
    assert r1.qoi_error == r2.qoi_error
    assert r1.features == r2.features


# --------------------------------------------------------------------------- #
# build_run: qoi / features computed consistently with physics                #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "fault, lo, hi",
    [
        (Fault.BC_MISMATCH, 0.17, 0.20),
        (Fault.COARSE_MESH, 0.05, 0.07),
        (Fault.SOLVER_SETTING_ERROR, 0.13, 0.16),
    ],
)
def test_build_run_qoi_matches_physics(fault, lo, hi):
    yn = physics.normalized_y()
    u = physics.failed_profile(fault.value, yn)
    residual = physics.residual_for(fault.value, repaired=False)
    r = mock_runner.build_run(
        "t_build", Workflow.AGENT_PLUS_BENCHMARK, fault,
        u_profile=u, residual=residual, runtime_s=12.0,
    )
    expected_qoi = physics.l2_relative_error(np.asarray(u, float), physics.analytical_profile())
    expected_feats = physics.profile_features(np.asarray(u, float))
    # build_run rounds qoi to 5 dp and features to 5 dp — compare at that precision.
    assert r.qoi_error == pytest.approx(round(float(expected_qoi), 5), abs=1e-5)
    assert lo <= r.qoi_error <= hi
    for k, v in expected_feats.items():
        assert r.features[k] == pytest.approx(round(float(v), 5), abs=1e-5)


def test_build_run_features_coarse_mesh_shape():
    # coarse mesh respects no-slip (≈0 slip). The genuine, robust signal is a
    # faceted interior -> non-zero curvature_rmse (this is what the diagnosis
    # layer can rely on regardless of cell parity).
    yn = physics.normalized_y()
    u = physics.failed_profile("coarse_mesh", yn)
    r = mock_runner.build_run(
        "t_coarse", Workflow.AGENT_PLUS_BENCHMARK, Fault.COARSE_MESH,
        u_profile=u, residual=physics.residual_for("coarse_mesh", repaired=False),
        runtime_s=1.0,
    )
    assert r.features["wall_slip"] < config.WALL_SLIP_TOL
    assert r.features["curvature_rmse"] > 0.0


def test_build_run_coarse_mesh_has_positive_peak_deficit():
    # Cell-centre sampling clips the centreline peak -> positive peak deficit,
    # a second genuine signal (alongside curvature) for the coarse-mesh fault.
    yn = physics.normalized_y()
    u = physics.failed_profile("coarse_mesh", yn)
    r = mock_runner.build_run(
        "t_coarse_pd", Workflow.AGENT_PLUS_BENCHMARK, Fault.COARSE_MESH,
        u_profile=u, residual=physics.residual_for("coarse_mesh", repaired=False),
        runtime_s=1.0,
    )
    assert r.features["peak_deficit"] > 0.0


def test_build_run_reference_is_analytical():
    yn = physics.normalized_y()
    u = physics.analytical_profile(yn)
    r = mock_runner.build_run(
        "t_ref", Workflow.AGENT_PLUS_BENCHMARK, Fault.NONE,
        u_profile=u, residual=physics.residual_for("none", repaired=True),
        runtime_s=1.0,
    )
    # reference must be the exact parabola: wall nodes 0, centerline U_MAX, len 41.
    ref = r.reference.u
    assert len(ref) == config.N_PROFILE_POINTS
    assert ref[0] == pytest.approx(0.0, abs=1e-6)
    assert ref[-1] == pytest.approx(0.0, abs=1e-6)
    assert max(ref) == pytest.approx(config.U_MAX, abs=1e-6)
    # NONE profile equals reference -> qoi exactly 0.
    assert r.qoi_error == pytest.approx(0.0, abs=1e-9)


# --------------------------------------------------------------------------- #
# replay_runner against the real bundle                                       #
# --------------------------------------------------------------------------- #
def test_list_runs_nonempty_all_runresult():
    runs = replay_runner.list_runs()
    assert len(runs) > 0
    assert all(isinstance(r, RunResult) for r in runs)


def test_get_run_known_id():
    runs = replay_runner.list_runs()
    known = runs[0].run_id
    r = replay_runner.get_run(known)
    assert isinstance(r, RunResult)
    assert r.run_id == known


def test_get_run_unknown_id_raises_keyerror():
    with pytest.raises(KeyError):
        replay_runner.get_run("definitely_not_a_real_run_id_xyz")


def test_load_bundle_missing_path_raises_bundlenotfound(tmp_path):
    missing = tmp_path / "no_such_bundle.json"
    with pytest.raises(replay_runner.BundleNotFound):
        replay_runner.load_bundle(missing)


def test_load_bundle_real_has_runs_key():
    bundle = replay_runner.load_bundle()
    assert "runs" in bundle
    assert isinstance(bundle["runs"], list) and bundle["runs"]


# --------------------------------------------------------------------------- #
# openfoam_runner — pure functions only (NO docker)                           #
# --------------------------------------------------------------------------- #
def test_fault_params_repaired_correct_state():
    # Repaired (good) state for any fault: fine mesh, full end_time, no-slip wall.
    p = openfoam_runner._fault_params(Fault.BC_MISMATCH, repaired=True)
    assert p["ny"] == 40
    assert p["end_time"] == pytest.approx(6.0)
    assert p["wall_type"] == "noSlip"


def test_fault_params_bc_mismatch_moving_wall():
    p = openfoam_runner._fault_params(Fault.BC_MISMATCH, repaired=False)
    assert p["wall_type"] == "moving"


def test_fault_params_coarse_mesh_ny4():
    p = openfoam_runner._fault_params(Fault.COARSE_MESH, repaired=False)
    assert p["ny"] == 4


def test_fault_params_solver_short_end_time():
    p = openfoam_runner._fault_params(Fault.SOLVER_SETTING_ERROR, repaired=False)
    assert p["end_time"] == pytest.approx(0.05)


def test_fault_params_none_is_default_good():
    p = openfoam_runner._fault_params(Fault.NONE, repaired=False)
    assert p["ny"] == 40
    assert p["end_time"] == pytest.approx(6.0)
    assert p["wall_type"] == "noSlip"


@pytest.mark.parametrize(
    "fault, repaired",
    [
        (Fault.NONE, False),
        (Fault.BC_MISMATCH, False),
        (Fault.COARSE_MESH, False),
        (Fault.SOLVER_SETTING_ERROR, False),
        (Fault.BC_MISMATCH, True),
    ],
)
def test_generate_case_writes_expected_files(tmp_path, fault, repaired):
    case_dir = tmp_path / "case"
    openfoam_runner.generate_case(case_dir, fault, repaired)
    expected = [
        "system/blockMeshDict",
        "system/controlDict",
        "system/fvSchemes",
        "system/fvSolution",
        "constant/transportProperties",
        "0/U",
        "0/p",
    ]
    for rel in expected:
        f = case_dir / rel
        assert f.exists(), f"missing {rel}"
        assert f.read_text().strip(), f"empty {rel}"


def test_generate_case_bc_mismatch_moving_wall_in_U(tmp_path):
    case_dir = tmp_path / "case_bc"
    openfoam_runner.generate_case(case_dir, Fault.BC_MISMATCH, repaired=False)
    u_text = (case_dir / "0" / "U").read_text()
    # moving-wall fault => translating wall (no-slip violated), not `noSlip`.
    assert "fixedValue" in u_text
    assert "noSlip" not in u_text


def test_generate_case_repaired_uses_noslip_wall(tmp_path):
    case_dir = tmp_path / "case_rep"
    openfoam_runner.generate_case(case_dir, Fault.BC_MISMATCH, repaired=True)
    u_text = (case_dir / "0" / "U").read_text()
    assert "noSlip" in u_text


def test_generate_case_coarse_mesh_ny4_in_blockmesh(tmp_path):
    case_dir = tmp_path / "case_coarse"
    openfoam_runner.generate_case(case_dir, Fault.COARSE_MESH, repaired=False)
    bm = (case_dir / "system" / "blockMeshDict").read_text()
    # 60 x 4 x 1 mesh: the under-resolved wall-normal count must appear.
    assert "(60 4 1)" in bm


def test_generate_case_solver_short_end_time_in_controldict(tmp_path):
    case_dir = tmp_path / "case_solver"
    openfoam_runner.generate_case(case_dir, Fault.SOLVER_SETTING_ERROR, repaired=False)
    cd = (case_dir / "system" / "controlDict").read_text()
    assert "endTime 0.05;" in cd


def test_generate_case_controldict_samples_41_points(tmp_path):
    case_dir = tmp_path / "case_sample"
    openfoam_runner.generate_case(case_dir, Fault.NONE, repaired=False)
    cd = (case_dir / "system" / "controlDict").read_text()
    # canonical 41 wall-normal sample stations, matching the QoI grid.
    assert f"nPoints {config.N_PROFILE_POINTS};" in cd


def test_generate_case_transport_properties_has_nu(tmp_path):
    case_dir = tmp_path / "case_nu"
    openfoam_runner.generate_case(case_dir, Fault.NONE, repaired=False)
    tp = (case_dir / "constant" / "transportProperties").read_text()
    assert str(config.KINEMATIC_VISCOSITY) in tp


def test_generate_case_does_not_write_into_real_data_dir(tmp_path):
    # Sanity: generate_case writes strictly under the caller-provided dir (tmp).
    case_dir = tmp_path / "isolated"
    openfoam_runner.generate_case(case_dir, Fault.NONE, repaired=False)
    written = list(case_dir.rglob("*"))
    assert written
    real_data = Path("/Users/Zhuanz/Desktop/OpenFOAM-AgentBench MiniLab/data")
    for f in written:
        assert real_data not in f.resolve().parents
