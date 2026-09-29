# Checkpoints Tree contract

## Persisted current state

`Tree.json`:

```json
{
  "schema": "better-plan.checkpoints-tree",
  "id": "TREE-001",
  "title": "Delivery",
  "goal": "Final outcome",
  "success": ["Observable success criterion"],
  "architecture": null,
  "delivery_policy": null,
  "requirements": ["Shared working requirement"],
  "open_decisions": [],
  "delivery": {"result": null, "review": []},
  "checks": []
}
```

`tasks/TASK-001.json`:

```json
{
  "id": "TASK-001",
  "title": "Grouped outcome",
  "outcome": "What this group delivers",
  "requirements": ["Requirement for this Task"],
  "draft_pr": null,
  "integration_owner": "task-integrator",
  "delivery": {"result": null, "review": []},
  "checks": []
}
```

`nodes/NODE-001.json`:

```json
{
  "id": "NODE-001",
  "task": "TASK-001",
  "title": "Executable work",
  "outcome": "What completion produces",
  "after": [],
  "status": "pending",
  "role": "worker",
  "executors": [],
  "resources": [],
  "contract": {"scope": "Node-specific facts only"},
  "review": [],
  "result": null,
  "commit": null,
  "checks": []
}
```

A Task is an independently deliverable group of Nodes and corresponds to one Draft
PR containing those Nodes' commits. A Node is one scoped change and corresponds to
one commit. Ready Nodes inside a Task may execute in parallel; actual ordering is
stored in their dependencies. `draft_pr` and `commit` hold the current reference only; they are not Git
event ledgers. Every delivered Task and its Draft PR must leave the client buildable
and runnable. This mapping is a Better Plan convention.

A Tree or Task `requirements` entry may be a plain string or an object carrying a
`statement` and `source_ids`. `source_ids` reference ids from the programme's
`Requirements.json` catalogue; the catalogue owns requirement identity and status,
so Trees and Tasks reference it instead of duplicating status. Text values may be
plain strings or bilingual objects such as `{"en": "...", "zh": "..."}` and are
treated as opaque.

`integration_owner` identifies the Agent responsibility for Task integration, not a
model or temporary session. Assign it before dispatch. When all Nodes finish,
`ready_for_integration` informs this owner to assemble commits, resolve conflicts,
verify the Task and maintain its Draft PR. The final Worker does not inherit ownership.

`delivery_policy` is optional current Tree policy. Default delivery ends at
engineering completion with PRs Draft. Ready, merge, installation and live acceptance
are separately authorized project work; recording delivery performs none of them.

## Delivery results

Task integration owners use `task finish <root> <id> --summary TEXT` or `--result FILE`.
The main Agent uses `tree finish <root>` with the same result options after overall
review and verification. `--result` is a JSON object (or `-` for stdin); use `summary`
and `exceptions` for the conclusion and any exceptions. Commands record declarations
without approval, Git or test gates. They replace only the owner's current result
and clear only that owner's delivery reviews. Generic Tree/Task updates do not edit
`delivery`; use finish for confirmation.

Derived delivery states are `unrecorded` (no result), `recorded` (result with no
pending review), and `needs_review` (preserved result with pending review). Tree
validity also depends on every current Task being recorded; Tree finish cannot hide
an unrecorded or stale Task. Checks and Node reviews remain separate visible facts.
A successful check or cleared Node review never reconfirms delivery automatically.

Delivery invalidation applies only when a previous result exists. Before initial
confirmation the delivery is already unrecorded, so redundant review markers are
not accumulated. Current review sources are deduplicated by kind and id:

