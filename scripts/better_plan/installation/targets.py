"""Target-specific Better Plan installer adapters."""

from __future__ import annotations

import json
import hashlib
import os
import posixpath
import re
import shlex
import shutil
import subprocess
from pathlib import Path

from ..hooks.config import (
    HookConfigError as _HookConfigError,
    hook_command as _hook_command,
    install_hook_config as _install_hook_config,
    uninstall_hook_config as _uninstall_hook_config,
)
from .models import (
    AGENTS,
    DESCRIPTION,
    SKILL_NAME,
    VERSION,
    InstallError as _InstallError,
    InstallPaths as _InstallPaths,
    WslOpenCodeRuntime as _WslOpenCodeRuntime,
)
from .assignments import RoleAssignment as _RoleAssignment, select_role_assignments as _select_role_assignments
from .skills import copy_skill_tree as _copy_skill_tree, remove_path as _remove_path


NATIVE_ROLE_FILES: dict[str, tuple[str, ...]] = {
    "codex": ("designer.toml", "worker-standard.toml", "worker-complex.toml", "reviewer.toml", "finder.toml", "fallback_finder.toml"),
    "claude": ("designer.md", "worker-standard.md", "worker-complex.md", "reviewer.md"),
    "opencode": ("designer.md", "worker-standard.md", "worker-complex.md", "reviewer.md"),
    "cursor": ("designer.md", "worker-standard.md", "worker-complex.md", "reviewer.md"),
}
KILO_AGENT_FILES = (
    "better-plan.md",
    "better-plan-designer.md",
    "better-plan-worker-standard.md",
    "better-plan-worker-complex.md",
    "better-plan-reviewer.md",
)
KILO_SUBAGENTS = KILO_AGENT_FILES[1:]
_NATIVE_SOURCE_TARGET = {"claude": "claude-code"}
_OPENCODE_NO_TEMPERATURE = frozenset(
    {"opencode-go/gpt-5.6-luna", "opencode-go/kimi-k3"}
)
_SAFE_OPENCODE_SELECTOR = re.compile(r"opencode-go/[A-Za-z0-9._+-]{1,128}")


def _native_role_directory(paths: _InstallPaths, target: str) -> Path:
    if target == "codex":
        return paths.codex_home / "agents"
    if target == "claude":
        return paths.claude_home / "agents"
    if target == "opencode":
        return paths.opencode_config / "agents"
    if target == "cursor":
        return paths.cursor_home / "agents"
    raise _InstallError("native role templates are unavailable for this target")


def _native_source_directory(paths: _InstallPaths, target: str) -> Path:
    source_target = _NATIVE_SOURCE_TARGET.get(target, target)
    return paths.repo_root / "agents" / source_target


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
            if filename == "better-plan.md":
                required = (
                    "mode: primary",
                    '"*": deny',
                    "better-plan-designer: allow",
                    "better-plan-worker-standard: allow",
                    "better-plan-worker-complex: allow",
                    "better-plan-reviewer: allow",
                    "better-plan: allow",
                    "Handle simple tasks directly",
                )
            else:
                required = (
                    "mode: subagent",
                    "task: deny",
                    "question: deny",
                    "model=parent-inherited",
                    "reasoning_effort=host-default",
                )
                if re.search(r"(?m)^model:\s*", text):
                    raise ValueError
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
    temp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        temp.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temp, path)
    except OSError as exc:
        if temp.exists():
            temp.unlink()
        raise _InstallError("could not write Kilo Agent receipt") from exc


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
        (destination / filename).write_bytes(content)
    _write_kilo_receipt(_kilo_receipt_path(paths), payload)
    return ["native: installed kilo Agent matrix"]


def kilo_agent_status(paths: _InstallPaths) -> tuple[bool, str]:
    """Verify only the immutable Kilo matrix created by Better Plan."""

    try:
        files = _load_kilo_receipt(_kilo_receipt_path(paths))
    except _InstallError:
        return False, "Kilo Agent receipt is missing, obsolete, or invalid"
    if files is None:
        return False, "Kilo Agent receipt is missing"
    try:
        for filename, digest in files.items():
            path = paths.kilo_agents / filename
            if path.is_symlink() or not path.is_file() or _content_digest(path.read_bytes()) != digest:
                return False, "Kilo Agent files do not match the managed receipt"
    except OSError:
        return False, "Kilo Agent files are unreadable"
    return True, "current namespaced Kilo Agent matrix verified"


