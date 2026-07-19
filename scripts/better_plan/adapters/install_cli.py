"""Command-line adapter for Better Plan installation use cases."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from ..installation import doctor as _doctor
from ..installation import service as _service
from ..installation import skills as _skills
from ..installation import targets as _targets
from ..installation.models import AGENTS, InstallError as _InstallError, InstallPaths as _InstallPaths


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def default_paths(args: argparse.Namespace) -> _InstallPaths:
    home = Path.home()
    repo_root = Path(args.source).expanduser().resolve() if args.source else REPOSITORY_ROOT
    return _InstallPaths(
        repo_root=repo_root,
        codex_home=Path(args.codex_home or os.environ.get("CODEX_HOME") or home / ".codex").expanduser(),
        shared_home=Path(
            args.shared_home or os.environ.get("BETTER_PLAN_SHARED_HOME") or home / ".agents"
        ).expanduser(),
        claude_home=Path(args.claude_home or os.environ.get("CLAUDE_HOME") or home / ".claude").expanduser(),
        opencode_config=Path(
            args.opencode_config or os.environ.get("OPENCODE_CONFIG_HOME") or home / ".config" / "opencode"
        ).expanduser(),
        cursor_home=Path(args.cursor_home or os.environ.get("CURSOR_HOME") or home / ".cursor").expanduser(),
        copilot_home=Path(args.copilot_home or os.environ.get("COPILOT_HOME") or home / ".copilot").expanduser(),
        gemini_home=Path(args.gemini_home or os.environ.get("GEMINI_HOME") or home / ".gemini").expanduser(),
        gemini_scope=_targets.relative_scope(args.gemini_scope or "*"),
    )


def parse_agents(values: list[str] | None) -> list[str]:
    if not values:
        return list(AGENTS)
    tokens = [token.strip().lower() for value in values for token in value.split(",")]
    if "all" in tokens:
        return list(AGENTS)
    agents: list[str] = []
    invalid: list[str] = []
    for token in tokens:
        if not token:
            continue
        if token not in AGENTS:
            invalid.append(token)
        elif token not in agents:
            agents.append(token)
    if invalid:
        expected = ", ".join(("all", *AGENTS))
        raise _InstallError(f"unknown agent target; expected one of {expected}")
    if not agents:
        raise _InstallError("at least one agent target is required")
    return agents


def print_checks(checks) -> int:
    failures = 0
    for check in checks:
        print(f"{check.status}: {check.target}: {check.message}")
        failures += check.status == "FAIL"
    return 1 if failures else 0


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--agents",
        nargs="+",
        help="agent targets: all, codex, claude, opencode, cursor, copilot, gemini",
    )
    parser.add_argument("--source", help="Better Plan source tree; defaults to this repository")
    parser.add_argument("--codex-home", help="Codex home directory")
    parser.add_argument("--shared-home", help="shared agent home")
    parser.add_argument("--claude-home", help="Claude home directory")
    parser.add_argument("--opencode-config", help="OpenCode config directory")
    parser.add_argument("--cursor-home", help="Cursor home directory")
    parser.add_argument("--copilot-home", help="GitHub Copilot home directory")
    parser.add_argument("--gemini-home", help="Gemini home directory")
    parser.add_argument("--gemini-scope", help="relative Gemini extension enablement pattern")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install Better Plan for local coding agents")
    subparsers = parser.add_subparsers(dest="command", required=True)
    commands = {
        "install": ("install Better Plan adapters", install_command),
        "update": ("update Better Plan adapters", update_command),
        "doctor": ("verify installed adapters", doctor_command),
        "uninstall": ("remove Better Plan adapters", uninstall_command),
        "uninstall-hooks": ("remove Better Plan managed hooks", uninstall_hooks_command),
    }
    for name, (help_text, handler) in commands.items():
        command = subparsers.add_parser(name, help=help_text)
        add_common_arguments(command)
        if name != "doctor":
            command.add_argument("--dry-run", action="store_true")
        if name == "uninstall":
            command.add_argument("--remove-shared", action="store_true")
        command.set_defaults(func=handler)
    return parser


def install_command(args: argparse.Namespace) -> int:
    paths = default_paths(args)
    agents = parse_agents(args.agents)
    if _skills.existing_install_paths(paths, agents):
        print("existing Better Plan install found; switching installer to update")
    for message in _service.install_agents(paths, agents, dry_run=args.dry_run):
        print(message)
    return 0


def update_command(args: argparse.Namespace) -> int:
    paths = default_paths(args)
    agents = parse_agents(args.agents)
    for message in _service.install_agents(paths, agents, dry_run=args.dry_run):
        print(message)
    return 0


def doctor_command(args: argparse.Namespace) -> int:
    return print_checks(_doctor.doctor(default_paths(args), parse_agents(args.agents)))


def uninstall_command(args: argparse.Namespace) -> int:
    paths = default_paths(args)
    agents = parse_agents(args.agents)
    remove_shared = args.remove_shared or set(agents) == set(AGENTS)
    for message in _service.uninstall_agents(
        paths,
        agents,
        remove_shared=remove_shared,
        dry_run=args.dry_run,
    ):
        print(message)
    return 0


def uninstall_hooks_command(args: argparse.Namespace) -> int:
    for message in _service.uninstall_hooks(
        default_paths(args), parse_agents(args.agents), dry_run=args.dry_run
    ):
        print(message)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the installer without exposing implementation symbols at the entrypoint."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        arguments.insert(0, "install")
    elif arguments[0].startswith("-") and arguments[0] not in {"-h", "--help"}:
        arguments.insert(0, "install")
    args = build_parser().parse_args(arguments)
    try:
        return args.func(args)
    except _InstallError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except Exception:
        print("error: installer operation could not be completed safely", file=sys.stderr)
        return 2
