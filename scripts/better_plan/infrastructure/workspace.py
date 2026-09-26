"""Filesystem persistence for a Checkpoints Tree workspace.

One JSON object, one lock, atomic writes. Nothing here knows what a Tree means.
"""

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
    """Open and lock the workspace file, retrying mandatory-lock collisions.

    Windows `msvcrt.locking` is mandatory: another process holding the lock can
    make `open()` or `locking()` raise `PermissionError` instead of waiting.
    """

    deadline = time.monotonic() + 30
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        stream = None
        try:
            stream = path.open("a+b")
            stream.seek(0)
            if stream.read(1) == b"":
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            _native_lock.locking(stream.fileno(), _native_lock.LK_NBLCK, 1)
            return stream
        except OSError as exc:
            last_error = exc
            if stream is not None:
                stream.close()
            time.sleep(0.05)
    raise ToolError("cannot acquire workspace lock (%s)" % last_error)


@contextmanager
def workspace_lock(root: Path, *, create: bool = False) -> Iterator[None]:
    """Hold the one lock a Tree workspace has, for short state writes only.

    Long work — running a Node's commands — happens outside this lock. A workspace
    is created only when the caller is the one creating it; every other caller must
    already have one, so naming a wrong or missing directory never leaves a
    directory or a lock file behind.
    """

    if create:
        root.mkdir(parents=True, exist_ok=True)
    elif not root.is_dir():
        raise ToolError("no Checkpoints Tree workspace at %s" % (root.name or str(root)))
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
