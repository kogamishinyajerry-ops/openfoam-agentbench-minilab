"""Canonical repository paths. Importable from anywhere in the package."""
from __future__ import annotations

from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent          # backend/ofab
BACKEND_DIR = PKG_DIR.parent                        # backend
REPO_ROOT = BACKEND_DIR.parent                      # project root

BENCHMARKS_DIR = REPO_ROOT / "benchmarks"
CONTRACTS_DIR = BENCHMARKS_DIR / "contracts"
REFERENCES_DIR = BENCHMARKS_DIR / "references"
INJECTIONS_DIR = BENCHMARKS_DIR / "failure_injections"

EXPERIMENTS_DIR = REPO_ROOT / "experiments"
OPENFOAM_CASES_DIR = REPO_ROOT / "openfoam_cases"

FRONTEND_DATA_DIR = REPO_ROOT / "frontend" / "src" / "data"

# Generated artifacts
DATA_DIR = REPO_ROOT / "data"          # replay/demo bundle
RUNS_DIR = REPO_ROOT / "runs"          # per-run outputs


def ensure_dirs() -> None:
    for d in (DATA_DIR, RUNS_DIR, FRONTEND_DATA_DIR):
        d.mkdir(parents=True, exist_ok=True)
