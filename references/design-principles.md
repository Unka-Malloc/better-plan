# Better Plan Design Principles

This document is the canonical rationale and evolution criteria for Better Plan itself. Use it when
maintaining, auditing, simplifying, or extending the skill across workflow, state, roles, tools,
installation, and host integration. `SKILL.md` remains the operational entry contract, and the CLI
schemas remain authoritative for runtime state.

## Disclosure boundary

Keep general skill knowledge separate from role-specific execution knowledge. This reference does
not replace `references/designer.md`, `references/worker.md`, `references/reviewer.md`, native role
templates, or the compiled brief for one dispatch. Preserve those role contracts and load them when
that role starts. Do not inject this general reference into every leaf role unless the assigned work
actually requires reasoning about Better Plan's cross-cutting design.

## Principles

1. **Keep the workflow simple, clear, efficient, and economical.** Better Plan tools must provide
   the shortest workflow that preserves correctness, authority, evidence, and recovery. Strictly
   reject labyrinthine state machines, repeated gates, duplicated ledgers, redundant passes, and
   slow orchestration that adds no distinct safety or evidence boundary. Every step, state, role,
   artifact, and validation must justify its operational and context cost.

2. **Use progressive disclosure.** Separate common skill knowledge from role-specific knowledge,
   load references only when they become relevant, and give each role the smallest complete context
   for its assignment. Keep role-specific prompts and references intact so a Designer, Worker, or
   Reviewer knows its exact authority, prohibitions, evidence duties, and completion contract.
   Minimize irrelevant context so role attention stays on the assigned work.

3. **Match orchestration depth to delivery risk.** Handle one small, directly understandable closure
   with the native workflow. Activate Better Plan only when complete migration, elevated risk,
   multiple independently acceptable Tasks, real handoffs, or long-lived recovery justify its cost.

4. **Discover facts before requesting decisions.** Inspect repository contracts, tests, schemas,
   state owners, failure behavior, and tooling first. Ask the user only for outcome-changing choices
   that cannot be discovered, and consolidate them into one coherent Decision Dossier.

5. **Give each phase one accountable authority.** Resolve decisions once, use one direct-write
   Designer, authorize one exact Plan revision, and use one writable Reviewer. Repair within the
   current Task or Reviewer session instead of creating recursive planning and repair roles.

6. **Keep one semantic source for each kind of truth.** `Plan.json` owns delivery semantics,
   `Manifest.json` indexes Plans, `Checkpoints.json` owns execution state, and `Plan.md` is a
   render-only projection. Derive secondary views instead of synchronizing competing ledgers.

7. **Compile plans into independently acceptable outcomes.** A Task represents one observable
   result, not a file list, role, or development phase. Freeze its scope, direct inputs, guaranteed
   outputs, ownership, risk, design decisions, acceptance oracle, evidence, and focused regression
   so a fresh-context Worker can execute it without the original conversation.

8. **Use one dependency graph and prove safe parallelism.** `prerequisites` is the sole scheduling
   graph; input/output mappings explain and validate its edges. Run Tasks concurrently only when
   reachability, write ownership, and exclusive resources prove independence.

9. **Bind authorization to exact semantics.** Seal authorization to a revision and semantic digest.
   Freeze started Task contracts and evidence. Continuations may revise only unstarted in-scope work
   and must not silently expand goal, scope, user decisions, elevated risk, or irreversible authority.

10. **Continue autonomously after authorization.** Do not return ordinary implementation decisions
    to the user. Apply selected decisions, authorized intent, public repository contracts, the safest
    reversible behavior, and the simplest adequate implementation in that order. Isolate hard
    authority or environment blockers and continue independent safe branches.

11. **Define completion with executable evidence.** Complete each Task only through its focused
    regression and close the delivery only through the sole Reviewer's full regression. Require real
    rendered evidence for visual behavior; source inspection, snapshots, or build success are not
    substitutes for the declared oracle.

12. **Make delegation precise and recovery explicit.** Bind every live dispatch to one host agent
    identity and consume only an exact final callback. Spawn is not completion, silence is not
    failure, and context loss must be recoverable from canonical state, receipts, and bounded briefs.

13. **Protect privacy and fail closed.** Keep secrets, machine identity, absolute local paths,
    runtime endpoints, and backend runtime data out of state, prompts, evidence, and reports. Reject
    ambiguous callbacks, invalid state, unknown ownership, and unsupported generations instead of
    guessing, translating, or broadening authority.

14. **Integrate additively with native hosts.** Use each host's native skill, role, Hook, and plugin
    formats. Manage only Better Plan-owned artifacts and namespaced entries, preserve unrelated local
    configuration, and verify the installed generation, selectors, receipts, structure, and Doctor
    result after installation changes.

## Change test

A Better Plan change is aligned only when it preserves the authorized outcome with less or equal
workflow complexity, context burden, duplicated state, and repeated work, or when every added cost
is required by a distinct correctness, authority, privacy, evidence, recovery, or host boundary.
Never simplify by deleting role-specific instructions or runtime enforcement that carries such a
boundary.
