---
name: efficiency-inspector
description: Prompt-led audit of Codex Better Plan conversations for main-thread Token efficiency, supervision effectiveness, child workload, and timeout-to-runtime alignment. Use when discovering and comparing inefficient behavior across Better Plan conversations, measuring Token input/output, sampling Designer/Worker/Reviewer or FSM execution time, or studying their distributions. Treat Token usage and elapsed time as separate measurement dimensions. Prefer concurrent child auditors for broad searches, while adapting the execution strategy to available capacity. Current raw-evidence support is Codex-only; bundled scripts are optional calculators over normalized observations.
---

# 效率督查

## 任务定位

探究主线程在 Better Plan 全流程中的经济效率。观察主线程的等待、监督、调度、状态推进、返工
和超时行为，统计它们的发生条件、Token 用量与持续时间分布，再提出可以通过后续样本验证的
Better Plan 优化方向。

把 Token 与时间作为两个并列的计量维度：Token 描述模型上下文和生成用量，时间描述任务、
命令与等待的持续过程。分别计算、分别报告，再通过同一根对话、阶段或行为标签分析两者关系；
不要把它们相加成一个数或当作同一种量。

## 执行者的工作

把这项工作当作需要理解上下文的调查。充分使用对话读取、搜索、时间线、工具调用及结果、Token
usage、父子会话关系和 Better Plan 状态记录：

1. 从对话中定位根任务、子任务、角色、阶段、关键决策和状态变化。
2. 沿时间线关联模型响应、工具调用、工具结果、Token usage、任务开始与终态。
3. 结合行为发生前后的状态，判断它在推动任务、降低风险、解除阻塞还是制造重复成本。
4. 给观察记录选择行为标签和有效性，并在 shard finding 中简要说明判断理由。
5. 复核高 Token、高耗时和结论边界附近的样本，必要时调整分类或补充新的行为标签。
6. 汇总分布、解释形成机制，并提出下一轮可验证的优化实验。

标准化记录服务于统计，不替代执行者的理解。遇到新的对话结构或行为类型时，可以扩展标签、
修改或组合任务内工具，并清楚说明采用的方法。

## 监督行为与有效性

监督行为是主线程为了组织、观察、校验或推进子智能体及 Better Plan 工作流而采取的动作，例如
任务拆分、派发、等待、状态查看、消息沟通、依赖协调、结果审阅、纠正、重试和 FSM 状态推进。

结合具体上下文判断监督是否有效：

- **有效监督**：获得了下一步决策需要的新信息；建立或修正了任务所有权；解除依赖或阻塞；
  发现并纠正实质问题；完成必要验收或状态推进；以合理频率观察长任务。
- **低效监督**：重复读取未变化状态；过密唤醒却没有形成新决策；重复发送等价指令；因分派不清
  导致返工或重复劳动；主线程无必要地重做子任务；协调消耗明显超过它带来的信息或风险降低。
- **混合监督**：同一段行为既产生有效结果又包含可分离的重复成本。保留为 `mixed`，并解释组成。

超时等待只是判断线索，不自动等于低效；成功唤醒也不自动等于有效。比较行为目的、当时可用
信息、状态变化和后续决策，发挥执行者的分析能力。

## 工具分工

执行智能体负责发现对话、读取原始轨迹、识别父子谱系、关联事件、分类行为、判断监督有效性、
解释原因和提出建议。两个附带计算器只处理执行智能体已经写好的标准化 JSONL：

- `scripts/token_totals.py`：按 scope、kind、behavior 和 assessment 加总 Token 并计算比率；
- `scripts/timeout_summary.py`：校验执行—超时关联并生成描述性统计。

计算器保持简单、独立、可组合。执行者可以为单次审计修改、裁剪、组合或新写工具；一次性能力
留在当前任务，稳定复现的能力再考虑沉淀。阅读
[Agent 适配边界](references/adapter-boundary.md) 区分专用取证方法与通用计算。

## 并发建议