def native_role_configuration_exists(paths: _InstallPaths, target: str) -> bool:
    """Return whether this host already owns any local Better Plan role state."""

    destination = _native_role_directory(paths, target)
    receipt = _native_receipt_path(destination)
    if receipt.exists() or receipt.is_symlink():
        return True
    return any(
        (destination / filename).exists() or (destination / filename).is_symlink()
        for filename in NATIVE_ROLE_FILES[target]
    )


def _content_digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _assignment_value(value: object) -> _RoleAssignment:
    if not isinstance(value, dict) or set(value) != {
        "role", "agent_name", "model", "reasoning_effort", "benchmark_id",
        "index_score", "cost_per_task_usd", "source",
    }:
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
    if any(parsed_by_file[name].agent_name != Path(name).stem for name in parsed_by_file):
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
    temp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        temp.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temp, path)
    except OSError as exc:
        if temp.exists():
            temp.unlink()
        raise _InstallError("could not write native role template receipt") from exc


def _validate_native_sources(paths: _InstallPaths, target: str) -> dict[str, str]:
    filenames = NATIVE_ROLE_FILES.get(target)
    if filenames is None:
        raise _InstallError("native role templates are unavailable for this target")
    source = _native_source_directory(paths, target)
    payload: dict[str, str] = {}
    try:
        for filename in filenames:
            path = source / filename
            text = path.read_text(encoding="utf-8")
            if not text.strip() or "ASSIGNMENT_PLACEHOLDER" not in text:
                raise ValueError
            if target == "codex":
                if not text.startswith("name = ") or "developer_instructions =" not in text:
                    raise ValueError
            else:
                if not text.startswith("---\n"):
                    raise ValueError
            payload[Path(filename).stem] = text
    except (OSError, UnicodeError, ValueError, TypeError):
        raise _InstallError("native role template source is missing or malformed")
    return payload


def _render_native_source(target: str, source: str, assignment: _RoleAssignment) -> bytes:
    effort = assignment.reasoning_effort or "host-default"
    if assignment.role == "worker" and assignment.cost_per_task_usd is not None:
        basis = "Coding Agent"
        measurement = f"score={assignment.index_score}"
    elif assignment.role == "worker":
        basis = "Intelligence Index proxy"
        measurement = f"score={assignment.index_score}"
    elif assignment.role == "finder":
        basis = "Codex read-only utility"
        measurement = "mode=read-only"
    else:
        basis = "Intelligence Index"
        measurement = f"score={assignment.index_score}"
    cost = (
        ""
        if assignment.cost_per_task_usd is None
        else f" | measured_cost_per_task_usd={assignment.cost_per_task_usd:.2f}"
    )
    line = (
        f"assignment: agent={assignment.agent_name} | role={assignment.role} | "
        f"model={assignment.model} | reasoning_effort={effort} | basis={basis} | "
        f"{measurement}{cost} | benchmark={assignment.benchmark_id} | source={assignment.source}"
    )
    rendered = source.replace("Pinned identity: ASSIGNMENT_PLACEHOLDER", line)
    rendered = rendered.replace("ASSIGNMENT_PLACEHOLDER", line)
    if target == "codex":
        marker = "sandbox_mode = "
        position = rendered.find(marker)
        if position < 0:
            raise _InstallError("native role template source is missing or malformed")
        selector = f'model = "{assignment.model}"\n'
        if assignment.reasoning_effort is not None:
            selector += f'model_reasoning_effort = "{assignment.reasoning_effort}"\n'
        rendered = rendered[:position] + selector + rendered[position:]
    elif target == "opencode":
        if assignment.model in _OPENCODE_NO_TEMPERATURE:
            rendered = re.sub(r"(?m)^temperature:\s*[^\n]+\n", "", rendered, count=1)
        closing = rendered.find("\n---\n", 4)
        if closing < 0:
            raise _InstallError("native role template source is missing or malformed")
        selector = f"\nmodel: {assignment.model}"
        if assignment.reasoning_effort is not None:
            selector += f"\nreasoningEffort: {assignment.reasoning_effort}"
        rendered = rendered[:closing] + selector + rendered[closing:]
    else:
        closing = rendered.find("\n---\n", 4)
        if closing < 0:
            raise _InstallError("native role template source is missing or malformed")
        selector = f"\nmodel: {assignment.model}"
        if assignment.reasoning_effort is not None:
            selector += f"\nreasoning_effort: {assignment.reasoning_effort}"
        rendered = rendered[:closing] + selector + rendered[closing:]
    return rendered.encode("utf-8")


