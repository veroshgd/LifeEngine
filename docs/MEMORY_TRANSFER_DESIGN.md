# MEMORY_TRANSFER_DESIGN —— 实验 029 设计草案

**状态：设计草案（DRAFT）· 2026-08-18 · 第 7 版 —— ★ 已升级为预注册，本文件转为历史设计记录 ★**

> ### ✅ 预注册已写成：`MEMORY_TRANSFER029_PREREGISTRATION.md`
> **本文件到此定格，转为"设计是怎么一步步长出来的"的历史记录。**
> 从现在起以预注册为准；本文件不再是活文档。
> （唯一待拍板处在预注册 §6.3：SHUFFLE 判据落在点估计还是 CI 上界。）

> ⚠ **这不是预注册。**
> 这个文件今天可以随便改、改多少次都行。
> 预注册（`NOVEL_TASK029_PREREGISTRATION.md`）是**另一个文件**，
> 等这里的问题全部拍板、且 group-blind 校准通过之后才写，
> 写完就一个字不许动（承 027 / 028 的 closure rule）。

**今天已经落地的**：② ③ ④ 从"待定"变成"已定草案"；探针跑了两版 ——
v1 one-shot（SWAP dominance 未通过 → **该判据已撤回**）、
v2 stateful（Directional SWAP check PASS）、v3 修 resolution 时序 bug（效果缩水、故事不变）；
**手工 memory probe 阶段就此结束**，已开 `memory_acquisition_probe.py` 做真实
Stable/Volatile 历史 —— 方向完全正确；yield 已由 **ANOMALY_AT=36** 修到 65.8%/73.2% 并**冻结**；
λ 接口容量校准已跑（group-blind），**λ=1.00 与四个 capacity gate 正式冻结**；
OWN/DELETE/SWAP/SHUFFLE rehearsal 已在开发种子上跑完（**SHUFFLE 塌缩、SWAP-XS 保留 96%**）。见 §⑥–§⑨。

---

## ① 029 到底测什么？（已写死）

> **Can structurally relevant past experience be retrieved and causally used
> to adapt to a surface-novel problem?**
>
> 过去的经历如果与新问题在**底层结构**上相关，agent 能否**检索**并**利用**
> 这些经历，来适应一个**表面上完全陌生**的问题？

### 与 025 / 027 / 028 的分工（明确切开）

| 实验 | 问题 | 结果 |
|---|---|---|
| **025 / v3** | 过去能不能**留下**？ | ✓ 明显（1.142，参数集合 78.3% 同向） |
| **027** | 留下的 personality 会**自动迁移**吗？ | 极弱（0.08 trial，低于功能门槛） |
| **028** | 多读一些 personality history 能救吗？ | 没有（G ≈ 0，等预算下无增益） |
| **★ 029 ★** | 过去的经验能否被**真正检索**并用于**类比**？ | ← 新问题 |

### 029 为什么不是 028 的续集

028 已经把"读得更宽"这条路走完了（G = −0.002，CI [−0.031, +0.023]，
对接入符号稳健），而且 **027 A 在新 sampling block 上没有复制**
（E_A = −0.039，CI 含 0，点估计减半）。

所以 029 换掉的必须是**通路的类型**，不是带宽：

```
027 / 028   历史 → 我们替它读出的一个标量 → β → 探索加成
029         历史 → 可寻址的条目 → agent 自己按相似度取用 → 决策
```

⚠ **如果 029 最后退化成"experimenter 挑一个更好的 readout"，
它就是 028 的第三个臂，不该单独立项。**

---

## ② development history：★ 先不要碰 rich / poor ★（已定草案）

029 **不用** v3 的丰富/贫瘠世界。重新造一套非常干净的小型 learning history。

### Stable history

过去遇到**多个**问题，规则**从不反转**：

```
Problem 1     X 比 Y 好  →  一直如此
Problem 2     ○ 比 △ 好  →  一直如此
Problem 3     左 比 右 好 →  一直如此
```

### Volatile history

问题数量、reward magnitude、trial 数**完全相同**，但每个问题都出现 change point：

```
Problem 1     X 好  →  后来 Y 好
Problem 2     ○ 好  →  后来 △ 好
Problem 3     左 好 →  后来 右 好
```

### ★ 三条纪律 ★

1. **stable / volatile 不是性格。** 它们只是让 agent 拥有**不同的经验库**。
   （这正是与 027/028 的分界：那两个实验做的是 trait；029 做的是经验。）
