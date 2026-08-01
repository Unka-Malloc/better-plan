"""Workflow layer for Better Plan workflow state."""

from __future__ import annotations

from typing import Any
from pathlib import Path
import argparse
import json
from ..domain.models import ACCEPTANCE_PREPARATION_FIELDS, ACCEPTANCE_STABLE_PREPARATION_FIELDS, AUTOMATED_NODE_ROLES, GIT_SHA_PATTERN, OPAQUE_EVENT_ID_PATTERN, REGRESSION_NODE_ROLES, SHA256_PATTERN, ToolError, UUID4_PATTERN, WORKFLOW_STATE_MACHINE, expected_regression_scope, generate_id, is_string_list, safe_summary_issue
from ..domain.roles import knowledge_references_for_action as _knowledge_references_for_action, reference_for_action as _reference_for_action
from ..domain.transitions import next_action as acceptance_next_action, transition as acceptance_transition
from ..infrastructure.regression import current_platform, ensure_node_regression, evidence_timestamp, platform_matches, preparation_fingerprints, regression_receipt_status, run_node_regression, run_regression_at_location as _run_regression_at_location, validated_design_contract, validated_regression_contract
from ..infrastructure.workspace import NodeLocation as _NodeLocation, capability_scope_for_plan, ensure_location_is_valid, locate_node, project_root_for, relative_path_label, workspace_manifest_lock, workspace_manifest_path, workspace_node_statuses, write_location_and_sync_plan


def run_node_mutation(
    root: str,
    node_id: str,
    target: str,
    *,
    reason: str | None = None,
    delivered: str | None = None,
    require_current: str | None = None,
) -> list[str]:
    manifest = workspace_manifest_path(Path(root))
    location = locate_node(manifest, node_id)
    node = location.checkpoints_data[location.node_index]

    current = node.get("status")
    if not WORKFLOW_STATE_MACHINE.is_status(current):
        raise ToolError(
            f"{location.checkpoints_path.name}: node[{location.node_index}].status is invalid; "
            "fix the state file before transitioning"
        )
    current_status = str(current)
    if require_current is not None and current_status != require_current:
        raise ToolError(f"node {node_id}: this command requires an {require_current!r} node; current status is {current_status!r}")
    if not WORKFLOW_STATE_MACHINE.can_transition(current_status, target):
        allowed = ", ".join(sorted(WORKFLOW_STATE_MACHINE.transitions[current_status]))
        raise ToolError(f"node {node_id}: cannot transition from {current_status!r} to {target!r}; allowed targets: {allowed}")

    normalized_reason: str | None = None
    if target in {"blocked", "deferred", "skipped"}:
        if reason is None or not reason.strip():
            raise ToolError(f"a non-empty --reason is required to mark a node {target}")
        reason_issue = safe_summary_issue(reason)
        if reason_issue is not None:
            raise ToolError(f"--reason {reason_issue}")
        normalized_reason = reason.strip()
    elif target == "pending" and reason is not None and reason.strip():
        reason_issue = safe_summary_issue(reason)
        if reason_issue is not None:
            raise ToolError(f"--reason {reason_issue}")
        normalized_reason = reason.strip()

    if target in {"blocked", "deferred", "skipped"} and current_status == target:
        if node.get("status_reason") == normalized_reason:
            return [f"OK: node {node_id} remains {target}"]
        raise ToolError(
            f"node {node_id}: already {target}; an idempotent repeat must use the existing reason exactly"
        )

    if target == "in_progress":
        declared_platform = node.get("platform")
        actual_platform = current_platform()
        if not platform_matches(declared_platform, actual_platform):
            raise ToolError(
                f"node {node_id}: platform {declared_platform!r} does not match current runtime {actual_platform!r}"
            )
        required_scope = expected_regression_scope(node.get("role"))
        if required_scope is not None and not isinstance(node.get("regression"), dict):
            raise ToolError(
                f"node {node_id}: {node.get('role')} work requires a machine-readable {required_scope} regression contract before start"
            )
        if node.get("role") == "final_validation":
            unfinished = [
                str(entry.get("id"))
                for entry in location.checkpoints_data
                if isinstance(entry, dict)
                and entry.get("role") == "implementation"
                and entry.get("status") not in {"completed", "skipped"}
            ]
            if unfinished:
                raise ToolError(
                    f"node {node_id}: final_validation cannot start until every non-skipped implementation node is completed: "
                    f"{', '.join(unfinished)}"
                )
        for entry in location.checkpoints_data:
            if isinstance(entry, dict) and entry.get("status") == "in_progress" and entry.get("id") != node_id:
                state_label = relative_path_label(
                    location.checkpoints_path,
                    project_root_for(location.manifest.parent),
                )
                raise ToolError(
                    f"node {entry.get('id')} is already in_progress in {state_label}; "
                    f"pause it with `pause {entry.get('id')}` to yield, or complete/block it, before starting {node_id}"
                )
        statuses = workspace_node_statuses(manifest)
        prerequisites = node.get("prerequisites")
        if not is_string_list(prerequisites):
            raise ToolError(f"node {node_id}: prerequisites must be an array")
        if any(statuses.get(ref) != "completed" for ref in prerequisites):
            raise ToolError(
                f"node {node_id}: prerequisites must be completed before the node starts"
            )
        if current_status != "in_progress" and isinstance(node.get("regression"), dict):
            node["regression"].pop("last_pass", None)

    if target == "completed" and expected_regression_scope(node.get("role")) is not None:
        fresh, reason = regression_receipt_status(location)
        if not fresh:
            raise ToolError(f"node {node_id}: cannot complete without a current passing regression receipt: {reason}")

    normalize_delivery_administrative_transition(node, target)

    node["status"] = target
    if target in {"blocked", "deferred", "skipped"}:
        assert normalized_reason is not None
        node["status_reason"] = normalized_reason
    elif target == "pending" and normalized_reason is not None:
        node["status_reason"] = normalized_reason
    else:
        node.pop("status_reason", None)
    if delivered is not None:
        commit = node.get("commit")
        if not isinstance(commit, dict):
            raise ToolError(f"node {node_id}: commit must be an object before recording --delivered")
        commit["delivered"] = delivered

    messages = [f"OK: node {node_id} {current_status} -> {target}"]
    messages.extend(write_location_and_sync_plan(location))
    return messages


