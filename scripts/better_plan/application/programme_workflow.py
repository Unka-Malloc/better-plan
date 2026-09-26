"""CLI workflow for the programme index.

A programme answers one question a single Tree cannot: which deliveries exist,
which of them a delivery waits for, and what is actually runnable now. The index
stores order only; every status this module prints is read from the Trees.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping
import json
import sys

from ..domain.programme import (
    PROGRAMME_NAME,
    apply_operations,
    delivery_order,
    new_programme,
    programme_report,
    render_programme,
    validate_programme,
)
from ..domain.checkpoints_tree import validate_tree
from ..domain.models import ToolError
from ..infrastructure.workspace import read_json, workspace_lock, write_json


def programme_path(root: Path) -> Path:
    root = root.expanduser()
    if root.is_file() and root.name == PROGRAMME_NAME:
        return root.resolve()
    return (root / PROGRAMME_NAME).resolve()


def programme_root(value: Any) -> Path:
    """Resolve a directory or a direct Programme.json path."""

    path = Path(str(value or ".")).expanduser()
    if path.is_file() and path.name == PROGRAMME_NAME:
        return path.resolve().parent
    return path.resolve()


def load_programme(root: Path) -> dict[str, Any]:
    path = programme_path(root)
    if not path.is_file():
        raise ToolError("no programme at %s" % PROGRAMME_NAME)
    value = read_json(path)
    if not isinstance(value, dict):
        raise ToolError("%s must be an object" % PROGRAMME_NAME)
    issues = validate_programme(value)
    if issues:
        raise ToolError("invalid programme: %s" % "; ".join(issues[:6]))
    return value


def require_programme(root: Path) -> None:
    """Refuse a directory that holds no programme before taking its lock."""

    if not programme_path(root).is_file():
        raise ToolError("no programme at %s" % PROGRAMME_NAME)


def save_programme(root: Path, programme: dict[str, Any]) -> None:
    issues = validate_programme(programme)
    if issues:
        raise ToolError("refusing to write an invalid programme: %s" % "; ".join(issues[:6]))
    write_json(programme_path(root), programme)


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
    if not isinstance(operations, list):
        raise ToolError("batch.operations must be an array")
    batch_id = value.get("batch_id")
    actor = value.get("actor")
    base_revision = value.get("base_revision")
    if batch_id is not None and not isinstance(batch_id, str):
        raise ToolError("batch.batch_id must be a string")
    if actor is not None and not isinstance(actor, str):
        raise ToolError("batch.actor must be a string")
    if base_revision is not None and type(base_revision) is not int:
        raise ToolError("batch.base_revision must be an integer")
    return operations, batch_id, actor, base_revision


def _read_trees(root: Path, programme: Mapping[str, Any]) -> dict[str, Any]:
    """Read every referenced Tree; a missing or unreadable one stays None."""

    trees: dict[str, Any] = {}
    for delivery in programme.get("deliveries") or []:
        if not isinstance(delivery, Mapping):
            continue
        code = delivery.get("id")
        reference = delivery.get("tree")
        if not isinstance(code, str) or not isinstance(reference, str):
            continue
        path = root / reference
        try:
            trees[code] = read_json(path) if path.is_file() else None
        except ToolError:
            trees[code] = None
    return trees


def init_programme(args: Any) -> int:
    root = programme_root(args.root)
    path = programme_path(root)
    if path.exists():
        raise ToolError("%s already exists; apply a batch to it instead" % PROGRAMME_NAME)
    with workspace_lock(root, create=True):
        if path.exists():
            raise ToolError("%s already exists; apply a batch to it instead" % PROGRAMME_NAME)
        programme = new_programme(args.id, args.title)
        save_programme(root, programme)
    print(json.dumps({"created": True, "path": str(path), "id": programme["id"]}, sort_keys=True))
    return 0


def apply_programme_batch(args: Any) -> int:
    root = programme_root(args.root)
    try:
        payload = json.loads(_read_batch_text(args.input, root))
    except json.JSONDecodeError as exc:
        raise ToolError("batch input is not valid JSON: %s" % exc.msg)
    operations, batch_id, actor, base_revision = _batch_payload(payload)
    require_programme(root)
    with workspace_lock(root, create=False):
        programme = load_programme(root)
        receipt = apply_operations(
            programme,
            operations,
            actor=actor,
            batch_id=batch_id,
            base_revision=base_revision,
            dry_run=getattr(args, "dry_run", False),
        )
        if not getattr(args, "dry_run", False):
            save_programme(root, programme)
    if getattr(args, "json", False):
        print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    elif receipt.get("dry_run"):
        print(
            "dry-run ok: %(operations)s operations, next revision %(next_revision)s, %(deliveries)s"
            % receipt
        )
    elif receipt.get("idempotent"):
        print("batch already applied: %s" % receipt.get("batch_id"))
    else:
        print(
            "applied %(operations)s operations, revision %(revision)s, %(deliveries)s"
            % receipt
        )
    return 0


def programme_status(args: Any) -> int:
    root = programme_root(args.root)
    require_programme(root)
    with workspace_lock(root, create=False):
        programme = load_programme(root)
        trees = _read_trees(root, programme)
    report = programme_report(programme, trees)
    if getattr(args, "json", False):
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0
    print(
        "%(id)s %(title)s [%(counts)s] ready=%(ready)s"
        % {
            "id": report["id"],
            "title": report["title"],
            "counts": ", ".join(
                "%s=%d" % (state, count) for state, count in sorted(report["counts"].items())
            )
            or "no deliveries",
            "ready": ", ".join(report["ready"]) or "none",
        }
    )
    for state in report["deliveries"]:
        blocked = " blocked_by=%s" % ", ".join(state["blocked_by"]) if state["blocked_by"] else ""
        print(
            "  %s [%s]%s nodes=%d ready_nodes=%s"
            % (
                state["id"],
                state["state"],
                blocked,
                state["nodes"],
                ", ".join(state["ready_nodes"]) or "none",
            )
        )
    for issue in report["issues"]:
        print("programme issue: %s" % issue)
    for item in report["contention"]:
        print(
            "contention: %s shared by %s; unordered: %s"
            % (
                item["resource"],
                ", ".join(item["owners"]),
                "; ".join("%s <-> %s" % (first, second) for first, second in item["unordered"]),
            )
        )
    return 0


def show_programme(args: Any) -> int:
    root = programme_root(args.root)
    require_programme(root)
    with workspace_lock(root, create=False):
        programme = load_programme(root)
    print(render_programme(programme))
    return 0


def programme_validate_command(args: Any) -> int:
    root = programme_root(args.root)
    path = programme_path(root)
    if not path.is_file():
        message = "no programme at %s" % PROGRAMME_NAME
        if getattr(args, "json", False):
            print(json.dumps({"valid": False, "issues": [message]}))
        else:
            print("error: %s" % message)
        return 1
    try:
        programme = read_json(path)
        issues = validate_programme(programme)
        trees = _read_trees(root, programme) if isinstance(programme, Mapping) else {}
        contention = programme_report(programme, trees)["contention"] if not issues else []
    except ToolError as exc:
        issues, contention = [str(exc)], []
    if getattr(args, "json", False):
        print(json.dumps({"valid": not issues, "issues": issues, "contention": contention}))
    elif issues:
        for issue in issues:
            print("error: %s" % issue)
    else:
        for item in contention:
            print(
                "contention: %s shared by %s" % (item["resource"], ", ".join(item["owners"]))
            )
        if not getattr(args, "quiet", False):
            print("OK: programme is valid")
    return 0 if not issues else 1
