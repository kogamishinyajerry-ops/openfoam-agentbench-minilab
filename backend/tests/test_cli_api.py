"""Tests for the ofab CLI (typer) and FastAPI surface.

These tests assert *real invariants* of the benchmark-feedback loop, not
just "the process exits 0":

  - `ofab run --fault bc_mismatch --mode mock` must produce a run that ran
    fine (execution success) yet is engineering-wrong (needs_repair) — i.e.
    the project's whole thesis: a benchmark catches a FALSE SUCCESS.
  - The `ofab benchmark` chain must flag that false success.
  - The FastAPI bundle/summary routes must return the seeded head-to-head
    numbers (before=0, after=3 false successes; before=5/after=2 reruns; …).
  - A missing route is 404; POST /api/demo/run with a legal body runs the
    benchmark layer in-process.

CLI is exercised both via subprocess (the installed `ofab` console script,
real exit codes) and via typer's CliRunner (in-process, fast). The API is
exercised purely with fastapi.testclient.TestClient — no uvicorn, no port.

The CLI `run`/`benchmark` commands write to ``runs/`` (the package's transient
per-run output dir, derived from __file__), NOT to the protected ``data/``
real-data files. We never write under ``data/``.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from ofab.api import app as fastapi_app
from ofab.cli import app as cli_app
from ofab import config, paths
from ofab.runner.replay_runner import BundleNotFound, load_bundle


# --------------------------------------------------------------------------- #
# Fixtures / module-level guards                                              #
# --------------------------------------------------------------------------- #
ROOT = paths.REPO_ROOT
VENV_OFAB = ROOT / ".venv" / "bin" / "ofab"


def _bundle_available() -> bool:
    try:
        load_bundle()
        return True
    except BundleNotFound:
        return False


bundle_required = pytest.mark.skipif(
    not _bundle_available(),
    reason="demo bundle not seeded (run `ofab demo seed`); API GET routes need it",
)


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(fastapi_app)


@pytest.fixture(scope="module")
def runner() -> CliRunner:
    return CliRunner()


# --------------------------------------------------------------------------- #
# CLI — in-process via typer CliRunner                                        #
# --------------------------------------------------------------------------- #
def test_cli_run_bc_mismatch_mock_is_false_success(runner: CliRunner):
    """`ofab run --fault bc_mismatch --mode mock` exits 0 and the run is a
    FALSE SUCCESS: execution succeeded but engineering needs repair.

    Asserts the run actually got persisted to runs/latest.json with the fixed
    bc_mismatch invariants (wall_slip≈0.283, qoi≈0.184), so the command did
    real work — not a vacuous exit-0."""
    result = runner.invoke(
        cli_app, ["run", "--fault", "bc_mismatch", "--mode", "mock"]
    )
    assert result.exit_code == 0, result.output

    latest = paths.RUNS_DIR / "latest.json"
    assert latest.exists()
    run = json.loads(latest.read_text())

    assert run["fault"] == "bc_mismatch"
    assert run["mode"] == "mock"
    # ran fine ...
    assert run["execution_status"] == "success"
    # ... yet engineering-wrong: the false success the benchmark must catch.
    assert run["engineering_status"] == "needs_repair"
    # fixed physics constants for bc_mismatch (slip=0.283, L2≈0.184).
    assert run["features"]["wall_slip"] == pytest.approx(0.283, abs=1e-6)
    assert run["qoi_error"] == pytest.approx(0.184, abs=0.01)
    assert run["qoi_error"] > 0.05  # above the QOI_L2_TOL, so it fails


def test_cli_run_repaired_passes(runner: CliRunner):
    """The repaired bc_mismatch case must cross the pass line (L2≈0.021 < 0.05)
    and report engineering pass."""
    result = runner.invoke(
        cli_app,
        ["run", "--fault", "bc_mismatch", "--mode", "mock", "--repaired"],
    )
    assert result.exit_code == 0, result.output
    run = json.loads((paths.RUNS_DIR / "latest.json").read_text())
    assert run["execution_status"] == "success"
    assert run["qoi_error"] == pytest.approx(0.021, abs=0.01)
    assert run["qoi_error"] < 0.05
    assert run["engineering_status"] == "pass"


# --------------------------------------------------------------------------- #
# CLI — second case: the --case flag must actually switch flows                #
# (regression lock for the fixed bug where --case was ignored -> always hero)  #
# --------------------------------------------------------------------------- #
def test_cli_run_couette_case_switches_flow_and_is_false_success(runner: CliRunner):
    """`ofab run --case couette_shear --mode mock` must run the SECOND flow, not
    the hero. The persisted run's case_id has to be couette_shear (this is the
    regression lock: before the fix, --case was ignored and it always ran
    Poiseuille). The Couette bc fault is a false success: ran fine, engineering
    needs repair, wall slip above tolerance, L2 ≈ the injected slip (~18%)."""
    result = runner.invoke(
        cli_app, ["run", "--case", "couette_shear", "--mode", "mock"]
    )
    assert result.exit_code == 0, result.output
    run = json.loads((paths.RUNS_DIR / "latest.json").read_text())

    assert run["case_id"] == config.COUETTE_CASE_ID    # the flag actually switched flows
    assert run["case_id"] != config.CASE_ID            # ... and is NOT the hero case
    assert run["fault"] == "bc_mismatch"               # default injected fault
    # ran fine yet engineering-wrong — the false success on a different flow.
    assert run["execution_status"] == "success"
    assert run["engineering_status"] == "needs_repair"
    assert run["qoi_error"] == pytest.approx(config.COUETTE_BC_SLIP, abs=1e-2)  # ~0.18
    assert run["qoi_error"] > config.QOI_L2_TOL
    assert run["features"]["wall_slip"] > config.WALL_SLIP_TOL


def test_cli_run_default_case_is_the_hero(runner: CliRunner):
    """The contrast that proves --case selects: with no --case, the run is the
    hero channel_poiseuille (so the couette assertion above isn't vacuously true
    for every invocation)."""
    result = runner.invoke(cli_app, ["run", "--fault", "bc_mismatch", "--mode", "mock"])
    assert result.exit_code == 0, result.output
    run = json.loads((paths.RUNS_DIR / "latest.json").read_text())
    assert run["case_id"] == config.CASE_ID            # channel_poiseuille


def test_cli_run_couette_repaired_passes(runner: CliRunner):
    """The repaired Couette case crosses the pass line (L2 ≈ 2% < 5%) — the same
    acceptance band as the hero, judged by the same unchanged benchmark."""
    result = runner.invoke(
        cli_app,
        ["run", "--case", "couette_shear", "--mode", "mock", "--repaired"],
    )
    assert result.exit_code == 0, result.output
    run = json.loads((paths.RUNS_DIR / "latest.json").read_text())
    assert run["case_id"] == config.COUETTE_CASE_ID
    assert run["qoi_error"] == pytest.approx(config.COUETTE_REPAIR_SLIP, abs=1e-2)  # ~0.02
    assert run["qoi_error"] < config.QOI_L2_TOL
    assert run["engineering_status"] == "pass"


def test_cli_benchmark_couette_flags_false_success(runner: CliRunner):
    """The generalisation claim through the actual CLI: `ofab run --case
    couette_shear` then `ofab benchmark runs/latest` runs the SAME unchanged
    scoring chain on the second flow and flags its false success — proof the
    benchmark is case-agnostic end-to-end, not just inside the pre-built bundle."""
    r1 = runner.invoke(
        cli_app, ["run", "--case", "couette_shear", "--mode", "mock"]
    )
    assert r1.exit_code == 0, r1.output
    r2 = runner.invoke(cli_app, ["benchmark", "runs/latest"])
    assert r2.exit_code == 0, r2.output
    assert "FALSE SUCCESS" in r2.output

    sc = json.loads((paths.RUNS_DIR / "scorecard.json").read_text())
    assert sc["false_success"] is True
    assert sc["overall_pass"] is False


# --------------------------------------------------------------------------- #
# CLI — third case (round pipe): the --case flag switches flow AND the bare      #
# invocation showcases the pipe's HERO fault (coarse_mesh), not the global       #
# bc_mismatch default. This is what makes `ofab run --case pipe_poiseuille` a     #
# real false-success demo instead of a vacuous clean pass.                       #
# --------------------------------------------------------------------------- #
def test_cli_run_pipe_case_switches_flow_and_heroes_coarse_mesh(runner: CliRunner):
    """`ofab run --case pipe_poiseuille --mode mock` (no --fault) must run the THIRD
    flow AND inject the pipe's hero fault coarse_mesh — NOT the global bc_mismatch
    default (which the pipe's synthetic path doesn't model, so it would be a vacuous
    clean pass). The result is a false success on a *different fault*: ran fine, needs
    repair, radial mesh too coarse so the curved profile's peak is clipped (~7.9% L2)."""
    result = runner.invoke(
        cli_app, ["run", "--case", "pipe_poiseuille", "--mode", "mock"]
    )
    assert result.exit_code == 0, result.output
    run = json.loads((paths.RUNS_DIR / "latest.json").read_text())

    assert run["case_id"] == config.PIPE_CASE_ID       # flag switched to the third flow
    assert run["case_id"] != config.CASE_ID            # ... not the hero channel
    assert run["case_id"] != config.COUETTE_CASE_ID    # ... not the Couette case
    # the bare invocation defaults to the PIPE'S hero, not the global bc_mismatch.
    assert run["fault"] == "coarse_mesh"
    # ran fine yet engineering-wrong — the false success on a third flow + a new fault.
    assert run["execution_status"] == "success"
    assert run["engineering_status"] == "needs_repair"
    assert 0.06 < run["qoi_error"] < 0.10              # clipped-peak band (~7.9%)
    assert run["qoi_error"] > config.QOI_L2_TOL


