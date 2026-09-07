---
name: better-plan
description: Complete-delivery planning for large refactors, migrations, high-risk changes, and real parallel multi-Task delivery. It consolidates material user decisions, compiles one Designer's structured solution draft into the Plan, executes ordinary in-scope work autonomously, and closes through one write-capable Reviewer.
---

# Better Plan

Better Plan is a complete-delivery protocol. It freezes the whole authorized outcome before any
Worker starts, then executes one Designer-authored parallel Task frontier with executable evidence.
The latest user request is always authoritative; stored state never grants work by itself.

## Internal operating guidance

Understand the user's request and inspect repository facts first. Use Better Plan only for large
delivery. Use a Decision Dossier only for material choices that cannot be discovered. After
authorization, resolve ordinary implementation decisions autonomously. Promptly surface missing
user input or authority, prepare the concrete decision within existing authorization, and continue
independent work while awaiting the required answer. Existing approval requirements still apply. Run
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
  install a missing role matrix once, but no later install, update, uninstall, repair, Doctor result, or user
  request authorizes editing, replacing, adopting, re-signing, or regenerating it. Receipt drift is
  report-only; continue skill, Hook, plugin, and adapter updates around the local roles.
- `Plan.json` is the sole semantic source; `Manifest.json` indexes Plans; `Checkpoints.json` holds
  execution state only; `Plan.md` is a render-only projection that is never parsed back. `Design.md`
  and its pristine archive are pre-authorization compiler inputs, never semantic state.
- Every Task belongs to one mutually independent parallel frontier. Dependent implementation work
  stays inside one Task; Python fixes the v3 `prerequisites` and `inputs` fields to empty arrays.
- Every Task declares `worker: general|frontend` independently from its standard/complex tier. For
  a Codex frontend Task, the native main checks the local `frontend-worker` before doing frontend
  implementation: a valid configured role must be dispatched, while an absent optional role falls
  back to the Task's exact standard/complex Worker.
- Every Task contains one static Node DAG. The Designer exposes all safe concurrency, Python
  generates and validates `NODE-*` references, and the Worker executes every ready Node
  concurrently, waiting only at declared joins. Nodes never gain separate roles or lifecycle state.
- A Task is one independently acceptable observable outcome. File lists, development phases,
  generic investigation, design, approval, and final review are not Tasks.
- Present at most one Decision Dossier per Delivery Plan; resolve it once only when needed. With no
  material undiscoverable choice, keep `not_required` and proceed without a question or empty Dossier.
  Never ask a sequence of granular questions that one coherent choice can close.
- Dispatch exactly one Designer. During its exclusive session it writes one complete structured
  `Design.md` solution into the neutral field-only skeleton precreated at the canonical draft path;
  Python derives canonical codes, mappings, defaults, and `Plan.json.spec`.
- Make the compiler finish diagnostic work in one pass. Every conversion error identifies its exact
  Design line and canonical Plan field; unmapped content identifies its exact line range. Never make
  an agent rediscover locations or split a generic error by manually reparsing the draft.
- Dispatch exactly one Reviewer. It directly repairs code, tests, documentation, and generated
  artifacts after Python runs the complete regression, receives its precise diagnostics, obtains
  rendered evidence when required, and never spends model time supervising that regression.
- Task ownership never limits Reviewer repair authority inside the authorized Plan. The Reviewer
  leaves confirmed defects outside that Plan untouched and returns the complete structured
  `out_of_scope_findings` array after every response. The native main records it before regression
  or close; only after the current Plan closes does Python create separate unapproved draft repair
  Plans, which the native main must report to the user rather than silently discard or execute.
- The Reviewer never creates a Git commit. After a successful close, Python returns a
  `version_control_handoff` and the native main owns the final archival judgment: if the project is
  a Git repository, inspect the final worktree, preserve unrelated changes, and create exactly one
  commit for the completed Delivery Plan on the current branch using the repository's normal Git
  conventions; otherwise skip Git. Committing must not change production files.
