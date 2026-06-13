"""Benchmark contract — tolerances + QoI definition for the hero case.

Loaded from ``benchmarks/contracts/channel_poiseuille.yaml`` when present, with
a fallback to ``ofab.config`` so the pipeline runs even without the YAML on disk.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .. import config
from ..paths import CONTRACTS_DIR


@dataclass
class BenchmarkContract:
    case_id: str
    qoi_name: str
    qoi_l2_tol: float
    residual_tol: float
    wall_slip_tol: float
    reference_csv: str | None = None

    @classmethod
    def from_config(cls) -> "BenchmarkContract":
        return cls(
            case_id=config.CASE_ID,
            qoi_name="velocity_profile_l2_error",
            qoi_l2_tol=config.QOI_L2_TOL,
            residual_tol=config.RESIDUAL_TOL,
            wall_slip_tol=config.WALL_SLIP_TOL,
            reference_csv="channel_poiseuille_reference.csv",
        )

    @classmethod
    def load(cls, path: str | Path | None = None) -> "BenchmarkContract":
        if path is None:
            path = CONTRACTS_DIR / f"{config.CASE_ID}.yaml"
        path = Path(path)
        if not path.exists():
            return cls.from_config()
        data = yaml.safe_load(path.read_text()) or {}
        tol = data.get("tolerances", {})
        qoi = data.get("qoi", {})
        return cls(
            case_id=data.get("case_id", config.CASE_ID),
            qoi_name=qoi.get("name", "velocity_profile_l2_error"),
            qoi_l2_tol=float(tol.get("qoi_l2", config.QOI_L2_TOL)),
            residual_tol=float(tol.get("residual", config.RESIDUAL_TOL)),
            wall_slip_tol=float(tol.get("wall_slip", config.WALL_SLIP_TOL)),
            reference_csv=data.get("reference", {}).get("path"),
        )
