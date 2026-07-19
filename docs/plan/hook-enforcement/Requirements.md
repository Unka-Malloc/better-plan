# Hook Enforcement Requirements

> Completed delivery record. The current session/task alignment contract is defined by `../task-plan-alignment/`; this Plan's terminal Nodes are not reopened.

## Problem

Better Plan currently tells an agent to match a Node's platform and run appropriate validation, but the executable state transition does not enforce either obligation. An agent can start a platform-incompatible Node, and a completed Node has no machine-readable definition of the regression commands that prove its acceptance criteria.

## Users and workflow

The target user runs Better Plan through Codex, Cursor, or Claude Code on macOS, Linux, or Windows. The intended workflow is:

1. The agent selects a pending Node.
2. Before work begins, the state machine determines the current platform and rejects an incompatible Node.
3. When the agent attempts to stop, the lifecycle hook runs the active Node's declared regression contract.
4. The Node can complete only with a current passing regression receipt for the declared tested paths and commands.

## Functional requirements

- **REQ-001 — Platform gate:** expose the normalized runtime platform (`macos`, `linux`, or `windows`) and reject `start` when a Node declares a different non-`any` platform.
- **REQ-002 — Regression contract:** non-terminal `implementation` and `final_validation` Nodes must declare machine-readable regression scope, commands, mapped acceptance criteria, and repository-relative tested paths. Implementation scope is `focused`; final validation scope is `full`.
- **REQ-003 — Regression receipt:** execute declared commands from the project root without persisting their output, mark only the mapped criteria after every command passes, and record a contract-and-content fingerprint that becomes stale when the contract or tested paths change.
- **REQ-004 — Lifecycle enforcement:** provide one Stop Hook runtime that understands Codex, Cursor, and Claude Code event payloads, validates exactly one active platform-compatible Node, and requests continued work on regression failure, unchecked criteria, or incomplete status.
- **REQ-005 — Managed installation:** install, update, diagnose, and uninstall Better Plan Hook entries for Codex, Cursor, and Claude Code without deleting or duplicating unrelated user hooks.
- **REQ-006 — Deterministic fallback:** the manifest tool remains the hard enforcement boundary: `complete` must reuse a current receipt or run the same declared regression even when a host does not invoke its lifecycle Hook.
- **REQ-007 — Safe evidence:** plans and receipts retain only command identity, exit success, timestamps, and hashes; captured command output, secrets, personal data, local-machine details, ciphertext, credentials, and backend runtime data must not be persisted or echoed by Hook decisions.

## Non-functional constraints

- Keep Hook event translation separate from workflow state and regression execution.
- Use bounded, sequential command execution and deterministic sorted path hashing.
- Reject ambiguous active-node selection instead of guessing.
- Preserve immutable completed historical Nodes; enforcement applies whenever a delivery Node can still be started or completed.
- Keep focused regression within implementation Nodes and reserve the complete suite for `final_validation`.
- Configuration updates must be idempotent and must preserve unknown top-level fields, existing events, groups, and handlers.

## Scope

In scope: Node schema and state transitions, regression execution, Hook protocol adapters, installer configuration for Codex/Cursor/Claude Code, doctor and uninstall behavior, documentation, and automated tests.

Out of scope: replacing each host's native sandbox or permission system, supporting hosts without lifecycle Hook APIs, parsing arbitrary shell commands to infer Node identity, storing command output, and automatically choosing among multiple active Nodes.

## Final acceptance target

The full automated suite proves start-time platform rejection, focused/full contract validation, stale-receipt invalidation, privacy-safe failure behavior, host-specific Stop continuations, idempotent configuration merging, scoped uninstall, and installed-tree diagnostics. The final Better Plan workspace validation and requirement-label cross-check both pass.
