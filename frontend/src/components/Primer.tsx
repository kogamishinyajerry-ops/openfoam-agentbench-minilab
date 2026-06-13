import { Cpu, AlertTriangle, CheckCircle2, ArrowRight, BookOpen } from "lucide-react";

const STEPS = [
  {
    tag: "怎么来的",
    icon: Cpu,
    tint: "#38bdf8",
    title: "AI 已经能自动做「仿真」了",
    body:
      "仿真，就是用电脑「预演」真实世界里的水流、气流——造汽车前先在电脑里吹风、修水管前先在电脑里走一遍水。不用每次都真做实验，又快又省钱。现在的 AI 已经能自己写、自己跑这些仿真。",
  },
  {
    tag: "卡在哪",
    icon: AlertTriangle,
    tint: "#fb7185",
    title: "但「程序没报错」≠「算得对」",
    body:
      "这是最要命的地方。就像考试「交了卷」不代表「答对了」。仿真程序跑完、没报错，看起来很成功——可结果可能和正确答案差着十万八千里。这种「假成功」要是被当成对的，工程上会出大问题。",
  },
  {
    tag: "我们怎么做",
    icon: CheckCircle2,
    tint: "#34d399",
    title: "给 AI 配一个「判卷老师」",
    body:
      "我们给 AI 加了一道「基准检验」——一个拿着标准答案的判卷老师。它对照标准答案，发现错误、说清为什么错、给出怎么改；AI 照着改、再验证，并把每次失败记成「错题本」。于是 AI 不只是「会跑」，而是「会变好、越用越聪明」。",
  },
];

const GLOSSARY = [
  ["仿真", "用电脑预演真实世界的水流 / 气流，省去真做实验"],
  ["AI Agent", "一个能自己动手、自己跑流程的 AI 助手"],
  ["OpenFOAM", "一款被广泛使用的专业流体仿真软件"],
  ["基准检验 / Benchmark", "拿「标准答案」给结果打分、挑错的「判卷老师」"],
  ["标准答案 / 解析解", "这个简单案例有数学上的精确答案，可直接对照"],
];

export default function Primer() {
  return (
    <section className="glass-strong p-6 sm:p-8">
      <div className="mb-5 flex items-center gap-2.5">
        <span className="grid h-9 w-9 place-items-center rounded-xl bg-cyan-400/15 text-cyan-300">
          <BookOpen size={18} />
        </span>
        <div>
          <p className="section-title">先花一分钟 · 看懂这个项目</p>
          <h2 className="mt-0.5 text-lg font-semibold text-slate-100">
            不懂技术也能看明白：它怎么来的、为什么这么做、做到了什么
          </h2>
        </div>
      </div>

      <div className="grid gap-3 lg:grid-cols-[1fr_auto_1fr_auto_1fr] lg:items-stretch">
        {STEPS.map((s, i) => {
          const Icon = s.icon;
          return (
            <div key={s.tag} className="contents">
              <div
                className="reveal rounded-2xl border border-white/10 bg-ink-900/50 p-5"
                style={{ animationDelay: `${i * 110}ms` }}
              >
                <div className="mb-2 flex items-center gap-2">
                  <span
                    className="grid h-8 w-8 place-items-center rounded-lg"
                    style={{ background: `${s.tint}1f`, color: s.tint }}
                  >
                    <Icon size={17} />
                  </span>
                  <span
                    className="rounded-full px-2 py-0.5 text-[11px] font-semibold"
                    style={{ background: `${s.tint}1f`, color: s.tint }}
                  >
                    {s.tag}
                  </span>
                </div>
                <p className="text-[15px] font-semibold text-slate-100">{s.title}</p>
                <p className="mt-1.5 text-[13px] leading-relaxed text-slate-400">
                  {s.body}
                </p>
              </div>
              {i < STEPS.length - 1 && (
                <div className="hidden items-center justify-center lg:flex">
                  <ArrowRight className="text-slate-600" size={20} />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* 关键词小词典 */}
      <div className="mt-5 rounded-2xl border border-white/10 bg-ink-900/40 p-4">
        <p className="mb-2 text-xs font-semibold text-slate-400">
          几个会反复出现的词（一句话解释）
        </p>
        <div className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
          {GLOSSARY.map(([term, def]) => (
            <div key={term} className="flex gap-2 text-[13px]">
              <span className="shrink-0 font-semibold text-cyan-200">{term}</span>
              <span className="text-slate-400">{def}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
