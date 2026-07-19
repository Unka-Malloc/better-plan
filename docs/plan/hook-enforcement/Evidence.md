# Hook Enforcement Evidence

## Repository evidence

- `scripts/manifest_tool.py` already normalizes the runtime through `current_platform()`, but only `next` uses that value. `start_command()` delegates directly to `run_node_mutation()` and therefore does not reject an incompatible Node. This grounds **REQ-001**.
- The canonical Node schema currently contains acceptance criteria and evidence references but no executable regression contract or freshness receipt. `complete_command()` only relies on checked criteria and status-transition validation. This grounds **REQ-002**, **REQ-003**, and **REQ-006**.
- `scripts/install.py` already owns atomic skill-tree copying plus per-agent install, doctor, and uninstall routing. `InstallPaths` exposes Codex, Cursor, and Claude homes, so Hook configuration belongs behind a dedicated configuration adapter consumed by this installer rather than inside workflow logic. This grounds **REQ-005**.
- `SKILL.md` requires platform matching, focused regression per implementation closure, one full regression after all implementation, minimal redacted evidence, and preservation of terminal Node history. These are executable invariants for **REQ-001**, **REQ-002**, **REQ-006**, and **REQ-007**.

## Host lifecycle evidence

- Codex documents a `Stop` response with `decision: "block"` as a continuation prompt and exposes `stop_hook_active` to bound repeated callbacks. Source: <https://learn.chatgpt.com/docs/hooks>.
- Cursor documents `stop` plus `followup_message` and `loop_count` for bounded self-correcting continuation. Source: <https://cursor.com/docs/hooks> and Cursor's official self-correcting-loop example at <https://cursor.com/blog/agent-best-practices>.
- Claude Code documents that `Stop` may prevent stopping so Claude can act on the reason and exposes `stop_hook_active` to bound repeated callbacks. Source: <https://code.claude.com/docs/en/hooks>.

## Design deductions

1. A host Hook alone cannot be the source of truth because host coverage, trust, disablement, and failure behavior differ. The manifest state machine must enforce platform and completion rules independently.
2. A prose acceptance criterion cannot select the right regression command. The Node needs a validated contract that maps all commands to explicit criterion indexes and tested paths.
3. A passing command is not sufficient after subsequent edits. A receipt must bind the contract digest and a deterministic digest of the tested paths, and completion must reject a stale receipt.
4. Hook payload and response formats differ, but discovery, platform matching, regression execution, and privacy behavior do not. A thin protocol adapter should call a single workflow runtime.
5. More than one active Node is ambiguous in an agent-wide stop event. Accurate validation requires a continuation that asks the agent to resolve or explicitly validate the intended Node, not an arbitrary first match.
6. Persisting captured stdout or stderr would create an unnecessary disclosure channel. The runtime should capture output only to prevent terminal leakage, discard it, and report command index plus exit status.
