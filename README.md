# Better Plan

Better Plan is a dependency-tree assistant for long-lived delivery work. It keeps
the current plan small, gives Agents local Task, Node, edge, and subtree operations,
and moves old context into immutable archives that are read only on request.

It requires Python 3.8 or newer and has no third-party runtime dependency.

## Current workspace

```text
Tree.json
tasks/<task-id>.json
nodes/<node-id>.json
history/<archive-id>.json
```

`Tree.json` owns the delivery goal, success criteria, shared requirements, current
decisions, and Tree checks. A Task is one independently deliverable Node group and
one Draft PR; its ready Nodes may execute in parallel. A Node is one scoped change
and one commit. The files may store the
current Draft PR and commit references; they do not store Git event histories.
Each Task has a designated integration owner. Task and Tree delivery results are
recorded explicitly, separately from Node execution progress.
History never participates in ordinary reads or writes.

One optional `Programme.json` indexes several delivery workspaces and their order.
It stores no copied execution state.

## Quick start

```sh
python3 scripts/manifest_tool.py tree init docs/plan \
  --title "Delivery" --goal "The final outcome"
python3 scripts/manifest_tool.py task add docs/plan --input task.json
python3 scripts/manifest_tool.py node add docs/plan --input node.json
python3 scripts/manifest_tool.py edge add docs/plan NODE-001 NODE-002
python3 scripts/manifest_tool.py node start docs/plan NODE-001
python3 scripts/manifest_tool.py node finish docs/plan NODE-001 \
  --summary "Done" --commit <ref>
python3 scripts/manifest_tool.py task finish docs/plan TASK-001 --summary "Integrated; PR remains Draft"
python3 scripts/manifest_tool.py tree finish docs/plan --summary "Overall engineering verified"
python3 scripts/manifest_tool.py tree export docs/plan
```

Before updating the current plan, archive the relevant conversation you actually
have. This is guidance, not a gate:

```sh
python3 scripts/manifest_tool.py history archive docs/plan \
  --input conversation.md --kind transcript --source current-chat
```

## Operations

The single CLI groups commands by the object they affect:

| Group | Commands |
| --- | --- |
| `tree` | `init`, `show`, `next`, `status`, `export`, `refresh`, `update`, `finish` |
| `task` | `add`, `update`, `show`, `remove`, `finish` |
| `node` | `add`, `update`, `edit`, `move`, `remove`, `start`, `finish`, `review-done`, `show` |
| `edge` | `add`, `remove` |
| `subtree` | `show`, `attach`, `move`, `remove` |
| `history` | `archive`, `list`, `search`, `show` |
| `checks` | `list`, `run`, `record`, `recover` |
| `programme` | `init`, `update`, `show`, `status` |

Node changes propagate a source-keyed review item through the affected downstream
graph. Completed Nodes keep their results. Unrelated branches are untouched. Node
removal reconnects its direct predecessors and successors by default; subtree
operations preserve external joins and accept explicit entry and exit boundaries.

Finishing a Node prints an advisory scoped-commit reminder. When all Nodes finish,
the designated Task integration owner assembles commits, verifies the integrated
outcome and maintains its Draft PR before recording `task finish`. The main Agent
records `tree finish` after overall review. Finish records a conclusion and any
exceptions, without executing Git or tests. PRs remain Draft; subsequent Ready,
merge, installation and live acceptance require separate authorization.

Task and Tree delivery states are `unrecorded`, `recorded` or `needs_review`.
Relevant changes preserve the latest delivery result and mark it for reconfirmation.
The report exposes execution progress, delivery validity and unresolved child facts
separately. Programme dependencies require a currently recorded Tree delivery,
including confirmed Tasks.

Checks are defined once at Node, Task, Tree, or explicit Node-set scope. Relevant
changes mark those checks pending. A change during a run marks that check dirty, so
its observed result is retained while another run remains pending. Checks never gate
Node completion. Each check has an independent nonblocking execution lock.
Overlapping runs or result writes are rejected without cancelling the active run.
Interrupted executors require explicit `checks recover` after confirming leftover
commands have ended. Recovery preserves the previous result and leaves a rerun
pending; there is no execution deadline or automatic retry.

The tool writes only changed current-state files with atomic replacement under a
short workspace lock. Editors and check commands run outside the lock. It has no
whole-tree revision, generation comparison, lifecycle validator, role cardinality
rule, or approval state machine.

## Development

Better Plan source maintenance follows this repository's native workflow. Run
focused tests while editing and the complete suite once before handoff:

```sh
python3 -m unittest -v tests.test_checkpoints_tree tests.test_programme
python3 scripts/run_tests.py
```

See [SKILL.md](SKILL.md), [references/checkpoints-tree.md](references/checkpoints-tree.md),
and [references/programme.md](references/programme.md) for the maintained contract.
Host role configuration and receipts are user-owned and immutable after their first
creation; installer operations update the surrounding skill payload only.
