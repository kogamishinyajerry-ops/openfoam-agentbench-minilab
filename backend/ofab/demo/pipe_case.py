"""Third-case (round-pipe Hagen–Poiseuille) demonstration builder.

Widens the generalisation proof from "same benchmark, different flow" to "same
benchmark, different flow AND a different HERO fault". It pushes a pipe run — a
curved radial parabola — through the SAME, unchanged :func:`build_scorecard` +
:func:`diagnose`, and shows a false success caught and classified as
MESH_TOO_COARSE from the clipped-peak / faceted-curve features. Returned as the
additive ``bundle["third_case"]``; it does NOT touch the locked hero (Poiseuille)
or Couette numbers.

The honest physics note here is the MIRROR of Couette's: ``coarse_mesh`` does NOT
apply to linear Couette (any mesh reconstructs a line exactly), so the pipe is its
natural home — the framework matches case-appropriate faults to each flow rather
than pretending every fault fits every flow.
"""
from __future__ import annotations

import numpy as np

from .. import config
from .. import physics_pipe as pp
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
    rn = pp.normalized_r()
    return {
        "label": label,
        "y": [round(float(v), 5) for v in rn],
        "u": [round(float(v), 6) for v in np.asarray(u, dtype=float)],
        "qoi_error": round(float(pp.l2_relative_error(np.asarray(u, dtype=float), ref)), 5),
    }


def _pipe_run(
    run_id: str, u: np.ndarray, *, repaired: bool, ref: np.ndarray,
    fault: Fault = Fault.COARSE_MESH,
) -> RunResult:
    """Package a pipe profile into a standard RunResult so the case-agnostic
    benchmark layer can judge it exactly as it judges the other cases."""
    u = np.asarray(u, dtype=float)
    qoi = pp.l2_relative_error(u, ref)
    residual = pp.residual_for(repaired)
    feats = pp.pipe_features(u, ref)
    engineering = (
        EngineeringStatus.PASS
        if (qoi < config.QOI_L2_TOL and residual < config.RESIDUAL_TOL)
        else EngineeringStatus.NEEDS_REPAIR
    )
    rn = pp.normalized_r()
    rs = [round(float(v), 5) for v in rn]
    return RunResult(
        run_id=run_id,
        workflow=Workflow.AGENT_PLUS_BENCHMARK,
        case_id=config.PIPE_CASE_ID,
        fault=fault,
        mode=RunMode.REPLAY,
        round_index=1 if repaired else 0,
        execution_status=ExecutionStatus.SUCCESS,
        engineering_status=engineering,
        qoi_error=round(float(qoi), 5),
        residual_final=residual,
        runtime_s=33.0 if repaired else 31.0,
        profile=VelocityProfile(label="simulated", y=rs, u=[round(float(v), 6) for v in u]),
        reference=VelocityProfile(label="analytical", y=rs, u=[round(float(v), 6) for v in ref]),
        features={k: round(float(v), 5) for k, v in feats.items()},
        notes=(
            "refined radial mesh — curved profile resolved, QoI within tolerance"
            if repaired
            else "under-resolved radial mesh — benchmark flags false success"
        ),
    )


def synthesize_pipe_run(
    fault: Fault, repaired: bool = False, run_id: str | None = None
) -> RunResult:
    """Deterministic synthetic pipe run for the CLI's mock/replay path (the pipe
    analog of mock_runner.run_synthetic). The coarse-mesh fault is modelled exactly
    (under-resolved radial mesh); BC reuses the radial parabola's wall; other faults
    fall back to the clean parabola — use ``--mode openfoam`` for a real solve."""
    rn = pp.normalized_r()
    ref = pp.analytical_profile(rn)
    if repaired:
        u = pp.repaired_profile(rn)
    elif fault == Fault.COARSE_MESH:
        u = pp.failed_profile(rn)
    else:
        u = ref
    rid = run_id or f"pipe_{fault.value}_{'fix' if repaired else 'raw'}"
    return _pipe_run(rid, u, repaired=repaired, ref=ref, fault=fault)


def build_third_case() -> dict:
    """Assemble the additive ``third_case`` bundle field."""
    rn = pp.normalized_r()
    ref = pp.analytical_profile(rn)
    u_failed = pp.failed_profile(rn)
    u_repaired = pp.repaired_profile(rn)

    failed_run = _pipe_run("pipe_mesh_0", u_failed, repaired=False, ref=ref)
    repaired_run = _pipe_run("pipe_mesh_1", u_repaired, repaired=True, ref=ref)

    # The SAME, unchanged benchmark functions judge this different flow + fault.
    sc_failed = build_scorecard(failed_run)
    dg_failed = diagnose(failed_run)
    sc_repaired = build_scorecard(repaired_run)

    peak_deficit = pp.pipe_features(u_failed, ref)["peak_deficit"]

    return {
        "case": {
            "id": config.PIPE_CASE_ID,
            "title": config.PIPE_TITLE,
            "mean_velocity": config.PIPE_MEAN_VELOCITY,
            "radius": config.PIPE_RADIUS,
            "reynolds": round(config.REYNOLDS_PIPE, 1),
            "u_max": config.PIPE_U_MAX,
            "kinematic_viscosity": config.PIPE_KINEMATIC_VISCOSITY,
            "tolerances": {
                "qoi_l2": config.QOI_L2_TOL,
                "residual": config.RESIDUAL_TOL,
                "wall_slip": config.WALL_SLIP_TOL,
            },
        },
        "profiles": {
            "reference": _profile_dict("标准答案（圆管抛物线解析解）", ref, ref),
            "failed": _profile_dict("注入故障后（径向网格太粗）", u_failed, ref),
            "repaired": _profile_dict("修复后（加密网格）", u_repaired, ref),
        },
        "scorecard": sc_failed.model_dump(mode="json"),
        "diagnosis": dg_failed.model_dump(mode="json"),
        "repaired_pass": sc_repaired.overall_pass,
        "peak_deficit_pct": round(peak_deficit * 100, 1),
        "shared_benchmark": True,
        "hero_fault": "coarse_mesh",
        "generalizes_note": (
            "同一套「判卷老师」（scorecard / diagnose 一行未改）换到圆管这第三种流动、"
            "而且换了一种故障——「网格太粗」——照样抓出假成功，并判明是网格分辨率问题。"
        ),
        "fault_fit_note": {
            "fault": "coarse_mesh",
            "label": "网格太粗",
            "reason": (
                "「网格太粗」在 Couette（直线解）里几乎不构成误差、被老实标成「不适用」；"
                "可圆管的解是一条弯曲的抛物线，太粗的径向网格会把中心峰值削平、把曲线压成"
                "折线——所以圆管正是这个故障的「主场」。同一个框架，对不同流动按实际敏感度"
                "匹配不同故障，不硬套。"
            ),
        },
    }
