import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import SecondCaseCouette from "./SecondCaseCouette";
import { bundle, pct, FAILURE_SHORT } from "../lib/data";

// 第二个案例（Couette）：证明基准检验「举一反三」。锁住屏幕上的关键结论确实来自
// bundle.second_case——同一套基准检验在一个不同流动上抓出的假成功 + 诊断 + 修复。
describe("SecondCaseCouette", () => {
  const s = bundle.second_case;

  it("渲染剪切流案例标题与「代码一行没改」的主张", () => {
    const { container } = render(<SecondCaseCouette />);
    expect(screen.getByText(/换个流动照样管用/)).toBeInTheDocument();
    expect((container.textContent ?? "").replace(/\s+/g, " ")).toContain(
      s.generalizes_note.replace(/\s+/g, " ")
    );
  });

  it("抓到的假成功 + 诊断 + 修复结论绑定到 bundle.second_case", () => {
    const { container } = render(<SecondCaseCouette />);
    const text = container.textContent ?? "";
    // 同一套基准检验抓出的假成功：失败剖面误差
    expect(text).toContain(pct(s.profiles.failed.qoi_error));
    // 诊断失效模式（中文短名 + 代号）
    expect(text).toContain(FAILURE_SHORT[s.diagnosis.failure_mode]);
    expect(text).toContain(s.diagnosis.failure_mode);
    // 贴壁滑移百分比
    expect(text).toContain(`${s.wall_slip_pct}%`);
    // 修复后误差
    expect(text).toContain(pct(s.profiles.repaired.qoi_error));
  });

  it("数据层确认这是「同一套基准检验」判出的 BC_MISMATCH 假成功", () => {
    // 不是组件断言，是把 second_case 的数据契约钉死（与后端对应）
    expect(s.scorecard.false_success).toBe(true);
    expect(s.diagnosis.failure_mode).toBe("BC_MISMATCH");
    expect(s.repaired_pass).toBe(true);
    expect(s.not_applicable.fault).toBe("coarse_mesh");
  });
});
