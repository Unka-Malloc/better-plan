# Better Plan v3 State Protocol

The CLI schemas are authoritative:

```sh
python3 scripts/manifest_tool.py schema manifest
python3 scripts/manifest_tool.py schema plan
python3 scripts/manifest_tool.py schema task
python3 scripts/manifest_tool.py schema question
python3 scripts/manifest_tool.py schema checkpoints
python3 scripts/manifest_tool.py schema design
```

Every state file carries an exact `better-plan.*/v3` marker. Missing markers and earlier
generations fail closed; there is no translation layer.

## Workspace

```text
Manifest.json
<delivery-directory>/
  Plan.json          # sole semantic source
  Plan.md            # render-only projection, never parsed back
  Design.md          # neutral field skeleton, then optional Designer draft
  Design.pristine.md # immutable archive created by draft compilation
  Checkpoints.json   # created only by authorization
```

`Manifest.json` indexes Delivery Plans and marks the workspace root for Hook detection. It owns no
semantic delivery status.

`Plan.json` is the semantic source. Its approval-relevant digest covers schema, code, title, intent,
ledger, Dossier, and spec. Mutable sessions and receipts never change that digest, so an authorized
digest stays stable across dispatches.

`open-designer-session` creates a field-only `Design.md` at the Plan's canonical draft path without
adding solution examples. The untouched skeleton preserves the direct-write mode. A completed
`Design.md` is an optional authoring input, not semantic state. When it exists at Designer close,
Python compiles it into `Plan.json.spec`, archives the exact returned draft as `Design.pristine.md`,
and records a lifecycle receipt. The returned draft is then read-only. If conversion is incomplete,
the native main completes `Plan.json`; `compile-design --apply` verifies that repair without
recompiling the draft. Before authorization, workspace validation requires both files and their
pristine digest when a compile receipt exists. After sealing, the receipt digest is enough.

`Checkpoints.json` appears only after authorization. It binds the sealed revision and digest and
stores Task status, dispatch correlation, evidence, freshness, and the independent full-regression
receipt. It never duplicates Task definitions or stores command output.

## Identity

Stable codes are the only identity: `PLAN-*`, `REQ-*`, `TASK-*`, `NODE-*`, `OUT-*`, `AC-*`,
`Q-*`, `DEC-*`.
No agent ever authors a UUID. Runtime correlation handles are minted by Better Plan, live only in
lifecycle and Checkpoint receipts, and never enter the semantic payload. Codes never renumber or
reuse after deletion.

## Lifecycle

```text
draft → designing → ready → authorized → completed
                              authorized → revising → authorized
                              authorized → blocked
```

`blocked` is a final delivery state when the sole Reviewer proves a hard blocker, not a state for
merely unanswered user input. Record a pending prerequisite in a Task's optional `input_request`
instead; its status and historical evidence remain intact. A sealed revision
exists only from authorization onward: `authorize-plan` creates revision 1 and every closed
continuation increments it.

Receipts only move forward. A Plan carrying `lifecycle.sealed` can never return to `draft`,
`designing`, or `ready`, and `authorize-plan` refuses a Plan that is already sealed. An edit that
tries to rewind a live delivery fails validation instead of silently resetting Checkpoint evidence.
A `revising` Plan must carry its `continuation_session` receipt, so a lost receipt is a loud
validation error rather than a stuck phase.

The Designer and Reviewer session objects each have `count: 1`. Once a session exists, another
session of the same type is invalid even if delegation failed; the native-main fallback completes
the existing session. One host agent id may own only one live dispatch at a time, so a single final
callback can always be attributed to exactly one dispatch; an ambiguous callback advances nothing.

`run-full-regression` is an independent delivery stage. It runs outside the global lock, stores only
its receipt and covered-path fingerprint in `Checkpoints.json.full_regression`, and returns bounded
privacy-safe diagnostics ephemerally to the native main. `open-reviewer-session` executes no tests:
it only validates that current receipt and creates the Reviewer session. The native main forwards
the immediately preceding diagnostics with the dispatch brief. A green receipt is reused while
covered paths stay unchanged; a failed baseline or Reviewer repair makes `next-action` select the
independent regression stage again before the session can close.

