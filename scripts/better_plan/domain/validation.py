"""Validation layer for Better Plan workflow state."""

from __future__ import annotations

from typing import Any, Mapping, Sequence
from pathlib import Path
from .design import independent_ownership_issues, normalize_design_path, paths_overlap, validate_design_contract as _validate_design_contract
from .models import ACCEPTANCE_AUDIT_FIELDS, ACCEPTANCE_DESIGNER_DISPATCH_REQUIRED_FIELDS, ACCEPTANCE_DISPATCH_OPTIONAL_FIELDS, ACCEPTANCE_DISPATCH_REQUIRED_FIELDS, ACCEPTANCE_FAILURE_OUTCOMES, ACCEPTANCE_OPTIONAL_FIELDS, ACCEPTANCE_OUTCOMES, ACCEPTANCE_PHASES, ACCEPTANCE_PREPARATION_FIELDS, ACCEPTANCE_REQUIRED_FIELDS, COMMIT_OPTIONAL_FIELDS, COMMIT_REQUIRED_FIELDS, CRITERION_OPTIONAL_FIELDS, CRITERION_REQUIRED_FIELDS, EVIDENCE_REF_FIELDS, EVIDENCE_REF_TYPES, FOUNDATION_ROLE_ORDER, GIT_SHA_PATTERN, HIGH_OR_DEEP_REQUIRED_ROLES, Issue, REGRESSION_NODE_ROLES, REGRESSION_OPTIONAL_FIELDS, REGRESSION_RECEIPT_FIELDS, REGRESSION_REQUIRED_FIELDS, SHA256_PATTERN, TASK_OPTIONAL_FIELDS, TASK_REQUIRED_FIELDS, UUID4_PATTERN, VALID_DIFFICULTIES, VALID_NODE_ROLES, VALID_PLATFORMS, VALID_REGRESSION_SCOPES, WORKFLOW_STATE_MACHINE, expected_regression_scope, is_git_entry_path, is_manifest_id, is_relative_workspace_path, is_requirement_label, is_string_list, normalize_workspace_path, safe_summary_issue


