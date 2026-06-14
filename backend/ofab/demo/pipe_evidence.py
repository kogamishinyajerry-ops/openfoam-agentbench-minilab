"""Capture real-OpenFOAM evidence for the third case (round-pipe Hagen–Poiseuille).

Runs, on a live OpenFOAM container, the correct pipe case (must match the radial
parabola analytical solution) and the false-success faults the SAME benchmark should
catch. Unlike Couette — where ``coarse_mesh`` is *not applicable* and appears only as
a confirming CHECK — the pipe's HERO fault IS ``coarse_mesh``: a curved radial
parabola is exactly what a too-coarse radial mesh clips, so here it is a real,
benchmark-caught false success classified as MESH_TOO_COARSE. This is the third
case's whole point: the unchanged, case-agnostic benchmark generalises to a new flow
AND a new headline fault, proven on real hardware.

Writes both ``data/real_evidence_pipe.json`` (canonical) and
``frontend/src/data/realEvidencePipe.json`` (the dashboard's copy) from the same
object, so they never drift.
"""
from __future__ import annotations

import json
from pathlib import Path

from .. import paths
from ..benchmark import build_scorecard, diagnose
from ..models import Fault, Workflow

# Repo root: this file is backend/ofab/demo/pipe_evidence.py
_FRONTEND_JSON = (
    Path(__file__).resolve().parents[3]
    / "frontend" / "src" / "data" / "realEvidencePipe.json"
)


def capture_pipe_evidence() -> dict:
    from ..runner import openfoam_pipe as ofp

    container = ofp.detect_container()  # raises OpenFOAMUnavailable if none

    # Correct baseline — must reproduce the radial parabola analytical solution
    # (u_max = 2·U_mean at the axis, no-slip at the wall).
    correct = ofp.run(Workflow.AGENT_PLUS_BENCHMARK, Fault.NONE,
                      repaired=True, run_id="real_pipe_correct")
    evidence = {
        "container": container.name,
        "openfoam_env": container.bashrc,
        "case": "pipe_poiseuille",
        "geometry": "axisymmetric wedge (5°), collapsed axis edge",
        "note": "真实 OpenFOAM（icoFoam）圆管层流运行，用轴对称楔形网格。正确算例复现径向"
                "抛物线解析解（轴线峰值 = 2·U_mean、管壁 no-slip）；三种故障是被同一套基准"
                "检验真实抓到的「假成功」，其中「网格太粗」正是圆管的主场故障（径向抛物线被"
                "粗网格削平）——与 Couette 互为镜像。",
        "correct": {
            "execution_status": correct.execution_status.value,
            "engineering_status": correct.engineering_status.value,
            "qoi_error": correct.qoi_error,
            "residual_final": correct.residual_final,
            "u_peak_sampled": round(max(correct.profile.u), 5),
            "u_peak_analytical": round(max(correct.reference.u), 5),
        },
        "hero_fault": "coarse_mesh",
        "faults": [],
    }

    # False-success faults the benchmark should catch + classify. coarse_mesh is the
    # HERO (the pipe's natural home for it) and leads the list.
    for fault in (Fault.COARSE_MESH, Fault.BC_MISMATCH, Fault.SOLVER_SETTING_ERROR):
        r = ofp.run(Workflow.AGENT_PLUS_BENCHMARK, fault, repaired=False,
                    run_id=f"real_pipe_{fault.value}")
        sc = build_scorecard(r)
        dg = diagnose(r)
        evidence["faults"].append({
            "fault": fault.value,
            "is_hero": fault == Fault.COARSE_MESH,
            "execution_status": r.execution_status.value,
            "engineering_status": r.engineering_status.value,
            "qoi_error": r.qoi_error,
            "residual_final": r.residual_final,
            "features": r.features,
            "false_success_detected": sc.false_success,
            "diagnosis": dg.failure_mode.value,
            "confidence": dg.confidence,
        })

    payload = json.dumps(evidence, indent=2, ensure_ascii=False) + "\n"
    paths.ensure_dirs()
    out = paths.DATA_DIR / "real_evidence_pipe.json"
    out.write_text(payload)
    # Also write the frontend copy from the SAME object, so they can't drift.
    _FRONTEND_JSON.write_text(payload)
    evidence["_path"] = str(out)
    evidence["_frontend_path"] = str(_FRONTEND_JSON)
    return evidence
