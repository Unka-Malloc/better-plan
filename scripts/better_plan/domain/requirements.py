"""Programme-wide requirement catalogue and derived coverage.

``Requirements.json`` next to ``Programme.json`` owns requirement identity and
status. Deliveries, Trees, and Tasks reference catalogue ids through ``source_ids``;
coverage is computed on demand and never stored.
"""

from __future__ import annotations

from typing import Any, Mapping

from .models import ToolError
from .programme import delivery_index, programme_order


REQUIREMENTS_SCHEMA = "better-plan.requirements"
REQUIREMENTS_NAME = "Requirements.json"


def new_catalogue() -> dict[str, Any]:
    return {"schema": REQUIREMENTS_SCHEMA, "requirements": []}


def requirement_id(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise ToolError("requirement.id must be a non-empty string")
    return value


def normalize_requirement(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ToolError("requirement entry must be an object")
    entry = dict(value)
    entry["id"] = requirement_id(entry.get("id"))
    return entry


def catalogue_index(catalogue: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Index catalogue entries by id, rejecting duplicate identities."""

    values: dict[str, dict[str, Any]] = {}
    for item in catalogue.get("requirements") or []:
        entry = normalize_requirement(item)
        if entry["id"] in values:
            raise ToolError("duplicate requirement id %s" % entry["id"])
        values[entry["id"]] = entry
    return values


def source_ids(entry: Any) -> list[str]:
    """Return the catalogue id references carried by one requirement entry."""

    if not isinstance(entry, Mapping):
        return []
    values = entry.get("source_ids")
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, str)]


def coverage(
    programme: Mapping[str, Any], catalogue: Mapping[str, Any], exports: Mapping[str, Any]
) -> dict[str, Any]:
    """Derive catalogue coverage from delivery outlines, Trees, and Tasks."""

    index = catalogue_index(catalogue)
    deliveries = delivery_index(programme)
    by_requirement = {code: {"deliveries": [], "tasks": []} for code in index}
    unknown_refs: list[dict[str, Any]] = []
    seen_unknown: set[tuple[str, str | None, str]] = set()

    def record(delivery_id: str, task_id: str | None, ref: str) -> None:
        if ref in index:
            item = by_requirement[ref]
            if delivery_id not in item["deliveries"]:
                item["deliveries"].append(delivery_id)
            if task_id is not None:
                pair = {"delivery": delivery_id, "task": task_id}
                if pair not in item["tasks"]:
                    item["tasks"].append(pair)
            return
        key = (delivery_id, task_id, ref)
        if key not in seen_unknown:
            seen_unknown.add(key)
            unknown_refs.append({"delivery": delivery_id, "task": task_id, "ref": ref})

    for delivery_id in programme_order(programme):
        delivery = deliveries.get(delivery_id) or {}
        if not delivery.get("tree"):
            for entry in delivery.get("requirements") or []:
                for ref in source_ids(entry):
                    record(delivery_id, None, ref)
            continue
        export = exports.get(delivery_id)
        tree = export.get("tree") if isinstance(export, Mapping) else None
        if not isinstance(tree, Mapping):
            continue
        for entry in tree.get("requirements") or []:
            for ref in source_ids(entry):
                record(delivery_id, None, ref)
        for task in tree.get("tasks") or []:
            if not isinstance(task, Mapping):
                continue
            task_id = task.get("id")
            for entry in task.get("requirements") or []:
                for ref in source_ids(entry):
                    record(delivery_id, str(task_id) if task_id is not None else None, ref)

    uncovered = [
        code for code in index if not by_requirement[code]["deliveries"] and "exclusion" not in index[code]
    ]
    excluded = [code for code in index if "exclusion" in index[code]]
    return {
        "by_requirement": by_requirement,
        "uncovered": uncovered,
        "excluded": excluded,
        "unknown_refs": unknown_refs,
    }
