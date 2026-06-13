import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import ErrorBoundary from "./ErrorBoundary";

// 一个按需抛错的子组件，用来触发错误边界。
function Boom({ explode }: { explode: boolean }) {
  if (explode) throw new Error("kaboom");
  return <p>正常内容</p>;
}

describe("ErrorBoundary", () => {
  beforeEach(() => {
    // 抑制 React 把捕获到的错误打到控制台（用例里这是预期行为）。
    vi.spyOn(console, "error").mockImplementation(() => {});
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("子组件正常时原样透传内容", () => {
    render(
      <ErrorBoundary label="速度剖面">
        <Boom explode={false} />
      </ErrorBoundary>
    );
    expect(screen.getByText("正常内容")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("子组件抛错时降级成带区块名的友好兜底卡片", () => {
    render(
      <ErrorBoundary label="速度剖面">
        <Boom explode={true} />
      </ErrorBoundary>
    );
    const alert = screen.getByRole("alert");
    expect(alert).toBeInTheDocument();
    // 兜底卡片点名是哪个区块出错，并安抚其余内容不受影响。
    expect(alert).toHaveTextContent("速度剖面");
    expect(alert).toHaveTextContent("其余内容不受影响");
    // 原始的崩溃内容不应再出现。
    expect(screen.queryByText("正常内容")).not.toBeInTheDocument();
  });
});
