"""Resolve bounded native role selectors for runtime dispatch."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from ..installation.assignments import CODEX_DEFAULT_MATRIX, CODEX_FINDER_MATRIX


_MODEL = re.compile(r'(?m)^model\s*=\s*"([A-Za-z0-9._:/+-]{1,128})"\s*$')
_EFFORT = re.compile(r'(?m)^model_reasoning_effort\s*=\s*"([A-Za-z0-9._+-]{1,64})"\s*$')
_PROVIDER = re.compile(r'(?m)^model_provider\s*=\s*"([A-Za-z0-9._+-]{1,64})"\s*$')
_SAFE_AGENT_NAME = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


@dataclass(frozen=True)
class NativeRoleSelector:
    """One safe public selector, without file paths or provider credentials."""

    model: str
    reasoning_effort: str | None
    model_provider: str | None
    source: str


def _installed_codex_selector(agent_name: str, codex_home: Path) -> NativeRoleSelector | None:
    if _SAFE_AGENT_NAME.fullmatch(agent_name) is None:
        return None
    path = codex_home / "agents" / f"{agent_name}.toml"
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 262_144:
            return None
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    model_match = _MODEL.search(content)
    if model_match is None:
        return None
    effort_match = _EFFORT.search(content)
    provider_match = _PROVIDER.search(content)
    return NativeRoleSelector(
        model=model_match.group(1),
        reasoning_effort=effort_match.group(1) if effort_match is not None else None,
        model_provider=provider_match.group(1) if provider_match is not None else None,
        source="installed-codex-role",
    )


def _recommended_codex_selector(agent_name: str, package_root: Path) -> NativeRoleSelector | None:
    template = package_root / "agents" / "codex" / f"{agent_name}.toml"
    try:
        if template.is_symlink() or not template.is_file() or template.stat().st_size > 262_144:
            return None
        template_content = template.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    if "ASSIGNMENT_PLACEHOLDER" not in template_content:
        return None
    delivery = CODEX_DEFAULT_MATRIX.get(agent_name)
    if delivery is not None:
        _, model, effort, _ = delivery
        return NativeRoleSelector(model, effort, None, "project-recommendation")
    finder = CODEX_FINDER_MATRIX.get(agent_name)
    if finder is not None:
        model, effort = finder
        return NativeRoleSelector(model, effort, None, "project-recommendation")
    return None


def resolve_codex_role(
    agent_name: str,
    codex_home: Path,
    package_root: Path | None = None,
) -> NativeRoleSelector | None:
    """Prefer the exact installed Codex role, then the packaged recommendation."""

    root = package_root or Path(__file__).resolve().parents[3]
    return _installed_codex_selector(agent_name, codex_home) or _recommended_codex_selector(agent_name, root)
