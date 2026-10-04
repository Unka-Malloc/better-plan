"""Target-specific Better Plan installer adapters for every supported host."""

from __future__ import annotations

import json
import hashlib
import posixpath
import re
import shutil
import subprocess
from pathlib import Path

from ..domain.models import ToolError
from ..infrastructure.native_roles import configured_codex_role_names, _role_documents, tomllib
from .models import (
    AGENTS,
    DESCRIPTION,
    SKILL_NAME,
    VERSION,
    InstallError as _InstallError,
    InstallPaths as _InstallPaths,
)
from .assignments import RoleAssignment as _RoleAssignment, select_role_assignments as _select_role_assignments
from .skills import (
    copy_skill_tree as _copy_skill_tree,
    remove_path as _remove_path,
    staged_tree as _staged_tree,
)


NATIVE_ROLE_FILES: dict[str, tuple[str, ...]] = {
    "codex": ("designer.toml", "worker.toml", "reviewer.toml", "verifier.toml", "adversary.toml"),
    "claude": ("designer.md", "worker.md", "reviewer.md", "verifier.md", "adversary.md"),
    "cursor": ("designer.md", "worker.md", "reviewer.md", "verifier.md", "adversary.md"),
}
# Claude Code keeps its packaged role sources under `agents/claude-code`.
_NATIVE_SOURCE_TARGET = {"claude": "claude-code"}
# Hosts with no packaged preset: their role files inherit model, variant, and reasoning effort
# from the host and the user's own configuration, so Better Plan writes no selector into them.
UNPINNED_HOSTS = ("claude", "cursor")
KILO_AGENT_FILES = (
    "better-plan.md",
    "better-plan-designer.md",
    "better-plan-worker.md",
    "better-plan-reviewer.md",
    "better-plan-verifier.md",
    "better-plan-adversary.md",
)
# These roles may be added to recognized earlier matrices, independently.
_ADDITIVE_ROLES = ("verifier", "adversary")
_BASE_ROLES = ("designer", "worker", "reviewer")
# Kilo owns model and variant selection. A packaged Kilo file must never pin one.
_KILO_SELECTOR_PIN = re.compile(r"(?m)^(?:model|variant|reasoning_effort|reasoningEffort)\s*:")


def _codex_role_names() -> tuple[str, ...]:
    return tuple(posixpath.splitext(filename)[0] for filename in NATIVE_ROLE_FILES["codex"])


def _native_role_directory(paths: _InstallPaths, target: str) -> Path:
    if target == "codex":
        return paths.codex_home / "agents"
    if target == "claude":
        return paths.claude_home / "agents"
    if target == "cursor":
        return paths.cursor_home / "agents"
    raise _InstallError("native role templates are unavailable for this target")


def _native_source_directory(paths: _InstallPaths, target: str) -> Path:
    return paths.repo_root / "agents" / _NATIVE_SOURCE_TARGET.get(target, target)


def unpinned_role_payload(paths: _InstallPaths, target: str) -> dict[str, bytes]:
    """Return assignment-neutral prompt files for a host-owned selector."""

    filenames = NATIVE_ROLE_FILES.get(target)
    if filenames is None or target not in UNPINNED_HOSTS:
        raise _InstallError("native role templates are unavailable for this target")
    source = _native_source_directory(paths, target)
    payload: dict[str, bytes] = {}
    try:
        for filename in filenames:
            text = (source / filename).read_text(encoding="utf-8")
            if (
                not text.strip()
                or not text.startswith("---\n")
                or "\n---\n" not in text[4:]
            ):
                raise ValueError
            payload[filename] = text.encode("utf-8")
    except (OSError, UnicodeError, ValueError):
        raise _InstallError("%s role template source is missing or malformed" % target)
    return payload


def _native_receipt_path(destination: Path) -> Path:
    """Return metadata outside the native agent directory.

    Keeping the receipt beside (rather than inside) the host directory avoids
    presenting Better Plan bookkeeping as an additional native agent file.
    """

    return destination.with_name(f"{destination.name}.better-plan.json")


def _kilo_receipt_path(paths: _InstallPaths) -> Path:
    return _native_receipt_path(paths.kilo_agents)


def kilo_agent_configuration_exists(paths: _InstallPaths) -> bool:
    """Return whether any same-name local Kilo Agent state already exists."""

    receipt = _kilo_receipt_path(paths)
    if receipt.exists() or receipt.is_symlink():
        return True
    return any(
        (paths.kilo_agents / filename).exists()
        or (paths.kilo_agents / filename).is_symlink()
        for filename in KILO_AGENT_FILES
    )


def _validate_kilo_sources(paths: _InstallPaths) -> dict[str, bytes]:
    source = paths.repo_root / "agents" / "kilo"
    payload: dict[str, bytes] = {}
    try:
        for filename in KILO_AGENT_FILES:
            text = (source / filename).read_text(encoding="utf-8")
            if not text.startswith("---\n") or "\n---\n" not in text[4:]:
                raise ValueError
            # The host owns model, variant, and reasoning selection; every packaged
            # Kilo file inherits all three and the installer writes no selector.
            if _KILO_SELECTOR_PIN.search(text):
                raise ValueError
            if filename == "better-plan.md":
                required = (
                    "mode: primary",
                    '"*": allow',
                    "better-plan: allow",
                    "Read the installed `better-plan` SKILL.md",
                )
            else:
                # These equal host permissions keep all packaged Subagents at the host's leaf boundary.
                required = (
                    "mode: subagent",
                    "task: deny",
                    "question: deny",
                    "Read the installed `better-plan` SKILL.md",
                )
            if any(value not in text for value in required):
                raise ValueError
            payload[filename] = text.encode("utf-8")
    except (OSError, UnicodeError, ValueError):
        raise _InstallError("Kilo Agent template source is missing or malformed")
    return payload


