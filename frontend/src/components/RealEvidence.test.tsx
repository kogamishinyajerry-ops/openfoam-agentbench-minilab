import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import RealEvidence from "./RealEvidence";
import evidence from "../data/realEvidence.json";
import { pct, FAILURE_SHORT } from "../lib/data";

// claim 3 的 credibility 区:「不是演的 · 真实 OpenFOAM」。屏幕上的数字必须来自
// realEvidence.json(真实捕获的运行结果),不能写死——这份 JSON 和后端
// data/real_evidence.json 字节一致(后端 test 锁),这里锁前端渲染确实绑定到它。
describe("RealEvidence", () => {
  const ev = evidence as {
    container: string;
    correct: { qoi_error: number; u_peak_sampled: number; u_peak_analytical: number };
    faults: {
      fault: string;
      qoi_error: number;
      diagnosis: string;
      confidence: number;
      false_success_detected: boolean;
    }[];
  };

  it("渲染真实运行的标题与容器名(render 不抛错 = 直播安全网)", () => {
    const { container } = render(<RealEvidence />);
    const text = container.textContent ?? "";
    expect(text).toContain("真实 OpenFOAM");
    expect(text).toContain(ev.container); // 容器:ofab-openfoam
  });

  it("正确案例的 L2 误差与峰值流速绑定到 realEvidence.json", () => {
    const { container } = render(<RealEvidence />);
    const text = container.textContent ?? "";
    expect(text).toContain(pct(ev.correct.qoi_error)); // 几乎贴合解析解
    expect(text).toContain(String(ev.correct.u_peak_sampled)); // 0.14981
    expect(text).toContain(String(ev.correct.u_peak_analytical)); // 标准 0.15
  });

  it("三个故障的误差/诊断/置信度全部来自数据(三张卡都渲染)", () => {
    const { container } = render(<RealEvidence />);
    const text = container.textContent ?? "";
    expect(ev.faults).toHaveLength(3);
    for (const f of ev.faults) {
      expect(text).toContain(pct(f.qoi_error)); // 21.7% / 16.0% / 4.1%
      expect(text).toContain(FAILURE_SHORT[f.diagnosis] ?? f.diagnosis); // 诊断短名
      expect(text).toContain(`${Math.round(f.confidence * 100)}%`); // 置信度
    }
  });

  it("数据契约:正确案例合格 + 三个故障都是被抓到的假成功(模式各异)", () => {
    // 钉死这一节 credibility 主张的底层数据(对应后端 real_evidence 的回归锁)。
    expect(ev.correct.qoi_error).toBeLessThan(0.05); // 正确案例在容差内
    for (const f of ev.faults) expect(f.false_success_detected).toBe(true);
    const modes = ev.faults.map((f) => f.diagnosis).sort();
    expect(modes).toEqual(["BC_MISMATCH", "MESH_TOO_COARSE", "RESIDUAL_NOT_CONVERGED"]);
  });
});
