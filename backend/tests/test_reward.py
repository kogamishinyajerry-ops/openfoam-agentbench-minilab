"""Tests for ofab.benchmark.reward.compute_reward.

These assert the *real* invariants of the reward signal (the project's own
thesis applied to itself): engineering reward is driven by the QoI L2 error,
the sign flips around a 10% error, efficiency decays with round_index, the
experience bonus is fixed at +0.20, the accept/repair decision follows
overall_pass, and suggested_focus maps by failure_mode.

We construct Scorecard / Diagnosis inputs directly — no real pipeline needed.
"""
from __future__ import annotations

import pytest

from ofab.benchmark.reward import compute_reward
from ofab.models import (
    Diagnosis,
    ExecutionStatus,
    EngineeringStatus,
    FailureMode,
    Fault,
    Scorecard,
    Workflow,
)


# --------------------------------------------------------------------------- #
# Builders                                                                     #
# --------------------------------------------------------------------------- #
def make_scorecard(
    qoi_error: float,
    *,
    overall_pass: bool = False,
    run_id: str = "run-test",
    residual_final: float = 6e-7,
) -> Scorecard:
    """Minimal Scorecard carrying only what compute_reward reads.

    compute_reward only consumes .qoi_error, .overall_pass and .run_id, but we
    fill the full contract so the pydantic model validates.
    """
    return Scorecard(
        run_id=run_id,
        workflow=Workflow.AGENT_PLUS_BENCHMARK,
        fault=Fault.NONE,
        checks=[],
        qoi_error=qoi_error,
        residual_final=residual_final,
        execution_status=ExecutionStatus.SUCCESS,
        engineering_status=(
            EngineeringStatus.PASS if overall_pass else EngineeringStatus.NEEDS_REPAIR
        ),
        false_success=(not overall_pass),
        overall_pass=overall_pass,
    )


def make_diagnosis(
    failure_mode: FailureMode = FailureMode.NONE,
    *,
    run_id: str = "run-test",
    confidence: float = 0.95,
) -> Diagnosis:
    return Diagnosis(
        run_id=run_id,
        failure_mode=failure_mode,
        confidence=confidence,
        evidence=[],
        suggested_repair=[],
    )


# --------------------------------------------------------------------------- #
# engineering_reward ground truth: engineering = clip(0.8*(1 - qoi/0.10))     #
# --------------------------------------------------------------------------- #
def test_engineering_zero_qoi_is_plus_0_8():
    # qoi = 0 -> 0.8 * (1 - 0) = +0.8
    r = compute_reward(make_scorecard(0.0), make_diagnosis(), round_index=0)
    assert r.engineering_reward == pytest.approx(0.8, abs=1e-9)


def test_engineering_crosses_zero_at_ten_percent():
    # qoi = 0.10 -> 0.8 * (1 - 1) = 0.0 (zero crossing)
    r = compute_reward(make_scorecard(0.10), make_diagnosis(), round_index=0)
    assert r.engineering_reward == pytest.approx(0.0, abs=1e-9)


def test_engineering_clips_to_lower_bound_for_huge_qoi():
    # qoi very large -> 0.8*(1 - big) is strongly negative, clipped to -0.85.
    r = compute_reward(make_scorecard(10.0), make_diagnosis(), round_index=0)
    assert r.engineering_reward == pytest.approx(-0.85, abs=1e-9)


def test_engineering_clips_to_upper_bound_for_negative_qoi():
    # A (hypothetical) negative qoi would push above the +0.85 clip ceiling.
    # 0.8*(1 - (-0.5)/0.10) = 0.8*6 = 4.8 -> clipped to +0.85.
    r = compute_reward(make_scorecard(-0.5), make_diagnosis(), round_index=0)
    assert r.engineering_reward == pytest.approx(0.85, abs=1e-9)


def test_engineering_monotonically_decreases_with_qoi():
    r_low = compute_reward(make_scorecard(0.02), make_diagnosis())
    r_mid = compute_reward(make_scorecard(0.05), make_diagnosis())
    r_high = compute_reward(make_scorecard(0.08), make_diagnosis())
    assert r_low.engineering_reward > r_mid.engineering_reward > r_high.engineering_reward


# --------------------------------------------------------------------------- #
# decision: follows overall_pass                                              #
# --------------------------------------------------------------------------- #
def test_decision_accept_when_overall_pass():
    r = compute_reward(
        make_scorecard(0.021, overall_pass=True), make_diagnosis()
    )
    assert r.decision == "accept"


def test_decision_repair_when_not_overall_pass():
    r = compute_reward(
        make_scorecard(0.184, overall_pass=False), make_diagnosis()
    )
    assert r.decision == "repair_and_rerun"