def refresh_preparation(location: _NodeLocation, node: dict[str, Any]) -> dict[str, Any]:
    """Invalidate stale preparation without automatically re-running Designer or Reviewer."""

    acceptance = acceptance_snapshot(node)
    phase = str(acceptance.get("phase"))
    role = node.get("role")
    if phase in {"awaiting_designer", "awaiting_worker", "awaiting_reviewer", "accepted"}:
        return acceptance

    current = preparation_fingerprints(location)
    if phase == "designer_running":
        dispatch = acceptance.get("dispatch")
        stale = not isinstance(dispatch, dict) or dispatch.get("design_digest") != current["design_digest"]
    else:
        fields = ACCEPTANCE_STABLE_PREPARATION_FIELDS if role == "implementation" else ACCEPTANCE_PREPARATION_FIELDS
        stale = any(acceptance.get(field) != current[field] for field in fields)
    if not stale:
        return acceptance

    clear_regression_proof(node)
    if node.get("status") not in {"blocked", "deferred"}:
        node["status"] = "pending"
        node.pop("status_reason", None)
    if role == "group_design":
        reset_phase = "awaiting_designer"
    elif role == "implementation":
        reset_phase = "awaiting_worker"
    else:
        reset_phase = "reviewer_complete" if isinstance(acceptance.get("review"), dict) else "awaiting_reviewer"
    reset = {"phase": reset_phase, "attempt": int(acceptance.get("attempt", 0)), "outcome": "none"}
    if isinstance(acceptance.get("review"), dict) and role == "final_validation":
        reset["review"] = acceptance["review"]
        reset.update({field: current[field] for field in ACCEPTANCE_PREPARATION_FIELDS})
    node["acceptance"] = reset
    return reset


def automated_node_role(node: dict[str, Any]) -> str:
    role = node.get("role")
    if role not in AUTOMATED_NODE_ROLES:
        raise ToolError("delivery commands require a group_design, implementation, or final_validation node")
    return str(role)


def implicit_acceptance_snapshot(node: dict[str, Any]) -> dict[str, Any]:
    role = automated_node_role(node)
    phase = {
        "group_design": "awaiting_designer",
        "implementation": "awaiting_worker",
        "final_validation": "awaiting_reviewer",
    }[role]
    return {"phase": phase, "attempt": 0, "outcome": "none"}


def acceptance_snapshot(node: dict[str, Any], *, required: bool = False) -> dict[str, Any]:
    acceptance = node.get("acceptance")
    if isinstance(acceptance, dict):
        return acceptance
    if required:
        raise ToolError("acceptance event is out of order for an unenrolled node")
    return implicit_acceptance_snapshot(node)


def ensure_event_id(value: Any) -> str:
    if not isinstance(value, str) or not OPAQUE_EVENT_ID_PATTERN.fullmatch(value):
        raise ToolError("--dispatch-id must be a bounded opaque correlation id")
    return value


def ensure_node_can_start(location: _NodeLocation, node: dict[str, Any]) -> None:
    node_id = str(node.get("id"))
    status = node.get("status")
    if status not in {"pending", "in_progress", "blocked"}:
        raise ToolError(f"node {node_id}: automated acceptance requires a pending, blocked, or in_progress node")

    actual_platform = current_platform()
    if not platform_matches(node.get("platform"), actual_platform):
        raise ToolError(
            f"node {node_id}: declared platform does not match the current runtime platform"
        )
    validated_design_contract(location)
    if node.get("role") in REGRESSION_NODE_ROLES:
        regression = validated_regression_contract(location)
        criteria = node.get("acceptance_criteria")
        criterion_count = len(criteria) if isinstance(criteria, list) else 0
        mapped = regression.get("criteria")
        if not isinstance(mapped, list) or len(mapped) != criterion_count or set(mapped) != set(range(criterion_count)):
            raise ToolError("automated delivery requires regression criteria to map every acceptance criterion exactly once")

    status_by_id = workspace_node_statuses(location.manifest)
    prerequisites = node.get("prerequisites")
    if not is_string_list(prerequisites):
        raise ToolError(f"node {node_id}: prerequisites must be an array")
    incomplete = [ref for ref in prerequisites if status_by_id.get(ref) != "completed"]
    if incomplete:
        raise ToolError(f"node {node_id}: prerequisites must be completed before automated acceptance starts")

    if node.get("role") == "final_validation":
        unfinished = [
            entry
            for entry in location.checkpoints_data
            if isinstance(entry, dict)
            and entry.get("role") == "implementation"
            and entry.get("status") not in {"completed", "skipped"}
        ]
        if unfinished:
            raise ToolError(
                "final_validation cannot start until every non-skipped implementation node is completed"
            )

    other_active = [
        entry
        for entry in location.checkpoints_data
        if isinstance(entry, dict)
        and entry.get("status") == "in_progress"
        and entry.get("id") != node.get("id")
    ]
    if other_active and (
        node.get("role") != "implementation"
        or any(entry.get("role") != "implementation" for entry in other_active)
    ):
        raise ToolError(
            "only independent implementation nodes may run concurrently in one task group"
        )