- After authorization, do not ask for ordinary implementation decisions or reconfirm existing
  permission. Only the native main requests newly missing user input or authority. Record a pending
  request with `record-task-input`; continue independent work and preserve explicit approval gates.
  Silence, defaults, and a recorded answer never authorize expanded Plan semantics.
- Started Task goals, guarantees, ownership, design, risk, acceptance semantics, and historical
  evidence are frozen. After the Worker returns, a continuation may correct an unfinished Task's
  focused-regression commands or paths to preserve the same oracle, with a recorded reason and fresh
  focused evidence. Completed Task definitions remain immutable. Other continuation edits apply only
  to unstarted work and cannot expand scope, user decisions, elevated risk, or irreversible authority.
- Run each Task's focused regression to establish current acceptance after implementation or
  correction. After all Tasks finish, Python runs the complete regression
  as the independent `run-full-regression` stage outside model time. Only after that stage completes
  may `open-reviewer-session` dispatch the Reviewer. The native main forwards the stage's ephemeral
  privacy-safe diagnostics with the dispatch; `open-reviewer-session` never executes tests. Reuse
  an unchanged green receipt; rerun the independent stage only after Reviewer repairs change
  covered paths or the prior run failed, and resume the same Reviewer from new diagnostics if needed.

## Delivery guardrails

- Protect machine identity, personal data, credentials, ciphertext, backend runtime data, and other
  private operational details in every prompt, state file, command result, evidence item, screenshot,
  and report. Persist and return only privacy-safe summaries and repository-relative paths.
- Keep every proposal and change minimal, value-driven, and tied to the user's explicit outcome.
  Avoid speculative scope, redundant hashes, defensive layers, fallback branches, repeated
  validation, and broad regression that do not materially improve the delivered behavior.
- When algorithms or data structures materially affect the solution, study suitable proven
  open-source implementations and choose the simplest applicable practice that reduces complexity,
  repeated computation, memory use, or scheduling cost while improving caching and concurrency.
- When the authorized work is a refactor or migration, complete the migration in one coherent
  delivery and remove the superseded implementation, documentation, and compatibility path. Prove
  removal with a one-time targeted script or command; do not preserve it as a permanent test or gate.
- Close work through the smallest independently acceptable capability, module, or scenario. Keep
  edits and focused checks inside that closure, then move to the next closure without absorbing
  unrelated work.
- Use the narrowest useful checks during delivery. Run the first complete regression only after all
  Worker changes are integrated and focused evidence is green. Reuse green evidence while covered
  inputs are unchanged; a failed run or later repair requires verification through the same stage.
  Do not repeatedly consume shared resources or disturb concurrent Workers for unchanged green
  evidence. Report ordinary defects promptly and fix them within existing authorization. If project
  rules explicitly reserve full-regression failures for a developer decision, obtain that decision
  before dependent repairs or reruns; a routine progress report adds no approval gate.

## Delivery sequence

### 1. Explore before asking

Inspect the affected capability, its current contracts, tests, schemas, interfaces, state owners,
failure behavior, and delivery tooling. Record source-grounded facts in `ledger.observed`. Do not
ask questions whose answers exist in the repository.

### 2. Resolve material choices when needed

If no material choice remains undiscoverable, keep `dossier.status = not_required` and go directly
to the Designer; neither `build-dossier` nor `resolve-dossier` nor a user confirmation is required.
Otherwise bundle the remaining outcome-changing preferences. Each question
carries context, the `DEC-*` decisions it closes, two to six mutually exclusive options whose
`effects` state exactly what the option freezes, plus a recommended and a default option.

