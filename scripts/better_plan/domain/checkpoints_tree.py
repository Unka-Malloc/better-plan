"""Canonical agent-neutral Checkpoints Tree.

The canonical structure is deliberately small and universal:

    Tree
    └─ tasks[]
       └─ nodes[]
          └─ after[]       dependency edges to Node ids

Only executable Nodes carry execution state.  Task and Tree status are derived
views computed from Node state, never stored.  Every Task and Node may carry an
opaque ``contract`` object; the Tree may carry an opaque ``meta`` object.  The
tool never interprets either object.

Nothing in this module selects, validates, or pins a host, agent, model,
provider, role, vendor, or execution capacity.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
import json
import re

from .models import ToolError, safe_summary_issue


TREE_SCHEMA = "better-plan.checkpoints-tree"
TREE_NAME = "Tree.json"

NODE_STATUSES = (
    "pending",
    "running",
    "completed",
    "failed",
    "blocked",
    "cancelled",
)
TASK_STATUSES = (
    "pending",
    "ready",
    "running",
    "completed",
    "failed",
    "blocked",
    "cancelled",
)
TREE_STATUSES = TASK_STATUSES
TRANSITION_ACTIONS = ("start", "complete", "fail", "block", "cancel", "reset")

# Where completion evidence came from. `cli` means the tool executed the Node's
# declared commands and produced the receipts itself; `reported` means a caller
# asserted the outcome. Only `cli` can complete a Node that declares commands.
EVIDENCE_ORIGINS = ("cli", "reported")
# The single `contract` key the tool interprets. Every other contract value stays
# opaque project data that the Tree stores without reading.
NODE_COMMANDS_KEY = "commands"
# A delivery is one graph with a fixed outside and a free inside: exactly one
# `designer` Node starts it, exactly one `reviewer` Node ends it, and every Node
# between them runs on a worker. A worker name is a role slot, not a person: the
# Tree names `worker` or `worker-<n>`, and a host binds that slot to whatever
# executor and model it has. There is no ceiling on how many worker slots a
# delivery uses, and no second kind of worker.
DESIGNER_ROLE = "designer"
REVIEWER_ROLE = "reviewer"
WORKER_ROLE = "worker"
_WORKER_SLOT = re.compile(r"^worker(-\d+)?$")


def is_worker_role(value: Any) -> bool:
    return isinstance(value, str) and _WORKER_SLOT.fullmatch(value) is not None


def is_delivery_role(value: Any) -> bool:
    return value in (DESIGNER_ROLE, REVIEWER_ROLE) or is_worker_role(value)


# Resources are what a Node contends on: a file tree, a build directory, a cache,
# a version-control index, a port, a device. The tool never resolves or reserves
# one; it stores the names and reports Nodes that share a resource without an
# ordering path between them, because that is the design decision principle 10
# asks the Designer to make and nothing else can check.
NODE_RESOURCE_CHARACTERS = 256

OPERATION_KINDS = (
    "tree.update",
    "task.add",
    "task.update",
    "task.remove",
    "node.add",
    "node.update",
    "node.move",
    "node.remove",
    "after.add",
    "after.remove",
)

_TREE_FIELDS = frozenset(
    {"schema", "id", "title", "generation", "tasks", "meta", "history", "created_at", "updated_at"}
)
_TASK_FIELDS = frozenset({"id", "title", "outcome", "contract", "nodes"})
_NODE_FIELDS = frozenset(
    {
        "id",
        "title",
        "outcome",
        "role",
        "executors",
        "resources",
        "after",
        "status",
        "executor",
        "attempts",
        "evidence",
        "contract",
    }
)
_TASK_UPDATE_FIELDS = frozenset({"title", "outcome", "contract"})
_NODE_UPDATE_FIELDS = frozenset(
    {"title", "outcome", "role", "executors", "resources", "after", "contract"}
)

_ID_PATTERN = re.compile(r"^[^\x00]{1,256}$")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_text(value: Any, field: str, *, max_chars: int = 4000) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ToolError("%s must be a non-empty string" % field)
    if "\x00" in value or len(value) > max_chars:
        raise ToolError("%s is invalid or too long" % field)
    return value.strip()


def safe_record_text(value: Any, field: str, *, max_chars: int = 4000) -> str:
    """Return text the tool may store, or refuse it with the failing rule.

    Everything the Tree records as its own structured data — ids, titles,
    outcomes, roles, executors, notes, evidence, history — passes the same privacy
    guard the diagnostics use, so a secret, an absolute local path, or an endpoint
    never reaches stored state. Only ``contract`` and ``meta`` stay opaque project
    data, deliberately unread (rule 7).
    """

    text = _safe_text(value, field, max_chars=max_chars)
    issue = safe_summary_issue(text, max_chars=max_chars)
    if issue is not None:
        raise ToolError("%s %s" % (field, issue))
    return text


EVIDENCE_TEXT_CHARACTERS = 2000


def _safe_evidence(value: Any, field: str, *, depth: int = 0) -> Any:
    """Return evidence whose every string is safe to store, or refuse it."""

    if depth > 8:
        raise ToolError("%s is nested too deeply" % field)
    if isinstance(value, str):
        return safe_record_text(value, field, max_chars=EVIDENCE_TEXT_CHARACTERS)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, Mapping):
        guarded: dict[str, Any] = {}
        for key, item in value.items():
            key_text = safe_record_text(key, "%s key" % field, max_chars=256)
            guarded[key_text] = _safe_evidence(
                item, "%s.%s" % (field, key_text), depth=depth + 1
            )
        return guarded
    if isinstance(value, list):
        return [
            _safe_evidence(item, "%s[%d]" % (field, index), depth=depth + 1)
            for index, item in enumerate(value)
        ]
    raise ToolError("%s must be JSON data" % field)


def safe_id(value: Any, field: str = "id") -> str:
    text = safe_record_text(value, field, max_chars=256)
    if _ID_PATTERN.fullmatch(text) is None:
        raise ToolError("%s must be a safe opaque id" % field)
    return text


def safe_object(value: Any, field: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ToolError("%s must be an object" % field)
    return deepcopy(dict(value))


def _unknown_fields(value: Mapping[str, Any], allowed: frozenset[str], field: str) -> list[str]:
    unknown = sorted(set(value) - allowed)
    return ["%s has unknown field(s): %s" % (field, ", ".join(unknown))] if unknown else []


def new_tree(tree_id: str, title: str) -> dict[str, Any]:
    tree_id = safe_id(tree_id, "tree.id")
    title = safe_record_text(title, "tree.title", max_chars=500)
    stamp = now()
    return {
        "schema": TREE_SCHEMA,
        "id": tree_id,
        "title": title,
        "generation": 0,
        "tasks": [],
        "meta": {},
        "history": [],
        "created_at": stamp,
        "updated_at": stamp,
    }


def tree_template() -> dict[str, Any]:
    return {
        "schema": TREE_SCHEMA,
        "id": "TREE-001",
        "title": "Delivery tree",
        "generation": 0,
        "tasks": [],
        "meta": {},
        "history": [],
        "created_at": "timestamp",
        "updated_at": "timestamp",
    }


def iter_tasks(tree: Mapping[str, Any]) -> list[dict[str, Any]]:
    tasks = tree.get("tasks")
    if not isinstance(tasks, list):
        return []
    return [task for task in tasks if isinstance(task, dict)]


def iter_nodes(tree: Mapping[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    result: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for task in iter_tasks(tree):
        nodes = task.get("nodes")
        if not isinstance(nodes, list):
            continue
        for node in nodes:
            if isinstance(node, dict):
                result.append((task, node))
    return result


def node_index(tree: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for _, node in iter_nodes(tree):
        code = node.get("id")
        if isinstance(code, str) and code not in result:
            result[code] = node
    return result


def task_index(tree: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for task in iter_tasks(tree):
        code = task.get("id")
        if isinstance(code, str) and code not in result:
            result[code] = task
    return result


def _task_of_node(tree: Mapping[str, Any], node_code: str) -> dict[str, Any] | None:
    for task, node in iter_nodes(tree):
        if node.get("id") == node_code:
            return task
    return None


def _node_task_id(tree: Mapping[str, Any], node_code: str) -> str | None:
    task = _task_of_node(tree, node_code)
    return str(task.get("id")) if isinstance(task, Mapping) and isinstance(task.get("id"), str) else None


def _node_after(node: Mapping[str, Any]) -> list[str]:
    after = node.get("after")
    if not isinstance(after, list):
        return []
    return [item for item in after if isinstance(item, str)]


def node_commands(node: Mapping[str, Any]) -> list[str]:
    """Return the verification commands a Node declares in its contract.

    `contract.commands` is the one interpreted contract key. A Node that declares
    commands cannot be completed on its author's word: only the tool may run them
    and record what happened.
    """

    contract = node.get("contract")
    if not isinstance(contract, Mapping):
        return []
    commands = contract.get(NODE_COMMANDS_KEY)
    if not isinstance(commands, list):
        return []
    return [item for item in commands if isinstance(item, str) and item.strip()]


def _node_can_start(tree: Mapping[str, Any], node: Mapping[str, Any]) -> bool:
    nodes = node_index(tree)
    if node.get("status") not in {"pending", "failed", "blocked"}:
        return False
    for prerequisite in _node_after(node):
        if not isinstance(nodes.get(prerequisite), Mapping):
            return False
        if nodes[prerequisite].get("status") != "completed":
            return False
    return True


def ready_codes(tree: Mapping[str, Any]) -> list[str]:
    """Return executable Node ids that can start now.

    A Node is startable when it is pending/failed/blocked and every id in its
    ``after`` list is completed.  No host, model, role, provider, or capacity
    condition participates.
    """

    return sorted(node.get("id") for _, node in iter_nodes(tree) if _node_can_start(tree, node))


def derive_task_status(tree: Mapping[str, Any], task: Mapping[str, Any]) -> str:
    nodes = [
        node
        for node in task.get("nodes", []) or []
        if isinstance(node, Mapping)
    ]
    if not nodes:
        return "pending"
    statuses = [str(node.get("status")) for node in nodes]
    if all(status == "completed" for status in statuses):
        return "completed"
    if any(status == "failed" for status in statuses):
        return "failed"
    if any(status == "blocked" for status in statuses):
        return "blocked"
    if all(status == "cancelled" for status in statuses):
        return "cancelled"
    if any(status == "running" for status in statuses):
        return "running"
    if any(status == "completed" for status in statuses):
        return "running"
    if any(_node_can_start(tree, node) for node in nodes):
        return "ready"
    return "pending"


def derive_tree_status(tree: Mapping[str, Any]) -> str:
    tasks = iter_tasks(tree)
    if not tasks:
        return "pending"
    statuses = [derive_task_status(tree, task) for task in tasks]
    if all(status == "completed" for status in statuses):
        return "completed"
    if any(status == "failed" for status in statuses):
        return "failed"
    if any(status == "blocked" for status in statuses):
        return "blocked"
    if all(status == "cancelled" for status in statuses):
        return "cancelled"
    if any(status in {"running", "completed"} for status in statuses):
        return "running"
    if any(status == "ready" for status in statuses):
        return "ready"
    return "pending"


def _downstream_ids(tree: Mapping[str, Any], start_id: str) -> set[str]:
    """Return the Node plus every Node that transitively waits on it."""

    affected = {start_id}
    changed = True
    while changed:
        changed = False
        for _, node in iter_nodes(tree):
            code = node.get("id")
            if not isinstance(code, str) or code in affected:
                continue
            if any(item in affected for item in _node_after(node)):
                affected.add(code)
                changed = True
    return affected


def _reset_nodes(tree: Mapping[str, Any], codes: set[str], status: str = "pending") -> None:
    nodes = node_index(tree)
    for code in codes:
        node = nodes.get(code)
        if isinstance(node, dict):
            node["status"] = status
            node["executor"] = None


def _detach_after(tree: Mapping[str, Any], removed_ids: set[str]) -> None:
    for _, node in iter_nodes(tree):
        after = node.get("after")
        if isinstance(after, list):
            node["after"] = [item for item in after if item not in removed_ids]


def validate_tree(tree: Mapping[str, Any]) -> list[str]:
    """Validate exactly the canonical nested Checkpoints Tree shape.

    Unknown fields are rejected.  Extensible project data belongs in the opaque
    ``contract`` or ``meta`` objects, not in new structural fields.
    """

    issues: list[str] = []
    if not isinstance(tree, Mapping):
        return ["tree must be an object"]
    issues.extend(_unknown_fields(tree, _TREE_FIELDS, "tree"))
    if tree.get("schema") != TREE_SCHEMA:
        issues.append("tree.schema must be %s" % TREE_SCHEMA)
    if not isinstance(tree.get("id"), str) or _ID_PATTERN.fullmatch(str(tree.get("id"))) is None:
        issues.append("tree.id must be a safe non-empty id")
    if not isinstance(tree.get("title"), str) or not str(tree.get("title")).strip():
        issues.append("tree.title must be non-empty text")
    if type(tree.get("generation")) is not int or tree.get("generation") < 0:
        issues.append("tree.generation must be a non-negative integer")
    for field in ("created_at", "updated_at"):
        if not isinstance(tree.get(field), str) or not str(tree.get(field)).strip():
            issues.append("tree.%s must be a timestamp string" % field)
    if not isinstance(tree.get("meta"), Mapping):
        issues.append("tree.meta must be an object")
    if not isinstance(tree.get("history"), list):
        issues.append("tree.history must be an array")
    tasks = tree.get("tasks")
    if not isinstance(tasks, list):
        return issues + ["tree.tasks must be an array"]

    seen_ids: set[str] = set()
    node_ids: set[str] = set()
    for task_index_value, task in enumerate(tasks):
        prefix = "tasks[%d]" % task_index_value
        if not isinstance(task, Mapping):
            issues.append("%s must be an object" % prefix)
            continue
        issues.extend(_unknown_fields(task, _TASK_FIELDS, prefix))
        task_id = task.get("id")
        if not isinstance(task_id, str) or _ID_PATTERN.fullmatch(task_id) is None:
            issues.append("%s.id must be a safe non-empty id" % prefix)
        elif task_id in seen_ids:
            issues.append("%s.id is duplicate: %s" % (prefix, task_id))
        else:
            seen_ids.add(task_id)
        for field in ("title", "outcome"):
            if not isinstance(task.get(field), str) or not str(task.get(field)).strip():
                issues.append("%s.%s must be non-empty text" % (prefix, field))
        if not isinstance(task.get("contract"), Mapping):
            issues.append("%s.contract must be an object" % prefix)
        elif NODE_COMMANDS_KEY in task["contract"]:
            issues.append(
                "%s.contract must not declare %s; only a Node owns executable verification"
                % (prefix, NODE_COMMANDS_KEY)
            )
        nodes = task.get("nodes")
        if not isinstance(nodes, list) or not nodes:
            issues.append("%s.nodes must be a non-empty array" % prefix)
            continue
        for node_index_value, node in enumerate(nodes):
            node_prefix = "%s.nodes[%d]" % (prefix, node_index_value)
            if not isinstance(node, Mapping):
                issues.append("%s must be an object" % node_prefix)
                continue
            issues.extend(_unknown_fields(node, _NODE_FIELDS, node_prefix))
            node_id = node.get("id")
            if not isinstance(node_id, str) or _ID_PATTERN.fullmatch(node_id) is None:
                issues.append("%s.id must be a safe non-empty id" % node_prefix)
            elif node_id in seen_ids:
                issues.append("%s.id is duplicate: %s" % (node_prefix, node_id))
            else:
                seen_ids.add(node_id)
                node_ids.add(node_id)
            for field in ("title", "outcome"):
                if not isinstance(node.get(field), str) or not str(node.get(field)).strip():
                    issues.append("%s.%s must be non-empty text" % (node_prefix, field))
            if not is_delivery_role(node.get("role")):
                issues.append(
                    "%s.role must be 'designer', 'reviewer', or a worker slot such as 'worker' or "
                    "'worker-1'" % node_prefix
                )
            executors = node.get("executors")
            if executors is not None and (
                not isinstance(executors, list)
                or any(
                    not isinstance(item, str)
                    or not item.strip()
                    or len(item) > 256
                    or "\x00" in item
                    for item in executors
                )
                or len(set(executors)) != len(executors)
            ):
                issues.append(
                    "%s.executors must be an array of unique, non-empty executor names" % node_prefix
                )
            resources = node.get("resources")
            if resources is not None and (
                not isinstance(resources, list)
                or any(
                    not isinstance(item, str)
                    or not item.strip()
                    or len(item) > NODE_RESOURCE_CHARACTERS
                    or "\x00" in item
                    for item in resources
                )
                or len(set(resources)) != len(resources)
            ):
                issues.append(
                    "%s.resources must be an array of unique, non-empty resource names"
                    % node_prefix
                )
            after = node.get("after")
            if not isinstance(after, list) or any(not isinstance(item, str) for item in after):
                issues.append("%s.after must be an array of Node ids" % node_prefix)
            elif len(set(after)) != len(after):
                issues.append("%s.after must not repeat" % node_prefix)
            status = node.get("status")
            if status not in NODE_STATUSES:
                issues.append("%s.status is invalid" % node_prefix)
            executor = node.get("executor")
            if executor is not None and (
                not isinstance(executor, str) or len(executor) > 256 or "\x00" in executor
            ):
                issues.append("%s.executor must be null or an opaque string" % node_prefix)
            if type(node.get("attempts")) is not int or node.get("attempts") < 0:
                issues.append("%s.attempts must be a non-negative integer" % node_prefix)
            if not isinstance(node.get("evidence"), list):
                issues.append("%s.evidence must be an array" % node_prefix)
            if not isinstance(node.get("contract"), Mapping):
                issues.append("%s.contract must be an object" % node_prefix)
            else:
                commands = node["contract"].get(NODE_COMMANDS_KEY)
                if commands is not None and (
                    not isinstance(commands, list)
                    or not commands
                    or any(not isinstance(item, str) or not item.strip() for item in commands)
                ):
                    issues.append(
                        "%s.contract.%s must be a non-empty array of commands"
                        % (node_prefix, NODE_COMMANDS_KEY)
                    )

    # Dependency-reference integrity and cycle detection.
    for task in tasks:
        if not isinstance(task, Mapping):
            continue
        for node in task.get("nodes", []) or []:
            if not isinstance(node, Mapping):
                continue
            code = node.get("id")
            after = node.get("after")
            if not isinstance(after, list):
                continue
            for dependency in after:
                if not isinstance(dependency, str):
                    continue
                if dependency == code:
                    issues.append("%s.after cannot reference itself" % code)
                elif dependency not in node_ids:
                    issues.append("%s.after references unknown Node %s" % (code, dependency))

    graph = {
        str(node.get("id")): [item for item in _node_after(node) if item in node_ids]
        for _, node in iter_nodes(tree)
        if isinstance(node.get("id"), str)
    }
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def visit(code: str) -> list[str] | None:
        if code in visiting:
            return stack[stack.index(code):] + [code]
        if code in visited:
            return None
        visiting.add(code)
        stack.append(code)
        for prerequisite in graph.get(code, []):
            cycle = visit(prerequisite)
            if cycle is not None:
                return cycle
        stack.pop()
        visiting.remove(code)
        visited.add(code)
        return None

    for code in graph:
        cycle = visit(code)
        if cycle is not None:
            issues.append("after cycle: %s" % " -> ".join(cycle))
            break
    return issues


def shape_issues(tree: Mapping[str, Any]) -> list[str]:
    """Report why this delivery is not runnable yet.

    Authoring stays free: a half-built Tree is still valid data. These are the
    checks that decide whether the graph may start running — one designer Node
    opens it, one reviewer Node closes it, workers fill the middle.
    """

    issues: list[str] = []
    nodes = node_index(tree)
    designers = [
        str(node.get("id")) for _, node in iter_nodes(tree) if node.get("role") == DESIGNER_ROLE
    ]
    reviewers = [
        str(node.get("id")) for _, node in iter_nodes(tree) if node.get("role") == REVIEWER_ROLE
    ]
    if len(designers) != 1:
        issues.append("needs exactly one designer Node, found %d" % len(designers))
    for code in designers:
        if _node_after(nodes.get(code, {})):
            issues.append("the designer Node %s must open the tree and wait for nothing" % code)
    if len(reviewers) != 1:
        issues.append("needs exactly one reviewer Node, found %d" % len(reviewers))
    for code in reviewers:
        waited_on = sorted(
            str(node.get("id")) for _, node in iter_nodes(tree) if code in _node_after(node)
        )
        if waited_on:
            issues.append(
                "the reviewer Node %s must close the tree; %s wait for it"
                % (code, ", ".join(waited_on))
            )
    return issues


def append_history(
    tree: dict[str, Any],
    *,
    action: str,
    node: str | None = None,
    from_status: str | None = None,
    to_status: str | None = None,
    executor: str | None = None,
    note: str | None = None,
    batch_id: str | None = None,
    actor: str | None = None,
    operations: Sequence[Any] | None = None,
    source: str | None = None,
    details: Mapping[str, Any] | None = None,
) -> None:
    history = tree.setdefault("history", [])
    entry: dict[str, Any] = {
        "seq": len(history) + 1,
        "at": now(),
        "action": action,
    }
    if details:
        # A caller may add context; it may never rewrite the record's identity.
        entry.update(
            {
                key: deepcopy(value)
                for key, value in details.items()
                if key not in {"seq", "at", "action", "node"}
            }
        )
    if node is not None:
        entry.update({"node": node, "from": from_status, "to": to_status, "executor": executor})
    if source is not None:
        entry["source"] = source
    if note is not None:
        entry["note"] = note
    if batch_id is not None:
        entry["batch_id"] = batch_id
    if actor is not None:
        entry["actor"] = actor
    if operations is not None:
        entry["operations"] = deepcopy(list(operations))
        entry["operation_count"] = len(operations)
    history.append(entry)


def _normalized_evidence(evidence: Any) -> list[Any]:
    if evidence is None:
        return []
    values = evidence if isinstance(evidence, list) else [evidence]
    return [_safe_evidence(value, "evidence") for value in values]


def node_executors(node: Mapping[str, Any]) -> list[str]:
    """Return the ordered executor list a Node declares, best candidate first.

    An executor is whatever your host can run: a provider and model pair, a named
    profile, an account. The tool never consults a registry or a quota; it stores the
    order, records which candidate was tried, and names the next one.
    """

    values = node.get("executors")
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, str) and item.strip()]


def node_resources(node: Mapping[str, Any]) -> list[str]:
    """Return the resources a Node declares it contends on."""

    values = node.get("resources")
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, str) and item.strip()]


def ordered_pairs(tree: Mapping[str, Any]) -> set[frozenset[str]]:
    """Return every Node pair this Tree orders through `after`, directly or not."""

    nodes = node_index(tree)
    ordered: set[frozenset[str]] = set()
    for code in nodes:
        downstream = _downstream_ids(tree, code) - {code}
        ordered.update(frozenset((code, other)) for other in downstream if other in nodes)
    return ordered


def shared_resource_groups(tree: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Report resources that unordered Nodes declare together.

    A shared resource is not an error: two Nodes may read the same input, and a
    Designer may deliberately serialize them instead. The report exists because
    principle 10 makes contention part of the design, and only the graph can show
    whether the design actually ordered it.
    """

    by_resource: dict[str, list[str]] = {}
    for _, node in iter_nodes(tree):
        code = node.get("id")
        if not isinstance(code, str):
            continue
        for resource in node_resources(node):
            by_resource.setdefault(resource, []).append(code)
    ordered = ordered_pairs(tree)
    groups: list[dict[str, Any]] = []
    for resource in sorted(by_resource):
        codes = sorted(set(by_resource[resource]))
        if len(codes) < 2:
            continue
        unordered = [
            [first, second]
            for index, first in enumerate(codes)
            for second in codes[index + 1 :]
            if frozenset((first, second)) not in ordered
        ]
        if unordered:
            groups.append({"resource": resource, "nodes": codes, "unordered": unordered})
    return groups


