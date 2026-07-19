"""Workflow layer for Better Plan workflow state."""

from __future__ import annotations

from typing import Any
from pathlib import Path
import argparse
import json
from ..domain.models import ACCEPTANCE_PREPARATION_FIELDS, ACCEPTANCE_STABLE_PREPARATION_FIELDS, GIT_SHA_PATTERN, OPAQUE_EVENT_ID_PATTERN, REGRESSION_NODE_ROLES, SHA256_PATTERN, ToolError, UUID4_PATTERN, WORKFLOW_STATE_MACHINE, expected_regression_scope, generate_id, is_string_list, safe_summary_issue
from ..domain.transitions import next_action as acceptance_next_action, transition as acceptance_transition
from ..infrastructure.regression import current_platform, ensure_node_regression, evidence_timestamp, platform_matches, preparation_fingerprints, regression_receipt_status, run_node_regression, run_regression_at_location as _run_regression_at_location, validated_design_contract, validated_regression_contract
from ..infrastructure.workspace import NodeLocation as _NodeLocation, ensure_location_is_valid, locate_node, project_root_for, relative_path_label, workspace_manifest_path, write_location_and_sync_plan


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
    if target in {"blocked", "skipped"}:
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

    if target in {"blocked", "skipped"} and current_status == target:
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
        if current_status != "in_progress" and isinstance(node.get("regression"), dict):
            node["regression"].pop("last_pass", None)

    if target == "completed" and expected_regression_scope(node.get("role")) is not None:
        fresh, reason = regression_receipt_status(location)
        if not fresh:
            raise ToolError(f"node {node_id}: cannot complete without a current passing regression receipt: {reason}")

    normalize_delivery_administrative_transition(node, target)

    node["status"] = target
    if target in {"blocked", "skipped"}:
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
    """Invalidate stale pre-execution approval and return the current bounded snapshot."""
    acceptance = acceptance_snapshot(node)
    phase = str(acceptance.get("phase"))
    freshness_phases = {
        "acceptance_designer_running",
        "awaiting_acceptance_review",
        "acceptance_reviewer_running",
        "repair_required",
        "executor_running",
        "awaiting_auditor",
        "auditor_running",
        "awaiting_executor",
        "awaiting_regression",
        "repair_plan_required",
        "awaiting_repair",
    }
    if phase not in freshness_phases:
        return acceptance

    current = preparation_fingerprints(location)
    if phase == "acceptance_designer_running":
        dispatch = acceptance.get("dispatch")
        stale = not isinstance(dispatch, dict) or dispatch.get("design_digest") != current["design_digest"]
    elif node.get("role") == "implementation" and phase == "awaiting_executor":
        compare_fields = (
            ACCEPTANCE_PREPARATION_FIELDS
            if (
                isinstance(acceptance.get("scaffold_fingerprint"), str)
                and SHA256_PATTERN.fullmatch(str(acceptance.get("scaffold_fingerprint")))
            )
            else ACCEPTANCE_STABLE_PREPARATION_FIELDS
        )
        stale = any(acceptance.get(field) != current[field] for field in compare_fields)
    elif node.get("role") == "implementation" and phase in {"executor_running", "repair_required", "awaiting_auditor", "auditor_running"}:
        stale = any(
            acceptance.get(field) != current[field] for field in ACCEPTANCE_STABLE_PREPARATION_FIELDS
        )
    elif node.get("role") == "final_validation" and phase in {
        "awaiting_regression",
        "awaiting_auditor",
        "auditor_running",
        "repair_plan_required",
        "awaiting_repair",
    }:
        stale = any(acceptance.get(field) != value for field, value in current.items())
    else:
        stale = any(acceptance.get(field) != value for field, value in current.items())
    if not stale:
        return acceptance

    clear_regression_proof(node)
    if node.get("status") != "blocked":
        node["status"] = "pending"
        node.pop("status_reason", None)
    reset = {
        "phase": "acceptance_revision_required",
        "attempt": int(acceptance.get("attempt", 0)),
        "outcome": "none",
    }
    node["acceptance"] = reset
    return reset


