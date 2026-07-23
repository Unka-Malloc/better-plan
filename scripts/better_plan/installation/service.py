"""Installer use-case composition without CLI or diagnostic concerns."""

from __future__ import annotations

from pathlib import Path

from . import skills as _skills
from . import targets as _targets
from .models import AGENTS, InstallPaths as _InstallPaths


_MANAGED_HOOK_AGENTS = {"codex", "claude", "cursor", "kimi"}


def install_agents(paths: _InstallPaths, agents: list[str], *, dry_run: bool) -> list[str]:
    """Install selected agents through one deterministic composition path."""
    _skills.validate_source_tree(paths.repo_root)
    messages: list[str] = []
    scan_targets = _skills.shared_scan_targets(paths, agents)
    implementation = _skills.implementation_root(paths, scan_targets)
    updated_roots: set[Path] = set()

    def update_skill_root(target: Path, label: str) -> None:
        if target in updated_roots:
            return
        _skills.copy_skill_tree(paths.repo_root, target, dry_run=dry_run)
        updated_roots.add(target)
        messages.append(f"{label}: {'would update' if dry_run else 'updated'} skill")

    for kind, target in scan_targets.values():
        update_skill_root(target, kind)
    if _skills.adapter_needs_skill_root(agents):
        label = "shared" if implementation == paths.shared_skill else "implementation"
        update_skill_root(implementation, label)

    for agent in AGENTS:
        if agent not in agents:
            continue
        if agent in scan_targets:
            kind, _ = scan_targets[agent]
            messages.append(f"{agent}: {'would use' if dry_run else 'using'} {kind} skill")
        messages.extend(_targets.install_target(paths, agent, dry_run=dry_run))

    messages.extend(
        _skills.remove_shared_scan_duplicates(paths, scan_targets, dry_run=dry_run)
    )
    return messages


def uninstall_hooks(paths: _InstallPaths, agents: list[str], *, dry_run: bool) -> list[str]:
    """Remove only Better Plan-managed lifecycle handlers."""
    messages: list[str] = []
    for agent in agents:
        if agent == "antigravity":
            path = paths.antigravity_plugin / "hooks.json"
            changed = path.exists()
            if changed and not dry_run:
                _skills.remove_path(path)
            action = "would remove managed handlers" if dry_run else "removed managed handlers"
            if not changed:
                action = "no managed handlers found"
            messages.append(f"{agent}: {action}")
            continue
        if agent in _MANAGED_HOOK_AGENTS:
            _, changed = _targets.remove_agent_hooks(paths, agent, dry_run=dry_run)
            action = "would remove managed handlers" if dry_run else "removed managed handlers"
            if not changed:
                action = "no managed handlers found"
            messages.append(f"{agent}: {action}")
        else:
            messages.append(f"{agent}: no managed lifecycle config")
    return messages


def uninstall_agents(
    paths: _InstallPaths,
    agents: list[str],
    *,
    remove_shared: bool,
    dry_run: bool,
) -> list[str]:
    messages: list[str] = []
    for agent in _MANAGED_HOOK_AGENTS:
        if agent not in agents:
            continue
        _, changed = _targets.remove_agent_hooks(paths, agent, dry_run=dry_run)
        if changed:
            action = "would remove managed handlers" if dry_run else "removed managed handlers"
        else:
            action = "no managed handlers found"
        messages.append(f"{agent} hooks: {action}")

    for agent in AGENTS:
        if agent in agents:
            messages.extend(_targets.remove_target(paths, agent, dry_run=dry_run))
    if remove_shared:
        if not dry_run:
            _skills.remove_path(paths.shared_skill)
        messages.append(f"shared: {'would remove' if dry_run else 'removed'} installed adapter")
    return messages
