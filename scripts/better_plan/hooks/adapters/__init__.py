"""Registry of isolated native-host Hook adapters."""

from __future__ import annotations

from .base import CompletionSignal, HookProtocolError, HostHookAdapter
from .claude import ADAPTER as CLAUDE
from .codex import ADAPTER as CODEX
from .cursor import ADAPTER as CURSOR


ADAPTERS = (CODEX, CLAUDE, CURSOR)
BY_NAME = {adapter.name: adapter for adapter in ADAPTERS}


def get(name: str) -> HostHookAdapter:
    try:
        return BY_NAME[name]
    except KeyError as exc:
        raise HookProtocolError(f"unknown agent: {name}") from exc


__all__ = [
    "ADAPTERS",
    "BY_NAME",
    "CompletionSignal",
    "HookProtocolError",
    "HostHookAdapter",
    "get",
]
