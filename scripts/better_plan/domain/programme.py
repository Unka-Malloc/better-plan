"""Small order-only index over split Better Plan deliveries."""

from __future__ import annotations

from collections import deque
from typing import Any, Mapping

from .checkpoints_tree import safe_id
from .models import ToolError


PROGRAMME_SCHEMA = "better-plan.programme"
PROGRAMME_NAME = "Programme.json"


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


def normalize_delivery(value: Mapping[str, Any]) -> dict[str, Any]:
    delivery = dict(value)
    delivery["id"] = safe_id(delivery.get("id"), "delivery.id")
    delivery["title"] = str(delivery.get("title") or delivery["id"])
    tree = delivery.get("tree")
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
    for code in programme_order(programme):
        export = exports.get(code)
        derived = export.get("derived") if isinstance(export, Mapping) else None
        state = str(derived.get("delivery_status")) if isinstance(derived, Mapping) else "missing"
        if state == "recorded":
            completed.add(code)
        requires = list(deliveries[code].get("requires") or [])
        states.append(
            {
                "id": code,
                "title": deliveries[code].get("title"),
                "tree": deliveries[code].get("tree"),
                "state": state,
                "execution_status": derived.get("status") if isinstance(derived, Mapping) else "missing",
                "unconfirmed_tasks": list(derived.get("unconfirmed_tasks") or []) if isinstance(derived, Mapping) else [],
                "requires": requires,
                "blocked_by": [item for item in requires if item not in completed],
                "ready_nodes": list(derived.get("ready") or []) if isinstance(derived, Mapping) else [],
                "review_nodes": list(derived.get("review_nodes") or []) if isinstance(derived, Mapping) else [],
                "error": (errors or {}).get(code),
            }
        )
    ready = [item["id"] for item in states if item["state"] != "missing" and item["state"] != "recorded" and not item["blocked_by"]]
    counts: dict[str, int] = {}
    for item in states:
        counts[item["state"]] = counts.get(item["state"], 0) + 1
    return {
        "id": programme.get("id"),
        "title": programme.get("title"),
        "deliveries": states,
        "ready": ready,
        "counts": counts,
        "errors": dict(errors or {}),
    }
