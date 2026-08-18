# ODD 模型描述 —— AI SANDBOX Life Engine v3

对象：`v3_frozen/sim.py`（`MODEL_VERSION = "v3"`，`COND_RECOVER_AT = 65.0`）
**所有行号均为 `v3_frozen/sim.py` 的行号**（见 §8 的行号对照说明）。

本文件是按 ODD 规范写的模型描述，同时充当**最后一次静态代码审计** ——
每一句"agent 为什么做 X""这个变量什么时候变""这条记忆什么时候被读"
都回代码核对过。审计中发现的问题记在 §8，**不修饰**。

---

## 1. Purpose（目的）

回答：**相同的个体，因为经历了不同的过去，是否成为行为上不同的个体？**

模型**不**试图模拟真实的人格形成。它是一个最小装置，用来问：
在一个只有环境差异、没有任何"个体类型"输入的系统里，
经历能否产生**移植到同一环境后仍然存在**的行为差异。

⚠ 模型里**没有"用户类型"这个概念**（v2 的核心变化）。
"谁在投喂""投喂得勤不勤"是**实验脚本**的事（`scenarios.py`），
Life Engine 本身不知道用户是什么。

---

## 2. Entities, state variables, scales（实体、状态变量、尺度）

### 2.1 Agent

| 变量 | 量程 | 何时改变 | 行号 |
|---|---|---|---|
| `traits{caution, curiosity, industry}` | [floor, 100] | 每次行动后（正反馈） | 906–912 |
| `trait_floor` | [identity, 90] | 关键经历、hardship 抬升；每日衰减 | 550, 973, 917 |
| `trait_identity` | [0, 90] | 只被关键经历抬高，**永不下降** | 553 |
| `hunger` | [0, 100] | +2.2/tick；吃一次 −20 | 936, 865 |
| `energy` | [0, 100] | −1.2/tick；各行动另有消耗 | 937 |
| `shelter` | [0, 100] | −0.35/tick；暴雨扣；build +22 | 938, 943, 882 |
| `condition` | [0, 100] | 饿>70 时 −0.40；饿<65 时 +0.16 | 953–961 |
| `inventory{food, material}` | ≥0 | 采集/消耗 | 864–882 |
| `hardship` | ≥0 | 每 tick += deficit/24 | 966 |
| `_hardship_anchor` | dict 或 None | **首次 condition<100 时写入一次，此后不改** | 967–968 |
| `flags` | set | 关键经历触发 | 541 |
| `knowledge` / `knowledge_strength` | 强度 (0,1] | 学到/重温回满 1.0；每日 −0.02 | 484, 499–502 |
| `memories` | list | 关键经历追加 | — |
| `goal` | dict 或 None | **每天早上（tick 0）更新一次** | 931–933 |
| `goal_satiation` | dict | 目标完成/放弃时记日 | 740, 747 |
| `alive` | bool | **只有 condition ≤ 0 会置 False** | 983 |

### 2.2 World

`food`（存量，上限 `food_cap`）、`objects`（`book` / `music`）、
`p`（参数：`food_regen` / `material_yield` / `storm_chance` / …）、
`weather`（`clear` / `storm`）、`rng`、`events`（仅记录）。

### 2.3 尺度

`TICKS_PER_DAY = 24`。实验窗口：发育期 30 天 → 移植 → 观察 30 天。

---

## 3. Process overview and scheduling（流程与调度）

**一个 tick 内的严格顺序**（实验循环 + `Agent.tick`，926–988）：

```
1. world.tick(day, t)          资源再生；tick_of_day==3 时按 storm_chance 掷天气
2. influences(...)             外部干预（投喂、实验层 probe）—— 在 agent 之前
3. agent.tick(day, t):
   a. 若 not alive → 直接返回
   b. 若 tick_of_day == 0 → update_goal()，并把当天目标写入 goal_by_day
   c. hunger += 2.2 ; energy −= 1.2 ; shelter −= 0.35
   d. 若 weather == "storm" → shelter −= damage；damage>28 触发关键经历
   e. condition：饿>70 → −0.40 ；否则 饿<65 → +0.16 ；否则 0
   f. deficit>0 → hardship += deficit/24；**若 anchor 为空则写入 anchor**
   g. anchor 非空 → 用 hardship_norm 抬 trait_floor；hnorm≥0.5 触发 fears_hunger
   h. **若 condition ≤ 0 → alive=False，返回（唯一死亡路径）**
   i. 对全部 7 个动作算分 → argmax → act()
4. （每天末）agent.daily(day):  trait_floor 向 identity 衰减；
                               condition≥99.5 时 hardship 淡忘；knowledge 衰减
```

⚠ 顺序上两处容易看错，都核对过：
- **influence 在 `agent.tick` 之前** → 实验层 probe 只能对**上一 tick** 的
  动作施加后果（026 里所有 influence 型 probe 都有这个一 tick 延迟）。
