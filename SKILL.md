---
name: better-plan
description: Maintain a long-lived delivery plan as Tasks and dependency Nodes. Use tree operations for local edits, handoffs, scoped checks, current-state reports, and immutable on-demand history.
---

# Better Plan

Use Better Plan when delivery must survive context changes or contains several
independently executable pieces. The tool is a tree-aware planning assistant. It
does not approve work, validate a plan as a gate, restrict roles, or decide whether
an Agent may start or finish.

Maintaining the Better Plan source repository itself uses the ordinary repository
workflow. Do not create a Better Plan workspace merely to edit this package.

## Current state and history

An Agent normally reads and writes current state only:

```text
Tree.json           goal, requirements, decisions, checks, overall delivery result
tasks/<id>.json     Task outcome, integration owner, requirements, checks, delivery result
nodes/<id>.json     one executable Node and its current result
history/<id>.json   immutable, explicitly archived context
```

Before changing a plan, archive the relevant conversation material that is
available to you. This is working guidance, not a tool gate:

```sh
python3 scripts/manifest_tool.py history archive <root> \
  --input conversation.md --kind transcript --source current-chat
```

The archive command stores only supplied content and explicitly named attachments.
History is append-only and read only when `history list`, `history search`, or
`history show` is called. A summary is a new archive with kind `summary`; it never
replaces source material.

## Model

A Task is an independently deliverable group of Nodes and maps to one Draft Pull
Request. Its Draft PR contains the commits produced by its Nodes. A Node is one
scoped change and maps to one commit. Nodes contain the work, dependency edges,
current status, current result, optional current commit reference, and pending
upstream reviews. A Task may store one optional current Draft PR reference.

Every delivered Task and its Draft PR must produce a buildable, runnable client.
Assign each Task an `integration_owner` before dispatch. Ownership identifies a
responsibility, not a model or temporary Agent session. The owner integrates Node
commits, resolves conflicts, verifies the Task and maintains its Draft PR.
Design Task groups so their ready Nodes can run in parallel and the group can be
implemented and reviewed independently after declared prerequisites; represent real
ordering within and between Tasks with explicit dependencies. This Task/PR and Node/commit
mapping is a Better Plan project convention, not an assertion that every engineering
organization uses the same terminology.

Shared requirements live once in `Tree.json`. Task requirements live once in their
Task. Do not copy either into every Node. A Node's `contract` contains only facts
specific to that work.

Pending review and completion are independent facts. When work or dependencies
change, the tool walks only the affected downstream graph and adds a source-keyed
review item. It keeps existing status and result. Repeated changes from the same
source replace that pending item instead of building a revision story.

## Worker flow

Start through the tool:

```sh
python3 scripts/manifest_tool.py node start <root> NODE-001
```

The response prints shared requirements, Task requirements, Node context, and
pending reviews. Do the work and report the result, then finish:

```sh
python3 scripts/manifest_tool.py node finish <root> NODE-001 \
  --summary "Implemented and checked the scoped behavior." --commit <ref>
```

The requirements are printed again with a prompt to report compliance and
exceptions. Record the Node's scoped commit. When all Nodes finish, the response
reports `ready_for_integration` and the designated `integration_owner`; finishing
last never assigns that responsibility to the Worker.

The integration owner records the Task result after integrating and verifying it.
The main Agent records the overall Tree result after whole-delivery review and
verification:

```sh
python3 scripts/manifest_tool.py task finish <root> TASK-001 --summary "Integrated and verified; PR remains Draft."
python3 scripts/manifest_tool.py tree finish <root> --result delivery-result.json
```

Both commands accept `--summary` or `--result` (a JSON object containing the current
conclusion and any `exceptions`). They record declarations only: no Git action,
test execution or approval gate. Default delivery ends at engineering completion
with PRs Draft. Ready, merge, installation and live acceptance follow separately
authorized project work.

Node execution progress and delivery validity are separate. Task and Tree `delivery`
hold the latest `result` and source-keyed `review` items. Reports derive `unrecorded`,
`recorded`, or `needs_review`. Relevant changes preserve the result while requiring
reconfirmation. A finish command confirms only its own layer; it never clears Node
reviews, failed checks or Task delivery concerns. A Tree cannot appear currently
confirmed while any Task is unrecorded or needs review. Successful checks and
`node review-done` never reconfirm delivery automatically.

## Refactoring slices

