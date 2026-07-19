"""Target-specific Better Plan installer adapters."""

from __future__ import annotations

import json
import os
import posixpath
import shlex
import shutil
import subprocess
from pathlib import Path

from ..hooks.config import (
    HookConfigError as _HookConfigError,
    install_hook_config as _install_hook_config,
    uninstall_hook_config as _uninstall_hook_config,
)
from .models import (
    AGENTS,
    DESCRIPTION,
    SKILL_NAME,
    VERSION,
    InstallError as _InstallError,
    InstallPaths as _InstallPaths,
    WslOpenCodeRuntime as _WslOpenCodeRuntime,
)
from .skills import copy_skill_tree as _copy_skill_tree, remove_path as _remove_path


def read_json_object(path: Path) -> dict[str, object]:
    try:
        if not path.exists() or not path.read_text(encoding="utf-8").strip():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise _InstallError(f"{path.name}: could not read configuration") from exc
    except json.JSONDecodeError as exc:
        raise _InstallError(
            f"{path.name}: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    if not isinstance(data, dict):
        raise _InstallError(f"{path.name}: top-level JSON value must be an object")
    return data


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, data: object) -> None:
    write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def install_claude_plugin(paths: _InstallPaths, *, dry_run: bool) -> None:
    # Validate even for dry runs through the canonical allowlisted copier.
    if dry_run:
        _copy_skill_tree(paths.repo_root, paths.claude_skill, dry_run=True)
        return

    target = paths.claude_plugin
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.tmp-{os.getpid()}")
    if temp.exists():
        shutil.rmtree(temp)
    try:
        (temp / ".claude-plugin").mkdir(parents=True)
        (temp / "skills").mkdir()
        write_json(
            temp / ".claude-plugin" / "plugin.json",
            {
                "name": SKILL_NAME,
                "version": VERSION,
                "description": DESCRIPTION,
                "author": {"name": "Better Plan"},
            },
        )
        for name in ("README.md", "LICENSE"):
            source = paths.repo_root / name
            if source.is_file():
                shutil.copy2(source, temp / name)
        _copy_skill_tree(paths.repo_root, temp / "skills" / SKILL_NAME, dry_run=False)
        if target.exists():
            shutil.rmtree(target)
        temp.rename(target)
    except Exception:
        if temp.exists():
            shutil.rmtree(temp)
        raise


def opencode_agent_text() -> str:
    return """---
description: Follow the Better Plan design-first workflow with deterministic acceptance and regression.
mode: primary
temperature: 0.1
permission:
  edit: allow
  bash: allow
---

Before acting, locate the installed `better-plan` skill, read its `SKILL.md` completely,
and follow it as the active workflow. Use `scripts/manifest_tool.py` inside the skill for
state transitions and validation. Do not preserve removed implementations or compatibility
shims. Preserve unrelated user changes and verify real behavior before completion.
"""


def gemini_manifest() -> dict[str, str]:
    return {
        "name": SKILL_NAME,
        "version": VERSION,
        "description": DESCRIPTION,
        "contextFileName": "GEMINI.md",
    }


def gemini_context_text() -> str:
    return """# Better Plan

When a project uses Better Plan, locate the installed `better-plan` skill, read its
`SKILL.md` completely, and follow it as the active workflow. Use
`scripts/manifest_tool.py` for state transitions and validation. Preserve unrelated
user changes, remove obsolete implementations completely, and verify real behavior.
"""


def install_gemini_extension(paths: _InstallPaths, *, dry_run: bool) -> None:
    if dry_run:
        return
    paths.gemini_extension.mkdir(parents=True, exist_ok=True)
    write_json(paths.gemini_extension / "gemini-extension.json", gemini_manifest())
    write_text(paths.gemini_extension / "GEMINI.md", gemini_context_text())
    update_gemini_enablement(paths, enabled=True, dry_run=False)