def validate_regression_contract(
    path: Path,
    prefix: str,
    node: dict[str, Any],
    criterion_count: int,
) -> list[Issue]:
    issues: list[Issue] = []
    role = node.get("role")
    status = node.get("status")
    regression = node.get("regression")
    required_scope = expected_regression_scope(role)

    if regression is None:
        if required_scope is not None and status == "in_progress":
            issues.append(
                Issue(
                    path,
                    f"{prefix}.regression: in-progress {role!r} nodes must declare a {required_scope!r} regression contract",
                )
            )
        return issues
    if not isinstance(regression, dict):
        return [Issue(path, f"{prefix}.regression: must be an object")]

    for field in sorted(REGRESSION_REQUIRED_FIELDS - set(regression)):
        issues.append(Issue(path, f"{prefix}.regression.{field}: missing required field"))
    for field in sorted(set(regression) - REGRESSION_REQUIRED_FIELDS - REGRESSION_OPTIONAL_FIELDS):
        issues.append(Issue(path, f"{prefix}.regression.{field}: unknown field"))

    scope = regression.get("scope")
    if scope not in VALID_REGRESSION_SCOPES:
        values = ", ".join(sorted(VALID_REGRESSION_SCOPES))
        issues.append(Issue(path, f"{prefix}.regression.scope: must be one of {values}"))
    elif required_scope is not None and scope != required_scope:
        issues.append(Issue(path, f"{prefix}.regression.scope: role {role!r} must use {required_scope!r}"))

    commands = regression.get("commands")
    if not is_string_list(commands) or not commands:
        issues.append(Issue(path, f"{prefix}.regression.commands: must be a non-empty array of command strings"))
    else:
        seen_commands: set[str] = set()
        for index, command in enumerate(commands):
            normalized = command.strip()
            if not normalized:
                issues.append(Issue(path, f"{prefix}.regression.commands[{index}]: must be a non-empty command"))
            elif normalized in seen_commands:
                issues.append(Issue(path, f"{prefix}.regression.commands[{index}]: duplicate command"))
            else:
                seen_commands.add(normalized)

    criteria = regression.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        issues.append(Issue(path, f"{prefix}.regression.criteria: must be a non-empty array of criterion indexes"))
    else:
        seen_criteria: set[int] = set()
        for index, criterion_index in enumerate(criteria):
            if type(criterion_index) is not int:
                issues.append(Issue(path, f"{prefix}.regression.criteria[{index}]: must be an integer"))
            elif criterion_index < 0 or criterion_index >= criterion_count:
                issues.append(
                    Issue(
                        path,
                        f"{prefix}.regression.criteria[{index}]: must be between 0 and {max(criterion_count - 1, 0)}",
                    )
                )
            elif criterion_index in seen_criteria:
                issues.append(Issue(path, f"{prefix}.regression.criteria[{index}]: duplicate criterion index"))
            else:
                seen_criteria.add(criterion_index)

        automated = role in REGRESSION_NODE_ROLES and (
            status not in WORKFLOW_STATE_MACHINE.terminal_statuses or "acceptance" in node
        )
        if automated and seen_criteria != set(range(criterion_count)):
            issues.append(
                Issue(
                    path,
                    f"{prefix}.regression.criteria: automated delivery nodes must map every acceptance criterion exactly once",
                )
            )

    paths = regression.get("paths")
    if not is_string_list(paths) or not paths:
        issues.append(Issue(path, f"{prefix}.regression.paths: must be a non-empty array of repository-relative paths"))
    else:
        normalized_paths: list[str] = []
        for index, value in enumerate(paths):
            if not is_relative_workspace_path(value):
                issues.append(Issue(path, f"{prefix}.regression.paths[{index}]: must be a safe repository-relative path"))
                continue
            normalized = normalize_workspace_path(value)
            if normalized in normalized_paths:
                issues.append(Issue(path, f"{prefix}.regression.paths[{index}]: duplicate path {normalized!r}"))
                continue
            overlap = next(
                (
                    other
                    for other in normalized_paths
                    if normalized.startswith(f"{other}/") or other.startswith(f"{normalized}/")
                ),
                None,
            )
            if overlap is not None:
                issues.append(
                    Issue(
                        path,
                        f"{prefix}.regression.paths[{index}]: overlaps declared path {overlap!r}; keep one smallest path root",
                    )
                )
            normalized_paths.append(normalized)

    if "last_pass" in regression:
        receipt = regression.get("last_pass")
        if not isinstance(receipt, dict):
            issues.append(Issue(path, f"{prefix}.regression.last_pass: must be an object"))
        else:
            for field in sorted(REGRESSION_RECEIPT_FIELDS - set(receipt)):
                issues.append(Issue(path, f"{prefix}.regression.last_pass.{field}: missing required field"))
            for field in sorted(set(receipt) - REGRESSION_RECEIPT_FIELDS):
                issues.append(Issue(path, f"{prefix}.regression.last_pass.{field}: unknown field"))
            recorded_at = receipt.get("recorded_at")
            if not isinstance(recorded_at, str) or not recorded_at.strip():
                issues.append(Issue(path, f"{prefix}.regression.last_pass.recorded_at: must be a non-empty timestamp"))
            for field in ("contract_digest", "content_fingerprint"):
                value = receipt.get(field)
                if not isinstance(value, str) or not SHA256_PATTERN.fullmatch(value):
                    issues.append(Issue(path, f"{prefix}.regression.last_pass.{field}: must be a lowercase sha256 digest"))

    return issues


def validate_node_design_contract(path: Path, prefix: str, node: dict[str, Any]) -> list[Issue]:
    """Validate the pure machine-readable design boundary for delivery Nodes."""
    role = node.get("role")
    status = node.get("status")
    design = node.get("design")
    requires_design = role in REGRESSION_NODE_ROLES and status not in WORKFLOW_STATE_MACHINE.terminal_statuses
    if design is None:
        return [Issue(path, f"{prefix}.design: nonterminal delivery nodes require a design contract")] if requires_design else []
    if not isinstance(design, dict):
        return [Issue(path, f"{prefix}.design: must be an object")]

    issues = [Issue(path, f"{prefix}.design: {message}") for message in _validate_design_contract(design)]
    if issues:
        return issues

    owned_paths = [normalize_design_path(value) for value in design["owned_paths"]]
    acceptance_paths = [normalize_design_path(value) for value in design["acceptance_paths"]]
    for acceptance_path in acceptance_paths:
        if any(paths_overlap(acceptance_path, owned_path) for owned_path in owned_paths):
            issues.append(
                Issue(
                    path,
                    f"{prefix}.design.acceptance_paths: acceptance ownership must not overlap executor ownership",
                )
            )
            break
    return issues


