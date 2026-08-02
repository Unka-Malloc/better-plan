# Host Configuration and Role Visibility

Read this reference only for the first Better Plan activation in a conversation, native role
configuration changes, installation/update/Doctor work, selector diagnosis, or host integration.
Ordinary planning and delivery turns do not load it.

## First-use role visibility gate

Before discovering or mutating Plan state or dispatching any role agent on the first Better Plan
activation, inspect the current host's installed Better Plan role files and receipt read-only.
Compare every installed role with the package recommendation in one localized Markdown table:

| 角色 | 用途 | 已安装选择器 | 推荐选择器 | 差异 |
|---|---|---|---|---|
| Designer | 整组预测式设计 | `gpt-5.6-sol / max` | `gpt-5.6-sol / max` | 无 |

Render selectors as `model / effort`. When either side pins a provider, append `@ provider` and
label the other side `@ unpinned`; otherwise omit provider cells and state once that every role uses
the host default. Mark missing roles explicitly. Never infer a provider or inspect credentials.

A complete valid installed matrix is authoritative. Use it automatically; do not ask the user to
choose between installed and recommended matrices or pause for that choice. The package
recommendation is only a per-role fallback for an absent, unreadable, unsafe, or model-less role and
never overrides or mutates an installed role. If no native matrix exists, show `not installed`,
explain packaged fallbacks, and mention bundled templates for Codex, Claude Code, OpenCode, and
Cursor. Do not solicit configuration changes unless requested. Show this gate once per conversation
and never inject it from Hooks.

## Role-change reconfirmation gate

Whenever the user requests any native role configuration change, repeat the complete
installed-versus-recommended table even if it was already shown. Include every role, use the same
five-column selector format, and label client-specific overrides separately from package
recommendations; never describe a local override as a recommendation change.

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