def _load_kilo_receipt(path: Path) -> dict[str, str] | None:
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise _InstallError("Kilo Agent receipt is invalid")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise _InstallError("Kilo Agent receipt is invalid")
    if (
        not isinstance(value, dict)
        or set(value) != {"schema_version", "target", "files"}
        or value.get("schema_version") != 1
        or value.get("target") != "kilo"
    ):
        raise _InstallError("Kilo Agent receipt is invalid")
    files = value.get("files")
    if (
        not isinstance(files, dict)
        or not _recognized_matrix_files(set(files), "kilo")
        or any(
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            for digest in files.values()
        )
    ):
        raise _InstallError("Kilo Agent receipt is invalid")
    return {str(name): str(digest) for name, digest in files.items()}


def _write_kilo_receipt(path: Path, payload: dict[str, bytes]) -> None:
    value = {
        "schema_version": 1,
        "target": "kilo",
        "files": {name: _content_digest(content) for name, content in payload.items()},
    }
    try:
        with path.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(value, sort_keys=True) + "\n")
    except OSError as exc:
        raise _InstallError("could not write Kilo Agent receipt") from exc


def _replace_kilo_receipt(path: Path, files: dict[str, str]) -> None:
    """Refresh Kilo receipt digests after a prompt-only update.

    Kilo pins no model, so only the digests of the maintained prompt files change.
    """

    value = {"schema_version": 1, "target": "kilo", "files": files}
    try:
        path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as exc:
        raise _InstallError("could not write Kilo Agent receipt") from exc


def _create_native_role(path: Path, content: bytes) -> None:
    try:
        with path.open("xb") as stream:
            stream.write(content)
    except OSError as exc:
        raise _InstallError("could not create native role; existing role files are never overwritten") from exc


def install_kilo_agent_matrix(paths: _InstallPaths, *, dry_run: bool) -> list[str]:
    """Install the namespaced Kilo matrix once without adopting local files."""

    payload = _validate_kilo_sources(paths)
    if kilo_agent_configuration_exists(paths):
        messages = ["native: preserved kilo Agent matrix"]
        upgrade, managed_roles = _upgrade_additive_roles(paths, "kilo", dry_run=dry_run)
        messages.extend(upgrade)
        messages.extend(_refresh_kilo_prompts(
            paths, dry_run=dry_run, skip_roles=set(_ADDITIVE_ROLES) - managed_roles
        ))
        return messages
    destination = paths.kilo_agents
    if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        raise _InstallError("Kilo Agent destination is not a managed directory")
    if dry_run:
        return ["native: would install kilo Agent matrix"]
    destination.mkdir(parents=True, exist_ok=True)
    for filename, content in payload.items():
        _create_native_role(destination / filename, content)
    _write_kilo_receipt(_kilo_receipt_path(paths), payload)
    return ["native: installed kilo Agent matrix"]


def kilo_agent_status(paths: _InstallPaths) -> tuple[bool, str]:
    """Compare the installed Kilo Agents with the packaged matrix.

    Kilo pins no model, so its Agent files are installed verbatim and can be compared byte for
    byte. Receipt integrity is checked independently; neither check rewrites host files.
    """

    try:
        sources = _validate_kilo_sources(paths)
    except _InstallError:
        return False, "the packaged Kilo Agent sources are unreadable"
    missing: list[str] = []
    changed: list[str] = []
    try:
        for filename, content in sorted(sources.items()):
            path = paths.kilo_agents / filename
            if path.is_symlink() or not path.is_file():
                missing.append(filename)
            elif path.read_text(encoding="utf-8") != content.decode("utf-8"):
                changed.append(filename)
    except OSError:
        return False, "Kilo Agent files are unreadable"
    if missing:
        return False, "missing Agent file(s): %s" % ", ".join(missing)
    if changed:
        return False, "Agent template(s) differ: %s; difference alone does not establish a workflow conflict" % ", ".join(changed)
    return True, "current namespaced Kilo Agent matrix verified (%d files)" % len(sources)


def native_role_configuration_exists(paths: _InstallPaths, target: str) -> bool:
    """Return whether this host already owns any local Better Plan role state."""

    destination = _native_role_directory(paths, target)
    receipt = _native_receipt_path(destination)
    if receipt.exists() or receipt.is_symlink():
        return True
    if target == "codex":
        # An unreadable or oversized file may still declare a colliding host identity.
        # Do not treat an incomplete scan as permission to install a fresh matrix.
        if any(document is None or document.get("name") in _codex_role_names()
               for _, document in _role_documents(destination)):
            return True
    if target in UNPINNED_HOSTS:
        packaged_names = {Path(filename).stem for filename in NATIVE_ROLE_FILES[target]}
        # Native identities survive filename changes. Unreadable names cannot
        # establish that a first install is safe either.
        if any(_markdown_role_name(path) in packaged_names | {None}
               for path in destination.glob("*.md")):
            return True
    return any(
        (destination / filename).exists() or (destination / filename).is_symlink()
        for filename in NATIVE_ROLE_FILES[target]
    )