def clear_regression_proof(node: dict[str, Any]) -> None:
    regression = node.get("regression")
    if not isinstance(regression, dict):
        return
    regression.pop("last_pass", None)
    criteria = node.get("acceptance_criteria")
    if not isinstance(criteria, list):
        return
    for criterion_index in regression.get("criteria", []):
        if type(criterion_index) is not int or not 0 <= criterion_index < len(criteria):
            continue
        criterion = criteria[criterion_index]
        if not isinstance(criterion, dict):
            continue
        criterion["checked"] = False
        criterion.pop("evidence", None)
        criterion.pop("evidence_refs", None)


def invalidate_preparation_after_plan_edit(node: dict[str, Any]) -> None:
    """Clear stale proof while preserving the one-Reviewer-per-group invariant."""

    role = node.get("role")
    if role not in AUTOMATED_NODE_ROLES:
        return
    status = node.get("status")
    if status in WORKFLOW_STATE_MACHINE.terminal_statuses:
        return
    clear_regression_proof(node)
    if status == "deferred":
        node.pop("acceptance", None)
        return
    prior = node.get("acceptance")
    attempt = prior.get("attempt", 0) if isinstance(prior, dict) else 0
    safe_attempt = int(attempt) if type(attempt) is int and attempt >= 0 else 0
    if role == "group_design":
        phase = "awaiting_designer"
    elif role == "implementation":
        phase = "awaiting_worker"
    else:
        phase = "reviewer_complete" if isinstance(prior, dict) and isinstance(prior.get("review"), dict) else "awaiting_reviewer"
    reset: dict[str, Any] = {"phase": phase, "attempt": safe_attempt, "outcome": "none"}
    if isinstance(prior, dict) and isinstance(prior.get("review"), dict):
        reset["review"] = prior["review"]
    node["acceptance"] = reset
    if status == "in_progress":
        node["status"] = "pending"
        node.pop("status_reason", None)


def normalize_delivery_administrative_transition(node: dict[str, Any], target: str) -> None:
    """Cancel automated proof before a delivery node is paused, blocked, deferred, or skipped."""
    role = node.get("role")
    if role not in AUTOMATED_NODE_ROLES or target not in {
        "pending",
        "blocked",
        "deferred",
        "skipped",
    }:
        return

    if role in REGRESSION_NODE_ROLES:
        clear_regression_proof(node)
    if target == "skipped":
        node.pop("acceptance", None)
        return

    acceptance = node.get("acceptance")
    if not isinstance(acceptance, dict):
        return

    attempt = acceptance.get("attempt")
    if type(attempt) is not int or attempt < 0:
        raise ToolError("cannot administratively suspend an invalid acceptance attempt")

    phase = acceptance.get("phase")
    if target == "deferred":
        review = acceptance.get("review")
        if role != "final_validation" or not isinstance(review, dict):
            node.pop("acceptance", None)
            return
        if phase in {"repair_plan_required", "awaiting_repair"}:
            preserved = dict(acceptance)
            preserved.pop("dispatch", None)
        else:
            preserved = {
                "phase": "reviewer_complete",
                "attempt": attempt,
                "outcome": "none",
                "review": review,
            }
            for field in ACCEPTANCE_PREPARATION_FIELDS:
                if field in acceptance:
                    preserved[field] = acceptance[field]
        node["acceptance"] = preserved
        return
    if role == "final_validation" and phase in {"repair_plan_required", "awaiting_repair"}:
        preserved = {
            "phase": phase,
            "attempt": attempt,
            "outcome": acceptance.get("outcome"),
        }
        for field in ACCEPTANCE_PREPARATION_FIELDS:
            if field in acceptance:
                preserved[field] = acceptance[field]
        if phase == "awaiting_repair" and "repair_node_id" in acceptance:
            preserved["repair_node_id"] = acceptance["repair_node_id"]
        if isinstance(acceptance.get("review"), dict):
            preserved["review"] = acceptance["review"]
        node["acceptance"] = preserved
        return

    if role == "group_design":
        resumed_phase = "awaiting_designer"
    elif role == "implementation":
        resumed_phase = "awaiting_worker"
    else:
        resumed_phase = "reviewer_complete" if isinstance(acceptance.get("review"), dict) else "awaiting_reviewer"
    normalized = {
        "phase": resumed_phase,
        "attempt": attempt,
        "outcome": "none",
    }
    if role != "group_design":
        fields = ACCEPTANCE_PREPARATION_FIELDS if role == "final_validation" else ACCEPTANCE_STABLE_PREPARATION_FIELDS
        for field in fields:
            if field in acceptance:
                normalized[field] = acceptance[field]
    if isinstance(acceptance.get("review"), dict):
        normalized["review"] = acceptance["review"]
    node["acceptance"] = normalized


def regression_failure_outcome(error: ToolError) -> str:
    message = str(error).lower()
    if "timed out" in message:
        return "regression_timeout"
    if "could not be started" in message or "required" in message or "invalid regression" in message:
        return "regression_unavailable"
    return "regression_failed"


