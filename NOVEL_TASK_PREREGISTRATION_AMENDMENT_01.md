# 027 预注册 · 修订 01

**创建于彩排之后、查看 final 种子块 60000–61499 之前。**

> Amendment created after rehearsal but before inspection of final seeds
> 60000–61499. Rehearsal rich/poor contrasts had been observed. The SESOI
> was determined from the pooled latency scale and task-native unit, not
> from the between-history rehearsal contrast. The original statistical H2
> criterion is retained; this amendment adds a separate practical-
> significance interpretation using a ±1 trial equivalence region.

⚠ **原 `NOVEL_TASK_PREREGISTRATION.md` 一字不改**（它写明是一次性文件）。
本文件是**透明的 pre-final amendment**，**不假装是原预注册的一部分**。

---

## A. 新增：SESOI = 1.0 trial，作为 ±1 practical-equivalence region

### 为什么需要

原预注册 §4 只写了「95% CI 不含 0」。在 N=1500 下：

```
pooled restricted latency（量程 0–36）：均值 18.04   SD 8.15
配对差 SE ≈ 0.30  →  纯精度上 |Δ| ≈ 0.58 trial 就会"显著"
```

**0.58 trial 在 0–36 的量程上只有 1.6%。** 只看 CI 不含 0，
可能把一个统计显著但功能上毫无意义的差异宣布成 027 成功。

### SESOI = 1.0 trial 的依据（**与 rich/poor 对比无关**）

- **1 trial 是 latency 的最小自然单位**（任务自身的尺度）
- 相对 pooled mean 18.04 ≈ **5.5%**
- 相对 pooled SD 8.15 ≈ **0.12 SD**
- 明显高于 N=1500 下约 0.58 trial 的纯精度检出能力

### 三值判读（★取代原来的二值判读★）

| 情况 | 判读 |
|---|---|
| 95% CI **包含 0** | **H2 不获支持** |
| CI **排除 0**，但仍与 **[−1, +1]** 重叠 | **统计上存在 history effect，但功能意义未建立** |
| CI **整体 > +1** 或 **整体 < −1** | **functionally meaningful reversal-transfer established** |

⚠ **不采用**"CI 不含 0 且点估计 \|Δ\| ≥ 1.0"这种写法。
反例：`Δ = 1.05, CI = [0.20, 1.90]` —— 点估计过线，但 CI 允许真值只有
0.2 trial，**没有把握说它超过功能门槛**。用等价区间才干净。

**原统计判据（CI 不含 0）保留**，本修订只是**另加**一层功能显著性解释。

---

## B. 控制三 / 控制四的定性更正

### 撤回原来的说法

> ~~控制四：若主效应仍在 → 说明还有别的历史载体~~ ★撤回★

**这在当前任务下是构造上不可能发生的。** 历史进入任务的唯一路径是

```
history → curiosity / caution → novelty_style → beta_i
```

所以「history-blind 关掉这个入口」与「trait-leveling 把入口两端拉平」，
在"rich/poor 还能不能产生差异"这个问题上**构造等价**。
彩排实测两者**都逐位为零**，正是这个原因 —— 不是"搜遍了载体只找到 traits"。

### 新定性：pathway-isolation / leakage controls

两个测试**都保留**，因为它们检查**不同的实现层**：

| 控制 | 检查什么 |
|---|---|
| history-blind | NovelTask **内部**把历史通道关掉后，是否还漏信号 |
| trait-leveling | 从 **agent state 侧**消除唯一输入差后，任务结果是否归零 |

工程上不是重复测试；**科学证据上不能算两个独立的 negative control。**

### 可以说 / 不可以说

- ✅ 若 main 有效而两个 pathway-isolation control 都归零：
  **027 中观察到的 history effect，按设计是经由
  curiosity/caution 定义的 novelty style 进入新任务的。**
- ⛔ **不许说**："我们搜索了所有历史载体，发现只有 traits。"
  实验**根本没给其他载体进入任务的机会**。

---

## C. 记录更正：彩排 attrition 数字

`final_027_rehearsal.txt` 是唯一权威记录：

```
attrition rich=0.0000  poor=0.0367  keep=0.9633   n=289/300
```

⚠ 对话中一度报成 "rich 3.33% / poor 4.00%" —— **那两个数字是错的**，
是在输出被 `tail` 截断、未实际看到该行的情况下写出的。
**不存在两份口径**：文件正确，口述错误，无 supersede 关系。

> ### ★ 规则 78：没有亲眼看到的数字，一个都不许写进报告 ★
> 输出被 `tail` / `head` 截断时，**必须回去取那一行**，
> 而不是填一个看起来合理的值。这类错误在别处几乎无法被发现 ——
> 这次是靠日志对账抓出来的。

---

## D. 本修订**不改**的东西

`α = 0.05`、`β = 0.05`、`τ = 0.20`、reward probabilities、trial 数、
reversal point、H1/H2 endpoint、截尾规则（None → 36）、有效性闸（90%）、
统计程序（cluster bootstrap 10,000 + 配对符号置换 10,000）、
closure rule（§8）—— **一律不动。**
