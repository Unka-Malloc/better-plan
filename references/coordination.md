# Multi-plan coordination

The coordinator connects explicitly selected source-owned plans to an asynchronous execution
host. A repository can have one mainline and any number of collaboration lanes. Each lane owns
its execution and acceptance; observing an upstream never authorizes changing that upstream.
Source plans remain authoritative. A v3 Task is the executable unit and its static Node DAG stays
inside that Task. Whole-Plan review, full regression, and closure remain native workflow steps.

## Configuration

All semantic paths are relative to `--root`. `Coordination.json` selects lanes, cross-plan input
requirements, concurrency, and an optional execution adapter:

```json
{
  "schema": "better-plan.coordination/v1",
  "namespace": "delivery",
  "portfolio": "planning/portfolio.json",
  "max_parallel": 3,
  "lanes": [
    {"id": "protocol-main", "kind": "mainline", "repository": "Protocol", "source": "protocol"},
    {"id": "client-main", "kind": "mainline", "repository": "Client", "source": "client"},
    {"id": "integration", "kind": "collaboration", "repository": "Client", "source": "integration"}
  ],
  "requires": [
    {"consumer": "integration/TASK-001", "provider": "protocol/TASK-002", "binding": "EXACT-BINDING-FROM-STATUS"}
  ],
  "host": {
    "kind": "command",
    "command": ["python3", "tools/execution_adapter.py"],
    "profiles": {"worker-standard": "implementation", "worker-complex": "complex-implementation"}
  }
}
```

The adapter command above is an example, not a bundled execution service. Supply an adapter for
the host you operate. `profiles` maps native Worker roles to that host's profile identifiers; the
adapter must honor the selected role, model, and execution policy. For a source without a native
role, set `host.lanes`, for example `{"client-main": "worker-complex"}`. This does not override a
native role. Optional `constraints` contains privacy-safe instructions passed to every Worker.
Omit `host` to inspect sources without enabling execution.

The portfolio explicitly selects current sources; it does not discover old or unapproved plans:

```json
{
  "schema": "better-plan.coordination-portfolio/v1",
  "sources": [
    {"id": "protocol", "kind": "better-plan-v3", "path": "Protocol/docs/plans/main/Plan.json"},
    {"id": "client", "kind": "better-plan-v3", "path": "Client/docs/plans/main/Plan.json"},
    {"id": "integration", "kind": "better-plan-v3", "path": "Client/docs/plans/integration/Plan.json"}
  ]
}
```

`better-plan-v3` uses the selected sealed Plan, its Checkpoints, Manifest, and native public CLI.
`execution-graph-v7` uses a selected `graph/project.json`, producer-generated work items, a
`state` path to the native SQLite ledger, and the source's `tools/planctl.py`. Its existing claim,
heartbeat, and evidence acceptance operations retain ownership. Neither adapter fabricates
progress from worker messages.

An external requirement is satisfied only by an accepted provider with the declared exact binding.
Read bindings from `status`. Optional `materialized: [{"path": "Client/vendor/schema.json",
"sha256": "EXPECTED-DIGEST"}]` additionally verifies a consumed local artifact; omit this when only
source acceptance matters. Changed or unknown upstream state holds its consumers while unrelated
lanes continue. Native prerequisites and external requirements form one checked DAG. Write scopes
and exclusive resources constrain concurrency across all lanes.

## Execution adapter contract

The configured command is invoked from the workspace root with its argument array, without shell
interpolation. Each invocation reads one JSON object from stdin and returns one JSON object on
stdout with exit code zero. Runtime diagnostics stay private; the coordinator does not forward
stdout or stderr to users. Adapter calls have no imposed execution timeout.

Start request:

```json
{
  "schema": "better-plan.coordination-host/v1",
  "action": "start",
  "operation_id": "coord-opaque-operation-id",
  "key": "client/TASK-001",
  "repository": "Client",
  "profile": "implementation",
  "brief": {"agent_type": "worker-standard", "assignment": "...", "brief": {}}
}
```

Return `{"host_id": "opaque-worker-id"}` after durably submitting asynchronous work. Persist the
`operation_id` correlation before responding: repeated start calls, including after a process
restart or lost response, must recover the same job. Distinct operations can arrive concurrently.
Preserve the supplied brief and repository boundary. A command that waits for the entire Worker
to finish does not satisfy this asynchronous submission contract.

Inspect request is `{"schema": "better-plan.coordination-host/v1", "action": "inspect",
"host_id": "opaque-worker-id"}`. Return `{"state": "running"}` or one of `pending`, `succeeded`,
`failed`, and `unknown`. Successful v7 handoff also returns `evidence`, a repository-relative path
to its native evidence manifest. Identifiers must be opaque, not local paths or endpoints.
Return only the state and evidence path; no execution logs, credentials, or private claim tokens.

The coordinator advances native dispatch, binds the returned host identity, observes the job,
then calls the source's native acceptance operation. `succeeded` is a handoff, not acceptance.
Only native acceptance releases dependents. Python callers may inject an object implementing
`start(operation_id, key, brief, repository) -> host_id` and `inspect(host_id) -> state` directly.

## Authorization and operation

The user's implementation instruction supplies authority. `grant` records that authority for
exact units and the current policy; it does not invent permission or require another approval.

```sh
python3 scripts/coordination_tool.py status --root WORKSPACE \
  --config planning/Coordination.json --state PRIVATE/Coordinator.json
python3 scripts/coordination_tool.py grant --root WORKSPACE \
  --config planning/Coordination.json --state PRIVATE/Coordinator.json \
  --lane integration --reference "User authorized this integration delivery"
python3 scripts/coordination_tool.py watch --root WORKSPACE \
  --config planning/Coordination.json --state PRIVATE/Coordinator.json --interval 60
```

Use repeatable `--unit source/TASK-ID` or `--lane` to select units for `grant`, `revoke`, and
`reconcile`. `status` is read-only. `tick` advances once; `watch` observes at a cadence and reports
changed results. Its interval is never a Worker deadline. `wake` notifies an existing observer to
re-read current facts; it carries no execution authority.

`pause` stops new starts while maintaining existing work. `resume` permits still-valid grants;
`revoke` removes selected grants. Stopping observation does not terminate workers. Before changing
execution routing, settle existing jobs through their owning host, update configuration, and
record authorization for the changed policy. Keep the same private journal for recovery.

The journal stores authorization bindings and dispatch correlations, including private source
claim receipts where required. Keep it outside tracked or shared artifacts. Unknown host/source
state and invalidated inputs retain ownership and require reconciliation, rather than triggering
duplicate execution or releasing resources. Failed native acceptance is reported for correction;
the coordinator does not automatically rerun a repair loop. `reconcile` rechecks the existing
operation after its cause has been resolved, without inventing a new job.