def test_cli_run_pipe_explicit_fault_is_honored_verbatim(runner: CliRunner):
    """An explicit --fault is honored exactly — NOT silently swapped to the pipe's
    hero. `--fault bc_mismatch` on the pipe records bc_mismatch (the synthetic pipe
    doesn't model that fault, so it yields the clean parabola — an honest 'this fault
    isn't injected here', not a fabricated failure). This guards the default-swap from
    over-reaching into explicit user choices."""
    result = runner.invoke(
        cli_app,
        ["run", "--case", "pipe_poiseuille", "--fault", "bc_mismatch", "--mode", "mock"],
    )
    assert result.exit_code == 0, result.output
    run = json.loads((paths.RUNS_DIR / "latest.json").read_text())
    assert run["case_id"] == config.PIPE_CASE_ID
    assert run["fault"] == "bc_mismatch"               # honored, NOT swapped to coarse_mesh
    # explicit coarse_mesh reaches the same hero false success as the bare default.
    r2 = runner.invoke(
        cli_app,
        ["run", "--case", "pipe_poiseuille", "--fault", "coarse_mesh", "--mode", "mock"],
    )
    assert r2.exit_code == 0, r2.output
    run2 = json.loads((paths.RUNS_DIR / "latest.json").read_text())
    assert run2["fault"] == "coarse_mesh"
    assert run2["engineering_status"] == "needs_repair"
    assert run2["qoi_error"] > config.QOI_L2_TOL