def opencode_model_selectors() -> frozenset[str]:
    """Return bounded public OpenCode Go model selectors from the local runtime."""

    opencode = shutil.which("opencode")
    if opencode is None:
        return frozenset()
    try:
        result = run_text_command([opencode, "models", "opencode-go"], timeout=30)
    except _InstallError:
        return frozenset()
    if result.returncode != 0:
        return frozenset()
    return frozenset(
        line.strip()
        for line in result.stdout.splitlines()
        if line.startswith("opencode-go/") and _SAFE_OPENCODE_SELECTOR.fullmatch(line.strip())
    )


def _native_payload(
    paths: _InstallPaths,
    target: str,
    receipt: dict[str, object] | None,
) -> list[tuple[str, bytes, _RoleAssignment]]:
    sources = _validate_native_sources(paths, target)
    if receipt is None:
        try:
            assignments = _select_role_assignments(
                paths,
                target,
                excluded_names=NATIVE_ROLE_FILES[target],
                available_model_selectors=(
                    opencode_model_selectors() if target == "opencode" else None
                ),
            )
        except ToolError as exc:
            raise _InstallError("native role assignments could not be selected") from exc
    else:
        receipt_assignments = receipt["assignments"]
        if not isinstance(receipt_assignments, dict):
            raise _InstallError("native role template receipt is invalid")
        assignments = dict(receipt_assignments)
    payload: list[tuple[str, bytes, _RoleAssignment]] = []
    extension = ".toml" if target == "codex" else ".md"
    for agent_name, assignment in sorted(assignments.items()):
        if not isinstance(assignment, _RoleAssignment) or agent_name not in sources:
            raise _InstallError("native role template receipt is invalid")
        filename = f"{agent_name}{extension}"
        payload.append((filename, _render_native_source(target, sources[agent_name], assignment), assignment))
    return payload