2. **所有具体符号都 counterbalance。** 学到的**不能**是
   ~~"B 后来总会变好"~~，而必须是
   **"过去有效的 relation 有时会失效"**。
   只有抽象到 relation 这一层，以后才谈得上迁移。
3. 两条历史的**数量、幅度、trial 数逐项相等** —— 唯一差异是有没有 change point。
   （承规则 67 / 026：两个发育世界必须同等新颖。）

⬜ 未定：problem 数（暂定 3）、每个问题的 trial 数、change point 的位置分布、
   符号 counterbalance 的具体排布方案。

---

## ③ 记忆到底是什么（已定草案）

**不复用**现在的自传体结构：

```json
{"event": ..., "day": ..., "importance": ..., "text": ...}
```

它存的是"发生了什么"，适合 autobiographical memory，
**不足以做 causal transfer** —— 它没存"什么关系起了作用"。

029 单独建一个实验层结构：

```
Episode:
    context               关系性情境标签
    previous_expectation  当时对手上这个策略的预期
    observation           实际观察到的回报
    prediction_error      observation − previous_expectation
    action_relation       ★ "stay" / "switch" ★
    outcome               采取该 action_relation 之后拿到的回报
```

例：

```
旧选项过去一直好 → 连续收到异常低奖励 → stay   → 仍然失败
连续异常低奖励                        → switch → 奖励恢复
```

### ★★ 最重要的一条：存 stay/switch，不存 A/B ★★

存了 A/B，换一个新任务之后就没有任何可迁移性 —— 新任务里根本没有 A 和 B。
**存关系才可能迁移。**

✅ 已实现为硬约束：`memory_transfer_probe.py` 的
`Episode.__post_init__` + `_assert_relational_only()`，
字段里出现任何选项身份直接报错。

---

## ④ 检索（第一版：一个 relational query，故意极简）（已定草案）

第一版**不需要**"真正智能"的检索。只要一条关系查询：

```
当前状态：  手上这个策略过去一直很好  +  最近连续 prediction error
                    ↓
检索：      过去有没有出现过 "previously-good strategy + persistent surprise"
                    ↓
记忆返回：  那种情况下 stay 之后回报怎样、switch 之后回报怎样
                    ↓
evidence：  mᵢ = E[R | switch, similar past] − E[R | stay, similar past]
                    ↓
决策：      logit(switch) = base_learning + λ·mᵢ
```

query 不成立时 **m = 0，记忆不进入决策** —— 检索是**情境触发**的，这正是重点。

### ★ 与 027 的本质差异 ★

```
027    traitᵢ → βᵢ                                      我们替它读一个标量
029    current situation → retrieval → past outcomes → evidence → choice
```

后者才是真的"**我现在遇到了这个情况，所以我想起以前类似的情况**"。

### ★ (a) stateful retrieval（v2 已实现）★

v1 是 one-shot：想起过去 → 推一下这一刀 → 马上忘掉刚才想起来的东西。
那是 priming，不是 memory-guided adaptation。改成状态机，
**不用"固定保持 N trial"**（那会新增一个任意参数）：

```
NORMAL →（连续 persistent surprise ≥ SURPRISE_RUN_MIN 且手上策略过去很好）
       → RETRIEVE：记下 suspect strategy
       → ACTIVE：m 持续进入 working decision state
ACTIVE →① Q[另一个] > Q[suspect]              "哦，看来真的变了"   → RESOLVED
       →② 在 suspect 上连续 SURPRISE_RUN_MIN 次不再意外
                                              "刚才只是偶然"      → RESOLVED
```

两个 resolution 条件**只用已有量**（Q、pe、`PE_THRESH`、`SURPRISE_RUN_MIN`），
**零新增参数**；②与入场条件对称（进场要连续 3 次意外，出场也要连续 3 次不意外）。

★ **ACTIVE 期间 m 作用于 suspect，不是作用于"switch 这个动作"** ★

```
logit(switch) += λ · m · s      s=+1 若 switch 是【离开】suspect
                                s=−1 若 switch 是【回到】suspect
```

v1 每 trial 都把 `+λm` 加在 switch 上 —— 推成一次切换后，下一 trial 就变成
"再换回去"，语义错误、会来回抖。新写法才是"**我怀疑规则变了**"，
而这个怀疑会持续到被确认或被打消。

