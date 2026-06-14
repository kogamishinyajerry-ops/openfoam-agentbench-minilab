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
import { CircleDot, ShieldAlert, ScanSearch, CheckCircle2, Repeat, Waves } from "lucide-react";
import { bundle, pct, FAILURE_SHORT, FAULT_LABELS } from "../lib/data";
import pipeEvidence from "../data/realEvidencePipe.json";
import type { Fault } from "../lib/types";

type PipeEvidence = {
  container: string;
  geometry: string;
  correct: { qoi_error: number; u_peak_sampled: number; u_peak_analytical: number };
  faults: {
    fault: string;
    is_hero?: boolean;
    qoi_error: number;
    false_success_detected: boolean;
    diagnosis: string;
    confidence: number;
  }[];
};

/**
 * 第三个案例：圆管 Hagen–Poiseuille 流。把「举一反三」再推一步——不只换流动，还换了
 * 一种**故障**：这次主打的是「网格太粗」。同一套没改动的 scorecard / diagnose，照样把
 * 圆管里因径向网格太粗导致的「假成功」抓出来，并判明是网格分辨率问题。
 * 妙处：这个故障在第二个案例 Couette（直线解）里被老实标成「不适用」，到了圆管这条
 * 弯曲的抛物线上，它正是主场——框架按案例匹配故障，不硬套。
 */
export default function ThirdCasePipe() {
  const s = bundle.third_case;
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
  const xMax = s.case.u_max * 1.15;

  return (
    <section className="glass-strong relative overflow-hidden p-6">
      <div className="pointer-events-none absolute -right-20 -top-16 h-60 w-60 rounded-full bg-teal-500/10 blur-3xl" />

      <div className="mb-2 flex items-center gap-2.5">
        <span className="grid h-9 w-9 place-items-center rounded-xl bg-teal-400/15 text-teal-300">
          <CircleDot size={18} />
        </span>
        <div>
          <p className="section-title">举一反三 · 第三个案例</p>
          <h2 className="mt-0.5 text-lg font-semibold text-slate-100">
            再换一种流动 + 换一种「错法」，判卷老师照样接得住
          </h2>
        </div>
      </div>
      <p className="mb-5 max-w-3xl text-[13px] text-slate-400">
        这次是<span className="text-teal-200">圆管里的流动</span>（Hagen–Poiseuille），正确答案是一条
        <span className="text-sky-300">弯曲的抛物线</span>，管中心最快、贴着管壁为 0。更关键的是——这次的
        故障换成了<span className="text-amber-200">「网格太粗」</span>：径向网格太稀，会把中心的尖峰削平、
        把光滑曲线压成折线。<span className="text-cyan-200">判卷老师的代码依然一行没改</span>，照样抓出这个
        「假成功」，而且这回诊断的是<span className="text-amber-200">网格问题</span>，不是前两个案例的边界条件问题。
      </p>

      <div className="grid gap-5 lg:grid-cols-[1.5fr_1fr]">
        {/* 径向剖面图 */}
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
                  value: "径向位置（0=管中心，1=管壁）",
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
                labelFormatter={(v) => `径向位置 ${Number(v).toFixed(2)}`}
                formatter={(val: number, name) => [val.toFixed(4), name]}
              />
              <Line
                name="标准答案（抛物线）"
                dataKey="ref"
                stroke="#38bdf8"
                strokeWidth={2.5}
                dot={false}
                isAnimationActive={false}
              />
              <Line
                name="网格太粗（削平+折线）"
                dataKey="failed"
                stroke="#fbbf24"
                strokeWidth={2.5}
                strokeDasharray="6 4"
                dot={false}
                isAnimationActive={false}
              />
              <Line
                name="加密网格后"
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

          {/* 诊断 —— 这次是网格问题 */}
          <div className="rounded-xl border border-amber-400/25 bg-amber-400/[0.05] p-4">
            <p className="flex items-center gap-1.5 text-xs font-semibold text-amber-200">
              <ScanSearch size={14} /> 同一套诊断：{FAILURE_SHORT[s.diagnosis.failure_mode]}
              <span className="ml-1 font-mono text-[10px] font-normal text-slate-500">
                {s.diagnosis.failure_mode} · {Math.round(s.diagnosis.confidence * 100)}%
              </span>
            </p>
            <p className="mt-1.5 text-[12px] text-slate-300">
              中心峰值被削掉了 <span className="font-semibold text-amber-200">{s.peak_deficit_pct}%</span>
              ——贴壁仍是 0（不是边界条件问题），是<span className="text-amber-200">网格太粗</span>把曲线压扁了。
            </p>
          </div>

          {/* 修复后通过 */}
          <div className="rounded-xl border border-emerald-400/20 bg-emerald-400/[0.06] p-4">
            <p className="flex items-center gap-1.5 text-xs font-semibold text-emerald-200">
              <CheckCircle2 size={14} /> 加密网格后：误差 {pct(p.repaired.qoi_error)}，
              {s.repaired_pass ? "同一套基准检验判合格" : "仍需修复"}
            </p>
          </div>
        </div>
      </div>

      {/* 一行没改 + 故障匹配（与 Couette 互为镜像） */}
      <div className="mt-5 grid gap-3 sm:grid-cols-[1.4fr_1fr]">
        <div className="flex items-center gap-2.5 rounded-xl border border-cyan-400/20 bg-cyan-400/[0.06] px-4 py-3">
          <span className="text-lg">🔁</span>
          <p className="text-[13px] text-cyan-100">{s.generalizes_note}</p>
        </div>
        <div className="flex items-start gap-2 rounded-xl border border-amber-400/15 bg-amber-400/[0.04] px-4 py-3">
          <Repeat size={14} className="mt-0.5 shrink-0 text-amber-300/80" />
          <p className="text-[11px] leading-relaxed text-slate-400">
            <span className="text-amber-200/90">「{s.fault_fit_note.label}」在这里正是主场：</span>
            {s.fault_fit_note.reason}
          </p>
        </div>
      </div>

      {/* 真实 OpenFOAM 验证 —— 圆管也在真刀真枪的轴对称楔形网格上跑出了证据 */}
      <RealStrip ev={pipeEvidence as PipeEvidence} />
    </section>
  );
}

