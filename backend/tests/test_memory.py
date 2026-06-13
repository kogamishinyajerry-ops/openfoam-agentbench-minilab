"""Tests for ofab.memory — case_miner.mine_experience + store.ExperienceStore.

These assert real invariants:
  * promote_to_regression is True iff a genuine failure (qoi_before >= 0.05)
    was repaired below tolerance (qoi_after < 0.05).
  * outcome text follows the exact "误差从 X% 降到 Y%" format.
  * symptom / repair are selected by failure_mode (and fall back sensibly).
  * ExperienceStore round-trips append/extend/all, clears, and returns []
    on a missing/empty file.

Every store path uses tmp_path — the real data/ directory is never touched.
"""
from __future__ import annotations

import pytest

from ofab import config
from ofab.memory.case_miner import _REPAIR, _SYMPTOM, mine_experience
from ofab.memory.store import ExperienceStore
from ofab.models import Diagnosis, ExperienceRecord, Fault, FailureMode


# --------------------------------------------------------------------------- #
# helpers                                                                     #
# --------------------------------------------------------------------------- #
def _diag(
    mode: FailureMode = FailureMode.BC_MISMATCH,
    *,
    repair: list[str] | None = None,
) -> Diagnosis:
    return Diagnosis(
        run_id="r1",
        failure_mode=mode,
        confidence=0.9,
        evidence=["e"],
        suggested_repair=repair if repair is not None else ["fix it"],
    )


def _record(
    *,
    case_id: str = "c",
    mode: FailureMode = FailureMode.BC_MISMATCH,
    promote: bool = True,
    rnd: int = 0,
) -> ExperienceRecord:
    return ExperienceRecord(
        case_id=case_id,
        failure_mode=mode,
        symptom="s",
        repair="r",
        outcome="o",
        promote_to_regression=promote,
        created_round=rnd,
    )


# --------------------------------------------------------------------------- #
# mine_experience: promote logic                                              #
# --------------------------------------------------------------------------- #
def test_tol_constant_is_what_we_assert_against():
    # Guard: the promote thresholds below are written against 0.05.
    assert config.QOI_L2_TOL == 0.05


def test_promote_true_when_genuine_failure_repaired_below_tol():
    # before >= 0.05 (real failure) AND after < 0.05 (now passing) -> promote.
    rec = mine_experience(_diag(), Fault.BC_MISMATCH, qoi_before=0.184, qoi_after=0.021)
    assert rec.promote_to_regression is True


def test_promote_false_when_before_already_below_tol():
    # before < 0.05 -> never a "real failure", nothing to promote even if after is tiny.
    rec = mine_experience(_diag(), Fault.BC_MISMATCH, qoi_before=0.04, qoi_after=0.01)
    assert rec.promote_to_regression is False


def test_promote_false_when_after_not_below_tol():
    # before >= 0.05 but after still >= 0.05 (plateau / agent-only) -> not promoted.
    rec = mine_experience(_diag(), Fault.BC_MISMATCH, qoi_before=0.184, qoi_after=0.087)
    assert rec.promote_to_regression is False


def test_promote_boundary_after_exactly_at_tol_is_not_promoted():
    # after == 0.05 fails strict "< tol" -> not promoted.
    rec = mine_experience(_diag(), Fault.BC_MISMATCH, qoi_before=0.184, qoi_after=0.05)
    assert rec.promote_to_regression is False


def test_promote_boundary_before_exactly_at_tol_counts_as_failure():
    # before == 0.05 satisfies ">= tol" -> counts as a genuine failure; after below -> promote.
    rec = mine_experience(_diag(), Fault.BC_MISMATCH, qoi_before=0.05, qoi_after=0.02)
    assert rec.promote_to_regression is True


# --------------------------------------------------------------------------- #
# mine_experience: outcome text + symptom/repair selection                    #
# --------------------------------------------------------------------------- #
def test_outcome_text_format():
    rec = mine_experience(_diag(), Fault.BC_MISMATCH, qoi_before=0.1842, qoi_after=0.0211)
    # 0.1842*100 -> 18.4, 0.0211*100 -> 2.1 (one decimal, rounded).
    assert rec.outcome == "误差从 18.4% 降到 2.1%"


def test_outcome_text_rounds_to_one_decimal():
    rec = mine_experience(_diag(), Fault.BC_MISMATCH, qoi_before=0.0872, qoi_after=0.02115)
    # 8.72 -> 8.7, 2.115 -> 2.1
    assert rec.outcome == "误差从 8.7% 降到 2.1%"


@pytest.mark.parametrize("mode", [
    FailureMode.BC_MISMATCH,
    FailureMode.MESH_TOO_COARSE,
    FailureMode.RESIDUAL_NOT_CONVERGED,
])
def test_symptom_and_repair_selected_by_failure_mode(mode):
    rec = mine_experience(_diag(mode), Fault.NONE, qoi_before=0.1, qoi_after=0.01)
    assert rec.failure_mode is mode
    assert rec.symptom == _SYMPTOM[mode]
    assert rec.repair == _REPAIR[mode]


def test_unknown_mode_falls_back_to_default_symptom_and_suggested_repair():
    # FailureMode.NONE is not in the _SYMPTOM/_REPAIR tables -> fallbacks fire.
    rec = mine_experience(
        _diag(FailureMode.NONE, repair=["手动校核全部边界"]),
        Fault.NONE,
        qoi_before=0.1,
        qoi_after=0.01,
    )
    assert rec.symptom == "工程检查未通过"
    # repair fallback = first suggested_repair entry.
    assert rec.repair == "手动校核全部边界"


def test_unknown_mode_empty_suggested_repair_yields_empty_string():
    rec = mine_experience(
        _diag(FailureMode.NONE, repair=[]),
        Fault.NONE,
        qoi_before=0.1,
        qoi_after=0.01,
    )
    assert rec.repair == ""