⚠ `suspect` 是决策时的**工作变量**，不是 Episode 字段 —— 规则 85 不变。

### ★ 铁律（承 028）★

> **检索通道更强 ≠ 给历史更大权重。**
> 029 同样要有**等预算**对照，不许靠调大 λ 赢。
> 028 的 quantile mapping 是现成可复用的做法。

⚠ 但"等预算"**不等于**"等 exposure" —— 见规则 87（下面 §⑥）。

⬜ 未定：λ 的值（**今天只扫不选**）、
   `GOOD_THRESH` / `PE_THRESH` / `SURPRISE_RUN_MIN` 三个阈值的正式值
   （目前是 probe 旋钮，未校准，正式值必须走 group-blind 校准）。

---

## ⑤ 什么结果算 029 失败？怎么在跑之前就知道设计是干净的？

**（草案，待拍板）**

### 三值判读（承规则 56 / 79）

| 情况 | 判读 |
|---|---|
| CI 包含 0 | 没有证据表明结构相关经验被因果使用 |
| CI > 0 但与 [0, SESOI] 重叠 | 检测到效应，但**低于功能门槛** |
| CI 整体 > SESOI | functionally meaningful retrieval-conditioned adaptation |

### 预先承认的失败模式

1. **识别性探针不通过** → 机制根本没有能力影响 outcome，**不许跑 group comparison**。
   ← v1 卡在这里；v2 已通过（见 §⑥）。
2. **校准阶段找不到 group-blind 合格参数** → 判该设计不干净，按 026 封存。
   **绝不放宽标准去救它。**
3. **Stable 与 Volatile 都没有效应** → 阴性结果，照写。
4. **有效应，但 memory-blind 消融不掉** → 通路未识别，不许声称"检索"。

### ★ 跑之前就写死：029 阴性也有信息量 ★

核心命题现在是 **Persistent individuality ≠ automatically functional
generalization.** 029 若也 ≈ 0，命题不变，只会加强为
"即使给它一条**真正的 episodic 检索通道**，仍然……"。

**这一段现在就写死，防止跑完之后为了拿阳性而回头改设计。**

### 措辞纪律

- ⛔ 不许写 *analogical reasoning* / agent "理解了结构"
- ⛔ 不许写 *generalized individuality*
- ✅ 可写：**retrieval-conditioned adaptation to a surface-novel task**

### ★ endpoint 结构（v4 定）★

```
Primary candidate    ΔC = post-change cumulative errors（反转后 40 trial 选错次数）
                     C_i = Σ_{t=40..79} 1(choice_t ≠ correct_t)   ΔC<0 = 记忆有帮助
Secondary mechanistic  restricted switch latency / retrieval exposure /
                     per-opportunity potency / ACTIVE duration / realized retrieval
```

> **规则 89**：primary endpoint 不能与机制自身的活跃窗口构造性重叠。
> `ACTIVE` 退出 ≈「Q 证明新策略更好」，latency ≈「新策略开始稳定占优」——
> 天然绑在一起，所以 latency **降级为 secondary mechanistic**。

ΔC 的好处：窗口由任务事先固定 / 不读 ACTIVE 或 RESOLVED / 无 never-switch
censoring / 所有 agent 都有 / 单位是 trial，好定 SESOI / 测的就是实际 functional cost。

⬜ 未定：SESOI 的单位与数值（今天**不定**）。

---

## ⑥ ★ 2026-08-18 识别性探针结果（v1 → v2）★

程序**故意不叫** `experiment029.py`，叫 `memory_transfer_probe.py` ——
今天只问一件事：**这条机制有没有能力影响 outcome。**
底座 = 027 的任务，一个数没改；种子 = development 段 `0–399`；**80000–81499 没碰**。

### v1（one-shot retrieval）—— positive control 通过、SWAP dominance 未通过

```
工程自检   关系性约束 / 确定性 / memory-blind(λ=0)   全过
正控制     λ=1：17.8% 轨迹改变，Δlatency −0.125，方向正确
诊断       检索平均只在 0.69/80 个 trial 上进入决策；body 的 β 在 80/80 上
           触发时 base p(switch) 中位数 0.208 → 决策没饱和，记忆有发挥空间
```

### ⛔ dominance criterion 正式撤回 ⛔