def validate_acceptance_snapshot(path: Path, prefix: str, node: dict[str, Any]) -> list[Issue]:
    """Validate bounded automated-acceptance state without consulting runtime data."""
    if "acceptance" not in node:
        return []

    issues: list[Issue] = []
    acceptance = node.get("acceptance")
    if not isinstance(acceptance, dict):
        return [Issue(path, f"{prefix}.acceptance: must be an object")]

    for field in sorted(ACCEPTANCE_REQUIRED_FIELDS - set(acceptance)):
        issues.append(Issue(path, f"{prefix}.acceptance.{field}: missing required field"))
    for field in sorted(set(acceptance) - ACCEPTANCE_REQUIRED_FIELDS - ACCEPTANCE_OPTIONAL_FIELDS):
        issues.append(Issue(path, f"{prefix}.acceptance.{field}: unknown field"))

    role = node.get("role")
    status = node.get("status")
    phase = acceptance.get("phase")
    attempt = acceptance.get("attempt")
    outcome = acceptance.get("outcome")

    if role not in REGRESSION_NODE_ROLES:
        issues.append(Issue(path, f"{prefix}.acceptance: only implementation and final_validation nodes may be enrolled"))
    if phase not in ACCEPTANCE_PHASES:
        values = ", ".join(sorted(ACCEPTANCE_PHASES))
        issues.append(Issue(path, f"{prefix}.acceptance.phase: must be one of {values}"))
    if type(attempt) is not int or attempt < 0:
        issues.append(Issue(path, f"{prefix}.acceptance.attempt: must be a non-negative integer"))
    if outcome not in ACCEPTANCE_OUTCOMES:
        values = ", ".join(sorted(ACCEPTANCE_OUTCOMES))
        issues.append(Issue(path, f"{prefix}.acceptance.outcome: must be one of {values}"))

    if role == "implementation" and phase in {"awaiting_regression", "repair_plan_required", "awaiting_repair"}:
        issues.append(Issue(path, f"{prefix}.acceptance.phase: phase {phase!r} is not valid for implementation"))
    if role == "final_validation" and phase in {"awaiting_executor", "executor_running", "correction_required"}:
        issues.append(Issue(path, f"{prefix}.acceptance.phase: phase {phase!r} is not valid for final_validation"))

    if phase == "accepted":
        if status != "completed":
            issues.append(Issue(path, f"{prefix}.status: an accepted node must be completed"))
    elif phase in {
        "awaiting_acceptance_design",
        "acceptance_revision_required",
        "awaiting_executor",
        "awaiting_regression",
    }:
        if status not in {"pending", "blocked"}:
            issues.append(
                Issue(
                    path,
                    f"{prefix}.status: a resumable node in phase {phase!r} must be pending or blocked",
                )
            )
    elif phase in {"repair_plan_required", "awaiting_repair"}:
        if status not in {"pending", "blocked"}:
            issues.append(
                Issue(
                    path,
                    f"{prefix}.status: a parked final_validation node in phase {phase!r} must be pending or blocked",
                )
            )
    elif status != "in_progress":
        issues.append(Issue(path, f"{prefix}.status: an enrolled node in phase {phase!r} must be in_progress"))

    expected_outcomes: dict[str, set[str]] = {
        "awaiting_acceptance_design": {"none"},
        "acceptance_designer_running": {"none"},
        "acceptance_revision_required": {"none"},
        "awaiting_executor": {"none"},
        "executor_running": {"none"},
        "awaiting_regression": {"none"},
        "awaiting_auditor": {"regression_passed"},
        "auditor_running": {"regression_passed"},
        "correction_required": ACCEPTANCE_FAILURE_OUTCOMES,
        "repair_plan_required": ACCEPTANCE_FAILURE_OUTCOMES,
        "awaiting_repair": ACCEPTANCE_FAILURE_OUTCOMES,
        "accepted": {"accepted"},
    }
    if phase in expected_outcomes and outcome not in expected_outcomes[phase]:
        values = ", ".join(sorted(expected_outcomes[phase]))
        issues.append(Issue(path, f"{prefix}.acceptance.outcome: phase {phase!r} requires one of {values}"))

    repair_node_id = acceptance.get("repair_node_id")
    if phase == "awaiting_repair":
        if not isinstance(repair_node_id, str) or not UUID4_PATTERN.fullmatch(repair_node_id):
            issues.append(Issue(path, f"{prefix}.acceptance.repair_node_id: awaiting_repair requires a UUID4 node id"))
    elif "repair_node_id" in acceptance:
        issues.append(Issue(path, f"{prefix}.acceptance.repair_node_id: only awaiting_repair may bind a repair node"))

    dispatch = acceptance.get("dispatch")
    dispatch_roles = {
        "acceptance_designer_running": "acceptance_designer",
        "executor_running": "executor",
        "auditor_running": "auditor",
    }
    dispatch_required = phase in dispatch_roles
    if dispatch_required and not isinstance(dispatch, dict):
        issues.append(Issue(path, f"{prefix}.acceptance.dispatch: phase {phase!r} requires an outstanding dispatch"))
    elif not dispatch_required and "dispatch" in acceptance:
        issues.append(Issue(path, f"{prefix}.acceptance.dispatch: only running agent phases may retain a dispatch"))
    elif isinstance(dispatch, dict):
        for field in sorted(ACCEPTANCE_DISPATCH_REQUIRED_FIELDS - set(dispatch)):
            issues.append(Issue(path, f"{prefix}.acceptance.dispatch.{field}: missing required field"))
        allowed = ACCEPTANCE_DISPATCH_REQUIRED_FIELDS | ACCEPTANCE_DISPATCH_OPTIONAL_FIELDS
        for field in sorted(set(dispatch) - allowed):
            issues.append(Issue(path, f"{prefix}.acceptance.dispatch.{field}: unknown field"))
        dispatch_id = dispatch.get("id")
        if not isinstance(dispatch_id, str) or not UUID4_PATTERN.fullmatch(dispatch_id):
            issues.append(Issue(path, f"{prefix}.acceptance.dispatch.id: must be an opaque UUID4 correlation id"))
        dispatch_role = dispatch.get("role")
        expected_role = dispatch_roles.get(str(phase))
        if dispatch_role != expected_role:
            issues.append(Issue(path, f"{prefix}.acceptance.dispatch.role: phase {phase!r} requires role {expected_role!r}"))
        regression_digest_fields = {"contract_digest", "content_fingerprint"}
        if expected_role == "auditor":
            for field in regression_digest_fields:
                value = dispatch.get(field)
                if not isinstance(value, str) or not SHA256_PATTERN.fullmatch(value):
                    issues.append(Issue(path, f"{prefix}.acceptance.dispatch.{field}: must be a lowercase sha256 digest"))
            for field in set(ACCEPTANCE_PREPARATION_FIELDS) & set(dispatch):
                issues.append(Issue(path, f"{prefix}.acceptance.dispatch.{field}: auditor dispatches use the regression receipt only"))
        elif expected_role == "acceptance_designer":
            for field in sorted(ACCEPTANCE_DESIGNER_DISPATCH_REQUIRED_FIELDS - set(dispatch)):
                issues.append(Issue(path, f"{prefix}.acceptance.dispatch.{field}: missing required field"))
            value = dispatch.get("design_digest")
            if not isinstance(value, str) or not SHA256_PATTERN.fullmatch(value):
                issues.append(Issue(path, f"{prefix}.acceptance.dispatch.design_digest: must bind the current design digest"))
            for field in {"acceptance_fingerprint", "scaffold_fingerprint", *regression_digest_fields} & set(dispatch):
                issues.append(Issue(path, f"{prefix}.acceptance.dispatch.{field}: acceptance designer dispatch has an invalid binding"))
        else:
            for field in (regression_digest_fields | set(ACCEPTANCE_PREPARATION_FIELDS)) & set(dispatch):
                issues.append(Issue(path, f"{prefix}.acceptance.dispatch.{field}: executor dispatches must not retain fingerprints"))

    for field in ACCEPTANCE_PREPARATION_FIELDS:
        if field in acceptance:
            value = acceptance.get(field)
            if not isinstance(value, str) or not SHA256_PATTERN.fullmatch(value):
                issues.append(Issue(path, f"{prefix}.acceptance.{field}: must be a lowercase sha256 digest"))

    audit = acceptance.get("audit")
    if phase == "accepted" and not isinstance(audit, dict):
        issues.append(Issue(path, f"{prefix}.acceptance.audit: accepted phase requires an audit receipt"))
    elif phase != "accepted" and "audit" in acceptance:
        issues.append(Issue(path, f"{prefix}.acceptance.audit: only accepted nodes may retain an audit receipt"))
    elif isinstance(audit, dict):
        for field in sorted(ACCEPTANCE_AUDIT_FIELDS - set(audit)):
            issues.append(Issue(path, f"{prefix}.acceptance.audit.{field}: missing required field"))
        for field in sorted(set(audit) - ACCEPTANCE_AUDIT_FIELDS):
            issues.append(Issue(path, f"{prefix}.acceptance.audit.{field}: unknown field"))
        recorded_at = audit.get("recorded_at")
        if not isinstance(recorded_at, str) or not recorded_at.strip():
            issues.append(Issue(path, f"{prefix}.acceptance.audit.recorded_at: must be a non-empty timestamp"))
        for field in ("contract_digest", "content_fingerprint"):
            value = audit.get(field)
            if not isinstance(value, str) or not SHA256_PATTERN.fullmatch(value):
                issues.append(Issue(path, f"{prefix}.acceptance.audit.{field}: must be a lowercase sha256 digest"))

    regression = node.get("regression")
    last_pass = regression.get("last_pass") if isinstance(regression, dict) else None
    if phase in {"awaiting_auditor", "auditor_running", "accepted"} and not isinstance(last_pass, dict):
        issues.append(Issue(path, f"{prefix}.regression.last_pass: phase {phase!r} requires a passing regression receipt"))
    if phase in {
        "awaiting_acceptance_design",
        "acceptance_designer_running",
        "acceptance_revision_required",
        "awaiting_executor",
        "executor_running",
        "correction_required",
        "awaiting_regression",
        "repair_plan_required",
        "awaiting_repair",
    } and isinstance(last_pass, dict):
        issues.append(Issue(path, f"{prefix}.regression.last_pass: phase {phase!r} must not retain an obsolete receipt"))

    if isinstance(dispatch, dict) and dispatch.get("role") == "auditor" and isinstance(last_pass, dict):
        for field in ("contract_digest", "content_fingerprint"):
            if dispatch.get(field) != last_pass.get(field):
                issues.append(Issue(path, f"{prefix}.acceptance.dispatch.{field}: must bind the current regression receipt"))
    if isinstance(audit, dict) and isinstance(last_pass, dict):
        for field in ("contract_digest", "content_fingerprint"):
            if audit.get(field) != last_pass.get(field):
                issues.append(Issue(path, f"{prefix}.acceptance.audit.{field}: must bind the accepted regression receipt"))

    return issues


