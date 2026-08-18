# 实验 027 预注册 —— Novel-Task Transfer + Reversal

**写死日期：2026-08-17 · 状态：待彩排 → 待执行**

一次性文件。写完之后到跑完之前，**不改这个文件、不改任务参数、不改模型**。
跑完之后**也不改**，只在实验记录里追加结果。

---

## 0. 模型与冻结对象

**v4 = `v3_frozen/` 的核心（逐字节不动） + `novel_task.py`**

`novel_task.py` **不修改 `v3_frozen/` 的任何一行**，也**不在 60 天之内接触
agent 状态**，所以「NovelTask 关闭时 v4 与 v3 逐 tick 完全相同」是
**构造上成立**的（仍写成回归测试，见 §5 控制一）。

### 任务配置（已由 group-blind 校准冻结）

```
α (学习率)        = 0.05     所有 agent 相同
β (不确定性奖励)   = 0.05     ★唯一让历史进来的旋钮★
τ (softmax 温度)  = 0.20     所有 agent 相同，不是历史通道
TRIALS = 80   REVERSAL_AT = 40   P_HIGH/P_LOW = 0.80/0.20   Q_INIT = 0.5

配置指纹 config_fingerprint() = 26778f672e9e7009
```

`assert_frozen()` 在每次正式运行前硬拦截；指纹随结果一起落盘。
**默认参数已等于冻结值** —— 即使 runner 忘了显式传参也跑不错版本。

---

## 1. 研究问题

> 两只起点完全相同、过去经历不同、后来已形成持久差异的 agent，
> 在第一次面对一个**双方都从未见过的新任务**时，
> 会不会因为过去不同而**学得不同 / 选择不同 / 适应路径不同**？

### 流程

```
30 天发育（丰富 / 贫瘠）→ 30 天 common garden → 拉平身体状态
→ 进入新任务：A / B 两个从未存在过的选项，80 trial
   trial 1–40   好选项 80% / 差选项 20%（哪个先好按种子随机）
   trial 41     ★规则突然反转★
   trial 41–80  反过来
```

### 历史唯一的入口

```
novelty_style = (curiosity − caution + 100) / 200 ∈ [0,1]
beta_i        = β × novelty_style_i
value(x)      = Q_x + beta_i / sqrt(1 + N_x)
choice        ~ softmax(value / τ)，用共享的 u_t 决定
```

**过去不许决定 A 还是 B 好。** 学习率 α、温度 τ、奖励表对所有 agent 完全相同。

---

## 2. ★ Primary hypothesis H2 —— Reversal adaptation ★

> **H2：developmental history alters adaptation to reversal in a jointly
> novel task.**

**Primary endpoint = restricted switch latency。**

```
switch latency = 反转后第一个 trial t，使 [t, t+5) 内 ≥4 次选中新的正确选项
可检测的最大值 = 35
整个观察期都没切换 → 截尾为 36
```

⚠ **36 不是"它在第 36 个 trial 切换了"，而是"观察窗内未切换"。**
这条截尾规则**跑前写死**，理由：

- **删掉 never-switcher** → 制造 selection（若某一支 never-switch 更多，
  效应会被悄悄抹掉）
- **当成 0** → 把"从不切换"错当成"立刻切换"，方向完全反
- **事后改用 survival model** → 那是看到结果之后选统计方法

（校准实测 never-switch 只有 **2.0%**，所以截尾不会主导结果，但仍提前写死。）

### 统计

```
逐种子      d_i = L_rich,i − L_poor,i        （same-seed 双胞胎配对）
Primary     mean(d_i)
CI          按种子 cluster bootstrap 10,000 次，95%
p           same-seed 配对符号置换 10,000 次
```

**H2 是双侧**：95% CI 不含 0 → developmental history 改变 reversal adaptation
latency。**rich 更快、poor 更快、没区别 —— 三种结果都接受。**
⛔ **不预设方向。**

---

## 3. Secondary confirmatory H1 —— Novel-task transfer

> **H1：developmental history already alters behavior during initial
> acquisition of the novel task.**

**Endpoint = trial 1–10 的 exploration rate**
（"探索" = 选了当前 Q 值较低的那个）。选前 10 个 trial，
因为那是 agent **真正第一次面对陌生选项**的时刻。

同样用 same-seed 配对 + cluster bootstrap + 符号置换，双侧。

> ### ⛔ H1 是 secondary，不得替代 primary ⛔
> **不许出现**："H2 不显著 → H1 显著 → 宣布 027 成功"。
> H2 是唯一的 primary endpoint。

---

## 4. 判据

