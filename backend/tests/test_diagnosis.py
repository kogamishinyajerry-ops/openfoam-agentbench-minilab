"""Tests for ofab.benchmark.diagnosis.diagnose.

These assert *real invariants* of the rule-based failure diagnoser:
RunResults are built from genuine physics features (no hand-typed fixtures),
and we check the gate-priority ordering, the low-confidence mesh fallback,
and the confidence/evidence/repair contract. Numbers are anchored to
ofab.config tolerances and ofab.physics computed features.
"""
from __future__ import annotations

import numpy as np
import pytest

from ofab import config, physics
from ofab.benchmark.contracts import BenchmarkContract
from ofab.benchmark.diagnosis import diagnose
from ofab.models import (
    ExecutionStatus,
    EngineeringStatus,
    Fault,
    FailureMode,
    RunMode,
    RunResult,
    Workflow,
)

# Shared reference geometry / analytical baseline.
YN = physics.normalized_y()
REF = physics.analytical_profile()


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #
def _make_run(
    profile_u: np.ndarray,
    *,
    residual: float,
    fault: Fault,
    run_id: str = "r-test",
    include_features: bool = True,
) -> RunResult:
    """Build a RunResult from a real velocity profile array.

    qoi_error and features are *computed* from physics, never hand-typed, so the
    test exercises the same numbers the production pipeline would feed diagnose.
    """
    qoi = physics.l2_relative_error(profile_u, REF)
    feats = physics.profile_features(profile_u, REF) if include_features else {}
    return RunResult(
        run_id=run_id,
        workflow=Workflow.AGENT_PLUS_BENCHMARK,
        fault=fault,
        mode=RunMode.MOCK,
        execution_status=ExecutionStatus.SUCCESS,
        engineering_status=EngineeringStatus.NEEDS_REPAIR,
        qoi_error=qoi,
        residual_final=residual,
        runtime_s=1.0,
        features=feats,
    )


GOOD_RESID = physics.residual_for("bc_mismatch", repaired=True)  # 6e-7, below tol
BAD_RESID = physics.residual_for("solver_setting_error", repaired=False)  # 8e-3


# --------------------------------------------------------------------------- #
# Per-fault classification (features from real physics)                       #
# --------------------------------------------------------------------------- #
def test_bc_mismatch_classified_as_bc_mismatch():
    """Partial-slip profile (slip=0.283) -> BC_MISMATCH. Residual is healthy so
    the residual gate does not fire; the wall-slip gate does."""
    u = physics.failed_profile("bc_mismatch")
    run = _make_run(u, residual=GOOD_RESID, fault=Fault.BC_MISMATCH)
    # Sanity: this is the real high-slip fingerprint.
    assert run.features["wall_slip"] == pytest.approx(0.283, abs=1e-3)
    assert run.features["wall_slip"] >= config.WALL_SLIP_TOL
    assert run.qoi_error == pytest.approx(0.184, abs=0.01)

    diag = diagnose(run)
    assert diag.failure_mode is FailureMode.BC_MISMATCH
    assert diag.run_id == run.run_id


def test_coarse_mesh_classified_as_mesh_too_coarse():
    """Coarse-mesh profile: ~zero wall slip, residual ok, qoi just over 5%
    -> MESH_TOO_COARSE via the interior-resolution gate."""
    u = physics.failed_profile("coarse_mesh")
    run = _make_run(u, residual=GOOD_RESID, fault=Fault.COARSE_MESH)
    assert run.features["wall_slip"] < config.WALL_SLIP_TOL
    assert run.features["peak_deficit"] > 0.0  # cell-centre clipping clips the peak
    assert run.qoi_error == pytest.approx(0.0547, abs=0.005)
    assert run.qoi_error >= config.QOI_L2_TOL  # fails the qoi check

    diag = diagnose(run)
    assert diag.failure_mode is FailureMode.MESH_TOO_COARSE


