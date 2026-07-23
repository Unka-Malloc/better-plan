# Planning Reachability Evidence

## Repository evidence

- `references/state-files.md` defines both `completed` and `skipped` as terminal, and the transition
  table permits no transition out of `skipped`.
- `README.md` nevertheless demonstrates `skip --reason "deferred to a follow-up plan"`, and CLI tests
  preserve that exact interpretation.
- `scripts/better_plan/adapters/manifest_cli.py::next_command` omits terminal Plans and selects only
  pending Nodes, so a future goal stored as skipped disappears from execution discovery.
- Final-validation guards intentionally ignore skipped implementation Nodes, which turns a future
  promise into a waived delivery obligation.
- `scripts/better_plan/domain/validation.py` validates prerequisite references and cycles inside one
  checkpoint array only. It also requires every prerequisite to point backward in that array.
- `scripts/better_plan/infrastructure/workspace.py` already enforces globally unique IDs, but it does
  not build a workspace-wide prerequisite graph from those IDs.
- `status_reason` is validated only as safe text, while `next` is not consulted by execution
  selection. A wait recorded in either field is therefore invisible to cycle validation.

## Behavioral deduction

The current status axis conflates lifecycle outcome with scheduling intent. The dependency model
then compounds the problem by splitting executable truth between a local graph and unstructured
prose. Separating `deferred` from terminal `skipped`, and resolving every prerequisite through the
existing globally unique Node IDs, restores one authoritative reachability model without adding a
scheduler or inferring work from Plans.
