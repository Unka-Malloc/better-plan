# Host Configuration and Role Visibility

Read this reference only before the first Better Plan role dispatch in a conversation, native role
configuration changes, installation/update/Doctor work, selector diagnosis, or host integration.
Ordinary planning and delivery turns do not load it.

## Role matrix

Better Plan installs four delivery roles per supported host:

| 角色 | 用途 | 推荐选择器 |
|---|---|---|
| `designer` | 单次完成结构化方案草稿，由 Python 编译 Plan | `gpt-5.6-sol / max` |
| `worker-standard` | 经济档：普通有界 Task | `gpt-5.6-luna / max` |
| `worker-complex` | 强力档：高风险或结构耦合 Task | `gpt-5.6-sol / high` |
| `reviewer` | 全量回归后的唯一可写终审，审计源码、测试、诊断与渲染证据 | `gpt-5.6-sol / max` |

A complete valid installed matrix is authoritative. Use it automatically and silently; never ask the
user to choose between installed and recommended matrices, and never pause delivery for that choice.
The package recommendation is only a per-role fallback for an absent, unreadable, unsafe, or
model-less role, and never overrides or mutates an installed role.

Show the installed-versus-recommended comparison only when the matrix is missing or invalid, or when
the user asks about role configuration. Render selectors as `model / effort`; when either side pins a
provider, append `@ provider` and label the other side `@ unpinned`. Mark missing roles explicitly,
never infer a provider, and never inspect credentials. Never inject this table from Hooks.

## Role-change reconfirmation gate

Whenever the user requests any native role configuration change, show the complete
installed-versus-recommended table even if it was already shown. Include every role, use the same
selector format, and label client-specific overrides separately from package recommendations; never
describe a local override as a recommendation change.

Restate the exact requested mutations, ask the user to confirm them, then stop and wait. Before that
fresh confirmation, do not edit role files, provider configuration, receipts, templates, or
recommendation matrices. A prior confirmation never satisfies a later role-change request.

## Additive host integration — iron rule

Treat every pre-existing host or user file as immutable. General installation, update, provider,
model, routing, Hook, MCP, or skill requests never authorize replacing, overwriting, renaming,
moving, deleting, taking receipt ownership of, or wholesale rewriting an existing file.

Create a uniquely named Better Plan-owned file, or add only the smallest authorized namespaced entry
when the host format supports a non-destructive merge. A receipt covers only artifacts or entries
Better Plan created and never converts a pre-existing file into a managed file. Uninstall removes
only owned artifacts. On a collision or replacement requirement, fail closed and leave the original
untouched. Only an explicit request naming the exact existing file and mutation can authorize it.

## Selector and generation rules

The current installed native role matrix is the only supported generation and one receipt-managed
unit. Runtime reads the pinned installed selector and uses the packaged selector only as a per-role
fallback. Never reselect from conversation memory or leaderboard changes. Normal updates preserve
pinned delivery roles.

An explicit replacement of an older Better Plan setup authorizes removing only that setup from the
active agent directory and installing the complete current matrix with a fresh receipt. A backup is
manual-recovery-only; runtime never reads or restores it. Never displace unrelated agents. Finish by
verifying selectors, receipt inventory, skill structure, and installer Doctor.

## Framework and adapter boundary

Keep lifecycle truth host-neutral. Exact opaque identity preservation, one-ID-to-one-dispatch
binding, retry ceilings, Task independence, and final-callback reduction are Better Plan framework
rules. Fix defects in those invariants once in the framework; never duplicate them across native
hosts.

A host adapter owns only behavior imposed by that host's API or configuration format: native event
names and payload fields, response encoding, spawn options, capacity semantics, and the identity the
host exposes at each boundary. Each host adapter is isolated; adding or changing one must not alter
another host's event inventory or completion parser. If a new host already satisfies the shared
framework contract, its adapter stays declarative and minimal.

## Codex collaboration adapter

Codex configured roles require a fresh child context. For every Designer, Worker, or Reviewer
spawn, pass the returned Better Plan `agent_type`, set `fork_turns` to `none`, and give the attempt a
unique lower-snake `task_name`. Never combine `agent_type` with a full-history fork: Codex inherits
the parent role in that mode and rejects the configured child role.

Codex collaboration capacity is bounded and includes the native main. Inspect current capacity
before `dispatch-task`, then dispatch only the eligible Tasks that can be spawned immediately. Keep
the rest pending until a slot opens. Capacity-limited batching is a host constraint, not permission
to merge Tasks, serialize their internal Nodes, or substitute a generic `worker`. If the exact
`worker-standard` or `worker-complex` role cannot start, use the existing `delegation-failed`, retry,
and `main-complete` lifecycle for that same role.

Bind the canonical `task_name` returned by Codex spawn, for example `/root/backend_worker`, without
normalization. It is the sole Better Plan host identity; a UI task/thread UUID is not equivalent.
Wait for the exact final callback from that spawned task, then have the native main invoke
`agent-complete` with the same canonical task name.

Codex has no Better Plan completion Hook. Its current subagent-stop event identifies the child by a
thread UUID rather than the canonical task name returned by spawn, so a Hook cannot correlate the
two safely—especially for parallel children using the same role. Session-start and prompt-submit
Hooks remain supported; completion stays parent-driven until Codex exposes one stable shared
identity at both boundaries.
