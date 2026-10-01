---
name: better-plan
description: "Coordinate long-lived work through a shared plan: one Designer, parallel Workers, and one independent Reviewer. Tree tools maintain requirements, dependencies, results, checks, and retrievable history."
---

# Better Plan

Better Plan is a shared blackboard for long-term work. Agents read the same user
requirements, plan, repository documents, and evidence directly. Its tools assist
collaboration; they do not grant permission or police Agent judgment.

## Workflow

**Main understands and faithfully conveys user needs, keeps work moving, and answers
to the user for their execution.** It connects one Designer, parallel Workers, and
one Reviewer. It relays questions and decisions, resumes interrupted work, starts
the next ready work, and promptly points out observed deviations. It does not
reinterpret repository materials for specialists or prescribe their technical
approach. See [main guidance](references/main.md).

**One Designer designs what the user's long-term goal needs.** Architecture, code,
documentation, workflows, scripts, and tools are all available means. The Designer
chooses the approach and decomposition, using the repository and shared evidence.
See [Designer guidance](references/designer.md).

**Workers execute ready Nodes autonomously and in parallel.** Give each Worker the
repository, plan, and Node reference; the shared materials supply the work. Design
real dependencies and ownership to maximize useful parallelism, not repeated main
instructions. See [Worker guidance](references/worker.md).

**One Reviewer independently brings the delivery to completion.** After the other
writers have finished, it examines user needs, industry best practices, repository
rules, and whether the plan and its execution actually serve the original intent.
It directly repairs what it discovers, including defects in the design or plan,
then integrates and verifies the result. Neither main's checklist nor the plan
limits its investigation or repairs. Keep the same Reviewer through corrections;
there is no separate integration Agent and no concurrent writer during convergence.
See [Reviewer guidance](references/reviewer.md).

Every role exercises its own judgment under the user's requirements, repository
rules, and actual host permissions. A main brief adds no further authority boundary.
Agents raise material uncertainty through main to the user; pause work that depends
on the answer rather than inventing requirements. Main's in-process correction and
the Reviewer's independent final judgment protect the outcome without per-step
approval. Model capability and parent-child topology do not establish technical
superiority.

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

A Task is one independently deliverable Draft PR containing its Nodes' commits.
A Node is one coherent change and one commit. The Reviewer owns integration;
`integration_owner` records that responsibility, not an additional Agent. Task PRs
leave the project buildable and runnable after their declared prerequisites.
Longer programmes keep future milestones as outlines until their requirements are
understood; see [programme guidance](references/programme.md).

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
