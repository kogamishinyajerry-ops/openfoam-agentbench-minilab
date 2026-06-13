# channel_poiseuille — 算例模板

这道「主角题」对应的真实 OpenFOAM 算例是**用程序动态生成的**（这样几何、网格分辨率、边界条件都能按不同故障逐项扰动），而不是以静态字典文件的形式存盘。详见
[`backend/ofab/runner/openfoam_runner.py`](../../../backend/ofab/runner/openfoam_runner.py)
里的 `generate_case()`。

> 一句话背景：仿真 = 用电脑「预演」真实世界的水流 / 气流。这道题就是让水在一条扁扁的窄缝里流，看程序算出来的流速曲线跟「标准答案」对不对得上。

## 几何 & 物理参数（来自 `backend/ofab/config.py`）

| 参数 | 数值 |
|---|---|
| 通道高 H | 0.01 m |
| 通道长 L | 0.12 m（= 12 H） |
| 入口速度 U0 | 0.10 m/s（均匀） |
| 运动黏度 ν | 5e-5 m²/s |
| 雷诺数（Re_H） | ≈ 20（层流） |
| 解析峰值 u_max | 1.5 · U0 = 0.15 m/s |

二维平板通道：上下壁面无滑移（no-slip）、入口均匀来流、出口固定压力、前后面为
`empty`。用 `icoFoam` 求解（瞬态、层流），一直算到出口处的速度剖面充分发展，
再用 `sets` function object 沿垂直壁面方向采样，跟解析解
`u(y) = u_max · 4 (y/H)(1 − y/H)` 对照。

> 这条解析解就是这道题的「标准答案」——数学上能精确写出来的精确答案。能跑 ≠ 算对（交卷 ≠ 答对），所以才要拿它打分挑错。

## 故障注入（真实运行器）

| 故障 | 改动的旋钮 |
|---|---|
| `bc_mismatch` | 壁面 → 移动壁面 moving wall `fixedValue (0.05 0 0)`（破坏了 no-slip） |
| `coarse_mesh` | 垂直壁面方向网格数 40 → 4 |
| `solver_setting_error` | `endTime` 6.0 → 0.05（没收敛就提前停了） |

> 「故障注入」就是故意给算例埋雷，看「判卷老师」（基准检验 Benchmark）能不能拿标准答案把这些错揪出来。比如壁面本该贴着不动（速度为零），`bc_mismatch` 偏让它以 0.05 m/s 滑着走——结果看着也能跑出个数，但其实是「假成功」（退出码 0，可工程结果是错的）。

生成并查看一个真实算例目录：

```bash
OFAB_OPENFOAM_CONTAINER=ofab-openfoam \
  ./.venv/bin/ofab run --fault bc_mismatch --mode openfoam
# 生成的算例会留在 runs/ofab_<run_id>_out/ 目录下
```