Present every question together. `build-dossier` may be rebuilt while unresolved; one
`resolve-dossier` call applies explicit selections, adopts declared defaults for omissions, and
closes the Dossier permanently.
Defaults apply only to ordinary preferences. They cannot supply missing authority, override an
explicit user instruction, or count as approval of an irreversible or otherwise reserved action.

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
The gate records authorization; it does not necessarily ask for a new approval. Use
`inherited_implementation_request` only when an existing explicit implementation request covers the
same concrete specification with no added choice, scope, risk, or reserved action. A general request
to investigate or refactor does not approve an unseen design. Otherwise present the complete Plan
and obtain the required explicit approval. Never reauthorize an already sealed Plan.

### 5. Execute within authorization

Read `next-action` and dispatch the full eligible frontier. Serialize only the short state writes;
native Workers may run concurrently. Each Worker receives one compiled brief containing the exact
Task, relevant decisions, authorized scope, and execution policy — never an opaque ID.
Forward each Designer, Worker, and Reviewer dispatch's `role_reference` with its complete brief.
New first-install roles read the referenced contract from the installed skill before acting.
Existing local role constraints remain authoritative; a skill update does not rewrite them.
Within that Task, the Worker runs every ready Node concurrently and waits only when a Node declares
all predecessors of a real join.

Bind every returned host ID to its dispatch, and never bind one host ID to two live dispatches.
Spawn return is not completion. Silence, elapsed time, or context compaction is not failure; record
`delegation-failed` only for a conclusive refusal, unavailability, terminal failure, or a
host-confirmed terminated child with no final callback. At the retry ceiling `next-action` reports
`complete_in_main` and the native main completes that same role contract.

Verification and regression commands have no framework-imposed execution deadline. Observation
windows determine when to report progress, not when to terminate work. Preserve explicit user
cancellation and any project-required deadline expressed by the declared command.

Group eligible Tasks by the exact returned `agent_type` only for prompt construction. Reuse the
returned Worker assignment byte-for-byte as each group's prompt prefix and append the individual
compiled brief as its suffix. This stable prefix is specifically for higher prompt-cache hit rate
and Token efficiency; Tasks still dispatch separately and concurrently, and never share one live
host agent ID.

Before the first role dispatch, apply the native host's exact spawn, capacity, identity, and
completion rules from `references/host-configuration.md`. Host-imposed batching never changes Task
contracts or authorizes an unconfigured fallback role.

Before every host wait or sleep, explicitly set an adaptive timeout instead of using the system
default. Estimate completion percentage and remaining work from `Difficulty`, `Workload`, observed
progress, elapsed time, and prior comparable experience; give heavy or early-stage work longer
windows, shorten only when completion is plausibly near, and re-estimate after every progress signal
or expired wait.

Optional helpers, when useful: run `python3 scripts/task_shape.py <Plan.json> --task TASK-001` after
a Task is compiled to summarize its DAG and verification shape. Before choosing a wait window, run
`python3 scripts/wait_hint.py --workload heavy --elapsed 1800 --progress 35 --history 4800` to combine
your progress estimate with prior durations. Both tools are read-only suggestions and may be skipped.

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

For an in-scope change, open a continuation and revise unstarted work. For a started but unfinished
Task, wait for its Worker's final callback and correct only the focused-regression command or path
error without weakening its oracle. Reseal and rerun focused acceptance; retain all earlier evidence.
The continuation records the reason and before/after regression contract. Never rewrite a completed
Task or change ownership, guarantees, or acceptance to make a failure disappear.

If required input or authority is missing, promptly tell the native main. It records the affected
Task with `record-task-input --needed`, completes authorized preparation, and requests only the
remaining concrete input or approval. While the answer is pending, continue independent work and
do not accept that Task or close the Plan. After the actual answer or prerequisite is verified, use
`record-task-input --resolved` and continue the same delivery when the existing semantic authority
still covers it. This receipt grants no new permission and never replaces `authorize-plan`.
During review, resolution returns `resume_reviewer`; resume the same Reviewer and record its next
final callback and findings before closing. Availability of input is not completion evidence.
Expanded goal, scope, decisions, risk, or irreversible authority still needs a separately authorized
Plan; no continuation may inherit it. Only a proven hard blocker uses `block-task` and a blocked
final handoff, never a merely unanswered request. An unrelated confirmed defect follows the Reviewer
finding handoff below.