| Change | Delivery affected |
| --- | --- |
| Node scope, dependencies or commit | Owning and affected downstream Tasks, plus Tree |
| Node result | Owning and downstream Tasks, plus Tree; downstream Node reviews and covered checks also change |
| Node execution status | Owning Task and Tree |
| Node addition, removal or Task move | Old/new owners and affected downstream Tasks, plus Tree |
| Task goal or requirements | Task and downstream Tasks, plus Tree; includes empty Tasks |
| Tree goal, requirements or success criteria | All Tasks and Tree |
| Check commands/coverage added, removed or changed | Union of old/new covered Tasks and Tree |
| New failed check result or explicit interrupted-run recovery | Covered Tasks and Tree |
| Task delivery recorded or Task added/removed | Tree |
| Display title, integration owner, role/executor label or PR reference | No code review or delivery invalidation |

Identical value updates do not propagate. Source kind `check` uses the compound id
`<owner-kind>:<owner-id>:<check-id>`, so checks with the same id at different owners
remain distinct. No content hash, whole-tree revision, or background file watching is
used. Manually edited files cannot acquire missed notifications through refresh.

The maintained status vocabulary is `pending`, `running`, `completed`, `failed`,
`blocked`, and `cancelled`. `node start` writes `running`; `node finish` writes
`completed`. Status does not restrict either command.

Task membership and `after` dependencies are stored only on the Node. Task execution progress,
reverse dependencies, readiness, blockers, role groupings, contention, and report
views are derived. Unknown metadata may be retained; the tool does not turn schema
shape into a workflow gate. IDs must be filename-safe because they name files.

`Tree.json` stores no assembled `tasks` or `nodes`; those live in `tasks/` and
`nodes/`. An earlier single-file Checkpoints Tree reused this schema string while
keeping its Tasks and Nodes inside `Tree.json`, so a shape check refuses that file
instead of reporting an empty plan. Migrate such a workspace into the split layout
or read it with the matching earlier tool version.

## Pending review

A review item is current state:

```json
{
  "source": {"kind": "node", "id": "NODE-001"},
  "reason": "content_changed"
}
```

Sources are `tree`, `task`, or `node`. Reasons are
`content_changed`, `dependency_changed`, `requirements_changed`, or
`manual_refresh`. The same source occupies one item. A changed Node and its
downstream Nodes receive the item; Task changes start at that Task's Nodes; Tree
content changes cover the Tree. The traversal builds adjacency once and uses a
queue plus a visited set, so branches, joins, and cycles terminate.

Review does not reset status or result. `node review-done` clears all review items or
the selected source after an Agent handles them.

## Check definition and state

```json
{
  "id": "CHECK-001",
  "title": "Focused behavior",
  "commands": ["project-test-command"],
  "coverage": {"kind": "task"},
  "pending": true,
  "running": false,
  "run_id": null,
  "dirty": false,
  "result": null
}
```

Coverage forms:

| Kind | Meaning |
| --- | --- |
| `node` | the owning Node |
| `task` | the owning Task's current Nodes |
| `tree` | the Tree's current Nodes |
| `nodes` | exactly `coverage.nodes` |

Place the definition at the lowest owner common to its coverage. A stable ID is
unique within that owner. Commands are not compared or deduplicated by text.

Changing covered work sets `pending`. If the check is running, it also sets `dirty`.
When a run returns, its result is recorded; `pending` remains true when dirty. An
external result may be recorded only when no execution is active or unresolved;
it clears dirty and pending. Readiness in an export
means all currently covered Nodes are completed, but `checks run` and `checks record`
do not enforce readiness and do not gate Node completion.

Each `<owner, check-id>` has one independent nonblocking OS lock held through
command execution and result publication. The short workspace lock is released
while commands execute. Duplicate runs, external result writes and recovery return
an active-execution error immediately; they never queue or cancel existing work.
A temporary `run_id` associates a return with the current check object. Removing and
recreating that object cannot accept an older run's result. Definition edits preserve
runtime fields and make an active run dirty.

A check result is free-form JSON. A result object containing a `metrics` object whose
values are numbers is collected by `programme export`; metrics never gate completion
or delivery. For example, `checks record <root> CHECK-001 --owner tree --result
metrics.json` with `{"status": "passed", "summary": "Measured", "metrics":
{"native_loc": 367511}}` contributes one `native_loc` measurement.

