"""Tests for ofab.models — the pydantic contract shared across CLI/API/runners/frontend.

These assert *real invariants* of the schema:
  - enum .value strings are exactly the wire format the frontend consumes
  - model_dump(mode="json") -> model_validate round-trips without losing fields
  - documented defaults (round_index=0, features={}, case_id, profile/reference=None)
  - WorkflowMetrics carries regression_cases_promoted as an int
"""
from __future__ import annotations

import pytest

from ofab.models import (
    BenchmarkCheck,
    Diagnosis,
    EngineeringStatus,
    ExecutionStatus,
    ExperienceRecord,
    ExperimentResult,
    Fault,
    FailureMode,
    Reward,
    RunMode,
    RunResult,
    Scorecard,
    TimelineStep,
    VelocityProfile,
    Workflow,
    WorkflowMetrics,
)


# --------------------------------------------------------------------------- #
# Enum .value invariants — these strings are the on-the-wire contract          #
# --------------------------------------------------------------------------- #
def test_workflow_values():
    assert Workflow.AGENT_ONLY.value == "agent_only"
    assert Workflow.AGENT_PLUS_BENCHMARK.value == "agent_plus_benchmark"
    assert {w.value for w in Workflow} == {"agent_only", "agent_plus_benchmark"}


def test_fault_values():
    assert Fault.NONE.value == "none"
    assert Fault.BC_MISMATCH.value == "bc_mismatch"
    assert Fault.COARSE_MESH.value == "coarse_mesh"
    assert Fault.SOLVER_SETTING_ERROR.value == "solver_setting_error"
    assert {f.value for f in Fault} == {
        "none",
        "bc_mismatch",
        "coarse_mesh",
        "solver_setting_error",
    }


def test_run_mode_values():
    assert RunMode.REPLAY.value == "replay"
    assert RunMode.MOCK.value == "mock"
    assert RunMode.OPENFOAM.value == "openfoam"
    assert {m.value for m in RunMode} == {"replay", "mock", "openfoam"}


def test_execution_status_values():
    assert ExecutionStatus.SUCCESS.value == "success"
    assert ExecutionStatus.FAILED.value == "failed"
    assert {s.value for s in ExecutionStatus} == {"success", "failed"}


def test_engineering_status_values():
    assert EngineeringStatus.PASS.value == "pass"
    assert EngineeringStatus.NEEDS_REPAIR.value == "needs_repair"
    assert EngineeringStatus.UNKNOWN.value == "unknown"
    assert {s.value for s in EngineeringStatus} == {"pass", "needs_repair", "unknown"}


def test_failure_mode_values():
    # FailureMode is uppercased on the wire, distinct from Fault's lowercase.
    assert FailureMode.NONE.value == "NONE"
    assert FailureMode.BC_MISMATCH.value == "BC_MISMATCH"
    assert FailureMode.MESH_TOO_COARSE.value == "MESH_TOO_COARSE"
    assert FailureMode.RESIDUAL_NOT_CONVERGED.value == "RESIDUAL_NOT_CONVERGED"
    assert {m.value for m in FailureMode} == {
        "NONE",
        "BC_MISMATCH",
        "MESH_TOO_COARSE",
        "RESIDUAL_NOT_CONVERGED",
    }


def test_str_enum_serializes_to_value():
    # str-Enum subclass: model_dump(mode="json") emits the .value string, not "Fault.NONE".
    dumped = RunResult(
        run_id="r",
        workflow=Workflow.AGENT_ONLY,
        fault=Fault.NONE,
        mode=RunMode.REPLAY,
        execution_status=ExecutionStatus.SUCCESS,
        engineering_status=EngineeringStatus.PASS,
        qoi_error=0.0,
        residual_final=0.0,
        runtime_s=0.0,
    ).model_dump(mode="json")
    assert dumped["workflow"] == "agent_only"
    assert dumped["fault"] == "none"
    assert dumped["mode"] == "replay"
    assert dumped["execution_status"] == "success"
    assert dumped["engineering_status"] == "pass"


# --------------------------------------------------------------------------- #
# Defaults                                                                      #
# --------------------------------------------------------------------------- #
def test_run_result_defaults():
    r = RunResult(
        run_id="run-1",
        workflow=Workflow.AGENT_PLUS_BENCHMARK,
        fault=Fault.BC_MISMATCH,
        mode=RunMode.REPLAY,
        execution_status=ExecutionStatus.SUCCESS,
        engineering_status=EngineeringStatus.NEEDS_REPAIR,
        qoi_error=0.184,
        residual_final=6e-7,
        runtime_s=12.3,
    )
    assert r.case_id == "channel_poiseuille"
    assert r.round_index == 0
    assert r.features == {}
    assert r.profile is None
    assert r.reference is None
    assert r.notes == ""


