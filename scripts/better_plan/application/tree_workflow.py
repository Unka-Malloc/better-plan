"""Application services for the split, current-state Checkpoints Tree."""

from __future__ import annotations

from collections import deque
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable, Mapping
import base64
import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
import uuid

from ..domain.checkpoints_tree import (
    TREE_NAME,
    add_review,
    adjacency,
    clear_review,
    check_coverage,
    delivery_status,
    new_delivery,
    descendants,
    derived_state,
    export_payload,
    flattened_checks,
    mark_checks_pending,
    new_node,
    new_task,
    new_tree,
    normalize_check,
    safe_id,
    task_nodes,
)
from ..domain.models import ToolError, deep_patch
from ..infrastructure.command_runner import run_commands_with_diagnostics
from ..infrastructure.workspace import (
    CurrentWorkspace,
    check_lock,
    annotate_check_runs,
    read_json,
    resolve_root,
    workspace_lock,
    write_json,
)


def _root(args: Any) -> Path:
    return resolve_root(getattr(args, "root", "."))


def _json_input(value: str, root: Path) -> Any:
    if value == "-":
        text = sys.stdin.read()
    else:
        path = Path(value).expanduser()
        if not path.is_absolute() and not path.is_file():
            path = root / path
        if not path.is_file():
            raise ToolError("input is missing at %s" % path)
        text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ToolError("input is not valid JSON: %s" % exc.msg)


def _object_input(value: str, root: Path) -> dict[str, Any]:
    result = _json_input(value, root)
    if not isinstance(result, dict):
        raise ToolError("input must contain a JSON object")
    return result


def _normalize_checks(container: dict[str, Any], owner_kind: str) -> None:
    if "checks" in container:
        container["checks"] = [normalize_check(item, owner_kind) for item in container["checks"]]


def _merge_checks(old: Iterable[Mapping[str, Any]], new: Iterable[Mapping[str, Any]], owner_kind: str) -> list[dict[str, Any]]:
    """Preserve runtime state while replacing check definitions by stable id."""

    previous = {str(item.get("id")): item for item in old}
    result = []
    for raw in new:
        item = normalize_check(raw, owner_kind)
        prior = previous.get(item["id"])
        if prior is not None:
            for field in ("pending", "running", "dirty", "result", "run_id"):
                item[field] = prior.get(field)
            definition_changed = any(
                prior.get(field) != item.get(field) for field in ("commands", "coverage")
            )
            if definition_changed:
                item["pending"] = True
                if prior.get("running"):
                    item["running"] = True
                    item["dirty"] = True
        result.append(item)
    return result


def _overlay_edits(latest: Any, before: Any, edited: Any) -> Any:
    """Apply only editor-visible differences to the latest concurrently updated value."""

    if before == edited:
        return latest
    if not isinstance(before, Mapping) or not isinstance(edited, Mapping) or not isinstance(latest, Mapping):
        return deepcopy(edited)
    result = dict(latest)
    for key in set(before).union(edited):
        if key not in edited:
            result.pop(key, None)
        elif key not in before:
            result[key] = deepcopy(edited[key])
        elif before[key] != edited[key]:
            result[key] = _overlay_edits(result.get(key), before[key], edited[key])
    return result


def _snapshot(root: Path):
    workspace = CurrentWorkspace(root)
    with workspace_lock(root):
        tree, tasks, nodes = workspace.load()
        annotate_check_runs(root, tree, tasks, nodes)
        return tree, tasks, nodes


def _check_unique(items: Iterable[Mapping[str, Any]], kind: str) -> None:
    seen: set[str] = set()
    for item in items:
        code = safe_id(item.get("id"), "%s.id" % kind)
        if code in seen:
            raise ToolError("duplicate %s id %s" % (kind, code))
        seen.add(code)


def _write_changed(
    workspace: CurrentWorkspace,
    tree: dict[str, Any],
    tasks: Mapping[str, dict[str, Any]],
    nodes: Mapping[str, dict[str, Any]],
    changed: set[tuple[str, str]],
) -> None:
    for kind, code in changed:
        if kind == "tree":
            workspace.write_tree(tree)
        elif kind == "task" and code in tasks:
            workspace.write_task(tasks[code])
        elif kind == "node" and code in nodes:
            workspace.write_node(nodes[code])


def _mark_deliveries(tree, tasks, nodes, affected, source_kind, source_id, reason, task_ids=()):
    owners = set(task_ids)
    owners.update(str(nodes[code].get("task")) for code in affected if code in nodes)
    changed = set()
    for kind, code, container in [("tree", tree["id"], tree)] + [
        ("task", code, tasks[code]) for code in sorted(owners) if code in tasks
    ]:
        delivery = container.setdefault("delivery", new_delivery())
        if delivery.get("result") is None:
            continue
        if add_review({code: delivery}, [code], source_kind, source_id, reason):
            changed.add((kind, code))
    return changed


def _check_delivery_change(tree, tasks, nodes, kind, owner_id, check, reason):
    covered = check_coverage(check, kind, owner_id, nodes)
    owners = [owner_id] if kind == "task" and check["coverage"]["kind"] == "task" else []
    return _mark_deliveries(tree, tasks, nodes, covered, "check",
                            "%s:%s:%s" % (kind, owner_id, check["id"]), reason, owners)


def _changed_check_definitions(tree, tasks, nodes, kind, owner_id, before, after):
    old = {item["id"]: item for item in before}
    new = {item["id"]: item for item in after}
    changed = set()
    for code in old.keys() | new.keys():
        left, right = old.get(code), new.get(code)
        if left is not None and right is not None and all(
            left.get(field) == right.get(field) for field in ("commands", "coverage")
        ):
            continue
        for check in (left, right):
            if check is not None:
                changed.update(_check_delivery_change(tree, tasks, nodes, kind, owner_id, check, "check_changed"))
    return changed


def _mark_change(
    tree: dict[str, Any],
    tasks: Mapping[str, dict[str, Any]],
    nodes: Mapping[str, dict[str, Any]],
    seeds: Iterable[str],
    source_kind: str,
    source_id: str,
    reason: str,
) -> set[tuple[str, str]]:
    affected = descendants(nodes, seeds)
    changed = {("node", code) for code in add_review(nodes, affected, source_kind, source_id, reason)}
    changed.update(mark_checks_pending(tree, tasks, nodes, affected))
    changed.update(_mark_deliveries(tree, tasks, nodes, affected, source_kind, source_id, reason))
    return changed


