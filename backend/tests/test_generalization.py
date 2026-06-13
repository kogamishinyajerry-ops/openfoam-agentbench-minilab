"""The generalisation thesis, asserted directly as a test.

The project's headline claim is that the benchmark is a *general method*, not a
one-case demo: the SAME unchanged diagnosis routes a fault correctly across
physically different flows. These tests feed runs from both the parabola
(Poiseuille) and the line (Couette) physics into the one `diagnose()` and check
the classifications agree with each flow's ground truth.
"""
from __future__ import annotations

import numpy as np

from ofab import physics
from ofab import physics_couette as pc
from ofab.benchmark import diagnose
from ofab.models import (
    EngineeringStatus,
    ExecutionStatus,
    Fault,
    RunMode,
    RunResult,
    Workflow,
)


def _run(case_id: str, u, ref, feats_fn, *, residual: float = 6.0e-7) -> RunResult:
    u = np.asarray(u, dtype=float)
    ref = np.asarray(ref, dtype=float)
    qoi = physics.l2_relative_error(u, ref)
    feats = feats_fn(u, ref)
    return RunResult(
        run_id=f"gen_{case_id}",
        workflow=Workflow.AGENT_PLUS_BENCHMARK,
        case_id=case_id,
        fault=Fault.BC_MISMATCH,
        mode=RunMode.REPLAY,
        round_index=0,
        execution_status=ExecutionStatus.SUCCESS,
        engineering_status=EngineeringStatus.NEEDS_REPAIR,
        qoi_error=round(float(qoi), 5),
        residual_final=residual,
        runtime_s=1.0,
        features={k: round(float(v), 5) for k, v in feats.items()},
    )


def test_same_diagnose_classifies_bc_fault_in_both_flows():
    """One diagnose(), two different flows -> both BC faults classified BC_MISMATCH
    from the wall-slip feature. This is the generalisation claim, as a test."""
    pois = _run(
        "channel_poiseuille",
        physics.failed_profile("bc_mismatch"),
        physics.analytical_profile(),
        physics.profile_features,
    )
    cou = _run(
        "couette_shear",
        pc.failed_profile(),
        pc.analytical_profile(),
        pc.couette_features,
    )
    assert diagnose(pois).failure_mode.value == "BC_MISMATCH"
    assert diagnose(cou).failure_mode.value == "BC_MISMATCH"


def test_same_diagnose_passes_clean_runs_in_both_flows():
    """The correct solution of each flow (parabola / line) is judged NONE by the
    same function — no false positives across cases."""
    pois = _run(
        "channel_poiseuille",
        physics.analytical_profile(),
        physics.analytical_profile(),
        physics.profile_features,
    )
    cou = _run(
        "couette_shear",
        pc.analytical_profile(),
        pc.analytical_profile(),
        pc.couette_features,
    )
    assert diagnose(pois).failure_mode.value == "NONE"
    assert diagnose(cou).failure_mode.value == "NONE"


def test_couette_bc_fault_is_not_misread_as_mesh():
    """The Couette-specific feature extractor matters: a linear BC fault must not
    trip the mesh gate (peak_deficit / curvature stay ~0 for a line)."""
    cou = _run(
        "couette_shear",
        pc.failed_profile(),
        pc.analytical_profile(),
        pc.couette_features,
    )
    d = diagnose(cou)
    assert d.failure_mode.value == "BC_MISMATCH"
    assert d.failure_mode.value != "MESH_TOO_COARSE"
