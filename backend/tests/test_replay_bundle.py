"""Headline-number regression lock for the replay bundle.

This is the most load-bearing test in the suite: it pins every number the demo
puts on screen (the comparison cards, workflow metrics, hero profiles) and the
sync invariant between the backend's canonical bundle and the frontend's copy.

All asserted values come from the project's fixed constants (config / physics)
and from the bundle the demo ships. They are NOT recomputed loosely here — they
are exact (ints / labels) or tight intervals (floats), so a drift in any
headline number breaks this test instead of silently shipping a wrong demo.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ofab.demo.replay_data import build_bundle
from ofab.models import RunMode

# Repository root (this file lives at backend/tests/test_replay_bundle.py).
REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_BUNDLE_JSON = REPO_ROOT / "data" / "demo_bundle.json"
FRONTEND_DEMO_JSON = REPO_ROOT / "frontend" / "src" / "data" / "demoRuns.json"


@pytest.fixture(scope="module")
def bundle() -> dict:
    return build_bundle(RunMode.REPLAY)


# --------------------------------------------------------------------------- #
# Top-level shape                                                             #
# --------------------------------------------------------------------------- #
def test_bundle_top_level_keys(bundle: dict) -> None:
    required = {
        "case", "profiles", "runs", "scorecards", "diagnoses", "rewards",
        "workflows", "timeline", "comparison", "experience", "story", "flywheel",
        "second_case",
    }
    missing = required - set(bundle.keys())
    assert not missing, f"bundle missing keys: {sorted(missing)}"


def test_bundle_mode_is_replay(bundle: dict) -> None:
    assert bundle["mode"] == RunMode.REPLAY.value == "replay"


# --------------------------------------------------------------------------- #
# Comparison cards — the headline numbers                                     #
# --------------------------------------------------------------------------- #
def test_comparison_rerun_count(bundle: dict) -> None:
    rc = bundle["comparison"]["rerun_count"]
    assert rc["before"] == 5
    assert rc["after"] == 2


def test_comparison_time_to_pass(bundle: dict) -> None:
    t = bundle["comparison"]["time_to_pass"]
    assert t["before"] == pytest.approx(747.4)
    assert t["after"] == pytest.approx(249.8)
    assert t["before_label"] == "12m 27s"
    assert t["after_label"] == "4m 10s"


def test_comparison_qoi_error(bundle: dict) -> None:
    q = bundle["comparison"]["qoi_error"]
    assert q["before"] == pytest.approx(0.0872)
    assert q["after"] == pytest.approx(0.02115)
    # before > tolerance (agent-only stalls), after < tolerance (passes).
    assert q["before"] > 0.05
    assert q["after"] < 0.05


def test_comparison_false_success_detected(bundle: dict) -> None:
    f = bundle["comparison"]["false_success_detected"]
    assert f["before"] == 0
    assert f["after"] == 3


def test_comparison_experience_records(bundle: dict) -> None:
    e = bundle["comparison"]["experience_records"]
    assert e["before"] == 0
    assert e["after"] == 3


# --------------------------------------------------------------------------- #
# Workflow metrics                                                            #
# --------------------------------------------------------------------------- #
def _workflows_by_name(bundle: dict) -> dict[str, dict]:
    return {w["workflow"]: w for w in bundle["workflows"]}


def test_workflows_both_present(bundle: dict) -> None:
    wf = _workflows_by_name(bundle)
    assert set(wf) == {"agent_only", "agent_plus_benchmark"}


def test_agent_plus_benchmark_regression_and_repair_rate(bundle: dict) -> None:
    ab = _workflows_by_name(bundle)["agent_plus_benchmark"]
    assert ab["regression_cases_promoted"] == 3
    assert ab["auto_repair_success_rate"] == pytest.approx(1.0)


def test_agent_only_repair_rate_is_zero(bundle: dict) -> None:
    ao = _workflows_by_name(bundle)["agent_only"]
    assert ao["auto_repair_success_rate"] == pytest.approx(0.0)
    # agent-only has no benchmark feedback => promotes nothing.
    assert ao["regression_cases_promoted"] == 0


def test_workflow_metrics_match_comparison(bundle: dict) -> None:
    """Comparison cards are derived from the workflow metrics; they must agree."""
    wf = _workflows_by_name(bundle)
    cmp = bundle["comparison"]
    assert wf["agent_only"]["rerun_count"] == cmp["rerun_count"]["before"]
    assert wf["agent_plus_benchmark"]["rerun_count"] == cmp["rerun_count"]["after"]
    assert wf["agent_only"]["final_qoi_error"] == pytest.approx(cmp["qoi_error"]["before"])
    assert wf["agent_plus_benchmark"]["final_qoi_error"] == pytest.approx(cmp["qoi_error"]["after"])


# --------------------------------------------------------------------------- #
# Hero velocity profiles                                                      #
# --------------------------------------------------------------------------- #
def test_profile_qoi_errors(bundle: dict) -> None:
    p = bundle["profiles"]
    assert p["reference"]["qoi_error"] == pytest.approx(0.0)
    # failed ~ 18.4%, repaired ~ 2.1%, agent-only plateau ~ 8.7%.
    assert p["failed"]["qoi_error"] == pytest.approx(0.1842, abs=2e-3)
    assert p["repaired"]["qoi_error"] == pytest.approx(0.0211, abs=2e-3)
    assert p["agent_only_final"]["qoi_error"] == pytest.approx(0.0872, abs=2e-3)


def test_profile_qoi_ordering(bundle: dict) -> None:
    """failed worst > plateau > repaired best; only repaired passes tolerance."""
    p = bundle["profiles"]
    failed = p["failed"]["qoi_error"]
    plateau = p["agent_only_final"]["qoi_error"]
    repaired = p["repaired"]["qoi_error"]
    assert failed > plateau > repaired
    assert repaired < 0.05 <= plateau


# --------------------------------------------------------------------------- #
# Hero reward swing + per-fault diagnosis — the diagnosis-panel numbers        #
# --------------------------------------------------------------------------- #
def test_hero_reward_swings_negative_to_positive(bundle: dict) -> None:
    """The diagnosis panel shows the hero bc_mismatch reward going from clearly
    negative (needs repair) to clearly positive (accept): -0.37 -> +0.71."""
    rewards = {r["run_id"]: r for r in bundle["rewards"]}
    hero = sorted(
        (r for r in bundle["runs"]
         if r["workflow"] == "agent_plus_benchmark" and r["fault"] == "bc_mismatch"),
        key=lambda r: r["round_index"],
    )
    assert [r["round_index"] for r in hero] == [0, 1, 2]
    before = rewards[hero[0]["run_id"]]["total_reward"]
    after = rewards[hero[-1]["run_id"]]["total_reward"]
    assert before == pytest.approx(-0.373, abs=5e-3)
    assert after == pytest.approx(0.711, abs=5e-3)
    assert before < 0 < after  # the sign flip the demo highlights


def test_per_fault_diagnosis_modes(bundle: dict) -> None:
    """Each injected fault is diagnosed as its expected failure mode in the
    benchmark workflow's first (unrepaired) round."""
    diags = {d["run_id"]: d for d in bundle["diagnoses"]}
    expected = {
        "bc_mismatch": "BC_MISMATCH",
        "coarse_mesh": "MESH_TOO_COARSE",
        "solver_setting_error": "RESIDUAL_NOT_CONVERGED",
    }
    for fault, mode in expected.items():
        r0 = next(
            r for r in bundle["runs"]
            if r["workflow"] == "agent_plus_benchmark"
            and r["fault"] == fault and r["round_index"] == 0
        )
        d = diags[r0["run_id"]]
        assert d["failure_mode"] == mode, f"{fault} -> {d['failure_mode']} (want {mode})"
        assert 0.0 < d["confidence"] <= 1.0


