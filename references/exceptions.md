# Exceptions and recovery

Recovery guidance for interrupted, stale, or contested state. Contract details live
in checkpoints-tree.md; this page states what roles do when something breaks. Fix
the state, never paper over it: no invented results, no silent reruns, no
competing owners.

## Interrupted or active checks

- A read snapshot reports `interrupted: true` when an unresolved execution marker
  has no live executor lock. Confirm the leftover commands have actually ended,
  then run `checks recover`; it clears the marker and leaves the check pending.
  It never kills processes and never reports a passed result.
- A duplicate run or external result write while execution is active returns an
  active-execution error immediately: never queue, never cancel. Wait or recover
  explicitly.
- A temporary `run_id` associates a return with the current check object; an older
  run's result cannot be accepted after the object changed. A running check turns
  `dirty` when its definition changes; the result is recorded but `pending` stays
  true until a clean rerun.
- Lock files under `.better-plan-checks/` are stable synchronization artifacts,
  not history: never remove them while the workspace is in use.

## Stale or manually edited state

- After manual edits, run `tree refresh` to recompute the view. It does not invent
  missed notifications; there is no whole-tree revision or background watching.
- Review items are current state: a changed Node and its downstream Nodes receive
  one item; `node review-done` clears handled items after an Agent actually
  handles them.

## Phase mismatch and competing writers

- Before resuming a stopped role (for example returning to execution after final
  review), make the ownership handoff explicit; never run competing final owners.
- Phase authority and frozen artifacts are defined in lifecycle.md: during
  milestone review the snapshot is immutable; during final review no new round
  starts and no agent writes the final candidate.
- If a milestone filter or review boundary seems to block legitimate work, report
  the phase mismatch to Main with the facts rather than writing around it.

## Missing host capability

- Report missing dispatch, stopping, resume, messaging, or permission capability
  to Main; never emulate it or claim an enforced lifecycle. Installing a profile
  does not start an agent.
- Host settings (model, reasoning, tools, budgets) stay user-owned; never change
  them to create capacity.

## Stagnation and blockers

- Repeated failure without new evidence, rounds without uncertainty removal, and
  prerequisite growth are route-review triggers (route-review.md), not reasons to
  rerun the same work.
- A real blocker gets an evidence-backed block report: known facts, unknowns,
  cause, options, recommendation, and what can continue. Pause only dependent
  work. Reporting a blocker is not an approval gate and never requires permission.

## Pending user decisions

- Pause only work that depends on the answer; continue independent work. Silence
  and declared defaults never grant approval; neither silence nor elapsed time is
  evidence of completion or failure.