def test_run_result_features_default_is_independent():
    # default_factory=dict must give each instance its own dict (no shared mutable state).
    a = RunResult(
        run_id="a",
        workflow=Workflow.AGENT_ONLY,
        fault=Fault.NONE,
        mode=RunMode.MOCK,
        execution_status=ExecutionStatus.SUCCESS,
        engineering_status=EngineeringStatus.UNKNOWN,
        qoi_error=0.0,
        residual_final=0.0,
        runtime_s=0.0,
    )
    b = RunResult(
        run_id="b",
        workflow=Workflow.AGENT_ONLY,
        fault=Fault.NONE,
        mode=RunMode.MOCK,
        execution_status=ExecutionStatus.SUCCESS,
        engineering_status=EngineeringStatus.UNKNOWN,
        qoi_error=0.0,
        residual_final=0.0,
        runtime_s=0.0,
    )
    a.features["k"] = 1.0
    assert b.features == {}


def test_experience_record_default_created_round():
    rec = ExperienceRecord(
        case_id="channel_poiseuille",
        failure_mode=FailureMode.BC_MISMATCH,
        symptom="wall slip",
        repair="fix BC",
        outcome="误差从 18.4% 降到 2.1%",
        promote_to_regression=True,
    )
    assert rec.created_round == 0


def test_experiment_result_runs_default_empty():
    exp = ExperimentResult(
        case_id="channel_poiseuille",
        mode=RunMode.REPLAY,
        workflows=[],
        timeline=[],
    )
    assert exp.runs == []


# --------------------------------------------------------------------------- #
# WorkflowMetrics carries regression_cases_promoted as int                     #
# --------------------------------------------------------------------------- #
def _workflow_metrics(**over):
    base = dict(
        workflow=Workflow.AGENT_PLUS_BENCHMARK,
        rerun_count=2,
        time_to_pass_s=249.8,
        false_success_detected=3,
        final_qoi_error=0.02115,
        experience_records=3,
        regression_cases_promoted=3,
        auto_repair_success_rate=1.0,
        passed=True,
    )
    base.update(over)
    return WorkflowMetrics(**base)


def test_workflow_metrics_regression_cases_promoted_is_int():
    m = _workflow_metrics()
    assert m.regression_cases_promoted == 3
    assert isinstance(m.regression_cases_promoted, int)


def test_workflow_metrics_regression_cases_promoted_field_typed_int():
    # The schema must declare an int field, so a float-ish string coerces to int.
    fields = WorkflowMetrics.model_fields
    assert "regression_cases_promoted" in fields
    assert fields["regression_cases_promoted"].annotation is int
    m = _workflow_metrics(regression_cases_promoted=3)
    assert m.regression_cases_promoted == 3


# --------------------------------------------------------------------------- #
# Round-trip: model_dump(mode="json") -> model_validate is lossless            #
# --------------------------------------------------------------------------- #
def _assert_roundtrip(model):
    cls = type(model)
    dumped = model.model_dump(mode="json")
    restored = cls.model_validate(dumped)
    assert restored == model
    # Re-dump must equal the first dump too (field set + values stable).
    assert restored.model_dump(mode="json") == dumped
    # No field silently dropped: the dumped dict covers exactly the declared fields.
    assert set(dumped.keys()) == set(cls.model_fields.keys())
    return dumped


def test_roundtrip_run_result_full():
    prof = VelocityProfile(label="sim", y=[0.0, 0.5, 1.0], u=[0.0, 0.15, 0.0])
    ref = VelocityProfile(label="analytical", y=[0.0, 0.5, 1.0], u=[0.0, 0.15, 0.0])
    r = RunResult(
        run_id="run-42",
        workflow=Workflow.AGENT_PLUS_BENCHMARK,
        case_id="channel_poiseuille",
        fault=Fault.BC_MISMATCH,
        mode=RunMode.OPENFOAM,
        round_index=2,
        execution_status=ExecutionStatus.SUCCESS,
        engineering_status=EngineeringStatus.NEEDS_REPAIR,
        qoi_error=0.1842,
        residual_final=6e-7,
        runtime_s=747.4,
        profile=prof,
        reference=ref,
        features={"wall_slip": 0.283},
        notes="bc mismatch",
    )
    dumped = _assert_roundtrip(r)
    # spot-check load-bearing nested + scalar fields survived verbatim
    assert dumped["features"] == {"wall_slip": 0.283}
    assert dumped["profile"]["u"] == [0.0, 0.15, 0.0]
    assert dumped["round_index"] == 2


