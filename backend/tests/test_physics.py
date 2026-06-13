"""Invariant tests for ofab.physics.

These assert the *real* physical invariants and the fixed numerical targets
documented in the project, not tautologies. The project's thesis is that
verification catches fake success, so these tests must hold the physics layer
to its own ground truth.
"""
from __future__ import annotations

import numpy as np
import pytest

from ofab import config, physics


# --------------------------------------------------------------------------- #
# normalized_y                                                                #
# --------------------------------------------------------------------------- #
def test_normalized_y_default_length_and_endpoints():
    yn = physics.normalized_y()
    assert len(yn) == config.N_PROFILE_POINTS == 41
    assert yn[0] == pytest.approx(0.0)
    assert yn[-1] == pytest.approx(1.0)
    # strictly increasing, stays in [0, 1]
    assert np.all(np.diff(yn) > 0)
    assert yn.min() == pytest.approx(0.0)
    assert yn.max() == pytest.approx(1.0)


@pytest.mark.parametrize("n", [5, 11, 41, 101])
def test_normalized_y_custom_length_endpoints(n):
    yn = physics.normalized_y(n)
    assert len(yn) == n
    assert yn[0] == pytest.approx(0.0)
    assert yn[-1] == pytest.approx(1.0)


# --------------------------------------------------------------------------- #
# analytical_profile                                                          #
# --------------------------------------------------------------------------- #
def test_analytical_profile_walls_zero():
    u = physics.analytical_profile()
    assert u[0] == pytest.approx(0.0, abs=1e-12)
    assert u[-1] == pytest.approx(0.0, abs=1e-12)


def test_analytical_profile_centerline_is_u_max():
    # N=41 is odd so index 20 is exactly y/H = 0.5
    u = physics.analytical_profile()
    mid = len(u) // 2
    assert u[mid] == pytest.approx(config.U_MAX)
    assert u[mid] == pytest.approx(0.15)


def test_analytical_profile_symmetry():
    u = physics.analytical_profile()
    assert np.allclose(u, u[::-1])


def test_analytical_profile_length_and_max():
    u = physics.analytical_profile()
    assert len(u) == 41
    assert float(np.max(u)) == pytest.approx(config.U_MAX) == pytest.approx(0.15)


def test_analytical_profile_formula_matches_parabola():
    yn = physics.normalized_y()
    u = physics.analytical_profile(yn)
    expected = config.U_MAX * 4.0 * yn * (1.0 - yn)
    assert np.allclose(u, expected)


# --------------------------------------------------------------------------- #
# l2_relative_error                                                           #
# --------------------------------------------------------------------------- #
def test_l2_relative_error_self_is_zero():
    ref = physics.analytical_profile()
    assert physics.l2_relative_error(ref, ref) == pytest.approx(0.0, abs=1e-12)


def test_l2_relative_error_against_default_ref_is_zero():
    ref = physics.analytical_profile()
    # default u_ref is analytical_profile() -> identical
    assert physics.l2_relative_error(ref) == pytest.approx(0.0, abs=1e-12)


# --------------------------------------------------------------------------- #
# failed_profile: feature + L2 signatures                                     #
# --------------------------------------------------------------------------- #
def test_bc_mismatch_signature():
    u = physics.failed_profile("bc_mismatch")
    feats = physics.profile_features(u)
    # wall slip ~ slip fraction = 0.283
    assert feats["wall_slip"] == pytest.approx(0.283, abs=0.005)
    l2 = physics.l2_relative_error(u)
    assert 0.17 <= l2 <= 0.20


def test_coarse_mesh_signature():
    u = physics.failed_profile("coarse_mesh")
    feats = physics.profile_features(u)
    # no-slip respected: wall nodes stay 0 -> wall_slip below tolerance
    assert feats["wall_slip"] < config.WALL_SLIP_TOL
    assert feats["wall_slip"] == pytest.approx(0.0, abs=1e-9)
    # L2 error lands in the documented coarse-mesh band
    l2 = physics.l2_relative_error(u)
    assert 0.05 <= l2 <= 0.07


