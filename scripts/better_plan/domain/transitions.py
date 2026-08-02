"""Pure transition rules for deterministic Better Plan delivery cycles."""

from __future__ import annotations

from types import MappingProxyType
from typing import Final, Mapping, Tuple


TransitionKey = Tuple[str, str, str]


_TRANSITION_TABLE: Final[Mapping[TransitionKey, str]] = MappingProxyType(
    {
        ("awaiting_designer", "designer-dispatched", "designer"): "designer_running",
        ("designer_running", "agent-complete", "designer"): "accepted",
        ("awaiting_worker", "worker-dispatched", "worker"): "worker_running",
        ("correction_required", "worker-dispatched", "worker"): "worker_running",
        ("worker_running", "agent-complete", "worker"): "awaiting_verifier",
        ("worker_running", "regression-passed", "worker"): "accepted",
        ("worker_running", "regression-failed", "worker"): "correction_required",
        ("awaiting_verifier", "verifier-dispatched", "verifier"): "verifier_running",
        ("verifier_running", "regression-passed", "verifier"): "accepted",
        ("verifier_running", "regression-failed", "verifier"): "correction_required",
        ("awaiting_reviewer", "reviewer-dispatched", "reviewer"): "reviewer_running",
        ("reviewer_running", "agent-complete", "reviewer"): "reviewer_complete",
        ("reviewer_complete", "regression-passed", "system"): "accepted",
        ("reviewer_complete", "regression-failed", "system"): "repair_plan_required",
        ("repair_plan_required", "repair-registered", "final_validation"): "awaiting_repair",
        ("awaiting_repair", "regression-passed", "system"): "accepted",
        ("awaiting_repair", "regression-failed", "system"): "repair_plan_required",
    }
)

_NEXT_ACTIONS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "awaiting_designer": "dispatch_designer",
        "designer_running": "await_designer_exit",
        "awaiting_worker": "dispatch_worker",
        "worker_running": "await_worker_exit",
        "correction_required": "main_correction_decision",
        "awaiting_verifier": "dispatch_verifier",
        "verifier_running": "await_verifier_exit",
        "awaiting_reviewer": "dispatch_reviewer",
        "reviewer_running": "await_reviewer_exit",
        "reviewer_complete": "main_reviewer_decision",
        "repair_plan_required": "create_repair_plan",
        "awaiting_repair": "await_repair_completion",
        "accepted": "complete_node",
    }
)

_ROLES: Final[frozenset[str]] = frozenset(
    {
        "designer",
        "worker",
        "verifier",
        "reviewer",
        "system",
        "group_design",
        "implementation",
        "final_validation",
    }
)


def transition(phase: str, event: str, role: str) -> str:
    """Return the unique next phase for a guarded state/event/role tuple."""

    try:
        return _TRANSITION_TABLE[(phase, event, role)]
    except KeyError as exc:
        raise ValueError("invalid delivery transition") from exc


def next_action(phase: str, role: str) -> str:
    """Derive the sole orchestration action without external state."""

    if role not in _ROLES:
        raise ValueError("invalid delivery role")
    try:
        return _NEXT_ACTIONS[phase]
    except KeyError as exc:
        raise ValueError("invalid delivery phase") from exc
