"""Workspace layer for Better Plan workflow state."""

from __future__ import annotations

from typing import Any
from pathlib import Path
from dataclasses import dataclass
import json
import os
import subprocess
from ..domain.models import CHECKPOINTS_NAME, DISCOVERY_SKIP_DIRS, EXTERNAL_SOURCE_PATTERN, Issue, MANIFEST_NAME, PLAN_OPTIONAL_FIELDS, PLAN_REQUIRED_FIELDS, REQUIREMENT_LABEL_CANDIDATE_PATTERN, STATE_FILE_NAMES, ToolError, UUID4_PATTERN, WORKFLOW_STATE_MACHINE, derive_plan_status, expected_checkpoints_path, is_manifest_id, is_relative_workspace_path, is_requirement_label, is_string_list, normalize_workspace_path, public_summary
from ..domain.validation import validate_checkpoints_data as _validate_checkpoints_data


def find_manifests(root: Path) -> list[Path]:
    if root.is_file():
        return [root] if root.name in STATE_FILE_NAMES else []

    manifest = root / MANIFEST_NAME
    return [manifest] if manifest.is_file() else []


def referenced_checkpoints_files(manifest: Path) -> list[Path]:
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    if not isinstance(data, list):
        return []

    checkpoints: list[Path] = []
    seen: set[Path] = set()
    for plan in data:
        if not isinstance(plan, dict):
            continue
        value = plan.get("checkpoints")
        if not is_relative_workspace_path(value):
            continue
        path = manifest.parent / normalize_workspace_path(value)
        if path.name != CHECKPOINTS_NAME or not path.is_file() or path in seen:
            continue
        seen.add(path)
        checkpoints.append(path)
    return checkpoints


def discover_workspace_manifests(root: Path) -> list[Path]:
    if root.is_file():
        if root.name == MANIFEST_NAME and is_structural_workspace_manifest(root):
            return [root]
        return []

    candidates: list[Path] = []
    for current_root, dirs, files in os.walk(root):
        dirs[:] = [dirname for dirname in dirs if dirname not in DISCOVERY_SKIP_DIRS]
        if MANIFEST_NAME not in files:
            continue
        manifest = Path(current_root) / MANIFEST_NAME
        if is_structural_workspace_manifest(manifest):
            candidates.append(manifest)

    return sorted(candidates)


def is_structural_workspace_manifest(manifest: Path) -> bool:
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False

    if not isinstance(data, list) or not data:
        return False

    for plan in data:
        if not isinstance(plan, dict):
            return False
        if not PLAN_REQUIRED_FIELDS.issubset(plan):
            return False

        directory = plan.get("directory")
        checkpoints = plan.get("checkpoints")
        if not is_relative_workspace_path(directory) or not is_relative_workspace_path(checkpoints):
            return False

        normalized_directory = normalize_workspace_path(str(directory))
        normalized_checkpoints = normalize_workspace_path(str(checkpoints))
        if normalized_checkpoints != expected_checkpoints_path(normalized_directory):
            return False

        plan_dir = manifest.parent / normalized_directory
        checkpoint_path = manifest.parent / normalized_checkpoints
        if not plan_dir.is_dir() or checkpoint_path.name != CHECKPOINTS_NAME or not checkpoint_path.is_file():
            return False

        try:
            checkpoint_data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return False
        if not isinstance(checkpoint_data, list):
            return False

    return True


def relative_path_label(path: Path, anchor: Path) -> str:
    raw = str(path)
    if raw.startswith("<") and raw.endswith(">"):
        return raw
    try:
        resolved = path.expanduser().resolve()
        base = anchor.expanduser().resolve()
        if base.is_file():
            base = base.parent
        relative = resolved.relative_to(base)
    except (OSError, ValueError):
        return path.name or "."
    return relative.as_posix() or "."


def is_workspace_root_manifest(path: Path) -> bool:
    return path.name == MANIFEST_NAME


