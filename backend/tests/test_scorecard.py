"""Tests for ofab.benchmark.scorecard.build_scorecard.

The project's thesis is that benchmark verification catches *false success*:
a run that exits cleanly yet produces an untrustworthy engineering result.
These tests pin that truth table down against the fixed contract tolerances
(residual_tol = 1e-4, qoi_l2_tol = 0.05) and assert the strict-< boundary so
the suite cannot go green by relaxing the very invariant it is meant to guard.
"""
from __future__ import annotations

import pytest

from ofab import config
from ofab.benchmark.contracts import BenchmarkContract
from ofab.benchmark.scorecard import build_scorecard
from ofab.models import (
    EngineeringStatus,
    ExecutionStatus,
    Fault,
    RunMode,
    RunResult,
    Workflow,
)


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def make_run(
    *,
    execution_status: ExecutionStatus = ExecutionStatus.SUCCESS,
    qoi_error: float,
    residual_final: float,
    run_id: str = "run-test",
    fault: Fault = Fault.NONE,
) -> RunResult:
    """Build a minimal RunResult. engineering_status on the *input* is
    intentionally UNKNOWN — build_scorecard must derive PASS/NEEDS_REPAIR
    itself from residual + qoi, not echo the input field."""
    return RunResult(
        run_id=run_id,
        workflow=Workflow.AGENT_PLUS_BENCHMARK,
        fault=fault,
        mode=RunMode.MOCK,
        execution_status=execution_status,
        engineering_status=EngineeringStatus.UNKNOWN,
        qoi_error=qoi_error,
        residual_final=residual_final,
        runtime_s=1.0,
    )


def check_by_name(scorecard, name):
    matches = [c for c in scorecard.checks if c.name == name]
    assert len(matches) == 1, f"expected exactly one '{name}' check, got {len(matches)}"
    return matches[0]


# Anchor the tests to the documented fixed tolerances.
RESIDUAL_TOL = 1.0e-4
QOI_L2_TOL = 0.05


def test_contract_tolerances_match_config():
    """Sanity: the default contract really carries the fixed constants we assert against."""
    contract = BenchmarkContract.from_config()
    assert contract.residual_tol == pytest.approx(RESIDUAL_TOL)
    assert contract.qoi_l2_tol == pytest.approx(QOI_L2_TOL)
    assert config.RESIDUAL_TOL == pytest.approx(RESIDUAL_TOL)
    assert config.QOI_L2_TOL == pytest.approx(QOI_L2_TOL)


# --------------------------------------------------------------------------- #
# Truth table                                                                 #
# --------------------------------------------------------------------------- #
def test_false_success_exec_ok_residual_ok_qoi_bad():
    """Row 1: process exited 0, residual converged, but QoI deviates ->
    the run *looks* successful yet is engineering-wrong = false success."""
    sc = build_scorecard(make_run(qoi_error=0.18, residual_final=6e-7))

    assert sc.execution_status == ExecutionStatus.SUCCESS
    assert sc.overall_pass is False
    assert sc.false_success is True
    assert sc.engineering_status == EngineeringStatus.NEEDS_REPAIR

    assert check_by_name(sc, "execution").passed is True
    assert check_by_name(sc, "residual").passed is True
    assert check_by_name(sc, "qoi_l2").passed is False


def test_all_ok_is_pass_not_false_success():
    """Row 2: everything within tolerance -> PASS, overall_pass, no false success."""
    sc = build_scorecard(make_run(qoi_error=0.021, residual_final=6e-7))

    assert sc.overall_pass is True
    assert sc.false_success is False
    assert sc.engineering_status == EngineeringStatus.PASS

    assert check_by_name(sc, "execution").passed is True
    assert check_by_name(sc, "residual").passed is True
    assert check_by_name(sc, "qoi_l2").passed is True


