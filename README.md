# Better Plan

Better Plan is a complete-delivery planning and execution protocol for native coding agents. It is
designed for large refactors, migrations, high-risk changes, and multi-Task work that must remain
decision-complete across long-running sessions.

Four guarantees define the workflow:

1. Every non-discoverable user choice is bundled into one Decision Dossier and resolved once.
2. One Designer directly completes the entire Delivery Plan in one writable session.
3. Authorization is the single gate and starts uninterrupted execution; no later user questions.
4. One writable Reviewer repairs the whole delivery and closes the full regression in that session.

## Canonical workspace

```text
Manifest.json
delivery/
  Plan.json          # sole semantic source
  Plan.md            # render-only projection
  Checkpoints.json   # authorization creates this file
```

Every state file carries a `better-plan.*/v3` schema marker. Earlier generations are unsupported.
Stable codes (`PLAN-*`, `REQ-*`, `TASK-*`, `OUT-*`, `AC-*`, `Q-*`, `DEC-*`) are the only identity an
agent ever writes.

## Lifecycle

```text
draft → designing → ready → authorized → completed
                              authorized → revising → authorized
                              authorized → blocked
```

Closing the design session only verifies correlation and immutability, so it can always be closed;
`check-readiness` then lists every remaining gap in one pass and `authorize-plan` is the single hard
gate. A continuation may revise unstarted work without another Designer or user question when the
change stays inside the approved goal, scope, decisions, and risk boundary. Started Tasks stay frozen.

## Roles

| Role | Tier | Duty |
| --- | --- | --- |
| `designer` | high | writes the complete Plan once |
| `worker-standard` | economical | one ordinary bounded Task |
| `worker-complex` | strong | one elevated-risk or coupled Task |
| `reviewer` | high | whole-chain repair, rendered evidence, full regression |

## Quick schema inspection

```sh
python3 scripts/manifest_tool.py schema manifest
python3 scripts/manifest_tool.py schema plan
python3 scripts/manifest_tool.py schema task
python3 scripts/manifest_tool.py schema question
python3 scripts/manifest_tool.py schema checkpoints
```

## Principal commands

```sh
python3 scripts/manifest_tool.py init-plan ...
python3 scripts/manifest_tool.py build-dossier ...
python3 scripts/manifest_tool.py resolve-dossier ...
python3 scripts/manifest_tool.py open-designer-session ...
python3 scripts/manifest_tool.py close-designer-session ...
python3 scripts/manifest_tool.py check-readiness ...
python3 scripts/manifest_tool.py authorize-plan ...
python3 scripts/manifest_tool.py next-action ...
python3 scripts/manifest_tool.py dispatch-task ...
python3 scripts/manifest_tool.py accept-task ...
python3 scripts/manifest_tool.py open-reviewer-session ...
python3 scripts/manifest_tool.py close-reviewer-session ...
```

See [SKILL.md](SKILL.md) and the [state protocol](references/state.md) for the complete contract.

## Installation

Better Plan installs one receipt-managed generation of native role templates, skill files, and
optional host Hooks. Updates fail closed on unowned same-name files and never displace unrelated
agents. An explicit replacement removes only an older Better Plan generation, installs the complete
current matrix, and creates a fresh receipt.

```sh
python3 scripts/install.py install --agent codex
python3 scripts/install.py doctor --agent codex
```

Codex, Claude Code, OpenCode, Cursor, Copilot, Antigravity, Kimi, and supported plugin targets use
their native role and Hook formats. Installed selectors remain authoritative; package selectors are
fallbacks only.

## Development

Python 3.8 or newer is the supported runtime range.

Run focused tests while changing one invariant. After all changes are integrated, run the complete
suite once:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
```

The Better Plan source repository uses its ordinary native development workflow and never requires
a repository-local Plan workspace for self-maintenance.
