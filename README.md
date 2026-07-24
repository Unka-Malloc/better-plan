# better-plan

Better Plan is an agent skill that turns project plans into a small validated workflow state machine.

Plans are revisable delivery models derived from the latest user request. Requirements and evidence come first, implementation checkpoints follow, and validation traces to canonical `REQ-...` labels recorded on each Node. Labels begin with `REQ` and use hyphen-delimited alphanumeric segments; Plan-local `REQ-###` labels are preferred, and prefixes before `REQ` are invalid.

Architecture establishes only the boundaries and decisions relevant to the requested change. Files, symbols, interfaces, errors, algorithms, data structures, state, cache, isolation, and concurrency are risk-driven design candidates rather than mandatory prose. Implementation Nodes declare a primary file focus, while the native main judges necessary adjacent changes reported by a leaf.

The workflow state is stored in two JSON files:

- `Manifest.json` indexes Plans.
- `Checkpoints.json` stores each Plan's executable Node graph, including each Node's delivery `role` and `requirements` labels.

One user-visible capability uses one selected implementation Node as its lifecycle identity. Acceptance revision, implementation repair, focused regression, and audit remain correlated to that Node. The state tool runs the declared focused regression after executor exit: failure returns a repair/defer decision to the native main, success selects one fresh read-only auditor, and a fingerprint-bound PASS completes the Node. Completion and adjacent findings never select another Node automatically.

Plans can be nested when one plan is the common foundation for other plans. For example, a shared `common` plan can own `common/Checkpoints.json`, while dependent business-line plans live under `common/a/Checkpoints.json`, `common/b/Checkpoints.json`, and `common/c/Checkpoints.json`. The root `Manifest.json` stays a flat array; hierarchy is expressed through each Plan's relative `directory` and `checkpoints` paths. The tree grows top-down: upper directories are foundations, leaves are concrete delivery branches. Platform adaptation follows the same shape — a platform-neutral parent plan with one child plan per operating system or runtime target, so each platform's development direction is planned and executed independently.

Field semantics and examples are in the canonical plan/schema output from `scripts/manifest_tool.py schema plan|node`.

## Install

Better Plan supports Python 3.8 or newer and uses only the Python standard library at runtime.

Install or update Better Plan for all supported local agents:

```sh
python3 scripts/install.py
python3 scripts/install.py update
```

The installer is idempotent and installs:

- A configured shared or client-native skill source for Codex, Cursor, Copilot, Pi, Kimi Code, and adapter clients
- A Claude Code skills-dir plugin
- An OpenCode primary agent
- An Antigravity plugin containing the Better Plan skill and a first-invocation lifecycle Hook
- The Better Plan skill in every configured Craft Agents workspace
- Managed detector-gated lifecycle handlers for Codex, Claude Code, Cursor, and Kimi Code:
  - Codex and Claude Code receive nested `SessionStart`, `UserPromptSubmit`, and an Agent-only `PostToolUse` hook.
  - Cursor receives flat version 1 hooks: `sessionStart`, `beforeSubmitPrompt`, and Agent/Task-only `postToolUse`.
  - Kimi Code receives TOML `SessionStart`, `UserPromptSubmit`, and `SubagentStop` hooks.
- A plugin-owned Antigravity `PreInvocation` handler that injects guidance only on invocation zero.
- Managed Hook handlers are attached only through these supported events.

Nested Codex and Claude command handlers and Kimi Code TOML handlers use one bounded timeout, `HOOK_TIMEOUT_SECONDS` (currently 30 seconds), for the Hook command process itself. It does not observe, limit, interrupt, or replace an Agent: Agent completion has already occurred before the completion Hook starts. If automatic regression outlives that outer Hook window, the host may terminate the Hook before its directive or final state update is returned; the native main remains running and can inspect progress. Cursor handlers use the host's flat version 1 command shape without adding undocumented handler fields.

Better Plan does not poll or time delegated Agents. Dispatch lifetime, cancellation, and host-level timeout behavior belong exclusively to the native agent framework. Better Plan reacts only after the correlated Agent-completion event is delivered.

