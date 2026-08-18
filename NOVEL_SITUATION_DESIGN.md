# NOVEL-SITUATION 实验设计 v3（**定稿方向 → 进入 group-blind 校准**）

状态：设计已收敛。**未碰 `60000–61499`，未改 `v3_frozen/`。**
下一步：写 `novel_situation.py` + `novel_calibrate.py`，在 `20000+` 上做校准。
v2 → v3 依据：全部数值拍板 + **规则 61**（§10 变更记录）。

---

## 0. 架构射程（进预注册）

v3 的动作选择是 `score(action)` = 「状态 + 性状 + 目标 + landmark/knowledge」
加权和，**没有在场因果学习机制**。本实验最强只能回答：

> 由不同过去塑造出来的**既有内部结构**，被放进一个训练历史中从未存在过的
> 环境结构时，会不会产生系统性不同的**决策与后果**。

**不能**回答"不同的过去会不会带来不同的**学习**"（那需要 v4）。**本阶段不扩模型。**

### 措辞纪律

- **不许写**"适应冻土需要理解：采材料 → 盖房 → 才能觅食"。v3 不会发现任何规则。
  **正确**：新环境把既有的内部差异，**投影**到一个训练历史中不存在的策略分岔上。
- **不许写**"history 携带的信息不是 `B_familiar` 的函数"。
  **只能写**：*History carries predictive information not captured by the
  preregistered familiar-behavior representation and model class.*
  （历史包含了**预注册的熟悉行为表征与模型类**无法充分捕捉的、
  对新情境行为具有预测价值的信息。）

---

## 1. ★★ 规则 61：counterfactual sibling branches ★★

**这是整个设计里最重要的一条，比 RF 用 8 层还是 12 层重要得多。**

### 不能这样（v2 的隐含做法，错的）

```
agent → 熟悉世界跑 W 天，测 B_familiar → 再进冻土，测 B_novel
```

**因为那 W 天的 familiar 测量本身就是一段额外经历**，会继续改变
traits / goal / trait_floor / knowledge / hardship。
到进冻土时，你预测的**已经不是"同一个历史状态面对两个未来"**。

### 必须这样

```
              development 结束
                     ↓
                  状态拉平
                     ↓
              完整 snapshot（含 RNG）
                  ↙        ↘
             clone F        clone N
             熟悉世界        Novel 世界
                ↓              ↓
            B_familiar      B_novel
```

- 两个 clone 在**分叉瞬间**的完整可执行状态与 **RNG state 完全相同**。
- **任何一个分支之后发生的事都不得反馈给另一个**（`copy.deepcopy` 后互不引用）。
- 两个分支跑**同样长度 W**，窗口口径一致，`B_familiar` 与 `B_novel` 才可比。

⚠ 实现陷阱（024 踩过）：`FrozenZero` 是 `dict` 子类且 `__setitem__` 是 no-op，
`deepcopy` 重建它时走 `__setitem__` → 复制出**空 dict** → `KeyError`。
分叉后必须重建 `FrozenZero()`（它不携带状态，重建等价）。

---

## 1b. ★★ 规则 62：behavior window 与 consequence window 必须分离 ★★

### 问题

校准允许 novel probe 里死掉近 20%。但 G1 预测的是 **7 维动作占比**。
若一只球第 8 天死、另一只活满窗口：

```
A：只观察到 8 天行为        B：观察到 30 天行为
```

- **删掉死亡个体** → 又制造 **survivor selection**，
  而这正是 persistence 阶段花了大量实验才清理掉的东西（规则 44）。
- **直接用死亡前的行为** → **观察窗口长度不同**，占比不可比；
  而且死亡本身可能就是 rich/poor 历史造成的
  → G1 会把**"谁活得久"**和**"怎么做决策"**混在一起。

### 结构

```
进入 Novel world
      ↓
【decision window】W_dec 天  ——  算 B_novel → G1（行为）
      ↓
继续运行
      ↓
【consequence window】跑满  ——  survival / food / shelter / condition → G2（后果）
```

- **G1 只用 decision window**，且校准必须保证该窗口内 **pooled survival ≥ 95%**。
- **G2 才用长窗口**的死亡与资源后果。
- **禁止用"只分析幸存者"来定义 G1。**

> G1 测的是「**面对陌生情境时怎么选择**」；
> G2 测的是「**这些选择后来造成什么后果**」。**这两个不许混。**