def install_role_templates(
    paths: _InstallPaths,
    target: str,
    *,
    dry_run: bool,
) -> list[str]:
    """Install a missing matrix once; never mutate existing native role state."""

    if native_role_configuration_exists(paths, target):
        return [f"native: preserved {target} role templates"]

    destination = _native_role_directory(paths, target)
    receipt_path = _native_receipt_path(destination)
    if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        raise _InstallError("native role template destination is not a managed directory")
    receipt = _load_native_receipt(receipt_path, target)
    obsolete_files: dict[str, str] = {}
    if receipt is not None:
        receipt_files = receipt.get("files")
        receipt_assignments = receipt.get("assignments")
        if not isinstance(receipt_files, dict) or not isinstance(receipt_assignments, dict):
            raise _InstallError("native role template receipt is invalid")
        allowed = set(NATIVE_ROLE_FILES[target])
        obsolete_files = {
            filename: str(digest)
            for filename, digest in receipt_files.items()
            if filename not in allowed
        }
        for filename, digest in obsolete_files.items():
            path = destination / filename
            if not path.exists():
                continue
            if path.is_symlink() or not path.is_file():
                raise _InstallError("obsolete managed native role collides with an unmanaged file")
            try:
                current_digest = _content_digest(path.read_bytes())
            except OSError as exc:
                raise _InstallError("obsolete managed native role is unreadable") from exc
            if current_digest != digest:
                raise _InstallError("obsolete managed native role was modified outside Better Plan")
        extension = ".toml" if target == "codex" else ".md"
        receipt = {
            "files": {name: digest for name, digest in receipt_files.items() if name in allowed},
            "assignments": {
                name: assignment
                for name, assignment in receipt_assignments.items()
                if f"{name}{extension}" in allowed
            },
        }
    payload = _native_payload(paths, target, receipt)
    if not payload:
        return [f"native: skipped {target}; no locally callable benchmarked role configuration was found"]
    expected = {filename: _content_digest(content) for filename, content, _ in payload}
    receipt_files = receipt.get("files") if receipt is not None else None
    if receipt_files is not None and (
        not isinstance(receipt_files, dict)
        or not set(receipt_files).issubset(expected)
    ):
        raise _InstallError("native role template receipt is invalid")

    # Existing same-name files are safe to touch only when the receipt proves
    # that Better Plan still owns the exact bytes.  A pre-existing collision
    # without a receipt fails closed instead of being overwritten.
    for filename, content, _ in payload:
        path = destination / filename
        if path.is_symlink():
            raise _InstallError("native role template destination collides with an unmanaged file")
        if not path.exists():
            continue
        if not path.is_file():
            raise _InstallError("native role template destination collides with an unmanaged file")
        if receipt is None:
            raise _InstallError("native role template destination collides with an unmanaged file")
        try:
            current_digest = _content_digest(path.read_bytes())
        except OSError as exc:
            raise _InstallError("native role template destination is unreadable") from exc
        if not isinstance(receipt_files, dict) or receipt_files.get(filename) != current_digest:
            raise _InstallError("native role template destination was modified outside Better Plan")

    if dry_run:
        action = f"native: would pin {target} role assignments"
        if obsolete_files:
            action += " and remove obsolete managed roles"
        return [action, _assignment_message(target, payload)]
    destination.mkdir(parents=True, exist_ok=True)
    changed = bool(obsolete_files)
    for filename in obsolete_files:
        path = destination / filename
        if path.exists():
            path.unlink()
    for filename, content, _ in payload:
        path = destination / filename
        if not path.exists() or path.read_bytes() != content:
            path.write_bytes(content)
            changed = True
    if receipt is None or receipt_files != expected or obsolete_files:
        _write_native_receipt(receipt_path, target, payload)
    return [f"native: {'updated' if changed else 'already current'} {target} role templates", _assignment_message(target, payload)]


def _assignment_message(target: str, payload: list[tuple[str, bytes, _RoleAssignment]]) -> str:
    values = "; ".join(_assignment_summary(assignment) for _, _, assignment in payload)
    return f"native assignments ({target}, pinned until explicit reinstall): {values}"


def _assignment_summary(assignment: _RoleAssignment) -> str:
    effort = assignment.reasoning_effort or "host-default"
    if assignment.role == "worker" and assignment.cost_per_task_usd is not None:
        basis = "Coding Agent"
        metric = f"score {assignment.index_score}, cost ${assignment.cost_per_task_usd:.2f}/task"
    elif assignment.role == "worker":
        basis = "Intelligence Index proxy"
        metric = f"score {assignment.index_score}, price ignored"
    elif assignment.role == "finder":
        basis = "Codex read-only utility"
        metric = "fixed selector"
    else:
        basis = "Intelligence Index"
        metric = f"score {assignment.index_score}, price ignored"
    return (
        f"{assignment.agent_name} -> {assignment.role}, {assignment.model}/{effort}, "
        f"{basis} {metric}, source {assignment.source}"
    )


