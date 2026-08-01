"""Pure interfaces for resolving one Better Plan role contract per action."""

from __future__ import annotations

from types import MappingProxyType
from typing import Final, Mapping
import re


ORCHESTRATION_MAIN_REFERENCE: Final[str] = "references/orchestration-main.md"

MAIN_ACTIONS: Final[frozenset[str]] = frozenset(
    {
        "await_designer_exit",
        "await_worker_exit",
        "main_correction_decision",
        "await_verifier_exit",
        "run_regression",
        "await_reviewer_exit",
        "main_reviewer_decision",
        "create_repair_plan",
        "await_repair_completion",
        "complete_node",
    }
)

ROLE_REFERENCES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "dispatch_designer": "references/designer.md",
        "dispatch_worker": "references/worker.md",
        "dispatch_verifier": "references/verifier.md",
        "dispatch_reviewer": "references/reviewer.md",
    }
)

# Knowledge references supplement one role contract without becoming another role.
# Designer receives the complete local catalog on every fresh dispatch so pattern
# decisions never depend on network access or inherited conversation history.
ROLE_KNOWLEDGE_REFERENCES: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        "dispatch_designer": ("references/design-patterns.md",),
    }
)

_TOKEN_RE: Final = re.compile(r"^[A-Za-z0-9._:-]+$")
_MAX_TOKEN_LEN: Final = 64


def _is_safe_token(value: str) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= _MAX_TOKEN_LEN
        and all(0x20 <= ord(ch) < 0x7F for ch in value)
        and _TOKEN_RE.fullmatch(value) is not None
    )


def reference_for_action(action: str) -> str | None:
    """Return the leaf reference for an action, otherwise none."""

    if not _is_safe_token(action) or action in MAIN_ACTIONS:
        return None
    return ROLE_REFERENCES.get(action)


def knowledge_references_for_action(action: str) -> tuple[str, ...]:
    """Return immutable local knowledge references required by one leaf action."""

    if not _is_safe_token(action) or action in MAIN_ACTIONS:
        return ()
    return ROLE_KNOWLEDGE_REFERENCES.get(action, ())


def bounded_main_obligation(node_id: str, phase: str, action: str) -> str:
    """Build a short native-parent obligation without delegated-role prose."""

    if not all(_is_safe_token(value) for value in (node_id, phase, action)):
        raise ValueError("invalid obligation input")
    if action in MAIN_ACTIONS:
        reference = ORCHESTRATION_MAIN_REFERENCE
    elif action in ROLE_REFERENCES:
        reference = ROLE_REFERENCES[action]
    else:
        raise ValueError("invalid obligation input")
    return f"Node {node_id} in phase {phase} must run action {action}, see {reference}."