| 判据 | 内容 |
|---|---|
| **H2（primary）** | restricted switch latency 的配对差，95% CI 不含 0 |
| **H1（secondary）** | trial 1–10 exploration rate 的配对差，95% CI 不含 0 |
| **有效性闸** | 见 §6，不过则判 validity compromised，不做强结论 |
| **四个控制** | 见 §5，任一失败则整批作废 |

### ⚠ 提前套用规则 56（可判定性）

`CI 不含 0` 又是一条 bright line。**彩排阶段**（已烧种子）要换 8 个分析
随机种子重跑，若判读会被随机种子左右，**在跑 final 之前**改成三值判读
（过 / 不过 / 落在检出边界无法裁决），边界宽度取 ≥10 × 实测 MC SD。
**绝不事后改。**

---

## 5. 四个控制（任一失败 = 整批作废）

1. **v3 等价控制** —— NovelTask 关闭时前 60 天与 frozen v3 逐位一致；
   任务不得回写 agent 的任何既有状态。
2. **完全相同 agent 控制** —— 同一第 60 天 snapshot clone 两份 + 同一奖励表
   → 必须**逐 trial 相同**。否则有 RNG / 共享引用泄漏。
3. **history-blind 控制** —— 把 curiosity/caution 对 β 的影响关掉
   （beta 固定为中值），学习照常。
   **若两个历史的 task trajectory 仍系统性不同 → 存在未发现的通路。**
4. **trait-leveling 控制** —— 在任务入口把 rich/poor 的 curiosity、caution
   拉成相同，**保留其他一切历史**。
   - 主效应**消失** → 证实 `过去 → trait → 新任务行为` 这条机制
   - 主效应**仍在** → 说明还有别的历史载体（是发现，不是失败）

---

## 6. ★ 有效性闸：pre-task paired attrition ★

NovelTask 本身完全不碰 survival，但进入任务的 agent 仍是被 v3 前 60 天
筛过的。所以：

- **只有 rich 与 poor 都活到 task entry 的种子进入 primary paired analysis**
  （same-seed 双胞胎交集）
- **必须分别报告**：rich pre-task mortality、poor pre-task mortality、
  paired exclusion 数
- **闸**：若 1500 个 final 种子中**有效双胞胎 < 90%**，
  判 **validity compromised，不做强结论**

（校准阶段 600 → 589，损失约 1.8%，预计远达不到 10%。提前锁死。）

---

## 7. 种子

```
开发 / 校准 / 彩排   20000–21499 及其他已烧段
★ FINAL ★           60000–61499（N=1500）—— 从未使用，只跑一次
```

已污染、不得作 final 的段：`0–1499`、`10000–11499`、`20000–21499`、
`50000–51499`。

---

## 8. ★★ Closure rule ★★

> **一旦看到 60000–61499 的 rich/poor 结果，不允许再改：**
> reward probabilities、reversal time、learning rate α、softmax 温度 τ、
> trait coupling β、primary metric、task length、截尾规则、统计程序。
>
> **Primary test 失败就是失败。**

失败后可以做 exploratory analysis，但**只能标为 exploratory**，
不得包装成新的 confirmation。

---

## 9. 事前预测（跑前写下，跑完照抄对比）

| 判据 | 预测 |
|---|---|
| H2 方向 | **不预设**（双侧） |
| H2 是否显著 | **未知** —— 这是本实验唯一真正未知的一项 |
| H1 | 倾向于有差异（novelty_style 直接进 β），但同样双侧 |
| 控制 1/2 | 必过（已在自检中通过） |
| 控制 3 | beta 固定后两支应无系统差异 |
| 控制 4 | 若机制如设计，主效应应**大幅减弱** |
| 有效双胞胎率 | > 95% |

---

## 10. 措辞纪律（成功时也不许越界）

- ✅ 可写：**developmental history transferred to learning and adaptation
  in a jointly novel task**
- ⛔ **不许写** *generalized individuality* ——
  本任务**明确设计了** `curiosity/caution → exploration bonus` 这条接口，
  测的是"一个预先指定的通用探索接口能否把历史差异带进新任务"，
  **不是**"随便给什么未知问题，个体性都会自动泛化"。
  要升级措辞，需要**第二个结构完全不同的任务**也复现（028）。
- ⛔ **不许写** agent "理解 / 学会了世界的因果结构" ——
  它学的是**一个 2 臂赌博机的价值**。
- **必须在 Methods 里主动说明**：rich/poor 双胞胎共享同一奖励表与同一
  softmax 抽样 `u_t`，这是 **common random numbers / counterfactual
  pairing 的方差缩减设计**，
  **不是**假装现实中两个 agent 会共享随机数。
  （可预注册一个 independent-choice-noise 的 secondary robustness 分析，
  但它**不是** primary 成立的必要条件。）
