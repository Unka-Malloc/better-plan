# Lightweight Capability Lifecycle Architecture

## Lifecycle boundary

The selected implementation Node is the sole lifecycle identity for one user-visible capability.
Its existing UUID already supplies a stable correlation key, so no duplicate lifecycle ID or
compatibility field is added. Acceptance revisions and implementation repairs mutate only the
bounded `acceptance` snapshot of that Node. Completion is terminal and produces no action that
selects another Node.

The machine cannot infer semantic user intent. The native main therefore owns the only semantic
decision: whether a finding still belongs to the selected capability. Deterministic code enforces
the structural proxy by returning revision and drift to a main decision instead of selecting a
new role or Node.

## Files and symbols

- `SKILL.md` and `references/orchestration-main.md`
  - define one capability/one lifecycle, proportional design, main-owned scope decisions, stop
    after completion, and quiet unchanged waiting;
  - describe engineering design dimensions as applicable considerations rather than mandatory
    boilerplate.
- `references/acceptance-designer.md`
  - changes the six observation dimensions into a risk-driven candidate catalogue;
  - forbids tests added only to fill a category.
- `references/acceptance-reviewer.md`
  - reviews concrete requirement proofs and material risks;
  - cannot reject solely for an omitted irrelevant category or expand scope.
- `scripts/better_plan/domain/transitions.py::next_action`
  - maps `acceptance_revision_required` to `main_acceptance_decision`.
- `scripts/better_plan/domain/roles.py::MAIN_ACTIONS`
  - recognizes the main acceptance decision as non-delegating orchestration work.
- `scripts/better_plan/application/workflow.py::refresh_preparation`
  - routes stale enrolled preparation to `acceptance_revision_required` rather than an automatic
    fresh design dispatch.
- `scripts/better_plan/application/workflow.py::invalidate_preparation_after_plan_edit`
  - preserves initial design entry for unenrolled Nodes but returns changes to an already enrolled
    lifecycle to the native main.
- `scripts/better_plan/hooks/context.py::INTENT_GUIDANCE`
  - adds only the short capability boundary; it does not inject Plan inventory or role templates.
- `agents/openai.yaml` and `README.md`
  - expose the same lightweight generic behavior to installed users.

## Interfaces and errors

- `next_action(phase: str, role: str) -> str`
  - output for `acceptance_revision_required` becomes `main_acceptance_decision`;
  - unsupported phase/role behavior remains unchanged.
- `refresh_preparation(location, node) -> dict[str, Any]`
  - an unenrolled Node still begins at `awaiting_acceptance_design`;
  - stale enrolled preparation clears proof and parks at a main decision without launching work.
- Role references remain plain guidance inputs. They introduce no state mutation, timer, model
  launcher, provider routing, or host-specific branch.

## Algorithms and data structures

- Phase routing remains one immutable hash-table lookup, expected `O(1)` time and fixed memory.
- Freshness comparison remains linear in the existing bounded fingerprint field set.
- The existing Node UUID and acceptance mapping are reused; no duplicate registry, cache, queue,
  or compatibility schema is introduced.

## State, isolation, and concurrency

- Automatic transitions stay inside one selected Node lifecycle.
- Rejection or drift parks that lifecycle for native-main judgment; explicit redispatch may revise
  the same Node, but no transition creates or selects another Node.
- Executor regression and thin audit keep their existing deterministic boundaries.
- Agent lifetime and waiting cadence remain host-owned. Quiet-wait language is heuristic only.
- Role files stay isolated and repository-neutral; all persisted paths remain relative.

## Non-goals

- No fixed maximum agent duration, retry count, test count, or acceptance category count.
- No project-, provider-, model-, client-, or platform-specific workflow.
- No new compatibility field, old-interface alias, or permanent migration-only gate.