`B_familiar` 同样只取 decision window（两支等长，规则 61），
两支之后都继续跑到 consequence window —— 熟悉支的后果即 G2 的轭式对照基线。

### `W_dec` 也不凭感觉选（与 S / λ 同等待遇）

候选集 `W_dec ∈ {5, 7, 10, 14}` 天，先写死，在 `20000+` 上 **group-blind** 选。

## 2. 两个结构正交的 probe（定死，禁止事后追加）

**两个都过 G1 → 才允许用 *generalized individuality*；
只过一个 → 只能写 *novel-context transfer*。**

### Probe A —— 「冻土」（N1：前置条件门控）

`world.food` 只在 `agent.shelter ≥ S` 时**可取**。

> ### ★ 规则 60：必须是 non-destructive gate ★
> **绝不能**写 `world.food = 0`。`World.take_food` 是从**库存**扣
> （`sim.py:181-186`），清零 = 每 tick 烧掉世界存粮、下一 tick 从 0 重新 regen
> —— 那是"shelter 不够就毁掉食物"，不是"食物存在但取不到"。**物理规律不同。**
>
> ```python
> class GatedWorld(sim.World):          # 实验层子类，不改 v3
>     def take_food(self, rng):
>         if self.agent.shelter >= self.gate_S:
>             return super().take_food(rng)
>         if self.food >= 1:            # 与 v3 相同的抽样条件，保持随机流对齐
>             rng.random()              # 门只改可供性，不额外扰动 RNG
>         return 0
> ```
>
> `self.agent` 在换世界时绑定 → `shelter` 在**调用时刻**读取，**无一 tick 延迟**，
> 且 Probe A 根本不需要 influence。
>
> 一般教训：**在有库存/存量语义的变量上做临时限制，不能改写存量，
> 要改取用规则。**

策略分岔来源：`explore` 的产出走 `EXPLORE_FOOD_YIELD`，**不经过 `world.food`**
（`sim.py:886`）→「盖房 → 正常觅食」与「持续探索」两条路都能活。

### Probe B —— 「盐碱地」（N2：零和耦合）

`gather_material` 额外扣 `world.food`；`gather_food` 额外扣 `agent.shelter`。

**一维 λ 校准**（二维空间里"最小耦合强度"没有唯一含义）：

```
c_f = λ × k_food       k_food    = 一次 gather_food 的产出 = 1     （sim.py:185）
c_s = λ × k_shelter    k_shelter = 一次 build 的 shelter 增量 = 22 （sim.py:882）
```

λ 的含义对称可读：**一次采材料 = 毁掉 λ 次觅食的收成；
一次觅食 = 毁掉 λ 次盖房的成果。** 校准只在 `λ = 0.1, 0.2, 0.3 …` 里找**第一个**
满足 pooled 判据的值。

实现有**一 tick 延迟**（influence 在 `agent.tick()` 之前跑）——**论文里如实写明**。
`explore` 不吃 material 也不掉 shelter → 保留第三条路。

### 正交性
A = **门控 / 前置条件**（达标才解锁）；B = **零和权衡**（此消彼长）。因果拓扑不同。

---

## 3. 特征、目标与损失（★ v3 定稿 ★）

### `B_familiar` = **182 维**（故意给 M0 优势）

| 维度 | 内容 |
|---|---|
| 168 | 24 小时 × 7 动作的**完整动作比例矩阵**（每小时内归一） |
| 7 | 全窗口动作占比 |
| 7 | **后半段 − 前半段**的动作占比变化量 |

后 14 维都是 168 / 原始行为记录的**确定性摘要**，**不引入新信息**，
只是让 RF 更容易读到已有信息（"几点做什么" + "熟悉环境中行为是否还在漂移"）。

> **为什么不用 7 维**：审稿人一句
> "history 只是补回了你自己压缩掉的 circadian / temporal information"
> 就挡不住。182 维让 G1 更难通过，**但通过以后更硬**。

### `B_novel` = **7 维动作占比分布**（primary target）

即：182 维熟悉行为信息 → 预测 7 维 novel 策略剖面。**刻意让 M0 占便宜。**

### 损失 = TV 距离（接得上项目一贯的行为指标）

```
L(p, p̂) = ½ Σ_{a=1..7} |p_a − p̂_a|

d_i = L(actual_novel, M0预测) − L(actual_novel, M1预测)
```

