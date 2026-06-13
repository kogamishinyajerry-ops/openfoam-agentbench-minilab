# OpenFOAM-AgentBench 迷你实验室（MiniLab）

**让 AI 从「会跑仿真」变成「会算对、还越用越聪明」——用「基准检验反馈」(Benchmark Feedback) 把一个 CFD 智能体变成会自我改进的闭环。**

这是一个小而完整、可以直接拿去路演的研究 Demo。它想说清一件事:给「AI 自动做 CFD 仿真」的工作流加上一道**基准检验**之后,AI 不再只是把 OpenFOAM「跑完」,而是**知道自己哪里算错了、该怎么改、改完到底有没有变好,并且把每一次失败都沉淀成可复用的经验。**

它是一个**刻意做小的 1–2 天实验**,*不是*工业级 CFD 平台。它只把一个观点讲到最尖锐:

> **OpenFOAM 成功跑完 ≠ 工程结果是对的。**
> 就像「交了卷 ≠ 答对了」。基准检验能抓住这个差别,驱动一次自动修复,并把每一次失败,变成下一次自动避开它的能力。

---

## 一分钟看懂(不懂技术也能读)

- **仿真** = 用电脑「预演」真实世界里的水流、气流——造汽车前先在电脑里吹风、修水管前先在电脑里走一遍水,又快又省钱。现在的 AI 已经能自己写、自己跑这些仿真。
- **卡在哪** = 仿真程序「跑完了、没报错」,看起来很成功——可结果可能和正确答案差着十万八千里。这种**「假成功」**要是被当成对的,工程上会出大问题。
- **我们怎么做** = 给 AI 配一个**「判卷老师」(基准检验)**:它拿着标准答案,发现错误、说清为什么错、给出怎么改;AI 照着改、再验证,并把每次失败记成**「错题本」**。于是 AI 不只是「会跑」,而是「会变好、越用越聪明」。

| 术语 | 一句话解释 |
|---|---|
| 解析解 / 标准答案 | 这个简单案例有数学上的精确答案,可以直接对照打分 |
| QoI(关键物理量) | 这里指「速度剖面」与标准答案的相对误差,越小越准 |
| 残差 residual | 衡量「算稳了没」;只看它不够,它过了也可能算错 |
| 假成功 false success | 退出码是 0(程序跑完了),工程结果却是错的 |
| 失效模式 failure mode | 错的「类型」,比如边界条件错 / 网格太粗 / 没算到收敛 |

---

## 它要证明的三件事

1. **AI 智能体能自动生成 / 修改一个 OpenFOAM 算例**(主线案例是一个有精确解析解的二维平板通道层流)。
2. **基准检验能抓住「跑得好好的、工程上却是错的」假成功**——只看退出码的自动化会把它们悄悄放过去。
3. **基准检验的反馈能驱动自动修复 + 形成数据飞轮**——每一次失败都被诊断、修复、验证,并存成一条可复用的经验;**同一故障复发时,直接召回这条经验、套用已知修复,修得更快**(少一轮重跑、耗时省 33%)。

## 反馈飞轮

```
任务 → AI 智能体 → OpenFOAM → 基准检验 → 诊断 → 修复 → 经验记忆
任务   Agent      跑仿真      Benchmark   Diagnose Repair  Memory
                               │            │        │       │
                          QoI / 残差        │     打补丁、重跑  │
                          假成功检测     失效模式            一条经验记录
                                          + 置信度          + 回归用例守护
```

普通 AI 只做前三步(跑完就算完)。我们多加了后面四步——**检验 → 诊断 → 修复 → 记经验**,让它转成一个会自我改进的飞轮。

---

## 主线案例 —— 二维平板通道层流

一个层流通道流动(雷诺数 Re_H ≈ 20),它充分发展后的速度剖面正好是一条精确的抛物线
`u(y) = u_max · 4 (y/H)(1 − y/H)`。它是绝佳的教学案例:正确答案是一条任何人都看得懂的对称「小山包」曲线,而三种经典错误,各自把它扭成一种**物理上截然不同**的样子。

