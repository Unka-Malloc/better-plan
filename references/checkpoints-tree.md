# Checkpoints Tree

The Checkpoints Tree is the canonical delivery state.  It is one JSON object at `Tree.json`.
Whatever produces it — a Designer, an agent batch, a hand edit, or a converter — the tool
accepts it only when it matches the canonical shape below.

## Canonical shape

```json
{
  "schema": "better-plan.checkpoints-tree",
  "id": "TREE-001",
  "title": "Delivery",
  "generation": 3,
  "tasks": [
    {
      "id": "TASK-001",
      "title": "Build the result",
      "outcome": "The result is built and ready for verification.",
      "contract": {},
      "nodes": [
        {
          "id": "NODE-001",
          "title": "compile",
          "outcome": "The artifact compiles.",
          "role": "worker",
          "executors": ["provider-a/model-x", "provider-b/model-x"],
          "resources": ["build/", "cargo-target/"],
          "after": [],
          "status": "completed",
          "executor": "any/agent",
          "attempts": 1,
          "evidence": [
            {
              "verified": true,
              "commands": [
                {
                  "command_sha256": "9f2c…",
                  "outcome": "passed",
                  "exit_code": 0,
                  "recorded_at": "timestamp"
                }
              ]
            }
          ],
          "contract": {}
        },
        {
          "id": "NODE-002",
          "title": "verify",
          "outcome": "The artifact passes verification.",
          "role": "worker-2",
          "executors": [],
          "resources": [],
          "after": ["NODE-001"],
          "status": "pending",
          "executor": null,
          "attempts": 0,
          "evidence": [],
          "contract": {}
        }
      ]
    }
  ],
  "meta": {},
  "history": [],
  "created_at": "timestamp",
  "updated_at": "timestamp"
}
```

## Rules

1. **Tasks group Nodes.** A Task is not an executable unit; only a Node is executable.
2. **`after` is the only dependency edge.** It names Node ids and may cross Tasks.
3. **Only Nodes store execution state.** Task and Tree status are computed from Node state.
4. **Node status is one of:** `pending`, `running`, `completed`, `failed`, `blocked`, `cancelled`.
5. **`ready` is not stored.** A Node is startable when its status is `pending`, `failed`, or `blocked`
   and every id in `after` is `completed`.
6. **Ids are opaque and globally unique.** They are not required to use `TASK-*` or `NODE-*`; those
   prefixes are a readable convention, not a rule.
7. **`contract` and `meta` are opaque objects, with exactly one interpreted key.** Ownership,
   acceptance criteria, project requirements, and project metadata belong there, and the tool only
   stores them. The single exception is `contract.commands` on a Node: it names the commands whose
   execution produces that Node's completion evidence, so the tool has to read it. Commands declared
   anywhere else — including a Task `contract` — are rejected rather than silently ignored.
   Everything else the tool records as its own structured data — ids, titles, outcomes, roles,
   executors, `after` references, notes, evidence, and history — must survive the privacy guard:
   a secret, an absolute local path, or a network endpoint in any of them is refused with the exact
   field and rule, and the batch or transition is not applied. `contract` and `meta` are the only
   places opaque project data may sit.
8. **Unknown structural fields are rejected.** Extension points are `contract` and `meta`.
9. **A cycle is invalid.** The `after` graph must be acyclic.
10. **Every write is atomic.** `tree-apply` validates the whole batch before committing.
11. **Completion evidence records who produced it.** A Node that declares `contract.commands` is
    completed only by `tree-verify`, which runs those commands itself and appends the receipts it
    observed (`source: cli`). A Node without commands has nothing to run, so only a report can
    complete it (`source: reported`), and `tree-status` lists reported completions separately so the
    two kinds of green never look alike.
12. **Every Node names the role that executes it.** `role` is required and is `designer`, `reviewer`,
    or a worker slot. A worker name is a slot, not a person: write `worker`, or `worker-1`,
    `worker-2`, … when a delivery splits work across several workers. There is no ceiling on how many
    worker slots a delivery uses, and no second kind of worker. `role` is the design-time assignment —
    who owes this outcome. `executor` is a different thing: the opaque identity of the session that
    actually ran the Node, recorded when it starts. `tree-next` reports every ready Node with its
    role, `tree-status` lists the Nodes each role owns, and changing a role on a Node that already
    started requires `reset: true`, exactly like any other definition change.
13. **One designer opens the graph, one reviewer closes it, workers fill the middle.** Authoring stays
    free: a half-built Tree is valid data and writes normally. The shape is checked when work starts.
    `tree-next` reports what is missing, `tree-transition … start` refuses until the shape is complete,
    and `tree-validate --json` reports `runnable` and `shape_issues` separately from data errors, so
    "not finished designing yet" never looks like "corrupt file".
