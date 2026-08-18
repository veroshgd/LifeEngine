# 复现指南

```bash
pip install -r requirements.txt
pytest                       # < 1 分钟，全绿即环境正常
```

只需要 **Python 3.10+ 与标准库**；`pytest` 仅用于自检。无第三方依赖。

---

## 三层复现

| 层 | 命令 | 耗时 | 证明什么 |
|---|---|---|---|
| **① 自检 / 回归** | `pytest` | < 1 分钟 | 冻结完整性、模型来源、机制层、确定性 |
| **② 小规模烟测** | 见下 | ~15 分钟 | 核心结果的**方向**能复现 |
| **③ 完整复现** | 见下 | ~4 小时 | 论文里的**具体数字** |

### ① 自检 / 回归

```bash
pytest
```

校验 `v2_frozen/` 与 `v3_frozen/` 的 SHA256；断言模型确实从 `v3_frozen`
导入且 `MODEL_VERSION == "v3"`、`COND_RECOVER_AT == 65.0`；
用 **AST 比对**确认 v2 → v3 的唯一可执行差异仍然只有那一个常量；
跑机制层 6 项自检；验规则 72 的窗口回归；验同种子两次运行逐位相同。

### ② 小规模烟测（方向，不是数字）

```bash
python novel_situation.py                        # 机制层 8 项自检
python final_confirm.py --check                  # 冻结校验闸
python final_confirm.py --seed0 20000 --n 200    # 主分析流水线（小 N）
python rule71_ablation.py --seeds 50 --workers 4 # TRAIT_DRIFT 因果方向
```

⚠ 小 N 下点估计会偏高（规则 34：比值估计量 N 小则虚高），**只看方向**。

### ③ 完整复现（论文数字）

```bash
# 最终确认（预注册，seeds 50000–51499，只跑一次）  ~1.5 小时
python final_confirm.py --final

# v3 参数稳健性  500 组 × 300 种子  ~45 分钟
python param_sweep.py --configs 500 --seeds 300 --out sweep_results_v3.csv
python sweep_report.py sweep_results_v3.csv

# v2→v3 同种子重验（实验 023 §7）  ~40 分钟
python v3_revalidate.py

# 规则 71 因果消融  ~20 分钟
python rule71_ablation.py --seeds 300
```

---

## 结果来自哪个模型 —— 这一栏必须看

| 产物 | 模型 | 地位 |
|---|---|---|
| `final_confirm_result.txt` | **v3_frozen** | ★预注册最终确认★（seeds 50000–51499，只跑一次） |
| `sweep_results_v3.csv` | **v3_frozen** | v3 参数稳健性（论文用这份） |
| `rule71_ablation` 输出 | **v3_frozen** | TRAIT_DRIFT 因果消融（探索性，方向预测已事前写死） |
| `sweep_results.csv` / `holdout.csv` | **v2** | ⚠ **development history**，表头无版本列。论文不得引用为 v3 的稳健性 |
| `final_confirm_result.VOID_bug.txt` | — | ⚠ **作废**：分块索引 bug 的空跑，保留作过程记录 |
| 实验 011–022 的全部数字 | **v2** | development history，**保留不覆盖** |
| 实验 026（novel-situation） | v3_frozen | **阴性结果**：四个 probe 全部退役 |

> Experiments 011–022 were conducted under model v2 and are retained as
> development history rather than overwritten by subsequent model correction.

---

## 种子账本（哪些段已烧掉）

| 段 | 用途 | 还能不能作 holdout |
|---|---|---|
| `0–1499` | 开发 | ✗ |
| `10000–11499` | 021 留出集（已多次查看） | ✗ |
| `20000–21499` | 022 预注册段 / 全部 group-blind 校准 | ✗ |
| `50000–51499` | **最终确认，已使用一次** | ✗ |
| `60000–61499` | 曾预留给 026 final —— **026 已封存，从未使用** | ✓ 干净 |

---

## 目录

```
v2_frozen/     v2 冻结快照（COND_RECOVER_AT = 30）+ SHA256SUMS.txt
v3_frozen/     v3 冻结快照（COND_RECOVER_AT = 65）+ SHA256SUMS.txt  ★论文模型★
tests/         pytest 自检
FINAL_PREREGISTRATION.md      预注册全文（含修订 A）
NOVEL_SITUATION_DESIGN.md     026 设计（已封存）
```

根目录的 `*.py` 是**实验脚本**，不是 pytest 测试 —— 它们跑起来是几十分钟的
模拟。`pytest.ini` 已限定 `testpaths = tests`，并排除两个 frozen 目录
（那里有同名模块，且不能改动）。

**已废弃**（保留作历史，不要用）：`sweep.py`、`food_sweep.py`。
**已退役**（026 的四个 probe 校准，保留作阴性结果证据）：
`novel_calibrate.py`、`novel_calibrate2.py`、`novel_calibrate3.py`。
