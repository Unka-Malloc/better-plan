"""Models layer for Better Plan workflow state."""

from __future__ import annotations

from typing import Any
from pathlib import Path
from dataclasses import dataclass
import re
import uuid


MANIFEST_NAME = "Manifest.json"


CHECKPOINTS_NAME = "Checkpoints.json"


STATE_FILE_NAMES = {MANIFEST_NAME, CHECKPOINTS_NAME}


STATUS_ORDER = ("pending", "in_progress", "blocked", "completed", "skipped")


VALID_STATUSES = set(STATUS_ORDER)


VALID_DIFFICULTIES = {"low", "medium", "high", "deep"}


VALID_PLATFORMS = {"any", "linux", "macos", "windows"}


VALID_REGRESSION_SCOPES = {"focused", "full"}


VALID_NODE_ROLES = {
    "product_requirements",
    "evidence",
    "validation_matrix",
    "architecture_scaffold",
    "implementation",
    "final_validation",
}


REGRESSION_NODE_ROLES = {"implementation", "final_validation"}


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


SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


REQUIREMENT_LABEL_TOKEN = r"REQ(?:-[A-Za-z0-9]+)+"


REQUIREMENT_LABEL_PATTERN = re.compile(rf"^{REQUIREMENT_LABEL_TOKEN}$")


REQUIREMENT_LABEL_CANDIDATE_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_-])(?:[A-Za-z0-9]+[-_])*REQ(?:[-_][A-Za-z0-9]+)+(?![A-Za-z0-9_-])"
)


EXTERNAL_SOURCE_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+:")


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


TASK_OPTIONAL_FIELDS = {"requirements", "status_reason", "regression", "acceptance", "design"}


COMMIT_REQUIRED_FIELDS = {"repository", "message", "target"}


COMMIT_OPTIONAL_FIELDS = {"delivered"}


CRITERION_REQUIRED_FIELDS = {"checked", "text"}


CRITERION_OPTIONAL_FIELDS = {"evidence", "evidence_refs"}


REGRESSION_REQUIRED_FIELDS = {"scope", "commands", "criteria", "paths"}


REGRESSION_OPTIONAL_FIELDS = {"last_pass"}


REGRESSION_RECEIPT_FIELDS = {"recorded_at", "contract_digest", "content_fingerprint"}


ACCEPTANCE_REQUIRED_FIELDS = {"phase", "attempt", "outcome"}


ACCEPTANCE_OPTIONAL_FIELDS = {
    "dispatch",
    "audit",
    "repair_node_id",
    "scaffold_fingerprint",
    "design_digest",
    "acceptance_fingerprint",
}


ACCEPTANCE_PREPARATION_FIELDS = ("design_digest", "scaffold_fingerprint", "acceptance_fingerprint")


ACCEPTANCE_STABLE_PREPARATION_FIELDS = ("design_digest", "acceptance_fingerprint")


ACCEPTANCE_DISPATCH_REQUIRED_FIELDS = {"id", "role"}


ACCEPTANCE_DISPATCH_OPTIONAL_FIELDS = {
    "contract_digest",
    "content_fingerprint",
    "design_digest",
    "scaffold_fingerprint",
    "acceptance_fingerprint",
}


ACCEPTANCE_DESIGNER_DISPATCH_REQUIRED_FIELDS = ACCEPTANCE_DISPATCH_REQUIRED_FIELDS | {"design_digest"}


ACCEPTANCE_REVIEWER_DISPATCH_REQUIRED_FIELDS = ACCEPTANCE_DISPATCH_REQUIRED_FIELDS | set(ACCEPTANCE_PREPARATION_FIELDS)


ACCEPTANCE_AUDIT_FIELDS = {"recorded_at", "contract_digest", "content_fingerprint"}


ACCEPTANCE_PHASES = {
    "awaiting_acceptance_design",
    "acceptance_designer_running",
    "awaiting_acceptance_review",
    "acceptance_reviewer_running",
    "acceptance_revision_required",
    "awaiting_executor",
    "executor_running",
    "repair_required",
    "awaiting_regression",
    "awaiting_auditor",
    "auditor_running",
    "repair_plan_required",
    "awaiting_repair",
    "accepted",
}