def validate_manifest(path: Path, snapshot_indexes: set[int] | None = None) -> tuple[int, list[Issue]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return 0, [Issue(path, f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}")]
    except OSError:
        return 0, [Issue(path, "cannot read file")]

    if not isinstance(data, list):
        return 0, [Issue(path, "top-level value must be an array")]

    if path.name == MANIFEST_NAME:
        return validate_plan_manifest_data(path, data, snapshot_indexes=snapshot_indexes)
    if path.name == CHECKPOINTS_NAME:
        return _validate_checkpoints_data(path, data)
    return len(data), [Issue(path, f"state file must be named {MANIFEST_NAME} or {CHECKPOINTS_NAME}")]


def validate_plan_manifest_data(path: Path, data: list[Any], snapshot_indexes: set[int] | None = None) -> tuple[int, list[Issue]]:
    issues: list[Issue] = []
    seen: set[str] = set()
    directories: set[str] = set()

    if not is_workspace_root_manifest(path):
        issues.append(Issue(path, f"Plan manifest must be named {MANIFEST_NAME}"))

    for index, plan in enumerate(data):
        prefix = f"plan[{index}]"
        if not isinstance(plan, dict):
            issues.append(Issue(path, f"{prefix}: must be an object"))
            continue

        missing = sorted(PLAN_REQUIRED_FIELDS - set(plan))
        for field in missing:
            issues.append(Issue(path, f"{prefix}.{field}: missing required field"))

        extra = sorted(set(plan) - PLAN_REQUIRED_FIELDS - PLAN_OPTIONAL_FIELDS)
        for field in extra:
            issues.append(Issue(path, f"{prefix}.{field}: unknown field"))

        plan_id = plan.get("id")
        if not isinstance(plan_id, str) or not plan_id.strip():
            issues.append(Issue(path, f"{prefix}.id: must be a non-empty string"))
        else:
            if not is_manifest_id(plan_id):
                issues.append(Issue(path, f"{prefix}.id: must be a UUID4 value; generate ids with the manifest tool's uuid command"))
            if plan_id in seen:
                issues.append(Issue(path, f"{prefix}.id: duplicate id {plan_id!r}"))
            else:
                seen.add(plan_id)

        status_issue = WORKFLOW_STATE_MACHINE.status_issue(path, prefix, plan.get("status"))
        if status_issue is not None:
            issues.append(status_issue)

        for field in ("title", "goal", "description"):
            if not isinstance(plan.get(field), str) or not plan.get(field, "").strip():
                issues.append(Issue(path, f"{prefix}.{field}: must be a non-empty string"))

        directory = plan.get("directory")
        normalized_directory = ""
        if not is_relative_workspace_path(directory):
            issues.append(Issue(path, f"{prefix}.directory: must be a relative workspace path"))
        else:
            normalized_directory = str(directory).strip().replace("\\", "/").strip("/")
            if normalized_directory in directories:
                issues.append(Issue(path, f"{prefix}.directory: duplicate directory {normalized_directory!r}"))
            else:
                directories.add(normalized_directory)
            plan_dir = path.parent / normalized_directory
            if not plan_dir.is_dir():
                issues.append(Issue(path, f"{prefix}.directory: directory does not exist: {normalized_directory}"))

        source_files = plan.get("source_files")
        if not is_string_list(source_files):
            issues.append(Issue(path, f"{prefix}.source_files: must be an array of strings"))
        elif any(not item.strip() for item in source_files):
            issues.append(Issue(path, f"{prefix}.source_files: must not contain empty strings"))
        else:
            for source_index, source in enumerate(source_files):
                value = source.strip()
                if "://" in value or EXTERNAL_SOURCE_PATTERN.match(value):
                    continue
                if not is_relative_workspace_path(value):
                    issues.append(
                        Issue(path, f"{prefix}.source_files[{source_index}]: local source paths must be repository-relative")
                    )

        checkpoints = plan.get("checkpoints")
        if not is_relative_workspace_path(checkpoints):
            issues.append(Issue(path, f"{prefix}.checkpoints: must be a relative path to {CHECKPOINTS_NAME}"))
        elif normalized_directory:
            normalized_checkpoints = str(checkpoints).strip().replace("\\", "/").strip("/")
            expected = expected_checkpoints_path(normalized_directory)
            if normalized_checkpoints != expected:
                issues.append(Issue(path, f"{prefix}.checkpoints: must be {expected!r}"))
            if not (path.parent / normalized_checkpoints).is_file():
                issues.append(Issue(path, f"{prefix}.checkpoints: file does not exist: {normalized_checkpoints}"))

    issues.extend(plan_snapshot_issues(path, data, include_indexes=snapshot_indexes))
    return len(data), issues


def plan_snapshot_issues(
    path: Path,
    data: list[Any],
    include_indexes: set[int] | None = None,
) -> list[Issue]:
    """Compare Plan statuses with their persisted checkpoint snapshots."""
    issues: list[Issue] = []
    for index, plan in enumerate(data):
        if not isinstance(plan, dict):
            continue
        if include_indexes is not None and index not in include_indexes:
            continue
        status = plan.get("status")
        checkpoints = plan.get("checkpoints")
        if not WORKFLOW_STATE_MACHINE.is_status(status) or not is_relative_workspace_path(checkpoints):
            continue

        checkpoint_path = path.parent / normalize_workspace_path(str(checkpoints))
        try:
            checkpoint_data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(checkpoint_data, list):
            continue

        node_statuses = [
            node.get("status")
            for node in checkpoint_data
            if isinstance(node, dict) and WORKFLOW_STATE_MACHINE.is_status(node.get("status"))
        ]
        if not node_statuses:
            continue

        all_terminal = all(
            value in WORKFLOW_STATE_MACHINE.terminal_statuses for value in node_statuses
        )
        if status == "completed":
            unfinished = sorted(
                set(node_statuses) - WORKFLOW_STATE_MACHINE.terminal_statuses
            )
            if unfinished:
                issues.append(
                    Issue(
                        path,
                        f"plan[{index}].status: cannot be 'completed' while checkpoints contain non-terminal nodes: {', '.join(unfinished)}",
                    )
                )
        elif status == "blocked" and "blocked" not in node_statuses:
            issues.append(
                Issue(path, f"plan[{index}].status: cannot be 'blocked' without a blocked checkpoint node")
            )
        elif status == "skipped" and "in_progress" in node_statuses:
            issues.append(
                Issue(path, f"plan[{index}].status: cannot be 'skipped' while a checkpoint node is in_progress")
            )
        elif status == "pending":
            if all_terminal:
                issues.append(
                    Issue(path, f"plan[{index}].status: cannot stay 'pending' when every checkpoint node is terminal; run sync-plan")
                )
            elif any(value in {"in_progress", "completed"} for value in node_statuses):
                issues.append(
                    Issue(path, f"plan[{index}].status: cannot stay 'pending' after checkpoint work has started; run sync-plan")
                )
        elif status == "in_progress" and all_terminal:
            issues.append(
                Issue(path, f"plan[{index}].status: cannot stay 'in_progress' when every checkpoint node is terminal; run sync-plan")
            )
    return issues


def git_head_entries(path: Path) -> list[Any] | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(path.parent), "show", f"HEAD:./{path.name}"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, list) else None


def git_transition_issues(path: Path, data: list[Any]) -> list[Issue]:
    head_entries = git_head_entries(path)
    if head_entries is None:
        return []

    head_statuses: dict[str, str] = {}
    for entry in head_entries:
        if isinstance(entry, dict) and isinstance(entry.get("id"), str) and WORKFLOW_STATE_MACHINE.is_status(entry.get("status")):
            head_statuses[entry["id"]] = str(entry["status"])

    label = "plan" if path.name == MANIFEST_NAME else "node"
    issues: list[Issue] = []
    for index, entry in enumerate(data):
        if not isinstance(entry, dict):
            continue
        entry_id = entry.get("id")
        status = entry.get("status")
        if not isinstance(entry_id, str) or not WORKFLOW_STATE_MACHINE.is_status(status):
            continue
        previous = head_statuses.get(entry_id)
        if previous is None:
            continue
        if not WORKFLOW_STATE_MACHINE.can_reach(previous, str(status)):
            issues.append(Issue(path, f"{label}[{index}].status: cannot change from {previous!r} (git HEAD) to {status!r}; no transition path allows it"))
    return issues


def load_state_entries(path: Path) -> list[Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ToolError(f"{path.name}: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc
    except OSError as exc:
        raise ToolError(f"{path.name}: cannot read file") from exc
    if not isinstance(data, list):
        raise ToolError(f"{path.name}: top-level value must be an array")
    return data


def write_state_entries(path: Path, data: list[Any]) -> None:
    temp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        temp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(temp, path)
    except OSError as exc:
        raise ToolError(f"{path.name}: could not write state safely") from exc


def workspace_manifest_path(root: Path) -> Path:
    if UUID4_PATTERN.fullmatch(str(root).strip().lower()):
        raise ToolError(
            f"{root} looks like a node UUID, not a workspace root; "
            "the argument order is `<command> <node-id> [root]`, where [root] is the Better Plan workspace directory"
        )
    root = root.expanduser().resolve()
    if root.is_file():
        if root.name == MANIFEST_NAME:
            return root
        raise ToolError(f"workspace root must be a directory containing {MANIFEST_NAME}")
    manifest = root / MANIFEST_NAME
    if not manifest.is_file():
        raise ToolError(
            f"No {MANIFEST_NAME} found at the supplied workspace root; pass the directory holding {MANIFEST_NAME}, "
            "not a plan directory or state file"
        )
    return manifest


def resolve_plan_entry(manifest: Path, manifest_data: list[Any], selector: str) -> tuple[int, dict[str, Any]]:
    """Resolve a plan by id, directory, or title. Raises when unknown or ambiguous."""
    wanted = selector.strip()
    wanted_directory = normalize_workspace_path(wanted) if is_relative_workspace_path(wanted) else None
    matches: list[tuple[int, dict[str, Any]]] = []
    for index, plan in enumerate(manifest_data):
        if not isinstance(plan, dict):
            continue
        directory = plan.get("directory")
        normalized = normalize_workspace_path(str(directory)) if is_relative_workspace_path(directory) else None
        if wanted in {plan.get("id"), plan.get("title")} or (wanted_directory is not None and wanted_directory == normalized):
            matches.append((index, plan))

    if not matches:
        known = ", ".join(
            str(plan.get("directory"))
            for plan in manifest_data
            if isinstance(plan, dict) and is_relative_workspace_path(plan.get("directory"))
        )
        raise ToolError(f"no plan matches the supplied selector by id, directory, or title; known plan directories: {known}")
    if len(matches) > 1:
        values = ", ".join(f"plan[{index}]" for index, _ in matches)
        raise ToolError(f"the supplied plan selector is ambiguous: {values}; use the plan id")
    return matches[0]


def project_root_for(workspace_root: Path) -> Path:
    for candidate in (workspace_root, *workspace_root.parents):
        if (candidate / ".git").exists():
            return candidate
    return workspace_root


def source_file_issues(manifest: Path, data: list[Any], include_indexes: set[int] | None = None) -> list[Issue]:
    """Check that plan source_files entries resolve to real files or directories.

    Entries are resolved against the project root (nearest ancestor with .git),
    and the workspace root. URL entries and external repository references such
    as `owner/repo:path` are skipped.
    """
    workspace_root = manifest.parent
    bases: list[Path] = []
    for base in (project_root_for(workspace_root), workspace_root):
        if base not in bases:
            bases.append(base)

    issues: list[Issue] = []
    for index, plan in enumerate(data):
        if not isinstance(plan, dict):
            continue
        if include_indexes is not None and index not in include_indexes:
            continue
        source_files = plan.get("source_files")
        if not is_string_list(source_files):
            continue
        for position, entry in enumerate(source_files):
            value = entry.strip()
            if not value or "://" in value or EXTERNAL_SOURCE_PATTERN.match(value):
                continue
            normalized = value.replace("\\", "/")
            candidate = Path(normalized)
            if candidate.is_absolute():
                continue
            exists = any((base / normalized).exists() for base in bases)
            if not exists:
                issues.append(
                    Issue(
                        manifest,
                        f"plan[{index}].source_files[{position}]: not found from the project root or workspace root: {value}",
                    )
                )
    return issues


def workspace_semantic_issues(manifest: Path) -> list[Issue]:
    """Return current workspace issues without consulting history or mutating state."""
    resolved = manifest.expanduser().resolve()
    if resolved.is_dir():
        resolved = resolved / MANIFEST_NAME

    state_files = [resolved, *referenced_checkpoints_files(resolved)]
    all_issues: list[Issue] = []
    global_ids: dict[str, Path] = {}
    display_root = project_root_for(resolved.parent)

    for state_file in state_files:
        _, issues = validate_manifest(state_file)
        all_issues.extend(issues)

        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, list):
            continue

        if state_file == resolved:
            all_issues.extend(source_file_issues(resolved, data))
            for plan_index, plan in enumerate(data):
                if not isinstance(plan, dict):
                    continue
                status = plan.get("status")
                checkpoints = plan.get("checkpoints")
                if not WORKFLOW_STATE_MACHINE.is_status(status) or not is_relative_workspace_path(checkpoints):
                    continue
                checkpoints_path = resolved.parent / normalize_workspace_path(str(checkpoints))
                try:
                    checkpoints_data = json.loads(checkpoints_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    continue
                if not isinstance(checkpoints_data, list):
                    continue
                derived = derive_plan_status(str(status), checkpoints_data)
                if derived != status:
                    all_issues.append(
                        Issue(
                            resolved,
                            f"plan[{plan_index}].status: {status!r} does not match derived status {derived!r}; run sync-plan",
                        )
                    )

        for index, entry in enumerate(data):
            if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
                continue
            entry_id = entry["id"]
            other = global_ids.get(entry_id)
            if other is not None and other != state_file:
                other_label = relative_path_label(other, display_root)
                all_issues.append(
                    Issue(state_file, f"entry[{index}].id: duplicates id from {other_label}: {entry_id!r}")
                )
            else:
                global_ids[entry_id] = state_file

    return all_issues


@dataclass
class NodeLocation:
    manifest: Path
    manifest_data: list[Any]
    plan_index: int
    checkpoints_path: Path
    checkpoints_data: list[Any]
    node_index: int


def active_node_locations_for_manifest(manifest: Path) -> list[NodeLocation]:
    resolved = manifest.expanduser().resolve()
    if resolved.is_dir():
        resolved = resolved / MANIFEST_NAME
    if not is_structural_workspace_manifest(resolved):
        return []
    manifest = resolved
    active: list[NodeLocation] = []
    manifest_data = load_state_entries(manifest)
    for plan_index, plan in enumerate(manifest_data):
        if not isinstance(plan, dict):
            continue
        value = plan.get("checkpoints")
        if not is_relative_workspace_path(value):
            continue
        checkpoints_path = manifest.parent / normalize_workspace_path(str(value))
        if checkpoints_path.name != CHECKPOINTS_NAME or not checkpoints_path.is_file():
            continue
        checkpoints_data = load_state_entries(checkpoints_path)
        for node_index, node in enumerate(checkpoints_data):
            if isinstance(node, dict) and node.get("status") == "in_progress":
                active.append(
                    NodeLocation(
                        manifest,
                        manifest_data,
                        plan_index,
                        checkpoints_path,
                        checkpoints_data,
                        node_index,
                    )
                )
    return active


def locate_node(manifest: Path, node_id: str) -> NodeLocation:
    manifest_data = load_state_entries(manifest)
    matches: list[NodeLocation] = []
    seen_paths: set[Path] = set()

    for plan_index, plan in enumerate(manifest_data):
        if not isinstance(plan, dict):
            continue
        value = plan.get("checkpoints")
        if not is_relative_workspace_path(value):
            continue
        checkpoints_path = manifest.parent / normalize_workspace_path(str(value))
        resolved = checkpoints_path.resolve()
        if resolved in seen_paths or checkpoints_path.name != CHECKPOINTS_NAME or not checkpoints_path.is_file():
            continue
        seen_paths.add(resolved)
        checkpoints_data = load_state_entries(checkpoints_path)
        for node_index, node in enumerate(checkpoints_data):
            if isinstance(node, dict) and node.get("id") == node_id:
                matches.append(NodeLocation(manifest, manifest_data, plan_index, checkpoints_path, checkpoints_data, node_index))

    if not matches:
        raise ToolError(f"node {node_id} not found in any referenced checkpoints file")
    if len(matches) > 1:
        raise ToolError(f"node {node_id} appears multiple times; fix duplicate ids before transitioning")
    return matches[0]


def plan_label(plan: dict[str, Any], index: int) -> str:
    title = plan.get("title")
    return public_summary(title, f"plan[{index}]")


def write_location_and_sync_plan(location: NodeLocation) -> list[str]:
    """Validate the mutated checkpoints file, write it, and re-derive the owning plan status."""
    project_root = project_root_for(location.manifest.parent)
    _, issues = _validate_checkpoints_data(location.checkpoints_path, location.checkpoints_data)
    if issues:
        details = "\n".join(
            f"  {relative_path_label(issue.path, project_root)}: {issue.message}"
            for issue in issues
        )
        raise ToolError(f"refusing to write an invalid state file; fix these issues first:\n{details}")

    plan = location.manifest_data[location.plan_index]
    plan_status = plan.get("status") if isinstance(plan, dict) else None
    if not isinstance(plan, dict) or not WORKFLOW_STATE_MACHINE.is_status(plan_status):
        raise ToolError(f"{MANIFEST_NAME}: plan[{location.plan_index}].status is invalid; fix the manifest before mutating nodes")

    label = plan_label(plan, location.plan_index)
    derived = derive_plan_status(str(plan_status), location.checkpoints_data)
    if derived != plan_status and not WORKFLOW_STATE_MACHINE.can_reach(str(plan_status), derived):
        raise ToolError(
            f"plan {label!r}: this change derives plan status {derived!r}, but {plan_status!r} cannot reach it; "
            f"fix {MANIFEST_NAME} first"
        )

    write_state_entries(location.checkpoints_path, location.checkpoints_data)
    messages: list[str] = []
    if derived != plan_status:
        plan["status"] = derived
        write_state_entries(location.manifest, location.manifest_data)
        messages.append(f"OK: plan {label!r} {plan_status} -> {derived}")
    return messages


def load_plan_checkpoints(manifest: Path, plan: dict[str, Any]) -> tuple[list[Any] | None, str | None]:
    value = plan.get("checkpoints")
    if not is_relative_workspace_path(value):
        return None, "invalid checkpoints path"
    normalized = normalize_workspace_path(str(value))
    path = manifest.parent / normalized
    if path.name != CHECKPOINTS_NAME or not path.is_file():
        return None, f"missing checkpoints file: {normalized}"
    try:
        return load_state_entries(path), None
    except ToolError as exc:
        return None, str(exc)


def ensure_location_is_valid(location: NodeLocation) -> None:
    """Reject malformed state before an acceptance event can cause effects."""
    _, issues = _validate_checkpoints_data(location.checkpoints_path, location.checkpoints_data)
    if not issues:
        return
    project_root = project_root_for(location.manifest.parent)
    details = "; ".join(
        f"{relative_path_label(issue.path, project_root)}: {issue.message}"
        for issue in issues
    )
    raise ToolError(f"acceptance event rejected because current state is invalid: {details}")


def plan_document_labels(plan_dir: Path, exclude_dirs: set[Path]) -> tuple[set[str], set[str], int]:
    labels: set[str] = set()
    invalid_labels: set[str] = set()
    scanned = 0
    for current_root, dirs, files in os.walk(plan_dir):
        current = Path(current_root)
        dirs[:] = [
            name
            for name in dirs
            if name not in DISCOVERY_SKIP_DIRS and (current / name).resolve() not in exclude_dirs
        ]
        for name in files:
            if not name.endswith(".md"):
                continue
            try:
                text = (current / name).read_text(encoding="utf-8")
            except OSError:
                continue
            scanned += 1
            for candidate in REQUIREMENT_LABEL_CANDIDATE_PATTERN.findall(text):
                if is_requirement_label(candidate):
                    labels.add(candidate)
                else:
                    invalid_labels.add(candidate)
    return labels, invalid_labels, scanned
