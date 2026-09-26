# Programme

One Tree is one delivery. A **programme** is the small index over many of them: which deliveries
exist, where their Trees are, and which delivery must land before another may start. It is one JSON
object at `Programme.json`, beside the Trees it names.

Load this reference when a piece of work spans several deliveries, when a delivery waits on another,
or when parallel deliveries contend for one machine resource.

## The index stores order, never state

`Programme.json` records identity, location, and edges. It has **no** status, count, gate, or
progress field, and unknown fields are rejected — so a hand-maintained `state` cannot creep in and
drift from the Tree that owns it. Every state a command prints is derived by reading the referenced
Trees at that moment.

```json
{
  "schema": "better-plan.programme",
  "id": "PROGRAMME-001",
  "title": "Client delivery",
  "revision": 3,
  "deliveries": [
    {
      "id": "DELIVERY-M10",
      "title": "Platform separation",
      "tree": "10-platform-separation/Tree.json",
      "requires": []
    },
    {
      "id": "DELIVERY-M11",
      "title": "Command contract",
      "tree": "11-mobile-command-contract/Tree.json",
      "requires": ["DELIVERY-M10"]
    }
  ],
  "meta": {},
  "history": [],
  "created_at": "timestamp",
  "updated_at": "timestamp"
}
```

Rules:

1. **`tree` is workspace-relative.** An absolute path is refused, because a programme has to move
   with the repository it describes.
2. **`requires` names deliveries in the same programme.** A missing reference is a data error, and so
   is a cycle.
3. **A delivery is ready when every delivery it requires is `completed`** — as derived from those
   Trees, not as declared here.
4. **The programme never constrains a Node.** It does not gate `tree-transition`, does not schedule
   anything, and never writes to a Tree. It answers "what may start now" and nothing else.
5. **The programme is not a second ledger.** It holds no state to keep honest; it is an index plus an
   order. The Tree remains the only writer per truth, and `tree --json` remains the only projection a
   renderer needs.

## Authoring it

```sh
python3 scripts/manifest_tool.py programme-init  <root> --title "<programme>"
python3 scripts/manifest_tool.py programme-apply <root> --input batch.json --dry-run
python3 scripts/manifest_tool.py programme-apply <root> --input batch.json
python3 scripts/manifest_tool.py programme-status <root> --json
python3 scripts/manifest_tool.py programme-validate <root>
python3 scripts/manifest_tool.py programme <root>
```

| Operation | Required fields | Effect |
| --- | --- | --- |
| `programme.update` | one or more of `title`, `meta` | Update programme-level context. |
| `delivery.add` | `id`, `tree`; optional `title`, `requires` | Add a delivery to the programme. |
| `delivery.update` | `id`, `set` | Replace `title`, `tree`, or `requires`. |
| `delivery.remove` | `id`; `force` when another delivery requires it | Remove a delivery and detach the edges pointing at it. |

A batch is atomic and carries `batch_id`, `actor`, and `base_revision` exactly like `tree-apply`;
`base_revision` compares the programme `revision`, and a replayed `batch_id` is reported as
`idempotent` rather than applied twice.

## What `programme-status` reports

For each delivery, in dependency order:

| Field | Meaning |
| --- | --- |
| `state` | the Tree's own derived status: `pending`, `ready`, `running`, `completed`, `failed`, `blocked`, `cancelled`, or `missing` / `invalid` when the Tree cannot be read |
| `blocked_by` | the deliveries it requires that are not yet `completed` |
| `ready` | true when nothing blocks it and it is not already finished |
| `ready_nodes` | the Nodes that may start now inside that Tree |
| `reviewer`, `gate` | the closing Node and the Node(s) it waits for |
| `counts`, `nodes`, `tasks` | what the Tree contains, derived |

and for the programme as a whole: validation `issues`, per-state `counts`, the `ready` delivery list,
and `contention`.

## Contention

Principle 10 asks a Designer to attribute the resources parallel units contend on — a worktree, a
build directory, a toolchain cache, a version-control index, a test store, a port, a device. Nodes
declare them in `resources`; the two ordering layers are a Tree's `after` graph (inside one delivery)
and a programme's `requires` edges (between deliveries).

`programme-status`, `programme-validate`, and `tree-validate` all report a resource that two Nodes
declare together with **no ordering path between them**:

```text
contention: worktree/ shared by M11/NODE-002, M12/NODE-002, M13/NODE-002; unordered: M12/NODE-002 <-> M13/NODE-002
```

That line is the whole check. It is a report, never an error: two Nodes may read one input, and the
repair is either an `after` edge that serializes them or narrower resource names that stop colliding.
A delivery that another delivery requires is treated as ordered by that edge.

## Migrating a hand-maintained manifest

A workspace that already keeps its own programme document usually carries a `state` field, a
`directory`, and a `code`. Drop the state — it is what the Trees are for — and map the rest:

| Hand-maintained field | Programme field |
| --- | --- |
| `code` | `id` |
| `title` | `title` |
| `directory` + file name | `tree` (relative to the programme file) |
| `requires` (names or directories) | `requires` (delivery ids) |
| `state` | delete it; `programme-status` derives `state` per delivery |

Then a renderer reads `programme-status --json` plus `tree --json` instead of re-implementing status
derivation, and the delivery record has one writer again.