def test_solver_high_residual_classified_as_residual_not_converged():
    """Solver-setting fault carries an un-converged residual (8e-3 >> 1e-4).
    The residual gate fires first -> RESIDUAL_NOT_CONVERGED, regardless of the
    profile shape (which has zero wall slip here)."""
    u = physics.failed_profile("solver_setting_error")
    run = _make_run(u, residual=BAD_RESID, fault=Fault.SOLVER_SETTING_ERROR)
    assert run.residual_final >= config.RESIDUAL_TOL
    assert run.features["wall_slip"] < config.WALL_SLIP_TOL

    diag = diagnose(run)
    assert diag.failure_mode is FailureMode.RESIDUAL_NOT_CONVERGED


def test_passing_run_classified_as_none():
    """Repaired profile: qoi ~2.1% < 5% and residual healthy -> NONE / 0.95."""
    u = physics.repaired_profile("bc_mismatch")
    run = _make_run(u, residual=GOOD_RESID, fault=Fault.BC_MISMATCH)
    assert run.qoi_error < config.QOI_L2_TOL
    assert run.residual_final < config.RESIDUAL_TOL

    diag = diagnose(run)
    assert diag.failure_mode is FailureMode.NONE
    assert diag.confidence == pytest.approx(0.95)
    # NONE => no repair work to suggest.
    assert diag.suggested_repair == []
    # Evidence is still populated (status + the two in-tolerance lines).
    assert len(diag.evidence) >= 2


# --------------------------------------------------------------------------- #
# Gate priority: residual gate beats wall-slip gate                           #
# --------------------------------------------------------------------------- #
def test_residual_gate_wins_over_high_wall_slip():
    """Pathological mix: high wall slip (would be BC_MISMATCH) AND a residual
    above threshold. The residual gate has top priority, so the verdict must be
    RESIDUAL_NOT_CONVERGED, not BC_MISMATCH."""
    u = physics.failed_profile("bc_mismatch")  # wall_slip ~0.283, well over tol
    run = _make_run(u, residual=BAD_RESID, fault=Fault.BC_MISMATCH)
    assert run.features["wall_slip"] >= config.WALL_SLIP_TOL  # BC gate would fire
    assert run.residual_final >= config.RESIDUAL_TOL          # residual gate fires

    diag = diagnose(run)
    assert diag.failure_mode is FailureMode.RESIDUAL_NOT_CONVERGED


def test_residual_gate_at_threshold_boundary():
    """Boundary: residual == tol is NOT below tol (strict `<`), so residual_ok
    is False and the residual gate still fires even with a clean profile."""
    u = physics.repaired_profile("bc_mismatch")  # would otherwise be NONE
    run = _make_run(u, residual=config.RESIDUAL_TOL, fault=Fault.BC_MISMATCH)
    diag = diagnose(run)
    assert diag.failure_mode is FailureMode.RESIDUAL_NOT_CONVERGED


# --------------------------------------------------------------------------- #
# Low-confidence mesh fallback: empty features + failing qoi                   #
# --------------------------------------------------------------------------- #
def test_empty_features_failing_qoi_is_low_confidence_mesh():
    """No profile features at all + residual ok + qoi over tolerance ->
    MESH_TOO_COARSE at the explicit 0.4 low-confidence fallback."""
    u = physics.failed_profile("coarse_mesh")  # qoi ~6.25% > 5%
    run = _make_run(
        u, residual=GOOD_RESID, fault=Fault.COARSE_MESH, include_features=False
    )
    assert run.features == {}
    assert run.qoi_error >= config.QOI_L2_TOL

    diag = diagnose(run)
    assert diag.failure_mode is FailureMode.MESH_TOO_COARSE
    assert diag.confidence == pytest.approx(0.4)


