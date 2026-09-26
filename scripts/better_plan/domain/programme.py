"""Programme index: many deliveries, their order, and nothing else.

One Tree is one delivery. A programme is the small document that says which
deliveries exist, where their Trees are, and which delivery must land before
another may start. It is deliberately **not** a second ledger:

* it stores no execution state — no status, no counts, no gates;
* every state it reports is derived by reading the referenced Trees;
* unknown fields are rejected, so a hand-maintained ``state`` cannot creep in and
  drift from the Tree that owns it.

The Tree stays the one writer per truth. The programme owns order only.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence
import json
import posixpath
import re

from .checkpoints_tree import (
    append_history,
    iter_nodes,
    iter_tasks,
    node_index,
    node_resources,
    derive_tree_status,
    now,
    ordered_pairs,
    ready_codes,
    reject_unknown_operation_fields,
    safe_id,
    safe_object,
    safe_record_text,
    shape_issues,
    validate_tree,
)
from .models import ToolError


PROGRAMME_SCHEMA = "better-plan.programme"
PROGRAMME_NAME = "Programme.json"
PROGRAMME_OPERATIONS = (
    "programme.update",
    "delivery.add",
    "delivery.update",
    "delivery.remove",
)

_PROGRAMME_FIELDS = frozenset(
    {
        "schema",
        "id",
        "title",
        "revision",
        "deliveries",
        "meta",
        "history",
        "created_at",
        "updated_at",
    }
)
_DELIVERY_FIELDS = frozenset({"id", "title", "tree", "requires"})
_DELIVERY_UPDATE_FIELDS = frozenset({"title", "tree", "requires"})

# A Tree reference is workspace-relative: a programme that names an absolute path
# cannot move with the repository it describes.
_SAFE_TREE_PATH = re.compile(r"^[A-Za-z0-9._][A-Za-z0-9._/-]*\.json$")


def new_programme(programme_id: str, title: str) -> dict[str, Any]:
    stamp = now()
    return {
        "schema": PROGRAMME_SCHEMA,
        "id": safe_id(programme_id, "programme.id"),
        "title": safe_record_text(title, "programme.title", max_chars=500),
        "revision": 0,
        "deliveries": [],
        "meta": {},
        "history": [],
        "created_at": stamp,
        "updated_at": stamp,
    }


def programme_template() -> dict[str, Any]:
    return {
        "schema": PROGRAMME_SCHEMA,
        "id": "PROGRAMME-001",
        "title": "Delivery programme",
        "revision": 0,
        "deliveries": [],
        "meta": {},
        "history": [],
        "created_at": "timestamp",
        "updated_at": "timestamp",
    }


def iter_deliveries(programme: Mapping[str, Any]) -> list[dict[str, Any]]:
    deliveries = programme.get("deliveries")
    if not isinstance(deliveries, list):
        return []
    return [item for item in deliveries if isinstance(item, dict)]


def delivery_index(programme: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for delivery in iter_deliveries(programme):
        code = delivery.get("id")
        if isinstance(code, str) and code not in result:
            result[code] = delivery
    return result


def _validate_tree_reference(value: Any) -> str | None:
    text = safe_record_text(value, "delivery.tree", max_chars=256)
    if _SAFE_TREE_PATH.fullmatch(text) is None or ".." in text.split("/"):
        raise ToolError("delivery.tree must be a relative path to a Tree.json")
    return posixpath.normpath(text)


def _delivery_requires(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ToolError("delivery.requires must be an array of delivery ids")
    requires: list[str] = []
    for item in value:
        code = safe_id(item, "delivery.requires")
        if code not in requires:
            requires.append(code)
    return requires


def validate_programme(programme: Mapping[str, Any]) -> list[str]:
    """Validate the programme index: shape, references, and acyclicity."""

    issues: list[str] = []
    if not isinstance(programme, Mapping):
        return ["programme must be an object"]
    unknown = sorted(set(programme) - _PROGRAMME_FIELDS)
    if unknown:
        issues.append("programme has unknown field(s): %s" % ", ".join(unknown))
    if programme.get("schema") != PROGRAMME_SCHEMA:
        issues.append("programme.schema must be %s" % PROGRAMME_SCHEMA)
    if not isinstance(programme.get("id"), str) or not str(programme.get("id")).strip():
        issues.append("programme.id must be a safe non-empty id")
    if not isinstance(programme.get("title"), str) or not str(programme.get("title")).strip():
        issues.append("programme.title must be non-empty text")
    if type(programme.get("revision")) is not int or programme.get("revision") < 0:
        issues.append("programme.revision must be a non-negative integer")
    if not isinstance(programme.get("meta"), Mapping):
        issues.append("programme.meta must be an object")
    if not isinstance(programme.get("history"), list):
        issues.append("programme.history must be an array")
    for field in ("created_at", "updated_at"):
        if not isinstance(programme.get(field), str) or not str(programme.get(field)).strip():
            issues.append("programme.%s must be a timestamp string" % field)
    deliveries = programme.get("deliveries")
    if not isinstance(deliveries, list):
        return issues + ["programme.deliveries must be an array"]

    seen: set[str] = set()
    for index, delivery in enumerate(deliveries):
        prefix = "deliveries[%d]" % index
        if not isinstance(delivery, Mapping):
            issues.append("%s must be an object" % prefix)
            continue
        unknown = sorted(set(delivery) - _DELIVERY_FIELDS)
        if unknown:
            issues.append("%s has unknown field(s): %s" % (prefix, ", ".join(unknown)))
        code = delivery.get("id")
        if not isinstance(code, str) or not code.strip():
            issues.append("%s.id must be a safe non-empty id" % prefix)
        elif code in seen:
            issues.append("%s.id is duplicate: %s" % (prefix, code))
        else:
            seen.add(code)
        if not isinstance(delivery.get("title"), str) or not str(delivery.get("title")).strip():
            issues.append("%s.title must be non-empty text" % prefix)
        tree = delivery.get("tree")
        if not isinstance(tree, str) or _SAFE_TREE_PATH.fullmatch(tree) is None or ".." in tree.split("/"):
            issues.append("%s.tree must be a relative path to a Tree.json" % prefix)
        requires = delivery.get("requires")
        if requires is not None:
            if not isinstance(requires, list) or any(not isinstance(item, str) for item in requires):
                issues.append("%s.requires must be an array of delivery ids" % prefix)
            else:
                if len(set(requires)) != len(requires):
                    issues.append("%s.requires must not repeat a delivery" % prefix)
                if isinstance(code, str) and code in requires:
                    issues.append("%s.requires cannot reference itself" % prefix)

    for index, delivery in enumerate(deliveries):
        if not isinstance(delivery, Mapping):
            continue
        for requirement in delivery.get("requires") or []:
            if not isinstance(requirement, str):
                continue
            if requirement not in seen:
                issues.append(
                    "deliveries[%d].requires references unknown delivery %s" % (index, requirement)
                )

    graph = {
        str(delivery.get("id")): [
            item for item in (delivery.get("requires") or []) if item in seen
        ]
        for delivery in deliveries
        if isinstance(delivery, Mapping) and isinstance(delivery.get("id"), str)
    }
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(code: str, trail: list[str]) -> list[str] | None:
        if code in visiting:
            return trail[trail.index(code) :] + [code]
        if code in visited:
            return None
        visiting.add(code)
        trail.append(code)
        for requirement in graph.get(code, []):
            cycle = visit(requirement, trail)
            if cycle is not None:
                return cycle
        trail.pop()
        visiting.remove(code)
        visited.add(code)
        return None

    for code in graph:
        cycle = visit(code, [])
        if cycle is not None:
            issues.append("delivery cycle: %s" % " -> ".join(cycle))
            break
    return issues


def delivery_order(programme: Mapping[str, Any]) -> list[str]:
    """Return delivery ids with every requirement before the delivery it gates."""

    index = delivery_index(programme)
    order: list[str] = []
    pending = [code for code in index]
    while pending:
        progressed = False
        remaining = set(pending)
        for code in list(pending):
            requirements = [item for item in (index[code].get("requires") or []) if item in remaining]
            if not requirements:
                order.append(code)
                pending.remove(code)
                progressed = True
        if not progressed:
            # A cycle keeps its declared order; validation already reported it.
            order.extend(pending)
            break
    return order


def _operation_programme_update(programme: dict[str, Any], operation: Mapping[str, Any]) -> None:
    reject_unknown_operation_fields(operation, {"op", "title", "meta"})
    if "title" in operation:
        programme["title"] = safe_record_text(operation["title"], "programme.title", max_chars=500)
    if "meta" in operation:
        programme["meta"] = safe_object(operation["meta"], "programme.meta")


def _operation_delivery_add(programme: dict[str, Any], operation: Mapping[str, Any]) -> None:
    reject_unknown_operation_fields(
        operation, {"op", "id", "title", "tree", "requires"}
    )
    code = safe_id(operation.get("id"), "delivery.add id")
    if code in delivery_index(programme):
        raise ToolError("delivery.add id already exists: %s" % code)
    programme.setdefault("deliveries", []).append(
        {
            "id": code,
            "title": safe_record_text(
                operation.get("title") or code, "delivery.title", max_chars=500
            ),
            "tree": _validate_tree_reference(operation.get("tree")),
            "requires": _delivery_requires(operation.get("requires")),
        }
    )


def _operation_delivery_update(programme: dict[str, Any], operation: Mapping[str, Any]) -> None:
    reject_unknown_operation_fields(operation, {"op", "id", "set"})
    code = safe_id(operation.get("id"), "delivery.update id")
    delivery = delivery_index(programme).get(code)
    if delivery is None:
        raise ToolError("unknown delivery: %s" % code)
    changes = operation.get("set")
    if not isinstance(changes, Mapping) or not changes:
        raise ToolError("delivery.update set must be a non-empty object")
    unknown = sorted(set(changes) - _DELIVERY_UPDATE_FIELDS)
    if unknown:
        raise ToolError("delivery.update cannot change: %s" % ", ".join(unknown))
    if "title" in changes:
        delivery["title"] = safe_record_text(changes["title"], "delivery.title", max_chars=500)
    if "tree" in changes:
        delivery["tree"] = _validate_tree_reference(changes["tree"])
    if "requires" in changes:
        delivery["requires"] = _delivery_requires(changes["requires"])


def _operation_delivery_remove(programme: dict[str, Any], operation: Mapping[str, Any]) -> None:
    reject_unknown_operation_fields(operation, {"op", "id", "force"})
    code = safe_id(operation.get("id"), "delivery.remove id")
    delivery = delivery_index(programme).get(code)
    if delivery is None:
        raise ToolError("unknown delivery: %s" % code)
    dependents = sorted(
        str(item.get("id"))
        for item in iter_deliveries(programme)
        if code in (item.get("requires") or [])
    )
    if dependents and operation.get("force") is not True:
        raise ToolError(
            "delivery %s is required by %s; use force:true" % (code, ", ".join(dependents))
        )
    programme["deliveries"] = [item for item in programme["deliveries"] if item is not delivery]
    for item in iter_deliveries(programme):
        item["requires"] = [value for value in (item.get("requires") or []) if value != code]


def _apply_operation(programme: dict[str, Any], operation: Mapping[str, Any]) -> None:
    kind = operation.get("op")
    if kind not in PROGRAMME_OPERATIONS:
        raise ToolError("unknown programme operation: %s" % kind)
    handlers = {
        "programme.update": _operation_programme_update,
        "delivery.add": _operation_delivery_add,
        "delivery.update": _operation_delivery_update,
        "delivery.remove": _operation_delivery_remove,
    }
    handlers[kind](programme, operation)


def apply_operations(
    programme: dict[str, Any],
    operations: Sequence[Any],
    *,
    actor: str | None = None,
    batch_id: str | None = None,
    base_revision: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Apply one atomic batch of programme operations."""

    if not isinstance(operations, Sequence) or isinstance(operations, (str, bytes)) or not operations:
        raise ToolError("operations must be a non-empty JSON array")
    if base_revision is not None and (type(base_revision) is not int or base_revision < 0):
        raise ToolError("base_revision must be a non-negative integer")
    actor = safe_record_text(actor, "actor", max_chars=256) if actor is not None else None
    batch_id = (
        safe_record_text(batch_id, "batch_id", max_chars=256) if batch_id is not None else None
    )
    if batch_id is not None:
        for entry in programme.get("history", []) or []:
            if isinstance(entry, Mapping) and entry.get("batch_id") == batch_id:
                return {
                    "applied": False,
                    "idempotent": True,
                    "batch_id": batch_id,
                    "revision": programme.get("revision", 0),
                    "operations": int(entry.get("operation_count", 0) or 0),
                }
    if base_revision is not None and int(programme.get("revision", 0) or 0) != base_revision:
        raise ToolError(
            "base_revision mismatch: programme is revision %s, batch expects %s"
            % (programme.get("revision", 0), base_revision)
        )

    working = deepcopy(programme)
    for index, operation in enumerate(operations):
        if not isinstance(operation, Mapping):
            raise ToolError("operation %d must be an object" % index)
        try:
            _apply_operation(working, operation)
        except ToolError as error:
            raise ToolError("operation %d (%s): %s" % (index, operation.get("op"), error))
    issues = validate_programme(working)
    if issues:
        raise ToolError("programme rejected by its invariants: %s" % "; ".join(issues[:6]))

    if dry_run:
        return {
            "applied": False,
            "dry_run": True,
            "batch_id": batch_id,
            "revision": programme.get("revision", 0),
            "next_revision": int(programme.get("revision", 0) or 0) + 1,
            "operations": len(operations),
            "deliveries": [str(item.get("id")) for item in iter_deliveries(working)],
        }

    programme.clear()
    programme.update(working)
    programme["revision"] = int(programme.get("revision", 0) or 0) + 1
    programme["updated_at"] = now()
    append_history(
        programme,
        action="apply",
        batch_id=batch_id,
        actor=actor,
        operations=operations,
    )
    return {
        "applied": True,
        "batch_id": batch_id,
        "revision": programme["revision"],
        "operations": len(operations),
        "deliveries": [str(item.get("id")) for item in iter_deliveries(programme)],
    }


