---
name: better-plan
description: Design-first Better Plan workflow guide for structured workspaces with lightweight, risk-proportional execution.
---

# Better Plan

Better Plan is a guidance and state-transition aid for planning, coding, or explicit implementation
work. The latest user request is authoritative; a Plan is a revisable model of that request, never
an independent instruction.

## Activation

1. At session start, detect a structured workspace with
   `scripts/manifest_tool.py discover <project-root>`.
2. If no unique valid workspace exists, silently continue with ordinary project handling.
3. Even when a workspace exists, consider Better Plan only for planning, coding, or explicit
   implementation work. Never infer work from a pending or active Node.
4. Use repository-relative paths and exclude secrets, machine identity, personal data, and backend
   runtime output from plans, prompts, evidence, and responses.

## One capability, one lifecycle

One user-visible capability maps to one selected implementation Node and one lifecycle. The Node
UUID is its lifecycle identity; acceptance revision, implementation repair, focused regression,
and audit remain inside that same lifecycle.

Completion must not select or start a next or different Node. Adjacent findings, possible follow-up
work, and any newly discovered capability return to the native main, which compares them with the
latest user request before deciding what to do.

## End-to-end closure policy

- Complete one end-to-end user-visible capability in one pass. Do not split ordinary planning,
  scaffolding, compilation, focused testing, or review into separate Nodes or repeated dispatch
  cycles.
- Freeze acceptance exactly once before implementation and perform exactly one independent review
  after the focused regression. Do not add a separate acceptance-review dispatch.
- Resolve ordinary compiler, type, lint, import, and local integration errors during the same
  implementation dispatch.
- Open a repair cycle only when evidence identifies a real design error or product-semantics error.
  Ordinary implementation defects stay inside the current implementation closure and do not reopen
  design or acceptance.
- Run only the selected Node's focused tests during its closure. Run the full regression exactly
  once, after every implementation Node in the requested delivery is complete.

## Native-main alignment

For planning, coding, or explicit implementation work:

1. Derive the requested outcome, constraints, observable acceptance target, and non-goals before
   reading planning state.
2. Inspect only repository evidence and Plan material plausibly related to that request.
3. Correct or create the one Node that represents the capability. Keep its Requirements, Evidence,
   Architecture, regression contract, and minimal scaffold current without rewriting unrelated
   planning history.
4. Treat engineering design dimensions—files, symbols, interfaces, errors, algorithms, data
   structures, state, cache, isolation, and concurrency—as heuristic candidates. Select only those
   applicable to the change's behavior and material risk; do not invent decisions or boilerplate
   merely to fill headings.
5. For planning-only requests, finish the requested Plan work and return to the user without
   selecting executable work. When the request authorizes implementation, use execution selection
   only to authorize a leaf dispatch for that Node. Invalid authority or no eligible work returns
   to native-main planning; repair relevant planning state if useful, but
   never auto-dispatch or loop.

## Bounded lifecycle routing

Automatic routing is limited to objective actions correlated to the selected Node:

- one acceptance-design dispatch freezes the acceptance contract and may route directly to an
  executor, or to the final regression for a final-validation Node;
- executor exit runs the declared focused regression;
- a passing focused regression may route to the lifecycle's sole independent read-only auditor.

Acceptance rejection, preparation drift, regression failure, audit findings, completion, and new
scope return to the native main. `main_acceptance_decision` may revise the same Node explicitly,
narrow its current capability, defer it, or proceed when the evidence supports that choice; it does
not map to a leaf role or choose another Node.

Deferral is a visible, non-terminal scheduling decision: use the manifest tool's `defer` command,
and use `activate` before the capability may become executable again. `skipped` is reserved for an
irreversible waiver or not-applicable outcome and must never represent promised follow-up work.
Every wait on another Better Plan Node belongs in workspace-wide `prerequisites`; prose,
`status_reason`, Plan nesting, and `next` never create execution dependencies.

When delegated state is unchanged, do not repeat status or progress reports. Use the host's waiting
capability and report only completion, blocking, a needed decision, or a material scope change.

Quiet waiting is a communication heuristic: it does not time or poll delegated work, does not
interrupt, cancel, or replace a child agent lifecycle, and is not an execution, completion, or
failure gate. Agent lifetime and cancellation remain owned by the host framework.

## Role boundaries

Load exactly one role reference for the role currently active; do not merge leaf prompts.

- Main orchestration: `references/orchestration-main.md`
- Acceptance designer: `references/acceptance-designer.md`
- Executor: `references/executor.md`
- Auditor: `references/auditor.md`

Planned focus paths guide architecture; they are not filesystem permission boundaries. A write role
may make necessary adjacent changes inside the current capability and must report them to the native
main. Reviewers and auditors remain read-only. No leaf mutates Plan state, criteria, or receipts.

## Host and state boundaries

- Supported lifecycle events are `session-start`, `prompt-submit`, and Agent-only
  `agent-complete`.
- Session and prompt Hooks provide bounded guidance only.
- Agent completion may reduce one correlated write-role exit and return one parent directive. It
  never launches an agent, continues a stopped child, denies a prompt, or selects another Node.
- All state transitions and contract checks use `scripts/manifest_tool.py`.
- `start`, `check`, and `complete` are not implementation-acceptance shortcuts.

## Minimal commands

- `scripts/manifest_tool.py discover <project-root>`
- `scripts/manifest_tool.py next-action <node-id> [workspace]`
- `scripts/manifest_tool.py dispatch <node-id> [workspace] --role ...`
- `scripts/manifest_tool.py advance <node-id> ...`
- `scripts/manifest_tool.py defer <node-id> [workspace] --reason ...`
- `scripts/manifest_tool.py activate <node-id> [workspace]`
- `scripts/manifest_tool.py validate [workspace]`

## role references

Conditionally load exactly one applicable reference while that role is active:

- Load `references/orchestration-main.md` only while the native main aligns the selected capability,
  decides scope, or dispatches a reported action.
- Load `references/acceptance-designer.md` only for an acceptance-designer dispatch.
- Load `references/executor.md` only for an executor dispatch.
- Load `references/auditor.md` only after focused regression selects the read-only auditor.
