"""Plane Poiseuille analytics + physically-motivated fault synthesis.

The reference is the *exact* laminar parabola. Each fault returns a deviated
profile whose **shape encodes the failure mode**, so the diagnosis layer can
classify it from measured features (wall slip, peak deficit, residual) instead
of a hard-coded label. Every QoI error downstream is computed from these arrays
— there are no magic error constants anywhere in the pipeline.

    u(y) = u_max * 4 (y/H) (1 - y/H)          (no-slip walls at y/H = 0 and 1)
"""
from __future__ import annotations

import numpy as np

from . import config


# --------------------------------------------------------------------------- #
# Reference solution                                                          #
# --------------------------------------------------------------------------- #
def normalized_y(n: int = config.N_PROFILE_POINTS) -> np.ndarray:
    """Wall-normal sample stations y/H in [0, 1]."""
    return np.linspace(0.0, 1.0, n)


def analytical_profile(yn: np.ndarray | None = None, u_max: float = config.U_MAX) -> np.ndarray:
    """Exact fully-developed laminar parabola."""
    if yn is None:
        yn = normalized_y()
    return u_max * 4.0 * yn * (1.0 - yn)


# --------------------------------------------------------------------------- #
# Fault synthesis                                                             #
# --------------------------------------------------------------------------- #
def _bc_mismatch_profile(yn: np.ndarray, slip: float, u_max: float = config.U_MAX) -> np.ndarray:
    """Wrong wall BC (partial slip) -> blunted, plug-like profile with non-zero
    wall velocity. ``slip`` is the fraction of u_max that leaks at the walls.
    Signature: large wall slip, reduced curvature."""
    parabola = 4.0 * yn * (1.0 - yn)
    return u_max * (slip + (1.0 - slip) * parabola)


def _coarse_mesh_profile(yn: np.ndarray, n_cells: int, u_max: float = config.U_MAX) -> np.ndarray:
    """Under-resolved wall-normal mesh. A finite-volume solver stores the solution
    at *cell centres* (the walls are faces held at no-slip), so a coarse mesh
    reconstructs the profile by linear interpolation through the ``n_cells``
    cell-centre values. The smooth parabola becomes faceted **and** its centreline
    peak is clipped: the true maximum at y/H = 0.5 falls *between* cell centres and
    is never sampled. (Sampling at mesh *nodes* would put a node exactly on the
    centreline for even ``n_cells`` and hide the deficit — cell centres are both
    physically faithful to FV and keep the peak-deficit signal honest.)
    Signature: ~zero wall slip, positive peak deficit, faceted interior."""
    centres = (np.arange(n_cells) + 0.5) / n_cells
    sample_y = np.concatenate(([0.0], centres, [1.0]))   # walls are faces (no-slip)
    sample_u = analytical_profile(sample_y, u_max=u_max)
    sample_u[0] = 0.0
    sample_u[-1] = 0.0
    return np.interp(yn, sample_y, sample_u)