- **目标一天只定一次**（tick 0），不是每 tick 重选 —— 这是"连续性"的来源。

---

## 4. Design concepts（设计概念）

**Emergence**：个体差异不是输入的，是"行动 → 性状 → 更倾向该行动"的
正反馈放大出来的。

**Adaptation**：**纯反应式**。agent 对当前状态打分并取最大，
**没有任何在场契约学习** —— 它不能通过试错发现"这个世界里 X 导致 Y"。
（这是 026 的核心射程限制。）

**Objectives**：`score(action)` = 状态项 + 性状匹配 + 当前目标加成
+ landmark/knowledge 加成。**无效用函数、无规划、无前瞻。**

**Learning**：只有两条弱通路 —— 性状漂移（连续）与 knowledge
（离散、学到即回满、按日衰减）。

**Prediction**：无。

**Sensing**：agent 读自身全部状态与 `world.objects` / `world.p` /
`world.food` / `world.weather`。**不感知其他 agent**（模型里只有一个 agent）。

**Interaction**：无 agent–agent 交互。

**Stochasticity**：**只有 5 个来源**，全部核对过：

| 来源 | 行号 |
|---|---|
| 出生时性状偏移 ±6 | 418 |
| 暴雨是否发生 / 强度 | 175, 178 |
| 采集食物成功率 0.85 | 183 |
| 探索找到食物 0.28 | 886 |
| 关键经历触发 0.30 / 0.25 | 888, 895 |
| （实验层）投喂时机 | 200 |

**动作选择本身是完全确定的 argmax，没有 softmax、没有 ε-greedy。**

**Collectives**：无。

**Observation**：`action_by_hour`（24×动作）、`goal_by_day`、
`action_log`、`flags`、`memories`。
⚠ 其中 `action_log` 与 `goal_satiation` **会被回读**（见 §5），
不是纯日志 —— 这一点在实验 024 的字段审计（规则 63）中才被发现。

---

## 5. Submodels（子模型，逐条核对）

### 5.1 动作选择

```python
scored = [(self.score(a, day), a) for a in ACTIONS]
scored = [(s, a) for s, a in scored if s is not None]
self.act(max(scored)[1], day, tick_of_day)          # 986–988
```

- `score()` 返回 `None` = 该动作**不合法**（`read` 需要世界里有 `book`，
  `ACTION_REQUIRES_OBJECT`，276）。
- ★**隐藏机制**★ `max((score, action))` 在**分数相同**时按**动作名字母序**
  裁决 → `sleep` 恒胜、`build` 恒败。
  **实测 19,200 个决策 tick 中精确平局 0 次**，所以它存在但从未触发。
  仍然记下来，因为它是确定性的、且未在任何文档中出现过。

### 5.2 正反馈（persistence 的来源）

```python
extremity = abs(traits[t] - 50)/50
pull      = max(0.12, 1 - extremity * TRAIT_SATURATION)
traits[t] = clamp(traits[t] + delta * TRAIT_DRIFT * pull, trait_floor[t], 100)
```
（906–912）

- `delta` 来自 `ACTION_TRAIT_FEEDBACK`（264–272）：做什么 → 强化促使你做它的性状。
- `pull` 是**边际递减刹车**：越极端越难继续极端化。没有它，
  explore 的 `caution −0.10` 会把球推到只会在外面跑（v1 靠永久地板挡，
  v2 地板会消退，于是必须换这个刹车）。
- **下界是 `trait_floor` —— 这就是棘轮。**

★ 因果证据：`TRAIT_DRIFT` 从 0 调到 2.4，移植比值 1.021 → 1.575；
且它是 500 组参数随机化里最敏感的旋钮（ρ = +0.442）。

### 5.3 地板（floor）

- `trait_floor` 被两件事抬高：**关键经历**（550）与 **hardship**（973）
- 每天向 `trait_identity` 衰减 `FLOOR_DECAY_PER_DAY`（917–919）
- `trait_identity` **只升不降**（553），是永久身份
- 地板作为性状更新的**下界**生效（912）

### 5.4 hardship 棘轮

```
首次 condition < 100  → _hardship_anchor = 当时的 traits 快照（写一次，此后不改）
每 tick               → hardship += (100−condition)/100/24
trait_floor[t]        ← min(anchor[t] + w × 22 × hardship_norm, 90)
hardship_norm         = 1 − exp(−hardship / 1.5)
```

⚠ `HARDSHIP_SCALE = 1.5` 意味着累积约 5 天赤字就顶到 1.0，
而实测 hardship 是 23–48 → **hnorm 对所有球、所有条件都饱和在天花板上**。
所以这条棘轮**不是渐变信号，而是二值开关**（规则 50）。
携带个体差异的是 **anchor 里那张快照**，不是"苦吃了多少"。

