# Better Plan

Better Plan delivers one authorized outcome through a single **Checkpoints Tree**. Reach for it when
the work has several independently acceptable pieces, must survive a lost context, or touches state,
data, protocol, or release boundaries. For one small change you can understand and verify directly,
use your host's ordinary native workflow instead.

A delivery is one graph with a fixed outside and a free inside:

- exactly one `designer` Node with no `after` opens it;
- exactly one `reviewer` Node that nothing waits for closes it;
- worker Nodes fill the middle, on slots named `worker`, `worker-1`, `worker-2`, …

A Node is the executable unit. A Task only groups the Nodes of one delivery outcome.

## One source of truth

`Tree.json` is the delivery: Tasks, executable Nodes, `after` edges, execution state, evidence, and
history. There is no second ledger to keep honest, no rendered projection to parse back, and no
approval ceremony to replay. Task and Tree status are derived views computed from Node state.

Each Node declares:

| Field | Meaning |
| --- | --- |
| `outcome` | the one independently checkable result, written for an executor who never saw the original conversation |
| `role` | `designer`, `reviewer`, or a worker slot such as `worker` or `worker-1` |
| `executors` | an ordered list, best candidate first, of whatever your host can run — a provider and model pair, a named profile, an account |
| `resources` | what the Node contends on — a worktree, a build directory, a cache, an index, a port; shared resources without an ordering path are reported |
| `after` | the Nodes this one waits for; the only dependency edge, and it may cross Tasks |
| `contract.commands` | the commands that prove the outcome, when a machine can check it |

An empty `executors` list means "any executor". The tool keeps no registry and checks no quota; it
stores the order, records which candidate each attempt used, and names the next one, so a spent
account or an exhausted quota is one reported failure away from continuing.

Authoring is one batch per Task: `task.add` carries its Task's `nodes`, so a delivery is a handful of
operations instead of a generator script.

## Many deliveries

Several deliveries with an order between them share one `Programme.json` beside the Trees. It stores
identity, location, and `requires` edges — never status, which is always derived by reading the
Trees. `programme-status` reports each delivery's derived state, what may start now, and any resource
that parallel deliveries share without an order, so a contended worktree or build cache is a
reported fact rather than something a reviewer discovers at runtime. The index never gates a Node:
the Tree stays the only writer.

## Running it

```sh
python3 scripts/manifest_tool.py tree-init   <root> --title "<delivery>"
python3 scripts/manifest_tool.py tree-apply  <root> --input batch.json --dry-run
python3 scripts/manifest_tool.py tree-apply  <root> --input batch.json
python3 scripts/manifest_tool.py tree-next   <root> --explain
python3 scripts/manifest_tool.py tree-verify <root> NODE-002
python3 scripts/manifest_tool.py tree-transition <root> NODE-004 complete --note "audited"
python3 scripts/manifest_tool.py tree-status <root>
```

| Command | Contract |
| --- | --- |
| `tree-init` | create one empty Tree (`--id` defaults to `TREE-001`) |
| `tree-apply` | apply one atomic batch of Tasks and Nodes; `--dry-run` previews it without changing the Tree, `--input -` reads stdin, `--json` prints the receipt |
| `tree-next` | list ready Nodes with their role, the executor to try next, the fallback order behind it, and what is already spent; `--limit`, `--explain`, `--json` |
| `tree-transition` | apply one Node transition: `start`, `complete`, `fail`, `block`, `cancel`, `reset` |
| `tree-verify` | run a Node's declared commands and complete it on tool-produced evidence (`--executor`, `--cwd`, `--json`) |
| `tree-status` | show Tree state and which Nodes each role owns; lists reported completions separately |
| `tree-validate` | report data errors, then shape gaps, then resource contention (`--json` separates `issues` from `shape_issues` and reports `runnable`) |
| `tree` | render the Tree as text (`--details` adds executor, attempts, and evidence count; `--json` exports the Tree with derived state) |
| `programme-init` | create one empty programme index |
| `programme-apply` | apply one atomic batch of deliveries |
| `programme-status` | derive every delivery's state, readiness, and contention |
| `programme` / `programme-validate` | render and validate the index |
| `schema` | print a canonical shape (`tree`, `programme`); `--version` names the generation |

Authoring is free. A half-built Tree is valid data: write it through `tree-apply` batches in as many
passes as you like, and the shape is checked when work starts, not when it is written. One invalid
operation rejects the whole batch.

## Evidence, not assertions