def relative_scope(value: str) -> str:
    normalized = value.strip().replace("\\", "/")
    unsafe = (
        not normalized
        or normalized.startswith("/")
        or normalized.startswith("~/")
        or ".." in normalized.split("/")
        or (len(normalized) >= 3 and normalized[0].isalpha() and normalized[1:3] == ":/")
    )
    if unsafe:
        raise _InstallError("Gemini scope must be a relative pattern")
    return normalized


def update_gemini_enablement(paths: _InstallPaths, *, enabled: bool, dry_run: bool) -> None:
    if dry_run:
        return
    data = read_json_object(paths.gemini_enablement)
    updated = dict(data)
    if enabled:
        updated[SKILL_NAME] = {"overrides": [relative_scope(paths.gemini_scope)]}
    else:
        updated.pop(SKILL_NAME, None)
    if updated != data:
        write_json(paths.gemini_enablement, updated)


def hook_config_path(paths: _InstallPaths, agent: str) -> Path:
    if agent == "codex":
        return paths.codex_hooks
    if agent == "claude":
        return paths.claude_settings
    if agent == "cursor":
        return paths.cursor_hooks
    raise _InstallError(f"{agent} does not support Better Plan lifecycle Hooks")


def update_agent_hooks(paths: _InstallPaths, agent: str, *, dry_run: bool) -> tuple[Path, bool]:
    config = hook_config_path(paths, agent)
    try:
        changed = _install_hook_config(config, agent, dry_run=dry_run)
    except _HookConfigError as exc:
        raise _InstallError(str(exc)) from exc
    return config, changed


def remove_agent_hooks(paths: _InstallPaths, agent: str, *, dry_run: bool) -> tuple[Path, bool]:
    config = hook_config_path(paths, agent)
    try:
        changed = _uninstall_hook_config(config, agent, dry_run=dry_run)
    except _HookConfigError as exc:
        raise _InstallError(str(exc)) from exc
    return config, changed


