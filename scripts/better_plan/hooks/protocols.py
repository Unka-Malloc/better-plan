"""Stable facade over isolated native-host Hook adapters."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from . import adapters


AGENTS = tuple(adapter.name for adapter in adapters.ADAPTERS)
NESTED_CONFIG_AGENTS = frozenset(
    adapter.name for adapter in adapters.ADAPTERS if adapter.config_shape == "nested-json"
)
HookProtocolError = adapters.HookProtocolError


def host_events(agent: str) -> Mapping[str, str]:
    """Return the immutable-by-contract event mapping for one current host."""

    return adapters.get(agent).host_events()


def context_response(
    agent: str,
    event: str,
    value: str,
    host_event_name: str | None = None,
) -> dict[str, Any] | str:
    """Encode bounded lifecycle context with exactly one host adapter."""

    if event not in {"session-start", "prompt-submit", "agent-complete"}:
        raise HookProtocolError(f"unsupported event: {event}")
    return adapters.get(agent).context_response(event, value, host_event_name)


def event_matcher(agent: str, normalized_event: str) -> str | None:
    """Return the narrow native matcher for a configured completion event."""

    adapter = adapters.get(agent)
    if normalized_event not in adapter.host_events().values():
        return None
    return adapter.completion_matcher if normalized_event == "agent-complete" else None


def prompt_allow_response(agent: str) -> dict[str, Any]:
    """Return the explicit non-blocking prompt response required by one host."""

    return adapters.get(agent).prompt_allow_response()


def completion_signal(
    agent: str,
    payload: Mapping[str, Any],
) -> adapters.CompletionSignal | None:
    """Normalize one host-native final callback, or fail closed."""

    return adapters.get(agent).completion_signal(payload)


def accepts_event(agent: str, event: str, payload: Mapping[str, Any]) -> bool:
    """Apply only the selected host's native event filter."""

    return adapters.get(agent).accepts_event(event, payload)


def config_shape(agent: str) -> str:
    """Return the selected host's native configuration shape."""

    return adapters.get(agent).config_shape


def emit_empty_response(agent: str) -> bool:
    """Return whether the host requires an explicit empty JSON response."""

    return adapters.get(agent).emit_empty_response


def skill_root_expressions(agent: str) -> tuple[str, ...]:
    """Return only the selected host's portable skill discovery expressions."""

    return adapters.get(agent).skill_root_expressions


def missing_skill_response(agent: str) -> str:
    """Return the selected host's safe launcher fallback expression."""

    return adapters.get(agent).missing_skill_response
