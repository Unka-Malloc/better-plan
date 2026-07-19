# Task–Plan Alignment Validation

| Requirement | Focused proof | Final proof |
| --- | --- | --- |
| REQ-001, REQ-002 | Hook tests cover structural activation, no-workspace no-op, relative context, and Codex/Claude/Cursor session response shapes. | Full suite and workspace validation. |
| REQ-003, REQ-004 | Prompt-submit tests assert semantic latest-intent, drift-correction, nonterminal-update, and terminal-new-Plan instructions. | Requirement-label check and documentation review. |
| REQ-005 | Configuration tests assert Codex/Claude session, prompt, and Stop events plus Cursor session and Stop only. | Installer doctor tests. |
| REQ-006 | Static inventory and configuration tests prove no tool-use or Cursor prompt interception is installed; Stop loop tests remain bounded. | One-time obsolete-interface search. |
| REQ-007 | Hook tests use private sentinels and assert no prompt, Plan prose, runtime path, or command output appears. | Privacy search and full suite. |
| REQ-008 | Installer tests prove idempotent current handler counts, portable commands, diagnosis, and scoped uninstall. | Full suite once. |

Focused tests run after each independently acceptable closure. The complete unit suite runs once after implementation and documentation converge, followed by Plan validation, requirement-label checking, and local-skill synchronization that leaves managed local Hook counts at zero.