def test_roundtrip_scorecard():
    sc = Scorecard(
        run_id="run-1",
        workflow=Workflow.AGENT_PLUS_BENCHMARK,
        fault=Fault.BC_MISMATCH,
        checks=[
            BenchmarkCheck(name="execution", passed=True, value=1.0, threshold=1.0),
            BenchmarkCheck(
                name="residual", passed=True, value=6e-7, threshold=1e-4, detail="ok"
            ),
            BenchmarkCheck(
                name="qoi_l2", passed=False, value=0.184, threshold=0.05, detail="high"
            ),
        ],
        qoi_error=0.184,
        residual_final=6e-7,
        execution_status=ExecutionStatus.SUCCESS,
        engineering_status=EngineeringStatus.NEEDS_REPAIR,
        false_success=True,
        overall_pass=False,
    )
    dumped = _assert_roundtrip(sc)
    assert len(dumped["checks"]) == 3
    assert {c["name"] for c in dumped["checks"]} == {"execution", "residual", "qoi_l2"}
    assert dumped["false_success"] is True
    assert dumped["overall_pass"] is False


def test_roundtrip_diagnosis():
    d = Diagnosis(
        run_id="run-1",
        failure_mode=FailureMode.BC_MISMATCH,
        confidence=0.9,
        evidence=["wall_slip=0.283"],
        suggested_repair=["fix inlet BC"],
    )
    dumped = _assert_roundtrip(d)
    assert dumped["failure_mode"] == "BC_MISMATCH"
    assert dumped["confidence"] == 0.9


def test_roundtrip_reward():
    rw = Reward(
        run_id="run-1",
        total_reward=0.8,
        efficiency_reward=0.1,
        engineering_reward=0.8,
        experience_reward=0.0,
        decision="accept",
        suggested_focus=["boundary_condition", "qoi_alignment"],
    )
    dumped = _assert_roundtrip(rw)
    assert dumped["decision"] == "accept"
    assert dumped["suggested_focus"] == ["boundary_condition", "qoi_alignment"]


def test_roundtrip_experience_record():
    rec = ExperienceRecord(
        case_id="channel_poiseuille",
        failure_mode=FailureMode.BC_MISMATCH,
        symptom="wall slip 0.283",
        repair="correct no-slip wall BC",
        outcome="误差从 18.4% 降到 2.1%",
        promote_to_regression=True,
        created_round=1,
    )
    dumped = _assert_roundtrip(rec)
    assert dumped["promote_to_regression"] is True
    assert dumped["created_round"] == 1


def test_roundtrip_workflow_metrics():
    m = _workflow_metrics()
    dumped = _assert_roundtrip(m)
    assert dumped["regression_cases_promoted"] == 3
    assert dumped["auto_repair_success_rate"] == 1.0
    assert dumped["false_success_detected"] == 3


def test_roundtrip_timeline_step():
    ts = TimelineStep(
        workflow=Workflow.AGENT_PLUS_BENCHMARK,
        fault=Fault.BC_MISMATCH,
        round_index=0,
        label="first attempt",
        execution_status=ExecutionStatus.SUCCESS,
        engineering_status=EngineeringStatus.NEEDS_REPAIR,
        qoi_error=0.1842,
        residual_final=6e-7,
        runtime_s=120.0,
    )
    dumped = _assert_roundtrip(ts)
    assert dumped["label"] == "first attempt"
    assert dumped["round_index"] == 0


def test_roundtrip_experiment_result_nested():
    # Aggregate object nests WorkflowMetrics + TimelineStep + RunResult; round-trip whole tree.
    exp = ExperimentResult(
        case_id="channel_poiseuille",
        mode=RunMode.REPLAY,
        workflows=[_workflow_metrics()],
        timeline=[
            TimelineStep(
                workflow=Workflow.AGENT_PLUS_BENCHMARK,
                fault=Fault.BC_MISMATCH,
                round_index=0,
                label="step",
                execution_status=ExecutionStatus.SUCCESS,
                engineering_status=EngineeringStatus.NEEDS_REPAIR,
                qoi_error=0.1842,
                residual_final=6e-7,
                runtime_s=120.0,
            )
        ],
        runs=[
            RunResult(
                run_id="run-1",
                workflow=Workflow.AGENT_PLUS_BENCHMARK,
                fault=Fault.BC_MISMATCH,
                mode=RunMode.REPLAY,
                execution_status=ExecutionStatus.SUCCESS,
                engineering_status=EngineeringStatus.NEEDS_REPAIR,
                qoi_error=0.1842,
                residual_final=6e-7,
                runtime_s=120.0,
            )
        ],
    )
    dumped = _assert_roundtrip(exp)
    assert dumped["workflows"][0]["regression_cases_promoted"] == 3
    assert dumped["timeline"][0]["fault"] == "bc_mismatch"
    assert dumped["runs"][0]["run_id"] == "run-1"


def test_velocity_profile_roundtrip_preserves_lists():
    p = VelocityProfile(label="analytical", y=[0.0, 0.25, 0.5, 0.75, 1.0],
                        u=[0.0, 0.1125, 0.15, 0.1125, 0.0])
    dumped = _assert_roundtrip(p)
    assert dumped["u"][2] == 0.15  # center == U_MAX
    assert dumped["u"][0] == 0.0 and dumped["u"][-1] == 0.0  # walls no-slip
