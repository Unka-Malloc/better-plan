#!/usr/bin/env python3
"""Install Better Plan for local coding agents."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


SKILL_NAME = "better-plan"
AGENTS = ("codex", "claude", "opencode", "cursor", "copilot", "gemini")
AGENT_ALIASES = {
    "vscode": "copilot",
    "vscode-copilot": "copilot",
    "github-copilot": "copilot",
}
SHARED_SCAN_AGENTS = {"codex", "cursor", "copilot"}
ADAPTER_SKILL_AGENTS = {"opencode", "gemini"}
REPO_ROOT = Path(__file__).resolve().parents[1]
COPY_IGNORE = (".git", "__pycache__", ".pytest_cache", ".DS_Store")
DESCRIPTION = "Better Plan workflow for project planning, checkpoints, execution, validation, and commits."


class InstallError(RuntimeError):
    """Raised when an install operation cannot be completed safely."""


@dataclass(frozen=True)
class InstallPaths:
    repo_root: Path
    codex_home: Path
    shared_home: Path
    claude_home: Path
    opencode_config: Path
    cursor_home: Path
    copilot_home: Path
    gemini_home: Path
    gemini_scope: str

    @property
    def codex_skill(self) -> Path:
        return self.codex_home / "skills" / SKILL_NAME

    @property
    def shared_skill(self) -> Path:
        return self.shared_home / "skills" / SKILL_NAME

    @property
    def claude_plugin(self) -> Path:
        return self.claude_home / "skills" / SKILL_NAME

    @property
    def claude_skill(self) -> Path:
        return self.claude_plugin / "skills" / SKILL_NAME

    @property
    def opencode_agent(self) -> Path:
        return self.opencode_config / "agents" / f"{SKILL_NAME}.md"

    @property
    def cursor_skill(self) -> Path:
        return self.cursor_home / "skills" / SKILL_NAME

    @property
    def copilot_skill(self) -> Path:
        return self.copilot_home / "skills" / SKILL_NAME

    @property
    def gemini_extension(self) -> Path:
        return self.gemini_home / "extensions" / SKILL_NAME

    @property
    def gemini_enablement(self) -> Path:
        return self.gemini_home / "extensions" / "extension-enablement.json"


@dataclass(frozen=True)
class Check:
    status: str
    target: str
    message: str


@dataclass(frozen=True)
class RuntimeProbe:
    runtime: str
    location: str
    version: str


def default_paths(args: argparse.Namespace) -> InstallPaths:
    home = Path.home()
    repo_root = Path(args.source).expanduser().resolve() if args.source else REPO_ROOT
    return InstallPaths(
        repo_root=repo_root,
        codex_home=Path(args.codex_home or os.environ.get("CODEX_HOME") or home / ".codex").expanduser(),
        shared_home=Path(args.shared_home or os.environ.get("BETTER_PLAN_SHARED_HOME") or home / ".agents").expanduser(),
        claude_home=Path(args.claude_home or os.environ.get("CLAUDE_HOME") or home / ".claude").expanduser(),
        opencode_config=Path(
            args.opencode_config or os.environ.get("OPENCODE_CONFIG_HOME") or home / ".config" / "opencode"
        ).expanduser(),
        cursor_home=Path(args.cursor_home or os.environ.get("CURSOR_HOME") or home / ".cursor").expanduser(),
        copilot_home=Path(args.copilot_home or os.environ.get("COPILOT_HOME") or home / ".copilot").expanduser(),
        gemini_home=Path(args.gemini_home or os.environ.get("GEMINI_HOME") or home / ".gemini").expanduser(),
        gemini_scope=args.gemini_scope or f"{home}/*",
    )


def parse_agents(values: list[str] | None) -> list[str]:
    if not values:
        return list(AGENTS)

    tokens: list[str] = []
    for value in values:
        tokens.extend(token.strip().lower() for token in value.split(","))

    if any(token == "all" for token in tokens):
        return list(AGENTS)

    agents: list[str] = []
    invalid: list[str] = []
    for token in tokens:
        if not token:
            continue
        token = AGENT_ALIASES.get(token, token)
        if token not in AGENTS:
            invalid.append(token)
            continue
        if token not in agents:
            agents.append(token)

    if invalid:
        expected = ", ".join(("all", *AGENTS))
        raise InstallError(f"unknown agent target(s): {', '.join(invalid)}; expected one of {expected}")
    if not agents:
        raise InstallError("at least one agent target is required")
    return agents


def adapter_needs_skill_root(agents: Iterable[str]) -> bool:
    return any(agent in ADAPTER_SKILL_AGENTS for agent in agents)


def validate_source_tree(repo_root: Path) -> None:
    missing = [
        path
        for path in (
            repo_root / "SKILL.md",
            repo_root / "scripts" / "manifest_tool.py",
        )
        if not path.is_file()
    ]
    if missing:
        values = ", ".join(str(path) for path in missing)
        raise InstallError(f"source tree is missing required file(s): {values}")


def copy_skill_tree(source: Path, target: Path, *, dry_run: bool) -> None:
    validate_source_tree(source)
    if dry_run:
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.tmp-{os.getpid()}")
    if temp.exists():
        shutil.rmtree(temp)
    try:
        shutil.copytree(source, temp, ignore=shutil.ignore_patterns(*COPY_IGNORE))
        if target.exists():
            shutil.rmtree(target)
        temp.rename(target)
    except Exception:
        if temp.exists():
            shutil.rmtree(temp)
        raise


def install_claude_plugin(paths: InstallPaths, *, dry_run: bool) -> None:
    validate_source_tree(paths.repo_root)
    if dry_run:
        return

    target = paths.claude_plugin
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.tmp-{os.getpid()}")
    if temp.exists():
        shutil.rmtree(temp)
    try:
        (temp / ".claude-plugin").mkdir(parents=True)
        (temp / "skills").mkdir()
        plugin = {
            "name": SKILL_NAME,
            "description": DESCRIPTION,
            "author": {
                "name": "Better Plan",
            },
        }
        write_json(temp / ".claude-plugin" / "plugin.json", plugin)
        for name in ("README.md", "LICENSE"):
            source = paths.repo_root / name
            if source.is_file():
                shutil.copy2(source, temp / name)
        shutil.copytree(paths.repo_root, temp / "skills" / SKILL_NAME, ignore=shutil.ignore_patterns(*COPY_IGNORE))
        if target.exists():
            shutil.rmtree(target)
        temp.rename(target)
    except Exception:
        if temp.exists():
            shutil.rmtree(temp)
        raise


def opencode_agent_text(skill: Path) -> str:
    return f"""---
