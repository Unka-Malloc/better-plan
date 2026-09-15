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

3. **Spend scarce model intelligence on solution design and automate representation work.** When a
   planning stage uses an especially capable or expensive model, constrain it only where user
   authority, safety, privacy, scope, or semantic correctness requires a hard boundary. Let that
   model produce one structured solution plan in the form that best preserves its reasoning,
   tradeoffs, architecture, risks, and delivery strategy; do not spend its context and attention on
   stable codes, receipt mechanics, schema boilerplate, graph normalization, or other work that
   deterministic tooling can perform. Python automation should convert that structured proposal into
   the canonical Better Plan representation, derive mechanical fields, validate the result, and
   report conversion defects precisely. If conversion is incomplete, ambiguous, or invalid, the
   native main takes ownership of completing and repairing `Plan.json` instead of constraining or
   redispatching the expensive model. After the Designer returns, `Design.md` is a read-only source
   record: never repair conversion by changing or deleting its content. Keep `Plan.json` as the sole
   semantic source.

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
   state owners, failure behavior, and tooling first. Ask the user only for outcome-changing choices
   that cannot be discovered, and consolidate them into one coherent Decision Dossier. If none
   remain, retain `not_required` and skip clarification. Defaults never grant reserved authority.

7. **Give each phase one accountable authority.** Resolve decisions once, use one Designer for the
   solution draft and one deterministic compiler write path for its Plan representation, authorize
   one exact revision, and use one writable Reviewer. Repair within the native main, current Task,
   or Reviewer session instead of creating recursive planning and repair roles. Confirmed defects
   outside the authorized Plan are structured handoffs: close the current delivery first, then let
   deterministic tooling create separate unapproved draft Plans for later user authorization.

8. **Keep one semantic source for each kind of truth.** `Plan.json` owns delivery semantics,
   `Manifest.json` indexes Plans, `Checkpoints.json` owns execution state, and `Plan.md` is a
   render-only projection. Derive secondary views instead of synchronizing competing ledgers.

9. **Compile plans into independently acceptable outcomes.** A Task represents one observable
   result, not a file list, role, or development phase. Freeze its scope, guaranteed outputs,
   ownership, risk, design decisions, acceptance oracle, evidence, and focused regression so a
   fresh-context Worker can execute it without the original conversation.

10. **Execute every available parallel frontier.** The native main passes requirements, not a
    predesigned Task graph. The Designer makes all Tasks mutually independent, then gives each Task
    a minimal Node DAG: declare an edge only for a real ordering or data dependency, branch every
    independent Node, and join only where its prerequisites converge. Python compiles and validates
    that structure; Workers run every ready Node concurrently, and the native main runs focused
    acceptance concurrently for every awaiting independent Task. Long-running work never holds the
    global state lock. No Node receives a separate role, approval, or persistent execution ledger.

11. **Bind authorization to exact semantics.** Seal authorization to a revision and semantic digest.
   Freeze started Task guarantees, ownership, design, acceptance, and historical evidence. After a
   Worker returns, the native main may correct an unfinished Task's focused command or path error
   while preserving the oracle, recording the reason and before/after contract, and obtaining fresh
   acceptance. Completed Task definitions stay frozen. Other continuation edits apply to unstarted
   work and must not expand goal, scope, user decisions, elevated risk, or irreversible authority.
   Reuse an existing exact authorization; recording its source does not require another user vote.

12. **Continue autonomously after authorization.** Do not return ordinary implementation decisions
    to the user. Apply selected decisions, authorized intent, public repository contracts, the safest
    reversible behavior, and the simplest adequate implementation in that order. Promptly report
    missing user prerequisites to the native main. It records pending input, prepares the concrete
    decision within existing authorization, and requests only the missing input or approval while
    independent branches continue. Preserve explicit approval requirements; a routine defect report
    does not add one. Do not finalize merely unanswered requests as hard blockers.

13. **Define completion with executable evidence.** Complete each Task only through its focused
    regression. Run the complete regression as an independent Python stage before Reviewer
    dispatch; Reviewer session commands must never own or execute it. Give the Reviewer its
    diagnostics, and reuse green evidence unless Reviewer repairs change covered paths. Require real
    rendered evidence for visual behavior; source inspection, snapshots, or build success are not
    substitutes for the declared oracle.

14. **Make delegation precise and recovery explicit.** Bind every live dispatch to one host agent
    identity and consume only an exact final callback. Spawn is not completion, silence is not
    failure, and context loss must be recoverable from canonical state, receipts, and bounded briefs.

15. **Protect privacy and fail closed.** Keep secrets, machine identity, absolute local paths,
    runtime endpoints, and backend runtime data out of state, prompts, evidence, and reports. Reject
    ambiguous callbacks, invalid state, unknown ownership, and unsupported generations instead of
    guessing, translating, or broadening authority. Rejection applies to the attempted transition;
    use permitted repair and verification paths supported by current authority and repository facts.

16. **Integrate additively with native hosts.** Use each host's native skill, role, Hook, and plugin
    formats. Manage only Better Plan-owned artifacts and namespaced entries, preserve unrelated local
    configuration, and verify the installed generation, selectors, receipts, structure, and Doctor
    result after installation changes.

## Change test

A Better Plan change is aligned only when it preserves the authorized outcome with less or equal
workflow complexity, context burden, duplicated state, and repeated work, or when every added cost
is required by a distinct correctness, authority, privacy, evidence, recovery, or host boundary.
Never simplify by deleting role-specific instructions or runtime enforcement that carries such a
boundary.
