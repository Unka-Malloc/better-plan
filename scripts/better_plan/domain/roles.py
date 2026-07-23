"""Pure interfaces for resolving one Better Plan role contract per action."""

from __future__ import annotations

from types import MappingProxyType
from typing import Final, Mapping
import re


ORCHESTRATION_MAIN_REFERENCE: Final[str] = "references/orchestration-main.md"

MAIN_ACTIONS: Final[frozenset[str]] = frozenset(
    {
        "await_acceptance_designer_exit",
        "main_acceptance_decision",
        "await_executor_exit",
        "main_correction_decision",
        "run_regression",
        "await_auditor_verdict",
        "create_repair_plan",
        "await_repair_completion",
        "complete_node",
    }
)

ROLE_REFERENCES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "dispatch_acceptance_designer": "references/acceptance-designer.md",
        "dispatch_executor": "references/executor.md",
        "dispatch_auditor": "references/auditor.md",
    }
)

_TOKEN_RE: Final = re.compile(r"^[A-Za-z0-9._:-]+$")
_MAX_TOKEN_LEN: Final = 64


def _is_safe_token(value: str) -> bool:
    """Validate non-empty bounded ASCII token without path control characters."""

    return (
        isinstance(value, str)
        and 0 < len(value) <= _MAX_TOKEN_LEN
        and all(ord(ch) >= 0x20 and ord(ch) < 0x7F for ch in value)
        and _TOKEN_RE.fullmatch(value) is not None
    )


def reference_for_action(action: str) -> str | None:
    """Return role reference for a leaf action, otherwise none."""
    if not _is_safe_token(action):
        return None
    if action in MAIN_ACTIONS:
        return None
    return ROLE_REFERENCES.get(action)


def bounded_main_obligation(node_id: str, phase: str, action: str) -> str:
    """Build a short native-parent obligation without delegated-role prose."""
    if not (
        _is_safe_token(node_id)
        and _is_safe_token(phase)
        and _is_safe_token(action)
    ):
        raise ValueError("invalid obligation input")

    if action in MAIN_ACTIONS:
        ref = ORCHESTRATION_MAIN_REFERENCE
    elif action in ROLE_REFERENCES:
        ref = ROLE_REFERENCES[action]
    else:
        raise ValueError("invalid obligation input")

    return (
        f"Node {node_id} in phase {phase} must run action {action}, see {ref}."
    )
