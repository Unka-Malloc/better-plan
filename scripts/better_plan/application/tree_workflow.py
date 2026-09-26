"""Agent-neutral CLI workflow for the single Checkpoints Tree.

These commands expose the tree directly.  They do not read, write, or require a
Plan, Manifest, Designer session, authorization receipt, dispatch binding,
host adapter, role, model, or provider.  Any caller may initialize, inspect,
start, block, cancel, or reset a Node; the tree is the only state authority.

Completion is the one place where the tool does not take a caller's word: a Node
that declares ``contract.commands`` is finished by ``tree-verify``, which runs
those commands itself and records the receipts it observed.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping
import hashlib
import json
import sys

from ..domain.checkpoints_tree import (
    NODE_COMMANDS_KEY,
    TREE_NAME,
    append_history,
    apply_operations,
    canonical_json,
    derive_task_status,
    iter_nodes,
    iter_tasks,
    new_tree,
    next_executor,
    node_commands,
    node_executors,
    node_index,
    readiness_report,
    ready_codes,
    render_tree,
    role_nodes,
    shape_issues,
    shared_resource_groups,
    status_payload,
    transition,
    tried_executors,
    validate_tree,
)
from ..domain.models import ToolError
from ..infrastructure.command_runner import run_commands_with_diagnostics
from ..infrastructure.workspace import read_json, workspace_lock, write_json


def tree_path(root: Path) -> Path:
    root = root.expanduser()
    if root.is_file():
        return root.resolve()
    return (root / TREE_NAME).resolve()


def tree_root(value: Any) -> Path:
    """Resolve a workspace root or a direct Tree.json path."""

    path = Path(str(value or ".")).expanduser()
    if path.is_file():
        return path.resolve().parent
    if not path.exists():
        return path.resolve()
    current = path.resolve()
    if (current / TREE_NAME).is_file():
        return current
    while current != current.parent:
        if (current / TREE_NAME).is_file():
            return current
        current = current.parent
    return path.resolve()


def load_tree(root: Path) -> dict[str, Any]:
    path = tree_path(root)
    if not path.is_file():
        raise ToolError("no Checkpoints Tree at %s" % path.name)
    value = read_json(path)
    if not isinstance(value, dict):
        raise ToolError("Tree.json must be an object")
    issues = validate_tree(value)
    if issues:
        raise ToolError("invalid Checkpoints Tree: %s" % "; ".join(issues[:6]))
    return value


def save_tree(root: Path, tree: dict[str, Any]) -> None:
    issues = validate_tree(tree)
    if issues:
        raise ToolError("refusing to write an invalid Checkpoints Tree: %s" % "; ".join(issues[:6]))
    write_json(tree_path(root), tree)


@contextmanager
def locked_tree(root: Path, *, initializing: bool = False) -> Iterator[None]:
    """Take the workspace lock without ever creating a workspace by accident.

    Only `tree-init` creates one. Every other command refuses a directory that
    holds no Tree before it could leave a lock file beside nothing.
    """

    if not initializing and not tree_path(root).is_file():
        raise ToolError("no Checkpoints Tree at %s" % TREE_NAME)
    with workspace_lock(root, create=initializing):
        yield


def _read_batch_text(value: str, root: Path) -> str:
    if value == "-":
        return sys.stdin.read()
    path = Path(value).expanduser()
    if not path.is_absolute() and not path.is_file():
        path = root / path
    if not path.is_file():
        raise ToolError("batch input is missing at %s" % path.name)
    return path.read_text(encoding="utf-8")


def _batch_payload(value: Any) -> tuple[list[Any], str | None, str | None, int | None]:
    if isinstance(value, list):
        return value, None, None, None
    if not isinstance(value, dict):
        raise ToolError("batch input must be a JSON array or object")
    allowed = {"operations", "batch_id", "actor", "base_revision"}
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ToolError("unknown batch field(s): %s" % ", ".join(unknown))
    operations = value.get("operations")
    batch_id = value.get("batch_id")
    actor = value.get("actor")
    base_revision = value.get("base_revision")
    if not isinstance(operations, list):
        raise ToolError("batch.operations must be an array")
    if batch_id is not None and not isinstance(batch_id, str):
        raise ToolError("batch.batch_id must be a string")
    if actor is not None and not isinstance(actor, str):
        raise ToolError("batch.actor must be a string")
    if base_revision is not None and type(base_revision) is not int:
        raise ToolError("batch.base_revision must be an integer")
    return operations, batch_id, actor, base_revision


def apply_batch(args: Any) -> int:
    root = tree_root(args.root)
    try:
        payload = json.loads(_read_batch_text(args.input, root))
    except json.JSONDecodeError as exc:
        raise ToolError("batch input is not valid JSON: %s" % exc.msg)
    operations, batch_id, actor, base_revision = _batch_payload(payload)
    with locked_tree(root):
        tree = load_tree(root)
        receipt = apply_operations(
            tree,
            operations,
            actor=actor,
            batch_id=batch_id,
            base_revision=base_revision,
            dry_run=getattr(args, "dry_run", False),
        )
        if not getattr(args, "dry_run", False):
            save_tree(root, tree)
    if getattr(args, "json", False):
        print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    elif receipt.get("dry_run"):
        print(
            "dry-run ok: %(operations)s operations, next generation %(next_generation)s, ready=%(ready)s"
            % receipt
        )
    elif receipt.get("idempotent"):
        print("batch already applied: %s" % receipt.get("batch_id"))
    else:
        print(
            "applied %(operations)s operations, generation %(generation)s, ready=%(ready)s"
            % receipt
        )
    return 0


def init_tree(args: Any) -> int:
    root = tree_root(args.root)
    path = tree_path(root)
    replace = bool(getattr(args, "replace", False))
    reason = getattr(args, "reason", None)
    if replace and not reason:
        raise ToolError("--replace requires --reason so the replacement is auditable")
    if path.exists() and not replace:
        raise ToolError("Tree.json already exists; edit the existing tree instead")
    if not path.exists() and not getattr(args, "title", None):
        raise ToolError("tree-init needs --title")
    with locked_tree(root, initializing=not path.exists()):
        previous = load_tree(root) if path.exists() else None
        if previous is None and path.exists():
            raise ToolError("Tree.json already exists; edit the existing tree instead")
        tree_id = getattr(args, "id", None) or (previous or {}).get("id") or "TREE-001"
        title = getattr(args, "title", None) or (previous or {}).get("title")
        tree = new_tree(tree_id, title)
        if previous is not None:
            # A replacement is a deliberate re-authoring. The identity, the creation
            # time, the generation, and the whole audit trail carry forward, so the
            # work that led here stays readable even though its graph is gone.
            tree["created_at"] = previous.get("created_at", tree["created_at"])
            tree["history"] = previous.get("history", [])
            tree["generation"] = int(previous.get("generation", 0) or 0) + 1
            append_history(
                tree,
                action="replace",
                note=reason,
                details={
                    "replaced": {
                        "generation": previous.get("generation", 0),
                        "tasks": len(iter_tasks(previous)),
                        "nodes": len(iter_nodes(previous)),
                        "sha256": hashlib.sha256(
                            canonical_json(previous).encode("utf-8")
                        ).hexdigest(),
                    }
                },
            )
        save_tree(root, tree)
    print(json.dumps({"created": True, "path": str(path), "id": tree["id"]}, sort_keys=True))
    return 0


def _executor_suffix(item: Mapping[str, Any]) -> str:
    """Show the executor to use next, what is still behind it, and what is spent."""

    chain = item.get("executors") or []
    if not chain:
        return ""
    upcoming = item.get("next_executor")
    tried = [name for name in (item.get("tried_executors") or [])]
    if not upcoming:
        return "  executor: none left (tried: %s)" % ", ".join(tried)
    index = chain.index(upcoming) if upcoming in chain else 0
    remaining = [name for name in chain[index + 1 :]]
    spent = [name for name in tried if name != upcoming]
    notes: list[str] = []
    if remaining:
        notes.append("fallback: %s" % " -> ".join(remaining))
    if spent:
        notes.append("tried: %s" % ", ".join(spent))
    return "  executor: %s%s" % (upcoming, (" (%s)" % "; ".join(notes)) if notes else "")


def next_nodes(args: Any) -> int:
    root = tree_root(args.root)
    with locked_tree(root):
        tree = load_tree(root)
        blocking = shape_issues(tree)
        codes = ready_codes(tree)
        selected = codes[: int(args.limit)] if getattr(args, "limit", None) else codes
        by_code = node_index(tree)
        payload = {
            "tree": tree.get("id"),
            "status": status_payload(tree)["status"],
            "shape_issues": blocking,
            "ready": [
                {
                    "id": code,
                    "title": by_code.get(code, {}).get("title"),
                    "outcome": by_code.get(code, {}).get("outcome"),
                    "role": by_code.get(code, {}).get("role"),
                    "executors": node_executors(by_code.get(code, {})),
                    "next_executor": next_executor(tree, by_code.get(code, {})),
                    "tried_executors": tried_executors(tree, code),
                    "contract": by_code.get(code, {}).get("contract", {}),
                }
                for code in selected
            ],
            "total_ready": len(codes),
        }
        if getattr(args, "explain", False):
            payload["explain"] = readiness_report(tree)
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        for issue in blocking:
            print("not runnable yet: %s" % issue)
        if not payload["ready"]:
            print("no ready Nodes")
        for item in payload["ready"]:
            print(
                "%(id)s [%(role)s] %(title)s%(executor)s"
                % dict(item, executor=_executor_suffix(item))
            )
        if getattr(args, "explain", False):
            explain = payload["explain"]
            for group in ("waiting", "running", "failed", "blocked"):
                for item in explain[group]:
                    if group == "waiting":
                        print(
                            "%(id)s [%(status)s] waiting on %(blockers)s"
                            % item
                        )
                    else:
                        print("%(id)s [%(status)s]" % item)
    return 0


def transition_node(args: Any) -> int:
    root = tree_root(args.root)
    evidence: Any = None
    if getattr(args, "evidence", None) is not None:
        try:
            evidence = json.loads(args.evidence)
        except json.JSONDecodeError as exc:
            raise ToolError("--evidence must be valid JSON: %s" % exc.msg)
    with locked_tree(root):
        tree = load_tree(root)
        receipt = transition(
            tree,
            args.node,
            args.action,
            executor=getattr(args, "executor", None),
            evidence=evidence,
            note=getattr(args, "note", None),
        )
        save_tree(root, tree)
    if getattr(args, "json", False):
        print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    else:
        print(
            "%(node)s %(action)s -> %(status)s (tree %(tree_status)s)"
            % receipt
        )
        if receipt.get("status") in {"failed", "blocked"}:
            if receipt.get("next_executor"):
                print(
                    "next executor: %s%s"
                    % (
                        receipt["next_executor"],
                        " (already tried: %s)" % ", ".join(receipt["tried_executors"])
                        if receipt.get("tried_executors")
                        else "",
                    )
                )
            elif receipt.get("tried_executors"):
                print(
                    "every declared executor has been tried: %s"
                    % ", ".join(receipt["tried_executors"])
                )
    return 0


def _verification_root(root: Path, value: Any) -> Path:
    if value:
        candidate = Path(str(value)).expanduser()
        if not candidate.is_absolute():
            candidate = root / candidate
        return candidate.resolve()
    return root.resolve()


def verify_node(args: Any) -> int:
    """Run one Node's declared commands and complete it on tool-produced evidence.

    A Node that is still pending but has nothing left to wait for is started here, so
    the common path is one command instead of two. The commands run outside the
    workspace lock; the tree is then re-read and the Node is only completed when
    nothing moved while they ran.
    """

    root = tree_root(args.root)
    with locked_tree(root):
        tree = load_tree(root)
        node = node_index(tree).get(args.node)
        if not isinstance(node, Mapping):
            raise ToolError("unknown tree node: %s" % args.node)
        commands = node_commands(node)
        if not commands:
            raise ToolError(
                "Node %s declares no contract.%s; use `tree-transition ... complete`"
                % (args.node, NODE_COMMANDS_KEY)
            )
        if node.get("status") != "running":
            transition(
                tree,
                args.node,
                "start",
                executor=getattr(args, "executor", None),
            )
        generation = int(tree.get("generation", 0) or 0)
        save_tree(root, tree)

    project_root = _verification_root(root, getattr(args, "cwd", None))
    if not project_root.is_dir():
        raise ToolError("verification directory does not exist: %s" % project_root.name)
    passed, receipts, diagnostics = run_commands_with_diagnostics(project_root, commands)

    with locked_tree(root):
        tree = load_tree(root)
        if int(tree.get("generation", 0) or 0) != generation:
            raise ToolError("the Tree changed while verification ran; re-run tree-verify")
        node = node_index(tree).get(args.node)
        if not isinstance(node, Mapping) or node.get("status") != "running":
            raise ToolError("Node %s is no longer running; re-run tree-verify" % args.node)
        result = transition(
            tree,
            args.node,
            "complete" if passed else "fail",
            executor=getattr(args, "executor", None),
            evidence={"verified": bool(passed), "commands": receipts},
            note=None if passed else "declared commands failed",
            origin="cli",
        )
        save_tree(root, tree)

    payload = {
        "node": args.node,
        "verified": passed,
        "status": result["status"],
        "generation": result["generation"],
        "commands": receipts,
        "diagnostics": diagnostics,
        "next_executor": result.get("next_executor"),
        "tried_executors": result.get("tried_executors", []),
    }
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print(
            "%s %s -> %s (%d command(s))"
            % (
                args.node,
                "verified" if passed else "verification failed",
                result["status"],
                len(receipts),
            )
        )
        if not passed and result.get("next_executor"):
            print("next executor: %s" % result["next_executor"])
    return 0 if passed else 1


def show_tree(args: Any) -> int:
    root = tree_root(args.root)
    with locked_tree(root):
        tree = load_tree(root)
    if getattr(args, "json", False):
        derived = status_payload(tree)
        derived["task_status"] = {
            str(task.get("id")): derive_task_status(tree, task) for task in iter_tasks(tree)
        }
        derived["contention"] = shared_resource_groups(tree)
        print(json.dumps({"tree": tree, "derived": derived}, ensure_ascii=False, sort_keys=True))
        return 0
    print(render_tree(tree, details=getattr(args, "details", False)))
    return 0


def tree_status(args: Any) -> int:
    root = tree_root(args.root)
    with locked_tree(root):
        tree = load_tree(root)
    payload = status_payload(tree)
    if getattr(args, "json", False):
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print(
            "%(id)s %(title)s [%(status)s] ready=%(ready)s nodes=%(nodes)s tasks=%(tasks)s"
            % payload
        )
        for role, codes in role_nodes(tree).items():
            print("%s: %s" % (role, ", ".join(codes)))
        reported = payload.get("reported_completions")
        if reported:
            print("reported (not tool-verified) completions: %s" % ", ".join(reported))
    return 0


def validate_tree_command(args: Any) -> int:
    root = tree_root(args.root)
    path = tree_path(root)
    if not path.is_file():
        message = "no Checkpoints Tree at %s" % path.name
        if getattr(args, "json", False):
            print(json.dumps({"valid": False, "issues": [message]}))
        else:
            print("error: %s" % message)
        return 1
    try:
        tree = read_json(path)
    except ToolError as exc:
        if getattr(args, "json", False):
            print(json.dumps({"valid": False, "issues": [str(exc)]}))
        else:
            print("error: %s" % exc)
        return 1
    issues = validate_tree(tree)
    blocking = shape_issues(tree)
    contention = shared_resource_groups(tree)
    if getattr(args, "json", False):
        print(
            json.dumps(
                {
                    "valid": not issues,
                    "issues": issues,
                    "runnable": not blocking,
                    "shape_issues": blocking,
                    "contention": contention,
                }
            )
        )
    elif issues:
        for issue in issues:
            print("error: %s" % issue)
    elif blocking:
        for issue in blocking:
            print("not runnable yet: %s" % issue)
    else:
        for item in contention:
            print(
                "contention: %s shared by %s; unordered: %s"
                % (
                    item["resource"],
                    ", ".join(item["nodes"]),
                    "; ".join("%s <-> %s" % (first, second) for first, second in item["unordered"]),
                )
            )
        if not getattr(args, "quiet", False):
            print("OK: Checkpoints Tree is valid and runnable")
    return 0 if not issues else 1