14. **A Node declares who may run it, in order.** `executors` is an optional ordered list of
    executor names — whatever your host can run: a provider and model pair, a named profile, an
    account. The tool keeps no registry and checks no quota. It stores the order, records which
    candidate each attempt used, and names the next one, so a spent account is one retry away from
    continuing. An empty or absent list means "any executor". Appending a fallback to a Node that
    already started is the one edit that needs no reset, because adding a place to run does not
    redefine the work; replacing the list, like any other definition change, requires `reset: true`.
    A Node that declared no chain has no fallback to append to, so pinning one for the first time is
    a replacement and needs the reset too.
    `tree-next` prints the executor to use next, what is behind it, and what is already spent;
    `tree-transition … fail` reports the next candidate after a spent one.

15. **A Node declares what it contends on.** `resources` is an optional list of opaque names — a
    file tree, a build or artifact directory, a toolchain cache, a version-control index, a test
    store, a port, a device. The tool never resolves, reserves, or locks one. It reports every
    resource that two Nodes declare together **without an ordering path between them**: that is the
    design question principle 10 asks the Designer to answer, and `tree-validate` and `tree` state
    the answer instead of leaving an unordered collision to be discovered at runtime. A shared
    resource is never an error — two Nodes may read the same input, and a deliberate serialization
    is just `after`. Ordering the Nodes, or narrowing the resource names until they no longer
    collide, is the whole repair.

16. **The Tree may be replaced, never silently.** `tree-init --replace --reason "<why>"` re-authors a
    delivery in place: the new Tree keeps the old identity, `created_at`, and the complete `history`,
    continues the generation, and appends one `replace` entry recording the reason, the replaced
    graph's generation, Task and Node counts, and a `sha256` of its canonical bytes. Without
    `--reason` the command refuses, and deleting `Tree.json` by hand is never the supported path.

## Direct authoring operations

The Designer writes Tree operations through `tree-apply`.  A batch is one JSON object:

```json
{
  "batch_id": "designer-1",
  "actor": "designer/any",
  "base_revision": 3,
  "operations": [
    {
      "op": "task.add",
      "id": "TASK-001",
      "title": "deliver",
      "outcome": "The delivery is directly visible in the Tree."
    },
    {
      "op": "node.add",
      "task": "TASK-001",
      "id": "NODE-001",
      "title": "build",
      "outcome": "Build the result."
    },
    {
      "op": "node.add",
      "task": "TASK-001",
      "id": "NODE-002",
      "title": "verify",
      "outcome": "Verify the result."
    },
    {
      "op": "after.add",
      "node": "NODE-002",
      "after": "NODE-001"
    }
  ]
}
```

| Operation | Required fields | Effect |
| --- | --- | --- |
| `tree.update` | one or more of `title`, `meta` | Update tree-level context. |
| `task.add` | `id`; optional `title`, `outcome`, `contract`, `nodes` | Add a Task together with its Nodes. |
| `task.update` | `id`, `set` | Replace `title`, `outcome`, or `contract`. |
| `task.remove` | `id`; `force` for non-pending Nodes | Remove a Task and its Nodes. Edges pointing at removed Nodes are detached. |
| `node.add` | `task`, `id`, `role`; optional `title`, `outcome`, `executors`, `resources`, `after`, `contract` | Add an executable Node to a Task. `title` and `outcome` default to the id. |
| `node.update` | `id`, `set` | Replace `title`, `outcome`, `role`, `executors`, `resources`, `after`, or `contract`. Active Nodes require `reset: true`, which resets the Node and its downstream Nodes. |
| `node.move` | `id`, `task` | Move a Node to another Task. |
| `node.remove` | `id`; `force` for active Nodes or downstream Nodes | Remove a Node and detach edges pointing at it. |
| `after.add` | `node`, `after` | Add a dependency. Non-pending Nodes require `reset: true`. |
| `after.remove` | `node`, `after` | Remove a dependency. Non-pending Nodes require `reset: true`. |

`task.add` takes the whole Task in one operation: give it `nodes` and every entry is added as that
Task's Node, in order, with the Task already named. One operation per Task is the ordinary
authoring shape; a generator script that expands flat operations is not needed and is not a second
dialect.

```json
{
  "op": "task.add",
  "id": "TASK-001",
  "title": "deliver",
  "outcome": "The delivery is directly visible in the Tree.",
  "nodes": [
    {"id": "NODE-001", "title": "design", "outcome": "The approach is fixed.", "role": "designer"},
    {
      "id": "NODE-002",
      "title": "build",
      "outcome": "The artifact builds.",
      "role": "worker-1",
      "after": ["NODE-001"],
      "resources": ["build/"],
      "contract": {"commands": ["npm run build"]}
    },
    {"id": "NODE-003", "title": "review", "outcome": "The delivery is audited.", "role": "reviewer", "after": ["NODE-002"]}
  ]
}
```

`tree-apply --dry-run` evaluates the whole batch and returns the resulting ready set without changing
the Tree. One invalid operation rejects the whole batch. A batch may also be a bare array of
operations; the object form additionally carries `batch_id`, `actor`, and `base_revision`, and a
`batch_id` already present in the history is reported as `idempotent` instead of applied twice.