`d_i > 0` 的通俗含义：**知道过去以后，对这个 agent 在新世界里会怎么分配
行为时间，预测得更准了多少。**

**聚合顺序**：一颗 seed 的 rich/poor 两只球**先取平均** loss improvement，
**再**做 seed-level 推断。

### ⚠ `entry_state` 在主分析里是常量

拉平之后所有 agent 的进入态**按构造完全相同** → 在主分析中 `entry_state`
不携带任何信息，`M0 = f(B_familiar)`。
`entry_state` 只在**未拉平的配对匹配次分析**里才是真变量。
这一点要写明，否则看起来像漏了一项。

---

## 4. 模型与推断

### 模型类

- **Primary：Random Forest**，`n_estimators = 1000`（压低森林自身随机性），
  `random_state` 固定。
- **Robustness：二次基展开 Ridge**（好解释，但只覆盖预先指定的二阶结构）。
  **不要求两者都显著。**
- **不用 k-NN**（行为向量维度一高，距离就不好使）。

**M0 与 M1 必须同模型类、同超参、同 fold、同特征预处理、同 random_state。
M1 唯一多 `development_history` 这一列。**

### 超参选择：group-blind，且**只优化 M0**

在 `20000+` 上扫小网格：

```
max_depth        ∈ {8, 12, None}
min_samples_leaf ∈ {5, 10, 20}
max_features     ∈ {"sqrt", 0.5, 1.0}
```

> ### ★ 铁律 ★
> 调参脚本**不接收 `development_history`**，**更不许看哪个模型让 M1−M0 最大**。
> 唯一目标：**哪个 RF 最能从 `B_familiar` 预测 `B_novel`**。
> **性能接近时，预先规定选更简单 / 更正则化的那个**
> （更大的 `min_samples_leaf`、更小的 `max_depth`、更小的 `max_features`），
> 而不是挑结果最漂亮的。

### 推断：`ΔOOS` + 种子聚类 bootstrap

```
ΔOOS = mean_i d_i          （只在【没参与拟合】的 fold 上算）
```

- **CI**：按**种子** cluster bootstrap，**10 000 次**，取 2.5/97.5 分位。
- **判据**：`ΔOOS` 的 95% CI 下界 **> 0**。
- **Secondary**：双胞胎对内交换 rich/poor 标签 + 重跑整条 CV 流水线的置换检验。

### ★ 规则 56 强化版：消灭分析随机性，而不只是测量它 ★

R52 的教训是"换个分析种子结论就翻"。**这次从源头堵死**：

1. **CV fold 确定性**：`fold = deterministic_hash(seed) % K`，
   **rich/poor 双胞胎永远同 fold**（否则信息泄漏）。**不每次随机分。**
2. **RF `random_state` 固定**；`n_estimators = 1000` 进一步压低森林随机性。
3. **bootstrap 固定 analysis seed**，replicates 提到 **10 000**
   （只是重采样 OOS 的 `d_i`，很便宜）。

**正式分析本质上是 deterministic 的。**
8 个 analysis seed 的彩排仍然跑，但**只作稳定性诊断**，不再是判读的一部分。
若彩排显示判读仍会被随机性左右 → **跑前**改三值判读，绝不事后改。

### 容量对照 —— 护栏（★ v3 收紧判读 ★）

RF 之下 `rank(explore)` 这种**单调变换无效**（树本就按阈值切分）。
改用**需要交互才能恢复**的、100% 是 `f(B_familiar)` 的变量：

```
C1 = explore × build
C2 = 1[ (explore > median) XOR (build > median) ]
```

**判「模型容量不足，不能解释」需要【两个条件同时成立】**：

1. 该容量对照**自身的 `ΔOOS` CI 下界 > 0**（它自己得是真的有用），**且**
2. 点估计 ≥ 真 history 的 **50%**

> 只看点估计会让一个很噪的 C1 恰好到 51% 就把实验判死。
> **50% 是人为护栏，不假装它是某个理论常数。**
>
> ⚠ **通过容量对照 ≠ 证明没有 underfit。** 只能说
> "预先检验的两类交互结构未攻破 M0"。

---

## 5. 状态相同性与阴性对照

① **状态拉平**（主分析）：沿用 `leveling.py`（020），统一
`hunger / energy / shelter / condition / inventory`。拉平后 shelter **必须低于 S**。
② **配对匹配**（次分析，无干预）：不拉平，只留进入态接近（ε 预定）的配对。

