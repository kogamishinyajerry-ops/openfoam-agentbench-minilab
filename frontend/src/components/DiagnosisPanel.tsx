import { useMemo, useState } from "react";
import { ScanSearch, Wrench, Microscope, Gauge, Target } from "lucide-react";
import {
  bundle,
  pct,
  FAULT_LABELS,
  FAILURE_SHORT,
  FAILURE_LABELS,
  focusCn,
  decisionCn,
} from "../lib/data";
import type { Diagnosis, Fault, Reward, RunResult } from "../lib/types";

interface FaultData {
  fault: Fault;
  diag: Diagnosis;
  run0: RunResult;
  rewardBefore: Reward;
  rewardAfter: Reward;
  qoiAfter: number;
}

export default function DiagnosisPanel() {
  const byRunDiag = useMemo(
    () => Object.fromEntries(bundle.diagnoses.map((d) => [d.run_id, d])),
    []
  );
  const byRunReward = useMemo(
    () => Object.fromEntries(bundle.rewards.map((r) => [r.run_id, r])),
    []
  );

  const faults = useMemo<FaultData[]>(() => {
    const order: Fault[] = ["bc_mismatch", "coarse_mesh", "solver_setting_error"];
    return order.map((fault) => {
      const runs = bundle.runs
        .filter((r) => r.workflow === "agent_plus_benchmark" && r.fault === fault)
        .sort((a, b) => a.round_index - b.round_index);
      const run0 = runs[0];
      const last = runs[runs.length - 1];
      return {
        fault,
        diag: byRunDiag[run0.run_id],
        run0,
        rewardBefore: byRunReward[run0.run_id],
        rewardAfter: byRunReward[last.run_id],
        qoiAfter: last.qoi_error,
      };
    });
  }, [byRunDiag, byRunReward]);

  const [sel, setSel] = useState<Fault>("bc_mismatch");
  const d = faults.find((f) => f.fault === sel)!;

  return (
    <section className="glass-strong p-6">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="section-title">智能审计 · 哪里错 + 怎么改</p>
          <h2 className="mt-1 text-lg font-semibold text-slate-100">
            从「它错了」到「为什么错、该怎么改」
          </h2>
        </div>
        <div className="flex flex-wrap gap-1 rounded-xl border border-white/10 bg-white/5 p-1">
          {faults.map((f) => (
            <button
              key={f.fault}
              onClick={() => setSel(f.fault)}
              className={`rounded-lg px-2.5 py-1.5 text-xs font-medium transition ${
                sel === f.fault ? "bg-white/10 text-white" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {FAULT_LABELS[f.fault]}
            </button>
          ))}
        </div>
      </div>
      <p className="mb-4 max-w-3xl text-[13px] text-slate-400">
        基准检验不只说「错了」，还像一份审计报告：指出是哪一类错、列出证据、开出修改清单。
        上方可切换看三种故障各自的诊断。
      </p>

      <div className="grid gap-5 lg:grid-cols-[1.3fr_1fr]">
        {/* 诊断 */}
        <div
          key={sel}
          className="reveal rounded-2xl border border-fuchsia-400/20 bg-fuchsia-400/[0.04] p-5"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-fuchsia-400/15 text-fuchsia-300">
                <ScanSearch size={20} />
              </span>
              <div>
                <p className="text-[11px] uppercase tracking-wider text-slate-400">
                  检测到的失效模式
                </p>
                <p className="text-base font-bold text-fuchsia-200">
                  {FAILURE_SHORT[d.diag.failure_mode]}
                  <span className="ml-2 font-mono text-[11px] font-normal text-slate-500">
                    {d.diag.failure_mode}
                  </span>
                </p>
              </div>
            </div>
            <ConfidenceRing value={d.diag.confidence} />
          </div>

          <p className="mt-3 text-xs text-slate-400">{FAILURE_LABELS[d.diag.failure_mode]}</p>

          <div className="mt-4">
            <p className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-slate-300">
              <Microscope size={13} /> 证据
            </p>
            <ul className="space-y-1.5">
              {d.diag.evidence.map((e, i) => (
                <li key={i} className="flex gap-2 text-[13px] text-slate-300">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-fuchsia-300" />
                  {e}
                </li>
              ))}
            </ul>
          </div>

          <div className="mt-4 rounded-xl border border-emerald-400/20 bg-emerald-400/[0.05] p-3">
            <p className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-emerald-200">
              <Wrench size={13} /> 修复建议
            </p>
            <ul className="space-y-1">
              {d.diag.suggested_repair.map((r, i) => (
                <li key={i} className="flex gap-2 text-[13px] text-slate-300">
                  <span className="text-emerald-400">→</span>
                  {r}
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* 奖励 */}
        <div className="flex flex-col gap-4">
          <div className="rounded-2xl border border-white/10 bg-ink-900/50 p-5">
            <p className="flex items-center gap-1.5 text-xs font-semibold text-slate-300">
              <Gauge size={14} /> 奖励信号 —— 驱动修复的「燃料」
            </p>
            <RewardMeter
              key={sel}
              before={d.rewardBefore.total_reward}
              after={d.rewardAfter.total_reward}
            />
            <div className="mt-3 grid grid-cols-3 gap-2 text-center text-[11px]">
              <RewardPart label="工程分" value={d.rewardAfter.engineering_reward} />
              <RewardPart label="效率分" value={d.rewardAfter.efficiency_reward} />
              <RewardPart label="经验分" value={d.rewardAfter.experience_reward} />
            </div>
            <p className="mt-2 text-[11px] text-slate-500">
              分数从负转正，就是基准检验在告诉 AI：「这次改对了」。
            </p>
          </div>

          <div className="rounded-2xl border border-white/10 bg-ink-900/50 p-5">
            <p className="flex items-center gap-1.5 text-xs font-semibold text-slate-300">
              <Target size={14} /> 决策 & 关注点
            </p>
            <p className="mt-2 font-mono text-sm text-cyan-200">
              {decisionCn(d.rewardBefore.decision)} → {decisionCn(d.rewardAfter.decision)}
            </p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {d.rewardBefore.suggested_focus.map((f) => (
                <span key={f} className="chip text-slate-300">
                  {focusCn(f)}
                </span>
              ))}
            </div>
            <p className="mt-3 text-xs text-slate-400">
              误差 {pct(d.run0.qoi_error)} →{" "}
              <span className="text-emerald-300">{pct(d.qoiAfter)}</span>
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

function ConfidenceRing({ value }: { value: number }) {
  const r = 18;
  const circ = 2 * Math.PI * r;
  return (
    <div className="relative grid h-14 w-14 place-items-center">
      <svg width="56" height="56" className="-rotate-90">
        <circle cx="28" cy="28" r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="5" />
        <circle
          cx="28"
          cy="28"
          r={r}
          fill="none"
          stroke="#c084fc"
          strokeWidth="5"
          strokeLinecap="round"
          strokeDasharray={circ}
          strokeDashoffset={circ * (1 - value)}
        />
      </svg>
      <div className="absolute flex flex-col items-center leading-none">
        <span className="stat-num text-xs font-bold text-fuchsia-200">
          {Math.round(value * 100)}%
        </span>
        <span className="text-[8px] text-slate-500">置信度</span>
      </div>
    </div>
  );
}

function RewardMeter({ before, after }: { before: number; after: number }) {
  // [-1,1] 映射到 [0,100]%
  const toPct = (v: number) => ((v + 1) / 2) * 100;
  return (
    <div className="mt-4">
      <div className="relative h-3 w-full rounded-full bg-gradient-to-r from-rose-500/40 via-slate-600/30 to-emerald-500/40">
        <div className="absolute left-1/2 top-1/2 h-4 w-px -translate-y-1/2 bg-white/20" />
        <div
          className="absolute top-1/2 h-5 w-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-rose-300 bg-ink-900"
          style={{ left: `${toPct(before)}%` }}
        />
        <div
          className="absolute top-1/2 z-10 h-5 w-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-emerald-300 bg-emerald-400 shadow-glow-emerald transition-all duration-700"
          style={{ left: `${toPct(after)}%` }}
        />
      </div>
      <div className="mt-2 flex items-center justify-between">
        <span className="stat-num text-lg font-bold text-rose-300">{before.toFixed(2)}</span>
        <span className="text-xs text-slate-500">总分（修复前 → 修复后）</span>
        <span className="stat-num text-lg font-bold text-emerald-300">
          {after >= 0 ? "+" : ""}
          {after.toFixed(2)}
        </span>
      </div>
    </div>
  );
}

function RewardPart({ label, value }: { label: string; value: number }) {
  const pos = value >= 0;
  return (
    <div className="rounded-lg border border-white/10 bg-white/5 px-2 py-1.5">
      <p className={`stat-num text-sm font-bold ${pos ? "text-emerald-300" : "text-rose-300"}`}>
        {pos ? "+" : ""}
        {value.toFixed(2)}
      </p>
      <p className="text-slate-500">{label}</p>
    </div>
  );
}