def validate_checkpoints_data(path: Path, data: list[Any]) -> tuple[int, list[Issue]]:
    issues: list[Issue] = []
    seen: set[str] = set()

    for index, node in enumerate(data):
        prefix = f"node[{index}]"
        if not isinstance(node, dict):
            issues.append(Issue(path, f"{prefix}: must be an object"))
            continue

        missing = sorted(TASK_REQUIRED_FIELDS - set(node))
        for field in missing:
            issues.append(Issue(path, f"{prefix}.{field}: missing required field"))

        extra = sorted(set(node) - TASK_REQUIRED_FIELDS - TASK_OPTIONAL_FIELDS)
        for field in extra:
            issues.append(Issue(path, f"{prefix}.{field}: unknown field"))

        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id.strip():
            issues.append(Issue(path, f"{prefix}.id: must be a non-empty string"))
        else:
            if not is_manifest_id(node_id):
                issues.append(Issue(path, f"{prefix}.id: must be a UUID4 value; generate ids with the manifest tool's uuid command"))
            if node_id in seen:
                issues.append(Issue(path, f"{prefix}.id: duplicate id {node_id!r}"))
            else:
                seen.add(node_id)

        status_issue = WORKFLOW_STATE_MACHINE.status_issue(path, prefix, node.get("status"))
        if status_issue is not None:
            issues.append(status_issue)

        difficulty = node.get("difficulty")
        if difficulty not in VALID_DIFFICULTIES:
            values = ", ".join(sorted(VALID_DIFFICULTIES))
            issues.append(Issue(path, f"{prefix}.difficulty: must be one of {values}"))

        role = node.get("role")
        if role not in VALID_NODE_ROLES:
            values = ", ".join(sorted(VALID_NODE_ROLES))
            issues.append(Issue(path, f"{prefix}.role: must be one of {values}"))

        for field in ("prerequisites", "next"):
            if not is_string_list(node.get(field)):
                issues.append(Issue(path, f"{prefix}.{field}: must be an array of strings"))

        if "requirements" in node:
            requirements = node.get("requirements")
            if not is_string_list(requirements):
                issues.append(Issue(path, f"{prefix}.requirements: must be an array of requirement label strings"))
            else:
                seen_labels: set[str] = set()
                for label_index, label in enumerate(requirements):
                    if not is_requirement_label(label):
                        issues.append(
                            Issue(
                                path,
                                f"{prefix}.requirements[{label_index}]: must use the canonical format 'REQ-...' "
                                "with REQ first and hyphen-delimited alphanumeric segments, such as 'REQ-001'",
                            )
                        )
                    elif label in seen_labels:
                        issues.append(Issue(path, f"{prefix}.requirements[{label_index}]: duplicate label {label!r}"))
                    else:
                        seen_labels.add(label)

        if "status_reason" in node:
            status_reason = node.get("status_reason")
            reason_issue = safe_summary_issue(status_reason)
            if reason_issue is not None:
                issues.append(Issue(path, f"{prefix}.status_reason: {reason_issue}"))

        acceptance_criteria = node.get("acceptance_criteria")
        if not isinstance(acceptance_criteria, list):
            issues.append(Issue(path, f"{prefix}.acceptance_criteria: must be a non-empty array of checkbox objects"))
        elif not acceptance_criteria:
            issues.append(Issue(path, f"{prefix}.acceptance_criteria: must not be empty"))
        else:
            for criterion_index, criterion in enumerate(acceptance_criteria):
                criterion_prefix = f"{prefix}.acceptance_criteria[{criterion_index}]"
                if not isinstance(criterion, dict):
                    issues.append(Issue(path, f"{criterion_prefix}: must be an object"))
                    continue
                missing_criterion_fields = sorted(CRITERION_REQUIRED_FIELDS - set(criterion))
                for field in missing_criterion_fields:
                    issues.append(Issue(path, f"{criterion_prefix}.{field}: missing required field"))
                extra_criterion_fields = sorted(set(criterion) - CRITERION_REQUIRED_FIELDS - CRITERION_OPTIONAL_FIELDS)
                for field in extra_criterion_fields:
                    issues.append(Issue(path, f"{criterion_prefix}.{field}: unknown field"))
                if type(criterion.get("checked")) is not bool:
                    issues.append(Issue(path, f"{criterion_prefix}.checked: must be a boolean"))
                if not isinstance(criterion.get("text"), str) or not criterion.get("text", "").strip():
                    issues.append(Issue(path, f"{criterion_prefix}.text: must be a non-empty string"))
                if "evidence" in criterion:
                    evidence = criterion.get("evidence")
                    evidence_issue = safe_summary_issue(evidence)
                    if evidence_issue is not None:
                        issues.append(Issue(path, f"{criterion_prefix}.evidence: {evidence_issue}"))
                if "evidence_refs" in criterion:
                    issues.extend(validate_evidence_refs(path, criterion_prefix, criterion.get("evidence_refs")))

        criterion_count = len(acceptance_criteria) if isinstance(acceptance_criteria, list) else 0
        issues.extend(validate_node_design_contract(path, prefix, node))
        issues.extend(validate_regression_contract(path, prefix, node, criterion_count))
        issues.extend(validate_acceptance_snapshot(path, prefix, node))

        platform = node.get("platform")
        if platform not in VALID_PLATFORMS:
            values = ", ".join(sorted(VALID_PLATFORMS))
            issues.append(Issue(path, f"{prefix}.platform: must be one of {values}"))

        for field in ("goal", "description"):
            if not isinstance(node.get(field), str) or not node.get(field, "").strip():
                issues.append(Issue(path, f"{prefix}.{field}: must be a non-empty string"))

        commit = node.get("commit")
        if not isinstance(commit, dict):
            issues.append(Issue(path, f"{prefix}.commit: must be an object"))
        else:
            for field in ("repository", "message", "target"):
                value = commit.get(field)
                if not isinstance(value, str) or not value.strip():
                    issues.append(Issue(path, f"{prefix}.commit.{field}: must be a non-empty string"))
            if not is_git_entry_path(commit.get("repository")):
                issues.append(Issue(path, f"{prefix}.commit.repository: must point to a .git filesystem entry"))
            if "delivered" in commit:
                delivered = commit.get("delivered")
                if not isinstance(delivered, str) or not GIT_SHA_PATTERN.fullmatch(delivered):
                    issues.append(Issue(path, f"{prefix}.commit.delivered: must be a lowercase hex commit sha (7-40 characters) when present"))
            extra_commit_fields = sorted(set(commit) - COMMIT_REQUIRED_FIELDS - COMMIT_OPTIONAL_FIELDS)
            for field in extra_commit_fields:
                issues.append(Issue(path, f"{prefix}.commit.{field}: unknown field"))

    for index, node in enumerate(data):
        if not isinstance(node, dict):
            continue
        for field in ("prerequisites", "next"):
            refs = node.get(field)
            if isinstance(refs, list):
                for ref in refs:
                    if not isinstance(ref, str):
                        continue
                    if not is_manifest_id(ref):
                        issues.append(
                            Issue(path, f"node[{index}].{field}: must contain UUID4 node ids")
                        )

    issues.extend(validate_independent_design_ownership(path, data))
    issues.extend(validate_delivery_roles(path, data))
    issues.extend(validate_requirement_traceability(path, data))
    issues.extend(WORKFLOW_STATE_MACHINE.checkpoint_snapshot_issues(path, data))
    return len(data), issues