def tried_executors(tree: Mapping[str, Any], node_id: str) -> list[str]:
    """Return the executors this Node has already started under, oldest first."""

    tried: list[str] = []
    for entry in tree.get("history", []) or []:
        if (
            isinstance(entry, Mapping)
            and entry.get("node") == node_id
            and entry.get("action") == "start"
            and isinstance(entry.get("executor"), str)
            and entry["executor"].strip()
        ):
            if entry["executor"] not in tried:
                tried.append(str(entry["executor"]))
    return tried


def next_executor(tree: Mapping[str, Any], node: Mapping[str, Any]) -> str | None:
    """Return the first declared executor this Node has not tried yet.

    ``None`` means either the Node declares no chain, or every candidate in it has
    already been tried — the caller decides what to do about that.
    """

    tried = tried_executors(tree, str(node.get("id")))
    for candidate in node_executors(node):
        if candidate not in tried:
            return candidate
    return None


def _start_node(
    tree: Mapping[str, Any], node: dict[str, Any], node_id: str, executor: str | None
) -> None:
    """Move one Node to running, or explain exactly what it is waiting for."""

    blocking = shape_issues(tree)
    if blocking:
        raise ToolError("this delivery is not runnable yet: %s" % "; ".join(blocking[:3]))
    if not _node_can_start(tree, node):
        blockers = [
            item
            for item in _node_after(node)
            if node_index(tree).get(item, {}).get("status") != "completed"
        ]
        raise ToolError(
            "Node %s cannot start from %s%s"
            % (
                node_id,
                node.get("status"),
                " (waiting on %s)" % ", ".join(blockers) if blockers else "",
            )
        )
    node["status"] = "running"
    node["attempts"] = int(node.get("attempts", 0) or 0) + 1
    if executor is not None:
        node["executor"] = executor


