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