function RealStrip({ ev }: { ev: PipeEvidence }) {
  return (
    <div className="mt-3 rounded-xl border border-sky-400/20 bg-sky-400/[0.05] p-4">
      <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 text-xs font-semibold text-sky-200">
          <Waves size={14} /> 不是演的：真实 OpenFOAM（轴对称楔形网格）也验证过
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
          sub={`复现径向抛物线 · 峰值 ${ev.correct.u_peak_sampled}/${ev.correct.u_peak_analytical}`}
        />
        {ev.faults.map((f) => (
          <EvCard
            key={f.fault}
            tone={f.is_hero ? "hero" : "bad"}
            title={`${FAULT_LABELS[f.fault as Fault] ?? f.fault}${f.is_hero ? " ★主场" : ""}`}
            big={pct(f.qoi_error)}
            sub={`→ ${FAILURE_SHORT[f.diagnosis] ?? f.diagnosis}（${Math.round(f.confidence * 100)}%）`}
          />
        ))}
      </div>
      <p className="mt-2 text-center text-[11px] text-slate-500">
        自己跑：<code className="font-mono text-slate-400">ofab demo pipe-evidence</code>
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
  tone: "good" | "bad" | "hero";
  title: string;
  big: string;
  sub: string;
}) {
  const styles = {
    good: { box: "border-emerald-400/25 bg-emerald-400/[0.06]", num: "text-emerald-300", t: "text-emerald-200" },
    bad: { box: "border-rose-400/20 bg-rose-400/[0.05]", num: "text-rose-300", t: "text-rose-200" },
    hero: { box: "border-amber-400/30 bg-amber-400/[0.07]", num: "text-amber-300", t: "text-amber-200" },
  }[tone];
  return (
    <div className={`rounded-lg border ${styles.box} p-3`}>
      <p className={`text-xs font-semibold ${styles.t}`}>{title}</p>
      <p className={`stat-num mt-1 text-xl font-bold ${styles.num}`}>{big}</p>
      <p className="mt-0.5 text-[10px] leading-tight text-slate-400">{sub}</p>
    </div>
  );
}