★ 但实验 024 证明：**anchor 的内容只解释 1.3% 的效应**（规则 54）。
起作用的是"地板存在过"，不是"地板锚在哪张快照上"。

### 5.5 knowledge（实验 022 接入决策）

```
learn/重温 → knowledge_strength[key] = 1.0          484
每日        → strength −= 0.02，≤0 则删除           499–502
score()     → += 12.0 × strength（× slack 若为可自由支配动作）  835
目标优先级   → += 0.25 × strength                    656
```

⚠ 强度实测近乎二值（p10 = 0.000、p50 = 0.979），**不是梯度通道**（规则 73）。

### 5.6 condition / 死亡

```
饿 > 70 → condition −= 0.40
饿 < 65 → condition += 0.16          （v3；v2 是 < 30）
其余     → 0（死区，v3 只剩 5 分宽）
condition ≤ 0 → 死亡（唯一路径）
```

**饥饿本身不致死**，它经由 condition 致死。
v2 的死区宽 40 分且恢复通道几乎不触发 → 无稳态、120 天死亡率 40.7%；
v3 把阈值抬到 65，**必须跨过"怠惰谷"**（规则 49）才有效。

### 5.7 目标

每天早上 `update_goal()`：`propose_goals()` 给 5 个目标打优先级
（读 shelter / food / condition / knowledge / flags），减去
`_satiation`（不应期），取最高者；有切换边际与最短持续天数。
目标通过 `GOAL_ACTIONS`（300–305）给对应动作加成。

⚠ `learn` 目标在基准世界**参与率 0.0%**（需要书）；`recover` 只有 16.6%。
**实际只有 3 个活跃目标。**

---

## 6. Initialization（初始化）

`traits = 50 ± U(−6, 6)`（418）；`hunger=30, energy=?, shelter=?, condition=100`；
`inventory` 空；`flags/knowledge/memories` 空；`trait_floor = trait_identity = 0`。
世界按 `scenarios.WORLDS` 的参数构造。

★ 关键：**两个发育世界唯一的差别是世界参数**
（`food_regen` 3.2/1.8、`material_yield` 2.0/0.5、`objects`
`("book","music")`/`()`、`storm_chance` 0.02/0.1）。
**agent 的初始化完全相同，只由种子决定。**

---

## 7. Input data（外部输入）

无外部数据。所有随机性来自种子。

---

## 8. ★ 审计中发现的问题（不修饰，如实记录）★

### 8.1 行号对照：记录里 023 之前的行号在 v3 上对不上

`v2_frozen/sim.py` 1013 行，`v3_frozen/sim.py` 1043 行。
v3 在文件头加了约 27 行 docstring，又在中部加了 3 行 `MODEL_VERSION`，
**所以偏移不是常数**：

```
                              v2      v3     偏移
def take_food                 154     181    +27
KNOWLEDGE_WEIGHT × know       805     835    +30
hardship += deficit           936     966    +30
_hardship_anchor = dict       938     968    +30
trait_floor[t] = max(         943     973    +30
```

⚠ **实验记录里 023 及更早引用的 `sim.py:NNN` 用的是 v2 编号**，
在 `v3_frozen/` 里要 **+27（`MODEL_VERSION` 之前）或 +30（之后）**。
本 ODD 的全部行号已统一为 **v3_frozen 编号**。

### 8.2 平局裁决是隐藏的确定性机制

`max((score, action))` 按动作名字母序裁决平局。
实测 0/19,200 次触发，**但此前从未在任何文档里出现过** ——
如果有人改动打分让平局变常见，行为会系统性偏向 `sleep`。

### 8.3 写 ODD 时确认的、此前理解错过的机制

| 机制 | 曾经的错误理解 | 正确的 | 记在哪 |
|---|---|---|---|
| `take_food` | 以为可以清零 `world.food` 来"暂时封锁" | 它是**从库存扣**，清零 = 烧掉存粮 | 规则 60 |
| `memories` | 以为是纯日志 | 被 `recall()` 回读 | 规则 63 |
| `action_log` | 以为是纯日志 | 喂**目标进度** | 规则 63 |
| `goal_satiation` | 漏了 | 被回读（不应期） | 规则 63 |
| `storm_damage` | 漏了 | **动态属性**，暴雨后才存在 | 规则 63 |
| `explore` 食物产出 | 以为足以独立维生 | 0.14/tick vs 需要 0.11/tick，扣掉睡眠为负 | 规则 64 |
| `knowledge_strength` | 以为是连续通道 | 近乎二值（0 或 0.98） | 规则 73 |

**这七条都是"我知道所以没写"的隐含机制，写 ODD 时才逐一暴露。**