def _solver_error_profile(
    yn: np.ndarray, develop: float, noise: float, u_max: float = config.U_MAX,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Bad solver settings (too-large timestep / too-few iterations) -> the run
    stops before steady state. The parabola is under-developed (scaled by
    ``develop`` < 1) and carries residual noise. The *primary* signal is a
    non-converged residual, not the shape."""
    if rng is None:
        rng = np.random.default_rng(config.RNG_SEED)
    base = develop * analytical_profile(yn, u_max=u_max)
    wobble = noise * u_max * np.sin(3.0 * np.pi * yn) * rng.uniform(0.6, 1.0, size=yn.shape)
    prof = base + wobble
    prof[0] = 0.0   # no-slip still enforced numerically
    prof[-1] = 0.0
    return np.clip(prof, 0.0, None)


def _repaired_profile(yn: np.ndarray, slip: float, u_max: float = config.U_MAX) -> np.ndarray:
    """Post-repair profile: analytical parabola plus a small residual deviation
    (a tiny leftover slip) so the QoI error lands in the acceptable band."""
    return _bc_mismatch_profile(yn, slip=slip, u_max=u_max)


# Tuned parameters: chosen so computed L2 errors land near presentation targets
# (~18% bc, ~6% mesh, ~14% solver; ~2% after repair). The errors are still
# *computed* from the arrays below — these only set perturbation magnitude.
_FAULT_PARAMS = {
    "bc_mismatch": dict(slip=0.283),
    "coarse_mesh": dict(n_cells=4),
    "solver_setting_error": dict(develop=0.86, noise=0.05),
}
_REPAIR_SLIP = 0.0325          # residual slip after a good fix -> ~2.1% L2
# Agent-only plateau: blind tweaking lowers the hero-fault error but never sees
# the QoI, so it stalls above tolerance. Used to synthesize its final profile.
AGENT_ONLY_PLATEAU_SLIP = 0.134   # -> ~8.7% L2
_SOLVER_BAD_RESIDUAL = 8.0e-3   # un-converged residual for the solver fault
_GOOD_RESIDUAL = 6.0e-7        # healthy converged residual


def failed_profile(fault: str, yn: np.ndarray | None = None) -> np.ndarray:
    """The deviated profile produced by injecting ``fault``."""
    if yn is None:
        yn = normalized_y()
    rng = np.random.default_rng(config.RNG_SEED)
    if fault == "bc_mismatch":
        return _bc_mismatch_profile(yn, **_FAULT_PARAMS["bc_mismatch"])
    if fault == "coarse_mesh":
        return _coarse_mesh_profile(yn, **_FAULT_PARAMS["coarse_mesh"])
    if fault == "solver_setting_error":
        return _solver_error_profile(yn, rng=rng, **_FAULT_PARAMS["solver_setting_error"])
    raise ValueError(f"unknown fault: {fault}")


def repaired_profile(fault: str, yn: np.ndarray | None = None) -> np.ndarray:
    """The profile after the suggested repair is applied — near-analytical."""
    if yn is None:
        yn = normalized_y()
    return _repaired_profile(yn, slip=_REPAIR_SLIP)


def bc_profile(slip: float, yn: np.ndarray | None = None) -> np.ndarray:
    """Partial-slip channel profile for an arbitrary wall-slip fraction — used to
    represent intermediate states of a guided BC repair loop."""
    if yn is None:
        yn = normalized_y()
    return _bc_mismatch_profile(yn, slip=slip)


def plateau_profile(yn: np.ndarray | None = None) -> np.ndarray:
    """Agent-only end state for the hero fault: partially improved but stalled
    above tolerance because the workflow never measures the QoI."""
    if yn is None:
        yn = normalized_y()
    return _bc_mismatch_profile(yn, slip=AGENT_ONLY_PLATEAU_SLIP)


def residual_for(fault: str, repaired: bool) -> float:
    """Final solver residual associated with a (fault, repaired) state."""
    if fault == "solver_setting_error" and not repaired:
        return _SOLVER_BAD_RESIDUAL
    return _GOOD_RESIDUAL


# --------------------------------------------------------------------------- #
# Quantities of interest & profile features                                  #
# --------------------------------------------------------------------------- #
def l2_relative_error(u_test: np.ndarray, u_ref: np.ndarray | None = None) -> float:
    """Relative L2 error of a profile against the analytical reference."""
    if u_ref is None:
        u_ref = analytical_profile()
    num = float(np.linalg.norm(u_test - u_ref))
    den = float(np.linalg.norm(u_ref))
    return num / den if den > 0 else 0.0


def profile_features(u_test: np.ndarray, u_ref: np.ndarray | None = None) -> dict[str, float]:
    """Shape features the diagnosis layer keys on.

    - wall_slip:    mean |u| at the two walls, normalized by u_max
    - peak_deficit: fractional shortfall of the centerline peak
    - curvature_rmse: RMS of the discrete 2nd-derivative residual vs reference,
                      normalized — large for faceted (coarse-mesh) profiles
    """
    if u_ref is None:
        u_ref = analytical_profile()
    u_max = float(np.max(u_ref))
    wall_slip = (abs(float(u_test[0])) + abs(float(u_test[-1]))) / 2.0 / u_max

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