def _requirement_closure(programme: Mapping[str, Any], code: str) -> set[str]:
    """Return every delivery that must land before this one, transitively."""

    deliveries = delivery_index(programme)
    seen: set[str] = set()
    pending = [code]
    while pending:
        current = pending.pop()
        delivery = deliveries.get(current)
        if delivery is None:
            continue
        for requirement in delivery.get("requires") or []:
            if isinstance(requirement, str) and requirement not in seen:
                seen.add(requirement)
                pending.append(requirement)
    return seen


def _delivery_state(delivery: Mapping[str, Any], tree: Mapping[str, Any] | None) -> dict[str, Any]:
    code = str(delivery.get("id"))
    if tree is None:
        return {
            "id": code,
            "title": delivery.get("title"),
            "tree": delivery.get("tree"),
            "state": "missing",
            "nodes": 0,
            "tasks": 0,
            "counts": {},
            "ready_nodes": [],
            "reviewer": None,
            "gate": [],
            "issues": ["no Tree at %s" % delivery.get("tree")],
        }
    issues = validate_tree(tree)
    if issues:
        return {
            "id": code,
            "title": delivery.get("title"),
            "tree": delivery.get("tree"),
            "state": "invalid",
            "nodes": len(iter_nodes(tree)),
            "tasks": len(iter_tasks(tree)),
            "counts": {},
            "ready_nodes": [],
            "reviewer": None,
            "gate": [],
            "issues": issues[:6],
        }
    nodes = node_index(tree)
    counts: dict[str, int] = {}
    for _, node in iter_nodes(tree):
        status = str(node.get("status"))
        counts[status] = counts.get(status, 0) + 1
    reviewer = next(
        (
            str(node.get("id"))
            for _, node in iter_nodes(tree)
            if node.get("role") == "reviewer"
        ),
        None,
    )
    gate = [str(code) for code in (nodes[reviewer].get("after") or [])] if reviewer else []
    return {
        "id": code,
        "title": delivery.get("title") or tree.get("title"),
        "tree": delivery.get("tree"),
        "state": derive_tree_status(tree),
        "nodes": len(iter_nodes(tree)),
        "tasks": len(iter_tasks(tree)),
        "counts": counts,
        "ready_nodes": ready_codes(tree),
        "reviewer": reviewer,
        "gate": gate,
        "issues": [],
        "shape_issues": shape_issues(tree),
    }


