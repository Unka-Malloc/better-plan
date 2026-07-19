# Lightweight Capability Lifecycle Validation

## Selected observation dimensions

The cases below use only dimensions justified by this Node: `success` for deterministic routing,
`boundary` for lifecycle termination and quiet waiting, `negative` for preventing mechanical
acceptance rejection, `fingerprint` for preparation drift, and `privacy` for generic bounded
guidance. `replay` is intentionally omitted because this change introduces no retry, idempotency,
or concurrent-write interface.

## Executable acceptance tests and Validation mapping

### success

#### LC-S01 — Rejected acceptance returns a decision but remains explicitly revisable

- `path`: `tests/test_acceptance_state_machine.py`, `tests/test_manifest_tool_cli.py`
- Observation: `next_action`, `acceptance_revision_required`, `dispatch --role acceptance_designer`
- Preconditions: the reviewer has rejected acceptance for one enrolled implementation Node.
- Action: query `next-action`, then have the native main explicitly dispatch an acceptance designer
  for that same Node; submit the designer exit, dispatch a fresh reviewer, approve the revised
  acceptance, and dispatch the executor authorized for that Node.
- Observable result: the query returns `main_acceptance_decision`; the explicit revision traverses
  `acceptance_designer_running` to reviewer approval and `dispatch_executor` for the same Node.
- Oracle: no query automatically selects the designer, the explicit same-Node revision path reaches
  execution, and a second eligible pending Node remains byte-for-byte unchanged throughout.

#### LC-S02 — Initial enrollment still starts acceptance design

- `path`: `tests/test_acceptance_state_machine.py`, `tests/test_manifest_tool_cli.py`
- Observation: `implicit_acceptance_snapshot`, `next-action`
- Preconditions: a valid pending implementation Node has design and acceptance paths but no
  `acceptance` mapping.
- Action: query `next-action`.
- Observable result: the action is `dispatch_acceptance_designer` and the query does not invent a
  revision decision.
- Oracle: first entry and revision are distinguishable without a compatibility field.

#### LC-S03 — Main acceptance decisions resolve to the main contract

- `path`: `tests/test_role_contracts.py`
- Observation: `MAIN_ACTIONS`, `reference_for_action`, `bounded_main_obligation`
- Preconditions: action is `main_acceptance_decision` for a safe Node and phase token.
- Action: resolve its role reference and bounded obligation.
- Observable result: the action has no leaf reference; its obligation names only
  `references/orchestration-main.md`.
- Oracle: the decision cannot be mistaken for `dispatch_acceptance_designer`.

### boundary

#### LC-B01 — One user-visible capability owns one terminal lifecycle

- `path`: `tests/test_orchestration_workflow.py`
- Observation: `SKILL.md`, `references/orchestration-main.md`
- Preconditions: Better Plan has been selected for an explicit implementation request.
- Action: inspect the main lifecycle guidance.
- Observable result: it identifies one user-visible capability with one lifecycle and states that
  completion does not select or start a next/different Node automatically.
- Oracle: adjacent findings and possible follow-up capabilities return to native-main judgment.

#### LC-B02 — Unchanged delegated state is quiet by heuristic guidance only

- `path`: `tests/test_orchestration_workflow.py`
- Observation: main and skill waiting guidance.
- Preconditions: a delegated child is still owned by the host and its state has not changed.
- Action: inspect the waiting contract.
- Observable result: it recommends no repeated unchanged-status report and explicitly labels this
  communication heuristic as neither timing nor polling nor intervention in the child lifecycle.
- Oracle: the rule is not an execution, completion, or failure gate; no fixed-duration policy
  appears, and child lifetime remains owned by the host framework.

#### LC-B03 — Terminal completion does not enroll an adjacent eligible Node

- `path`: `tests/test_manifest_tool_cli.py`
- Observation: `audit-passed`, terminal `next-action`, untouched pending Node serialization.
- Preconditions: two implementation Nodes are eligible and pending, but the native main selects
  only one for the current user-visible capability. Their fixture-owned, scaffold, and acceptance
  paths are disjoint so the case reaches lifecycle routing instead of the ownership validator.
- Action: drive the selected Node through acceptance, execution, focused regression, and
  `audit-passed`, then query that completed Node's next action.
