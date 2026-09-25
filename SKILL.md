---
name: better-plan
description: Complete-delivery planning for large refactors, migrations, high-risk changes, and real parallel multi-Task delivery. It consolidates material user decisions, compiles one Designer's structured solution draft into the Plan, executes ordinary in-scope work autonomously, and closes through one write-capable Reviewer.
---

# Better Plan

Freeze the whole authorized outcome, execute one Designer-authored parallel Task frontier, and
close with executable evidence and one writable Reviewer. The latest user request is authoritative;
stored state never grants work by itself. Run `next-action` when delivery state is unclear.

## Activation and source-repository exemption

Use the native main's ordinary workflow for one small closure that can be understood, implemented,
and verified directly. Activate Better Plan for independently acceptable parallel Tasks, a complete
migration or refactor, coordinated schema/data/protocol/state/concurrency/security/privacy/release
work, or a long delivery that must remain executable after context loss.

Maintaining the Better Plan source repository itself uses the ordinary native repository workflow.
Do not create a repository-local Better Plan workspace merely to edit this package.

## Load context by role and stage

This file is the native main's entry point. Forward each dispatch's exact `role_reference`, compiled
brief, and returned assignment to the selected role. Leaf roles read their own reference from the
installed skill; do not attach this main-thread guide, other roles' instructions, interim transcripts,
or the complete command walkthrough to every dispatch. Existing local role constraints remain
authoritative; skill updates cannot rewrite them.

- Designer: `references/designer.md`, then `references/design-format.md` for its required draft.
  Load `references/design-patterns.md` only for a non-trivial structural choice.
- Worker and Hybrid Worker: `references/worker.md`. Its brief supplies the complete Task, owned
  requirements, authorized goal/scope/success/risk boundary, global architecture, and all resolved
  decisions. v3 has no reliable Task applicability link for ledger decisions; do not guess a filter.
  Read other original Plan context only as needed via `plan_path`.
- Reviewer: `references/reviewer.md`. Its brief supplies the semantic Plan, all Task evidence, one
  regression receipt, and rendered-evidence Task codes. Forward the preceding stage's ephemeral
  diagnostics separately. Original records remain at `plan_path` and `checkpoints_path`.
- Native main: consult the relevant section of `references/workflow.md` for command examples,
  `references/state.md` for schemas and lifecycle contracts, and `references/structure-repair.md`
  when conversion requires repair. Before the first dispatch, read `references/host-configuration.md`
  for the host's exact role, spawn, capacity, identity, and completion rules.
- General principles: `references/design-principles.md`, only when maintaining or auditing Better Plan itself
  or resolving a cross-cutting workflow tradeoff.
- Token, wait, and parallel-efficiency audits: `skills/efficiency-inspector/SKILL.md`.

Keep fixed role rules in those references and delivery-specific facts in briefs. Forward each brief
unchanged instead of appending paraphrased policy or a second copy of its source records.
Record paths are relative to the CLI workspace root; supply its repository-relative location with
the dispatch so roles can find the original files without searching.

## Delivery guardrails

- Protect machine identity, personal data, credentials, ciphertext, backend runtime data, runtime
  endpoints, and private operational details in prompts, state, commands, evidence, screenshots,
  and reports. Use privacy-safe summaries and repository-relative paths.
- Treat existing native role files and receipts as immutable local configuration. Create a role
  matrix only when no same-name configuration or receipt exists. Install, update, uninstall, repair,
  Doctor, migration, and explicit replacement requests never authorize editing, removing, adopting,
  re-signing, or regenerating existing roles or receipts. Drift is report-only; update skills, Hooks,
  plugins, and adapters around them without displacing unrelated agents.
- Create the workspace in the main repository, never inside a linked Git worktree: a workspace there
  forks one delivery into two sealed revisions that cannot be reconciled. `init-plan` refuses it and
  names the alternative — create the workspace in the main repository and point `Manifest.json`
  `project_root` at the delivery directory — and `--worktree-workspace` exists only to accept the
  split deliberately.
- `Plan.json` is the sole semantic source; `Manifest.json` indexes Plans; `Checkpoints.json` holds
  execution state. `Plan.md` is render-only and never parsed back. `Design.md` and its pristine
  archive are pre-authorization compiler inputs, never semantic state.