def test_cli_run_pipe_repaired_passes(runner: CliRunner):
    """The repaired pipe case (refined radial mesh) crosses the pass line — the same
    acceptance band as the other two cases, judged by the same unchanged benchmark."""
    result = runner.invoke(
        cli_app,
        ["run", "--case", "pipe_poiseuille", "--mode", "mock", "--repaired"],
    )
    assert result.exit_code == 0, result.output
    run = json.loads((paths.RUNS_DIR / "latest.json").read_text())
    assert run["case_id"] == config.PIPE_CASE_ID
    assert run["qoi_error"] < config.QOI_L2_TOL        # refined mesh resolves the parabola
    assert run["engineering_status"] == "pass"


def test_cli_benchmark_pipe_flags_mesh_false_success(runner: CliRunner):
    """Generalisation to a different FAULT, end-to-end through the CLI: `ofab run
    --case pipe_poiseuille` then `ofab benchmark` + `ofab diagnose` on runs/latest
    runs the SAME unchanged scoring/diagnosis chain on the third flow, flags its
    false success, and classifies it as MESH_TOO_COARSE — distinct from the
    BC_MISMATCH the other two cases hero. Proof the benchmark is case- AND
    fault-agnostic end-to-end, not just inside the pre-built bundle."""
    r1 = runner.invoke(cli_app, ["run", "--case", "pipe_poiseuille", "--mode", "mock"])
    assert r1.exit_code == 0, r1.output

    r2 = runner.invoke(cli_app, ["benchmark", "runs/latest"])
    assert r2.exit_code == 0, r2.output
    assert "FALSE SUCCESS" in r2.output
    sc = json.loads((paths.RUNS_DIR / "scorecard.json").read_text())
    assert sc["false_success"] is True
    assert sc["overall_pass"] is False

    r3 = runner.invoke(cli_app, ["diagnose", "runs/latest"])
    assert r3.exit_code == 0, r3.output
    assert "MESH_TOO_COARSE" in r3.output              # the pipe's hero failure mode
    dg = json.loads((paths.RUNS_DIR / "diagnosis.json").read_text())
    assert dg["failure_mode"] == "MESH_TOO_COARSE"
    assert dg["failure_mode"] != "BC_MISMATCH"         # ... NOT the other cases' hero


