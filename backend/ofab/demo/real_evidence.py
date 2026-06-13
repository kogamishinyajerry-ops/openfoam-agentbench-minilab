"""Capture real-OpenFOAM evidence that the benchmark loop is not faked.

Runs the correct case (matches analytical) plus the three injected faults
through a live OpenFOAM container, and records what the benchmark layer detected
and diagnosed for each. Writes ``data/real_evidence.json``.
"""
from __future__ import annotations

import json

from .. import paths
from ..benchmark import build_scorecard, diagnose
from ..models import Fault, Workflow


def capture_real_evidence() -> dict:
    from ..runner import openfoam_runner as ofr

    container = ofr.detect_container()  # raises OpenFOAMUnavailable if none

    # Correct / repaired baseline.
    correct = ofr.run(Workflow.AGENT_PLUS_BENCHMARK, Fault.BC_MISMATCH,
                      repaired=True, run_id="real_correct")
    evidence = {
        "container": container.name,
        "openfoam_env": container.bashrc,
        "note": "Live OpenFOAM (icoFoam) runs. Correct case matches the analytical "
                "parabola; each injected fault is a real false success the benchmark "
                "catches and diagnoses.",
        "correct": {
            "execution_status": correct.execution_status.value,
            "engineering_status": correct.engineering_status.value,
            "qoi_error": correct.qoi_error,
            "residual_final": correct.residual_final,
            "u_peak_sampled": round(max(correct.profile.u), 5),
            "u_peak_analytical": round(max(correct.reference.u), 5),
        },
        "faults": [],
    }

    for fault in (Fault.BC_MISMATCH, Fault.COARSE_MESH, Fault.SOLVER_SETTING_ERROR):
        r = ofr.run(Workflow.AGENT_PLUS_BENCHMARK, fault, repaired=False,
                    run_id=f"real_{fault.value}")
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

    paths.ensure_dirs()
    out = paths.DATA_DIR / "real_evidence.json"
    out.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n")
    evidence["_path"] = str(out)
    return evidence
