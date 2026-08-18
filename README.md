# LifeEngine

一个**纯 Python、零 LLM、无第三方依赖**的人工生命 agent-based model。

它是一台**最小装置**，用来检验一个问题：

> **发育期的不同经历，会不会在移植到同一环境之后仍然留下差异？
> 如果会，这些差异能不能被用在一个陌生的新问题上？**

⚠ 它**不是**在模拟人格形成。所有结论都限定在这台装置内部。

---

## 主要结果

| 实验 | 问题 | 结果 |
|---|---|---|
| **v3 / 025** | 过去能不能**留下**？ | **能**。移植后逐时辰动作分布的 TV 比值 **1.142，95% CI [1.098, 1.183]**（预注册，只跑一次） |
| **027** | 留下的 personality 会**自动迁移**到新任务吗？ | **极弱**（0.08 trial），且在新采样块上**未能复制** |
| **028** | 等 coupling budget 下**加宽**历史读取接口能救吗？ | **没有增益**（G ≈ 0，且对接入符号稳健） |
| **029** | 真实经历长出的**关系性记忆**能否被检索并因果使用？ | **能，但未达功能门槛**（见下） |

### 029 FINAL（种子 80000–81499，N=1500）

```
ΔC = -0.8833     95% CI [-1.0160, -0.7533]     SESOI = 1.0 post-change error
→ Detectable memory-mediated transfer,
  but functional significance not established.

SHUFFLE retention  R = 0.0106   CI 上界 0.1102 < 0.25
→ ≥75% attenuation established：效应由【关系结构】承载，
  而不是记忆库的 marginal statistics

XSEED-DONOR 保留 104.6%  →  效应不依赖发育与测试共享种子
四个 validity gate 全部通过
```

**合起来说明的是**：把发育史压成一个 personality readout 送进新任务，几乎不携带
可复制的功能迁移；但当发育史以**关系性经验**的形式被存下、并在结构相似的情境中
被检索时，它确实能因果性地减少新问题中的错误 —— **只是幅度小于 1 个
post-change error，没有跨过预先定下的功能门槛。**

⛔ 本仓库**不声称** agent "学会 / 理解 / 意识到"任何东西，
也不声称 analogical reasoning 或 generalized individuality。
每条 claim 的边界见 [`CLAIMS.md`](CLAIMS.md)。

---

## 方法纪律

这个项目的大部分工作量在**防止自己骗自己**：

- **预注册在先**。每个确认性实验先写死假设、endpoint、SESOI、判读规则与统计程序，
  之后一个字不改。看到分组效应后**不得**修改任何关键设计。
- **种子账本**。每个确认性实验用一段**从未使用过**的种子；一旦开跑即永久 burned，
  绝不复用（`final_029_STARTED.lock` 一旦创建，哪怕程序崩溃也不删）。
- **group-blind 校准**。所有参数在**看不到分组差异**的前提下标定；
  找不到合格参数就判该设计不干净，**绝不放宽标准去救它**（实验 026 因此被封存为阴性结果）。
- **冻结与哈希**。`v2_frozen/`、`v3_frozen/` 各带 SHA256；
  `final_029.py` 开跑前校验 6 个模块的 sha256、任务指纹与预注册哈希，任一不符即拒绝运行。
- **失败照写**。被后续实验推翻的结论**保留原文**并注明撤回；
  协议偏离如实记录（见台账中的规则 98）。

⚠ `.gitattributes` 里的 `* -text` **不能删** —— 本项目用源文件 sha256 把关，
任何行尾转换都会让冻结校验失效。

---

## 目录

```
sim.py, scenarios.py, behavior.py …      模型核心
v2_frozen/ , v3_frozen/                  两个冻结版本（各带 SHA256）
                                         v2→v3 唯一可执行差异是一个常量
novel_task.py                            027/028/029 共用的新任务底座
memory_transfer_probe{,2,3}.py           029 机制识别性探针（v1 one-shot →
                                         v2 stateful → v3 时序修正）
memory_acquisition_probe.py              Stable/Volatile 发育史 → 关系性记忆
memory_lambda_calibration.py             group-blind 接口容量校准（λ 由此冻结）
memory_transfer_rehearsal.py             OWN/DELETE/SWAP/SHUFFLE 彩排
final_029.py                             029 FINAL runner（seed guard + 一次性 lock）
*_result.txt                             各实验的结果落盘
tests/                                   自检与回归
docs/                                    预注册、设计演进、完整实验台账
```

### 文档

| 文件 | 内容 |
|---|---|
| [`REPRODUCE.md`](REPRODUCE.md) | 三层复现：自检 / 烟测 / 完整复现 |
| [`CLAIMS.md`](CLAIMS.md) | 每条 claim 的证据等级 + **禁止措辞表** |
| [`ODD.md`](ODD.md) | 标准 ODD 模型描述 |
| [`docs/MEMORY_TRANSFER029_PREREGISTRATION.md`](docs/MEMORY_TRANSFER029_PREREGISTRATION.md) | 029 预注册（`final_029.py` 校验的就是它的 sha256） |
| [`docs/MEMORY_TRANSFER_DESIGN.md`](docs/MEMORY_TRANSFER_DESIGN.md) | 029 设计 v1→v7 的演进记录 |
| [`docs/模拟实验记录.md`](docs/模拟实验记录.md) | 完整实验台账，规则 1–98（含被撤回的原文） |
| `FINAL_PREREGISTRATION.md`, `NOVEL_TASK*_PREREGISTRATION*.md` | v3 / 027 / 028 的预注册与修订 |

---

## 运行

```bash
pip install -r requirements.txt   # 只有 pytest，用于自检
pytest                            # < 1 分钟，全绿即环境正常
```

只需要 **Python 3.10+ 与标准库**。完整复现见 [`REPRODUCE.md`](REPRODUCE.md)。

⚠ `final_029.py --final` 会**永久烧掉** `80000–81499` 这段种子，且该实验**已经跑过**
（`final_029_STARTED.lock` 已存在，runner 会拒绝重跑）。要看它的行为请用
`--rehearse`，它在已烧的开发种子段上跑同尺寸彩排。

⚠ `final_029.py` 里的 `PREREG_PATH` 指向作者本机的 vault 路径，clone 后该项会显示
"找不到预注册"。这是 FINAL 跑完时的历史状态，**刻意不修改**。
复现者可直接核对副本哈希：

```
sha256(docs/MEMORY_TRANSFER029_PREREGISTRATION.md)
  = 29e45930a07f2649c7958fdc0cd20a389005ca43e93287b9f69e2ccdcf867145
```