def test_coarse_mesh_peak_deficit_positive():
    # The coarse mesh stores values at cell centres (FV), so the true centreline
    # peak at y/H=0.5 falls *between* centres and is clipped -> positive deficit.
    u = physics.failed_profile("coarse_mesh")
    feats = physics.profile_features(u)
    assert feats["peak_deficit"] > 0.0
    assert feats["peak_deficit"] == pytest.approx(0.0625, abs=0.01)


def test_solver_setting_error_signature():
    u = physics.failed_profile("solver_setting_error")
    # no-slip enforced numerically at both walls
    assert u[0] == pytest.approx(0.0, abs=1e-12)
    assert u[-1] == pytest.approx(0.0, abs=1e-12)
    l2 = physics.l2_relative_error(u)
    assert 0.13 <= l2 <= 0.16


# --------------------------------------------------------------------------- #
# repaired / plateau profiles                                                 #
# --------------------------------------------------------------------------- #
def test_repaired_profile_passes_tolerance():
    u = physics.repaired_profile("bc_mismatch")
    l2 = physics.l2_relative_error(u)
    assert l2 < config.QOI_L2_TOL
    assert l2 == pytest.approx(0.021, abs=0.005)


def test_plateau_profile_stalls_above_tolerance():
    u = physics.plateau_profile()
    l2 = physics.l2_relative_error(u)
    assert l2 > config.QOI_L2_TOL
    assert l2 == pytest.approx(0.087, abs=0.005)


# --------------------------------------------------------------------------- #
# residual_for: four combinations                                            #
# --------------------------------------------------------------------------- #
def test_residual_for_solver_unrepaired_is_bad():
    r = physics.residual_for("solver_setting_error", repaired=False)
    assert r == pytest.approx(8.0e-3)
    assert r > config.RESIDUAL_TOL


def test_residual_for_solver_repaired_is_good():
    r = physics.residual_for("solver_setting_error", repaired=True)
    assert r == pytest.approx(6.0e-7)
    assert r < config.RESIDUAL_TOL


def test_residual_for_other_fault_unrepaired_is_good():
    r = physics.residual_for("bc_mismatch", repaired=False)
    assert r == pytest.approx(6.0e-7)
    assert r < config.RESIDUAL_TOL


def test_residual_for_other_fault_repaired_is_good():
    r = physics.residual_for("coarse_mesh", repaired=True)
    assert r == pytest.approx(6.0e-7)
    assert r < config.RESIDUAL_TOL


# --------------------------------------------------------------------------- #
# profile_features: keys                                                      #
# --------------------------------------------------------------------------- #
def test_profile_features_keys():
    u = physics.failed_profile("bc_mismatch")
    feats = physics.profile_features(u)
    assert set(feats.keys()) == {"wall_slip", "peak_deficit", "curvature_rmse"}
    for v in feats.values():
        assert isinstance(v, float)


def test_profile_features_reference_is_clean():
    ref = physics.analytical_profile()
    feats = physics.profile_features(ref, ref)
    assert feats["wall_slip"] == pytest.approx(0.0, abs=1e-9)
    assert feats["peak_deficit"] == pytest.approx(0.0, abs=1e-9)
    assert feats["curvature_rmse"] == pytest.approx(0.0, abs=1e-9)


# --------------------------------------------------------------------------- #
# determinism + error handling                                                #
# --------------------------------------------------------------------------- #
def test_failed_profile_deterministic():
    # solver fault carries RNG noise; must be byte-reproducible across calls
    a = physics.failed_profile("solver_setting_error")
    b = physics.failed_profile("solver_setting_error")
    assert np.array_equal(a, b)


def test_failed_profile_deterministic_all_faults():
    for fault in ("bc_mismatch", "coarse_mesh", "solver_setting_error"):
        a = physics.failed_profile(fault)
        b = physics.failed_profile(fault)
        assert np.array_equal(a, b)


def test_failed_profile_unknown_fault_raises():
    with pytest.raises(ValueError):
        physics.failed_profile("not_a_real_fault")
