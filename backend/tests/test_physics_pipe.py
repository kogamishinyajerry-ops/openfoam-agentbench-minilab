"""Invariants for the third case — round-pipe Hagen–Poiseuille physics.

Pure numpy, no Docker. These pin the radial analytical solution, the coarse-mesh
fault's fingerprint, and — the headline of case 3 — that the SAME unchanged
diagnosis routes this flow's false success to MESH_TOO_COARSE (a *different* hero
fault than the BC_MISMATCH of cases 1 and 2). Numbers are computed from the arrays,
never hard-coded.
"""
from __future__ import annotations

import numpy as np
import pytest

from ofab import config
from ofab import physics_pipe as pp
from ofab.benchmark import diagnose
from ofab.models import (
    EngineeringStatus,
    ExecutionStatus,
    Fault,
    RunMode,
    RunResult,
    Workflow,
)


def _run(u, ref, *, residual: float) -> RunResult:
    u = np.asarray(u, dtype=float)
    return RunResult(
        run_id="pipe_t",
        workflow=Workflow.AGENT_PLUS_BENCHMARK,
        case_id=config.PIPE_CASE_ID,
        fault=Fault.COARSE_MESH,
        mode=RunMode.REPLAY,
        round_index=0,
        execution_status=ExecutionStatus.SUCCESS,
        engineering_status=EngineeringStatus.NEEDS_REPAIR,
        qoi_error=round(float(pp.l2_relative_error(u, ref)), 5),
        residual_final=residual,
        runtime_s=1.0,
        features={k: round(float(v), 5) for k, v in pp.pipe_features(u, ref).items()},
    )


# --------------------------------------------------------------------------- #
# Analytical radial parabola                                                  #
# --------------------------------------------------------------------------- #
def test_analytical_is_radial_parabola_peaking_on_axis():
    rn = pp.normalized_r()
    u = pp.analytical_profile(rn)
    assert u[0] == pytest.approx(config.PIPE_U_MAX)     # axis = peak
    assert u[-1] == pytest.approx(0.0)                  # wall = no-slip
    # monotonically decreasing from axis to wall (a half-parabola)
    assert np.all(np.diff(u) < 0)
    # exact shape u = u_max (1 - rn^2)
    assert np.allclose(u, config.PIPE_U_MAX * (1 - rn**2), atol=1e-12)


def test_u_max_is_twice_the_mean_velocity():
    # the defining round-pipe relation (vs 1.5x for the plane channel)
    assert config.PIPE_U_MAX == pytest.approx(2.0 * config.PIPE_MEAN_VELOCITY)


# --------------------------------------------------------------------------- #
# Coarse-mesh fault fingerprint                                               #
# --------------------------------------------------------------------------- #
def test_coarse_mesh_is_a_false_success_with_clipped_peak():
    rn = pp.normalized_r()
    ref = pp.analytical_profile(rn)
    u = pp.failed_profile(rn)
    qoi = pp.l2_relative_error(u, ref)
    feats = pp.pipe_features(u, ref)
    assert qoi > config.QOI_L2_TOL                    # past tolerance -> false success
    assert 0.06 <= qoi <= 0.10                         # ~7.9%
    assert feats["peak_deficit"] > 0.0                 # the axis peak got clipped
    assert feats["wall_slip"] < config.WALL_SLIP_TOL   # no-slip wall still respected


def test_repaired_fine_mesh_passes():
    rn = pp.normalized_r()
    ref = pp.analytical_profile(rn)
    u = pp.repaired_profile(rn)
    assert pp.l2_relative_error(u, ref) < config.QOI_L2_TOL


def test_clean_run_reproduces_parabola_exactly():
    rn = pp.normalized_r()
    ref = pp.analytical_profile(rn)
    assert pp.l2_relative_error(ref, ref) == pytest.approx(0.0)


# --------------------------------------------------------------------------- #
# The headline: a DIFFERENT hero fault, same unchanged diagnose()             #
# --------------------------------------------------------------------------- #
def test_coarse_mesh_routes_to_mesh_not_bc():
    rn = pp.normalized_r()
    ref = pp.analytical_profile(rn)
    d = diagnose(_run(pp.failed_profile(rn), ref, residual=pp.residual_for(False)))
    assert d.failure_mode.value == "MESH_TOO_COARSE"
    assert d.failure_mode.value != "BC_MISMATCH"


def test_clean_run_diagnoses_none():
    rn = pp.normalized_r()
    ref = pp.analytical_profile(rn)
    d = diagnose(_run(ref, ref, residual=pp.residual_for(True)))
    assert d.failure_mode.value == "NONE"


def test_wall_slip_feature_ignores_the_axis_peak():
    """The pipe feature extractor must check ONLY the wall (r/R = 1). The axis
    (r/R = 0) carries the peak velocity u_max and must NOT be read as wall slip —
    otherwise a perfectly correct pipe profile would look like a massive BC fault."""
    rn = pp.normalized_r()
    ref = pp.analytical_profile(rn)
    feats = pp.pipe_features(ref, ref)
    assert feats["wall_slip"] == pytest.approx(0.0)   # axis peak NOT counted as slip
