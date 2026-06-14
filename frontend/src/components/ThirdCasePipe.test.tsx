import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import ThirdCasePipe from "./ThirdCasePipe";
import { bundle, pct, FAILURE_SHORT } from "../lib/data";

// 第三个案例（圆管）：把「举一反三」推到「换流动 + 换故障」。锁住屏幕上的关键结论确实
// 来自 bundle.third_case——同一套基准检验在圆管上抓出的、由「网格太粗」导致的假成功 +
// 诊断（MESH_TOO_COARSE，不同于前两案的 BC_MISMATCH）+ 修复。
describe("ThirdCasePipe", () => {
  const s = bundle.third_case;

  it("渲染圆管案例标题与「换种错法」的主张", () => {
    const { container } = render(<ThirdCasePipe />);
    expect(screen.getByText(/再换一种流动/)).toBeInTheDocument();
    expect((container.textContent ?? "").replace(/\s+/g, " ")).toContain(
      s.generalizes_note.replace(/\s+/g, " ")
    );
  });

  it("抓到的假成功 + 诊断 + 修复结论绑定到 bundle.third_case", () => {
    const { container } = render(<ThirdCasePipe />);
    const text = container.textContent ?? "";
    // 同一套基准检验抓出的假成功：失败剖面误差
    expect(text).toContain(pct(s.profiles.failed.qoi_error));
    // 诊断失效模式（中文短名 + 代号）——这次是网格问题，不是边界条件
    expect(text).toContain(FAILURE_SHORT[s.diagnosis.failure_mode]);
    expect(text).toContain(s.diagnosis.failure_mode);
    // 中心峰值亏损百分比
    expect(text).toContain(`${s.peak_deficit_pct}%`);
    // 修复后误差
    expect(text).toContain(pct(s.profiles.repaired.qoi_error));
  });

  it("数据层确认这是「同一套基准检验」判出的 MESH_TOO_COARSE 假成功（不同于前两案的 BC）", () => {
    // 把 third_case 的数据契约钉死（与后端对应）：第三案主打的是另一种故障
    expect(s.scorecard.false_success).toBe(true);
    expect(s.diagnosis.failure_mode).toBe("MESH_TOO_COARSE");
    expect(s.diagnosis.failure_mode).not.toBe("BC_MISMATCH");
    expect(s.repaired_pass).toBe(true);
    expect(s.hero_fault).toBe("coarse_mesh");
    // 与 Couette 的「不适用」互为镜像：同一个故障，那边不适用、这边是主场
    expect(bundle.second_case.not_applicable.fault).toBe("coarse_mesh");
    expect(s.fault_fit_note.fault).toBe("coarse_mesh");
  });
});