def ensure_matching_dispatch(
    acceptance: dict[str, Any],
    *,
    expected_phase: str,
    expected_role: str,
    dispatch_id: str,
) -> dict[str, Any]:
    if acceptance.get("phase") != expected_phase:
        raise ToolError("acceptance event is out of order for the current phase")
    dispatch = acceptance.get("dispatch")
    if not isinstance(dispatch, dict):
        raise ToolError("acceptance event has no outstanding correlated dispatch")
    if dispatch.get("role") != expected_role or dispatch.get("id") != dispatch_id:
        raise ToolError("acceptance event does not match the outstanding dispatch")
    return dispatch


def _relative_leaf_paths(node: dict[str, Any]) -> list[str]:
    design = node.get("design")
    if not isinstance(design, dict):
        raise ToolError("leaf dispatch requires a validated design contract")
    values: list[str] = []
    for field in ("artifact", "owned_paths", "scaffold_paths", "acceptance_paths"):
        raw = design.get(field)
        raw_values = [raw] if field == "artifact" else raw if isinstance(raw, list) else []
        for value in raw_values:
            if not isinstance(value, str):
                raise ToolError("leaf dispatch contains an invalid repository path")
            normalized = value.strip().replace("\\", "/")
            parts = [part for part in normalized.split("/") if part]
            if (
                not parts
                or normalized.startswith("/")
                or ":/" in normalized
                or any(part in {".", ".."} for part in parts)
            ):
                raise ToolError("leaf dispatch contains an invalid repository path")
            if normalized not in values:
                values.append(normalized)
    if not values:
        raise ToolError("leaf dispatch requires repository-relative paths")
    return sorted(values)


