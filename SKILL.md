---
name: better-plan
description: "Coordinate long-lived work through a shared plan: one Designer, parallel Workers, a persistent Verifier, one independent Reviewer, and assignable feedback-only Adversaries. Tree tools maintain requirements, dependencies, results, checks, and retrievable history."
---

# Better Plan

Better Plan is a shared blackboard for long-term work. Agents read the same user
requirements, plan, repository documents, and evidence directly. Its tools assist
collaboration; they do not grant permission or police Agent judgment.

It assumes every Agent makes mistakes. Widen implementation in parallel, independently
verify and integrate throughout execution, and independently review the final code.
See [design principles](references/design-principles.md).

## Workflow

**Main owns user requirements, dispatch, and process.** Keep the central requirement
record faithful, work moving, and real blockers visible. Main does not prescribe
implementation details. It connects one Designer, parallel Workers, a default-on
persistent Verifier, and one independent Reviewer. Native host tools carry dispatch,
resumption, and stopping; see [Main guidance](references/main.md).

**One Designer turns requirements into architecture and deliverable work.** Choose
complete milestones, real dependencies, and maximum useful parallelism. Hand off
once Workers can proceed; do not exhaustively predesign implementation details or
runtime failures. See [Designer guidance](references/designer.md).

**Workers only implement assigned code.** Give them the repository, shared requirements,
and work reference. They do not own quality, process, cross-task integration, or
acceptance, and owe no evidence pack. Their completion claims locate code; they are
never trusted acceptance evidence. Parallelize useful implementation within actual
host resources. See [Worker guidance](references/worker.md).

**One persistent Verifier independently inspects, integrates, checks, and repairs.**
Start it by default alongside Main and keep it through execution of the whole plan,
not just one milestone. It may inspect every change, verify actual code, and arrange
bounded repairs. Main retains process ownership. See [Verifier guidance](references/verifier.md).

**One Reviewer independently closes milestones and all final requirements.** For a
milestone, give it requirements and a stable code snapshot; Verifier may continue
unrelated work without changing that snapshot. Reviewer reaches its own conclusions
from code and independently performed checks, not Worker or Verifier process proof.
For whole-plan final review, wait for all Workers to finish, Verifier's final regression
and notification, then Main stops Verifier before Reviewer's final takeover. Reviewer
independently validates, repairs, and reconciles every recorded requirement, including
plan omissions. Rework is allowed with an explicit ownership handoff. See
[Reviewer guidance](references/reviewer.md).

**Adversaries independently challenge assigned agents through feedback only.** One
or multiple Adversaries may target one or multiple agents, including Main, Designer,
Workers, Verifier, or Reviewer. Group related Worker targets by functional domain.
They investigate actual activity, environment capabilities, applicable rules, and
external best practices from the outset of their assignment, including concerns
outside the plan. Direct messages go to targets where supported; otherwise Main
relays unchanged. They never edit artifacts or perform repairs. This reusable role
needs no plan and is explicitly assigned, not automatically started. See
[Adversary guidance](references/adversary.md).

No role owes Reviewer a proof pack. Shared results aid coordination but never substitute
for independent judgment. Every role follows user requirements, repository rules,
and actual host permissions; Main's brief adds no authority boundary. Host settings,
including model, reasoning, tools, and budgets, stay user-owned. Missing host capacity
or lifecycle controls must be reported rather than assumed. This role handoff adds
no human-approval mechanism or runtime enforcement.

## Shared information

```text
Tree.json          goal, success, architecture, requirements, open decisions, delivery
 tasks/<id>.json   Task outcome, requirements, checks, Draft PR, delivery
 nodes/<id>.json   Node work, dependencies, progress, result, commit
 history/<id>.json immutable source material, retrieved when needed
```

Keep shared requirements once at Tree level, Task requirements once at Task level,
and Node-specific facts in the Node. Record unanswered questions in `open_decisions`;
after clarification, update the current requirements and decisions for all Agents.
Before revising the plan, archive relevant available conversation with `history
archive`; retain source meaning without requiring Agents to replay the conversation.
History is read on demand, not injected into every assignment.

A Task describes a deliverable outcome. A Draft PR may group related Tasks when that
is the clearest reviewable delivery. A Node describes a coherent contribution; its
commit field records the resulting revision and may name a revision containing
multiple commits. Keep Task, Node, commit, and PR relationships explicit without
forcing a one-to-one mapping. The Verifier owns ongoing integration;
`integration_owner` records that responsibility. Reviewer independently integrates
and revalidates any repairs during review. Deliveries leave the project
buildable and runnable after their declared prerequisites.
Longer programmes keep future milestones as outlines until their requirements are
understood; each milestone is one independently deliverable unit rather than a layer
or partial slice. See [programme guidance](references/programme.md).

Optional [engineering references](references/engineering.md) cover architecture,
work slicing, tests, and acceptance; consult the relevant topic when useful.

## Tools when needed

Use `python3 scripts/manifest_tool.py` from the installed skill:

| Need | Command |
| --- | --- |
| See ready work and dependencies | `tree next <plan> --json` |
| Read or begin a Node with shared context | `node show/start <plan> <node>` |
| Record implemented work | `node finish <plan> <node> --summary TEXT --commit REF` |
| Read the whole current delivery | `tree export <plan>` |
| Change the plan | `tree/task/node update`, `edge`, `subtree` |
| Verify affected work | `checks list/run/record/recover` |
| Record reviewed and integrated results | `task finish`, then `tree finish` |
| Recover source context | `history list/search/show` |

Read [the tree contract](references/checkpoints-tree.md) for command syntax, state,
and recovery details. Results and checks record evidence, not approval. Relevant
changes preserve earlier results and mark affected work for review; reconfirm the
actual outcome. Default engineering delivery leaves PRs Draft. Later publication,
merge, installation, and live acceptance follow the user's project authorization.

Host-native tools carry Agent messages, questions, completion, and resumption;
Better Plan does not duplicate the host scheduler. Read [host configuration](references/host-configuration.md)
only for host integration or installation questions. Existing role model, tools,
permissions, and sandbox settings belong to the user; prompt updates preserve them.

Maintaining Better Plan itself uses the ordinary repository workflow, without
creating a Better Plan workspace. [Design principles](references/design-principles.md)
explain the maintained product decisions.