def programme_report(
    programme: Mapping[str, Any],
    trees: Mapping[str, Mapping[str, Any] | None],
) -> dict[str, Any]:
    """Derive the whole programme from its Trees, in dependency order."""

    issues = validate_programme(programme)
    states: list[dict[str, Any]] = []
    for code in delivery_order(programme):
        delivery = delivery_index(programme)[code]
        states.append(_delivery_state(delivery, trees.get(code)))
    by_id = {state["id"]: state for state in states}
    for state in states:
        delivery = delivery_index(programme)[state["id"]]
        blocked_by = [
            requirement
            for requirement in (delivery.get("requires") or [])
            if by_id.get(requirement, {}).get("state") != "completed"
        ]
        state["requires"] = list(delivery.get("requires") or [])
        state["blocked_by"] = blocked_by
        # Ready means "may start work now": unblocked and not already finished.
        state["ready"] = not blocked_by and state["state"] not in {
            "missing",
            "invalid",
            "completed",
            "cancelled",
        }
    counts: dict[str, int] = {}
    for state in states:
        counts[state["state"]] = counts.get(state["state"], 0) + 1
    return {
        "id": programme.get("id"),
        "title": programme.get("title"),
        "revision": programme.get("revision", 0),
        "issues": issues,
        "deliveries": states,
        "counts": counts,
        "ready": [state["id"] for state in states if state["ready"]],
        "contention": programme_contention(programme, trees),
    }