# --------------------------------------------------------------------------- #
# Flywheel — store → recall → faster on recurrence                            #
# --------------------------------------------------------------------------- #
def test_flywheel_present_and_shaped(bundle: dict) -> None:
    fw = bundle["flywheel"]
    assert fw["fault"] == "bc_mismatch"
    assert fw["failure_mode"] == "BC_MISMATCH"
    for k in ("symptom", "repair", "outcome"):
        assert fw["recalled"][k]  # non-empty recalled lesson


def test_flywheel_recurrence_is_faster(bundle: dict) -> None:
    fw = bundle["flywheel"]
    first, second = fw["first_encounter"], fw["second_encounter"]
    # recall cuts a repair round and wall-clock time.
    assert second["rerun_count"] < first["rerun_count"]
    assert second["time_s"] < first["time_s"]
    assert fw["rounds_saved"] == first["rerun_count"] - second["rerun_count"]
    assert fw["time_saved_pct"] < 0  # negative = faster


def test_flywheel_paths_start_failed_end_passing(bundle: dict) -> None:
    fw = bundle["flywheel"]
    tol_pct = bundle["case"]["tolerances"]["qoi_l2"] * 100
    for enc in (fw["first_encounter"], fw["second_encounter"]):
        path = enc["path_pct"]
        assert path[0] > tol_pct           # starts as a failure
        assert path[-1] < tol_pct          # ends within tolerance
    # second encounter skips the intermediate exploration step.
    assert len(fw["first_encounter"]["path_pct"]) == 3
    assert len(fw["second_encounter"]["path_pct"]) == 2


