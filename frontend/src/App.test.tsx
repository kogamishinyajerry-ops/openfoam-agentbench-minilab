import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import App from "./App";
import { bundle } from "./lib/data";

// 这是前端侧的「数字锁」：与后端 test_replay_bundle 对应——确认看板 Hero 区
// 渲染出的关键数字确实来自 bundle（而非写死），且九个区块锚点都挂载成功。
describe("App", () => {
  it("整页渲染不崩溃，标语来自 bundle", () => {
    render(<App />);
    expect(screen.getByText(bundle.story.slogan)).toBeInTheDocument();
  });

  it("Hero 的关键数字绑定到 bundle.case（不是写死的）", () => {
    const { container } = render(<App />);
    const c = bundle.case;

    // 案例标题
    expect(screen.getAllByText(c.title).length).toBeGreaterThan(0);
    // 雷诺数
    expect(
      screen.getByText(`雷诺数 Re_H ≈ ${c.reynolds_h}（层流）`)
    ).toBeInTheDocument();
    // 管中央最快流速（两位小数）
    expect(
      screen.getByText(`管中央最快流速 ≈ ${c.u_max.toFixed(2)} m/s`)
    ).toBeInTheDocument();
    // 合格线（容差百分比，0 位小数）
    expect(
      screen.getByText(
        `合格线：误差 < ${(c.tolerances.qoi_l2 * 100).toFixed(0)}%`
      )
    ).toBeInTheDocument();

    // 模式徽章：replay → 回放演示
    if (bundle.mode === "replay") {
      expect(screen.getByText("回放演示")).toBeInTheDocument();
    }

    // 主标题确实存在且包含核心口号
    const h1 = container.querySelector("h1");
    expect(h1?.textContent).toContain("会算对");
  });

  it("九个区块锚点全部挂载（供右侧章节导航定位）", () => {
    const { container } = render(<App />);
    const ids = [
      "primer",
      "loop",
      "profile",
      "metrics",
      "experiment",
      "diagnosis",
      "memory",
      "recall",
      "evidence",
    ];
    for (const id of ids) {
      expect(container.querySelector(`#${id}`)).not.toBeNull();
    }
  });
});
