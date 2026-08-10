"""Antigravity Hook protocol."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .base import HookProtocolError, HostHookAdapter


def encode_context(
    event: str,
    value: str,
    _host_event_name: str | None,
) -> dict[str, Any]:
    if event != "session-start":
        raise HookProtocolError(f"unsupported Antigravity event: {event}")
    return {"injectSteps": [{"ephemeralMessage": value}]}


def accepts_event(event: str, payload: Mapping[str, Any]) -> bool:
    return event != "session-start" or payload.get("invocationNum") == 0


ADAPTER = HostHookAdapter(
    name="antigravity",
    events=(("PreInvocation", "session-start"),),
    config_shape="plugin-json",
    skill_root_expressions=(
        "Path(os.environ.get('ANTIGRAVITY_HOME') or h/'.gemini'/'config')/'plugins'/'better-plan'/'skills'/'better-plan'",
    ),
    context_encoder=encode_context,
    event_filter=accepts_event,
)
