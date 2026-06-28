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
AGENTS = ("codex", "claude", "opencode", "gemini")
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


def adapter_needs_shared(agents: Iterable[str]) -> bool:
    return any(agent in {"opencode", "gemini"} for agent in agents)


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


def opencode_agent_text(paths: InstallPaths) -> str:
    skill = paths.shared_skill
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


def gemini_context_text(paths: InstallPaths) -> str:
    skill = paths.shared_skill
    return f"""# Better Plan

When the user asks to use Better Plan, continue a Better Plan workflow, inspect project progress, or execute plan/checkpoint work, read `{skill / "SKILL.md"}` completely and follow it as the active workflow.

Use `{skill / "scripts" / "manifest_tool.py"}` for UUID generation, status transition checks, and Manifest.json / Checkpoints.json validation.

Do not preserve legacy compatibility, old implementations, fallback shims, deprecated paths, versioned wrappers, or duplicate implementations unless an existing external service contract requires them.

Work from the current project root unless the user gives another root, preserve unrelated user changes, and verify real behavior before reporting completion.
"""


def install_gemini_extension(paths: InstallPaths, *, dry_run: bool) -> None:
    if dry_run:
        return
    paths.gemini_extension.mkdir(parents=True, exist_ok=True)
    write_json(paths.gemini_extension / "gemini-extension.json", gemini_manifest(), backup=True)
    write_text(paths.gemini_extension / "GEMINI.md", gemini_context_text(paths), backup=True)
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


def install_agents(paths: InstallPaths, agents: list[str], *, dry_run: bool) -> list[str]:
    validate_source_tree(paths.repo_root)
    messages: list[str] = []

    if adapter_needs_shared(agents):
        copy_skill_tree(paths.repo_root, paths.shared_skill, dry_run=dry_run)
        messages.append(f"shared: {'would update' if dry_run else 'updated'} {paths.shared_skill}")

    if "codex" in agents:
        copy_skill_tree(paths.repo_root, paths.codex_skill, dry_run=dry_run)
        messages.append(f"codex: {'would update' if dry_run else 'updated'} {paths.codex_skill}")

    if "claude" in agents:
        install_claude_plugin(paths, dry_run=dry_run)
        messages.append(f"claude: {'would update' if dry_run else 'updated'} {paths.claude_plugin}")

    if "opencode" in agents:
        if not dry_run:
            write_text(paths.opencode_agent, opencode_agent_text(paths), backup=True)
        messages.append(f"opencode: {'would update' if dry_run else 'updated'} {paths.opencode_agent}")

    if "gemini" in agents:
        install_gemini_extension(paths, dry_run=dry_run)
        messages.append(f"gemini: {'would update' if dry_run else 'updated'} {paths.gemini_extension}")

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


def run_manifest_tool(skill_root: Path) -> bool:
    tool = skill_root / "scripts" / "manifest_tool.py"
    if not tool.is_file():
        return False
    result = subprocess.run(
        [sys.executable, str(tool), "uuid"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
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


def doctor(paths: InstallPaths, agents: list[str]) -> list[Check]:
    checks: list[Check] = []

    if adapter_needs_shared(agents):
        checks.append(check_skill_tree("shared", paths.shared_skill))
    if "codex" in agents:
        checks.append(check_skill_tree("codex", paths.codex_skill))
    if "claude" in agents:
        checks.append(check_claude(paths))
    if "opencode" in agents:
        checks.append(check_opencode(paths))
    if "gemini" in agents:
        checks.append(check_gemini(paths))
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

    result = subprocess.run(
        [claude, "plugin", "validate", str(paths.claude_plugin)],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        return Check("FAIL", "claude", f"plugin validation failed for {paths.claude_plugin}")
    return Check("OK", "claude", f"plugin installed at {paths.claude_plugin}")


def check_opencode(paths: InstallPaths) -> Check:
    if not paths.opencode_agent.is_file():
        return Check("FAIL", "opencode", f"missing {paths.opencode_agent}")
    text = paths.opencode_agent.read_text(encoding="utf-8")
    if str(paths.shared_skill / "SKILL.md") not in text:
        return Check("FAIL", "opencode", f"{paths.opencode_agent} does not reference the shared skill")

    opencode = shutil.which("opencode")
    if opencode is None:
        return Check("WARN", "opencode", f"agent file installed at {paths.opencode_agent}; opencode CLI not found")

    result = subprocess.run(
        [opencode, "agent", "list"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        return Check("FAIL", "opencode", "opencode agent list failed")
    if SKILL_NAME not in result.stdout:
        return Check("FAIL", "opencode", f"opencode agent list did not include {SKILL_NAME}")
    return Check("OK", "opencode", f"agent installed at {paths.opencode_agent}")


def check_gemini(paths: InstallPaths) -> Check:
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
    if str(paths.shared_skill / "SKILL.md") not in text:
        return Check("FAIL", "gemini", f"{context} does not reference the shared skill")
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
        help="agent targets to install; comma-separated or repeated values: all, codex, claude, opencode, gemini",
    )
    parser.add_argument("--source", help="Better Plan source tree; defaults to this repository")
    parser.add_argument("--codex-home", help="Codex home directory; defaults to $CODEX_HOME or ~/.codex")
    parser.add_argument("--shared-home", help="shared agent home; defaults to $BETTER_PLAN_SHARED_HOME or ~/.agents")
    parser.add_argument("--claude-home", help="Claude home directory; defaults to $CLAUDE_HOME or ~/.claude")
    parser.add_argument("--opencode-config", help="OpenCode config directory; defaults to $OPENCODE_CONFIG_HOME or ~/.config/opencode")
    parser.add_argument("--gemini-home", help="Gemini home directory; defaults to $GEMINI_HOME or ~/.gemini")
    parser.add_argument("--gemini-scope", help="Gemini extension enablement scope; defaults to <home>/*")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install Better Plan for local coding agents")
    subparsers = parser.add_subparsers(dest="command", required=True)

    install = subparsers.add_parser("install", help="install Better Plan adapters")
    add_common_arguments(install)
    install.add_argument("--dry-run", action="store_true", help="print planned changes without writing files")
    install.set_defaults(func=install_command)

    update = subparsers.add_parser("update", help="alias for install")
    add_common_arguments(update)
    update.add_argument("--dry-run", action="store_true", help="print planned changes without writing files")
    update.set_defaults(func=install_command)

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
