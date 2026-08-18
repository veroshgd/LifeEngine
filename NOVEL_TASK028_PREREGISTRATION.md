# 实验 028 预注册 —— Interface Breadth and Component Transfer

**写死日期：2026-08-17 · 状态：待彩排 → 待执行**

一次性文件。写完之后到跑完之前，**不改这个文件、不改 frozen transform、
不改五臂定义、不改 gates、不改 G/R_B、不改 SESOI、不改 joint-bootstrap 方法。**

---

## 0. 研究问题

027 逼出了一个概念区分：

```
有没有历史信息              ← v3 证明存在
新任务能不能【访问】这些信息   ← 027：经一条窄接口只读到极微弱的功能影响（0.08 trial）
```

**028 专门把这两件事拆开。**

> **在总 coupling budget 相同的情况下，broader historical readout
> 是否比 027 的窄接口产生更大的 novel-task transfer magnitude？**

⚠ **名字刻意不叫 generalization**，也不叫 interface-width：
C 最终仍然压成**一个** `beta_i` 进同一个 softmax，
扩大的是**历史读取范围**，**不是决策通道数**。

---

## 1. 冻结对象

```
模型      v4 = v3_frozen 核心（逐字节不动）+ novel_task.py
任务      α=0.05  β=0.05  τ=0.20  TRIALS=80  REVERSAL_AT=40  P=0.80/0.20
          指纹 26778f672e9e7009
接口      interface028_frozen.json   sha256 f82497fb5b1ff535…（n_cal=2936）
```

### 五臂

| 臂 | historical readout | 说明 |
|---|---|---|
| **A** | `curiosity − caution` | **027 原接口，一行不改**。不经 028 任何映射 |
| **B+** | `+industry⊥` | component assay |
| **B−** | `−industry⊥` | component assay |
| **C+** | `A_std + industry⊥` | broader readout |
| **C−** | `A_std − industry⊥` | broader readout |

`industry⊥` = industry 对 **`curiosity − caution`（A 的真实排序变量）** 的
**OLS 残差**，calibration 上 Pearson = 0.000000、**Spearman = −0.0080**。

⚠ 正交化基准必须是 **raw 差**，不是 `z(cur) − z(cau)` ——
A 的 beta 是 raw 差的单调函数，而 σ_cur=20.87 ≠ σ_cau=29.55，
两者**排序不同**（Spearman 0.9999）。quantile mapping 完全基于排序。

### 等预算：quantile mapping

所有非 A 臂的 readout **单调 rank-normalize 到 A 的冻结 beta 边际分布**，
于是 support / mean / SD / 偏度 / 尾部 **全部与 A 相同**，
**唯一差异是"哪些 agent 拿到较大的 beta"（排序）**。

> All historical readouts were monotonically rank-normalized to the frozen
> marginal coupling distribution of the original 027 interface, so arms
> differed in historical ordering rather than overall coupling magnitude.

⚠ **B− 不是 `0.05 − b(B+)`** —— A 的分布不对称（[0.012139, 0.048427]，
μ=0.036948），必须走**反向 percentile**。

⚠ **adapter 必须抵消内部乘法**：`NT.run_task(..., beta=X)` 内部会做
`b = X × novelty_style(agent)`。直接把映射好的 `b_i` 当 `beta=` 传入
会变成 `b_i × novelty_style_i` —— **A 轴被偷偷乘回来，五臂设计失效**。
实测该误差 0.0107 ≈ A 臂整个 SD（0.0122）的同量级。

---

## 2. ★ Primary：G = min(|E_C+|, |E_C−|) − |E_A| ★

`E_arm` = 该臂下 restricted switch latency 的 **same-seed 配对差**
（`d_i = L_rich,i − L_poor,i`，截尾 None → 36，沿用 027）。

**取 min 的含义**：**无论这份未赋予语义方向的历史成分以哪个符号接入，
更宽的 readout 都必须比窄接口产生更强的 transfer**，才算 robust breadth gain。
只有 C+ 或 C− 一个赢 → **sign-dependent，明确不计 primary success**。