ACCEPTANCE_OUTCOMES = {
    "none",
    "acceptance_rejected",
    "regression_passed",
    "regression_failed",
    "regression_timeout",
    "regression_unavailable",
    "audit_failed",
    "accepted",
}


ACCEPTANCE_FAILURE_OUTCOMES = {
    "regression_failed",
    "regression_timeout",
    "regression_unavailable",
    "audit_failed",
}


OPAQUE_EVENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


EVIDENCE_REF_TYPES = {"file", "command"}


EVIDENCE_REF_FIELDS = {
    "file": {"type", "path", "sha256", "recorded_at"},
    "command": {"type", "command_sha256", "exit_code", "recorded_at"},
}


SAFE_SUMMARY_MAX_CHARS = 500


ABSOLUTE_PATH_PATTERN = re.compile(
    r"(?<![\w./\\~+-])(?://|/(?!/)|~[/\\]|[A-Za-z]:[/\\]|\\\\)"
)


NETWORK_ENDPOINT_PATTERN = re.compile(
    r"(?i)(?:\b(?:https?|wss?)://\S+|\b(?:localhost|(?:\d{1,3}\.){3}\d{1,3})(?::\d+)?\b)"
)


SENSITIVE_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(?:password|passwd|secret|api[_-]?key|access[_-]?token|refresh[_-]?token|authorization|"
    r"private[_-]?key|host|hostname|server|endpoint|dsn|database[_-]?url)\s*[:=]\s*\S+"
)


SENSITIVE_TOKEN_PATTERN = re.compile(
    r"(?i)(?:\bbearer\s+\S+|-----BEGIN [A-Z ]*PRIVATE KEY-----|\b(?:sk|ghp|xox[baprs])[-_][A-Za-z0-9]{12,})"
)


EVIDENCE_COMMAND_TIMEOUT_SECONDS = 1800