def native_role_status(paths: _InstallPaths, target: str) -> tuple[bool, str]:
    """Verify the complete receipt-owned native role matrix without exposing selectors."""

    destination = _native_role_directory(paths, target)
    try:
        receipt = _load_native_receipt(_native_receipt_path(destination), target)
    except _InstallError:
        return False, "native role receipt is missing, obsolete, or invalid"
    if receipt is None:
        try:
            selectable = _select_role_assignments(
                paths,
                target,
                excluded_names=NATIVE_ROLE_FILES[target],
                available_model_selectors=(
                    opencode_model_selectors() if target == "opencode" else None
                ),
            )
        except ToolError:
            return False, "native role selection could not be verified"
        if not selectable:
            return True, "no qualifying native role configuration; adapter-only installation verified"
        return False, "native role receipt is missing"
    files = receipt.get("files")
    if not isinstance(files, dict) or not files or not set(files).issubset(NATIVE_ROLE_FILES[target]):
        return False, "native role inventory is invalid"
    try:
        for filename, digest in files.items():
            path = destination / filename
            if path.is_symlink() or not path.is_file() or _content_digest(path.read_bytes()) != digest:
                return False, "native role files do not match the managed receipt"
    except OSError:
        return False, "native role files are unreadable"
    return True, "current native role generation and pinned selectors verified"


def remove_role_templates(
    paths: _InstallPaths,
    target: str,
    *,
    dry_run: bool,
) -> list[str]:
    destination = _native_role_directory(paths, target)
    receipt_path = _native_receipt_path(destination)
    receipt = _load_native_receipt(receipt_path, target)
    existing: list[Path] = []
    if receipt is not None:
        receipt_files = receipt.get("files")
        if not isinstance(receipt_files, dict):
            raise _InstallError("native role template receipt is invalid")
        for filename in receipt_files:
            path = destination / filename
            if not path.exists():
                continue
            if path.is_symlink() or not path.is_file():
                continue
            try:
                current_digest = _content_digest(path.read_bytes())
            except OSError as exc:
                raise _InstallError("native role template destination is unreadable") from exc
            if receipt_files.get(filename) == current_digest:
                existing.append(path)
    if not dry_run:
        for path in existing:
            path.unlink()
        if receipt_path.exists():
            receipt_path.unlink()
    action = "would remove" if dry_run else "removed"
    return [f"{target}: {action} native role templates"]


def read_json_object(path: Path) -> dict[str, object]:
    try:
        if not path.exists() or not path.read_text(encoding="utf-8").strip():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise _InstallError(f"{path.name}: could not read configuration") from exc
    except json.JSONDecodeError as exc:
        raise _InstallError(
            f"{path.name}: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    if not isinstance(data, dict):
        raise _InstallError(f"{path.name}: top-level JSON value must be an object")
    return data


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, data: object) -> None:
    write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def install_claude_plugin(paths: _InstallPaths, *, dry_run: bool) -> None:
    # Validate even for dry runs through the canonical allowlisted copier.
    if dry_run:
        _copy_skill_tree(paths.repo_root, paths.claude_skill, dry_run=True)
        return

    target = paths.claude_plugin
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.tmp-{os.getpid()}")
    if temp.exists():
        shutil.rmtree(temp)
    try:
        (temp / ".claude-plugin").mkdir(parents=True)
        (temp / "skills").mkdir()
        write_json(
            temp / ".claude-plugin" / "plugin.json",
            {
                "name": SKILL_NAME,
                "version": VERSION,
                "description": DESCRIPTION,
                "author": {"name": "Better Plan"},
            },
        )
        for name in ("README.md", "LICENSE"):
            source = paths.repo_root / name
            if source.is_file():
                shutil.copy2(source, temp / name)
        _copy_skill_tree(paths.repo_root, temp / "skills" / SKILL_NAME, dry_run=False)
        if target.exists():
            shutil.rmtree(target)
        temp.rename(target)
    except Exception:
        if temp.exists():
            shutil.rmtree(temp)
        raise


def opencode_agent_text() -> str:
    return """---
description: Follow the Better Plan design-first workflow with deterministic acceptance and regression.
mode: primary
temperature: 0.1
permission:
  edit: allow
  bash: allow
---

Before acting, locate the installed `better-plan` skill, read its `SKILL.md` completely,
and follow it as the active workflow. Use `scripts/manifest_tool.py` inside the skill for
state transitions and validation. Do not preserve removed implementations or compatibility
shims. Preserve unrelated user changes and verify real behavior before completion.
"""


def antigravity_manifest() -> dict[str, str]:
    return {"name": SKILL_NAME}