def create_tree_workspace(
    root: Path,
    tree_id: str,
    title: str,
    goal: str = "",
    fields: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create one Tree workspace exactly as `tree init` does, under its own lock."""

    workspace = CurrentWorkspace(root)
    with workspace_lock(root, create=True):
        if workspace.tree_path.exists():
            raise ToolError("Tree.json already exists")
        tree = new_tree(tree_id, title, goal)
        if fields:
            tree.update(fields)
        workspace.write_tree(tree)
        workspace.tasks_path.mkdir(parents=True, exist_ok=True)
        workspace.nodes_path.mkdir(parents=True, exist_ok=True)
        workspace.history_path.mkdir(parents=True, exist_ok=True)
    return tree


def init_tree(args: Any) -> int:
    root = _root(args)
    tree = create_tree_workspace(root, args.id or "TREE-001", args.title, args.goal or "")
    print(json.dumps({"created": True, "root": str(root), "tree": tree}, ensure_ascii=False))
    return 0


def _print_outstanding(payload):
    tree = payload["tree"]
    for kind, container in [("tree", tree)] + [("task", task) for task in tree["tasks"]]:
        delivery = container.get("delivery") or {}
        for review in delivery.get("review") or []:
            source = review.get("source") or {}
            print("  delivery review %s:%s from %s:%s %s" % (
                kind, container["id"], source.get("kind"), source.get("id"), review.get("reason")))
        exceptions = (delivery.get("result") or {}).get("exceptions")
        if exceptions:
            print("  delivery exceptions %s:%s %s" % (kind, container["id"], json.dumps(exceptions, ensure_ascii=False)))
    if tree.get("open_decisions"):
        print("  open decisions: %s" % json.dumps(tree["open_decisions"], ensure_ascii=False))
    if payload["derived"]["unconfirmed_tasks"]:
        print("  unconfirmed Tasks: %s" % ",".join(payload["derived"]["unconfirmed_tasks"]))
    for check in payload["checks"]:
        if check["pending"] or check["interrupted"] or (check.get("result") or {}).get("status") == "failed":
            print("  check %s:%s/%s pending=%s interrupted=%s previous_result=%s" % (
                check["owner"]["kind"], check["owner"]["id"], check["id"], check["pending"],
                check["interrupted"], (check.get("result") or {}).get("status", "unknown")))


def show_tree(args: Any) -> int:
    tree, tasks, nodes = _snapshot(_root(args))
    payload = export_payload(tree, tasks, nodes)
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return 0
    print("%s %s [execution=%s delivery=%s]" % (tree["id"], tree.get("title", ""), payload["derived"]["status"], payload["derived"]["delivery_status"]))
    if tree.get("goal"):
        print("goal: %s" % tree["goal"])
    for task in payload["tree"]["tasks"]:
        print("  %s %s [execution=%s delivery=%s owner=%s]" % (task["id"], task.get("title", ""), payload["derived"]["task_status"][task["id"]], payload["derived"]["task_delivery_status"][task["id"]], task.get("integration_owner") or "unassigned"))
        for node in task["nodes"]:
            marker = " review" if node.get("review") else ""
            print("    %s %s [%s%s]" % (node["id"], node.get("title", ""), node.get("status"), marker))
    _print_outstanding(payload)
    return 0


def tree_status(args: Any) -> int:
    tree, tasks, nodes = _snapshot(_root(args))
    assembled = export_payload(tree, tasks, nodes)
    payload = dict(assembled["derived"])
    payload["checks"] = assembled["checks"]
    payload["delivery"] = tree["delivery"]
    payload["task_deliveries"] = {code: task["delivery"] for code, task in tasks.items()}
    payload["open_decisions"] = tree.get("open_decisions") or []
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print("execution=%s delivery=%s ready=%s review=%s" % (payload["status"], payload["delivery_status"], ",".join(payload["ready"]) or "none", ",".join(payload["review_nodes"]) or "none"))
        _print_outstanding(assembled)
    return 0


def next_nodes(args: Any) -> int:
    tree, tasks, nodes = _snapshot(_root(args))
    state = derived_state(tree, tasks, nodes)
    ready = state["ready"][: args.limit or None]
    payload = [{"id": code, "task": nodes[code].get("task"), "title": nodes[code].get("title"), "role": nodes[code].get("role"), "review": nodes[code].get("review") or []} for code in ready]
    review_needed = [
        {"id": code, "task": nodes[code].get("task"), "status": nodes[code].get("status"), "review": nodes[code].get("review") or []}
        for code in state["review_nodes"]
    ]
    if getattr(args, "json", False):
        print(json.dumps({"ready": payload, "review_needed": review_needed, "blockers": state["blockers"]}, ensure_ascii=False, sort_keys=True))
    else:
        for item in payload:
            print("%s task=%s role=%s %s" % (item["id"], item["task"], item["role"] or "any", item["title"] or ""))
        for item in review_needed:
            print("review %s task=%s status=%s" % (item["id"], item["task"], item["status"]))
    return 0


def export_tree(args: Any) -> int:
    tree, tasks, nodes = _snapshot(_root(args))
    print(json.dumps(export_payload(tree, tasks, nodes), indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def refresh_tree(args: Any) -> int:
    """Recompute the complete view after manual file edits; write no state."""

    tree, tasks, nodes = _snapshot(_root(args))
    payload = export_payload(tree, tasks, nodes)
    payload["refresh_note"] = "Derived state rebuilt. Manual edits cannot reconstruct missed change notifications."
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def update_tree(args: Any) -> int:
    root = _root(args)
    workspace = CurrentWorkspace(root)
    patch = _object_input(args.input, root)
    with workspace_lock(root):
        tree, tasks, nodes = workspace.load()
        if any(key in patch for key in ("id", "schema", "tasks", "delivery")):
            raise ToolError("tree identity, assembled tasks and delivery are not update fields; use tree finish for delivery")
        before_tree = deepcopy(tree)
        old_checks = deepcopy(tree.get("checks") or [])
        tree = deep_patch(tree, patch)
        if "checks" in patch:
            tree["checks"] = _merge_checks(old_checks, patch["checks"], "tree")
        else:
            _normalize_checks(tree, "tree")
        _check_unique(tree.get("checks") or [], "check")
        propagation = any(
            before_tree.get(key) != tree.get(key)
            for key in set(before_tree).union(tree)
            if key not in ("checks", "schema", "id", "title", "delivery")
        )
        changed: set[tuple[str, str]] = set()
        if tree != before_tree:
            changed.add(("tree", tree["id"]))
        changed.update(_changed_check_definitions(tree, tasks, nodes, "tree", tree["id"], old_checks, tree["checks"]))
        if propagation:
            changed.update(_mark_change(tree, tasks, nodes, nodes, "tree", tree["id"], "requirements_changed"))
            changed.update(_mark_deliveries(tree, tasks, nodes, [], "tree", tree["id"], "requirements_changed", tasks))
        _write_changed(workspace, tree, tasks, nodes, changed)
    print(json.dumps({"updated": tree["id"], "affected": sorted(code for kind, code in changed if kind == "node")}, ensure_ascii=False))
    return 0


def add_task(args: Any) -> int:
    root = _root(args)
    workspace = CurrentWorkspace(root)
    value = _object_input(args.input, root)
    task = new_task(value.get("id"), value.get("title") or value.get("id"), value.get("outcome", ""))
    task.update(value)
    task["id"] = safe_id(task["id"], "task.id")
    _normalize_checks(task, "task")
    _check_unique(task.get("checks") or [], "check")
    with workspace_lock(root):
        tree, tasks, nodes = workspace.load()
        if task["id"] in tasks:
            raise ToolError("task %s already exists" % task["id"])
        tasks[task["id"]] = task
        changed = _mark_deliveries(tree, tasks, nodes, [], "task", task["id"], "membership_changed")
        changed.add(("task", task["id"]))
        _write_changed(workspace, tree, tasks, nodes, changed)
    print(json.dumps({"added": task["id"]}))
    return 0


def update_task(args: Any) -> int:
    root = _root(args)
    workspace = CurrentWorkspace(root)
    patch = _object_input(args.input, root)
    with workspace_lock(root):
        tree, tasks, nodes = workspace.load()
        task_id = safe_id(args.id, "task.id")
        if task_id not in tasks:
            raise ToolError("unknown task %s" % task_id)
        if any(key in patch for key in ("id", "nodes", "delivery")):
            raise ToolError("task identity, derived nodes and delivery are not update fields; use task finish for delivery")
        before_task = deepcopy(tasks[task_id])
        old_checks = deepcopy(tasks[task_id].get("checks") or [])
        tasks[task_id] = deep_patch(tasks[task_id], patch)
        if "checks" in patch:
            tasks[task_id]["checks"] = _merge_checks(old_checks, patch["checks"], "task")
        else:
            _normalize_checks(tasks[task_id], "task")
        _check_unique(tasks[task_id].get("checks") or [], "check")
        propagation = any(
            before_task.get(key) != tasks[task_id].get(key)
            for key in set(before_task).union(tasks[task_id])
            if key not in ("checks", "id", "draft_pr", "integration_owner", "title", "delivery")
        )
        changed: set[tuple[str, str]] = set()
        if tasks[task_id] != before_task:
            changed.add(("task", task_id))
        changed.update(_changed_check_definitions(tree, tasks, nodes, "task", task_id, old_checks, tasks[task_id]["checks"]))
        if propagation:
            changed.update(_mark_change(tree, tasks, nodes, task_nodes(nodes, task_id), "task", task_id, "requirements_changed"))
            changed.update(_mark_deliveries(tree, tasks, nodes, [], "task", task_id, "requirements_changed", [task_id]))
        _write_changed(workspace, tree, tasks, nodes, changed)
    print(json.dumps({"updated": task_id, "affected": sorted(code for kind, code in changed if kind == "node")}))
    return 0


def show_task(args: Any) -> int:
    tree, tasks, nodes = _snapshot(_root(args))
    task_id = safe_id(args.id, "task.id")
    if task_id not in tasks:
        raise ToolError("unknown task %s" % task_id)
    value = dict(tasks[task_id])
    value["nodes"] = [nodes[code] for code in nodes if nodes[code].get("task") == task_id]
    value["status"] = derived_state(tree, tasks, nodes)["task_status"][task_id]
    value["delivery_status"] = delivery_status(tasks[task_id])
    print(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def remove_task(args: Any) -> int:
    root = _root(args)
    workspace = CurrentWorkspace(root)
    with workspace_lock(root):
        tree, tasks, nodes = workspace.load()
        task_id = safe_id(args.id, "task.id")
        if task_id not in tasks:
            raise ToolError("unknown task %s" % task_id)
        owned = task_nodes(nodes, task_id)
        if owned and not args.with_nodes:
            raise ToolError("task %s has nodes; use --with-nodes to remove its group" % task_id)
        changed: set[tuple[str, str]] = set()
        if owned:
            changed = _remove_subtree_objects(workspace, tree, tasks, nodes, owned, task_id, "task")
        changed.update(_mark_deliveries(tree, tasks, nodes, [], "task", task_id, "membership_changed"))
        tasks.pop(task_id)
        workspace.remove_task(task_id)
        _write_changed(workspace, tree, tasks, nodes, changed)
    print(json.dumps({"removed": task_id, "nodes": owned}))
    return 0


def _prepare_node(value: dict[str, Any]) -> dict[str, Any]:
    node = new_node(value.get("id"), value.get("task"), value.get("title") or value.get("id"), value.get("outcome", ""), value.get("after") or [])
    node.update(value)
    node["id"] = safe_id(node["id"], "node.id")
    node["task"] = safe_id(node["task"], "node.task")
    node["after"] = list(dict.fromkeys(safe_id(item, "node.after") for item in node.get("after") or []))
    _normalize_checks(node, "node")
    _check_unique(node.get("checks") or [], "check")
    return node


def add_node(args: Any) -> int:
    root = _root(args)
    workspace = CurrentWorkspace(root)
    value = _object_input(args.input, root)
    node = _prepare_node(value)
    with workspace_lock(root):
        tree, tasks, nodes = workspace.load()
        if node["id"] in nodes:
            raise ToolError("node %s already exists" % node["id"])
        if node["task"] not in tasks:
            raise ToolError("unknown task %s" % node["task"])
        changed: set[tuple[str, str]] = {("node", node["id"])}
        if args.between:
            predecessor, successor = args.between
            if predecessor not in nodes or successor not in nodes:
                raise ToolError("--between names unknown nodes")
            if predecessor not in nodes[successor].get("after", []):
                raise ToolError("%s does not directly depend on %s" % (successor, predecessor))
            node["after"] = list(dict.fromkeys(list(node.get("after") or []) + [predecessor]))
            nodes[node["id"]] = node
            nodes[successor]["after"] = [node["id"] if item == predecessor else item for item in nodes[successor]["after"]]
            changed.add(("node", successor))
            changed.update(_mark_change(tree, tasks, nodes, [successor], "node", node["id"], "dependency_changed"))
        else:
            missing = [dependency for dependency in node["after"] if dependency not in nodes]
            if missing:
                raise ToolError("node.after names unknown node(s): %s" % ", ".join(missing))
            nodes[node["id"]] = node
        changed.update(mark_checks_pending(tree, tasks, nodes, [node["id"]]))
        changed.update(_mark_deliveries(tree, tasks, nodes, descendants(nodes, [node["id"]]), "node", node["id"], "membership_changed"))
        _write_changed(workspace, tree, tasks, nodes, changed)
    print(json.dumps({"added": node["id"], "changed": sorted("%s:%s" % item for item in changed)}))
    return 0


_NODE_NON_PROPAGATING = frozenset({"status", "result", "review", "checks", "commit", "title", "role", "executors"})


def _apply_node_change(tree, tasks, nodes, node_id, before, node):
    fields = {key for key in set(before).union(node) if before.get(key) != node.get(key)}
    if not fields:
        return set()
    changed = {("node", node_id)}
    structural = fields - _NODE_NON_PROPAGATING
    evidence = fields.intersection({"commit", "result"})
    old_affected = descendants(nodes, [node_id]) if structural or evidence else []
    if structural or evidence:
        changed.update(mark_checks_pending(tree, tasks, nodes, old_affected))
        changed.update(_mark_deliveries(tree, tasks, nodes, old_affected, "node", node_id, "content_changed"))
        # Preserve invalidation on this Node's own checks before replacing its object.
        previous_checks = {item["id"]: item for item in nodes[node_id].get("checks") or []}
        for check in node.get("checks") or []:
            prior = previous_checks.get(check["id"])
            if prior and prior.get("pending"):
                check["pending"] = True
                check["dirty"] = bool(check.get("dirty") or prior.get("dirty"))
    nodes[node_id] = node
    changed.update(_changed_check_definitions(tree, tasks, nodes, "node", node_id,
                                             before.get("checks") or [], node.get("checks") or []))
    if structural:
        reason = "dependency_changed" if "after" in fields else "content_changed"
        changed.update(_mark_change(tree, tasks, nodes, [node_id], "node", node_id, reason))
    elif evidence:
        affected = old_affected
        changed.update(("node", code) for code in add_review(nodes, affected[1:], "node", node_id, "result_changed"))
        changed.update(mark_checks_pending(tree, tasks, nodes, affected))
        changed.update(_mark_deliveries(tree, tasks, nodes, affected, "node", node_id, "result_changed"))
    if "status" in fields:
        changed.update(_mark_deliveries(tree, tasks, nodes, [node_id], "node", node_id, "execution_changed"))
    return changed


def _update_node(
    root: Path,
    node_id: str,
    patch: dict[str, Any],
    replace: bool = False,
    edit_base: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], set[tuple[str, str]]]:
    workspace = CurrentWorkspace(root)
    with workspace_lock(root):
        tree, tasks, nodes = workspace.load()
        node_id = safe_id(node_id, "node.id")
        if node_id not in nodes:
            raise ToolError("unknown node %s" % node_id)
        before = deepcopy(nodes[node_id])
        if replace:
            value = _overlay_edits(before, edit_base, patch) if edit_base is not None else dict(patch)
            value.setdefault("id", node_id)
            if value.get("id") != node_id:
                raise ToolError("node edit cannot change identity")
            node = _prepare_node(value)
            node["checks"] = _merge_checks(before.get("checks") or [], node.get("checks") or [], "node")
        else:
            if "id" in patch:
                raise ToolError("node identity is not an update field")
            node = deep_patch(before, patch)
            if "checks" in patch:
                node["checks"] = _merge_checks(before.get("checks") or [], patch["checks"], "node")
            node = _prepare_node(node)
        if node["task"] not in tasks:
            raise ToolError("unknown task %s" % node["task"])
        if "after" in patch or replace:
            missing = [dependency for dependency in node["after"] if dependency not in nodes]
            if missing:
                raise ToolError("node.after names unknown node(s): %s" % ", ".join(missing))
        changed = _apply_node_change(tree, tasks, nodes, node_id, before, node)
        _write_changed(workspace, tree, tasks, nodes, changed)
        return node, changed


def update_node(args: Any) -> int:
    root = _root(args)
    node, changed = _update_node(root, args.id, _object_input(args.input, root))
    print(json.dumps({"updated": node["id"], "affected": sorted(code for kind, code in changed if kind == "node")}))
    return 0


def edit_node(args: Any) -> int:
    root = _root(args)
    if args.input:
        edited = _object_input(args.input, root)
        base = None
    else:
        if not args.editor:
            raise ToolError("node edit needs --input or --editor")
        _, _, nodes = _snapshot(root)
        node_id = safe_id(args.id, "node.id")
        if node_id not in nodes:
            raise ToolError("unknown node %s" % node_id)
        base = deepcopy(nodes[node_id])
        descriptor, temporary = tempfile.mkstemp(prefix="better-plan-node-", suffix=".json")
        os.close(descriptor)
        temporary_path = Path(temporary)
        try:
            write_json(temporary_path, base)
            command = shlex.split(args.editor) + [str(temporary_path)]
            completed = subprocess.run(command, check=False)
            if completed.returncode != 0:
                raise ToolError("editor exited with status %d" % completed.returncode)
            edited = read_json(temporary_path)
            if not isinstance(edited, dict):
                raise ToolError("edited Node must be a JSON object")
        finally:
            if temporary_path.exists():
                temporary_path.unlink()
    node, changed = _update_node(root, args.id, edited, replace=True, edit_base=base)
    print(json.dumps({"edited": node["id"], "affected": sorted(code for kind, code in changed if kind == "node")}))
    return 0


def move_node(args: Any) -> int:
    patch: dict[str, Any] = {}
    if args.task:
        patch["task"] = args.task
    if args.after is not None:
        patch["after"] = args.after
    if not patch:
        raise ToolError("node move needs --task or --after")
    node, changed = _update_node(_root(args), args.id, patch)
    print(json.dumps({"moved": node["id"], "affected": sorted(code for kind, code in changed if kind == "node")}))
    return 0


def _remove_node_object(
    workspace: CurrentWorkspace,
    tree: dict[str, Any],
    tasks: Mapping[str, dict[str, Any]],
    nodes: dict[str, dict[str, Any]],
    node_id: str,
    disconnect: bool,
) -> tuple[list[str], set[tuple[str, str]]]:
    node = nodes[node_id]
    parents = list(node.get("after") or [])
    children = [code for code, value in nodes.items() if node_id in (value.get("after") or [])]
    affected_before = descendants(nodes, [node_id])
    changed: set[tuple[str, str]] = set(mark_checks_pending(tree, tasks, nodes, affected_before))
    changed.update(_mark_deliveries(tree, tasks, nodes, affected_before, "node", node_id, "membership_changed"))
    del nodes[node_id]
    for child in children:
        values = [item for item in nodes[child].get("after") or [] if item != node_id]
        if not disconnect:
            values.extend(parent for parent in parents if parent != child)
        nodes[child]["after"] = list(dict.fromkeys(values))
        changed.add(("node", child))
    if children:
        changed.update(_mark_change(tree, tasks, nodes, children, "node", node_id, "dependency_changed"))
    workspace.remove_node(node_id)
    return children, changed


def remove_node(args: Any) -> int:
    root = _root(args)
    workspace = CurrentWorkspace(root)
    with workspace_lock(root):
        tree, tasks, nodes = workspace.load()
        node_id = safe_id(args.id, "node.id")
        if node_id not in nodes:
            raise ToolError("unknown node %s" % node_id)
        children, changed = _remove_node_object(workspace, tree, tasks, nodes, node_id, args.disconnect)
        _write_changed(workspace, tree, tasks, nodes, changed)
    print(json.dumps({"removed": node_id, "reconnected": children if not args.disconnect else []}))
    return 0


def show_node(args: Any) -> int:
    tree, tasks, nodes = _snapshot(_root(args))
    node_id = safe_id(args.id, "node.id")
    if node_id not in nodes:
        raise ToolError("unknown node %s" % node_id)
    node = dict(nodes[node_id])
    task = tasks.get(str(node.get("task")))
    payload = {
        "tree": {key: tree.get(key) for key in ("id", "title", "goal", "success", "delivery_policy")},
        "requirements": {"tree": tree.get("requirements") or [], "task": (task or {}).get("requirements") or []},
        "task": {key: (task or {}).get(key) for key in ("id", "title", "outcome", "requirements", "draft_pr", "integration_owner", "delivery")},
        "node": node,
        "dependencies": [nodes[code] for code in node.get("after") or [] if code in nodes],
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def _worker_context(
    tree: Mapping[str, Any],
    task: Mapping[str, Any],
    node: Mapping[str, Any],
    dependencies: Iterable[Mapping[str, Any]],
    phase: str,
) -> dict[str, Any]:
    result = {
        "phase": phase,
        "tree": {key: tree.get(key) for key in ("id", "title", "goal", "success", "delivery_policy")},
        "task": {key: task.get(key) for key in ("id", "title", "outcome", "requirements", "draft_pr", "integration_owner", "delivery")},
        "requirements": {"tree": tree.get("requirements") or [], "task": task.get("requirements") or []},
        "node": {"id": node.get("id"), "title": node.get("title"), "outcome": node.get("outcome"), "contract": node.get("contract") or {}, "commit": node.get("commit")},
        "dependencies": [
            {key: dependency.get(key) for key in ("id", "title", "status", "result", "commit")}
            for dependency in dependencies
        ],
        "review": node.get("review") or [],
    }
    if phase == "finish":
        result["confirmation_prompt"] = "Confirm how each shared and Task requirement was followed, and record any exception. This does not gate completion."
    return result


def start_node(args: Any) -> int:
    root = _root(args)
    workspace = CurrentWorkspace(root)
    with workspace_lock(root):
        tree, tasks, nodes = workspace.load()
        node_id = safe_id(args.id, "node.id")
        if node_id not in nodes:
            raise ToolError("unknown node %s" % node_id)
        before = deepcopy(nodes[node_id])
        node = deepcopy(before)
        node["status"] = "running"
        changed = _apply_node_change(tree, tasks, nodes, node_id, before, node)
        _write_changed(workspace, tree, tasks, nodes, changed)
        task = tasks.get(str(nodes[node_id].get("task")), {"requirements": []})
        dependencies = [nodes[code] for code in nodes[node_id].get("after") or [] if code in nodes]
        payload = _worker_context(tree, task, nodes[node_id], dependencies, "start")
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def finish_node(args: Any) -> int:
    root = _root(args)
    workspace = CurrentWorkspace(root)
    result = _object_input(args.result, root) if args.result else ({"summary": args.summary} if args.summary else {})
    with workspace_lock(root):
        tree, tasks, nodes = workspace.load()
        node_id = safe_id(args.id, "node.id")
        if node_id not in nodes:
            raise ToolError("unknown node %s" % node_id)
        before = deepcopy(nodes[node_id])
        node = deepcopy(before)
        node["status"] = "completed"
        node["result"] = result
        if args.commit:
            node["commit"] = args.commit
        changed = _apply_node_change(tree, tasks, nodes, node_id, before, node)
        _write_changed(workspace, tree, tasks, nodes, changed)
        task = tasks.get(str(nodes[node_id].get("task")), {"requirements": []})
        dependencies = [nodes[code] for code in nodes[node_id].get("after") or [] if code in nodes]
        payload = _worker_context(tree, task, nodes[node_id], dependencies, "finish")
        payload["result"] = result
        payload["commit_reference"] = nodes[node_id].get("commit")
        if nodes[node_id].get("commit"):
            payload["commit_reminder"] = (
                "Scoped Node commit recorded as %s. Keep that commit limited to this Node's changes."
                % nodes[node_id]["commit"]
            )
        else:
            payload["commit_reminder"] = (
                "Create one scoped commit containing this Node's changes, then record its current "
                "reference with node update or node finish --commit. This reminder does not gate completion."
            )
        owned = task_nodes(nodes, str(nodes[node_id].get("task")))
        ready_for_integration = bool(owned) and all(nodes[code].get("status") == "completed" for code in owned)
        payload["ready_for_integration"] = ready_for_integration
        payload["integration_owner"] = task.get("integration_owner")
        if ready_for_integration:
            payload["integration_reminder"] = (
                "All Node execution is complete. Hand off to the Task's designated integration owner "
                "to assemble commits, verify the integrated outcome, maintain the Draft PR and record "
                "task finish. Completion order does not assign ownership. Keep the PR Draft; Ready, "
                "merge, installation and live acceptance require the project's separate authorization."
            )
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def finish_delivery(args: Any) -> int:
    root = _root(args)
    workspace = CurrentWorkspace(root)
    result = _object_input(args.result, root) if args.result else {"summary": args.summary}
    with workspace_lock(root):
        tree, tasks, nodes = workspace.load()
        task_id = getattr(args, "id", None)
        if task_id is not None and task_id not in tasks:
            raise ToolError("unknown task %s" % task_id)
        container = tasks[task_id] if task_id is not None else tree
        container["delivery"] = {"result": result, "review": []}
        changed = {("task", task_id)} if task_id is not None else {("tree", tree["id"])}
        if task_id is not None:
            changed.update(_mark_deliveries(tree, tasks, nodes, [], "task", task_id, "delivery_recorded"))
        _write_changed(workspace, tree, tasks, nodes, changed)
        annotate_check_runs(root, tree, tasks, nodes)
        payload = export_payload(tree, tasks, nodes)
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def review_done(args: Any) -> int:
    root = _root(args)
    workspace = CurrentWorkspace(root)
    with workspace_lock(root):
        _, _, nodes = workspace.load()
        node_id = safe_id(args.id, "node.id")
        if node_id not in nodes:
            raise ToolError("unknown node %s" % node_id)
        removed = clear_review(nodes[node_id], args.source_kind, args.source_id)
        workspace.write_node(nodes[node_id])
    print(json.dumps({"node": node_id, "cleared": removed, "remaining": nodes[node_id].get("review") or []}))
    return 0


def change_edge(args: Any, add: bool) -> int:
    root = _root(args)
    workspace = CurrentWorkspace(root)
    predecessor = safe_id(args.predecessor, "edge.predecessor")
    successor = safe_id(args.successor, "edge.successor")
    with workspace_lock(root):
        tree, tasks, nodes = workspace.load()
        if predecessor not in nodes or successor not in nodes:
            raise ToolError("edge names unknown nodes")
        values = list(nodes[successor].get("after") or [])
        before = list(values)
        if add and predecessor not in values:
            values.append(predecessor)
        if not add:
            values = [item for item in values if item != predecessor]
        nodes[successor]["after"] = values
        changed: set[tuple[str, str]] = set()
        if values != before:
            changed.add(("node", successor))
            changed.update(_mark_change(tree, tasks, nodes, [successor], "node", predecessor, "dependency_changed"))
        _write_changed(workspace, tree, tasks, nodes, changed)
    print(json.dumps({"edge": [predecessor, successor], "present": add, "affected": sorted(code for kind, code in changed if kind == "node")}))
    return 0


def add_edge(args: Any) -> int:
    return change_edge(args, True)


def remove_edge(args: Any) -> int:
    return change_edge(args, False)


def _subtree_nodes(
    nodes: Mapping[str, Mapping[str, Any]], entries: Iterable[str], exits: Iterable[str] = ()
) -> list[str]:
    """Return a branch in O(V + E), preserving external joins by default."""

    forward, reverse = adjacency(nodes)
    entry_list = list(dict.fromkeys(entries))
    exit_set = set(exits)
    included = set(entry_list)
    ordered = list(entry_list)
    queue = deque(entry_list)
    remaining = {code: len(parents) for code, parents in reverse.items()}
    while queue:
        current = queue.popleft()
        if current in exit_set:
            continue
        for child in forward[current]:
            if child in included:
                continue
            remaining[child] -= 1
            if remaining[child] > 0 and child not in exit_set:
                continue
            included.add(child)
            ordered.append(child)
            queue.append(child)
    return ordered


def _subtree_boundaries(args: Any, nodes: Mapping[str, Mapping[str, Any]]) -> tuple[list[str], list[str]]:
    entries = list(dict.fromkeys([safe_id(args.id, "subtree.id")] + [safe_id(item, "subtree.entry") for item in (getattr(args, "entry", None) or [])]))
    exits = list(dict.fromkeys(safe_id(item, "subtree.exit") for item in (getattr(args, "exit", None) or [])))
    missing = [code for code in entries + exits if code not in nodes]
    if missing:
        raise ToolError("subtree boundary names unknown node(s): %s" % ", ".join(missing))
    return entries, exits


def _subtree_exit_nodes(
    nodes: Mapping[str, Mapping[str, Any]], selected: Iterable[str], explicit: Iterable[str]
) -> list[str]:
    selected_set = set(selected)
    explicit_list = [code for code in explicit if code in selected_set]
    if explicit_list:
        return explicit_list
    forward, _ = adjacency(nodes)
    return [code for code in selected if not selected_set.intersection(forward[code])]


def _requested_nodes(values: Iterable[str] | None, nodes: Mapping[str, Any], field: str) -> list[str]:
    result = list(dict.fromkeys(safe_id(item, field) for item in (values or [])))
    missing = [item for item in result if item not in nodes]
    if missing:
        raise ToolError("%s names unknown node(s): %s" % (field, ", ".join(missing)))
    return result


def show_subtree(args: Any) -> int:
    _, _, nodes = _snapshot(_root(args))
    entries, exits_requested = _subtree_boundaries(args, nodes)
    selected = _subtree_nodes(nodes, entries, exits_requested)
    forward, _ = adjacency(nodes)
    exits = sorted({child for code in selected for child in forward[code] if child not in selected})
    print(json.dumps({"entries": entries, "nodes": selected, "external_dependencies": {entry: [code for code in nodes[entry].get("after") or [] if code not in selected] for entry in entries}, "exits": exits}, indent=2, ensure_ascii=False))
    return 0


def attach_subtree(args: Any) -> int:
    root = _root(args)
    workspace = CurrentWorkspace(root)
    with workspace_lock(root):
        tree, tasks, nodes = workspace.load()
        entries, exits = _subtree_boundaries(args, nodes)
        selected = _subtree_nodes(nodes, entries, exits)
        exit_nodes = _subtree_exit_nodes(nodes, selected, exits)
        after = _requested_nodes(args.after, nodes, "subtree.after")
        before = _requested_nodes(args.before, nodes, "subtree.before")
        if not after and not before:
            raise ToolError("subtree attach needs --after or --before")
        changed: set[tuple[str, str]] = set()
        edges: list[dict[str, Any]] = []
        for entry in entries:
            original = list(nodes[entry].get("after") or [])
            updated = list(dict.fromkeys(original + after))
            if updated != original:
                nodes[entry]["after"] = updated
                changed.add(("node", entry))
                edges.extend({"action": "add", "from": parent, "to": entry} for parent in after if parent not in original)
        for successor in before:
            values = list(nodes[successor].get("after") or [])
            updated = list(dict.fromkeys(values + exit_nodes))
            if updated != values:
                nodes[successor]["after"] = updated
                changed.add(("node", successor))
                edges.extend({"action": "add", "from": endpoint, "to": successor} for endpoint in exit_nodes if endpoint not in values)
        if changed:
            changed_endpoints = [code for kind, code in changed if kind == "node"]
            changed.update(_mark_change(tree, tasks, nodes, changed_endpoints, "node", entries[0], "dependency_changed"))
        _write_changed(workspace, tree, tasks, nodes, changed)
    print(json.dumps({"attached": selected, "entries": entries, "exits": exit_nodes, "edges": edges, "changed": sorted("%s:%s" % item for item in changed), "affected": sorted(code for kind, code in changed if kind == "node")}))
    return 0


def move_subtree(args: Any) -> int:
    root = _root(args)
    workspace = CurrentWorkspace(root)
    with workspace_lock(root):
        tree, tasks, nodes = workspace.load()
        entries, exits = _subtree_boundaries(args, nodes)
        selected_list = _subtree_nodes(nodes, entries, exits)
        selected = set(selected_list)
        exit_nodes = _subtree_exit_nodes(nodes, selected_list, exits)
        replacement = _requested_nodes(args.after, nodes, "subtree.after") if args.after is not None else None
        before = _requested_nodes(args.before, nodes, "subtree.before") if args.before is not None else None
        if replacement is None and before is None:
            raise ToolError("subtree move needs --after or --before")
        changed: set[tuple[str, str]] = set()
        edges: list[dict[str, Any]] = []
        if replacement is not None:
            for entry in entries:
                original = list(nodes[entry].get("after") or [])
                internal = [item for item in original if item in selected]
                updated = list(dict.fromkeys(internal + replacement))
                if updated != original:
                    nodes[entry]["after"] = updated
                    changed.add(("node", entry))
                    edges.extend({"action": "remove", "from": parent, "to": entry} for parent in original if parent not in internal and parent not in replacement)
                    edges.extend({"action": "add", "from": parent, "to": entry} for parent in replacement if parent not in original)
        if before is not None:
            forward, _ = adjacency(nodes)
            old_successors = sorted({child for code in exit_nodes for child in forward[code] if child not in selected})
            for successor in old_successors:
                original = list(nodes[successor].get("after") or [])
                updated = [item for item in original if item not in exit_nodes]
                if updated != original:
                    nodes[successor]["after"] = updated
                    changed.add(("node", successor))
                    edges.extend({"action": "remove", "from": parent, "to": successor} for parent in original if parent in exit_nodes)
            for successor in before:
                original = list(nodes[successor].get("after") or [])
                updated = list(dict.fromkeys(original + exit_nodes))
                if updated != original:
                    nodes[successor]["after"] = updated
                    changed.add(("node", successor))
                    edges.extend({"action": "add", "from": endpoint, "to": successor} for endpoint in exit_nodes if endpoint not in original)
        if changed:
            changed_endpoints = [code for kind, code in changed if kind == "node"]
            changed.update(_mark_change(tree, tasks, nodes, changed_endpoints, "node", entries[0], "dependency_changed"))
        _write_changed(workspace, tree, tasks, nodes, changed)
    print(json.dumps({"moved": selected_list, "entries": entries, "exits": exit_nodes, "edges": edges, "changed": sorted("%s:%s" % item for item in changed), "affected": sorted(code for kind, code in changed if kind == "node")}))
    return 0


def _remove_subtree_objects(
    workspace: CurrentWorkspace,
    tree: dict[str, Any],
    tasks: Mapping[str, dict[str, Any]],
    nodes: dict[str, dict[str, Any]],
    selected: Iterable[str],
    source_id: str,
    source_kind: str = "node",
) -> set[tuple[str, str]]:
    selected_set = set(selected)
    forward, reverse = adjacency(nodes)
    changed: set[tuple[str, str]] = set(
        mark_checks_pending(tree, tasks, nodes, descendants(nodes, selected_set))
    )
    changed.update(_mark_deliveries(tree, tasks, nodes, descendants(nodes, selected_set), source_kind, source_id, "membership_changed"))
    boundary = sorted({child for code in selected_set for child in forward[code] if child not in selected_set})
    for child in boundary:
        removed_parents = [item for item in nodes[child].get("after") or [] if item in selected_set]
        queue = deque(removed_parents)
        visited = set(removed_parents)
        sources: list[str] = []
        while queue:
            current = queue.popleft()
            for parent in reverse[current]:
                if parent in selected_set:
                    if parent not in visited:
                        visited.add(parent)
                        queue.append(parent)
                elif parent not in sources:
                    sources.append(parent)
        values = [item for item in nodes[child].get("after") or [] if item not in selected_set]
        values.extend(parent for parent in sources if parent != child)
        nodes[child]["after"] = list(dict.fromkeys(values))
    for code in selected_set:
        nodes.pop(code, None)
        workspace.remove_node(code)
    changed.update(("node", code) for code in boundary)
    if boundary:
        changed.update(_mark_change(tree, tasks, nodes, boundary, source_kind, source_id, "dependency_changed"))
    return changed


def remove_subtree(args: Any) -> int:
    root = _root(args)
    workspace = CurrentWorkspace(root)
    with workspace_lock(root):
        tree, tasks, nodes = workspace.load()
        entries, exits = _subtree_boundaries(args, nodes)
        selected = _subtree_nodes(nodes, entries, exits)
        changed = _remove_subtree_objects(workspace, tree, tasks, nodes, selected, entries[0])
        _write_changed(workspace, tree, tasks, nodes, changed)
    print(json.dumps({"removed": selected, "changed": sorted("%s:%s" % item for item in changed)}))
    return 0


def list_checks(args: Any) -> int:
    tree, tasks, nodes = _snapshot(_root(args))
    values = flattened_checks(tree, tasks, nodes)
    if args.node:
        values = [item for item in values if args.node in item["covers"]]
    print(json.dumps(values, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def _owner(value: str, tree: Mapping[str, Any], tasks: Mapping[str, Any], nodes: Mapping[str, Any]) -> tuple[str, str, dict[str, Any]]:
    if value == "tree":
        return "tree", str(tree["id"]), tree  # type: ignore[return-value]
    if ":" not in value:
        raise ToolError("owner must be tree, task:<id>, or node:<id>")
    kind, code = value.split(":", 1)
    if kind == "task" and code in tasks:
        return kind, code, tasks[code]
    if kind == "node" and code in nodes:
        return kind, code, nodes[code]
    raise ToolError("unknown check owner %s" % value)


def _find_check(container: dict[str, Any], check_id: str) -> dict[str, Any]:
    matches = [check for check in container.get("checks") or [] if check.get("id") == check_id]
    if not matches:
        raise ToolError("unknown check %s" % check_id)
    return matches[0]


def _write_owner(workspace: CurrentWorkspace, kind: str, container: dict[str, Any]) -> None:
    if kind == "tree":
        workspace.write_tree(container)
    elif kind == "task":
        workspace.write_task(container)
    else:
        workspace.write_node(container)


def _require_recovered(check):
    if check.get("running") or check.get("run_id"):
        raise ToolError("check execution was interrupted; result unknown. Confirm leftover commands "
                        "have ended, then use checks recover before running or recording a result")


def run_check(args: Any) -> int:
    root = _root(args)
    workspace = CurrentWorkspace(root)
    with check_lock(root, args.owner, args.id):
        with workspace_lock(root):
            tree, tasks, nodes = workspace.load()
            kind, owner_id, container = _owner(args.owner, tree, tasks, nodes)
            check = _find_check(container, args.id)
            _require_recovered(check)
            run_id = uuid.uuid4().hex
            check.update(running=True, run_id=run_id, dirty=False, pending=True)
            _write_owner(workspace, kind, container)
            commands = list(check.get("commands") or [])
        # Exceptions deliberately leave the unresolved execution marker for explicit recovery.
        passed, receipts, diagnostics = run_commands_with_diagnostics(Path(args.cwd).resolve() if args.cwd else root, commands)
        with workspace_lock(root):
            tree, tasks, nodes = workspace.load()
            try:
                kind, owner_id, container = _owner(args.owner, tree, tasks, nodes)
                check = _find_check(container, args.id)
            except ToolError:
                raise ToolError("check or owner was removed during execution; result not recorded")
            if check.get("run_id") != run_id:
                raise ToolError("check was replaced during execution; result not recorded")
            dirty = bool(check.get("dirty"))
            result = {"status": "passed" if passed else "failed", "details": receipts}
            changed = {(kind, owner_id)}
            if not passed and result != check.get("result"):
                changed.update(_check_delivery_change(tree, tasks, nodes, kind, owner_id, check, "check_failed"))
            check.update(running=False, run_id=None, pending=dirty, result=result)
            _write_changed(workspace, tree, tasks, nodes, changed)
        payload = {"id": args.id, "passed": passed, "pending": dirty, "result": result, "diagnostics": diagnostics}
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if passed else 1


def record_check(args: Any) -> int:
    root = _root(args)
    workspace = CurrentWorkspace(root)
    result = _object_input(args.result, root) if args.result else {"status": args.status, "summary": args.summary}
    with check_lock(root, args.owner, args.id):
        with workspace_lock(root):
            tree, tasks, nodes = workspace.load()
            kind, owner_id, container = _owner(args.owner, tree, tasks, nodes)
            check = _find_check(container, args.id)
            _require_recovered(check)
            changed = {(kind, owner_id)}
            if result.get("status") == "failed" and result != check.get("result"):
                changed.update(_check_delivery_change(tree, tasks, nodes, kind, owner_id, check, "check_failed"))
            check.update(running=False, run_id=None, dirty=False, pending=False, result=result)
            _write_changed(workspace, tree, tasks, nodes, changed)
    print(json.dumps({"id": args.id, "recorded": result}, ensure_ascii=False))
    return 0


def recover_check(args: Any) -> int:
    root = _root(args)
    workspace = CurrentWorkspace(root)
    with check_lock(root, args.owner, args.id):
        with workspace_lock(root):
            tree, tasks, nodes = workspace.load()
            kind, owner_id, container = _owner(args.owner, tree, tasks, nodes)
            check = _find_check(container, args.id)
            interrupted = check.get("running") or check.get("run_id")
            if interrupted:
                check.update(running=False, run_id=None, dirty=False, pending=True)
                changed = {(kind, owner_id)}
                changed.update(_check_delivery_change(tree, tasks, nodes, kind, owner_id, check, "check_interrupted"))
                _write_changed(workspace, tree, tasks, nodes, changed)
    print(json.dumps({"id": args.id, "recovered": bool(interrupted),
                      "note": "Caller confirms leftover commands have ended. No process was killed and no result was declared passed."}))
    return 0


def archive_history(args: Any) -> int:
    root = _root(args)
    workspace = CurrentWorkspace(root)
    content_path = Path(args.input).expanduser()
    if not content_path.is_absolute() and not content_path.is_file():
        content_path = root / content_path
    if not content_path.is_file():
        raise ToolError("history input is missing at %s" % content_path)
    content = content_path.read_text(encoding="utf-8")
    archive_id = safe_id(args.id or (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + uuid.uuid4().hex[:8]), "history.id")
    entry: dict[str, Any] = {
        "schema": "better-plan.history-entry",
        "id": archive_id,
        "kind": args.kind,
        "source": args.source,
        "content": content,
    }
    if args.summary:
        entry["summary"] = args.summary
    attachments = []
    for name in args.attach or []:
        path = Path(name).expanduser()
        if not path.is_absolute():
            path = root / path
        if not path.is_file():
            raise ToolError("history attachment is missing at %s" % path)
        try:
            relative = path.resolve().relative_to(root).as_posix()
        except ValueError:
            relative = path.name
        attachments.append(
            {
                "path": relative,
                "encoding": "base64",
                "content": base64.b64encode(path.read_bytes()).decode("ascii"),
            }
        )
    if attachments:
        entry["attachments"] = attachments
    destination = workspace.history_path / (archive_id + ".json")
    with workspace_lock(root):
        if not workspace.tree_path.is_file() and not (root / "Programme.json").is_file():
            raise ToolError("no Better Plan Tree or Programme at %s" % root)
        if destination.exists():
            raise ToolError("history archive %s already exists" % archive_id)
        write_json(destination, entry)
    print(json.dumps({"archived": archive_id, "path": str(destination)}))
    return 0


def list_history(args: Any) -> int:
    workspace = CurrentWorkspace(_root(args))
    if not workspace.tree_path.is_file() and not (workspace.root / "Programme.json").is_file():
        raise ToolError("no Better Plan Tree or Programme at %s" % workspace.root)
    values = []
    if workspace.history_path.is_dir():
        for path in sorted(workspace.history_path.glob("*.json")):
            entry = read_json(path)
            values.append({key: entry.get(key) for key in ("id", "kind", "source", "summary")})
    print(json.dumps(values, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def show_history(args: Any) -> int:
    workspace = CurrentWorkspace(_root(args))
    path = workspace.history_path / (safe_id(args.id, "history.id") + ".json")
    if not path.is_file():
        raise ToolError("unknown history archive %s" % args.id)
    entry = read_json(path)
    if args.attachment:
        for attachment in entry.get("attachments") or []:
            if attachment.get("path") == args.attachment:
                if attachment.get("encoding") != "base64":
                    raise ToolError("attachment encoding is unsupported")
                sys.stdout.flush()
                sys.stdout.buffer.write(base64.b64decode(attachment.get("content") or ""))
                return 0
        raise ToolError("archive has no attachment %s" % args.attachment)
    print(json.dumps(entry, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def search_history(args: Any) -> int:
    workspace = CurrentWorkspace(_root(args))
    if not workspace.tree_path.is_file() and not (workspace.root / "Programme.json").is_file():
        raise ToolError("no Better Plan Tree or Programme at %s" % workspace.root)
    needle = args.query.casefold()
    matches = []
    if workspace.history_path.is_dir():
        for path in sorted(workspace.history_path.glob("*.json")):
            entry = read_json(path)
            haystack = json.dumps(entry, ensure_ascii=False).casefold()
            attachment_text = []
            for attachment in entry.get("attachments") or []:
                if attachment.get("encoding") != "base64":
                    continue
                try:
                    attachment_text.append(
                        base64.b64decode(attachment.get("content") or "").decode("utf-8")
                    )
                except (ValueError, UnicodeDecodeError):
                    continue
            haystack += "\n".join(attachment_text).casefold()
            if needle in haystack:
                matches.append({key: entry.get(key) for key in ("id", "kind", "source", "summary")})
    print(json.dumps(matches, indent=2, ensure_ascii=False, sort_keys=True))
    return 0
