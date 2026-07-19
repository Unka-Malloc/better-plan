# Hook Safety Validation

| Requirement | Focused proof | Final proof |
| --- | --- | --- |
| REQ-001, REQ-002 | Dedicated detector and Hook tests cover one repository, no workspace, multiple workspaces, multiple Nodes, malformed state, ambiguous roots, and recovery commands. | Full suite. |
| REQ-003 | Host-specific Stop payload tests prove the second callback is an empty response. | Full suite. |
| REQ-004 | Existing state-machine tests continue to prove platform and regression gates without Hooks. | Plan validation and full suite. |
| REQ-005 | Manifest CLI tests prove relative paths, digested command evidence, discarded output, and safe errors. | Static path/privacy scan. |
| REQ-006 | Installer tests prove automatic managed delivery enters through the detector and scoped removal preserves unrelated handlers. | Installed local handler count remains zero for this requested uninstall. |
| REQ-007 | One-time repository search proves the wrapper, aliases, and fallback-removal gate are absent. | Static inventory. |
| REQ-008 | Focused host tests use current wire fields. | Full suite once. |

The final regression runs the complete unit suite once, validates all plan state and requirement labels, and performs a one-time static search for removed interfaces and concrete local paths.