def automated_node_role(node: dict[str, Any]) -> str:
    role = node.get("role")
    if role not in REGRESSION_NODE_ROLES:
        raise ToolError("acceptance commands require an implementation or final_validation node")
    return str(role)


def implicit_acceptance_snapshot(node: dict[str, Any]) -> dict[str, Any]:
    automated_node_role(node)
    return {"phase": "awaiting_acceptance_design", "attempt": 0, "outcome": "none"}


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
    regression = validated_regression_contract(location)
    criteria = node.get("acceptance_criteria")
    criterion_count = len(criteria) if isinstance(criteria, list) else 0
    mapped = regression.get("criteria")
    if not isinstance(mapped, list) or len(mapped) != criterion_count or set(mapped) != set(range(criterion_count)):
        raise ToolError("automated acceptance requires regression criteria to map every acceptance criterion exactly once")

    status_by_id = {
        str(entry.get("id")): entry.get("status")
        for entry in location.checkpoints_data
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }
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
            raise ToolError("final_validation cannot start while implementation nodes remain unfinished")

    for entry in location.checkpoints_data:
        if (
            isinstance(entry, dict)
            and entry.get("status") == "in_progress"
            and entry.get("id") != node.get("id")
        ):
            raise ToolError("another node is already in_progress in this plan")


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
    """Clear reviewed preparation and park an enrolled lifecycle for main judgment."""
    if node.get("role") not in REGRESSION_NODE_ROLES:
        return
    status = node.get("status")
    if status in WORKFLOW_STATE_MACHINE.terminal_statuses:
        return
    clear_regression_proof(node)
    prior = node.get("acceptance")
    attempt = prior.get("attempt", 0) if isinstance(prior, dict) else 0
    safe_attempt = int(attempt) if type(attempt) is int and attempt >= 0 else 0
    node["acceptance"] = {
        "phase": (
            "acceptance_revision_required"
            if isinstance(prior, dict)
            else "awaiting_acceptance_design"
        ),
        "attempt": safe_attempt,
        "outcome": "none",
    }
    if status == "in_progress":
        node["status"] = "pending"
        node.pop("status_reason", None)


def normalize_delivery_administrative_transition(node: dict[str, Any], target: str) -> None:
    """Cancel automated proof before a delivery node is paused, blocked, or skipped."""
    role = node.get("role")
    if role not in REGRESSION_NODE_ROLES or target not in {"pending", "blocked", "skipped"}:
        return

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
        node["acceptance"] = preserved
        return

    preparation_incomplete = phase in {
        "awaiting_acceptance_design",
        "acceptance_designer_running",
        "awaiting_acceptance_review",
        "acceptance_reviewer_running",
    }
    if phase == "acceptance_revision_required":
        resumed_phase = "acceptance_revision_required"
    elif preparation_incomplete:
        resumed_phase = "awaiting_acceptance_design"
    elif role == "implementation":
        resumed_phase = "awaiting_executor"
    else:
        resumed_phase = "awaiting_regression"
    normalized = {
        "phase": resumed_phase,
        "attempt": attempt,
        "outcome": "none",
    }
    if not preparation_incomplete and phase != "acceptance_revision_required":
        fields = ACCEPTANCE_PREPARATION_FIELDS if role == "final_validation" else ACCEPTANCE_STABLE_PREPARATION_FIELDS
        for field in fields:
            if field in acceptance:
                normalized[field] = acceptance[field]
    node["acceptance"] = normalized


def regression_failure_outcome(error: ToolError) -> str:
    message = str(error).lower()
    if "timed out" in message:
        return "regression_timeout"
    if "could not be started" in message or "required" in message or "invalid regression" in message:
        return "regression_unavailable"
    return "regression_failed"


def current_regression_binding(location: _NodeLocation) -> dict[str, str]:
    fresh, _ = regression_receipt_status(location)
    if not fresh:
        raise ToolError("auditor event requires a current passing regression fingerprint")
    node = location.checkpoints_data[location.node_index]
    regression = node.get("regression")
    receipt = regression.get("last_pass") if isinstance(regression, dict) else None
    if not isinstance(receipt, dict):
        raise ToolError("auditor event requires a current passing regression fingerprint")
    return {
        "contract_digest": str(receipt["contract_digest"]),
        "content_fingerprint": str(receipt["content_fingerprint"]),
    }


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