> Original SWAP dominance criterion `|memory| > |body|` failed at all tested λ,
> after which inspection showed that the criterion compared an event-triggered
> channel active on ~0.69/80 trials with an always-on trait channel.
> The dominance criterion was therefore **retired before any Stable/Volatile
> outcome was observed**.

**撤回理由不是"它没通过"，而是它测的不是我们想知道的东西。**
v1 文件与结果**原封保留、不覆盖** —— 这条失败本身是方法学记录。

### 新 SWAP estimand

```
M_C = L(Body C, Mem V) − L(Body C, Mem S)
M_K = L(Body K, Mem V) − L(Body K, Mem S)
M   = (M_C + M_K)/2
```

关心：① M_C / M_K 方向一致性 ② pooled M 是否在预注册方向
③ 是否超过功能 SESOI（**今天不定**） ④ Body×Memory interaction
**body effect 只作 robustness diagnostic，不再是闸门。**

### ★ 规则 87（修正规则 86 的方向）★

> memory 与 personality **本来就不该有相同 exposure**：人格是一直存在的 prior，
> 记忆应该**遇到相关情况时才被调用**。强行让 memory 80/80 在线，
> 会毁掉本设计最重要的理论特征 —— **context-dependent retrieval**。
>
> 对 event-triggered 机制，**不能直接拿 endpoint effect 与 always-on 机制比大小**；
> 必须把 **exposure** 与 **per-opportunity influence** 分开报告。

### ★ 规则 88：potential vs realized retrieval ★

> `fired` 本身受前面 choice sequence 影响（cautious body 更容易连续 stay 三次）
> —— 触发次数本身就是 task dynamics 的产物。
> ```
> potential   在 memory-blind（λ=0）轨迹上定义 → 机制 exposure
> realized    memory-enabled 轨迹上实际发生   → 结果的一部分
> ```
> ⛔ 绝对不许只分析"成功想起了记忆"的 agent —— survivor conditioning。
> 已写成断言：所有汇总必须用全部 400 个种子。

### v2（stateful retrieval）—— 阈值/任务/种子一个没动

```
① ② EXPOSURE        eligible 种子   potential   realized(λ=1)
   v1 one-shot          45.0%         0.75         0.69
   v2 stateful          45.0%         7.18         6.96      ← 9.6×
   仍是 event-triggered（7.2/80），没有被拉成 80/80。这是对的。

③ POTENCY（λ=0 冻结 decision state 上反事实换记忆）
                     机会数   base p 中位数   饱和   mean|Δp| (λ=1)
   v1 one-shot         300       0.208       0.0%      0.2205
   v2 stateful        2873       0.400       0.0%      0.2807
   → v1 的 per-opportunity potency 本来就不低。v1 缺的是 exposure，不是 potency。

④ 新 SWAP        M_C      M_K   pooled M      95% CI（描述性）   方向一致  interaction
   v1  λ=1     −0.125   −0.083    −0.104   [−0.410, +0.215]      是      −0.042
   v2  λ=0.25  −0.875   −0.900    −0.887   [−1.343, −0.471]      是      +0.025
   v2  λ=1     −4.058   −3.920    −3.989   [−4.785, −3.231]      是      −0.138
   v2  λ=4     −9.607   −9.710    −9.659   [−10.815, −8.549]     是      +0.103
   ★ Directional SWAP check: PASS ★（两套机制、所有 λ 全部同号）
   interaction 相对 M 极小 → memory 不依赖某一种特定 body 才能工作
   CI 是描述性的（seed cluster bootstrap，n_boot=10000，分析种子 8181）；
   今天不定 SESOI，不做功能意义判读。

⑤ DOWNSTREAM（只作 consequence）  轨迹改变   Δlatency   Δ反转后正确率
   v1  λ=1                          17.8%     −0.125      +0.0029
   v2  λ=1                          43.2%     −4.058      +0.0535
   v2  λ=4                          45.0%     −9.607      +0.1688
   ⚑ λ=4 时 45.0% 恰好等于 eligible 种子比例 —— 上限是 eligibility，符合构造。
```

> ### ★ 探针阶段结论 ★
> **v1 的问题确实是"retrieved evidence 没有形成持续的 decision state"，
> 不是 λ 不够。** 阈值、任务、种子一个没动，只把检索改成 stateful，
> pooled M 就从 −0.10 走到 **−3.99 trial**（λ=1，38×）。

### ⚠ 风险方向已经翻转（留给校准）