### 统计：joint same-seed bootstrap

```
每个 replicate b：
    idx = 重采样一次种子下标        ★五臂共用同一组 idx★
    E_A^(b), E_Cp^(b), E_Cm^(b)    ← 都用这组 idx
    G^(b) = min(|E_Cp^(b)|, |E_Cm^(b)|) − |E_A^(b)|
CI 直接取自 {G^(b)}     n_boot = 10,000   analysis seed 固定
```

⛔ **两类禁止做法**（`stats028.py` 有对抗性测试让它们显式失败）：
① 各臂分别算 marginal CI 再拿端点相减 —— 实测虚宽 **29.2×**
② 先对各臂求 bootstrap 均值再套 `abs()`/`min()` —— `G` 是非线性的，
   必须**逐 replicate** 施加

### 三值判读（SESOI = 1.0 trial，与 027 同单位）

| 情况 | 判读 |
|---|---|
| 95% CI **包含 0** | **没有证据表明 broader readout 比 A 更强** |
| CI 完全 **> 0**，但仍与 **[0, 1]** 重叠 | **检测到 breadth gain，但增益低于功能门槛** |
| CI **整体 > 1 trial** | **functionally meaningful breadth gain established** |

**C+、C− 各自再按 ±1 trial 等价区间单独报一次** ——
"C 比 A 强"与"C 本身有功能意义"是**两个不同的 claim**。

---

## 3. Secondary：R_B = min(|E_B+|, |E_B−|)

同样在 **每个 joint replicate 内部**计算。B+、B− 的原始值全部报告。

⚠ B 问的**不是**"industry 天生能不能迁移"，而是：
**industry 中不被 exploration 轴解释的那部分历史信息，
接到与 027 相同的标准化 decision interface 上时，能产生多少 transfer。**
这是**信息通路实验**，不是心理学语义断言。

**预先记录的结构事实**：`corr(A轴, raw industry) = −0.8823` ——
raw industry 的大部分变异与 exploration 轴重叠。

---

## 4. ★ Validity gates（判读顺序：先于 outcome）★

```
support gate            raw 越界 ≤ 2.0%   且   boundary mass ≤ 2.0%
budget-transport gate   |μ_j − μ_A|/SD_A ≤ 10%   且   |SD_j − SD_A|/SD_A ≤ 10%
```

⚠ `μ_A / SD_A` 必须是**同一批 confirmatory population 上实际跑出来的 A 臂**，
不是 calibration 的 A —— 这样 population shift 自动被消掉。
（transport 彩排实测：A 自己从 0.036948 漂到 0.036663，即 2.3% 的 SD_A。）

⚠ **out-of-support 查【输入端 raw readout】，不是 beta 输出** ——
beta 已被 frozen mapping 限死在 A 的 support 内，本身看不出 extrapolation。

### 分层失败处理

| 失败 | 后果 |
|---|---|
| C+ 或 C− 任一 gate 失败 | **primary G invalid / not cleanly interpretable** —— 既不许声称 breadth gain，也不许声称 no-gain |
| B+ 或 B− gate 失败 | R_B secondary invalid；**若 C± 都通过，G 不受影响** |
| A | **没有 mapping transport gate**（它就是 contemporaneous reference） |

失败时的固定措辞：

> Frozen coupling normalization did not transport adequately to the
> confirmatory population; breadth contrast is not cleanly interpretable
> under the preregistered equal-budget assumption.

⚠ gate 失败**不许重估 mapping**。

### transport 彩排实测（seeds 10000–11499，n=2944，group-blind）

```
最大越界合计 0.10%   最大边界质量 0.20%
最大 |Δμ| = 3.2% × SD_A     最大 |ΔSD| = 2.4% × SD_A
```

---

## 5. ★ A 臂的双重身份（必须分开判）★

`70000–71499` 对 A 也是**真正的新 sampling block**，所以 028 同时产生两个层次的结果：

| | |
|---|---|
| **A 臂** | 027 effect 的 **sampling-level replication**（区别于 027 内部的 analysis-level MC stability，规则 80） |
| **G** | broader readout 相对 A 的 fixed-budget breadth contrast |

