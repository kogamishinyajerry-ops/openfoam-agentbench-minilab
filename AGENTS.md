# AGENTS.md — 在 OpenFOAM-AgentBench MiniLab 中开发

写给要扩展本仓库的 AI 智能体（或工程师）的上手指南。改动请保持小、外科、可复现——本项目的全部意义，就是一条值得信任的闭环。

一句话先把场景说清楚：这里的「仿真」就是用电脑「预演」真实世界里的水流 / 气流；而「能跑起来」并不等于「算对了」——就像「交了卷」并不等于「答对了」。本仓库要做的，就是给智能体配一个「判卷老师」（基准检验 Benchmark），拿标准答案打分挑错，并把抓到的错题记进「错题本」。

## 心智模型（Mental model）

一次运行（run）会穿过**一条契约 + 四层流水**：

```
runner (mock | replay | openfoam)  →  RunResult
        → benchmark.scorecard       →  Scorecard   (false-success detection)
        → benchmark.diagnosis       →  Diagnosis   (failure mode from features)
        → benchmark.reward          →  Reward      (the repair fuel)
        → memory.case_miner/store   →  ExperienceRecord
```

`backend/ofab/models.py` 是**唯一契约**——所有跨模块边界、或以 JSON 落盘、或被 React 看板逐字消费的数据形状都定义在这里。不要 fork 它，只能扩展它。

`backend/ofab/config.py` 是**数值的唯一真相源**（物理参数 + 容差）。在这里改一个数字，整条流水线连同重新生成的回放（replay）数据就会保持一致。绝不要在别处硬编码 QoI / 误差常量——一律从 `physics.py` 算出来。

> 本案例 CANON（数字以此为准，勿另造）：平板通道层流 `channel_poiseuille`，雷诺数 Re_H ≈ 20（层流）。入口流速 U0 = 0.10 m/s；中心峰值 u_max = 0.150 m/s = 1.5·U0；通道高 H = 0.01 m；通道长 L = 0.12 m = 12H；运动黏度 ν = 5e-5 m²/s。
> 解析解（即「标准答案」，数学上的精确解）：u(y) = u_max · 4 (y/H)(1 − y/H)。
> 合格线 / 容差：QoI L2 误差 < 5%；残差 residual < 1e-4；壁面滑移 wall_slip < 5%。

## 黄金法则（Golden rules）

1. **数字是算出来的，不是编的（Numbers are derived, not invented）。** 速度剖面来自 `physics.py`；QoI / L2 误差是从那些数组里**量出来**的。如果你需要某个特定的「头条数字」，去调一个*扰动幅度（perturbation magnitude）*，而不是直接改误差本身。
2. **诊断靠特征，不靠标签（Diagnosis classifies from features，not labels）。** 一个故障的剖面*形状*（wall_slip / peak_deficit / curvature_rmse / residual）必须把它的失效模式编码进去，这样 `diagnosis.py` 才能把它还原出来。要拿一次真实运行来验证。
3. **回放是主干（Replay is the spine）。** 一切都必须在**没装 OpenFOAM** 的情况下能跑。真实运行器只是一个可选、非破坏性的加分项，跑不起来时回退到 mock。
4. **前端可见性绝不依赖 JS 动画跑完（Frontend visibility never depends on JS animation completing）。** 入场显现用的是 CSS（`.reveal` / `.reveal-pop`）；内容在静止态始终是 opacity-1。Framer Motion 只用于交互式 / 首屏（above-the-fold）的动效。

## 重新生成全部产物（Regenerate everything）

```bash
./.venv/bin/ofab demo seed                                   # bundle + frontend data
./.venv/bin/ofab experiment experiments/pilot_001/protocol.yaml   # artifacts + report
```

任何会影响数字的后端改动之后，都要重新 seed，好让 `frontend/src/data/demoRuns.json` 和 `data/real_evidence.json`（如果你重跑过 `ofab demo real-evidence`）保持同步。

## 如何加一个新故障（How to add a new fault）

