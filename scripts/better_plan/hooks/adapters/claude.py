"""Claude Code Hook protocol."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .base import (
    CompletionSignal,
    HookProtocolError,
    HostHookAdapter,
    exact_completion_signal,
    normalized_name,
)


def encode_context(
    event: str,
    value: str,
    host_event_name: str | None,
) -> dict[str, Any]:
    host_event = {
        "session-start": "SessionStart",
        "prompt-submit": "UserPromptSubmit",
        "agent-complete": "SubagentStop",
    }.get(event)
    if host_event is None:
        raise HookProtocolError(f"unsupported Claude event: {event}")
    if event == "agent-complete" and isinstance(host_event_name, str) and host_event_name.strip():
        host_event = host_event_name
    return {
        "hookSpecificOutput": {
            "hookEventName": host_event,
            "additionalContext": value,
        }
    }


def parse_completion(payload: Mapping[str, Any]) -> CompletionSignal | None:
    if normalized_name(payload.get("hook_event_name")) != "subagentstop":
        return None
    return exact_completion_signal(payload)


ADAPTER = HostHookAdapter(
    name="claude",
    events=(
        ("SessionStart", "session-start"),
        ("UserPromptSubmit", "prompt-submit"),
        ("SubagentStop", "agent-complete"),
    ),
    config_shape="nested-json",
    skill_root_expressions=(
        "Path(os.environ.get('CLAUDE_HOME') or h/'.claude')/'skills'/'better-plan'/'skills'/'better-plan'",
    ),
    context_encoder=encode_context,
    prompt_allow_encoder=lambda: {},
    completion_matcher="^Agent$",
    completion_parser=parse_completion,
)
