# better-plan

Better Plan is a Codex skill that turns project plans into a small validated workflow state machine.

Plans are treated as end-to-end product delivery contracts: requirements and evidence come first, implementation checkpoints follow, and validation must trace back to the original requirements through `REQ-...` labels recorded on each Node.

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

Verify the local install:

```sh
python3 scripts/install.py doctor
```

On Windows, `doctor` also checks running WSL distributions for OpenCode when `opencode` is not on the Windows `PATH`. If Docker is available, it checks running containers for `opencode` as additional diagnostic context.

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

Validate a Better Plan workspace that already contains `Manifest.json` and plan-local `Checkpoints.json` files. `--json` prints machine-readable results; `--no-git` skips the git HEAD transition comparison:

```sh
python3 scripts/manifest_tool.py validate <better-plan-workspace> [--json] [--no-git]
```

Generate IDs and check one status transition edge:

```sh
python3 scripts/manifest_tool.py uuid --count 3
python3 scripts/manifest_tool.py transition pending in_progress
```

Change Node status through enforced transitions. Each command validates the whole state file before writing, writes atomically, and re-derives the owning Plan's status:

```sh
python3 scripts/manifest_tool.py start <node-id> <workspace>
python3 scripts/manifest_tool.py check <node-id> <workspace> --criterion 0 --evidence "unit tests passed"
python3 scripts/manifest_tool.py complete <node-id> <workspace> --delivered <sha>
python3 scripts/manifest_tool.py block <node-id> <workspace> --reason "waiting on credentials"
python3 scripts/manifest_tool.py skip <node-id> <workspace> --reason "deferred to a follow-up plan"
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

The validator checks JSON shape, UUIDs, delivery roles, role difficulty floors, requirement-label traceability, graph references, prerequisite cycles, unstartable nodes behind skipped prerequisites, state-machine snapshot guards such as prerequisite completion and checked acceptance criteria, Plan status consistency and drift against referenced checkpoints, and status changes against the git HEAD version of each state file.

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