def dependency_cycle_path(
    graph: Mapping[str, Sequence[str]],
) -> list[str] | None:
    """Return one exact closed cycle path using iterative O(V + E) traversal."""
    white = 0
    gray = 1
    black = 2
    color: dict[str, int] = {}
    active_path: list[str] = []
    active_positions: dict[str, int] = {}

    for root in graph:
        if color.get(root, white) != white:
            continue

        color[root] = gray
        active_positions[root] = len(active_path)
        active_path.append(root)
        frames: list[tuple[str, int]] = [(root, 0)]

        while frames:
            node_id, offset = frames[-1]
            dependencies = graph.get(node_id, ())
            if offset >= len(dependencies):
                frames.pop()
                color[node_id] = black
                active_positions.pop(node_id, None)
                active_path.pop()
                continue

            dependency = dependencies[offset]
            frames[-1] = (node_id, offset + 1)
            if dependency not in graph:
                continue

            dependency_color = color.get(dependency, white)
            if dependency_color == white:
                color[dependency] = gray
                active_positions[dependency] = len(active_path)
                active_path.append(dependency)
                frames.append((dependency, 0))
                continue
            if dependency_color == gray:
                start = active_positions[dependency]
                return [*active_path[start:], dependency]

    return None


def validate_evidence_refs(path: Path, prefix: str, refs: Any) -> list[Issue]:
    issues: list[Issue] = []
    if not isinstance(refs, list) or not refs:
        issues.append(Issue(path, f"{prefix}.evidence_refs: must be a non-empty array of evidence reference objects"))
        return issues

    for ref_index, ref in enumerate(refs):
        ref_prefix = f"{prefix}.evidence_refs[{ref_index}]"
        if not isinstance(ref, dict):
            issues.append(Issue(path, f"{ref_prefix}: must be an object"))
            continue
        ref_type = ref.get("type")
        if ref_type not in EVIDENCE_REF_TYPES:
            values = ", ".join(sorted(EVIDENCE_REF_TYPES))
            issues.append(Issue(path, f"{ref_prefix}.type: must be one of {values}"))
            continue
        expected_fields = EVIDENCE_REF_FIELDS[str(ref_type)]
        for field in sorted(expected_fields - set(ref)):
            issues.append(Issue(path, f"{ref_prefix}.{field}: missing required field"))
        for field in sorted(set(ref) - expected_fields):
            issues.append(Issue(path, f"{ref_prefix}.{field}: unknown field"))
        recorded_at = ref.get("recorded_at")
        if "recorded_at" in ref and (not isinstance(recorded_at, str) or not recorded_at.strip()):
            issues.append(Issue(path, f"{ref_prefix}.recorded_at: must be a non-empty timestamp string"))
        if ref_type == "file":
            if "path" in ref and not is_relative_workspace_path(ref.get("path")):
                issues.append(Issue(path, f"{ref_prefix}.path: must be a safe repository-relative path"))
            sha256 = ref.get("sha256")
            if "sha256" in ref and (not isinstance(sha256, str) or not SHA256_PATTERN.fullmatch(sha256)):
                issues.append(Issue(path, f"{ref_prefix}.sha256: must be a 64-character lowercase hex digest"))
        else:
            command_sha256 = ref.get("command_sha256")
            if "command_sha256" in ref and (
                not isinstance(command_sha256, str) or not SHA256_PATTERN.fullmatch(command_sha256)
            ):
                issues.append(Issue(path, f"{ref_prefix}.command_sha256: must be a 64-character lowercase hex digest"))
            exit_code = ref.get("exit_code")
            if "exit_code" in ref and (type(exit_code) is not int or exit_code != 0):
                issues.append(Issue(path, f"{ref_prefix}.exit_code: must be the integer 0; command evidence must record a passing run"))

    return issues