Codex, Cursor, Copilot, Pi, and Kimi Code can scan the configured shared skill directory, but each client resolves its install target independently. A clean install uses the shared target. If only a client's native target already has Better Plan, update keeps that target as the source of truth. If both shared and native copies exist for the same client, shared wins and the duplicate is removed so only one current implementation remains. When `scripts/install.py` sees an existing Better Plan install, it switches to the same update flow automatically.

Antigravity uses its documented global plugin location. Its plugin owns one `PreInvocation` Hook
that injects Better Plan guidance only for the first model invocation in a structurally detected
workspace. It does not install `PreToolUse`, `PostToolUse`, `PostInvocation`, or `Stop` handlers.
Craft Agents isolates skills by workspace, so installation updates each existing workspace that has
a `config.json`; if no workspace exists, installation reports that fact without creating a fake one.

Selecting Cursor through `--agents` installs both its Better Plan skill surface and its managed lifecycle handlers.
Selecting Kimi through `--agents` installs its discoverable skill surface and manages only Better Plan-owned
`[[hooks]]` tables in `config.toml`. Kimi's `UserPromptSubmit` carries the short intent guidance;
`SessionStart` performs detector-gated observation, and `SubagentStop` reduces a correlated lifecycle after
the child succeeds. Kimi documents the latter two events as observation-only, so Better Plan never treats
their stdout as a main-thread control channel.

On Windows, installation and update also discover each running WSL distribution with OpenCode and run the same installer inside that distribution. This creates its WSL shared skill source and OpenCode primary agent, rather than leaving WSL to use a Windows-only adapter. The Better Plan source must be reachable from that distribution through `wslpath`.

The installed payload has one canonical layered implementation:

- `scripts/better_plan/domain/`: workflow values, validation, design contracts, and transitions
- `scripts/better_plan/infrastructure/`: workspace persistence and regression execution
- `scripts/better_plan/application/`: workflow use cases and Agent-completion reduction
- `scripts/better_plan/hooks/`: workspace scope, event context, read-only runtime, and Hook config ownership
- `scripts/better_plan/installation/`: models, atomic skill copies, target adapters, diagnostics, and service composition
- `scripts/better_plan/adapters/`: manifest and installer CLI adapters
- `scripts/manifest_tool.py`, `scripts/hook_tool.py`, and `scripts/install.py`: behavior-free executable entrypoints
- `references/`: one conditionally loaded contract per orchestration role

Verify the local install:

```sh
python3 scripts/install.py doctor
```

`doctor` validates structural adapters for all supported clients and requires exactly one managed handler for each supported event:

- Codex: `SessionStart`, `UserPromptSubmit`, `PostToolUse` matched only to `Agent`
- Claude Code: `SessionStart`, `UserPromptSubmit`, `PostToolUse` matched only to `Agent`
- Cursor: `sessionStart`, `beforeSubmitPrompt`, `postToolUse` matched only to `Agent` or `Task`
- Antigravity: plugin-owned `PreInvocation` only
- Kimi Code: `SessionStart`, `UserPromptSubmit`, `SubagentStop`

When a native CLI is available, it additionally checks Cursor, Copilot, and Kimi Code can run, validates the Claude plugin, and confirms OpenCode lists the Better Plan agent. It structurally validates the Antigravity plugin and every configured Craft workspace. On Windows it performs the OpenCode agent-list check inside every detected WSL distribution as well. Missing optional client CLIs produce a warning instead of a failed structural install.

Codex, Claude Code, Cursor, and Kimi Code Hook installation preserves unrelated settings and handlers. Antigravity's Hook is isolated inside the Better Plan plugin. Repeated install/update replaces only Better Plan-owned handlers or plugin files; full `uninstall` removes installed adapters and their managed handlers, while hook-only uninstallation is done with `uninstall-hooks`. Managed commands contain no concrete machine path and locate the skill through client environment roots plus relative path segments. Every invocation runs the dedicated project detector first and returns a safe no-op when no structured Better Plan workspace exists.

Every invocation first detects exactly one valid Better Plan workspace. If there is no workspace, ambiguity, malformed structure, or conflicting repository root, callbacks exit successfully with no action.

