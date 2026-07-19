# Acceptance State Machine Architecture

## Design goal and order

Move design, acceptance quality, execution effects, and completion into explicit ownership boundaries. The permanent order is:

1. The native main agent owns requirements, evidence, architecture, the Node graph, symbol-level design, and interface scaffolds.
2. A fresh acceptance designer reads the frozen design and writes validation artifacts and tests, using declared paths as its planned focus and reporting necessary adjacent test changes.
3. A different fresh acceptance reviewer judges the tests before code execution.
4. A fresh executor implements the frozen Node design, using declared paths as its planned focus and reporting necessary adjacent implementation changes.
5. The state tool runs regression on executor exit and routes success to audit or failure to a native-main repair decision.
6. A fresh auditor receives a minimal fingerprint-bound review contract; PASS permits automatic completion.

The main agent is therefore the design owner, not a passive dispatcher. Delegated agents produce one bounded artifact or verdict. Deterministic code owns correlations, fingerprints, regression outcomes, evidence mutation, and terminal state; the native main owns every repair decision.

## Machine-readable design contract

Every new nonterminal `implementation` or `final_validation` Node carries a `design` object before any delegated preparation role is dispatched:

```json
{
  "design": {
    "artifact": "docs/plan/example/Architecture.md",
    "owned_paths": ["scripts/example.py"],
    "scaffold_paths": ["scripts/example.py"],
    "acceptance_paths": ["docs/plan/example/Validation.md", "tests/test_example.py"],
    "symbols": [
      {
        "path": "scripts/example.py",
        "kind": "function",
        "name": "evaluate",
        "operation": "add",
        "signature": "evaluate(state: Mapping[str, object]) -> str"
      }
    ],
    "interfaces": [
      {
        "name": "evaluate",
        "producer": "scripts/example.py",
        "consumers": ["scripts/manifest_tool.py"],
        "inputs": "validated immutable state mapping",
        "outputs": "one bounded action string",
        "errors": ["ValueError for an unsupported state"]
      }
    ],
    "dependencies": [
      {
        "from": "scripts/manifest_tool.py",
        "to": "scripts/example.py",
        "reason": "the effectful adapter depends on the pure domain function"
      }
    ],
    "decisions": {
      "composition": "compose pure functions; no substitutable runtime types require inheritance",
      "algorithms": "constant-time transition lookup from an immutable table",
      "data_structures": "MappingProxyType tables and normalized tuples",
      "state": "the checkpoints adapter is the sole persisted-state writer",
      "isolation": "role contracts and writable paths are disjoint",
      "concurrency": "serialize one Plan state file; allow concurrency only across disjoint Plans"
    },
    "test_seams": ["pure transition lookup", "atomic adapter boundary"]
  }
}
```

Validation rules:

- All paths are normalized repository-relative paths without `.` or `..`, absolute roots, control characters, symlinks, or overlap between acceptance ownership and executor ownership.
- `artifact`, `owned_paths`, `scaffold_paths`, and `acceptance_paths` are non-empty. Every scaffold path belongs to `owned_paths`; every symbol path belongs to `owned_paths`.
- Symbol `kind` is `module`, `function`, `class`, `interface`, or `type`; `operation` is `add`, `modify`, or `remove`; name and signature are bounded non-empty strings.
- Interface producers and consumers name declared modules; inputs, outputs, and errors state observable contracts rather than implementation prose.
- Dependency edges point from consumers to providers and must agree with the module dependency direction below.
- Every decision field is explicit. `none: <reason>` is valid when a topic does not apply; omission is not.
- Independent implementation Nodes with no prerequisite path may not own equal, ancestor, or descendant paths. This is checked by normalized component comparison, not string-prefix comparison.
- Terminal Nodes without `design` remain immutable historical snapshots. New and nonterminal delivery work uses the current contract only; there is no compatibility execution path.

## Preparation and delivery phases

The coarse Node `status` remains the delivery lifecycle. A bounded `acceptance` snapshot carries the current preparation or delivery phase:

- `awaiting_acceptance_design`: design and scaffold are frozen; a fresh acceptance designer is next.
- `acceptance_designer_running`: one acceptance-designer dispatch is outstanding.
- `awaiting_acceptance_review`: declared acceptance artifacts exist for the current design fingerprint.
- `acceptance_reviewer_running`: one different read-only reviewer is bound to design and acceptance fingerprints.
- `acceptance_revision_required`: the reviewer rejected the cases; a fresh designer must revise them.
- `awaiting_executor`: reviewed implementation acceptance is current.
- `executor_running`: one code-only executor dispatch is outstanding.
- `repair_required`: regression or code audit failed without invalidating design or tests; the
  native main must choose repair or defer. A fresh executor is legal only after that choice.
- `awaiting_regression`: reviewed final-validation acceptance is current and the single full run is next.
- `awaiting_auditor`: a current passing regression receipt exists.
- `auditor_running`: one minimal read-only audit is bound to the current regression fingerprint.
- `repair_plan_required`: final validation found work that must become a new repair Node.
- `awaiting_repair`: final validation is bound to one new repair Node.
- `accepted`: current preparation, regression, and audit bindings agree; completion is the only effect.

The snapshot stores only bounded phase, attempt count, opaque correlation, safe outcome class, preparation digests, and audit digests. It never stores prompts, role-template content, command output, findings, absolute paths, machine identity, server information, or runtime data.

## Events and actions

| Current phase | Correlated event | Guard and effect | Next action |
| --- | --- | --- | --- |
| `awaiting_acceptance_design` or `acceptance_revision_required` | acceptance designer dispatched | valid design; no outstanding dispatch | wait for designer exit |
| `acceptance_designer_running` | `acceptance-designer-exited` | matching role and correlation; fingerprint design, scaffold, validation, and tests | `dispatch_acceptance_reviewer` |
| `awaiting_acceptance_review` | acceptance reviewer dispatched | different role; bind both preparation fingerprints | wait for reviewer verdict |
| `acceptance_reviewer_running` | `acceptance-approved` | matching correlation and unchanged fingerprints | implementation → `dispatch_executor`; final → `run_regression` |
| `acceptance_reviewer_running` | `acceptance-rejected` | matching correlation; clear candidate approval | `dispatch_acceptance_designer` |
| `awaiting_executor` or `repair_required` | executor dispatched | current preparation approval; increment attempt | wait for executor exit |
| `executor_running` | `executor-exited` | matching executor; first compare stable reviewed inputs, then run focused regression | reviewed-input drift → `dispatch_acceptance_designer`; unchanged-input failure → `main_repair_decision`; success → `dispatch_auditor` |
| `awaiting_regression` | `regression-requested` | final Node and current preparation approval | failure → `create_repair_plan`; success → `dispatch_auditor` |
| `awaiting_auditor` | auditor dispatched | current regression receipt | wait for minimal audit verdict |
| `auditor_running` | `audit-failed` | matching correlation and fingerprint | implementation → repair; final → repair Plan |
| `auditor_running` | `audit-passed` | matching correlation and fingerprint | atomically accept and complete |
| `repair_plan_required` | `repair-registered` | new pending implementation prerequisite | await the exact repair Node |
| `awaiting_repair` | `repair-completed` | bound repair Node completed | return to preparation freshness check, then full regression |

`next-action` refreshes preparation freshness before returning an action. Before executor dispatch, a design, scaffold, validation, or test change clears acceptance candidate and approval and returns `dispatch_acceptance_designer`. Executor dispatch is the handoff boundary: after it, planned implementation and scaffold edits no longer invalidate the reviewed test contract, while requirements, design, validation, or test drift cancels execution/repair proof and returns `dispatch_acceptance_designer`. Changed implementation code invalidates regression and audit receipts, not acceptance approval.

## Fingerprints and proof ownership

Four distinct SHA-256 bindings are composed rather than conflated:

1. `design_digest`: canonical JSON of the `design` object plus requirements and architecture artifacts.
2. `scaffold_fingerprint`: declared scaffold contents for the current design digest; required only through executor dispatch.
3. `acceptance_fingerprint`: declared validation and test file contents for the current design digest.
4. `content_fingerprint`: implementation source plus declared tests used by regression.

The acceptance reviewer approves the first three. Executor dispatch consumes the scaffold freeze and retains only the stable design and acceptance bindings, because changing scaffold behavior is the executor's declared job. Regression proves only criteria mapped to commands. The final auditor approves only the tested delivery fingerprint. Audit is a state gate, not a criterion that a test command may pre-check. Changing any bound input invalidates only downstream proof; upstream design evidence remains intact.

The canonical encoder uses sorted JSON keys, UTF-8, explicit separators, sorted normalized paths, and length-delimited file bytes. No timestamp, process identity, hostname, local root, or agent identity participates in a digest.

## Module and file map

| File | Responsibility | Writable role | Dependencies |
| --- | --- | --- | --- |
| `docs/plan/acceptance-state-machine/Requirements.md` | product and role contract | native main designer | user intent |
| `docs/plan/acceptance-state-machine/Evidence.md` | observed gaps and decision evidence | native main designer | current repository |
| `docs/plan/acceptance-state-machine/Architecture.md` | design contract and symbol inventory | native main designer | requirements and evidence |
| `scripts/design_contract.py` | pure schema, canonical design digest, and ownership-overlap rules | design-state executor after scaffold | standard library only |
| `scripts/acceptance_machine.py` | pure phase/event/role transition and next-action tables | design-state executor | standard library only |
| `scripts/manifest_tool.py` | structural validation, filesystem fingerprints, correlations, effects, atomic writes, CLI | design-state executor, then ordered integration executor | pure domain modules |
| `scripts/role_contracts.py` | immutable action-to-one-reference mapping and bounded main obligation | context-isolation executor after scaffold | standard library only |
| `scripts/hook_context.py` | bounded main-session locator; never embeds delegated role text | context-isolation executor | manifest inventory and role mapping |
| `scripts/hook_tool.py` | read-only lifecycle adapter and next-action report | context-isolation executor | scope, context, state readers |
| `references/orchestration-main.md` | main design/orchestration contract | native main designer, then context executor | Plan artifacts |
| `references/acceptance-designer.md` | only the acceptance-authoring contract | native main designer, then context executor | frozen design paths |
| `references/acceptance-reviewer.md` | only the early test-quality review contract | native main designer, then context executor | design and test fingerprints |
| `references/executor.md` | only code ownership and return shape | native main designer, then context executor | approved Node design |
| `references/auditor.md` | minimal read-only PASS/findings contract | native main designer, then context executor | current regression receipt |
| `references/state-files.md` | current public schema and CLI semantics | ordered integration executor | implemented interfaces |
| `scripts/hook_config.py` | current lifecycle event inventory, bounded command configuration, and managed-entry removal | installer-hygiene executor | Hook adapter entry point |
| `scripts/install.py` | current skill payload, platform adapters, diagnosis, and Hook-only uninstall CLI | installer-hygiene executor | current skill files and Hook configuration |

Dependency direction is Hook or CLI adapter → application/state adapter → pure design and transition modules. Reference documents are data inputs and never import one another. Pure modules perform no filesystem mutation, subprocess, clock, UUID, Hook, or agent work.

## Symbol inventory

### Add `scripts/design_contract.py`

- `normalize_design_path(value: object) -> str`: return one canonical repository-relative path or raise `ValueError`.
- `validate_design_contract(design: Mapping[str, object]) -> tuple[str, ...]`: return bounded field-level issues without I/O.
- `canonical_design_bytes(design: Mapping[str, object]) -> bytes`: encode a validated contract deterministically.
- `design_digest(design: Mapping[str, object]) -> str`: SHA-256 the canonical bytes.
- `paths_overlap(left: str, right: str) -> bool`: compare normalized path components for equality or ancestry.
- `independent_ownership_issues(nodes: Sequence[Mapping[str, object]], reachable: Callable[[str, str], bool]) -> tuple[str, ...]`: detect ownership collisions only where no dependency path orders the Nodes.