**两者必须分开判：**

- 即使 A 没复制出 027 的 −0.08 trial，**G 仍然可以计算**，
  但论文必须写：*027 narrow-interface effect did not replicate on the new
  sampling block.*
- 即使 A 又复制出来，**也不能把 A 的成功算成 028 breadth hypothesis 的成功**。
  G 仍按自己的 CI + 1-trial SESOI 判断。

---

## 6. ★ 四种 dilution 判读模式（预先写死）★

| 模式 | 结论 |
|---|---|
| **C > A，且 B 有 transfer** | 增加可读取的历史成分，在固定耦合预算下**提高了** transfer |
| **C ≈ A** | 更宽的历史 readout **没有增加** transfer；额外维度没有提供净增益 |
| **C < A，且 B 很弱** | 与"固定预算下加入低-transferability 成分造成**信息稀释**"一致 |
| **B 很强，但 C < A** | **不能**叫 dilution-by-noise；提示组合 readout 中可能存在**抵消、相关结构或非线性交互**，需后续机制研究 |

⛔ **不许**把结果简化成 "C>A → 宽接口有效 / C≤A → 宽接口无效"。

---

## 7. 种子账本

```
0–1499          development
10000–11499     021 留出集 / 028 transport rehearsal
20000–21499     022 预注册段 / 027 + 028 group-blind calibration
50000–51499     v3 persistence FINAL
60000–61499     027 novel-task FINAL
70000–71499     ★028 breadth FINAL★   ← 新，从未使用
```

### 028 FINAL CONFIRMATORY BLOCK

```
seed0 = 70000     N = 1500     seeds = 70000–71499
```

- **仅用于 Experiment 028 FINAL**
- **禁止**用于 calibration / transport / rehearsal / parameter selection
- **一旦任何 agent trajectory 被正式生成，该 block 视为 burned**

已核实：代码、实验记录、结果文件中 `70000` 出现 **0 次**。

---

## 8. 工程保护（runner 必须实现）

1. **Seed guard** —— `--final` 只接受 `seed0=70000, N=1500`，其他值直接拒绝
2. **One-shot lock** —— `final_028_result.txt` 已存在则拒绝再次运行
3. **Preflight ledger print** —— final 开始前打印并落盘完整种子账本（§7），
   使四个阶段的数据角色一眼可辨
4. frozen JSON sha256 + 任务指纹校验，任一不符即拒绝运行

---

## 9. ★★ Closure rule ★★

> **一旦看到 70000–71499 的 rich/poor 结果，不允许再改：**
> frozen transform、五臂定义、quantile mapping、transport gates、
> G / R_B 定义、SESOI、joint-bootstrap 方法、任务参数、种子块。
>
> **Primary 失败就是失败。**

失败后可做 exploratory analysis，但**只能标为 exploratory**。

---

## 10. 事前预测（跑前写下，跑完照抄对比）

| 项 | 预测 |
|---|---|
| G 方向 | **不预设**（双侧） |
| G 是否越过 SESOI | **未知** —— 这是 028 唯一真正未知的一项 |
| A 臂 replication | 倾向于再次得到极小效应，但**不预设是否复制** |
| R_B | 未知；`corr(A轴, raw industry) = −0.88` 意味着残差成分的历史信息量可能很小 |
| transport gates | 预计全部通过（彩排最坏 3.2% / 0.20%） |
| C+ / C− 各自 | 预计都落在 ±1 等价区间内 |

---

## 11. 措辞纪律

- ⛔ **不许写** *generalized individuality*
- ⛔ **不许写** agent "理解 / 学会了因果结构" —— 它学的是 2 臂赌博机的价值
- ⛔ **不许写** "我们搜索了所有历史载体" —— 任务只给了一条 readout
- ✅ 必须在 Methods 说明：双胞胎共享 reward table 与 softmax 抽样 `u_t`，
  这是 **common random numbers / counterfactual pairing 的方差缩减设计**
- ✅ B 的措辞必须是 **residual component**，不是 "industry"