def test_flywheel_recalled_matches_stored_experience(bundle: dict) -> None:
    """The recalled lesson is exactly the stored bc_mismatch experience record."""
    fw = bundle["flywheel"]
    bc_exp = next(e for e in bundle["experience"] if e["failure_mode"] == "BC_MISMATCH")
    assert fw["recalled"]["symptom"] == bc_exp["symptom"]
    assert fw["recalled"]["repair"] == bc_exp["repair"]
    assert fw["recalled"]["outcome"] == bc_exp["outcome"]


# --------------------------------------------------------------------------- #
# Second case (Couette) — the benchmark generalises                           #
# --------------------------------------------------------------------------- #
def test_second_case_identity(bundle: dict) -> None:
    sc = bundle["second_case"]
    assert sc["case"]["id"] == "couette_shear"
    assert sc["case"]["reynolds"] == pytest.approx(20.0)
    assert sc["case"]["u_max"] == pytest.approx(0.10)
    # shares the hero case's benchmark tolerances (same judge, different flow)
    assert sc["case"]["tolerances"]["qoi_l2"] == bundle["case"]["tolerances"]["qoi_l2"]


def test_second_case_profiles_land_on_targets(bundle: dict) -> None:
    p = bundle["second_case"]["profiles"]
    assert p["reference"]["qoi_error"] == pytest.approx(0.0)
    # injected stationary-wall slip -> 18% (false success), repaired -> 2% (passes)
    assert p["failed"]["qoi_error"] == pytest.approx(0.18, abs=1e-3)
    assert p["repaired"]["qoi_error"] == pytest.approx(0.02, abs=1e-3)
    assert p["failed"]["qoi_error"] > 0.05 > p["repaired"]["qoi_error"]


def test_second_case_same_benchmark_catches_false_success(bundle: dict) -> None:
    """The crux: the unchanged scorecard flags the Couette run as a false success
    and the unchanged diagnosis classifies it BC_MISMATCH from the wall slip."""
    sc = bundle["second_case"]
    assert sc["scorecard"]["false_success"] is True
    assert sc["scorecard"]["overall_pass"] is False
    assert sc["diagnosis"]["failure_mode"] == "BC_MISMATCH"
    assert 0.0 < sc["diagnosis"]["confidence"] <= 1.0
    assert sc["wall_slip_pct"] == pytest.approx(18.0, abs=0.5)
    # and the repaired run passes the same benchmark
    assert sc["repaired_pass"] is True


def test_second_case_documents_inapplicable_fault(bundle: dict) -> None:
    """Honest physics: coarse_mesh does not apply to a linear profile."""
    na = bundle["second_case"]["not_applicable"]
    assert na["fault"] == "coarse_mesh"
    assert na["reason"]  # non-empty explanation


# --------------------------------------------------------------------------- #
# Sync invariant — the load-bearing one                                       #
# --------------------------------------------------------------------------- #
def test_demo_data_files_exist() -> None:
    assert DEMO_BUNDLE_JSON.is_file(), f"missing {DEMO_BUNDLE_JSON}"
    assert FRONTEND_DEMO_JSON.is_file(), f"missing {FRONTEND_DEMO_JSON}"


def test_backend_and_frontend_bundles_identical() -> None:
    """The backend canonical bundle and the frontend copy must be byte-for-byte
    equal once parsed — they are written from the same object by seed()."""
    backend = json.loads(DEMO_BUNDLE_JSON.read_text())
    frontend = json.loads(FRONTEND_DEMO_JSON.read_text())
    assert backend == frontend


def test_persisted_bundle_matches_freshly_built(bundle: dict) -> None:
    """The committed demo_bundle.json must reflect the current build_bundle()
    output — i.e. the headline numbers on disk are not stale."""
    persisted = json.loads(DEMO_BUNDLE_JSON.read_text())
    pc = persisted["comparison"]
    bc = bundle["comparison"]
    assert pc["rerun_count"] == bc["rerun_count"]
    assert pc["time_to_pass"] == bc["time_to_pass"]
    assert pc["qoi_error"] == bc["qoi_error"]
    assert pc["false_success_detected"] == bc["false_success_detected"]
    assert pc["experience_records"] == bc["experience_records"]
