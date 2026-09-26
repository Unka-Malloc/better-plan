"""Read-only verification of installed Better Plan targets."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from . import skills as _skills
from . import targets as _targets
from .models import (
    CURRENT_SKILL_FILES,
    OPTIONAL_CLIENT_CLI_COMMANDS,
    Check as _Check,
    InstallError as _InstallError,
    InstallPaths as _InstallPaths,
)


def run_manifest_tool(skill_root) -> bool:
    """Prove the installed tool runs by asking it for the Tree shape."""

    tool = skill_root / "scripts" / "manifest_tool.py"
    if not tool.is_file():
        return False
    result = _targets.run_text_command([sys.executable, str(tool), "schema"], timeout=10)
    return result.returncode == 0 and "better-plan.checkpoints-tree" in result.stdout


def check_skill_tree(target: str, root) -> _Check:
    missing = [relative for relative in CURRENT_SKILL_FILES if not (root / relative).is_file()]
    if missing:
        return _Check("FAIL", target, f"installed skill is invalid: missing file(s) {', '.join(missing)}")
    if not run_manifest_tool(root):
        return _Check("FAIL", target, "manifest tool validation failed")
    return _Check("OK", target, "installed skill structure verified")


def check_skill_source(target: str, root: Path, source: Path) -> _Check:
    """Compare the packaged payload, excluding immutable host role files."""

    label = f"{target} skill source"
    if root.resolve() == source.resolve():
        return _Check(
            "WARN", label,
            "selected source is the installed tree; use --source with an independent source tree to verify an update",
        )
    try:
        if any(not (source / relative).is_file() for relative in CURRENT_SKILL_FILES):
            return _Check("FAIL", label, "selected source is missing required skill files")
        if any(not (root / relative).is_file() for relative in CURRENT_SKILL_FILES):
            return _Check("FAIL", label, "installed skill is incomplete; source comparison unavailable")
        different = sum(
            (root / relative).read_bytes() != (source / relative).read_bytes()
            for relative in CURRENT_SKILL_FILES
        )
    except OSError:
        return _Check("FAIL", label, "skill files could not be read for source comparison")
    if different:
        return _Check(
            "WARN", label,
            f"{different} packaged file(s) differ from the selected source; structure validity does not establish update status",
        )
    return _Check("OK", label, "all packaged files match the selected source")


def check_shared_scan_agent(paths: _InstallPaths, target: str) -> _Check:
    kind, root = _skills.shared_scan_skill_target(paths, target)
    check = check_skill_tree(target, root)
    if check.status != "OK":
        return check
    native_root = _skills.native_skill_path(paths, target)
    # A host whose own path *is* the shared directory has no duplicate to report: the
    # shared skill is its native skill, so comparing the two would always match.
    if kind == "shared" and native_root != paths.shared_skill and native_root.exists():
        return _Check("WARN", target, "shared skill is installed but a duplicate native skill still exists")
    return _Check("OK", target, f"installed via {kind} skill")


def check_claude(paths: _InstallPaths) -> _Check:
    """Verify the Claude Code plugin layout, without validating an installed selector."""

    manifest = paths.claude_plugin / ".claude-plugin" / "plugin.json"
    if not manifest.is_file():
        return _Check("FAIL", "claude", "plugin manifest is missing")
    skill_check = check_skill_tree("claude", paths.claude_skill)
    if skill_check.status != "OK":
        return skill_check
    claude = shutil.which("claude")
    if claude is None:
        return _Check(
            "WARN", "claude", "plugin structure verified; claude CLI not found for runtime validation"
        )
    result = _targets.run_text_command(
        [claude, "plugin", "validate", str(paths.claude_plugin)], timeout=30
    )
    if result.returncode != 0:
        return _Check("FAIL", "claude", "plugin validation failed")
    return _Check("OK", "claude", "plugin structure and runtime validation passed")


def check_optional_client_cli(target: str) -> _Check:
    """Verify a host CLI that has no other runtime validation, when it is installed."""

    for command in OPTIONAL_CLIENT_CLI_COMMANDS[target]:
        name = command[0]
        if os.path.isabs(name):
            executable = name if os.path.isfile(name) else None
        else:
            executable = shutil.which(name)
        if executable is None:
            continue
        try:
            result = _targets.run_text_command([executable, *command[1:]], timeout=30)
        except _InstallError:
            continue
        if result.returncode in (126, 127):
            continue
        if result.returncode != 0:
            return _Check("FAIL", target, f"{name} CLI version check failed")
        return _Check("OK", target, f"adapter structure and {name} CLI verified")
    return _Check(
        "WARN", target, f"adapter structure verified; {target} CLI not found for runtime validation"
    )


def doctor(paths: _InstallPaths, agents: list[str]) -> list[_Check]:
    """Return bounded structural and optional runtime checks for selected agents."""
    checks: list[_Check] = []
    scan_targets = _skills.shared_scan_targets(paths, agents)
    if "codex" in agents:
        checks.append(check_native_roles(paths, "codex"))
        checks.append(check_shared_scan_agent(paths, "codex"))
    if "claude" in agents:
        checks.append(check_native_roles(paths, "claude"))
        checks.append(check_claude(paths))
    if "cursor" in agents:
        checks.append(check_native_roles(paths, "cursor"))
        checks.append(check_shared_scan_agent(paths, "cursor"))
        checks.append(check_optional_client_cli("cursor"))
    if "kilo" in agents:
        checks.append(check_kilo_agents(paths))
        checks.append(check_shared_scan_agent(paths, "kilo"))
    if "dsh" in agents:
        # DeepSeek Harness reads the shared skill and spawns subagents from a prompt,
        # so it installs no role file and no lifecycle Hook to verify.
        checks.append(check_shared_scan_agent(paths, "dsh"))

    # Shared consumers use the same payload. Compare it once, while retaining
    # each host's separate role, plugin, and adapter checks above.
    skill_roots = {root: kind for kind, root in scan_targets.values()}
    checks.extend(
        check_skill_source(target, root, paths.repo_root)
        for root, target in skill_roots.items()
    )
    return checks


def check_native_roles(paths: _InstallPaths, target: str) -> _Check:
    """Report the immutable local role matrix without proposing replacement."""

    ok, message = _targets.native_role_status(paths, target)
    if ok:
        status = "OK"
    elif _targets.native_role_configuration_exists(paths, target):
        status = "WARN"
    else:
        status = "FAIL"
    return _Check(status, f"{target} native roles", message)


def check_kilo_agents(paths: _InstallPaths) -> _Check:
    ok, message = _targets.kilo_agent_status(paths)
    if not ok:
        if _targets.kilo_agent_configuration_exists(paths):
            return _Check(
                "WARN",
                "kilo native Agents",
                f"local Kilo Agents preserved; {message}",
            )
        return _Check("FAIL", "kilo native Agents", message)
    kilo = shutil.which("kilo")
    if kilo is None:
        return _Check(
            "WARN",
            "kilo native Agents",
            "Agent matrix verified; kilo CLI not found for runtime validation",
        )
    result = _targets.run_text_command([kilo, "agent", "list"], timeout=30)
    if result.returncode != 0:
        return _Check("FAIL", "kilo native Agents", "kilo agent list failed")
    if any(Path(filename).stem not in result.stdout for filename in _targets.KILO_AGENT_FILES):
        return _Check(
            "FAIL",
            "kilo native Agents",
            "kilo agent list did not include the complete Better Plan matrix",
        )
    return _Check("OK", "kilo native Agents", "Agent matrix and runtime listing verified")
