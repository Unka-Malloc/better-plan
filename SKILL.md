---
name: better-plan
description: Complete-delivery planning for large refactors, migrations, high-risk changes, and real parallel multi-Task delivery. It consolidates user decisions once, compiles one Designer's structured solution draft into the Plan, then executes without mid-delivery questions and closes through one write-capable Reviewer.
---

# Better Plan

Better Plan is a complete-delivery protocol. It freezes the whole authorized outcome before any
Worker starts, then executes one Designer-authored parallel Task frontier with executable evidence.
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

- multiple independently acceptable Tasks that form a real parallel frontier;
- a complete migration or refactor that removes an old generation;
- coordinated schema, data, protocol, state, concurrency, security, privacy, or release work; or
- a long delivery whose result must remain executable after context loss.

Maintaining the Better Plan source repository itself uses the ordinary native repository workflow.
Do not create a repository-local Better Plan workspace merely to edit this package.

## Non-negotiable protocol

- Keep secrets, personal or machine identity, absolute local paths, runtime endpoints, and backend
  runtime data out of state, prompts, evidence, and reports.
- Treat existing native role files and receipts as immutable local configuration. Better Plan may
  install a missing role matrix once, but no later install, update, repair, Doctor result, or user
  request authorizes editing, replacing, adopting, re-signing, or regenerating it. Receipt drift is
  report-only; continue skill, Hook, plugin, and adapter updates around the local roles.
- `Plan.json` is the sole semantic source; `Manifest.json` indexes Plans; `Checkpoints.json` holds
  execution state only; `Plan.md` is a render-only projection that is never parsed back. `Design.md`
  and its pristine archive are pre-authorization compiler inputs, never semantic state.
- Every Task belongs to one mutually independent parallel frontier. Dependent implementation work
  stays inside one Task; Python fixes the v3 `prerequisites` and `inputs` fields to empty arrays.
- Every Task contains one static Node DAG. The Designer exposes all safe concurrency, Python
  generates and validates `NODE-*` references, and the Worker executes every ready Node
  concurrently, waiting only at declared joins. Nodes never gain separate roles or lifecycle state.
- A Task is one independently acceptable observable outcome. File lists, development phases,
  generic investigation, design, approval, and final review are not Tasks.
- Present at most one Decision Dossier per Delivery Plan and resolve it exactly once. Never ask a
  sequence of granular questions that one coherent choice can close.
- Dispatch exactly one Designer. During its exclusive session it writes one complete structured
  `Design.md` solution into the neutral field-only skeleton precreated at the canonical draft path;
  Python derives canonical codes, mappings, defaults, and `Plan.json.spec`.
- Make the compiler finish diagnostic work in one pass. Every conversion error identifies its exact
  Design line and canonical Plan field; unmapped content identifies its exact line range. Never make
  an agent rediscover locations or split a generic error by manually reparsing the draft.
- Dispatch exactly one Reviewer. It directly repairs code, tests, documentation, and generated
  artifacts after Python runs the complete regression, receives its precise diagnostics, obtains
  rendered evidence when required, and never spends model time supervising that regression.
- After authorization, never ask the user another question. Apply the frozen decision precedence,
  revise unstarted in-scope work autonomously, continue independent branches, and report hard
  authority or environment blockers only at final handoff.
- Started Task contracts and evidence are frozen. A continuation may add or replace unstarted work
  but cannot expand goal, scope, user decisions, elevated risk, or irreversible authority.
- Run one focused regression per Task. After all Tasks finish, Python runs the complete regression
  as the independent `run-full-regression` stage outside model time. Only after that stage completes
  may `open-reviewer-session` dispatch the Reviewer. The native main forwards the stage's ephemeral
  privacy-safe diagnostics with the dispatch; `open-reviewer-session` never executes tests. Reuse
  an unchanged green receipt; rerun the independent stage only after Reviewer repairs change
  covered paths or the prior run failed, and resume the same Reviewer from new diagnostics if needed.

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

### 3. Pass requirements and design once

Pass the authorized goal, in/out scope, success conditions, risk boundary, requirements, resolved
decisions, and repository facts to exactly one Designer with repository access and the documented
`Design.md` format. The native main does not pre-design Tasks. The Designer creates the Task
boundaries and keeps every dependency inside one Task so all resulting Tasks are mutually
parallel-safe. Inside each Task it declares a minimal Node DAG with no avoidable ordering edge. It
may change interfaces, schemas, algorithms, state, ownership, risk handling, and acceptance, and run
`compile-design --check` when useful.

Pass the `assignment` returned by `open-designer-session` to the sole Designer unchanged.

The Designer must preserve goal, selected options, global scope, and authority. It completes and
self-corrects the solution in the same session without authoring canonical IDs or schema mechanics.
Never dispatch it again. `close-designer-session` restores immutable fields, archives the pristine
draft, compiles the candidate spec, and always reaches `ready`. Structure, content, or unmapped
conversion issues are returned by `next-action` in one self-contained repair brief; the native main
completes `Plan.json` and runs `compile-design --apply` instead of redispatching the Designer.
Each reported issue already carries the precise Design line and canonical Plan field needed for
repair; use those locations directly instead of repeating compiler analysis.
After the Designer returns, `Design.md` is read-only. Without a draft, the existing direct-write
path remains valid.