```
机制现在可能【太强】：λ=4 时 −9.7 trial，而 latency 量程只有 0–36。
手工记忆处在【最大可能对比度】（m_S=−0.667，m_V=+0.667）。
真实 Stable/Volatile 历史产生的 |m| 会小得多。
→ −4 trial 是【最大记忆对比度下的上界】，不是预期效应量。
```

⚠ 另一条要盯住：**ACTIVE 窗口与 latency 终点在构造上重叠**
（怀疑大致在切换成功时解除）。做强结论前需要一个**不由同一窗口定义的终点**。

### 仍然不是 029 scientific success

记忆是手工造的、λ 没冻结、Stable/Volatile 根本还没跑。

---

## ⑦ ★ acquisition 阶段（2026-08-18 起）★

**手工 memory probe 阶段结束。下一步不是校准 λ。**
在不知道真实 Stable/Volatile 到底产生 m = 0.03 还是 0.30 之前，
争论 λ 取 .25 还是 1 没有科学意义。正式顺序：

```
修 resolution bug → 锁 independent endpoint → 造真实 Stable/Volatile histories
→ 让 history 自己生成 Episode → 观察真实 memory evidence 分布 → 最后才校准 λ
→ acquisition+memory+novel task 接起来，做 DELETE / SWAP / SHUFFLE rehearsal
→ 全部冻结后才写 029 preregistration、SESOI 和 fresh final seeds
```

### 设计：两边都经历 surprise

```
t <  20     原策略 p_high、另一个 p_low        ← 两条件相同
t 20–27     ★两个都掉到 p_low★                ← 两条件【逐位相同】
t ≥  28     Stable：原策略恢复 / Volatile：另一个变好
```

**光看异常本身分不出身处哪个世界**，差异只在"这次异常意味着什么"。
（已核 100 种子 ×3 问题：t<28 逐位相同。）

### 结果：方向完全正确

```
             n(可定义 m)   mean m     SD      中位数     m>0 比例
Stable            94      −0.3783  0.3410   −0.4000       8.5%
Volatile          96      +0.5257  0.2240   +0.5000     100.0%
分离度 +0.9040   手工版 +1.3333   → 真实经历达到手工版的 67.8%
```

matching：① 总 trial 数 ② 总 reward opportunity ④ first-good side **逐位相等**；
③ episode 数 2.88 vs 3.67（行为产物，报告）。

### ⚠ 卡点：yield 只有 24%

```
episode completeness   Stable 23.5%   Volatile 24.0%
→ 约 3/4 的 agent 发育结束时【根本没有可用记忆】
yield 诊断（每 problem）：异常起点 Q≥.60 只有 57.8%；曾达成 stay-run≥3 为 57–77%；
                        两者同时 17.2%
```

> **规则 90**：入场条件的两半在构造上互相拆台 —— 要求"策略仍被信任（Q≥.60）"
> 且"连续三次失望"，但每次失望都在压 Q。**卡的是前一半** →
> 该动的是**异常前的经验量**，不是 surprise 那一半。
> ⛔ 绝不许用"只分析长出了记忆的 agent"绕过（规则 88）。

### caveat：realized reward 无法匹配

Volatile 总收益更低（73.19 vs 82.99），因为 change point 后要重新学。
opportunity 已逐位匹配；realized reward 要匹配就等于取消 manipulation 本身。
**记录、不修。**

### 本阶段只许看上游

```
✅ episode 数 / surprise 数 / stay-switch 数 / reward marginal / m 分布 /
   completeness / manipulation check / matching diagnostics
⛔ novel-task latency  ⛔ post-change errors  ⛔ Stable vs Volatile transfer effect
```
**代码里也没有这些量。** 这样才保留调 acquisition 的自由，
而不会开始围着 final outcome 调设计。

### λ 最后怎么定

等真实 m 分布出来后，用 **不看 transfer outcome** 的办法：
拿真实 acquisition memory 在 burned development seeds 上的 empirical |m|，
只做 **frozen-state counterfactual potency** `Δp_t(λ)`（probe3 已写好这套 pipeline），
按 **不饱和 / 有实质但不过强 / memory 保持 event-triggered** 去冻结 λ。

> **λ 是按接口容量定的，不是按"Stable/Volatile 最后谁赢得漂亮"定的。**

---

## ⑧ ★ acquisition 冻结 + λ 接口容量校准（2026-08-18）★