def antigravity_hooks() -> dict[str, object]:
    return {
        SKILL_NAME: {
            "PreInvocation": [
                {
                    "type": "command",
                    "command": _hook_command("antigravity", "session-start"),
                    "timeout": 30,
                }
            ]
        }
    }


def install_antigravity_plugin(paths: _InstallPaths, *, dry_run: bool) -> None:
    if dry_run:
        _copy_skill_tree(paths.repo_root, paths.antigravity_skill, dry_run=True)
        return

    target = paths.antigravity_plugin
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.tmp-{os.getpid()}")
    if temp.exists():
        shutil.rmtree(temp)
    try:
        temp.mkdir()
        write_json(temp / "plugin.json", antigravity_manifest())
        write_json(temp / "hooks.json", antigravity_hooks())
        _copy_skill_tree(paths.repo_root, temp / "skills" / SKILL_NAME, dry_run=False)
        if target.exists():
            shutil.rmtree(target)
        temp.rename(target)
    except Exception:
        if temp.exists():
            shutil.rmtree(temp)
        raise


def install_craft_skills(paths: _InstallPaths, *, dry_run: bool) -> int:
    for target in paths.craft_skills:
        _copy_skill_tree(paths.repo_root, target, dry_run=dry_run)
    return len(paths.craft_skills)


def hook_config_path(paths: _InstallPaths, agent: str) -> Path:
    if agent == "codex":
        return paths.codex_hooks
    if agent == "claude":
        return paths.claude_settings
    if agent == "cursor":
        return paths.cursor_hooks
    if agent == "kimi":
        return paths.kimi_config
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


