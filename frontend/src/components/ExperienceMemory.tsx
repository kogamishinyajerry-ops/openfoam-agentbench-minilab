import { BrainCircuit, FileJson, FileText, ShieldCheck, Sparkles } from "lucide-react";
import { bundle, FAILURE_SHORT, FAILURE_LABELS } from "../lib/data";
import type { FailureMode } from "../lib/types";

const MODE_TINT: Record<FailureMode, string> = {
  NONE: "#64748b",
  BC_MISMATCH: "#fb7185",
  MESH_TOO_COARSE: "#fbbf24",
  RESIDUAL_NOT_CONVERGED: "#c084fc",
};

export default function ExperienceMemory() {
  const records = bundle.experience;

  return (
    <section className="glass-strong relative overflow-hidden p-6">
      <div className="pointer-events-none absolute -left-16 bottom-0 h-56 w-56 rounded-full bg-fuchsia-500/10 blur-3xl" />
      <div className="mb-2 flex items-center gap-2.5">
        <span className="grid h-9 w-9 place-items-center rounded-xl bg-fuchsia-400/15 text-fuchsia-300">
          <BrainCircuit size={18} />
        </span>
        <div>
          <p className="section-title">经验飞轮 · 错题本</p>
          <h2 className="mt-0.5 text-lg font-semibold text-slate-100">
            每一次失败，都被记成一条「错题」
          </h2>
        </div>
      </div>
      <p className="mb-5 max-w-3xl text-[13px] text-slate-400">
        每修好一种故障，就把「什么症状 → 怎么改 → 改完什么效果」存成一条经验。
        下次再遇到同样的坑，AI 能直接翻「错题本」，不用从头试。
      </p>

      <div className="grid gap-4 md:grid-cols-3">
        {records.map((r, i) => {
          const tint = MODE_TINT[r.failure_mode];
          return (
            <div
              key={r.failure_mode}
              className="reveal relative rounded-2xl border border-white/10 bg-ink-900/50 p-4"
              style={{ animationDelay: `${i * 100}ms` }}
            >
              <div
                className="pointer-events-none absolute -right-8 -top-8 h-24 w-24 rounded-full opacity-20 blur-2xl"
                style={{ background: tint }}
              />
              <div className="flex items-center justify-between">
                <span className="text-sm font-bold" style={{ color: tint }}>
                  {FAILURE_SHORT[r.failure_mode]}
                </span>
                {r.promote_to_regression && (
                  <span className="chip border-emerald-400/30 bg-emerald-400/10 text-[10px] text-emerald-300">
                    <ShieldCheck size={11} /> 转为回归用例
                  </span>
                )}
              </div>
              <p className="mt-1 text-[11px] text-slate-500">
                {FAILURE_LABELS[r.failure_mode]}
              </p>

              <Field label="症状" value={r.symptom} />
              <Field label="修复方式" value={r.repair} />
              <div className="mt-2.5">
                <p className="text-[10px] uppercase tracking-wider text-slate-500">结果</p>
                <p className="mt-0.5 text-[13px] font-medium text-emerald-300">{r.outcome}</p>
              </div>

              <div className="mt-3 flex flex-wrap gap-1.5 border-t border-white/5 pt-3">
                <Artifact icon={FileJson} name="failure_mode.json" />
                <Artifact icon={FileText} name="repair.md" />
                <Artifact icon={ShieldCheck} name="regression.yaml" />
              </div>
            </div>
          );
        })}
      </div>

      <div className="reveal mt-6 flex items-center justify-center gap-2 rounded-xl border border-fuchsia-400/20 bg-fuchsia-400/[0.05] px-4 py-3 text-center">
        <Sparkles size={16} className="text-fuchsia-300" />
        <p className="text-sm font-medium text-fuchsia-100">
          每一次失败，都变成下一次自动避开它的能力。
        </p>
      </div>
    </section>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="mt-2.5">
      <p className="text-[10px] uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-0.5 text-[13px] leading-snug text-slate-300">{value}</p>
    </div>
  );
}

function Artifact({ icon: Icon, name }: { icon: typeof FileJson; name: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-md border border-white/10 bg-white/5 px-2 py-0.5 font-mono text-[10px] text-slate-400">
      <Icon size={11} /> {name}
    </span>
  );
}
