// Vitest 全局测试准备：引入 jest-dom 的自定义断言（toBeInTheDocument 等），
// 每个用例后清理已挂载的 React 组件，并补齐 jsdom 默认缺失的几个浏览器 API，
// 让用到它们的组件（SectionNav→IntersectionObserver、recharts→ResizeObserver、
// framer-motion→matchMedia）能在测试环境里正常渲染。
import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

afterEach(() => {
  cleanup();
});

// matchMedia：framer-motion 的 reduced-motion 探测、SectionNav 的跳转都会用到。
if (!window.matchMedia) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

// IntersectionObserver：SectionNav 用它追踪当前可见区块。
class MockIntersectionObserver {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
  takeRecords = vi.fn(() => []);
  root = null;
  rootMargin = "";
  thresholds = [];
}
vi.stubGlobal("IntersectionObserver", MockIntersectionObserver);

// ResizeObserver：recharts 的 ResponsiveContainer 用它测容器尺寸。
class MockResizeObserver {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
}
vi.stubGlobal("ResizeObserver", MockResizeObserver);

// recharts 在 jsdom 里量不到容器尺寸（ResizeObserver 是桩，宽高恒为 0），会刷一条
// "width(0) and height(0)" 警告——纯属测试环境产物，过滤掉以保持输出干净；
// 其余真实告警照常透传。
const _warn = console.warn.bind(console);
console.warn = (...args: unknown[]) => {
  if (typeof args[0] === "string" && args[0].includes("width(0) and height(0)")) {
    return;
  }
  _warn(...(args as []));
};
