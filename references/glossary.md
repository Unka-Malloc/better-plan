# Glossary

Terms used across Better Plan guidance and contracts. Write canonical terms in
briefs, prompts, and plan records; the deprecated column lists terms still read,
never written. One fact has one owner, and one term has one meaning.

| Canonical term | Meaning | Use instead of |
| --- | --- | --- |
| Tree workspace (root) | the directory containing `Tree.json`, `tasks/`, `nodes/`, `history/`, and `.better-plan-checks/`; the unit addressed by tree commands (commands still spell the placeholder `<plan>`) | "plan" (when referring to the directory) |
| Tree | the current plan files together: `Tree.json` plus `tasks/` and `nodes/`; also the single `Tree.json` root record when context makes that clear | "plan document" |
| Programme | `Programme.json` ordering several delivery Trees; owns requirement identity via `Requirements.json` | "roadmap" |
| Milestone | one independently deliverable unit of a Programme or Tree plan | "phase", "layer", "slice" |
| Task | a deliverable outcome grouping Nodes; may share one Draft PR | — |
| Node | one coherent contribution with contract, dependencies, status, result, and commit | "todo item", "work item" |
| Draft PR | reviewable delivery boundary; groups related Tasks when that is the clearest review | "PR" (until publication is authorized) |
| Check | a recorded verification command and its result, owned by a Node, Task, or Tree | "validation" (host term), "test run" |
| Verification | the act of independently inspecting actual code and behavior, never trusting claims | — |
| Review item | a pending-review marker propagated by tree operations when work-defining facts change | "flag" |
| Closure | the Reviewer's independent judgment that a candidate satisfies the requirements | "review pass" |
| Delivery result | the recorded `delivery` object of a Task or Tree: `unrecorded`, `recorded`, `needs_review` | "acceptance" |
| Open decision | a recorded unanswered question in `open_decisions`; dependent work pauses, independent work continues | "question TODO" |
| Route | the current plan of record plus the execution strategy: what is being done, why, and how it will finish | "direction", "approach" |
| Route review | the event-triggered re-decision of the Route against the original requirements and verified facts | "fresh decide" |
| Round | one working cycle by one agent: read shared state, act, record, report | "iteration" (when implying progress) |
| Uncertainty removal | a round ending with a named unknown resolved or a named option ruled out | "progress" (when unqualified) |
| Proof pack | a report assembled to persuade another role; no role owes one | "evidence pack" |
| Acceptance | the final judgment that the user's requirements are satisfied; only the Reviewer closes it | "completion" |
| Block report | an evidence-backed statement of a real blocker: known facts, unknowns, cause, options, recommendation, and what can continue | "status update" |
| History | the immutable archives under `history/`; read on demand, never injected | "transcript" |
| Snapshot | the immutable revision handed to the Reviewer for a milestone review | "branch state" |
| Final candidate | the integrated revision held stable during final whole-plan review | "head" |
| Integration owner | the recorded responsibility for ongoing integration, default `verifier` | "maintainer" |
| Contention | derived report of Nodes sharing executors or resources | "conflict" (unverified) |

## Bilingual data

Stored text values may be plain strings or bilingual objects such as
`{"en": "...", "zh": "..."}`; the tools treat them as opaque and never translate
one side into the other. Guidance and role prompts stay in one canonical language;
translate values, never rules.

## Terminology hygiene

- Never redefine a canonical term in a brief or role guide; extend the glossary
  instead.
- A "check" records evidence; a "verification" is an act. Both assist coordination;
  neither is acceptance proof.
- `delivery` names the result record only. Publication, merge, installation, and
  live acceptance are separately authorized project work; write "publication" for it.