def _content_digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _assignment_value(value: object) -> _RoleAssignment:
    required = {
        "role", "agent_name", "model", "reasoning_effort", "benchmark_id",
        "index_score", "cost_per_task_usd", "source",
    }
    # A receipt is written once at first installation and later refreshed only by a prompt
    # update, so the shapes written by earlier versions must stay readable: `index_basis`
    # is accepted and ignored, because evaluation now always uses the single standard
    # Intelligence Index.
    if not isinstance(value, dict) or set(value) not in (required, required | {"index_basis"}):
        raise _InstallError("native role template receipt is invalid")
    # Host-default provenance records no invented model, effort, or benchmark.
    if value.get("source") == "host-default":
        if (
            value.get("role") not in _ADDITIVE_ROLES or value.get("agent_name") != value.get("role")
            or any(value.get(field) is not None for field in (
                "model", "reasoning_effort", "benchmark_id", "index_score", "cost_per_task_usd"
            ))
            or "index_basis" in value
        ):
            raise _InstallError("native role template receipt is invalid")
        return _RoleAssignment(**value)
    # Explicit presets can precede a benchmark catalog row; never fabricate provenance.
    if value.get("source") == "codex-preset-unbenchmarked":
        if (
            value.get("role") not in (*_BASE_ROLES, *_ADDITIVE_ROLES)
            or value.get("agent_name") != value.get("role")
            or any(not isinstance(value.get(field), str) or not value[field].strip()
                   for field in ("model", "reasoning_effort"))
            or any(value.get(field) is not None
                   for field in ("benchmark_id", "index_score", "cost_per_task_usd"))
            or "index_basis" in value
        ):
            raise _InstallError("native role template receipt is invalid")
        return _RoleAssignment(**value)
    strings = ("role", "agent_name", "model", "benchmark_id", "source")
    if any(not isinstance(value.get(field), str) or not str(value[field]).strip() for field in strings):
        raise _InstallError("native role template receipt is invalid")
    effort = value.get("reasoning_effort")
    if effort is not None and (not isinstance(effort, str) or not effort.strip()):
        raise _InstallError("native role template receipt is invalid")
    if type(value.get("index_score")) is not int:
        raise _InstallError("native role template receipt is invalid")
    cost = value.get("cost_per_task_usd")
    if cost is not None and (isinstance(cost, bool) or not isinstance(cost, (int, float)) or cost < 0):
        raise _InstallError("native role template receipt is invalid")
    legacy_basis = value.get("index_basis", "")
    if not isinstance(legacy_basis, str) or legacy_basis not in ("", "coding_agent", "intelligence"):
        raise _InstallError("native role template receipt is invalid")
    return _RoleAssignment(
        role=str(value["role"]),
        agent_name=str(value["agent_name"]),
        model=str(value["model"]),
        reasoning_effort=None if effort is None else str(effort),
        benchmark_id=str(value["benchmark_id"]),
        index_score=int(value["index_score"]),
        cost_per_task_usd=None if cost is None else float(cost),
        source=str(value["source"]),
    )


def _load_native_receipt(path: Path, target: str) -> dict[str, object] | None:
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise _InstallError("native role template receipt is invalid")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise _InstallError("native role template receipt is invalid")
    if not isinstance(value, dict) or value.get("schema_version") != 3 or value.get("target") != target or set(value) != {"schema_version", "target", "files", "assignments"}:
        raise _InstallError("native role template receipt is invalid")
    files = value.get("files")
    if not isinstance(files, dict) or any(
        not isinstance(name, str) or not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
        for name, digest in files.items()
    ):
        raise _InstallError("native role template receipt is invalid")
    assignments = value.get("assignments")
    if not isinstance(assignments, dict) or set(assignments) != set(files):
        raise _InstallError("native role template receipt is invalid")
    parsed_by_file = {name: _assignment_value(assignment) for name, assignment in assignments.items()}
    if any(parsed_by_file[name].agent_name != posixpath.splitext(name)[0] for name in parsed_by_file):
        raise _InstallError("native role template receipt is invalid")
    parsed = {assignment.agent_name: assignment for assignment in parsed_by_file.values()}
    if len(parsed) != len(parsed_by_file):
        raise _InstallError("native role template receipt is invalid")
    return {"files": {name: str(digest) for name, digest in files.items()}, "assignments": parsed}


def _assignment_payload(assignment: _RoleAssignment) -> dict[str, object]:
    return {
        "role": assignment.role,
        "agent_name": assignment.agent_name,
        "model": assignment.model,
        "reasoning_effort": assignment.reasoning_effort,
        "benchmark_id": assignment.benchmark_id,
        "index_score": assignment.index_score,
        "cost_per_task_usd": assignment.cost_per_task_usd,
        "source": assignment.source,
    }


def _write_native_receipt(path: Path, target: str, payload: list[tuple[str, bytes, _RoleAssignment]]) -> None:
    value = {
        "schema_version": 3,
        "target": target,
        "files": {filename: _content_digest(content) for filename, content, _ in payload},
        "assignments": {filename: _assignment_payload(assignment) for filename, _, assignment in payload},
    }
    try:
        with path.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(value, sort_keys=True) + "\n")
    except OSError as exc:
        raise _InstallError("could not write native role template receipt") from exc


def _replace_native_receipt(
    path: Path,
    digests: dict[str, str],
) -> None:
    """Refresh Codex receipt digests after a prompt-only update.

    Assignment provenance stays as originally selected: host-owned selector fields
    are never rewritten by a prompt refresh.
    """

    try:
        # Retain the original serialized provenance, including legacy metadata.
        # Only prompts actually refreshed may get a new digest; unrelated drift
        # remains visible to Doctor instead of being silently rebaselined.
        value = json.loads(path.read_text(encoding="utf-8"))
        value["files"].update(digests)
        path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as exc:
        raise _InstallError("could not write native role template receipt") from exc


def _validate_native_sources(paths: _InstallPaths, target: str) -> dict[str, str]:
    filenames = NATIVE_ROLE_FILES.get(target)
    if filenames is None:
        raise _InstallError("native role templates are unavailable for this target")
    source = _native_source_directory(paths, target)
    payload: dict[str, str] = {}
    try:
        for filename in filenames:
            text = (source / filename).read_text(encoding="utf-8")
            if not text.strip():
                raise ValueError
            if not text.startswith("name = ") or "developer_instructions =" not in text:
                raise ValueError
            payload[posixpath.splitext(filename)[0]] = text
    except (OSError, UnicodeError, ValueError, TypeError):
        raise _InstallError("native role template source is missing or malformed")
    return payload