Session and prompt Hooks provide guidance only. The Agent-completion Hook is the sole tool-scoped specialization: it runs after a native child Agent has returned, never blocks the tool or continues the stopped child, and invokes only the correlated Better Plan reducer. No Hook subscribes to `PreToolUse`, generic tool calls, or a main-agent stop event, and no callback may deny user prompts.

Install a subset of agents:

```sh
python3 scripts/install.py --agents codex,claude
python3 scripts/install.py update --agents opencode cursor copilot antigravity pi craft kimi
```

Remove installed adapters:

```sh
python3 scripts/install.py uninstall
python3 scripts/install.py uninstall-hooks --agents codex,claude,cursor,antigravity,kimi
```

Hook-only removal is idempotent and affects only managed handlers; it does not remove installed skills or unrelated settings.

The current implementation uses `CURRENT_SKILL_FILES` above as the canonical payload inventory for each resolved target. OpenCode discovers the installed skill by logical name, Antigravity receives a plugin-owned skill tree, and Craft receives one tree per configured workspace. Claude receives a skills-dir plugin because it expects a plugin-shaped install. Existing user config files that the installer manages are updated in place without creating Better Plan backup copies.

## Commands

Discover existing Better Plan workspaces by structure, regardless of directory name:

```sh
python3 scripts/manifest_tool.py discover <project-root>
```

Validate a Better Plan workspace that already contains `Manifest.json` and plan-local `Checkpoints.json` files. `--plan` scopes validation to one plan (by id, directory, or title) plus the shared index so sibling-plan debt does not block the current change; `--check-sources` verifies that `source_files` entries still resolve; `--json` prints machine-readable results; `--no-git` skips the git HEAD transition comparison:

```sh
python3 scripts/manifest_tool.py validate <better-plan-workspace> [--plan <selector>] [--check-sources] [--json] [--no-git]
```

Cross-check requirement labels between plan markdown documents and Node `requirements` fields. Noncanonical document or Node labels and Node labels missing from the documents are errors; documented canonical labels carried by no non-skipped Node are warnings:

```sh
python3 scripts/manifest_tool.py check-labels <workspace> [--plan <selector>] [--json]
```

Generate IDs and check one status transition edge:

```sh
python3 scripts/manifest_tool.py uuid --count 3
python3 scripts/manifest_tool.py transition pending in_progress
python3 scripts/manifest_tool.py platform --json
```

Drive implementation and final-validation Nodes through the acceptance state machine. `next-action` is read-only. `dispatch` creates one bounded correlation, and `advance` consumes matching acceptance-design/executor/audit/regression/repair events. The state tool runs tests, writes safe receipts, routes repair, checks mapped criteria, and auto completes; native agents do none of those things:

```sh
python3 scripts/manifest_tool.py next-action <node-id> <workspace>
python3 scripts/manifest_tool.py dispatch <node-id> <workspace> --role acceptance_designer
python3 scripts/manifest_tool.py advance <node-id> <workspace> --event acceptance-designer-exited --dispatch-id <id>
python3 scripts/manifest_tool.py dispatch <node-id> <workspace> --role executor
python3 scripts/manifest_tool.py advance <node-id> <workspace> --event executor-exited --dispatch-id <id>
python3 scripts/manifest_tool.py dispatch <node-id> <workspace> --role auditor
python3 scripts/manifest_tool.py advance <node-id> <workspace> --event audit-passed --dispatch-id <id>
python3 scripts/manifest_tool.py advance <final-id> <workspace> --event regression-requested
```

Foundation Nodes that are not `implementation` or `final_validation` retain the smaller evidence workflow. This is not a delivery acceptance backdoor:

```sh
python3 scripts/manifest_tool.py start <foundation-node-id> <workspace>
python3 scripts/manifest_tool.py check <node-id> <workspace> --criterion 0 --evidence "unit tests passed" \
  --evidence-cmd "python3 -m unittest tests.test_example -v" --evidence-file reports/coverage.txt
python3 scripts/manifest_tool.py complete <foundation-node-id> <workspace> --delivered <sha>
```