### 冻结的 acquisition candidate

```
ANOMALY_AT  = 36   （原 20；只加 anomaly【前】的学习长度）
ANOMALY_LEN =  8   （不变）
T_PROBLEM   = 66   （anomaly 后仍为 22，与原来相同）
GOOD_THRESH / PE_THRESH / SURPRISE_RUN_MIN / problem 数  ★一律不动★
```

纯上游 sweep（未接 novel task）显示：**增加 pre-anomaly experience 主要修 yield，
几乎不改 memory contrast** —— 干净的 engineering correction。
选 36 是 **elbow**（20→36 换 +42/+49pp；36→40 只再换 3–4pp），
**不是**挑 separation 最大的点。

```
pre-anomaly   Stable comp.   Volatile comp.   complete-only 分离度
    20           23.5%           24.0%            +0.904
★   36 ★         65.8%           73.3%            +0.894
    40           69.5%           76.8%            +0.884
```

### ★ 规则 91：memory availability 本身就是发育结果 ★

> Memory availability is itself a developmental outcome. Do not condition
> transfer or calibration on successful memory formation. Report the extensive
> margin (P[m usable]) and intensive margin (m | usable) separately, but all
> primary analyses use the full predefined population.

```
            extensive P[m 可用]   intensive mean(m|可用)   全体 mean m   全体 median
Stable            65.8%                 −0.4099            −0.2695       −0.2440
Volatile          73.2%                 +0.4842            +0.3546       +0.4099

population 分离度（含 m=0）= +0.6241  ★真值★
complete-only 分离度        = +0.8940  ⚠ 夸大（手工版 +1.3333）
```

- yield 不相等（65.8% vs 73.2%）**不修** —— 强行配平 = 修改 post-treatment mediator。
- 未来把 memory effect 拆成 **extensive margin**（有没有形成可用 relational memory）
  与 **intensive margin**（形成了的话方向多大），由 SWAP / DELETE / SHUFFLE 检验因果。
- realized reward（117.24 vs 103.42）同样**不修**：补平它 = 取消 volatility 的成本。
  该匹配的是 trial opportunity / reward schedule 机会量 / first-good identity /
  pre-anomaly observations / task length —— 这些已逐位相等。

### λ 接口容量校准（group-blind，结构性保证）

```
pooled_empirical_m()  两 condition 汇入同一池 → ★含 m=0★ → 排序（摧毁分组对应）
输入 n=800  mean +0.0426  |m| 中位数 0.3571  ★m=0 占 31.2%★
Δp 口径 = 相对"没有记忆"的反事实；states 取自 λ=0 memory-blind 轨迹（2708 个）
```

```
   λ    median|Δp|   推后饱和   P(翻转偏好)   exposure     三判据
 0.25     0.0182       0.0%        3.2%      6.80/80    ✗②（微不足道）
 0.50     0.0363       0.0%        6.6%      6.71/80    ✓✓✓
 1.00     0.0717       0.0%       13.4%      6.73/80    ✓✓✓
 2.00     0.1354       0.6%       24.8%      6.86/80    ✓✓✓（flip 踩在边上）
 4.00     0.2250      12.7%       33.5%      7.35/80    ✗①✗②
```

**合格带 λ ∈ {0.5, 1, 2}；建议 λ = 1.00**（带中心，两侧都不贴边）。
⚠ 三条判据的**数值阈值也待拍板**（当前是本文件的读数口径，非预注册值）。

> **λ 是按接口容量定的，不是按"Stable/Volatile 最后谁赢得漂亮"定的。**
> 校准模块里 condition label 在输入处即被丢弃，物理上算不出 group 差异。

---

## ⑨ ★ λ 冻结 + rehearsal（2026-08-18）★

### 冻结（不再因任何 Stable/Volatile outcome 改动）

```
SATURATION_MAX = 0.05   MEDIAN_ABS_DP_MIN = 0.02
PREF_FLIP_MAX  = 0.25   ACTIVE_EXPOSURE_MAX = 20 / 80
MEMORY_LAMBDA  = 1.00
exposure gate 用 ★max(E[m10],E[m50],E[m90])★，不用 mean
```

四个数是 **engineering admissibility gates，不是 significance thresholds**。
用 max 是因为 event-triggeredness 不该允许"某一种 memory sign 已接近常驻、
却被另外两种平均掉"（λ=1 的 max exposure 只有 6.95/80，判定不变）。