def _render_native_source(source: str, assignment: _RoleAssignment) -> bytes:
    """Render one assignment-neutral role prompt with its configured TOML selectors."""

    if assignment.model is None:
        return source.encode("utf-8")
    rendered = source
    marker = "sandbox_mode = "
    position = rendered.find(marker)
    if position < 0:
        raise _InstallError("native role template source is missing or malformed")
    selector = f'model = "{assignment.model}"\n'
    if assignment.reasoning_effort is not None:
        selector += f'model_reasoning_effort = "{assignment.reasoning_effort}"\n'
    rendered = rendered[:position] + selector + rendered[position:]
    return rendered.encode("utf-8")


def _merge_markdown_prompt(existing: str, expected: str) -> str | None:
    """Replace description and body, preserving host-owned frontmatter keys.

    ``name``, ``tools``, ``permission``, ``mode``, ``temperature`` and any local key
    stay byte-identical. A file without a recognizable frontmatter block is left
    untouched by returning ``None``.
    """

    def split(text: str) -> tuple[str, list[str], str, str] | None:
        opening = re.match(r"---\r?\n", text)
        if opening is None:
            return None
        closing = re.search(r"(?m)^---\r?\n", text[opening.end():])
        if closing is None:
            return None
        end = opening.end() + closing.start()
        body = opening.end() + closing.end()
        return text[:opening.end()], text[opening.end():end].splitlines(keepends=True), text[end:body], text[body:]

    current = split(existing)
    target = split(expected)
    if current is None or target is None:
        return None
    opening, front, closing, _ = current
    _, target_front, _, target_body = target
    newline = "\r\n" if opening.endswith("\r\n") else "\n"
    description = next(
        (line.rstrip("\r\n") for line in target_front if line.startswith("description:")), None
    )
    merged: list[str] = []
    replaced = False
    for line in front:
        if line.startswith("description:"):
            replaced = True
            if description is not None:
                ending = "\r\n" if line.endswith("\r\n") else "\n"
                merged.append(description + ending)
            continue
        merged.append(line)
    if not replaced and description is not None:
        index = next(
            (position for position, line in enumerate(target_front)
             if line.startswith("description:")), len(merged),
        )
        merged.insert(min(index, len(merged)), description + newline)
    body = target_body.replace("\r\n", "\n").replace("\n", newline)
    return opening + "".join(merged) + closing + body


def _merge_codex_prompt(existing: str, rendered: str) -> str | None:
    """Replace description and developer_instructions, preserving selector lines.

    ``model``, ``model_reasoning_effort``, ``sandbox_mode`` and any local key stay
    byte-identical. A file without a recognizable prompt block is left untouched.
    """

    def locate(text: str) -> tuple[list[str], str, int, int] | None:
        lines = text.splitlines(keepends=True)
        description: str | None = None
        start = end = None
        for index, line in enumerate(lines):
            if description is None and line.startswith("description = "):
                description = line
            if start is None and line.startswith("developer_instructions = "):
                start = index
                for close in range(index + 1, len(lines)):
                    if lines[close].rstrip("\r\n") == '"""':
                        end = close
                        break
                break
        if description is None or start is None or end is None:
            return None
        return lines, description, start, end

    current = locate(existing)
    target = locate(rendered)
    if current is None or target is None:
        return None
    lines, current_description, start, end = current
    target_lines, target_description, target_start, target_end = target
    description_newline = "\r\n" if current_description.endswith("\r\n") else "\n"
    target_description = target_description.rstrip("\r\n") + description_newline
    prompt_newline = "\r\n" if lines[start].endswith("\r\n") else "\n"
    prompt = "".join(target_lines[target_start:target_end + 1])
    prompt = prompt.replace("\r\n", "\n").replace("\n", prompt_newline)
    merged = [*lines[:start], prompt, *lines[end + 1:]]
    result: list[str] = []
    replaced = False
    for line in merged:
        if line.startswith("description = ") and not replaced:
            result.append(target_description)
            replaced = True
            continue
        result.append(line)
    return "".join(result)


def _refresh_prompt_files(
    destination: Path,
    expected: dict[str, str],
    *,
    format: str,
    dry_run: bool,
) -> tuple[list[str], dict[str, str], bool]:
    """Rewrite only skill-owned prompt content; host-owned fields stay untouched."""

    changed: list[str] = []
    digests: dict[str, str] = {}
    complete = True
    for filename, expected_text in sorted(expected.items()):
        path = destination / filename
        if path.is_symlink() or not path.is_file():
            complete = False
            continue
        try:
            original = path.read_bytes()
            existing = original.decode("utf-8")
        except (OSError, UnicodeError):
            complete = False
            continue
        digests[filename] = _content_digest(original)
        if format == "codex":
            merged = _merge_codex_prompt(existing, expected_text)
        else:
            merged = _merge_markdown_prompt(existing, expected_text)
        if merged is None or merged == existing:
            continue
        content = merged.encode("utf-8")
        if not dry_run:
            try:
                path.write_bytes(content)
            except OSError as exc:
                raise _InstallError("could not refresh native role prompt") from exc
        digests[filename] = _content_digest(content)
        changed.append(filename)
    return changed, digests, complete


def _refresh_message(target: str, changed: list[str], *, dry_run: bool) -> list[str]:
    if not changed:
        return [f"native: {target} role prompts current"]
    verb = "would refresh" if dry_run else "refreshed"
    return [f"native: {verb} {target} role prompt(s): {', '.join(changed)}"]


