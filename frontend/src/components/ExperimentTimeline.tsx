import { Bot, GitBranch, Clock, Flag, CheckCircle2 } from "lucide-react";
import { bundle, fmtDuration, pct, FAULT_LABELS } from "../lib/data";
import type { TimelineStep, Workflow } from "../lib/types";

const STATUS_COLOR: Record<string, string> = {
  pass: "#34d399",
  needs_repair: "#fb7185",
  unknown: "#fbbf24",
};

function steps(workflow: Workflow, fault: string): TimelineStep[] {
  return bundle.timeline
    .filter((s) => s.workflow === workflow && s.fault === fault)
    .sort((a, b) => a.round_index - b.round_index);
}

export default function ExperimentTimeline() {
  const ao = bundle.workflows.find((w) => w.workflow === "agent_only")!;
  const ab = bundle.workflows.find((w) => w.workflow === "agent_plus_benchmark")!;
  const aoHero = steps("agent_only", "bc_mismatch");
  const abHero = steps("agent_plus_benchmark", "bc_mismatch");

  return (
    <section className="glass-strong p-6">
      <div className="mb-2">
        <p className="section-title">对照实验 · 两种 AI 同一道错题</p>
        <h2 className="mt-1 text-lg font-semibold text-slate-100">
          瞎试 5 次还是错 vs. 指点 2 次就修对
        </h2>
      </div>
      <p className="mb-5 max-w-3xl text-[13px] text-slate-400">
        给两种 AI 出同一道错题。每个圈是一次运行，圈下数字是<span className="text-slate-300">当次误差</span>
        （0 号圈＝刚注入故障）。没有判卷老师的只能瞎试、越改越久还停在错的地方；有判卷老师的按指点改，两步就修对了。
      </p>

      <div className="space-y-5">
        <Track
          icon={Bot}
          name="只有 AI"
          tint="#fbbf24"
          subtitle="只能看到「跑完了没」，只能瞎猜"
          steps={aoHero}
          timeLabel={fmtDuration(ao.time_to_pass_s)}
          endLabel={`停在 ${pct(ao.final_qoi_error)} —— 还是错的`}
          endGood={false}
        />
        <Track
          icon={GitBranch}
          name="AI + 基准检验"
          tint="#22d3ee"
          subtitle="靠误差和诊断，每一步都改在点子上"
          steps={abHero}
          timeLabel={fmtDuration(ab.time_to_pass_s)}
          endLabel={`修到 ${pct(ab.final_qoi_error)} —— 合格了`}
          endGood
        />
      </div>

      {/* 广度：带检验的流程把其他故障也都抓到并修好 */}
      <div className="mt-6 border-t border-white/5 pt-4">
        <p className="mb-2 text-xs text-slate-400">
          这套带检验的流程，把另外两种注入的故障也都抓到并修好了：
        </p>
        <div className="flex flex-wrap gap-2">
          {["coarse_mesh", "solver_setting_error"].map((f) => {
            const s = steps("agent_plus_benchmark", f);
            const last = s[s.length - 1];
            return (
              <span
                key={f}
                className="chip border-emerald-400/25 bg-emerald-400/[0.07] text-emerald-200"
              >
                <CheckCircle2 size={13} /> {FAULT_LABELS[f as keyof typeof FAULT_LABELS]} →{" "}
                {pct(last.qoi_error)}
              </span>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function Track({
  icon: Icon,
  name,
  subtitle,
  tint,
  steps,
  timeLabel,
  endLabel,
  endGood,
}: {
  icon: typeof Bot;
  name: string;
  subtitle: string;
  tint: string;
  steps: TimelineStep[];
  timeLabel: string;
  endLabel: string;
  endGood: boolean;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-ink-900/40 p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span
            className="grid h-8 w-8 place-items-center rounded-lg border border-white/10"
            style={{ background: `${tint}1a`, color: tint }}
          >
            <Icon size={16} />
          </span>
          <div>
            <p className="text-sm font-semibold text-slate-100">{name}</p>
            <p className="text-[11px] text-slate-500">{subtitle}</p>
          </div>
        </div>
        <span className="chip text-slate-300">
          <Clock size={12} /> {timeLabel}
        </span>
      </div>

      <div className="flex items-center gap-1 overflow-x-auto pb-1">
        {steps.map((s, i) => (
          <div key={s.round_index} className="flex items-center">
            <div
              className="reveal-pop flex flex-col items-center"
              style={{ animationDelay: `${i * 110}ms` }}
            >
              <div
                className="grid h-9 w-9 place-items-center rounded-full border-2 text-[12px] font-bold"
                style={{
                  borderColor: STATUS_COLOR[s.engineering_status],
                  color: STATUS_COLOR[s.engineering_status],
                  background: `${STATUS_COLOR[s.engineering_status]}14`,
                }}
              >
                {s.round_index}
              </div>
              <span className="mt-1 stat-num text-[10px] text-slate-400">
                {pct(s.qoi_error)}
              </span>
            </div>
            {i < steps.length - 1 && (
              <div className="mx-1 h-0.5 w-6 shrink-0 bg-white/10 sm:w-10" />
            )}
          </div>
        ))}

        <div className="mx-2 h-0.5 w-6 shrink-0 bg-white/10" />
        <div
          className="reveal flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold"
          style={{
            background: endGood ? "rgba(52,211,153,0.12)" : "rgba(251,191,36,0.12)",
            color: endGood ? "#6ee7b7" : "#fcd34d",
            animationDelay: `${steps.length * 110}ms`,
          }}
        >
          <Flag size={13} /> {endLabel}
        </div>
      </div>
    </div>
  );
}