### 4. Authorize once

`authorize-plan` is the single gate. It proves decision completeness, one parallel frontier,
ownership independence, acceptance coverage, and regression contracts; optionally proves
the host harness with `--verify-command` without mutating declared inputs; then seals the revision,
records authorization, and creates `Checkpoints.json`.

Host Plan Mode approval may be inherited only when the approved artifact binds this exact semantic
specification.

### 5. Execute without interruption

Read `next-action` and dispatch the full eligible frontier. Serialize only the short state writes;
native Workers may run concurrently. Each Worker receives one compiled brief containing the exact
Task, relevant decisions, authorized scope, and execution policy — never an opaque ID.
Within that Task, the Worker runs every ready Node concurrently and waits only when a Node declares
all predecessors of a real join.

Bind every returned host ID to its dispatch, and never bind one host ID to two live dispatches.
Spawn return is not completion. Silence, elapsed time, or context compaction is not failure; record
`delegation-failed` only for a conclusive refusal, unavailability, terminal failure, or a
host-confirmed terminated child with no final callback. At the retry ceiling `next-action` reports
`complete_in_main` and the native main completes that same role contract.

Before the first role dispatch, apply the native host's exact spawn, capacity, identity, and
completion rules from `references/host-configuration.md`. Host-imposed batching never changes Task
contracts or authorizes an unconfigured fallback role.

After Workers return, run `accept-task` concurrently for the entire awaiting Task frontier. Python
locks only the short state snapshot and result commit; each Task's declared command list keeps its
own order. If focused regression fails the Task enters `worker_correction`: repair it in the native
main and rerun `accept-task`, or run `dispatch-task` again to send exactly one correction Worker.
Keep ordinary compile, type, test, integration, and implementation defects inside the same Task.

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

After every Task reaches a terminal state and no continuation is open, run the independent
`run-full-regression` stage outside the workspace lock. It records only the regression receipt in
Checkpoints and returns precise privacy-safe diagnostics ephemerally to the native main. Then
`open-reviewer-session` only validates that current receipt, opens the sole Reviewer, and returns
its compiled audit brief. Forward the immediately preceding diagnostics with that brief. The
Reviewer audits source and tests, directly repairs every in-scope defect, and never runs or waits
for the complete regression.

After the Reviewer returns, `next-action` either closes against an unchanged green receipt or names
`run_full_regression`. A failed independent rerun yields diagnostics for the same Reviewer session;
never dispatch a second Reviewer. `close-reviewer-session` performs no tests. Once the session
closes, no production code may change.

## Task contract

Every Task freezes a stable `TASK-*` code, title, outcome, in/out scope, `OUT-*` outputs with
guarantees, write ownership and exclusive shared resources, tier
(`standard` or `complex`), verification (`code`, `visual`, or `hybrid`), requirements, risk tags,
design decisions, `AC-*` Given/When/Then acceptance with an exact oracle and evidence, and focused
regression commands with fingerprint paths. Python emits empty `prerequisites` and `inputs`
compatibility fields; the workflow has no cross-Task scheduling edges. Each Task also contains a
non-empty static `NODE-*` DAG of `{code, title, outcome, prerequisites}`.

Record only the design dimensions a Worker actually needs. Every requirement and output the Task
owns must be covered by executable acceptance. An elevated risk tag requires the `complex` tier.
The Designer must merge coupled work until every Task has disjoint write ownership and exclusive
resources. It then minimizes each Task's Node edges so every ready branch can run concurrently.
Nodes share the Task's Worker, ownership, acceptance, and Checkpoint; they add no orchestration state.

## Command entry points

All commands use `scripts/manifest_tool.py`.

- Authoring: `init-plan`, `build-dossier`, `resolve-dossier`.
- Design and authorization: `open-designer-session`, `compile-design --check|--apply`,
  `close-designer-session`, `check-readiness`, `authorize-plan`.
- Continuation: `begin-continuation`, `close-continuation`.
- Delivery: `next-action`, `dispatch-task`, `bind-agent`, `agent-complete`, `delegation-failed`,
  `main-complete`, `accept-task`, `block-task`.
- Closure: `run-full-regression`, `open-reviewer-session`, `close-reviewer-session`.
- Inspection: `validate`, `status`, `tree`, `schema manifest|plan|task|question|checkpoints|design`.

Removed v1 and v2 top-level commands — Node, Gate, capability, rewire, repair-plan, decision-session,
seal-plan, render-plan, import-plan-edits, check-host-readiness, visual-verifier, and generic
dispatch — do not exist. Their absence is part of the v3 contract.

## Progressive references

- End-to-end user workflow, including every command, role handoff, prompt, recovery branch, and
  close step: `references/workflow.md`
- General design principles, only when maintaining or auditing Better Plan itself or resolving a
  cross-cutting workflow tradeoff: `references/design-principles.md`
- State formats, lifecycle, and command contracts: `references/state.md`
- Leaf contracts: `references/designer.md`, `references/worker.md`, `references/reviewer.md`
- Designer draft syntax: `references/design-format.md`
- Main-thread conversion repair: `references/structure-repair.md`
- Designer pattern decisions, when a structural choice is non-trivial: `references/design-patterns.md`
- Host roles, installation, and Doctor: `references/host-configuration.md`