> ### ★ 规则 92：selection rule 必须连"怎么选的"一起写死 ★
> Lambda was calibrated without condition labels or downstream transfer
> outcomes. Values were required to satisfy prespecified interface-capacity
> constraints on saturation, median probability shift, preference reversal,
> and retrieval exposure. Among admissible values, the log-scale midpoint of
> the admissible range was selected.
>
> 合格带 {0.5,1,2}，`1.0 = √(0.5×2)` 是 log 尺度中心 ——
> 选"距离上下失效方向最远的"，不是"potency 最大的"。代码里有断言。

### rehearsal（开发种子 0–399，非 FINAL）

```
臂          ΔC = C(V) − C(S)     95% CI（描述性）      相对 OWN
OWN            -0.927        [-1.202, -0.677]          1.00
DELETE         +0.000        [+0.000, +0.000]          0.00   ← 恒等
SWAP           +0.927        [+0.680, +1.202]         -1.00   ← 恒等
SHUFFLE        +0.087        [-0.068, +0.242]         -0.09   ★塌缩
SWAP-XS        -0.890        [-1.140, -0.660]          0.96   ★保留
```

> ### ★ 规则 93：只有一条通路时，DELETE / SWAP 退化为断言，不是证据 ★
> body 常数 + 发育史只经记忆进入任务 → 同种子两 condition 只差记忆，
> 于是 `DELETE ≡ 0`、`SWAP ≡ −OWN` 在**构造上必然成立**。
> 它们证明的是"**没有第二条泄漏通路**"，不是"记忆有因果作用"。
>
> **要让 SWAP 成为非平凡检验，发育史必须还携带记忆以外的东西**
> （例如 027/028 的 trait 通路）。← ★ 这是真正 029 待拍板的第一件事 ★

真正有信息量的两个控制都符合预期：
**SHUFFLE**（保留 episode 数 / stay-switch 条数 / outcome 边际，只打乱
action↔outcome 关系）→ ΔC 塌到 OWN 的 −9.4%，CI 跨 0
→ **效应来自关系结构，不是 marginal statistics**；
**SWAP-XS**（跨种子重新配对）→ 保留 96%
→ **效应由记忆内容携带**，不靠发育-测试共享种子的耦合。

### ⚠ extensive margin 的两个定义不要混用

```
usable（m ≠ 0）          Stable 64.2%   Volatile 73.2%
complete（两侧都有条目）  Stable 65.75%  Volatile 73.25%
```
差在 6 个 Stable agent（1.5%）两侧都有条目但均值恰好相等 → m=0。**报哪个就一直报哪个。**

### 还差什么才能写预注册

```
① 发育史是否还要携带 trait 通路（否则 SWAP 永远是恒等式）—— 规则 93
② SESOI（ΔC 单位是 trial，现在 OWN ≈ 0.93）
③ fresh final seeds（80000–81499 仍干净）
④ MEMORY_TRANSFER029_PREREGISTRATION.md
```

---

## 附：种子账本

```
0–1499          development（★ 今天的 probe 用 0–399 ★）
10000–11499     021 留出集 / 028 transport rehearsal
20000–21499     022 预注册段 / 027 + 028 group-blind calibration
50000–51499     v3 persistence FINAL
60000–61499     027 novel-task FINAL
70000–71499     028 breadth FINAL
80000–81499     ★ 029 FINAL 预留 ★  ← 已核实：全库从未作为种子出现
```

⬜ 未定：029 的 calibration / rehearsal 用哪一段（**不得**动 80000 段）。

---

## 附：今天暂时不做的事（写下来防止手滑）

```
⛔ 定 029 final seeds          ⛔ 写 preregistration
⛔ 定 SESOI                    ⛔ 决定 λ 最终值
⛔ 用新 final block            ⛔ 把 memory 直接加进 sim.py
⛔ 上 LLM / embedding          ⛔ episodic + semantic + abstraction 三套同时上
⛔ 看 Stable vs Volatile 的正式差异
⛔ (b) 放宽 SURPRISE_RUN_MIN    ⛔ (d) 多 change-point 任务
```

