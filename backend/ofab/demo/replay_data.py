"""Scenario builder — the scripted two-workflow experiment behind the demo.

It runs the SAME hero fault through both workflows for the head-to-head
efficiency comparison, and runs the full fault set through the benchmark
workflow for breadth (false-success detection + experience). Every number is
computed from physics + the benchmark layer; only the *trajectory* (which slip
each repair round lands on, runtimes, agent overhead) is scripted.
"""
from __future__ import annotations

import numpy as np

from .. import config, physics
from ..benchmark import build_scorecard, compute_reward, diagnose
from ..benchmark import metrics as M
from ..memory import mine_experience
from .couette_case import build_second_case
from .pipe_case import build_third_case
from ..models import (
    EngineeringStatus,
    ExperimentResult,
    Fault,
    RunMode,
    RunResult,
    TimelineStep,
    Workflow,
    WorkflowMetrics,
)
from ..runner import mock_runner

HERO_FAULT = Fault.BC_MISMATCH

# Per-round agent overhead (seconds) on top of solver runtime. Benchmark feedback
# makes each iteration cheaper because the agent is guided, not guessing.
_OVERHEAD = {Workflow.AGENT_ONLY: 83.0, Workflow.AGENT_PLUS_BENCHMARK: 42.0}

# Scripted bc-repair slip trajectories.
_AGENT_ONLY_SLIPS = [0.283, 0.235, 0.198, 0.171, 0.150, 0.134]  # ends ~8.7%, stalled
# Intermediate bc-repair state after round 0: no-slip restored (~5.8%, still > tol)
# before the pressure-gradient fix lands the final repaired round within tolerance.
_BENCH_BC_SLIPS = [0.089]
_SOLVER_RUNTIMES = [42.3, 41.0, 40.5, 42.1, 41.5, 42.0]


def _fmt_duration(seconds: float) -> str:
    m, s = divmod(int(round(seconds)), 60)
    return f"{m}m {s:02d}s"


def _profile_dict(label: str, u, qoi: float | None = None) -> dict:
    yn = physics.normalized_y()
    d = {
        "label": label,
        "y": [round(float(v), 5) for v in yn],
        "u": [round(float(v), 6) for v in np.asarray(u, dtype=float)],
    }
    if qoi is not None:
        d["qoi_error"] = round(float(qoi), 5)
    return d


# --------------------------------------------------------------------------- #
# Workflow trajectories                                                       #
# --------------------------------------------------------------------------- #
def _agent_only_runs() -> list[RunResult]:
    """Hero fault, 6 blind attempts. No benchmark -> engineering_status UNKNOWN,
    error wanders down but stalls above tolerance, never detected."""
    runs = []
    for i, slip in enumerate(_AGENT_ONLY_SLIPS):
        runs.append(
            mock_runner.run_synthetic(
                run_id=f"ao_bc_{i}",
                workflow=Workflow.AGENT_ONLY,
                fault=HERO_FAULT,
                slip=slip,
                round_index=i,
                runtime_s=_SOLVER_RUNTIMES[i],
                mode=RunMode.REPLAY,
                has_benchmark=False,
                notes="blind rerun — only exit code visible, QoI unknown",
            )
        )
    return runs


def _bench_repair_loop(fault: Fault, slips: list[float] | None) -> list[RunResult]:
    """Round 0 = injected fault; subsequent rounds = guided repair until pass."""
    runs: list[RunResult] = []
    # round 0: the injected fault
    runs.append(
        mock_runner.run_synthetic(
            run_id=f"ab_{fault.value}_0",
            workflow=Workflow.AGENT_PLUS_BENCHMARK,
            fault=fault,
            round_index=0,
            runtime_s=_SOLVER_RUNTIMES[0],
            mode=RunMode.REPLAY,
            has_benchmark=True,
            notes="injected fault — benchmark flags false success",
        )
    )
    if slips:  # bc: intermediate partial-slip states, last round = repaired
        for i, slip in enumerate(slips, start=1):
            runs.append(
                mock_runner.run_synthetic(
                    run_id=f"ab_{fault.value}_{i}",
                    workflow=Workflow.AGENT_PLUS_BENCHMARK,
                    fault=fault,
                    slip=slip,
                    round_index=i,
                    runtime_s=_SOLVER_RUNTIMES[i],
                    mode=RunMode.REPLAY,
                    has_benchmark=True,
                    notes="guided repair — no-slip restored",
                )
            )
        # final repaired round
        last = len(slips) + 1
        runs.append(
            mock_runner.run_synthetic(
                run_id=f"ab_{fault.value}_{last}",
                workflow=Workflow.AGENT_PLUS_BENCHMARK,
                fault=fault,
                repaired=True,
                round_index=last,
                runtime_s=_SOLVER_RUNTIMES[min(last, len(_SOLVER_RUNTIMES) - 1)],
                mode=RunMode.REPLAY,
                has_benchmark=True,
                notes="guided repair — pressure-gradient corrected, QoI within tolerance",
            )
        )
    else:  # coarse / solver: single guided repair to pass
        runs.append(
            mock_runner.run_synthetic(
                run_id=f"ab_{fault.value}_1",
                workflow=Workflow.AGENT_PLUS_BENCHMARK,
                fault=fault,
                repaired=True,
                round_index=1,
                runtime_s=_SOLVER_RUNTIMES[1],
                mode=RunMode.REPLAY,
                has_benchmark=True,
                notes="guided repair applied, QoI within tolerance",
            )
        )
    return runs


