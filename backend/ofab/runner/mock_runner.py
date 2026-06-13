"""Mock runner — synthesize a RunResult from the physics model.

No OpenFOAM, no randomness beyond the seeded fault noise. This is what builds the
replay bundle and what powers ``ofab run --mode mock``. Execution always
"succeeds" (exit 0) — the whole point of the demo is that engineering failure
hides behind a clean exit code.
"""
from __future__ import annotations

import numpy as np

from .. import config, physics
from ..models import (
    EngineeringStatus,
    ExecutionStatus,
    Fault,
    RunMode,
    RunResult,
    VelocityProfile,
    Workflow,
)


def profile_model(label: str, u) -> VelocityProfile:
    yn = physics.normalized_y()
    return VelocityProfile(
        label=label,
        y=[round(float(v), 5) for v in yn],
        u=[round(float(v), 6) for v in np.asarray(u, dtype=float)],
    )


def build_run(
    run_id: str,
    workflow: Workflow,
    fault: Fault,
    *,
    u_profile,
    residual: float,
    runtime_s: float,
    round_index: int = 0,
    mode: RunMode = RunMode.MOCK,
    has_benchmark: bool = True,
    notes: str = "",
) -> RunResult:
    """Package a velocity profile into a full RunResult, computing QoI/features."""
    u_ref = physics.analytical_profile()
    u_arr = np.asarray(u_profile, dtype=float)
    qoi = physics.l2_relative_error(u_arr, u_ref)
    feats = physics.profile_features(u_arr, u_ref)

    execution_status = ExecutionStatus.SUCCESS  # always runs
    if has_benchmark:
        engineering_status = (
            EngineeringStatus.PASS
            if (qoi < config.QOI_L2_TOL and residual < config.RESIDUAL_TOL)
            else EngineeringStatus.NEEDS_REPAIR
        )
    else:
        # No benchmark -> the agent genuinely cannot tell if it is right.
        engineering_status = EngineeringStatus.UNKNOWN

    return RunResult(
        run_id=run_id,
        workflow=workflow,
        case_id=config.CASE_ID,
        fault=fault,
        mode=mode,
        round_index=round_index,
        execution_status=execution_status,
        engineering_status=engineering_status,
        qoi_error=round(float(qoi), 5),
        residual_final=residual,
        runtime_s=round(float(runtime_s), 2),
        profile=profile_model("simulated", u_arr),
        reference=profile_model("analytical", u_ref),
        features={k: round(float(v), 5) for k, v in feats.items()},
        notes=notes,
    )


def run_synthetic(
    run_id: str,
    workflow: Workflow,
    fault: Fault,
    *,
    repaired: bool = False,
    slip: float | None = None,
    round_index: int = 0,
    runtime_s: float = 42.0,
    mode: RunMode = RunMode.MOCK,
    has_benchmark: bool = True,
    notes: str = "",
) -> RunResult:
    """Convenience: synthesize a run for a (fault, state) directly from physics.

    ``slip`` overrides the wall-slip fraction to represent intermediate states of
    a guided repair loop. ``repaired`` produces the near-analytical end state.
    """
    yn = physics.normalized_y()
    if repaired:
        u = physics.repaired_profile(fault.value, yn)
        residual = physics.residual_for(fault.value, repaired=True)
    elif slip is not None:
        u = physics.bc_profile(slip, yn)
        residual = physics.residual_for(fault.value, repaired=True)
    elif fault == Fault.NONE:
        u = physics.analytical_profile(yn)
        residual = physics.residual_for("none", repaired=True)
    else:
        u = physics.failed_profile(fault.value, yn)
        residual = physics.residual_for(fault.value, repaired=False)

    return build_run(
        run_id,
        workflow,
        fault,
        u_profile=u,
        residual=residual,
        runtime_s=runtime_s,
        round_index=round_index,
        mode=mode,
        has_benchmark=has_benchmark,
        notes=notes,
    )
