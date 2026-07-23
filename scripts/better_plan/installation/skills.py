"""Atomic Better Plan skill-tree operations and target selection."""

from __future__ import annotations

import os
import shutil
from collections.abc import Iterable
from pathlib import Path

from .models import (
    ADAPTER_SKILL_AGENTS,
    AGENTS,
    CURRENT_SKILL_FILES,
    SHARED_SCAN_AGENTS,
    InstallError as _InstallError,
    InstallPaths as _InstallPaths,
)


def validate_source_tree(repo_root: Path) -> None:
    missing = [relative for relative in CURRENT_SKILL_FILES if not (repo_root / relative).is_file()]
    if missing:
        raise _InstallError(f"source tree is invalid: missing required file(s): {', '.join(missing)}")


def adapter_needs_skill_root(agents: Iterable[str]) -> bool:
    return any(agent in ADAPTER_SKILL_AGENTS for agent in agents)


def copy_skill_tree(source: Path, target: Path, *, dry_run: bool) -> None:
    """Atomically replace one skill tree built from the canonical payload allowlist."""
    validate_source_tree(source)
    if dry_run:
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.tmp-{os.getpid()}")
    if temp.exists():
        shutil.rmtree(temp)
    try:
        temp.mkdir()
        for relative in CURRENT_SKILL_FILES:
            destination = temp / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / relative, destination)
        if target.exists():
            shutil.rmtree(target)
        temp.rename(target)
    except Exception:
        if temp.exists():
            shutil.rmtree(temp)
        raise


def native_skill_path(paths: _InstallPaths, agent: str) -> Path:
    if agent == "codex":
        return paths.codex_skill
    if agent == "cursor":
        return paths.cursor_skill
    if agent == "copilot":
        return paths.copilot_skill
    if agent == "pi":
        return paths.pi_skill
    if agent == "kimi":
        return paths.kimi_skill
    raise _InstallError(f"{agent} does not have a native skill tree path")


def shared_scan_skill_target(paths: _InstallPaths, agent: str) -> tuple[str, Path]:
    native = native_skill_path(paths, agent)
    if paths.shared_skill.exists():
        return "shared", paths.shared_skill
    if native.exists():
        return "native", native
    return "shared", paths.shared_skill


def shared_scan_targets(
    paths: _InstallPaths,
    agents: Iterable[str],
) -> dict[str, tuple[str, Path]]:
    selected = set(agents)
    names = [agent for agent in AGENTS if agent in SHARED_SCAN_AGENTS and agent in selected]
    if not names:
        return {}
    if paths.shared_skill.exists():
        return {agent: ("shared", paths.shared_skill) for agent in names}
    if any(native_skill_path(paths, agent).exists() for agent in names):
        return {agent: ("native", native_skill_path(paths, agent)) for agent in names}
    return {agent: ("shared", paths.shared_skill) for agent in names}


def implementation_root(
    paths: _InstallPaths,
    targets: dict[str, tuple[str, Path]],
) -> Path:
    if paths.shared_skill.exists():
        return paths.shared_skill
    for agent in AGENTS:
        target = targets.get(agent)
        if target and target[0] == "native":
            return target[1]
    for agent in AGENTS:
        if agent in SHARED_SCAN_AGENTS:
            native = native_skill_path(paths, agent)
            if native.exists():
                return native
    return paths.shared_skill


def remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def remove_duplicate_skill_tree(path: Path, *, dry_run: bool) -> bool:
    if not path.exists():
        return False
    if not dry_run:
        remove_path(path)
    return True


def remove_shared_scan_duplicates(
    paths: _InstallPaths,
    targets: dict[str, tuple[str, Path]],
    *,
    dry_run: bool,
) -> list[str]:
    messages: list[str] = []
    for name, (kind, _) in targets.items():
        if kind != "shared":
            continue
        removed = remove_duplicate_skill_tree(native_skill_path(paths, name), dry_run=dry_run)
        if removed:
            verb = "would remove duplicate native skill" if dry_run else "removed duplicate native skill"
            messages.append(f"{name}: {verb}")
        else:
            messages.append(f"{name}: no duplicate native skill")
    return messages


def existing_install_paths(paths: _InstallPaths, agents: Iterable[str]) -> list[Path]:
    selected = set(agents)
    values: list[Path] = []
    if paths.shared_skill.exists() and selected & (SHARED_SCAN_AGENTS | ADAPTER_SKILL_AGENTS):
        values.append(paths.shared_skill)
    if "codex" in selected:
        values.append(paths.codex_skill)
    if "claude" in selected:
        values.append(paths.claude_plugin)
    if "opencode" in selected:
        values.append(paths.opencode_agent)
    if "cursor" in selected:
        values.append(paths.cursor_skill)
    if "copilot" in selected:
        values.append(paths.copilot_skill)
    if "antigravity" in selected:
        values.append(paths.antigravity_plugin)
    if "pi" in selected:
        values.append(paths.pi_skill)
    if "craft" in selected:
        values.extend(paths.craft_skills)
    if "kimi" in selected:
        values.append(paths.kimi_skill)
    return [path for path in values if path.exists()]
