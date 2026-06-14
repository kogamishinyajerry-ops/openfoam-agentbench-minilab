"""Round-pipe Hagen–Poiseuille analytics + coarse-mesh fault synthesis.

The third analytically-verifiable case. A round pipe with a no-slip wall carries a
fully-developed laminar flow whose exact steady solution is a **radial parabola**:

    u(r) = u_max * (1 - (r/R)^2)        (peak u_max on the axis, u = 0 at the wall)

with u_max = 2 * U_mean. We sample along the radius r/R in [0, 1]: index 0 is the
**axis** (centreline peak) and index -1 is the **pipe wall** (no-slip).

This mirrors :mod:`physics` / :mod:`physics_couette` but with a pipe-specific feature
extractor and — crucially — a different HERO fault. Couette's linear solution is
reconstructed exactly on any mesh, so ``coarse_mesh`` is honestly marked
*not applicable* there. The pipe's CURVED radial profile is the opposite: it is
genuinely under-resolved on a coarse radial mesh (the axis peak is clipped and the
curve facets), so ``coarse_mesh`` is the natural HERO fault here. Same case-agnostic
:func:`benchmark.build_scorecard` + :func:`benchmark.diagnose` then judge the run and
route it to MESH_TOO_COARSE — widening the generalisation claim from "different flow"
to "different flow AND different failure mode", all on one unchanged benchmark.
"""
from __future__ import annotations

import numpy as np

from . import config, physics


# --------------------------------------------------------------------------- #
# Reference solution                                                          #
# --------------------------------------------------------------------------- #
def normalized_r(n: int = config.N_PROFILE_POINTS) -> np.ndarray:
    """Radial sample stations r/R in [0, 1]: 0 = axis (centreline), 1 = pipe wall."""
    return np.linspace(0.0, 1.0, n)


def analytical_profile(
    rn: np.ndarray | None = None, u_max: float = config.PIPE_U_MAX
) -> np.ndarray:
    """Exact Hagen–Poiseuille radial parabola — peak u_max on the axis, 0 at the wall."""
    if rn is None:
        rn = normalized_r()
    return u_max * (1.0 - rn**2)


# --------------------------------------------------------------------------- #
# Fault synthesis                                                             #
# --------------------------------------------------------------------------- #
def coarse_mesh_profile(
    rn: np.ndarray, n_cells: int, u_max: float = config.PIPE_U_MAX
) -> np.ndarray:
    """Under-resolved RADIAL mesh. A finite-volume solver stores the **cell average**
    of the solution over each of ``n_cells`` radial cells; the wall is a no-slip face
    (u = 0) and the axis is a symmetry face (zero-gradient, so the centreline is
    reconstructed flat from the first cell value). Using the exact cell average of the
    parabola (not its centre-point value) is FV-faithful — and because u(r) is convex
    the average sits *below* the centre value, so a coarse mesh clips the axis peak
    harder and facets the curve. The smooth radial parabola is never resolved: its true
    maximum at r = 0 is never represented. Signature: ~zero wall slip, positive peak
    deficit, faceted interior -> the diagnosis layer reads MESH_TOO_COARSE."""
    edges = np.linspace(0.0, 1.0, n_cells + 1)
    r_lo, r_hi = edges[:-1], edges[1:]
    # exact cell average of u_max(1 - r^2): <r^2> = (r_hi^3 - r_lo^3) / (3 (r_hi - r_lo))
    r2_avg = (r_hi**3 - r_lo**3) / (3.0 * (r_hi - r_lo))
    u_cells = u_max * (1.0 - r2_avg)
    centres = 0.5 * (r_lo + r_hi)
    sample_r = np.concatenate(([0.0], centres, [1.0]))       # axis, cell centres, wall
    # axis: symmetry -> flat from the first cell value (clips the peak); wall: no-slip 0
    sample_u = np.concatenate(([u_cells[0]], u_cells, [0.0]))
    return np.interp(rn, sample_r, sample_u)


def failed_profile(
    rn: np.ndarray | None = None, n_cells: int = config.PIPE_COARSE_NCELLS
) -> np.ndarray:
    """The injected-fault profile (default coarse radial mesh -> false success)."""
    if rn is None:
        rn = normalized_r()
    return coarse_mesh_profile(rn, n_cells=n_cells)


def repaired_profile(
    rn: np.ndarray | None = None, n_cells: int = config.PIPE_FINE_NCELLS
) -> np.ndarray:
    """The profile after the suggested mesh refinement — a fine radial mesh whose
    residual discretisation error lands the QoI within tolerance."""
    if rn is None:
        rn = normalized_r()
    return coarse_mesh_profile(rn, n_cells=n_cells)


def residual_for(repaired: bool) -> float:  # noqa: ARG001 - symmetry with physics
    """A mesh-resolution fault converges fine, so the residual is healthy either way
    (the error hides in the QoI, not the residual). Kept as a function for symmetry
    with :func:`physics.residual_for`."""
    return physics.residual_for("coarse_mesh", repaired=repaired)


# --------------------------------------------------------------------------- #
# Quantities of interest & profile features                                  #
# --------------------------------------------------------------------------- #
def l2_relative_error(u_test: np.ndarray, u_ref: np.ndarray | None = None) -> float:
    """Relative L2 error of a pipe profile against the radial analytical parabola."""
    if u_ref is None:
        u_ref = analytical_profile()
    return physics.l2_relative_error(u_test, u_ref)


def pipe_features(u_test: np.ndarray, u_ref: np.ndarray | None = None) -> dict[str, float]:
    """Shape features keyed by the SAME names the diagnosis layer reads — but
    wall_slip checks ONLY the pipe wall (r/R = 1, last sample). The axis (r/R = 0,
    first sample) is the centreline PEAK, not a wall, so its velocity must not count
    as slip. A coarse radial mesh keeps the wall at no-slip (wall_slip ~ 0) while
    clipping the axis peak (peak_deficit > 0) and faceting the curve
    (curvature_rmse > 0) -> the run routes cleanly to MESH_TOO_COARSE."""
    if u_ref is None:
        u_ref = analytical_profile()
    u_max = float(np.max(u_ref))              # reference peak == axis velocity
    wall_slip = abs(float(u_test[-1])) / u_max   # pipe wall only (r/R = 1)

    peak_test = float(np.max(u_test))
    peak_deficit = (u_max - peak_test) / u_max

    d2_test = np.diff(u_test, n=2)
    d2_ref = np.diff(u_ref, n=2)
    curvature_rmse = float(np.sqrt(np.mean((d2_test - d2_ref) ** 2))) / u_max

    return {
        "wall_slip": round(wall_slip, 5),
        "peak_deficit": round(peak_deficit, 5),
        "curvature_rmse": round(curvature_rmse, 5),
    }