def bounded_acceptance_payload(node: dict[str, Any], *, action: str | None = None) -> dict[str, Any]:
    acceptance = acceptance_snapshot(node)
    phase = str(acceptance["phase"])
    if action is None:
        action = "none" if node.get("status") in WORKFLOW_STATE_MACHINE.terminal_statuses else acceptance_next_action(
            phase,
            str(node.get("role")),
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
    return payload


def print_acceptance_payload(node: dict[str, Any], *, action: str | None = None) -> None:
    print(json.dumps(bounded_acceptance_payload(node, action=action), sort_keys=True, separators=(",", ":")))


def next_action_command(args: argparse.Namespace) -> int:
    manifest = workspace_manifest_path(Path(args.root))
    location = locate_node(manifest, args.node_id)
    ensure_location_is_valid(location)
    node = location.checkpoints_data[location.node_index]
    automated_node_role(node)
    if node.get("status") in {"pending", "blocked", "in_progress"} and "acceptance" not in node:
        ensure_node_can_start(location, node)
    before = json.dumps(node, sort_keys=True, separators=(",", ":"))
    refresh_preparation(location, node)
    after = json.dumps(node, sort_keys=True, separators=(",", ":"))
    if after != before:
        write_location_and_sync_plan(location)
    print_acceptance_payload(node)
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
        "acceptance_designer_running": "acceptance_designer",
        "acceptance_reviewer_running": "acceptance_reviewer",
        "executor_running": "executor",
        "auditor_running": "auditor",
    }
    if phase in running_roles:
        dispatch = acceptance.get("dispatch")
        expected_role = running_roles[str(phase)]
        if not isinstance(dispatch, dict) or args.role != expected_role:
            raise ToolError("a different acceptance dispatch is already outstanding")
        if expected_role == "acceptance_designer":
            binding = preparation_fingerprints(location)
            if dispatch.get("design_digest") != binding["design_digest"]:
                raise ToolError("the outstanding acceptance designer dispatch is stale")
        elif expected_role == "acceptance_reviewer":
            binding = preparation_fingerprints(location)
            if any(dispatch.get(field) != binding[field] for field in binding):
                raise ToolError("the outstanding acceptance reviewer dispatch is stale")
        elif expected_role == "auditor":
            binding = current_regression_binding(location)
            if any(dispatch.get(field) != binding[field] for field in binding):
                raise ToolError("the outstanding auditor dispatch is stale")
        print_acceptance_payload(node)
        return 0

    if args.role == "acceptance_designer":
        if phase not in {"awaiting_acceptance_design", "acceptance_revision_required"}:
            raise ToolError("acceptance designer dispatch is out of order for the current acceptance phase")
        ensure_node_can_start(location, node)
        binding = preparation_fingerprints(location)
        node["status"] = "in_progress"
        node.pop("status_reason", None)
        clear_regression_proof(node)
        acceptance = {
            "phase": acceptance_transition(str(phase), "acceptance-designer-dispatched", "acceptance_designer"),
            "attempt": int(acceptance.get("attempt", 0)),
            "dispatch": {
                "id": generate_id(),
                "role": "acceptance_designer",
                "design_digest": binding["design_digest"],
            },
            "outcome": "none",
        }
    elif args.role == "acceptance_reviewer":
        if phase != "awaiting_acceptance_review" or node.get("status") != "in_progress":
            raise ToolError("acceptance reviewer dispatch is out of order for the current acceptance phase")
        binding = preparation_fingerprints(location)
        if any(acceptance.get(field) != value for field, value in binding.items()):
            raise ToolError("acceptance reviewer dispatch requires current designer fingerprints")
        acceptance = {
            "phase": acceptance_transition(str(phase), "acceptance-reviewer-dispatched", "acceptance_reviewer"),
            "attempt": int(acceptance.get("attempt", 0)),
            "dispatch": {"id": generate_id(), "role": "acceptance_reviewer", **binding},
            "outcome": "none",
            **binding,
        }
    elif args.role == "executor":
        if node_role != "implementation" or phase not in {"awaiting_executor", "repair_required"}:
            raise ToolError("executor dispatch is out of order for the current acceptance phase")
        ensure_node_can_start(location, node)
        node["status"] = "in_progress"
        node.pop("status_reason", None)
        clear_regression_proof(node)
        acceptance = {
            "phase": acceptance_transition(str(phase), "executor-dispatched", "executor"),
            "attempt": int(acceptance.get("attempt", 0)) + 1,
            "dispatch": {"id": generate_id(), "role": "executor"},
            "outcome": "none",
        }
        for field in ACCEPTANCE_STABLE_PREPARATION_FIELDS:
            if field in prior_acceptance:
                acceptance[field] = prior_acceptance[field]
    elif args.role == "auditor":
        if phase != "awaiting_auditor" or node.get("status") != "in_progress":
            raise ToolError("auditor dispatch is out of order for the current acceptance phase")
        binding = current_regression_binding(location)
        acceptance = {
            "phase": acceptance_transition(str(phase), "auditor-dispatched", "auditor"),
            "attempt": int(acceptance.get("attempt", 0)),
            "dispatch": {"id": generate_id(), "role": "auditor", **binding},
            "outcome": "regression_passed",
        }
        fields = ACCEPTANCE_PREPARATION_FIELDS if node_role == "final_validation" else ACCEPTANCE_STABLE_PREPARATION_FIELDS
        for field in fields:
            if field in prior_acceptance:
                acceptance[field] = prior_acceptance[field]
    else:
        raise ToolError("unsupported acceptance dispatch role")

    node["acceptance"] = acceptance
    write_location_and_sync_plan(location)
    print_acceptance_payload(node)
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


