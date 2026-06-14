"""Single source of numerical truth for the whole demo.

Physics, benchmark, runners and the reference CSV all import from here so every
profile, QoI error and tolerance agrees. Change a number here and the entire
pipeline (and the regenerated replay data) stays self-consistent.
"""
from __future__ import annotations

# --- Hero case identity --------------------------------------------------------
CASE_ID = "channel_poiseuille"
CASE_TITLE = "平板通道层流（管道里的稳定水流）"

# --- Physical parameters (SI) --------------------------------------------------
# Chosen to keep the flow firmly laminar (Re_H ~ 20) so a short developing
# channel reaches a fully-developed parabola the analytical solution can verify.
CHANNEL_HEIGHT = 0.01          # H  [m]   wall-to-wall gap
CHANNEL_LENGTH = 0.12          # L  [m]   = 12 H, exceeds the development length
INLET_VELOCITY = 0.10          # U0 [m/s] uniform inlet -> bulk mean velocity
KINEMATIC_VISCOSITY = 5.0e-5   # nu [m^2/s]

# --- Derived analytical quantities --------------------------------------------
REYNOLDS_H = INLET_VELOCITY * CHANNEL_HEIGHT / KINEMATIC_VISCOSITY  # ~20
U_MAX = 1.5 * INLET_VELOCITY   # fully-developed parabola peak (mean is conserved)

# --- Sampling ------------------------------------------------------------------
N_PROFILE_POINTS = 41          # wall-normal samples used for the profile & QoI

# --- Benchmark tolerances ------------------------------------------------------
QOI_L2_TOL = 0.05              # relative L2 of u(y) vs analytical -> pass < 5%
RESIDUAL_TOL = 1.0e-4          # final solver residual must be below this
WALL_SLIP_TOL = 0.05          # |u_wall|/U_MAX above this => no-slip violated

# Deterministic seed so synthesized replay data is byte-reproducible.
RNG_SEED = 20240613


# =============================================================================
# Second case — plane Couette (shear-driven) flow
# =============================================================================
# A second analytically-verifiable flow, added to show the benchmark GENERALISES:
# the *same* scorecard + diagnosis code (unchanged) judges a different flow. Here
# the lower wall is stationary (no-slip, u=0) and the upper wall (lid) is dragged
# at a constant speed, so the exact steady solution is LINEAR: u(y) = U_lid * y/H.
# (Contrast with the pressure-driven parabola above — same fault taxonomy, mirror
# physics.) Shared benchmark thresholds (QOI_L2_TOL / RESIDUAL_TOL / WALL_SLIP_TOL),
# sampling and seed are reused; only the case geometry + injected slip differ.
COUETTE_CASE_ID = "couette_shear"
COUETTE_TITLE = "平板剪切流（Couette：上盖板拖动的水流）"

COUETTE_HEIGHT = 0.01            # H  [m]    gap between the plates
COUETTE_LID_VELOCITY = 0.10     # U_lid [m/s]  top plate speed (bottom is fixed)
COUETTE_KINEMATIC_VISCOSITY = 5.0e-5   # nu [m^2/s]  (same fluid as the hero case)

REYNOLDS_COUETTE = COUETTE_LID_VELOCITY * COUETTE_HEIGHT / COUETTE_KINEMATIC_VISCOSITY  # ~20
COUETTE_U_MAX = COUETTE_LID_VELOCITY   # the linear profile peaks at the moving lid

# Injected fault (case-2 hero): partial slip at the STATIONARY wall — the no-slip
# BC is violated so the fluid "leaks" along the fixed plate. For the symmetric
# sample grid the relative L2 error equals the slip fraction exactly, so 0.18 ->
# ~18% (false success, well past the 5% tolerance) and 0.02 -> ~2% (repaired,
# within tolerance). wall_slip feature == slip, so diagnosis fires BC_MISMATCH.
COUETTE_BC_SLIP = 0.18          # injected slip  -> ~18% L2, a false success
COUETTE_REPAIR_SLIP = 0.02      # residual slip after the fix -> ~2% L2, passes


# A THIRD analytically-verifiable flow, added to widen the generalisation proof
# from "same benchmark, different flow" to "same benchmark, different flow AND a
# different HERO fault". Round-pipe Hagen–Poiseuille: a RADIAL parabola
# u(r) = u_max (1 - (r/R)^2), peak on the axis, no-slip at the wall, u_max = 2*U_mean.
# Hero fault = COARSE_MESH — the curved radial profile is genuinely under-resolved
# on a coarse radial mesh (centreline peak clipped + faceted), so it routes to
# MESH_TOO_COARSE via the unchanged diagnose(). This is *exactly* the fault that
# does NOT apply to linear Couette (honestly marked not_applicable there) — the pipe
# is its natural home, closing the "framework matches faults to flows" honesty loop.
# Shared benchmark thresholds / sampling / seed reused; no hero/Couette constant touched.
PIPE_CASE_ID = "pipe_poiseuille"
PIPE_TITLE = "圆管层流（Hagen–Poiseuille：水管里的稳定水流）"

PIPE_RADIUS = 0.005             # R  [m]   (diameter 2R = 0.01 = same scale as channel H)
PIPE_LENGTH = 0.12              # L  [m] = 12 * diameter
PIPE_MEAN_VELOCITY = 0.10       # U_mean [m/s]  bulk (cross-section average) velocity
PIPE_KINEMATIC_VISCOSITY = 5.0e-5   # nu [m^2/s]  (same fluid as the other cases)

REYNOLDS_PIPE = PIPE_MEAN_VELOCITY * (2 * PIPE_RADIUS) / PIPE_KINEMATIC_VISCOSITY  # ~20
PIPE_U_MAX = 2.0 * PIPE_MEAN_VELOCITY   # round-pipe peak = 2*U_mean (= 0.20 m/s)

# Injected fault (case-3 hero): under-resolved RADIAL mesh. Cell-centre sampling of
# the parabola clips the axis peak and facets the curve; on the symmetric sample grid
# this lands the relative L2 clearly past the 5% tolerance (false success) while the
# wall stays no-slip (so it diagnoses MESH_TOO_COARSE, not BC_MISMATCH).
PIPE_COARSE_NCELLS = 2          # injected coarse radial mesh -> ~7.9% L2, false success
PIPE_FINE_NCELLS = 32           # repaired (refined) radial mesh -> ~0.02% L2, passes
