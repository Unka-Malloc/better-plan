---
name: better-plan
description: "Coordinate long-lived work through a shared plan: one Designer, parallel Workers, and one independent Reviewer. Tree tools maintain requirements, dependencies, results, checks, and retrievable history."
---

# Better Plan

Better Plan is a shared blackboard for long-term work. Agents read the same user
requirements, plan, repository documents, and evidence directly. Its tools assist
collaboration; they do not grant permission or police Agent judgment.

It assumes every Agent makes mistakes, so it widens parallel work instead of gating
each contribution and concentrates integration and review in one capable Reviewer.
See [design principles](references/design-principles.md).

## Workflow

**Main understands and faithfully conveys user needs, keeps work moving, and answers
to the user for their execution.** It connects one Designer, parallel Workers, and
one Reviewer. It tracks the user's next useful outcome, true blockers, ready work,
and repeated effort; resumes interrupted work and starts work as dependencies allow.
It does not reinterpret repository materials for specialists or prescribe technical
remedies. When the host does not let the Reviewer dispatch a Worker, Main forwards
the Reviewer's repair assignment unchanged and returns the result. See [main
guidance](references/main.md).

**One Designer designs what the user's long-term goal needs.** Architecture, code,
documentation, workflows, scripts, and tools are all available means. The Designer
chooses the approach and decomposition, using the repository and shared evidence.
See [Designer guidance](references/designer.md).

**Workers execute ready Nodes and scoped repairs autonomously and in parallel.** Give
each Worker the repository, plan, and work reference; shared materials supply the
context. Design real dependencies and exclusive write ownership to maximize useful
parallelism, not repeated main instructions. See [Worker guidance](references/worker.md).

**One Reviewer independently brings the delivery to completion.** It examines user
needs, industry best practices, repository rules, and whether the plan and its
execution serve the original intent. It may repair issues directly or dispatch
subagents for independent, bounded tasks — repairs, verification, focused
investigation — running several at once in isolated worktrees. The same Reviewer
retains source review, integration, verification, and delivery judgment. Freeze only
the exact candidate that needs a stable verification snapshot; unrelated writers may
continue outside it. If the host does not let the Reviewer dispatch, Main forwards its
assignment mechanically. See [Reviewer guidance](references/reviewer.md).

Every role exercises its own judgment under the user's requirements, repository
rules, and actual host permissions. A main brief adds no further authority boundary.
Host tools and permissions determine whether a role can dispatch another Agent;
model capability or parent-child topology does not establish that capability.
Agents raise material uncertainty through main to the user; pause work that depends
on the answer rather than inventing requirements. Main's active coordination and
the Reviewer's independent final judgment protect the outcome without per-step
approval.

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
forcing a one-to-one mapping. The Reviewer owns integration; `integration_owner`
records that responsibility, not an additional Agent. Deliveries leave the project
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