def validate_independent_design_ownership(path: Path, data: Any) -> list[Issue]:
    if not isinstance(data, list):
        return []

    graph: dict[str, tuple[str, ...]] = {}
    designed_nodes: list[dict[str, Any]] = []
    for node in data:
        if not isinstance(node, dict) or node.get("role") not in REGRESSION_NODE_ROLES:
            continue
        node_id = node.get("id")
        prerequisites = node.get("prerequisites")
        design = node.get("design")
        if not isinstance(node_id, str) or not is_string_list(prerequisites) or not isinstance(design, dict):
            continue
        if _validate_design_contract(design):
            continue
        graph[node_id] = tuple(prerequisites)
        designed_nodes.append({"id": node_id, "owned_paths": list(design["owned_paths"])})

    reachability_cache: dict[tuple[str, str], bool] = {}

    def reachable(source: str, target: str) -> bool:
        key = (source, target)
        if key in reachability_cache:
            return reachability_cache[key]
        stack = list(graph.get(source, ()))
        visited: set[str] = set()
        while stack:
            current = stack.pop()
            if current == target:
                reachability_cache[key] = True
                return True
            if current in visited:
                continue
            visited.add(current)
            stack.extend(graph.get(current, ()))
        reachability_cache[key] = False
        return False

    return [
        Issue(path, f"delivery design: {message}")
        for message in independent_ownership_issues(designed_nodes, reachable)
    ]


