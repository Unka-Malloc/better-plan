"""Reduce one correlated leaf-agent completion into a bounded parent directive."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..domain.models import ToolError
from ..domain.transitions import next_action
from ..infrastructure.workspace import (
    active_node_locations_for_manifest,
    workspace_semantic_issues,
)
from .workflow import (
    acceptance_snapshot,
    advance_acceptance_design_exit,
    advance_executor_exit,
    automated_node_role,
)


@dataclass(frozen=True)
class AgentCompletionDirective:
    """Privacy-safe state result consumed by the parent-agent Hook response."""

    node_id: str
    phase: str
    action: str


def _outstanding_dispatch(node: dict[str, object]) -> tuple[str, str, str] | None:
    try:
        acceptance = acceptance_snapshot(node, required=True)
    except ToolError:
        return None
    phase = acceptance.get("phase")
    dispatch = acceptance.get("dispatch")
    if not isinstance(phase, str) or not isinstance(dispatch, dict):
        return None
    dispatch_id = dispatch.get("id")
    role = dispatch.get("role")
    if not isinstance(dispatch_id, str) or not isinstance(role, str):
        return None
    return phase, role, dispatch_id


def _directive(node: dict[str, object], *, action: str | None = None) -> AgentCompletionDirective | None:
    node_id = node.get("id")
    if not isinstance(node_id, str):
        return None
    try:
        acceptance = acceptance_snapshot(node, required=True)
        phase = str(acceptance["phase"])
        node_role = automated_node_role(node)
        resolved_action = action or next_action(phase, node_role)
    except (ToolError, ValueError, KeyError):
        return None
    return AgentCompletionDirective(node_id=node_id, phase=phase, action=resolved_action)


def reduce_agent_completion(manifest: Path) -> AgentCompletionDirective | None:
    """Advance objective write-role exits and report read-only verdicts to the parent.

    Exactly one active Node and one outstanding dispatch are required. This is the
    correlation boundary: Better Plan dispatches one leaf at a time, so unrelated or
    duplicate completion callbacks fail open without consuming state.
    """

    if workspace_semantic_issues(manifest):
        return None
    active = active_node_locations_for_manifest(manifest)
    if len(active) != 1:
        return None
    location = active[0]
    node = location.checkpoints_data[location.node_index]
    if not isinstance(node, dict):
        return None
    outstanding = _outstanding_dispatch(node)
    if outstanding is None:
        return None
    phase, role, dispatch_id = outstanding

    try:
        if (phase, role) == ("acceptance_designer_running", "acceptance_designer"):
            updated = advance_acceptance_design_exit(location, dispatch_id)
            return _directive(updated)
        if (phase, role) == ("executor_running", "executor"):
            updated = advance_executor_exit(location, dispatch_id)
            acceptance = acceptance_snapshot(updated, required=True)
            if acceptance.get("phase") == "correction_required":
                return _directive(updated, action="main_correction_decision")
            return _directive(updated)
        if (phase, role) == ("auditor_running", "auditor"):
            return _directive(node, action="main_audit_decision")
    except (ToolError, ValueError, KeyError, TypeError):
        return None
    return None