def transition(
    tree: dict[str, Any],
    node_id: str,
    action: str,
    *,
    executor: str | None = None,
    evidence: Any = None,
    note: str | None = None,
    origin: str = "reported",
) -> dict[str, Any]:
    """Apply one execution-state transition to one executable Node.

    ``origin`` is tool-owned rather than caller-supplied: the CLI surface never
    lets a caller claim evidence the tool did not produce.
    """

    if action not in TRANSITION_ACTIONS:
        raise ToolError("unknown tree action: %s" % action)
    if origin not in EVIDENCE_ORIGINS:
        raise ToolError("unknown evidence origin: %s" % origin)
    nodes = node_index(tree)
    node = nodes.get(node_id)
    if not isinstance(node, dict):
        raise ToolError("unknown tree node: %s" % node_id)
    executor = (
        safe_record_text(executor, "executor", max_chars=256) if executor is not None else None
    )
    note = safe_record_text(note, "note", max_chars=4000) if note is not None else None
    # Every caller-supplied value is validated before the Node changes, so a refused
    # transition leaves the Tree exactly as it was.
    guarded_evidence = _normalized_evidence(evidence)
    before = str(node.get("status"))

    if action == "start":
        _start_node(tree, node, node_id, executor)
        affected = {node_id}
    elif action == "complete":
        if node.get("status") != "running":
            if node_commands(node):
                raise ToolError(
                    "Node %s is not running; finish a Node that declares contract.%s with "
                    "`tree-verify`" % (node_id, NODE_COMMANDS_KEY)
                )
            # Reporting a judged Node as done starts it when it can, so finishing
            # simple work is one command rather than two.
            _start_node(tree, node, node_id, executor)
        if node_commands(node) and origin != "cli":
            raise ToolError(
                "Node %s declares contract.%s; complete it with `tree-verify` so the tool runs the "
                "commands and records the evidence" % (node_id, NODE_COMMANDS_KEY)
            )
        node["status"] = "completed"
        node["evidence"].extend(guarded_evidence)
        if executor is not None:
            node["executor"] = executor
        affected = {node_id}
    elif action == "fail":
        if node.get("status") != "running":
            raise ToolError("Node %s must be running before failing" % node_id)
        node["status"] = "failed"
        node["evidence"].extend(guarded_evidence)
        if note:
            node["evidence"].append({"status": "failed", "reason": note})
        if executor is not None:
            node["executor"] = executor
        affected = {node_id}
    elif action == "block":
        if node.get("status") in {"completed", "cancelled"}:
            raise ToolError("Node %s cannot be blocked from %s" % (node_id, node.get("status")))
        node["status"] = "blocked"
        node["evidence"].extend(guarded_evidence)
        if note:
            node["evidence"].append({"status": "blocked", "reason": note})
        if executor is not None:
            node["executor"] = executor
        affected = {node_id}
    elif action == "cancel":
        if node.get("status") == "completed":
            raise ToolError("Node %s is completed and cannot be cancelled" % node_id)
        affected = _downstream_ids(tree, node_id)
        _reset_nodes(tree, affected, "cancelled")
        if note:
            node["evidence"].append({"status": "cancelled", "reason": note})
    else:  # reset
        affected = _downstream_ids(tree, node_id)
        _reset_nodes(tree, affected, "pending")
        if note:
            node["evidence"].append({"status": "reset", "reason": note})

    tree["generation"] = int(tree.get("generation", 0) or 0) + 1
    tree["updated_at"] = now()
    append_history(
        tree,
        action=action,
        node=node_id,
        from_status=before,
        to_status=str(node.get("status")),
        executor=executor,
        note=note,
        source=origin,
    )
    return {
        "applied": True,
        "node": node_id,
        "action": action,
        "status": node.get("status"),
        "tree_status": derive_tree_status(tree),
        "affected": sorted(affected),
        "generation": tree["generation"],
        # A failed Node hands the caller the next candidate in its declared order, so
        # a spent account or an exhausted quota is one retry away from continuing.
        "next_executor": next_executor(tree, node),
        "tried_executors": tried_executors(tree, node_id),
    }


