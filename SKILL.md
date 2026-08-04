---
name: better-plan
description: Design-first native-main orchestration for large refactors, complete migrations, and high-risk multi-Node delivery. Small tasks use the native main's ordinary repository workflow. Do not activate it inside an already-dispatched native leaf whose installed role contract and task brief are complete, or merely to maintain the Better Plan source repository itself.
---

# Better Plan

Better Plan maps only the repository detail needed by the latest authorized request, then delivers
one cohesive capability through deterministic task-group state and native role agents. The latest
user request is always authoritative; stored state never authorizes work by itself.

## Activation gate and fast path

Better Plan is for large refactors, complete migrations, cross-module delivery, parallel
implementation, and work with consequential state or security boundaries. The native main decides
whether the latest request actually needs that machinery before reading Plan state.

Use the ordinary repository workflow when the native main can directly understand, implement, and
verify one small closure. Typical fast-path work includes copy or style changes, a local logic fix,
one-file maintenance, an explicit test addition, and other bounded changes without a real
cross-Node handoff. On the fast path the native main may reason and close the task in the simplest
safe way: do not discover, create, or mutate Better Plan state and do not dispatch Better Plan
roles. An existing Better Plan workspace, multiple touched files, or a prior Better Plan turn is
never sufficient reason to activate the workflow.

Activate Better Plan only when the request has at least one concrete large-delivery pressure:

- multiple independently acceptable implementation Nodes with a real handoff or parallel frontier;
- a complete migration or refactor that must remove an old generation without compatibility residue;
- coordinated cross-module, schema, data, protocol, or behavioral sequencing; or
- a high-risk security, state, concurrency, release, or visual boundary needing independent review.

When activation is not obvious, prefer the fast path. When activating, state the concrete pressure
briefly; never justify activation by file count alone.

## Non-negotiable rules

- Maintain the Better Plan source repository with its ordinary native workflow. Do not create or
  mutate repository-local Plan state except in an explicit product-behavior test.
- Keep secrets, personal or machine identity, backend runtime data, and absolute local paths out of
  Plan state, delegated prompts, evidence, and responses.
- The native main owns scope, authorization, Plan mutations, child correlation, decisions, and user
  communication. Leaves never mutate Plan state, criteria, receipts, or decision history.
- `Capabilities.json`, `Manifest.json`, and branch `Checkpoints.json` are canonical. Supporting
  documents are projections. `prerequisites` is the sole execution graph.
- Disclose only the selected root-to-leaf capability path. Record encountered siblings as
  `known/untouched`; never pre-model or inspect the whole repository.
- Treat observed mature architecture as established fact. Use a Designer only for new delivery
  design, not retrospective approval of observed ancestors.
- Never infer implementation authority from an existing Plan, pending Node, completion event, or
  adjacent finding.
- Progressive disclosure is an information-relevance rule, never a Token, word, character, or line
  quota. Tell each role every material fact, constraint, uncertainty, dependency, risk, and
  acceptance condition honestly. Omit only information that is irrelevant or redundant for that
  role; never hide useful context merely to shorten a prompt. A role may inspect any accessible
  skill, reference, repository file, or other local guidance it believes useful.
- Preserve every independent ready frontier. Reuse must not create artificial serialization.
- Run one focused regression per implementation Node and one full regression per task group. Extra
  runs require failure evidence, release policy, or an explicit user request.
- Pre-existing host files are immutable unless the user explicitly names the exact file and
  mutation. Receipts own only artifacts Better Plan created.
- A user request to converge quickly narrows exploration and repair to the accepted capability and
  known failure evidence. Aggregate related failures into the smallest repair batch, isolate
  unrelated pre-existing failures, and do not add reassurance checks or speculative Nodes.

## Progressive-disclosure router

Read this file completely. Start with the references required by the current action, and follow
additional references whenever they may resolve a real uncertainty or improve the work. Avoid
proactively loading unrelated or redundant material, but never block useful self-directed reading.

| Current action | Required reference |
|---|---|
| First role dispatch, role visibility, native configuration, install/update/Doctor, selector diagnosis | `references/host-configuration.md` |
| Discover, create, validate, inspect, or repair capability/Plan/Node state | `references/state-files.md` |
| Group planning, dispatch, correlation, recovery, Worker continuation, decisions, or regression closure | `references/orchestration-main.md` |
| Author a leaf brief | The matching primary role contract: `references/designer.md`, `references/worker.md`, `references/visual-verifier.md`, `references/reviewer.md`, or `references/visual-reviewer.md` |
| Designer pattern decision | `references/design-patterns.md`, supplied to Designer as explicit action-specific knowledge |

