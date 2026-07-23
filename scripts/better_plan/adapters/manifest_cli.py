"""Manifest Cli layer for Better Plan workflow state."""

from __future__ import annotations

from typing import Any
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys
from ..application.workflow import advance_command as _advance_command, block_command, complete_command, dispatch_command, invalidate_preparation_after_plan_edit, next_action_command, pause_command, regress_command, skip_command, start_command
from ..domain.design import DECISION_FIELDS, DESIGN_REQUIRED_FIELDS, SYMBOL_KINDS, SYMBOL_OPERATIONS, validate_design_contract as _validate_design_contract
from ..domain.models import ACCEPTANCE_OPTIONAL_FIELDS, ACCEPTANCE_OUTCOMES, ACCEPTANCE_PHASES, ACCEPTANCE_REQUIRED_FIELDS, CHECKPOINTS_NAME, COMMIT_OPTIONAL_FIELDS, COMMIT_REQUIRED_FIELDS, CRITERION_OPTIONAL_FIELDS, CRITERION_REQUIRED_FIELDS, EVIDENCE_COMMAND_TIMEOUT_SECONDS, Issue, MANIFEST_NAME, NODE_TEMPLATE, PLAN_OPTIONAL_FIELDS, PLAN_REQUIRED_FIELDS, PLAN_TEMPLATE, REGRESSION_NODE_ROLES, REGRESSION_OPTIONAL_FIELDS, REGRESSION_RECEIPT_FIELDS, REGRESSION_REQUIRED_FIELDS, REQUIREMENT_LABEL_PATTERN, STATUS_ORDER, TASK_OPTIONAL_FIELDS, TASK_REQUIRED_FIELDS, ToolError, VALID_DIFFICULTIES, VALID_NODE_ROLES, VALID_PLATFORMS, VALID_REGRESSION_SCOPES, WORKFLOW_STATE_MACHINE, derive_plan_status, expected_regression_scope, generate_id, is_manifest_id, is_relative_workspace_path, is_requirement_label, is_string_list, normalize_workspace_path, public_summary, safe_summary_issue
from ..domain.validation import validate_checkpoints_data as _validate_checkpoints_data
from ..infrastructure.regression import current_platform, evidence_timestamp, platform_matches
from ..infrastructure.workspace import NodeLocation as _NodeLocation, discover_workspace_manifests, find_manifests, git_transition_issues, load_plan_checkpoints, load_state_entries, locate_node, plan_document_labels, plan_label, project_root_for, referenced_checkpoints_files, relative_path_label, resolve_plan_entry, source_file_issues, validate_manifest, workspace_manifest_path, write_location_and_sync_plan, write_state_entries