Read snapshots report `interrupted: true` when an unresolved execution marker has
no live executor lock. Its commands may still be running; the result is unknown and
the previous result is preserved. Confirm leftover commands have ended, then invoke:

```sh
python3 scripts/manifest_tool.py checks recover <root> CHECK-001 --owner task:TASK-001
```

Recovery explicitly clears the unresolved marker and leaves the check pending. It
never kills processes or reports a passed result. Running or recording without
recovery reports the unresolved execution. No elapsed-time limit terminates work.
Lock files under `.better-plan-checks/` are stable synchronization artifacts, not
execution history, and must not be removed while the workspace is in use.

## Local structural operations

- `node add --between A B` replaces edge `A -> B` with `A -> new -> B` and keeps
  every other dependency declared for the new Node.
- `node remove` reconnects each direct successor to the removed Node's predecessors.
  `--disconnect` removes the edges without reconnecting.
- `node update` recursively merges objects; arrays and scalar values replace.
- `node edit --editor COMMAND` snapshots one Node, runs the editor outside the lock,
  and overlays only the actual edits onto the latest Node when the editor returns.
- `edge add/remove` changes one named edge and propagates from its successor.
- `subtree` accepts a primary entry, repeated `--entry`, and repeated `--exit`.
  Default traversal stops before a join with a predecessor outside the selected
  branch. A named exit is included and traversal stops after it.
- `subtree attach` adds `--after` predecessors to the entries and may add selected
  exits to `--before` successors. `subtree move` replaces either boundary only when
  that option is present; unrelated successor dependencies remain.
- Subtree removal reconnects each external successor only to external predecessors
  reachable through that successor's removed paths. Disconnected groups do not gain
  false cross-dependencies.

Local operations inspect their named targets. Unrelated dangling references, cycles,
roles, statuses, or metadata do not block a write. `tree refresh` recomputes the view
after manual edits without inventing missed notifications.

## Worker context

`node show`, `node start`, and `node finish` return the Tree identity, title, goal and
success criteria; the Task identity, title, outcome and requirements; shared
requirements; the Node contract; necessary dependencies; and pending reviews. They
do not load unrelated branches or history. Start and finish both print requirements;
finish also asks for compliance and exception reporting without requiring an answer
to record completion. Finish accepts `--commit` for the Node's current commit. It
prints an advisory commit reminder and, when every Node in the Task is completed,
`ready_for_integration`, `integration_owner` and an integration handoff reminder.
The Task result remains unrecorded until its owner explicitly records delivery; a
project may open the Draft PR earlier.

## Export

`tree export` assembles the split files for read-only consumers:

```json
{
  "tree": {"tasks": [{"nodes": []}]},
  "derived": {
    "status": "running",
    "delivery_status": "unrecorded",
    "task_delivery_status": {},
    "unconfirmed_tasks": [],
    "ready": [],
    "node_counts": {},
    "task_status": {},
    "role_nodes": {},
    "contention": [],
    "review_nodes": [],
    "task_review_nodes": {},
    "blockers": {}
  },
  "checks": []
}
```

Each flattened check contains its owner, resolved covered Node ids, state, readiness,
commands, and latest result. Export never reads `history/`.

## History

`history archive` accepts caller-supplied transcript or summary content. Optional
attachments are stored byte-for-byte as base64 with their relative display path.
Archives cannot be replaced or edited. `history search` explicitly reads archive
content and decodes UTF-8 attachments for search; binary attachments are skipped.
`history show --attachment PATH` restores one attachment's original bytes.

History has no influence on current status, review, checks, or reports.

## Persistence and concurrency

Individual current files use temporary-file replacement under one short workspace
lock. A multi-file operation is serialized, not a crash-atomic transaction.
Only changed Tree, Task, and Node files are written. Editors and check commands run
without the lock. Read projections take one locked multi-file snapshot and release
the lock before rendering. A running check uses its local `dirty` bit to observe
relevant concurrent changes and its temporary `run_id` to reject obsolete returns;
there is no whole-tree revision, generation, hash, or version comparison.
