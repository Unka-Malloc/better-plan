"""Detect whether one host lifecycle event belongs to a Better Plan project."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..domain.models import MANIFEST_NAME
from ..infrastructure.workspace import (
    discover_workspace_manifests,
    is_structural_workspace_manifest,
)


def event_directories(payload: dict[str, Any]) -> list[Path] | None:
    """Return usable host directory signals, rejecting ambiguous root lists."""
    directories: list[Path] = []
    cwd = payload.get("cwd")
    if isinstance(cwd, str) and cwd.strip():
        directories.append(Path(cwd.strip()))

    workspace_roots = payload.get("workspace_roots")
    if workspace_roots is not None:
        if not isinstance(workspace_roots, list):
            return None
        roots: list[Path] = []
        for value in workspace_roots:
            if not isinstance(value, str) or not value.strip():
                return None
            roots.append(Path(value.strip()))
        if len(roots) > 1:
            return None
        directories.extend(roots)
    return directories or None


def repository_root(context: Path) -> Path | None:
    resolved = context.expanduser().resolve()
    if resolved.is_file():
        resolved = resolved.parent
    for candidate in (resolved, *resolved.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def event_repository(payload: dict[str, Any]) -> Path | None:
    """Resolve all host signals to exactly one repository directory."""
    directories = event_directories(payload)
    if directories is None:
        return None
    repositories: set[Path] = set()
    for directory in directories:
        resolved = directory.expanduser().resolve()
        if not resolved.is_dir():
            return None
        root = repository_root(resolved)
        if root is None:
            return None
        repositories.add(root.resolve())
    return next(iter(repositories)) if len(repositories) == 1 else None


def detect_workspace(context: Path) -> Path | None:
    resolved = context.expanduser().resolve()
    if resolved.is_file() and resolved.name == MANIFEST_NAME:
        return resolved if is_structural_workspace_manifest(resolved) else None

    root = repository_root(resolved)
    if root is None:
        return None
    manifests = discover_workspace_manifests(root)
    unique = {manifest.resolve(): manifest for manifest in manifests}
    if len(unique) != 1:
        return None
    return next(iter(unique.values()))


def detect_event_workspace(payload: dict[str, Any]) -> Path | None:
    root = event_repository(payload)
    if root is None:
        return None
    manifests = discover_workspace_manifests(root)
    unique = {manifest.resolve(): manifest for manifest in manifests}
    return next(iter(unique.values())) if len(unique) == 1 else None
