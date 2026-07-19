# Task–Plan Alignment Evidence

## Repository evidence

- `scripts/hook_scope.py` already resolves one event root to exactly one structural workspace and fails open on absent or ambiguous repositories. This is the deterministic boundary for **REQ-001**.
- `scripts/hook_tool.py` currently translates only Stop behavior. A separate context builder keeps task guidance and bounded Plan inventory out of regression and state-transition logic, grounding **REQ-002**, **REQ-003**, **REQ-004**, and **REQ-007**.
- `scripts/hook_config.py` owns only marked handlers and removes marked entries across all events before writing the current set. That ownership model supports a complete single-interface migration for **REQ-005**, **REQ-006**, and **REQ-008**.

## Host protocol evidence

- Codex documents `SessionStart`, `UserPromptSubmit`, additional context output, and bounded `Stop` continuation: <https://learn.chatgpt.com/docs/hooks>.
- Claude Code documents `SessionStart`, `UserPromptSubmit`, `additionalContext`, and `stop_hook_active`: <https://code.claude.com/docs/en/hooks>.
- Cursor documents lifecycle Hooks including `sessionStart`, `beforeSubmitPrompt`, and `stop`; the current prompt-submit response permits continuation control and a user-facing message but does not provide the session-start context field: <https://cursor.com/docs/hooks>.

## Deductions

1. Workspace existence is structural and deterministic; task-to-Plan correspondence is semantic and must use the agent's understanding of the complete latest intent.
2. Passing raw task or Plan prose through an intermediate script adds an unnecessary disclosure and prompt-injection surface. A bounded directory/status inventory is sufficient to direct the agent to inspect canonical files.
3. Session context is the safe common denominator. Codex and Claude can additionally run the comparison on every prompt; Cursor must carry the standing rule from session start until its nonblocking prompt context protocol supports the same result.
4. Planning correction must distinguish mutable work from historical delivery: pending and active Nodes can change, but terminal history requires a new Plan.
5. Generic tool interception has no role in workflow alignment. Manifest `start` remains an internal Node transition; Agent completion is consumed only after the host reports return and cannot create a user task.