def test_empty_features_passing_qoi_is_none_not_mesh():
    """Empty features but qoi within tolerance + residual ok -> the NONE gate
    wins before the empty-features fallback is ever reached."""
    u = physics.repaired_profile("bc_mismatch")  # qoi ~2.1% < 5%
    run = _make_run(
        u, residual=GOOD_RESID, fault=Fault.BC_MISMATCH, include_features=False
    )
    diag = diagnose(run)
    assert diag.failure_mode is FailureMode.NONE


# --------------------------------------------------------------------------- #
# Universal contract: confidence range, evidence/repair non-empty             #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "fault_key, residual, expected_mode",
    [
        ("bc_mismatch", GOOD_RESID, FailureMode.BC_MISMATCH),
        ("coarse_mesh", GOOD_RESID, FailureMode.MESH_TOO_COARSE),
        ("solver_setting_error", BAD_RESID, FailureMode.RESIDUAL_NOT_CONVERGED),
    ],
)
def test_failure_cases_have_nonempty_evidence_and_repair(
    fault_key, residual, expected_mode
):
    u = physics.failed_profile(fault_key)
    run = _make_run(u, residual=residual, fault=Fault.BC_MISMATCH)
    diag = diagnose(run)
    assert diag.failure_mode is expected_mode
    # Every non-NONE diagnosis must carry actionable evidence AND a repair plan.
    assert diag.evidence, "evidence must be non-empty"
    assert diag.suggested_repair, "failure diagnosis must suggest a repair"


@pytest.mark.parametrize(
    "fault_key, residual, include_features",
    [
        ("bc_mismatch", GOOD_RESID, True),
        ("coarse_mesh", GOOD_RESID, True),
        ("coarse_mesh", GOOD_RESID, False),  # empty-features fallback
        ("solver_setting_error", BAD_RESID, True),
        ("solver_setting_error", BAD_RESID, False),
    ],
)
def test_confidence_always_in_unit_interval(fault_key, residual, include_features):
    """confidence is a probability in (0, 1] for every reachable branch,
    including the passing/NONE case."""
    u = physics.failed_profile(fault_key)
    run = _make_run(
        u, residual=residual, fault=Fault.BC_MISMATCH, include_features=include_features
    )
    diag = diagnose(run)
    assert 0.0 < diag.confidence <= 1.0


def test_none_case_confidence_in_unit_interval():
    u = physics.repaired_profile("bc_mismatch")
    run = _make_run(u, residual=GOOD_RESID, fault=Fault.BC_MISMATCH)
    diag = diagnose(run)
    assert 0.0 < diag.confidence <= 1.0


# --------------------------------------------------------------------------- #
# Determinism + contract injection                                            #
# --------------------------------------------------------------------------- #
def test_diagnose_is_deterministic():
    """Same RunResult diagnosed twice -> identical verdict (no hidden state)."""
    u = physics.failed_profile("bc_mismatch")
    run = _make_run(u, residual=GOOD_RESID, fault=Fault.BC_MISMATCH)
    d1 = diagnose(run)
    d2 = diagnose(run)
    assert d1.failure_mode is d2.failure_mode
    assert d1.confidence == d2.confidence
    assert d1.evidence == d2.evidence
    assert d1.suggested_repair == d2.suggested_repair


def test_explicit_contract_matches_default_from_config():
    """Passing the from_config contract explicitly gives the same result as
    letting diagnose build its own default."""
    u = physics.failed_profile("bc_mismatch")
    run = _make_run(u, residual=GOOD_RESID, fault=Fault.BC_MISMATCH)
    contract = BenchmarkContract.from_config()
    assert contract.qoi_l2_tol == config.QOI_L2_TOL
    assert contract.residual_tol == config.RESIDUAL_TOL
    assert contract.wall_slip_tol == config.WALL_SLIP_TOL

    d_default = diagnose(run)
    d_explicit = diagnose(run, contract=contract)
    assert d_default.failure_mode is d_explicit.failure_mode
    assert d_default.confidence == d_explicit.confidence
