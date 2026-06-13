"""Invariant tests for ofab.physics_couette (the second case).

These hold the Couette layer to its own analytical ground truth: a linear
shear profile, a stationary-wall slip fault whose relative L2 error equals the
slip fraction, and features that route a BC fault to BC_MISMATCH (not mesh).
Same discipline as test_physics.py — assert real physics, not tautologies.
"""
from __future__ import annotations

import numpy as np
import pytest

from ofab import config, physics_couette as pc


# --------------------------------------------------------------------------- #
# Reference solution                                                          #
# --------------------------------------------------------------------------- #
def test_reference_is_linear_with_correct_endpoints():
    yn = pc.normalized_y()
    u = pc.analytical_profile(yn)
    assert u[0] == pytest.approx(0.0)                       # no-slip at fixed wall
    assert u[-1] == pytest.approx(config.COUETTE_LID_VELOCITY)  # lid speed at top
    # exactly linear: u = U_lid * y/H everywhere
    assert np.allclose(u, config.COUETTE_LID_VELOCITY * yn)


def test_reference_against_itself_is_zero_error():
    u = pc.analytical_profile()
    assert pc.l2_relative_error(u, u) == pytest.approx(0.0)


# --------------------------------------------------------------------------- #
# Fault synthesis                                                             #
# --------------------------------------------------------------------------- #
def test_bc_slip_leaks_at_fixed_wall_keeps_lid():
    yn = pc.normalized_y()
    slip = 0.18
    u = pc.bc_slip_profile(yn, slip=slip)
    assert u[0] == pytest.approx(slip * config.COUETTE_LID_VELOCITY)   # leak at bottom
    assert u[-1] == pytest.approx(config.COUETTE_LID_VELOCITY)         # lid intact
    # still linear (a BC fault, not a curvature/mesh fault)
    assert np.allclose(np.diff(u, n=2), 0.0, atol=1e-12)


def test_l2_error_equals_slip_fraction():
    """The neat identity that makes the case readable: on the symmetric grid the
    relative L2 error of a stationary-wall slip equals the slip fraction."""
    yn = pc.normalized_y()
    for slip in (0.05, 0.10, 0.18, 0.30):
        u = pc.bc_slip_profile(yn, slip=slip)
        assert pc.l2_relative_error(u) == pytest.approx(slip, abs=1e-9)


def test_failed_and_repaired_land_on_documented_targets():
    failed = pc.failed_profile()
    repaired = pc.repaired_profile()
    # ~18% (false success, past the 5% tol) and ~2% (within tol)
    assert pc.l2_relative_error(failed) == pytest.approx(config.COUETTE_BC_SLIP, abs=1e-9)
    assert pc.l2_relative_error(repaired) == pytest.approx(config.COUETTE_REPAIR_SLIP, abs=1e-9)
    assert pc.l2_relative_error(failed) > config.QOI_L2_TOL    # would be flagged
    assert pc.l2_relative_error(repaired) < config.QOI_L2_TOL  # passes after repair


def test_l2_error_is_monotonic_in_slip():
    yn = pc.normalized_y()
    errs = [pc.l2_relative_error(pc.bc_slip_profile(yn, slip=s)) for s in (0.02, 0.08, 0.15, 0.25)]
    assert errs == sorted(errs)
    assert all(b > a for a, b in zip(errs, errs[1:]))


# --------------------------------------------------------------------------- #
# Features -> diagnosis routing                                              #
# --------------------------------------------------------------------------- #
def test_features_of_clean_run_are_all_zero():
    feats = pc.couette_features(pc.analytical_profile())
    assert feats["wall_slip"] == pytest.approx(0.0)
    assert feats["peak_deficit"] == pytest.approx(0.0)
    assert feats["curvature_rmse"] == pytest.approx(0.0)


def test_bc_fault_features_route_to_bc_mismatch_not_mesh():
    feats = pc.couette_features(pc.failed_profile())
    # wall_slip == slip and is past the BC tolerance -> BC_MISMATCH gate fires
    assert feats["wall_slip"] == pytest.approx(config.COUETTE_BC_SLIP, abs=1e-5)
    assert feats["wall_slip"] >= config.WALL_SLIP_TOL
    # linear flow -> no false mesh signal (lid is the peak, no curvature)
    assert feats["peak_deficit"] == pytest.approx(0.0, abs=1e-9)
    assert feats["curvature_rmse"] == pytest.approx(0.0, abs=1e-9)


def test_moving_lid_is_not_counted_as_wall_slip():
    """The crux of the Couette-specific extractor: the lid carries U_lid but that
    must NOT register as a no-slip violation (only the stationary wall does)."""
    feats = pc.couette_features(pc.analytical_profile())
    # the clean linear profile has full lid velocity yet zero wall_slip
    assert feats["wall_slip"] == pytest.approx(0.0)
