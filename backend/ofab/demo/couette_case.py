"""Second-case (Couette) demonstration builder.

Proves the benchmark *generalises*: it pushes a Couette run — a different flow —
through the SAME, unchanged :func:`build_scorecard` + :func:`diagnose`, and shows
the false success caught and classified as BC_MISMATCH from the stationary-wall
slip feature. Returned as the additive ``bundle["second_case"]``; it does NOT
touch the locked hero (Poiseuille) numbers.

Honest physics note carried in the payload: ``coarse_mesh`` does not apply here —
a linear profile is reconstructed exactly on any mesh — so the framework reasons
about case-appropriate faults rather than pretending every fault fits every flow.
"""
from __future__ import annotations

import numpy as np

from .. import config
from .. import physics_couette as pc
from ..benchmark import build_scorecard, diagnose
from ..models import (
    EngineeringStatus,
    ExecutionStatus,
    Fault,
    RunMode,
    RunResult,
    VelocityProfile,
    Workflow,
)


def _profile_dict(label: str, u: np.ndarray, ref: np.ndarray) -> dict:
    yn = pc.normalized_y()
    return {
        "label": label,
        "y": [round(float(v), 5) for v in yn],
        "u": [round(float(v), 6) for v in np.asarray(u, dtype=float)],
        "qoi_error": round(float(pc.l2_relative_error(np.asarray(u, dtype=float), ref)), 5),
    }


def _couette_run(run_id: str, u: np.ndarray, *, repaired: bool, ref: np.ndarray) -> RunResult:
    """Package a Couette profile into a standard RunResult so the case-agnostic
    benchmark layer can judge it exactly as it judges the hero case."""
    u = np.asarray(u, dtype=float)
    qoi = pc.l2_relative_error(u, ref)
    residual = pc.residual_for(repaired)
    feats = pc.couette_features(u, ref)
    engineering = (
        EngineeringStatus.PASS
        if (qoi < config.QOI_L2_TOL and residual < config.RESIDUAL_TOL)
        else EngineeringStatus.NEEDS_REPAIR
    )
    yn = pc.normalized_y()
    ys = [round(float(v), 5) for v in yn]
    return RunResult(
        run_id=run_id,
        workflow=Workflow.AGENT_PLUS_BENCHMARK,
        case_id=config.COUETTE_CASE_ID,
        fault=Fault.BC_MISMATCH,
        mode=RunMode.REPLAY,
        round_index=1 if repaired else 0,
        execution_status=ExecutionStatus.SUCCESS,
        engineering_status=engineering,
        qoi_error=round(float(qoi), 5),
        residual_final=residual,
        runtime_s=39.0 if repaired else 38.0,
        profile=VelocityProfile(label="simulated", y=ys, u=[round(float(v), 6) for v in u]),
        reference=VelocityProfile(label="analytical", y=ys, u=[round(float(v), 6) for v in ref]),
        features={k: round(float(v), 5) for k, v in feats.items()},
        notes=(
            "no-slip restored at the fixed wall — QoI within tolerance"
            if repaired
            else "injected stationary-wall slip — benchmark flags false success"
        ),
    )


def build_second_case() -> dict:
    """Assemble the additive ``second_case`` bundle field."""
    yn = pc.normalized_y()
    ref = pc.analytical_profile(yn)
    u_failed = pc.failed_profile(yn)
    u_repaired = pc.repaired_profile(yn)

    failed_run = _couette_run("couette_bc_0", u_failed, repaired=False, ref=ref)
    repaired_run = _couette_run("couette_bc_1", u_repaired, repaired=True, ref=ref)

    # The SAME, unchanged benchmark functions judge this different flow.
    sc_failed = build_scorecard(failed_run)
    dg_failed = diagnose(failed_run)
    sc_repaired = build_scorecard(repaired_run)

    wall_slip = pc.couette_features(u_failed, ref)["wall_slip"]

    return {
        "case": {
            "id": config.COUETTE_CASE_ID,
            "title": config.COUETTE_TITLE,
            "lid_velocity": config.COUETTE_LID_VELOCITY,
            "height": config.COUETTE_HEIGHT,
            "reynolds": round(config.REYNOLDS_COUETTE, 1),
            "u_max": config.COUETTE_U_MAX,
            "kinematic_viscosity": config.COUETTE_KINEMATIC_VISCOSITY,
            "tolerances": {
                "qoi_l2": config.QOI_L2_TOL,
                "residual": config.RESIDUAL_TOL,
                "wall_slip": config.WALL_SLIP_TOL,
            },
        },
        "profiles": {
            "reference": _profile_dict("标准答案（线性解析解）", ref, ref),
            "failed": _profile_dict("注入故障后（贴壁滑移）", u_failed, ref),
            "repaired": _profile_dict("修复后", u_repaired, ref),
        },
        "scorecard": sc_failed.model_dump(mode="json"),
        "diagnosis": dg_failed.model_dump(mode="json"),
        "repaired_pass": sc_repaired.overall_pass,
        "wall_slip_pct": round(wall_slip * 100, 1),
        "shared_benchmark": True,
        "generalizes_note": (
            "同一套「判卷老师」（scorecard / diagnose 一行未改）换到一个完全不同的"
            "流动上，照样抓出「贴壁滑移」这类假成功，并判明是边界条件错误。"
        ),
        "not_applicable": {
            "fault": "coarse_mesh",
            "label": "网格太粗",
            "reason": (
                "Couette 的精确解是一条直线，任意疏密的网格用线性插值都能精确还原，"
                "所以「网格太粗」在这个流动里几乎不构成误差——不同算例对不同故障的"
                "敏感度本就不同，基准检验照实反映、不硬套。"
            ),
        },
    }
