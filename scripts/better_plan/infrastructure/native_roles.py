"""Resolve public native role selectors without changing host configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Iterator

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.8–3.10.
    from .._vendor import tomli as tomllib

from ..domain.models import ToolError
from ..installation.assignments import CODEX_DEFAULT_MATRIX


_SAFE_AGENT_NAME = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")
_SAFE_SELECTOR = re.compile(r"^[A-Za-z0-9._:/+-]{1,128}$")


@dataclass(frozen=True)
class NativeRoleSelector:
    """Public pins only; omitted settings remain inherited by the native host."""

    model: str | None
    reasoning_effort: str | None
    model_provider: str | None
    source: str


def _role_documents(directory: Path) -> Iterator[tuple[Path, dict[str, Any] | None]]:
    if not directory.is_dir():
        return
    for path in sorted(directory.glob("*.toml")):
        try:
            if not path.is_file() or path.stat().st_size > 262_144:
                yield path, None
                continue
            yield path, tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            yield path, None


def configured_codex_role_names(codex_home: Path) -> frozenset[str]:
    """Identify personal roles by TOML name, independent of their filenames."""

    return frozenset(
        value["name"]
        for _, value in _role_documents(codex_home / "agents")
        if value is not None and isinstance(value.get("name"), str)
    )


def _configured_selector(agent_name: str, directory: Path, source: str) -> NativeRoleSelector | None:
    matches: list[dict[str, Any]] = []
    for path, value in _role_documents(directory):
        if value is None:
            if path.stem == agent_name:
                raise ToolError("the configured Codex role cannot be parsed; leave its file unchanged")
            continue
        if value.get("name") == agent_name:
            matches.append(value)
    if len(matches) > 1:
        raise ToolError("multiple Codex role files in one scope declare the requested name")
    if not matches:
        return None
    pins = {}
    for field in ("model", "model_reasoning_effort", "model_provider"):
        value = matches[0].get(field)
        if value is not None and (not isinstance(value, str) or not _SAFE_SELECTOR.fullmatch(value)):
            raise ToolError("the configured Codex role has an invalid public selector")
        pins[field] = value
    return NativeRoleSelector(
        model=pins["model"],
        reasoning_effort=pins["model_reasoning_effort"],
        model_provider=pins["model_provider"],
        source=source,
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
    if delivery is None:
        return None
    _, model, effort, _ = delivery
    return NativeRoleSelector(model, effort, None, "project-recommendation")


def resolve_codex_role(
    agent_name: str,
    codex_home: Path,
    package_root: Path | None = None,
    *,
    project_root: Path | None = None,
) -> NativeRoleSelector | None:
    """Prefer a project role, then a personal role, then an absent-role recommendation."""

    if _SAFE_AGENT_NAME.fullmatch(agent_name) is None:
        return None
    if project_root is not None:
        project = _configured_selector(agent_name, project_root / ".codex" / "agents", "project-codex-role")
        if project is not None:
            return project
    personal = _configured_selector(agent_name, codex_home / "agents", "installed-codex-role")
    if personal is not None:
        return personal
    root = package_root or Path(__file__).resolve().parents[3]
    return _recommended_codex_selector(agent_name, root)
