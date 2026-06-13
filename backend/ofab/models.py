"""Pydantic schemas — the contract shared by CLI, API, runners and the frontend.

These are the *only* shapes that cross module boundaries or hit disk as JSON.
Keep them stable: the React dashboard consumes them verbatim.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Enumerations                                                                #
# --------------------------------------------------------------------------- #
class Workflow(str, Enum):
    AGENT_ONLY = "agent_only"
    AGENT_PLUS_BENCHMARK = "agent_plus_benchmark"


class Fault(str, Enum):
    NONE = "none"
    BC_MISMATCH = "bc_mismatch"
    COARSE_MESH = "coarse_mesh"
    SOLVER_SETTING_ERROR = "solver_setting_error"


class RunMode(str, Enum):
    REPLAY = "replay"
    MOCK = "mock"
    OPENFOAM = "openfoam"


class ExecutionStatus(str, Enum):
    """What ordinary software testing sees — did the process finish?"""
    SUCCESS = "success"
    FAILED = "failed"


class EngineeringStatus(str, Enum):
    """What Benchmark Feedback sees — is the engineering result trustworthy?"""
    PASS = "pass"
    NEEDS_REPAIR = "needs_repair"
    UNKNOWN = "unknown"  # agent-only workflow: no benchmark, cannot tell


class FailureMode(str, Enum):
    NONE = "NONE"
    BC_MISMATCH = "BC_MISMATCH"
    MESH_TOO_COARSE = "MESH_TOO_COARSE"
    RESIDUAL_NOT_CONVERGED = "RESIDUAL_NOT_CONVERGED"


# --------------------------------------------------------------------------- #
# Core data objects                                                           #
# --------------------------------------------------------------------------- #
class VelocityProfile(BaseModel):
    """A wall-normal velocity profile u(y), normalized y/H in [0, 1]."""
    label: str
    y: list[float]                 # y / H, 0 (wall) .. 1 (wall)
    u: list[float]                 # streamwise velocity [m/s]


class RunResult(BaseModel):
    run_id: str
    workflow: Workflow
    case_id: str = Field(default="channel_poiseuille")
    fault: Fault
    mode: RunMode
    round_index: int = 0           # 0 = first attempt, >0 = repair reruns
    execution_status: ExecutionStatus
    engineering_status: EngineeringStatus
    qoi_error: float               # relative L2 of u(y) vs analytical
    residual_final: float
    runtime_s: float
    profile: Optional[VelocityProfile] = None
    reference: Optional[VelocityProfile] = None
    features: dict[str, float] = Field(default_factory=dict)
    notes: str = ""


class BenchmarkCheck(BaseModel):
    name: str
    passed: bool
    value: float
    threshold: float
    detail: str = ""


class Scorecard(BaseModel):
    run_id: str
    workflow: Workflow
    fault: Fault
    checks: list[BenchmarkCheck]
    qoi_error: float
    residual_final: float
    execution_status: ExecutionStatus
    engineering_status: EngineeringStatus
    false_success: bool            # ran "successfully" yet engineering-failed
    overall_pass: bool


class Diagnosis(BaseModel):
    run_id: str
    failure_mode: FailureMode
    confidence: float
    evidence: list[str]
    suggested_repair: list[str]


class Reward(BaseModel):
    run_id: str
    total_reward: float
    efficiency_reward: float
    engineering_reward: float
    experience_reward: float
    decision: str                  # e.g. "repair_and_rerun" | "accept"
    suggested_focus: list[str]


class ExperienceRecord(BaseModel):
    case_id: str
    failure_mode: FailureMode
    symptom: str
    repair: str
    outcome: str
    promote_to_regression: bool
    created_round: int = 0


# --------------------------------------------------------------------------- #
# Aggregate / experiment-level                                                #
# --------------------------------------------------------------------------- #
class WorkflowMetrics(BaseModel):
    workflow: Workflow
    rerun_count: int
    time_to_pass_s: float
    false_success_detected: int
    final_qoi_error: float
    experience_records: int
    regression_cases_promoted: int
    auto_repair_success_rate: float
    passed: bool


class TimelineStep(BaseModel):
    workflow: Workflow
    fault: Fault
    round_index: int
    label: str
    execution_status: ExecutionStatus
    engineering_status: EngineeringStatus
    qoi_error: float
    residual_final: float
    runtime_s: float


class ExperimentResult(BaseModel):
    case_id: str
    mode: RunMode
    workflows: list[WorkflowMetrics]
    timeline: list[TimelineStep]
    runs: list[RunResult] = Field(default_factory=list)
