import { describe, it, expect } from "vitest";
import {
  pct,
  fmtDuration,
  focusCn,
  decisionCn,
  FAULT_LABELS,
  FAILURE_SHORT,
  FAILURE_LABELS,
} from "./data";

describe("pct", () => {
  it("把小数格式化成默认 1 位小数的百分比", () => {
    expect(pct(0.055)).toBe("5.5%");
    expect(pct(0.001)).toBe("0.1%");
    expect(pct(1)).toBe("100.0%");
  });

  it("尊重自定义小数位", () => {
    expect(pct(0.5, 0)).toBe("50%");
    expect(pct(0.12345, 2)).toBe("12.35%");
  });
});

describe("fmtDuration", () => {
  it("把秒数格式化成「M 分 SS 秒」并对秒补零", () => {
    expect(fmtDuration(167.3)).toBe("2 分 47 秒");
    expect(fmtDuration(250)).toBe("4 分 10 秒");
    expect(fmtDuration(125)).toBe("2 分 05 秒"); // 秒补零到两位
    expect(fmtDuration(0)).toBe("0 分 00 秒");
  });
});

describe("focusCn / decisionCn", () => {
  it("已知键翻译成中文", () => {
    expect(focusCn("boundary_condition")).toBe("边界条件");
    expect(focusCn("convergence")).toBe("收敛性");
    expect(decisionCn("repair_and_rerun")).toBe("修复并重跑");
    expect(decisionCn("accept")).toBe("接受（合格）");
  });

  it("未知键原样返回（不丢数据）", () => {
    expect(focusCn("brand_new_focus")).toBe("brand_new_focus");
    expect(decisionCn("brand_new_decision")).toBe("brand_new_decision");
  });
});

describe("label maps", () => {
  it("四种故障都有中文短名", () => {
    expect(FAULT_LABELS.none).toBe("无故障");
    expect(FAULT_LABELS.bc_mismatch).toBe("边界条件错误");
    expect(FAULT_LABELS.coarse_mesh).toBe("网格太粗");
    expect(FAULT_LABELS.solver_setting_error).toBe("求解器设置错误");
  });

  it("失效模式短名与一句话解释一一对应", () => {
    const modes = ["NONE", "BC_MISMATCH", "MESH_TOO_COARSE", "RESIDUAL_NOT_CONVERGED"];
    for (const m of modes) {
      expect(FAILURE_SHORT[m]).toBeTruthy();
      expect(FAILURE_LABELS[m]).toBeTruthy();
    }
    expect(FAILURE_SHORT.MESH_TOO_COARSE).toBe("网格太粗");
  });
});
