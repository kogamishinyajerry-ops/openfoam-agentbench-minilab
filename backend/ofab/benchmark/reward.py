"""Reward signal — the *fuel* Benchmark Feedback hands back to the agent.

Three components, each roughly in [-1, 1]:

  * engineering_reward — driven by the QoI L2 error (the thing that actually
    matters); strongly negative when the profile is wrong, positive when close.
  * efficiency_reward  — rewards reaching a pass in few reruns.
  * experience_reward  — credit for capturing/confirming a reusable lesson.

The decision tells the agent what to do next; suggested_focus points the next
repair at the right knob.
"""
from __future__ import annotations

from ..models import Diagnosis, FailureMode, Reward, Scorecard

_FOCUS: dict[FailureMode, list[str]] = {
    FailureMode.BC_MISMATCH: ["boundary_condition", "qoi_alignment"],
    FailureMode.MESH_TOO_COARSE: ["mesh_resolution", "qoi_alignment"],
    FailureMode.RESIDUAL_NOT_CONVERGED: ["solver_settings", "convergence"],
    FailureMode.NONE: [],
}


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def compute_reward(
    scorecard: Scorecard,
    diagnosis: Diagnosis,
    round_index: int = 0,
    experience_created: bool = False,
) -> Reward:
    qoi = scorecard.qoi_error

    # QoI maps to engineering reward: 0 error -> +0.8, 10% error -> -0.0..,
    # i.e. crosses zero around a 10% L2 error, saturating at +/-0.85.
    engineering = _clip(0.8 * (1.0 - qoi / 0.10), -0.85, 0.85)
    # Fewer reruns is better; the first attempt is mildly positive.
    efficiency = round(0.10 - 0.11 * round_index, 3)
    experience = 0.20 if experience_created else 0.0

    total = round(engineering + efficiency + experience, 3)
    decision = "accept" if scorecard.overall_pass else "repair_and_rerun"
    focus = _FOCUS.get(diagnosis.failure_mode, [])

    return Reward(
        run_id=scorecard.run_id,
        total_reward=total,
        efficiency_reward=efficiency,
        engineering_reward=round(engineering, 3),
        experience_reward=experience,
        decision=decision,
        suggested_focus=focus,
    )
