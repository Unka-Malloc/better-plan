# Agent Orchestration Evidence

## Repository evidence

- `scripts/hook_scope.py` activates host events only when every supplied directory signal resolves to one repository with exactly one structural workspace. Multiple roots, conflicting repositories, file-valued event signals, and non-repository signals fail open for **REQ-001**, **REQ-007**, and **REQ-008**. Its explicit CLI structural probe remains separate and emits only a relative workspace label.
- `scripts/hook_context.py` contains bounded, data-only comprehension, alignment, acceptance, execution, and audit obligations for the lifecycle hosts that can preserve them, grounding **REQ-001** through **REQ-008** without copying prompt or Plan prose.
- `scripts/hook_tool.py` allows Codex and Claude focused implementation Stop events to obtain a focused receipt before audit. A final-validation Stop with no current full receipt runs no command and requires an independent audit PASS before the main agent manually runs the single full contract; a current full receipt still requires final read-only acceptance. This grounds **REQ-005** and **REQ-009** without inventing audit state.
- `scripts/hook_config.py` and `scripts/install.py` configure lifecycle handlers only for Codex and Claude. Cursor remains a skill target, while installer and doctor output report its lifecycle capability gap and do not install, adapt, or verify Cursor Hooks.
- The manifest tool owns platform, prerequisite, status, regression, receipt, and completion guarantees. Agent orchestration therefore remains in the skill and supported lifecycle context instead of duplicating state mutation in Hook scripts.

## Host evidence

- Codex enables subagent workflows by default in current local clients, can delegate when project or skill instructions request it, and exposes separate worker, explorer, and default agent roles: <https://learn.chatgpt.com/docs/agent-configuration/subagents>.
- Codex command Hooks support lifecycle context, while prompt and agent Hook handler types are parsed but skipped; the parent agent must perform delegation rather than a command Hook claiming it did so: <https://learn.chatgpt.com/docs/config-file/config-reference#configtoml>.
- Claude Code provides an `Agent` tool whose subagents run in separate contexts, supports explicit sequential chaining, and documents that subagents cannot spawn more subagents: <https://code.claude.com/docs/en/subagents>.
- Claude agent-based Hooks can spawn verifiers, but that Hook type is experimental; the portable workflow should continue using command Hooks plus native parent-agent delegation: <https://code.claude.com/docs/en/hooks>.
- Cursor documents independent subagents and asynchronous delegation, but its current lifecycle surface does not provide reliable standing-context delivery: `sessionStart` additional context may be discarded, and Stop identifiers are insufficient to distinguish the main session from subagent Stops. Better Plan can install its skill but cannot honestly claim lifecycle enforcement or automatic Stop audit there: <https://cursor.com/changelog/2-5> and <https://cursor.com/docs/subagents>.

## Deductions

1. The portable contract belongs in Better Plan instructions and injected context. The active parent agent has native delegation tools; a shell Hook does not.
2. Acceptance design must precede final Node construction so acceptance cannot be reverse-engineered from completed code.
3. One execution agent receiving an ordered list matches the user's required sequential semantics and avoids write conflicts between sibling agents.
4. Stop-time audit must be fresh and read-only. Its independence is lost if the implementation agent audits itself or if the auditor is asked to repair findings.
5. Focused implementation regression may precede the independent audit. Full final-validation regression must follow an audit PASS, run manually exactly once, and be followed by final read-only acceptance because the new receipt invalidates the earlier evidence snapshot.
6. The main agent must stay alive as the stateful orchestrator: it validates plan changes, waits for agents, handles findings, and decides whether another executor pass is required.
