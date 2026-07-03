# better-plan

Better Plan is a Codex skill that turns project plans into a small validated workflow state machine.

Plans are treated as end-to-end product delivery contracts: requirements and evidence come first, implementation checkpoints follow, and validation must trace back to the original requirements.

The workflow state is stored in two JSON files:

- `Manifest.json` indexes Plans.
- `Checkpoints.json` stores each Plan's executable Node graph, including each Node's delivery `role`.

Plans can be nested when one plan is the common foundation for other plans. For example, a shared `common` plan can own `common/Checkpoints.json`, while dependent business-line plans live under `common/a/Checkpoints.json`, `common/b/Checkpoints.json`, and `common/c/Checkpoints.json`. The root `Manifest.json` stays a flat array; hierarchy is expressed through each Plan's relative `directory` and `checkpoints` paths.

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

Validate a Better Plan workspace that already contains `Manifest.json` and plan-local `Checkpoints.json` files:

```sh
python3 scripts/manifest_tool.py validate <better-plan-workspace>
```

Generate IDs:

```sh
python3 scripts/manifest_tool.py uuid --count 3
```

Check one status transition:

```sh
python3 scripts/manifest_tool.py transition pending in_progress
```

The validator checks JSON shape, UUIDs, delivery roles, role-specific difficulty, graph references, prerequisite cycles, and lightweight state-machine guards such as prerequisite completion, checked acceptance criteria, and Plan status consistency with referenced checkpoints.

## Test

```sh
python3 -m unittest discover -s tests -v
```

The test suite covers the validator state machine and CLI behavior.

## Minimal Release Checklist

- `python3 -m unittest discover -s tests -v` passes.
- `python3 scripts/install.py doctor` passes after local install.
- `python3 scripts/manifest_tool.py discover <project-root>` finds structurally valid Better Plan workspaces.
- `python3 scripts/manifest_tool.py uuid --count 1` prints one UUID4 value.
- `python3 scripts/manifest_tool.py transition pending in_progress` succeeds.
- `git status --short` contains only intended release files.
