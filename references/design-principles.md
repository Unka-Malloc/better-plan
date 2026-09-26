# Better Plan Design Principles

This document is the canonical rationale and evolution criteria for Better Plan itself. Use it when
maintaining, auditing, simplifying, or extending the skill across workflow, state, roles, tools,
installation, and host integration. `SKILL.md` remains the operational entry contract, and the
`schema` command remains authoritative for runtime state.

## Disclosure boundary

Keep general skill knowledge separate from the knowledge that belongs to one assignment. This
reference does not replace `references/checkpoints-tree.md`, a Node's own contract, or the task the
executor was given. Preserve those contracts and load them when the work needs them. Do not inject
this general reference into every leaf role unless the assigned work actually requires reasoning
about Better Plan's cross-cutting design.

## Principles

1. **Keep the workflow simple, clear, efficient, and economical.** Better Plan tools must provide
   the shortest workflow that preserves correctness, authority, evidence, and recovery. Strictly
   reject labyrinthine state machines, repeated gates, duplicated ledgers, redundant passes, and
   slow orchestration that adds no distinct safety or evidence boundary. Every step, state, role,
   artifact, and validation must justify its operational and context cost.

2. **Use progressive disclosure.** Separate common skill knowledge from the work at hand, load
   references only when they become relevant, and give each executor the smallest complete context
   for its assignment. Keep a Node's contract intact so whoever runs it knows the exact outcome,
   dependencies, and check it owes. Minimize irrelevant context so attention stays on the assigned
   work.

3. **Spend scarce model intelligence on solution design and automate representation work.** Constrain
   the designing model only where authority, safety, privacy, scope, or semantic correctness needs a
   hard boundary. Its job is the solution: outcomes, dependencies, contracts, risks, and the order of
   work. Codes, sequence numbers, timestamps, state derivation, graph validation, and evidence
   receipts are deterministic work that belongs to the tool, which must report a defect precisely
   (exact field, exact operation) instead of asking the model to guess again. The Designer writes the
   Tree through atomic `tree-apply` batches; the tool derives everything derivable, and one invalid
   operation rejects the whole batch.

4. **Make deterministic tools finish diagnostic work.** A compiler error must identify the exact
   source line or line range, the canonical target field, and the specific failed condition. Missing
   values point to their owning section and absent field; unexpected internal failures report the
   nearest compiler phase, source line, and field. Never collapse distinct defects into a generic
   summary that forces the native main, Designer, or another agent to parse and validate the same
   material again. Diagnostics must remain privacy-safe while making one-pass repair possible.

5. **Match orchestration depth to delivery risk.** Handle one small, directly understandable closure
   with the native workflow. Activate Better Plan only when complete migration, elevated risk,
   multiple independently acceptable parallel Tasks, or long-lived recovery justify its cost.

6. **Discover facts before requesting decisions.** Inspect repository contracts, tests, schemas,
   state owners, failure behavior, and tooling first, and record what was observed. Ask the user
   only for outcome-changing choices that cannot be discovered, and ask them together rather than
   one at a time. If none remain, ask nothing. Declared defaults never grant reserved authority.

7. **Give each phase one accountable authority.** One Designer authors the Tree, one deterministic
   tool derives and validates it, and the executor of a Node never grades the check it can run
   itself. Repair inside the current delivery instead of inventing recursive planning or review
   roles. A confirmed defect outside the current delivery gets its own Tree rather than being
   folded silently into this one.

8. **Keep one semantic source.** `Tree.json` owns the delivery: Tasks, executable Nodes, dependency
   edges, execution state, evidence, and history. There is no second ledger to synchronize, no
   approval projection to keep honest, and no mapping layer between two models of the same work.
   Derived views are rendered on demand and are never parsed back. A `Programme.json` beside a set
   of Trees is an index, not a ledger: it stores identity, location, and cross-delivery order, never
   status, and everything it reports is read from the Trees.

9. **Make the executable unit the one that carries the outcome.** A Node is one independently
   acceptable, observable result; a Task groups the Nodes of one delivery outcome. A Node a machine
   can check declares `contract.commands`; a Node only a person can judge declares none and is
   completed by an explicit report. Freeze each Node's outcome, dependencies, and contract so any
   executor can run it without the original conversation, and keep a Node small enough to finish in
   one sitting.

10. **Execute every available parallel frontier.** `after` is the only ordering: it names the Nodes
    a Node waits for, and it may cross Tasks. Every Node whose dependencies are complete is ready,
    and every ready Node may run at once — with no separate scheduling document, approval, or
    per-Node ledger.

    Disjoint write paths are necessary but not sufficient for real parallelism: it is a property of
    the machine. Attribute the resources parallel units contend on — build and artifact directories,
    version-control indexes and locks, test stores, ports, devices, toolchain caches. Nodes declare
    them in `resources`, and the tool reports every shared one that no `after` path orders, so the
    check is a command rather than a review. Across deliveries, the ordering that keeps two of them
    off one resource belongs in the programme's `requires` edges, next to the Trees it orders.

11. **Keep authority with the user, and observation with the tool.** A delivery runs on the request
   that authorized it: the Tree records no approval ceremony, and no agent may widen the goal,
   scope, or risk boundary on its own — that needs a fresh user decision. The inverse holds too: the
   Tree never accepts an executor's word for a check the tool can run itself, and never treats a
   rendered status as evidence that the work happened.

12. **Continue autonomously inside the authorized request.** Do not return ordinary implementation
    decisions to the user. Apply the user's request, public repository contracts, the safest
    reversible behavior, and the simplest adequate implementation in that order. Report a genuinely
    missing prerequisite promptly, prepare the concrete decision, and ask only for what is missing
    while independent Nodes keep running. Preserve explicit approval requirements; a routine defect
    report does not add one, and an unanswered request is not a hard blocker.

13. **Define completion with executable evidence.** A Node that declares commands is complete only
    when the tool ran them and recorded the receipts; a reported completion is stored and displayed as
    reported, never as a verified one. Never treat a status field, a summary, or a build log as proof
    that a declared check passed. Rendered behavior needs rendered evidence: source inspection,
    snapshots, and build success are not substitutes for the declared oracle.

14. **Make delegation precise and recovery explicit.** Bind each dispatched unit to one identifiable
    executor and consume one exact final report. A spawn is not a completion, silence is not a
    failure, and any executor must be able to resume from `Tree.json` alone after its context is
    lost.

15. **Protect privacy and fail closed.** Keep secrets, machine identity, absolute local paths,
    runtime endpoints, and backend runtime data out of state, prompts, evidence, and reports. Reject
    ambiguous callbacks, invalid state, unknown ownership, and unsupported generations instead of
    guessing, translating, or broadening authority. Rejection applies to the attempted transition;
    use permitted repair and verification paths supported by current authority and repository facts.

16. **Integrate additively with native hosts.** Use each host's native skill, role, and plugin
    formats. Manage only Better Plan-owned artifacts and namespaced entries, preserve unrelated local
    configuration, and verify the installed generation, selectors, receipts, structure, and Doctor
    result after installation changes.

## Change test

A Better Plan change is aligned only when it preserves the delivery outcome with less or equal
workflow complexity, context burden, duplicated state, and repeated work, or when every added cost
is required by a distinct correctness, authority, privacy, evidence, recovery, or host boundary.
Removing a cost is aligned only when no such boundary depended on it. Never simplify by deleting
instructions or runtime enforcement that carries such a boundary.
