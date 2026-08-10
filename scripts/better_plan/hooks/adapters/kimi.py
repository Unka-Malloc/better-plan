"""Kimi Code Hook protocol."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .base import (
    CompletionSignal,
    HookProtocolError,
    HostHookAdapter,
    exact_completion_signal,
    nonempty_string,
)


def encode_context(event: str, value: str, _host_event_name: str | None) -> str:
    if event not in {"session-start", "prompt-submit", "agent-complete"}:
        raise HookProtocolError(f"unsupported Kimi event: {event}")
    return value


def parse_completion(payload: Mapping[str, Any]) -> CompletionSignal | None:
    if not nonempty_string(payload.get("agent_name")):
        return None
    return exact_completion_signal(payload)


ADAPTER = HostHookAdapter(
    name="kimi",
    events=(
        ("SessionStart", "session-start"),
        ("UserPromptSubmit", "prompt-submit"),
        ("SubagentStop", "agent-complete"),
    ),
    config_shape="toml",
    skill_root_expressions=(
        "Path(os.environ.get('BETTER_PLAN_SHARED_HOME') or h/'.agents')/'skills'/'better-plan'",
        "Path(os.environ.get('KIMI_CODE_HOME') or h/'.kimi-code')/'skills'/'better-plan'",
    ),
    context_encoder=encode_context,
    completion_parser=parse_completion,
    emit_empty_response=False,
    missing_skill_response="None",
)