No class hierarchy is added. These are stateless pure functions; composition is clearer than inheritance because no runtime subtype substitution is required.

### Modify `scripts/acceptance_machine.py`

- Extend the immutable transition table with preparation roles `acceptance_designer` and `acceptance_reviewer` and the phases/events above.
- Extend `next_action(phase: str, role: str) -> str` without adding effect logic.
- Keep `transition(phase: str, event: str, role: str) -> str` as the sole phase-selection interface.

### Modify `scripts/manifest_tool.py`

- `validated_design_contract(location: NodeLocation) -> dict[str, object]`: adapt pure issues into repository validation errors.
- `preparation_fingerprints(location: NodeLocation) -> dict[str, str]`: combine design digest with stable artifact fingerprints.
- `refresh_preparation(location: NodeLocation, node: dict[str, object]) -> dict[str, object]`: derive the safe phase after input drift without running commands.
- Extend `bounded_acceptance_payload` with one `role_reference` field only when an action delegates a role.
- Extend `dispatch_command` for `acceptance_designer` and `acceptance_reviewer`; reject the same role from approving its own output by correlation role, not by storing personal identity.
- Add `advance_acceptance_design_exit(location, dispatch_id)` and `advance_acceptance_review(location, dispatch_id, passed)`.
- Extend `advance_command` events with `acceptance-designer-exited`, `acceptance-approved`, and `acceptance-rejected`.
- Extend schema and graph validation so every new nonterminal delivery Node has a valid `design` object and independent owned paths do not overlap.
- Replace nonterminal acceptance criteria through repeated `edit-node --criterion`; remove `--add-criterion` rather than preserve two interfaces. Replacement clears downstream preparation, regression, criterion, dispatch, and audit proof atomically.

### Add `scripts/role_contracts.py`

- `reference_for_action(action: str) -> str | None`: map one current action to one repository-relative reference path.
- `bounded_main_obligation(node_id: str, phase: str, action: str) -> str`: produce a short main-agent instruction without role-template prose.
- Store mappings in `MappingProxyType`; reject unknown delegating actions rather than use a combined fallback.

### Modify Hook and skill entry files

- Session and prompt context contain only the short intent guidance after structural detection;
  they contain no Plan inventory, active Node, workspace label, or role reference.
- `hook_tool.next_action_response` returns `node_id`, `phase`, `next_action`, `role_reference`, and a bounded native-parent obligation. Stop remains read-only.
- `SKILL.md` changes the foundation order to requirements → evidence → architecture/scaffold → acceptance design/review → implementation, and links role references conditionally instead of requiring one combined file.
- `README.md`, `references/state-files.md`, and installer payload describe only the current separated interface.
- Remove `references/agent-orchestration.md`; no compatibility pointer or duplicate content remains.

### Current installer and Hook hygiene scaffold

- `scripts/install.py::CURRENT_SKILL_FILES`: one immutable repository-relative inventory containing the current state machine, design contract, role router, lifecycle modules, state reference, and all five separated role contracts.
- `scripts/install.py::uninstall_hooks(paths, agents, *, dry_run) -> list[str]`: remove Better Plan-managed lifecycle handlers only. It never removes a skill tree, plugin, unrelated setting, or unrelated Hook.
- `scripts/install.py::uninstall_hooks_command(args) -> int`: public `uninstall-hooks` adapter over the pure removal boundary.
- `scripts/hook_config.py::HOOK_TIMEOUT_SECONDS`: a single bounded timeout used by `SessionStart`, `UserPromptSubmit`, and `Stop`; no per-tool or long-running Stop exception remains.
- Cursor is not accepted by the executable Hook configuration adapter. Its current installation surface is skill-only and Hook-only uninstall is a no-op statement, not a compatibility handler.
- Removed artifacts are checked once during the migration and are not retained as constants, compatibility branches, documentation interfaces, or permanent regression tests. Current inventory validation is sufficient after atomic skill replacement.