- Keep changes minimal, value-driven, and tied to the explicit outcome. Reject speculative scope,
  redundant hashes, defensive layers, fallback branches, and repeated validation without benefit.
  When algorithms or data structures matter, study suitable proven open-source implementations;
  choose the simplest practice that reduces complexity, repeated computation, memory, or scheduling
  cost while improving caching and concurrency.
- Complete an authorized migration in one coherent delivery, removing superseded code, documentation,
  and compatibility paths. Prove removal with a one-time targeted script or command, not a permanent
  test or gate. Close the smallest independently acceptable capability, module, or scenario without
  absorbing unrelated work.
- Report ordinary defects promptly and fix them within existing authorization. A report adds no
  approval gate. Only the native main asks for genuinely missing user input or authority, after
  preparing a concrete decision; continue independent work while it is pending. Silence, defaults,
  and recorded answers never grant expanded authority. Preserve explicit project approval rules,
  including developer decisions before dependent repairs or reruns after complete-regression failures.

## Functional readiness before performance (mandatory)

For an application or service delivery, establish real product usability before benchmark
implementation or validation, load/capacity experiments, profiling, or performance optimization.
This is an execution prerequisite, not another user-approval ceremony:

1. Implement or repair functional behavior and run the owning focused correctness checks.
2. Start the actual candidate through its supported entry points. Verify backend readiness and a
   representative authorized operation; where the product includes a frontend, verify its actual
   browser rendering and an action against that same backend. Verify the required end-to-end
   protocol path and observable result, including normal shutdown. A CLI-only substitute does not
   establish the usability of a product that also delivers a frontend.
3. Record the candidate/configuration, executed checks, expected and observed results, safe evidence
   references, and `passed|failed|not_run|blocked` outcomes. Only current passing functional evidence
   permits dependent performance work. Relevant candidate, runtime, routing, configuration, or
   frontend/backend changes invalidate that evidence and require the affected focused checks again.
4. Only then run the authorized benchmark/performance work, followed by the declared final regression
   and review. The prerequisite is a bounded functional check, not repeated full regression.

Builds, typechecks, unit/Mock tests, benchmark-tool self-tests, health checks alone, image construction,
package inspection, and receipts for another candidate cannot replace this prerequisite. Calling a
performance activity a fixture, independent tool Task, or separate repository does not bypass it.
Mock controllable external services where appropriate, not the product frontend, backend, or measured
integration. Do not launch performance work in parallel with the work needed to establish usability.

Put this real dependency in the Task's Node DAG and acceptance before authorization. A separate
performance delivery must consume actual prerequisite evidence before dispatch; an upstream Plan's
existence or authorization is not evidence. If an already-started Plan omitted the prerequisite,
pause dependent work and use the existing input/continuation rules without rewriting sealed history
or fabricating a pass. Missing credentials/environment/authority are reported, never worked around.
The native main enforces this ordering even if `next-action` reports a structurally eligible command;
the CLI's structural readiness is not proof of runtime usability. Do not invent a new receipt format
or parallel gate framework when existing verification records can carry the evidence.

## Delivery sequence

### 1. Inspect and resolve material choices

Inspect repository contracts, tests, schemas, interfaces, state owners, failure behavior, and tools.
Record source-grounded facts in `ledger.observed`; do not ask for discoverable information.

If no material undiscoverable choice remains, keep `dossier.status = not_required` and open the
Designer without an empty Dossier or confirmation. Otherwise present all questions together in
at most one Decision Dossier. Each question gives context, resolved `DEC-*` codes, two to six mutually
exclusive options with frozen `effects`, and recommended/default selections. `build-dossier` may be
rebuilt while unresolved; one `resolve-dossier` call applies explicit selections and ordinary
preference defaults for omissions, then closes it permanently. Defaults cannot supply authority,
override explicit instructions, or approve irreversible or reserved actions.

### 2. Design once and compile

Pass the confirmed goal, in/out scope, success conditions, risk boundary, requirements, resolved
decisions, and repository facts to exactly one fresh-context Designer in its exclusive session.
Forward the `assignment` returned by `open-designer-session` unchanged. Do not pre-design Tasks or
enlist the Reviewer early.
The Designer writes the complete solution into the neutral field-only `Design.md` skeleton,
self-corrects in that session, and may run `compile-design --check`.

For performance-related work, freeze the functional-readiness evidence and predecessor ordering
defined above. Do not make frontend/backend validation a later cleanup item after benchmarking.

