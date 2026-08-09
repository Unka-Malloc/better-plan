---
name: better-plan
description: Complete-delivery planning for large refactors, migrations, high-risk changes, and real multi-Task handoffs. It consolidates user decisions once, lets one Designer directly finish the Plan, then executes without mid-delivery questions and closes through one write-capable Reviewer.
---

# Better Plan

Better Plan is a complete-delivery protocol. It freezes the whole authorized outcome before any
Worker starts, then advances independent Tasks through explicit handoffs and executable evidence.
The latest user request is always authoritative; stored state never grants work by itself.

## Internal operating guidance

Understand the user's request and inspect repository facts first. Use Better Plan only for large
delivery. Before authorization, consolidate every non-discoverable choice into one Decision Dossier
and resolve it once. After authorization, never ask the user another question: continue safe
in-scope work and report hard authority or environment blockers only at final handoff. Run
`next-action` when the delivery state is unclear; it always names one next step.

## Activation and source-repository exemption

Use the native main's ordinary workflow for one small closure that can be understood, implemented,
and verified directly. Activate Better Plan only for at least one of:

- multiple independently acceptable Tasks with a real handoff or parallel frontier;
- a complete migration or refactor that removes an old generation;
- coordinated schema, data, protocol, state, concurrency, security, privacy, or release work; or
- a long delivery whose result must remain executable after context loss.

Maintaining the Better Plan source repository itself uses the ordinary native repository workflow.
Do not create a repository-local Better Plan workspace merely to edit this package.

## Non-negotiable protocol

- Keep secrets, personal or machine identity, absolute local paths, runtime endpoints, and backend
  runtime data out of state, prompts, evidence, and reports.
- `Plan.json` is the sole semantic source; `Manifest.json` indexes Plans; `Checkpoints.json` holds
  execution state only; `Plan.md` is a render-only projection that is never parsed back.
- `prerequisites` is the sole execution graph. Every Task-to-Task edge declares one matching input
  `{from, output, guarantee}`.
- A Task is one independently acceptable observable outcome. File lists, development phases,
  generic investigation, design, approval, and final review are not Tasks.
- Present at most one Decision Dossier per Delivery Plan and resolve it exactly once. Never ask a
  sequence of granular questions that one coherent choice can close.
- Dispatch exactly one Designer. During its exclusive session the Designer directly edits the
  complete `Plan.json`; it is not a patch-only or read-only adviser.
- Dispatch exactly one Reviewer. It directly repairs code, tests, documentation, and generated
  artifacts, obtains rendered evidence when the Plan requires it, and stays in that same session
  through final regression.
- After authorization, never ask the user another question. Apply the frozen decision precedence,
  revise unstarted in-scope work autonomously, continue independent branches, and report hard
  authority or environment blockers only at final handoff.
- Started Task contracts and evidence are frozen. A continuation may add or replace unstarted work
  but cannot expand goal, scope, user decisions, elevated risk, or irreversible authority.
- Run one focused regression per Task. Run the complete regression inside the sole Reviewer session
  after all repairs are integrated. A failed full run is repaired and repeated inside that same
  session, never through a second Reviewer.

## Delivery sequence

### 1. Explore before asking

Inspect the affected capability, its current contracts, tests, schemas, interfaces, state owners,
failure behavior, and delivery tooling. Record source-grounded facts in `ledger.observed`. Do not
ask questions whose answers exist in the repository.

### 2. Ask once

Bundle only materially outcome-changing preferences that remain undiscoverable. Each question
carries context, the `DEC-*` decisions it closes, two to six mutually exclusive options whose
`effects` state exactly what the option freezes, plus a recommended and a default option.

Present every question together. `build-dossier` may be rebuilt while unresolved; one
`resolve-dossier` call applies explicit selections, adopts declared defaults for omissions, and
closes the Dossier permanently.

### 3. Draft and design once

Draft the authorized goal, in/out scope, success conditions, risk boundary, requirements, and the
initial Task closures. Then open exactly one Designer session with the whole Plan, repository
access, and write access to `Plan.json`. It may add, remove, split, merge, reorder, or redesign
Tasks; change prerequisites, interfaces, schemas, algorithms, state, ownership, risk handling, and
acceptance; and run the validators.

The Designer must preserve goal, selected options, global scope, and authority. It completes and
self-corrects the Plan in the same session. Never dispatch it again. `close-designer-session`
verifies correlation only and restores any authorized field the Designer touched, so a design session
can always be closed; any remaining gap is listed by `check-readiness` and repaired by the native
main.