# --------------------------------------------------------------------------- #
# Bundle assembly                                                             #
# --------------------------------------------------------------------------- #
def _timeline(runs: list[RunResult]) -> list[TimelineStep]:
    steps = []
    for r in runs:
        if r.round_index == 0:
            label = f"inject {r.fault.value}" if r.fault != Fault.NONE else "run"
        elif r.engineering_status == EngineeringStatus.PASS:
            label = "repaired → pass"
        elif r.workflow == Workflow.AGENT_ONLY:
            label = f"blind rerun #{r.round_index}"
        else:
            label = f"guided repair #{r.round_index}"
        steps.append(
            TimelineStep(
                workflow=r.workflow,
                fault=r.fault,
                round_index=r.round_index,
                label=label,
                execution_status=r.execution_status,
                engineering_status=r.engineering_status,
                qoi_error=r.qoi_error,
                residual_final=r.residual_final,
                runtime_s=r.runtime_s,
            )
        )
    return steps


def _workflow_metrics(
    workflow: Workflow,
    all_runs: list[RunResult],
    false_success: int,
    experience_records: int,
    regression_cases_promoted: int,
    repairs_attempted: int,
    repairs_succeeded: int,
) -> WorkflowMetrics:
    hero = M.hero_loop(all_runs, HERO_FAULT.value)
    time_to_pass = sum(r.runtime_s for r in hero) + len(hero) * _OVERHEAD[workflow]
    passed = hero[-1].engineering_status == EngineeringStatus.PASS if hero else False
    return WorkflowMetrics(
        workflow=workflow,
        rerun_count=M.rerun_count(hero),
        time_to_pass_s=round(time_to_pass, 1),
        false_success_detected=false_success,
        final_qoi_error=M.final_qoi_error(hero),
        experience_records=experience_records,
        regression_cases_promoted=regression_cases_promoted,
        auto_repair_success_rate=M.auto_repair_success_rate(
            repairs_attempted, repairs_succeeded
        ),
        passed=passed,
    )