Administrative suspension is separate from acceptance. It cancels stale dispatches and proof before moving the Node:

```sh
python3 scripts/manifest_tool.py pause <node-id> <workspace> --reason "yielding to an inserted task"
python3 scripts/manifest_tool.py block <node-id> <workspace> --reason "waiting on credentials"
python3 scripts/manifest_tool.py defer <node-id> <workspace> --reason "resume after the next planning review"
python3 scripts/manifest_tool.py activate <node-id> <workspace>
python3 scripts/manifest_tool.py skip <node-id> <workspace> --reason "waived from this delivery"
```

`deferred` is non-terminal backlog state: it stays visible in `status`, is absent from executable
selection, and returns to `pending` only through `activate`. A deferred implementation still blocks
final validation and Plan completion. `skipped` is an irreversible terminal waiver or
not-applicable outcome; it never means “do this later.”

Every executable `implementation` or `final_validation` Node declares a regression object. Implementation uses `focused`; final validation uses `full`. `criteria` identifies which acceptance criteria the complete command set proves, while `paths` identifies the smallest repository-relative source/test content bound into the freshness receipt:

```json
{
  "regression": {
    "scope": "focused",
    "commands": ["python3 -m unittest tests.test_example"],
    "criteria": [0],
    "paths": ["src/example.py", "tests/test_example.py"]
  }
}
```

Every supported lifecycle callback enters the thin Hook runtime, which first runs the
canonical structural detector in `scripts/better_plan/hooks/scope.py`. Every invocation requires exactly one valid Better Plan workspace, otherwise it returns success with no action.
Only supported-callback contexts continue orchestration. The native parent then uses this role model:

- Native main
- Acceptance designer
- Executor
- Auditor

For planning, coding, or explicit implementation work, the entry guidance activates Better Plan. For every other request, the agent follows the user's instructions and performs the requested work or answers accordingly. The entry guidance contains no lifecycle policy: after activation, the native main loads `SKILL.md`, and each active role loads only its own reference from `references/`. This progressive disclosure keeps implementation, acceptance, regression, and audit details out of unrelated conversations.
The native main first understands and follows the request, then inspects relevant Plans as fallible references and aligns one selected Node to one user-visible capability. A planning-only request ends after the requested Plan work; execution selection requires user authorization for implementation. An existing or active Node never authorizes work by itself.
The parent reads `next-action`, then dispatches `dispatch_acceptance_designer`, `dispatch_executor`, or `dispatch_auditor` by the returned role with role isolation.
When a native Agent tool returns, the completion Hook submits the correlated write-role exit to the state reducer before the parent receives its next model step. The acceptance designer freezes the contract once and routes directly to execution. Executor exit runs the declared focused regression: success selects the lifecycle's single independent auditor, while failure returns to native-main classification. Ordinary implementation defects stay inside the same Node and frozen acceptance; only real design or product-semantics errors open a repair cycle. The Hook never launches an agent itself and never continues the stopped child.

Read-only verdicts remain main-thread decisions. Approval may continue the same Node; rejection and preparation drift emit `main_acceptance_decision`, where the native main may explicitly revise the same Node, narrow the capability, defer it, or proceed when evidence permits. Regression failure and audit findings likewise return to the native main. No rejection, drift, failure, finding, completion, or newly discovered scope automatically selects a different Node.

Waiting cadence is a communication heuristic. While delegated state is unchanged, the native main uses the host waiting facility without repeating status reports. Better Plan does not time, poll, interrupt, replace, or decide the lifetime of a delegated agent, and waiting is never an execution, completion, or failure gate.

Codex, Claude, and Kimi Code receive only the short routing guidance at prompt submit; no lifecycle policy, Plan list, Plan prose, active Node, workspace label, or role contract is injected ahead of the main agent's judgment. After Better Plan activates, `SKILL.md` discloses the workflow and the active role discloses exactly one applicable role reference.
- Cursor `sessionStart` supplies `additional_context`. Its `beforeSubmitPrompt` callback returns only `continue: true`; the standing session duty therefore carries intent-alignment responsibility without denying the prompt.
- Session and prompt duties share one short routing instruction: enter Better Plan for planning, coding, or explicit implementation work; otherwise perform the requested work or answer accordingly.
- Recognized Codex and Claude subagent lifecycle callbacks are no-ops to prevent orchestration recursion without misclassifying ordinary named main sessions.

