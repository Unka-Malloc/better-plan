# Progressive Workflow Disclosure Architecture

## Disclosure boundary

`scripts/better_plan/hooks/context.py::INTENT_GUIDANCE` and
`agents/openai.yaml::interface.default_prompt` are entrance surfaces. They state only:

1. coding and explicit implementation use Better Plan;
2. all other work follows the user's request through the native workflow.

They do not summarize how Better Plan executes. `SKILL.md` remains the canonical workflow entry
after activation. It routes the native main to `references/orchestration-main.md`, and the selected
lifecycle phase loads exactly one of the acceptance designer, executor, or auditor references.
Cross-phase policy remains in the Skill and native-main contract: the executor owns implementation
and ordinary build errors but does not run the focused regression itself; the correlated lifecycle
boundary runs that regression after executor exit.

## Files and interfaces

- `scripts/better_plan/hooks/context.py`
  - continues to return one static, privacy-safe string for session and prompt events;
  - removes lifecycle implementation policy from that string.
- `agents/openai.yaml`
  - exposes the same entrance-only rule when the Skill is selected.
- `SKILL.md` and `references/*.md`
  - retain the complete workflow without importing it into entry guidance.
- `README.md`
  - documents the progressive-disclosure boundary.
- `tests/test_hook_tool.py` and `tests/test_orchestration_workflow.py`
  - prove both absence at entry and retention after activation.

## Design decisions

- Composition: static activation routing followed by Skill and role disclosure.
- Algorithm and data structure: one constant string; no parsing, classifier, cache, or new state.
- Isolation: entrance tests reject lifecycle vocabulary, while workflow tests assert that the
  canonical Skill and role references retain their duties.
- Compatibility: Hook event mapping, payload encoding, detector gating, and fail-open behavior are
  unchanged.

## Non-goals

- No state-machine, installer, host configuration, or role behavior change.
- No runtime prompt classification beyond the instruction given to the agent.
- No compatibility copy of the former expanded entry prompt.
