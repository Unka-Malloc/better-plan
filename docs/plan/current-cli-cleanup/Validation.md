# Validation

## REQ-001 oracle

The focused durable oracle runs `tests.test_manifest_tool_cli`. The executor removes
only the obsolete negative-test function; it must retain and pass
`test_edit_node_replaces_delivery_criteria_and_clears_active_proof` and
`test_edit_node_fails_atomically_when_edit_rejected`. Together those durable current
tests prove criterion replacement, proof invalidation, and rejected-edit atomicity.

A separate one-time command scans the active surfaces `README.md`, `SKILL.md`,
`references/`, `scripts/`, and `tests/` for the deleted criterion-append syntax. It
runs only after executor exit and before audit, explicitly excludes `docs/plan/`
history, and is migration evidence only. It must never become a recurring unit test,
installer check, workspace gate, or final-validation gate.

Final validation runs the complete suite, workspace source validation, and the
current Plan's requirement-label cross-check in that order. Command receipts do not
self-approve; a fresh fingerprint-bound auditor follows.

## Final oracle

The final Node evaluates one reviewed repository fingerprint with these commands,
in this fixed order:

1. `python3 -m unittest discover -s tests -v` runs the complete unit suite exactly
   once. Its durable coverage includes current criterion replacement, proof
   invalidation, and atomic rejection of an invalid edit.
2. `python3 scripts/manifest_tool.py validate docs/plan --check-sources --no-git`
   validates the Better Plan workspace and its current source references.
3. `python3 scripts/manifest_tool.py check-labels docs/plan --plan current-cli-cleanup`
   verifies the current Plan's `REQ-001` label mapping.

The implementation Node's one-time deleted-syntax scan is migration evidence and
is not repeated by this final oracle. Passing command evidence cannot approve its
own fingerprint. After all three commands succeed, a fresh fingerprint-bound
auditor must approve the declared criteria before the final Node may complete.
