import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle } from "lucide-react";

interface Props {
  /** 出错区块的中文名，显示在兜底卡片里，方便演示时一眼定位。 */
  label: string;
  children: ReactNode;
}

interface State {
  failed: boolean;
}

/**
 * 区块级错误边界。给每个看板区块单独包一层：某个区块抛错时，只有它降级成
 * 一张友好的提示卡片，其余区块照常显示——绝不让整页变成白屏（现场演示最怕这个）。
 * React 的错误边界必须是 class 组件（没有等价的 hook）。
 */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // 留一条控制台记录，便于排查；不向用户暴露堆栈。
    console.error(`[区块「${this.props.label}」渲染出错]`, error, info.componentStack);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <section
        role="alert"
        className="glass flex items-center gap-3 border-amber-400/25 bg-amber-400/[0.06] p-6"
      >
        <AlertTriangle className="shrink-0 text-amber-400" size={22} />
        <div>
          <p className="text-sm font-semibold text-amber-200">
            「{this.props.label}」区块暂时无法显示
          </p>
          <p className="mt-0.5 text-[13px] text-slate-400">
            其余内容不受影响，可继续向下浏览。
          </p>
        </div>
      </section>
    );
  }
}