def _definition_node(node: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": node.get("id"),
        "title": node.get("title"),
        "outcome": node.get("outcome"),
        "role": node.get("role"),
        "executors": list(node.get("executors", []) or []),
        "resources": list(node.get("resources", []) or []),
        "after": list(node.get("after", []) or []),
        "contract": deepcopy(node.get("contract", {})),
    }


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _task_with_nodes(tree: Mapping[str, Any], task_id: str) -> dict[str, Any] | None:
    return task_index(tree).get(task_id)


def reject_unknown_operation_fields(operation: Mapping[str, Any], allowed: set[str]) -> None:
    unknown = sorted(set(operation) - allowed)
    if unknown:
        raise ToolError("unknown operation field(s): %s" % ", ".join(unknown))


def _operation_tree_update(tree: dict[str, Any], operation: Mapping[str, Any]) -> None:
    reject_unknown_operation_fields(operation, {"op", "title", "meta"})
    if "title" in operation:
        tree["title"] = safe_record_text(operation["title"], "tree.title", max_chars=500)
    if "meta" in operation:
        tree["meta"] = safe_object(operation["meta"], "tree.meta")


def _operation_task_add(tree: dict[str, Any], operation: Mapping[str, Any]) -> None:
    reject_unknown_operation_fields(
        operation, {"op", "id", "title", "outcome", "contract", "nodes"}
    )
    task_id = safe_id(operation.get("id"), "task.add id")
    if task_id in task_index(tree):
        raise ToolError("task.add id already exists: %s" % task_id)
    nested = operation.get("nodes", [])
    if not isinstance(nested, list) or any(not isinstance(item, Mapping) for item in nested):
        raise ToolError("task.add nodes must be an array of Node objects")
    tree.setdefault("tasks", []).append(
        {
            "id": task_id,
            "title": safe_record_text(
                operation.get("title") or task_id, "task.title", max_chars=500
            ),
            "outcome": safe_record_text(
                operation.get("outcome") or operation.get("title") or task_id,
                "task.outcome",
                max_chars=1000,
            ),
            "contract": safe_object(operation.get("contract"), "task.contract"),
            "nodes": [],
        }
    )
    for index, item in enumerate(nested):
        node_operation = dict(item)
        node_operation.pop("op", None)
        if "task" in node_operation:
            raise ToolError(
                "task.add nodes[%d] must not repeat the task; it is already named here" % index
            )
        node_operation["op"] = "node.add"
        node_operation["task"] = task_id
        _operation_node_add(tree, node_operation)


