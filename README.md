# better-plan

Better Plan is a Codex skill that turns project plans into a small validated workflow state machine.

The workflow state is stored in two JSON files:

- `Manifest.json` indexes Plans.
- `Checkpoints.json` stores each Plan's executable Node graph.

## Install

Install or update Better Plan for all supported local agents:

```sh
python3 scripts/install.py
```

The installer is idempotent and installs:

- Codex skill: `~/.codex/skills/better-plan`
- Shared skill source for adapters: `~/.agents/skills/better-plan`
- Claude Code skills-dir plugin: `~/.claude/skills/better-plan`
- OpenCode primary agent: `~/.config/opencode/agents/better-plan.md`
- Cursor skill: `~/.cursor/skills/better-plan`
- VS Code Copilot skill: `~/.copilot/skills/better-plan`
- Gemini/Antigravity extension: `~/.gemini/extensions/better-plan`

Verify the local install:

```sh
python3 scripts/install.py doctor
```

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

The installer uses `SKILL.md` and `scripts/manifest_tool.py` as the single implementation. Claude, OpenCode, and Gemini/Antigravity receive small adapter entries that point back to that implementation. Codex, Cursor, and VS Code Copilot receive complete skill-tree installs. Existing user config files that the installer edits are backed up with a `.bak-better-plan-<timestamp>` suffix before changes.

## Commands

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

The validator checks JSON shape, UUIDs, graph references, prerequisite cycles, and lightweight state-machine guards such as prerequisite completion, checked acceptance criteria, and Plan status consistency with referenced checkpoints.

## Test

```sh
python3 -m unittest discover -s tests -v
```

The test suite covers the validator state machine and CLI behavior.

## Minimal Release Checklist

- `python3 -m unittest discover -s tests -v` passes.
- `python3 scripts/install.py doctor` passes after local install.
- `python3 scripts/manifest_tool.py uuid --count 1` prints one UUID4 value.
- `python3 scripts/manifest_tool.py transition pending in_progress` succeeds.
- `git status --short` contains only intended release files.
