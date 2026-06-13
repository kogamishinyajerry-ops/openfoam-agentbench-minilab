import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import ExperimentTimeline from "./ExperimentTimeline";
import { bundle, fmtDuration, pct, FAULT_LABELS } from "../lib/data";
import type { Workflow } from "../lib/types";

// claim 1 + 2 的核心叙事:「瞎试 5 次还是错 vs 指点 2 次就修对」。这条对照时间线上的
// 每个误差圈、收尾标签、广度 chip 都必须来自 bundle.timeline / bundle.workflows,不能写死。
// 复刻组件的 steps() 取数逻辑,断言渲染确实绑定数据(否则测试会变成恒真)。
function steps(workflow: Workflow, fault: string) {
  return bundle.timeline
    .filter((s) => s.workflow === workflow && s.fault === fault)
    .sort((a, b) => a.round_index - b.round_index);
}

describe("ExperimentTimeline", () => {
  const ao = bundle.workflows.find((w) => w.workflow === "agent_only")!;
  const ab = bundle.workflows.find((w) => w.workflow === "agent_plus_benchmark")!;

  it("渲染对照实验标题与两条轨道(render 不抛错 = 直播安全网)", () => {
    const { container } = render(<ExperimentTimeline />);
    const text = container.textContent ?? "";
    expect(text).toContain("只有 AI");
    expect(text).toContain("AI + 基准检验");
  });

  it("两条轨道的收尾(耗时 + 最终误差)绑定到 bundle.workflows", () => {
    const { container } = render(<ExperimentTimeline />);
    const text = container.textContent ?? "";
    // 只有 AI:停在 final_qoi_error(8.7%)、耗时更久,还是错的
    expect(text).toContain(pct(ao.final_qoi_error));
    expect(text).toContain(fmtDuration(ao.time_to_pass_s));
    // AI + 基准检验:修到 final_qoi_error(2.1%)、更快,合格了
    expect(text).toContain(pct(ab.final_qoi_error));
    expect(text).toContain(fmtDuration(ab.time_to_pass_s));
  });

  it("主线 bc_mismatch 修复路径逐圈绑定 timeline,且带检验侧步数更少", () => {
    const { container } = render(<ExperimentTimeline />);
    const text = container.textContent ?? "";
    const aoHero = steps("agent_only", "bc_mismatch");
    const abHero = steps("agent_plus_benchmark", "bc_mismatch");
    expect(abHero.length).toBeGreaterThan(0);
    // 带检验:每一圈误差都渲染(18.4% → 5.8% → 2.1%)
    for (const s of abHero) expect(text).toContain(pct(s.qoi_error));
    // 「瞎试 5 次 vs 2 次修对」:无检验侧明显更多圈
    expect(aoHero.length).toBeGreaterThan(abHero.length);
  });

  it("广度:另外两种故障也被带检验流程修好(末圈误差 + 故障标签来自数据)", () => {
    const { container } = render(<ExperimentTimeline />);
    const text = container.textContent ?? "";
    for (const f of ["coarse_mesh", "solver_setting_error"] as const) {
      const s = steps("agent_plus_benchmark", f);
      expect(s.length).toBeGreaterThan(0);
      expect(text).toContain(pct(s[s.length - 1].qoi_error)); // 末圈修到的误差
      expect(text).toContain(FAULT_LABELS[f]); // 故障中文名
    }
  });
});
