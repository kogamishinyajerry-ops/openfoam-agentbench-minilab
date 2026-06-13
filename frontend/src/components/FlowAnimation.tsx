import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Target,
  Bot,
  Waves,
  Gauge,
  ScanSearch,
  Wrench,
  BrainCircuit,
  Play,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import { bundle, pct } from "../lib/data";

const STAGES = [
  { key: "任务", icon: Target, color: "#7dd3fc", blurb: "「跑一个水管流动的算例」" },
  { key: "AI 生成", icon: Bot, color: "#818cf8", blurb: "AI 自动写出仿真算例" },
  { key: "跑仿真", icon: Waves, color: "#38bdf8", blurb: "求解器跑完，没报错" },
  { key: "基准检验", icon: Gauge, color: "#22d3ee", blurb: "拿标准答案对照、量误差" },
  { key: "诊断", icon: ScanSearch, color: "#c084fc", blurb: "说清是哪一类错" },
  { key: "修复", icon: Wrench, color: "#34d399", blurb: "照建议改，再跑一遍" },
  { key: "沉淀经验", icon: BrainCircuit, color: "#f0abfc", blurb: "把失败记成错题本" },
] as const;

export default function FlowAnimation() {
  const [active, setActive] = useState(-1);
  const [running, setRunning] = useState(false);
  const timers = useRef<number[]>([]);

  const clearTimers = () => {
    timers.current.forEach((t) => window.clearTimeout(t));
    timers.current = [];
  };

  const play = () => {
    clearTimers();
    setRunning(true);
    setActive(-1);
    STAGES.forEach((_, i) => {
      timers.current.push(
        window.setTimeout(() => {
          setActive(i);
          if (i === STAGES.length - 1) {
            timers.current.push(window.setTimeout(() => setRunning(false), 1100));
          }
        }, 200 + i * 850)
      );
    });
  };

  const reset = () => {
    clearTimers();
    setRunning(false);
    setActive(-1);
  };

  useEffect(() => () => clearTimers(), []);

  const heroFailed = bundle.profiles.failed.qoi_error ?? 0;

  return (
    <section className="glass-strong relative overflow-hidden p-6 sm:p-8">
      {/* 背景缓慢旋转的飞轮 */}
      <div className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 opacity-[0.13]">
        <div className={`h-full w-full rounded-full border border-dashed border-cyan-300 ${running ? "animate-spin-slow" : ""}`} />
        <div className="absolute inset-6 rounded-full border border-dashed border-fuchsia-300" />
        <div className="absolute inset-12 rounded-full border border-dashed border-emerald-300" />
      </div>

      <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="section-title">核心机制 · 反馈飞轮</p>
          <h2 className="mt-1 text-lg font-semibold text-slate-100">
            任务 → AI 生成 → 跑仿真 → 基准检验 → 诊断 → 修复 → 沉淀经验
          </h2>
        </div>
        <div className="flex gap-2">
          <button
            onClick={play}
            disabled={running}
            className="inline-flex items-center gap-2 rounded-xl bg-cyan-500/90 px-4 py-2 text-sm font-semibold text-ink-950 shadow-glow transition hover:bg-cyan-400 disabled:opacity-50"
          >
            <Play size={16} /> {running ? "演示中…" : "开始演示"}
          </button>
          <button
            onClick={reset}
            aria-label="重置演示"
            title="重置演示"
            className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-300 transition hover:bg-white/10"
          >
            <RotateCcw size={15} />
          </button>
        </div>
      </div>
      <p className="mb-6 max-w-3xl text-[13px] text-slate-400">
        普通 AI 只做前三步（跑完就算完）。我们多加了后面四步——
        <span className="text-cyan-200">检验 → 诊断 → 修复 → 记经验</span>，
        让它转成一个会自我改进的「飞轮」。点「开始演示」看它转一圈。
      </p>

      {/* 流程 */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
        {STAGES.map((s, i) => {
          const on = active >= i;
          const isActive = active === i;
          const Icon = s.icon;
          return (
            <div key={s.key} className="relative flex flex-col items-center text-center">
              <motion.div
                animate={{
                  scale: isActive ? 1.08 : 1,
                  borderColor: on ? s.color : "rgba(255,255,255,0.08)",
                }}
                transition={{ type: "spring", stiffness: 240, damping: 18 }}
                className="relative grid h-16 w-16 place-items-center rounded-2xl border bg-ink-850/80"
                style={{ boxShadow: on ? `0 0 28px -6px ${s.color}66` : "none" }}
              >
                {isActive && (
                  <span
                    className="absolute inset-0 animate-pulse-ring rounded-2xl border"
                    style={{ borderColor: s.color }}
                  />
                )}
                <Icon size={26} style={{ color: on ? s.color : "#64748b" }} />
              </motion.div>
              <p
                className="mt-2 text-sm font-semibold transition-colors"
                style={{ color: on ? "#e2e8f0" : "#64748b" }}
              >
                {s.key}
              </p>
              <p className="mt-0.5 hidden text-[11px] leading-tight text-slate-500 sm:block">
                {s.blurb}
              </p>
              {i < STAGES.length - 1 && (
                <div className="absolute right-[-10px] top-8 hidden h-px w-5 lg:block">
                  <div className="h-full w-full bg-white/10" />
                  <motion.div
                    className="h-full w-full"
                    style={{ background: s.color, marginTop: "-1px" }}
                    initial={{ scaleX: 0 }}
                    animate={{ scaleX: active > i ? 1 : 0 }}
                    transition={{ duration: 0.4 }}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* 核心反差：退出码"成功" vs 基准检验"其实错了" */}
      <AnimatePresence>
        {active >= 3 && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="mt-6 grid gap-3 sm:grid-cols-2"
          >
            <div className="flex items-center gap-3 rounded-xl border border-emerald-400/20 bg-emerald-400/[0.06] px-4 py-3">
              <CheckCircle2 className="shrink-0 text-emerald-400" size={22} />
              <div>
                <p className="text-sm font-semibold text-emerald-200">普通测试：成功 ✓</p>
                <p className="font-mono text-xs text-slate-400">退出码 = 0 · 程序跑完了</p>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-xl border border-rose-400/25 bg-rose-400/[0.07] px-4 py-3">
              <AlertTriangle className="shrink-0 text-rose-400" size={22} />
              <div>
                <p className="text-sm font-semibold text-rose-200">
                  基准检验：误差 {pct(heroFailed)} ✗
                </p>
                <p className="font-mono text-xs text-slate-400">
                  工程状态 = 需要修复（这是「假成功」）
                </p>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