### ③ 完整可执行状态拉平 —— 阴性对照

不只 traits/floor/knowledge/flags/memories/hardship，**还必须包括**：
**RNG state**（`agent.rng` / `world.rng` / `life.inf_rng`，用 `getstate()`）、
goal 状态、landmark 状态、`_hardship_anchor`、所有计数器与缓存
（`action_log` / `action_by_hour` / `goal_by_day` / `events` …）。

**执行**：probe 前完整序列化两个 agent，除 `development_history_label` 外
**hash 必须相同**。若全部一致、放进同一环境仍不逐位相同 → 有泄漏 → **整批作废**。

### 其余阴性对照
- 只删 memories：必须**逐位** no-op
- novel 规则关闭：必须复现 persistence 阶段数字

---

## 6. 难度校准：group-blind，先冻结算法后定数值

在**已烧掉的 `20000+`** 上跑，**脚本不接收发育世界标签**，不得计算任何按发育
世界分组的量。

策略归类：novel 窗口内 `b = (gather_material + build) 占比`、`e = explore 占比`：
`盖房派 b−e ≥ m` / `探索派 e−b ≥ m` / 其余混合。**`m = 0.05`**。

### 合格条件（pooled，标签隐藏）

1. 两条主策略**各自** ≥ 20% 且 ≤ 80%（在 **decision window** 内归类）
2. **★规则 62★ decision window 内 pooled 存活率 ≥ 95%**
3. consequence window 的总体存活率 ≥ 80%
4. 进入后 5 天内达标者 ≤ 50%（不是所有球瞬间过关）
5. **门确实打得开**：consequence window **结束前**达到 `S` 的比例 ∈ **20–80%**
6. **不是伪分岔**：两条策略各自 pooled 存活率 **各 ≥ 80%**，且**相差 ≤ 10pp**
7. **行为样本够**：每小时格 ≥ 5 次观测（即 `W_dec ≥ 5`），每只球总动作数 ≥ 120

### 选择顺序（★ 二维也要有唯一解 ★）

`W_dec` 与 `S`（或 `λ`）**联合**决定，但用**字典序**取唯一解，
避免重蹈 `c_f/c_s` 那种"二维空间里最小没有唯一含义"：

```
for W_dec in (5, 7, 10, 14):          # 先按 W_dec 升序
    for S in 候选升序:                 # 再按 S 升序
        if 满足全部 1–7:  取之，停止
```

即 **先取最短的 decision window，再取最小的 S / λ。**

> ### ★ 铁律 ★
> 选 `S` / `λ` 时**不许看哪个值让 rich/poor 差异最大** —— 那是在调 effect size。
>
> ### ★ 找不到满足条件的 S / λ 怎么办 ★
> **就说明这个 probe 的设计本身不够干净，不应该为了让它能跑而放宽标准。**
> 026 要测的是 strategy transfer，**不是重新研究 survival selection**。
> 允许一条路线死 30%、另一条死 10%，已经足够让行为样本产生明显筛选。

---

## 7. 判据

| 判据 | 内容 |
|---|---|
| **G1 主判据** | 双 probe **各自** `ΔOOS` 的种子聚类 bootstrap 95% CI 下界 > 0，**且容量对照未被攻破**。**只用 decision window**（规则 62），**禁止靠只分析幸存者来定义** |
| **G2 后果判据** | **consequence window** 里存活率或末期资源存在世界差异，配对检验 `p < 0.01` |
| **G3 机制问题** | `−全部地板①②` 下 G1 是否仍成立 —— **探索性，不预设方向** |
| **命名判据** | 两 probe 都过 G1 → *generalized individuality*；只过一个 → *novel-context transfer* |
| 阴性对照 | §5 三条全过 |

### G3 的地位：机制问题，不是必要条件

若 persistence 本来就由 floor 携带，那么
`history → floor consolidation → novel context → new divergence`
**完全可以是真正的 generalization**。generalization **不要求换载体**；
载体可以还是同一个，**新的是它对未见问题产生了新的功能后果**。

- 关 floor 后 G1 消失 → *generalization depends on the same consolidation
  architecture*。**不是失败**，是完整故事：
  **同一结构既保存过去，也把过去投射到新的未来。**