description: Follow the Better Plan workflow for project planning, checkpoints, execution, validation, and commits.
mode: primary
temperature: 0.1
permission:
  edit: allow
  bash: allow
---

You are operating in Better Plan mode.

Before acting, read `{skill / "SKILL.md"}` completely and follow that workflow as the active operating procedure.

Use `{skill / "scripts" / "manifest_tool.py"}` for UUID generation, state transition checks, and Manifest.json / Checkpoints.json validation.

Do not preserve legacy compatibility, old implementations, fallback shims, deprecated paths, versioned wrappers, or duplicate implementations unless an existing external service contract requires them.

Keep all work grounded in current repository files, preserve unrelated user changes, verify real behavior before completion, and commit only intentional task changes when the user asks for delivery.
"""


def gemini_manifest() -> dict[str, str]:
    return {
        "name": SKILL_NAME,
        "version": "0.1.0",
        "description": DESCRIPTION,
        "contextFileName": "GEMINI.md",
    }


def gemini_context_text(skill: Path) -> str:
    return f"""# Better Plan

When the user asks to use Better Plan, continue a Better Plan workflow, inspect project progress, or execute plan/checkpoint work, read `{skill / "SKILL.md"}` completely and follow it as the active workflow.

Use `{skill / "scripts" / "manifest_tool.py"}` for UUID generation, status transition checks, and Manifest.json / Checkpoints.json validation.

Do not preserve legacy compatibility, old implementations, fallback shims, deprecated paths, versioned wrappers, or duplicate implementations unless an existing external service contract requires them.

