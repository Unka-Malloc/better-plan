"""Canonical Better Plan v3 protocol models and pure helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping
import hashlib
import json
import re
import uuid


MANIFEST_NAME = "Manifest.json"
PLAN_NAME = "Plan.json"
CHECKPOINTS_NAME = "Checkpoints.json"
PLAN_DOCUMENT = "Plan.md"
DESIGN_NAME = "Design.md"
DESIGN_PRISTINE_NAME = "Design.pristine.md"

MANIFEST_SCHEMA = "better-plan.manifest/v3"
PLAN_SCHEMA = "better-plan.plan/v3"
CHECKPOINTS_SCHEMA = "better-plan.checkpoints/v3"

STATE_FILE_NAMES = {MANIFEST_NAME, PLAN_NAME, CHECKPOINTS_NAME}

PLAN_PHASES = (
    "draft",
    "designing",
    "ready",
    "authorized",
    "revising",
    "completed",
    "blocked",
)
# Only an unsealed Plan may be edited freely; a sealed Plan changes through a
# continuation. The Dossier belongs to the pre-authorization phases alone.
EDITABLE_PHASES = frozenset({"draft", "designing", "revising"})
DOSSIER_PHASES = frozenset({"draft", "designing"})
AUTHORIZED_PHASES = frozenset({"authorized", "revising", "completed", "blocked"})

TASK_STATUSES = (
    "pending",
    "in_progress",
    "completed",
    "blocked_by_authority",
    "blocked_by_environment",
)
TERMINAL_TASK_STATUSES = frozenset(
    {"completed", "blocked_by_authority", "blocked_by_environment"}
)
DELIVERY_STATUSES = ("pending", "in_progress", "completed", "blocked")
DISPATCH_PHASES = ("worker_running", "worker_correction", "awaiting_acceptance")

VALID_DIFFICULTIES = ("standard", "complex")
VALID_WORKERS = ("general", "frontend")
VALID_WORKLOADS = ("light", "medium", "heavy")
VALID_VERIFICATIONS = ("code", "visual", "hybrid")
RENDERED_VERIFICATIONS = frozenset({"visual", "hybrid"})
VALID_AUTHORIZATION_SOURCES = (
    "explicit",
    "inherited_host_plan",
    "inherited_implementation_request",
)

# One flat risk vocabulary. Elevated tags stay immutable across an inherited
# continuation, but do not mechanically select a Worker tier.
ELEVATED_RISKS = frozenset(
    {
        "migration",
        "removal",
        "security",
        "privacy",
        "irreversible_side_effect",
        "release",
        "public_interface",
        "schema",
        "protocol",
        "persistent_state",
        "concurrency",
        "shared_resource",
        "performance",
        "operations",
    }
)
VALID_RISKS = ELEVATED_RISKS | {"observability", "quality"}

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
# Host identities are opaque framework values. Preserve the exact returned
# token while bounding its size and character set; slash namespaces are not
# filesystem paths merely because one host renders them that way.
OPAQUE_EVENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:/-]{1,128}$")
CODE_PATTERN = re.compile(r"^(?:PLAN|REQ|TASK|NODE|OUT|AC|Q|DEC)-[A-Z0-9][A-Z0-9-]*$")
OPTION_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")

# Absolute local paths and UNC shares leak machine identity and break portability.
# A leading separator must introduce a real path segment, so public `https://`
# references, shell globs such as `tests/**/*.py`, and arithmetic like `3 / 4`
# are all left alone.
ABSOLUTE_PATH_PATTERN = re.compile(
    r"(?<![\w./\\~+*?-])(?:/(?=[A-Za-z0-9_.])|~[/\\]|[A-Za-z]:[/\\]|\\\\)"
)
# Only runtime endpoints are rejected: loopback names and bare IP literals.
NETWORK_ENDPOINT_PATTERN = re.compile(
    r"(?i)(?<![\w.])(?:localhost"
    r"|(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3})"
    r"(?::\d{1,5})?(?![\w.])"
)
# Token shapes only. Ordinary prose about bearer authentication is not a secret.
SENSITIVE_TOKEN_PATTERN = re.compile(
    r"(?i)(?:\bbearer\s+[A-Za-z0-9._~+/-]{16,}=*"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|\b(?:sk|ghp|xox[baprs])[-_][A-Za-z0-9]{12,})"
)


class ToolError(RuntimeError):
    """Raised when a state operation cannot be completed safely."""


@dataclass(frozen=True)
class Issue:
    path: Path
    message: str


def generate_id() -> str:
    """Return one opaque runtime correlation handle.

    Correlation handles are minted by Better Plan, never authored by an agent,
    and never appear in the semantic Plan payload.
    """

    return str(uuid.uuid4())


def is_code(value: Any, prefix: str | None = None) -> bool:
    if not isinstance(value, str) or CODE_PATTERN.fullmatch(value) is None:
        return False
    return prefix is None or value.startswith(prefix + "-")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def semantic_payload(plan: Mapping[str, Any]) -> dict[str, Any]:
    """Return the approval-relevant Plan payload without mutable receipts."""

    return {
        "schema": plan.get("schema"),
        "code": plan.get("code"),
        "title": plan.get("title"),
        "intent": plan.get("intent"),
        "ledger": plan.get("ledger"),
        "dossier": plan.get("dossier"),
        "spec": plan.get("spec"),
    }


def semantic_digest(plan: Mapping[str, Any]) -> str:
    return sha256_value(semantic_payload(plan))


def normalize_workspace_path(value: str) -> str:
    text = Path(value.replace("\\", "/")).as_posix()
    return text[2:] if text.startswith("./") else text


def plain_shell_command(value: str) -> str:
    """Return one regression command without a Markdown code-span wrapper.

    Designers habitually write ``- `cmake --build build` ``; a literal backtick
    pair handed to the shell becomes command substitution that executes the
    command's own output. The wrapper carries no meaning, so it is removed
    wherever a stored command is executed or compiled.
    """

    text = value.strip()
    if len(text) >= 2 and text[0] == "`" and text[-1] == "`" and "`" not in text[1:-1]:
        text = text[1:-1].strip()
    return text


def plain_regression_paths(values: Iterable[str]) -> list[str]:
    """Return declared regression paths as separate plain repository-relative entries.

    One Markdown bullet may list several backticked, comma-separated paths. Each
    path becomes its own entry so fingerprinting covers exactly the declared files.
    """

    paths: list[str] = []
    for raw in values:
        for item in str(raw).split(","):
            text = item.strip()
            if len(text) >= 2 and text[0] == "`" and text[-1] == "`":
                text = text[1:-1].strip()
            if text and text not in paths:
                paths.append(text)
    return paths


def is_relative_workspace_path(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        return False
    path = Path(value.replace("\\", "/"))
    return not path.is_absolute() and ".." not in path.parts and value not in {".", ".."}


def safe_summary_issue(value: Any, max_chars: int = 1000) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return "must be a non-empty string"
    text = value.strip()
    if len(text) > max_chars:
        return "is too long"
    if "\n" in text or "\r" in text:
        return "must be a single line"
    if ABSOLUTE_PATH_PATTERN.search(text):
        return "must not expose an absolute local path"
    if NETWORK_ENDPOINT_PATTERN.search(text):
        return "must not expose a runtime endpoint"
    if SENSITIVE_TOKEN_PATTERN.search(text):
        return "must not contain secret-shaped data"
    return None


def public_summary(value: Any, field: str) -> str:
    issue = safe_summary_issue(value)
    if issue is not None:
        raise ToolError("%s %s" % (field, issue))
    return str(value).strip()


def plan_template() -> dict[str, Any]:
    return {
        "schema": PLAN_SCHEMA,
        "code": "PLAN-001",
        "title": "Delivery plan",
        "directory": "delivery",
        "phase": "draft",
        "intent": {
            "goal": "One observable delivery outcome.",
            "scope": {"in": ["Authorized capability"], "out": ["Unrelated work"]},
            "success": ["Every requirement has executable evidence."],
            "risk_boundary": ["No unapproved irreversible side effects."],
            "autonomy": {
                "allow_in_scope_revision": True,
                "allow_reviewer_repairs": True,
                "forbid_mid_execution_questions": True,
                "blocked_branch_policy": "continue_independent_work",
            },
        },
        "ledger": {
            "observed": [],
            "user_decided": [],
            "defaulted": [],
            "unresolved": [],
        },
        "dossier": {"status": "not_required", "questions": []},
        "spec": {
            "requirements": [],
            "architecture": {"summary": "", "notes": []},
            "tasks": [],
            "full_regression": {"commands": [], "paths": []},
        },
        "lifecycle": {
            "sealed": None,
            "designer_session": None,
            "reviewer_session": None,
            "authorization": None,
            "continuation_receipts": [],
        },
    }


def task_template() -> dict[str, Any]:
    """Return one illustrative Task contract for authors."""

    return {
        "code": "TASK-001",
        "title": "Deliver one bounded outcome",
        "outcome": "One observable behavior satisfies its focused oracle.",
        "scope": {"in": ["Bounded capability"], "out": ["Unrelated behavior"]},
        "prerequisites": [],
        "inputs": [],
        "outputs": [
            {
                "code": "OUT-001",
                "title": "Verified result",
                "artifact": "relative/path",
                "guarantee": "The delivery can rely on this behavior.",
            }
        ],
        "ownership": {"write_paths": ["relative/output"], "shared_exclusive": []},
        "worker": "general",
        "difficulty": "standard",
        "workload": "medium",
        "verification": "code",
        "requirements": ["REQ-001"],
        "risks": [],
        "nodes": [
            {
                "code": "NODE-001",
                "title": "deliver-result",
                "outcome": "Complete the Task's bounded implementation and verification.",
                "prerequisites": [],
            }
        ],
        "design": {
            "approach": ["The direct implementation that satisfies the outcome"],
            "interfaces": ["Public contract, when the Task changes one"],
        },
        "acceptance": [
            {
                "code": "AC-001",
                "covers": ["REQ-001", "OUT-001"],
                "given": "Declared starting state",
                "when": "The behavior is exercised",
                "then": "The observable result occurs",
                "oracle": "Exact pass/fail rule",
                "evidence": {"type": "command", "source": "focused check"},
            }
        ],
        "focused_regression": {"commands": ["focused command"], "paths": ["relative/path"]},
    }


def question_template() -> dict[str, Any]:
    """Return one illustrative Decision Dossier question."""

    return {
        "code": "Q-001",
        "question": "Which delivery boundary should this migration adopt?",
        "context": "The repository supports both boundaries; the choice is not discoverable.",
        "resolves": ["DEC-001"],
        "options": [
            {
                "id": "compatible",
                "label": "Keep the old surface during one deprecation window",
                "effects": [
                    "Both surfaces stay callable until the next release.",
                    "Acceptance covers old and new call paths.",
                ],
            },
            {
                "id": "replace",
                "label": "Remove the old surface in this delivery",
                "effects": [
                    "The old surface is deleted with its tests.",
                    "Acceptance proves no caller remains.",
                ],
            },
        ],
        "recommended": "compatible",
        "default": "compatible",
    }


def manifest_template() -> dict[str, Any]:
    return {"schema": MANIFEST_SCHEMA, "plans": []}


def checkpoints_template(plan: Mapping[str, Any]) -> dict[str, Any]:
    spec = plan.get("spec") if isinstance(plan.get("spec"), Mapping) else {}
    tasks = spec.get("tasks") if isinstance(spec.get("tasks"), list) else []
    sealed = plan.get("lifecycle", {}).get("sealed")
    revision = sealed.get("revision") if isinstance(sealed, Mapping) else None
    return {
        "schema": CHECKPOINTS_SCHEMA,
        "plan": plan.get("code"),
        "revision": revision,
        "semantic_digest": semantic_digest(plan),
        "delivery_status": "pending",
        "full_regression": None,
        "tasks": [task_state(task.get("code")) for task in tasks if isinstance(task, Mapping)],
    }


def task_state(code: Any) -> dict[str, Any]:
    return {"code": code, "status": "pending", "dispatch": None, "evidence": []}


PLAN_TEMPLATE = plan_template()
MANIFEST_TEMPLATE = manifest_template()
