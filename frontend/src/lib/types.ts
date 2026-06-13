// Mirrors the Pydantic schemas in backend/ofab/models.py + the bundle assembled
// in backend/ofab/demo/replay_data.py. The dashboard consumes this verbatim.

export type Workflow = "agent_only" | "agent_plus_benchmark";
export type Fault = "none" | "bc_mismatch" | "coarse_mesh" | "solver_setting_error";
export type ExecutionStatus = "success" | "failed";
export type EngineeringStatus = "pass" | "needs_repair" | "unknown";
export type FailureMode =
  | "NONE"
  | "BC_MISMATCH"
  | "MESH_TOO_COARSE"
  | "RESIDUAL_NOT_CONVERGED";

export interface Profile {
  label: string;
  y: number[];
  u: number[];
  qoi_error?: number;
}

export interface RunResult {
  run_id: string;
  workflow: Workflow;
  case_id: string;
  fault: Fault;
  mode: string;
  round_index: number;
  execution_status: ExecutionStatus;
  engineering_status: EngineeringStatus;
  qoi_error: number;
  residual_final: number;
  runtime_s: number;
  features: Record<string, number>;
  notes: string;
}

export interface WorkflowMetrics {
  workflow: Workflow;
  rerun_count: number;
  time_to_pass_s: number;
  false_success_detected: number;
  final_qoi_error: number;
  experience_records: number;
  regression_cases_promoted: number;
  auto_repair_success_rate: number;
  passed: boolean;
}

export interface TimelineStep {
  workflow: Workflow;
  fault: Fault;
  round_index: number;
  label: string;
  execution_status: ExecutionStatus;
  engineering_status: EngineeringStatus;
  qoi_error: number;
  residual_final: number;
  runtime_s: number;
}

export interface Diagnosis {
  run_id: string;
  failure_mode: FailureMode;
  confidence: number;
  evidence: string[];
  suggested_repair: string[];
}

export interface Reward {
  run_id: string;
  total_reward: number;
  efficiency_reward: number;
  engineering_reward: number;
  experience_reward: number;
  decision: string;
  suggested_focus: string[];
}

export interface ExperienceRecord {
  case_id: string;
  failure_mode: FailureMode;
  symptom: string;
  repair: string;
  outcome: string;
  promote_to_regression: boolean;
  created_round: number;
}

export interface FlywheelEncounter {
  rerun_count: number;
  time_s: number;
  time_label: string;
  path_pct: number[];
}

export interface Flywheel {
  fault: Fault;
  failure_mode: FailureMode;
  recalled: { symptom: string; repair: string; outcome: string };
  first_encounter: FlywheelEncounter;
  second_encounter: FlywheelEncounter;
  rounds_saved: number;
  time_saved_pct: number;
}

export interface ComparisonMetric {
  before: number;
  after: number;
  delta_pct: number | null;
  unit: string;
  before_label?: string;
  after_label?: string;
}

export interface Comparison {
  rerun_count: ComparisonMetric;
  time_to_pass: ComparisonMetric;
  qoi_error: ComparisonMetric;
  false_success_detected: ComparisonMetric;
  experience_records: ComparisonMetric;
  hero_qoi: { failed: number; repaired: number };
}

export interface CaseInfo {
  id: string;
  title: string;
  reynolds_h: number;
  u_max: number;
  inlet_velocity: number;
  channel_height: number;
  channel_length: number;
  kinematic_viscosity: number;
  tolerances: { qoi_l2: number; residual: number; wall_slip: number };
}

export interface Bundle {
  case: CaseInfo;
  story: { slogan: string; steps: string[] };
  mode: string;
  workflows: WorkflowMetrics[];
  comparison: Comparison;
  timeline: TimelineStep[];
  profiles: {
    reference: Profile;
    failed: Profile;
    repaired: Profile;
    agent_only_final: Profile;
  };
  diagnosis: Diagnosis;
  diagnoses: Diagnosis[];
  reward: { before: Reward; after: Reward };
  rewards: Reward[];
  experience: ExperienceRecord[];
  flywheel: Flywheel;
  scorecards: unknown[];
  runs: RunResult[];
}
