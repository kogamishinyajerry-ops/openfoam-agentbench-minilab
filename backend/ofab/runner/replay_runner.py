"""Replay runner — serve pre-generated RunResults from the demo bundle.

This is what makes the demo run with **zero OpenFOAM installed**: the experiment
is generated once (``ofab demo seed``) into ``data/demo_bundle.json`` and the
replay runner reads it back instantly.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..models import RunResult
from ..paths import DATA_DIR

BUNDLE_PATH = DATA_DIR / "demo_bundle.json"


class BundleNotFound(FileNotFoundError):
    pass


def load_bundle(path: str | Path | None = None) -> dict:
    path = Path(path) if path else BUNDLE_PATH
    if not path.exists():
        raise BundleNotFound(
            f"Replay bundle not found at {path}. Run `ofab demo seed` first."
        )
    return json.loads(path.read_text())


def list_runs(path: str | Path | None = None) -> list[RunResult]:
    bundle = load_bundle(path)
    return [RunResult.model_validate(r) for r in bundle.get("runs", [])]


def get_run(run_id: str, path: str | Path | None = None) -> RunResult:
    for run in list_runs(path):
        if run.run_id == run_id:
            return run
    raise KeyError(f"run_id '{run_id}' not found in replay bundle")


def latest_run(workflow: str | None = None, path: str | Path | None = None) -> RunResult:
    runs = list_runs(path)
    if workflow:
        runs = [r for r in runs if r.workflow.value == workflow]
    if not runs:
        raise KeyError("no runs in replay bundle")
    # last attempt of the last fault in the bundle order
    return runs[-1]
