# Lightweight Capability Lifecycle Evidence

## Repository evidence

- `references/orchestration-main.md` currently requires an exhaustive engineering inventory for
  every implementation and tells the main to dispatch several reported actions immediately.
- `references/acceptance-designer.md` presents six observation dimensions as required output, so
  an agent can mistake a useful risk catalogue for a mandatory coverage matrix.
- `references/acceptance-reviewer.md` currently requires boundary coverage for every criterion
  and mandatory negative/boundary cases without first establishing applicability.
- `scripts/better_plan/domain/transitions.py` maps `acceptance_revision_required` directly to
  `dispatch_acceptance_designer`; after the main records a rejection, the machine therefore
  recommends another leaf without a scope decision.
- `scripts/better_plan/application/workflow.py` resets stale reviewed preparation to
  `awaiting_acceptance_design`, which has the same automatic redispatch effect.
- The current main contract says to correlate and wait but gives no guidance to suppress repeated
  unchanged-state narration.

## Behavioral deduction

The host Hook is not itself a model launcher, but fixed next-action wording plus automatic
revision routing can make the native main behave like a recursive scheduler. The generic remedy
is to use the selected Node as the lifecycle boundary, reserve automatic actions for objective
within-lifecycle transitions, and return every rejection, drift, completion, or new-scope choice
to native-main judgment.

Acceptance breadth also needs a semantic boundary. A fixed category matrix creates tests for
irrelevant concerns and gives a reviewer an unlimited source of speculative findings. Candidate
dimensions should instead be chosen only when connected to a requirement, interface, state
transition, or material risk.