def advance_acceptance_design_exit(location: _NodeLocation, dispatch_id: str) -> dict[str, Any]:
    node = location.checkpoints_data[location.node_index]
    automated_node_role(node)
    acceptance = acceptance_snapshot(node, required=True)
    dispatch = ensure_matching_dispatch(
        acceptance,
        expected_phase="acceptance_designer_running",
        expected_role="acceptance_designer",
        dispatch_id=dispatch_id,
    )
    binding = preparation_fingerprints(location)
    if dispatch.get("design_digest") != binding["design_digest"]:
        raise ToolError("acceptance designer exit does not match the current design fingerprint")
    node["acceptance"] = {
        "phase": acceptance_transition(
            "acceptance_designer_running",
            "acceptance-designer-exited",
            "acceptance_designer",
        ),
        "attempt": int(acceptance.get("attempt", 0)),
        "outcome": "none",
        **binding,
    }
    write_location_and_sync_plan(location)
    return node


def advance_acceptance_review(
    location: _NodeLocation,
    dispatch_id: str,
    *,
    passed: bool,
) -> dict[str, Any]:
    node = location.checkpoints_data[location.node_index]
    node_role = automated_node_role(node)
    acceptance = acceptance_snapshot(node, required=True)
    dispatch = ensure_matching_dispatch(
        acceptance,
        expected_phase="acceptance_reviewer_running",
        expected_role="acceptance_reviewer",
        dispatch_id=dispatch_id,
    )
    binding = preparation_fingerprints(location)
    if any(dispatch.get(field) != value for field, value in binding.items()):
        raise ToolError("acceptance reviewer verdict does not match current preparation fingerprints")
    if not passed:
        node["acceptance"] = {
            "phase": acceptance_transition(
                "acceptance_reviewer_running",
                "acceptance-rejected",
                "acceptance_reviewer",
            ),
            "attempt": int(acceptance.get("attempt", 0)),
            "outcome": "acceptance_rejected",
        }
        node["status"] = "pending"
        node.pop("status_reason", None)
        write_location_and_sync_plan(location)
        return node

    next_phase = acceptance_transition(
        "acceptance_reviewer_running",
        "acceptance-approved",
        "acceptance_reviewer",
    )
    if node_role == "final_validation":
        next_phase = "awaiting_regression"
    node["acceptance"] = {
        "phase": next_phase,
        "attempt": int(acceptance.get("attempt", 0)),
        "outcome": "none",
        **binding,
    }
    node["status"] = "pending"
    node.pop("status_reason", None)
    write_location_and_sync_plan(location)
    return node