- Observable result: the selected Node is `completed` with terminal action `none`; the other Node
  remains pending and has no acceptance state or dispatch.
- Oracle: the other Node's serialized bytes are unchanged, so terminal completion cannot start a
  second lifecycle.

### negative

#### LC-N01 — Acceptance categories are a risk catalogue, not a rejection checklist

- `path`: `tests/test_orchestration_workflow.py`
- Observation: `references/acceptance-designer.md`, `references/acceptance-reviewer.md`
- Preconditions: a Node has observable requirements and material risks that do not use every
  candidate dimension.
- Action: inspect the designer and reviewer role contracts.
- Observable result: one explicit designer clause names all six dimensions as candidates and says
  to select only those justified by applicable Node risk; one explicit reviewer clause forbids
  rejection solely because an irrelevant or inapplicable dimension is omitted.
- Oracle: neither role can manufacture tests or findings merely to populate a category.

### fingerprint

#### LC-F01 — Drift in an enrolled lifecycle parks for main judgment

- `path`: `tests/test_acceptance_state_machine.py`, `tests/test_manifest_tool_cli.py`
- Observation: `refresh_preparation`, `invalidate_preparation_after_plan_edit`
- Preconditions: acceptance preparation was previously enrolled and its design, scaffold,
  acceptance path, or edited criteria fingerprint changes.
- Action: query `next-action` or submit the correlated executor exit after the change.
- Observable result: stale proof and dispatch data are cleared, phase becomes
  `acceptance_revision_required`, and action becomes `main_acceptance_decision`.
- Oracle: the state never falls back to automatic `dispatch_acceptance_designer`; attempt history
  remains bounded to the same Node.

### privacy

#### LC-P01 — Lifecycle guidance stays generic and bounded

- `path`: `tests/test_orchestration_workflow.py`, `tests/test_hook_tool.py`
- Observation: role guidance and `INTENT_GUIDANCE`.
- Preconditions: a supported session or prompt Hook detects a structured workspace.
- Action: inspect the exact injected context and generic role contracts.
- Observable result: the short Hook context carries the one-capability boundary without a fixed
  duration, and lifecycle guidance contains no concrete project, model, provider, client, or
  operating-system routing policy.
- Oracle: context remains equal to `INTENT_GUIDANCE`; prompt/Plan content, absolute paths, machine
  identity, secrets, and backend runtime data are not copied into it.

## Coverage mapping

| Design object | Cases |
| --- | --- |
| `next_action` | LC-S01, LC-S02 |
| `refresh_preparation` | LC-F01 |
| `invalidate_preparation_after_plan_edit` | LC-F01 |
| `INTENT_GUIDANCE` | LC-B01, LC-P01 |
| `capability_lifecycle_boundary` | LC-B01, LC-B02, LC-B03, LC-P01 |
| `acceptance_revision_routing` | LC-S01, LC-S03, LC-F01 |
| `risk_based_acceptance` | LC-N01 |
| error: adjacent scope returns to native main | LC-B01 |
| error: invalid phase/role remains bounded | LC-S01, existing guarded-transition assertions |
| error: concrete proof gaps do not expand scope | LC-N01 |
| decision: reuse one Node UUID and acceptance mapping | LC-S01, LC-S02, LC-B03, LC-F01 |
| decision: constant-time action lookup | LC-S01 |
| decision: main-owned state/scope judgment | LC-B01, LC-B03, LC-F01 |
| decision: role isolation and repository neutrality | LC-S03, LC-P01 |
| decision: host-owned child lifetime | LC-B02 |
| decision: terminal lifecycle does not select adjacent work | LC-B03 |
| test seam: pure next-action lookup | LC-S01, LC-S02 |
| test seam: stale enrolled preparation refresh | LC-F01 |
| test seam: main versus leaf role routing | LC-S03 |
| test seam: generic Hook guidance | LC-P01 |
| test seam: risk-based acceptance prose | LC-N01 |

## Design gaps

None blocking. Quiet waiting is intentionally observable only as heuristic guidance because child
lifetime and progress delivery belong to the host framework; adding a timer, polling test, or
execution gate would contradict REQ-006.