Design refactors as small, behavior-preserving steps that keep the system working,
following the incremental principle described by [Refactoring](https://refactoring.com/).
Each Node commit owns one coherent scoped change. Each Task/Draft PR is an
independently implementable integration slice whose final state builds and runs.
[Google's engineering guidance on small changes](https://google.github.io/eng-practices/review/developer/small-cls.html)
likewise recommends self-contained changes that include their related consumers and
tests and leave the system working; Better Plan applies the dependency principle,
without imposing a line-count or universal test-count gate.

Update affected producers, consumers, tests, and documentation in the same Task.
When correcting unpublished project-owned work, remove the superseded path instead
of adding compatibility layers merely to preserve the obsolete implementation.
State cross-Task dependencies explicitly; do not hide an incomplete dependency in
a nominally parallel Draft PR.

Nodes represent real scoped code, documentation, or configuration changes. Do not
invent design-only, status-only, or audit-only Nodes that would require empty
commits. A Tree-level final audit is delivery lifecycle activity; create a Node only
when that audit discovers a real correction to implement.

Task and Tree finish leave PRs Draft. Their result is an engineering handoff, not
authorization to make PRs Ready, merge, install or run live acceptance. A project's
explicit delivery policy may describe those later operations; the main Agent must
follow the actual authorization. Dependent Task PRs may be stacked on their declared
dependencies. Do not label them independent merely to maximize parallel work.

Parallelize source changes and isolated builds when their declared resources do not
conflict. Treat a shared runtime, installed client, or real user-data location as a
coordinated resource and serialize only operations that actually contend on it. Use
the project's fixed acceptance scope; do not invent alternate backends, fake
directories, or broader scenarios as substitutes for the required real workflow.

## Tree operations

Use `scripts/manifest_tool.py` as the single entry point:

```sh
python3 scripts/manifest_tool.py tree init <root> --title "Delivery" --goal "Outcome"
python3 scripts/manifest_tool.py task add <root> --input task.json
python3 scripts/manifest_tool.py node add <root> --input node.json
python3 scripts/manifest_tool.py edge add <root> NODE-001 NODE-002
python3 scripts/manifest_tool.py tree next <root> --json
python3 scripts/manifest_tool.py tree export <root>
```

`node update` recursively merges object fields, so changing `contract.scope` does
not replace the rest of the contract. `node edit --editor <command>` opens a
temporary copy outside the workspace lock and merges only the actual edits into the
latest Node. `node add --between A B` inserts a Node into an edge. Removing a Node
reconnects its predecessors to its direct successors unless `--disconnect` is used.

`subtree show`, `attach`, `move`, and `remove` operate on a branch. A downstream join
that also has a predecessor outside the branch remains an external boundary.

Each file write is atomic and current-state operations hold one short workspace lock. Commands and editors run
outside the lock. Local operations do not validate or rewrite unrelated branches.
`tree refresh` simply rebuilds the current derived view after manual edits; it cannot
reconstruct notifications bypassed by those edits.

## Checks

Define each check once at the lowest common owner:

- Node check: covers one Node.
- Task check: covers the Task's current Nodes.
- Tree check: covers the current Tree.
- Explicit `nodes` coverage: covers only the listed Node ids.

Every check has a stable id, commands, coverage, pending/running/dirty state, and its
latest result. A relevant plan change marks only checks whose coverage intersects
the affected graph. If a relevant change occurs while a check runs, the result is
kept and the check remains pending. Unrelated changes do not invalidate it.

```sh
python3 scripts/manifest_tool.py checks list <root>
python3 scripts/manifest_tool.py checks run <root> CHECK-001 --owner task:TASK-001
python3 scripts/manifest_tool.py checks record <root> CHECK-002 \
  --owner node:NODE-003 --status passed --summary "Observed externally"
```

Running or recording checks is optional convenience and never controls whether a
Node may finish. Each check has one nonblocking process lock; duplicate runs and
external result writes report an active execution without cancelling or queueing.
Different checks remain parallel. A temporary run identity prevents a removed and
recreated check from accepting an old execution's result.

An interrupted executor leaves an unknown result, not a failure or success. Confirm
that leftover commands have ended, then run
`checks recover <root> CHECK-001 --owner task:TASK-001` before retrying. Recovery preserves the previous result and leaves the
check pending; it does not kill processes. No elapsed-time rule terminates work.

## Programmes and reports

`Programme.json` stores delivery identities, Tree paths, and `requires` edges only.
It has no history or duplicated execution state. `programme status` derives current
state by reading each split Tree workspace. A dependency is satisfied only when its
Tree delivery is currently `recorded`, including confirmed Task deliveries.

Reports consume `tree export`. The export assembles Tasks and Nodes for presentation
and includes derived readiness, status, review, contention, blockers, and flattened
checks. Reports do not parse prose or read history.

Read [references/checkpoints-tree.md](references/checkpoints-tree.md) for the exact
file and command contract, [references/programme.md](references/programme.md) for
multi-delivery indexing, and the role references for concise authoring and execution
guidance. Host role files and receipts are existing user configuration; installation
operations never rewrite or re-sign them.

## Host role boundaries

Load the current skill and role reference for each assignment. Existing native role
files and receipts remain user configuration; skill updates cannot override their
instructions. Report a concrete host/skill constraint conflict to the main Agent.
Doctor reports source consistency, receipt integrity and template differences
separately; template drift alone is not evidence of a semantic conflict.
