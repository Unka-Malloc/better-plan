# better-plan

Better Plan is a Codex skill that turns project plans into a small validated workflow state machine.

The workflow state is stored in two JSON files:

- `Manifest.json` indexes Plans.
- `Checkpoints.json` stores each Plan's executable Node graph.

## Install

Use this repository as a Codex skill directory. The skill entry point is `SKILL.md`; optional UI metadata is in `agents/openai.yaml`.

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
- `python3 scripts/manifest_tool.py uuid --count 1` prints one UUID4 value.
- `python3 scripts/manifest_tool.py transition pending in_progress` succeeds.
- `git status --short` contains only intended release files.
