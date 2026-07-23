# Planning Reachability Validation

## Executable acceptance cases

### PR-S01 — Defer, observe, and explicitly reactivate

- Path: `tests/test_planning_reachability.py`
- Observation target: `defer`, `activate`, `status --json`, `next --json`, Plan derivation.
- Preconditions: one valid pending foundation Node with completed prerequisites.
- Action: defer it with a safe reason, query status and execution selection, reject direct start,
  then activate it.
- Observable result: Node and Plan become `deferred`; status exposes the bounded goal/reason; no
  execution candidate exists; activation returns the Node to reason-free `pending`.
- Oracle: the same Node ID becomes eligible only after explicit activation. A later terminal skip
  cannot be activated.
- Maps to: REQ-001, REQ-005, REQ-006; criteria 0 and 4; `deferred_lifecycle`.

### PR-N01 — Terminal skip cannot mean future work

- Path: `tests/test_planning_reachability.py`, `tests/test_acceptance_state_machine.py`
- Observation target: status transition graph, CLI skip/activate rejection, public lifecycle prose.
- Preconditions: a pending or active delivery has been explicitly removed from current scope.
- Action: skip it with a waiver reason, query its action, attempt activation, and inspect guidance.
- Observable result: skipped is terminal, has action `none`, clears stale delivery proof, and rejects
  activation; guidance uses defer/activate for future scheduling.
- Oracle: no public `skip` example or role contract describes follow-up deferral.
- Maps to: REQ-001, REQ-002; criteria 0, 1, and 4; `deferred_lifecycle`.

### PR-B01 — Deferred obligations cannot pass final delivery

- Path: `tests/test_planning_reachability.py`, `tests/test_manifest_tool_state_machine.py`
- Observation target: final-validation dispatch guard and `derive_plan_status`.
- Preconditions: an implementation Node is deferred and a final-validation Node is pending in the
  same Plan.
- Action: validate the workspace, attempt final-validation dispatch, and synchronize Plan status.
- Observable result: the workspace structure remains valid, dispatch is rejected as unfinished
  implementation work, and the Plan remains `deferred`.
- Oracle: neither Plan completion nor final validation treats deferred work as terminal.
- Maps to: REQ-002; criterion 1; `deferred_lifecycle`.

### PR-S02 — Cross-Plan prerequisites control eligibility

- Path: `tests/test_planning_reachability.py`, `tests/test_manifest_tool_cli.py`
- Observation target: workspace dependency index, `validate`, `next`, and foundation start.
- Preconditions: two Plans have globally unique Nodes and the second depends on the first.
- Action: validate, query next, reject premature dependent start, complete the prerequisite, and
  query next again.
- Observable result: the cross-Plan edge validates, dependent work is initially hidden/rejected,
  then becomes eligible after prerequisite completion.
- Oracle: validate, start, and next agree on the same global Node status without array-order rules.
- Maps to: REQ-003, REQ-005; criterion 2; `workspace_dependency_graph`.

### PR-N02 — Cross-Plan cycles fail before mutation or dispatch

- Path: `tests/test_planning_reachability.py`
- Observation target: `dependency_cycle_path`, workspace graph validation, `rewire` atomicity.
- Preconditions: an acyclic two-Plan workspace and a proposed edge that closes its cycle.
- Action: exercise a 4097-Node pure graph to prove non-recursive traversal, then propose the
  cross-Plan cycle through `rewire`.
- Observable result: the pure function returns an exact closed path; rewiring reports the logical
  cycle and returns nonzero.
- Oracle: Manifest and both checkpoint files remain byte-identical after rejection; diagnostics do
  not contain the temporary root.
- Maps to: REQ-003, REQ-004, REQ-005, REQ-006; criteria 2, 3, and 4;
  `workspace_dependency_graph`.

### PR-P01 — Reporting stays bounded and private

- Path: `tests/test_planning_reachability.py`
- Observation target: deferred status payload and dependency error text.
- Preconditions: fixture summaries pass the existing bounded safe-summary validator.
- Action: query deferred status and trigger an atomic cycle rejection.
- Observable result: outputs contain only logical IDs, relative labels, and safe summaries.
- Oracle: the temporary absolute root and command output are absent.
- Maps to: REQ-006; criterion 4; reporting boundary.

## Coverage mapping

| Contract | Cases |
| --- | --- |
| deferred lifecycle | PR-S01, PR-N01, PR-B01 |
| global prerequisite resolution | PR-S02, PR-N02 |
| iterative cycle detection | PR-N02 |
| atomic mutation guard | PR-N02 |
| final-validation obligation | PR-B01 |
| bounded reporting | PR-P01 |

## Focused regression

Run the dedicated planning-reachability tests plus the existing manifest state-machine, CLI,
acceptance, and orchestration contract suites. Run the complete repository regression only once
after the capability passes focused review.
