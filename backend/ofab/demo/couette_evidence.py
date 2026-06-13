"""Capture real-OpenFOAM evidence for the second case (Couette / shear flow).

Runs, on a live OpenFOAM container, the correct Couette case (must match the
linear analytical solution), the false-success faults the benchmark should catch
(BC mismatch + early-stopped solver), and a coarse-mesh CHECK that empirically
confirms the honest "not applicable" claim — a linear profile is reconstructed
exactly even on a very coarse mesh, so coarse_mesh does not manifest as error.

Writes both ``data/real_evidence_couette.json`` (canonical) and
``frontend/src/data/realEvidenceCouette.json`` (the dashboard's copy) from the
same object, so they never drift.
"""
from __future__ import annotations

import json
from pathlib import Path

from .. import paths
from ..benchmark import build_scorecard, diagnose
from ..models import Fault, Workflow

# Repo root: this file is backend/ofab/demo/couette_evidence.py
_FRONTEND_JSON = Path(__file__).resolve().parents[3] / "frontend" / "src" / "data" / "realEvidenceCouette.json"


def capture_couette_evidence() -> dict:
    from ..runner import openfoam_couette as ofc

    container = ofc.detect_container()  # raises OpenFOAMUnavailable if none

    # Correct baseline — must reproduce the linear analytical solution.
    correct = ofc.run(Workflow.AGENT_PLUS_BENCHMARK, Fault.NONE,
                      repaired=True, run_id="real_couette_correct")
    evidence = {
        "container": container.name,
        "openfoam_env": container.bashrc,
        "case": "couette_shear",
        "note": "真实 OpenFOAM（icoFoam）剪切流运行。正确算例复现线性解析解；BC/求解器"
                "故障是被同一套基准检验真实抓到的「假成功」；粗网格一项印证「不适用」"
                "——线性剖面在任意网格上都精确还原。",
        "correct": {
            "execution_status": correct.execution_status.value,
            "engineering_status": correct.engineering_status.value,
            "qoi_error": correct.qoi_error,
            "residual_final": correct.residual_final,
            "u_top_sampled": round(max(correct.profile.u), 5),
            "u_top_analytical": round(max(correct.reference.u), 5),
        },
        "faults": [],
    }

    # False-success faults the benchmark should catch + classify.
    for fault in (Fault.BC_MISMATCH, Fault.SOLVER_SETTING_ERROR):
        r = ofc.run(Workflow.AGENT_PLUS_BENCHMARK, fault, repaired=False,
                    run_id=f"real_couette_{fault.value}")
        sc = build_scorecard(r)
        dg = diagnose(r)
        evidence["faults"].append({
            "fault": fault.value,
            "execution_status": r.execution_status.value,
            "engineering_status": r.engineering_status.value,
            "qoi_error": r.qoi_error,
            "residual_final": r.residual_final,
            "features": r.features,
            "false_success_detected": sc.false_success,
            "diagnosis": dg.failure_mode.value,
            "confidence": dg.confidence,
        })

    # Coarse-mesh CHECK — not a fault here: a linear profile is exact on any mesh,
    # so the error stays ~0 and the run passes. This empirically backs the honest
    # "coarse_mesh not applicable to Couette" note carried in the bundle.
    coarse = ofc.run(Workflow.AGENT_PLUS_BENCHMARK, Fault.COARSE_MESH,
                     repaired=False, run_id="real_couette_coarse")
    sc_coarse = build_scorecard(coarse)
    evidence["coarse_mesh_check"] = {
        "qoi_error": coarse.qoi_error,
        "engineering_status": coarse.engineering_status.value,
        "overall_pass": sc_coarse.overall_pass,
        "note": "粗网格（ny=4）下误差仍≈0、照样合格——线性剖面不受网格疏密影响，"
                "印证「网格太粗」对剪切流不适用。",
    }

    payload = json.dumps(evidence, indent=2, ensure_ascii=False) + "\n"
    paths.ensure_dirs()
    out = paths.DATA_DIR / "real_evidence_couette.json"
    out.write_text(payload)
    # Also write the frontend copy from the SAME object, so they can't drift.
    _FRONTEND_JSON.write_text(payload)
    evidence["_path"] = str(out)
    evidence["_frontend_path"] = str(_FRONTEND_JSON)
    return evidence
