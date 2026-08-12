"""Small valid Better Plan v3 fixtures."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from scripts.better_plan.domain.models import MANIFEST_SCHEMA, plan_template
from scripts.better_plan.infrastructure.plan_render import render_plan
from scripts.better_plan.infrastructure.workspace import write_json


PASSING_COMMAND = 'python3 -c "raise SystemExit(0)"'
FAILING_COMMAND = 'python3 -c "raise SystemExit(1)"'
# Fails until the Worker produces its artifact, so a correction can be proven
# without editing a frozen authorized Plan.
MARKER_COMMAND = (
    'python3 -c "import pathlib, sys; sys.exit(0 if pathlib.Path(\'marker.txt\').is_file() else 1)"'
)


def task(
    code: str = "TASK-001",
    *,
    write_paths: list[str] | None = None,
    prerequisites: list[str] | None = None,
    inputs: list[dict[str, Any]] | None = None,
    outputs: list[dict[str, Any]] | None = None,
    nodes: list[dict[str, Any]] | None = None,
    requirements: list[str] | None = None,
    acceptance_code: str = "AC-001",
    difficulty: str = "standard",
    workload: str = "medium",
    verification: str = "code",
    command: str = PASSING_COMMAND,
) -> dict[str, Any]:
    suffix = code.split("-")[-1]
    owned = write_paths or ["source.txt"]
    outputs = (
        outputs
        if outputs is not None
        else [
            {
                "code": "OUT-%s" % suffix,
                "title": "Verified behavior",
                "artifact": owned[0],
                "guarantee": "The focused command proves the behavior.",
            }
        ]
    )
    requirements = requirements if requirements is not None else ["REQ-001"]
    nodes = (
        nodes
        if nodes is not None
        else [
            {
                "code": "NODE-%s" % suffix,
                "title": "deliver-result-%s" % suffix,
                "outcome": "Complete this Task's bounded implementation and verification.",
                "prerequisites": [],
            }
        ]
    )
    covers = list(requirements) + [item["code"] for item in outputs]
    return {
        "code": code,
        "title": "Deliver the bounded behavior %s" % suffix,
        "outcome": "The requested behavior passes its focused oracle.",
        "scope": {"in": ["The bounded module and focused test"], "out": ["Unrelated capabilities"]},
        "prerequisites": prerequisites or [],
        "inputs": inputs or [],
        "outputs": outputs,
        "ownership": {"write_paths": owned, "shared_exclusive": []},
        "difficulty": difficulty,
        "workload": workload,
        "verification": verification,
        "requirements": requirements,
        "risks": [],
        "nodes": nodes,
        "design": {"approach": ["One direct bounded implementation"]},
        "acceptance": [
            {
                "code": acceptance_code,
                "covers": covers,
                "given": "A valid authorized workspace state",
                "when": "The focused verification command runs",
                "then": "The command exits successfully",
                "oracle": "The command exit code is exactly zero",
                "evidence": {"type": "command", "source": "focused regression"},
            }
        ],
        "focused_regression": {"commands": [command], "paths": owned},
    }


def complete_plan(directory: str = "delivery") -> dict[str, Any]:
    """Return a design-ready Plan whose sole Designer session already closed."""

    plan = plan_template()
    plan.update(
        {
            "code": "PLAN-001",
            "title": "Complete delivery",
            "directory": directory,
            "phase": "ready",
        }
    )
    plan["ledger"]["observed"] = [
        {"fact": "The bounded module has one focused test seam.", "source": "source.txt"}
    ]
    plan["spec"] = {
        "requirements": [
            {
                "code": "REQ-001",
                "statement": "The authorized behavior is observable and verified.",
                "source_refs": ["user-request"],
            }
        ],
        "architecture": {
            "summary": "One bounded module with an explicit test seam.",
            "notes": [
                "The module exposes one stable operation.",
                "No persisted schema change is required.",
            ],
        },
        "tasks": [task()],
        "full_regression": {"commands": [PASSING_COMMAND], "paths": ["source.txt"]},
    }
    plan["lifecycle"]["designer_session"] = {
        "count": 1,
        "id": "6f1d9a02-1f2b-4c3d-8e4f-5a6b7c8d9e01",
        "status": "completed",
    }
    return plan


def draft_plan(directory: str = "delivery") -> dict[str, Any]:
    """Return the same delivery before its Designer session opens."""

    plan = complete_plan(directory)
    plan["phase"] = "draft"
    plan["lifecycle"]["designer_session"] = None
    return plan


def write_workspace(root: Path, plan: dict[str, Any] | None = None) -> dict[str, Any]:
    value = deepcopy(plan or complete_plan())
    directory = root / value["directory"]
    directory.mkdir(parents=True, exist_ok=True)
    (root / "source.txt").write_text("fixture\n", encoding="utf-8")
    write_json(directory / "Plan.json", value)
    render_plan(directory, value)
    write_json(
        root / "Manifest.json",
        {
            "schema": MANIFEST_SCHEMA,
            "plans": [
                {
                    "code": value["code"],
                    "title": value["title"],
                    "directory": value["directory"],
                    "plan": "%s/Plan.json" % value["directory"],
                }
            ],
        },
    )
    return value