def test_cli_benchmark_chain_flags_false_success(runner: CliRunner):
    """`ofab run` (bc_mismatch/mock) then `ofab benchmark runs/latest` runs the
    scoring chain end to end and prints the FALSE SUCCESS verdict."""
    r1 = runner.invoke(
        cli_app, ["run", "--fault", "bc_mismatch", "--mode", "mock"]
    )
    assert r1.exit_code == 0, r1.output

    r2 = runner.invoke(cli_app, ["benchmark", "runs/latest"])
    assert r2.exit_code == 0, r2.output
    assert "FALSE SUCCESS" in r2.output

    # the scorecard artifact must agree with the printed verdict.
    sc = json.loads((paths.RUNS_DIR / "scorecard.json").read_text())
    assert sc["false_success"] is True
    assert sc["overall_pass"] is False


def test_cli_benchmark_repaired_no_false_success(runner: CliRunner):
    """After repair the scorecard must show overall_pass and NOT a false
    success — the benchmark verdict tracks the engineering reality."""
    runner.invoke(
        cli_app,
        ["run", "--fault", "bc_mismatch", "--mode", "mock", "--repaired"],
    )
    r = runner.invoke(cli_app, ["benchmark", "runs/latest"])
    assert r.exit_code == 0, r.output
    assert "FALSE SUCCESS" not in r.output
    sc = json.loads((paths.RUNS_DIR / "scorecard.json").read_text())
    assert sc["false_success"] is False
    assert sc["overall_pass"] is True


def test_cli_no_args_shows_help(runner: CliRunner):
    """Bare `ofab` is configured no_args_is_help; it must not crash."""
    result = runner.invoke(cli_app, [])
    # typer/click exits 0 (or 2) on help, never a traceback.
    assert result.exit_code in (0, 2)
    assert "Usage" in result.output or "benchmark" in result.output


@bundle_required
def test_cli_recall_hits_seeded_experience(runner: CliRunner):
    """`ofab recall --fault bc_mismatch` finds the seeded lesson in the experience
    store and prints the recalled failure mode (the flywheel's retrieval half).

    Depends on the same seeding as the bundle (seed() populates the store)."""
    result = runner.invoke(cli_app, ["recall", "--fault", "bc_mismatch"])
    assert result.exit_code == 0, result.output
    assert "BC_MISMATCH" in result.output


