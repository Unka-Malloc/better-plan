"""Current-state model for a long-lived Checkpoints Tree.

The persisted plan is split across ``Tree.json``, ``tasks/*.json`` and
``nodes/*.json``. This module contains graph algorithms and derived views;
filesystem writes and immutable history archives live elsewhere.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Iterable, Mapping
import re

from .models import ToolError


TREE_SCHEMA = "better-plan.checkpoints-tree"
TREE_NAME = "Tree.json"
TASKS_DIRECTORY = "tasks"
NODES_DIRECTORY = "nodes"
HISTORY_DIRECTORY = "history"

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def safe_id(value: Any, field: str = "id") -> str:
    """Return a filename-safe identity used by local plan files."""

    if not isinstance(value, str) or _SAFE_ID.fullmatch(value) is None:
        raise ToolError("%s must use letters, numbers, '.', '_' or '-'" % field)
    return value


def string_list(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ToolError("%s must be an array of strings" % field)
    return list(dict.fromkeys(value))


def new_delivery() -> dict[str, Any]:
    return {"result": None, "review": []}


def delivery_status(container: Mapping[str, Any]) -> str:
    delivery = container.get("delivery") or {}
    if delivery.get("result") is None:
        return "unrecorded"
    return "needs_review" if delivery.get("review") else "recorded"


def execution_status(values: Iterable[str]) -> str:
    statuses = set(values)
    if not statuses or statuses == {"pending"}:
        return "pending"
    if statuses == {"completed"}:
        return "completed"
    if "running" in statuses:
        return "running"
    if "failed" in statuses:
        return "failed"
    if "blocked" in statuses:
        return "blocked"
    if statuses <= {"cancelled", "completed"}:
        return "cancelled"
    return "pending"


def new_tree(tree_id: str, title: str, goal: str = "") -> dict[str, Any]:
    return {
        "schema": TREE_SCHEMA,
        "id": safe_id(tree_id, "tree.id"),
        "title": str(title),
        "goal": str(goal),
        "success": [],
        "architecture": None,
        "delivery_policy": None,
        "requirements": [],
        "open_decisions": [],
        "delivery": new_delivery(),
        "checks": [],
    }


def tree_template() -> dict[str, Any]:
    return new_tree("TREE-001", "Delivery", "Describe the final outcome.")


def new_task(task_id: str, title: str, outcome: str = "") -> dict[str, Any]:
    return {
        "id": safe_id(task_id, "task.id"),
        "title": str(title),
        "outcome": str(outcome),
        "requirements": [],
        "draft_pr": None,
        "integration_owner": None,
        "delivery": new_delivery(),
        "checks": [],
    }


def new_node(
    node_id: str,
    task_id: str,
    title: str,
    outcome: str = "",
    after: Iterable[str] = (),
) -> dict[str, Any]:
    return {
        "id": safe_id(node_id, "node.id"),
        "task": safe_id(task_id, "node.task"),
        "title": str(title),
        "outcome": str(outcome),
        "after": list(dict.fromkeys(safe_id(item, "node.after") for item in after)),
        "status": "pending",
        "role": None,
        "executors": [],
        "resources": [],
        "contract": {},
        "review": [],
        "result": None,
        "commit": None,
        "checks": [],
    }


def normalize_check(value: Mapping[str, Any], owner_kind: str) -> dict[str, Any]:
    """Normalize one check without treating it as a completion gate."""

    check = dict(value)
    check["id"] = safe_id(check.get("id"), "check.id")
    check["title"] = str(check.get("title") or check["id"])
    commands = check.get("commands", [])
    if isinstance(commands, str):
        commands = [commands]
    check["commands"] = string_list(commands, "check.commands")
    coverage = check.get("coverage") or {"kind": owner_kind}
    if not isinstance(coverage, Mapping):
        raise ToolError("check.coverage must be an object")
    coverage = dict(coverage)
    kind = coverage.get("kind")
    if kind not in ("tree", "task", "node", "nodes"):
        raise ToolError("check.coverage.kind must be tree, task, node, or nodes")
    if kind == "nodes":
        coverage["nodes"] = string_list(coverage.get("nodes", []), "check.coverage.nodes")
    else:
        coverage.pop("nodes", None)
    check["coverage"] = coverage
    check["pending"] = bool(check.get("pending", True))
    check["running"] = bool(check.get("running", False))
    check["run_id"] = check.get("run_id")
    check["dirty"] = bool(check.get("dirty", False))
    check["result"] = check.get("result")
    return check


def adjacency(nodes: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Build forward and reverse adjacency once for O(V + E) traversals."""

    forward = {code: [] for code in nodes}
    reverse = {code: [] for code in nodes}
    for code, node in nodes.items():
        for dependency in dict.fromkeys(node.get("after") or []):
            if dependency in nodes:
                forward[dependency].append(code)
                reverse[code].append(dependency)
    return forward, reverse