def bounded_acceptance_payload(
    node: dict[str, Any],
    *,
    action: str | None = None,
    group_nodes: list[Any] | None = None,
    capability_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    acceptance = acceptance_snapshot(node)
    phase = str(acceptance["phase"])
    if action is None:
        action = (
            "none"
            if node.get("status") == "deferred"
            or node.get("status") in WORKFLOW_STATE_MACHINE.terminal_statuses
            else acceptance_next_action(phase, str(node.get("role")))
        )
    payload: dict[str, Any] = {
        "node_id": node.get("id"),
        "phase": phase,
        "action": action,
        "attempt": acceptance.get("attempt", 0),
    }
    dispatch = acceptance.get("dispatch")
    if isinstance(dispatch, dict) and isinstance(dispatch.get("id"), str):
        payload["dispatch_id"] = dispatch["id"]
    if capability_context is not None:
        payload["capability_scope"] = capability_context
    if action.startswith("dispatch_"):
        agent_type = {
            "dispatch_designer": "designer",
            "dispatch_worker": f"worker-{node.get('difficulty')}",
            "dispatch_verifier": "verifier",
            "dispatch_reviewer": "reviewer",
        }.get(action)
        role_reference = _reference_for_action(action)
        if agent_type is None or role_reference is None:
            raise ToolError("unsupported leaf dispatch action")
        payload.update(
            {
                "agent_type": agent_type,
                "fork_turns": "none",
                "role_reference": role_reference,
                "repository_paths": _relative_leaf_paths(node),
            }
        )
        knowledge_references = _knowledge_references_for_action(action)
        if knowledge_references:
            payload["knowledge_references"] = list(knowledge_references)
            payload["required_outputs"] = ["design_pattern_assessment"]
        if action in {"dispatch_designer", "dispatch_reviewer"} and group_nodes is not None:
            group_ids: list[str] = []
            group_paths: set[str] = set(payload["repository_paths"])
            for group_node in group_nodes:
                if not isinstance(group_node, dict):
                    continue
                group_id = group_node.get("id")
                if isinstance(group_id, str):
                    group_ids.append(group_id)
                if isinstance(group_node.get("design"), dict):
                    group_paths.update(_relative_leaf_paths(group_node))
                regression = group_node.get("regression")
                if isinstance(regression, dict) and is_string_list(regression.get("paths")):
                    group_paths.update(str(value) for value in regression["paths"])
            payload["group_node_ids"] = group_ids
            payload["repository_paths"] = sorted(group_paths)
    return payload


def print_acceptance_payload(
    node: dict[str, Any],
    *,
    action: str | None = None,
    group_nodes: list[Any] | None = None,
    location: _NodeLocation | None = None,
) -> None:
    capability_context = None
    if location is not None:
        plan = location.manifest_data[location.plan_index]
        if isinstance(plan, dict):
            capability_context = capability_scope_for_plan(location.manifest, plan)
    payload = bounded_acceptance_payload(
        node,
        action=action,
        group_nodes=group_nodes,
        capability_context=capability_context,
    )
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def next_action_command(args: argparse.Namespace) -> int:
    manifest = workspace_manifest_path(Path(args.root))
    location = locate_node(manifest, args.node_id)
    ensure_location_is_valid(location)
    node = location.checkpoints_data[location.node_index]
    automated_node_role(node)
    if node.get("status") == "deferred":
        print_acceptance_payload(node, action="none", group_nodes=location.checkpoints_data, location=location)
        return 0
    if node.get("status") in {"pending", "blocked", "in_progress"} and "acceptance" not in node:
        ensure_node_can_start(location, node)
    before = json.dumps(node, sort_keys=True, separators=(",", ":"))
    refresh_preparation(location, node)
    after = json.dumps(node, sort_keys=True, separators=(",", ":"))
    if after != before:
        write_location_and_sync_plan(location)
    print_acceptance_payload(node, group_nodes=location.checkpoints_data, location=location)
    return 0


def dispatch_command(args: argparse.Namespace) -> int:
    manifest = workspace_manifest_path(Path(args.root))
    location = locate_node(manifest, args.node_id)
    ensure_location_is_valid(location)
    node = location.checkpoints_data[location.node_index]
    node_role = automated_node_role(node)
    acceptance = refresh_preparation(location, node)
    prior_acceptance = acceptance
    phase = acceptance.get("phase")

    running_roles = {
        "designer_running": "designer",
        "worker_running": "worker",
        "verifier_running": "verifier",
        "reviewer_running": "reviewer",
    }
    if phase in running_roles:
        dispatch = acceptance.get("dispatch")
        expected_role = running_roles[str(phase)]
        if not isinstance(dispatch, dict) or args.role != expected_role:
            raise ToolError("a different acceptance dispatch is already outstanding")
        if expected_role == "designer":
            binding = preparation_fingerprints(location)
            if dispatch.get("design_digest") != binding["design_digest"]:
                raise ToolError("the outstanding Designer dispatch is stale")
        print_acceptance_payload(node, group_nodes=location.checkpoints_data, location=location)
        return 0

    if args.role == "designer":
        if node_role != "group_design" or phase != "awaiting_designer":
            raise ToolError("Designer dispatch is out of order for this task group")
        ensure_node_can_start(location, node)
        binding = preparation_fingerprints(location)
        node["status"] = "in_progress"
        node.pop("status_reason", None)
        acceptance = {
            "phase": acceptance_transition(str(phase), "designer-dispatched", "designer"),
            "attempt": int(acceptance.get("attempt", 0)),
            "dispatch": {
                "id": generate_id(),
                "role": "designer",
                "design_digest": binding["design_digest"],
            },
            "outcome": "none",
        }
    elif args.role == "worker":
        if node_role != "implementation" or phase not in {"awaiting_worker", "correction_required"}:
            raise ToolError("Worker dispatch is out of order for the current delivery phase")
        ensure_node_can_start(location, node)
        node["status"] = "in_progress"
        node.pop("status_reason", None)
        clear_regression_proof(node)
        current = preparation_fingerprints(location)
        acceptance = {
            "phase": acceptance_transition(str(phase), "worker-dispatched", "worker"),
            "attempt": int(acceptance.get("attempt", 0)) + 1,
            "dispatch": {"id": generate_id(), "role": "worker"},
            "outcome": "none",
            **{field: current[field] for field in ACCEPTANCE_STABLE_PREPARATION_FIELDS},
        }
    elif args.role == "verifier":
        if node_role != "implementation" or phase != "awaiting_verifier" or node.get("status") != "in_progress":
            raise ToolError("Verifier dispatch is out of order for the current delivery phase")
        acceptance = {
            "phase": acceptance_transition(str(phase), "verifier-dispatched", "verifier"),
            "attempt": int(acceptance.get("attempt", 0)),
            "dispatch": {"id": generate_id(), "role": "verifier"},
            "outcome": "none",
        }
        for field in ACCEPTANCE_STABLE_PREPARATION_FIELDS:
            if field in prior_acceptance:
                acceptance[field] = prior_acceptance[field]
    elif args.role == "reviewer":
        if node_role != "final_validation" or phase != "awaiting_reviewer":
            raise ToolError("Reviewer dispatch is out of order for the current task group")
        if isinstance(prior_acceptance.get("review"), dict):
            raise ToolError("the task group's one Reviewer has already completed")
        ensure_node_can_start(location, node)
        node["status"] = "in_progress"
        node.pop("status_reason", None)
        clear_regression_proof(node)
        current = preparation_fingerprints(location)
        acceptance = {
            "phase": acceptance_transition(str(phase), "reviewer-dispatched", "reviewer"),
            "attempt": int(acceptance.get("attempt", 0)),
            "dispatch": {"id": generate_id(), "role": "reviewer"},
            "outcome": "none",
            **{field: current[field] for field in ACCEPTANCE_PREPARATION_FIELDS},
        }
    else:
        raise ToolError("unsupported delivery dispatch role")

    node["acceptance"] = acceptance
    write_location_and_sync_plan(location)
    print_acceptance_payload(node, group_nodes=location.checkpoints_data, location=location)
    return 0


def ensure_host_agent_id(value: Any) -> str:
    """Validate one bounded opaque identity returned by the native host."""

    if not isinstance(value, str) or not OPAQUE_EVENT_ID_PATTERN.fullmatch(value):
        raise ToolError("--agent-id must be a bounded opaque host agent id")
    return value


def bind_agent_command(args: argparse.Namespace) -> int:
    """Commit the real host identity to one outstanding dispatch."""

    manifest = workspace_manifest_path(Path(args.root))
    location = locate_node(manifest, args.node_id)
    ensure_location_is_valid(location)
    dispatch_id = ensure_event_id(args.dispatch_id)
    agent_id = ensure_host_agent_id(args.agent_id)
    node = location.checkpoints_data[location.node_index]
    acceptance = acceptance_snapshot(node, required=True)
    dispatch = acceptance.get("dispatch")
    if not isinstance(dispatch, dict) or dispatch.get("id") != dispatch_id:
        raise ToolError("bind-agent does not match the outstanding dispatch")
    if acceptance.get("phase") not in {
        "designer_running",
        "worker_running",
        "verifier_running",
        "reviewer_running",
    }:
        raise ToolError("bind-agent is out of order for the current delivery phase")
    prior = dispatch.get("host_agent_id")
    if prior is not None:
        if prior != agent_id:
            raise ToolError("bind-agent cannot replace an existing host identity")
        print_acceptance_payload(node, group_nodes=location.checkpoints_data, location=location)
        return 0
    dispatch["host_agent_id"] = agent_id
    write_location_and_sync_plan(location)
    print_acceptance_payload(node, group_nodes=location.checkpoints_data, location=location)
    return 0


def agent_complete_command(args: argparse.Namespace) -> int:
    """Reduce one explicit final host callback, or emit a safe no-op."""

    from .agent_completion import reduce_agent_completion

    manifest = workspace_manifest_path(Path(args.root))
    # Validate the identity before invoking the reducer so malformed values
    # cannot be correlated accidentally and are never echoed in output.
    agent_id = ensure_host_agent_id(args.agent_id)
    directive = reduce_agent_completion(
        manifest,
        agent_id=agent_id,
        final=bool(args.final),
        node_id=args.node_id,
        dispatch_id=getattr(args, "dispatch_id", None),
    )
    if directive is None:
        print("{}")
    else:
        from dataclasses import asdict

        print(json.dumps(asdict(directive), sort_keys=True, separators=(",", ":")))
    return 0


def _delivery_preparation_binding(
    location: _NodeLocation,
    acceptance: dict[str, Any],
) -> dict[str, str]:
    role = location.checkpoints_data[location.node_index].get("role")
    fields = ACCEPTANCE_STABLE_PREPARATION_FIELDS if role == "implementation" else ACCEPTANCE_PREPARATION_FIELDS
    current = preparation_fingerprints(location)
    binding = {
        field: str(acceptance[field])
        for field in fields
        if isinstance(acceptance.get(field), str) and SHA256_PATTERN.fullmatch(str(acceptance[field]))
    }
    for field in fields:
        binding.setdefault(field, current[field])
    return binding


def _complete_mapped_criteria(location: _NodeLocation, node: dict[str, Any]) -> None:
    regression = validated_regression_contract(location)
    criteria = node.get("acceptance_criteria")
    if not isinstance(criteria, list):
        raise ToolError("acceptance criteria are unavailable for automatic completion")
    for criterion_index in regression["criteria"]:
        criterion = criteria[criterion_index]
        if not isinstance(criterion, dict):
            raise ToolError("acceptance criteria are invalid for automatic completion")
        criterion["checked"] = True


def advance_designer_exit(location: _NodeLocation, dispatch_id: str) -> dict[str, Any]:
    node = location.checkpoints_data[location.node_index]
    if automated_node_role(node) != "group_design":
        raise ToolError("Designer exit events require a group_design node")
    acceptance = acceptance_snapshot(node, required=True)
    ensure_matching_dispatch(
        acceptance,
        expected_phase="designer_running",
        expected_role="designer",
        dispatch_id=dispatch_id,
    )
    criteria = node.get("acceptance_criteria")
    if not isinstance(criteria, list):
        raise ToolError("group design criteria are unavailable")
    for criterion in criteria:
        if not isinstance(criterion, dict):
            raise ToolError("group design criteria are invalid")
        criterion["checked"] = True
    node["acceptance"] = {
        "phase": acceptance_transition("designer_running", "agent-complete", "designer"),
        "attempt": int(acceptance.get("attempt", 0)),
        "outcome": "accepted",
    }
    node["status"] = "completed"
    node.pop("status_reason", None)
    write_location_and_sync_plan(location)
    return node


def advance_worker_exit(location: _NodeLocation, dispatch_id: str) -> dict[str, Any]:
    node = location.checkpoints_data[location.node_index]
    if automated_node_role(node) != "implementation":
        raise ToolError("worker exit events require an implementation node")
    acceptance = acceptance_snapshot(node, required=True)
    ensure_matching_dispatch(
        acceptance,
        expected_phase="worker_running",
        expected_role="worker",
        dispatch_id=dispatch_id,
    )
    acceptance = refresh_preparation(location, node)
    if acceptance.get("phase") != "worker_running":
        write_location_and_sync_plan(location)
        return node
    preparation = _delivery_preparation_binding(location, acceptance)
    clear_regression_proof(node)
    acceptance = {
        "phase": acceptance_transition("worker_running", "agent-complete", "worker"),
        "attempt": int(acceptance["attempt"]),
        "outcome": "none",
        **preparation,
    }
    node["acceptance"] = acceptance
    write_location_and_sync_plan(location)
    return node


def advance_verifier_exit(location: _NodeLocation, dispatch_id: str) -> dict[str, Any]:
    """Let a write-capable Verifier repair the Node, then prove its final state."""

    node = location.checkpoints_data[location.node_index]
    if automated_node_role(node) != "implementation":
        raise ToolError("Verifier exit events require an implementation node")
    acceptance = acceptance_snapshot(node, required=True)
    ensure_matching_dispatch(
        acceptance,
        expected_phase="verifier_running",
        expected_role="verifier",
        dispatch_id=dispatch_id,
    )
    acceptance = refresh_preparation(location, node)
    if acceptance.get("phase") != "verifier_running":
        write_location_and_sync_plan(location)
        return node
    preparation = _delivery_preparation_binding(location, acceptance)
    clear_regression_proof(node)
    try:
        _run_regression_at_location(location, persist=False)
    except ToolError as exc:
        clear_regression_proof(node)
        node["acceptance"] = {
            "phase": acceptance_transition("verifier_running", "regression-failed", "verifier"),
            "attempt": int(acceptance["attempt"]),
            "outcome": regression_failure_outcome(exc),
            **preparation,
        }
    else:
        _complete_mapped_criteria(location, node)
        node["acceptance"] = {
            "phase": acceptance_transition("verifier_running", "regression-passed", "verifier"),
            "attempt": int(acceptance["attempt"]),
            "outcome": "accepted",
            **preparation,
        }
        node["status"] = "completed"
        node.pop("status_reason", None)
    write_location_and_sync_plan(location)
    return node


def advance_reviewer_exit(location: _NodeLocation, dispatch_id: str) -> dict[str, Any]:
    """Persist the one group Reviewer completion for native-main decision handling."""

    node = location.checkpoints_data[location.node_index]
    if automated_node_role(node) != "final_validation":
        raise ToolError("Reviewer exit events require a final_validation node")
    acceptance = acceptance_snapshot(node, required=True)
    ensure_matching_dispatch(
        acceptance,
        expected_phase="reviewer_running",
        expected_role="reviewer",
        dispatch_id=dispatch_id,
    )
    current = preparation_fingerprints(location)
    node["acceptance"] = {
        "phase": acceptance_transition("reviewer_running", "agent-complete", "reviewer"),
        "attempt": int(acceptance["attempt"]),
        "outcome": "none",
        "review": {"recorded_at": evidence_timestamp(), "dispatch_id": dispatch_id},
        **current,
    }
    write_location_and_sync_plan(location)
    return node


def _run_group_regression_after_review(
    location: _NodeLocation,
    acceptance: dict[str, Any],
    *,
    source_phase: str,
) -> dict[str, Any]:
    """Run one normal group regression, or a failure-driven repair rerun."""

    node = location.checkpoints_data[location.node_index]
    review = acceptance.get("review")
    if not isinstance(review, dict):
        raise ToolError("full regression requires the completed group Reviewer receipt")
    ensure_immediate_decisions_resolved(location)
    ensure_node_can_start(location, node)
    node["status"] = "in_progress"
    node.pop("status_reason", None)
    current = preparation_fingerprints(location)
    clear_regression_proof(node)
    try:
        _run_regression_at_location(location, persist=False)
    except ToolError as exc:
        clear_regression_proof(node)
        node["acceptance"] = {
            "phase": acceptance_transition(source_phase, "regression-failed", "system"),
            "attempt": int(acceptance["attempt"]),
            "outcome": regression_failure_outcome(exc),
            "review": review,
            **current,
        }
        node["status"] = "pending"
        node.pop("status_reason", None)
    else:
        _complete_mapped_criteria(location, node)
        node["acceptance"] = {
            "phase": acceptance_transition(source_phase, "regression-passed", "system"),
            "attempt": int(acceptance["attempt"]),
            "outcome": "accepted",
            "review": review,
            **current,
        }
        node["status"] = "completed"
        node.pop("status_reason", None)
    write_location_and_sync_plan(location)
    return node


def advance_reviewer_finished(location: _NodeLocation, dispatch_id: str) -> dict[str, Any]:
    """After main records decisions, verify the Reviewer's repairs with full regression."""

    node = location.checkpoints_data[location.node_index]
    if automated_node_role(node) != "final_validation":
        raise ToolError("reviewer-finished events require a final_validation node")
    acceptance = acceptance_snapshot(node, required=True)
    review = acceptance.get("review")
    if acceptance.get("phase") != "reviewer_complete" or not isinstance(review, dict) or review.get("dispatch_id") != dispatch_id:
        raise ToolError("reviewer-finished does not match the completed group Reviewer")
    return _run_group_regression_after_review(
        location,
        acceptance,
        source_phase="reviewer_complete",
    )


def ensure_immediate_decisions_resolved(location: _NodeLocation) -> None:
    """Prevent every post-Reviewer regression path from bypassing a blocking choice."""

    plan = location.manifest_data[location.plan_index]
    decisions = plan.get("decision_issues") if isinstance(plan, dict) else None
    if isinstance(decisions, list) and any(
        isinstance(decision, dict)
        and decision.get("status") == "open"
        and decision.get("urgency") == "immediate"
        for decision in decisions
    ):
        raise ToolError(
            "post-Reviewer regression requires every immediate developer decision to be resolved"
        )


def ensure_repair_node_id(value: Any) -> str:
    if not isinstance(value, str) or not UUID4_PATTERN.fullmatch(value):
        raise ToolError("--repair-node must be a UUID4 node id")
    return value


def validated_final_repair_node(
    location: _NodeLocation,
    repair_node_id: str,
    *,
    required_status: str,
) -> dict[str, Any]:
    final = location.checkpoints_data[location.node_index]
    if automated_node_role(final) != "final_validation":
        raise ToolError("repair handoff events require a final_validation node")
    prerequisites = final.get("prerequisites")
    if not is_string_list(prerequisites) or repair_node_id not in prerequisites:
        raise ToolError("repair node must already be a prerequisite of final_validation")

    repair_index: int | None = None
    repair: dict[str, Any] | None = None
    for index, entry in enumerate(location.checkpoints_data):
        if isinstance(entry, dict) and entry.get("id") == repair_node_id:
            repair_index = index
            repair = entry
            break
    if repair is None or repair_index is None:
        raise ToolError("repair node was not found in the final_validation checkpoints")
    if repair_index >= location.node_index:
        raise ToolError("repair node must appear before final_validation")
    if repair.get("role") != "implementation":
        raise ToolError("repair node must use the implementation role")
    if repair.get("status") != required_status:
        raise ToolError(f"repair node must be {required_status}")
    if required_status == "completed":
        repair_acceptance = repair.get("acceptance")
        if not isinstance(repair_acceptance, dict) or repair_acceptance.get("phase") != "accepted":
            raise ToolError("repair node must complete its automated acceptance cycle")
    return repair


def advance_repair_registration(location: _NodeLocation, repair_node_id: str) -> dict[str, Any]:
    node = location.checkpoints_data[location.node_index]
    if automated_node_role(node) != "final_validation":
        raise ToolError("repair-registered events require a final_validation node")
    acceptance = acceptance_snapshot(node, required=True)
    if acceptance.get("phase") != "repair_plan_required":
        raise ToolError("acceptance event is out of order for the current phase")
    validated_final_repair_node(location, repair_node_id, required_status="pending")

    preserved_preparation = _delivery_preparation_binding(location, acceptance)
    node["acceptance"] = {
        "phase": acceptance_transition("repair_plan_required", "repair-registered", "final_validation"),
        "attempt": int(acceptance["attempt"]),
        "outcome": str(acceptance["outcome"]),
        "repair_node_id": repair_node_id,
        "review": acceptance["review"],
        **preserved_preparation,
    }
    node["status"] = "pending"
    node.pop("status_reason", None)
    write_location_and_sync_plan(location)
    return node


def advance_repair_completion(location: _NodeLocation, repair_node_id: str) -> dict[str, Any]:
    node = location.checkpoints_data[location.node_index]
    if automated_node_role(node) != "final_validation":
        raise ToolError("repair-completed events require a final_validation node")
    acceptance = acceptance_snapshot(node, required=True)
    if acceptance.get("phase") != "awaiting_repair":
        raise ToolError("acceptance event is out of order for the current phase")
    if acceptance.get("repair_node_id") != repair_node_id:
        raise ToolError("repair completion does not match the bound repair node")
    validated_final_repair_node(location, repair_node_id, required_status="completed")
    return _run_group_regression_after_review(
        location,
        acceptance,
        source_phase="awaiting_repair",
    )


def advance_command(args: argparse.Namespace) -> int:
    repair_events = {"repair-registered", "repair-completed"}
    if args.event in repair_events:
        if args.dispatch_id is not None:
            raise ToolError("repair handoff events reject --dispatch-id")
        repair_node_id = ensure_repair_node_id(args.repair_node)
        dispatch_id = None
    elif args.event == "reviewer-finished":
        if args.repair_node is not None:
            raise ToolError("Reviewer events reject --repair-node")
        dispatch_id = ensure_event_id(args.dispatch_id)
        repair_node_id = None
    else:
        raise ToolError("unsupported acceptance event")

    manifest = workspace_manifest_path(Path(args.root))
    location = locate_node(manifest, args.node_id)
    ensure_location_is_valid(location)

    if args.event == "reviewer-finished":
        assert dispatch_id is not None
        node = advance_reviewer_finished(location, dispatch_id)
    elif args.event == "repair-registered":
        assert repair_node_id is not None
        node = advance_repair_registration(location, repair_node_id)
    elif args.event == "repair-completed":
        assert repair_node_id is not None
        node = advance_repair_completion(location, repair_node_id)
    else:
        raise ToolError("unsupported acceptance event")

    print_acceptance_payload(node, group_nodes=location.checkpoints_data, location=location)
    return 0


def start_command(args: argparse.Namespace) -> int:
    reject_manual_delivery_command(args.root, args.node_id, "start")
    print(f"OK: current platform is {current_platform()}")
    for message in run_node_mutation(args.root, args.node_id, "in_progress"):
        print(message)
    return 0


def reject_manual_delivery_command(root: str | Path, node_id: str, command: str) -> None:
    manifest = workspace_manifest_path(Path(root))
    location = locate_node(manifest, node_id)
    node = location.checkpoints_data[location.node_index]
    if node.get("role") in AUTOMATED_NODE_ROLES:
        raise ToolError(
            f"node {node_id}: automated acceptance rejects direct {command}; use next-action, dispatch, and advance"
        )


def regress_command(args: argparse.Namespace) -> int:
    reject_manual_delivery_command(args.root, args.node_id, "regress")
    for message in run_node_regression(args.root, args.node_id, force=True):
        print(message)
    return 0


def complete_command(args: argparse.Namespace) -> int:
    reject_manual_delivery_command(args.root, args.node_id, "complete")
    if args.delivered is not None and not GIT_SHA_PATTERN.fullmatch(args.delivered):
        raise ToolError("--delivered must be a lowercase hex commit sha (7-40 characters)")
    for message in ensure_node_regression(args.root, args.node_id):
        print(message)
    for message in run_node_mutation(args.root, args.node_id, "completed", delivered=args.delivered):
        print(message)
    return 0


def block_command(args: argparse.Namespace) -> int:
    for message in run_node_mutation(args.root, args.node_id, "blocked", reason=args.reason):
        print(message)
    return 0


def skip_command(args: argparse.Namespace) -> int:
    for message in run_node_mutation(args.root, args.node_id, "skipped", reason=args.reason):
        print(message)
    return 0


def defer_command(args: argparse.Namespace) -> int:
    for message in run_node_mutation(
        args.root,
        args.node_id,
        "deferred",
        reason=args.reason,
    ):
        print(message)
    return 0


def activate_command(args: argparse.Namespace) -> int:
    for message in run_node_mutation(
        args.root,
        args.node_id,
        "pending",
        require_current="deferred",
    ):
        print(message)
    return 0


def pause_command(args: argparse.Namespace) -> int:
    for message in run_node_mutation(args.root, args.node_id, "pending", reason=args.reason, require_current="in_progress"):
        print(message)
    return 0