读取 [并发审计建议](references/parallel-audit.md)。大范围统计通常包含多个互不依赖的根对话，
宿主容量允许时，优先把它们分成互斥 shard 并发交给多个子审计员，以缩短搜索和取证时间。

令 `K` 为待审 shard 数，`C` 为可用子槽。推荐首波派发 `min(K, C)` 个审计员，再在槽位释放时
补派剩余 shard。容量、样本数量或依赖关系不适合并发时，采用串行或较小波次同样可以完成审计；
在报告中说明实际执行方式即可。等待在途审计员时优先使用集合式或事件驱动方式，宿主只提供
逐个等待时就按宿主能力执行。

## 数据目录

开始派发前阅读 [数据目录与并发写入](references/data-layout.md)。协调者创建一个批次目录和
manifest，为每个审计员分配独立的 token JSONL、timeout JSONL 与 finding 文件。每个文件只有
一个写入者；审计员可以反复完善自己的文件，交付后由协调者只读聚合。这样既支持并发，又避免
多人同时追加同一文件。

## 通用流程

1. 定义问题、样本范围、共同 UTC cutoff、批次标签和比较维度。
2. 创建批次目录、manifest、shard 所有权和输出路径。
3. 按宿主容量并发或串行搜索根对话；一个根及其相关后代归入同一统计 shard。
4. 执行智能体阅读上下文并生成 Token、超时观察记录及判断说明。
5. 协调者检查目录完整性，选择已完成的 shard 文件。
6. 按需运行轻量计算器；小样本也可以透明手算或使用其它数学工具。
7. 对比绝对量、比率、阶段、任务类型和异常值，形成结论与下一轮采样方案。

## 能力一：主线程 Token 效率

读取 [Token 发现、监督判断与计算](references/token-accounting.md)。对父线程和子线程的模型响应
统计输入、缓存输入和输出 Token：

```text
uncached_input_tokens = input_tokens - cached_input_tokens
total_tokens = input_tokens + output_tokens
```

按 `scope` 区分父线程和子线程，按 `kind` 区分监督与任务工作，用开放的 `behavior` 标签描述
等待、派发、审阅、纠正、状态推进等具体行为，再由执行者给出 `effective`、`inefficient`、
`mixed` 或 `neutral` 判断。

需要批量加总时，在技能目录执行：

```sh
python3 scripts/token_totals.py \
  --input shard-001.jsonl shard-002.jsonl \
  --output token-summary.json
```

重点比较主线程低效 Token、有效与低效监督占比、监督总量、父子线程总量、系统效率和委派杠杆，
并回到对话解释高消耗行为为何发生。

## 能力二：超时统计

读取 [超时统计与关联采样](references/timeout-statistics.md)。固定目录当前有 `N = 7` 个策略项：
三个角色观察窗口、三个 FSM 命令执行期限和一个显式生命周期 Hook 期限。报告全部 N 项，并区分
策略维度数 `N` 与执行样本数 `M`。

一个 Designer、Worker 或 Reviewer 执行形成一个真实运行时间样本，可以关联多次等待设置。
观察窗口描述主线程观察节奏，执行期限描述命令或 Hook 的运行边界，分别分析。执行者从开始、
结束、回调、状态和时间戳中重建真实运行时间，并说明关联方式。

```sh
python3 scripts/timeout_summary.py \
  --input shard-001.jsonl shard-002.jsonl \
  --output timeout-summary.json
```

描述统计之后，根据样本结构选择 Kaplan–Meier、Aalen–Johansen、对数正态、Weibull、Gamma 或
聚类 bootstrap。由执行者检查异质性、删失、竞争结果和根对话聚类，再决定合适的数学方法。

## 报告要求

报告样本选择、根对话数、cutoff、执行方式和数据目录；分别给出 Token 与时间结果；说明监督行为
定义、有效性判断、主要分布、异常值、阶段差异、任务差异和判断理由；最后给出可验证的优化建议、
局限以及下一轮采样设计。

当前原始证据支持 Codex。扩展其它 Agent 时先建立专用取证配方或小型适配器，再输出相同的
标准化记录；通用计算器继续处理 Agent 无关的算术与描述统计。