def validate_delivery_roles(path: Path, data: Any) -> list[Issue]:
    if not isinstance(data, list):
        return []

    issues: list[Issue] = []
    role_indexes: dict[str, list[int]] = {}

    for index, node in enumerate(data):
        if not isinstance(node, dict):
            continue
        role = node.get("role")
        if isinstance(role, str) and role in VALID_NODE_ROLES:
            role_indexes.setdefault(role, []).append(index)
            difficulty = node.get("difficulty")
            if role in HIGH_OR_DEEP_REQUIRED_ROLES and difficulty not in {"high", "deep"}:
                issues.append(Issue(path, f"node[{index}].difficulty: role {role!r} must use 'high' or 'deep'"))

    first_indexes = {role: indexes[0] for role, indexes in role_indexes.items()}
    for before, after in zip(FOUNDATION_ROLE_ORDER, FOUNDATION_ROLE_ORDER[1:]):
        if before in first_indexes and after in first_indexes and first_indexes[before] > first_indexes[after]:
            issues.append(Issue(path, f"delivery roles: {before!r} must appear before {after!r}"))

    validation_index = first_indexes.get("validation_matrix")
    for role in ("architecture_scaffold", "implementation"):
        if validation_index is not None and role in first_indexes and first_indexes[role] < validation_index:
            issues.append(Issue(path, f"delivery roles: {role!r} must not appear before 'validation_matrix'"))

    implementation_indexes = role_indexes.get("implementation", [])
    final_validation_indexes = role_indexes.get("final_validation", [])
    if implementation_indexes and final_validation_indexes:
        last_implementation = max(implementation_indexes)
        first_final_validation = min(final_validation_indexes)
        if first_final_validation < last_implementation:
            issues.append(Issue(path, "delivery roles: 'final_validation' must appear after implementation nodes"))

    return issues


