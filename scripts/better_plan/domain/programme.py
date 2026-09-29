"""Small order-only index over split Better Plan deliveries."""

from __future__ import annotations

from collections import deque
from typing import Any, Mapping

from .checkpoints_tree import safe_id
from .models import ToolError


PROGRAMME_SCHEMA = "better-plan.programme"
PROGRAMME_EXPORT_SCHEMA = "better-plan.programme-export"
PROGRAMME_NAME = "Programme.json"
OUTLINE_FIELDS = ("goal", "success", "requirements", "open_decisions")


def new_programme(programme_id: str, title: str) -> dict[str, Any]:
    return {
        "schema": PROGRAMME_SCHEMA,
        "id": safe_id(programme_id, "programme.id"),
        "title": str(title),
        "deliveries": [],
    }


def programme_template() -> dict[str, Any]:
    return new_programme("PROGRAMME-001", "Delivery programme")


def delivery_index(programme: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    values: dict[str, dict[str, Any]] = {}
    for item in programme.get("deliveries") or []:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            values[item["id"]] = item
    return values


def delivery_slug(delivery_id: str) -> str:
    """Return the lower-case workspace slug used for a planned delivery's Tree."""

    slug = str(delivery_id).lower()
    if slug.startswith("delivery-") and len(slug) > len("delivery-"):
        slug = slug[len("delivery-"):]
    return slug


def default_tree_path(delivery_id: str) -> str:
    return delivery_slug(delivery_id) + "/Tree.json"


def default_tree_id(delivery_id: str) -> str:
    return "TREE-" + delivery_slug(delivery_id).upper()


def normalize_delivery(value: Mapping[str, Any]) -> dict[str, Any]:
    delivery = dict(value)
    delivery["id"] = safe_id(delivery.get("id"), "delivery.id")
    delivery["title"] = str(delivery.get("title") or delivery["id"])
    tree = delivery.get("tree")
    if tree is not None:
        if not isinstance(tree, str) or not tree:
            raise ToolError("delivery.tree must be a path")
        delivery["tree"] = tree.replace("\\", "/")
    requires = delivery.get("requires") or []
    if not isinstance(requires, list):
        raise ToolError("delivery.requires must be an array")
    delivery["requires"] = list(dict.fromkeys(safe_id(item, "delivery.requires") for item in requires))
    return delivery


def programme_order(programme: Mapping[str, Any]) -> list[str]:
    deliveries = delivery_index(programme)
    forward = {code: [] for code in deliveries}
    indegree = {code: 0 for code in deliveries}
    for code, delivery in deliveries.items():
        for requirement in delivery.get("requires") or []:
            if requirement in deliveries:
                forward[requirement].append(code)
                indegree[code] += 1
    queue = deque(code for code in deliveries if indegree[code] == 0)
    ordered: list[str] = []
    while queue:
        current = queue.popleft()
        ordered.append(current)
        for child in forward[current]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    visited = set(ordered)
    ordered.extend(code for code in deliveries if code not in visited)
    return ordered


def programme_report(
    programme: Mapping[str, Any], exports: Mapping[str, Any], errors: Mapping[str, str] | None = None
) -> dict[str, Any]:
    deliveries = delivery_index(programme)
    states = []
    completed: set[str] = set()
    planned: list[str] = []
    for code in programme_order(programme):
        delivery = deliveries[code]
        has_tree = bool(delivery.get("tree"))
        export = exports.get(code) if has_tree else None
        derived = export.get("derived") if isinstance(export, Mapping) else None
        if has_tree:
            state = str(derived.get("delivery_status")) if isinstance(derived, Mapping) else "missing"
        else:
            state = "planned"
        if state == "recorded":
            completed.add(code)
        requires = list(delivery.get("requires") or [])
        execution = derived.get("status") if isinstance(derived, Mapping) else "missing"
        if not has_tree or (isinstance(derived, Mapping) and derived.get("node_counts") == {}):
            execution = "planned"
            planned.append(code)
        states.append(
            {
                "id": code,
                "title": delivery.get("title"),
                "tree": delivery.get("tree"),
                "state": state,
                "execution_status": execution,
                "unconfirmed_tasks": list(derived.get("unconfirmed_tasks") or []) if isinstance(derived, Mapping) else [],
                "requires": requires,
                "blocked_by": [item for item in requires if item not in completed],
                "ready_nodes": list(derived.get("ready") or []) if isinstance(derived, Mapping) else [],
                "review_nodes": list(derived.get("review_nodes") or []) if isinstance(derived, Mapping) else [],
                "error": (errors or {}).get(code),
            }
        )
    ready = [
        item["id"]
        for item in states
        if item["state"] not in ("missing", "recorded", "planned")
        and item["execution_status"] != "planned"
        and not item["blocked_by"]
    ]
    counts: dict[str, int] = {}
    for item in states:
        counts[item["state"]] = counts.get(item["state"], 0) + 1
    report = {
        "id": programme.get("id"),
        "title": programme.get("title"),
        "deliveries": states,
        "ready": ready,
        "ready_to_design": [item["id"] for item in states if item["id"] in planned and not item["blocked_by"]],
        "counts": counts,
        "errors": dict(errors or {}),
    }
    for key in ("goal", "success"):
        if key in programme:
            report[key] = programme[key]
    return report


def programme_export(
    programme: Mapping[str, Any],
    exports: Mapping[str, Any],
    errors: Mapping[str, str] | None,
    catalogue: Mapping[str, Any],
    coverage: Mapping[str, Any],
) -> dict[str, Any]:
    """Assemble the read-only programme projection consumed by reports."""

    deliveries = delivery_index(programme)
    order = programme_order(programme)
    result: dict[str, Any] = {}
    for code in order:
        delivery = deliveries.get(code) or {}
        tree = delivery.get("tree")
        if not tree:
            result[code] = {
                "kind": "planned",
                "outline": {
                    "goal": delivery.get("goal") or "",
                    "success": list(delivery.get("success") or []),
                    "requirements": list(delivery.get("requirements") or []),
                    "open_decisions": list(delivery.get("open_decisions") or []),
                },
            }
        elif code in (errors or {}):
            result[code] = {"kind": "error", "tree": tree, "error": (errors or {})[code]}
        else:
            export = exports.get(code)
            if not isinstance(export, Mapping):
                result[code] = {"kind": "error", "tree": tree, "error": "delivery export is unavailable"}
            else:
                result[code] = {"kind": "tree", "tree": tree, "export": export}
    metrics: dict[str, list[dict[str, Any]]] = {}
    for code in order:
        item = result.get(code) or {}
        if item.get("kind") != "tree":
            continue
        for check in item["export"].get("checks") or []:
            if not isinstance(check, Mapping):
                continue
            check_result = check.get("result")
            if not isinstance(check_result, Mapping):
                continue
            values = check_result.get("metrics")
            if not isinstance(values, Mapping):
                continue
            for name, value in values.items():
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    continue
                metrics.setdefault(str(name), []).append(
                    {
                        "delivery": code,
                        "check": check.get("id"),
                        "owner": check.get("owner"),
                        "value": value,
                        "status": check_result.get("status"),
                    }
                )
    return {
        "schema": PROGRAMME_EXPORT_SCHEMA,
        "programme": programme,
        "report": programme_report(programme, exports, errors),
        "deliveries": result,
        "requirements": {
            "catalogue": list(catalogue.get("requirements") or []),
            "coverage": coverage,
        },
        "metrics": metrics,
    }
