"""Seed the replay bundle and run the pilot experiment, writing all artifacts."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from .. import paths
from ..memory import ExperienceStore
from ..models import RunMode
from .replay_data import HERO_FAULT, build_bundle


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")


def _hero_round0(bundle: dict) -> dict:
    for r in bundle["runs"]:
        if r["workflow"] == "agent_plus_benchmark" and r["fault"] == HERO_FAULT.value and r["round_index"] == 0:
            return r
    return bundle["runs"][0]


# --------------------------------------------------------------------------- #
# Seed                                                                        #
# --------------------------------------------------------------------------- #
def seed(mode: RunMode = RunMode.REPLAY) -> dict:
    """Generate the replay bundle + canonical example artifacts + frontend data."""
    paths.ensure_dirs()
    bundle = build_bundle(mode)

    # Canonical replay bundle (API + frontend both read this shape).
    _write_json(paths.DATA_DIR / "demo_bundle.json", bundle)
    _write_json(paths.FRONTEND_DATA_DIR / "demoRuns.json", bundle)

    # Cumulative experience memory.
    store = ExperienceStore()
    store.clear()
    from ..models import ExperienceRecord
    store.extend([ExperienceRecord.model_validate(e) for e in bundle["experience"]])

    # Single-object example artifacts (the "ran fine but engineering wrong" run).
    hero = _hero_round0(bundle)
    hero_sc = next(s for s in bundle["scorecards"] if s["run_id"] == hero["run_id"])
    hero_dg = next(d for d in bundle["diagnoses"] if d["run_id"] == hero["run_id"])
    _write_json(paths.DATA_DIR / "run_result.json", hero)
    _write_json(paths.DATA_DIR / "scorecard.json", hero_sc)
    _write_json(paths.DATA_DIR / "diagnosis.json", hero_dg)
    _write_json(paths.DATA_DIR / "reward.json", bundle["reward"]["before"])
    _write_jsonl(paths.DATA_DIR / "experience_record.jsonl", bundle["experience"])

    return {
        "mode": mode.value,
        "bundle": str(paths.DATA_DIR / "demo_bundle.json"),
        "frontend_data": str(paths.FRONTEND_DATA_DIR / "demoRuns.json"),
        "runs": len(bundle["runs"]),
        "false_success_detected": bundle["comparison"]["false_success_detected"]["after"],
        "experience_records": len(bundle["experience"]),
    }


# --------------------------------------------------------------------------- #
# Experiment                                                                  #
# --------------------------------------------------------------------------- #
_DECISION_CN = {"repair_and_rerun": "修复并重跑", "accept": "接受"}


def _report_md(bundle: dict, protocol: dict) -> str:
    c = bundle["case"]
    cmp = bundle["comparison"]
    ao, ab = bundle["workflows"]
    dg = bundle["diagnosis"]
    lines = []
    lines.append(f"# 试点实验报告 —— {protocol.get('name', 'pilot_001')}\n")
    lines.append(f"**案例：** {c['title']}（`{c['id']}`）—— 雷诺数 Re_H ≈ {c['reynolds_h']:.0f}，"
                 f"中心最大流速 u_max = {c['u_max']:.3f} m/s  ")
    lines.append(f"**模式：** {bundle['mode']}（回放）  |  **合格线：** 速度剖面误差 < "
                 f"{c['tolerances']['qoi_l2']*100:.0f}%，残差 < {c['tolerances']['residual']:.0e}\n")

    lines.append("## 研究问题\n")
    lines.append("> 给 AI 配上「基准检验」反馈后，它能不能更快得到一个*可信*的 OpenFOAM 结果——"
                 "抓住那些只看退出码的自动化会漏掉的失败，并把每一次失败都沉淀成可复用的经验？\n")

    lines.append("## 两组对照\n")
    lines.append("| 指标 | 只有 AI | AI + 基准检验 | 变化 |")
    lines.append("|---|---|---|---|")
    lines.append(f"| 重跑次数 | {cmp['rerun_count']['before']} | "
                 f"{cmp['rerun_count']['after']} | {cmp['rerun_count']['delta_pct']:.0f}% |")
    lines.append(f"| 修对耗时 | {cmp['time_to_pass']['before_label']} | "
                 f"{cmp['time_to_pass']['after_label']} | {cmp['time_to_pass']['delta_pct']:.0f}% |")
    lines.append(f"| 最终误差 | {cmp['qoi_error']['before_label']} | "
                 f"{cmp['qoi_error']['after_label']} | — |")
    lines.append(f"| 抓到的假成功 | {cmp['false_success_detected']['before']} | "
                 f"{cmp['false_success_detected']['after']} | — |")
    lines.append(f"| 沉淀的经验 | {cmp['experience_records']['before']} | "
                 f"{cmp['experience_records']['after']} | — |")
    lines.append(f"| 自动修复成功率 | {ao['auto_repair_success_rate']*100:.0f}% | "
                 f"{ab['auto_repair_success_rate']*100:.0f}% | — |\n")

    lines.append("## 主线故障 —— 边界条件错误（bc_mismatch）\n")
    lines.append(f"OpenFOAM 成功跑完，但速度剖面相对标准答案（解析解）的误差高达 "
                 f"**{cmp['hero_qoi']['failed']*100:.1f}%** —— 这是一次只看退出码根本发现不了的「假成功」。\n")
    lines.append(f"**诊断：** `{dg['failure_mode']}`（置信度 {dg['confidence']:.0%}）\n")
    for ev in dg["evidence"]:
        lines.append(f"- {ev}")
    lines.append("\n**修复建议：**")
    for fix in dg["suggested_repair"]:
        lines.append(f"- {fix}")
    lines.append(f"\n按建议修复后，误差降到 "
                 f"**{cmp['hero_qoi']['repaired']*100:.1f}%** —— 进入合格线。\n")

    lines.append("## 奖励信号（驱动修复的「燃料」）\n")
    rb, ra = bundle["reward"]["before"], bundle["reward"]["after"]
    lines.append(f"- 修复前：总分 **{rb['total_reward']:+.2f}**"
                 f"（工程分 {rb['engineering_reward']:+.2f}），决策：{_DECISION_CN.get(rb['decision'], rb['decision'])}")
    lines.append(f"- 修复后：总分 **{ra['total_reward']:+.2f}**"
                 f"（工程分 {ra['engineering_reward']:+.2f}），决策：{_DECISION_CN.get(ra['decision'], ra['decision'])}\n")

    lines.append("## 沉淀的经验（数据飞轮）\n")
    for e in bundle["experience"]:
        promo = "✅ 已升级为回归用例" if e["promote_to_regression"] else "已记录"
        lines.append(f"- **{e['failure_mode']}** —— {e['symptom']}  \n"
                     f"  修复方式：{e['repair']}  \n  结果：{e['outcome']}（{promo}）")
    lines.append("\n> 每一次失败，都变成下一次自动避开它的能力。\n")
    return "\n".join(lines)


def run_experiment(protocol_path: str | Path) -> dict:
    protocol_path = Path(protocol_path)
    protocol = yaml.safe_load(protocol_path.read_text()) or {}
    mode = RunMode(protocol.get("mode", "replay"))
    results_dir = protocol_path.parent / protocol.get("results_dir", "results")
    results_dir.mkdir(parents=True, exist_ok=True)

    bundle = build_bundle(mode)

    _write_json(results_dir / "bundle.json", bundle)
    _write_json(results_dir / "run_results.json", bundle["runs"])
    _write_json(results_dir / "scorecards.json", bundle["scorecards"])
    _write_json(results_dir / "diagnoses.json", bundle["diagnoses"])
    _write_json(results_dir / "rewards.json", bundle["rewards"])
    _write_json(results_dir / "metrics.json", bundle["workflows"])
    _write_json(results_dir / "timeline.json", bundle["timeline"])
    _write_json(results_dir / "comparison.json", bundle["comparison"])
    _write_jsonl(results_dir / "experience_record.jsonl", bundle["experience"])

    report = _report_md(bundle, protocol)
    (protocol_path.parent / "report.md").write_text(report)

    # Also refresh the canonical seed bundle so the API/frontend stay in sync.
    seed(mode)

    return {
        "mode": mode.value,
        "results_dir": str(results_dir),
        "report": str(protocol_path.parent / "report.md"),
        "runs": len(bundle["runs"]),
        "false_success_detected": bundle["comparison"]["false_success_detected"]["after"],
        "experience_records": len(bundle["experience"]),
    }
