"""Aggregate metric helpers used to build the workflow comparison cards.

The headline metrics deliberately mix two scopes (matching how the demo is told):

  * efficiency metrics (rerun_count, time_to_pass, final_qoi_error) are measured
    on the **hero fault** repair loop (bc_mismatch);
  * breadth metrics (false_success_detected, experience_records) span the
    **whole experiment** (all injected faults).

Both are computed from the generated RunResults / scorecards, never hard-coded.
"""
from __future__ import annotations

from ..models import EngineeringStatus, ExecutionStatus, RunResult, Scorecard


def count_false_success(scorecards: list[Scorecard]) -> int:
    return sum(1 for s in scorecards if s.false_success)


def auto_repair_success_rate(attempted: int, succeeded: int) -> float:
    return round(succeeded / attempted, 3) if attempted else 0.0


def hero_loop(runs: list[RunResult], hero_fault: str) -> list[RunResult]:
    """The ordered repair loop for the hero fault."""
    loop = [r for r in runs if r.fault.value == hero_fault]
    return sorted(loop, key=lambda r: r.round_index)


def rerun_count(hero_runs: list[RunResult]) -> int:
    """Re-executions beyond the first attempt."""
    if not hero_runs:
        return 0
    return max(r.round_index for r in hero_runs)


def final_qoi_error(hero_runs: list[RunResult]) -> float:
    if not hero_runs:
        return 0.0
    return hero_runs[-1].qoi_error
