"""Plane Couette (shear-driven) analytics + BC-mismatch fault synthesis.

The second analytically-verifiable case. The lower wall is stationary (no-slip)
and the upper wall (lid) is dragged at a constant speed, so the exact steady
solution is **linear**:

    u(y) = U_lid * (y / H)        (u = 0 at the fixed wall, u = U_lid at the lid)

This mirrors :mod:`physics` for the hero parabola, but with a Couette-specific
feature extractor: only the **stationary** wall is checked for no-slip — the lid
is *meant* to move, so its velocity must not count as "wall slip". Every QoI error
is computed from these arrays (no magic constants), and the same case-agnostic
:func:`benchmark.build_scorecard` + :func:`benchmark.diagnose` then judge the run —
which is the whole point: the benchmark generalises to a different flow unchanged.
"""
from __future__ import annotations

import numpy as np

from . import config, physics


# --------------------------------------------------------------------------- #
# Reference solution                                                          #
# --------------------------------------------------------------------------- #
def normalized_y(n: int = config.N_PROFILE_POINTS) -> np.ndarray:
    """Wall-normal stations y/H in [0, 1]: 0 = fixed wall, 1 = moving lid."""
    return np.linspace(0.0, 1.0, n)


def analytical_profile(
    yn: np.ndarray | None = None, u_lid: float = config.COUETTE_LID_VELOCITY
) -> np.ndarray:
    """Exact steady Couette solution — linear from 0 (fixed wall) to U_lid (lid)."""
    if yn is None:
        yn = normalized_y()
    return u_lid * yn


# --------------------------------------------------------------------------- #
# Fault synthesis                                                             #
# --------------------------------------------------------------------------- #
def bc_slip_profile(
    yn: np.ndarray, slip: float, u_lid: float = config.COUETTE_LID_VELOCITY
) -> np.ndarray:
    """Partial slip at the STATIONARY wall: the fluid leaks along the bottom plate
    instead of sticking. u(0) = slip * U_lid (should be 0) while the lid is kept
    correct at u(H) = U_lid. Still linear, so the error is a triangle peaking at
    the fixed wall. Signature: large slip at the fixed wall, ~zero curvature, lid
    velocity intact."""
    return u_lid * (slip + (1.0 - slip) * yn)


def failed_profile(yn: np.ndarray | None = None, slip: float = config.COUETTE_BC_SLIP) -> np.ndarray:
    """The injected-fault profile (default slip -> ~18% L2, a false success)."""
    if yn is None:
        yn = normalized_y()
    return bc_slip_profile(yn, slip=slip)


def repaired_profile(
    yn: np.ndarray | None = None, slip: float = config.COUETTE_REPAIR_SLIP
) -> np.ndarray:
    """The profile after the suggested no-slip repair — small residual slip so the
    QoI error lands within tolerance (~2% L2)."""
    if yn is None:
        yn = normalized_y()
    return bc_slip_profile(yn, slip=slip)


def residual_for(repaired: bool) -> float:  # noqa: ARG001 - symmetry with physics
    """A BC fault converges fine, so the residual is healthy either way. Kept as a
    function for symmetry with :func:`physics.residual_for`."""
    return physics.residual_for("bc_mismatch", repaired=repaired)


# --------------------------------------------------------------------------- #
# Quantities of interest & profile features                                  #
# --------------------------------------------------------------------------- #
def l2_relative_error(u_test: np.ndarray, u_ref: np.ndarray | None = None) -> float:
    """Relative L2 error of a Couette profile against the *linear* reference."""
    if u_ref is None:
        u_ref = analytical_profile()
    return physics.l2_relative_error(u_test, u_ref)


def couette_features(u_test: np.ndarray, u_ref: np.ndarray | None = None) -> dict[str, float]:
    """Shape features keyed by the SAME names the diagnosis layer reads — but
    wall_slip checks ONLY the stationary wall (y = 0). The moving lid (y = H) is
    meant to carry U_lid and must not count as slip. For a linear flow curvature
    and peak_deficit are ~0, so a BC fault routes cleanly to BC_MISMATCH rather
    than MESH_TOO_COARSE."""
    if u_ref is None:
        u_ref = analytical_profile()
    u_lid = float(np.max(u_ref))   # reference peak == lid speed
    wall_slip = abs(float(u_test[0])) / u_lid    # stationary wall only

    peak_test = float(np.max(u_test))
    peak_deficit = (u_lid - peak_test) / u_lid

    d2_test = np.diff(u_test, n=2)
    d2_ref = np.diff(u_ref, n=2)
    curvature_rmse = float(np.sqrt(np.mean((d2_test - d2_ref) ** 2))) / u_lid

    return {
        "wall_slip": round(wall_slip, 5),
        "peak_deficit": round(peak_deficit, 5),
        "curvature_rmse": round(curvature_rmse, 5),
    }
