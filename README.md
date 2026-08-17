# Better Plan

Better Plan is a complete-delivery planning and execution protocol for native coding agents. It is
designed for large refactors, migrations, high-risk changes, and multi-Task work that must remain
decision-complete across long-running sessions.

Four guarantees define the workflow:

1. Every non-discoverable user choice is bundled into one Decision Dossier and resolved once.
2. One Designer completes a structured solution draft once; Python compiles the canonical Plan.
3. Authorization is the single gate and starts uninterrupted execution; no later user questions.
4. An independent Python stage runs the complete regression; only afterward does one writable
   Reviewer audit its diagnostics and repair the delivery. Confirmed defects outside that Plan
   become separate unapproved draft repair Plans for explicit user handoff after close.

## Canonical workspace

```text
Manifest.json
delivery/
  Plan.json          # sole semantic source
  Plan.md            # render-only projection
  Design.md          # optional draft; read-only after Designer return
  Design.pristine.md # immutable draft archive after Designer close
  Checkpoints.json   # authorization creates this file
```

Every state file carries a `better-plan.*/v3` schema marker. Earlier generations are unsupported.
Stable codes (`PLAN-*`, `REQ-*`, `TASK-*`, `NODE-*`, `OUT-*`, `AC-*`, `Q-*`, `DEC-*`) are the
only canonical identity; Python generates design-derived codes.

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
Focused acceptance runs concurrently across independent Tasks and holds the workspace lock only for
its short state snapshot and result commit.

## Roles

| Role | Tier | Duty |
| --- | --- | --- |
| `designer` | high | writes one complete structured solution draft |
| `worker-standard` | economical | one ordinary bounded Task |
| `worker-complex` | strong | one Task the Designer judges to need stronger reasoning |
| `reviewer` | high | post-regression source, test, evidence, and diagnostic audit |

Codex can also provide an optional unmanaged `frontend-worker`. Tasks explicitly marked
`worker: frontend` must use it when its local configuration is valid; without it they retain their
standard/complex Worker tier. Better Plan does not install or rewrite this specialist role.

## Quick schema inspection

```sh
python3 scripts/manifest_tool.py schema manifest
python3 scripts/manifest_tool.py schema plan
python3 scripts/manifest_tool.py schema task
python3 scripts/manifest_tool.py schema question
python3 scripts/manifest_tool.py schema checkpoints
python3 scripts/manifest_tool.py schema design
```

## Principal commands

```sh
python3 scripts/manifest_tool.py init-plan ...
python3 scripts/manifest_tool.py build-dossier ...
python3 scripts/manifest_tool.py resolve-dossier ...
python3 scripts/manifest_tool.py open-designer-session ...
python3 scripts/manifest_tool.py compile-design ... --check
python3 scripts/manifest_tool.py close-designer-session ...
python3 scripts/manifest_tool.py compile-design ... --apply
python3 scripts/manifest_tool.py check-readiness ...
python3 scripts/manifest_tool.py authorize-plan ...
python3 scripts/manifest_tool.py next-action ...
python3 scripts/manifest_tool.py dispatch-task ...
python3 scripts/manifest_tool.py accept-task ...
python3 scripts/manifest_tool.py run-full-regression ...
python3 scripts/manifest_tool.py open-reviewer-session ...
python3 scripts/manifest_tool.py record-reviewer-findings ...
python3 scripts/manifest_tool.py close-reviewer-session ...
```

See [SKILL.md](SKILL.md), the [general design principles](references/design-principles.md), and the
[state protocol](references/state.md) for the complete contract and its rationale.

## Reference skills

The repository includes [效率督查](skills/efficiency-inspector/SKILL.md), an audit skill for
studying the main thread's resource economy across the complete Better Plan lifecycle. It samples
Token usage, supervision effectiveness, child workload, waits, and real execution durations so
Better Plan can be optimized from observed behavior rather than intuition. Token and time remain
separate measurement dimensions. It is prompt-led: child auditors interpret Codex conversations,
record their reasoning as normalized observations, and use two small optional calculators for
repetitive arithmetic. Broad searches prefer concurrent disjoint shards while smaller or
capacity-limited audits may run serially. Current raw-evidence support is Codex-only; future Agents
receive dedicated observation recipes or adapters while reusing the generic calculators.

## Installation

Better Plan installs one receipt-managed generation of native role templates, skill files, and
optional host Hooks. Updates fail closed on unowned same-name files and never displace unrelated
agents. Native roles are installed only when no same-name role configuration or receipt exists;
afterward every role file and receipt is immutable, including when Doctor reports drift.

```sh
python3 scripts/install.py install --agents codex
python3 scripts/install.py install --agents kilo
python3 scripts/install.py doctor --agents codex
python3 scripts/install.py update --agents all
```

Updates always preserve native role files and receipts while refreshing skills, Hooks, plugins, and
adapters. Host-neutral lifecycle invariants remain in the framework; only native API, event,
payload, response, and configuration differences live in isolated host adapters.

Codex, Claude Code, OpenCode, Cursor, Copilot, Antigravity, Kilo Code, Kimi, and supported plugin
targets use their native role and Hook formats. Installed selectors remain authoritative; package
selectors are fallbacks only.

The Kilo target installs one short `better-plan` primary Agent and four exact namespaced Subagents.
It uses Kilo's native or shared Agent Skills scan path, restricts the primary Agent to those four
delegates, and leaves model and reasoning selection to the invoking primary Agent for provider
portability. Kilo Agent files and their receipt are created only when no same-name local state
exists and remain immutable afterward.

## Development

Python 3.8 or newer is the supported runtime range.

Run focused tests while changing one invariant. After all changes are integrated, run the complete
suite once:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
```

The Better Plan source repository uses its ordinary native development workflow and never requires
a repository-local Plan workspace for self-maintenance.

## Workflow at a glance

1. Inspect the repository and resolve every non-discoverable outcome choice in one Decision
   Dossier.
2. Dispatch one Designer with the confirmed requirements. It writes `Design.md`, chooses the
   architecture, creates mutually independent Tasks, and exposes parallel Node branches.
3. Python archives the pristine draft and compiles it into `Plan.json`. The native main repairs any
   precisely located conversion issue in `Plan.json`; the Designer is never redispatched.
4. Authorize the exact semantic Plan once, then dispatch every independent Task and every ready Node
   branch concurrently. Python accepts each Task through focused regression.
5. After all Tasks are terminal, run the independent complete-regression stage. It stores only a
   receipt and returns privacy-safe diagnostics without consuming Reviewer model time.
6. Dispatch one writable Reviewer after that regression. It audits source, tests, evidence, and
   diagnostics, then directly repairs in-scope defects without running or waiting for the complete
   regression.
7. Reuse unchanged green evidence or rerun the independent regression after repairs. Resume the
   same Reviewer on failure, then close the delivery without a second Reviewer or approval gate.

The [end-to-end workflow guide](references/workflow.md) lists every command, role handoff, prompt,
state transition, repair path, and final close step. Designer draft syntax and deterministic
compilation are documented separately in the [Design format](references/design-format.md).
