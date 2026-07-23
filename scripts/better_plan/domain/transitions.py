"""Pure transition rules for deterministic Better Plan acceptance cycles."""

from __future__ import annotations

from types import MappingProxyType
from typing import Final, Mapping, Tuple


TransitionKey = Tuple[str, str, str]


_TRANSITION_TABLE: Final[Mapping[TransitionKey, str]] = MappingProxyType(
    {
        (
            "awaiting_acceptance_design",
            "acceptance-designer-dispatched",
            "acceptance_designer",
        ): "acceptance_designer_running",
        (
            "acceptance_designer_running",
            "acceptance-designer-exited",
            "acceptance_designer",
        ): "awaiting_executor",
        (
            "acceptance_revision_required",
            "acceptance-designer-dispatched",
            "acceptance_designer",
        ): "acceptance_designer_running",
        ("awaiting_executor", "executor-dispatched", "executor"): "executor_running",
        ("correction_required", "executor-dispatched", "executor"): "executor_running",
        ("executor_running", "regression-passed", "system"): "awaiting_auditor",
        ("executor_running", "regression-failed", "system"): "correction_required",
        ("awaiting_regression", "regression-passed", "system"): "awaiting_auditor",
        ("awaiting_regression", "regression-failed", "system"): "repair_plan_required",
        ("awaiting_auditor", "auditor-dispatched", "auditor"): "auditor_running",
        ("auditor_running", "audit-failed", "implementation"): "correction_required",
        ("auditor_running", "audit-failed", "final_validation"): "repair_plan_required",
        ("auditor_running", "audit-passed", "auditor"): "accepted",
        ("repair_plan_required", "repair-registered", "final_validation"): "awaiting_repair",
        ("awaiting_repair", "repair-completed", "final_validation"): "awaiting_regression",
    }
)

_NEXT_ACTIONS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "awaiting_acceptance_design": "dispatch_acceptance_designer",
        "acceptance_designer_running": "await_acceptance_designer_exit",
        "acceptance_revision_required": "main_acceptance_decision",
        "awaiting_executor": "dispatch_executor",
        "executor_running": "await_executor_exit",
        "correction_required": "main_correction_decision",
        "awaiting_regression": "run_regression",
        "awaiting_auditor": "dispatch_auditor",
        "auditor_running": "await_auditor_verdict",
        "repair_plan_required": "create_repair_plan",
        "awaiting_repair": "await_repair_completion",
        "accepted": "complete_node",
    }
)

_ROLES: Final[frozenset[str]] = frozenset(
    {
        "executor",
        "auditor",
        "system",
        "implementation",
        "final_validation",
        "acceptance_designer",
    }
)


def transition(phase: str, event: str, role: str) -> str:
    """Return the unique next phase for a guarded state/event/role tuple."""
    try:
        return _TRANSITION_TABLE[(phase, event, role)]
    except KeyError as exc:
        raise ValueError("invalid acceptance transition") from exc


def next_action(phase: str, role: str) -> str:
    """Derive the sole orchestration action without reading or mutating external state."""
    if role not in _ROLES:
        raise ValueError("invalid acceptance role")
    try:
        return _NEXT_ACTIONS[phase]
    except KeyError as exc:
        raise ValueError("invalid acceptance phase") from exc
