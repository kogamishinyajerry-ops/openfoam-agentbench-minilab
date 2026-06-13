"""把一次"诊断 + 修复成功"的失败，沉淀成一条可复用的经验记录。"""
from __future__ import annotations

from .. import config
from ..models import Diagnosis, ExperienceRecord, Fault, FailureMode

_SYMPTOM: dict[FailureMode, str] = {
    FailureMode.BC_MISMATCH:
        "程序成功跑完，但速度剖面偏离标准答案 —— 壁面出现了不该有的滑移速度",
    FailureMode.MESH_TOO_COARSE:
        "程序成功跑完，但剖面变成折线、中心峰值被削平 —— 网格太粗",
    FailureMode.RESIDUAL_NOT_CONVERGED:
        "日志显示跑完了，但残差仍高于阈值 —— 其实没算到收敛",
}

_REPAIR: dict[FailureMode, str] = {
    FailureMode.BC_MISMATCH:
        "恢复壁面 no-slip 边界条件，并检查压力梯度设置",
    FailureMode.MESH_TOO_COARSE:
        "在垂直管壁方向加密网格，把抛物线分辨清楚",
    FailureMode.RESIDUAL_NOT_CONVERGED:
        "减小时间步、增加迭代次数，直到残差收敛",
}


def mine_experience(
    diagnosis: Diagnosis,
    fault: Fault,
    qoi_before: float,
    qoi_after: float,
    created_round: int = 0,
    case_id: str = config.CASE_ID,
) -> ExperienceRecord:
    mode = diagnosis.failure_mode
    outcome = f"误差从 {qoi_before * 100:.1f}% 降到 {qoi_after * 100:.1f}%"
    # 当一次真正的工程失败被修复到容差以内，就把它升级为"以后必查"的回归用例
    promote = qoi_before >= config.QOI_L2_TOL and qoi_after < config.QOI_L2_TOL

    return ExperienceRecord(
        case_id=case_id,
        failure_mode=mode,
        symptom=_SYMPTOM.get(mode, "工程检查未通过"),
        repair=_REPAIR.get(mode, "；".join(diagnosis.suggested_repair[:1])),
        outcome=outcome,
        promote_to_regression=promote,
        created_round=created_round,
    )
