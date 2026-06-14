import type { ReactNode } from "react";
import { FlaskConical, Github, Waves, Gauge, Ruler } from "lucide-react";
import { bundle } from "./lib/data";
import Primer from "./components/Primer";
import FlowAnimation from "./components/FlowAnimation";
import VelocityProfileChart from "./components/VelocityProfileChart";
import MetricCards from "./components/MetricCards";
import ExperimentTimeline from "./components/ExperimentTimeline";
import DiagnosisPanel from "./components/DiagnosisPanel";
import ExperienceMemory from "./components/ExperienceMemory";
import FlywheelRecall from "./components/FlywheelRecall";
import SecondCaseCouette from "./components/SecondCaseCouette";
import ThirdCasePipe from "./components/ThirdCasePipe";
import RealEvidence from "./components/RealEvidence";
import SectionNav, { type NavSection } from "./components/SectionNav";
import ErrorBoundary from "./components/ErrorBoundary";

const SECTIONS: NavSection[] = [
  { id: "primer", label: "看懂项目" },
  { id: "loop", label: "反馈飞轮" },
  { id: "profile", label: "速度剖面" },
  { id: "metrics", label: "前后对比" },
  { id: "experiment", label: "对照实验" },
  { id: "diagnosis", label: "智能审计" },
  { id: "memory", label: "错题本" },
  { id: "recall", label: "复发复用" },
  { id: "secondcase", label: "举一反三" },
  { id: "thirdcase", label: "圆管案例" },
  { id: "evidence", label: "真实验证" },
];

const MODE_CN: Record<string, string> = {
  replay: "回放演示",
  mock: "模拟数据",
  openfoam: "真实 OpenFOAM",
};

export default function App() {
  const c = bundle.case;
  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:py-14">
      {/* Hero */}
      <header className="reveal mb-8">
        <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-medium text-cyan-200">
          <FlaskConical size={14} /> OpenFOAM-AgentBench 迷你实验室
          <span className="rounded-full bg-cyan-400/15 px-2 py-0.5 text-[10px] uppercase tracking-wider text-cyan-300">
            {MODE_CN[bundle.mode] ?? bundle.mode}
          </span>
        </div>
        <h1 className="bg-gradient-to-br from-white via-slate-200 to-slate-400 bg-clip-text text-4xl font-extrabold leading-tight text-transparent sm:text-5xl">
          让 AI 从「会跑仿真」<br className="hidden sm:block" />
          变成「会算对、还越用越聪明」
        </h1>
        <p className="mt-3 max-w-2xl text-base text-slate-400">
          {bundle.story.slogan}
        </p>

        <div className="mt-5 flex flex-wrap gap-2">
          <Chip icon={Waves} text={c.title} />
          <Chip icon={Gauge} text={`雷诺数 Re_H ≈ ${c.reynolds_h}（层流）`} />
          <Chip icon={Ruler} text={`管中央最快流速 ≈ ${c.u_max.toFixed(2)} m/s`} />
          <Chip
            icon={Ruler}
            text={`合格线：误差 < ${(c.tolerances.qoi_l2 * 100).toFixed(0)}%`}
          />
        </div>

        <p className="mt-4 max-w-3xl text-[11px] leading-relaxed text-slate-500">
          <span className="font-medium text-slate-400">关于本页数据</span>：速度剖面与误差都由物理解析解
          <span className="text-slate-300"> 真实算出、不是编的</span>；本页聚焦「判卷老师 → 反馈」这一层，
          AI 的修复<span className="text-slate-300">决策轨迹是脚本演示</span>（隔离讲清机制，并非真实 LLM 智能体在跑）；
          而页面底部「真实验证」一节，是在<span className="text-slate-300">真实 OpenFOAM</span> 里跑出来的结果。
        </p>
      </header>

      <main className="space-y-6">
        <Section id="primer" label="看懂项目"><Primer /></Section>
        <Section id="loop" label="反馈飞轮"><FlowAnimation /></Section>
        <Section id="profile" label="速度剖面"><VelocityProfileChart /></Section>
        <Section id="metrics" label="前后对比"><MetricCards /></Section>
        <Section id="experiment" label="对照实验"><ExperimentTimeline /></Section>
        <Section id="diagnosis" label="智能审计"><DiagnosisPanel /></Section>
        <Section id="memory" label="错题本"><ExperienceMemory /></Section>
        <Section id="recall" label="复发复用"><FlywheelRecall /></Section>
        <Section id="secondcase" label="举一反三"><SecondCaseCouette /></Section>
        <Section id="thirdcase" label="圆管案例"><ThirdCasePipe /></Section>
        <Section id="evidence" label="真实验证"><RealEvidence /></Section>
      </main>

      <SectionNav sections={SECTIONS} />

      <footer className="mt-10 flex flex-col items-center justify-between gap-3 border-t border-white/5 pt-6 text-sm text-slate-500 sm:flex-row">
        <p>
          一个 1–2 天的研究 Demo · 用「基准检验反馈」驱动 CFD 智能体闭环。
        </p>
        <span className="inline-flex items-center gap-1.5">
          <Github size={14} /> openfoam-agentbench-minilab
        </span>
      </footer>
    </div>
  );
}

// 每个区块 = 锚点容器（供右侧章节导航定位）+ 错误边界（单区块抛错只降级自己）。
function Section({
  id,
  label,
  children,
}: {
  id: string;
  label: string;
  children: ReactNode;
}) {
  return (
    <div id={id} className="scroll-mt-6">
      <ErrorBoundary label={label}>{children}</ErrorBoundary>
    </div>
  );
}

function Chip({ icon: Icon, text }: { icon: typeof Waves; text: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs font-medium text-slate-300">
      <Icon size={13} className="text-slate-400" />
      {text}
    </span>
  );
}
