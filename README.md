# better-plan

Better Plan is a Codex skill that turns project plans into a small validated workflow state machine.

Plans are treated as end-to-end product delivery contracts: requirements and evidence come first, implementation checkpoints follow, and validation must trace back to the original requirements through canonical `REQ-...` labels recorded on each Node. Labels begin with `REQ` and use hyphen-delimited alphanumeric segments; Plan-local `REQ-###` labels are preferred, and prefixes before `REQ` are invalid.

The architecture role fixes module boundaries, layering, dependency direction, and deliberate design-pattern choices in `Architecture.md` before implementation starts. Implementation Nodes are split along those module boundaries and declare the files they own, so independent Nodes stay decoupled and can be developed in parallel instead of piling code into one file.

The workflow state is stored in two JSON files:

- `Manifest.json` indexes Plans.
- `Checkpoints.json` stores each Plan's executable Node graph, including each Node's delivery `role` and `requirements` labels.

Status changes go through the manifest tool's mutation commands, which enforce the transition table and every snapshot invariant before writing. `validate` additionally compares each Plan and Node status against the file's git HEAD version and rejects changes that no transition path allows, such as `completed` back to `in_progress`.

Plans can be nested when one plan is the common foundation for other plans. For example, a shared `common` plan can own `common/Checkpoints.json`, while dependent business-line plans live under `common/a/Checkpoints.json`, `common/b/Checkpoints.json`, and `common/c/Checkpoints.json`. The root `Manifest.json` stays a flat array; hierarchy is expressed through each Plan's relative `directory` and `checkpoints` paths. The tree grows top-down: upper directories are foundations, leaves are concrete delivery branches. Platform adaptation follows the same shape — a platform-neutral parent plan with one child plan per operating system or runtime target, so each platform's development direction is planned and executed independently.

Field semantics and examples live in `references/state-files.md`; the canonical object shapes are printed by `scripts/manifest_tool.py schema plan|node`.

## Install

Install or update Better Plan for all supported local agents:

```sh
python3 scripts/install.py
python3 scripts/update.py
```

The installer is idempotent and installs:

- Shared skill source for Codex, Cursor, VS Code Copilot, and adapters when selected by the per-agent resolver: `~/.agents/skills/better-plan`
- Claude Code skills-dir plugin: `~/.claude/skills/better-plan`
- OpenCode primary agent: `~/.config/opencode/agents/better-plan.md`
- Gemini/Antigravity extension: `~/.gemini/extensions/better-plan`

Codex, Cursor, and VS Code Copilot can scan `~/.agents/skills`, but each client resolves its install target independently. A clean install defaults to `~/.agents/skills/better-plan`. If only a client's native path already has Better Plan, such as `~/.codex/skills/better-plan`, update keeps that native path as the source of truth instead of creating a duplicate in `~/.agents`. If both shared and native copies exist for the same client, shared wins and the native duplicate is removed so only one current implementation remains. When `scripts/install.py` sees an existing Better Plan install, it switches to the same update flow automatically.

On Windows, installation and update also discover each running WSL distribution with OpenCode and run the same installer inside that distribution. This creates its WSL shared skill source and OpenCode primary agent, rather than leaving WSL to use a Windows-only adapter. The Better Plan source must be reachable from that distribution through `wslpath`.

Verify the local install:

```sh
python3 scripts/install.py doctor
```

`doctor` validates the structural adapter for every supported client. When a native CLI is available, it additionally checks Cursor and Copilot can run, validates and lists the Gemini extension, validates the Claude plugin, and confirms OpenCode lists the Better Plan agent. On Windows it performs the OpenCode agent-list check inside every detected WSL distribution as well. Missing optional client CLIs produce a warning instead of a failed structural install.

Install a subset of agents:

```sh
python3 scripts/install.py --agents codex,claude
python3 scripts/install.py update --agents opencode cursor copilot gemini
python3 scripts/install.py update --agents vscode-copilot
```

Remove installed adapters:

```sh
python3 scripts/install.py uninstall
```

The installer uses `SKILL.md` and `scripts/manifest_tool.py` as the single implementation for each resolved target. OpenCode and Gemini/Antigravity point to whichever skill tree the resolver selected. Claude receives a skills-dir plugin because it expects a plugin-shaped install. Existing user config files that the installer manages are updated in place without creating Better Plan backup copies.

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
```

Change Node status through enforced transitions. Each command validates the whole state file before writing, writes atomically, and re-derives the owning Plan's status. `pause` returns the running Node to `pending` so another Node can start, keeping `blocked` reserved for real dependencies. `check` records verifiable evidence: `--evidence-cmd` runs the verification command and requires exit 0, `--evidence-file` records the artifact with a sha256:

```sh
python3 scripts/manifest_tool.py start <node-id> <workspace>
python3 scripts/manifest_tool.py pause <node-id> <workspace> --reason "yielding to an inserted task"
python3 scripts/manifest_tool.py check <node-id> <workspace> --criterion 0 --evidence "unit tests passed" \
  --evidence-cmd "python3 -m unittest discover -s tests" --evidence-file reports/coverage.txt
python3 scripts/manifest_tool.py complete <node-id> <workspace> --delivered <sha>
python3 scripts/manifest_tool.py block <node-id> <workspace> --reason "waiting on credentials"
python3 scripts/manifest_tool.py skip <node-id> <workspace> --reason "deferred to a follow-up plan"
```

Change Node structure without hand-editing JSON. `add-node` inserts a new pending Node at a validated position (`--after X --splice` inserts it into X's outgoing chain and rewires downstream prerequisites), `rewire` edits `prerequisites`/`next`, and `edit-node` updates Node fields — terminal Nodes accept only requirements-label corrections because completed history stays immutable:

```sh
python3 scripts/manifest_tool.py add-node <workspace> --plan <selector> --after <node-id> --splice \
  --goal "..." --description "Scope: ... Context: ... Target: ..." --requirements REQ-001 \
  --criterion "..." --commit-message "..." --commit-target "..."
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

The validator checks JSON shape, UUIDs, delivery roles, role difficulty floors, requirement-label traceability, graph references, prerequisite cycles, unstartable nodes behind skipped prerequisites, state-machine snapshot guards such as prerequisite completion and checked acceptance criteria, structured evidence references, Plan status consistency and drift against referenced checkpoints, and status changes against the git HEAD version of each state file.

## Test

```sh
python3 -m unittest discover -s tests -v
```

The test suite covers the validator state machine, the mutation commands, and CLI behavior.

## Minimal Release Checklist

- `python3 -m unittest discover -s tests -v` passes.
- `python3 scripts/install.py doctor` passes after local install.
- `python3 scripts/manifest_tool.py discover <project-root>` finds structurally valid Better Plan workspaces.
- `python3 scripts/manifest_tool.py uuid --count 1` prints one UUID4 value.
- `python3 scripts/manifest_tool.py transition pending in_progress` succeeds.
- `python3 scripts/manifest_tool.py schema node` prints the canonical Node shape.
- `start`, `check`, `complete`, and `sync-plan` drive a sample workspace from `pending` to `completed` and `validate` stays clean.
- `git status --short` contains only intended release files.