**(b) 为什么不做**：v1 已证明触发时决策没饱和（base p=0.208），
不是"想起来太晚"。3→2 只是让记忆更早出现，**没解决"一出现就被清掉"**——
那是治数量，不是治机制。
**(d) 为什么不做**：一次 reversal 变三次，exposure 自然变多，
结果变强时分不清是"机制修好了"还是"同一个弱 one-shot 效应重复三遍"。
(d) 该在单 change-point 上把机制搞对之后再做，那时它是
**dose-of-opportunity robustness test**。

我们现在还在问：**这条机制本身有没有可识别性？**
和 026 当时一样，先证明"实验有能力测到它声称测的东西"。

---

## 附：待办

- [x] ② development history 换成 stable / volatile（不碰 rich/poor）
- [x] ③ 029 自己的 Episode 结构（存 stay/switch，不存 A/B）
- [x] ④ 极简 relational retrieval + `logit(switch)=base+λm`
- [x] ⑥ positive control + SWAP test 跑出来
- [x] **(c) SWAP 判读口径** —— dominance 撤回，改 M_C/M_K/pooled M + 方向一致性
- [x] **(a) stateful retrieval** —— RETRIEVE → ACTIVE → RESOLVED，零新增参数
- [x] exposure × potency 分解（规则 87）+ potential/realized 分离（规则 88）
- [ ] ② 的 problem 数 / trial 数 / change point 分布 / counterbalance 排布
- [ ] 三个阈值的 group-blind 校准方案
- [ ] ⑤ SESOI 的单位与数值
- [ ] calibration 种子段

---

## 版本记录

| 版本 | 日期 | 改了什么 |
|---|---|---|
| v1 | 2026-08-18 | 初稿。① 写死；②–⑤ 为草案，全部待拍板 |
| v2 | 2026-08-18 | ② 改为 stable/volatile（不碰 rich/poor）；③ 定 Episode 结构；④ 定极简 retrieval + 决策规则；新增 ⑥ 探针结果：**positive control 通过、SWAP 未通过**，诊断为 exposure 不对称 |
| v7 | 2026-08-18 | **不加 trait 通路**（规则 93 最终版：不能为了让控制非平凡而增加第二条发育通路）；`SWAP-XS` 改名 **XSEED-DONOR**；extensive margin 正式选 **completeness**（规则 94：m=0 是有意义的零证据，不是"没有记忆"）；**SESOI = 1.0 post-change error** + 三档判读；SHUFFLE 冻结为 **retention ratio R**（判据 A/B 待拍板，实测 R=0.094，CI [0.005, 0.261]）；**FINAL 80000–81499 N=1500 冻结**；预注册写成 → 本文件定格 |
| v6 | 2026-08-18 | **λ=1.00 与四个 capacity gate 正式冻结**（exposure gate 改用 max）；**规则 92** selection rule 写死（合格带 log 中心，附断言）；跑完 OWN/DELETE/SWAP/SHUFFLE rehearsal：OWN ΔC=−0.927、**SHUFFLE 塌到 −9.4%**、**SWAP-XS 保留 96%**；**规则 93** —— 单通路下 DELETE/SWAP 是代数恒等式，只能当断言；非平凡 SWAP 需要发育史再带一条通路 |
| v5 | 2026-08-18 | 冻结 acquisition candidate（ANOMALY_AT=36/LEN=8/T=66，只加 pre-anomaly 学习长度，yield 24%→66–73%）；**规则 91** extensive/intensive margin 分开报、primary 用全体人群（population 分离度 +0.624，complete-only +0.894 会夸大）；yield 与 realized reward 的不匹配**均不修**；跑完 group-blind λ 接口容量校准，合格带 λ∈{0.5,1,2}，建议 λ=1 |
| v4 | 2026-08-18 | 修 resolution 时序 bug（v3，效果缩水故事不变，旧结果保留）；**规则 89** latency 降级、ΔC 定为 primary candidate；新建 `memory_acquisition_probe.py`：真实 Stable/Volatile 长出的 m 方向正确、分离度达手工版 67.8%，但 **completeness 只有 24%（规则 90）**；正式顺序改为"先 acquisition，最后才校准 λ" |
| v3 | 2026-08-18 | (c) **dominance 判据撤回**，换成 M_C/M_K/pooled M；规则 86 方向修正 → **规则 87**（exposure × potency 分开报告）；新增**规则 88**（potential vs realized retrieval，禁 survivor conditioning）；(a) **stateful retrieval** 实现并跑通：**Directional SWAP check PASS**，pooled M −0.10 → −3.99；风险方向翻转为"机制可能太强" |
