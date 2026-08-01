"""Models layer for Better Plan workflow state."""

from __future__ import annotations

from typing import Any, Mapping
from pathlib import Path
from dataclasses import dataclass
import re
import uuid


MANIFEST_NAME = "Manifest.json"


CHECKPOINTS_NAME = "Checkpoints.json"


CAPABILITIES_NAME = "Capabilities.json"


STATE_FILE_NAMES = {MANIFEST_NAME, CHECKPOINTS_NAME, CAPABILITIES_NAME}


STATUS_ORDER = ("pending", "in_progress", "blocked", "deferred", "completed", "skipped")


VALID_STATUSES = set(STATUS_ORDER)


VALID_DIFFICULTIES = {"routine", "standard", "complex", "critical"}


VALID_VERIFICATION_PROFILES = {"code", "visual", "hybrid"}


VALID_PLATFORMS = {"any", "linux", "macos", "windows"}


VALID_REGRESSION_SCOPES = {"focused", "full"}


VALID_PLAN_KINDS = {
    "branch",
    "context",
    "gate",
    "group",
    "plan",
    "release",
    "root",
    "rule",
    "stage",
}


VALID_TREE_MODES = {"flatten", "hide", "show"}


VALID_NODE_STATUS_MODES = {"hide", "show"}


ENTRY_GATE_REQUIRED_FIELDS = {"title", "prerequisites", "conditions"}


ENTRY_GATE_OPTIONAL_FIELDS: set[str] = set()


MILESTONE_GATE_ROLE = "milestone_gate"


GATE_LEAF_TAG = "GATE_LEAF"


RESERVED_NODE_TAGS = {GATE_LEAF_TAG}


MILESTONE_GATE_LEAF_REQUIRED_STATUSES = {
    "pending",
    "in_progress",
    "completed",
}


VALID_NODE_ROLES = {
    "product_requirements",
    "evidence",
    "validation_matrix",
    "architecture_scaffold",
    "group_design",
    MILESTONE_GATE_ROLE,
    "implementation",
    "final_validation",
}


REGRESSION_NODE_ROLES = {"implementation", "final_validation"}


AUTOMATED_NODE_ROLES = REGRESSION_NODE_ROLES | {"group_design"}


DESIGN_NODE_ROLES = AUTOMATED_NODE_ROLES


COMPLEX_OR_CRITICAL_REQUIRED_ROLES = {
    "product_requirements",
    "evidence",
    "validation_matrix",
    "architecture_scaffold",
    "group_design",
    MILESTONE_GATE_ROLE,
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
    "purpose",
    "goal",
    "description",
    "checkpoints",
}


PLAN_OPTIONAL_FIELDS = {
    "kind",
    "tree_mode",
    "node_status",
    "entry_gate",
    "decision_issues",
    "capability_key",
}


DECISION_ISSUE_REQUIRED_FIELDS = {
    "id",
    "urgency",
    "question",
    "context",
    "options",
    "status",
}


DECISION_ISSUE_OPTIONAL_FIELDS = {"resolution"}


VALID_DECISION_URGENCIES = {"immediate", "deferred"}


VALID_DECISION_STATUSES = {"open", "resolved"}


TASK_REQUIRED_FIELDS = {
    "id",
    "status",
    "role",
    "prerequisites",
    "platform",
    "difficulty",
    "verification_profile",
    "goal",
    "description",
    "acceptance_criteria",
    "commit",
    "next",
}


TASK_OPTIONAL_FIELDS = {
    "requirements",
    "status_reason",
    "regression",
    "acceptance",
    "design",
    "code",
    "title",
    "tags",
    "conditions",
}


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
    "review",
    "repair_node_id",
    "scaffold_fingerprint",
    "design_digest",
    "acceptance_fingerprint",
}


ACCEPTANCE_PREPARATION_FIELDS = ("design_digest", "scaffold_fingerprint", "acceptance_fingerprint")


ACCEPTANCE_STABLE_PREPARATION_FIELDS = ("design_digest", "acceptance_fingerprint")