def advance_executor_exit(location: _NodeLocation, dispatch_id: str) -> dict[str, Any]:
    node = location.checkpoints_data[location.node_index]
    if automated_node_role(node) != "implementation":
        raise ToolError("executor exit events require an implementation node")
    acceptance = acceptance_snapshot(node, required=True)
    ensure_matching_dispatch(
        acceptance,
        expected_phase="executor_running",
        expected_role="executor",
        dispatch_id=dispatch_id,
    )
    acceptance = refresh_preparation(location, node)
    if acceptance.get("phase") != "executor_running":
        write_location_and_sync_plan(location)
        return node
    preparation = _delivery_preparation_binding(location, acceptance)

    try:
        _run_regression_at_location(location, persist=False)
    except ToolError as exc:
        clear_regression_proof(node)
        acceptance = {
            "phase": acceptance_transition("executor_running", "regression-failed", "system"),
            "attempt": int(acceptance["attempt"]),
            "outcome": regression_failure_outcome(exc),
            **preparation,
        }
    else:
        acceptance = {
            "phase": acceptance_transition("executor_running", "regression-passed", "system"),
            "attempt": int(acceptance["attempt"]),
            "outcome": "regression_passed",
            **preparation,
        }
    node["acceptance"] = acceptance
    write_location_and_sync_plan(location)
    return node


def advance_final_regression(location: _NodeLocation) -> dict[str, Any]:
    node = location.checkpoints_data[location.node_index]
    if automated_node_role(node) != "final_validation":
        raise ToolError("regression-requested events require a final_validation node")
    acceptance = acceptance_snapshot(node, required=True)
    if acceptance.get("phase") != "awaiting_regression":
        raise ToolError("acceptance event is out of order for the current phase")
    current_preparation = preparation_fingerprints(location)
    if any(acceptance.get(field) != value for field, value in current_preparation.items()):
        raise ToolError("final regression requires current reviewed preparation fingerprints")
    ensure_node_can_start(location, node)
    node["status"] = "in_progress"
    node.pop("status_reason", None)
    clear_regression_proof(node)
    node["acceptance"] = acceptance

    try:
        _run_regression_at_location(location, persist=False)
    except ToolError as exc:
        clear_regression_proof(node)
        acceptance = {
            "phase": acceptance_transition("awaiting_regression", "regression-failed", "system"),
            "attempt": int(acceptance.get("attempt", 0)),
            "outcome": regression_failure_outcome(exc),
            **current_preparation,
        }
        node["status"] = "pending"
        node.pop("status_reason", None)
    else:
        acceptance = {
            "phase": acceptance_transition("awaiting_regression", "regression-passed", "system"),
            "attempt": int(acceptance.get("attempt", 0)),
            "outcome": "regression_passed",
            **current_preparation,
        }
    node["acceptance"] = acceptance
    write_location_and_sync_plan(location)
    return node