“Node start” is an internal acceptance transition, not a host Hook. Session and prompt callbacks stop after returning bounded context or explicit prompt allowance. Only the Agent-completion callback reads the unique correlated dispatch, and duplicate, unrelated, ambiguous, or out-of-phase callbacks are successful no-ops.

Each implementation Node runs only its focused regression. The automatic full-regression route starts exactly once from a final-validation Node's `regression-requested`, after all implementation Nodes finish, and a fresh full receipt still requires the lifecycle's single read-only audit. Handoffs and responses use repository-relative paths and redacted evidence; raw prompts, Plan prose, absolute paths, machine identity, backend runtime data, and command output are excluded.

Change Node structure without hand-editing JSON. `add-node` inserts a new pending Node at a validated position (`--after X --splice` inserts it into X's outgoing chain and rewires downstream prerequisites), `rewire` edits `prerequisites`/`next`, and `edit-node` updates Node fields — terminal Nodes accept only requirements-label corrections because completed history stays immutable. `prerequisites` is the sole execution-dependency authority and may reference any globally unique Node in the workspace; `next` is navigation metadata only:

```sh
python3 scripts/manifest_tool.py add-node <workspace> --plan <selector> --after <node-id> --splice \
  --goal "..." --description "Scope: ... Context: ... Target: ..." --requirements REQ-001 \
  --criterion "..." --commit-message "..." --commit-target "..." \
  --regression-command "python3 -m unittest tests.test_example" \
  --regression-path src/example.py --regression-path tests/test_example.py --regression-criterion 0
python3 scripts/manifest_tool.py rewire <node-id> <workspace> --add-prerequisite <id> --remove-next <id>
python3 scripts/manifest_tool.py edit-node <node-id> <workspace> --add-requirement REQ-002
```

Re-derive Plan statuses, inspect progress, and pick the next task:

```sh
python3 scripts/manifest_tool.py sync-plan <workspace>
python3 scripts/manifest_tool.py status <workspace> [--json]
python3 scripts/manifest_tool.py next <workspace> [--json]
```

Print the canonical Plan or Node schema and template:

```sh
python3 scripts/manifest_tool.py schema plan
python3 scripts/manifest_tool.py schema node
```

The validator checks JSON shape, UUIDs, delivery roles, role difficulty floors, requirement-label traceability, regression contracts and receipts, workspace-wide graph references and prerequisite cycles, unstartable nodes behind skipped prerequisites, state-machine snapshot guards such as prerequisite completion and checked acceptance criteria, structured evidence references, Plan status consistency and drift against referenced checkpoints, and status changes against the git HEAD version of each state file.

Reference set:
- [orchestration-main](references/orchestration-main.md)
- [acceptance-designer](references/acceptance-designer.md)
- [executor](references/executor.md)
- [auditor](references/auditor.md)

## Test

```sh
python3 -m unittest discover -s tests -v
```

The test suite covers the validator state machine, mutation commands, regression freshness, Hook protocol translation, the five-stage role and prompt contract, configuration ownership, installer behavior, and CLI behavior.

## Minimal Release Checklist

- `python3 -m unittest discover -s tests -v` passes.
- `python3 scripts/install.py doctor` passes after local install.
- `python3 scripts/manifest_tool.py discover <project-root>` finds structurally valid Better Plan workspaces.
- `python3 scripts/manifest_tool.py uuid --count 1` prints one UUID4 value.
- `python3 scripts/manifest_tool.py transition pending in_progress` succeeds.
- `python3 scripts/manifest_tool.py platform --json` prints one normalized platform.
- `python3 scripts/manifest_tool.py schema node` prints the canonical Node shape.
- `next-action`, `dispatch`, and `advance` drive a sample delivery Node through executor exit, regression, audit, and automatic completion while `validate` stays clean.
- `git status --short` contains only intended release files.