- 关 floor 后 G1 仍在 → 存在第二条载体，更意外，但**不是必要条件**。

---

## 8. 种子计划

**留给 novel-situation final 的干净段：`60000–61499`。预注册写死前不许指向。**
已烧掉、可用于设计 / 校准 / 调参 / 彩排：`0–1499`、`10000–11499`、
`20000–21499`、`50000–51499`。校准与彩排一律用 `20000+`（规则 57）。

---

## 9. 实现约束

1. **不改 `v3_frozen/` 任何一行。** Probe A = `GatedWorld` 子类；
   Probe B = influence（一 tick 延迟，需披露）。要改 v3 就分叉 v4。
2. 新模块：`novel_situation.py`（GatedWorld / Probe B / 拉平 / 分叉 / 序列化对照）、
   `novel_calibrate.py`（**group-blind**）、`novel_probe.py`（执行）。
3. **规则 55**：每个子任务显式设定所有 `sim.` 全局量；换 `--workers` 跑两遍须逐字节相同。
4. **规则 57**：彩排参数形状与正式运行一致（不用 `seed0 = 0`）。
5. 覆盖率自检 + `n = 0` 拦截（025 §4）照搬。
6. 分叉后重建 `FrozenZero()`（deepcopy 陷阱，024）。
7. ★ **C2 的中位数只能用 training fold 计算**，再应用到 held-out fold。
   用全数据中位数会造成 test information leakage。
   （C1 = `explore × build` 是纯乘积，无此问题。）
   同理：任何特征标准化 / 分箱都只在 training fold 上拟合。
8. ★ **sibling 隔离的主动证明**（规则 61 的验收测试，很便宜）：
   分叉后不只检查"没有共享引用"，还要在开发种子上做一次
   **突变测试** —— 改 clone F 的 `inventory` / `traits` / `world.food`，
   **断言 clone N 逐位不变**；反向再做一次。不过不往下走。

---

## 10. v2 → v3 变更记录

| # | 变更 |
|---|---|
| 1 | ★ **新增规则 61：counterfactual sibling branches** ★ —— `B_familiar` 与 `B_novel` 必须来自同一进入态的两个平行分支，不能顺序测量 |
| 2 | `B_familiar` 定为 **182 维**（168 时辰×动作 + 7 全窗口占比 + 7 前后半段变化） |
| 3 | `B_novel` 定为 **7 维动作占比**；**损失 = TV 距离**；先对双胞胎取平均再做 seed-level 推断 |
| 4 | 容量对照判读加条件：**对照自身 CI 下界 > 0 且点估计 ≥ history 的 50%** 才判容量不足 |
| 5 | 校准第 5 条收紧：两策略存活率**各 ≥ 80%、相差 ≤ 10pp**（原 70% / 20pp）；并写明"找不到就说明 probe 不干净，不放宽标准" |
| 6 | RF 超参：`n_estimators = 1000` 固定，小网格 group-blind **只优化 M0**，性能接近时**预先规定选更正则化的** |
| 7 | **规则 56 强化为"消灭分析随机性"**：fold = `hash(seed) % K` 确定性划分、RF 固定 `random_state`、bootstrap 固定种子且提到 10 000 次；8 种子彩排降为稳定性诊断 |
| 8 | 写明 **`entry_state` 在拉平后的主分析中是常量**，只在未拉平的次分析里是真变量 |
| 9 | ★ **新增规则 62：decision window / consequence window 分离** ★ —— G1 只用短窗口且要求窗内存活 ≥95%，G2 才用长窗口的死亡与资源后果；禁止用"只分析幸存者"定义 G1 |
| 10 | `W_dec` 与 `S`/`λ` 用**字典序**联合选择（先最短窗口，再最小 S/λ），保证二维也有唯一解 |
| 11 | 实现约束新增：C2 中位数只在 training fold 算（防泄漏）；sibling 隔离要做**突变测试**主动证明 |

---

## 11. 下一步

设计到此收敛，**不再发散**。接下来：

1. 写 `novel_situation.py`（机制层：`GatedWorld`、Probe B influence、
   拉平、**规则 61 的分叉**、完整序列化对照）
2. 写 `novel_calibrate.py`（**group-blind**），在 `20000+` 上校准 `S` 与 `λ`
3. 校准产出数值 → 写 `NOVEL_PREREGISTRATION.md` → **然后才**碰 `60000–61499`
