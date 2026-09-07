# 超时统计与关联采样

本能力测量时间。Token 与时间是两个独立维度：同一执行可以同时拥有 Token 观察和时间观察，
通过 root、阶段与行为标签分析关联，但分别保留各自单位和统计结果。

## 固定 N 项目录

令 `P` 为观察窗口和执行期限的采样目录，`N = |P|`。当前 `N = 7`：

| Policy key | 性质 | 一个样本代表 |
| --- | --- | --- |
| `role.designer.poll` | 观察窗口 | 一个 Designer 会话 |
| `role.worker.poll` | 观察窗口 | 一次 Worker 派发或纠正 |
| `role.reviewer.poll` | 观察窗口 | 一个 Reviewer 会话 |
| `fsm.authorize.verify-command` | 命令期限（默认无） | 一次授权验证命令 |
| `fsm.task.focused-regression` | 命令期限（默认无） | 一次聚焦回归命令尝试 |
| `fsm.delivery.full-regression` | 命令期限（默认无） | 一次完整回归命令尝试 |
| `framework.lifecycle-hook` | 执行期限 | 一次显式计时 Hook 调用 |

输出全部 N 行，包括零样本行。`N` 是策略维度数，`M` 是观测执行数。每个 wait、FSM 转移、
安装探针、测试夹具超时、shell yield 或用户命令可以作为行为或 covariate 观察。命令阶段保留
独立采样项，但框架不设置执行期限，`default_timeout_ms` 为 `null`。只记录实际观察到的项目
或用户命令期限；无期限时 `configured_timeouts_ms` 为空数组，不能推断一个默认期限。

`worker-standard` 和 `worker-complex` 共用一个策略，tier 作为 covariate。Hook 事件和宿主也作为
covariate。框架新增、删除或改变期限设置时，同步更新 `timeout-catalog.json`。历史样本保留当时
实际使用的期限，不按当前默认值重写。

## 先关联真实执行，再记录超时

一个角色执行只产生一个真实运行时间样本，可以关联多个主线程观察窗口。例如 Worker 运行
154.2 秒，期间三次 60 秒 wait、前两次超时，应记录一行执行样本，其中
`configured_timeouts_ms=[60000,60000,60000]`、`expired_timeout_count=2`、
`elapsed_ms=154200`，而不是三行伪独立样本。

观察窗口描述主线程何时醒来，执行期限描述框架对命令或 Hook 施加的运行边界。将二者分层，
分别解释观察节奏与任务终止风险。

执行智能体综合以下来源重建时间关联：

1. 同一原生调用或执行身份的开始与结束事件；
2. 同一宿主返回的单调时钟持续时间；
3. 精确关联会话内的 UTC 时间戳差；
4. cutoff 前只有开始、没有终态时的右删失时长。

共享执行身份通常形成 `direct` 关联；通过连续时间线、时间戳、角色边界和状态变化重建的关联
记为 `reconstructed`；主要依靠完整对话语境判断的关联记为 `contextual`。在 finding 中说明方法
和判断过程，方便后续复核。

## 标准化 JSONL

每行是一项真实执行：

```json
{"schema":"efficiency-inspector/timeout-sample/v1","sample_id":"conversation-001:worker-01","agent":"codex","batch":"snapshot-001","cluster":"conversation-001","policy_key":"role.worker.poll","configured_timeouts_ms":[60000,60000,60000],"expired_timeout_count":2,"elapsed_ms":154200,"outcome":"completed","correlation":"direct","measurement":"trace_pair","covariates":{"worker_tier":"complex","attempt":1}}
```

字段约束：

- `sample_id`：批次内唯一安全标签；
- `cluster`：隐私安全的根对话标签，用于聚类和防止跨 shard 拆分；
- `configured_timeouts_ms`：该执行精确关联的全部观察窗口或执行期限；
- `expired_timeout_count`：其中实际到期的次数，取值不超过列表长度；
- `elapsed_ms`：非负真实时长；无法测量时为 `null`；
- `outcome`：`completed`、`timed_out`、`active`、`failed`、`cancelled` 或 `blocked`；
- `correlation`：`direct`、`reconstructed` 或 `contextual`；
- `measurement`：`monotonic`、`trace_pair`、`cutoff` 或 `reconstructed`；
- `covariates`：任务规模、角色 tier、阶段、重试、宿主等小型分层信息，不写原始内容。

把同一根对话的所有策略样本放在同一 shard，以保留关联结构和根级 bootstrap 簇。

## 结果与删失

- `completed`、`failed`、`cancelled`、`blocked`：已观察终态；后三者是成功完成的竞争结果。
- `timed_out`：只知道执行至少持续到期限，是右删失，不是假定恰好在期限完成。
- `active`：只知道执行至少持续到共同 cutoff，也是右删失。

同时保留成功、删失和竞争结果，让长尾与失败进入分布分析。

## 轻量计算器

```sh
python3 scripts/timeout_summary.py \
  --input shard-001.jsonl shard-002.jsonl \
  --output timeout-summary.json
```

脚本只做：字段和目录校验、重复/跨 shard 根检查、全部 N 行覆盖、结果计数、配置超时计数、
完成样本的描述性分位数，以及观察窗口或执行期限的简单关联比率。完成样本分位数属于忽略删失
的探索性描述；总体持续时间分布结合生存分析判断。

脚本不负责发现样本、解释语义、选择模型或自动修改框架超时。小样本可直接阅读 JSONL 并手算；
需要重复算术时再使用脚本。

## 数学分析方法

先按策略性质、角色/阶段、任务规模和重试状态检查异质性，再选择工具：

1. 用事件计数、ECDF、对数时长图和完成样本分位数做探索，但注明删失偏差。
2. 存在右删失时，用 Kaplan–Meier 估计到任意终态的时间分布。
3. 关注成功完成且存在失败/取消/阻塞时，用 Aalen–Johansen 估计成功完成累积发生率。
4. 样本足够且分层合理时，比较对数正态、Weibull 和 Gamma；使用包含删失项的似然。
5. 用 AIC、概率图、尾部分位数校准和样本外稳定性共同判断，不只看单一拟合分数。
6. 不确定区间按 `cluster` 对根对话整簇 bootstrap，保留同一对话内的相关性。

候选密度与生存函数分别为 `f(t;θ)`、`S(t;θ)` 时，删失似然为：

```text
L(θ) = ∏ observed f(t_i;θ) × ∏ censored S(t_i;θ)
```

超时策略评估要回答实际问题，而不是寻找一个“漂亮分布”：

- 观察窗口过短是否只增加主线程唤醒和 Token 重载，却没有更早获得终态？
- 执行期限是否覆盖目标比例的正常任务，同时不过度掩盖卡死？
- 不同角色、阶段、任务规模或重试是否需要分层策略？
- 调整后的收益能否在新的冻结批次中复现？

可将候选期限与 Kaplan–Meier 尾部覆盖率、Aalen–Johansen 成功完成率、失败竞争风险以及唤醒
次数共同比较。由执行者选择候选策略，在新批次中验证后再决定是否调整框架配置。

## 报告

每个策略至少报告样本数与根簇数、结果计数、精确/部分/未关联比例、配置超时分布、到期次数、
真实执行时长描述量、删失与竞争风险、关键 covariate、采用的数学方法及局限。零样本项说明缺口，
并说明零样本项代表的采样缺口。
