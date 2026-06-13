import { History, Zap, BookOpen, Clock, RefreshCw, ArrowRight, Wrench } from "lucide-react";
import { bundle, pct } from "../lib/data";
import { FAILURE_SHORT } from "../lib/data";
import type { FlywheelEncounter } from "../lib/types";

export default function FlywheelRecall() {
  const fw = bundle.flywheel;
  const savedPct = Math.abs(Math.round(fw.time_saved_pct));

  return (
    <section className="glass-strong relative overflow-hidden p-6">
      <div className="pointer-events-none absolute -right-16 -top-10 h-56 w-56 rounded-full bg-cyan-500/10 blur-3xl" />
      <div className="mb-2 flex items-center gap-2.5">
        <span className="grid h-9 w-9 place-items-center rounded-xl bg-cyan-400/15 text-cyan-300">
          <Zap size={18} />
        </span>
        <div>
          <p className="section-title">经验飞轮 · 复发时直接翻错题本</p>
          <h2 className="mt-0.5 text-lg font-semibold text-slate-100">
            同样的错再犯,这次「秒修」
          </h2>
        </div>
      </div>
      <p className="mb-5 max-w-3xl text-[13px] text-slate-400">
        第一次遇到「{FAILURE_SHORT[fw.failure_mode]}」,得边诊断边试、修了 {fw.first_encounter.rerun_count} 轮。
        把它记进「错题本」之后——<span className="text-cyan-200">同样的故障再出现,直接命中已知修复,
        {fw.second_encounter.rerun_count} 轮就修好</span>,省掉一半来回。这就是「数据飞轮」:越用越快。
      </p>

      {/* 翻出来的那条错题 */}
      <div className="mb-5 rounded-2xl border border-fuchsia-400/20 bg-fuchsia-400/[0.05] p-4">
        <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-fuchsia-200">
          <BookOpen size={14} /> 从错题本翻出的这一条（{FAILURE_SHORT[fw.failure_mode]}）
        </p>
        <div className="grid gap-2 sm:grid-cols-2">
          <div className="flex gap-2 text-[13px] text-slate-300">
            <span className="shrink-0 text-slate-500">症状</span>
            <span>{fw.recalled.symptom}</span>
          </div>
          <div className="flex gap-2 text-[13px] text-slate-300">
            <Wrench size={13} className="mt-0.5 shrink-0 text-emerald-400" />
            <span className="text-emerald-200">{fw.recalled.repair}</span>
          </div>
        </div>
      </div>

      {/* 首次 vs 复发 */}
      <div className="grid items-center gap-3 lg:grid-cols-[1fr_auto_1fr]">
        <Encounter
          tag="第一次遇到"
          sub="边诊断边摸索"
          icon={History}
          tint="#fbbf24"
          enc={fw.first_encounter}
        />
        <div className="flex items-center justify-center">
          <div className="hidden lg:flex h-10 w-10 items-center justify-center rounded-full border border-cyan-400/30 bg-cyan-400/10 text-cyan-300">
            <ArrowRight size={18} />
          </div>
          <div className="lg:hidden text-cyan-400">↓ 记进错题本后 ↓</div>
        </div>
        <Encounter
          tag="复发 · 命中错题本"
          sub="直接套用已知修复"
          icon={Zap}
          tint="#22d3ee"
          enc={fw.second_encounter}
          good
        />
      </div>

      {/* 收益条 */}
      <div className="reveal mt-5 flex flex-wrap items-center justify-center gap-3 rounded-xl border border-emerald-400/20 bg-emerald-400/[0.06] px-4 py-3 text-center">
        <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-emerald-200">
          <RefreshCw size={15} /> 重跑少 {fw.rounds_saved} 轮
        </span>
        <span className="text-slate-600">·</span>
        <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-emerald-200">
          <Clock size={15} /> 修复耗时省 {savedPct}%
        </span>
        <span className="text-slate-600">·</span>
        <span className="text-sm text-emerald-100">每复用一次,飞轮就更快一点</span>
      </div>
    </section>
  );
}

function Encounter({
  tag,
  sub,
  icon: Icon,
  tint,
  enc,
  good,
}: {
  tag: string;
  sub: string;
  icon: typeof History;
  tint: string;
  enc: FlywheelEncounter;
  good?: boolean;
}) {
  return (
    <div
      className="reveal rounded-2xl border bg-ink-900/40 p-4"
      style={{ borderColor: good ? "rgba(34,211,238,0.25)" : "rgba(255,255,255,0.1)" }}
    >
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span
            className="grid h-8 w-8 place-items-center rounded-lg border border-white/10"
            style={{ background: `${tint}1a`, color: tint }}
          >
            <Icon size={16} />
          </span>
          <div>
            <p className="text-sm font-semibold text-slate-100">{tag}</p>
            <p className="text-[11px] text-slate-500">{sub}</p>
          </div>
        </div>
        <span className="chip text-slate-300">
          <Clock size={12} /> {enc.time_label}
        </span>
      </div>

      {/* 误差路径 */}
      <div className="flex flex-wrap items-center gap-1.5">
        {enc.path_pct.map((p, i) => {
          const last = i === enc.path_pct.length - 1;
          return (
            <div key={i} className="flex items-center gap-1.5">
              <span
                className={`stat-num rounded-md px-2 py-1 text-xs font-bold ${
                  last
                    ? "bg-emerald-400/15 text-emerald-300"
                    : "bg-rose-400/10 text-rose-300"
                }`}
              >
                {p.toFixed(1)}%
              </span>
              {!last && <span className="text-slate-600">→</span>}
            </div>
          );
        })}
      </div>
      <p className="mt-2 text-[11px] text-slate-500">
        {enc.rerun_count} 轮重跑修到合格（误差 {pct(enc.path_pct[enc.path_pct.length - 1] / 100)}）
      </p>
    </div>
  );
}
