import { useMemo } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Layers, ShieldAlert, ScanSearch, CheckCircle2, Ban, Waves } from "lucide-react";
import { bundle, pct, FAILURE_SHORT, FAULT_LABELS } from "../lib/data";
import couetteEvidence from "../data/realEvidenceCouette.json";
import type { Fault } from "../lib/types";

type CouetteEvidence = {
  container: string;
  correct: { qoi_error: number; u_top_sampled: number; u_top_analytical: number };
  faults: {
    fault: string;
    qoi_error: number;
    false_success_detected: boolean;
    diagnosis: string;
    confidence: number;
  }[];
  coarse_mesh_check: { qoi_error: number; overall_pass: boolean };
};

/**
 * 第二个案例：Couette 剪切流。证明「基准检验能举一反三」——用完全没改动的
 * scorecard / diagnose，去判一个和第一个案例不同的流动，照样抓出贴壁滑移的假成功。
 */
export default function SecondCaseCouette() {
  const s = bundle.second_case;
  const p = s.profiles;

  const data = useMemo(
    () =>
      p.reference.y.map((y, i) => ({
        y,
        ref: p.reference.u[i],
        failed: p.failed.u[i],
        repaired: p.repaired.u[i],
      })),
    [p]
  );
  const xMax = s.case.lid_velocity * 1.15;

  return (
    <section className="glass-strong relative overflow-hidden p-6">
      <div className="pointer-events-none absolute -right-20 -top-16 h-60 w-60 rounded-full bg-indigo-500/10 blur-3xl" />

      <div className="mb-2 flex items-center gap-2.5">
        <span className="grid h-9 w-9 place-items-center rounded-xl bg-indigo-400/15 text-indigo-300">
          <Layers size={18} />
        </span>
        <div>
          <p className="section-title">举一反三 · 第二个案例</p>
          <h2 className="mt-0.5 text-lg font-semibold text-slate-100">
            同一套「判卷老师」，换个流动照样管用
          </h2>
        </div>
      </div>
      <p className="mb-5 max-w-3xl text-[13px] text-slate-400">
        前面所有内容讲的是「水管里的流动」。这里换成另一种经典流动——
        <span className="text-indigo-200">剪切流（Couette）</span>：上面一块板拖着水走，
        贴着下面那块<span className="text-indigo-200">静止</span>的板，水速本该是 0。
        正确答案是一条<span className="text-sky-300">斜直线</span>（不再是「小山包」）。
        关键点：<span className="text-cyan-200">判卷老师的代码一行没改</span>，照样把这个全新流动里的「假成功」抓了出来。
      </p>

      <div className="grid gap-5 lg:grid-cols-[1.5fr_1fr]">
        {/* 线性剖面图 */}
        <div className="h-[300px] w-full">
          <ResponsiveContainer>
            <LineChart
              layout="vertical"
              data={data}
              margin={{ top: 8, right: 16, bottom: 24, left: 8 }}
            >
              <CartesianGrid stroke="rgba(255,255,255,0.06)" />
              <XAxis
                type="number"
                domain={[0, xMax]}
                tick={{ fill: "#94a3b8", fontSize: 11 }}
                tickFormatter={(v) => v.toFixed(2)}
                label={{
                  value: "流速 u（m/s）→ 越靠右越快",
                  position: "insideBottom",
                  offset: -12,
                  fill: "#94a3b8",
                  fontSize: 12,
                }}
              />
              <YAxis
                dataKey="y"
                type="number"
                domain={[0, 1]}
                ticks={[0, 0.25, 0.5, 0.75, 1]}
                tick={{ fill: "#94a3b8", fontSize: 11 }}
                label={{
                  value: "高度（0=静止板，1=拖动板）",
                  angle: -90,
                  position: "insideLeft",
                  fill: "#94a3b8",
                  fontSize: 12,
                }}
              />
              <Tooltip
                contentStyle={{
                  background: "rgba(14,20,38,0.95)",
                  border: "1px solid rgba(255,255,255,0.1)",
                  borderRadius: 12,
                  fontSize: 12,
                }}
                labelFormatter={(v) => `高度 ${Number(v).toFixed(2)}`}
                formatter={(val: number, name) => [val.toFixed(4), name]}
              />
              <Line
                name="标准答案（斜直线）"
                dataKey="ref"
                stroke="#38bdf8"
                strokeWidth={2.5}
                dot={false}
                isAnimationActive={false}
              />
              <Line
                name="注入故障后"
                dataKey="failed"
                stroke="#fb7185"
                strokeWidth={2.5}
                strokeDasharray="6 4"
                dot={false}
                isAnimationActive={false}
              />
              <Line
                name="修复后"
                dataKey="repaired"
                stroke="#34d399"
                strokeWidth={2.5}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* 判卷结果 */}
        <div className="flex flex-col gap-3">
          {/* 抓到假成功 */}
          <div className="rounded-xl border border-rose-400/25 bg-rose-400/[0.06] p-4">
            <p className="flex items-center gap-1.5 text-xs font-semibold text-rose-200">
              <ShieldAlert size={14} /> 同一套基准检验：抓到「假成功」
            </p>
            <p className="mt-1.5 font-mono text-[11px] text-slate-400">
              退出码 = 0（程序跑完了）· 工程误差 {pct(p.failed.qoi_error)}（其实不对）
            </p>
          </div>

          {/* 诊断 */}
          <div className="rounded-xl border border-fuchsia-400/20 bg-fuchsia-400/[0.05] p-4">
            <p className="flex items-center gap-1.5 text-xs font-semibold text-fuchsia-200">
              <ScanSearch size={14} /> 同一套诊断：{FAILURE_SHORT[s.diagnosis.failure_mode]}
              <span className="ml-1 font-mono text-[10px] font-normal text-slate-500">
                {s.diagnosis.failure_mode} · {Math.round(s.diagnosis.confidence * 100)}%
              </span>
            </p>
            <p className="mt-1.5 text-[12px] text-slate-300">
              贴壁滑移达 u_max 的 <span className="font-semibold text-fuchsia-200">{s.wall_slip_pct}%</span>
              ——静止板上的水速本该是 0，被设错了。
            </p>
          </div>

          {/* 修复后通过 */}
          <div className="rounded-xl border border-emerald-400/20 bg-emerald-400/[0.06] p-4">
            <p className="flex items-center gap-1.5 text-xs font-semibold text-emerald-200">
              <CheckCircle2 size={14} /> 修复后：误差 {pct(p.repaired.qoi_error)}，
              {s.repaired_pass ? "同一套基准检验判合格" : "仍需修复"}
            </p>
          </div>
        </div>
      </div>

      {/* 一行没改 + 诚实说明 */}
      <div className="mt-5 grid gap-3 sm:grid-cols-[1.4fr_1fr]">
        <div className="flex items-center gap-2.5 rounded-xl border border-cyan-400/20 bg-cyan-400/[0.06] px-4 py-3">
          <span className="text-lg">🔁</span>
          <p className="text-[13px] text-cyan-100">{s.generalizes_note}</p>
        </div>
        <div className="flex items-start gap-2 rounded-xl border border-white/10 bg-ink-900/50 px-4 py-3">
          <Ban size={14} className="mt-0.5 shrink-0 text-slate-500" />
          <p className="text-[11px] leading-relaxed text-slate-400">
            <span className="text-slate-300">「{s.not_applicable.label}」在这里不适用：</span>
            {s.not_applicable.reason}
          </p>
        </div>
      </div>

      {/* 真实 OpenFOAM 验证 —— 第二个案例同样有真刀真枪的证据 */}
      <RealStrip ev={couetteEvidence as CouetteEvidence} />
    </section>
  );
}

