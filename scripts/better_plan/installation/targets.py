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
from ..hooks.config import (
    HookConfigError as _HookConfigError,
    install_hook_config as _install_hook_config,
    uninstall_hook_config as _uninstall_hook_config,
)
from ..infrastructure.native_roles import configured_codex_role_names
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
    "codex": ("designer.toml", "worker.toml", "hybrid-worker.toml", "reviewer.toml"),
    "claude": ("designer.md", "worker.md", "hybrid-worker.md", "reviewer.md"),
    "cursor": ("designer.md", "worker.md", "hybrid-worker.md", "reviewer.md"),
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
    "better-plan-hybrid-worker.md",
    "better-plan-reviewer.md",
)
KILO_SUBAGENTS = KILO_AGENT_FILES[1:]
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


def _delivery_role(agent_name: str) -> str:
    """Return the delivery role one installed agent name provides."""

    return "worker" if agent_name == "hybrid-worker" else agent_name


def _unpinned_assignment_line(agent_name: str) -> str:
    """Return the static identity line for a host that packages no selector."""

    return (
        f"assignment: agent={agent_name} | role={_delivery_role(agent_name)} | "
        "model=host-inherited | reasoning_effort=host-inherited | source=host-inheritance"
    )


def unpinned_role_payload(paths: _InstallPaths, target: str) -> dict[str, bytes]:
    """Return each unpinned role file with its identity line substituted."""

    filenames = NATIVE_ROLE_FILES.get(target)
    if filenames is None or target not in UNPINNED_HOSTS:
        raise _InstallError("native role templates are unavailable for this target")
    source = _native_source_directory(paths, target)
    payload: dict[str, bytes] = {}
    try:
        for filename in filenames:
            text = (source / filename).read_text(encoding="utf-8")
            if not text.strip() or not text.startswith("---\n") or "ASSIGNMENT_PLACEHOLDER" not in text:
                raise ValueError
            line = _unpinned_assignment_line(posixpath.splitext(filename)[0])
            rendered = text.replace("Pinned identity: ASSIGNMENT_PLACEHOLDER", line)
            rendered = rendered.replace("ASSIGNMENT_PLACEHOLDER", line)
            payload[filename] = rendered.encode("utf-8")
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
                    "Handle simple tasks directly",
                )
            else:
                # Every Subagent is a leaf: the native main owns Task dispatch and joins,
                # so a Worker never receives the Task tool and nesting cannot recurse.
                required = (
                    "mode: subagent",
                    "task: deny",
                    "question: deny",
                    "model=parent-inherited",
                    "reasoning_effort=host-default",
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
        or set(files) != set(KILO_AGENT_FILES)
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
        return ["native: preserved kilo Agent matrix"]
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
    byte. The managed receipt is never required and never rewritten; it is read only as report-only
    context, so a receipt that disagrees with the local files is reported rather than repaired.
    """

    try:
        sources = _validate_kilo_sources(paths)
    except _InstallError:
        return False, "the packaged Kilo Agent sources are unreadable"
    notes: list[str] = []
    try:
        receipt = _load_kilo_receipt(_kilo_receipt_path(paths))
    except _InstallError:
        receipt = None
        notes.append("managed receipt is unreadable; report only")
    if receipt is None:
        notes.append("no managed receipt to verify against; report only")
    else:
        try:
            for filename, digest in sorted(receipt.items()):
                path = paths.kilo_agents / filename
                if path.is_symlink() or not path.is_file():
                    continue
                if _content_digest(path.read_bytes()) != digest:
                    notes.append(
                        "managed receipt reports %s changed outside Better Plan; report only"
                        % filename
                    )
        except OSError:
            notes.append("Kilo Agent files are unreadable; report only")
    suffix = f" ({'; '.join(notes)})" if notes else ""
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
        return False, "missing Agent file(s): %s%s" % (", ".join(missing), suffix)
    if changed:
        return False, "Agent file(s) differ from the packaged matrix: %s%s" % (
            ", ".join(changed),
            suffix,
        )
    return True, "current namespaced Kilo Agent matrix verified (%d files)%s" % (
        len(sources),
        suffix,
    )


def native_role_configuration_exists(paths: _InstallPaths, target: str) -> bool:
    """Return whether this host already owns any local Better Plan role state."""

    destination = _native_role_directory(paths, target)
    receipt = _native_receipt_path(destination)
    if receipt.exists() or receipt.is_symlink():
        return True
    if target == "codex" and configured_codex_role_names(paths.codex_home).intersection(
        _codex_role_names()
    ):
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
    # Receipts written before `index_basis` existed stay readable: this record is immutable and is
    # never regenerated, so an older receipt must not become invalid.
    if not isinstance(value, dict) or set(value) not in (required, required | {"index_basis"}):
        raise _InstallError("native role template receipt is invalid")
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
    basis = value.get("index_basis", "")
    if not isinstance(basis, str) or basis not in ("", "coding_agent", "intelligence"):
        raise _InstallError("native role template receipt is invalid")
    return _RoleAssignment(
        role=str(value["role"]),
        agent_name=str(value["agent_name"]),
        model=str(value["model"]),
        reasoning_effort=None if effort is None else str(effort),
        benchmark_id=str(value["benchmark_id"]),
        index_score=int(value["index_score"]),
        index_basis=str(basis),
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
        "index_basis": assignment.index_basis,
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


def _validate_native_sources(paths: _InstallPaths, target: str) -> dict[str, str]:
    filenames = NATIVE_ROLE_FILES.get(target)
    if filenames is None:
        raise _InstallError("native role templates are unavailable for this target")
    source = _native_source_directory(paths, target)
    payload: dict[str, str] = {}
    try:
        for filename in filenames:
            text = (source / filename).read_text(encoding="utf-8")
            if not text.strip() or "ASSIGNMENT_PLACEHOLDER" not in text:
                raise ValueError
            if not text.startswith("name = ") or "developer_instructions =" not in text:
                raise ValueError
            payload[posixpath.splitext(filename)[0]] = text
    except (OSError, UnicodeError, ValueError, TypeError):
        raise _InstallError("native role template source is missing or malformed")
    return payload


def _render_native_source(source: str, assignment: _RoleAssignment) -> bytes:
    """Render one packaged Codex role with its identity block and pinned selector.

    The installed prompt never repeats the installation-time benchmark receipt:
    Codex reports runtime identity, so the selector lives only in the TOML fields.
    """

    line = (
        f"Role identity: agent={assignment.agent_name} | role={assignment.role}\n"
        "Report model and reasoning_effort from host-provided runtime metadata when available, "
        "with source=host-runtime. Otherwise echo the dispatch's assignment_line unchanged; "
        "its source identifies configured selection, not confirmed runtime identity. "
        "If neither is available, report model=unknown | reasoning_effort=unknown | source=unavailable. "
        "Never guess your model, repeat an installation-time selector, or report benchmark scores "
        "as runtime identity."
    )
    rendered = source.replace("Pinned identity: ASSIGNMENT_PLACEHOLDER", line)
    rendered = rendered.replace("ASSIGNMENT_PLACEHOLDER", line)
    marker = "sandbox_mode = "
    position = rendered.find(marker)
    if position < 0:
        raise _InstallError("native role template source is missing or malformed")
    selector = f'model = "{assignment.model}"\n'
    if assignment.reasoning_effort is not None:
        selector += f'model_reasoning_effort = "{assignment.reasoning_effort}"\n'
    rendered = rendered[:position] + selector + rendered[position:]
    return rendered.encode("utf-8")


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
    """Install a missing matrix once; never mutate existing native role state."""

    if target in UNPINNED_HOSTS:
        return install_unpinned_role_templates(paths, target, dry_run=dry_run)
    if native_role_configuration_exists(paths, target):
        return [f"native: preserved {target} role templates"]

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
    """Install the four unpinned role files once, without a packaged selector."""

    if native_role_configuration_exists(paths, target):
        return [f"native: preserved {target} role templates"]
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
        return False, f"{prefix}role file(s) changed outside Better Plan: {', '.join(changed)}"
    return True, f"{target} role files verified (%d files, no packaged presets)" % len(expected)


def _assignment_message(target: str, payload: list[tuple[str, bytes, _RoleAssignment]]) -> str:
    values = "; ".join(_assignment_summary(assignment) for _, _, assignment in payload)
    return f"native assignments ({target}, immutable after first installation): {values}"


def _assignment_summary(assignment: _RoleAssignment) -> str:
    effort = assignment.reasoning_effort or "host-default"
    # The recorded basis tells the two published indices apart. A receipt written before the field
    # existed is read the old way: a Worker row with a task cost is the Coding Agent row.
    basis_kind = assignment.index_basis or (
        "coding_agent"
        if assignment.role == "worker" and assignment.cost_per_task_usd is not None
        else "intelligence"
    )
    if basis_kind == "coding_agent":
        basis = "Coding Agent"
        cost = (
            f"cost ${assignment.cost_per_task_usd:.2f}/task"
            if assignment.cost_per_task_usd is not None
            else "cost unavailable"
        )
        metric = f"score {assignment.index_score}, {cost}"
    elif assignment.role == "worker":
        basis = "Intelligence Index proxy"
        metric = f"score {assignment.index_score}, price ignored"
    else:
        basis = "Intelligence Index"
        metric = f"score {assignment.index_score}, price ignored"
    return (
        f"{assignment.agent_name} -> {assignment.role}, {assignment.model}/{effort}, "
        f"{basis} {metric}, source {assignment.source}"
    )


def _installed_role_names(paths: _InstallPaths) -> set[str]:
    """Return every Codex role name the local host configuration declares."""

    return set(configured_codex_role_names(paths.codex_home))


def native_role_status(paths: _InstallPaths, target: str) -> tuple[bool, str]:
    """Report the local role files against the packaged matrix, without exposing selectors.

    The inventory comes from the local role files, because that is the state a user can act on.
    The managed receipt stays a separate integrity record: Better Plan never edits, removes,
    adopts, re-signs, or regenerates it, so a receipt that describes an earlier matrix is context
    rather than a missing role. A host without a packaged preset has no receipt and is compared
    against its rendered role files instead.
    """

    if target in UNPINNED_HOSTS:
        return unpinned_role_status(paths, target)
    destination = _native_role_directory(paths, target)
    preserved = native_role_configuration_exists(paths, target)
    installed = _installed_role_names(paths)

    def failure(message: str, notes: list[str]) -> tuple[bool, str]:
        suffix = f" ({'; '.join(notes)})" if notes else ""
        prefix = "local roles preserved; " if preserved else ""
        return False, f"{prefix}{message}{suffix}"

    if not installed:
        return failure("no local Codex role files are installed", [])

    notes: list[str] = []
    try:
        receipt = _load_native_receipt(_native_receipt_path(destination), target)
    except _InstallError:
        receipt = None
        notes.append("managed receipt is unreadable; report only")
    if receipt is None:
        notes.append("no managed receipt to verify against; report only")
    else:
        files = receipt.get("files")
        if not isinstance(files, dict):
            notes.append("managed receipt is invalid; report only")
        elif not files:
            # A receipt that records no file verifies nothing, so it must never be reported as a
            # verified matrix. The local roles stay untouched: this is a report-only warning.
            return failure("managed receipt records no role files", ["report only"])
        else:
            try:
                for filename, digest in files.items():
                    path = destination / filename
                    if path.is_symlink() or not path.is_file():
                        continue
                    if _content_digest(path.read_bytes()) != digest:
                        return failure("role file %s changed outside Better Plan" % filename, [])
            except OSError:
                return failure("native role files are unreadable", [])
            detached = sorted(
                {posixpath.splitext(name)[0] for name in files} - installed
            )
            if detached:
                notes.append(
                    "managed receipt records role(s) no longer installed: %s; report only"
                    % ", ".join(detached)
                )

    missing = [name for name in _codex_role_names() if name not in installed]
    if missing:
        return failure("missing packaged role(s): %s" % ", ".join(missing), notes)
    extras = sorted(installed - set(_codex_role_names()))
    if extras:
        notes.append("preserved role(s) outside the packaged matrix: %s" % ", ".join(extras))
    summary = "local roles verified: %s" % ", ".join(sorted(installed))
    return True, f"{summary} ({'; '.join(notes)})" if notes else summary




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
    messages: list[str] = []
    if target == "claude":
        # Claude Code loads the skill from its plugin layout, so install that tree first.
        install_claude_plugin(paths, dry_run=dry_run)
        messages.append(f"claude: {'would update' if dry_run else 'updated'} plugin")
    messages.extend(install_role_templates(paths, target, dry_run=dry_run))
    _, changed = update_agent_hooks(paths, target, dry_run=dry_run)
    action = "would update" if dry_run and changed else "updated" if changed else "already current"
    messages.append(f"{target} hooks: {action} managed handlers")
    return messages


def remove_target(paths: _InstallPaths, target: str, *, dry_run: bool) -> list[str]:
    if target not in AGENTS:
        raise _InstallError(f"unknown agent target: {target}")
    action = "would remove" if dry_run else "removed"
    if target == "kilo":
        if not dry_run:
            _remove_path(paths.kilo_skill)
        return [
            f"kilo: {action} native skill",
            "kilo: preserved immutable native Agent matrix",
        ]
    if target == "claude":
        if not dry_run:
            _remove_path(paths.claude_plugin)
        return [
            "claude: preserved immutable native role templates",
            f"claude: {action} plugin",
        ]
    if target == "cursor":
        if not dry_run:
            _remove_path(paths.cursor_skill)
        return [
            "cursor: preserved immutable native role templates",
            f"cursor: {action} native skill",
        ]
    if not dry_run:
        _remove_path(paths.codex_skill)
    return [
        "codex: preserved immutable native role templates",
        f"codex: {action} native skill",
    ]