### 4. Authorize once

`authorize-plan` is the single gate. It proves decision completeness, graph validity, handoff
mapping, ownership independence, acceptance coverage, and regression contracts; optionally proves
the host harness with `--verify-command` without mutating declared inputs; then seals the revision,
records authorization, and creates `Checkpoints.json`.

Host Plan Mode approval may be inherited only when the approved artifact binds this exact semantic
specification.

### 5. Execute without interruption

Read `next-action` and dispatch the full eligible frontier. Serialize only the short state writes;
native Workers may run concurrently. Each Worker receives one compiled brief containing the exact
Task, relevant decisions, direct upstream outputs, and execution policy — never an opaque ID.

Bind every returned host ID to its dispatch, and never bind one host ID to two live dispatches.
Spawn return is not completion. Silence, elapsed time, or context compaction is not failure; record
`delegation-failed` only for a conclusive refusal, unavailability, terminal failure, or a
host-confirmed terminated child with no final callback. At the retry ceiling `next-action` reports
`complete_in_main` and the native main completes that same role contract.

After a Worker returns, run `accept-task`. If focused regression fails the Task enters
`worker_correction`: repair it in the native main and rerun `accept-task`, or run `dispatch-task`
again to send exactly one correction Worker. Keep ordinary compile, type, test, integration, and
implementation defects inside the same Task.

When implementation reveals a plan defect, resolve it in this order:

1. selected decision options;
2. authorized goal, scope, and risk boundary;
3. existing public repository contracts;
4. the safest reversible compatible behavior; and
5. the simplest implementation that meets the Plan.

For an in-scope change, open a continuation, revise only unstarted work, reseal, and continue
without Designer or user interaction. If it requires new scope, credentials, irreversible action, or
unavailable infrastructure, mark only that Task `blocked_by_authority` or
`blocked_by_environment`, continue independent Tasks, and report it once at final handoff.

### 6. Review once and finish

After every Task reaches a terminal state and no continuation is open, open the sole Reviewer
session. It receives the full Plan, all changes, tests, evidence, impacted shared paths, and the list
of Tasks that require rendered evidence. It reviews end to end, directly repairs every in-scope
defect, strengthens tests, exercises the real interface when required, and finishes with the complete
regression.

If that regression fails, repair inside this same session and run `close-reviewer-session` again;
the session stays open and closable. Never dispatch a second Reviewer. Once the session closes, no
production code may change.

## Task contract

Every Task freezes a stable `TASK-*` code, title, outcome, in/out scope, prerequisites, inputs,
`OUT-*` outputs with guarantees, write ownership and exclusive shared resources, tier
(`standard` or `complex`), verification (`code`, `visual`, or `hybrid`), requirements, risk tags,
design decisions, `AC-*` Given/When/Then acceptance with an exact oracle and evidence, and focused
regression commands with fingerprint paths.

Record only the design dimensions a Worker actually needs. Every requirement and output the Task
owns must be covered by executable acceptance. An elevated risk tag requires the `complex` tier.
Independent Tasks may run concurrently only when graph reachability, write ownership, and exclusive
resources prove that concurrency safe.

## Command entry points

All commands use `scripts/manifest_tool.py`.

- Authoring: `init-plan`, `build-dossier`, `resolve-dossier`.
- Design and authorization: `open-designer-session`, `close-designer-session`, `check-readiness`,
  `authorize-plan`.
- Continuation: `begin-continuation`, `close-continuation`.
- Delivery: `next-action`, `dispatch-task`, `bind-agent`, `agent-complete`, `delegation-failed`,
  `main-complete`, `accept-task`, `block-task`.
- Closure: `open-reviewer-session`, `close-reviewer-session`.
- Inspection: `validate`, `status`, `tree`, `schema manifest|plan|task|question|checkpoints`.

Removed v1 and v2 commands — Node, Gate, capability, rewire, repair-plan, decision-session,
seal-plan, render-plan, import-plan-edits, check-host-readiness, visual-verifier, and generic
dispatch — do not exist. Their absence is part of the v3 contract.

## Progressive references

- General design principles, only when maintaining or auditing Better Plan itself or resolving a
  cross-cutting workflow tradeoff: `references/design-principles.md`
- State formats, lifecycle, and command contracts: `references/state.md`
- Leaf contracts: `references/designer.md`, `references/worker.md`, `references/reviewer.md`
- Designer pattern decisions, when a structural choice is non-trivial: `references/design-patterns.md`
- Host roles, installation, and Doctor: `references/host-configuration.md`