def _operation_task_update(tree: dict[str, Any], operation: Mapping[str, Any]) -> None:
    reject_unknown_operation_fields(operation, {"op", "id", "set"})
    task = _task_with_nodes(tree, safe_id(operation.get("id"), "task.update id"))
    if not isinstance(task, dict):
        raise ToolError("unknown task: %s" % operation.get("id"))
    changes = operation.get("set")
    if not isinstance(changes, Mapping) or not changes:
        raise ToolError("task.update set must be a non-empty object")
    unknown = sorted(set(changes) - _TASK_UPDATE_FIELDS)
    if unknown:
        raise ToolError("task.update cannot change: %s" % ", ".join(unknown))
    if "title" in changes:
        task["title"] = safe_record_text(changes["title"], "task.title", max_chars=500)
    if "outcome" in changes:
        task["outcome"] = safe_record_text(changes["outcome"], "task.outcome", max_chars=1000)
    if "contract" in changes:
        task["contract"] = safe_object(changes["contract"], "task.contract")


def _operation_task_remove(tree: dict[str, Any], operation: Mapping[str, Any]) -> None:
    reject_unknown_operation_fields(operation, {"op", "id", "force"})
    task_id = safe_id(operation.get("id"), "task.remove id")
    tasks = iter_tasks(tree)
    task = next((item for item in tasks if item.get("id") == task_id), None)
    if not isinstance(task, Mapping):
        raise ToolError("unknown task: %s" % task_id)
    nodes = [node for node in task.get("nodes", []) or [] if isinstance(node, Mapping)]
    if operation.get("force") is not True and any(node.get("status") != "pending" for node in nodes):
        raise ToolError("task %s contains non-pending Nodes; use force:true" % task_id)
    removed_ids = {str(node.get("id")) for node in nodes if isinstance(node.get("id"), str)}
    tree["tasks"] = [item for item in tree.get("tasks", []) or [] if item is not task]
    _detach_after(tree, removed_ids)