### 6. Review once and finish

After every Task reaches a terminal state and no continuation is open, run the independent
`run-full-regression` stage outside the workspace lock. It records only the regression receipt in
Checkpoints and returns precise privacy-safe diagnostics ephemerally to the native main. Then
`open-reviewer-session` only validates that current receipt, opens the sole Reviewer, and returns
its compiled audit brief. Forward the immediately preceding diagnostics with that brief. The
Reviewer audits source and tests, directly repairs every in-scope defect, and never runs or waits
for the complete regression.

After every Reviewer return, persist its complete findings array, including `[]`, with
`record-reviewer-findings`; this receipt is required before regression or close. `next-action` then
either closes against an unchanged green receipt or names `run_full_regression`. A failed
independent rerun yields diagnostics for the same Reviewer session; never dispatch a second
Reviewer. The resumed Reviewer returns the complete findings array again and the native main
re-records it. `close-reviewer-session` performs no tests. Once the session closes, no production
code may change. The close result lists every generated draft repair Plan and returns the terminal
`version_control_handoff`. Before the final user report, the native main checks whether the project
is a Git repository. In Git, it inspects the final worktree, excludes unrelated existing changes,
and creates one repository-conventional commit for this completed Plan on the current branch; in a
non-Git project it skips that action. The Reviewer and Python lifecycle commands never create the
commit. Include the commit outcome and every unapproved pending defect in the final user handoff.

## Task contract

Every Task freezes a stable `TASK-*` code, title, outcome, in/out scope, `OUT-*` outputs with
guarantees, write ownership and exclusive shared resources, tier
(`standard` or `complex`), workload (`light`, `medium`, or `heavy`), verification (`code`, `visual`,
or `hybrid`), Worker specialization (`general` or `frontend`), requirements, risk tags, design
decisions, `AC-*` Given/When/Then acceptance with an
exact oracle and evidence, and focused regression commands with fingerprint paths. Python emits
empty `prerequisites` and `inputs`
compatibility fields; the workflow has no cross-Task scheduling edges. Each Task also contains a
non-empty static `NODE-*` DAG of `{code, title, outcome, prerequisites}`.

Record only the design dimensions a Worker actually needs. Every requirement and output the Task
owns must be covered by executable acceptance. The Designer chooses `standard` or `complex`
holistically from causal coupling, unknowns, tradeoffs, failure impact and reversibility, and
verification difficulty. Risk tags and surface size are evidence, never automatic tier triggers.
It separately marks relative execution workload from breadth, touchpoints, critical-path depth,
integration work, and verification volume without estimating clock time; workload does not select
the Worker tier.
The Designer must merge coupled work until every Task has disjoint write ownership and exclusive
resources. It then minimizes each Task's Node edges so every ready branch can run concurrently. Nodes
share the Task's Worker, ownership, acceptance, and Checkpoint; they add no orchestration state.

## Command entry points

All commands use `scripts/manifest_tool.py`.

- Authoring: `init-plan`, `build-dossier`, `resolve-dossier`.
- Design and authorization: `open-designer-session`, `compile-design --check|--apply`,
  `close-designer-session`, `check-readiness`, `authorize-plan`.
- Continuation: `begin-continuation`, `close-continuation`.
- Delivery: `next-action`, `dispatch-task`, `bind-agent`, `agent-complete`, `delegation-failed`,
  `main-complete`, `accept-task`, `record-task-input`, `block-task`.
- Closure: `run-full-regression`, `open-reviewer-session`, `record-reviewer-findings`,
  `close-reviewer-session`.
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
- Token-only main-thread waste, timeout statistics, and parallel efficiency audits:
  `skills/efficiency-inspector/SKILL.md`