## Execution commands

```sh
python3 scripts/manifest_tool.py --version
python3 scripts/manifest_tool.py schema
python3 scripts/manifest_tool.py schema programme
python3 scripts/manifest_tool.py tree-init <root> --id TREE-001 --title "..."
python3 scripts/manifest_tool.py tree-init <root> --replace --reason "..."
python3 scripts/manifest_tool.py tree-apply  <root> --input batch.json --dry-run
python3 scripts/manifest_tool.py tree-apply  <root> --input batch.json
python3 scripts/manifest_tool.py tree-apply  <root> --input - --json
python3 scripts/manifest_tool.py tree-next   <root> --explain --json
python3 scripts/manifest_tool.py tree-next   <root> --limit 2
python3 scripts/manifest_tool.py tree-transition <root> NODE-001 start --executor "<opaque-id>"
python3 scripts/manifest_tool.py tree-verify <root> NODE-001 --executor "<opaque-id>"
python3 scripts/manifest_tool.py tree-verify <root> NODE-001 --cwd <project-root>
python3 scripts/manifest_tool.py tree-transition <root> NODE-001 fail --note "..."
python3 scripts/manifest_tool.py tree-transition <root> NODE-001 block --note "..."
python3 scripts/manifest_tool.py tree-transition <root> NODE-001 complete --evidence '{"exit": 0}'
python3 scripts/manifest_tool.py tree-transition <root> NODE-001 reset
python3 scripts/manifest_tool.py tree-transition <root> NODE-001 cancel
python3 scripts/manifest_tool.py tree-status   <root> --json
python3 scripts/manifest_tool.py tree-validate <root> --quiet
python3 scripts/manifest_tool.py tree         <root> --details
python3 scripts/manifest_tool.py tree         <root> --json
```

`tree --json` is the read-only projection a host renders from: the stored Tree plus everything the
tool derives — Tree and Task status, the ready set, the role map, reported completions, and
contention. A renderer never has to re-implement derivation, and never parses a rendered view back.

Every command takes either a workspace root or a direct `Tree.json` path. Only `tree-init` creates a
workspace: every other command refuses a directory that holds no Tree and leaves nothing behind. A
command that finds one takes the workspace's `.better-plan.lock` — created beside the Tree it
protects — so two commands never write at once, and `tree-verify` releases that lock before it runs
the declared commands.

`tree-verify` runs the Node's declared `contract.commands` in the Tree's directory (or `--cwd`)
outside the workspace lock, then re-reads the Tree and completes the Node only when nothing moved
while the commands ran. A pending Node with nothing left to wait for is started first, so the common
path is one command instead of two. A failing command fails the Node and exits non-zero; either way
the tool's own receipts are what the Tree records. Completion by hand is refused for a Node that
declares commands.

Execution transitions are:

| Action | From | To | Notes |
| --- | --- | --- | --- |
| `start` | pending, failed, blocked | running | Requires every `after` Node to be completed and the delivery shape to be complete. Increments `attempts`. |
| `complete` | running, or pending/failed/blocked that may start | completed | Appends evidence and starts the Node first when it can, so judged work is one command. Refused when the Node declares `contract.commands`: use `tree-verify`. |
| `fail` | running | failed | Appends evidence and note. |
| `block` | any non-completed, non-cancelled | blocked | Appends evidence and note. |
| `reset` | any | pending | Resets the Node and every downstream Node; clears executor. |
| `cancel` | any non-completed | cancelled | Cancels the Node and every downstream Node. |

## What the status views show

```sh
python3 scripts/manifest_tool.py tree-next <root>            # ready Nodes, each with its role
python3 scripts/manifest_tool.py tree-status <root>          # who owns which Nodes
python3 scripts/manifest_tool.py tree-validate <root>        # data errors, then shape gaps
```

`tree-status` prints one line per role — `worker-1: NODE-002, NODE-005` — because the useful question
is which work a role owns, not how many Nodes it got. `tree-status --json` exposes the same map as
`role_nodes`, plus `reported_completions` for Nodes whose completion was asserted rather than run.

## Designer workflow

1. `tree-init` creates the empty Tree.
2. The Designer composes one or more `tree-apply` batches directly with Tasks, Nodes,
   `after` edges, and contracts. Give the graph its outside first — one `designer` Node with no
   `after`, one `reviewer` Node that nothing waits for — then fill the middle with worker Nodes.
   A Node that a machine can check declares its commands in `contract.commands`; a Node only a
   person can judge declares none.
3. `tree-apply --dry-run` previews the ready frontier.
4. The commit batch writes the Tree atomically.
5. Workers call `tree-next --explain`, execute ready Nodes, and report with `tree-transition`.
   A Node that declares `contract.commands` is finished with `tree-verify`, which runs them and
   records what it observed. Both finishing commands start the Node first when its dependencies are
   already done, so the ordinary path is one call per Node.

A Designer batch is the design. The Tree is not a projection of a Plan, and there is no second
authoring dialect to keep in sync.