def decode_probe_output(data: bytes) -> str:
    if not data:
        return ""
    if data.startswith(b"\xff\xfe") or data.count(b"\x00") > max(1, len(data) // 8):
        return data.decode("utf-16le", errors="replace").replace("\ufeff", "")
    return data.decode("utf-8", errors="replace")


def parse_running_wsl_distros(output: str) -> list[str]:
    distros: list[str] = []
    for value in (line.strip() for line in output.replace("\x00", "").splitlines()):
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


WSL_OPENCODE_PROBE_SCRIPT = (
    "path=$(command -v opencode 2>/dev/null) || exit 1; "
    "printf '%s\\n' \"$path\"; printf '%s\\n' \"$HOME\"; "
    "opencode --version 2>/dev/null | head -n 1 || true"
)


def wsl_executable() -> str | None:
    if os.name != "nt":
        return None
    return shutil.which("wsl.exe") or shutil.which("wsl")


def run_wsl_script(
    wsl: str,
    distro: str,
    script: str,
    *,
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    return run_text_command([wsl, "-d", distro, "-e", "bash", "-lic", script], timeout=timeout)


def split_wsl_probe_stdout(stdout: str) -> tuple[str, str, str] | None:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if len(lines) < 2:
        return None
    return lines[0], lines[1], lines[2] if len(lines) > 2 else "version unknown"


def discover_wsl_opencode() -> list[_WslOpenCodeRuntime]:
    wsl = wsl_executable()
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

    probes: list[_WslOpenCodeRuntime] = []
    for distro in parse_running_wsl_distros(decode_probe_output(result.stdout)):
        try:
            probe = run_wsl_script(wsl, distro, WSL_OPENCODE_PROBE_SCRIPT, timeout=20)
        except _InstallError:
            continue
        found = split_wsl_probe_stdout(probe.stdout if probe.returncode == 0 else "")
        if found:
            location, home, version = found
            probes.append(_WslOpenCodeRuntime(distro, location, home, version))
    return probes


def wsl_source_path(wsl: str, runtime: _WslOpenCodeRuntime, source: Path) -> str:
    result = run_text_command(
        [wsl, "-d", runtime.distro, "-e", "wslpath", "-a", str(source)],
        timeout=20,
    )
    path = result.stdout.strip() if result.returncode == 0 else ""
    if not path:
        raise _InstallError("unable to resolve Better Plan source inside the WSL runtime")
    return path


def install_wsl_opencode(
    paths: _InstallPaths,
    *,
    dry_run: bool,
) -> list[str]:
    wsl = wsl_executable()
    if wsl is None:
        return []
    messages: list[str] = []
    for runtime in discover_wsl_opencode():
        if dry_run:
            messages.append("opencode: would update detected WSL runtime")
            continue
        source = wsl_source_path(wsl, runtime, paths.repo_root)
        installer = posixpath.join(source, "scripts", "install.py")
        script = f"python3 {shlex.quote(installer)} update --agents codex,opencode"
        result = run_wsl_script(wsl, runtime.distro, script, timeout=120)
        if result.returncode != 0:
            raise _InstallError("failed to update Better Plan in the WSL runtime")
        messages.append("opencode: updated detected WSL runtime")
    return messages


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
    role_messages: list[str] = []
    if target in NATIVE_ROLE_FILES:
        role_messages.extend(install_role_templates(paths, target, dry_run=dry_run))
    if target == "codex":
        _, changed = update_agent_hooks(paths, target, dry_run=dry_run)
        action = "would update" if dry_run and changed else "updated" if changed else "already current"
        return [*role_messages, f"codex hooks: {action} managed handlers"]
    if target == "claude":
        install_claude_plugin(paths, dry_run=dry_run)
        _, changed = update_agent_hooks(paths, target, dry_run=dry_run)
        action = "would update" if dry_run and changed else "updated" if changed else "already current"
        return [
            *role_messages,
            f"claude: {'would update' if dry_run else 'updated'} plugin",
            f"claude hooks: {action} managed handlers",
        ]
    if target == "opencode":
        if not dry_run:
            write_text(paths.opencode_agent, opencode_agent_text())
        return [
            *role_messages,
            f"opencode: {'would update' if dry_run else 'updated'} agent",
            *install_wsl_opencode(
                paths,
                dry_run=dry_run,
            ),
        ]
    if target == "cursor":
        _, changed = update_agent_hooks(paths, target, dry_run=dry_run)
        action = "would update" if dry_run and changed else "updated" if changed else "already current"
        return [*role_messages, f"cursor hooks: {action} managed handlers"]
    if target == "kimi":
        _, changed = update_agent_hooks(paths, target, dry_run=dry_run)
        action = "would update" if dry_run and changed else "updated" if changed else "already current"
        return [f"kimi hooks: {action} managed handlers"]
    if target == "antigravity":
        install_antigravity_plugin(paths, dry_run=dry_run)
        return [f"antigravity: {'would update' if dry_run else 'updated'} plugin"]
    if target == "craft":
        count = install_craft_skills(paths, dry_run=dry_run)
        if count == 0:
            return ["craft: no configured workspaces found"]
        action = "would update" if dry_run else "updated"
        return [f"craft: {action} skill in {count} workspace(s)"]
    return []


def remove_target(paths: _InstallPaths, target: str, *, dry_run: bool) -> list[str]:
    if target not in AGENTS:
        raise _InstallError(f"unknown agent target: {target}")
    if target == "kilo":
        if not dry_run:
            _remove_path(paths.kilo_skill)
        action = "would remove" if dry_run else "removed"
        return [
            f"kilo: {action} native skill",
            "kilo: preserved immutable native Agent matrix",
        ]
    native_messages = (
        remove_role_templates(paths, target, dry_run=dry_run)
        if target in NATIVE_ROLE_FILES
        else []
    )
    if target == "craft":
        count = len(paths.craft_skills)
        if not dry_run:
            for path in paths.craft_skills:
                _remove_path(path)
        action = "would remove" if dry_run else "removed"
        return [*native_messages, f"craft: {action} skill from {count} workspace(s)"]

    path = {
        "codex": paths.codex_skill,
        "claude": paths.claude_plugin,
        "opencode": paths.opencode_agent,
        "cursor": paths.cursor_skill,
        "copilot": paths.copilot_skill,
        "antigravity": paths.antigravity_plugin,
        "pi": paths.pi_skill,
        "kimi": paths.kimi_skill,
    }[target]
    if not dry_run:
        _remove_path(path)
    return [*native_messages, f"{target}: {'would remove' if dry_run else 'removed'}"]
