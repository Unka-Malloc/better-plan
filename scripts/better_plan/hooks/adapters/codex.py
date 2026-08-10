"""Codex Hook protocol: entry guidance only, exact completion stays parent-driven."""

from __future__ import annotations

from typing import Any

from .base import HookProtocolError, HostHookAdapter


def encode_context(
    event: str,
    value: str,
    _host_event_name: str | None,
) -> dict[str, Any]:
    host_event = {
        "session-start": "SessionStart",
        "prompt-submit": "UserPromptSubmit",
    }.get(event)
    if host_event is None:
        raise HookProtocolError(
            "codex completion must use the parent callback and exact spawned task name"
        )
    return {
        "hookSpecificOutput": {
            "hookEventName": host_event,
            "additionalContext": value,
        }
    }


ADAPTER = HostHookAdapter(
    name="codex",
    events=(
        ("SessionStart", "session-start"),
        ("UserPromptSubmit", "prompt-submit"),
    ),
    config_shape="nested-json",
    skill_root_expressions=(
        "Path(os.environ.get('BETTER_PLAN_SHARED_HOME') or h/'.agents')/'skills'/'better-plan'",
        "Path(os.environ.get('CODEX_HOME') or h/'.codex')/'skills'/'better-plan'",
    ),
    context_encoder=encode_context,
    prompt_allow_encoder=lambda: {},
)
