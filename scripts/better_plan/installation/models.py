"""Typed values and immutable installer metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .. import __version__


SKILL_NAME = "better-plan"
# One version for the whole package: the CLI reports it, and the Claude Code plugin
# manifest embeds it, so a host can always name the generation it installed.
VERSION = __version__
# Five supported hosts. Only Codex has packaged role presets: it is the only host whose role
# files pin a model and reasoning effort. Claude Code, Cursor, and Kilo install unpinned role
# files and inherit whatever the host and the user configured locally.
AGENTS = ("codex", "claude", "cursor", "kilo", "dsh")
SHARED_SCAN_AGENTS = frozenset({"codex", "cursor", "kilo", "dsh"})
CURSOR_APP_BUNDLE_CLI = "/Applications/Cursor.app/Contents/Resources/app/bin/cursor"
OPTIONAL_CLIENT_CLI_COMMANDS = {
    "cursor": (
        ("cursor-agent", "--version"),
        ("cursor", "--version"),
        (CURSOR_APP_BUNDLE_CLI, "--version"),
    ),
}
DESCRIPTION = (
    "Agent-neutral Checkpoints Tree delivery: one Tree.json owns every Task, executable Node, "
    "dependency, transition, executor, and evidence record."
)
# This is the minimum executable payload, not a compatibility inventory. Removed
# top-level implementations must never reappear here.
CURRENT_SKILL_FILES = (
    "README.md",
    "SKILL.md",
    "agents/openai.yaml",
    "references/design-principles.md",
    "references/host-configuration.md",
    "references/designer.md",
    "references/checkpoints-tree.md",
    "references/programme.md",
    "references/worker.md",
    "references/reviewer.md",
    "scripts/__init__.py",
    "scripts/manifest_tool.py",
    "scripts/install.py",
    "scripts/better_plan/__init__.py",
    "scripts/better_plan/_vendor/__init__.py",
    "scripts/better_plan/_vendor/README.md",
    "scripts/better_plan/_vendor/tomli/__init__.py",
    "scripts/better_plan/_vendor/tomli/_parser.py",
    "scripts/better_plan/_vendor/tomli/_re.py",
    "scripts/better_plan/_vendor/tomli/_types.py",
    "scripts/better_plan/_vendor/tomli/py.typed",
    "scripts/better_plan/_vendor/tomli/LICENSE",
    "scripts/better_plan/domain/__init__.py",
    "scripts/better_plan/domain/models.py",
    "scripts/better_plan/domain/checkpoints_tree.py",
    "scripts/better_plan/domain/programme.py",
    "scripts/better_plan/domain/model_catalog.json",
    "scripts/better_plan/domain/model_routing.py",
    "scripts/better_plan/infrastructure/__init__.py",
    "scripts/better_plan/infrastructure/command_runner.py",
    "scripts/better_plan/infrastructure/workspace.py",
    "scripts/better_plan/infrastructure/native_roles.py",
    "scripts/better_plan/application/__init__.py",
    "scripts/better_plan/application/tree_workflow.py",
    "scripts/better_plan/application/programme_workflow.py",
    "scripts/better_plan/adapters/__init__.py",
    "scripts/better_plan/adapters/manifest_cli.py",
    "scripts/better_plan/adapters/install_cli.py",
    "scripts/better_plan/installation/__init__.py",
    "scripts/better_plan/installation/assignments.py",
    "scripts/better_plan/installation/models.py",
    "scripts/better_plan/installation/skills.py",
    "scripts/better_plan/installation/targets.py",
    "scripts/better_plan/installation/doctor.py",
    "scripts/better_plan/installation/service.py",
    "agents/codex/designer.toml",
    "agents/codex/worker.toml",
    "agents/codex/reviewer.toml",
    "agents/kilo/better-plan.md",
    "agents/kilo/better-plan-designer.md",
    "agents/kilo/better-plan-worker.md",
    "agents/kilo/better-plan-reviewer.md",
    "agents/claude-code/designer.md",
    "agents/claude-code/worker.md",
    "agents/claude-code/reviewer.md",
    "agents/cursor/designer.md",
    "agents/cursor/worker.md",
    "agents/cursor/reviewer.md",
)


class InstallError(RuntimeError):
    """Raised when an installation operation cannot complete safely."""


@dataclass(frozen=True)
class InstallPaths:
    repo_root: Path
    codex_home: Path
    shared_home: Path
    claude_home: Path
    cursor_home: Path
    kilo_home: Path
    kilo_config: Path

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
    def cursor_skill(self) -> Path:
        return self.cursor_home / "skills" / SKILL_NAME

    @property
    def kilo_skill(self) -> Path:
        return self.kilo_home / "skills" / SKILL_NAME

    @property
    def kilo_agents(self) -> Path:
        return self.kilo_config / "agents"


@dataclass(frozen=True)
class Check:
    status: str
    target: str
    message: str
