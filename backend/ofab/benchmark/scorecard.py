"""Scorecard — turn a finished run into pass/fail checks and detect false success.

This is the layer that separates "the process exited 0" (execution) from
"the engineering result is trustworthy" (residual + QoI). A *false success* is a
run that executed fine yet fails the engineering checks — exactly what ordinary
software testing cannot see.
"""
from __future__ import annotations

from ..models import (
    BenchmarkCheck,
    EngineeringStatus,
    ExecutionStatus,
    RunResult,
    Scorecard,
)
from .contracts import BenchmarkContract


def build_scorecard(run: RunResult, contract: BenchmarkContract | None = None) -> Scorecard:
    contract = contract or BenchmarkContract.from_config()

    exec_ok = run.execution_status == ExecutionStatus.SUCCESS
    residual_ok = run.residual_final < contract.residual_tol
    qoi_ok = run.qoi_error < contract.qoi_l2_tol

    checks = [
        BenchmarkCheck(
            name="execution",
            passed=exec_ok,
            value=1.0 if exec_ok else 0.0,
            threshold=1.0,
            detail="OpenFOAM process completed (exit 0)"
            if exec_ok
            else "solver crashed or diverged",
        ),
        BenchmarkCheck(
            name="residual",
            passed=residual_ok,
            value=run.residual_final,
            threshold=contract.residual_tol,
            detail="final residual below tolerance"
            if residual_ok
            else "residual above tolerance — solution not converged",
        ),
        BenchmarkCheck(
            name="qoi_l2",
            passed=qoi_ok,
            value=run.qoi_error,
            threshold=contract.qoi_l2_tol,
            detail="velocity profile within tolerance of the analytical solution"
            if qoi_ok
            else "velocity profile deviates from the analytical solution",
        ),
    ]

    overall_pass = exec_ok and residual_ok and qoi_ok
    engineering_status = (
        EngineeringStatus.PASS if overall_pass else EngineeringStatus.NEEDS_REPAIR
    )
    # ran "successfully" yet the engineering result is wrong
    false_success = exec_ok and not overall_pass

    return Scorecard(
        run_id=run.run_id,
        workflow=run.workflow,
        fault=run.fault,
        checks=checks,
        qoi_error=run.qoi_error,
        residual_final=run.residual_final,
        execution_status=run.execution_status,
        engineering_status=engineering_status,
        false_success=false_success,
        overall_pass=overall_pass,
    )