Every Task is one independently acceptable observable outcome, with disjoint write ownership and
exclusive resources. Keep all dependencies inside Tasks so the whole frontier is parallel-safe. A
Task is also one Worker session, so keep its execution shape inside the single-session ceiling that
readiness enforces; split into more Tasks instead of grouping past that budget.

Each Task freezes scope, guaranteed `OUT-*` outputs, requirements, risk, binding design decisions,
`AC-*` Given/When/Then oracles and evidence, focused commands and paths, and a static `NODE-*` DAG.
Expose all safe Node concurrency and wait only at declared joins. Nodes share the Task's role,
acceptance, and Checkpoint; Python fixes cross-Task `prerequisites` and `inputs` to empty arrays.
File lists, phases, investigation, approval, and final review are not Tasks.

Two Workers share every frontier, and the Task field names responsibility rather than strength: a
Task declares `worker: code|hybrid`, runs on the packaged `worker` role when its own commands prove
the result, and on `hybrid-worker` when the result is also judged visually and therefore owes
rendered evidence. `Verification` repeats that answer (`code` or `hybrid`), so the two fields always
agree and readiness rejects a Task that says one thing in each field; a Plan sealed before the
rename may still carry the legacy values `general` (reads as `code`) and `frontend` (reads as
`hybrid`). There is no tier to choose and no `Difficulty` field. Workload (`light|medium|heavy`) is
the separate execution-volume estimate that tells the native main how much observation a running
Task deserves; it is not a clock estimate and selects no role. Record only useful design dimensions
and cover every owned requirement and output with executable acceptance; implementation
recommendations leave Workers room for judgment inside binding guarantees.

`close-designer-session` restores immutable fields, archives the pristine draft, compiles canonical
codes/mappings/defaults into `Plan.json.spec`, and reaches `ready`. Each conversion issue identifies
the exact Design line/range and canonical Plan field. Use those locations directly; do not repeat
compiler analysis. If `next-action` returns a repair brief, the native main completes `Plan.json`
and runs `compile-design --apply`. Never redispatch the Designer or edit its returned draft. Without
a draft, the existing direct-write path remains valid.

### 3. Authorize the concrete specification

`authorize-plan` proves decisions, frontier independence, ownership, acceptance coverage, and
regression contracts; optionally verifies the host harness with `--verify-command` without mutating
inputs; then seals the revision and creates Checkpoints. It records authority, not necessarily a
new user vote. Host Plan Mode approval must bind this exact semantic specification.

Use `inherited_implementation_request` only when an existing explicit implementation request covers
this concrete specification without added choices, scope, risk, or reserved actions. A general
investigation or refactor request does not approve an unseen design. Otherwise present the complete
Plan for explicit approval. Never reauthorize an already sealed Plan.

### 4. Dispatch and observe the full frontier

Use `next-action` to dispatch all eligible Tasks separately and concurrently; serialize only short
state writes. Structural eligibility never overrides the functional-readiness prerequisite for
performance work. Pass the exact `--native-host codex|claude|cursor|kilo` so the returned
`agent_type` matches that host's installed role names. For a hybrid Task, the native main checks the
host's hybrid role before implementation: a valid configured role must be dispatched; an absent role
falls back to the `worker` role. Host batching never changes contracts or permits an
unconfigured fallback.

Group prompts by the exact returned `agent_type`. Reuse the returned Worker assignment byte-for-byte
as the group's prefix and append each Task's compiled brief. This improves prompt-cache hit rate and
Token efficiency. Tasks never share one live host agent ID. Bind each returned host identity to its
exact dispatch and use the host completion rules from `references/host-configuration.md`.

Spawn return is not completion. Silence, elapsed time, context compaction, and an expired observation
window are not failure or cancellation evidence. Record `delegation-failed` only for conclusive
refusal, unavailability, terminal failure, or host-confirmed termination without a final callback.
At the retry ceiling, `next-action` returns `complete_in_main` for the same role contract.

Before every host wait or sleep, explicitly set an adaptive timeout instead of using the system
default. Estimate completion percentage and remaining work from `Workload`, observed progress,
elapsed time, and prior comparable experience; give heavy or early-stage work longer
windows, shorten only when completion is plausibly near, and re-estimate after every progress signal
or expired wait. Verification commands have no framework-imposed execution deadline. Observation
windows determine progress reporting, never termination; preserve explicit cancellation and any
project-required deadline expressed by the declared command.

### 5. Accept Tasks and handle missing prerequisites