| 注入的故障 | 破坏了什么 | 基准检验的「指纹」 | 诊断结论 |
|---|---|---|---|
| `bc_mismatch`(边界条件错误) | no-slip 壁面被破坏(滑移 / 壁面在动) | 壁面速度不为零 | **BC_MISMATCH** |
| `coarse_mesh`(网格太粗) | 垂直管壁方向网格太粗 | 剖面变折线、峰值被削平 | **MESH_TOO_COARSE** |
| `solver_setting_error`(求解器设置错误) | 没算到收敛就停了 | 残差高于容差 | **RESIDUAL_NOT_CONVERGED** |

Demo 里的每一个数字都是**算出来的**,绝不写死:解析抛物线和每条故障剖面都由 NumPy 生成,所有 QoI / L2 误差都从这些数组里量出来。见
[`backend/ofab/physics.py`](backend/ofab/physics.py)。

## 对照实验 —— 两种工作流,正面 PK

* **只有 AI(Agent-only)** —— 只能看到退出码和日志。它只能盲目重跑,最后「接受」了一个其实还差 8.7% 的结果,自己却毫不知情。
* **AI + 基准检验(Agent + Benchmark)** —— 能看到 QoI、残差、诊断结论和一个奖励信号。它在指点下定向修复,最终进入合格线。

| 指标 | 只有 AI | AI + 基准检验 | 变化 |
|---|---|---|---|
| 重跑次数 | 5 | 2 | **−60%** |
| 修对耗时 | 12m 27s | 4m 10s | **−67%** |
| 最终 QoI L2 误差 | 8.7% | **2.1%** | 进入合格线 |
| 抓到的假成功 | 0 | **3** | 每种故障一次 |
| 沉淀的经验 | 0 | **3** | 数据飞轮 |
| 自动修复成功率 | 0% | **100%** | |

主线故障(`bc_mismatch`)在指点修复下走过 **18.4% → 5.8% → 2.1%**;奖励信号从 **−0.37 翻正到 +0.71**。

## 在真实 OpenFOAM 上验证过(不是假的)

上面的回放(replay)Demo 是「合成但有物理依据」的。同一套基准检验闭环,也会跑在一次**真实的 `icoFoam` 求解**上,证明它不是个壳子:

| 真实运行 | 与解析解的 L2 误差 | 残差 | 基准检验判定 |
|---|---|---|---|
| 正确案例 | **0.1%**(峰值流速 0.1498 vs 0.1500) | 6e-11 | 合格 pass |
| `bc_mismatch` | 21.7% | 已收敛 | 假成功 → **BC_MISMATCH**(88%) |
| `coarse_mesh` | 16.0% | 已收敛 | 假成功 → **MESH_TOO_COARSE**(79%) |
| `solver_setting_error` | 4.1% | 4.4e-3 | 假成功 → **RESIDUAL_NOT_CONVERGED**(95%) |

这些是**真实求解**的量级(来自 `data/real_evidence.json`);它们和上面回放的确定性数字不同,因为这里每个故障都是一次真实、独立收敛的 OpenFOAM 运行,而不是合成出来的剖面。复现命令:
`ofab demo real-evidence`(需要一个在跑的 OpenFOAM 容器,见下文)。

---

## 快速上手

### 后端(CLI + API)—— **不装 OpenFOAM 也能跑**

```bash
python3 -m venv .venv
./.venv/bin/pip install -e backend

# 1) 生成回放数据包 + 示例产物 + 前端数据
./.venv/bin/ofab demo seed

# 2) 跑完整的试点实验 -> 全部 JSON 产物 + report.md
./.venv/bin/ofab experiment experiments/pilot_001/protocol.yaml

# 3) 单步走一遍闭环
./.venv/bin/ofab run --fault bc_mismatch --mode replay
./.venv/bin/ofab benchmark runs/latest     # 评分卡 + 假成功标记
./.venv/bin/ofab diagnose  runs/latest      # 失效模式 + 修复建议
./.venv/bin/ofab reward    runs/latest      # 驱动修复的「燃料」
./.venv/bin/ofab recall    --fault bc_mismatch   # 复发时:召回错题本里的已知修复

# 启动看板要读的 API(ofab 已 pip 安装,从仓库根目录运行)
./.venv/bin/uvicorn ofab.api:app --reload --port 8000
```