def _refresh_role_prompts(
    paths: _InstallPaths,
    target: str,
    *,
    dry_run: bool,
    skip_roles: set[str] | None = None,
) -> list[str]:
    """Refresh skill-owned prompt content while preserving host-owned configuration."""

    skip_roles = skip_roles or set()
    destination = _native_role_directory(paths, target)
    if target == "codex":
        documents = dict(_role_documents(destination))
        expected = {
            f"{role}.toml": source
            for role, source in _validate_native_sources(paths, target).items()
            if role not in skip_roles
            and (documents.get(destination / f"{role}.toml") or {}).get("name") == role
        }
    elif target in UNPINNED_HOSTS:
        expected = {
            filename: content.decode("utf-8")
            for filename, content in unpinned_role_payload(paths, target).items()
            if Path(filename).stem not in skip_roles
            and _markdown_role_name(destination / filename) == Path(filename).stem
        }
    else:
        return []
    changed, digests, _ = _refresh_prompt_files(
        destination, expected, format="codex" if target == "codex" else "markdown",
        dry_run=dry_run,
    )
    if not dry_run and changed:
        receipt_path = _native_receipt_path(destination)
        try:
            receipt = (_load_native_receipt(receipt_path, target) if target == "codex" else
                       _load_unpinned_role_receipt(receipt_path, target))
        except _InstallError:
            receipt = None
        if receipt is not None:
            files = receipt["files"] if target == "codex" else receipt
            refreshed = {name: digests[name] for name in changed if name in files}
            if refreshed:
                if target == "codex":
                    _replace_native_receipt(receipt_path, refreshed)
                else:
                    _write_unpinned_role_receipt(
                        receipt_path, target, {**files, **refreshed}, refresh=True
                    )
    return _refresh_message(target, changed, dry_run=dry_run)


def _refresh_kilo_prompts(
    paths: _InstallPaths, *, dry_run: bool, skip_roles: set[str] | None = None,
) -> list[str]:
    """Refresh Kilo Agent prompts; the host owns mode, temperature, and permissions."""

    skipped = {f"better-plan-{role}.md" for role in (skip_roles or set())}
    expected = {
        filename: content.decode("utf-8")
        for filename, content in _validate_kilo_sources(paths).items()
        if filename not in skipped
    }
    changed, digests, _ = _refresh_prompt_files(
        paths.kilo_agents, expected, format="markdown", dry_run=dry_run
    )
    if not dry_run and changed:
        receipt_path = _kilo_receipt_path(paths)
        try:
            receipt = _load_kilo_receipt(receipt_path)
        except _InstallError:
            receipt = None
        if receipt is not None:
            refreshed = {name: digests[name] for name in changed if name in receipt}
            if refreshed:
                _replace_kilo_receipt(receipt_path, {**receipt, **refreshed})
    return _refresh_message("kilo", changed, dry_run=dry_run)


def _load_unpinned_role_receipt(path: Path, target: str) -> dict[str, str] | None:
    """Track additive-role ownership, including historical Verifier-only receipts."""
    if not path.exists() and not path.is_symlink():
        return None
    try:
        if path.is_symlink() or not path.is_file():
            raise ValueError
        value = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(value, dict) or set(value) != {"schema_version", "target", "files"}
                or value.get("schema_version") != 1 or value.get("target") != target):
            raise ValueError
        files = value.get("files")
        if (not isinstance(files, dict) or not files
                or not set(files).issubset({f"{role}.md" for role in _ADDITIVE_ROLES})
                or any(not isinstance(digest, str) or not re.fullmatch("[0-9a-f]{64}", digest)
                       for digest in files.values())):
            raise ValueError
        return files
    except (OSError, UnicodeError, ValueError):
        raise _InstallError("native additive role receipt is invalid")


def _write_unpinned_role_receipt(
    path: Path, target: str, files: dict[str, str], *, refresh: bool = False,
) -> None:
    value = {"schema_version": 1, "target": target, "files": files}
    try:
        with path.open("w" if refresh else "x", encoding="utf-8") as stream:
            stream.write(json.dumps(value, sort_keys=True) + "\n")
    except OSError as exc:
        raise _InstallError("could not write native additive role receipt") from exc


def _recognizable_markdown_role(path: Path, role: str) -> bool:
    """Recognize historical unreceipted prompts without interpreting host selectors."""
    if path.is_symlink() or not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return False
    return (text.startswith("---\n") and "\n---\n" in text[4:]
            and f"\nname: {role}\n" in text
            and "Read the installed `better-plan` SKILL.md" in text
            and f"`references/{role}.md`" in text)


def _markdown_role_name(path: Path) -> str | None:
    """Read one simple native identity, without guessing complex YAML syntax."""
    try:
        if path.is_symlink() or not path.is_file():
            return None
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        return None
    frontmatter = text[4:text.index("\n---\n", 4)]
    names = re.findall(r"(?m)^name:[ \t]*(.*)$", frontmatter)
    if len(names) != 1:
        return None
    scalar = re.fullmatch(
        r"(?:([A-Za-z0-9_-]+)|\"([A-Za-z0-9_-]+)\"|'([A-Za-z0-9_-]+)')[ \t]*(?:#.*)?",
        names[0],
    )
    return next((name for name in scalar.groups() if name is not None), None) if scalar else None


def _role_filename(target: str, role: str) -> str:
    if target == "kilo":
        return f"better-plan-{role}.md"
    return f"{role}.toml" if target == "codex" else f"{role}.md"


def _recognized_matrix_files(files: set[str], target: str) -> bool:
    """Recognize the original matrix and its independently added roles."""
    base = {_role_filename(target, role) for role in _BASE_ROLES}
    if target == "kilo":
        base.add("better-plan.md")
    additive = {_role_filename(target, role) for role in _ADDITIVE_ROLES}
    return base.issubset(files) and files.issubset(base | additive)


def _upgrade_additive_roles(
    paths: _InstallPaths, target: str, *, dry_run: bool,
) -> tuple[list[str], set[str]]:
    messages: list[str] = []
    managed: set[str] = set()
    for role in _ADDITIVE_ROLES:
        upgrade, owned = _upgrade_additive_role(paths, target, role, dry_run=dry_run)
        messages.extend(upgrade)
        if owned:
            managed.add(role)
    return messages, managed


