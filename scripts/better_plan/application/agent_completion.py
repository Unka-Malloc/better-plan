"""Reduce one correlated leaf-agent completion into a bounded parent directive."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..domain.models import OPAQUE_EVENT_ID_PATTERN, ToolError
from ..domain.transitions import next_action
from ..infrastructure.workspace import (
    active_node_locations_for_manifest,
    locate_node,
    workspace_manifest_lock,
    workspace_semantic_issues,
)
from .workflow import (
    acceptance_snapshot,
    advance_designer_exit,
    advance_reviewer_exit,
    advance_verifier_exit,
    advance_worker_exit,
    automated_node_role,
)


@dataclass(frozen=True)
class AgentCompletionDirective:
    """Privacy-safe state result consumed by the parent-agent Hook response."""

    node_id: str
    phase: str
    action: str


def _outstanding_dispatch(
    node: dict[str, object],
) -> tuple[str, str, str, str | None] | None:
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
    host_agent_id = dispatch.get("host_agent_id")
    if host_agent_id is not None and not isinstance(host_agent_id, str):
        return None
    return phase, role, dispatch_id, host_agent_id


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


def reduce_agent_completion(
    manifest: Path,
    *,
    agent_id: str,
    final: bool,
    node_id: str | None = None,
    expected_node_id: str | None = None,
    dispatch_id: str | None = None,
) -> AgentCompletionDirective | None:
    """Advance one exact, final, host-bound child-agent completion.

    A spawn return is not a completion boundary. The native host must report an
    unambiguous final callback whose opaque agent ID matches the ID bound to the
    outstanding dispatch. Unrelated, early, or replayed callbacks are no-ops.
    """

    if type(final) is not bool or final is not True:
        return None
    if not isinstance(agent_id, str) or not OPAQUE_EVENT_ID_PATTERN.fullmatch(agent_id):
        return None
    if node_id is not None and not isinstance(node_id, str):
        return None
    if expected_node_id is not None and not isinstance(expected_node_id, str):
        return None
    if node_id is not None and expected_node_id is not None and node_id != expected_node_id:
        return None
    if node_id is None:
        node_id = expected_node_id
    if dispatch_id is not None and (
        not isinstance(dispatch_id, str)
        or not OPAQUE_EVENT_ID_PATTERN.fullmatch(dispatch_id)
    ):
        return None

    # The lock covers the full reload/correlation/reduction sequence.  The
    # first successful callback writes its terminal transition while still
    # holding the lock, so a concurrent or replayed callback sees no dispatch.
    try:
        with workspace_manifest_lock(manifest):
            if workspace_semantic_issues(manifest):
                return None
            active = active_node_locations_for_manifest(manifest)
            if node_id is not None:
                try:
                    expected = locate_node(manifest, node_id)
                except ToolError:
                    return None
                matching = [
                    candidate
                    for candidate in active
                    if candidate.checkpoints_path.resolve()
                    == expected.checkpoints_path.resolve()
                    and candidate.node_index == expected.node_index
                ]
            else:
                matching = []
                for candidate in active:
                    candidate_node = candidate.checkpoints_data[candidate.node_index]
                    if not isinstance(candidate_node, dict):
                        continue
                    candidate_dispatch = _outstanding_dispatch(candidate_node)
                    if candidate_dispatch is None:
                        continue
                    _, _, candidate_dispatch_id, candidate_agent_id = candidate_dispatch
                    if candidate_agent_id == agent_id and (
                        dispatch_id is None or dispatch_id == candidate_dispatch_id
                    ):
                        matching.append(candidate)
            if len(matching) != 1:
                return None
            location = matching[0]
            if node_id is not None:
                if (
                    expected.checkpoints_path.resolve()
                    != location.checkpoints_path.resolve()
                    or expected.node_index != location.node_index
                ):
                    return None
            node = location.checkpoints_data[location.node_index]
            if not isinstance(node, dict):
                return None
            outstanding = _outstanding_dispatch(node)
            if outstanding is None:
                return None
            phase, role, outstanding_id, bound_agent_id = outstanding
            # An omitted Node identity is accepted only when one active
            # dispatch has the exact bound opaque agent ID. If a host supplies
            # a Node, the exact location check above is mandatory.
            if bound_agent_id != agent_id:
                return None
            if dispatch_id is not None and outstanding_id != dispatch_id:
                return None

            if (phase, role) == ("designer_running", "designer"):
                updated = advance_designer_exit(location, outstanding_id)
                return _directive(updated)
            if (phase, role) == ("worker_running", "worker"):
                updated = advance_worker_exit(location, outstanding_id)
                acceptance = acceptance_snapshot(updated, required=True)
                if acceptance.get("phase") == "correction_required":
                    return _directive(updated, action="main_correction_decision")
                return _directive(updated)
            if (phase, role) == ("verifier_running", "verifier"):
                updated = advance_verifier_exit(location, outstanding_id)
                if acceptance_snapshot(updated, required=True).get("phase") == "correction_required":
                    return _directive(updated, action="main_correction_decision")
                return _directive(updated)
            if (phase, role) == ("reviewer_running", "reviewer"):
                updated = advance_reviewer_exit(location, outstanding_id)
                return _directive(updated, action="main_reviewer_decision")
    except Exception:
        # A callback process may fail anywhere before its final state write.
        # The lock is released by the context manager and the untouched
        # dispatch remains retryable; host hooks receive a bounded no-op.
        return None
    return None
