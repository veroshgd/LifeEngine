# 028 预注册 · 修订 01

**创建于形状彩排之后、打开 final 种子块 70000–71499 之前。**

> Amendment created after the shape rehearsal (seeds 10000–10299, n=286)
> but before inspection of final seeds 70000–71499. Rehearsal breadth
> contrasts had been observed. The clause below concerns the **sample size
> at which the validity gates are defined**; it is derived from the sampling
> standard error of the gate statistics, **not** from the observed rehearsal
> G value. No gate threshold, arm definition, frozen transform, endpoint,
> SESOI, or inference method is changed.

⚠ 原 `NOVEL_TASK028_PREREGISTRATION.md` **一字不改**。
本文件是**透明的 pre-final amendment**，不假装是原预注册的一部分。

---

## A. 新增：validity gates 的样本量限定

### 条文

> **Validity gates 以 N = 1500 的 confirmatory run 为准。
> 小于该规模的彩排只验证代码路径、指标口径与量级；
> 其 gate 结果【不构成】对 frozen transform 的判定。**

### 依据（与观察到的 G 无关）

gate 统计量 `|μ_j − μ_A| / SD_A` 本身带抽样噪声。
两个均值算在**同一批 agent** 上，共 `M = 2 × n_pairs` 个 agent-instance，
所以配对差均值的抽样 SE 约为

```
SE( |Δμ| / SD_A )  ≈  √(2 / M)
```

| 阶段 | n_pairs | M | SE | 门槛 10% 相当于 |
|---|---|---|---|---|
| 形状彩排 | 286 | 572 | ≈ 5.9% | **< 2 SE** |
| FINAL | ≈ 1400 | ≈ 2800 | ≈ 2.7% | **≈ 3.7 SE** |

**在彩排规模上，10% 的门槛不到 2 个 SE —— 它基本是在检验噪声。**

**独立的经验锚点**：`transport028.py` 在 **n=2944**（seeds 10000–11499）上
用同一个 frozen transform 测得最大 `|Δμ|/SD_A = 3.2%`、`|ΔSD|/SD_A = 2.4%`，
与 final 规模的预期一致。而形状彩排（n=286）测得 Bp 的 `|Δμ|/SD_A = 10.4%`
——**两者的差别来自样本量，不是 transform 的 transport error**。

### 不改的东西

`support ≤ 2%`、`boundary ≤ 2%`、`|Δμ|,|ΔSD| ≤ 10% × SD_A`
这四个阈值**一律不动**。它们是在看到 transport 实测（n=2944）之后、
针对 **N=1500 的 confirmatory run** 冻结的。

### 分层失败处理不变

C± 任一失败 → primary G invalid；B± 失败 → 仅 secondary invalid；
A 无 mapping transport gate。失败措辞仍为：

> Frozen coupling normalization did not transport adequately to the
> confirmatory population; breadth contrast is not cleanly interpretable
> under the preregistered equal-budget assumption.

---

## B. runner 的对应改动（只影响打印，不影响判定逻辑）

`final_028.py` 在 `N < 1500` 时打印一行 **NON-BINDING** 提示，
说明该次 gate 结果不构成对 frozen transform 的判定。
**final 运行（N=1500）不受影响，gate 照常具约束力。**

---

## C. 记录：形状彩排的 gate 实测（seeds 10000–10299，n=286）

```
臂       越界     边界质量   |Δμ|/SD_A  |ΔSD|/SD_A  support  budget
Bp      0.00%    0.00%      10.4%       6.4%        ✓        ✗
Bm      0.00%    0.00%       7.3%       4.1%        ✓        ✓
Cp      0.17%    0.17%       5.1%       3.5%        ✓        ✓
Cm      0.00%    0.00%       2.0%       2.0%        ✓        ✓

primary (C±) ✓ valid      secondary (B±) ✗ invalid
```

support gate 全部通过且余量巨大（最坏 0.17%，门槛 2%）。
唯一失败的是 Bp 的 budget gate，超门槛 **0.4 个百分点**，
按 §A 属于**彩排规模下的噪声**，**不构成对 frozen transform 的判定**。

> ### ★ 规则 82：判据必须绑定它被设计时所针对的样本量 ★
> 一个为 N=1500 设计的阈值，放到 n=286 上会变成"检验噪声"。
> 预注册写阈值时，**必须同时写明它在什么规模下有效**，
> 否则小样本彩排会给出无意义的红灯（或更糟：无意义的绿灯）。