def _upgrade_additive_role(
    paths: _InstallPaths, target: str, role: str, *, dry_run: bool,
) -> tuple[list[str], bool]:
    """Add a missing specialist to a recognized earlier matrix without adopting files.

    The bool permits prompt maintenance only for a receipted, unambiguous role.
    Existing provenance and digests are preserved when extending the receipt.
    """
    destination = paths.kilo_agents if target == "kilo" else _native_role_directory(paths, target)
    filename = _role_filename(target, role)
    path = destination / filename
    label = role.title()
    prefix = f"native: {target} {label} upgrade"
    if destination.is_symlink() or not destination.is_dir():
        return [f"{prefix} skipped: role directory is not a regular directory"], False
    receipt_path = _native_receipt_path(destination)
    receipt = None
    try:
        if target == "codex":
            receipt = _load_native_receipt(receipt_path, target)
        elif target == "kilo":
            receipt = _load_kilo_receipt(receipt_path)
        else:
            receipt = _load_unpinned_role_receipt(receipt_path, target)
    except _InstallError:
        pass
    files = receipt["files"] if target == "codex" and receipt is not None else receipt
    occupied = path.exists() or path.is_symlink()
    identities: list[Path] = []
    if target == "codex":
        documents = dict(_role_documents(destination))
        uncertain = any(document is None for document in documents.values())
        identities = [candidate for candidate, document in documents.items()
                      if document is not None and document.get("name") == role]
    elif target in UNPINNED_HOSTS:
        names = {candidate: _markdown_role_name(candidate) for candidate in sorted(destination.glob("*.md"))}
        uncertain = any(name is None for name in names.values())
        identities = [candidate for candidate, name in names.items() if name == role]
    else:
        # Kilo identifies agents by filename, rather than a name field.
        uncertain = False
    if uncertain:
        return [f"{prefix} skipped: native role names are unreadable or ambiguous"], False
    if occupied or identities:
        managed = occupied and files is not None and filename in files
        if target != "kilo":
            managed = managed and identities == [path]
        if managed and path.is_file() and not path.is_symlink():
            return [], True
        return [f"{prefix} skipped: existing {label} name or path preserved (collision)"], False
    # A recorded but missing profile is local deletion/drift, not a legacy matrix.
    if files is not None and filename in files:
        return [f"{prefix} skipped: receipt records a missing role; report only"], False
    if target in UNPINNED_HOSTS:
        if files is None and (receipt_path.exists() or receipt_path.is_symlink()):
            return [f"{prefix} skipped: existing receipt requires inspection; no local files adopted"], False
        if not all(_recognizable_markdown_role(destination / f"{name}.md", name)
                   for name in _BASE_ROLES):
            return [f"{prefix} skipped: legacy role matrix is incomplete or unrecognized"], False
        if files is not None and any(
            _markdown_role_name(destination / name) != Path(name).stem for name in files
        ):
            return [f"{prefix} skipped: managed role matrix is incomplete or unrecognized"], False
        content = unpinned_role_payload(paths, target)[filename]
    else:
        if files is None or not _recognized_matrix_files(set(files), target):
            return [f"{prefix} skipped: valid legacy receipt required; no local files adopted"], False
        if any((destination / name).is_symlink() or not (destination / name).is_file()
               for name in files):
            return [f"{prefix} skipped: legacy role matrix is incomplete"], False
        if target == "codex":
            if any(not documents.get(destination / name)
                   or documents[destination / name].get("name") != Path(name).stem
                   or receipt["assignments"][Path(name).stem].role != Path(name).stem
                   for name in files):
                return [f"{prefix} skipped: legacy native role identity is unrecognized"], False
            try:
                assignment = _select_role_assignments(paths, target)[role]
            except ToolError as exc:
                raise _InstallError("native role assignments could not be selected") from exc
            content = _render_native_source(_validate_native_sources(paths, target)[role], assignment)
        else:
            content = _validate_kilo_sources(paths)[filename]
    settings = "packaged Codex preset" if target == "codex" else "host defaults"
    if dry_run:
        return [f"{prefix}: would add missing profile ({settings})"], False
    if files is not None and (receipt_path.is_symlink() or not receipt_path.is_file()):
        return [f"{prefix} skipped: receipt is no longer a regular file"], False
    _create_native_role(path, content)
    if files is None:
        _write_unpinned_role_receipt(receipt_path, target, {filename: _content_digest(content)})
    else:
        # Extend the validated original receipt without normalizing its provenance.
        value = json.loads(receipt_path.read_text(encoding="utf-8"))
        value["files"][filename] = _content_digest(content)
        if target == "codex":
            value["assignments"][filename] = _assignment_payload(assignment)
        try:
            receipt_path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
        except OSError as exc:
            raise _InstallError(f"{label} added but receipt extension failed; report only") from exc
    return [f"{prefix}: added missing profile ({settings})"], True


def _native_payload(
    paths: _InstallPaths,
    target: str,
) -> list[tuple[str, bytes, _RoleAssignment]]:
    sources = _validate_native_sources(paths, target)
    try:
        assignments = _select_role_assignments(paths, target)
    except ToolError as exc:
        raise _InstallError("native role assignments could not be selected") from exc
    payload: list[tuple[str, bytes, _RoleAssignment]] = []
    for agent_name, assignment in sorted(assignments.items()):
        if not isinstance(assignment, _RoleAssignment) or agent_name not in sources:
            raise _InstallError("native role template receipt is invalid")
        filename = f"{agent_name}.toml"
        payload.append((filename, _render_native_source(sources[agent_name], assignment), assignment))
    return payload


def install_role_templates(
    paths: _InstallPaths,
    target: str,
    *,
    dry_run: bool,
) -> list[str]:
    """Install a missing matrix once; later runs refresh prompts without touching host fields."""

    if target in UNPINNED_HOSTS:
        return install_unpinned_role_templates(paths, target, dry_run=dry_run)
    if native_role_configuration_exists(paths, target):
        messages = [f"native: preserved {target} role templates"]
        upgrade, managed_roles = _upgrade_additive_roles(paths, target, dry_run=dry_run)
        messages.extend(upgrade)
        messages.extend(_refresh_role_prompts(
            paths, target, dry_run=dry_run, skip_roles=set(_ADDITIVE_ROLES) - managed_roles
        ))
        return messages

    destination = _native_role_directory(paths, target)
    receipt_path = _native_receipt_path(destination)
    if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        raise _InstallError("native role template destination is not a managed directory")
    payload = _native_payload(paths, target)
    if not payload:
        raise _InstallError("native role template payload is empty")
    if dry_run:
        return [f"native: would install {target} role assignments", _assignment_message(target, payload)]
    destination.mkdir(parents=True, exist_ok=True)
    for filename, content, _ in payload:
        # Exclusive creation cannot overwrite a role that appeared after discovery.
        _create_native_role(destination / filename, content)
    _write_native_receipt(receipt_path, target, payload)
    return [f"native: installed {target} role templates", _assignment_message(target, payload)]


