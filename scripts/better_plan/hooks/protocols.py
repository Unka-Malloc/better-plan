"""Host-specific guidance event names and response encoders."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any


AGENTS = ("codex", "claude", "cursor")
NESTED_CONFIG_AGENTS = frozenset({"codex", "claude"})
HOST_EVENTS: dict[str, dict[str, str]] = {
    "codex": {
        "SessionStart": "session-start",
        "UserPromptSubmit": "prompt-submit",
        "PostToolUse": "agent-complete",
    },
    "claude": {
        "SessionStart": "session-start",
        "UserPromptSubmit": "prompt-submit",
        "PostToolUse": "agent-complete",
    },
    "cursor": {
        "sessionStart": "session-start",
        "beforeSubmitPrompt": "prompt-submit",
        "postToolUse": "agent-complete",
    },
}
AGENT_COMPLETION_MATCHERS = {
    "codex": "^Agent$",
    "claude": "^Agent$",
    "cursor": "^(Agent|Task)$",
}


class HookProtocolError(ValueError):
    """Raised when a lifecycle response cannot be encoded for a host."""


def host_events(agent: str) -> Mapping[str, str]:
    """Return the immutable-by-contract event mapping for one current host."""
    if agent not in AGENTS:
        raise HookProtocolError(f"unknown agent: {agent}")
    return MappingProxyType(HOST_EVENTS[agent].copy())


def context_response(agent: str, event: str, value: str) -> dict[str, Any]:
    """Encode bounded lifecycle context for one host."""
    host_events(agent)
    if event not in {"session-start", "prompt-submit", "agent-complete"}:
        raise HookProtocolError(f"unsupported event: {event}")
    if event == "session-start":
        if agent == "cursor":
            return {"additional_context": value}
        if agent in {"codex", "claude"}:
            return {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": value,
                }
            }
    if event == "prompt-submit":
        if agent in {"codex", "claude"}:
            return {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": value,
                }
            }
        if agent == "cursor":
            raise HookProtocolError("cursor prompt-submit must be handled by prompt_allow_response")
    if event == "agent-complete":
        if agent == "cursor":
            return {"additional_context": value}
        if agent in {"codex", "claude"}:
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": value,
                }
            }
    raise HookProtocolError(f"unsupported event for {agent}: {event}")


def event_matcher(agent: str, normalized_event: str) -> str | None:
    """Return the narrow native matcher for an event, when one is required."""
    host_events(agent)
    if normalized_event == "agent-complete":
        return AGENT_COMPLETION_MATCHERS[agent]
    return None


def prompt_allow_response(agent: str) -> dict[str, Any]:
    """Return the explicit non-blocking prompt response required by a host."""
    if agent == "cursor":
        return {"continue": True}
    if agent in {"codex", "claude"}:
        return {}
    raise HookProtocolError(f"unknown agent: {agent}")
