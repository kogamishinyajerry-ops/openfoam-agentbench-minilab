import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import FlywheelRecall from "./FlywheelRecall";
import { bundle } from "../lib/data";

// claim 3：经验飞轮「越用越快」——收益数字（少跑几轮 / 省多少时间）与翻出的错题
// 都必须来自 bundle.flywheel。
describe("FlywheelRecall", () => {
  const fw = bundle.flywheel;
  const savedPct = Math.abs(Math.round(fw.time_saved_pct));

  it("收益条数字绑定到 bundle.flywheel", () => {
    const { container } = render(<FlywheelRecall />);
    const text = (container.textContent ?? "").replace(/\s+/g, " ");
    expect(text).toContain(`重跑少 ${fw.rounds_saved} 轮`);
    expect(text).toContain(`修复耗时省 ${savedPct}%`);
  });

  it("翻出的错题（症状 + 修复）来自 recalled", () => {
    render(<FlywheelRecall />);
    expect(screen.getByText(fw.recalled.repair)).toBeInTheDocument();
    expect(screen.getByText(fw.recalled.symptom)).toBeInTheDocument();
  });
});