def validate_command(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    display_root = root.parent if root.is_file() else root
    manifests = find_manifests(root)

    if not manifests:
        message = f"No {MANIFEST_NAME} or {CHECKPOINTS_NAME} files found at the supplied validation root"
        if args.json:
            print(json.dumps({"ok": False, "state_files": 0, "items": 0, "issues": [{"path": ".", "message": message}]}, indent=2))
        else:
            print(message, file=sys.stderr)
        return 1

    snapshot_indexes: set[int] | None = None
    if args.plan is not None:
        if manifests[0].name != MANIFEST_NAME:
            raise ToolError(f"--plan requires the Better Plan workspace root or its {MANIFEST_NAME}, not a single {CHECKPOINTS_NAME}")
        manifest_data = load_state_entries(manifests[0])
        plan_index, plan = resolve_plan_entry(manifests[0], manifest_data, args.plan)
        snapshot_indexes = {plan_index}
        checkpoints = plan.get("checkpoints")
        if is_relative_workspace_path(checkpoints):
            checkpoint_path = manifests[0].parent / normalize_workspace_path(str(checkpoints))
            if checkpoint_path.name == CHECKPOINTS_NAME and checkpoint_path.is_file():
                manifests.append(checkpoint_path)
    elif len(manifests) == 1 and manifests[0].name == MANIFEST_NAME:
        manifests.extend(referenced_checkpoints_files(manifests[0]))

    all_issues: list[Issue] = []
    total_entries = 0
    global_ids: dict[str, Path] = {}

    for manifest in manifests:
        entry_count, issues = validate_manifest(
            manifest,
            snapshot_indexes=snapshot_indexes if manifest.name == MANIFEST_NAME else None,
        )
        total_entries += entry_count
        all_issues.extend(issues)

        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        if not isinstance(data, list):
            continue

        if not args.no_git:
            all_issues.extend(git_transition_issues(manifest, data))

        if args.check_sources and manifest.name == MANIFEST_NAME:
            all_issues.extend(source_file_issues(manifest, data, include_indexes=snapshot_indexes))

        for index, node in enumerate(data):
            if not isinstance(node, dict) or not isinstance(node.get("id"), str):
                continue
            node_id = node["id"]
            other = global_ids.get(node_id)
            if other is not None and other != manifest:
                other_label = relative_path_label(other, display_root)
                all_issues.append(Issue(manifest, f"entry[{index}].id: duplicates id from {other_label}: {node_id!r}"))
            else:
                global_ids[node_id] = manifest

    if args.json:
        payload = {
            "ok": not all_issues,
            "state_files": len(manifests),
            "items": total_entries,
            "issues": [
                {"path": relative_path_label(issue.path, display_root), "message": issue.message}
                for issue in all_issues
            ],
        }
        print(json.dumps(payload, indent=2))
        return 1 if all_issues else 0

    if all_issues:
        for issue in all_issues:
            print(f"{relative_path_label(issue.path, display_root)}: {issue.message}", file=sys.stderr)
        print(
            f"Validated {len(manifests)} state file(s), {total_entries} item(s), "
            f"{len(all_issues)} issue(s).",
            file=sys.stderr,
        )
        return 1

    if not args.quiet:
        print(f"OK: validated {len(manifests)} state file(s), {total_entries} item(s).")
    return 0


def discover_command(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    manifests = discover_workspace_manifests(root)

    if not manifests:
        print("No structurally valid Better Plan workspaces found at the supplied search root", file=sys.stderr)
        return 1

    for manifest in manifests:
        print(relative_path_label(manifest.parent, root))
    return 0


def uuid_command(args: argparse.Namespace) -> int:
    for _ in range(args.count):
        print(generate_id())
    return 0


def platform_command(args: argparse.Namespace) -> int:
    platform = current_platform()
    if args.json:
        print(json.dumps({"platform": platform}))
    else:
        print(platform)
    return 0


def transition_command(args: argparse.Namespace) -> int:
    issues = WORKFLOW_STATE_MACHINE.transition_issues(Path("<state-machine>"), "transition", args.current, args.target)
    if issues:
        for issue in issues:
            print(issue.message, file=sys.stderr)
        return 1
    if not args.quiet:
        print(f"OK: {args.current} -> {args.target}")
    return 0


def file_evidence_ref(value: str, project_root: Path) -> dict[str, Any]:
    if not is_relative_workspace_path(value):
        raise ToolError("--evidence-file must be a repository-relative regular file inside the project root")
    normalized = normalize_workspace_path(value)
    root = project_root.resolve()
    path = root / normalized
    if path.is_symlink():
        raise ToolError("--evidence-file must not be a symbolic link")
    try:
        resolved = path.resolve()
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise ToolError("--evidence-file must stay inside the project root") from exc
    if not resolved.is_file():
        raise ToolError("--evidence-file must be a readable repository file")
    digest = hashlib.sha256()
    try:
        with resolved.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ToolError("--evidence-file could not be read") from exc
    return {
        "type": "file",
        "path": normalized,
        "sha256": digest.hexdigest(),
        "recorded_at": evidence_timestamp(),
    }


def command_evidence_ref(command: str, project_root: Path) -> dict[str, Any]:
    if not command.strip():
        raise ToolError("--evidence-cmd must be a non-empty command")
    try:
        result = subprocess.run(
            command,
            cwd=project_root,
            shell=True,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=EVIDENCE_COMMAND_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise ToolError("--evidence-cmd timed out; command output was discarded") from exc
    except OSError as exc:
        raise ToolError("--evidence-cmd could not be started; command output was discarded") from exc
    if result.returncode != 0:
        raise ToolError(
            f"--evidence-cmd exited with {result.returncode}; command output was discarded and no evidence was recorded"
        )
    return {
        "type": "command",
        "command_sha256": hashlib.sha256(command.strip().encode("utf-8")).hexdigest(),
        "exit_code": 0,
        "recorded_at": evidence_timestamp(),
    }


def check_command(args: argparse.Namespace) -> int:
    manifest = workspace_manifest_path(Path(args.root))
    location = locate_node(manifest, args.node_id)
    node = location.checkpoints_data[location.node_index]
    if node.get("role") in REGRESSION_NODE_ROLES:
        raise ToolError(
            f"node {args.node_id}: automated acceptance rejects direct check; use next-action, dispatch, and advance"
        )
    project_root = project_root_for(manifest.parent)

    criteria = node.get("acceptance_criteria")
    if not isinstance(criteria, list) or not criteria:
        raise ToolError(f"node {args.node_id}: acceptance_criteria must be a non-empty array")
    if not 0 <= args.criterion < len(criteria):
        raise ToolError(f"node {args.node_id}: criterion index must be between 0 and {len(criteria) - 1}")
    criterion = criteria[args.criterion]
    if not isinstance(criterion, dict):
        raise ToolError(f"node {args.node_id}: acceptance_criteria[{args.criterion}] must be an object")

    refs: list[dict[str, Any]] = []
    for value in args.evidence_cmd or []:
        refs.append(command_evidence_ref(value, project_root))
    for value in args.evidence_file or []:
        refs.append(file_evidence_ref(value, project_root))

    criterion["checked"] = True
    if args.evidence is not None:
        evidence_issue = safe_summary_issue(args.evidence)
        if evidence_issue is not None:
            raise ToolError(f"--evidence {evidence_issue}")
        criterion["evidence"] = args.evidence.strip()
    if refs:
        criterion["evidence_refs"] = refs

    _, issues = _validate_checkpoints_data(location.checkpoints_path, location.checkpoints_data)
    if issues:
        details = "\n".join(
            f"  {relative_path_label(issue.path, project_root)}: {issue.message}"
            for issue in issues
        )
        raise ToolError(f"refusing to write an invalid state file; fix these issues first:\n{details}")

    write_state_entries(location.checkpoints_path, location.checkpoints_data)
    suffix = f" with {len(refs)} evidence reference(s)" if refs else ""
    print(f"OK: node {args.node_id} acceptance_criteria[{args.criterion}] checked{suffix}")
    return 0


def parse_id_list(value: str | None) -> list[str] | None:
    if value is None:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def find_node_index(checkpoints_data: list[Any], node_id: str, checkpoints_path: Path) -> int:
    for index, node in enumerate(checkpoints_data):
        if isinstance(node, dict) and node.get("id") == node_id:
            return index
    raise ToolError(f"node {node_id} not found in {checkpoints_path.name}")


def plan_checkpoints_location(manifest: Path, manifest_data: list[Any], selector: str) -> tuple[int, dict[str, Any], Path, list[Any]]:
    plan_index, plan = resolve_plan_entry(manifest, manifest_data, selector)
    checkpoints_value = plan.get("checkpoints")
    if not is_relative_workspace_path(checkpoints_value):
        raise ToolError(f"plan {plan_label(plan, plan_index)!r}: checkpoints must be a relative path to {CHECKPOINTS_NAME}")
    checkpoints_path = manifest.parent / normalize_workspace_path(str(checkpoints_value))
    if checkpoints_path.name != CHECKPOINTS_NAME or not checkpoints_path.is_file():
        raise ToolError(
            f"plan {plan_label(plan, plan_index)!r}: missing checkpoints file "
            f"{normalize_workspace_path(str(checkpoints_value))}"
        )
    return plan_index, plan, checkpoints_path, load_state_entries(checkpoints_path)


def add_node_command(args: argparse.Namespace) -> int:
    manifest = workspace_manifest_path(Path(args.root))
    manifest_data = load_state_entries(manifest)
    plan_index, plan, checkpoints_path, checkpoints_data = plan_checkpoints_location(manifest, manifest_data, args.plan)

    node_id = args.id or generate_id()
    if not is_manifest_id(node_id):
        raise ToolError("--id must be a UUID4 value; generate ids with the uuid command")

    if args.after and args.before:
        raise ToolError("use only one of --after or --before")
    if args.splice and not args.after:
        raise ToolError("--splice requires --after <node-id>; splice inserts the new node into that node's outgoing chain")

    prerequisites = parse_id_list(args.prerequisites) or []
    next_refs = parse_id_list(args.next) or []
    requirements = parse_id_list(args.requirements)
    design: dict[str, Any] | None = None
    if args.design_json is not None:
        try:
            parsed_design = json.loads(args.design_json)
        except json.JSONDecodeError as exc:
            raise ToolError("--design-json must be a valid JSON object") from exc
        if not isinstance(parsed_design, dict):
            raise ToolError("--design-json must be a JSON object")
        design_issues = _validate_design_contract(parsed_design)
        if design_issues:
            raise ToolError(f"--design-json is invalid: {'; '.join(design_issues)}")
        design = parsed_design
    if args.role in REGRESSION_NODE_ROLES and design is None:
        raise ToolError(f"role {args.role!r} requires --design-json before the Node can be added")
    regression_values_present = any(
        value is not None
        for value in (
            args.regression_scope,
            args.regression_command,
            args.regression_path,
            args.regression_criterion,
        )
    )
    required_regression_scope = expected_regression_scope(args.role)
    if required_regression_scope is not None or regression_values_present:
        missing: list[str] = []
        if not args.regression_command:
            missing.append("--regression-command")
        if not args.regression_path:
            missing.append("--regression-path")
        if not args.regression_criterion:
            missing.append("--regression-criterion")
        if missing:
            raise ToolError(
                f"role {args.role!r} requires a complete regression contract; missing {', '.join(missing)}"
            )

    anchor_index: int | None = None
    if args.after or args.before:
        anchor_index = find_node_index(checkpoints_data, args.after or args.before, checkpoints_path)

    spliced_downstream: list[str] = []
    if args.splice and anchor_index is not None:
        anchor = checkpoints_data[anchor_index]
        anchor_id = str(anchor.get("id"))
        anchor_next = anchor.get("next")
        inherited_next = [ref for ref in anchor_next if isinstance(ref, str)] if isinstance(anchor_next, list) else []
        merged_next = list(inherited_next)
        for ref in next_refs:
            if ref not in merged_next:
                merged_next.append(ref)
        next_refs = merged_next
        if anchor_id not in prerequisites:
            prerequisites.insert(0, anchor_id)
        anchor["next"] = [node_id]
        for entry in checkpoints_data:
            if not isinstance(entry, dict) or entry.get("id") not in inherited_next:
                continue
            entry_prerequisites = entry.get("prerequisites")
            if is_string_list(entry_prerequisites) and anchor_id in entry_prerequisites:
                entry["prerequisites"] = [node_id if ref == anchor_id else ref for ref in entry_prerequisites]
                spliced_downstream.append(str(entry.get("id")))

    node: dict[str, Any] = {
        "id": node_id,
        "status": "pending",
        "role": args.role,
        "prerequisites": prerequisites,
        "platform": args.platform,
        "difficulty": args.difficulty,
        "goal": args.goal,
        "description": args.description,
    }
    if requirements is not None:
        node["requirements"] = requirements
    if design is not None:
        node["design"] = design
    node["acceptance_criteria"] = [{"checked": False, "text": text} for text in args.criterion]
    node["commit"] = {
        "repository": args.commit_repository,
        "message": args.commit_message,
        "target": args.commit_target,
    }
    if required_regression_scope is not None or regression_values_present:
        node["regression"] = {
            "scope": args.regression_scope or required_regression_scope or "focused",
            "commands": list(args.regression_command),
            "criteria": list(args.regression_criterion),
            "paths": list(args.regression_path),
        }
    node["next"] = next_refs

    if args.before is not None and anchor_index is not None:
        insert_index = anchor_index
    elif args.after is not None and anchor_index is not None:
        insert_index = anchor_index + 1
    else:
        insert_index = len(checkpoints_data)
    checkpoints_data.insert(insert_index, node)

    location = _NodeLocation(manifest, manifest_data, plan_index, checkpoints_path, checkpoints_data, insert_index)
    messages = [f"OK: node {node_id} added to plan {plan_label(plan, plan_index)!r} at index {insert_index}"]
    if spliced_downstream:
        messages.append(f"OK: spliced into the chain; downstream prerequisites rewired: {', '.join(spliced_downstream)}")
    messages.extend(write_location_and_sync_plan(location))
    for message in messages:
        print(message)
    return 0


def rewire_command(args: argparse.Namespace) -> int:
    manifest = workspace_manifest_path(Path(args.root))
    location = locate_node(manifest, args.node_id)
    node = location.checkpoints_data[location.node_index]

    changed = False
    replacements = {"prerequisites": parse_id_list(args.prerequisites), "next": parse_id_list(args.next)}
    for field, value in replacements.items():
        if value is not None:
            node[field] = value
            changed = True

    additions = {"prerequisites": args.add_prerequisite or [], "next": args.add_next or []}
    removals = {"prerequisites": args.remove_prerequisite or [], "next": args.remove_next or []}
    for field in ("prerequisites", "next"):
        if not additions[field] and not removals[field]:
            continue
        refs = node.get(field)
        if not is_string_list(refs):
            raise ToolError(f"node {args.node_id}: {field} must be an array of node ids before incremental rewiring")
        for ref in additions[field]:
            if ref not in refs:
                refs.append(ref)
                changed = True
        for ref in removals[field]:
            if ref not in refs:
                raise ToolError(f"node {args.node_id}: cannot remove {ref!r} from {field}; it is not present")
            refs.remove(ref)
            changed = True

    if not changed:
        raise ToolError("provide at least one of --prerequisites, --next, --add-prerequisite, --remove-prerequisite, --add-next, --remove-next")

    messages = [
        f"OK: node {args.node_id} rewired; prerequisites={json.dumps(node.get('prerequisites'))} next={json.dumps(node.get('next'))}"
    ]
    messages.extend(write_location_and_sync_plan(location))
    for message in messages:
        print(message)
    return 0


def edit_node_command(args: argparse.Namespace) -> int:
    manifest = workspace_manifest_path(Path(args.root))
    location = locate_node(manifest, args.node_id)
    node = location.checkpoints_data[location.node_index]

    text_updates: dict[str, str | None] = {
        "goal": args.goal,
        "description": args.description,
        "difficulty": args.difficulty,
        "platform": args.platform,
    }
    commit_updates: dict[str, str | None] = {
        "repository": args.commit_repository,
        "message": args.commit_message,
        "target": args.commit_target,
    }
    requirements_replacement = parse_id_list(args.requirements)
    wants_regression_edit = any(
        value is not None
        for value in (
            args.regression_scope,
            args.regression_command,
            args.regression_path,
            args.regression_criterion,
        )
    )
    wants_content_edit = (
        any(value is not None for value in text_updates.values())
        or any(value is not None for value in commit_updates.values())
        or args.criterion is not None
        or wants_regression_edit
    )
    wants_requirements_edit = (
        requirements_replacement is not None or bool(args.add_requirement) or bool(args.remove_requirement)
    )
    if not wants_content_edit and not wants_requirements_edit:
        raise ToolError("provide at least one field to edit")

    status = node.get("status")
    if status in WORKFLOW_STATE_MACHINE.terminal_statuses and wants_content_edit:
        raise ToolError(
            f"node {args.node_id} is {status}; terminal nodes are historical snapshots and only accept requirements-label "
            "corrections. Record current truth in the plan documents or add a new node instead"
        )

    changed: list[str] = []
    for field, value in text_updates.items():
        if value is None:
            continue
        node[field] = value
        changed.append(field)
    if any(value is not None for value in commit_updates.values()):
        commit = node.get("commit")
        if not isinstance(commit, dict):
            raise ToolError(f"node {args.node_id}: commit must be an object before editing commit fields")
        for field, value in commit_updates.items():
            if value is None:
                continue
            commit[field] = value
            changed.append(f"commit.{field}")
    criterion_replacement = (
        [{"checked": False, "text": text} for text in args.criterion]
        if args.criterion is not None
        else None
    )
    if criterion_replacement is not None:
        if not criterion_replacement:
            raise ToolError("criterion replacement requires at least one value")
        node["acceptance_criteria"] = criterion_replacement
        changed.append("acceptance_criteria")

    regression: dict[str, Any] | None = (
        dict(node.get("regression")) if isinstance(node.get("regression"), dict) else None
    )
    if wants_regression_edit:
        if regression is None:
            regression = {}
        replacements: dict[str, Any] = {
            "scope": args.regression_scope,
            "commands": list(args.regression_command) if args.regression_command is not None else None,
            "paths": list(args.regression_path) if args.regression_path is not None else None,
            "criteria": list(args.regression_criterion) if args.regression_criterion is not None else None,
        }
        for field, value in replacements.items():
            if value is not None:
                regression[field] = value
                changed.append(f"regression.{field}")
        node["regression"] = regression

    if requirements_replacement is not None:
        node["requirements"] = requirements_replacement
        changed.append("requirements")
    if args.add_requirement or args.remove_requirement:
        requirements = node.get("requirements")
        if not is_string_list(requirements):
            requirements = []
            node["requirements"] = requirements
        for label in args.add_requirement or []:
            if label not in requirements:
                requirements.append(label)
                changed.append("requirements")
        for label in args.remove_requirement or []:
            if label not in requirements:
                raise ToolError(f"node {args.node_id}: cannot remove requirement {label!r}; it is not present")
            requirements.remove(label)
            changed.append("requirements")

    preparation_semantic_edit = (
        args.criterion is not None
        or any(value is not None for value in text_updates.values())
        or wants_regression_edit
        or wants_requirements_edit
    )
    if preparation_semantic_edit:
        invalidate_preparation_after_plan_edit(node)

    messages = [f"OK: node {args.node_id} updated fields: {', '.join(sorted(set(changed)))}"]
    messages.extend(write_location_and_sync_plan(location))
    for message in messages:
        print(message)
    return 0


def check_labels_command(args: argparse.Namespace) -> int:
    manifest = workspace_manifest_path(Path(args.root))
    manifest_data = load_state_entries(manifest)

    selected_index: int | None = None
    if args.plan is not None:
        selected_index, _ = resolve_plan_entry(manifest, manifest_data, args.plan)

    plan_dirs: dict[int, Path] = {}
    for index, plan in enumerate(manifest_data):
        if isinstance(plan, dict) and is_relative_workspace_path(plan.get("directory")):
            plan_dirs[index] = (manifest.parent / normalize_workspace_path(str(plan.get("directory")))).resolve()

    plans_payload: list[dict[str, Any]] = []
    errors = 0
    warnings = 0
    for index, plan in enumerate(manifest_data):
        if not isinstance(plan, dict):
            continue
        if selected_index is not None and index != selected_index:
            continue
        label = plan_label(plan, index)
        payload: dict[str, Any] = {"plan": label, "directory": plan.get("directory")}

        plan_dir = plan_dirs.get(index)
        if plan_dir is None or not plan_dir.is_dir():
            payload["error"] = "plan directory missing"
            plans_payload.append(payload)
            errors += 1
            continue
        nodes, error = load_plan_checkpoints(manifest, plan)
        if nodes is None:
            payload["error"] = error
            plans_payload.append(payload)
            errors += 1
            continue

        exclude_dirs = {path for other_index, path in plan_dirs.items() if other_index != index}
        doc_labels, invalid_document_labels, scanned = plan_document_labels(plan_dir, exclude_dirs)

        carried: dict[str, list[str]] = {}
        invalid_node_labels: dict[str, list[str]] = {}
        carried_non_skipped: set[str] = set()
        for node in nodes:
            if not isinstance(node, dict):
                continue
            requirements = node.get("requirements")
            if not is_string_list(requirements):
                continue
            for value in requirements:
                if not is_requirement_label(value):
                    invalid_node_labels.setdefault(value, []).append(str(node.get("id")))
                    continue
                carried.setdefault(value, []).append(str(node.get("id")))
                if node.get("status") != "skipped":
                    carried_non_skipped.add(value)

        payload["documents_scanned"] = scanned
        payload["doc_labels"] = len(doc_labels)
        payload["node_labels"] = len(carried)
        if invalid_document_labels:
            payload["invalid_document_labels"] = sorted(invalid_document_labels)
            errors += len(invalid_document_labels)
        if invalid_node_labels:
            payload["invalid_node_labels"] = {
                value: invalid_node_labels[value] for value in sorted(invalid_node_labels)
            }
            errors += len(invalid_node_labels)
        if not doc_labels:
            payload["warning"] = "no requirement labels found in plan documents; document labels before relying on traceability"
            warnings += 1
            plans_payload.append(payload)
            continue

        undefined = {value: carried[value] for value in sorted(set(carried) - doc_labels)}
        # A doc label that prefixes other doc labels (REQ-X next to REQ-X-001) is a family
        # reference in prose, not a requirement definition; keep it out of coverage warnings.
        family_prefixes = {
            value
            for value in doc_labels
            if any(other != value and other.startswith(f"{value}-") for other in doc_labels)
        }
        uncovered = sorted(doc_labels - family_prefixes - carried_non_skipped)
        payload["undefined"] = undefined
        payload["uncovered"] = uncovered
        errors += len(undefined)
        warnings += len(uncovered)
        plans_payload.append(payload)

    if args.json:
        workspace = relative_path_label(manifest.parent, project_root_for(manifest.parent))
        print(json.dumps({"workspace": workspace, "errors": errors, "warnings": warnings, "plans": plans_payload}, indent=2, ensure_ascii=False))
        return 1 if errors else 0

    for payload in plans_payload:
        print(f"Plan: {payload['plan']} ({payload.get('directory')})")
        if "error" in payload:
            print(f"  error: {payload['error']}", file=sys.stderr)
            continue
        print(f"  documents scanned: {payload['documents_scanned']}, doc labels: {payload['doc_labels']}, node labels: {payload['node_labels']}")
        for value in payload.get("invalid_document_labels", []):
            print(
                f"  error: noncanonical document label {value}; use REQ first, for example REQ-001",
                file=sys.stderr,
            )
        for value, node_ids in payload.get("invalid_node_labels", {}).items():
            print(
                f"  error: noncanonical node label {value} is carried by node(s) {', '.join(node_ids)}; "
                "use REQ first, for example REQ-001",
                file=sys.stderr,
            )
        if "warning" in payload:
            print(f"  warning: {payload['warning']}")
            continue
        for value, node_ids in payload.get("undefined", {}).items():
            print(f"  error: label {value} is carried by node(s) {', '.join(node_ids)} but defined in no plan document", file=sys.stderr)
        for value in payload.get("uncovered", []):
            print(f"  warning: label {value} appears in plan documents but no non-skipped node carries it")
        if not payload.get("undefined") and not payload.get("uncovered"):
            print("  OK: document labels and node labels are consistent")
    if errors:
        print(f"{errors} label error(s), {warnings} warning(s).", file=sys.stderr)
        return 1
    print(f"OK: label cross-check passed with {warnings} warning(s).")
    return 0


def sync_plan_command(args: argparse.Namespace) -> int:
    manifest = workspace_manifest_path(Path(args.root))
    manifest_data = load_state_entries(manifest)

    messages: list[str] = []
    errors: list[str] = []
    changed = False

    for index, plan in enumerate(manifest_data):
        if not isinstance(plan, dict):
            continue
        status = plan.get("status")
        label = plan_label(plan, index)
        if not WORKFLOW_STATE_MACHINE.is_status(status):
            errors.append(f"plan {label!r}: invalid status {status!r}; fix {MANIFEST_NAME} manually")
            continue
        nodes, error = load_plan_checkpoints(manifest, plan)
        if nodes is None:
            errors.append(f"plan {label!r}: {error}")
            continue
        derived = derive_plan_status(str(status), nodes)
        if derived == status:
            continue
        if not WORKFLOW_STATE_MACHINE.can_reach(str(status), derived):
            errors.append(f"plan {label!r}: cannot move from {status!r} to derived status {derived!r}; fix state files manually")
            continue
        plan["status"] = derived
        changed = True
        messages.append(f"OK: plan {label!r} {status} -> {derived}")

    if changed:
        write_state_entries(manifest, manifest_data)
    for message in messages:
        print(message)
    if not messages and not errors:
        print("OK: plan statuses already in sync")
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


def status_command(args: argparse.Namespace) -> int:
    manifest = workspace_manifest_path(Path(args.root))
    manifest_data = load_state_entries(manifest)
    workspace = relative_path_label(manifest.parent, project_root_for(manifest.parent))

    plans_payload: list[dict[str, Any]] = []
    for index, plan in enumerate(manifest_data):
        if not isinstance(plan, dict):
            continue
        payload: dict[str, Any] = {
            "id": plan.get("id"),
            "title": public_summary(plan.get("title"), f"plan[{index}]"),
            "status": plan.get("status"),
            "directory": plan.get("directory"),
        }
        nodes, error = load_plan_checkpoints(manifest, plan)
        if nodes is None:
            payload["error"] = error
            plans_payload.append(payload)
            continue

        counts = {status: 0 for status in STATUS_ORDER}
        in_progress: list[dict[str, Any]] = []
        blocked: list[dict[str, Any]] = []
        total = 0
        for node in nodes:
            if not isinstance(node, dict):
                continue
            total += 1
            status = node.get("status")
            if WORKFLOW_STATE_MACHINE.is_status(status):
                counts[str(status)] += 1
            entry = {"id": node.get("id"), "goal": public_summary(node.get("goal"), "[redacted]")}
            if status == "in_progress":
                in_progress.append(entry)
            elif status == "blocked":
                blocked.append(
                    {**entry, "status_reason": public_summary(node.get("status_reason"), "[redacted]")}
                )

        payload.update({"nodes": total, "counts": counts, "in_progress": in_progress, "blocked": blocked})
        plans_payload.append(payload)

    if args.json:
        print(json.dumps({"workspace": workspace, "plans": plans_payload}, indent=2, ensure_ascii=False))
        return 0

    print(f"Workspace: {workspace}")
    for payload in plans_payload:
        print(f"Plan: {payload.get('title')} [{payload.get('status')}] {payload.get('directory')}")
        if "error" in payload:
            print(f"  checkpoints: {payload['error']}")
            continue
        counts = payload["counts"]
        summary = ", ".join(f"{status} {counts[status]}" for status in STATUS_ORDER)
        print(f"  nodes: {payload['nodes']} total | {summary}")
        for entry in payload["in_progress"]:
            print(f"  in_progress: {entry['id']} {entry['goal']}")
        for entry in payload["blocked"]:
            reason = entry.get("status_reason") or "no status_reason recorded"
            print(f"  blocked: {entry['id']} {entry['goal']} (reason: {reason})")
    return 0


def next_command(args: argparse.Namespace) -> int:
    manifest = workspace_manifest_path(Path(args.root))
    manifest_data = load_state_entries(manifest)
    platform = current_platform()
    workspace = relative_path_label(manifest.parent, project_root_for(manifest.parent))

    plans_payload: list[dict[str, Any]] = []
    for index, plan in enumerate(manifest_data):
        if not isinstance(plan, dict):
            continue
        status = plan.get("status")
        if status in WORKFLOW_STATE_MACHINE.terminal_statuses:
            continue
        nodes, _ = load_plan_checkpoints(manifest, plan)
        if nodes is None:
            continue

        node_statuses: dict[str, Any] = {}
        for node in nodes:
            if isinstance(node, dict) and isinstance(node.get("id"), str):
                node_statuses[node["id"]] = node.get("status")

        def node_entry(node: dict[str, Any]) -> dict[str, Any]:
            return {
                "id": node.get("id"),
                "goal": public_summary(node.get("goal"), "[redacted]"),
                "difficulty": node.get("difficulty"),
                "platform": node.get("platform"),
            }

        resume = None
        for node in nodes:
            if isinstance(node, dict) and node.get("status") == "in_progress":
                resume = node_entry(node)
                break

        eligible: list[dict[str, Any]] = []
        if resume is None:
            for node in nodes:
                if not isinstance(node, dict) or node.get("status") != "pending":
                    continue
                prerequisites = node.get("prerequisites")
                if not is_string_list(prerequisites):
                    continue
                if any(node_statuses.get(ref) != "completed" for ref in prerequisites):
                    continue
                if not platform_matches(node.get("platform"), platform):
                    continue
                eligible.append(node_entry(node))

        plans_payload.append(
            {
                "id": plan.get("id"),
                "title": public_summary(plan.get("title"), f"plan[{index}]"),
                "status": status,
                "resume": resume,
                "eligible": eligible,
            }
        )

    if args.json:
        print(json.dumps({"workspace": workspace, "platform": platform, "plans": plans_payload}, indent=2, ensure_ascii=False))
        return 0

    printed = False
    for payload in plans_payload:
        resume = payload["resume"]
        eligible = payload["eligible"]
        if resume is None and not eligible:
            continue
        printed = True
        print(f"Plan: {payload.get('title')} [{payload.get('status')}]")
        if resume is not None:
            print(f"  resume: {resume['id']} {resume['goal']}")
            continue
        for entry in eligible:
            print(f"  next: {entry['id']} {entry['goal']} (difficulty {entry['difficulty']}, platform {entry['platform']})")
    if not printed:
        print(f"No executable nodes found for platform {platform}.")
    return 0


def schema_command(args: argparse.Namespace) -> int:
    if args.kind == "plan":
        payload: dict[str, Any] = {
            "kind": "plan",
            "file": MANIFEST_NAME,
            "required_fields": sorted(PLAN_REQUIRED_FIELDS),
            "optional_fields": sorted(PLAN_OPTIONAL_FIELDS),
            "statuses": list(STATUS_ORDER),
            "template": PLAN_TEMPLATE,
        }
    else:
        payload = {
            "kind": "node",
            "file": CHECKPOINTS_NAME,
            "required_fields": sorted(TASK_REQUIRED_FIELDS),
            "optional_fields": sorted(TASK_OPTIONAL_FIELDS),
            "commit_required_fields": sorted(COMMIT_REQUIRED_FIELDS),
            "commit_optional_fields": sorted(COMMIT_OPTIONAL_FIELDS),
            "acceptance_criterion_required_fields": sorted(CRITERION_REQUIRED_FIELDS),
            "acceptance_criterion_optional_fields": sorted(CRITERION_OPTIONAL_FIELDS),
            "regression_required_fields": sorted(REGRESSION_REQUIRED_FIELDS),
            "regression_optional_fields": sorted(REGRESSION_OPTIONAL_FIELDS),
            "regression_receipt_fields": sorted(REGRESSION_RECEIPT_FIELDS),
            "regression_scopes": sorted(VALID_REGRESSION_SCOPES),
            "acceptance_required_fields": sorted(ACCEPTANCE_REQUIRED_FIELDS),
            "acceptance_optional_fields": sorted(ACCEPTANCE_OPTIONAL_FIELDS),
            "acceptance_phases": sorted(ACCEPTANCE_PHASES),
            "acceptance_outcomes": sorted(ACCEPTANCE_OUTCOMES),
            "design_required_fields": sorted(DESIGN_REQUIRED_FIELDS),
            "design_symbol_kinds": sorted(SYMBOL_KINDS),
            "design_symbol_operations": sorted(SYMBOL_OPERATIONS),
            "design_decision_fields": sorted(DECISION_FIELDS),
            "statuses": list(STATUS_ORDER),
            "roles": sorted(VALID_NODE_ROLES),
            "difficulties": sorted(VALID_DIFFICULTIES),
            "platforms": sorted(VALID_PLATFORMS),
            "requirement_label_pattern": REQUIREMENT_LABEL_PATTERN.pattern,
            "template": NODE_TEMPLATE,
        }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Better Plan manifest utility")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help=f"validate a workspace {MANIFEST_NAME} and its referenced {CHECKPOINTS_NAME} files")
    validate.add_argument("root", nargs="?", default=".", help="Better Plan workspace root, manifest file, or checkpoints file")
    validate.add_argument("--plan", help="scope validation to one plan by id, directory, or title (plus the shared manifest index)")
    validate.add_argument("--check-sources", action="store_true", help="verify that plan source_files entries resolve to existing files or directories")
    validate.add_argument("--quiet", action="store_true", help="only print validation errors")
    validate.add_argument("--json", action="store_true", help="print machine-readable validation results")
    validate.add_argument("--no-git", action="store_true", help="skip comparing state files against their git HEAD versions")
    validate.set_defaults(func=validate_command)

    discover = subparsers.add_parser("discover", help=f"discover existing Better Plan workspaces by {MANIFEST_NAME}/{CHECKPOINTS_NAME} structure")
    discover.add_argument("root", nargs="?", default=".", help="project root or manifest file to search")
    discover.set_defaults(func=discover_command)

    uuid_parser = subparsers.add_parser("uuid", help="generate task IDs")
    uuid_parser.add_argument("--count", type=int, default=1, help="number of IDs to print")
    uuid_parser.set_defaults(func=uuid_command)

    platform_parser = subparsers.add_parser("platform", help="print the normalized current runtime platform")
    platform_parser.add_argument("--json", action="store_true", help="print a machine-readable platform object")
    platform_parser.set_defaults(func=platform_command)

    transition = subparsers.add_parser("transition", help="check whether one workflow status can transition to another")
    transition.add_argument("current", help="current status")
    transition.add_argument("target", help="target status")
    transition.add_argument("--quiet", action="store_true", help="only print transition errors")
    transition.set_defaults(func=transition_command)

    next_action_parser = subparsers.add_parser(
        "next-action",
        help="derive the deterministic next action for an automated delivery node without mutating state",
    )
    next_action_parser.add_argument("node_id", help="node UUID")
    next_action_parser.add_argument("root", nargs="?", default=".", help="Better Plan workspace root")
    next_action_parser.set_defaults(func=next_action_command)

    dispatch = subparsers.add_parser(
        "dispatch",
        help="record one idempotent preparation, executor, or auditor dispatch for a delivery node",
    )
    dispatch.add_argument("node_id", help="node UUID")
    dispatch.add_argument("root", nargs="?", default=".", help="Better Plan workspace root")
    dispatch.add_argument(
        "--role",
        required=True,
        choices=("acceptance_designer", "executor", "auditor"),
        help="fresh leaf-agent role",
    )
    dispatch.set_defaults(func=dispatch_command)

    advance = subparsers.add_parser(
        "advance",
        help="submit one correlated preparation, executor, regression, or auditor event",
    )
    advance.add_argument("node_id", help="node UUID")
    advance.add_argument("root", nargs="?", default=".", help="Better Plan workspace root")
    advance.add_argument(
        "--event",
        required=True,
        choices=(
            "acceptance-designer-exited",
            "executor-exited",
            "regression-requested",
            "audit-failed",
            "audit-passed",
            "repair-registered",
            "repair-completed",
        ),
        help="correlated acceptance event",
    )
    advance.add_argument("--dispatch-id", help="bounded opaque correlation id for preparation, executor, regression, and audit events")
    advance.add_argument("--repair-node", help="UUID4 repair Node id for repair handoff events")
    advance.set_defaults(func=_advance_command)

    start = subparsers.add_parser("start", help="mark a node in_progress after enforcing transitions and snapshot rules")
    start.add_argument("node_id", help="node UUID")
    start.add_argument("root", nargs="?", default=".", help="Better Plan workspace root")
    start.set_defaults(func=start_command)

    regress = subparsers.add_parser("regress", help="run an in-progress node's declared regression contract and record a passing receipt")
    regress.add_argument("node_id", help="node UUID")
    regress.add_argument("root", nargs="?", default=".", help="Better Plan workspace root")
    regress.set_defaults(func=regress_command)

    complete = subparsers.add_parser("complete", help="mark a node completed after enforcing transitions and snapshot rules")
    complete.add_argument("node_id", help="node UUID")
    complete.add_argument("root", nargs="?", default=".", help="Better Plan workspace root")
    complete.add_argument("--delivered", help="record the delivering commit sha in commit.delivered")
    complete.set_defaults(func=complete_command)

    block = subparsers.add_parser("block", help="mark a node blocked and record the reason in status_reason")
    block.add_argument("node_id", help="node UUID")
    block.add_argument("root", nargs="?", default=".", help="Better Plan workspace root")
    block.add_argument("--reason", required=True, help="why the node is blocked and what would unblock it")
    block.set_defaults(func=block_command)

    skip = subparsers.add_parser("skip", help="mark a node skipped and record the reason in status_reason")
    skip.add_argument("node_id", help="node UUID")
    skip.add_argument("root", nargs="?", default=".", help="Better Plan workspace root")
    skip.add_argument("--reason", required=True, help="why the node is intentionally deferred")
    skip.set_defaults(func=skip_command)

    pause = subparsers.add_parser("pause", help="return an in_progress node to pending so another node can start; progress notes stay in status_reason")
    pause.add_argument("node_id", help="node UUID")
    pause.add_argument("root", nargs="?", default=".", help="Better Plan workspace root")
    pause.add_argument("--reason", help="why the node yields and what remains when it resumes")
    pause.set_defaults(func=pause_command)

    check = subparsers.add_parser("check", help="mark one acceptance criterion checked, optionally recording evidence")
    check.add_argument("node_id", help="node UUID")
    check.add_argument("root", nargs="?", default=".", help="Better Plan workspace root")
    check.add_argument("--criterion", type=int, required=True, help="zero-based acceptance criterion index")
    check.add_argument("--evidence", help="what verification proved this criterion")
    check.add_argument("--evidence-file", action="append", help="record a file evidence reference (path plus sha256); repeatable")
    check.add_argument("--evidence-cmd", action="append", help="run a verification command and record it as evidence; the command must exit 0; repeatable")
    check.set_defaults(func=check_command)

    add_node = subparsers.add_parser("add-node", help="insert a new pending node into a plan's checkpoints with validated wiring")
    add_node.add_argument("root", nargs="?", default=".", help="Better Plan workspace root")
    add_node.add_argument("--plan", required=True, help="target plan id, directory, or title")
    add_node.add_argument("--goal", required=True, help="one-sentence node goal")
    add_node.add_argument(
        "--description",
        required=True,
        help=(
            "structured task design brief (implementation Scope begins with exactly one Closure: "
            "capability|module|scenario - target; then Context/Target/Design Considerations/Design Value/Constraints & Risks)"
        ),
    )
    add_node.add_argument("--role", default="implementation", choices=sorted(VALID_NODE_ROLES), help="delivery role; defaults to implementation")
    add_node.add_argument("--difficulty", default="medium", choices=sorted(VALID_DIFFICULTIES), help="difficulty; defaults to medium")
    add_node.add_argument("--platform", default="any", choices=sorted(VALID_PLATFORMS), help="platform; defaults to any")
    add_node.add_argument(
        "--requirements",
        help="comma-separated canonical labels that begin with REQ, such as REQ-001,REQ-002",
    )
    add_node.add_argument(
        "--design-json",
        help="complete machine-readable design object as JSON; required for delivery roles",
    )
    add_node.add_argument("--criterion", action="append", required=True, help="acceptance criterion text; repeatable, at least one")
    add_node.add_argument("--commit-message", required=True, help="suggested commit message")
    add_node.add_argument("--commit-target", required=True, help="where the work should be committed or delivered")
    add_node.add_argument("--commit-repository", default=".git", help="target repository .git entry; defaults to .git")
    add_node.add_argument("--regression-scope", choices=sorted(VALID_REGRESSION_SCOPES), help="regression scope; implementation defaults to focused and final_validation to full")
    add_node.add_argument("--regression-command", action="append", help="regression command run from the project root; repeatable")
    add_node.add_argument("--regression-path", action="append", help="repository-relative file or directory fingerprinted before and after regression; repeatable")
    add_node.add_argument("--regression-criterion", action="append", type=int, help="zero-based acceptance criterion checked by the complete command set; repeatable")
    add_node.add_argument("--after", help="insert the new node directly after this node id")
    add_node.add_argument("--before", help="insert the new node directly before this node id")
    add_node.add_argument("--prerequisites", help="comma-separated prerequisite node ids")
    add_node.add_argument("--next", help="comma-separated follow-up node ids")
    add_node.add_argument("--splice", action="store_true", help="with --after: inherit the anchor's next edges, make the anchor point to the new node, and rewire those downstream prerequisites")
    add_node.add_argument("--id", help="explicit UUID4 node id; generated when omitted")
    add_node.set_defaults(func=add_node_command)

    rewire = subparsers.add_parser("rewire", help="replace or incrementally edit a node's prerequisites and next edges with validation")
    rewire.add_argument("node_id", help="node UUID")
    rewire.add_argument("root", nargs="?", default=".", help="Better Plan workspace root")
    rewire.add_argument("--prerequisites", help="replace prerequisites with this comma-separated id list; pass '' to clear")
    rewire.add_argument("--next", help="replace next with this comma-separated id list; pass '' to clear")
    rewire.add_argument("--add-prerequisite", action="append", help="append one prerequisite id; repeatable")
    rewire.add_argument("--remove-prerequisite", action="append", help="remove one prerequisite id; repeatable")
    rewire.add_argument("--add-next", action="append", help="append one next id; repeatable")
    rewire.add_argument("--remove-next", action="append", help="remove one next id; repeatable")
    rewire.set_defaults(func=rewire_command)

    edit_node = subparsers.add_parser("edit-node", help="edit node fields through validation; terminal nodes only accept requirements-label corrections")
    edit_node.add_argument("node_id", help="node UUID")
    edit_node.add_argument("root", nargs="?", default=".", help="Better Plan workspace root")
    edit_node.add_argument("--goal", help="replace the node goal")
    edit_node.add_argument("--description", help="replace the node description")
    edit_node.add_argument("--difficulty", choices=sorted(VALID_DIFFICULTIES), help="replace the node difficulty")
    edit_node.add_argument("--platform", choices=sorted(VALID_PLATFORMS), help="replace the node platform")
    edit_node.add_argument(
        "--requirements",
        help="replace requirement labels with a comma-separated canonical REQ-... list; pass '' to clear",
    )
    edit_node.add_argument(
        "--add-requirement",
        action="append",
        help="append one canonical REQ-... requirement label; repeatable",
    )
    edit_node.add_argument("--remove-requirement", action="append", help="remove one requirement label; repeatable")
    edit_node.add_argument(
        "--criterion",
        action="append",
        help="replace the complete acceptance-criterion set with the repeated values",
    )
    edit_node.add_argument("--commit-message", help="replace commit.message")
    edit_node.add_argument("--commit-target", help="replace commit.target")
    edit_node.add_argument("--commit-repository", help="replace commit.repository")
    edit_node.add_argument("--regression-scope", choices=sorted(VALID_REGRESSION_SCOPES), help="replace regression.scope")
    edit_node.add_argument("--regression-command", action="append", help="replace regression.commands with the repeated values")
    edit_node.add_argument("--regression-path", action="append", help="replace regression.paths with the repeated values")
    edit_node.add_argument("--regression-criterion", action="append", type=int, help="replace regression.criteria with the repeated indexes")
    edit_node.set_defaults(func=edit_node_command)

    check_labels = subparsers.add_parser("check-labels", help="cross-check requirement labels between plan documents and checkpoint nodes")
    check_labels.add_argument("root", nargs="?", default=".", help="Better Plan workspace root")
    check_labels.add_argument("--plan", help="scope the cross-check to one plan by id, directory, or title")
    check_labels.add_argument("--json", action="store_true", help="print machine-readable results")
    check_labels.set_defaults(func=check_labels_command)

    sync_plan = subparsers.add_parser("sync-plan", help="re-derive every plan status from its checkpoint nodes")
    sync_plan.add_argument("root", nargs="?", default=".", help="Better Plan workspace root")
    sync_plan.set_defaults(func=sync_plan_command)

    status = subparsers.add_parser("status", help="report per-plan progress, the in_progress node, and blocked nodes")
    status.add_argument("root", nargs="?", default=".", help="Better Plan workspace root")
    status.add_argument("--json", action="store_true", help="print machine-readable status")
    status.set_defaults(func=status_command)

    next_parser = subparsers.add_parser("next", help="list the in_progress node or the eligible pending nodes per plan")
    next_parser.add_argument("root", nargs="?", default=".", help="Better Plan workspace root")
    next_parser.add_argument("--json", action="store_true", help="print machine-readable candidates")
    next_parser.set_defaults(func=next_command)

    schema = subparsers.add_parser("schema", help="print the canonical Plan or Node schema and template")
    schema.add_argument("kind", choices=("plan", "node"), help="which schema to print")
    schema.set_defaults(func=schema_command)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if getattr(args, "count", 1) < 1:
        parser.error("--count must be at least 1")
    try:
        return args.func(args)
    except ToolError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except Exception:
        print("error: operation could not be completed safely", file=sys.stderr)
        return 1
