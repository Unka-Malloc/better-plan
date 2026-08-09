# Better Plan v3 State Protocol

The CLI schemas are authoritative:

```sh
python3 scripts/manifest_tool.py schema manifest
python3 scripts/manifest_tool.py schema plan
python3 scripts/manifest_tool.py schema task
python3 scripts/manifest_tool.py schema question
python3 scripts/manifest_tool.py schema checkpoints
```

Every state file carries an exact `better-plan.*/v3` marker. Missing markers and earlier
generations fail closed; there is no translation layer.

## Workspace

```text
Manifest.json
<delivery-directory>/
  Plan.json          # sole semantic source
  Plan.md            # render-only projection, never parsed back
  Checkpoints.json   # created only by authorization
```

`Manifest.json` indexes Delivery Plans and marks the workspace root for Hook detection. It owns no
semantic delivery status.

`Plan.json` is the semantic source. Its approval-relevant digest covers schema, code, title, intent,
ledger, Dossier, and spec. Mutable sessions and receipts never change that digest, so an authorized
digest stays stable across dispatches.

`Checkpoints.json` appears only after authorization. It binds the sealed revision and digest and
stores Task status, dispatch correlation, evidence, and freshness. It never duplicates Task
definitions.

## Identity

Stable codes are the only identity: `PLAN-*`, `REQ-*`, `TASK-*`, `OUT-*`, `AC-*`, `Q-*`, `DEC-*`.
No agent ever authors a UUID. Runtime correlation handles are minted by Better Plan, live only in
lifecycle and Checkpoint receipts, and never enter the semantic payload. Codes never renumber or
reuse after deletion.

## Lifecycle

```text
draft → designing → ready → authorized → completed
                              authorized → revising → authorized
                              authorized → blocked
```

`blocked` is a final delivery state when the sole Reviewer proves a hard blocker. A sealed revision
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

## Intent and ledger

`intent` contains goal, in/out scope, success conditions, risk boundary, and autonomy. The four
autonomy values are fixed: in-scope revision allowed, Reviewer repairs allowed, mid-execution
questions forbidden, and blocked branches continue independent work. Authorization makes goal,
scope, user choices, and elevated risk immutable.

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
forces a new Plan. `resolve-dossier` runs exactly once: it records explicit selections in
`user_decided`, applies declared defaults into `defaulted`, clears the resolved `DEC-*` codes from
`unresolved`, and closes the Dossier permanently.

## Task

Before design, a Task requires code, title, outcome, scope, prerequisites, ownership, difficulty,
verification, requirements, and risks. Authorization additionally requires inputs, outputs, design,
acceptance, and focused regression.

`prerequisites` is the only graph. Every direct prerequisite must be matched by at least one input
`{from, output, guarantee}` that names a real upstream output. Consumers are derived by the
validator, never stored twice. Prose, document order, and output order never create scheduling
edges.

`design` is an object of lowercase keys to concrete decision lines. Record the dimensions the Task
actually needs — interfaces, schemas, data flow, algorithms, state, concurrency, error handling,
recovery, or test seams — and omit the rest instead of writing filler.

Independent Tasks must have non-overlapping write paths and no common exclusive shared resource.
The validator rejects unsafe parallelism instead of silently serializing it. Every declared output
artifact must fall inside its own Task's write ownership, so a Task can never promise a handoff at a
path it does not own.

Every acceptance criterion records `covers`, Given/When/Then, an exact oracle, and an evidence
contract. Together, a Task's criteria must cover every requirement and output it owns; a `covers`
entry naming an unowned `REQ-*` or `OUT-*` is rejected as a typo. Focused regression is the only
Task completion path.

Risk tags come from one fixed vocabulary. An elevated tag — migration, removal, security, privacy,
irreversible_side_effect, release, public_interface, schema, protocol, persistent_state,
concurrency, shared_resource, performance, operations — requires the `complex` Worker tier.
`observability` and `quality` do not.

## Privacy boundary

Secret-shaped data, absolute local paths, UNC shares, loopback names, and bare IP literals are
rejected anywhere in canonical state. Public `https://` documentation references, shell globs such as
`tests/**/*.py`, and ordinary prose about bearer authentication are all allowed, so a legitimate
plan never enters a rewording loop. Command output is never persisted: only
`{command_sha256, outcome, exit_code, recorded_at}` receipts are stored, while a bounded failure
tail is printed to stderr for the operator.

Declared-path fingerprints are receipts, never gates. A path a Task has not produced yet is recorded
as absent, so a greenfield Task dispatches and completes normally; only symlinks and non-relative
paths are hard errors.

## Authorization and uninterrupted continuation

Authorization binds source, an opaque reference digest, the semantic digest, risk reasons, and the
autonomy policy. Sources are `explicit`, `inherited_host_plan`, or
`inherited_implementation_request`.

An authorized continuation may change only unstarted execution specification. It records its reason,
preserves every started Task definition by digest, passes readiness, increments the revision, and
updates Checkpoint bindings atomically. Goal, scope, user decisions, and newly introduced elevated
risk require new authorization; execution never asks for it mid-run and instead marks the affected
branch blocked.

Task statuses are `pending`, `in_progress`, `completed`, `blocked_by_authority`, and
`blocked_by_environment`. Dispatch phases are `worker_running`, `worker_correction`, and
`awaiting_acceptance`.

## Commands

| Command | Contract |
| --- | --- |
| `init-plan` | create one draft Plan and its projection |
| `build-dossier` | load or replace the single Dossier while it is unresolved |
| `resolve-dossier` | apply explicit selections and declared defaults exactly once |
| `open-designer-session` | create the sole direct-write Designer session |
| `close-designer-session` | verify correlation, restore any authorized field the Designer touched, reach `ready`, and report open issues |
| `check-readiness` | list every remaining readiness issue in one pass |
| `authorize-plan` | the single gate: readiness, optional harness verification, seal, and Checkpoints |
| `begin-continuation` / `close-continuation` | revise unstarted in-scope work without questions |
| `next-action` | name one action for every phase and every delivery state |
| `dispatch-task` | dispatch one eligible Task, or re-dispatch one correction Worker |
| `bind-agent` | bind one opaque host agent id to one dispatch |
| `agent-complete` | consume one exact final callback |
| `delegation-failed` | record a conclusive delegation failure and raise the fallback |
| `main-complete` | record native-main completion of an exhausted delegation |
| `accept-task` | run focused regression and complete exactly one Task |
| `block-task` | record an authority or environment blocker and propagate downstream |
| `open-reviewer-session` | dispatch the sole Reviewer with its rendered-evidence Task list |
| `close-reviewer-session` | close after full regression passes or a hard blocker is proven; a failed run keeps the same session closable after repair |
| `validate`, `status`, `tree`, `schema` | inspect v3 workspace truth |
