---
name: better-plan
description: One-graph delivery planning for large refactors, migrations, and high-risk changes. A single Tree.json holds every Task, executable Node, dependency, executor chain, transition, and evidence record; one designer opens the graph, workers fill it, one reviewer closes it.
---

# Better Plan

Deliver one authorized outcome through a single Checkpoints Tree. Use the native
workflow for one small change you can understand and verify directly; reach for
Better Plan when the work has several independently acceptable pieces, needs to
survive a lost context, or touches state, data, protocol, or release boundaries.

Maintaining the Better Plan source repository itself uses the ordinary native
repository workflow. Do not create a repository-local Better Plan workspace merely to
edit this package.

## The graph

A delivery is one graph with a fixed outside and a free inside:

- exactly one `designer` Node with no `after` opens it;
- exactly one `reviewer` Node that nothing waits for closes it;
- worker Nodes fill the middle, on slots named `worker`, `worker-1`, `worker-2`, …

Authoring is free. Write one `Tree.json` with `tree-init`, then add Tasks and Nodes
through `tree-apply` batches in as many passes as you like. The shape is checked when
work starts, not when it is written, so a half-built graph is normal data.

Every Node names its role and, optionally, what may run it and what it contends on:

- `role` — `designer`, `reviewer`, or a worker slot. A slot is a name, not a person.
- `executors` — an ordered list, best candidate first, of whatever the host can run:
  a provider and model pair, a named profile, an account. The order is the fallback
  order. The tool keeps no registry and checks no quota; it records which candidate
  each attempt used and names the next one. An empty list means any executor.
- `resources` — what the Node contends on: a worktree, a build directory, a cache, an
  index, a port, a device. Two Nodes that share one without an ordering path between
  them are reported, because parallel units that collide on a machine resource were
  never ordered in the design.
- `contract.commands` — the commands that prove the outcome, when a machine can check
  it. Omit them when only a person can judge the result.

Authoring is one batch per Task: `task.add` takes the Task's `nodes` with it, so a whole
delivery is a handful of operations rather than a generator script.

## Many deliveries

When the work is several deliveries with an order between them, keep the order in one
`Programme.json` beside the Trees. It stores identity, location, and `requires` edges —
never status, which is always derived by reading the Trees. `programme-status` reports
each delivery's derived state, what is runnable now, and any resource that parallel
deliveries share without an order. The index never gates a Node: it answers what may
start, and the Tree stays the only writer.

```sh
python3 scripts/manifest_tool.py programme-init <root> --title "<programme>"
python3 scripts/manifest_tool.py programme-apply <root> --input deliveries.json
python3 scripts/manifest_tool.py programme-status <root> --json
```

## Running it

```sh
python3 scripts/manifest_tool.py tree-init <root> --title "<delivery>"
python3 scripts/manifest_tool.py tree-apply <root> --input batch.json --dry-run
python3 scripts/manifest_tool.py tree-apply <root> --input batch.json
python3 scripts/manifest_tool.py tree-next <root> --explain
python3 scripts/manifest_tool.py tree-verify <root> NODE-002
python3 scripts/manifest_tool.py tree-transition <root> NODE-004 complete --note "audited"
python3 scripts/manifest_tool.py tree-status <root>
```

`tree-next` reports every ready Node with its role, the executor to try next, the
fallback order behind it, and what has already been spent.

A Node that declares `contract.commands` is finished with `tree-verify`. It starts
the Node when its dependencies are done, runs those commands itself, and records the
receipts it observed. Completing such a Node by hand is refused: the tool must never
record a check it did not run. A Node with no commands is judged work, and
`tree-transition … complete` records who reported it.

When a Node fails, report it with the executor that failed:
`tree-transition <node> fail --executor "<who>" --note "<why>"`. The tool names the
next candidate in that Node's chain — a spent account is one retry away from
continuing, not a dead end. Appending another fallback to a Node that already started
needs no reset; replacing the chain, like any other definition change, requires
`reset: true`.

Long work never holds the workspace lock: `tree-verify` runs commands outside it and
re-reads the Tree afterwards, refusing to complete a Node that moved while they ran.

## Load context by role

Hand each executor only what its role needs, and keep interim transcripts out of the
dispatch:

- **Designer:** `references/designer.md` before authoring.
- **Worker:** `references/worker.md` before executing a Node.
- **Reviewer:** `references/reviewer.md` before auditing.

`references/checkpoints-tree.md` is the authoritative Tree contract: shapes, rules,
authoring operations, transitions, and every command's output.
`references/programme.md` owns the many-delivery index: its shape, operations, derived
status, and contention. `references/design-principles.md` is the rationale behind the
design and the test any change to it must pass. `references/host-configuration.md` owns
the per-host role matrix and installation rules.

## Guardrails

- One writer per truth: `Tree.json` is the delivery. A `Programme.json` holds order
  only — never status — and nothing else may keep a second ledger beside a Tree.
  Never parse a rendered view back into state.
- Evidence comes from the tool, not from the executor's word. A completion recorded
  as `reported` is displayed as reported, never as verified.
- Keep secrets, tokens, machine identity, absolute local paths, runtime endpoints,
  and backend data out of state, notes, evidence, and reports.
- Treat existing native role files and receipts as immutable host configuration.
  Create a role matrix only when no same-name configuration exists; report drift,
  never repair or re-sign it.
- Reject malformed data instead of guessing: unknown fields, unknown roles, cycles,
  and dangling `after` references fail closed.
- Re-author in place with `tree-init --replace --reason "<why>"`. Never delete
  `Tree.json`: the replacement keeps the identity and the whole history.

## Commands

Use `scripts/manifest_tool.py`:

| Command | Contract |
| --- | --- |
| `tree-init` | create one empty Tree; `--replace --reason` re-authors an existing one |
| `tree-apply` | apply one atomic batch of Tasks and Nodes (`--dry-run` previews) |
| `tree-next` | list ready Nodes with their role, executors, and blockers |
| `tree-transition` | apply one Node transition: start, complete, fail, block, cancel, reset |
| `tree-verify` | run a Node's declared commands and complete it on tool-produced evidence |
| `tree-status` | show Tree state and which Nodes each role owns |
| `tree-validate` | report data errors, then shape gaps, then resource contention |
| `tree` | render the Tree as text, or export it with derived state (`--json`) |
| `programme-init` | create one empty programme index |
| `programme-apply` | apply one atomic batch of deliveries (`--dry-run` previews) |
| `programme-status` | derive every delivery's state, readiness, and contention |
| `programme-validate` | validate the index and report contention |
| `programme` | render the index as text |
| `schema` | print a canonical shape (`tree`, `programme`) |
| `--version` | name the installed generation |

Install and inspect the host integration with `scripts/install.py`
(`--agents codex claude cursor kilo dsh`, plus `install`, `update`, `doctor`, and
`uninstall`).

## Failure surface

`tree-validate --json` separates `issues` (invalid data) from `shape_issues` (not
runnable yet) and reports `runnable`. `tree-next` prints what the shape is still
missing instead of offering work that cannot start. A Node whose declared executors
are all spent is reported as such rather than silently retried.