def advance_audit_verdict(location: _NodeLocation, dispatch_id: str, *, passed: bool) -> dict[str, Any]:
    node = location.checkpoints_data[location.node_index]
    node_role = automated_node_role(node)
    acceptance = acceptance_snapshot(node, required=True)
    dispatch = ensure_matching_dispatch(
        acceptance,
        expected_phase="auditor_running",
        expected_role="auditor",
        dispatch_id=dispatch_id,
    )
    acceptance = refresh_preparation(location, node)
    if acceptance.get("phase") != "auditor_running":
        write_location_and_sync_plan(location)
        return node
    binding = current_regression_binding(location)
    if any(dispatch.get(field) != binding[field] for field in binding):
        raise ToolError("audit verdict does not match the current regression fingerprint")

    if not passed:
        phase = acceptance_transition("auditor_running", "audit-failed", node_role)
        clear_regression_proof(node)
        node["acceptance"] = {
            "phase": phase,
            "attempt": int(acceptance["attempt"]),
            "outcome": "audit_failed",
            **_delivery_preparation_binding(location, acceptance),
        }
        if node_role == "final_validation":
            node["status"] = "pending"
            node.pop("status_reason", None)
        write_location_and_sync_plan(location)
        return node

    phase = acceptance_transition("auditor_running", "audit-passed", "auditor")
    regression = validated_regression_contract(location)
    criteria = node.get("acceptance_criteria")
    if not isinstance(criteria, list):
        raise ToolError("acceptance criteria are unavailable for automatic completion")
    for criterion_index in regression["criteria"]:
        criterion = criteria[criterion_index]
        if not isinstance(criterion, dict):
            raise ToolError("acceptance criteria are invalid for automatic completion")
        criterion["checked"] = True
    node["acceptance"] = {
        "phase": phase,
        "attempt": int(acceptance["attempt"]),
        "outcome": "accepted",
        "audit": {"recorded_at": evidence_timestamp(), **binding},
        **_delivery_preparation_binding(location, acceptance),
    }
    node["status"] = "completed"
    node.pop("status_reason", None)
    write_location_and_sync_plan(location)
    return node


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

    current = preparation_fingerprints(location)
    approved_is_current = all(acceptance.get(field) == value for field, value in current.items())
    node["acceptance"] = (
        {
            "phase": acceptance_transition("awaiting_repair", "repair-completed", "final_validation"),
            "attempt": int(acceptance["attempt"]),
            "outcome": "none",
            **current,
        }
        if approved_is_current
        else {
            "phase": "acceptance_revision_required",
            "attempt": int(acceptance["attempt"]),
            "outcome": "none",
        }
    )
    node["status"] = "pending"
    node.pop("status_reason", None)
    write_location_and_sync_plan(location)
    return node


def advance_command(args: argparse.Namespace) -> int:
    repair_events = {"repair-registered", "repair-completed"}
    if args.event in repair_events:
        if args.dispatch_id is not None:
            raise ToolError("repair handoff events reject --dispatch-id")
        repair_node_id = ensure_repair_node_id(args.repair_node)
        dispatch_id = None
    else:
        if args.repair_node is not None:
            raise ToolError("executor, regression, and audit events reject --repair-node")
        dispatch_id = ensure_event_id(args.dispatch_id)
        repair_node_id = None

    manifest = workspace_manifest_path(Path(args.root))
    location = locate_node(manifest, args.node_id)
    ensure_location_is_valid(location)

    if args.event == "acceptance-designer-exited":
        assert dispatch_id is not None
        node = advance_acceptance_design_exit(location, dispatch_id)
    elif args.event == "acceptance-approved":
        assert dispatch_id is not None
        node = advance_acceptance_review(location, dispatch_id, passed=True)
    elif args.event == "acceptance-rejected":
        assert dispatch_id is not None
        node = advance_acceptance_review(location, dispatch_id, passed=False)
    elif args.event == "executor-exited":
        assert dispatch_id is not None
        node = advance_executor_exit(location, dispatch_id)
    elif args.event == "regression-requested":
        node = location.checkpoints_data[location.node_index]
        if node.get("acceptance", {}).get("phase") != "awaiting_regression" and "acceptance" in node:
            raise ToolError("acceptance event is out of order for the current phase")
        node = advance_final_regression(location)
    elif args.event == "audit-failed":
        assert dispatch_id is not None
        node = advance_audit_verdict(location, dispatch_id, passed=False)
    elif args.event == "audit-passed":
        assert dispatch_id is not None
        node = advance_audit_verdict(location, dispatch_id, passed=True)
    elif args.event == "repair-registered":
        assert repair_node_id is not None
        node = advance_repair_registration(location, repair_node_id)
    else:
        assert repair_node_id is not None
        node = advance_repair_completion(location, repair_node_id)

    print_acceptance_payload(node)
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
    if node.get("role") in REGRESSION_NODE_ROLES:
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


def pause_command(args: argparse.Namespace) -> int:
    for message in run_node_mutation(args.root, args.node_id, "pending", reason=args.reason, require_current="in_progress"):
        print(message)
    return 0
