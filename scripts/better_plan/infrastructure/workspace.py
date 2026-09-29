"""Atomic, local persistence for split Better Plan workspaces."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
import json
import os
import tempfile
import time

if os.name == "nt":
    import msvcrt as _native_lock
else:
    import fcntl as _native_lock

from ..domain.checkpoints_tree import (
    HISTORY_DIRECTORY,
    NODES_DIRECTORY,
    TASKS_DIRECTORY,
    TREE_NAME,
    TREE_SCHEMA,
    normalize_check,
    new_delivery,
    iter_checks,
    safe_id,
)
from ..domain.models import ToolError


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ToolError("invalid JSON in %s at line %d" % (path.name, exc.lineno))
    except OSError:
        raise ToolError("cannot read %s" % path.name)


def _atomic_write(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".%s." % path.name, dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_json(path: Path, value: Any) -> None:
    _atomic_write(path, json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n")


def write_text(path: Path, value: str) -> None:
    _atomic_write(path, value)


def _acquire_windows_lock(path: Path):
    try:
        stream = path.open("a+b")
        stream.seek(0)
        if stream.read(1) == b"":
            stream.write(b"0")
            stream.flush()
    except OSError as exc:
        raise ToolError("cannot open workspace lock (%s)" % exc)
    while True:
        try:
            stream.seek(0)
            _native_lock.locking(stream.fileno(), _native_lock.LK_NBLCK, 1)
            return stream
        except OSError as exc:
            if getattr(exc, "errno", None) not in (11, 13, 35, 36):
                stream.close()
                raise ToolError("cannot acquire workspace lock (%s)" % exc)
            time.sleep(0.05)


@contextmanager
def workspace_lock(root: Path, *, create: bool = False) -> Iterator[None]:
    """Hold a short workspace write lock; work and checks run outside it."""

    if create:
        root.mkdir(parents=True, exist_ok=True)
    elif not root.is_dir():
        raise ToolError("no Better Plan workspace at %s" % (root.name or str(root)))
    path = root / ".better-plan.lock"
    if os.name == "nt":
        stream = _acquire_windows_lock(path)
    else:
        stream = path.open("a+b")
        _native_lock.flock(stream.fileno(), _native_lock.LOCK_EX)
    try:
        yield
    finally:
        try:
            if os.name == "nt":
                stream.seek(0)
                _native_lock.locking(stream.fileno(), _native_lock.LK_UNLCK, 1)
            else:
                _native_lock.flock(stream.fileno(), _native_lock.LOCK_UN)
        finally:
            stream.close()


@contextmanager
def check_lock(root: Path, owner: str, check_id: str, *, probe: bool = False):
    """Nonblocking OS lock. Stable lock files must never be unlinked while in use."""
    parts = owner.split(":", 1)
    if parts[0] not in ("tree", "task", "node") or (parts[0] != "tree" and len(parts) != 2):
        raise ToolError("check owner must be tree, task:<id>, or node:<id>")
    directory = root / ".better-plan-checks" / parts[0]
    if len(parts) == 2:
        directory /= safe_id(parts[1], "check.owner")
    path = directory / (safe_id(check_id, "check.id") + ".lock")
    if probe and not path.exists():
        yield True
        return
    if not (root / TREE_NAME).is_file():
        raise ToolError("no Better Plan workspace")
    if not probe:
        directory.mkdir(parents=True, exist_ok=True)
    stream = path.open("r+b" if probe else "a+b")
    acquired = False
    try:
        if os.name == "nt":
            if not probe and os.fstat(stream.fileno()).st_size == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            try:
                _native_lock.locking(stream.fileno(), _native_lock.LK_NBLCK, 1)
                acquired = True
            except OSError as exc:
                if getattr(exc, "errno", None) not in (11, 13, 35, 36):
                    raise
        else:
            try:
                _native_lock.flock(stream.fileno(), _native_lock.LOCK_EX | _native_lock.LOCK_NB)
                acquired = True
            except BlockingIOError:
                pass
        if not acquired and not probe:
            raise ToolError("check is already running; no execution was cancelled")
        yield acquired
    finally:
        try:
            if acquired:
                if os.name == "nt":
                    stream.seek(0)
                    _native_lock.locking(stream.fileno(), _native_lock.LK_UNLCK, 1)
                else:
                    _native_lock.flock(stream.fileno(), _native_lock.LOCK_UN)
        finally:
            stream.close()


def annotate_check_runs(root: Path, tree, tasks, nodes) -> None:
    """Annotate a locked read snapshot without rewriting persisted state."""
    for kind, code, check in iter_checks(tree, tasks, nodes):
        if check.get("running"):
            owner = "tree" if kind == "tree" else kind + ":" + code
            with check_lock(root, owner, check["id"], probe=True) as free:
                check["interrupted"] = free


def resolve_root(value: Any) -> Path:
    path = Path(str(value or ".")).expanduser()
    if path.is_file() and path.name == TREE_NAME:
        return path.resolve().parent
    return path.resolve()


class CurrentWorkspace:
    """Read and write current plan objects without touching ``history/``."""

    def __init__(self, root: Path):
        self.root = root
        self.tree_path = root / TREE_NAME
        self.tasks_path = root / TASKS_DIRECTORY
        self.nodes_path = root / NODES_DIRECTORY
        self.history_path = root / HISTORY_DIRECTORY

    def require(self) -> None:
        if not self.tree_path.is_file():
            raise ToolError("no Checkpoints Tree at %s" % self.tree_path)

    def load(self) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
        self.require()
        tree = read_json(self.tree_path)
        if not isinstance(tree, dict) or tree.get("schema") != TREE_SCHEMA:
            raise ToolError("Tree.json is not a current Checkpoints Tree")
        if isinstance(tree.get("tasks"), list):
            raise ToolError(
                "Tree.json holds assembled tasks and nodes from an earlier single-file "
                "Checkpoints Tree and cannot be read as a split workspace; this tool would "
                "otherwise report an empty plan. Open it with the matching earlier tool "
                "version, or migrate it into Tree.json plus tasks/ and nodes/ first."
            )
        tree.setdefault("goal", "")
        tree.setdefault("success", [])
        tree.setdefault("architecture", None)
        tree.setdefault("delivery_policy", None)
        tree.setdefault("requirements", [])
        tree.setdefault("open_decisions", [])
        tree.setdefault("delivery", new_delivery())
        tree["checks"] = [normalize_check(item, "tree") for item in tree.get("checks") or []]
        tasks = self._load_objects(self.tasks_path, "task")
        nodes = self._load_objects(self.nodes_path, "node")
        for task in tasks.values():
            task.setdefault("title", task["id"])
            task.setdefault("outcome", "")
            task.setdefault("requirements", [])
            task.setdefault("draft_pr", None)
            task.setdefault("integration_owner", None)
            task.setdefault("delivery", new_delivery())
            task["checks"] = [normalize_check(item, "task") for item in task.get("checks") or []]
        for node in nodes.values():
            node.setdefault("title", node["id"])
            node.setdefault("outcome", "")
            node.setdefault("after", [])
            node.setdefault("status", "pending")
            node.setdefault("role", None)
            node.setdefault("executors", [])
            node.setdefault("resources", [])
            node.setdefault("contract", {})
            node.setdefault("review", [])
            node.setdefault("result", None)
            node.setdefault("commit", None)
            node["checks"] = [normalize_check(item, "node") for item in node.get("checks") or []]
        return tree, tasks, nodes

    def _load_objects(self, directory: Path, kind: str) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        if not directory.is_dir():
            return result
        for path in sorted(directory.glob("*.json")):
            value = read_json(path)
            if not isinstance(value, dict):
                raise ToolError("%s file %s must contain an object" % (kind, path.name))
            code = safe_id(value.get("id"), "%s.id" % kind)
            if path.stem != code:
                raise ToolError("%s file name must match id %s" % (kind, code))
            if code in result:
                raise ToolError("duplicate %s %s" % (kind, code))
            result[code] = value
        return result

    def write_tree(self, tree: dict[str, Any]) -> None:
        write_json(self.tree_path, tree)

    def write_task(self, task: dict[str, Any]) -> None:
        write_json(self.tasks_path / (safe_id(task.get("id"), "task.id") + ".json"), task)

    def write_node(self, node: dict[str, Any]) -> None:
        write_json(self.nodes_path / (safe_id(node.get("id"), "node.id") + ".json"), node)

    def remove_task(self, task_id: str) -> None:
        path = self.tasks_path / (safe_id(task_id, "task.id") + ".json")
        if path.is_file():
            path.unlink()

    def remove_node(self, node_id: str) -> None:
        path = self.nodes_path / (safe_id(node_id, "node.id") + ".json")
        if path.is_file():
            path.unlink()