def descendants(
    nodes: Mapping[str, Mapping[str, Any]], seeds: Iterable[str], include_seeds: bool = True
) -> list[str]:
    forward, _ = adjacency(nodes)
    seed_list = [code for code in dict.fromkeys(seeds) if code in nodes]
    queue = deque(seed_list)
    seen = set(seed_list)
    ordered = list(seed_list) if include_seeds else []
    while queue:
        current = queue.popleft()
        for child in forward[current]:
            if child in seen:
                continue
            seen.add(child)
            ordered.append(child)
            queue.append(child)
    return ordered


def dependency_closure(nodes: Mapping[str, Mapping[str, Any]], seeds: Iterable[str]) -> list[str]:
    _, reverse = adjacency(nodes)
    queue = deque(code for code in dict.fromkeys(seeds) if code in nodes)
    seen = set(queue)
    ordered: list[str] = []
    while queue:
        current = queue.popleft()
        for dependency in reverse[current]:
            if dependency in seen:
                continue
            seen.add(dependency)
            ordered.append(dependency)
            queue.append(dependency)
    return ordered


def cycle(nodes: Mapping[str, Mapping[str, Any]]) -> list[str]:
    """Return the nodes involved in a cycle, or an empty list."""

    forward, _ = adjacency(nodes)
    indegree = {code: 0 for code in nodes}
    for children in forward.values():
        for child in children:
            indegree[child] += 1
    queue = deque(code for code, degree in indegree.items() if degree == 0)
    visited = 0
    while queue:
        current = queue.popleft()
        visited += 1
        for child in forward[current]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    return [] if visited == len(nodes) else sorted(code for code, degree in indegree.items() if degree)


def task_nodes(nodes: Mapping[str, Mapping[str, Any]], task_id: str) -> list[str]:
    return [code for code, node in nodes.items() if node.get("task") == task_id]


def task_status(nodes: Mapping[str, Mapping[str, Any]], task_id: str) -> str:
    return execution_status(nodes[code].get("status", "pending") for code in task_nodes(nodes, task_id))


def tree_status(nodes: Mapping[str, Mapping[str, Any]]) -> str:
    return execution_status(node.get("status", "pending") for node in nodes.values())


