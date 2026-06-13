import { Timer, RefreshCw, Activity, ShieldAlert, Brain, Wrench } from "lucide-react";
import { bundle, fmtDuration, pct } from "../lib/data";

type Dir = "lower" | "higher";

interface Card {
  icon: typeof Timer;
  title: string;
  hint: string;
  before: number;
  after: number;
  beforeLabel: string;
  afterLabel: string;
  dir: Dir; // 哪个方向算"更好"
  accent: string;
}

export default function MetricCards() {
  const c = bundle.comparison;
  const ab = bundle.workflows.find((w) => w.workflow === "agent_plus_benchmark")!;
  const ao = bundle.workflows.find((w) => w.workflow === "agent_only")!;

  const cards: Card[] = [
    {
      icon: Timer,
      title: "修对耗时",
      hint: "多久把它修到合格",
      before: c.time_to_pass.before,
      after: c.time_to_pass.after,
      beforeLabel: fmtDuration(c.time_to_pass.before),
      afterLabel: fmtDuration(c.time_to_pass.after),
      dir: "lower",
      accent: "#22d3ee",
    },
    {
      icon: RefreshCw,
      title: "重跑次数",
      hint: "来回试了几次",
      before: c.rerun_count.before,
      after: c.rerun_count.after,
      beforeLabel: `${c.rerun_count.before} 次`,
      afterLabel: `${c.rerun_count.after} 次`,
      dir: "lower",
      accent: "#818cf8",
    },
    {
      icon: Activity,
      title: "最终误差",
      hint: "和标准答案差多少",
      before: c.qoi_error.before,
      after: c.qoi_error.after,
      beforeLabel: pct(c.qoi_error.before),
      afterLabel: pct(c.qoi_error.after),
      dir: "lower",
      accent: "#34d399",
    },
    {
      icon: ShieldAlert,
      title: "抓到的假成功",
      hint: "看似成功、实则算错",
      before: 0,
      after: c.false_success_detected.after,
      beforeLabel: "0 次",
      afterLabel: `${c.false_success_detected.after} 次`,
      dir: "higher",
      accent: "#fb7185",
    },
    {
      icon: Brain,
      title: "沉淀的经验",
      hint: "攒了几条「错题」",
      before: 0,
      after: c.experience_records.after,
      beforeLabel: "0 条",
      afterLabel: `${c.experience_records.after} 条`,
      dir: "higher",
      accent: "#f0abfc",
    },
    {
      icon: Wrench,
      title: "自动修复成功率",
      hint: "给的建议改完管不管用",
      before: ao.auto_repair_success_rate,
      after: ab.auto_repair_success_rate,
      beforeLabel: pct(ao.auto_repair_success_rate, 0),
      afterLabel: pct(ab.auto_repair_success_rate, 0),
      dir: "higher",
      accent: "#38bdf8",
    },
  ];

  return (
    <section>
      <div className="mb-2 flex items-end justify-between">
        <div>
          <p className="section-title">前后对比</p>
          <h2 className="mt-1 text-lg font-semibold text-slate-100">
            加了「判卷老师」，到底值不值？
          </h2>
        </div>
        <div className="hidden gap-2 text-xs sm:flex">
          <span className="chip text-slate-400">只有 AI</span>
          <span className="chip border-cyan-400/30 bg-cyan-400/10 text-cyan-200">
            AI + 基准检验
          </span>
        </div>
      </div>
      <p className="mb-4 max-w-3xl text-[13px] text-slate-400">
        同一个任务：删除线上的是「只有 AI」的成绩，大字是「AI + 基准检验」的成绩。
        差距越大，越说明这道「检验」有用。
      </p>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {cards.map((card, i) => (
          <MetricCard key={card.title} card={card} index={i} />
        ))}
      </div>
    </section>
  );
}

function MetricCard({ card, index }: { card: Card; index: number }) {
  const improved =
    card.dir === "lower" ? card.after < card.before : card.after > card.before;
  const deltaPct =
    card.before === 0
      ? null
      : Math.round(((card.after - card.before) / card.before) * 100);
  const Icon = card.icon;

  return (
    <div
      className="glass reveal relative overflow-hidden p-5"
      style={{ animationDelay: `${index * 70}ms` }}
    >
      <div
        className="pointer-events-none absolute -right-10 -top-10 h-28 w-28 rounded-full opacity-20 blur-2xl"
        style={{ background: card.accent }}
      />
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span
            className="grid h-9 w-9 place-items-center rounded-xl border border-white/10"
            style={{ background: `${card.accent}1a`, color: card.accent }}
          >
            <Icon size={18} />
          </span>
          <div>
            <p className="text-sm font-medium text-slate-200">{card.title}</p>
            <p className="text-[11px] text-slate-500">{card.hint}</p>
          </div>
        </div>
        {deltaPct !== null && (
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
              improved
                ? "bg-emerald-400/15 text-emerald-300"
                : "bg-rose-400/15 text-rose-300"
            }`}
          >
            {deltaPct > 0 ? "+" : ""}
            {deltaPct}%
          </span>
        )}
      </div>

      <div className="mt-4 flex items-baseline gap-2.5">
        <span className="stat-num text-3xl font-bold" style={{ color: card.accent }}>
          {card.afterLabel}
        </span>
        <span className="text-sm text-slate-500 line-through decoration-slate-600">
          {card.beforeLabel}
        </span>
      </div>

      {/* 对比条 */}
      <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-white/5">
        <div
          className="h-full rounded-full transition-all"
          style={{ background: card.accent, width: `${barWidth(card)}%` }}
        />
      </div>
      <p className="mt-2 text-[11px] text-slate-500">
        {card.dir === "lower" ? "越低越好" : "越高越好"}
      </p>
    </div>
  );
}

function barWidth(card: Card): number {
  const max = Math.max(card.before, card.after, 1);
  const frac = card.after / max;
  return card.dir === "lower" ? (1 - frac) * 100 || 12 : frac * 100;
}