def install_unpinned_role_templates(
    paths: _InstallPaths,
    target: str,
    *,
    dry_run: bool,
) -> list[str]:
    """Install the five unpinned role files once, without a packaged selector."""

    if native_role_configuration_exists(paths, target):
        messages = [f"native: preserved {target} role templates"]
        upgrade, managed_roles = _upgrade_additive_roles(paths, target, dry_run=dry_run)
        messages.extend(upgrade)
        messages.extend(_refresh_role_prompts(
            paths, target, dry_run=dry_run, skip_roles=set(_ADDITIVE_ROLES) - managed_roles
        ))
        return messages
    destination = _native_role_directory(paths, target)
    if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        raise _InstallError("native role template destination is not a managed directory")
    payload = unpinned_role_payload(paths, target)
    if dry_run:
        return [f"native: would install {target} role templates (no packaged presets)"]
    destination.mkdir(parents=True, exist_ok=True)
    for filename, content in payload.items():
        # Exclusive creation cannot overwrite a role that appeared after discovery.
        _create_native_role(destination / filename, content)
    _write_unpinned_role_receipt(
        _native_receipt_path(destination), target,
        {f"{role}.md": _content_digest(payload[f"{role}.md"]) for role in _ADDITIVE_ROLES},
    )
    return [f"native: installed {target} role templates (no packaged presets)"]


def unpinned_role_status(paths: _InstallPaths, target: str) -> tuple[bool, str]:
    """Compare installed unpinned role files with the packaged templates, report only."""

    destination = _native_role_directory(paths, target)
    preserved = native_role_configuration_exists(paths, target)
    prefix = "local roles preserved; " if preserved else ""
    try:
        expected = unpinned_role_payload(paths, target)
    except _InstallError:
        return False, f"the packaged {target} role sources are unreadable"
    missing: list[str] = []
    changed: list[str] = []
    try:
        for filename, content in sorted(expected.items()):
            path = destination / filename
            if path.is_symlink() or not path.is_file():
                missing.append(filename)
            elif path.read_bytes() != content:
                changed.append(filename)
    except OSError:
        return False, f"{target} role files are unreadable"
    if missing:
        return False, f"{prefix}missing role file(s): {', '.join(missing)}"
    if changed:
        return False, f"{prefix}role template(s) differ: {', '.join(changed)}; difference alone does not establish a workflow conflict"
    return True, f"{target} role files verified (%d files, no packaged presets)" % len(expected)


def _assignment_message(target: str, payload: list[tuple[str, bytes, _RoleAssignment]]) -> str:
    values = "; ".join(_assignment_summary(assignment) for _, _, assignment in payload)
    return f"native assignments ({target}, model selectors preserved on update): {values}"


def _assignment_summary(assignment: _RoleAssignment) -> str:
    if assignment.model is None:
        return f"{assignment.agent_name} -> {assignment.role}, host-default (no model or effort selector)"
    effort = assignment.reasoning_effort or "host-default"
    if assignment.benchmark_id is None:
        return (f"{assignment.agent_name} -> {assignment.role}, {assignment.model}/{effort}, "
                f"benchmark unavailable, cost unavailable, source {assignment.source}")
    # One standard basis: every benchmarked pin reports its Intelligence Index score, and the task cost the
    # same table publishes for that row.
    cost = (
        f"cost ${assignment.cost_per_task_usd:.2f}/task"
        if assignment.cost_per_task_usd is not None
        else "cost unavailable"
    )
    return (
        f"{assignment.agent_name} -> {assignment.role}, {assignment.model}/{effort}, "
        f"Intelligence Index score {assignment.index_score}, {cost}, source {assignment.source}"
    )


def _installed_role_names(paths: _InstallPaths) -> set[str]:
    """Return every Codex role name the local host configuration declares."""

    return set(configured_codex_role_names(paths.codex_home))


def native_role_status(paths: _InstallPaths, target: str) -> tuple[bool, str]:
    """Report native role availability. Receipt and template checks are independent."""

    if target in UNPINNED_HOSTS:
        return unpinned_role_status(paths, target)
    preserved = native_role_configuration_exists(paths, target)
    installed = _installed_role_names(paths)

    def failure(message: str, notes: list[str]) -> tuple[bool, str]:
        suffix = f" ({'; '.join(notes)})" if notes else ""
        prefix = "local roles preserved; " if preserved else ""
        return False, f"{prefix}{message}{suffix}"

    if not installed:
        return failure("no local Codex role files are installed", [])

    notes: list[str] = []
    missing = [name for name in _codex_role_names() if name not in installed]
    if missing:
        return failure("missing packaged role(s): %s" % ", ".join(missing), notes)
    extras = sorted(installed - set(_codex_role_names()))
    if extras:
        notes.append("preserved role(s) outside the packaged matrix: %s" % ", ".join(extras))
    summary = "local roles verified: %s" % ", ".join(sorted(installed))
    return True, f"{summary} ({'; '.join(notes)})" if notes else summary