def blockers(nodes: Mapping[str, Mapping[str, Any]]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for code, node in nodes.items():
        waiting = [
            dependency
            for dependency in node.get("after") or []
            if dependency not in nodes or nodes[dependency].get("status") != "completed"
        ]
        if waiting:
            result[code] = waiting
    return result


def ready_nodes(nodes: Mapping[str, Mapping[str, Any]]) -> list[str]:
    waiting = blockers(nodes)
    return [
        code
        for code, node in nodes.items()
        if node.get("status", "pending") == "pending" and code not in waiting
    ]


def _reachable_set(forward: Mapping[str, list[str]], start: str) -> set[str]:
    queue = deque([start])
    seen = {start}
    while queue:
        current = queue.popleft()
        for child in forward.get(current, []):
            if child not in seen:
                seen.add(child)
                queue.append(child)
    seen.discard(start)
    return seen


def contention(nodes: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    owners: dict[str, list[str]] = {}
    for code, node in nodes.items():
        for resource in node.get("resources") or []:
            owners.setdefault(str(resource), []).append(code)
    forward, _ = adjacency(nodes)
    reachable: dict[str, set[str]] = {}
    result: list[dict[str, Any]] = []
    for resource, codes in sorted(owners.items()):
        unordered: list[list[str]] = []
        ordered_codes = sorted(dict.fromkeys(codes))
        for index, first in enumerate(ordered_codes):
            for second in ordered_codes[index + 1 :]:
                if first not in reachable:
                    reachable[first] = _reachable_set(forward, first)
                if second not in reachable:
                    reachable[second] = _reachable_set(forward, second)
                if second not in reachable[first] and first not in reachable[second]:
                    unordered.append([first, second])
        if unordered:
            result.append({"resource": resource, "owners": ordered_codes, "unordered": unordered})
    return result


def add_review(
    nodes: Mapping[str, dict[str, Any]], targets: Iterable[str], source_kind: str, source_id: str, reason: str
) -> list[str]:
    source = {"kind": source_kind, "id": source_id}
    changed: list[str] = []
    for code in targets:
        node = nodes.get(code)
        if node is None:
            continue
        review = list(node.get("review") or [])
        replacement = {"source": source, "reason": reason}
        found = False
        for index, item in enumerate(review):
            if item.get("source") == source:
                review[index] = replacement
                found = True
                break
        if not found:
            review.append(replacement)
        if review != node.get("review"):
            node["review"] = review
            changed.append(code)
    return changed


def clear_review(node: dict[str, Any], source_kind: str | None = None, source_id: str | None = None) -> int:
    review = list(node.get("review") or [])
    if source_kind is None and source_id is None:
        node["review"] = []
        return len(review)
    kept = []
    for item in review:
        source = item.get("source") or {}
        matches = (source_kind is None or source.get("kind") == source_kind) and (
            source_id is None or source.get("id") == source_id
        )
        if not matches:
            kept.append(item)
    node["review"] = kept
    return len(review) - len(kept)


def check_coverage(
    check: Mapping[str, Any], owner_kind: str, owner_id: str, nodes: Mapping[str, Mapping[str, Any]]
) -> list[str]:
    coverage = check.get("coverage") or {"kind": owner_kind}
    kind = coverage.get("kind")
    if kind == "tree":
        return list(nodes)
    if kind == "task":
        task_id = owner_id if owner_kind == "task" else str(coverage.get("task") or owner_id)
        return task_nodes(nodes, task_id)
    if kind == "node":
        node_id = owner_id if owner_kind == "node" else str(coverage.get("node") or owner_id)
        return [node_id] if node_id in nodes else []
    return [code for code in coverage.get("nodes") or [] if code in nodes]


def iter_checks(
    tree: Mapping[str, Any], tasks: Mapping[str, Mapping[str, Any]], nodes: Mapping[str, Mapping[str, Any]]
):
    for check in tree.get("checks") or []:
        yield "tree", str(tree.get("id")), check
    for task_id, task in tasks.items():
        for check in task.get("checks") or []:
            yield "task", task_id, check
    for node_id, node in nodes.items():
        for check in node.get("checks") or []:
            yield "node", node_id, check


def flattened_checks(
    tree: Mapping[str, Any], tasks: Mapping[str, Mapping[str, Any]], nodes: Mapping[str, Mapping[str, Any]]
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for owner_kind, owner_id, check in iter_checks(tree, tasks, nodes):
        covers = check_coverage(check, owner_kind, owner_id, nodes)
        result.append(
            {
                "id": check.get("id"),
                "title": check.get("title"),
                "commands": list(check.get("commands") or []),
                "owner": {"kind": owner_kind, "id": owner_id},
                "covers": covers,
                "pending": bool(check.get("pending", True)),
                "running": bool(check.get("running", False)),
                "dirty": bool(check.get("dirty", False)),
                "interrupted": bool(check.get("interrupted", False)),
                "ready": bool(covers) and all(nodes[code].get("status") == "completed" for code in covers),
                "result": check.get("result"),
            }
        )
    return result


def mark_checks_pending(
    tree: dict[str, Any],
    tasks: Mapping[str, dict[str, Any]],
    nodes: Mapping[str, dict[str, Any]],
    affected: Iterable[str],
) -> set[tuple[str, str]]:
    affected_set = set(affected)
    changed: set[tuple[str, str]] = set()
    for owner_kind, owner_id, check in iter_checks(tree, tasks, nodes):
        if not affected_set.intersection(check_coverage(check, owner_kind, owner_id, nodes)):
            continue
        before = (bool(check.get("pending")), bool(check.get("dirty")))
        check["pending"] = True
        if check.get("running"):
            check["dirty"] = True
        if before != (bool(check.get("pending")), bool(check.get("dirty"))):
            changed.add((owner_kind, owner_id))
    return changed


def derived_state(
    tree: Mapping[str, Any], tasks: Mapping[str, Mapping[str, Any]], nodes: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    counts: dict[str, int] = {}
    role_nodes: dict[str, list[str]] = {}
    review_nodes: list[str] = []
    task_review_nodes: dict[str, list[str]] = {}
    grouped = {task_id: [] for task_id in tasks}
    for code, node in nodes.items():
        status = str(node.get("status", "pending"))
        counts[status] = counts.get(status, 0) + 1
        role = node.get("role")
        if role:
            role_nodes.setdefault(str(role), []).append(code)
        if node.get("review"):
            review_nodes.append(code)
            task_review_nodes.setdefault(str(node.get("task")), []).append(code)
        grouped.setdefault(str(node.get("task")), []).append(status)
    task_states = {}
    for task_id in tasks:
        values = grouped.get(task_id, [])
        task_states[task_id] = execution_status(values)
    task_deliveries = {code: delivery_status(task) for code, task in tasks.items()}
    unconfirmed = [code for code, state in task_deliveries.items() if state != "recorded"]
    tree_delivery = delivery_status(tree)
    if tree_delivery == "recorded" and unconfirmed:
        tree_delivery = "needs_review"
    return {
        "status": tree_status(nodes),
        "delivery_status": tree_delivery,
        "task_delivery_status": task_deliveries,
        "unconfirmed_tasks": unconfirmed,
        "ready": ready_nodes(nodes),
        "node_counts": counts,
        "task_status": task_states,
        "role_nodes": role_nodes,
        "contention": contention(nodes),
        "review_nodes": review_nodes,
        "task_review_nodes": task_review_nodes,
        "blockers": blockers(nodes),
    }


def export_payload(
    tree: Mapping[str, Any], tasks: Mapping[str, Mapping[str, Any]], nodes: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    assembled = dict(tree)
    assembled["tasks"] = []
    grouped = {task_id: [] for task_id in tasks}
    for code, node in nodes.items():
        grouped.setdefault(str(node.get("task")), []).append(dict(node))
    for task_id, task in tasks.items():
        item = dict(task)
        item["nodes"] = grouped.get(task_id, [])
        assembled["tasks"].append(item)
    return {
        "tree": assembled,
        "derived": derived_state(tree, tasks, nodes),
        "checks": flattened_checks(tree, tasks, nodes),
    }