def build_bundle(mode: RunMode = RunMode.REPLAY) -> dict:
    contract_tol = config.QOI_L2_TOL

    # --- agent-only (hero fault only) -------------------------------------
    ao_runs = _agent_only_runs()

    # --- agent + benchmark (hero loop + breadth faults) -------------------
    bc_runs = _bench_repair_loop(HERO_FAULT, _BENCH_BC_SLIPS)
    coarse_runs = _bench_repair_loop(Fault.COARSE_MESH, None)
    solver_runs = _bench_repair_loop(Fault.SOLVER_SETTING_ERROR, None)
    ab_runs = bc_runs + coarse_runs + solver_runs

    # Benchmark layer over every benchmark-workflow run.
    scorecards = [build_scorecard(r) for r in ab_runs]
    diagnoses = [diagnose(r) for r in ab_runs]
    rewards = [
        compute_reward(
            sc,
            dg,
            round_index=r.round_index,
            experience_created=(not sc.overall_pass) or (r.round_index > 0),
        )
        for r, sc, dg in zip(ab_runs, scorecards, diagnoses)
    ]

    # Experience: one record per fault, mined at the repairing round.
    experience = []
    for fault_runs in (bc_runs, coarse_runs, solver_runs):
        first, last = fault_runs[0], fault_runs[-1]
        dg0 = diagnose(first)
        experience.append(
            mine_experience(
                dg0,
                first.fault,
                qoi_before=first.qoi_error,
                qoi_after=last.qoi_error,
                created_round=last.round_index,
            )
        )

    # A "false success" is a run an exit-code-only workflow would have ACCEPTED:
    # the first attempt of each fault. Intermediate repair rounds still fail the
    # benchmark but are known-in-progress, not claimed successes.
    false_success_total = sum(
        1 for r, sc in zip(ab_runs, scorecards)
        if r.round_index == 0 and sc.false_success
    )
    experience_total = len(experience)
    regression_total = sum(1 for e in experience if e.promote_to_regression)

    metrics = [
        _workflow_metrics(
            Workflow.AGENT_ONLY, ao_runs,
            false_success=0, experience_records=0,
            regression_cases_promoted=0,
            repairs_attempted=5, repairs_succeeded=0,
        ),
        _workflow_metrics(
            Workflow.AGENT_PLUS_BENCHMARK, ab_runs,
            false_success=false_success_total,
            experience_records=experience_total,
            regression_cases_promoted=regression_total,
            repairs_attempted=3, repairs_succeeded=3,
        ),
    ]
    ao_m, ab_m = metrics

    # --- hero profiles for the velocity chart -----------------------------
    yn = physics.normalized_y()
    u_ref = physics.analytical_profile(yn)
    u_failed = physics.failed_profile(HERO_FAULT.value, yn)
    u_repaired = physics.repaired_profile(HERO_FAULT.value, yn)
    u_ao_final = physics.plateau_profile(yn)
    profiles = {
        "reference": _profile_dict("标准答案（解析解）", u_ref, 0.0),
        "failed": _profile_dict("注入故障后", u_failed,
                                physics.l2_relative_error(u_failed, u_ref)),
        "repaired": _profile_dict("修复后", u_repaired,
                                  physics.l2_relative_error(u_repaired, u_ref)),
        "agent_only_final": _profile_dict("无基准检验（卡住）", u_ao_final,
                                          physics.l2_relative_error(u_ao_final, u_ref)),
    }

    # hero diagnosis + before/after reward (used by Diagnosis & Reward panels)
    hero_first = bc_runs[0]
    hero_last = bc_runs[-1]
    hero_diag = diagnose(hero_first)
    hero_sc0 = build_scorecard(hero_first)
    hero_scN = build_scorecard(hero_last)
    reward_before = compute_reward(hero_sc0, hero_diag, round_index=0, experience_created=True)
    reward_after = compute_reward(hero_scN, diagnose(hero_last),
                                  round_index=hero_last.round_index, experience_created=True)

    def _delta_pct(before: float, after: float) -> float:
        return round((after - before) / before * 100, 1) if before else 0.0

    comparison = {
        "rerun_count": {"before": ao_m.rerun_count, "after": ab_m.rerun_count,
                        "delta_pct": _delta_pct(ao_m.rerun_count, ab_m.rerun_count),
                        "unit": "reruns"},
        "time_to_pass": {"before": ao_m.time_to_pass_s, "after": ab_m.time_to_pass_s,
                         "before_label": _fmt_duration(ao_m.time_to_pass_s),
                         "after_label": _fmt_duration(ab_m.time_to_pass_s),
                         "delta_pct": _delta_pct(ao_m.time_to_pass_s, ab_m.time_to_pass_s),
                         "unit": "s"},
        "qoi_error": {"before": ao_m.final_qoi_error, "after": ab_m.final_qoi_error,
                      "before_label": f"{ao_m.final_qoi_error*100:.1f}%",
                      "after_label": f"{ab_m.final_qoi_error*100:.1f}%",
                      "delta_pct": _delta_pct(ao_m.final_qoi_error, ab_m.final_qoi_error),
                      "unit": "L2"},
        "false_success_detected": {"before": 0, "after": false_success_total,
                                   "delta_pct": None, "unit": "count"},
        "experience_records": {"before": 0, "after": experience_total,
                               "delta_pct": None, "unit": "count"},
        "hero_qoi": {"failed": profiles["failed"]["qoi_error"],
                     "repaired": profiles["repaired"]["qoi_error"]},
    }

    # --- flywheel: store → recall → faster on recurrence ------------------
    # First time the hero fault is hit, the benchmark guides a 2-rerun repair and
    # sediments a lesson. When the SAME fault recurs, that lesson is recalled and
    # the known fix applied directly — one rerun instead of two. The payoff is
    # computed the same way as the head-to-head time (solver runtime + overhead).
    bc_exp = experience[0]  # the bc_mismatch lesson sedimented just above
    overhead_ab = _OVERHEAD[Workflow.AGENT_PLUS_BENCHMARK]
    second_rerun = 1
    second_time = round(_SOLVER_RUNTIMES[0] + _SOLVER_RUNTIMES[1] + 2 * overhead_ab, 1)
    u_inter = physics.bc_profile(_BENCH_BC_SLIPS[0], yn)
    flywheel = {
        "fault": HERO_FAULT.value,
        "failure_mode": bc_exp.failure_mode.value,
        "recalled": {
            "symptom": bc_exp.symptom,
            "repair": bc_exp.repair,
            "outcome": bc_exp.outcome,
        },
        "first_encounter": {
            "rerun_count": ab_m.rerun_count,
            "time_s": ab_m.time_to_pass_s,
            "time_label": _fmt_duration(ab_m.time_to_pass_s),
            "path_pct": [round(profiles["failed"]["qoi_error"] * 100, 1),
                         round(physics.l2_relative_error(u_inter, u_ref) * 100, 1),
                         round(profiles["repaired"]["qoi_error"] * 100, 1)],
        },
        "second_encounter": {
            "rerun_count": second_rerun,
            "time_s": second_time,
            "time_label": _fmt_duration(second_time),
            "path_pct": [round(profiles["failed"]["qoi_error"] * 100, 1),
                         round(profiles["repaired"]["qoi_error"] * 100, 1)],
        },
        "rounds_saved": ab_m.rerun_count - second_rerun,
        "time_saved_pct": _delta_pct(ab_m.time_to_pass_s, second_time),
    }

    experiment = ExperimentResult(
        case_id=config.CASE_ID,
        mode=mode,
        workflows=metrics,
        timeline=_timeline(ao_runs) + _timeline(ab_runs),
        runs=ao_runs + ab_runs,
    )

    return {
        "case": {
            "id": config.CASE_ID,
            "title": config.CASE_TITLE,
            "reynolds_h": round(config.REYNOLDS_H, 1),
            "u_max": config.U_MAX,
            "inlet_velocity": config.INLET_VELOCITY,
            "channel_height": config.CHANNEL_HEIGHT,
            "channel_length": config.CHANNEL_LENGTH,
            "kinematic_viscosity": config.KINEMATIC_VISCOSITY,
            "tolerances": {
                "qoi_l2": config.QOI_L2_TOL,
                "residual": config.RESIDUAL_TOL,
                "wall_slip": config.WALL_SLIP_TOL,
            },
        },
        "story": {
            "slogan": "从“能跑”到“会变好”：用基准检验（Benchmark）的反馈，"
                      "让 AI 把每一次失败都变成下一次更高效、更可信的能力。",
            "steps": ["任务", "AI 生成", "跑仿真", "基准检验", "诊断", "修复", "沉淀经验"],
        },
        "mode": mode.value,
        "workflows": [m.model_dump(mode="json") for m in metrics],
        "comparison": comparison,
        "timeline": [s.model_dump(mode="json") for s in experiment.timeline],
        "profiles": profiles,
        "diagnosis": hero_diag.model_dump(mode="json"),
        "diagnoses": [d.model_dump(mode="json") for d in diagnoses],
        "reward": {"before": reward_before.model_dump(mode="json"), "after": reward_after.model_dump(mode="json")},
        "rewards": [r.model_dump(mode="json") for r in rewards],
        "experience": [e.model_dump(mode="json") for e in experience],
        "flywheel": flywheel,
        # Second case — proves the benchmark generalises (additive; the same
        # unchanged scorecard/diagnose judge a different flow). Does not affect
        # any of the locked hero numbers above.
        "second_case": build_second_case(),
        # Third case — widens the proof to a different HERO fault (coarse_mesh on a
        # round pipe), still the same unchanged scorecard/diagnose. Additive; does
        # not affect any locked hero/Couette numbers.
        "third_case": build_third_case(),
        "scorecards": [s.model_dump(mode="json") for s in scorecards],
        "runs": [r.model_dump(mode="json") for r in experiment.runs],
    }