- A Node that declares `contract.commands` is finished with `tree-verify`. It starts the Node when
  its dependencies are done, runs those commands itself, and records the receipts it observed
  (`source: cli`). Completing such a Node by hand is refused — the tool never records a check it did
  not run.
- A Node with no commands is judged work. `tree-transition … complete --note "<what you did>"`
  records who reported it, and `tree-status` lists those completions separately so the two kinds of
  green never look alike.
- Long work never holds the workspace lock: `tree-verify` runs the commands outside it, then re-reads
  the Tree and refuses to complete a Node that moved while they ran.
- Reject malformed data instead of guessing: unknown fields, unknown roles, cycles, and dangling
  `after` references all fail closed. Every write is atomic.
- Keep secrets, tokens, machine identity, absolute local paths, runtime endpoints, and backend data
  out of state, notes, evidence, and reports. The tool enforces that guard on everything it records;
  `contract` and `meta` stay opaque project data the tool never reads.

## Roles and references

Hand each executor only what its role needs:

- **Designer:** `references/designer.md` before authoring.
- **Worker:** `references/worker.md` before executing a Node.
- **Reviewer:** `references/reviewer.md` before auditing.

`references/checkpoints-tree.md` is the authoritative Tree contract: shapes, rules, authoring
operations, transitions, and every command's output. `references/programme.md` owns the
many-delivery index. `references/design-principles.md` is the rationale behind the design and the
test any change to it must pass. `references/host-configuration.md` owns the per-host role matrix
and installation rules.

## Installation

Better Plan supports five hosts. Codex is the only one with packaged role presets; every other host
installs unpinned roles and inherits its model and reasoning effort from the host and the user's own
configuration.

| Target | What is installed |
| --- | --- |
| `codex` | the shared skill, three role files in `$CODEX_HOME/agents`, and one receipt |
| `claude` | a plugin (`.claude-plugin/plugin.json` plus the skill payload) and three role files in `~/.claude/agents` |
| `cursor` | the shared skill and three role files in `~/.cursor/agents` |
| `kilo` | the skill, one `better-plan` primary Agent, three namespaced Subagents, and one receipt |
| `dsh` | the shared skill only; roles are prompts that inherit the harness model |

```sh
python3 scripts/install.py install   --agents codex
python3 scripts/install.py update    --agents codex
python3 scripts/install.py doctor    --agents codex
python3 scripts/install.py uninstall --agents codex
```

`--agents` accepts `all`, `codex`, `claude`, `cursor`, `kilo`, and `dsh`; `install`, `update`, and
`uninstall` also accept `--dry-run`. `uninstall` removes Better Plan's skills, plugin, and adapters
while preserving every native role file and receipt; add `--remove-shared` to remove the shared scan
skill as well.

Installation is additive. Better Plan creates a role matrix only when no same-name role
configuration or receipt exists, and from then on every role file and receipt is immutable — across
install, update, uninstall, and Doctor. A receipt mismatch is reported as a warning, never repaired
and never re-signed. Doctor verifies structure and source equality separately, and additionally
reports each host's own checks (the Claude plugin manifest, the Cursor and Kilo CLIs when present).

Codex pins its three packaged presets once, at first installation, and no later update rewrites
them: `designer` `gpt-6-astra / max`, `worker` `gpt-6-luna / max`, and `reviewer`
`gpt-6-astra / xhigh`. Each pin is evaluated on one standard basis — the Intelligence Index row for
the model and effort it selects — and the receipt records that row's score and published task cost.

## Development

Python 3.8 or newer is the supported runtime range.

Run focused tests while changing one invariant; after all changes are integrated, run the complete
suite once through the process-isolated parallel scheduler:

```sh
python3 scripts/run_tests.py
python3 scripts/run_tests.py --shard core
```

The scheduler partitions tests by architecture boundary (`core`, `hosts`, `installation`, `tooling`)
and runs all shards concurrently. Every `tests/test_*.py` module must belong to exactly one shard.

The Better Plan source repository uses its ordinary native development workflow and never requires a
repository-local Better Plan workspace for self-maintenance.

## Repository layout

```text
SKILL.md                     the operational entry contract
references/                  the Tree contract, design rationale, role briefs, host rules
agents/                      packaged host role templates (codex, claude-code, cursor, kilo)
scripts/manifest_tool.py     the Tree CLI entrypoint
scripts/install.py           the installer entrypoint
scripts/better_plan/         domain, application, infrastructure, adapters, installation
tests/                       the suite, sharded by architecture boundary
```