Work from the current project root unless the user gives another root, preserve unrelated user changes, and verify real behavior before reporting completion.
"""


def install_gemini_extension(paths: InstallPaths, skill: Path, *, dry_run: bool) -> None:
    if dry_run:
        return
    paths.gemini_extension.mkdir(parents=True, exist_ok=True)
    write_json(paths.gemini_extension / "gemini-extension.json", gemini_manifest(), backup=True)
    write_text(paths.gemini_extension / "GEMINI.md", gemini_context_text(skill), backup=True)
    update_gemini_enablement(paths, enabled=True, dry_run=False)


def update_gemini_enablement(paths: InstallPaths, *, enabled: bool, dry_run: bool) -> None:
    if dry_run:
        return

    path = paths.gemini_enablement
    data = read_json_object(path)
    next_data = dict(data)
    if enabled:
        next_data[SKILL_NAME] = {"overrides": [paths.gemini_scope]}
    else:
        next_data.pop(SKILL_NAME, None)

    if next_data != data:
        write_json(path, next_data, backup=path.exists())


def read_json_object(path: Path) -> dict[str, object]:
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InstallError(f"{path}: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise InstallError(f"{path}: top-level JSON value must be an object")
    return data


def write_json(path: Path, data: object, *, backup: bool = False) -> None:
    write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n", backup=backup)


def write_text(path: Path, content: str, *, backup: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    if backup and path.exists():
        backup_file(path)
    path.write_text(content, encoding="utf-8")


def backup_file(path: Path) -> Path:
    stamp = time.strftime("%Y%m%d%H%M%S")
    backup = path.with_name(f"{path.name}.bak-better-plan-{stamp}")
    shutil.copy2(path, backup)
    return backup


def native_skill_path(paths: InstallPaths, agent: str) -> Path:
    if agent == "codex":
        return paths.codex_skill
    if agent == "cursor":
        return paths.cursor_skill
    if agent == "copilot":
        return paths.copilot_skill
    raise InstallError(f"{agent} does not have a native skill tree path")


def shared_scan_skill_target(paths: InstallPaths, agent: str) -> tuple[str, Path]:
    native = native_skill_path(paths, agent)
    if paths.shared_skill.exists():
        return "shared", paths.shared_skill
    if native.exists():
        return "native", native
    return "shared", paths.shared_skill


def shared_scan_targets(paths: InstallPaths, agents: Iterable[str]) -> dict[str, tuple[str, Path]]:
    selected = set(agents)
    selected_shared_scan = [agent for agent in AGENTS if agent in SHARED_SCAN_AGENTS and agent in selected]
    if not selected_shared_scan:
        return {}
    if paths.shared_skill.exists():
        return {agent: ("shared", paths.shared_skill) for agent in selected_shared_scan}
    if any(native_skill_path(paths, agent).exists() for agent in selected_shared_scan):
        return {agent: ("native", native_skill_path(paths, agent)) for agent in selected_shared_scan}
    return {
        agent: ("shared", paths.shared_skill)
        for agent in selected_shared_scan
    }


def implementation_root(paths: InstallPaths, targets: dict[str, tuple[str, Path]]) -> Path:
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


def backup_root_for_skill_tree(path: Path) -> Path:
    return path.parent.parent / "skill-backups"


def unique_backup_path(backup_root: Path, name: str) -> Path:
    stamp = time.strftime("%Y%m%d%H%M%S")
    candidate = backup_root / f"{name}.bak-better-plan-{stamp}"
    index = 1
    while candidate.exists():
        candidate = backup_root / f"{name}.bak-better-plan-{stamp}-{index}"
        index += 1
    return candidate


def move_skill_tree_to_backup(path: Path, *, dry_run: bool) -> Path | None:
    if not path.exists():
        return None
    backup_root = backup_root_for_skill_tree(path)
    backup = unique_backup_path(backup_root, path.name)
    if dry_run:
        return backup
    backup_root.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(backup))
    return backup


def migrate_shared_scan_duplicates(
    paths: InstallPaths,
    targets: dict[str, tuple[str, Path]],
    *,
    dry_run: bool,
) -> list[str]:
    messages: list[str] = []
    for name, (kind, _) in targets.items():
        if kind != "shared":
            continue
        path = native_skill_path(paths, name)
        backup = move_skill_tree_to_backup(path, dry_run=dry_run)
        if backup is None:
            messages.append(f"{name}: no duplicate native skill at {path}")
        else:
            verb = "would move duplicate native skill" if dry_run else "moved duplicate native skill"
            messages.append(f"{name}: {verb} {path} -> {backup}")
    return messages


def existing_install_paths(paths: InstallPaths, agents: Iterable[str]) -> list[Path]:
    selected = set(agents)
    values: list[Path] = []
    if paths.shared_skill.exists() and (selected & (SHARED_SCAN_AGENTS | ADAPTER_SKILL_AGENTS)):
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
    if "gemini" in selected:
        values.append(paths.gemini_extension)
    return [path for path in values if path.exists()]


def install_agents(paths: InstallPaths, agents: list[str], *, dry_run: bool) -> list[str]:
    validate_source_tree(paths.repo_root)
    messages: list[str] = []
    targets = shared_scan_targets(paths, agents)
    root = implementation_root(paths, targets)
    updated_roots: set[Path] = set()

    def update_skill_root(target: Path, label: str) -> None:
        if target in updated_roots:
            return
        copy_skill_tree(paths.repo_root, target, dry_run=dry_run)
        updated_roots.add(target)
        messages.append(f"{label}: {'would update' if dry_run else 'updated'} {target}")

    for _, (kind, target) in targets.items():
        update_skill_root(target, kind)

    if adapter_needs_skill_root(agents):
        update_skill_root(root, "shared" if root == paths.shared_skill else "implementation")

    if "codex" in agents:
        kind, target = targets["codex"]
        messages.append(f"codex: {'would use' if dry_run else 'using'} {kind} skill {target}")

    if "claude" in agents:
        install_claude_plugin(paths, dry_run=dry_run)
        messages.append(f"claude: {'would update' if dry_run else 'updated'} {paths.claude_plugin}")

    if "opencode" in agents:
        if not dry_run:
            write_text(paths.opencode_agent, opencode_agent_text(root), backup=True)
        messages.append(f"opencode: {'would update' if dry_run else 'updated'} {paths.opencode_agent}")

    if "cursor" in agents:
        kind, target = targets["cursor"]
        messages.append(f"cursor: {'would use' if dry_run else 'using'} {kind} skill {target}")

    if "copilot" in agents:
        kind, target = targets["copilot"]
        messages.append(f"copilot: {'would use' if dry_run else 'using'} {kind} skill {target}")

    if "gemini" in agents:
        install_gemini_extension(paths, root, dry_run=dry_run)
        messages.append(f"gemini: {'would update' if dry_run else 'updated'} {paths.gemini_extension}")

    messages.extend(migrate_shared_scan_duplicates(paths, targets, dry_run=dry_run))
    return messages


def uninstall_agents(paths: InstallPaths, agents: list[str], *, remove_shared: bool, dry_run: bool) -> list[str]:
    messages: list[str] = []
    removals: list[tuple[str, Path]] = []

    if "codex" in agents:
        removals.append(("codex", paths.codex_skill))
    if "claude" in agents:
        removals.append(("claude", paths.claude_plugin))
    if "opencode" in agents:
        removals.append(("opencode", paths.opencode_agent))
    if "cursor" in agents:
        removals.append(("cursor", paths.cursor_skill))
    if "copilot" in agents:
        removals.append(("copilot", paths.copilot_skill))
    if "gemini" in agents:
        removals.append(("gemini", paths.gemini_extension))
    if remove_shared:
        removals.append(("shared", paths.shared_skill))

    for name, path in removals:
        if dry_run:
            messages.append(f"{name}: would remove {path}")
            continue
        remove_path(path)
        messages.append(f"{name}: removed {path}")

    if "gemini" in agents:
        update_gemini_enablement(paths, enabled=False, dry_run=dry_run)
        messages.append(f"gemini: {'would disable' if dry_run else 'disabled'} {paths.gemini_enablement}")

    return messages


def remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def run_text_command(command: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
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


def decode_probe_output(data: bytes) -> str:
    if not data:
        return ""
    if data.startswith(b"\xff\xfe") or data.count(b"\x00") > max(1, len(data) // 8):
        return data.decode("utf-16le", errors="replace").replace("\ufeff", "")
    return data.decode("utf-8", errors="replace")


def parse_running_wsl_distros(output: str) -> list[str]:
    distros: list[str] = []
    for line in output.replace("\x00", "").splitlines():
        value = line.strip()
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


def split_probe_stdout(stdout: str) -> tuple[str, str] | None:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if not lines:
        return None
    location = lines[0]
    version = lines[1] if len(lines) > 1 else "version unknown"
    return location, version


OPENCODE_PROBE_SCRIPT = (
    "path=$(command -v opencode 2>/dev/null) || exit 1; "
    "printf '%s\\n' \"$path\"; "
    "opencode --version 2>/dev/null | head -n 1 || true"
)


def discover_wsl_opencode() -> list[RuntimeProbe]:
    if os.name != "nt":
        return []
    wsl = shutil.which("wsl.exe") or shutil.which("wsl")
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

    probes: list[RuntimeProbe] = []
    for distro in parse_running_wsl_distros(decode_probe_output(result.stdout)):
        try:
            probe = run_text_command(
                [wsl, "-d", distro, "-e", "bash", "-lic", OPENCODE_PROBE_SCRIPT],
                timeout=20,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        found = split_probe_stdout(probe.stdout if probe.returncode == 0 else "")
        if found:
            location, version = found
            probes.append(RuntimeProbe(f"WSL {distro}", location, version))
    return probes


def discover_docker_opencode() -> list[RuntimeProbe]:
    docker = shutil.which("docker")
    if docker is None:
        return []
    try:
        result = run_text_command([docker, "ps", "--format", "{{.ID}}\t{{.Names}}"], timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []

    probes: list[RuntimeProbe] = []
    for line in result.stdout.splitlines()[:20]:
        value = line.strip()
        if not value:
            continue
        parts = value.split("\t", 1)
        container = parts[0].strip()
        name = parts[1].strip() if len(parts) > 1 and parts[1].strip() else container
        if not container:
            continue
        try:
            probe = run_text_command(
                [docker, "exec", container, "sh", "-lc", OPENCODE_PROBE_SCRIPT],
                timeout=20,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        found = split_probe_stdout(probe.stdout if probe.returncode == 0 else "")
        if found:
            location, version = found
            probes.append(RuntimeProbe(f"Docker {name}", location, version))
    return probes


def discover_external_opencode() -> list[RuntimeProbe]:
    return [*discover_wsl_opencode(), *discover_docker_opencode()]


def format_runtime_probes(probes: list[RuntimeProbe]) -> str:
    return "; ".join(f"{probe.runtime}: {probe.location} ({probe.version})" for probe in probes)


def run_manifest_tool(skill_root: Path) -> bool:
    tool = skill_root / "scripts" / "manifest_tool.py"
    if not tool.is_file():
        return False
    result = run_text_command(
        [sys.executable, str(tool), "uuid"],
        timeout=10,
    )
    return result.returncode == 0 and bool(result.stdout.strip())


def stale_shell_scripts(skill_root: Path) -> list[Path]:
    scripts = skill_root / "scripts"
    if not scripts.is_dir():
        return []
    return sorted(scripts.glob("manifest_tool_*.sh"))


def check_skill_tree(target: str, root: Path) -> Check:
    skill_file = root / "SKILL.md"
    tool_file = root / "scripts" / "manifest_tool.py"
    if not skill_file.is_file():
        return Check("FAIL", target, f"missing {skill_file}")
    if not tool_file.is_file():
        return Check("FAIL", target, f"missing {tool_file}")
    stale = stale_shell_scripts(root)
    if stale:
        values = ", ".join(str(path) for path in stale)
        return Check("FAIL", target, f"stale fallback script(s) found: {values}")
    if not run_manifest_tool(root):
        return Check("FAIL", target, f"manifest tool failed under {root}")
    return Check("OK", target, f"installed at {root}")


def check_shared_scan_agent(paths: InstallPaths, target: str) -> Check:
    kind, root = shared_scan_skill_target(paths, target)
    check = check_skill_tree(target, root)
    if check.status != "OK":
        return check
    legacy_root = native_skill_path(paths, target)
    if kind == "shared" and legacy_root.exists():
        return Check(
            "WARN",
            target,
            f"installed via shared skill at {root}; duplicate native skill still exists at {legacy_root}",
        )
    return Check("OK", target, f"installed via {kind} skill at {root}")


def doctor(paths: InstallPaths, agents: list[str]) -> list[Check]:
    checks: list[Check] = []
    targets = shared_scan_targets(paths, agents)
    root = implementation_root(paths, targets)

    if adapter_needs_skill_root(agents) and not any(target == root for _, target in targets.values()):
        checks.append(check_skill_tree("implementation", root))
    if "codex" in agents:
        checks.append(check_shared_scan_agent(paths, "codex"))
    if "claude" in agents:
        checks.append(check_claude(paths))
    if "opencode" in agents:
        checks.append(check_opencode(paths, root))
    if "cursor" in agents:
        checks.append(check_shared_scan_agent(paths, "cursor"))
    if "copilot" in agents:
        checks.append(check_shared_scan_agent(paths, "copilot"))
    if "gemini" in agents:
        checks.append(check_gemini(paths, root))
    return checks


def check_claude(paths: InstallPaths) -> Check:
    manifest = paths.claude_plugin / ".claude-plugin" / "plugin.json"
    if not manifest.is_file():
        return Check("FAIL", "claude", f"missing {manifest}")
    skill_check = check_skill_tree("claude", paths.claude_skill)
    if skill_check.status != "OK":
        return skill_check

    claude = shutil.which("claude")
    if claude is None:
        return Check("WARN", "claude", f"installed at {paths.claude_plugin}; claude CLI not found for plugin validation")

    result = run_text_command(
        [claude, "plugin", "validate", str(paths.claude_plugin)],
        timeout=30,
    )
    if result.returncode != 0:
        return Check("FAIL", "claude", f"plugin validation failed for {paths.claude_plugin}")
    return Check("OK", "claude", f"plugin installed at {paths.claude_plugin}")


def check_opencode(paths: InstallPaths, skill: Path) -> Check:
    if not paths.opencode_agent.is_file():
        return Check("FAIL", "opencode", f"missing {paths.opencode_agent}")
    text = paths.opencode_agent.read_text(encoding="utf-8")
    if str(skill / "SKILL.md") not in text:
        return Check("FAIL", "opencode", f"{paths.opencode_agent} does not reference {skill}")

    opencode = shutil.which("opencode")
    if opencode is None:
        probes = discover_external_opencode()
        if probes:
            return Check(
                "WARN",
                "opencode",
                (
                    f"agent file installed at {paths.opencode_agent}; host opencode CLI not found; "
                    f"found external runtime(s): {format_runtime_probes(probes)}"
                ),
            )
        return Check("WARN", "opencode", f"agent file installed at {paths.opencode_agent}; opencode CLI not found")

    result = run_text_command(
        [opencode, "agent", "list"],
        timeout=30,
    )
    if result.returncode != 0:
        return Check("FAIL", "opencode", "opencode agent list failed")
    if SKILL_NAME not in result.stdout:
        return Check("FAIL", "opencode", f"opencode agent list did not include {SKILL_NAME}")
    return Check("OK", "opencode", f"agent installed at {paths.opencode_agent}")


def check_gemini(paths: InstallPaths, skill: Path) -> Check:
    manifest = paths.gemini_extension / "gemini-extension.json"
    context = paths.gemini_extension / "GEMINI.md"
    if not manifest.is_file():
        return Check("FAIL", "gemini", f"missing {manifest}")
    if not context.is_file():
        return Check("FAIL", "gemini", f"missing {context}")
    try:
        data = read_json_object(manifest)
        enablement = read_json_object(paths.gemini_enablement)
    except InstallError as exc:
        return Check("FAIL", "gemini", str(exc))
    if data.get("contextFileName") != "GEMINI.md":
        return Check("FAIL", "gemini", f"{manifest} must set contextFileName to GEMINI.md")
    if SKILL_NAME not in enablement:
        return Check("FAIL", "gemini", f"{paths.gemini_enablement} does not enable {SKILL_NAME}")
    text = context.read_text(encoding="utf-8")
    if str(skill / "SKILL.md") not in text:
        return Check("FAIL", "gemini", f"{context} does not reference {skill}")
    return Check("OK", "gemini", f"extension installed at {paths.gemini_extension}")


def print_checks(checks: list[Check]) -> int:
    failures = 0
    for check in checks:
        print(f"{check.status}: {check.target}: {check.message}")
        if check.status == "FAIL":
            failures += 1
    return 1 if failures else 0


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--agents",
        nargs="+",
        help=(
            "agent targets to install; comma-separated or repeated values: "
            "all, codex, claude, opencode, cursor, copilot, gemini "
            "(aliases: vscode, vscode-copilot, github-copilot)"
        ),
    )
    parser.add_argument("--source", help="Better Plan source tree; defaults to this repository")
    parser.add_argument("--codex-home", help="Codex home directory; defaults to $CODEX_HOME or ~/.codex")
    parser.add_argument("--shared-home", help="shared agent home; defaults to $BETTER_PLAN_SHARED_HOME or ~/.agents")
    parser.add_argument("--claude-home", help="Claude home directory; defaults to $CLAUDE_HOME or ~/.claude")
    parser.add_argument("--opencode-config", help="OpenCode config directory; defaults to $OPENCODE_CONFIG_HOME or ~/.config/opencode")
    parser.add_argument("--cursor-home", help="Cursor home directory; defaults to $CURSOR_HOME or ~/.cursor")
    parser.add_argument("--copilot-home", help="GitHub Copilot home directory; defaults to $COPILOT_HOME or ~/.copilot")
    parser.add_argument("--gemini-home", help="Gemini home directory; defaults to $GEMINI_HOME or ~/.gemini")
    parser.add_argument("--gemini-scope", help="Gemini extension enablement scope; defaults to <home>/*")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install Better Plan for local coding agents")
    subparsers = parser.add_subparsers(dest="command", required=True)

    install = subparsers.add_parser("install", help="install Better Plan adapters")
    add_common_arguments(install)
    install.add_argument("--dry-run", action="store_true", help="print planned changes without writing files")
    install.set_defaults(func=install_command)

    update = subparsers.add_parser("update", help="update Better Plan adapters and migrate duplicate installs")
    add_common_arguments(update)
    update.add_argument("--dry-run", action="store_true", help="print planned changes without writing files")
    update.set_defaults(func=update_command)

    doctor_parser = subparsers.add_parser("doctor", help="verify installed adapters")
    add_common_arguments(doctor_parser)
    doctor_parser.set_defaults(func=doctor_command)

    uninstall = subparsers.add_parser("uninstall", help="remove Better Plan adapters")
    add_common_arguments(uninstall)
    uninstall.add_argument("--dry-run", action="store_true", help="print planned removals without deleting files")
    uninstall.add_argument("--remove-shared", action="store_true", help="also remove the shared ~/.agents skill tree")
    uninstall.set_defaults(func=uninstall_command)

    return parser


def install_command(args: argparse.Namespace) -> int:
    paths = default_paths(args)
    agents = parse_agents(args.agents)
    if existing_install_paths(paths, agents):
        print("existing Better Plan install found; switching installer to update")
        return update_command(args)
    for message in install_agents(paths, agents, dry_run=args.dry_run):
        print(message)
    return 0


def update_command(args: argparse.Namespace) -> int:
    paths = default_paths(args)
    agents = parse_agents(args.agents)
    for message in install_agents(paths, agents, dry_run=args.dry_run):
        print(message)
    return 0


def doctor_command(args: argparse.Namespace) -> int:
    paths = default_paths(args)
    agents = parse_agents(args.agents)
    return print_checks(doctor(paths, agents))


def uninstall_command(args: argparse.Namespace) -> int:
    paths = default_paths(args)
    agents = parse_agents(args.agents)
    remove_shared = args.remove_shared or set(agents) == set(AGENTS)
    for message in uninstall_agents(paths, agents, remove_shared=remove_shared, dry_run=args.dry_run):
        print(message)
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        argv.insert(0, "install")
    elif argv[0].startswith("-") and argv[0] not in {"-h", "--help"}:
        argv.insert(0, "install")
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except InstallError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
