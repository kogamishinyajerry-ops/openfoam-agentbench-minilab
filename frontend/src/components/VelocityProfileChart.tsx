import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { bundle, pct } from "../lib/data";

type View = "before" | "after";

export default function VelocityProfileChart() {
  const [view, setView] = useState<View>("before");
  const p = bundle.profiles;

  const data = useMemo(
    () =>
      p.reference.y.map((y, i) => ({
        y,
        ref: p.reference.u[i],
        failed: p.failed.u[i],
        repaired: p.repaired.u[i],
        stalled: p.agent_only_final.u[i],
      })),
    [p]
  );

  // 横轴范围按数据自动取，换案例也不会被裁掉
  const xMax = useMemo(
    () =>
      Math.max(...data.flatMap((d) => [d.ref, d.failed, d.repaired, d.stalled])) *
      1.13,
    [data]
  );

  const failedErr = p.failed.qoi_error ?? 0;
  const repairedErr = p.repaired.qoi_error ?? 0;
  const tol = bundle.case.tolerances.qoi_l2;

  return (
    <section className="glass-strong p-6">
      <div className="mb-2 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="section-title">看得见的「对错」· 速度剖面</p>
          <h2 className="mt-1 text-lg font-semibold text-slate-100">
            算出来的水流，和标准答案对得上吗？
          </h2>
        </div>
        <div className="flex rounded-xl border border-white/10 bg-white/5 p-1 text-sm">
          {(["before", "after"] as View[]).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`rounded-lg px-3 py-1.5 font-medium transition ${
                view === v ? "bg-white/10 text-white" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {v === "before" ? "故障时" : "修复后"}
            </button>
          ))}
        </div>
      </div>
      <p className="mb-4 max-w-3xl text-[13px] text-slate-400">
        水在管道里流，正确的样子是<span className="text-sky-300">中间快、贴着管壁为零</span>——
        一条对称的「小山包」曲线（蓝线就是标准答案）。点右上角切换：
        <span className="text-rose-300">故障时</span>红虚线偏得很远，
        <span className="text-emerald-300">修复后</span>绿线几乎贴回蓝线。
      </p>

      <div className="grid gap-5 lg:grid-cols-[1.6fr_1fr]">
        <div className="h-[340px] w-full">
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
                  value: "管道高度（0=下壁，1=上壁）",
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
                name="标准答案"
                dataKey="ref"
                stroke="#38bdf8"
                strokeWidth={2.5}
                dot={false}
                isAnimationActive={false}
              />
              {view === "before" ? (
                <Line
                  name="注入故障后"
                  dataKey="failed"
                  stroke="#fb7185"
                  strokeWidth={2.5}
                  strokeDasharray="6 4"
                  dot={false}
                  isAnimationActive={false}
                />
              ) : (
                <Line
                  name="修复后"
                  dataKey="repaired"
                  stroke="#34d399"
                  strokeWidth={2.5}
                  dot={false}
                  isAnimationActive={false}
                />
              )}
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="flex flex-col justify-center gap-3">
          <Legend color="#38bdf8" label="标准答案（解析解）" sub="数学上的精确答案，可直接对照" />
          <div key={view} className="reveal">
            {view === "before" ? (
              <Legend
                color="#fb7185"
                dashed
                label="注入故障后"
                sub={`误差 ${pct(failedErr)} · 超过 ${pct(tol, 0)} 合格线`}
                bad
              />
            ) : (
              <Legend
                color="#34d399"
                label="修复后"
                sub={`误差 ${pct(repairedErr)} · 已进入合格线`}
                good
              />
            )}
          </div>

          <div className="mt-1 rounded-xl border border-white/10 bg-ink-900/60 p-4">
            <p className="text-xs text-slate-400">和标准答案的差距（误差）</p>
            <div className="mt-1 flex items-baseline gap-2">
              <span className="stat-num text-2xl font-bold text-rose-300">{pct(failedErr)}</span>
              <span className="text-slate-500">→</span>
              <span className="stat-num text-2xl font-bold text-emerald-300">
                {pct(repairedErr)}
              </span>
            </div>
            <p className="mt-1 text-[11px] text-slate-500">
              从「明显不对」降到「基本准确」——越小越好
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

function Legend({
  color,
  label,
  sub,
  dashed,
  good,
  bad,
}: {
  color: string;
  label: string;
  sub: string;
  dashed?: boolean;
  good?: boolean;
  bad?: boolean;
}) {
  return (
    <div className="flex items-center gap-3">
      <svg width="34" height="12" className="shrink-0">
        <line
          x1="0"
          y1="6"
          x2="34"
          y2="6"
          stroke={color}
          strokeWidth="3"
          strokeDasharray={dashed ? "6 4" : undefined}
        />
      </svg>
      <div>
        <p
          className={`text-sm font-semibold ${
            good ? "text-emerald-200" : bad ? "text-rose-200" : "text-slate-200"
          }`}
        >
          {label}
        </p>
        <p className="text-[11px] text-slate-500">{sub}</p>
      </div>
    </div>
  );
}
