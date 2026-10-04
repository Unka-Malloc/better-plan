# Route review

Per-round decisions answer "how do I fix this step". Route review answers "is this
route still the right one" — judged against the original requirements, the success
criteria, and verified facts, never against the plan's own narrative. Route review
is event-triggered so that long-horizon execution re-decides reliably instead of
depending on the executor to remember to step back. A review conclusion that cannot
change execution is not a route review.

## Triggers

| Event | Trigger condition |
| --- | --- |
| Repeated failure | the same stage failed two or more consecutive times with no new evidence between failures |
| Empty round | a round completed without removing a named uncertainty (see Round DoD) |
| Prerequisite growth | a milestone's prerequisites grew without a user requirement or a newly verified fact |
| Excluded scope | work entered user-excluded territory, or a narrower proven path exists and was not adopted |
| Cost growth | verification round trips, context use, or role handoffs grow without acceptance value |
| User check-in | the user asks why, what remains, how long, or to stop; treat the question as a route-review prompt |
| Persistent blocker | a real blocker survives rounds without an evidence-backed block report |

When any trigger fires, stop adding the same kind of work: run the procedure below
before the next round.

## Procedure

1. **Re-read the original input.** Read the user's requirements, success criteria,
   boundaries, and repository rules — the Tree records them; do not mistake the
   plan narrative, previous choices, or your own summaries for the requirements.
2. **Re-read the verified facts.** Current results, checks, open decisions, and
   history on demand. Separate verified facts from assumptions and from recorded
   intentions.
3. **Decide explicitly.** Answer: if starting now with these facts, would we still
   choose this route? Name the alternatives considered and the evidence that
   ruled them out. If no alternative was genuinely available, say so and name the
   missing prerequisite.
4. **Change execution or stop.** Choose one outcome below. A route review that
   ends with "continue exactly as before" without new evidence has failed its
   purpose; record why the trigger was a false alarm if and only if that is the
   actual conclusion.

## Outcomes

- **Continue.** New evidence removed the named uncertainty; record that evidence
  (result, check, or verified fact) with the work.
- **Re-route.** Revise the affected Tree facts and dependencies with tree
  operations; archive relevant conversation with `history archive` before revising;
  updates that touch goal, requirements, architecture, or success criteria mark all
  work for re-review. Requirements changes still require the user: re-routing is
  not redefining the user's intent.
- **Stop.** Write a block report: known facts, unknowns, cause, options considered,
  recommended next action, and what can continue without the decision. Pause only
  dependent work. Silence and elapsed time are not progress; a block report is.

## Ownership and assignment

- **Main owns route review** for the plan, including deciding between the outcomes
  and when a user decision is required.
- **Anyone may raise a trigger with facts.** Verifier stagnation signals and
  Reviewer plan-omission findings are explicit route-review inputs; Adversaries
  may challenge the route of any target, including Main.
- **An Adversary may own the review procedure itself** when Main explicitly assigns
  it. Frame such assignments at route level, for example: "challenge whether each
  current prerequisite of the release comes from the user's requirement or the
  actual delivery contract; point out repeated verification, scope growth, and any
  shorter proven path that the executor ignored." The Adversary reads original
  requirements and verified facts, not the plan narrative as proof, and changes
  execution only through feedback (adversary.md).
- A route review never bypasses a user gate, approval boundary, or host
  permission; its stop/re-route authority is process authority, not permission.

## Round DoD

Before reporting completion, name the uncertainty your round removed:

- verified a behavior or check result that was previously unknown, or
- located a root cause, or
- ruled out an option or route, or
- confirmed or corrected a prerequisite (user requirement, contract, environment, or
  host fact).

A round that cannot name one of these is a signal, not progress: apply the triggers
and procedure before the next round rather than adding the same kind of work again.