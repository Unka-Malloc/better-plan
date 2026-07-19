# Architecture

## Package and dependency direction

```text
scripts/manifest_tool.py ─┐
scripts/hook_tool.py ─────┼─> adapters ─> application ─> domain
scripts/install.py ───────┘       │             │
                                  └─────────────> infrastructure
```

Domain modules never import application, infrastructure, adapters, subprocess, or
filesystem code. Infrastructure implements state and regression ports. Adapters own
argument parsing and host payload translation. Application services coordinate use
cases and depend on injected ports or narrow infrastructure interfaces.

## Files and symbols

- `scripts/better_plan/domain/models.py`
  - typed workflow constants, `Issue`, `WorkflowStateMachine`, receipt/dispatch value
    objects, and repository-relative path validation.
- `scripts/better_plan/domain/transitions.py`
  - pure acceptance transition and next-action tables.
- `scripts/better_plan/domain/design.py`
  - pure design-contract normalization, digest, and ownership checks.
- `scripts/better_plan/domain/validation.py`
  - pure Plan/Node/schema/graph/traceability validation.
- `scripts/better_plan/infrastructure/workspace.py`
  - discovery, JSON state loading/atomic writes, `NodeLocation`, source checks, and
    Plan-status synchronization.
- `scripts/better_plan/infrastructure/regression.py`
  - command execution, content fingerprints, bounded receipts, and output discard.
- `scripts/better_plan/application/workflow.py`
  - current Node use cases, preparation invalidation, dispatch/advance/repair, and
    acceptance completion.
- `scripts/better_plan/application/agent_completion.py`
  - deterministic reduction after the native host reports a correlated Agent completion.
- `scripts/better_plan/adapters/manifest_cli.py`
  - command handlers, parser construction, schema/status/reporting adapters.
- `scripts/better_plan/hooks/{scope,context,config,runtime}.py`
  - structural activation, bounded context, managed configuration, and lifecycle
    payload translation.
- `scripts/better_plan/installation/{models,skills,targets,doctor,service}.py`
  - installation data, skill trees, platform adapters, verification, and orchestration.
- `scripts/better_plan/adapters/install_cli.py`
  - installer parser and command entry.

## Entrypoints

`scripts/manifest_tool.py`, `scripts/install.py`, and `scripts/hook_tool.py` insert the
repository root deterministically and call exactly one package adapter `main`. They
contain no business logic and no fallback import ladder.

## Interfaces and errors

- Domain validators return deterministic issue values and never read files.
- Workspace infrastructure is the only owner of state-file writes.
- Regression infrastructure returns bounded success/failure classifications and never
  persists command output.
- Application workflow raises one safe workflow error type at adapter boundaries.
- Agent-completion reduction receives only the current workflow state after the host
  reports that a correlated Agent returned; it never supervises Agent lifetime.

## Algorithms and data structures

- Transition selection remains constant-time immutable mapping lookup.
- Graph validation remains adjacency-list traversal, `O(nodes + edges)`.
- Fingerprints stream declared files in deterministic path order, `O(bytes)` with
  constant additional memory per file.
- Agent-completion routing uses bounded role/state lookup and current workflow data.
- Installation inventories use immutable tuples and sets for membership/deduplication.

## State, cache, isolation, and concurrency

- JSON files remain the single persisted state owner and are replaced atomically.
- No cross-run cache is introduced; digests are recomputed from declared artifacts.
- Acceptance, executor, and auditor file ownership remains disjoint.
- Plan writes and installer target writes remain serialized; subprocess execution is
  bounded and output is discarded or reduced before state mutation.
