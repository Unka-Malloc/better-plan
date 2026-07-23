# Better Plan State Files Reference

This file documents the semantics of the two Better Plan state files. The canonical shapes, enums, and templates are printed by the manifest tool and take precedence over any prose copy:

```sh
python3 scripts/manifest_tool.py schema plan
python3 scripts/manifest_tool.py schema node
```

Contents: [Workspace Structure](#workspace-structure), [Plan Fields](#plan-fields), [Node Fields](#node-fields), [Status Machine Reference](#status-machine-reference), and [Manifest Tool Commands](#manifest-tool-commands).

## Workspace Structure

- The workspace root `Manifest.json` is a flat JSON array of Plan objects. It never contains Node objects.
- Each plan owns one directory under the workspace root and one `Checkpoints.json` inside that directory, a JSON array of Node objects.
- Hierarchy is expressed only through relative paths: a child plan's `directory` nests under its parent plan's `directory`. The manifest array itself stays flat.
- The plan directory tree grows from the top down: upper directories hold foundation plans, deeper directories hold progressively more specific branches, and leaf directories hold concrete delivery branches such as one platform target, one business line, or one integration. Platform adaptation is the canonical example: a platform-neutral parent plan such as `core` with one child plan per target, such as `core/macos` and `core/windows`.

## Plan Fields

- `id`: UUID4 plan ID. Generate with `scripts/manifest_tool.py uuid`.
- `status`: one of `pending`, `in_progress`, `blocked`, `completed`, `skipped`.
- `title`: concise human-readable plan name.
- `directory`: relative path from the workspace root to the plan's dedicated directory. May contain nested segments when the plan is a child of another plan.
- `source_files`: list of source plan files from Step 1. Use an empty list only when the plan came directly from the user request and has no source file yet. Write local entries relative to the project root (the nearest ancestor of the workspace with `.git`); external references use `owner/repo:path` or a URL. `validate --check-sources` verifies that local entries still resolve, so stale paths surface instead of rotting.
- `goal`: brief plan goal.
- `description`: lightweight plan summary only. Keep it short enough to identify the plan's scope, boundary, parent or child relationship when relevant, and important constraints. Do not put detailed design, architecture, dependency trees, task sequencing, implementation notes, risks, or acceptance logic here; move those details into the selected plan's `Checkpoints.json` Nodes.
- `checkpoints`: relative path to the plan's checkpoint file. Must be exactly `<directory>/Checkpoints.json`.

Hierarchical example:

```json
[
  {
    "id": "01234567-89ab-4def-8123-456789abcdef",
    "status": "pending",
    "title": "Common",
    "directory": "common",
    "source_files": ["docs/common-plan.md"],
    "goal": "Build the shared foundation required by the business-line plans.",
    "description": "Common base capability that child plans depend on.",
    "checkpoints": "common/Checkpoints.json"
  },
  {
    "id": "89abcdef-0123-4567-89ab-cdef01234567",
    "status": "pending",
    "title": "A",
    "directory": "common/a",
    "source_files": ["docs/a-plan.md"],
    "goal": "Deliver business-line A on top of the common foundation.",
    "description": "Child plan under Common because it depends on the shared foundation.",
    "checkpoints": "common/a/Checkpoints.json"
  }
]
```

## Node Fields

Required fields:

- `id`: UUID4 task ID. Generate with `scripts/manifest_tool.py uuid`.
- `status`: one of `pending`, `in_progress`, `blocked`, `completed`, `skipped`.
- `role`: one of `product_requirements`, `evidence`, `validation_matrix`, `architecture_scaffold`, `implementation`, `final_validation`. Roles let the validator enforce delivery order and role difficulty floors. The `architecture_scaffold` Node fixes the module and file decomposition, layer boundaries, dependency direction, interface contracts, and deliberate design-pattern choices in `Architecture.md` before implementation Nodes start.
- `prerequisites`: list of earlier Node IDs that must be `completed` before this task can run. Each ID must appear earlier in the array.
- `platform`: `any`, `linux`, `macos`, or `windows`. Use `any` unless the task genuinely requires one operating system. `platform` prints the normalized runtime, and delivery dispatch rejects a different non-`any` value before creating work. Platform-specific Nodes belong in that platform's child plan with `platform` set to the target; the platform-neutral foundation plan keeps its Nodes at `any`.
- `difficulty`: `low`, `medium`, `high`, or `deep`; only run the task when the agent can use that level or higher. The validator requires `high` or `deep` for `product_requirements`, `evidence`, `validation_matrix`, `architecture_scaffold`, and `final_validation`. The workflow additionally requires `deep` for new product or feature foundation work unless Step 1 verified the corresponding artifact is already complete.
- `goal`: brief task goal tied to product delivery, not only file edits.
- `description`: structured task design brief. Do not target a fixed sentence count and do not write free-form filler. Populate the following sections in order inside the string, using clear labels or compact labeled clauses when that keeps JSON readable:
  - `Scope`: name the concrete artifacts touched or inspected, such as code files, tests, scripts, configs, generated artifacts, documentation pages, or plan files. Also name the conceptual surface, such as modules, packages, components, commands, APIs, protocols, data models, feature areas, user-visible behaviors, or project capabilities. Include the Node's dependency-tree position when useful: its parent foundation or contract, its current level responsibility, and the child branches or consumers it unlocks. When exact files are not yet known, provide search targets such as symbols, routes, CLI flags, doc headings, config keys, schemas, or error strings. Begin every implementation Node with exactly one independently acceptable closure declaration: `Closure: capability - <target>`, `Closure: module - <target>`, or `Closure: scenario - <target>`. Name only the modules, directories, and files necessary for that closure, aligned with the `Architecture.md` module map, plus the interfaces consumed from other modules. Split distinct closures into separate Nodes so Nodes without a prerequisite path stay on disjoint files and can run in parallel.
  - `Context`: summarize the current behavior, project state, prior decision, or source-plan requirement that makes this task necessary. Ground this in Step 1 evidence instead of generic intent.
  - `Target`: describe the intended final behavior or design state for this Node only, including referenced requirement labels and evidence links when known. Keep ordering out of this section because `prerequisites` and `next` own execution order, and keep concrete completion checks out because `acceptance_criteria` owns verification. An implementation Node without `requirements` labels must describe here why it is enabling work for a later requirement.
  - `Design Considerations`: when relevant, identify existing architectural or design patterns to follow, abstractions to reuse or avoid, data structures, state shapes, schemas, storage formats, algorithms, control flow, ordering semantics, complexity, concurrency, caching, parsing, error handling, or ownership and API boundary concerns.
  - `Design Value`: explain why any material design choice is worth doing. A pattern, abstraction, data structure, algorithm, or architecture change is justified only when it reduces real complexity or duplication, preserves a domain invariant, clarifies ownership or API boundaries, improves correctness, testability, performance, scalability, observability, or failure handling, or aligns with an established project pattern. Prefer the project's existing patterns and the simplest local change unless this value test justifies a stronger design.
  - `Constraints & Risks`: capture invariants, non-goals, compatibility/removal expectations, dependencies, assumptions, unresolved questions, and implementation risks that the executor must keep in mind. Explicitly identify applicable privacy or backend-data restrictions, algorithm or data-structure evidence and performance targets, complete-refactor removal obligations, and the boundary that prevents the Node from expanding into another closure.
  - Omit a section only when it truly does not apply to the Node. If the source plan or inspected code does not justify a detail, state the uncertainty explicitly instead of inventing requirements.
- `acceptance_criteria`: non-empty list of criterion objects (see below).
- `commit`: expected commit or delivery information (see below).
- `next`: list of Node UUIDs that become natural follow-up candidates after this task. Use an empty list only when no follow-up Node exists.

Optional fields:

- `requirements`: list of requirement labels such as `REQ-001` that this Node delivers or proves. Labels must begin with `REQ` and contain one or more hyphen-delimited alphanumeric segments (`REQ-001` and `REQ-CLIENT-001` are valid; `CLIENT-REQ-001` is not). Prefer Plan-local `REQ-###` labels because the Plan boundary already supplies the namespace. Implementation Nodes must list at least one canonical label or describe enabling work in `description`. Final-validation Nodes must list the canonical labels they prove; the validator requires them to cover every label carried by non-skipped implementation Nodes. `check-labels` cross-checks these labels against the labels written in the plan directory's markdown documents and rejects noncanonical labels instead of silently dropping them.
- `status_reason`: why the Node is `blocked`, `skipped`, or paused back to `pending`, and what would unblock, revive, or resume it. The `block` and `skip` commands require it; `pause` records it when given; other transitions clear it.
- `acceptance` (tool-written for delivery Nodes): the deterministic acceptance snapshot. `phase` is one of `awaiting_acceptance_design`, `acceptance_designer_running`, `acceptance_revision_required`, `awaiting_executor`, `executor_running`, `correction_required`, `awaiting_regression`, `awaiting_auditor`, `auditor_running`, `repair_plan_required`, `awaiting_repair`, or `accepted`; `attempt` is a non-negative counter; `outcome` is bounded state-machine data. An unenrolled Node begins at `awaiting_acceptance_design`. The acceptance designer freezes the contract once and routes directly to execution or final regression. Preparation drift parks the same Node at `acceptance_revision_required` with `main_acceptance_decision`; an explicit designer dispatch may revise that Node, but no leaf is selected automatically. A running dispatch contains only an opaque `id`, its role, and the bounded fingerprints required by that role. Final repair handoff may contain a `repair_node_id`; accepted state contains bounded audit fingerprint metadata. Never hand-edit this object.
- `regression`: executable validation contract required before an `implementation` or `final_validation` Node can start. It contains:
  - `scope`: `focused` for `implementation`, `full` for `final_validation`.
  - `commands`: non-empty unique command strings executed sequentially from the project root. Every command must exit 0. Standard output and error are discarded rather than persisted or echoed.
  - `criteria`: non-empty unique zero-based indexes of the acceptance criteria proved by the complete command set. A passing run checks only these criteria.
  - `paths`: non-empty unique repository-relative files or directories fingerprinted immediately before and after execution. Paths must exist, stay inside the project, avoid symbolic links and mutable Better Plan state files, and not overlap one another.
  - `last_pass` (tool-written): `{recorded_at, contract_digest, content_fingerprint}`. Editing the contract or declared content makes the receipt stale. Do not hand-write receipts.

Acceptance criterion object:

- `checked`: boolean. Delivery criteria are checked together only by a fingerprint-bound `audit-passed` transition after regression succeeds; a foundation Node may still record its own evidence before its non-delivery completion transition.
- `text`: non-empty description of a concrete check that proves the task is complete. Reference requirement labels, evidence artifacts, tests, verifiers, or generated-artifact checks. Every implementation Node includes the smallest focused check for its declared closure. Add conditional criteria for redacted backend or sensitive evidence, open-source comparison and performance decisions for algorithm or data-structure work, and a purpose-built one-time removal check for refactors. Only final-validation Nodes may require the complete regression suite.
- `evidence` (optional): minimal redacted, single-line summary of what verification proved this criterion, recorded by `check --evidence`. The validator rejects concrete paths, network endpoints, server identifiers, secret-shaped assignments, credentials, and backend runtime output.
- `evidence_refs` (optional): machine-verifiable evidence records written by `check --evidence-file` and `check --evidence-cmd`. A file reference records `{type, path, sha256, recorded_at}`, where `path` is confined to the repository and persisted relative to its root. A command reference records `{type, command_sha256, exit_code, recorded_at}` and may only exist for a passing run (`exit_code` 0). Command text, standard output, and standard error are never persisted.

Commit object:

- `repository`: the target Git repository's `.git` entry.
- `message`: suggested commit message.
- `target`: where the work should be committed or delivered.
- `delivered` (optional): the actual delivering commit sha, recorded by `complete --delivered`.

## Status Machine Reference

Statuses: `pending`, `in_progress`, `blocked`, `completed`, `skipped`. `completed` and `skipped` are terminal.

Single-step transitions:

| from | allowed targets |
| --- | --- |
| `pending` | `pending`, `in_progress`, `blocked`, `skipped` |
| `in_progress` | `in_progress`, `pending`, `completed`, `blocked`, `skipped` |
| `blocked` | `blocked`, `in_progress`, `skipped` |
| `completed` | `completed` |
| `skipped` | `skipped` |

`in_progress` to `pending` is the pause edge: the Node yields so another Node can run, stays eligible, and is not fake-blocked. Use the `pause` command for it; `blocked` remains reserved for real external dependencies.

Operational transition gates:

- Before `pending` to `in_progress`, an implementation Node declares exactly one capability, module, or scenario closure and maps every applicable privacy, algorithm or data-structure, refactor, and focused-test obligation into its criteria.
- Better Plan never polls, times, interrupts, or replaces delegated Agents. The native host owns their lifetime and cancellation; unchanged delegated state should not produce repeated status reports, and this communication heuristic is not an execution, completion, or failure gate.
- The native parent reads `next-action`; `dispatch --role acceptance_designer|executor|auditor` obtains the runtime platform, checks prerequisites and unique active work, validates the phase/contract/criterion requirements, marks the Node active when execution begins, and records one opaque attempt. Direct `start`, `regress`, `check`, and `complete` are rejected for delivery Nodes.
- While `executor_running`, the fresh code-only executor implements the selected closure and resolves ordinary compiler, type, lint, import, and local integration errors before returning. Declared ownership is a planned focus rather than a filesystem boundary; necessary adjacent implementation changes are reported to the native main. The executor cannot mutate Plan state, edit frozen tests, run acceptance or full regression, or mark its own result.
- The correlated `executor-exited` event runs the focused contract automatically against unchanged declared paths. An ordinary implementation failure stays in the same Node and frozen acceptance; only a native-main finding of a real design or product-semantics error opens a repair cycle. Success enters `awaiting_auditor` with a fresh receipt. Command output is discarded.
- `dispatch --role auditor` binds the lifecycle's single independent audit to that receipt. `audit-failed` returns the finding to native-main classification; `audit-passed` checks every mapped criterion and auto completes the Node.
- Node completion is terminal for that user-visible capability lifecycle. It does not select or enroll a different Node; adjacent findings and possible follow-up capabilities return to the native main.
- A `final_validation` Node becomes eligible only after every non-skipped implementation Node is completed. Its `regression-requested` event owns the single full run for the current fingerprint. Failure parks it for a separately authored repair Node; success requires the final fingerprint-bound audit before automatic completion.

Mutation commands apply exactly one single-step transition. `validate` compares each Plan and Node status against the file's git HEAD version using path reachability: a change is legal when some sequence of single-step transitions connects the old status to the new one (for example `pending` to `completed` through `in_progress`), and illegal when no path exists (for example `completed` back to `in_progress`, or anything out of `skipped`).

Checkpoint snapshot and workflow invariants:

- At most one Node is `in_progress` per `Checkpoints.json`. To switch tasks, `pause` the running Node first.
- A Node is `in_progress` or `completed` only when every prerequisite is `completed`.
- A Node is `completed` only when every acceptance criterion is checked.
- An implementation Node is one independently acceptable closure and completes only after automatic focused regression plus an independent fingerprint-bound PASS.
- A final-validation Node runs only after all non-skipped implementation Nodes complete; its automatic full-regression route and final audit produce the plan's acceptance result.
- A non-terminal Node with a `skipped` (or transitively unstartable) prerequisite fails validation. Rewire its prerequisites or skip it; skip dependents before their prerequisite.
- Terminal Nodes are historical snapshots. Do not rewrite a completed Node's goal, description, or criteria to match later reality; record current truth in the plan documents and new Nodes. `edit-node` enforces this and only allows requirements-label corrections on terminal Nodes.

Plan consistency rules:

- `completed` requires every referenced Node to be terminal.
- `blocked` requires at least one blocked Node.
- `skipped` requires no `in_progress` Node.
- `pending` is invalid once Node work has started; `in_progress` is invalid once every Node is terminal. `sync-plan` re-derives Plan statuses: `in_progress` while work is running or partially done, `blocked` only when blocked Nodes leave nothing startable (a blocked Node with startable siblings keeps the Plan `in_progress`), `completed` or `skipped` when every Node is terminal.

## Manifest Tool Commands

| command | purpose |
| --- | --- |
| `validate [root] [--plan <selector>] [--check-sources] [--quiet] [--json] [--no-git]` | validate structure, schema, snapshot invariants, and git HEAD transition reachability; `--plan` scopes to one plan plus the shared index, `--check-sources` verifies `source_files` references |
| `discover [root]` | find structurally valid Better Plan workspaces |
| `uuid [--count N]` | generate UUID4 IDs |
| `platform [--json]` | print the normalized current runtime platform |
| `transition <current> <target>` | check one single-step status transition |
| `next-action <node-id> [root]` | return a delivery Node's bounded acceptance phase and sole next action without mutation |
| `dispatch <node-id> [root] --role acceptance_designer\|executor\|auditor` | create or reuse one correlated native-agent dispatch when that role is required |
| `advance <node-id> [root] --event <event> [--dispatch-id <id>] [--repair-node <id>]` | consume `acceptance-designer-exited`, `executor-exited`, `regression-requested`, `audit-passed`, `audit-failed`, `repair-registered`, or `repair-completed`; guarded events run regression, route repair, and auto complete |
| `start <node-id> [root]` | start a non-delivery foundation Node; rejected for implementation and final-validation acceptance |
| `pause <node-id> [root] [--reason "..."]` | return the `in_progress` Node to `pending` so another Node can start |
| `regress <node-id> [root]` | non-acceptance command entry; rejected for implementation and final-validation Nodes |
| `complete <node-id> [root] [--delivered <sha>]` | complete a fully checked non-delivery foundation Node; delivery Nodes auto complete after audit PASS |
| `block <node-id> [root] --reason "..."` | mark a Node `blocked` with a reason |
| `skip <node-id> [root] --reason "..."` | mark a Node `skipped` with a reason |
| `check <node-id> [root] --criterion <n> [--evidence "..."] [--evidence-file <path>] [--evidence-cmd "..."]` | record evidence for a non-delivery foundation criterion; rejected for delivery acceptance |
| `add-node [root] --plan <selector> --goal ... --description ... --criterion ... --commit-message ... --commit-target ... [--role] [--difficulty] [--platform] [--requirements] [--regression-scope] [--regression-command ...] [--regression-path ...] [--regression-criterion ...] [--after/--before <id>] [--prerequisites] [--next] [--splice] [--id]` | insert a new pending Node with validated placement and wiring; delivery roles require a complete regression contract, and `--splice` rewires the outgoing chain |
| `rewire <node-id> [root] [--prerequisites ...] [--next ...] [--add-prerequisite <id>] [--remove-prerequisite <id>] [--add-next <id>] [--remove-next <id>]` | replace or incrementally edit a Node's edges with validation |
| `edit-node <node-id> [root] [--goal] [--description] [--difficulty] [--platform] [--requirements] [--add-requirement] [--remove-requirement] [--criterion ...] [--commit-message] [--commit-target] [--commit-repository] [--regression-scope] [--regression-command ...] [--regression-path ...] [--regression-criterion ...]` | replace the full criterion set with repeated `--criterion` values (not additive); this replacement invalidates cached acceptance preparation, regression proof, dispatch, and audit state atomically; terminal Nodes accept only requirements-label corrections |
| `check-labels [root] [--plan <selector>] [--json]` | cross-check canonical `REQ-...` labels between plan markdown documents and Node `requirements`; noncanonical or undefined Node labels and noncanonical document labels are errors, uncovered canonical document labels are warnings |
| `sync-plan [root]` | re-derive every Plan status from its Nodes |
| `status [root] [--json]` | report per-plan progress, the in-progress Node, and blocked Nodes |
| `next [root] [--json]` | list the resumable or eligible Nodes per plan for the current platform |
| `schema plan\|node` | print the canonical object shape and template |

Plan selectors accept a plan id, `directory`, or `title`. Mutation commands validate the whole state file before writing, write atomically, and re-derive the owning Plan's status. When a command refuses, fix the underlying state instead of hand-editing `status`. Prefer `add-node`, `rewire`, and `edit-node` over hand-editing `Checkpoints.json`: they keep ids, placement, wiring, and snapshot invariants correct in one step.
