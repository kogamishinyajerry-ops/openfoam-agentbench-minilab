import { Waves, CheckCircle2, AlertTriangle } from "lucide-react";
import evidence from "../data/realEvidence.json";
import { FAULT_LABELS, FAILURE_SHORT, pct } from "../lib/data";
import type { Fault } from "../lib/types";

// 这一块不是回放：下面的数字来自一次真实的 OpenFOAM（icoFoam）运行。
export default function RealEvidence() {
  const ev = evidence as {
    container: string;
    correct: { qoi_error: number; u_peak_sampled: number; u_peak_analytical: number };
    faults: {
      fault: string;
      qoi_error: number;
      residual_final: number;
      false_success_detected: boolean;
      diagnosis: string;
      confidence: number;
    }[];
  };

  return (
    <section className="glass relative overflow-hidden p-6">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-sky-400/15 text-sky-300">
            <Waves size={18} />
          </span>
          <div>
            <p className="section-title">不是演的 · 真实 OpenFOAM</p>
            <h2 className="mt-0.5 text-lg font-semibold text-slate-100">
              这套流程，在一次真实的 icoFoam 运行上验证过
            </h2>
          </div>
        </div>
        <span className="chip border-sky-400/30 bg-sky-400/10 font-mono text-[11px] text-sky-200">
          容器：{ev.container}
        </span>
      </div>
      <p className="mb-4 max-w-3xl text-[13px] text-slate-400">
        前面的看板用内置数据演示「会发生什么」；这一块是真刀真枪在 OpenFOAM 里跑出来的结果——
        正确案例几乎贴合标准答案，每个注入的故障都是被检验真实抓到并诊断对的「假成功」。
      </p>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="reveal rounded-xl border border-emerald-400/25 bg-emerald-400/[0.06] p-4">
          <div className="flex items-center gap-2">
            <CheckCircle2 size={16} className="text-emerald-400" />
            <p className="text-sm font-semibold text-emerald-200">正确案例</p>
          </div>
          <p className="mt-2 stat-num text-2xl font-bold text-emerald-300">
            {pct(ev.correct.qoi_error)}
          </p>
          <p className="mt-1 text-[11px] text-slate-400">
            与标准答案的 L2 误差 · 峰值流速 {ev.correct.u_peak_sampled} / 标准{" "}
            {ev.correct.u_peak_analytical}
          </p>
        </div>

        {ev.faults.map((f, i) => (
          <div
            key={f.fault}
            className="reveal rounded-xl border border-rose-400/20 bg-rose-400/[0.05] p-4"
            style={{ animationDelay: `${(i + 1) * 70}ms` }}
          >
            <div className="flex items-center gap-2">
              <AlertTriangle size={16} className="text-rose-400" />
              <p className="text-sm font-semibold text-rose-200">
                {FAULT_LABELS[f.fault as Fault]}
              </p>
            </div>
            <p className="mt-2 stat-num text-2xl font-bold text-rose-300">{pct(f.qoi_error)}</p>
            <p className="mt-1 text-[11px] text-fuchsia-300">
              → 诊断：{FAILURE_SHORT[f.diagnosis] ?? f.diagnosis}（{Math.round(f.confidence * 100)}%）
            </p>
          </div>
        ))}
      </div>
      <p className="mt-3 text-center text-[11px] text-slate-500">
        正确案例复现了解析解的抛物线；每个注入的故障都是基准检验真实抓到并诊断正确的「假成功」。
        你也可以自己跑：{" "}
        <code className="font-mono text-slate-400">ofab demo real-evidence</code>
      </p>
    </section>
  );
}
