"""Quantity of Interest — relative L2 error of u(y) vs the analytical parabola."""
from __future__ import annotations

import numpy as np

from .. import physics


def compute_qoi(u_test, u_ref=None) -> float:
    """Relative L2 error of a velocity profile against the analytical solution."""
    return physics.l2_relative_error(np.asarray(u_test, dtype=float), u_ref)


def qoi_report(u_test, u_ref=None) -> dict[str, float]:
    """L2 error plus the shape features the diagnosis layer keys on."""
    u_test = np.asarray(u_test, dtype=float)
    feats = physics.profile_features(u_test, u_ref)
    feats["l2_error"] = round(compute_qoi(u_test, u_ref), 5)
    return feats