Before the first actual role dispatch in a conversation, read `host-configuration.md` and show its
complete role visibility table. Read-only analysis, history audits, workspace discovery, and state
inspection do not trigger this table. A valid installed matrix is runtime authority; never
ask the user to choose it over package recommendations. Any requested native role change must pass
the reference's fresh reconfirmation gate before edits.

After the activation gate selects Better Plan, for repositories other than Better Plan itself, run
`scripts/manifest_tool.py discover <project-root>`. If no unique valid workspace exists, continue
with ordinary handling.

## Planning kernel

Freeze a source-grounded intent spine before reading state: ownership, Purpose, Goal, Description,
status, real prerequisites, explicit non-dependencies, observable acceptance, and non-goals. Reuse
the stable capability key and matching nonterminal Plan before creating another.

An executable task group binds one examined in-scope `capability_key` and contains, in order:

1. exactly one `group_design` Node;
2. one or more `implementation` Nodes; and
3. exactly one Critical `final_validation` Node.

Every implementation directly depends on group design. Final validation directly depends on every
non-skipped implementation. Add other edges only for real artifact, data, schema, migration, or
behavioral handoffs. Independent Nodes own disjoint paths, consume stable interfaces, and run
concurrently.

## Delivery kernel

- Designer runs once for the whole ordered group and selected capability scope. It reads the local
  pattern catalog and freezes cross-Node handoffs and executable acceptance; it never implements.
- Each Worker turn owns one Node. Every code-profile Worker completion runs focused regression
  directly, including Critical code Nodes. Only `visual` or `hybrid` Critical implementation Nodes
  dispatch one Visual Verifier, which directly repairs visual defects before focused regression; it
  is never redispatched for a regression contract error.
- Express exceptional independent security review as an explicit implementation Node with its own
  ownership and acceptance, executed by a Worker. Never restore a universal verification role or
  mechanically attach security review to every Critical Node.
- After a Node reaches `accepted`, prefer the same idle Worker for the next eligible dispatch with
  the same `worker_continuation_key`. Each continuation keeps an independent dispatch, callback,
  regression, and acceptance boundary. On Codex use `followup_task`. Spawn only when no compatible
  idle Worker exists, continuation fails, or the Worker cannot safely perform the next task.
- Reviewer runs exactly once after all implementations. It repairs autonomous findings and reports
  genuine trade-offs as `decision_issues`. After decisions, run full regression once. A failure may
  create a bounded repair Node and rerun regression, never a second Reviewer.
- `visual` and `hybrid` Critical verification and final review require real browser, vision, and
  rendered evidence. Source, DOM text, snapshots, or build success are not substitutes.

## Delegation and recovery kernel

For a new leaf, spawn the dispatched native `agent_type` with `fork_turns: "none"`, the payload's
explicit selector, and a compact task-specific brief authored by the native main. Bind the real
opaque child ID, then wait for the exact final turn callback. Spawn or continuation return is not
completion; mismatched, early, unrelated, and replayed callbacks are no-ops.

Silence, elapsed time, missing artifacts, context compaction, or a wait timeout is not failure.
Never interrupt or cancel a bound child to accelerate delivery. A main-initiated `interrupted` or
`cancelled` status cannot consume an attempt. Record failure only for spawn refusal, confirmed
unavailability, or an independent terminal-failed host notification for the exact bound child.

One dispatch permits at most three delegation attempts: pinned role, same-role retry, then one
capability-equivalent temporary selector. At the ceiling, the native main performs the exact role
from the bounded payload and records `main-complete`. Delegation failure alone never blocks an
authorized task.

Keep a conversation-scoped availability circuit breaker for exact host/provider/model failures.
After the host conclusively reports a selector unavailable, do not attempt that same selector for
later Nodes in the conversation; resolve each dispatch normally, then immediately take its allowed
main-thread or capability-equivalent fallback. The breaker never persists to Plan state and never
changes the installed role matrix.

## Command entry points

- Discovery/state: `discover`, `validate`, `tree`, `capability-tree`, `status`
- Selection: `next-action <node-id> [workspace] [--native-host codex]`
- Delivery: `check-plan-readiness`, `preflight-regression`, `dispatch`, `bind-agent`, `agent-complete`, `delegation-failed`, `main-complete`
- Closure/decisions: `advance`, `repair-plan`, `open-decision-session`, `record-decision`, `resolve-decision`, `close-decision-session`

All commands run through `scripts/manifest_tool.py`. Use the exact syntax and state invariants from
the routed reference; never hand-edit lifecycle state.