def _executor_list(value: Any, field: str) -> list[str]:
    """Read an ordered list of opaque names. The only rules are shape rules.

    Executors and resources share this reader: no registry, no provider list, no
    quota, no path resolution. A name is opaque and the order is the fallback order.
    """

    if value is None:
        return []
    if not isinstance(value, list):
        raise ToolError("%s must be an array of names" % field)
    names: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip() or len(item) > 256 or "\x00" in item:
            raise ToolError("%s must contain non-empty names" % field)
        if item in names:
            raise ToolError("%s must not repeat a name: %s" % (field, item))
        names.append(safe_record_text(item, field, max_chars=256))
    return names


def _operation_node_add(tree: dict[str, Any], operation: Mapping[str, Any]) -> None:
    reject_unknown_operation_fields(
        operation,
        {
            "op",
            "task",
            "id",
            "title",
            "outcome",
            "role",
            "executors",
            "resources",
            "after",
            "contract",
        },
    )
    task = _task_with_nodes(tree, safe_id(operation.get("task"), "node.add task"))
    if not isinstance(task, dict):
        raise ToolError("node.add task is unknown: %s" % operation.get("task"))
    node_id = safe_id(operation.get("id"), "node.add id")
    if node_id in node_index(tree) or task_index(tree).get(node_id):
        raise ToolError("node.add id already exists: %s" % node_id)
    role = operation.get("role")
    if not is_delivery_role(role):
        raise ToolError(
            "node.add %s needs a role: 'designer', 'reviewer', or a worker slot such as 'worker' "
            "or 'worker-1'" % node_id
        )
    after = operation.get("after", []) or []
    if not isinstance(after, list) or any(not isinstance(item, str) for item in after):
        raise ToolError("node.add after must be an array of Node ids")
    after = [safe_record_text(item, "node.add after", max_chars=256) for item in after]
    task.setdefault("nodes", []).append(
        {
            "id": node_id,
            "title": safe_record_text(
                operation.get("title") or node_id, "node.title", max_chars=500
            ),
            "outcome": safe_record_text(
                operation.get("outcome") or operation.get("title") or node_id,
                "node.outcome",
                max_chars=1000,
            ),
            "role": role,
            "executors": _executor_list(
                operation.get("executors"), "node.add %s executors" % node_id
            ),
            "resources": _executor_list(
                operation.get("resources"), "node.add %s resources" % node_id
            ),
            "after": list(after),
            "status": "pending",
            "executor": None,
            "attempts": 0,
            "evidence": [],
            "contract": safe_object(operation.get("contract"), "node.contract"),
        }
    )


def _operation_node_update(tree: dict[str, Any], operation: Mapping[str, Any]) -> None:
    reject_unknown_operation_fields(operation, {"op", "id", "set", "reset"})
    node_id = safe_id(operation.get("id"), "node.update id")
    nodes = node_index(tree)
    target = nodes.get(node_id)
    if not isinstance(target, dict):
        raise ToolError("unknown tree node: %s" % node_id)
    changes = operation.get("set")
    if not isinstance(changes, Mapping) or not changes:
        raise ToolError("node.update set must be a non-empty object")
    unknown = sorted(set(changes) - _NODE_UPDATE_FIELDS)
    if unknown:
        raise ToolError("node.update cannot change: %s" % ", ".join(unknown))
    candidate = deepcopy(target)
    if "title" in changes:
        candidate["title"] = safe_record_text(changes["title"], "node.title", max_chars=500)
    if "outcome" in changes:
        candidate["outcome"] = safe_record_text(changes["outcome"], "node.outcome", max_chars=1000)
    if "role" in changes:
        if not is_delivery_role(changes["role"]):
            raise ToolError(
                "node.update role must be 'designer', 'reviewer', or a worker slot such as "
                "'worker' or 'worker-1'"
            )
        candidate["role"] = changes["role"]
    if "executors" in changes:
        candidate["executors"] = _executor_list(
            changes["executors"], "node.update %s executors" % node_id
        )
    if "resources" in changes:
        candidate["resources"] = _executor_list(
            changes["resources"], "node.update %s resources" % node_id
        )
    before_chain = [str(item) for item in (target.get("executors") or [])]
    after_chain = list(candidate.get("executors") or [])
    # Appending a fallback does not redefine the work: it only adds a place the
    # Node may run next. That is the one edit a started Node accepts without a reset,
    # because discovering a spent account must not throw away finished work. A Node
    # that declared no chain has no fallback to append to, so pinning one for the
    # first time is a replacement and needs the reset like any other.
    appended_fallback = (
        set(changes) == {"executors"}
        and bool(before_chain)
        and after_chain[: len(before_chain)] == before_chain
        and len(after_chain) > len(before_chain)
    )
    if "after" in changes:
        after = changes["after"]
        if not isinstance(after, list) or any(not isinstance(item, str) for item in after):
            raise ToolError("node.update after must be an array of Node ids")
        candidate["after"] = [
            safe_record_text(item, "node.update after", max_chars=256) for item in after
        ]
    if "contract" in changes:
        candidate["contract"] = safe_object(changes["contract"], "node.contract")
    definition_changed = canonical_json(_definition_node(target)) != canonical_json(_definition_node(candidate))
    if definition_changed and target.get("status") != "pending":
        if appended_fallback:
            pass
        elif operation.get("reset") is not True:
            raise ToolError(
                "Node %s is %s; set reset:true to redefine it and everything downstream"
                % (node_id, target.get("status"))
            )
        else:
            _reset_nodes(tree, _downstream_ids(tree, node_id), "pending")
    target.update(_definition_node(candidate))