## Agent lifetime ownership

The native agent framework exclusively owns dispatch lifetime, cancellation, and any platform timeout behavior. Better Plan does not poll a running Agent, record elapsed time, infer failure from delay, interrupt a dispatch, or create a replacement because no file has appeared. Orchestration resumes only after the correlated Agent-completion event arrives; result handling then follows the role and state transition contract.

## Interface and error contracts

- Pure validators return ordered bounded issue strings for schema errors and raise only for programmer misuse such as digesting an unvalidated contract.
- Application adapters convert issues to existing validation errors before any state write.
- Dispatch is idempotent only for the same outstanding role and current fingerprints; a different role, phase, or stale binding is rejected.
- Advance accepts only the outstanding opaque correlation. Replayed, stale, cross-role, or out-of-order events fail before file or command effects.
- Acceptance rejection persists only a safe outcome class. Reviewer findings stay in the parent conversation and never enter state.
- Hooks catch malformed input and fail open with `{}`. Valid Stop continuation may keep the main session active but cannot affect a tool call because no tool-use event is registered.

## Algorithms and data structures

- Phase lookup: immutable hash table, expected `O(1)` time and fixed memory per transition.
- Canonical design validation: one pass over fields, symbols, interfaces, edges, and paths, `O(n)` time and `O(n)` bounded issue storage.
- Ownership overlap: normalize and sort path-component tuples once, then compare adjacent ancestry candidates; `O(p log p)` time and `O(p)` memory rather than repeated all-pairs string-prefix scans.
- Dependency reachability: adjacency sets and an iterative stack with a visited set, `O(V + E)` per independent-ownership validation; cache results for the duration of one validation call only.
- Fingerprinting: streaming SHA-256 with fixed-size chunks, `O(bytes)` time and constant buffer memory.
- State persistence: validate a copied in-memory snapshot, write one temporary sibling, then atomically replace. No partially updated Plan or Node state is observable.

## Isolation, state, and concurrency

- Role context isolation is structural: separate files, one action-to-reference mapping, planned focus paths, and no shared prompt template. It does not rely on a role ignoring text it was given.
- The main agent may read all Plan artifacts because it owns synthesis. A delegated role receives one role reference and direct repository-relative artifact paths only.
- Acceptance designer and executor use declared paths as design focus and report necessary adjacent changes for native-main review. Acceptance reviewer and auditor are read-only. The state tool is the sole Plan-state writer.
- One Plan state file has a serialized mutation stream. This deliberately prevents the multi-active ambiguity that previously blocked unrelated commands.
- Independent Plans may progress concurrently. Within one Plan, sibling design can be prepared concurrently only as read-only analysis; writes and dispatch transitions remain ordered. Disjoint ownership validation preserves a future path to controlled parallel execution without changing the single-writer invariant.
- Cancellation through pause, block, skip, or intent realignment clears outstanding correlations and downstream proof. It never asks the stopped child to mutate state.

## Scaffold boundary

The architecture step precreates `scripts/design_contract.py`, `scripts/role_contracts.py`, and the five role-reference files with final interfaces and ownership language. Domain behavior remains unimplemented until reviewed acceptance tests exist. The scaffold must parse and expose signatures, but may explicitly raise `NotImplementedError`; it is a foundation artifact, not an acceptable product state.

## Migration and failure boundaries

- Completed Nodes remain immutable historical evidence. New preparation requirements apply to nonterminal and newly created delivery Nodes.
- The combined role reference is deleted once separated references are wired; no alias, redirect, versioned file, or fallback loader remains.
- Existing final audit failure remains a repair-plan event. The registered repair Node completes only after the design-first preparation implementation, role isolation, criterion replacement, installer payload, and corrected final evidence contract are current.
- Regression output, acceptance-review findings, audit findings, raw prompts, transcripts, server data, and local paths are never persisted.
- A final audit is intentionally short. If it discovers missing architecture or invalid tests, that is a preparation-gate defect and routes to a new Plan repair rather than expanding the auditor prompt.
