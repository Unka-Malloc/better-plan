"""Shared types for isolated native-host Hook adapters."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any


class HookProtocolError(ValueError):
    """Raised when a native host response cannot be encoded safely."""


@dataclass(frozen=True)
class CompletionSignal:
    """One host completion signal normalized for the shared reducer."""

    agent_id: str
    target_id: str | None
    dispatch_id: str | None


ContextEncoder = Callable[[str, str, str | None], dict[str, Any] | str]
PromptAllowEncoder = Callable[[], dict[str, Any]]
CompletionParser = Callable[[Mapping[str, Any]], CompletionSignal | None]
EventFilter = Callable[[str, Mapping[str, Any]], bool]


@dataclass(frozen=True)
class HostHookAdapter:
    """Complete Hook boundary owned by one native host."""

    name: str
    events: tuple[tuple[str, str], ...]
    config_shape: str
    skill_root_expressions: tuple[str, ...]
    context_encoder: ContextEncoder
    prompt_allow_encoder: PromptAllowEncoder | None = None
    completion_matcher: str | None = None
    completion_parser: CompletionParser | None = None
    event_filter: EventFilter | None = None
    emit_empty_response: bool = True
    missing_skill_response: str = "print('{}')"

    def host_events(self) -> Mapping[str, str]:
        return MappingProxyType(dict(self.events))

    def context_response(
        self,
        event: str,
        value: str,
        host_event_name: str | None = None,
    ) -> dict[str, Any] | str:
        return self.context_encoder(event, value, host_event_name)

    def prompt_allow_response(self) -> dict[str, Any]:
        if self.prompt_allow_encoder is None:
            raise HookProtocolError(f"prompt allow response is unsupported for {self.name}")
        return self.prompt_allow_encoder()

    def completion_signal(self, payload: Mapping[str, Any]) -> CompletionSignal | None:
        if self.completion_parser is None:
            return None
        return self.completion_parser(payload)

    def accepts_event(self, event: str, payload: Mapping[str, Any]) -> bool:
        return self.event_filter is None or self.event_filter(event, payload)


def nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def normalized_name(value: Any) -> str:
    if not nonempty_string(value):
        return ""
    return str(value).replace("_", "").replace("-", "").lower()


def exact_completion_signal(payload: Mapping[str, Any]) -> CompletionSignal | None:
    """Read the common exact-correlation fields after host-specific validation."""

    agent_id = payload.get("agent_id")
    if not nonempty_string(agent_id) or payload.get("final") is not True:
        return None
    target_id = payload.get("target_id") if "target_id" in payload else None
    dispatch_id = payload.get("dispatch_id") if "dispatch_id" in payload else None
    if target_id is not None and not nonempty_string(target_id):
        return None
    if dispatch_id is not None and not nonempty_string(dispatch_id):
        return None
    return CompletionSignal(
        agent_id=str(agent_id),
        target_id=str(target_id) if target_id is not None else None,
        dispatch_id=str(dispatch_id) if dispatch_id is not None else None,
    )