def _operation_node_move(tree: dict[str, Any], operation: Mapping[str, Any]) -> None:
    reject_unknown_operation_fields(operation, {"op", "id", "task"})
    node_id = safe_id(operation.get("id"), "node.move id")
    target_task = _task_with_nodes(tree, safe_id(operation.get("task"), "node.move task"))
    if not isinstance(target_task, dict):
        raise ToolError("node.move target Task is unknown: %s" % operation.get("task"))
    source_task = _task_of_node(tree, node_id)
    if not isinstance(source_task, dict):
        raise ToolError("unknown tree node: %s" % node_id)
    if source_task is target_task:
        return
    source_nodes = source_task.get("nodes")
    node = next(
        (item for item in source_nodes if isinstance(item, Mapping) and item.get("id") == node_id),
        None,
    )
    if not isinstance(node, Mapping):
        raise ToolError("unknown tree node: %s" % node_id)
    source_task["nodes"] = [item for item in source_nodes if item is not node]
    target_task.setdefault("nodes", []).append(node)


def _operation_node_remove(tree: dict[str, Any], operation: Mapping[str, Any]) -> None:
    reject_unknown_operation_fields(operation, {"op", "id", "force"})
    node_id = safe_id(operation.get("id"), "node.remove id")
    nodes = node_index(tree)
    node = nodes.get(node_id)
    if not isinstance(node, Mapping):
        raise ToolError("unknown tree node: %s" % node_id)
    downstream = _downstream_ids(tree, node_id) - {node_id}
    if downstream and operation.get("force") is not True:
        raise ToolError("node %s has downstream Nodes; use force:true" % node_id)
    if node.get("status") != "pending" and operation.get("force") is not True:
        raise ToolError("node %s is %s; use force:true" % (node_id, node.get("status")))
    for task in iter_tasks(tree):
        nodes_list = task.get("nodes")
        if isinstance(nodes_list, list):
            task["nodes"] = [
                item for item in nodes_list if not (isinstance(item, Mapping) and item.get("id") == node_id)
            ]
    _detach_after(tree, {node_id})


def _operation_after_add(tree: dict[str, Any], operation: Mapping[str, Any]) -> None:
    reject_unknown_operation_fields(operation, {"op", "node", "after", "reset"})
    node_id = safe_id(operation.get("node"), "after.add node")
    prerequisite = safe_id(operation.get("after"), "after.add after")
    nodes = node_index(tree)
    target = nodes.get(node_id)
    if not isinstance(target, dict):
        raise ToolError("after.add node is unknown: %s" % node_id)
    if prerequisite not in nodes:
        raise ToolError("after.add prerequisite is unknown: %s" % prerequisite)
    if prerequisite == node_id:
        raise ToolError("after.add cannot reference the same Node")
    after = target.get("after")
    if isinstance(after, list) and prerequisite in after:
        return
    if target.get("status") != "pending":
        if operation.get("reset") is not True:
            raise ToolError(
                "Node %s is %s; set reset:true to add this dependency"
                % (node_id, target.get("status"))
            )
        _reset_nodes(tree, _downstream_ids(tree, node_id), "pending")
    after = target.setdefault("after", [])
    after.append(prerequisite)


def _operation_after_remove(tree: dict[str, Any], operation: Mapping[str, Any]) -> None:
    reject_unknown_operation_fields(operation, {"op", "node", "after", "reset"})
    node_id = safe_id(operation.get("node"), "after.remove node")
    prerequisite = safe_id(operation.get("after"), "after.remove after")
    nodes = node_index(tree)
    target = nodes.get(node_id)
    if not isinstance(target, dict):
        raise ToolError("after.remove node is unknown: %s" % node_id)
    after = target.get("after")
    if not isinstance(after, list) or prerequisite not in after:
        raise ToolError("after.remove edge does not exist: %s -> %s" % (prerequisite, node_id))
    if target.get("status") != "pending":
        if operation.get("reset") is not True:
            raise ToolError(
                "Node %s is %s; set reset:true to remove this dependency"
                % (node_id, target.get("status"))
            )
        _reset_nodes(tree, _downstream_ids(tree, node_id), "pending")
    target["after"] = [item for item in target.get("after", []) if item != prerequisite]


def _apply_operation(tree: dict[str, Any], operation: Mapping[str, Any]) -> None:
    kind = operation.get("op")
    if kind not in OPERATION_KINDS:
        raise ToolError("unknown tree operation: %s" % kind)
    handlers = {
        "tree.update": _operation_tree_update,
        "task.add": _operation_task_add,
        "task.update": _operation_task_update,
        "task.remove": _operation_task_remove,
        "node.add": _operation_node_add,
        "node.update": _operation_node_update,
        "node.move": _operation_node_move,
        "node.remove": _operation_node_remove,
        "after.add": _operation_after_add,
        "after.remove": _operation_after_remove,
    }
    handlers[kind](tree, operation)