REGRESSION_COMMAND_TIMEOUT_SECONDS = 1800


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
        "Scope: Closure: module - one independently acceptable target; owned modules, directories, and files. "
        "Context: why this task is needed now. "
        "Target: intended final behavior for this Node. "
        "Design Considerations: patterns, data structures, and boundaries to follow. "
        "Design Value: why the design earns its complexity. "
        "Constraints & Risks: invariants, non-goals, and open questions."
    ),
    "requirements": ["REQ-001"],
    "design": {
        "artifact": "docs/plan/example/Architecture.md",
        "owned_paths": ["src/example.py"],
        "scaffold_paths": ["src/example.py"],
        "acceptance_paths": ["docs/plan/example/Validation.md", "tests/test_example.py"],
        "symbols": [
            {
                "path": "src/example.py",
                "kind": "function",
                "name": "evaluate",
                "operation": "add",
                "signature": "evaluate(state: object) -> str",
            }
        ],
        "interfaces": [
            {
                "name": "evaluate",
                "producer": "src/example.py",
                "consumers": ["tests/test_example.py"],
                "inputs": "validated state",
                "outputs": "one bounded result",
                "errors": ["ValueError for invalid state"],
            }
        ],
        "dependencies": [],
        "decisions": {
            "composition": "pure function composition",
            "algorithms": "constant-time lookup",
            "data_structures": "immutable mappings",
            "state": "one state owner",
            "isolation": "disjoint role paths",
            "concurrency": "serialized Plan writes",
        },
        "test_seams": ["pure function boundary"],
    },
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
    "regression": {
        "scope": "focused",
        "commands": ["python3 -m unittest tests.test_example"],
        "criteria": [0],
        "paths": ["src/example.py", "tests/test_example.py"],
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

            if node.get("role") == "final_validation" and status in {"in_progress", "completed"}:
                unfinished_implementations = [
                    str(entry.get("id"))
                    for entry in data
                    if isinstance(entry, dict)
                    and entry.get("role") == "implementation"
                    and entry.get("status") not in {"completed", "skipped"}
                ]
                if unfinished_implementations:
                    refs = ", ".join(unfinished_implementations)
                    issues.append(
                        Issue(
                            path,
                            f"node[{index}].status: final_validation cannot be {status!r} until every non-skipped implementation node is completed: {refs}",
                        )
                    )

        return issues

WORKFLOW_STATE_MACHINE = WorkflowStateMachine(
    statuses=frozenset(VALID_STATUSES),
    transitions={
        "pending": frozenset({"pending", "in_progress", "blocked", "skipped"}),
        "in_progress": frozenset({"in_progress", "pending", "completed", "blocked", "skipped"}),
        "blocked": frozenset({"blocked", "in_progress", "skipped"}),
        "completed": frozenset({"completed"}),
        "skipped": frozenset({"skipped"}),
    },
    terminal_statuses=frozenset({"completed", "skipped"}),
)


def generate_id() -> str:
    return str(uuid.uuid4())


def is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def is_requirement_label(value: Any) -> bool:
    return isinstance(value, str) and REQUIREMENT_LABEL_PATTERN.fullmatch(value) is not None


def is_manifest_id(value: Any) -> bool:
    return isinstance(value, str) and UUID4_PATTERN.fullmatch(value) is not None


def is_git_entry_path(value: Any) -> bool:
    if not is_relative_workspace_path(value):
        return False
    normalized = normalize_workspace_path(str(value))
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


def safe_summary_issue(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return "must be a non-empty string"
    normalized = value.strip()
    if len(normalized) > SAFE_SUMMARY_MAX_CHARS:
        return f"must be at most {SAFE_SUMMARY_MAX_CHARS} characters"
    if any(character in normalized for character in ("\n", "\r", "\x00")):
        return "must be a single line without control characters"
    if ABSOLUTE_PATH_PATTERN.search(normalized):
        return "must not contain a concrete absolute path"
    if NETWORK_ENDPOINT_PATTERN.search(normalized):
        return "must not contain a network endpoint or runtime address"
    if SENSITIVE_ASSIGNMENT_PATTERN.search(normalized) or SENSITIVE_TOKEN_PATTERN.search(normalized):
        return "must not contain a secret, credential, or server identifier"
    return None


def public_summary(value: Any, fallback: str) -> str:
    return value.strip() if isinstance(value, str) and safe_summary_issue(value) is None else fallback


def expected_checkpoints_path(directory: str) -> str:
    return f"{normalize_workspace_path(directory)}/{CHECKPOINTS_NAME}"


def expected_regression_scope(role: Any) -> str | None:
    if role == "implementation":
        return "focused"
    if role == "final_validation":
        return "full"
    return None


def has_startable_pending_node(nodes: list[Any]) -> bool:
    status_by_id: dict[str, str] = {}
    for node in nodes:
        if isinstance(node, dict) and isinstance(node.get("id"), str) and WORKFLOW_STATE_MACHINE.is_status(node.get("status")):
            status_by_id[node["id"]] = str(node["status"])

    for node in nodes:
        if not isinstance(node, dict) or node.get("status") != "pending":
            continue
        prerequisites = node.get("prerequisites")
        if not is_string_list(prerequisites):
            continue
        if all(status_by_id.get(ref) == "completed" for ref in prerequisites):
            return True
    return False


def derive_plan_status(current: str, nodes: list[Any]) -> str:
    node_statuses = [
        str(node.get("status"))
        for node in nodes
        if isinstance(node, dict) and WORKFLOW_STATE_MACHINE.is_status(node.get("status"))
    ]
    if not node_statuses:
        return current
    if "in_progress" in node_statuses:
        return "in_progress"
    if all(status in WORKFLOW_STATE_MACHINE.terminal_statuses for status in node_statuses):
        return "skipped" if all(status == "skipped" for status in node_statuses) else "completed"
    if "blocked" in node_statuses:
        # The plan stalls only when the blocked node leaves nothing startable;
        # otherwise sibling nodes can keep the plan moving.
        return "blocked" if not has_startable_pending_node(nodes) else "in_progress"
    if "completed" in node_statuses:
        return "in_progress"
    return "pending"
