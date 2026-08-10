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