def test_residual_above_tol_fails_even_when_qoi_ok():
    """Row 3: residual above tolerance fails the run even though QoI is fine.
    exec_ok still holds, so this is also a false success."""
    sc = build_scorecard(make_run(qoi_error=0.01, residual_final=8e-3))

    assert sc.overall_pass is False
    assert sc.false_success is True
    assert sc.engineering_status == EngineeringStatus.NEEDS_REPAIR

    assert check_by_name(sc, "execution").passed is True
    assert check_by_name(sc, "residual").passed is False
    assert check_by_name(sc, "qoi_l2").passed is True


def test_exec_failed_is_not_false_success():
    """A crash is an honest failure, not a false success: exec_ok is False,
    so false_success must be False regardless of the (meaningless) metrics."""
    sc = build_scorecard(
        make_run(
            execution_status=ExecutionStatus.FAILED,
            qoi_error=0.5,
            residual_final=1.0,
        )
    )

    assert sc.overall_pass is False
    assert sc.false_success is False
    assert sc.engineering_status == EngineeringStatus.NEEDS_REPAIR
    assert check_by_name(sc, "execution").passed is False


# --------------------------------------------------------------------------- #
# checks list structure                                                       #
# --------------------------------------------------------------------------- #
def test_checks_contains_exactly_the_three_named_checks():
    sc = build_scorecard(make_run(qoi_error=0.021, residual_final=6e-7))
    names = [c.name for c in sc.checks]
    assert names == ["execution", "residual", "qoi_l2"]


def test_check_values_and_thresholds_mirror_inputs():
    qoi = 0.18
    res = 6e-7
    sc = build_scorecard(make_run(qoi_error=qoi, residual_final=res))

    residual_check = check_by_name(sc, "residual")
    assert residual_check.value == pytest.approx(res)
    assert residual_check.threshold == pytest.approx(RESIDUAL_TOL)

    qoi_check = check_by_name(sc, "qoi_l2")
    assert qoi_check.value == pytest.approx(qoi)
    assert qoi_check.threshold == pytest.approx(QOI_L2_TOL)

    exec_check = check_by_name(sc, "execution")
    assert exec_check.value == pytest.approx(1.0)
    assert exec_check.threshold == pytest.approx(1.0)


def test_scorecard_metrics_echo_run():
    run = make_run(qoi_error=0.087, residual_final=6e-7, run_id="run-xyz", fault=Fault.BC_MISMATCH)
    sc = build_scorecard(run)
    assert sc.run_id == "run-xyz"
    assert sc.fault == Fault.BC_MISMATCH
    assert sc.workflow == Workflow.AGENT_PLUS_BENCHMARK
    assert sc.qoi_error == pytest.approx(0.087)
    assert sc.residual_final == pytest.approx(6e-7)
    assert sc.execution_status == ExecutionStatus.SUCCESS


# --------------------------------------------------------------------------- #
# Strict-< boundary: qoi exactly at tolerance must NOT pass                    #
# --------------------------------------------------------------------------- #
def test_qoi_exactly_at_tolerance_does_not_pass():
    """qoi == 0.05 is on the boundary. The contract is `qoi < tol` (strict),
    so exactly-at-tolerance must FAIL the QoI check and the run overall."""
    sc = build_scorecard(make_run(qoi_error=QOI_L2_TOL, residual_final=6e-7))

    assert check_by_name(sc, "qoi_l2").passed is False
    assert sc.overall_pass is False
    assert sc.false_success is True
    assert sc.engineering_status == EngineeringStatus.NEEDS_REPAIR


def test_qoi_just_below_tolerance_passes():
    """Just under the boundary must pass — confirms the boundary is at 0.05,
    not somewhere looser, so the strict-< test above is meaningful."""
    sc = build_scorecard(make_run(qoi_error=QOI_L2_TOL - 1e-9, residual_final=6e-7))
    assert check_by_name(sc, "qoi_l2").passed is True
    assert sc.overall_pass is True


def test_residual_exactly_at_tolerance_does_not_pass():
    """Same strict-< rule on residual: residual == tol must fail."""
    sc = build_scorecard(make_run(qoi_error=0.01, residual_final=RESIDUAL_TOL))
    assert check_by_name(sc, "residual").passed is False
    assert sc.overall_pass is False
