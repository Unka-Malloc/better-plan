# Programme contract

A Programme orders several delivery Trees without copying their execution state. It
may also outline far-term deliveries that have no Tree yet.

A delivery is one milestone: an independently deliverable unit. Independent
deliverability is the only criterion. A feature or capability, a module's rework or
refactor, a bounded group of defect repairs, a dependency or platform upgrade, or a
documentation and tooling change can each be one milestone. A layer, a partial slice,
or a shared mechanical step belongs inside a delivery as a Task or Node instead. The
requirement applies when the delivery is first outlined, before its Tree exists.

```json
{
  "schema": "better-plan.programme",
  "id": "PROGRAMME-001",
  "title": "Delivery programme",
  "goal": "Rolling-wave outcome",
  "success": ["Every milestone delivered"],
  "deliveries": [
    {
      "id": "DELIVERY-PLATFORM",
      "title": "Platform",
      "tree": "platform/Tree.json",
      "requires": []
    },
    {
      "id": "DELIVERY-ADAPTER-PACKAGES",
      "title": "Adapter packages",
      "requires": ["DELIVERY-PLATFORM"],
      "goal": "Ship adapter packages",
      "success": ["Adapters build and run"],
      "requirements": [
        {"code": "ADAPTERS", "statement": "Support adapters", "source_ids": ["REQ-ADAPTERS"]}
      ],
      "open_decisions": [{"title": "Which adapters first", "status": "open"}]
    }
  ]
}
```

`tree` is optional. A delivery without a Tree is planned; its outline fields use
exactly the names and shapes of the Tree fields they later become. The Programme
itself may carry descriptive `goal` and `success`; they are stored and exported
without derivation. Unknown fields are preserved everywhere.

The file stores identity, workspace-relative Tree paths, outline content, and
delivery dependency edges. It has no revision, history, status, counts, evidence, or
copied Node data. `programme status` locks and reads each split Tree workspace and
derives current state. A missing Tree is reported as `missing`. `state` is the Tree
delivery status: `unrecorded`, `recorded`, or `needs_review`; a planned delivery
reports `planned`. `execution_status` reports Node progress separately and is
`planned` for a delivery without a Tree or with a Tree that has zero Nodes. Neither
kind appears in `ready`. `ready_to_design` lists planned deliveries whose
`blocked_by` is empty, and `counts` includes `planned`. A `requires` dependency is
satisfied only by a currently `recorded` Tree delivery, including recorded Task
deliveries; Node completion alone cannot unblock another delivery, and a dangling
`requires` id keeps blocking. Readiness is advisory; it does not dispatch work or
enforce an approval gate.

```sh
python3 scripts/manifest_tool.py programme init <root> --title "Programme"
python3 scripts/manifest_tool.py programme update <root> --input update.json
python3 scripts/manifest_tool.py programme show <root>
python3 scripts/manifest_tool.py programme status <root> --json
python3 scripts/manifest_tool.py programme elaborate <root> DELIVERY-ADAPTER-PACKAGES
python3 scripts/manifest_tool.py programme export <root>
```

`programme update` accepts direct current-field updates. It also accepts an
`operations` array with `add`, `update`, and `remove` delivery operations. Removing a
delivery removes its id from other `requires` lists. There is no separate validation
or approval command.

`programme elaborate` transfers one planned delivery's outline into a new Tree
workspace and then removes the outline fields from the delivery. It refuses an
unknown delivery, a delivery that already has a `tree`, or a target Tree workspace
that already exists. The default Tree path is the lower-case delivery id with a
leading `delivery-` removed, then `/Tree.json`
(`DELIVERY-ADAPTER-PACKAGES` -> `adapter-packages/Tree.json`); `--tree` overrides
it. The Tree id is `TREE-` plus the upper-case slug, the title is the delivery
title, and `goal`, `success`, `requirements`, and `open_decisions` move from the
outline with empty defaults. The workspace is created exactly like `tree init` and
`Programme.json` is written atomically.

## Requirement catalogue

`Requirements.json`, next to `Programme.json`, owns programme-wide requirement
identity and status:

```json
{
  "schema": "better-plan.requirements",
  "requirements": [
    {
      "id": "REQ-ADAPTERS",
      "title": "Adapter support",
      "statement": "The client supports external adapters.",
      "status": "active",
      "priority": "high",
      "source": "product brief",
      "exclusion": "reason the programme intentionally does not own this"
    }
  ]
}
```

Every entry requires a unique string `id`; `title`, `statement`, `status`,
`priority`, and `source` are recommended. Text values may be plain strings or
bilingual objects such as `{"en": "...", "zh": "..."}`; the tool treats them as
opaque. Unknown fields are preserved.

```sh
python3 scripts/manifest_tool.py requirements list <root> [--json]
python3 scripts/manifest_tool.py requirements add <root> --input entry.json
python3 scripts/manifest_tool.py requirements update <root> REQ-ADAPTERS --input patch.json
python3 scripts/manifest_tool.py requirements remove <root> REQ-ADAPTERS
python3 scripts/manifest_tool.py requirements coverage <root> [--json]
```

`requirements add` accepts one entry object or an array and creates the file when
absent. `update` recursively merges object fields like `node update`; arrays and
scalar values replace. `remove` does not edit plans that still reference the id;
coverage reports the resulting unknown references.

## Coverage

Coverage is derived, never stored. `source_ids` are collected from planned delivery
outline `requirements`, each Tree's `requirements`, and each Task's `requirements`
entries that are objects carrying `source_ids`. Output keeps deterministic ordering:
catalogue order inside `by_requirement`, and programme order for deliveries,
references, and unknown references.

```json
{
  "by_requirement": {
    "REQ-ADAPTERS": {
      "deliveries": ["DELIVERY-ADAPTER-PACKAGES"],
      "tasks": [{"delivery": "DELIVERY-PLATFORM", "task": "TASK-002"}]
    }
  },
  "uncovered": ["catalogue ids no delivery outline, Tree, or Task references and without exclusion"],
  "excluded": ["catalogue ids carrying exclusion"],
  "unknown_refs": [{"delivery": "DELIVERY-PLATFORM", "task": null, "ref": "REQ-UNKNOWN"}]
}
```

`deliveries` lists every delivery that references the id, including through one of
its Tasks; `tasks` separately names those Task references. A requirement is
uncovered when no outline, Tree, or Task references it and it has no `exclusion`.

## Programme export

`programme export` is the single read-only projection for reports:

```json
{
  "schema": "better-plan.programme-export",
  "programme": {"the stored Programme object": "including goal and success"},
  "report": {"programme_report output including ready_to_design": "..."},
  "deliveries": {
    "DELIVERY-PLATFORM": {
      "kind": "tree",
      "tree": "platform/Tree.json",
      "export": {"tree": "...", "derived": "...", "checks": []}
    },
    "DELIVERY-ADAPTER-PACKAGES": {
      "kind": "planned",
      "outline": {"goal": "", "success": [], "requirements": [], "open_decisions": []}
    },
    "DELIVERY-BROKEN": {"kind": "error", "tree": "broken/Tree.json", "error": "message"}
  },
  "requirements": {"catalogue": [], "coverage": {}},
  "metrics": {
    "native_loc": [
      {
        "delivery": "DELIVERY-PLATFORM",
        "check": "CHECK-001",
        "owner": {"kind": "tree", "id": "TREE-001"},
        "value": 367511,
        "status": "passed"
      }
    ]
  }
}
```

One broken Tree appears as `kind` `error` and never fails the export. `owner` keeps
the flattened check's `{"kind", "id"}` shape. A check result that is a JSON object
containing `metrics` contributes one entry per metric name whose value is a number,
collected in programme order and then check order. Authors record metrics with a
check result:

```sh
python3 scripts/manifest_tool.py checks record <tree-root> CHECK-001 \
  --owner tree --result metrics.json
# metrics.json:
# {"status": "passed", "summary": "Measured", "metrics": {"native_loc": 367511}}
```

Archive programme conversation or the former Programme file with the same `history`
commands used by Tree workspaces. Programme history remains outside
`Programme.json` and is read only by explicit history queries.