Every final Reviewer return resets `reviewer_session.findings_recorded` to `false`.
`record-reviewer-findings` replaces the session's complete `out_of_scope_findings` array, adds a
null `followup_plan` receipt to each item, and marks that return recorded. An empty array is an
explicit receipt, not an omitted step. Neither post-review regression nor close may proceed until
the current return is recorded; a resumed Reviewer must return the complete array again.

Each finding contains exactly `title`, `summary`, `impact`, `evidence`, non-empty relative `paths`,
`scope_reason`, non-empty `success`, non-empty `risk_boundary`, and the tool-owned
`followup_plan`. Strings remain subject to the global privacy boundary. On close, after any required
green covered-path fingerprint has been checked, Python creates one separate unapproved `draft`
Plan per cohesive finding, records its `PLAN-*` code in `followup_plan`, and returns the pending
Plans for final user handoff. Creating the shell grants no authorization and starts no execution.
The close result sets `user_handoff_required` whenever any pending repair Plan exists.

The optional `designer_session.compile` receipt contains the pristine and compiled spec digests,
applied time, sections retained from the prior Plan, safe structure/content issues, and unmapped
line ranges and digests. It is lifecycle evidence and never enters the semantic digest. Any open
issue blocks authorization. A draft-free Designer session retains the existing direct-write behavior
and carries no compile receipt.

Every structure/content issue has exactly `{kind, message, line, field, status}`. `line` locates the
relevant `Design.md` source line and `field` names the canonical Plan target. Unmapped entries use
their exact `lines` range. Broad compiler errors without those locations are invalid receipts.

## Intent and ledger

`intent` contains goal, in/out scope, success conditions, risk boundary, and autonomy. The four
autonomy values are fixed: `allow_in_scope_revision: true`, `allow_reviewer_repairs: true`,
`forbid_mid_execution_questions: true`, and
`blocked_branch_policy: continue_independent_work`. Only the native main requests missing user input
or authority; leaf roles promptly report it to the native main. Authorization makes goal,
scope, user choices, and elevated risk immutable.

`forbid_mid_execution_questions` is the stable v3 storage name for prohibiting ordinary
implementation questions and repeated confirmation. It does not suppress genuinely missing user
input or an explicit approval requirement. Keep this persisted name so package updates preserve
existing semantic digests and authorization receipts. The runtime uses one v3 representation;
an update does not rename fields, reseal Plans, reset Checkpoints, or grant new authority.
Continuation recovery derives started Task status from Checkpoints, its existing source of truth,
and compares contracts with the session's prior Tasks; it needs no separate status snapshot.

The ledger contains exactly four classes:

- `observed`: `{fact, source}` repository facts;
- `user_decided`: `{source, option, resolves, effects}` for an explicit selection;
- `defaulted`: the same shape for an applied default;
- `unresolved`: `{code, statement, impact}` material decisions not yet closed.

Readiness rejects any unresolved item and requires one ledger record per Dossier question.

## Decision Dossier

```text
dossier: { status: not_required | draft | resolved, questions: [...] }
```

A question carries `code`, `question`, `context`, the `resolves` decision codes, two to six options,
`recommended`, `default`, and after resolution `selected`. Each option carries an `id`, a `label`,
and an `effects` array stating exactly what the option freezes.

`build-dossier` may be rebuilt while the Dossier is unresolved, so a malformed first attempt never
forces a new Plan. With no material undiscoverable choice, keep `not_required` and skip both Dossier
commands and any user confirmation. For a required Dossier, `resolve-dossier` runs once: it records explicit selections in
`user_decided`, applies declared defaults into `defaulted`, clears the resolved `DEC-*` codes from
`unresolved`, and closes the Dossier permanently.
Declared defaults fill ordinary preferences only; they cannot supply authority or replace explicit
approval. The native main checks this distinction before recording selections or authorizing.

## Task

The native main passes confirmed requirements to the Designer without pre-authoring Tasks. The
Designer creates every Task as one independently acceptable outcome and groups dependent
implementation work inside that same Task. Python generates the canonical Task structure and fixes
`prerequisites` and `inputs` to empty arrays, preserving the v3 Task frontier without cross-Task
ordering.

