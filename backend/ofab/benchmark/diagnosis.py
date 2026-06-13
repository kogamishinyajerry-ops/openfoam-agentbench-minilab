"""失效模式诊断 —— 基于测得的剖面特征做规则判定，而不是查表贴标签。

判定顺序（每道门对应一种物理上可区分的"指纹"）：

  1. 残差高于阈值              -> RESIDUAL_NOT_CONVERGED（求解器设置问题）
  2. 壁面速度不为零（滑移）     -> BC_MISMATCH（边界条件问题）
  3. no-slip 正常但内部分辨不足 -> MESH_TOO_COARSE（网格太粗）
  4. 全部在容差以内            -> NONE（工程上合格）
"""
from __future__ import annotations

from ..models import Diagnosis, ExecutionStatus, FailureMode, RunResult
from .contracts import BenchmarkContract

# 失效模式 -> 一组可执行的修复建议（中文）
_REPAIRS: dict[FailureMode, list[str]] = {
    FailureMode.BC_MISMATCH: [
        "恢复壁面的 no-slip 边界条件：紧贴管壁的水流速度应为 0",
        "检查驱动水流的压力梯度 / 入口设置",
        "改完后重新跑一遍基准检验",
    ],
    FailureMode.MESH_TOO_COARSE: [
        "在垂直管壁方向加密网格（横跨管道用更多网格点）",
        "把中心线附近的曲线分辨得更细",
        "改完后重新跑一遍基准检验",
    ],
    FailureMode.RESIDUAL_NOT_CONVERGED: [
        "减小时间步长 / 库朗数，让计算更稳定",
        "增加迭代步数（让它多算一会儿再停）",
        "收紧收敛判据后重跑",
    ],
}

_STATUS_CN = {"success": "成功完成", "failed": "运行失败"}


def diagnose(run: RunResult, contract: BenchmarkContract | None = None) -> Diagnosis:
    contract = contract or BenchmarkContract.from_config()
    feats = run.features or {}
    wall_slip = feats.get("wall_slip", 0.0)
    curvature = feats.get("curvature_rmse", 0.0)
    peak_deficit = feats.get("peak_deficit", 0.0)
    residual = run.residual_final
    qoi = run.qoi_error

    status_cn = _STATUS_CN.get(run.execution_status.value, run.execution_status.value)
    evidence_base = [f"OpenFOAM 仿真运行结束，状态：{status_cn}"]

    residual_ok = residual < contract.residual_tol
    qoi_ok = qoi < contract.qoi_l2_tol

    # 4) 工程合格
    if residual_ok and qoi_ok:
        return Diagnosis(
            run_id=run.run_id,
            failure_mode=FailureMode.NONE,
            confidence=0.95,
            evidence=evidence_base
            + [
                f"关键物理量误差 {qoi * 100:.1f}%，在 {contract.qoi_l2_tol * 100:.0f}% 容差以内",
                f"最终残差 {residual:.1e}，低于阈值 {contract.residual_tol:.0e}",
            ],
            suggested_repair=[],
        )

    # 1) 残差门 -> 求解器设置
    if not residual_ok:
        over = residual / contract.residual_tol
        confidence = round(min(0.96, 0.65 + 0.15 * min(2.0, over)), 2)
        return Diagnosis(
            run_id=run.run_id,
            failure_mode=FailureMode.RESIDUAL_NOT_CONVERGED,
            confidence=confidence,
            evidence=evidence_base
            + [
                f"最终残差 {residual:.1e}，超过阈值 {contract.residual_tol:.0e}（约 {over:.0f} 倍）",
                f"结果不可信（误差 {qoi * 100:.1f}%）—— 计算其实还没收敛",
            ],
            suggested_repair=_REPAIRS[FailureMode.RESIDUAL_NOT_CONVERGED],
        )

    # 2) 壁面滑移门 -> 边界条件
    if wall_slip >= contract.wall_slip_tol:
        confidence = round(min(0.96, 0.55 + wall_slip), 2)
        return Diagnosis(
            run_id=run.run_id,
            failure_mode=FailureMode.BC_MISMATCH,
            confidence=confidence,
            evidence=evidence_base
            + [
                f"壁面速度不为零：滑移量达 u_max 的 {wall_slip * 100:.0f}%（no-slip 被破坏）",
                f"速度剖面误差 {qoi * 100:.1f}%，超过 {contract.qoi_l2_tol * 100:.0f}% 容差",
                "残差检查通过，但关键物理量检查没过",
            ],
            suggested_repair=_REPAIRS[FailureMode.BC_MISMATCH],
        )

    # 3) 缺特征时的低置信度兜底
    if not feats:
        return Diagnosis(
            run_id=run.run_id,
            failure_mode=FailureMode.MESH_TOO_COARSE,
            confidence=0.4,
            evidence=evidence_base
            + [
                "缺少剖面特征数据 —— 失效模式为低置信度默认判定",
                f"速度剖面误差 {qoi * 100:.1f}%，超过 {contract.qoi_l2_tol * 100:.0f}% 容差",
            ],
            suggested_repair=_REPAIRS[FailureMode.MESH_TOO_COARSE],
        )

    # 3) 否则 -> 网格分辨率
    confidence = round(min(0.92, 0.5 + 20.0 * curvature + 0.5 * peak_deficit), 2)
    return Diagnosis(
        run_id=run.run_id,
        failure_mode=FailureMode.MESH_TOO_COARSE,
        confidence=confidence,
        evidence=evidence_base
        + [
            f"壁面 no-slip 正常（滑移 {wall_slip * 100:.0f}%），但管道内部分辨不足",
            f"曲率偏差 {curvature:.3f}、中心峰值亏损 {peak_deficit * 100:.0f}% —— 剖面变成了折线",
            f"速度剖面误差 {qoi * 100:.1f}%，超过 {contract.qoi_l2_tol * 100:.0f}% 容差",
        ],
        suggested_repair=_REPAIRS[FailureMode.MESH_TOO_COARSE],
    )
