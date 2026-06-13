"""FastAPI surface — serves the seeded replay bundle to the dashboard.

    uvicorn ofab.api:app --reload --port 8000

All GET endpoints read the bundle produced by ``ofab demo seed``. POST /run
executes a fresh run (mock / replay / real OpenFOAM) through the benchmark layer.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .benchmark import build_scorecard, compute_reward, diagnose
from .models import Fault, RunMode, Workflow
from .runner import mock_runner
from .runner.replay_runner import BundleNotFound, load_bundle

app = FastAPI(
    title="OpenFOAM-AgentBench MiniLab",
    description="Benchmark-Feedback CFD agent loop — replay API",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _bundle() -> dict:
    try:
        return load_bundle()
    except BundleNotFound as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/health")
def health() -> dict:
    try:
        load_bundle()
        seeded = True
    except BundleNotFound:
        seeded = False
    return {"status": "ok", "seeded": seeded}


@app.get("/api/demo/summary")
def summary() -> dict:
    b = _bundle()
    return {
        "case": b["case"],
        "story": b["story"],
        "mode": b["mode"],
        "workflows": b["workflows"],
        "comparison": b["comparison"],
    }


@app.get("/api/demo/timeline")
def timeline() -> dict:
    return {"timeline": _bundle()["timeline"]}


@app.get("/api/demo/profile")
def profile() -> dict:
    return {"profiles": _bundle()["profiles"]}


@app.get("/api/demo/metrics")
def metrics() -> dict:
    b = _bundle()
    return {"workflows": b["workflows"], "comparison": b["comparison"]}


@app.get("/api/demo/diagnosis")
def diagnosis() -> dict:
    b = _bundle()
    return {"diagnosis": b["diagnosis"], "diagnoses": b["diagnoses"],
            "reward": b["reward"]}


@app.get("/api/demo/memory")
def memory() -> dict:
    return {"experience": _bundle()["experience"]}


@app.get("/api/demo/flywheel")
def flywheel() -> dict:
    """The flywheel payoff: a recurring fault recalls a stored lesson and is fixed
    in fewer rounds (first vs second encounter)."""
    return {"flywheel": _bundle()["flywheel"]}


@app.get("/api/demo/bundle")
def bundle() -> dict:
    return _bundle()


class RunRequest(BaseModel):
    fault: Fault = Fault.BC_MISMATCH
    mode: RunMode = RunMode.MOCK
    repaired: bool = False
    workflow: Workflow = Workflow.AGENT_PLUS_BENCHMARK


@app.post("/api/demo/run")
def run(req: RunRequest) -> dict:
    has_bench = req.workflow == Workflow.AGENT_PLUS_BENCHMARK
    if req.mode == RunMode.OPENFOAM:
        from .runner import openfoam_runner
        try:
            run_result = openfoam_runner.run(req.workflow, req.fault,
                                             repaired=req.repaired, has_benchmark=has_bench)
        except openfoam_runner.OpenFOAMUnavailable as exc:
            run_result = mock_runner.run_synthetic(
                f"mock_{req.fault.value}", req.workflow, req.fault,
                repaired=req.repaired, has_benchmark=has_bench,
                notes=f"openfoam unavailable: {exc}")
    else:
        run_result = mock_runner.run_synthetic(
            f"{req.mode.value}_{req.fault.value}", req.workflow, req.fault,
            repaired=req.repaired, mode=req.mode, has_benchmark=has_bench)

    out: dict = {"run": run_result.model_dump()}
    if has_bench:
        sc = build_scorecard(run_result)
        dg = diagnose(run_result)
        rw = compute_reward(sc, dg, round_index=run_result.round_index,
                            experience_created=not sc.overall_pass)
        out["scorecard"] = sc.model_dump()
        out["diagnosis"] = dg.model_dump()
        out["reward"] = rw.model_dump()
    return out
