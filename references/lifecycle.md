# Plan lifecycle

One authoritative phase model for every plan and role. Role guides state only the
parts that apply to them; questions about sequencing, frozen artifacts, or who must
stay quiet are answered here. Phases describe ownership, not status words: Node
statuses are `pending`, `running`, `completed`, `failed`, `blocked`, `cancelled`;
delivery results are `unrecorded`, `recorded`, `needs_review`.

## Phases

| Phase | Who acts | Who must stay quiet | Frozen artifact | Entry | Exit |
| --- | --- | --- | --- | --- | --- |
| 0 Setup | Main | — | — | requirements confirmed | Tree initialized |
| 1 Design | Designer; Main | — | — | Tree initialized | ready Nodes exist |
| 2 Execute | Workers in parallel; Verifier; Main | — | — | a Node is ready | milestone snapshot stable |
| 3 Milestone review (repeatable) | Reviewer; Verifier at unrelated work | Workers; Verifier for the snapshot | milestone revision | stable snapshot handed over | closure recorded, or rework handed back and reviewed again |
| 4 Final regression | Verifier | — | final candidate | all Workers and repair writers finished | regression complete and Main notified |
| 5 Final review | Reviewer | Verifier (stopped); every other writer; new rounds | final candidate | Verifier shutdown confirmed | `tree finish` recorded |
| 6 Delivery | Main; user | — | — | `tree finish` recorded | user accepts or authorizes the next step |

## Rules

- **One phase has one owner.** A milestone loop repeats 3 until closure; each review
  of the loop is independent. Rework is an explicit ownership handoff, never
  competing owners.
- **Frozen means frozen.** During 3, Verifier never changes the milestone snapshot.
  During 5, no agent writes into the final candidate and no new round starts; the
  Verifier is stopped before Reviewer takeover, using available host controls.
- **Milestone review does not stop the Verifier.** It continues unrelated work and
  integrates reviewed repairs afterward (see verifier.md).
- **Final review is not an approval gate.** It is a separate independent judgment
  over the whole plan; finish commands record declarations, not tests or Git
  actions.
- **Route review is an event, not a phase.** It may fire during 2, 3, or 4, and the
  Reviewer's plan-omission reconciliation during 5 is route-level review by nature
  (see route-review.md). It never bypasses a user gate or silently redefines the
  user's requirements.

## Common transitions

| Transition | Who records it | Record |
| --- | --- | --- |
| Node starts | `node start`; running | status `running` |
| Node completes | `node finish` | status `completed`, result, commit |
| Task/Tree result recorded | Reviewer via `task finish`, `tree finish` | delivery result |
| Work-defining fact changes | Main, Designer, Verifier, or Reviewer | tree operations propagate review items |
| Interrupted run | explicit `checks recover` | pending remains; previous result preserved |