ACCEPTANCE_DISPATCH_REQUIRED_FIELDS = {"id", "role"}


ACCEPTANCE_DISPATCH_OPTIONAL_FIELDS = {
    "delegation_failures",
    "design_digest",
    "host_agent_id",
    "model",
    "model_provider",
    "reasoning_effort",
    "selector_source",
}


MAX_DELEGATION_FAILURES = 3


DESIGNER_DISPATCH_REQUIRED_FIELDS = ACCEPTANCE_DISPATCH_REQUIRED_FIELDS | {"design_digest"}


ACCEPTANCE_REVIEW_FIELDS = {"recorded_at", "dispatch_id"}


ACCEPTANCE_PHASES = {
    "awaiting_designer",
    "designer_running",
    "awaiting_worker",
    "worker_running",
    "correction_required",
    "awaiting_verifier",
    "verifier_running",
    "awaiting_reviewer",
    "reviewer_running",
    "reviewer_complete",
    "repair_plan_required",
    "awaiting_repair",
    "accepted",
}


ACCEPTANCE_OUTCOMES = {
    "none",
    "regression_passed",
    "regression_failed",
    "regression_timeout",
    "regression_unavailable",
    "accepted",
}


ACCEPTANCE_FAILURE_OUTCOMES = {
    "regression_failed",
    "regression_timeout",
    "regression_unavailable",
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
    r"(?i)\b(?:password|passwd|secret|api[_-]?key|token|access[_-]?token|refresh[_-]?token|authorization|"
    r"private[_-]?key|host|hostname|server|endpoint|dsn|database[_-]?url)\s*[:=]\s*\S+"
)


SENSITIVE_TOKEN_PATTERN = re.compile(
    r"(?i)(?:\bbearer\s+\S+|-----BEGIN [A-Z ]*PRIVATE KEY-----|\b(?:sk|ghp|xox[baprs])[-_][A-Za-z0-9]{12,})"
)


EVIDENCE_COMMAND_TIMEOUT_SECONDS = 1800


# Must cover the longest declared focused command (the frozen soak profile
# declares up to 150 minutes); a shorter cap would kill a compliant run.
REGRESSION_COMMAND_TIMEOUT_SECONDS = 9600


PLAN_TEMPLATE: dict[str, Any] = {
    "id": "01234567-89ab-4def-8123-456789abcdef",
    "status": "pending",
    "title": "Plan title",
    "directory": "plan-title",
    "source_files": ["docs/plan.md"],
    "purpose": "Why this Plan exists and what role it serves in the Plan hierarchy.",
    "goal": "One-sentence plan goal.",
    "description": "Short description of what this plan covers.",
    "checkpoints": "plan-title/Checkpoints.json",
    "kind": "group",
    "capability_key": "repository/capability",
    "tree_mode": "show",
    "node_status": "show",
    "decision_issues": [],
}