def apply_operations(
    tree: dict[str, Any],
    operations: Sequence[Any],
    *,
    actor: str | None = None,
    batch_id: str | None = None,
    base_revision: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Apply one atomic batch of canonical Tree operations.

    The entire batch is evaluated on a copy.  One invalid operation rejects the
    whole batch and leaves the stored Tree untouched.
    """

    if not isinstance(operations, Sequence) or isinstance(operations, (str, bytes)) or not operations:
        raise ToolError("operations must be a non-empty JSON array")
    if base_revision is not None and (type(base_revision) is not int or base_revision < 0):
        raise ToolError("base_revision must be a non-negative integer")
    actor = (
        safe_record_text(actor, "actor", max_chars=256) if actor is not None else None
    )
    batch_id = (
        safe_record_text(batch_id, "batch_id", max_chars=256) if batch_id is not None else None
    )
    # A retry of a batch that already landed is a no-op whatever the Tree's
    # generation is now; only a genuinely stale batch is a revision conflict.
    if batch_id is not None:
        for entry in tree.get("history", []) or []:
            if isinstance(entry, Mapping) and entry.get("batch_id") == batch_id:
                return {
                    "applied": False,
                    "idempotent": True,
                    "batch_id": batch_id,
                    "generation": tree.get("generation"),
                    "operations": int(entry.get("operation_count", 0) or 0),
                }
    if base_revision is not None and int(tree.get("generation", 0) or 0) != base_revision:
        raise ToolError(
            "base_revision mismatch: tree is generation %s, batch expects %s"
            % (tree.get("generation"), base_revision)
        )

    working = deepcopy(tree)
    for index, operation in enumerate(operations):
        if not isinstance(operation, Mapping):
            raise ToolError("operation %d must be an object" % index)
        try:
            _apply_operation(working, operation)
        except ToolError as error:
            raise ToolError("operation %d (%s): %s" % (index, operation.get("op"), error))
    issues = validate_tree(working)
    if issues:
        raise ToolError("batch rejected by tree invariants: %s" % "; ".join(issues[:6]))

    if dry_run:
        return {
            "applied": False,
            "dry_run": True,
            "batch_id": batch_id,
            "generation": tree.get("generation"),
            "next_generation": int(tree.get("generation", 0) or 0) + 1,
            "operations": len(operations),
            "ready": ready_codes(working),
            "status": derive_tree_status(working),
        }

    tree.clear()
    tree.update(working)
    tree["generation"] = int(tree.get("generation", 0) or 0) + 1
    tree["updated_at"] = now()
    append_history(
        tree,
        action="apply",
        batch_id=batch_id,
        actor=actor,
        operations=operations,
    )
    return {
        "applied": True,
        "batch_id": batch_id,
        "generation": tree["generation"],
        "operations": len(operations),
        "ready": ready_codes(tree),
        "status": derive_tree_status(tree),
    }


def render_tree(tree: Mapping[str, Any], *, details: bool = False) -> str:
    lines = ["%s %s [%s]" % (tree.get("id"), tree.get("title"), derive_tree_status(tree))]
    for task in iter_tasks(tree):
        lines.append(
            "  %s %s [%s]" % (task.get("id"), task.get("title"), derive_task_status(tree, task))
        )
        nodes = task.get("nodes") if isinstance(task.get("nodes"), list) else []
        for node in nodes:
            if not isinstance(node, Mapping):
                continue
            after = ",".join(_node_after(node)) or "none"
            line = "    %s %s [%s] after=%s" % (
                node.get("id"),
                node.get("title"),
                node.get("status"),
                after,
            )
            if details:
                line += " executor=%s attempts=%s evidence=%d" % (
                    node.get("executor") or "-",
                    node.get("attempts", 0),
                    len(node.get("evidence", []) or []),
                )
            lines.append(line)
    return "\n".join(lines)


def readiness_report(tree: Mapping[str, Any]) -> dict[str, Any]:
    """Explain the execution frontier without changing the tree."""

    nodes = node_index(tree)
    ready_set = set(ready_codes(tree))
    groups: dict[str, list[dict[str, Any]]] = {
        "ready": [],
        "waiting": [],
        "running": [],
        "completed": [],
        "failed": [],
        "blocked": [],
        "cancelled": [],
    }
    for task, node in iter_nodes(tree):
        code = str(node.get("id"))
        status = str(node.get("status"))
        blockers = [
            item for item in _node_after(node) if nodes.get(item, {}).get("status") != "completed"
        ]
        detail = {
            "id": code,
            "task": task.get("id"),
            "title": node.get("title"),
            "role": node.get("role"),
            "executors": node_executors(node),
            "next_executor": next_executor(tree, node),
            "tried_executors": tried_executors(tree, code),
            "status": status,
            "after": _node_after(node),
            "blockers": blockers,
            "executor": node.get("executor"),
            "attempts": node.get("attempts", 0),
        }
        if code in ready_set:
            groups["ready"].append(detail)
        elif status == "running":
            groups["running"].append(detail)
        elif status == "completed":
            groups["completed"].append(detail)
        elif status == "failed":
            groups["failed"].append(detail)
        elif status == "blocked":
            groups["blocked"].append(detail)
        elif status == "cancelled":
            groups["cancelled"].append(detail)
        else:
            groups["waiting"].append(detail)
    return groups


def reported_completions(tree: Mapping[str, Any]) -> list[str]:
    """Completed Nodes whose outcome was reported rather than executed by the tool.

    A Node without ``contract.commands`` has nothing for the tool to run, so a
    reported completion is the only honest option. Listing them keeps the two
    kinds of green distinguishable in every status view.
    """

    sources: dict[str, str] = {}
    for entry in tree.get("history", []) or []:
        if (
            isinstance(entry, Mapping)
            and entry.get("action") == "complete"
            and isinstance(entry.get("node"), str)
        ):
            sources[str(entry["node"])] = str(entry.get("source") or "reported")
    completed = {
        str(node.get("id")) for _, node in iter_nodes(tree) if node.get("status") == "completed"
    }
    return sorted(code for code in completed if sources.get(code, "reported") != "cli")


def role_nodes(tree: Mapping[str, Any]) -> dict[str, list[str]]:
    """List the Nodes each role slot owns, in tree order.

    This is the view a dispatcher needs: who does what, not how much.
    """

    owned: dict[str, list[str]] = {}
    for _, node in iter_nodes(tree):
        owned.setdefault(str(node.get("role")), []).append(str(node.get("id")))
    return owned


def status_payload(tree: Mapping[str, Any]) -> dict[str, Any]:
    node_counts: dict[str, int] = {}
    for _, node in iter_nodes(tree):
        status = str(node.get("status"))
        node_counts[status] = node_counts.get(status, 0) + 1
    task_counts: dict[str, int] = {}
    for task in iter_tasks(tree):
        status = derive_task_status(tree, task)
        task_counts[status] = task_counts.get(status, 0) + 1
    return {
        "id": tree.get("id"),
        "title": tree.get("title"),
        "status": derive_tree_status(tree),
        "generation": tree.get("generation"),
        "task_counts": task_counts,
        "node_counts": node_counts,
        "role_nodes": role_nodes(tree),
        "ready": ready_codes(tree),
        "tasks": len(iter_tasks(tree)),
        "nodes": len(iter_nodes(tree)),
        "reported_completions": reported_completions(tree),
    }


