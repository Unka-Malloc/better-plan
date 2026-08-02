# Better Plan State Files Reference

This file documents the orthogonal capability-fact and delivery-lifecycle state files. The canonical shapes, enums, and templates are printed by the manifest tool and take precedence over any prose copy:

```sh
python3 scripts/manifest_tool.py schema capability
python3 scripts/manifest_tool.py schema plan
python3 scripts/manifest_tool.py schema node
```

Contents: [Workspace Structure](#workspace-structure), [Capability Fields](#capability-fields), [Plan Fields](#plan-fields), [Node Fields](#node-fields), [Status Machine Reference](#status-machine-reference), and [Manifest Tool Commands](#manifest-tool-commands).

## Workspace Structure

- The workspace root `Capabilities.json` is a JSON array of durable repository facts. It has no
  delivery status, acceptance lifecycle, or audit requirement.
- The workspace root `Manifest.json` is a flat JSON array of Plan objects. It never contains Node objects.
- Each plan owns one directory under the workspace root and one `Checkpoints.json` inside that directory, a JSON array of Node objects.
- Hierarchy is expressed only through relative paths: a child plan's `directory` nests under its parent plan's `directory`. The manifest array itself stays flat.
- The Plan directory tree groups scope and ownership: upper directories name broader owned scopes,
  deeper directories name more specific owned scopes, and leaves may own one platform target,
  business line, or integration. For example, `core`, `core/macos`, and `core/windows` express an
  ownership grouping, not an execution order.
- Before converting a narrative plan, freeze a source-grounded intent spine from the latest user
  request and relevant `source_files`: exact Plan ownership, required raw Purpose, Goal,
  Description, status, true prerequisites, explicit non-dependencies, and source-authored readable
  fields. Compare the readable default projection and the details audit projection against that
  same source-grounded intent spine before handoff. Plan hierarchy is ownership only and never
  creates an execution dependency; only Node UUIDs listed in `Checkpoints.json` `prerequisites` do
  so.
- A product-wide model uses one canonical workspace and one parentless repository capability fact.
  Plans are unlimited historical delivery records, but the native main searches by stable
  capability key and reuses or extends a matching nonterminal Plan before creating another.
  Supporting requirements, architecture, validation, evidence, execution-policy, and localized
  documents remain source projections; `Capabilities.json`, `Manifest.json`, and branch-owned
  `Checkpoints.json` carry their distinct structured responsibilities.

## Capability Fields

Unknown means absent from `Capabilities.json`; do not create speculative entries merely to make the
tree look complete. Every stored capability contains:

- `key`: stable lowercase slash path, such as `repository/module-a/interface-x`. A child's key must
  extend its immediate parent's key by exactly one segment. Reuse this key across later work.
- `parent`: immediate parent key, or `null` for the one repository root. Parents appear before
  children, so progressive disclosure proceeds root to leaf.
- `title`: bounded human-readable identity. Two siblings may not have the same normalized title;
  reuse the existing key instead.
- `kind`: `repository`, `domain`, `module`, `component`, `service`, `interface`, `feature`, or
  `capability`. The parentless root is the only `repository` entry.
- `basis`: `observed` for architecture already present in a mature repository or `designed` for a
  genuinely new capability. Observed facts are accepted as current reality without retrospective
  Designer, Verifier, Reviewer, or acceptance work.
- `disclosure`: `known` or `examined`. `known` is a lightweight fact encountered beside the selected
  path; it does not claim internal understanding.
- `touch`: `untouched`, `in_scope`, or `modified`. A `known` entry must remain `untouched`; entering
  scope promotes it to `examined`. State is monotonic, so later work enriches the same entry.
- `source_files`: bounded repository-relative evidence locations or explicit external references.
- `description`: one privacy-safe line containing only the fact justified by current observation or
  design.

The root represents the repository's core or foundation and is always `examined`. Follow only the
root-to-leaf path required by the latest request. Record siblings encountered along that path as
`known/untouched` and stop; do not inspect their internals. `capability_scope` sent to children
contains the selected path and touched descendants and reports, but does not expose, omitted known
untouched descendants.

Capability ancestry never creates execution order. An observed ancestor is already established. If
a `designed` parent foundation must be delivered before a child, bind a parent task group and place
its completed Node UUID in the child Node's `prerequisites` list.

## Plan Fields

- `id`: UUID4 plan ID. Generate with `scripts/manifest_tool.py uuid`.
- `status`: one of `pending`, `in_progress`, `blocked`, `deferred`, `completed`, `skipped`.
- `title`: concise human-readable plan name.
- `directory`: relative path from the workspace root to the plan's dedicated directory. May contain nested segments when the plan is a child of another plan.
- `source_files`: list of source plan files from Step 1. Use an empty list only when the plan came directly from the user request and has no source file yet. Write local entries relative to the project root (the nearest ancestor of the workspace with `.git`); external references use `owner/repo:path` or a URL. `validate --check-sources` verifies that local entries still resolve, so stale paths surface instead of rotting.
- `purpose`: required privacy-safe single-line explanation of why this Plan exists and what role it serves in the Plan hierarchy. Keep it distinct from `goal` and `description`; do not derive or copy it from either field. The `tree --details` audit projection prints this exact field, and validation rejects missing, empty, multiline, unsafe, or oversized values.
- `goal`: brief plan goal.
- `description`: lightweight plan summary only. Keep it short enough to identify the plan's scope, boundary, parent or child relationship when relevant, and important constraints. Do not put detailed design, architecture, dependency trees, task sequencing, implementation notes, risks, or acceptance logic here; move those details into the selected plan's `Checkpoints.json` Nodes.
- `checkpoints`: relative path to the plan's checkpoint file. Must be exactly `<directory>/Checkpoints.json`.

Optional readable-projection fields:

- `kind`: `root`, `stage`, `group`, `gate`, `rule`, `branch`, `context`, `release`, or `plan`.
  It describes how the source authority names the Plan in the execution reading layer.
- `tree_mode`: `show`, `flatten`, or `hide`. `show` renders the Plan normally; `flatten` promotes
  only its child Plans while its structural wrapper and directly owned Nodes remain audit-only;
  `hide` omits its supplemental branch from the default view. An explicitly selected flattened
  Plan renders with `show` semantics, and `tree --details` always retains every Plan and owned Node.
- `node_status`: `show` or `hide`, controlling whether that Plan's child milestones include
  lifecycle/dependency brackets in the default view.
- `entry_gate`: `{title, prerequisites, conditions}`. `title` is the source-authored gate label,
  `prerequisites` is an ordered list of globally resolvable Node UUIDs, and `conditions` is an
  ordered list of explicit non-Node activation conditions. Conditions are explanatory and do not
  affect automatic Node eligibility.
- `decision_issues`: Reviewer-raised developer choices owned by this Plan. Each entry contains
  `{id, urgency, question, context, options, status}` and an optional `resolution` after it is
  resolved. `urgency` is `immediate` or `deferred`; `status` is `open` or `resolved`. Use the
  manifest tool's decision commands instead of hand-editing this history. Open immediate issues
  block `reviewer-finished`; open deferred issues remain visible through final handoff.
- `capability_key`: stable key from `Capabilities.json`. Every nonterminal `kind: "group"` Plan must
  bind one `examined` capability whose touch is `in_scope` or `modified`. At most one nonterminal
  group may bind a key, preventing duplicate active Plans while preserving terminal history.

A Plan that owns automated delivery Nodes must use `kind: "group"` and contain exactly one
`group_design`, at least one `implementation`, and exactly one trailing `final_validation` Node.
Every implementation directly depends on group design. Final validation directly depends on every
non-skipped implementation.

Hierarchical example:

```json
[
  {
    "id": "01234567-89ab-4def-8123-456789abcdef",
    "status": "pending",
    "title": "Common",
    "directory": "common",
    "source_files": ["docs/common-plan.md"],
    "purpose": "Group related business-line Plans within one owned scope.",
    "goal": "Describe the shared business planning area.",
    "description": "Broader ownership scope for related business-line work.",
    "checkpoints": "common/Checkpoints.json"
  },
  {
    "id": "89abcdef-0123-4567-89ab-cdef01234567",
    "status": "pending",
    "title": "A",
    "directory": "common/a",
    "source_files": ["docs/a-plan.md"],
    "purpose": "Own business-line A planning within the common scope.",
    "goal": "Describe the intended outcome for business-line A.",
    "description": "Specific ownership scope for business-line A work.",
    "checkpoints": "common/a/Checkpoints.json"
  }
]
```

This directory relationship records Plan ownership only. It creates no Node edge. Execution depends
on another Node only when that Node's UUID appears in a `Checkpoints.json` `prerequisites` list.

## Node Fields

Required fields:

- `id`: UUID4 task ID. Generate with `scripts/manifest_tool.py uuid`.
- `status`: one of `pending`, `in_progress`, `blocked`, `deferred`, `completed`, `skipped`.
- `role`: one of `product_requirements`, `evidence`, `validation_matrix`,
  `architecture_scaffold`, `group_design`, `milestone_gate`, `implementation`, or
  `final_validation`. Roles let the validator enforce delivery order and difficulty requirements.
  The `architecture_scaffold` Node
  fixes the module and file decomposition, layer boundaries, dependency direction, interface
  contracts, and deliberate design-pattern choices in `Architecture.md` before implementation
  Nodes start. `group_design`, `implementation`, and `final_validation` are automated delivery
  roles. Designer handles `group_design` once for the group; Worker and Verifier handle each
  implementation; Reviewer handles final validation once for the group.
  `milestone_gate` is a non-delivery aggregate evidence gate: it uses the manual `start`, `check`,
  and `complete` path and never enters implementation dispatch.
- `prerequisites`: the sole execution-dependency authority: a list of globally unique Node IDs in
  the same workspace that must be `completed` before this task can run. References may cross Plans
  and checkpoint-array positions. Validation resolves the complete workspace graph and rejects
  unknown IDs, skipped prerequisite chains, and cycles before mutation or dispatch.
- `platform`: `any`, `linux`, `macos`, or `windows`. Use `any` unless the task genuinely requires one operating system. `platform` prints the normalized runtime, and delivery dispatch rejects a different non-`any` value before creating work. Platform-specific Nodes belong in that platform's child plan with `platform` set to the target; the platform-neutral foundation plan keeps its Nodes at `any`.
- `difficulty`: task complexity and consequence, never reasoning effort. Use `routine` for a
  bounded local or mechanical change with an established contract; `standard` for an ordinary
  single-capability implementation with limited integration; `complex` for cross-component,
  migration, state, concurrency, or materially ambiguous work; and `critical` for architectural,
  security, privacy, release, or similarly high-consequence work. Worker Coding Agent score floors
  are respectively 25, 42, 55, and 64. The validator requires `complex` or `critical` for
  `product_requirements`, `evidence`, `validation_matrix`, `architecture_scaffold`,
  `group_design`, `milestone_gate`, and `final_validation`; group final validation must be
  `critical`. Use `critical` for new-product or feature-foundation work unless Step 1 verified the
  corresponding artifact is already complete.
- `verification_profile`: `code`, `visual`, or `hybrid`. This is independent of difficulty. `code`
  routes implementation and final validation to the rigorous code Verifier/Reviewer. `visual` and
  `hybrid` require Visual Verifier/Reviewer roles with vision, real-browser control, and rendered
  evidence for declared viewports and interaction states; `hybrid` also requires complete code and
  data-flow verification. The final-validation profile must equal the sole non-skipped
  implementation profile, or `hybrid` when implementation profiles are mixed or already hybrid.
- `goal`: brief task goal tied to product delivery, not only file edits.
- `description`: structured task design brief. Do not target a fixed sentence count and do not write free-form filler. Populate the following sections in order inside the string, using clear labels or compact labeled clauses when that keeps JSON readable:
  - `Scope`: name the concrete artifacts touched or inspected, such as code files, tests, scripts, configs, generated artifacts, documentation pages, or plan files. Also name the conceptual surface, such as modules, packages, components, commands, APIs, protocols, data models, feature areas, user-visible behaviors, or project capabilities. Include the Node's dependency-tree position when useful: its parent foundation or contract, its current level responsibility, and the child branches or consumers it unlocks. When exact files are not yet known, provide search targets such as symbols, routes, CLI flags, doc headings, config keys, schemas, or error strings. Begin every implementation Node with exactly one independently acceptable closure declaration: `Closure: capability - <target>`, `Closure: module - <target>`, or `Closure: scenario - <target>`. Name only the modules, directories, and files necessary for that closure, aligned with the `Architecture.md` module map, plus the interfaces consumed from other modules. Split distinct closures into separate Nodes so Nodes without a prerequisite path stay on disjoint files and can run in parallel.
  - `Context`: summarize the current behavior, project state, prior decision, or source-plan requirement that makes this task necessary. Ground this in Step 1 evidence instead of generic intent.
  - `Target`: describe the intended final behavior or design state for this Node only, including referenced requirement labels and evidence links when known. Keep ordering out of this section because `prerequisites` owns execution order, and keep concrete completion checks out because `acceptance_criteria` owns verification. An implementation Node without `requirements` labels must describe here why it is enabling work for a later requirement.
  - `Design Considerations`: when relevant, identify existing architectural or design patterns to follow, abstractions to reuse or avoid, data structures, state shapes, schemas, storage formats, algorithms, control flow, ordering semantics, complexity, concurrency, caching, parsing, error handling, or ownership and API boundary concerns.
  - `Design Value`: explain why any material design choice is worth doing. A pattern, abstraction, data structure, algorithm, or architecture change is justified only when it reduces real complexity or duplication, preserves a domain invariant, clarifies ownership or API boundaries, improves correctness, testability, performance, scalability, observability, or failure handling, or aligns with an established project pattern. Prefer the project's existing patterns and the simplest local change unless this value test justifies a stronger design.
  - `Constraints & Risks`: capture invariants, non-goals, compatibility/removal expectations, dependencies, assumptions, unresolved questions, and implementation risks that the worker must keep in mind. Explicitly identify applicable privacy or backend-data restrictions, algorithm or data-structure evidence and performance targets, complete-refactor removal obligations, and the boundary that prevents the Node from expanding into another closure.
  - Omit a section only when it truly does not apply to the Node. If the source plan or inspected code does not justify a detail, state the uncertainty explicitly instead of inventing requirements.
- `acceptance_criteria`: non-empty list of criterion objects (see below).
- `commit`: expected commit or delivery information (see below).
- `next`: list of Node UUIDs that become natural follow-up candidates after this task. Use an empty
  list only when no follow-up Node exists. Navigation references do not affect eligibility and
  never create execution dependencies.

Optional fields:

- `code`: workspace-unique, privacy-safe milestone code used for human dependency labels.
- `title`: privacy-safe source-authored milestone title. The renderer never invents or abbreviates
  it from Goal or Description.
- `tags`: ordered privacy-safe source tags such as `DESIGN_ONLY`. `GATE_LEAF` is reserved for a
  real non-`milestone_gate` Node whose evidence is consumed directly by a same-Plan
  `milestone_gate`. The tag does not change the leaf's role, eligibility, or lifecycle.
- `conditions`: ordered privacy-safe non-Node activation conditions. They remain presentation
  requirements and do not affect automatic eligibility.
- `requirements`: list of requirement labels such as `REQ-001` that this Node delivers or proves. Labels must begin with `REQ` and contain one or more hyphen-delimited alphanumeric segments (`REQ-001` and `REQ-CLIENT-001` are valid; `CLIENT-REQ-001` is not). Prefer Plan-local `REQ-###` labels because the Plan boundary already supplies the namespace. Implementation Nodes must list at least one canonical label or describe enabling work in `description`. Final-validation Nodes must list the canonical labels they prove; the validator requires them to cover every label carried by non-skipped implementation Nodes. `check-labels` cross-checks these labels against the labels written in the plan directory's markdown documents and rejects noncanonical labels instead of silently dropping them.
- `design`: machine-readable design boundary required for every non-terminal automated delivery
  Node. Its artifact and acceptance paths are passed to isolated roles. The group Designer also
  reads `references/design-patterns.md` locally and writes a `design_pattern_assessment` into the
  declared design artifact. The assessment compares a catalog candidate with the simplest direct
  solution, states the concrete benefit and costs, defines the smallest correct application and
  acceptance seam, or records `candidate: none`. A pattern name without that evidence is not a
  completed design.
- `status_reason`: why the Node is `blocked`, `deferred`, `skipped`, or paused back to `pending`,
  and what would unblock or resume it. The `block`, `defer`, and `skip` commands require it;
  `pause` records it when given; `activate` and other execution transitions clear it. This text is
  explanatory only and never creates a Node dependency.
- `acceptance` (tool-written for automated delivery Nodes): deterministic lifecycle state. Its
  phase is one of `awaiting_designer`, `designer_running`, `awaiting_worker`, `worker_running`,
  `correction_required`, `awaiting_verifier`, `verifier_running`, `awaiting_reviewer`,
  `reviewer_running`, `reviewer_complete`, `repair_plan_required`, `awaiting_repair`, or `accepted`.
  `attempt` is a non-negative
  counter and `outcome` is bounded state-machine data. A running dispatch stores an opaque ID,
  role, optional bound host-agent ID, and only role-required fingerprints. Final-validation state
  retains one `review` receipt after the group's sole Reviewer returns and may temporarily bind one
  `repair_node_id`. Never hand-edit this object.
- `regression`: executable validation contract required before an `implementation` or `final_validation` Node can start. It contains:
  - `scope`: `focused` for `implementation`, `full` for `final_validation`.
  - `commands`: non-empty unique command strings executed sequentially from the project root. Every command must exit 0. Standard output and error are discarded rather than persisted or echoed.
  - `criteria`: non-empty unique zero-based indexes of the acceptance criteria proved by the complete command set. A passing run checks only these criteria.
  - `paths`: non-empty unique repository-relative files or directories fingerprinted immediately before and after execution. Paths must exist, stay inside the project, avoid symbolic links and mutable Better Plan state files, and not overlap one another.
  - `last_pass` (tool-written): `{recorded_at, contract_digest, content_fingerprint}`. Editing the contract or declared content makes the receipt stale. Do not hand-write receipts.

Acceptance criterion object:

- `checked`: boolean. Group-design criteria are checked when the bound Designer completes;
  implementation criteria are checked only after the bound Verifier returns and focused regression
  passes; final-validation criteria are checked after the one Reviewer returns and post-review full
  regression passes. A foundation Node may record its own evidence before manual completion.
- `text`: non-empty description of a concrete check that proves the task is complete. Reference requirement labels, evidence artifacts, tests, verifiers, or generated-artifact checks. Every implementation Node includes the smallest focused check for its declared closure. Add conditional criteria for redacted backend or sensitive evidence, open-source comparison and performance decisions for algorithm or data-structure work, and a purpose-built one-time removal check for refactors. Only final-validation Nodes may require the complete regression suite.
- `evidence` (optional): minimal redacted, single-line summary of what verification proved this criterion, recorded by `check --evidence`. The validator rejects concrete paths, network endpoints, server identifiers, secret-shaped assignments, credentials, and backend runtime output.
- `evidence_refs` (optional): machine-verifiable evidence records written by `check --evidence-file` and `check --evidence-cmd`. A file reference records `{type, path, sha256, recorded_at}`, where `path` is confined to the repository and persisted relative to its root. A command reference records `{type, command_sha256, exit_code, recorded_at}` and may only exist for a passing run (`exit_code` 0). Command text, standard output, and standard error are never persisted.

Commit object:

- `repository`: the target Git repository's `.git` entry.
- `message`: suggested commit message.
- `target`: where the work should be committed or delivered.
- `delivered` (optional): the actual delivering commit sha, recorded by `complete --delivered`.

## Status Machine Reference

Statuses: `pending`, `in_progress`, `blocked`, `deferred`, `completed`, `skipped`. `completed` and
`skipped` are terminal. `deferred` is visible non-terminal backlog state and is never executable
until an explicit `activate` returns it to `pending`.

Single-step transitions:

| from | allowed targets |
| --- | --- |
| `pending` | `pending`, `in_progress`, `blocked`, `deferred`, `skipped` |
| `in_progress` | `in_progress`, `pending`, `completed`, `blocked`, `deferred`, `skipped` |
| `blocked` | `blocked`, `in_progress`, `deferred`, `skipped` |
| `deferred` | `deferred`, `pending`, `blocked`, `skipped` |
| `completed` | `completed` |
| `skipped` | `skipped` |

`in_progress` to `pending` is the pause edge: the Node yields so another Node can run, stays eligible, and is not fake-blocked. Use the `pause` command for it; `blocked` remains reserved for real external dependencies.

Use `defer` when the capability is still promised but intentionally postponed. It clears stale
delivery dispatch/proof, keeps the same lifecycle visible, and prevents automatic selection.
Use `activate` to return it to `pending`. Use terminal `skip` only when the obligation is explicitly
waived or not applicable; never use it for future work.

Operational transition gates:

- Before `pending` to `in_progress`, an implementation Node declares exactly one capability, module, or scenario closure and maps every applicable privacy, algorithm or data-structure, refactor, and focused-test obligation into its criteria.
- A foundation Node may directly execute through `start`, `check`, and `complete`. A
  `milestone_gate` is also non-delivery, but it may enter `pending`, `in_progress`, or `completed`
  only when its `prerequisites` directly contain at least one same-Plan non-gate Node tagged
  `GATE_LEAF`. Blocked and deferred gates may temporarily have no leaf; `activate` and `start`
  validate this contract before writing.
- Better Plan never polls, times, interrupts, or replaces delegated Agents. The native host owns their lifetime and cancellation; unchanged delegated state should not produce repeated status reports, and this communication heuristic is not an execution, completion, or failure gate.
- The native parent reads `next-action`; `dispatch --role designer|worker|verifier|reviewer`
  checks platform, prerequisites, ownership independence, group order, and current lifecycle phase,
  then records one opaque dispatch. Independent implementation Nodes in the same task group may
  remain active concurrently. State mutations are serialized even though bound child executions
  overlap. Direct `start`, `regress`, `check`, and `complete` are rejected for automated delivery
  Nodes.
- Every child dispatch uses `fork_turns: "none"`, receives only its Node or group, its one role
  reference, action-specific local knowledge references, and necessary repository-relative files,
  then binds the real opaque host-agent ID. Designer always receives the complete local
  `references/design-patterns.md` content and never needs to fetch its source website.
  Spawn return is not completion; only an exact final callback from the bound child may advance
  state.
- Code verification requires `code_reasoning`. Visual and hybrid verification additionally require
  `vision`, `browser`, and rendered browser evidence. A visual leaf reports a blocker when it cannot
  obtain the real rendered state; source inspection, DOM text, snapshots, and successful builds are
  not visual acceptance.
- While `worker_running`, the fresh code-only worker implements the selected closure and resolves ordinary compiler, type, lint, import, and local integration errors before returning. Declared ownership is a planned focus rather than a filesystem boundary; necessary adjacent implementation changes are reported to the native main. The worker cannot mutate Plan state, edit frozen tests, run acceptance or full regression, or mark its own result.
- The Worker's correlated final callback enters `awaiting_verifier` without running the frozen
  regression. The write-capable Verifier repairs the Node, and its final callback runs focused
  regression once. A passing run checks the mapped criteria and completes the Node; failure enters
  `correction_required`. Command output is discarded.
- Node completion is terminal for that user-visible capability lifecycle. It does not select or enroll a different Node; adjacent findings and possible follow-up capabilities return to the native main.
- A `final_validation` Node becomes eligible only after every non-skipped implementation Node is
  completed. It routes directly to the group's one Reviewer. The Reviewer repairs all autonomous
  findings and returns developer choices. After the native main records them, `reviewer-finished`
  runs full regression once. Failure may bind a separately authored repair Node; completing that
  Node triggers a failure-driven rerun and never another Reviewer.

Mutation commands apply exactly one single-step transition. `validate` compares each Plan and Node status against the file's git HEAD version using path reachability: a change is legal when some sequence of single-step transitions connects the old status to the new one (for example `pending` to `completed` through `in_progress`), and illegal when no path exists (for example `completed` back to `in_progress`, or anything out of `skipped`).

Checkpoint snapshot and workflow invariants:

- Multiple `implementation` Nodes may be `in_progress` in one `Checkpoints.json` only when their
  prerequisites are complete and their validated design ownership is independent. Every other role
  remains exclusive within its task group. Use `pause` to yield an active Node, not to serialize an
  otherwise safe parallel Worker frontier.
- A Node is `in_progress` or `completed` only when every prerequisite is `completed`.
- `GATE_LEAF` is not a dependency field. `prerequisites` remains the sole execution authority. A
  pending, in-progress, or completed `milestone_gate` must directly depend on at least one
  same-Plan `GATE_LEAF`; a prose task card, source document, Plan hierarchy, or transitive leaf is
  insufficient.
- Node prerequisites resolve across every Plan referenced by the workspace Manifest. `next`,
  `status_reason`, Plan hierarchy, descriptions, and architecture prose do not affect eligibility.
- A Node is `completed` only when every acceptance criterion is checked.
- An implementation Node is one independently acceptable closure and completes only after Worker,
  Verifier repair, and one passing focused regression.
- A final-validation Node runs only after all non-skipped implementation Nodes complete; its one
  whole-group Reviewer and one normal post-review full regression produce the group's acceptance
  result. Additional runs are failure-driven repair retries only.
- A non-terminal Node with a `skipped` (or transitively unstartable) prerequisite fails validation. Rewire its prerequisites or skip it; skip dependents before their prerequisite.
- Terminal Nodes are historical snapshots. Do not rewrite a completed Node's goal, description, or criteria to match later reality; record current truth in the plan documents and new Nodes. `edit-node` enforces this and only allows requirements-label corrections on terminal Nodes.

Plan consistency rules:

- `completed` requires every referenced Node to be terminal.
- `blocked` requires at least one blocked Node.
- `deferred` requires at least one deferred Node and leaves the Plan non-terminal.
- `skipped` requires no `in_progress` Node.
- `pending` is invalid once Node work has started or has been deferred; `in_progress` is invalid once every Node is terminal. `sync-plan` re-derives Plan statuses: `in_progress` while work is running or partially done, `blocked` only when blocked Nodes leave nothing startable (a blocked Node with startable siblings keeps the Plan `in_progress`), `deferred` when deferred obligations leave nothing startable, and `completed` or `skipped` only when every Node is terminal.

## Manifest Tool Commands

| command | purpose |
| --- | --- |
| `validate [root] [--plan <selector>] [--check-sources] [--quiet] [--json] [--no-git]` | validate capability facts, delivery bindings, state structure, snapshot invariants, and git HEAD transition reachability; `--plan` scopes delivery checks, while the shared capability catalog remains validated |
| `discover [root]` | find structurally valid Better Plan workspaces |
| `init-capabilities [root] --key <root> --title ... --description ... [--basis observed\|designed] [--source ...]` | initialize the one examined repository root; an exact repeat is idempotent |
| `upsert-capability [root] --key ... --parent ... --title ... --kind ... --description ... [--basis ...] [--source ...] [--disclosure known\|examined] [--touch untouched\|in_scope\|modified]` | create or monotonically enrich one fact; missing parents and stable-key identity conflicts are rejected |
| `promote-capability <key> [root] [--touch in_scope\|modified]` | promote an existing lightweight fact when the latest request actually touches it |
| `bind-plan-capability [root] --plan <selector> --capability <key>` | bind a task group to one examined in-scope capability; duplicate nonterminal ownership is rejected |
| `capability-tree [root] [--details]` | render known facts, disclosure/touch state, and optionally bounded descriptions and sources |
| `uuid [--count N]` | generate UUID4 IDs |
| `platform [--json]` | print the normalized current runtime platform |
| `transition <current> <target>` | check one single-step status transition |
| `next-action <node-id> [root]` | return an automated delivery Node's bounded phase, sole next action, transcript-free `work_items`, role and knowledge references, capability scope with known untouched descendants omitted, native agent type, and necessary paths without choosing a model |
| `dispatch <node-id> [root] --role designer\|worker\|verifier\|reviewer [--native-host codex]` | create or reuse one correlated native-agent dispatch with the same structured delegation facts; Codex freezes the installed role selector first and falls back to the packaged recommendation |
| `bind-agent <node-id> [root] --dispatch-id <id> --agent-id <id>` | bind the validated opaque native host identity returned by the real spawn call |
| `delegation-failed <node-id> [root] --dispatch-id <id> (--spawn-refused\|--agent-id <id>\|--unavailable)` | record one explicitly qualified delegation failure and enter native-main fallback at the retry ceiling |
| `main-complete <node-id> [root] --dispatch-id <id> --role designer\|worker\|verifier\|reviewer` | record completion of the exact role by the native main after bounded delegation failure |
| `agent-complete <node-id> [root] --agent-id <id> --final` | consume one exact final host callback; unbound, ambiguous, mismatched, and replayed callbacks are no-ops |
| `advance <node-id> [root] --event <event> [--dispatch-id <id>] [--repair-node <id>]` | consume `reviewer-finished`, `repair-registered`, or `repair-completed`; guarded events run the post-review full regression, route repair, and auto complete |
| `start <node-id> [root]` | start a non-delivery foundation Node; rejected for group-design, implementation, and final-validation lifecycles |
| `pause <node-id> [root] [--reason "..."]` | return the `in_progress` Node to `pending` so another Node can start |
| `regress <node-id> [root]` | manual foundation command entry; rejected for automated delivery Nodes |
| `complete <node-id> [root] [--delivered <sha>]` | complete a fully checked non-delivery foundation Node; automated Nodes complete through their role lifecycle |
| `block <node-id> [root] --reason "..."` | mark a Node `blocked` with a reason |
| `defer <node-id> [root] --reason "..."` | park promised work as visible, non-terminal, non-executable `deferred` |
| `activate <node-id> [root]` | return an explicitly deferred Node to `pending` |
| `skip <node-id> [root] --reason "..."` | irreversibly waive or mark a Node not applicable |
| `check <node-id> [root] --criterion <n> [--evidence "..."] [--evidence-file <path>] [--evidence-cmd "..."]` | record evidence for a non-delivery foundation criterion; rejected for delivery acceptance |
| `add-node [root] --plan <selector> --goal ... --description ... --criterion ... --commit-message ... --commit-target ... [--role] [--difficulty] [--platform] [--verification-profile code\|visual\|hybrid] [--requirements] [--design-json] [--regression-scope] [--regression-command ...] [--regression-path ...] [--regression-criterion ...] [--after/--before <id>] [--prerequisites] [--next] [--splice] [--id]` | insert a new pending Node with validated wiring and an explicit verification capability profile; automated roles require design and implementation/final-validation roles also require their regression contract |
| `rewire <node-id> [root] [--prerequisites ...] [--next ...] [--add-prerequisite <id>] [--remove-prerequisite <id>] [--add-next <id>] [--remove-next <id>]` | replace or incrementally edit a Node's edges with validation |
| `edit-node <node-id> [root] [--goal] [--description] [--difficulty] [--platform] [--verification-profile] [--requirements] [--add-requirement] [--remove-requirement] [--criterion ...] [--commit-message] [--commit-target] [--commit-repository] [--regression-scope] [--regression-command ...] [--regression-path ...] [--regression-criterion ...]` | replace content including verification capability; edits invalidate stale preparation and proof while preserving the one-Reviewer-per-group invariant; terminal Nodes accept only requirements-label corrections |
| `check-labels [root] [--plan <selector>] [--json]` | cross-check canonical `REQ-...` labels between plan markdown documents and Node `requirements`; noncanonical or undefined Node labels and noncanonical document labels are errors, uncovered canonical document labels are warnings |
| `sync-plan [root]` | re-derive every Plan status from its Nodes |
| `record-decision [root] --plan <selector> --urgency immediate\|deferred --question ... --context ... --option ... --option ...` | record one structured Reviewer-raised developer choice; immediate items must be reported now |
| `resolve-decision <decision-id> [root] --plan <selector> --resolution ...` | preserve the choice history and record the user's resolution |
| `tree [root] [--plan <selector>] [--details]` | render the capability facts followed by the concise source-grounded execution tree; `--details` adds full bounded capability detail and every raw Plan field |
| `status [root] [--json]` | report per-plan progress, active/blocked/deferred Nodes, and open decisions with immediate/final-handoff timing |
| `next [root] [--json]` | list all active Nodes and every safely eligible pending Node per plan for the current platform |
| `schema capability\|plan\|node` | print the canonical object shape and template |

Plan selectors accept a plan id, `directory`, or `title`. Mutation commands validate the whole state file before writing, write atomically, and re-derive the owning Plan's status. When a command refuses, fix the underlying state instead of hand-editing `status`. Prefer `add-node`, `rewire`, and `edit-node` over hand-editing `Checkpoints.json`: they keep ids, placement, wiring, and snapshot invariants correct in one step.