def programme_contention(
    programme: Mapping[str, Any],
    trees: Mapping[str, Mapping[str, Any] | None],
) -> list[dict[str, Any]]:
    """Report resources shared by Nodes the programme does not order.

    A Tree's own ``after`` graph orders Nodes inside one delivery; a programme's
    ``requires`` edges order whole deliveries. When neither holds, two Nodes that
    declare the same resource are a design collision — a shared worktree, build
    directory, cache, port, or index — and the report says so instead of leaving it
    for a reviewer to discover at runtime.
    """

    owners: dict[str, list[tuple[str, str]]] = {}
    ordered_within: dict[str, set[frozenset[str]]] = {}
    for delivery in iter_deliveries(programme):
        code = str(delivery.get("id"))
        tree = trees.get(code)
        if not isinstance(tree, Mapping) or validate_tree(tree):
            continue
        ordered_within[code] = ordered_pairs(tree)
        for _, node in iter_nodes(tree):
            node_code = node.get("id")
            if not isinstance(node_code, str):
                continue
            for resource in node_resources(node):
                owners.setdefault(resource, []).append((code, node_code))

    closures = {
        str(delivery.get("id")): _requirement_closure(programme, str(delivery.get("id")))
        for delivery in iter_deliveries(programme)
    }

    def ordered(first: tuple[str, str], second: tuple[str, str]) -> bool:
        first_delivery, first_node = first
        second_delivery, second_node = second
        if first_delivery == second_delivery:
            return frozenset((first_node, second_node)) in ordered_within.get(first_delivery, set())
        return (
            first_delivery in closures.get(second_delivery, set())
            or second_delivery in closures.get(first_delivery, set())
        )

    report: list[dict[str, Any]] = []
    for resource in sorted(owners):
        entries = sorted(set(owners[resource]))
        if len(entries) < 2:
            continue
        unordered = [
            ["%s/%s" % first, "%s/%s" % second]
            for index, first in enumerate(entries)
            for second in entries[index + 1 :]
            if not ordered(first, second)
        ]
        if unordered:
            report.append(
                {
                    "resource": resource,
                    "owners": ["%s/%s" % entry for entry in entries],
                    "unordered": unordered,
                }
            )
    return report


def render_programme(programme: Mapping[str, Any]) -> str:
    lines = ["%s %s" % (programme.get("id"), programme.get("title"))]
    for code in delivery_order(programme):
        delivery = delivery_index(programme)[code]
        requires = ", ".join(delivery.get("requires") or []) or "none"
        lines.append(
            "  %s %s tree=%s requires=%s"
            % (delivery.get("id"), delivery.get("title"), delivery.get("tree"), requires)
        )
    return "\n".join(lines)
