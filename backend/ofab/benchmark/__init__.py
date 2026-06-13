"""Benchmark Feedback layer.

Turns a finished OpenFOAM run into structured engineering feedback:
QoI -> scorecard -> diagnosis -> reward. Pure functions, no I/O.
"""
from .contracts import BenchmarkContract
from .qoi import compute_qoi, qoi_report
from .scorecard import build_scorecard
from .diagnosis import diagnose
from .reward import compute_reward

__all__ = [
    "BenchmarkContract",
    "compute_qoi",
    "qoi_report",
    "build_scorecard",
    "diagnose",
    "compute_reward",
]
