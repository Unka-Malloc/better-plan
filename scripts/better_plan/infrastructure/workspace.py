"""Filesystem persistence for Better Plan v3 workspaces."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping
import hashlib
import json
import os
import tempfile

if os.name == "nt":
    import msvcrt as _native_lock
else:
    import fcntl as _native_lock

from ..domain.models import (
    AUTHORIZED_PHASES,
    CHECKPOINTS_NAME,
    MANIFEST_NAME,
    PLAN_NAME,
    ToolError,
    is_relative_workspace_path,
)
from ..domain.validation import (
    validate_checkpoints_document,
    validate_manifest_document,
    validate_plan_document,
)


IGNORED_DIRECTORIES = {".git", ".venv", "node_modules", "build", "dist", "target"}


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


def workspace_root(value: Path) -> Path:
    value = value.expanduser()
    if value.is_file():
        if value.name == MANIFEST_NAME:
            return value.parent.resolve()
        if value.name in {PLAN_NAME, CHECKPOINTS_NAME}:
            candidate = value.parent.parent / MANIFEST_NAME
            if candidate.is_file():
                return candidate.parent.resolve()
    resolved = value.resolve()
    if (resolved / MANIFEST_NAME).is_file() or not resolved.exists():
        return resolved
    current = resolved
    while current != current.parent:
        if (current / MANIFEST_NAME).is_file():
            return current
        current = current.parent
    return resolved


@contextmanager
def workspace_lock(root: Path) -> Iterator[None]:
    root.mkdir(parents=True, exist_ok=True)
    path = root / ".better-plan.lock"
    with path.open("a+b") as stream:
        if os.name == "nt":
            stream.seek(0)
            if stream.read(1) == b"":
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            _native_lock.locking(stream.fileno(), _native_lock.LK_LOCK, 1)
        else:
            _native_lock.flock(stream.fileno(), _native_lock.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                _native_lock.locking(stream.fileno(), _native_lock.LK_UNLCK, 1)
            else:
                _native_lock.flock(stream.fileno(), _native_lock.LOCK_UN)


def load_manifest(root: Path) -> dict[str, Any]:
    value = read_json(root / MANIFEST_NAME)
    issues = validate_manifest_document(root / MANIFEST_NAME, value)
    if issues:
        raise ToolError("invalid Manifest.json: %s" % "; ".join(issue.message for issue in issues))
    return dict(value)


def resolve_plan_entry(manifest: Mapping[str, Any], selector: str) -> dict[str, Any]:
    matches = [
        entry
        for entry in manifest.get("plans", [])
        if isinstance(entry, Mapping)
        and selector in {entry.get("code"), entry.get("title"), entry.get("directory")}
    ]
    if len(matches) != 1:
        raise ToolError("plan selector must resolve exactly one Delivery Plan")
    return dict(matches[0])


def plan_paths(root: Path, entry: Mapping[str, Any]) -> dict[str, Path]:
    directory = entry.get("directory")
    if not is_relative_workspace_path(directory):
        raise ToolError("invalid plan directory")
    plan_dir = root / str(directory)
    return {
        "directory": plan_dir,
        "plan": plan_dir / PLAN_NAME,
        "checkpoints": plan_dir / CHECKPOINTS_NAME,
    }


def load_plan(root: Path, selector: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Path]]:
    manifest = load_manifest(root)
    entry = resolve_plan_entry(manifest, selector)
    paths = plan_paths(root, entry)
    plan = read_json(paths["plan"])
    issues = validate_plan_document(paths["plan"], plan)
    if issues:
        raise ToolError("invalid Plan.json: %s" % "; ".join(issue.message for issue in issues))
    if any(plan.get(field) != entry.get(field) for field in ("code", "directory")):
        raise ToolError("Manifest and Plan identity do not match")
    return manifest, dict(plan), paths


def validate_workspace(root: Path) -> list[str]:
    messages: list[str] = []
    manifest_path = root / MANIFEST_NAME
    if not manifest_path.is_file():
        return ["Manifest.json: missing"]
    manifest = read_json(manifest_path)
    messages.extend(issue.message for issue in validate_manifest_document(manifest_path, manifest))
    if not isinstance(manifest, Mapping):
        return messages
    for entry in manifest.get("plans", []):
        if not isinstance(entry, Mapping):
            continue
        paths = plan_paths(root, entry)
        if not paths["plan"].is_file():
            messages.append("%s: missing" % entry.get("plan"))
            continue
        plan = read_json(paths["plan"])
        messages.extend(issue.message for issue in validate_plan_document(paths["plan"], plan))
        if isinstance(plan, Mapping) and any(
            plan.get(field) != entry.get(field) for field in ("code", "directory")
        ):
            messages.append("%s: Manifest identity mismatch" % entry.get("plan"))
        if paths["checkpoints"].is_file():
            checkpoints = read_json(paths["checkpoints"])
            messages.extend(
                issue.message
                for issue in validate_checkpoints_document(paths["checkpoints"], checkpoints, plan)
            )
        elif isinstance(plan, Mapping) and plan.get("phase") in AUTHORIZED_PHASES:
            messages.append("%s: missing authorized Checkpoints.json" % entry.get("directory"))
    return messages


def discover_workspaces(root: Path) -> list[Path]:
    """Return every valid v3 workspace beneath one directory."""

    root = root.resolve()
    if root.is_file():
        root = root.parent
    candidates: list[Path] = []
    for current, directories, files in os.walk(str(root)):
        directories[:] = [name for name in directories if name not in IGNORED_DIRECTORIES]
        if MANIFEST_NAME not in files:
            continue
        candidate = Path(current)
        try:
            manifest = read_json(candidate / MANIFEST_NAME)
        except ToolError:
            continue
        if not validate_manifest_document(candidate / MANIFEST_NAME, manifest):
            candidates.append(candidate)
    return sorted(candidates)


def fingerprint_paths(project_root: Path, paths: list[str]) -> str:
    """Hash declared paths as a receipt, never as a gate.

    A path a Task has not produced yet is recorded as absent rather than raising,
    so a greenfield Task can be dispatched and accepted normally. Symlinks and
    non-relative paths remain hard errors because they break the safety boundary.
    """

    digest = hashlib.sha256()
    for relative in sorted(set(paths)):
        if not is_relative_workspace_path(relative):
            raise ToolError("fingerprint path must be repository-relative")
        path = project_root / relative
        if path.is_symlink():
            raise ToolError("fingerprint path is unsafe: %s" % relative)
        digest.update(relative.encode("utf-8"))
        if not path.exists():
            digest.update(b"\x00absent")
        elif path.is_file():
            digest.update(path.read_bytes())
        else:
            for child in sorted(item for item in path.rglob("*") if item.is_file() and not item.is_symlink()):
                digest.update(child.relative_to(project_root).as_posix().encode("utf-8"))
                digest.update(child.read_bytes())
    return digest.hexdigest()