def run_text_command(command: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise _InstallError("runtime validation timed out; command output was discarded") from exc
    except OSError as exc:
        raise _InstallError("runtime validation could not start; command output was discarded") from exc


def decode_probe_output(data: bytes) -> str:
    if not data:
        return ""
    if data.startswith(b"\xff\xfe") or data.count(b"\x00") > max(1, len(data) // 8):
        return data.decode("utf-16le", errors="replace").replace("\ufeff", "")
    return data.decode("utf-8", errors="replace")


def parse_running_wsl_distros(output: str) -> list[str]:
    distros: list[str] = []
    for value in (line.strip() for line in output.replace("\x00", "").splitlines()):
        if not value:
            continue
        if value.startswith("*"):
            value = value[1:].strip()
        parts = value.split()
        if not parts or parts[0].upper() == "NAME":
            continue
        if len(parts) >= 3 and parts[-2].lower() == "running":
            distros.append(" ".join(parts[:-2]))
    return distros


WSL_OPENCODE_PROBE_SCRIPT = (
    "path=$(command -v opencode 2>/dev/null) || exit 1; "
    "printf '%s\\n' \"$path\"; printf '%s\\n' \"$HOME\"; "
    "opencode --version 2>/dev/null | head -n 1 || true"
)


def wsl_executable() -> str | None:
    if os.name != "nt":
        return None
    return shutil.which("wsl.exe") or shutil.which("wsl")


def run_wsl_script(
    wsl: str,
    distro: str,
    script: str,
    *,
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    return run_text_command([wsl, "-d", distro, "-e", "bash", "-lic", script], timeout=timeout)


def split_wsl_probe_stdout(stdout: str) -> tuple[str, str, str] | None:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if len(lines) < 2:
        return None
    return lines[0], lines[1], lines[2] if len(lines) > 2 else "version unknown"


def discover_wsl_opencode() -> list[_WslOpenCodeRuntime]:
    wsl = wsl_executable()
    if wsl is None:
        return []
    try:
        result = subprocess.run(
            [wsl, "-l", "-v"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []

    probes: list[_WslOpenCodeRuntime] = []
    for distro in parse_running_wsl_distros(decode_probe_output(result.stdout)):
        try:
            probe = run_wsl_script(wsl, distro, WSL_OPENCODE_PROBE_SCRIPT, timeout=20)
        except _InstallError:
            continue
        found = split_wsl_probe_stdout(probe.stdout if probe.returncode == 0 else "")
        if found:
            location, home, version = found
            probes.append(_WslOpenCodeRuntime(distro, location, home, version))
    return probes


def wsl_source_path(wsl: str, runtime: _WslOpenCodeRuntime, source: Path) -> str:
    result = run_text_command(
        [wsl, "-d", runtime.distro, "-e", "wslpath", "-a", str(source)],
        timeout=20,
    )
    path = result.stdout.strip() if result.returncode == 0 else ""
    if not path:
        raise _InstallError("unable to resolve Better Plan source inside the WSL runtime")
    return path


def install_wsl_opencode(paths: _InstallPaths, *, dry_run: bool) -> list[str]:
    wsl = wsl_executable()
    if wsl is None:
        return []
    messages: list[str] = []
    for runtime in discover_wsl_opencode():
        if dry_run:
            messages.append("opencode: would update detected WSL runtime")
            continue
        source = wsl_source_path(wsl, runtime, paths.repo_root)
        installer = posixpath.join(source, "scripts", "install.py")
        script = f"python3 {shlex.quote(installer)} update --agents codex,opencode"
        result = run_wsl_script(wsl, runtime.distro, script, timeout=120)
        if result.returncode != 0:
            raise _InstallError("failed to update Better Plan in the WSL runtime")
        messages.append("opencode: updated detected WSL runtime")
    return messages


def install_target(paths: _InstallPaths, target: str, *, dry_run: bool) -> list[str]:
    """Apply only the target-specific side effects for one normalized target."""
    if target not in AGENTS:
        raise _InstallError(f"unknown agent target: {target}")
    if target == "codex":
        _, changed = update_agent_hooks(paths, target, dry_run=dry_run)
        action = "would update" if dry_run and changed else "updated" if changed else "already current"
        return [f"codex hooks: {action} managed handlers"]
    if target == "claude":
        install_claude_plugin(paths, dry_run=dry_run)
        _, changed = update_agent_hooks(paths, target, dry_run=dry_run)
        action = "would update" if dry_run and changed else "updated" if changed else "already current"
        return [
            f"claude: {'would update' if dry_run else 'updated'} plugin",
            f"claude hooks: {action} managed handlers",
        ]
    if target == "opencode":
        if not dry_run:
            write_text(paths.opencode_agent, opencode_agent_text())
        return [f"opencode: {'would update' if dry_run else 'updated'} agent", *install_wsl_opencode(paths, dry_run=dry_run)]
    if target == "cursor":
        _, changed = update_agent_hooks(paths, target, dry_run=dry_run)
        action = "would update" if dry_run and changed else "updated" if changed else "already current"
        return [f"cursor hooks: {action} managed handlers"]
    if target == "gemini":
        install_gemini_extension(paths, dry_run=dry_run)
        return [f"gemini: {'would update' if dry_run else 'updated'} extension"]
    return []


def remove_target(paths: _InstallPaths, target: str, *, dry_run: bool) -> list[str]:
    if target not in AGENTS:
        raise _InstallError(f"unknown agent target: {target}")
    path = {
        "codex": paths.codex_skill,
        "claude": paths.claude_plugin,
        "opencode": paths.opencode_agent,
        "cursor": paths.cursor_skill,
        "copilot": paths.copilot_skill,
        "gemini": paths.gemini_extension,
    }[target]
    if not dry_run:
        _remove_path(path)
    if target == "gemini":
        update_gemini_enablement(paths, enabled=False, dry_run=dry_run)
        return [f"gemini: {'would remove' if dry_run else 'removed'}"]
    return [f"{target}: {'would remove' if dry_run else 'removed'}"]
