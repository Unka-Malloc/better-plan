# Token 发现、监督判断与计算

本能力教执行者从 Codex 对话中发现 Token 用量、理解主线程行为并评估监督效能。原始证据由
执行智能体读取和解释，计算器接收已经形成的观察记录。

## 从对话中发现 Token

以一个根对话及其相关后代为观察范围，冻结共同 UTC cutoff，然后沿时间线执行：

1. 定位根对话、子智能体派发、父子会话身份和角色。
2. 找出每个模型响应之后的 usage 事件或累计 Token 快照。
3. 将模型响应与它触发的工具调用、工具结果、状态变化和下一步决策放在一起阅读。
4. 优先使用响应级 usage；只有累计量时，通过相邻累计快照差值恢复该段用量。
5. 遇到压缩、回滚或累计重置时，按时间段分别对账，再合并已确认的分量。
6. 对子会话使用 cutoff 前最后累计量，并归入对应根对话。

记录以下向量：

```text
input_tokens
cached_input_tokens
output_tokens
uncached_input_tokens = input_tokens - cached_input_tokens
total_tokens = input_tokens + output_tokens
```

缓存输入属于实际 Token 用量。推理输出已经包含在输出 usage 中时，保持提供方的输出总量，不做
重复累计。对账方法和任何重建步骤写入 shard finding，便于复核。

## 给行为分类

每条观察使用三个互补维度：

- `scope`：`parent` 或 `child`；
- `kind`：`supervision` 或 `task_work`；
- `assessment`：`effective`、`inefficient`、`mixed` 或 `neutral`。

`behavior` 是执行者选择的开放标签，例如：

```text
wait
status-poll
dispatch
message
dependency-coordination
review
correction
retry
state-transition
planning
implementation
regression
```

可以为新现象创建更贴切的标签，同一批次保持命名一致。把一次模型响应作为首选归因单位；如果
提供方给出了更细粒度 usage，也可以拆分。对跨多次响应才能判断的行为，可以汇总成一个观察，
并在 finding 中列出范围和判断依据。

## 判断监督是否有效

从“监督前状态 → 监督动作 → 获得的信息或状态变化 → 后续决策”四步判断：

| 问题 | 倾向有效 | 倾向低效 |
| --- | --- | --- |
| 是否得到新信息？ | 获得结果、进度、错误或依赖变化 | 状态与上次相同，没有新信号 |
| 是否改变决策？ | 触发补派、纠正、验收、重试或下一状态 | 没有形成任何后续动作 |
| 是否降低风险？ | 发现真实缺陷、避免重复、确认边界 | 重复检查已确认内容 |
| 频率是否合理？ | 与任务真实时长、风险和不确定性匹配 | 唤醒或查询明显密于状态变化 |
| 分工是否清楚？ | 建立所有权、解除依赖、整合结果 | 引发重复实现、主线程重做或互相覆盖 |

wait timeout 本身只是一次观察结果。它可能是合理的长任务观察，也可能是过密轮询；结合配置
窗口、真实运行时间、前后状态和后续决策判断。控制调用、状态推进和审阅同理。

## 标准化 JSONL

每行可以代表一次模型响应或一个经过说明的行为小计：

```json
{"schema":"efficiency-inspector/token-observation/v1","sample_id":"conversation-001:supervision-01","agent":"codex","batch":"snapshot-001","root":"conversation-001","cutoff":"2026-08-11T15:30:00Z","scope":"parent","kind":"supervision","behavior":"wait","assessment":"inefficient","input_tokens":130,"cached_input_tokens":120,"output_tokens":2,"event_count":1}
```

使用安全 root 与 sample 标签。一个 shard 文件可以包含多个根，但同一根在同一批次中保持单一
文件所有权。分类理由写入对应 finding 文件，不把原始对话内容复制进 JSONL。

## 轻量计算器

```sh
python3 scripts/token_totals.py \
  --input shard-001.jsonl shard-002.jsonl \
  --output token-summary.json
```

计算器按 scope、kind、assessment 和开放 behavior 标签汇总，并计算：

```text
parent_total = sum(scope=parent)
children_total = sum(scope=child)
system_total = parent_total + children_total
supervision = sum(scope=parent, kind=supervision)
effective_supervision = sum(supervision, assessment=effective)
inefficient_supervision = sum(supervision, assessment=inefficient)
mixed_supervision = sum(supervision, assessment=mixed)
inefficient_parent = sum(scope=parent, assessment=inefficient)
effective_system = system_total - inefficient_parent

parent_inefficiency_rate = inefficient_parent / parent_total
system_inefficiency_rate = inefficient_parent / system_total
parent_token_efficiency = (parent_total - inefficient_parent) / parent_total
token_efficiency = effective_system / system_total
supervision_effective_rate = effective_supervision / supervision
supervision_inefficient_rate = inefficient_supervision / supervision
effective_to_inefficient_ratio = effective_system / inefficient_parent
delegation_leverage = children_total / supervision
```

先汇总原始 Token，再计算整体比率。分母为零时返回 `null`。behavior breakdown 用来发现具体
低效模式，例如等待、状态查看、纠正或重复审阅中哪一类占比最高。

## 解释结果

同时比较绝对 Token、次数和比率：

- 高次数、低 Token 的监督可能是轻量观察；
- 低次数、高 Token 可能意味着每次监督重新加载了大上下文；
- 高有效监督率说明协调带来了信息、决策或风险降低；
- 高低效监督率需要回看轮询节奏、任务边界、依赖设计和返工来源；
- `mixed` 比例高时，说明观察粒度可能需要进一步拆分。

`delegation_leverage` 描述子工作量与主线程监督量的关系。可以据此形成效能判断；如果需要严格
回答“相比主线程单独执行节省了多少”，再设计同任务、同状态、同验收边界和同模型的对照样本。

## 数据管理

遵循 [数据目录与并发写入](data-layout.md)。原始会话保持只读，标准化观察使用安全标签，finding
只写归纳判断和方法，不复制线程身份、路径、提示词或完整工具载荷。
