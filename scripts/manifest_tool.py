#!/usr/bin/env python3
"""Validate, mutate, and report on Better Plan workflow state files."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MANIFEST_NAME = "Manifest.json"
CHECKPOINTS_NAME = "Checkpoints.json"
STATE_FILE_NAMES = {MANIFEST_NAME, CHECKPOINTS_NAME}
STATUS_ORDER = ("pending", "in_progress", "blocked", "completed", "skipped")
VALID_STATUSES = set(STATUS_ORDER)
VALID_DIFFICULTIES = {"low", "medium", "high", "deep"}
VALID_PLATFORMS = {"any", "linux", "macos", "windows"}
VALID_NODE_ROLES = {
    "product_requirements",
    "evidence",
    "validation_matrix",
    "architecture_scaffold",
    "implementation",
    "final_validation",
}
HIGH_OR_DEEP_REQUIRED_ROLES = {
    "product_requirements",
    "evidence",
    "validation_matrix",
    "architecture_scaffold",
    "final_validation",
}
FOUNDATION_ROLE_ORDER = ["product_requirements", "evidence", "validation_matrix", "architecture_scaffold"]
DISCOVERY_SKIP_DIRS = {
    ".git",
    ".hg",
    ".next",
    ".svn",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "target",
    "vendor",
}
UUID4_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
GIT_SHA_PATTERN = re.compile(r"^[0-9a-f]{7,40}$")
REQUIREMENT_LABEL_PATTERN = re.compile(r"^\S+$")
PLAN_REQUIRED_FIELDS = {
    "id",
    "status",
    "title",
    "directory",
    "source_files",
    "goal",
    "description",
    "checkpoints",
}
PLAN_OPTIONAL_FIELDS: set[str] = set()
TASK_REQUIRED_FIELDS = {
    "id",
    "status",
    "role",
    "prerequisites",
    "platform",
    "difficulty",
    "goal",
    "description",
    "acceptance_criteria",
    "commit",
    "next",
}
TASK_OPTIONAL_FIELDS = {"requirements", "status_reason"}
COMMIT_REQUIRED_FIELDS = {"repository", "message", "target"}
COMMIT_OPTIONAL_FIELDS = {"delivered"}
CRITERION_REQUIRED_FIELDS = {"checked", "text"}
CRITERION_OPTIONAL_FIELDS = {"evidence"}
PLAN_TEMPLATE: dict[str, Any] = {
    "id": "01234567-89ab-4def-8123-456789abcdef",
    "status": "pending",
    "title": "Plan title",
    "directory": "plan-title",
    "source_files": ["docs/plan.md"],
    "goal": "One-sentence plan goal.",
    "description": "Short description of what this plan covers.",
    "checkpoints": "plan-title/Checkpoints.json",
}
NODE_TEMPLATE: dict[str, Any] = {
    "id": "01234567-89ab-4def-8123-456789abcdef",
    "status": "pending",
    "role": "implementation",
    "prerequisites": [],
    "platform": "any",
    "difficulty": "medium",
    "goal": "One-sentence task goal.",
    "description": (
        "Scope: owned modules, directories, and files. "
        "Context: why this task is needed now. "
        "Target: intended final behavior for this Node. "
        "Design Considerations: patterns, data structures, and boundaries to follow. "
        "Design Value: why the design earns its complexity. "
        "Constraints & Risks: invariants, non-goals, and open questions."
    ),
    "requirements": ["REQ-001"],
    "acceptance_criteria": [
        {
            "checked": False,
            "text": "Describe a concrete check that proves this task is complete.",
        }
    ],
    "commit": {
        "repository": ".git",
        "message": "Suggested commit message.",
        "target": "Where the work should be committed or delivered.",
    },
    "next": [],
}


class ToolError(RuntimeError):
    """Raised when a command cannot be completed safely."""


@dataclass(frozen=True)
class Issue:
    path: Path
    message: str


@dataclass(frozen=True)
class WorkflowStateMachine:
    statuses: frozenset[str]
    transitions: dict[str, frozenset[str]]
    terminal_statuses: frozenset[str]

    def is_status(self, value: Any) -> bool:
        return isinstance(value, str) and value in self.statuses

    def can_transition(self, current: str, target: str) -> bool:
        return target in self.transitions.get(current, frozenset())

    def reachable_statuses(self, current: str) -> frozenset[str]:
        seen: set[str] = {current}
        frontier = [current]
        while frontier:
            status = frontier.pop()
            for target in self.transitions.get(status, frozenset()):
                if target not in seen:
                    seen.add(target)
                    frontier.append(target)
        return frozenset(seen)

    def can_reach(self, current: str, target: str) -> bool:
        return target in self.reachable_statuses(current)

    def status_issue(self, path: Path, prefix: str, value: Any) -> Issue | None:
        if self.is_status(value):
            return None
        values = ", ".join(sorted(self.statuses))
        return Issue(path, f"{prefix}.status: must be one of {values}")

    def transition_issues(self, path: Path, prefix: str, current: Any, target: Any) -> list[Issue]:
        issues: list[Issue] = []
        current_issue = self.status_issue(path, f"{prefix}.from", current)
        if current_issue is not None:
            issues.append(current_issue)
        target_issue = self.status_issue(path, f"{prefix}.to", target)
        if target_issue is not None:
            issues.append(target_issue)
        if issues:
            return issues

        if not self.can_transition(str(current), str(target)):
            allowed = ", ".join(sorted(self.transitions[str(current)]))
            issues.append(Issue(path, f"{prefix}: cannot transition from {current!r} to {target!r}; allowed targets: {allowed}"))
        return issues

    def checkpoint_snapshot_issues(self, path: Path, data: list[Any]) -> list[Issue]:
        issues: list[Issue] = []
        node_statuses: dict[str, str] = {}
        in_progress_indexes: list[int] = []

        for index, node in enumerate(data):
            if not isinstance(node, dict):
                continue
            node_id = node.get("id")
            status = node.get("status")
            if isinstance(node_id, str) and self.is_status(status):
                node_statuses[node_id] = status
            if status == "in_progress":
                in_progress_indexes.append(index)

        if len(in_progress_indexes) > 1:
            indexes = ", ".join(f"node[{index}]" for index in in_progress_indexes)
            issues.append(Issue(path, f"state machine: only one node may be in_progress at a time: {indexes}"))

        unstartable_ids: set[str] = set()
        for index, node in enumerate(data):
            if not isinstance(node, dict):
                continue

            status = node.get("status")
            if not self.is_status(status):
                continue

            prerequisites = node.get("prerequisites")
            if status in {"in_progress", "completed"} and is_string_list(prerequisites):
                incomplete = [ref for ref in prerequisites if node_statuses.get(ref) != "completed"]
                if incomplete:
                    refs = ", ".join(repr(ref) for ref in incomplete)
                    issues.append(Issue(path, f"node[{index}].status: cannot be {status!r} until prerequisites are completed: {refs}"))

            if is_string_list(prerequisites):
                blocking = [
                    ref
                    for ref in prerequisites
                    if node_statuses.get(ref) == "skipped"
                    or (ref in unstartable_ids and node_statuses.get(ref) != "completed")
                ]
                if blocking:
                    node_id = node.get("id")
                    if isinstance(node_id, str):
                        unstartable_ids.add(node_id)
                    if status in {"pending", "blocked"}:
                        refs = ", ".join(repr(ref) for ref in blocking)
                        issues.append(
                            Issue(
                                path,
                                f"node[{index}]: unstartable because prerequisites are skipped or unstartable: {refs}; "
                                "rewire prerequisites or skip this node",
                            )
                        )

            acceptance_criteria = node.get("acceptance_criteria")
            if status == "completed" and isinstance(acceptance_criteria, list):
                unchecked = [
                    criterion_index
                    for criterion_index, criterion in enumerate(acceptance_criteria)
                    if isinstance(criterion, dict) and criterion.get("checked") is False
                ]
                if unchecked:
                    indexes = ", ".join(str(criterion_index) for criterion_index in unchecked)
                    issues.append(Issue(path, f"node[{index}].status: cannot be 'completed' with unchecked acceptance criteria: {indexes}"))

        return issues

    def plan_snapshot_issues(self, path: Path, data: list[Any]) -> list[Issue]:
        issues: list[Issue] = []

        for index, plan in enumerate(data):
            if not isinstance(plan, dict):
                continue
            status = plan.get("status")
            checkpoints = plan.get("checkpoints")
            if not self.is_status(status) or not is_relative_workspace_path(checkpoints):
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
                if isinstance(node, dict) and self.is_status(node.get("status"))
            ]
            if not node_statuses:
                continue

            all_terminal = all(value in self.terminal_statuses for value in node_statuses)
            if status == "completed":
                unfinished = sorted(set(node_statuses) - self.terminal_statuses)
                if unfinished:
                    values = ", ".join(unfinished)
                    issues.append(Issue(path, f"plan[{index}].status: cannot be 'completed' while checkpoints contain non-terminal nodes: {values}"))
            elif status == "blocked" and "blocked" not in node_statuses:
                issues.append(Issue(path, f"plan[{index}].status: cannot be 'blocked' without a blocked checkpoint node"))
            elif status == "skipped" and "in_progress" in node_statuses:
                issues.append(Issue(path, f"plan[{index}].status: cannot be 'skipped' while a checkpoint node is in_progress"))
            elif status == "pending":
                if all_terminal:
                    issues.append(Issue(path, f"plan[{index}].status: cannot stay 'pending' when every checkpoint node is terminal; run sync-plan"))
                elif any(value in {"in_progress", "completed"} for value in node_statuses):
                    issues.append(Issue(path, f"plan[{index}].status: cannot stay 'pending' after checkpoint work has started; run sync-plan"))
            elif status == "in_progress" and all_terminal:
                issues.append(Issue(path, f"plan[{index}].status: cannot stay 'in_progress' when every checkpoint node is terminal; run sync-plan"))

        return issues


WORKFLOW_STATE_MACHINE = WorkflowStateMachine(
    statuses=frozenset(VALID_STATUSES),
    transitions={
        "pending": frozenset({"pending", "in_progress", "blocked", "skipped"}),
        "in_progress": frozenset({"in_progress", "completed", "blocked", "skipped"}),
        "blocked": frozenset({"blocked", "in_progress", "skipped"}),
        "completed": frozenset({"completed"}),
        "skipped": frozenset({"skipped"}),
    },
    terminal_statuses=frozenset({"completed", "skipped"}),
)


def generate_id() -> str:
    return str(uuid.uuid4())


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


def is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def is_manifest_id(value: Any) -> bool:
    return isinstance(value, str) and UUID4_PATTERN.fullmatch(value) is not None


def is_git_entry_path(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    normalized = value.strip().replace("\\", "/").rstrip("/")
    return normalized.split("/")[-1] == ".git"


def is_relative_workspace_path(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    normalized = value.strip().replace("\\", "/")
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized):
        return False
    parts = [part for part in normalized.split("/") if part]
    return bool(parts) and all(part not in {".", ".."} for part in parts)


def normalize_workspace_path(value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    return "/".join(part for part in normalized.split("/") if part)


def expected_checkpoints_path(directory: str) -> str:
    return f"{normalize_workspace_path(directory)}/{CHECKPOINTS_NAME}"


def is_workspace_root_manifest(path: Path) -> bool:
    return path.name == MANIFEST_NAME


def validate_manifest(path: Path) -> tuple[int, list[Issue]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return 0, [Issue(path, f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}")]
    except OSError as exc:
        return 0, [Issue(path, f"cannot read file: {exc}")]

    if not isinstance(data, list):
        return 0, [Issue(path, "top-level value must be an array")]

    if path.name == MANIFEST_NAME:
        return validate_plan_manifest_data(path, data)
    if path.name == CHECKPOINTS_NAME:
        return validate_checkpoints_data(path, data)
    return len(data), [Issue(path, f"state file must be named {MANIFEST_NAME} or {CHECKPOINTS_NAME}")]


def validate_plan_manifest_data(path: Path, data: list[Any]) -> tuple[int, list[Issue]]:
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

    issues.extend(WORKFLOW_STATE_MACHINE.plan_snapshot_issues(path, data))
    return len(data), issues


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
                    if not label.strip() or not REQUIREMENT_LABEL_PATTERN.fullmatch(label):
                        issues.append(Issue(path, f"{prefix}.requirements[{label_index}]: must be a non-empty label without whitespace, such as 'REQ-001'"))
                    elif label in seen_labels:
                        issues.append(Issue(path, f"{prefix}.requirements[{label_index}]: duplicate label {label!r}"))
                    else:
                        seen_labels.add(label)

        if "status_reason" in node:
            status_reason = node.get("status_reason")
            if not isinstance(status_reason, str) or not status_reason.strip():
                issues.append(Issue(path, f"{prefix}.status_reason: must be a non-empty string when present"))

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
                    if not isinstance(evidence, str) or not evidence.strip():
                        issues.append(Issue(path, f"{criterion_prefix}.evidence: must be a non-empty string when present"))

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

    id_first_index: dict[str, int] = {}
    for index, node in enumerate(data):
        if isinstance(node, dict) and isinstance(node.get("id"), str):
            id_first_index.setdefault(node["id"], index)

    for index, node in enumerate(data):
        if not isinstance(node, dict):
            continue

        prerequisites = node.get("prerequisites")
        if isinstance(prerequisites, list):
            for ref in prerequisites:
                if not isinstance(ref, str):
                    continue
                ref_index = id_first_index.get(ref)
                if ref_index is None:
                    issues.append(Issue(path, f"node[{index}].prerequisites: unknown node id {ref!r}"))
                elif ref_index >= index:
                    issues.append(Issue(path, f"node[{index}].prerequisites: must reference an earlier node id {ref!r}"))

        next_refs = node.get("next")
        if isinstance(next_refs, list):
            for ref in next_refs:
                if not isinstance(ref, str):
                    continue
                if not is_manifest_id(ref):
                    issues.append(Issue(path, f"node[{index}].next: must contain UUID4 node ids"))
                elif ref not in id_first_index:
                    issues.append(Issue(path, f"node[{index}].next: unknown node id {ref!r}"))

    issues.extend(validate_prerequisite_cycles(path, data))
    issues.extend(validate_delivery_roles(path, data))
    issues.extend(validate_requirement_traceability(path, data))
    issues.extend(WORKFLOW_STATE_MACHINE.checkpoint_snapshot_issues(path, data))
    return len(data), issues


def validate_prerequisite_cycles(path: Path, data: Any) -> list[Issue]:
    if not isinstance(data, list):
        return []

    graph: dict[str, list[str]] = {}
    for node in data:
        if not isinstance(node, dict):
            continue
        node_id = node.get("id")
        prereqs = node.get("prerequisites")
        if isinstance(node_id, str) and is_string_list(prereqs):
            graph[node_id] = list(prereqs)

    issues: list[Issue] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str, stack: list[str]) -> None:
        if node_id in visiting:
            cycle = stack[stack.index(node_id) :] + [node_id] if node_id in stack else stack + [node_id]
            issues.append(Issue(path, f"prerequisites contain a cycle: {' -> '.join(cycle)}"))
            return
        if node_id in visited:
            return

        visiting.add(node_id)
        for dep in graph.get(node_id, []):
            if dep in graph:
                visit(dep, stack + [node_id])
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in graph:
        visit(node_id, [])

    return issues


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
        labels = set(requirements) if is_string_list(requirements) else set()
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
        raise ToolError(f"{path}: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc
    except OSError as exc:
        raise ToolError(f"{path}: cannot read file: {exc}") from exc
    if not isinstance(data, list):
        raise ToolError(f"{path}: top-level value must be an array")
    return data


def write_state_entries(path: Path, data: list[Any]) -> None:
    temp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temp, path)


def workspace_manifest_path(root: Path) -> Path:
    root = root.expanduser().resolve()
    if root.is_file():
        if root.name == MANIFEST_NAME:
            return root
        raise ToolError(f"{root}: workspace root must be a directory containing {MANIFEST_NAME}")
    manifest = root / MANIFEST_NAME
    if not manifest.is_file():
        raise ToolError(f"No {MANIFEST_NAME} found under {root}; run from the Better Plan workspace root")
    return manifest


@dataclass
class NodeLocation:
    manifest: Path
    manifest_data: list[Any]
    plan_index: int
    checkpoints_path: Path
    checkpoints_data: list[Any]
    node_index: int


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
        raise ToolError(f"node {node_id} not found in any checkpoints file referenced by {manifest}")
    if len(matches) > 1:
        values = ", ".join(str(match.checkpoints_path) for match in matches)
        raise ToolError(f"node {node_id} appears multiple times: {values}; fix duplicate ids before transitioning")
    return matches[0]


def derive_plan_status(current: str, node_statuses: list[str]) -> str:
    if not node_statuses:
        return current
    if "in_progress" in node_statuses:
        return "in_progress"
    if "blocked" in node_statuses:
        return "blocked"
    if all(status in WORKFLOW_STATE_MACHINE.terminal_statuses for status in node_statuses):
        return "skipped" if all(status == "skipped" for status in node_statuses) else "completed"
    if "completed" in node_statuses:
        return "in_progress"
    return "pending"


def plan_label(plan: dict[str, Any], index: int) -> str:
    title = plan.get("title")
    if isinstance(title, str) and title.strip():
        return title
    return f"plan[{index}]"


def run_node_mutation(
    root: str,
    node_id: str,
    target: str,
    *,
    reason: str | None = None,
    delivered: str | None = None,
) -> list[str]:
    manifest = workspace_manifest_path(Path(root))
    location = locate_node(manifest, node_id)
    node = location.checkpoints_data[location.node_index]

    current = node.get("status")
    if not WORKFLOW_STATE_MACHINE.is_status(current):
        raise ToolError(f"{location.checkpoints_path}: node[{location.node_index}].status is invalid; fix the state file before transitioning")
    current_status = str(current)
    if not WORKFLOW_STATE_MACHINE.can_transition(current_status, target):
        allowed = ", ".join(sorted(WORKFLOW_STATE_MACHINE.transitions[current_status]))
        raise ToolError(f"node {node_id}: cannot transition from {current_status!r} to {target!r}; allowed targets: {allowed}")

    node["status"] = target
    if target in {"blocked", "skipped"}:
        if reason is None or not reason.strip():
            raise ToolError(f"a non-empty --reason is required to mark a node {target}")
        node["status_reason"] = reason.strip()
    else:
        node.pop("status_reason", None)
    if delivered is not None:
        commit = node.get("commit")
        if not isinstance(commit, dict):
            raise ToolError(f"node {node_id}: commit must be an object before recording --delivered")
        commit["delivered"] = delivered

    _, issues = validate_checkpoints_data(location.checkpoints_path, location.checkpoints_data)
    if issues:
        details = "\n".join(f"  {issue.path}: {issue.message}" for issue in issues)
        raise ToolError(f"refusing to write an invalid state file; fix these issues first:\n{details}")

    plan = location.manifest_data[location.plan_index]
    plan_status = plan.get("status") if isinstance(plan, dict) else None
    if not isinstance(plan, dict) or not WORKFLOW_STATE_MACHINE.is_status(plan_status):
        raise ToolError(f"{location.manifest}: plan[{location.plan_index}].status is invalid; fix the manifest before transitioning nodes")

    node_statuses = [
        str(entry.get("status"))
        for entry in location.checkpoints_data
        if isinstance(entry, dict) and WORKFLOW_STATE_MACHINE.is_status(entry.get("status"))
    ]
    label = plan_label(plan, location.plan_index)
    derived = derive_plan_status(str(plan_status), node_statuses)
    if derived != plan_status and not WORKFLOW_STATE_MACHINE.can_reach(str(plan_status), derived):
        raise ToolError(f"plan {label!r}: this change derives plan status {derived!r}, but {plan_status!r} cannot reach it; fix {location.manifest} first")

    write_state_entries(location.checkpoints_path, location.checkpoints_data)
    messages = [f"OK: node {node_id} {current_status} -> {target}"]
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


def current_platform() -> str:
    if sys.platform == "darwin":
        return "macos"
    if sys.platform in {"win32", "cygwin"}:
        return "windows"
    if sys.platform.startswith("linux"):
        return "linux"
    return sys.platform


def validate_command(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    manifests = find_manifests(root)

    if not manifests:
        message = f"No {MANIFEST_NAME} or {CHECKPOINTS_NAME} files found under {root}"
        if args.json:
            print(json.dumps({"ok": False, "state_files": 0, "items": 0, "issues": [{"path": str(root), "message": message}]}, indent=2))
        else:
            print(message, file=sys.stderr)
        return 1

    if len(manifests) == 1 and manifests[0].name == MANIFEST_NAME:
        manifests.extend(referenced_checkpoints_files(manifests[0]))

    all_issues: list[Issue] = []
    total_entries = 0
    global_ids: dict[str, Path] = {}

    for manifest in manifests:
        entry_count, issues = validate_manifest(manifest)
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

        for index, node in enumerate(data):
            if not isinstance(node, dict) or not isinstance(node.get("id"), str):
                continue
            node_id = node["id"]
            other = global_ids.get(node_id)
            if other is not None and other != manifest:
                all_issues.append(Issue(manifest, f"entry[{index}].id: duplicates id from {other}: {node_id!r}"))
            else:
                global_ids[node_id] = manifest

    if args.json:
        payload = {
            "ok": not all_issues,
            "state_files": len(manifests),
            "items": total_entries,
            "issues": [{"path": str(issue.path), "message": issue.message} for issue in all_issues],
        }
        print(json.dumps(payload, indent=2))
        return 1 if all_issues else 0

    if all_issues:
        for issue in all_issues:
            print(f"{issue.path}: {issue.message}", file=sys.stderr)
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
        print(f"No structurally valid Better Plan workspaces found under {root}", file=sys.stderr)
        return 1

    for manifest in manifests:
        print(manifest.parent)
    return 0


def uuid_command(args: argparse.Namespace) -> int:
    for _ in range(args.count):
        print(generate_id())
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


def start_command(args: argparse.Namespace) -> int:
    for message in run_node_mutation(args.root, args.node_id, "in_progress"):
        print(message)
    return 0


def complete_command(args: argparse.Namespace) -> int:
    if args.delivered is not None and not GIT_SHA_PATTERN.fullmatch(args.delivered):
        raise ToolError("--delivered must be a lowercase hex commit sha (7-40 characters)")
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


def check_command(args: argparse.Namespace) -> int:
    manifest = workspace_manifest_path(Path(args.root))
    location = locate_node(manifest, args.node_id)
    node = location.checkpoints_data[location.node_index]

    criteria = node.get("acceptance_criteria")
    if not isinstance(criteria, list) or not criteria:
        raise ToolError(f"node {args.node_id}: acceptance_criteria must be a non-empty array")
    if not 0 <= args.criterion < len(criteria):
        raise ToolError(f"node {args.node_id}: criterion index must be between 0 and {len(criteria) - 1}")
    criterion = criteria[args.criterion]
    if not isinstance(criterion, dict):
        raise ToolError(f"node {args.node_id}: acceptance_criteria[{args.criterion}] must be an object")

    criterion["checked"] = True
    if args.evidence is not None:
        if not args.evidence.strip():
            raise ToolError("--evidence must be a non-empty string")
        criterion["evidence"] = args.evidence.strip()

    _, issues = validate_checkpoints_data(location.checkpoints_path, location.checkpoints_data)
    if issues:
        details = "\n".join(f"  {issue.path}: {issue.message}" for issue in issues)
        raise ToolError(f"refusing to write an invalid state file; fix these issues first:\n{details}")

    write_state_entries(location.checkpoints_path, location.checkpoints_data)
    print(f"OK: node {args.node_id} acceptance_criteria[{args.criterion}] checked")
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
            errors.append(f"plan {label!r}: invalid status {status!r}; fix {manifest} manually")
            continue
        nodes, error = load_plan_checkpoints(manifest, plan)
        if nodes is None:
            errors.append(f"plan {label!r}: {error}")
            continue
        node_statuses = [
            str(node.get("status"))
            for node in nodes
            if isinstance(node, dict) and WORKFLOW_STATE_MACHINE.is_status(node.get("status"))
        ]
        derived = derive_plan_status(str(status), node_statuses)
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

    plans_payload: list[dict[str, Any]] = []
    for index, plan in enumerate(manifest_data):
        if not isinstance(plan, dict):
            continue
        payload: dict[str, Any] = {
            "id": plan.get("id"),
            "title": plan.get("title"),
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
            entry = {"id": node.get("id"), "goal": node.get("goal")}
            if status == "in_progress":
                in_progress.append(entry)
            elif status == "blocked":
                blocked.append({**entry, "status_reason": node.get("status_reason")})

        payload.update({"nodes": total, "counts": counts, "in_progress": in_progress, "blocked": blocked})
        plans_payload.append(payload)

    if args.json:
        print(json.dumps({"workspace": str(manifest.parent), "plans": plans_payload}, indent=2, ensure_ascii=False))
        return 0

    print(f"Workspace: {manifest.parent}")
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
                "goal": node.get("goal"),
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
                if node.get("platform") not in {"any", platform}:
                    continue
                eligible.append(node_entry(node))

        plans_payload.append(
            {
                "id": plan.get("id"),
                "title": plan.get("title"),
                "status": status,
                "resume": resume,
                "eligible": eligible,
            }
        )

    if args.json:
        print(json.dumps({"workspace": str(manifest.parent), "platform": platform, "plans": plans_payload}, indent=2, ensure_ascii=False))
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
            "statuses": list(STATUS_ORDER),
            "roles": sorted(VALID_NODE_ROLES),
            "difficulties": sorted(VALID_DIFFICULTIES),
            "platforms": sorted(VALID_PLATFORMS),
            "template": NODE_TEMPLATE,
        }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Better Plan manifest utility")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help=f"validate a workspace {MANIFEST_NAME} and its referenced {CHECKPOINTS_NAME} files")
    validate.add_argument("root", nargs="?", default=".", help="Better Plan workspace root, manifest file, or checkpoints file")
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

    transition = subparsers.add_parser("transition", help="check whether one workflow status can transition to another")
    transition.add_argument("current", help="current status")
    transition.add_argument("target", help="target status")
    transition.add_argument("--quiet", action="store_true", help="only print transition errors")
    transition.set_defaults(func=transition_command)

    start = subparsers.add_parser("start", help="mark a node in_progress after enforcing transitions and snapshot rules")
    start.add_argument("node_id", help="node UUID")
    start.add_argument("root", nargs="?", default=".", help="Better Plan workspace root")
    start.set_defaults(func=start_command)

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

    check = subparsers.add_parser("check", help="mark one acceptance criterion checked, optionally recording evidence")
    check.add_argument("node_id", help="node UUID")
    check.add_argument("root", nargs="?", default=".", help="Better Plan workspace root")
    check.add_argument("--criterion", type=int, required=True, help="zero-based acceptance criterion index")
    check.add_argument("--evidence", help="what verification proved this criterion")
    check.set_defaults(func=check_command)

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


if __name__ == "__main__":
    raise SystemExit(main())