### 运行测试(pytest)

后端带一套约 200 个用例的测试,把这套闭环的每一个不变量都锁住了:解析解的正确性、
「假成功」检测、失效模式诊断的门优先级、奖励公式,以及全部头条数字(防止任何改动悄悄
让 Demo 的数据失真)——相当于把这个项目「检验能抓住错误」的主张,反过来用在它自己身上。

```bash
./.venv/bin/pip install -e "backend[test]"   # 装上 pytest + httpx
./.venv/bin/python -m pytest backend          # 约 200 个用例,全绿
```

### 前端(看板 dashboard)

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

看板完全靠内置的 `src/data/demoRuns.json`(回放模式)运行,所以路演时**不需要后端**。如果 API 开着,实时「运行」接口会被代理,可以按需触发真实运行。

### 可选:一次真实的 OpenFOAM 运行

任何在跑的、带 `blockMesh` + `icoFoam` 的 OpenFOAM 容器都行(自动探测,或用 `OFAB_OPENFOAM_CONTAINER` 指定):

```bash
docker run -dit --name ofab-openfoam opencfd/openfoam-default:2312 bash
OFAB_OPENFOAM_CONTAINER=ofab-openfoam ./.venv/bin/ofab run --fault bc_mismatch --mode openfoam
OFAB_OPENFOAM_CONTAINER=ofab-openfoam ./.venv/bin/ofab demo real-evidence
```

这个真实运行器是**非破坏性**的:它把一份全新的算例拷进容器的 `/tmp` 里跑,解析出垂直管壁方向的速度剖面,然后清理干净。

---

## 这些指标各自是什么意思

**研究效率** —— *这是不是一条更快搭出「可信 CFD 结果」的路?*
`time_to_pass_s`(修对耗时)、`rerun_count`(重跑次数)、`auto_repair_success_rate`(自动修复成功率)。

**工程反馈** —— *它到底算对了没有?*
`qoi_error`(速度剖面相对解析解的 L2 误差)、`residual_check`(残差检查),还有最关键的
`false_success_detected`(假成功检测)——退出码是 0、工程上却错了的那一类运行。残差通过只是**及格线**;**对齐标准答案(QoI)才是「可信」的真正门槛。**

**数据飞轮** —— *它会不会越用越好?*
`experience_records`(沉淀的经验)、`regression_cases_promoted`(升级为回归用例的数量)——两者都在
`WorkflowMetrics` 里按工作流分别给出。

## 仓库结构

```
backend/ofab/
  config.py            # 数值的唯一真相源(物理参数 + 容差)
  physics.py           # 解析抛物线 + 故障合成 + QoI / 特征
  models.py            # Pydantic 数据契约(跨模块 + 前端共用)
  benchmark/           # qoi · 评分卡 · 诊断 · 奖励 · 契约 · 指标
  runner/              # mock · replay · openfoam(真实 Docker)三种运行器
  memory/              # 经验存储 + 案例挖掘(飞轮)
  demo/                # 场景构建 + 实验播种 + 真实证据
  cli.py  api.py       # Typer CLI + FastAPI 接口
frontend/              # Vite + React + TS + Tailwind + Recharts + Framer Motion
benchmarks/            # 契约 YAML · 解析参考 CSV · 故障注入
openfoam_cases/        # 算例模板说明
experiments/pilot_001/ # protocol.yaml + 生成的 results/ + report.md
docs/                  # 演示分镜脚本(3–4 分钟视频)
```

## 刻意不做的部分

不做完整 CFD 案例库,不做多智能体编排,不做 HPC,不做复杂三维几何,不做工业级验证。这是一个**最小可用的闭环**——正因为它跑通了,才值得去搭后面那一大套。

## 这件事的意义

> AI 智能体在 CFD 里的价值,不只是「会跑仿真」——而是在基准检验反馈的驱动下,**每一次失败,都变成下一次更高效、更可信的能力。**

3–4 分钟的讲解走查见 [`docs/demo_storyboard.md`](docs/demo_storyboard.md);
自动生成的试点报告见 [`experiments/pilot_001/report.md`](experiments/pilot_001/report.md)。
