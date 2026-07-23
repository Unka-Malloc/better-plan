# Planning Reachability Architecture

## State semantics

`deferred` is a non-terminal administrative state. `defer` may park a pending, in-progress, or
blocked Node after clearing stale dispatch and proof state. `activate` is its sole executable return
edge and moves it to `pending`; ordinary start and dispatch reject deferred Nodes. `status` reports
deferred goal/reason entries, while `next` continues to expose only explicitly executable work.

`skipped` remains terminal and means the obligation was waived or declared not applicable. It is
never described as future work. Because deferred implementations are non-terminal, existing
completion and final-validation gates naturally retain them as outstanding obligations.

## Dependency graph

Node UUIDs are already globally unique within a workspace. `prerequisites` therefore accepts any
Node UUID referenced by the workspace, regardless of Plan or checkpoint-array position. The
workspace layer loads each referenced checkpoint file once into:

- an ID-to-node record map containing status, path, index, and prerequisite IDs;
- one adjacency map from Node to prerequisite;
- one reverse adjacency map from prerequisite to dependent.

`status_reason` and `next` remain non-authoritative metadata. Documentation explicitly requires
every Node wait to use `prerequisites`.

## Files and interfaces

- `scripts/better_plan/domain/models.py`
  - adds `deferred` and its legal transitions;
  - keeps `completed` and `skipped` as the only terminal statuses;
  - derives Plan state without treating deferred work as complete.
- `scripts/better_plan/domain/validation.py`
  - provides an iterative linear-time cycle-path finder over an arbitrary dependency graph;
  - leaves reference resolution to the workspace boundary.
- `scripts/better_plan/infrastructure/workspace.py`
  - builds the global Node snapshot;
  - validates references, active/completed prerequisite guards, skipped propagation, and cycles;
  - validates an in-memory mutation snapshot before atomic writes.
- `scripts/better_plan/application/workflow.py`
  - adds defer/activate administrative transitions;
  - consults global prerequisite status before start or dispatch.
- `scripts/better_plan/adapters/manifest_cli.py`
  - exposes `defer` and `activate`;
  - reports deferred backlog entries and uses global prerequisite status for `next`;
  - invokes workspace dependency validation for full and Plan-scoped validation.
- `SKILL.md`, `README.md`, and the two state/orchestration references
  - map native-main defer decisions to `deferred`;
  - reserve `skipped` for explicit waiver;
  - require all Node waits to be structured prerequisites.

## Algorithms and data structures

Cycle detection uses an iterative three-color depth-first traversal. The active stack stores each
Node's current prerequisite offset and an index map into the active path. Encountering a gray Node
returns the exact closed cycle path. Each Node and edge is processed at most once, for `O(V + E)`
time and `O(V)` traversal memory, without recursion depth risk.

Skipped-prerequisite unstartability propagates once through reverse adjacency with a deque, also
`O(V + E)`. Eligibility then performs constant-time status lookups per edge from the shared global
index instead of repeatedly scanning checkpoint arrays.

## State, isolation, and failure handling

- All graph construction and validation is read-only until the proposed checkpoint snapshot passes.
- Rejected mutations write neither the checkpoint file nor the Manifest.
- Plan-scoped validation loads the global index but reports dependency problems only in the selected
  Plan's transitive prerequisite closure, so unrelated sibling debt remains isolated.
- The implementation adds no polling, queue, cache persistence, model launcher, compatibility alias,
  or backend data capture.

## Non-goals

- Automatically selecting deferred work.
- Inferring Node dependencies from prose, goals, `next`, or Plan hierarchy.
- Reopening completed or skipped history.
- Treating Plan nesting as an implicit dependency.