function RealStrip({ ev }: { ev: CouetteEvidence }) {
  return (
    <div className="mt-3 rounded-xl border border-sky-400/20 bg-sky-400/[0.05] p-4">
      <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 text-xs font-semibold text-sky-200">
          <Waves size={14} /> 不是演的：真实 OpenFOAM（icoFoam）也验证过
        </p>
        <span className="chip border-sky-400/30 bg-sky-400/10 font-mono text-[10px] text-sky-200">
          容器：{ev.container}
        </span>
      </div>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <EvCard
          tone="good"
          title="正确算例"
          big={pct(ev.correct.qoi_error)}
          sub={`复现解析直线 · 盖板 ${ev.correct.u_top_sampled}/${ev.correct.u_top_analytical}`}
        />
        {ev.faults.map((f) => (
          <EvCard
            key={f.fault}
            tone="bad"
            title={FAULT_LABELS[f.fault as Fault] ?? f.fault}
            big={pct(f.qoi_error)}
            sub={`→ ${FAILURE_SHORT[f.diagnosis] ?? f.diagnosis}（${Math.round(f.confidence * 100)}%）`}
          />
        ))}
        <EvCard
          tone="neutral"
          title="网格太粗（检查）"
          big={pct(ev.coarse_mesh_check.qoi_error)}
          sub="≈0 · 照样合格 → 印证不适用"
        />
      </div>
      <p className="mt-2 text-center text-[11px] text-slate-500">
        自己跑：<code className="font-mono text-slate-400">ofab demo couette-evidence</code>
      </p>
    </div>
  );
}

function EvCard({
  tone,
  title,
  big,
  sub,
}: {
  tone: "good" | "bad" | "neutral";
  title: string;
  big: string;
  sub: string;
}) {
  const styles = {
    good: { box: "border-emerald-400/25 bg-emerald-400/[0.06]", num: "text-emerald-300", t: "text-emerald-200" },
    bad: { box: "border-rose-400/20 bg-rose-400/[0.05]", num: "text-rose-300", t: "text-rose-200" },
    neutral: { box: "border-white/10 bg-ink-900/50", num: "text-slate-200", t: "text-slate-300" },
  }[tone];
  return (
    <div className={`rounded-lg border ${styles.box} p-3`}>
      <p className={`text-xs font-semibold ${styles.t}`}>{title}</p>
      <p className={`stat-num mt-1 text-xl font-bold ${styles.num}`}>{big}</p>
      <p className="mt-0.5 text-[10px] leading-tight text-slate-400">{sub}</p>
    </div>
  );
}
