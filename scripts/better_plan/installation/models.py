"""Typed values and immutable installer metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


SKILL_NAME = "better-plan"
VERSION = "0.3.0"
AGENTS = ("codex", "claude", "opencode", "cursor", "copilot", "gemini")
SHARED_SCAN_AGENTS = frozenset({"codex", "cursor", "copilot"})
ADAPTER_SKILL_AGENTS = frozenset({"opencode", "gemini"})
OPTIONAL_CLIENT_CLI_COMMANDS = {
    "cursor": ("cursor", "--version"),
    "copilot": ("copilot", "--version"),
}
DESCRIPTION = "Design-first Better Plan orchestration with deterministic acceptance and regression."
# This is the minimum executable payload, not a compatibility inventory. Removed
# top-level implementations must never reappear here.
CURRENT_SKILL_FILES = (
    "README.md",
    "SKILL.md",
    "agents/openai.yaml",
    "references/state-files.md",
    "references/orchestration-main.md",
    "references/acceptance-designer.md",
    "references/acceptance-reviewer.md",
    "references/executor.md",
    "references/auditor.md",
    "scripts/__init__.py",
    "scripts/manifest_tool.py",
    "scripts/hook_tool.py",
    "scripts/install.py",
    "scripts/better_plan/__init__.py",
    "scripts/better_plan/domain/__init__.py",
    "scripts/better_plan/domain/models.py",
    "scripts/better_plan/domain/validation.py",
    "scripts/better_plan/domain/design.py",
    "scripts/better_plan/domain/transitions.py",
    "scripts/better_plan/domain/roles.py",
    "scripts/better_plan/infrastructure/__init__.py",
    "scripts/better_plan/infrastructure/workspace.py",
    "scripts/better_plan/infrastructure/regression.py",
    "scripts/better_plan/application/__init__.py",
    "scripts/better_plan/application/agent_completion.py",
    "scripts/better_plan/application/workflow.py",
    "scripts/better_plan/adapters/__init__.py",
    "scripts/better_plan/adapters/manifest_cli.py",
    "scripts/better_plan/adapters/install_cli.py",
    "scripts/better_plan/hooks/__init__.py",
    "scripts/better_plan/hooks/scope.py",
    "scripts/better_plan/hooks/context.py",
    "scripts/better_plan/hooks/protocols.py",
    "scripts/better_plan/hooks/runtime.py",
    "scripts/better_plan/hooks/config.py",
    "scripts/better_plan/installation/__init__.py",
    "scripts/better_plan/installation/models.py",
    "scripts/better_plan/installation/skills.py",
    "scripts/better_plan/installation/targets.py",
    "scripts/better_plan/installation/doctor.py",
    "scripts/better_plan/installation/service.py",
)


class InstallError(RuntimeError):
    """Raised when an installation operation cannot complete safely."""


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
    def codex_hooks(self) -> Path:
        return self.codex_home / "hooks.json"

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
    def claude_settings(self) -> Path:
        return self.claude_home / "settings.json"

    @property
    def opencode_agent(self) -> Path:
        return self.opencode_config / "agents" / f"{SKILL_NAME}.md"

    @property
    def cursor_skill(self) -> Path:
        return self.cursor_home / "skills" / SKILL_NAME

    @property
    def cursor_hooks(self) -> Path:
        return self.cursor_home / "hooks.json"

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
class WslOpenCodeRuntime:
    distro: str
    location: str
    home: str
    version: str