Each Task contains a non-empty static `nodes` DAG. A Node is exactly
`{code, title, outcome, prerequisites}`; its prerequisites may name only Nodes in that Task.
Python generates global `NODE-*` codes and rejects unknown references, self-dependencies, and
cycles. Nodes with satisfied prerequisites form the ready frontier, all of which the Worker executes
concurrently. A join names every branch it waits for. Nodes have no separate role, approval,
acceptance, Checkpoint status, or receipt; the Task remains the sole dispatch and acceptance unit.

`design` is an object of lowercase keys to concrete decision lines. Record the dimensions the Task
actually needs — interfaces, schemas, data flow, algorithms, state, concurrency, error handling,
recovery, or test seams — and omit the rest instead of writing filler.

All Tasks must have non-overlapping write paths and no common exclusive shared resource. The
validator rejects a Designer partition that is not one parallel frontier instead of introducing
ordering. Every declared output artifact must fall inside its own Task's write ownership.
Task-internal Nodes share that Task's ownership and acceptance boundary.

Every acceptance criterion records `covers`, Given/When/Then, an exact oracle, and an evidence
contract. Together, a Task's criteria must cover every requirement and output it owns; a `covers`
entry naming an unowned `REQ-*` or `OUT-*` is rejected as a typo. Focused regression is the only
Task completion path.

Risk tags come from one fixed vocabulary. They describe the Task and protect continuation boundaries;
they do not select the Worker tier mechanically. The Designer chooses `standard` or `complex`
holistically from the Task's coupling, unknowns, tradeoffs, failure consequences and reversibility,
and verification difficulty.

Every Task records `worker: general|frontend`. This specialization is independent from its
`difficulty` tier. A Codex frontend Task deterministically selects the valid local optional
`frontend-worker` when present; absence preserves the standard/complex tier selection.

Every Task also records `workload: light|medium|heavy`. This is the Designer's relative estimate of
execution volume across touchpoints, change breadth, critical-path depth, integration, and
verification. It is not an elapsed-time estimate and does not select the Worker tier.

## Privacy boundary

Secret-shaped data, absolute local paths, UNC shares, loopback names, and bare IP literals are
rejected anywhere in canonical state. Public `https://` documentation references, shell globs such as
`tests/**/*.py`, and ordinary prose about bearer authentication are all allowed, so a legitimate
plan never enters a rewording loop. Command output is never persisted: only
`{command_sha256, outcome, exit_code, recorded_at}` receipts are stored. Unsafe diagnostic lines are
redacted deterministically; a bounded safe failure tail is emitted ephemerally to the operator and
Reviewer brief, never written into Plan or Checkpoints.

Slash-namespaced host identities, including Codex canonical task names such as
`/root/<task_name>`, are opaque correlation tokens rather than filesystem paths. They are allowed
only as `host_agent_id` values and must be stored and matched unchanged; the same text remains
forbidden in every semantic, diagnostic, and report field.

Declared-path fingerprints are receipts, never gates. A path a Task has not produced yet is recorded
as absent, so a greenfield Task dispatches and completes normally; only symlinks and non-relative
paths are hard errors. Full-regression freshness excludes the current Plan's mutable `Plan.json`
and `Checkpoints.json`; their lifecycle and receipt writes are validated as workflow state and must
not invalidate the covered delivery inputs they describe.

## Authorization, pending input, and continuation

Authorization binds source, an opaque reference digest, the semantic digest, risk reasons, and the
autonomy policy. Sources are `explicit`, `inherited_host_plan`, or
`inherited_implementation_request`.
The last source applies only when a prior explicit implementation request covers this same concrete
specification without new choices, scope, risk, or reserved actions. An approved host artifact must
likewise bind the exact semantics. Otherwise obtain explicit Plan approval. The CLI records the
native main's authorization judgment; it cannot prove that consent exists from a source label or
reference string. Do not ask again when the same specification is already authorized.

An authorized continuation may revise unstarted execution specification. A started, unfinished
Task may change only its focused-regression commands or paths after its Worker returns, to correct
execution errors while preserving the same acceptance oracle. All other Task fields and every
completed definition stay frozen. The continuation records its reason and any
`execution_corrections` with `task`, `before`, and `after` regression contracts; it preserves old
evidence and requires fresh focused acceptance. It passes readiness, increments the revision, and
updates Checkpoint bindings. Goal, scope, user decisions, and newly introduced elevated risk still
require a separately authorized Plan; a recorded input resolution cannot authorize that expansion.

