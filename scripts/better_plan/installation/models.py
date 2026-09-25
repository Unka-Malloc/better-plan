"""Typed values and immutable installer metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


SKILL_NAME = "better-plan"
VERSION = "3.2.0"
# Four supported hosts. Only Codex has packaged role presets: it is the only host whose role
# files pin a model and reasoning effort. Claude Code, Cursor, and Kilo install unpinned role
# files and inherit whatever the host and the user configured locally.
AGENTS = ("codex", "claude", "cursor", "kilo")
SHARED_SCAN_AGENTS = frozenset({"codex", "cursor", "kilo"})
CURSOR_APP_BUNDLE_CLI = "/Applications/Cursor.app/Contents/Resources/app/bin/cursor"
OPTIONAL_CLIENT_CLI_COMMANDS = {
    "cursor": (
        ("cursor-agent", "--version"),
        ("cursor", "--version"),
        (CURSOR_APP_BUNDLE_CLI, "--version"),
    ),
}
DESCRIPTION = (
    "Decision-complete Better Plan v3 orchestration with one design session, autonomous in-scope "
    "delivery, and one writable review session."
)
# This is the minimum executable payload, not a compatibility inventory. Removed
# top-level implementations must never reappear here.
CURRENT_SKILL_FILES = (
    "README.md",
    "SKILL.md",
    "agents/openai.yaml",
    "references/workflow.md",
    "references/design-principles.md",
    "references/host-configuration.md",
    "references/artificial-analysis-snapshot.json",
    "references/state.md",
    "references/designer.md",
    "references/design-format.md",
    "references/structure-repair.md",
    "references/design-patterns.md",
    "references/worker.md",
    "references/reviewer.md",
    "skills/efficiency-inspector/SKILL.md",
    "skills/efficiency-inspector/agents/openai.yaml",
    "skills/efficiency-inspector/references/adapter-boundary.md",
    "skills/efficiency-inspector/references/data-layout.md",
    "skills/efficiency-inspector/references/token-accounting.md",
    "skills/efficiency-inspector/references/parallel-audit.md",
    "skills/efficiency-inspector/references/timeout-catalog.json",
    "skills/efficiency-inspector/references/timeout-statistics.md",
    "skills/efficiency-inspector/scripts/token_totals.py",
    "skills/efficiency-inspector/scripts/timeout_summary.py",
    "scripts/__init__.py",
    "scripts/manifest_tool.py",
    "scripts/hook_tool.py",
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
    "scripts/better_plan/domain/design_compile.py",
    "scripts/better_plan/domain/tree.py",
    "scripts/better_plan/domain/report.py",
    "scripts/better_plan/domain/validation.py",
    "scripts/better_plan/domain/task_shape.py",
    "scripts/better_plan/domain/model_catalog.json",
    "scripts/better_plan/domain/model_routing.py",
    "scripts/better_plan/infrastructure/__init__.py",
    "scripts/better_plan/infrastructure/workspace.py",
    "scripts/better_plan/infrastructure/plan_render.py",
    "scripts/better_plan/infrastructure/native_roles.py",
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
    "scripts/better_plan/hooks/adapters/__init__.py",
    "scripts/better_plan/hooks/adapters/base.py",
    "scripts/better_plan/hooks/adapters/codex.py",
    "scripts/better_plan/hooks/adapters/claude.py",
    "scripts/better_plan/hooks/adapters/cursor.py",
    "scripts/better_plan/installation/__init__.py",
    "scripts/better_plan/installation/assignments.py",
    "scripts/better_plan/installation/models.py",
    "scripts/better_plan/installation/skills.py",
    "scripts/better_plan/installation/targets.py",
    "scripts/better_plan/installation/doctor.py",
    "scripts/better_plan/installation/service.py",
    "agents/codex/designer.toml",
    "agents/codex/worker.toml",
    "agents/codex/hybrid-worker.toml",
    "agents/codex/reviewer.toml",
    "agents/kilo/better-plan.md",
    "agents/kilo/better-plan-designer.md",
    "agents/kilo/better-plan-worker.md",
    "agents/kilo/better-plan-hybrid-worker.md",
    "agents/kilo/better-plan-reviewer.md",
    "agents/claude-code/designer.md",
    "agents/claude-code/worker.md",
    "agents/claude-code/hybrid-worker.md",
    "agents/claude-code/reviewer.md",
    "agents/cursor/designer.md",
    "agents/cursor/worker.md",
    "agents/cursor/hybrid-worker.md",
    "agents/cursor/reviewer.md",
    "web/plan-report.html",
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
    def cursor_skill(self) -> Path:
        return self.cursor_home / "skills" / SKILL_NAME

    @property
    def cursor_hooks(self) -> Path:
        return self.cursor_home / "hooks.json"

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