1. `models.py` —— 在 `Fault` 枚举里加上它。
2. `physics.py` —— 加一个 `_<fault>_profile(...)`，让它的形状把失效模式编码进去；在 `failed_profile()` 里注册它，并在 `residual_for()` 里设好它的残差。
3. `diagnosis.py` —— 确保有一道 gate 把它的特征映射到某个 `FailureMode`（如果是新模式，就把它加进 `models.FailureMode` 并补上修复说明文本）。
4. `benchmarks/failure_injections/<fault>.yaml` —— 把这次注入记录下来。
5. `runner/openfoam_runner.py` —— 在 `_fault_params()` / `generate_case()` 里实现真实注入，并**用一次 live run 验证**它确实是一个真实的「假成功 false success」（即退出码 0、但工程结果是错的）。
6. `demo/replay_data.py` —— 把它加进 benchmark-workflow 的「广度（breadth）」循环里。

> 三个内置故障 → 失效模式 → 指纹（feature 指纹），以及真实运行器要拧的「旋钮」：
> - `bc_mismatch` → `BC_MISMATCH`：壁面速度不为零（滑移达 u_max 的 28%，no-slip 被破坏）。真实旋钮：壁面 → moving wall `fixedValue (0.05 0 0)`。
> - `coarse_mesh` → `MESH_TOO_COARSE`：剖面变折线 / 峰值被削平。真实旋钮：垂直管壁方向网格 40 → 4。
> - `solver_setting_error` → `RESIDUAL_NOT_CONVERGED`：残差高于容差。真实旋钮：`endTime` 6.0 → 0.05。

## 如何加一个新案例（How to add a new case）

把 `config.py`（按案例的参数）和 `physics.py`（它的参考解 + 特征）泛化一下。只要 benchmark 层拿到的是「剖面 + 参考解 + 特征」，它就是与案例无关（case-agnostic）的。再加一个 `benchmarks/contracts/<case>.yaml`。

## 审查纪律（Review discipline）

涉及安全 / 契约敏感的改动（run / benchmark / diagnosis 这条路径、真实 OpenFOAM 运行器、任何 JSON schema）值得请第二双眼睛看。宣称「做完」之前，跑 `./.venv/bin/python -m pytest backend`（约 200 个用例，锁住物理不变量 / 假成功检测 / 诊断门 / 奖励公式 / 全部头条数字），把整条 CLI 链（`run → benchmark → diagnose → reward`）重跑一遍，并跑 `npm run build`。「做完」的意思是这条闭环能**复现**，而不是「我觉得它能跑」。

> 改了 `physics.py` / `config.py` 里任何会影响数字的东西后：先 `ofab demo seed` 重新生成回放包，再 `pytest backend`——`test_replay_bundle.py` 是头条数字的回归锁，会立刻告诉你哪个数字漂了、以及前端 `demoRuns.json` 是否还和后端同步。

> 参考数字（与 CANON 一致，便于自查复现是否对齐）：
> **回放对照实验**——只有 AI（agent_only）vs AI+基准检验（agent_plus_benchmark）：
> - 重跑次数 rerun_count：5 → 2（−60%）
> - 修对耗时 time_to_pass：12m 27s → 4m 10s（−67%）
> - 最终 QoI L2 误差：8.7% → 2.1%
> - 抓到的假成功 false_success_detected：0 → 3
> - 沉淀的经验 experience_records：0 → 3（这就是「错题本」里新增的条目）
> - 升级为回归用例 regression_cases_promoted：3（agent+benchmark 侧）
> - 自动修复成功率 auto_repair_success_rate：0% → 100%
>
> 主线故障 `bc_mismatch` 的回放修复路径：18.4% → 5.8% → 2.1%；奖励 reward 总分 −0.37 → +0.71，工程分 engineering_reward −0.67 → +0.63，决策 decision：`repair_and_rerun` → `accept`，诊断置信度 83%。其余两故障回放修复：`coarse_mesh` 5.5% → 2.1%；`solver_setting_error` 14.5% → 2.1%。
>
> **真实 OpenFOAM**（live icoFoam，容器 `ofab-openfoam`）：
> - 正确案例：0.1% L2（峰值流速 u_peak 0.1498 vs 解析 0.1500），残差 6e-11，合格 pass。
> - `bc_mismatch`：21.7%，已收敛，假成功 → `BC_MISMATCH`（88%）。
> - `coarse_mesh`：16.0%，已收敛，假成功 → `MESH_TOO_COARSE`（79%）。
> - `solver_setting_error`：4.1%，残差 4.4e-3，假成功 → `RESIDUAL_NOT_CONVERGED`（95%）。
