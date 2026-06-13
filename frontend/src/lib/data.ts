import raw from "../data/demoRuns.json";
import type { Bundle, Fault } from "./types";

// 回放优先：内置的 JSON 让看板在没有后端时也能完整演示。
export const bundle = raw as unknown as Bundle;

// 故障的中文短名
export const FAULT_LABELS: Record<Fault, string> = {
  none: "无故障",
  bc_mismatch: "边界条件错误",
  coarse_mesh: "网格太粗",
  solver_setting_error: "求解器设置错误",
};

// 失效模式：醒目的中文短名（替代英文代号做主标题）
export const FAILURE_SHORT: Record<string, string> = {
  NONE: "工程合格",
  BC_MISMATCH: "边界条件错误",
  MESH_TOO_COARSE: "网格太粗",
  RESIDUAL_NOT_CONVERGED: "没算到收敛",
};

// 失效模式：一句话通俗解释
export const FAILURE_LABELS: Record<string, string> = {
  NONE: "结果可信，工程上合格",
  BC_MISMATCH: "贴着管壁的水流速度本该是 0，被设错了",
  MESH_TOO_COARSE: "管道里划的网格太粗，曲线没分辨清楚",
  RESIDUAL_NOT_CONVERGED: "还没算稳就停了，结果不能信",
};

// 奖励里的"下一步该关注什么"
const FOCUS_CN: Record<string, string> = {
  boundary_condition: "边界条件",
  qoi_alignment: "对齐标准答案",
  mesh_resolution: "网格分辨率",
  solver_settings: "求解器设置",
  convergence: "收敛性",
};
export const focusCn = (k: string): string => FOCUS_CN[k] ?? k;

// 奖励决策
const DECISION_CN: Record<string, string> = {
  repair_and_rerun: "修复并重跑",
  accept: "接受（合格）",
};
export const decisionCn = (k: string): string => DECISION_CN[k] ?? k;

export function fmtDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m} 分 ${s.toString().padStart(2, "0")} 秒`;
}

export function pct(x: number, digits = 1): string {
  return `${(x * 100).toFixed(digits)}%`;
}

// 可选：连到后端做一次真实运行（后端没开也不会报错）
export async function runLive(body: {
  fault: Fault;
  mode: "mock" | "replay" | "openfoam";
  repaired?: boolean;
}): Promise<unknown | null> {
  try {
    const res = await fetch("/api/demo/run", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ workflow: "agent_plus_benchmark", ...body }),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}