# --------------------------------------------------------------------------- #
# CLI — subprocess via the installed `ofab` console script (real exit codes)  #
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(
    not VENV_OFAB.exists(), reason="venv `ofab` console script not installed"
)
def test_cli_subprocess_run_exit_zero():
    """The installed console script `ofab run --fault bc_mismatch --mode mock`
    exits 0 and prints the RunResult panel for a real (sub)process — proves the
    entry point is wired, not just the in-process app object."""
    proc = subprocess.run(
        [str(VENV_OFAB), "run", "--fault", "bc_mismatch", "--mode", "mock"],
        capture_output=True,
        text=True,
        cwd=str(paths.BACKEND_DIR),
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    out = proc.stdout
    assert "RunResult" in out
    assert "bc_mismatch" in out


# --------------------------------------------------------------------------- #
# API — health (works whether or not seeded)                                  #
# --------------------------------------------------------------------------- #
def test_api_health_ok(client: TestClient):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["seeded"] is _bundle_available()


# --------------------------------------------------------------------------- #
# API — GET bundle / summary / metrics (the seeded head-to-head numbers)      #
# --------------------------------------------------------------------------- #
@bundle_required
def test_api_bundle_200_contains_comparison(client: TestClient):
    """GET /api/demo/bundle -> 200 and JSON contains the comparison block with
    the fixed head-to-head numbers."""
    r = client.get("/api/demo/bundle")
    assert r.status_code == 200
    b = r.json()
    assert "comparison" in b
    cmp = b["comparison"]
    # before/after false successes: agent-only catches 0, agent+benchmark 3.
    assert cmp["false_success_detected"]["before"] == 0
    assert cmp["false_success_detected"]["after"] == 3
    assert cmp["experience_records"]["before"] == 0
    assert cmp["experience_records"]["after"] == 3
    # reruns 5 -> 2.
    assert cmp["rerun_count"]["before"] == 5
    assert cmp["rerun_count"]["after"] == 2
    # final QoI error 8.7% -> 2.1%.
    assert cmp["qoi_error"]["before"] == pytest.approx(0.0872, abs=1e-4)
    assert cmp["qoi_error"]["after"] == pytest.approx(0.02115, abs=1e-4)


@bundle_required
def test_api_summary_200_contains_comparison(client: TestClient):
    """GET /api/demo/summary -> 200 and exposes the same comparison block."""
    r = client.get("/api/demo/summary")
    assert r.status_code == 200
    b = r.json()
    assert "comparison" in b
    assert b["comparison"]["rerun_count"]["before"] == 5
    assert b["comparison"]["rerun_count"]["after"] == 2


@bundle_required
def test_api_metrics_time_to_pass(client: TestClient):
    """GET /api/demo/metrics -> 200; time_to_pass before 747.4s / after 249.8s."""
    r = client.get("/api/demo/metrics")
    assert r.status_code == 200
    cmp = r.json()["comparison"]
    assert cmp["time_to_pass"]["before"] == pytest.approx(747.4, abs=0.1)
    assert cmp["time_to_pass"]["after"] == pytest.approx(249.8, abs=0.1)
    assert cmp["time_to_pass"]["before_label"] == "12m 27s"
    assert cmp["time_to_pass"]["after_label"] == "4m 10s"


@bundle_required
def test_api_profile_route(client: TestClient):
    """GET /api/demo/profile -> 200; failed≈18.4%, repaired≈2.1%, agent_only≈8.7%."""
    r = client.get("/api/demo/profile")
    assert r.status_code == 200
    profiles = r.json()["profiles"]
    assert profiles["failed"]["qoi_error"] == pytest.approx(0.1842, abs=2e-3)
    assert profiles["repaired"]["qoi_error"] == pytest.approx(0.0211, abs=2e-3)
    assert profiles["agent_only_final"]["qoi_error"] == pytest.approx(
        0.0872, abs=2e-3
    )


@bundle_required
def test_api_flywheel_route(client: TestClient):
    """GET /api/demo/flywheel -> 200; the recurrence (second encounter) recalls a
    stored lesson and is fewer reruns + faster than the first encounter."""
    r = client.get("/api/demo/flywheel")
    assert r.status_code == 200
    fw = r.json()["flywheel"]
    assert fw["fault"] == "bc_mismatch"
    assert fw["second_encounter"]["rerun_count"] < fw["first_encounter"]["rerun_count"]
    assert fw["second_encounter"]["time_s"] < fw["first_encounter"]["time_s"]
    assert fw["recalled"]["repair"]  # non-empty recalled fix


def test_api_second_case_route(client: TestClient):
    """GET /api/demo/second-case -> 200; the same benchmark catches a false success
    on a different flow (Couette) and diagnoses BC_MISMATCH."""
    r = client.get("/api/demo/second-case")
    assert r.status_code == 200
    sc = r.json()["second_case"]
    assert sc["case"]["id"] == "couette_shear"
    assert sc["scorecard"]["false_success"] is True
    assert sc["diagnosis"]["failure_mode"] == "BC_MISMATCH"
    assert sc["repaired_pass"] is True


# --------------------------------------------------------------------------- #
# API — error handling                                                        #
# --------------------------------------------------------------------------- #
def test_api_unknown_route_404(client: TestClient):
    r = client.get("/api/demo/does-not-exist")
    assert r.status_code == 404


def test_api_get_on_post_only_run_is_405(client: TestClient):
    """/api/demo/run is POST-only; a GET must be 405, not 200/404."""
    r = client.get("/api/demo/run")
    assert r.status_code == 405


# --------------------------------------------------------------------------- #
# API — POST /api/demo/run (legal body, in-process benchmark layer)           #
# --------------------------------------------------------------------------- #
def test_api_post_run_bc_mismatch_mock(client: TestClient):
    """POST /api/demo/run with a legal body (bc_mismatch / mock /
    agent_plus_benchmark) -> 200, and because a benchmark is attached the
    response includes run + scorecard + diagnosis + reward, with the scorecard
    flagging the false success."""
    r = client.post(
        "/api/demo/run",
        json={
            "fault": "bc_mismatch",
            "mode": "mock",
            "repaired": False,
            "workflow": "agent_plus_benchmark",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert {"run", "scorecard", "diagnosis", "reward"} <= set(body)

    run = body["run"]
    assert run["fault"] == "bc_mismatch"
    assert run["execution_status"] == "success"
    assert run["engineering_status"] == "needs_repair"
    assert run["qoi_error"] == pytest.approx(0.184, abs=0.01)

    sc = body["scorecard"]
    assert sc["false_success"] is True
    assert sc["overall_pass"] is False

    # bc_mismatch (residual ok, wall_slip≥tol) must diagnose BC_MISMATCH.
    assert body["diagnosis"]["failure_mode"] == "BC_MISMATCH"
    assert 0.0 < body["diagnosis"]["confidence"] <= 1.0
    # not converged => repair, and engineering reward is the clip of qoi.
    assert body["reward"]["decision"] == "repair_and_rerun"


def test_api_post_run_repaired_passes(client: TestClient):
    """POST a repaired bc_mismatch run -> overall_pass True, no false success,
    decision accept."""
    r = client.post(
        "/api/demo/run",
        json={
            "fault": "bc_mismatch",
            "mode": "mock",
            "repaired": True,
            "workflow": "agent_plus_benchmark",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["run"]["engineering_status"] == "pass"
    assert body["run"]["qoi_error"] < 0.05
    assert body["scorecard"]["false_success"] is False
    assert body["scorecard"]["overall_pass"] is True
    assert body["reward"]["decision"] == "accept"


def test_api_post_run_agent_only_has_no_benchmark(client: TestClient):
    """agent_only workflow attaches no benchmark: the response carries only
    `run` (no scorecard/diagnosis/reward) — that's exactly why agent-only can't
    see the false success."""
    r = client.post(
        "/api/demo/run",
        json={
            "fault": "bc_mismatch",
            "mode": "mock",
            "workflow": "agent_only",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "run" in body
    assert "scorecard" not in body
    assert "diagnosis" not in body
    assert "reward" not in body


def test_api_post_run_invalid_fault_422(client: TestClient):
    """An illegal enum value must be a 422 validation error, not a 500."""
    r = client.post("/api/demo/run", json={"fault": "not_a_fault"})
    assert r.status_code == 422


def test_api_post_run_defaults_with_empty_body(client: TestClient):
    """RunRequest has all-default fields; an empty body is legal and defaults to
    bc_mismatch / mock / agent_plus_benchmark."""
    r = client.post("/api/demo/run", json={})
    assert r.status_code == 200, r.text
    run = r.json()["run"]
    assert run["fault"] == "bc_mismatch"
    assert run["mode"] == "mock"
