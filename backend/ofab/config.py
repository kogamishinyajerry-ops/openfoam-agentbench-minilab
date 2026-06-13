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