def test_case_id_and_round_passthrough():
    rec = mine_experience(
        _diag(),
        Fault.BC_MISMATCH,
        qoi_before=0.1,
        qoi_after=0.01,
        created_round=3,
        case_id="my_case",
    )
    assert rec.case_id == "my_case"
    assert rec.created_round == 3


def test_default_case_id_is_config_case_id():
    rec = mine_experience(_diag(), Fault.BC_MISMATCH, qoi_before=0.1, qoi_after=0.01)
    assert rec.case_id == config.CASE_ID == "channel_poiseuille"


# --------------------------------------------------------------------------- #
# ExperienceStore — always under tmp_path, never the real data/ dir           #
# --------------------------------------------------------------------------- #
def test_store_missing_file_returns_empty(tmp_path):
    store = ExperienceStore(tmp_path / "mem.jsonl")
    assert store.all() == []


def test_store_append_then_all_roundtrip(tmp_path):
    store = ExperienceStore(tmp_path / "mem.jsonl")
    rec = _record(case_id="alpha", mode=FailureMode.BC_MISMATCH, promote=True, rnd=2)
    store.append(rec)
    got = store.all()
    assert len(got) == 1
    assert got[0] == rec  # full pydantic equality incl. promote flag & round


def test_store_append_creates_parent_dirs(tmp_path):
    # path under a not-yet-existing subdir: append() must mkdir parents.
    store = ExperienceStore(tmp_path / "nested" / "deeper" / "mem.jsonl")
    store.append(_record())
    assert store.path.exists()
    assert len(store.all()) == 1


def test_store_extend_appends_in_order(tmp_path):
    store = ExperienceStore(tmp_path / "mem.jsonl")
    recs = [
        _record(case_id="a", rnd=0),
        _record(case_id="b", rnd=1),
        _record(case_id="c", rnd=2),
    ]
    store.extend(recs)
    got = store.all()
    assert [r.case_id for r in got] == ["a", "b", "c"]
    assert got == recs


def test_store_append_is_additive_not_overwrite(tmp_path):
    store = ExperienceStore(tmp_path / "mem.jsonl")
    store.append(_record(case_id="first"))
    store.append(_record(case_id="second"))
    got = store.all()
    assert [r.case_id for r in got] == ["first", "second"]


def test_store_clear_empties(tmp_path):
    store = ExperienceStore(tmp_path / "mem.jsonl")
    store.extend([_record(case_id="x"), _record(case_id="y")])
    assert len(store.all()) == 2
    store.clear()
    assert store.all() == []
    assert not store.path.exists()


def test_store_clear_on_missing_file_is_noop(tmp_path):
    store = ExperienceStore(tmp_path / "mem.jsonl")
    # must not raise even though file never existed.
    store.clear()
    assert store.all() == []


def test_store_empty_file_returns_empty(tmp_path):
    p = tmp_path / "mem.jsonl"
    p.write_text("")  # exists but empty
    store = ExperienceStore(p)
    assert store.all() == []


def test_store_blank_lines_are_skipped(tmp_path):
    p = tmp_path / "mem.jsonl"
    rec = _record(case_id="solo")
    # file with surrounding blank lines around one valid record.
    p.write_text("\n" + rec.model_dump_json() + "\n\n")
    store = ExperienceStore(p)
    got = store.all()
    assert len(got) == 1
    assert got[0].case_id == "solo"


def test_store_does_not_touch_real_data_dir(tmp_path):
    # Sanity: our store path is fully inside tmp_path, not the package data dir.
    from ofab.paths import DATA_DIR

    store = ExperienceStore(tmp_path / "mem.jsonl")
    store.append(_record())
    assert str(store.path).startswith(str(tmp_path))
    assert DATA_DIR not in store.path.parents


# --------------------------------------------------------------------------- #
# ExperienceStore.recall — the flywheel's retrieval half                      #
# --------------------------------------------------------------------------- #
def test_recall_empty_store_returns_none(tmp_path):
    store = ExperienceStore(tmp_path / "mem.jsonl")
    assert store.recall(FailureMode.BC_MISMATCH) is None


def test_recall_returns_matching_mode(tmp_path):
    store = ExperienceStore(tmp_path / "mem.jsonl")
    store.extend([
        _record(case_id="bc", mode=FailureMode.BC_MISMATCH),
        _record(case_id="mesh", mode=FailureMode.MESH_TOO_COARSE),
    ])
    rec = store.recall(FailureMode.MESH_TOO_COARSE)
    assert rec is not None
    assert rec.failure_mode is FailureMode.MESH_TOO_COARSE
    assert rec.case_id == "mesh"


def test_recall_accepts_string_value(tmp_path):
    store = ExperienceStore(tmp_path / "mem.jsonl")
    store.append(_record(mode=FailureMode.BC_MISMATCH))
    assert store.recall("BC_MISMATCH") is not None


def test_recall_returns_latest_when_multiple(tmp_path):
    # A recurring fault recalls the MOST RECENT lesson (the flywheel accrues).
    store = ExperienceStore(tmp_path / "mem.jsonl")
    store.append(_record(case_id="old", mode=FailureMode.BC_MISMATCH, rnd=0))
    store.append(_record(case_id="new", mode=FailureMode.BC_MISMATCH, rnd=5))
    rec = store.recall(FailureMode.BC_MISMATCH)
    assert rec is not None and rec.case_id == "new"


def test_recall_unseen_mode_returns_none(tmp_path):
    store = ExperienceStore(tmp_path / "mem.jsonl")
    store.append(_record(mode=FailureMode.BC_MISMATCH))
    assert store.recall(FailureMode.RESIDUAL_NOT_CONVERGED) is None