# --------------------------------------------------------------------------- #
# experience bonus + efficiency decay                                         #
# --------------------------------------------------------------------------- #
def test_experience_bonus_adds_exactly_0_20():
    sc = make_scorecard(0.05)
    diag = make_diagnosis()
    without = compute_reward(sc, diag, round_index=0, experience_created=False)
    with_exp = compute_reward(sc, diag, round_index=0, experience_created=True)
    assert without.experience_reward == pytest.approx(0.0)
    assert with_exp.experience_reward == pytest.approx(0.20)
    # The bonus must flow into total, isolating the +0.20 delta.
    assert with_exp.total_reward - without.total_reward == pytest.approx(0.20, abs=1e-9)


def test_efficiency_round0_is_0_10():
    r = compute_reward(make_scorecard(0.05), make_diagnosis(), round_index=0)
    assert r.efficiency_reward == pytest.approx(0.10)


def test_efficiency_round1_is_minus_0_01():
    # 0.10 - 0.11*1 = -0.01
    r = compute_reward(make_scorecard(0.05), make_diagnosis(), round_index=1)
    assert r.efficiency_reward == pytest.approx(-0.01)


def test_efficiency_round2_is_minus_0_12():
    # 0.10 - 0.11*2 = -0.12
    r = compute_reward(make_scorecard(0.05), make_diagnosis(), round_index=2)
    assert r.efficiency_reward == pytest.approx(-0.12)


def test_efficiency_strictly_decreases_with_round_index():
    effs = [
        compute_reward(make_scorecard(0.05), make_diagnosis(), round_index=i).efficiency_reward
        for i in range(4)
    ]
    assert all(later < earlier for earlier, later in zip(effs, effs[1:]))


# --------------------------------------------------------------------------- #
# sign flip: high qoi -> negative total, low qoi -> positive total           #
# --------------------------------------------------------------------------- #
def test_high_qoi_total_is_negative():
    # failed profile: qoi ~ 0.1842, round 0, no experience.
    # engineering = 0.8*(1 - 0.1842/0.10) = 0.8*(-0.842) = -0.6736
    # total = round(-0.6736 + 0.10 + 0, 3) = -0.574  -> negative
    r = compute_reward(
        make_scorecard(0.1842, overall_pass=False), make_diagnosis(FailureMode.BC_MISMATCH),
        round_index=0,
    )
    assert r.total_reward < 0
    assert r.total_reward == pytest.approx(-0.574, abs=1e-3)


def test_low_qoi_total_is_positive():
    # repaired profile: qoi ~ 0.0211, round 0, no experience.
    # engineering = 0.8*(1 - 0.0211/0.10) = 0.8*0.789 = 0.6312
    # total = round(0.6312 + 0.10, 3) = 0.731 -> positive
    r = compute_reward(
        make_scorecard(0.0211, overall_pass=True), make_diagnosis(FailureMode.NONE),
        round_index=0,
    )
    assert r.total_reward > 0
    assert r.total_reward == pytest.approx(0.731, abs=1e-3)


def test_sign_flips_between_repaired_and_failed():
    failed = compute_reward(make_scorecard(0.1842), make_diagnosis(FailureMode.BC_MISMATCH))
    repaired = compute_reward(
        make_scorecard(0.0211, overall_pass=True), make_diagnosis(FailureMode.NONE)
    )
    assert failed.total_reward < 0 < repaired.total_reward


# --------------------------------------------------------------------------- #
# suggested_focus mapping by failure_mode                                      #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "mode, expected",
    [
        (FailureMode.BC_MISMATCH, ["boundary_condition", "qoi_alignment"]),
        (FailureMode.MESH_TOO_COARSE, ["mesh_resolution", "qoi_alignment"]),
        (FailureMode.RESIDUAL_NOT_CONVERGED, ["solver_settings", "convergence"]),
        (FailureMode.NONE, []),
    ],
)
def test_suggested_focus_mapping(mode, expected):
    r = compute_reward(make_scorecard(0.05), make_diagnosis(mode))
    assert r.suggested_focus == expected


# --------------------------------------------------------------------------- #
# total = round(engineering + efficiency + experience, 3) — full composition  #
# --------------------------------------------------------------------------- #
def test_total_is_sum_of_components():
    r = compute_reward(
        make_scorecard(0.04), make_diagnosis(FailureMode.MESH_TOO_COARSE),
        round_index=1, experience_created=True,
    )
    expected = round(
        r.engineering_reward + r.efficiency_reward + r.experience_reward, 3
    )
    assert r.total_reward == pytest.approx(expected, abs=1e-9)


def test_run_id_propagates():
    r = compute_reward(
        make_scorecard(0.05, run_id="abc-123"), make_diagnosis(run_id="abc-123")
    )
    assert r.run_id == "abc-123"
