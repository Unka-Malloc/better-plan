"""Cursor Hook protocol."""

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
    _host_event_name: str | None,
) -> dict[str, Any]:
    if event in {"session-start", "agent-complete"}:
        return {"additional_context": value}
    if event == "prompt-submit":
        return {"continue": True}
    raise HookProtocolError(f"unsupported Cursor event: {event}")


def parse_completion(payload: Mapping[str, Any]) -> CompletionSignal | None:
    if normalized_name(payload.get("tool_name")) not in {"agent", "task"}:
        return None
    return exact_completion_signal(payload)


ADAPTER = HostHookAdapter(
    name="cursor",
    events=(
        ("sessionStart", "session-start"),
        ("beforeSubmitPrompt", "prompt-submit"),
        ("postToolUse", "agent-complete"),
    ),
    config_shape="flat-json",
    skill_root_expressions=(
        "Path(os.environ.get('BETTER_PLAN_SHARED_HOME') or h/'.agents')/'skills'/'better-plan'",
        "Path(os.environ.get('CURSOR_HOME') or h/'.cursor')/'skills'/'better-plan'",
    ),
    context_encoder=encode_context,
    prompt_allow_encoder=lambda: {"continue": True},
    completion_matcher="^(Agent|Task)$",
    completion_parser=parse_completion,
)
