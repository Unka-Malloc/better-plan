# Hook Enforcement Validation Matrix

| Requirement | Focused implementation proof | Final proof |
| --- | --- | --- |
| REQ-001 | Manifest CLI/state-machine tests cover normalized platform reporting, `start` rejection, and active-node mismatch detection. | Full suite plus workspace validation. |
| REQ-002 | Schema tests cover required contract fields, role-to-scope rules, path safety, criterion indexes, and add/edit CLI construction. | Schema output and requirement-label cross-check. |
| REQ-003 | Regression tests cover all-command success, failure atomicity, criterion evidence, deterministic path fingerprints, concurrent-change rejection, and stale receipts. | Full suite verifies receipt behavior through CLI and Hook paths. |
| REQ-004 | Hook runtime tests feed Codex, Cursor, and Claude payloads and assert platform denial, no-workspace no-op, one-node regression, ambiguity continuation, failure continuation, and privacy-safe output. | Installed Hook configurations are structurally diagnosed and the full suite passes. |
| REQ-005 | Installer tests start with unrelated Hook entries, install twice, diagnose, uninstall, and prove unrelated data remains while Better Plan entries are unique and removed. | Full installer suite and dry structural doctor checks. |
| REQ-006 | Completion CLI tests prove a missing or stale receipt causes the declared regression to run and a failing command prevents completion. | End-to-end completion path in the full suite. |
| REQ-007 | Failure commands emit a sentinel string; tests prove it is absent from Hook output, state files, and evidence references. | Repository search plus full suite and plan validation. |

## Regression policy

- `implementation` Nodes run only their declared `focused` commands.
- The `final_validation` Node alone declares `full` scope and runs `python3 -m unittest discover -s tests -p 'test_*.py'` once after every implementation Node is complete.
- Hook and manifest commands never print captured test output. A developer may rerun a known-safe failing command directly when detailed diagnostics are required.
- The final Node also runs:
  - `python3 scripts/manifest_tool.py validate docs/plan --check-sources`
  - `python3 scripts/manifest_tool.py check-labels docs/plan --plan hook-enforcement`
  - a repository search confirming there is one current Hook runtime/configuration implementation and no obsolete wrapper artifacts.