def validate_requirement_traceability(path: Path, data: Any) -> list[Issue]:
    if not isinstance(data, list):
        return []

    issues: list[Issue] = []
    covered: set[str] = set()
    required: set[str] = set()
    active_final_validation = False

    for index, node in enumerate(data):
        if not isinstance(node, dict):
            continue
        role = node.get("role")
        if role not in VALID_NODE_ROLES:
            continue
        requirements = node.get("requirements")
        labels = (
            {label for label in requirements if is_requirement_label(label)}
            if is_string_list(requirements)
            else set()
        )
        skipped = node.get("status") == "skipped"

        if role == "final_validation":
            if not labels:
                issues.append(Issue(path, f"node[{index}].requirements: final_validation nodes must list the requirement labels they prove"))
            if not skipped:
                active_final_validation = True
                covered |= labels
            continue

        if role == "implementation":
            if not labels:
                description = node.get("description")
                text = description.lower() if isinstance(description, str) else ""
                if "enabling" not in text:
                    issues.append(
                        Issue(
                            path,
                            f"node[{index}].requirements: implementation nodes must list at least one requirement label "
                            "or describe enabling work in description",
                        )
                    )
            if not skipped:
                required |= labels

    if active_final_validation:
        missing = sorted(required - covered)
        if missing:
            values = ", ".join(missing)
            issues.append(Issue(path, f"delivery roles: final_validation must cover requirement label(s): {values}"))

    return issues