After final Worker callbacks, run `accept-task` serially for the awaiting frontier: one returning
Task at a time, in the same build directory. Python locks only the snapshot and result commit;
commands inside each Task retain their declared order.
A focused failure enters `worker_correction`: repair ordinary defects in the native main and rerun
acceptance, or use `dispatch-task` for one correction Worker with the same frozen contract. Worker
development checks do not replace this canonical acceptance.
A Worker that returns `task-exceeds-session` is handing back a Task one session could not carry, not
reporting a failure: run acceptance the same way, and let its outcome decide between completion and one
correction Worker that carries the remaining frontier under the same frozen contract.

Resolve implementation choices by selected options, authorized goal/scope/risk, existing public
contracts, safest reversible compatible behavior, then the simplest adequate code. For a Plan defect,
open a continuation for in-scope revisions to unstarted work. Started goals, guarantees, ownership,
design, risk, acceptance, and historical evidence stay frozen. After a Worker's final callback, an
unfinished Task may correct only focused-regression commands or paths while preserving the oracle;
record the reason and before/after contract, reseal, and obtain fresh focused evidence. Completed Task
definitions remain immutable. No continuation expands scope, decisions, risk, or irreversible authority.

For missing input or authority, use `record-task-input --needed`, prepare the concrete request, and
pause only dependent work. Do not accept that Task or close the Plan while its request is pending.
After verifying the actual answer/prerequisite, use `--resolved` and continue under existing authority;
the receipt grants no permission and availability is not completion evidence. During review, resume
the same Reviewer and record its new final callback and findings. Expanded authority requires a
separately authorized Plan. Use `block-task` only for a proven hard blocker, never an unanswered request.

### 6. Run complete regression, review once, and close

Use narrow focused checks during implementation. Run the first complete regression only after all
Worker changes are integrated, focused evidence is green for completed Tasks, every Task is terminal,
and no input request or continuation remains. Python executes `run-full-regression` outside the
workspace lock and model time, stores its receipt, and returns ephemeral privacy-safe diagnostics.
Respect any required developer decision on failures before dependent repairs or reruns.

Only then call `open-reviewer-session`; it validates the current receipt and opens the sole fresh
Reviewer without running tests. Forward its brief and the preceding diagnostics. The role reference
owns source, test, design, diagnostic, and rendered-evidence auditing, in-scope repairs across Task
ownership, and structured out-of-scope findings. Keep interim collaboration transcripts out of this
audit and preserve the user's primary constraints.

After every Reviewer return or resume, record its complete `out_of_scope_findings` array (including
`[]`) with `record-reviewer-findings` before regression or close. `next-action` reuses an unchanged
green receipt; run the independent regression stage again only for failed or stale evidence after
repairs. New failure diagnostics return to the same Reviewer, subject to required developer decisions.
Never create a Repair Task or a second Reviewer, and never have the Reviewer supervise that stage.

`close-reviewer-session` runs no tests. Once it closes, production code must not change. Python creates
separate unapproved draft repair Plans from confirmed out-of-scope findings only after current Plan
closure. Report every such Plan; do not silently discard or execute it.

The Reviewer never creates a Git commit. A successful close returns `version_control_handoff`; the
native main inspects the final worktree, must preserve unrelated changes, and creates exactly one
commit for the completed Delivery Plan on the current branch using normal repository conventions
if the project is a Git repository; otherwise skip Git. Committing must not change production files.
Report the commit outcome, delivery evidence, blockers, and all unapproved pending defects.

## Command entry points

Use `scripts/manifest_tool.py` for lifecycle commands:

- Authoring: `init-plan`, `build-dossier`, `resolve-dossier`.
- Design/authorization: `open-designer-session`, `compile-design --check|--apply`,
  `close-designer-session`, `check-readiness`, `authorize-plan`.
- Continuation: `begin-continuation`, `close-continuation`, `supersede-decision`.
- Delivery: `next-action`, `dispatch-task`, `bind-agent`, `agent-complete`, `delegation-failed`,
  `main-complete`, `accept-task`, `record-task-input`, `block-task`.
- Closure: `run-full-regression`, `open-reviewer-session`, `record-reviewer-findings`,
  `close-reviewer-session`.
- Inspection: `validate`, `status`, `tree`, `report`,
  `schema manifest|plan|task|question|checkpoints|design`.

Removed v1/v2 Node, Gate, capability, rewire, repair-plan, decision-session, seal-plan, render-plan,
import-plan-edits, check-host-readiness, visual-verifier, and generic dispatch commands do not exist.
