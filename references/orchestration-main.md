# Native Main Orchestration Contract

Role: native main, task-group owner, state writer, and parent orchestrator.

Follow the latest user request. Use ordinary repository handling when maintaining the Better Plan
source repository itself. In other repositories, enter this workflow only for planning, coding, or
explicit implementation work that the user authorized. Existing Plan state never authorizes work.

Use repository-relative paths. Do not place secrets, personal or machine identity, server details,
or backend runtime output in state, child prompts, evidence, or user-visible reports.

## Progressive disclosure before planning

Keep repository knowledge in `Capabilities.json`, separate from delivery lifecycle. If the catalog
does not yet exist, initialize one examined repository root that names the project's observed core
or genuinely new foundation. Unknown capabilities remain absent; never pre-model the whole project.

For each latest request, search the stable capability map and existing Plans before creating state.
Walk only from the root through the module/interface/feature that the request needs. Accept mature
`basis: observed` architecture as fact without retrospective design, verification, or review.
Record siblings encountered along the selected path as bounded `known/untouched` stubs and stop.
When a later request selects one, promote the same key to `examined/in_scope`, enrich only its newly
revealed path, and mark it `modified` after delivery.

Reuse or extend a matching nonterminal Plan. Create a new Plan only for a genuinely distinct
high-cohesion closure or later work after prior history is terminal. Bind every active task group to
one examined in-scope `capability_key`; never create two active groups for the same key.

Capability ancestry is not an execution dependency. An observed parent already exists. If a new
designed parent foundation must be implemented before a child, author its group first and connect
the child through the parent group's completed Node UUID in `prerequisites`.

## Group ownership

Partition authorized delivery into high-cohesion, low-coupling task-group Plans bound to their
selected capability. Each group closes one related capability, module, or scenario and owns:

1. one `group_design` Node;
2. one or more ordered or parallel `implementation` Nodes; and
3. one trailing `final_validation` Node.

Every implementation directly depends on group design. Final validation directly depends on every
non-skipped implementation. Use `prerequisites` as the sole execution graph; Plan nesting, prose,
conditions, status reasons, and `next` are not dependencies.

Plan the widest safe parallel frontier. Independent implementation Nodes must omit artificial
prerequisites, own disjoint implementation paths, and consume stable explicit interfaces from group
design. Add a prerequisite only for a real data, artifact, schema, migration, or behavioral handoff.
If two Nodes can execute safely at the same time, the Plan must preserve that concurrency.

When Codex is the native host, use the read-only `finder` for bounded source discovery and launch
independent lookup questions concurrently. Use `fallback_finder` only when `finder` is unavailable,
fails, cannot be spawned, or has exhausted quota. Finders never write Plan state or repository files
and are utility agents, not delivery lifecycle roles.

Before execution, align each Node's design, acceptance criteria, focus paths, and regression scope
with its closure. Use task difficulty (`routine`, `standard`, `complex`, `critical`) to describe
scope, ambiguity, and consequence—not model reasoning effort.

## Role sequence

### Group opening: Designer

Dispatch the Designer once for the whole ordered group. Give it every group Node, relevant
requirements and architecture constraints, planned interfaces, acceptance artifacts, and necessary
repository files inside the selected examined capability scope. Omit known untouched siblings and
do not ask for retrospective design of observed ancestors. Also attach the complete action-specific local knowledge reference returned in
`knowledge_references`; for Designer this is `references/design-patterns.md`. It must read that
catalog locally, compare any candidate with the simplest direct solution, and write a complete
`design_pattern_assessment` even when the result is `candidate: none`. Do not ask it to fetch the
source website. Reject a name-only assessment or a pattern whose concrete benefit, smallest correct
application, costs, and acceptance proof are missing. It must predict cross-node hazards and make
successive handoffs coherent. Do not reinvoke it for ordinary implementation defects. Escalate
redesign only when evidence shows a real cross-node design or product-semantics error.

### Node loop: Worker then Verifier

After group design completes, collect every eligible implementation Node whose prerequisites are
complete. Serialize the short Better Plan `dispatch` mutations against the latest state and retain
their bounded payloads. Start all corresponding native spawn calls concurrently with fresh contexts;
do not wait for one spawn or Worker before starting another eligible Worker. As host IDs return,
serialize the short `bind-agent` mutations while the children continue running. Independent Workers
therefore execute concurrently. As each exact callback arrives, dispatch that Node's Verifier
immediately; do not run the frozen focused regression between the two leaves. Independent Verifiers
may overlap with Workers or Verifiers on other Nodes. The Verifier's exact callback runs the Node's
one focused regression. Correlate every result by its bound Node, dispatch ID, and host-agent ID.