def role_receipt_status(paths: _InstallPaths, target: str) -> tuple[bool, str]:
    destination = paths.kilo_agents if target == "kilo" else _native_role_directory(paths, target)
    try:
        receipt_path = _native_receipt_path(destination)
        receipt = (_load_kilo_receipt(receipt_path) if target == "kilo" else
                   _load_unpinned_role_receipt(receipt_path, target) if target in UNPINNED_HOSTS else
                   _load_native_receipt(receipt_path, target))
        if receipt is None:
            return False, "no managed receipt; report only"
        files = receipt.get("files", {}) if target == "codex" else receipt
        if not files:
            return False, "managed receipt records no role files; report only"
        different = [name for name, digest in files.items()
                     if not (destination / name).is_file() or (destination / name).is_symlink()
                     or _content_digest((destination / name).read_bytes()) != digest]
        if different:
            return False, "receipt differs for role file(s): %s; report only" % ", ".join(sorted(different))
        return True, "original role receipt matches local files"
    except (OSError, _InstallError):
        return False, "managed receipt or role files unreadable; report only"


def codex_template_status(paths: _InstallPaths) -> tuple[bool, str]:
    """Compare instructions by native name without resolving or changing selectors."""
    try:
        sources = _validate_native_sources(paths, "codex")
        local = {}
        for _, document in _role_documents(paths.codex_home / "agents"):
            if document is not None and isinstance(document.get("name"), str) and document["name"] in sources:
                local.setdefault(document["name"], []).append(document)
        different = []
        for role, source in sources.items():
            expected = tomllib.loads(source)
            documents = local.get(role, [])
            if len(documents) != 1 or any(documents[0].get(key) != expected.get(key)
                                          for key in ("description", "developer_instructions")):
                different.append(role)
        if different:
            return False, "role template differs or is unavailable: %s; difference alone does not establish a workflow conflict" % ", ".join(sorted(different))
        return True, "role instructions match current templates; host-owned fields were not compared"
    except (OSError, ValueError, _InstallError):
        return False, "role template comparison unavailable; report only"


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


def install_claude_plugin(paths: _InstallPaths, *, dry_run: bool) -> None:
    """Install the Claude Code plugin layout that contains the shared skill payload."""

    if dry_run:
        # Validate the source tree through the canonical allowlisted copier.
        _copy_skill_tree(paths.repo_root, paths.claude_skill, dry_run=True)
        return
    with _staged_tree(paths.claude_plugin) as temp:
        (temp / ".claude-plugin").mkdir(parents=True)
        (temp / "skills").mkdir()
        plugin = temp / ".claude-plugin" / "plugin.json"
        plugin.write_text(
            json.dumps(
                {
                    "name": SKILL_NAME,
                    "version": VERSION,
                    "description": DESCRIPTION,
                    "author": {"name": "Better Plan"},
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        for name in ("README.md", "LICENSE"):
            source = paths.repo_root / name
            if source.is_file():
                shutil.copy2(source, temp / name)
        _copy_skill_tree(paths.repo_root, temp / "skills" / SKILL_NAME, dry_run=False)


def install_target(
    paths: _InstallPaths,
    target: str,
    *,
    dry_run: bool,
) -> list[str]:
    """Apply only the target-specific side effects for one normalized target."""
    if target not in AGENTS:
        raise _InstallError(f"unknown agent target: {target}")
    if target == "kilo":
        return install_kilo_agent_matrix(paths, dry_run=dry_run)
    if target == "dsh":
        # DeepSeek Harness reads the shared skill at `~/.agents/skills`, and its
        # subagents are spawned from a prompt, so it installs no role file, no pin,
        # and no lifecycle Hook. Every role runs on whatever the harness runs.
        return [
            "dsh: skill only; roles are prompts and inherit the harness model"
        ]
    messages: list[str] = []
    if target == "claude":
        # Claude Code loads the skill from its plugin layout, so install that tree first.
        install_claude_plugin(paths, dry_run=dry_run)
        messages.append(f"claude: {'would update' if dry_run else 'updated'} plugin")
    messages.extend(install_role_templates(paths, target, dry_run=dry_run))
    return messages


def _shared_scan_skill_messages(
    paths: _InstallPaths,
    label: str,
    native: Path,
    *,
    remove_shared: bool,
    dry_run: bool,
) -> list[str]:
    """Report the skill this host actually reads, and only removals that happened.

    A shared-scan host installs to `~/.agents/skills/better-plan` whenever that
    directory exists, so uninstalling one host must not silently claim to have
    removed a skill that either was never there or is still shared with another
    host. Removal of the shared path stays an explicit `--remove-shared` decision.
    """

    action = "would remove" if dry_run else "removed"
    if native == paths.shared_skill or paths.shared_skill.exists():
        if remove_shared:
            return [f"{label}: {action} the shared scan skill"]
        return [
            f"{label}: skill is the shared scan path; kept (pass --remove-shared to remove it)"
        ]
    if native.exists():
        if not dry_run:
            _remove_path(native)
        return [f"{label}: {action} native skill"]
    return [f"{label}: no skill to remove"]


def remove_target(
    paths: _InstallPaths,
    target: str,
    *,
    remove_shared: bool,
    dry_run: bool,
) -> list[str]:
    if target not in AGENTS:
        raise _InstallError(f"unknown agent target: {target}")
    action = "would remove" if dry_run else "removed"
    if target == "claude":
        plugin = paths.claude_plugin
        existed = plugin.exists()
        if existed and not dry_run:
            _remove_path(plugin)
        return [
            "claude: preserved native role templates",
            f"claude: {action} plugin" if existed else "claude: no plugin to remove",
        ]
    native = {
        "codex": paths.codex_skill,
        "cursor": paths.cursor_skill,
        "kilo": paths.kilo_skill,
        "dsh": paths.shared_skill,
    }[target]
    messages = _shared_scan_skill_messages(
        paths,
        target,
        native,
        remove_shared=remove_shared,
        dry_run=dry_run,
    )
    if target == "kilo":
        messages.append("kilo: preserved native Agent matrix")
    elif target == "dsh":
        messages.append("dsh: no native role artifacts")
    else:
        messages.append(f"{target}: preserved native role templates")
    return messages
