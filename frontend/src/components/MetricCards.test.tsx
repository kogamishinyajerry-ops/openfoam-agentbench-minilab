import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import MetricCards from "./MetricCards";
import { bundle, fmtDuration, pct } from "../lib/data";

// claim 2：「加了判卷老师值不值」——六张前后对比卡的数字必须来自 bundle.comparison，
// 不能写死。任何让 Demo 数据失真的改动都该让这里变红。
describe("MetricCards", () => {
  const c = bundle.comparison;
  const ab = bundle.workflows.find((w) => w.workflow === "agent_plus_benchmark")!;

  it("六张对比卡的标题都在", () => {
    render(<MetricCards />);
    for (const t of [
      "修对耗时",
      "重跑次数",
      "最终误差",
      "抓到的假成功",
      "沉淀的经验",
      "自动修复成功率",
    ]) {
      expect(screen.getByText(t)).toBeInTheDocument();
    }
  });

  it("关键数字绑定到 bundle.comparison / workflows", () => {
    const { container } = render(<MetricCards />);
    const text = container.textContent ?? "";
    // 抓到的假成功（claim 2 核心指标）
    expect(text).toContain(`${c.false_success_detected.after} 次`);
    // 沉淀的经验
    expect(text).toContain(`${c.experience_records.after} 条`);
    // 最终误差（after，百分比）
    expect(text).toContain(pct(c.qoi_error.after));
    // 修对耗时（after，M 分 SS 秒）
    expect(text).toContain(fmtDuration(c.time_to_pass.after));
    // 自动修复成功率（after，0 位小数）
    expect(text).toContain(pct(ab.auto_repair_success_rate, 0));
  });
});