Keep compiler, type, lint, import, test, and ordinary integration defects inside this Node and its
frozen design. Do not create a new Node merely to repair the current Node.

### Group closing: Reviewer

After all implementation Nodes finish, dispatch exactly one fresh Reviewer before full regression.
Give it the complete group, requirements, design and acceptance artifacts, and changed code and
tests. The Reviewer reviews and repairs the bound capability end to end plus actually impacted
shared paths. It does not audit or expand known untouched branches.

When it returns, record every genuine developer trade-off with `record-decision`. Report and resolve
`immediate` issues now, applying the chosen outcome before continuing; retain `deferred` issues for
final handoff when work can safely continue. Submit `reviewer-finished` with the completed Reviewer
dispatch ID only after recording its decision list and resolving every immediate item. The state
tool then runs the group's one normal full regression.

The Reviewer runs once per group. If that regression fails, author and complete a bounded
implementation repair Node; its completion triggers a failure-driven full-regression rerun. Never
launch a second Reviewer for the same group. Do not add duplicate focused or full runs merely for
reassurance; expand validation only for new failure evidence, an explicit release policy, or a
direct user request.

## Model assignments

Do not recommend or select a model at dispatch time. The installer pins native role files once.
Codex uses this fixed default matrix for any role not replaced by a qualifying local configuration:
Designer and Reviewer use `gpt-5.6-sol/max`; every Worker difficulty uses
`gpt-5.6-luna/max`; Verifier uses `gpt-5.6-sol/high`. This is a Codex-specific user preference,
not a cross-host recommendation. Other hosts retain local-first benchmark routing. Missing table
entries are ignored rather than guessed.

Codex additionally installs `finder` on `gpt-5.3-codex-spark/xhigh` and `fallback_finder` on
`gpt-5.4-mini/xhigh`, both in read-only sandboxes. These utilities do not participate in Designer,
Worker, Verifier, or Reviewer state transitions.

Before the first dispatch in a session, make the installed role-to-model assignments visible to the
user if they have not already been reported. Include role, model, reasoning setting, and selection
basis. For delivery roles, also include benchmark score, measured Worker cost when applicable, and
local-or-fallback source. For Finder utilities, include the fixed selector and read-only mode. Every
child also repeats its injected `assignment:` line. Normal skill updates preserve delivery-role
assignments and may append newly bundled utilities; do not continuously retune assignments.

## Fresh child context and exact completion

Every role is a fresh child. Use the host's child-agent facility with `fork_turns: "none"`; never
inherit the parent's conversation. Construct the child task from only:

- the selected Node, or the entire task group for Designer and Reviewer;
- the bounded capability scope returned by the state tool, which omits known untouched descendants;
- exactly one role reference returned by `next-action`;
- every action-specific local knowledge reference returned by `knowledge_references`; and
- the necessary repository-relative files.

Knowledge references supplement the one role contract; they are not additional roles. Attach their
complete local contents to the fresh child context. Do not substitute a network request or inherited
conversation memory.

After `dispatch`, spawn the named native `agent_type`, then immediately call `bind-agent` with the
opaque host child-agent ID and Better Plan dispatch ID. An asynchronous spawn return means only
that the child exists. Wait for an unambiguous final completion notification. Only a final callback
whose host ID matches the bound dispatch may reduce state; early, mismatched, unrelated, or replayed
notifications are no-ops. Multiple independent implementation Nodes in the same group, as well as
Nodes in different groups, may have active children concurrently; never require the group or the
whole workspace to have only one active Node in order to correlate a callback.

Do not paste one role contract into another, ask a child to mutate Better Plan state, or continue a
stopped child. Completion of one Node never selects or starts another Node automatically.

## Main decisions and communication

For `main_correction_decision`, inspect concrete evidence. Redispatch the same Worker for an
ordinary implementation defect. Revise group design only for a genuine cross-node contract or
product-semantics problem. Defer or ask the user when the choice exceeds the current authority.

For `main_reviewer_decision`, record the Reviewer's structured issues, report immediate choices,
and initiate the post-review full regression. Do not reinterpret a fixable defect as a user choice.

Use `defer` for a visible but intentionally postponed obligation and `activate` before resuming it.
Use terminal `skipped` only for an explicit waiver or not-applicable outcome. When delegated state
has not changed, wait quietly; do not emit repeated progress messages.

## Action discipline

Ask `next-action` only after confirming that the selected Node still represents authorized work.
Dispatch exactly its returned role and then stop orchestration until the child reaches a real final
boundary. All Plan writes, criteria changes, receipts, repairs, and decision records go through
`scripts/manifest_tool.py`.
