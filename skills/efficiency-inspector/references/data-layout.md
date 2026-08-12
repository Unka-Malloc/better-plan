# 数据目录与并发写入

为每次督查创建独立批次目录。目录由协调者选择，可以位于任务工作区或临时目录；保持范围明确，
不要直接写入原始会话存储。目录中只保存安全标签、标准化观察、简短判断和汇总结果。

## 推荐结构

```text
<audit-batch>/
├── manifest.json
├── discovery/
│   ├── finder-001.jsonl
│   └── finder-002.jsonl
├── observations/
│   ├── token/
│   │   ├── shard-001.jsonl
│   │   └── shard-002.jsonl
│   └── timeout/
│       ├── shard-001.jsonl
│       └── shard-002.jsonl
├── findings/
│   ├── shard-001.md
│   └── shard-002.md
├── summaries/
│   ├── token-summary.json
│   └── timeout-summary.json
└── report.md
```

只创建本次需要的子目录。例如只做 Token 审计时，可以省略 `observations/timeout/`。

## 谁写什么

协调者在派发前创建 `manifest.json`，为每个 shard 指定安全标签、能力范围、执行者和三个输出
路径。每个审计员拥有独立文件：

```json
{
  "batch": "snapshot-001",
  "cutoff": "2026-08-11T15:30:00Z",
  "agent": "codex",
  "shards": [
    {
      "label": "shard-001",
      "roots": ["conversation-001", "conversation-002"],
      "token_output": "observations/token/shard-001.jsonl",
      "timeout_output": "observations/timeout/shard-001.jsonl",
      "finding_output": "findings/shard-001.md",
      "status": "assigned"
    }
  ]
}
```

使用以下写入分工：

- finder 只写自己的 `discovery/finder-NNN.jsonl`；
- auditor 只写 manifest 分配给自己的 shard 文件；
- coordinator 维护 manifest，读取完成的 shard，并写 `summaries/` 与最终 `report.md`；
- 原始会话由所有参与者只读访问，不复制到批次目录。

一个审计员可以在交付前多次完善自己的文件。并行审计时，为每个写入者分配不同路径，使写入
天然互不冲突，而不是让多个审计员共同 append 一个 JSONL。

## Shard 文件

Token 与 timeout 记录分别写入各自目录。一个 shard 可以包含多个互斥根对话，但同一个根及其
相关后代保持在同一个能力文件中。这样协调者可以直接把多个完成文件交给计算器：

```sh
python3 scripts/token_totals.py \
  --input <audit-batch>/observations/token/shard-001.jsonl \
          <audit-batch>/observations/token/shard-002.jsonl \
  --output <audit-batch>/summaries/token-summary.json
```

finding 文件记录该 shard 的判断过程：主要行为、有效监督和低效监督的理由、异常样本、数据关联
方法及建议。它不重复粘贴原始对话。

## 重试与交付

需要重试时使用新的 attempt 路径，例如 `shard-001.attempt-02.jsonl`，并在 manifest 中标记最终
采用哪个 attempt。协调者只把选中的文件传给计算器。这样保留排查空间，也不会让两个 attempt
同时进入统计。

审计员完成后先确认 JSONL 每行可独立解析，再把 shard 状态交给协调者。协调者在聚合前检查：

- 预期文件是否已交付；
- root 是否只出现在一个同能力 shard；
- batch、cutoff 和 Agent 是否一致；
- manifest 选中的 retry attempt 是否唯一；
- findings 是否覆盖主要判断与异常值。

最终报告引用安全 shard 标签和聚合结果。批次目录的保留或清理由任务所有者决定。