NODE_TEMPLATE: dict[str, Any] = {
    "id": "01234567-89ab-4def-8123-456789abcdef",
    "status": "pending",
    "role": "implementation",
    "prerequisites": [],
    "platform": "any",
    "difficulty": "standard",
    "verification_profile": "code",
    "goal": "One-sentence task goal.",
    "description": (
        "Scope: Closure: module - one independently acceptable target; owned modules, directories, and files. "
        "Context: why this task is needed now. "
        "Target: intended final behavior for this Node. "
        "Design Considerations: patterns, data structures, and boundaries to follow. "
        "Design Value: why the design earns its complexity. "
        "Constraints & Risks: invariants, non-goals, and open questions."
    ),
    "code": "K0",
    "title": "Concise source-grounded milestone title",
    "tags": [],
    "conditions": [],
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
        in_progress_nodes: list[tuple[int, dict[str, Any]]] = []

        for index, node in enumerate(data):
            if not isinstance(node, dict):
                continue
            status = node.get("status")
            if status == "in_progress":
                in_progress_nodes.append((index, node))

        if len(in_progress_nodes) > 1 and any(
            node.get("role") != "implementation" for _, node in in_progress_nodes
        ):
            indexes = ", ".join(f"node[{index}]" for index, _ in in_progress_nodes)
            issues.append(
                Issue(
                    path,
                    "state machine: only independent implementation nodes may be in_progress concurrently: "
                    f"{indexes}",
                )
            )

        for index, node in enumerate(data):
            if not isinstance(node, dict):
                continue

            status = node.get("status")
            if not self.is_status(status):
                continue

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
        "pending": frozenset({"pending", "in_progress", "blocked", "deferred", "skipped"}),
        "in_progress": frozenset({"in_progress", "pending", "completed", "blocked", "deferred", "skipped"}),
        "blocked": frozenset({"blocked", "in_progress", "deferred", "skipped"}),
        "deferred": frozenset({"deferred", "pending", "blocked", "skipped"}),
        "completed": frozenset({"completed"}),
        "skipped": frozenset({"skipped"}),
    },
    terminal_statuses=frozenset({"completed", "skipped"}),
)


def generate_id() -> str:
    return str(uuid.uuid4())


def is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def node_has_tag(node: Mapping[str, Any], tag: str) -> bool:
    tags = node.get("tags")
    return is_string_list(tags) and tag in tags


def is_gate_leaf_node(node: Mapping[str, Any]) -> bool:
    role = node.get("role")
    return (
        role in VALID_NODE_ROLES
        and role != MILESTONE_GATE_ROLE
        and node_has_tag(node, GATE_LEAF_TAG)
    )


def has_same_plan_gate_leaf_prerequisite(
    node: Mapping[str, Any],
    owning_nodes: list[Any],
) -> bool:
    if node_has_tag(node, GATE_LEAF_TAG):
        return False
    prerequisites = node.get("prerequisites")
    if not is_string_list(prerequisites):
        return False
    leaf_ids = {
        str(entry.get("id"))
        for entry in owning_nodes
        if isinstance(entry, Mapping)
        and is_manifest_id(entry.get("id"))
        and is_gate_leaf_node(entry)
    }
    return any(reference in leaf_ids for reference in prerequisites)


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


def has_startable_pending_node(
    nodes: list[Any],
    dependency_statuses: Mapping[str, str] | None = None,
) -> bool:
    status_by_id: dict[str, str] = dict(dependency_statuses or {})
    for node in nodes:
        if (
            isinstance(node, dict)
            and isinstance(node.get("id"), str)
            and WORKFLOW_STATE_MACHINE.is_status(node.get("status"))
        ):
            status_by_id[node["id"]] = str(node["status"])

    for node in nodes:
        if not isinstance(node, dict) or node.get("status") != "pending":
            continue
        if (
            node.get("role") == MILESTONE_GATE_ROLE
            and not has_same_plan_gate_leaf_prerequisite(node, nodes)
        ):
            continue
        if node.get("role") == "final_validation" and any(
            isinstance(entry, dict)
            and entry.get("role") == "implementation"
            and entry.get("status") not in WORKFLOW_STATE_MACHINE.terminal_statuses
            for entry in nodes
        ):
            continue
        prerequisites = node.get("prerequisites")
        if not is_string_list(prerequisites):
            continue
        if all(status_by_id.get(ref) == "completed" for ref in prerequisites):
            return True
    return False


def derive_plan_status(
    current: str,
    nodes: list[Any],
    dependency_statuses: Mapping[str, str] | None = None,
) -> str:
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
    startable = has_startable_pending_node(nodes, dependency_statuses)
    if "blocked" in node_statuses:
        # The plan stalls only when the blocked node leaves nothing startable;
        # otherwise sibling nodes can keep the plan moving.
        return "blocked" if not startable else "in_progress"
    if "deferred" in node_statuses and not startable:
        return "deferred"
    if any(status in {"completed", "deferred"} for status in node_statuses):
        return "in_progress"
    return "pending"
