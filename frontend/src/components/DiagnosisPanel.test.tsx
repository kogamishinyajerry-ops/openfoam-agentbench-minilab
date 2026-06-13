import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import DiagnosisPanel from "./DiagnosisPanel";
import { bundle, FAULT_LABELS, FAILURE_SHORT } from "../lib/data";
import type { Fault } from "../lib/types";

// 复刻组件挑选「该故障第一轮诊断」的逻辑，用来比对屏幕上显示的失效模式 / 置信度。
function diagFor(fault: Fault) {
  const runs = bundle.runs
    .filter((r) => r.workflow === "agent_plus_benchmark" && r.fault === fault)
    .sort((a, b) => a.round_index - b.round_index);
  return bundle.diagnoses.find((d) => d.run_id === runs[0].run_id)!;
}

// claim 2：基准检验不只说「错了」，还指出「哪一类错 + 多大把握」。诊断结论必须
// 绑定到 bundle.diagnoses，切换故障时随之更新。
describe("DiagnosisPanel", () => {
  it("三种故障的切换按钮都在", () => {
    render(<DiagnosisPanel />);
    for (const f of ["bc_mismatch", "coarse_mesh", "solver_setting_error"] as Fault[]) {
      expect(screen.getByRole("button", { name: FAULT_LABELS[f] })).toBeInTheDocument();
    }
  });

  it("默认显示 bc_mismatch 诊断：失效模式 + 置信度绑定到 bundle", () => {
    const { container } = render(<DiagnosisPanel />);
    const diag = diagFor("bc_mismatch");
    const text = container.textContent ?? "";
    expect(text).toContain(diag.failure_mode); // 原始代号，如 BC_MISMATCH
    expect(text).toContain(FAILURE_SHORT[diag.failure_mode]); // 中文短名
    expect(text).toContain(`${Math.round(diag.confidence * 100)}%`); // 置信度环
  });

  it("切到「网格太粗」后诊断更新为 MESH_TOO_COARSE", () => {
    const { container } = render(<DiagnosisPanel />);
    fireEvent.click(screen.getByRole("button", { name: FAULT_LABELS.coarse_mesh }));
    const diag = diagFor("coarse_mesh");
    expect(diag.failure_mode).toBe("MESH_TOO_COARSE"); // 锁住「粗网格 → 该失效模式」这条映射
    expect(container.textContent ?? "").toContain(diag.failure_mode);
  });
});