`record-task-input --needed` stores an optional safe summary in `Checkpoints.json.tasks[].input_request`.
It neither sends a question nor changes Task status, dispatch, evidence, or Plan semantics. The
native main prepares and asks the concrete missing question through the host. Independent Tasks
continue; `next-action` includes `awaiting_input` and returns `await_user_input` when only requests
remain. A request blocks its Task's dispatch/acceptance and final regression, Reviewer opening, and
Plan closure. `--resolved` removes it only after actual input or prerequisite resolution and appends
safe `user_input` evidence. Silence, defaults, and elapsed time are not resolution or approval.
When a Reviewer session is active, resolution clears its final-return flag and returns
`resume_reviewer`; the same Reviewer must finish the interrupted work and return a new final
callback and findings array before close. Input availability is not evidence of a completed audit.
If a prerequisite proves impossible within this delivery, `block-task` replaces the request with
a hard blocker. During an active review this also permits a completed Task with a recorded request
to become hard-blocked without rewriting its definition or historical evidence. Closed Plans never
reopen through the input command.

Task statuses are `pending`, `in_progress`, `completed`, `blocked_by_authority`, and
`blocked_by_environment`. Dispatch phases are `worker_running`, `worker_correction`, and
`awaiting_acceptance`.

## Commands

| Command | Contract |
| --- | --- |
| `init-plan` | create one draft Plan and its projection |
| `build-dossier` | load or replace the single Dossier while it is unresolved |
| `resolve-dossier` | apply explicit selections and declared defaults exactly once |
| `open-designer-session` | create the sole structured-design session and return its draft path plus the exact assignment the native main must forward |
| `compile-design --check` | compile in memory and return precise line-and-field conversion diagnostics plus readiness issues |
| `close-designer-session` | restore immutable fields, compile and archive a present draft, always reach `ready`, and report open issues |
| `compile-design --apply` | verify and record a native-main repair to `Plan.json` without changing or recompiling the archived draft |
| `check-readiness` | list every remaining readiness issue in one pass |
| `authorize-plan` | the single gate: readiness, optional harness verification, seal, and Checkpoints |
| `begin-continuation` / `close-continuation` | revise unstarted work or correct an unfinished Task's focused execution while preserving semantic authority |
| `next-action` | name one action for every phase and every delivery state |
| `dispatch-task` | dispatch one eligible Task, or re-dispatch one correction Worker |
| `bind-agent` | bind one opaque host agent id to one dispatch |
| `agent-complete` | consume one exact final callback |
| `delegation-failed` | record a conclusive delegation failure and raise the fallback |
| `main-complete` | record native-main completion of an exhausted delegation |
| `accept-task` | run one Task's focused regression outside the global lock; invoke concurrently across the awaiting Task frontier |
| `record-task-input` | record or resolve a missing user prerequisite without changing Task history or granting authority |
| `block-task` | record an authority or environment blocker for exactly one independent Task |
| `run-full-regression` | independently run the complete regression outside the lock, persist only its receipt, and return ephemeral safe diagnostics plus the next action |
| `open-reviewer-session` | validate current regression evidence and dispatch the sole Reviewer without executing tests |
| `record-reviewer-findings` | persist the complete structured out-of-scope finding array for the latest Reviewer return, including an explicit empty array |
| `close-reviewer-session` | close only against current green regression evidence; execute no tests |
| `validate`, `status`, `tree`, `schema` | inspect v3 workspace truth and the Design.md skeleton |

`dispatch.host_agent_id` is a framework-level opaque identity. It stores the exact bounded token
returned by the host, including slash-namespaced forms, without normalization or translation. A
host adapter may define which native callback field supplies that token, but it must never replace
the spawn identity with a second identifier. For Codex specifically, the child thread UUID exposed
by lifecycle Hooks is not the canonical task name returned by spawn, so the native main consumes the
exact final callback and submits the stored task name to `agent-complete`.
