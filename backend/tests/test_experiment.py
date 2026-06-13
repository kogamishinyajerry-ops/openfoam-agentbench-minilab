"""End-to-end lock for the `ofab experiment` flow (seed_experiment.run_experiment).

A documented core command (README "重新生成全部产物", Makefile `experiment`) that
takes a protocol.yaml and emits the per-run artifacts + a human-readable report.md.
It was previously untested. This drives the real entry point against a TEMP
protocol so every output lands in tmp.

Convention note: `run_experiment` also calls `seed()` to refresh the canonical
bundle, which writes under the protected `data/` + `frontend/src/data/` dirs. The
rest of the suite's discipline is "we never write under data/", so we monkeypatch
`seed` to a no-op here — that isolates the side effect under test (artifact + report
generation) and keeps committed data files untouched. `build_bundle` is pure
(in-memory), so neutering `seed` leaves nothing writing outside tmp.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ofab.demo.seed_experiment import run_experiment


def _write_protocol(tmp: Path) -> Path:
    p = tmp / "protocol.yaml"
    p.write_text("mode: replay\nresults_dir: results\n")
    return p


@pytest.fixture()
def experiment(tmp_path, monkeypatch):
    # Neuter ONLY the canonical re-seed (the data/-writing side effect); the rest
    # of run_experiment (build + write artifacts/report to tmp) runs for real.
    monkeypatch.setattr("ofab.demo.seed_experiment.seed", lambda *a, **k: None)
    out = run_experiment(_write_protocol(tmp_path))
    return {"out": out, "dir": tmp_path}


def test_run_experiment_summary_reports_head_to_head(experiment):
    out = experiment["out"]
    assert out["mode"] == "replay"
    assert out["runs"] > 0
    # agent+benchmark catches all 3 false successes and sediments 3 lessons.
    assert out["false_success_detected"] == 3
    assert out["experience_records"] == 3


def test_run_experiment_writes_report_and_artifacts(experiment):
    tmp = experiment["dir"]

    # report.md is written next to the protocol (in tmp — committed repo untouched).
    report = tmp / "report.md"
    assert report.is_file()
    md = report.read_text()
    assert md.strip()
    assert "bc_mismatch" in md            # the hero fault section
    assert "假成功" in md                  # the thesis word (exit-0-but-wrong)
    assert "## 沉淀的经验" in md           # the flywheel / experience section

    # the per-run artifacts land in the protocol-relative results dir.
    results = tmp / "results"
    for name in [
        "bundle.json", "run_results.json", "scorecards.json", "diagnoses.json",
        "rewards.json", "metrics.json", "timeline.json", "comparison.json",
    ]:
        assert (results / name).is_file(), f"missing {name}"
    assert (results / "experience_record.jsonl").is_file()

    # the written bundle is the same shape the API/frontend consume.
    b = json.loads((results / "bundle.json").read_text())
    assert b["comparison"]["false_success_detected"]["after"] == 3


def test_run_experiment_report_has_comparison_table(experiment):
    md = (experiment["dir"] / "report.md").read_text()
    # the before/after comparison rows (claim 2 head-to-head, mirrors the dashboard).
    for row in ["重跑次数", "修对耗时", "抓到的假成功", "沉淀的经验", "自动修复成功率"]:
        assert row in md
