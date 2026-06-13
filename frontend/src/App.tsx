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
import RealEvidence from "./components/RealEvidence";
import SectionNav, { type NavSection } from "./components/SectionNav";

const SECTIONS: NavSection[] = [
  { id: "primer", label: "看懂项目" },
  { id: "loop", label: "反馈飞轮" },
  { id: "profile", label: "速度剖面" },
  { id: "metrics", label: "前后对比" },
  { id: "experiment", label: "对照实验" },
  { id: "diagnosis", label: "智能审计" },
  { id: "memory", label: "错题本" },
  { id: "recall", label: "复发复用" },
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
      </header>

      <main className="space-y-6">
        <div id="primer" className="scroll-mt-6"><Primer /></div>
        <div id="loop" className="scroll-mt-6"><FlowAnimation /></div>
        <div id="profile" className="scroll-mt-6"><VelocityProfileChart /></div>
        <div id="metrics" className="scroll-mt-6"><MetricCards /></div>
        <div id="experiment" className="scroll-mt-6"><ExperimentTimeline /></div>
        <div id="diagnosis" className="scroll-mt-6"><DiagnosisPanel /></div>
        <div id="memory" className="scroll-mt-6"><ExperienceMemory /></div>
        <div id="recall" className="scroll-mt-6"><FlywheelRecall /></div>
        <div id="evidence" className="scroll-mt-6"><RealEvidence /></div>
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

function Chip({ icon: Icon, text }: { icon: typeof Waves; text: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs font-medium text-slate-300">
      <Icon size={13} className="text-slate-400" />
      {text}
    </span>
  );
}
