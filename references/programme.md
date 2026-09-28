# Programme contract

A Programme orders several delivery Trees without copying their execution state.

```json
{
  "schema": "better-plan.programme",
  "id": "PROGRAMME-001",
  "title": "Delivery programme",
  "deliveries": [
    {
      "id": "M10",
      "title": "Platform",
      "tree": "10-platform/Tree.json",
      "requires": []
    },
    {
      "id": "M11",
      "title": "Client",
      "tree": "11-client/Tree.json",
      "requires": ["M10"]
    }
  ]
}
```

The file stores identity, workspace-relative Tree paths, and delivery dependency
edges. It has no revision, history, status, counts, evidence, or copied Node data.
`programme status` locks and reads each split Tree workspace, derives its current
state, and reports ready deliveries. A missing Tree is reported as `missing`.
`state` is the Tree delivery status: `unrecorded`, `recorded`, or `needs_review`.
`execution_status` reports Node progress separately. A `requires` dependency is
satisfied only by a currently `recorded` Tree delivery, including recorded Task
deliveries. Node completion alone cannot unblock another delivery. A relevant change
can make a previously recorded dependency need review without erasing its result.
Readiness is advisory; it does not dispatch work or enforce an approval gate.

```sh
python3 scripts/manifest_tool.py programme init <root> --title "Programme"
python3 scripts/manifest_tool.py programme update <root> --input update.json
python3 scripts/manifest_tool.py programme show <root>
python3 scripts/manifest_tool.py programme status <root> --json
```

`programme update` accepts direct current-field updates. It also accepts an
`operations` array with `add`, `update`, and `remove` delivery operations. Removing a
delivery removes its id from other `requires` lists. Unknown metadata is preserved.
There is no separate validation or approval command.

Archive programme conversation or the former Programme file with the same `history`
commands used by Tree workspaces. Programme history remains outside
`Programme.json` and is read only by explicit history queries.
