"""Own Better Plan lifecycle Hook entries inside supported agent configs."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any

from . import protocols


AGENTS = ("codex", "claude", "cursor", "kimi")
MANAGED_MARKER = "--managed-by better-plan"
PORTABLE_PYTHON = "python" if os.name == "nt" else "python3"
HOOK_TIMEOUT_SECONDS = 30


class HookConfigError(RuntimeError):
    """Raised when Hook configuration cannot be updated without data loss."""


def read_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise HookConfigError("cannot read Hook configuration") from exc
    if not text.strip():
        return {}
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HookConfigError(
            f"invalid Hook JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    if not isinstance(value, dict):
        raise HookConfigError("top-level Hook configuration must be an object")
    return value


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    temp: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
        if path.exists() and path.read_text(encoding="utf-8") == content:
            return
        temp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
        temp.write_text(content, encoding="utf-8")
        if path.exists():
            temp.chmod(path.stat().st_mode)
        os.replace(temp, path)
    except OSError as exc:
        raise HookConfigError("cannot update Hook configuration safely") from exc
    finally:
        if temp is not None and temp.exists():
            try:
                temp.unlink()
            except OSError:
                pass


def skill_root_expressions(agent: str) -> list[str]:
    shared = "Path(os.environ.get('BETTER_PLAN_SHARED_HOME') or h/'.agents')/'skills'/'better-plan'"
    if agent == "codex":
        native = "Path(os.environ.get('CODEX_HOME') or h/'.codex')/'skills'/'better-plan'"
        return [shared, native]
    if agent == "claude":
        plugin = (
            "Path(os.environ.get('CLAUDE_HOME') or h/'.claude')/"
            "'skills'/'better-plan'/'skills'/'better-plan'"
        )
        return [plugin]
    if agent == "cursor":
        native = "Path(os.environ.get('CURSOR_HOME') or h/'.cursor')/'skills'/'better-plan'"
        return [shared, native]
    if agent == "antigravity":
        plugin = (
            "Path(os.environ.get('ANTIGRAVITY_HOME') or h/'.gemini'/'config')/"
            "'plugins'/'better-plan'/'skills'/'better-plan'"
        )
        return [plugin]
    if agent == "kimi":
        native = (
            "Path(os.environ.get('KIMI_CODE_HOME') or h/'.kimi-code')/"
            "'skills'/'better-plan'"
        )
        return [shared, native]
    raise HookConfigError(f"unsupported Hook agent: {agent}")


def hook_launcher_code(agent: str, event: str) -> str:
    roots = ",".join(skill_root_expressions(agent))
    missing_skill_response = "None" if agent == "kimi" else "print('{}')"
    return (
        "import os,runpy,sys;from pathlib import Path;h=Path.home();"
        f"roots=[{roots}];"
        "script=next((root/'scripts'/'hook_tool.py' for root in roots "
        "if (root/'SKILL.md').is_file() "
        "and (root/'scripts'/'better_plan'/'hooks'/'scope.py').is_file() "
        "and (root/'scripts'/'better_plan'/'hooks'/'context.py').is_file() "
        "and (root/'scripts'/'hook_tool.py').is_file()),None);"
        f"sys.argv=[str(script),'--agent',{agent!r},'--event',{event!r},'--managed-by','better-plan'];"
        "runpy.run_path(str(script),run_name='__main__') "
        f"if script is not None else {missing_skill_response}"
    )


def hook_command(agent: str, event: str) -> str:
    arguments = [
        PORTABLE_PYTHON,
        "-c",
        hook_launcher_code(agent, event),
        "--managed-by",
        "better-plan",
    ]
    return subprocess.list2cmdline(arguments) if os.name == "nt" else shlex.join(arguments)


def _toml_header(line: str) -> bool:
    value = line.strip()
    return (
        value.startswith("[")
        and "]" in value
        and not value.startswith("#")
    )


def clean_kimi_hooks(text: str) -> str:
    """Remove only complete Better Plan-owned Kimi Hook tables."""
    lines = text.splitlines(keepends=True)
    output: list[str] = []
    index = 0
    while index < len(lines):
        if lines[index].strip() != "[[hooks]]":
            output.append(lines[index])
            index += 1
            continue
        end = index + 1
        while end < len(lines) and not _toml_header(lines[end]):
            end += 1
        block = "".join(lines[index:end])
        if MANAGED_MARKER not in block:
            output.extend(lines[index:end])
        index = end
    return "".join(output)


def kimi_hook_tables() -> str:
    blocks: list[str] = []
    for host_event, event in protocols.host_events("kimi").items():
        command = json.dumps(hook_command("kimi", event), ensure_ascii=False)
        blocks.append(
            "\n".join(
                (
                    "[[hooks]]",
                    f"event = {json.dumps(host_event)}",
                    f"command = {command}",
                    f"timeout = {HOOK_TIMEOUT_SECONDS}",
                )
            )
        )
    return "\n\n".join(blocks) + "\n"


def merged_kimi_config(current: str) -> str:
    cleaned = clean_kimi_hooks(current).rstrip()
    managed = kimi_hook_tables().rstrip()
    return f"{cleaned}\n\n{managed}\n" if cleaned else f"{managed}\n"


def atomic_write_text(path: Path, content: str) -> None:
    temp: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_text(encoding="utf-8") == content:
            return
        temp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
        temp.write_text(content, encoding="utf-8")
        if path.exists():
            temp.chmod(path.stat().st_mode)
        os.replace(temp, path)
    except OSError as exc:
        raise HookConfigError("cannot update Hook configuration safely") from exc
    finally:
        if temp is not None and temp.exists():
            try:
                temp.unlink()
            except OSError:
                pass


def install_kimi_hook_config(path: Path, *, dry_run: bool) -> bool:
    try:
        current = path.read_text(encoding="utf-8") if path.exists() else ""
    except OSError as exc:
        raise HookConfigError("cannot read Hook configuration") from exc
    updated = merged_kimi_config(current)
    changed = updated != current
    if changed and not dry_run:
        atomic_write_text(path, updated)
    return changed


def uninstall_kimi_hook_config(path: Path, *, dry_run: bool) -> bool:
    if not path.exists():
        return False
    try:
        current = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise HookConfigError("cannot read Hook configuration") from exc
    updated = clean_kimi_hooks(current)
    changed = updated != current
    if changed and not dry_run:
        atomic_write_text(path, updated)
    return changed


def is_managed_handler(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("command"), str)
        and MANAGED_MARKER in value["command"]
    )


def _nested_host_events(agent: str) -> dict[str, str]:
    if agent not in {"codex", "claude"}:
        raise HookConfigError(f"unsupported Hook agent: {agent}")
    return dict(protocols.host_events(agent))


def _cursor_host_events(agent: str) -> dict[str, str]:
    if agent != "cursor":
        raise HookConfigError(f"unsupported Hook agent: {agent}")
    return dict(protocols.host_events(agent))


def clean_nested_hooks(data: dict[str, Any], agent: str) -> dict[str, Any]:
    if agent not in {"codex", "claude"}:
        raise HookConfigError(f"unsupported Hook agent: {agent}")
    nested_events = _nested_host_events(agent)
    cleaned = dict(data)
    hooks_value = cleaned.get("hooks")
    if hooks_value is None:
        return cleaned
    if not isinstance(hooks_value, dict):
        raise HookConfigError("Hook configuration field 'hooks' must be an object")

    hooks = dict(hooks_value)
    for event, groups_value in list(hooks.items()):
        if not isinstance(groups_value, list):
            if event in nested_events:
                raise HookConfigError(f"Hook event {event!r} must be an array")
            continue
        groups: list[Any] = []
        for group in groups_value:
            if not isinstance(group, dict):
                groups.append(group)
                continue
            handlers_value = group.get("hooks")
            if not isinstance(handlers_value, list):
                groups.append(group)
                continue
            had_managed_handler = any(
                is_managed_handler(handler) for handler in handlers_value
            )
            handlers = [handler for handler in handlers_value if not is_managed_handler(handler)]
            if handlers:
                next_group = dict(group)
                next_group["hooks"] = handlers
                groups.append(next_group)
            elif not had_managed_handler:
                groups.append(group)
        if groups:
            hooks[event] = groups
        else:
            hooks.pop(event, None)
    cleaned["hooks"] = hooks
    return cleaned


def clean_flat_hooks(data: dict[str, Any]) -> dict[str, Any]:
    if "version" in data and data.get("version") != 1:
        raise HookConfigError("unsupported Cursor Hook configuration version")
    cleaned = dict(data)
    hooks_value = cleaned.get("hooks")
    if hooks_value is None:
        return cleaned
    if not isinstance(hooks_value, dict):
        raise HookConfigError("Hook configuration field 'hooks' must be an object")

    current_events = set(_cursor_host_events("cursor"))
    hooks: dict[str, Any] = {}
    for event, handlers_value in hooks_value.items():
        if not isinstance(handlers_value, list):
            if event in current_events:
                raise HookConfigError(f"Hook event {event!r} must be an array")
            hooks[event] = handlers_value
            continue
        had_managed_handler = any(
            is_managed_handler(handler) for handler in handlers_value
        )
        handlers = [handler for handler in handlers_value if not is_managed_handler(handler)]
        if handlers:
            hooks[event] = handlers
        elif not had_managed_handler:
            hooks[event] = handlers_value
    cleaned["hooks"] = hooks
    return cleaned


def nested_handlers(agent: str) -> dict[str, list[dict[str, Any]]]:
    if agent not in {"codex", "claude"}:
        raise HookConfigError(f"unsupported Hook agent: {agent}")
    handlers: dict[str, list[dict[str, Any]]] = {}
    for host_event, normalized_event in _nested_host_events(agent).items():
        group: dict[str, Any] = {
            "hooks": [
                {
                    "type": "command",
                    "command": hook_command(agent, normalized_event),
                    "timeout": HOOK_TIMEOUT_SECONDS,
                }
            ]
        }
        matcher = protocols.event_matcher(agent, normalized_event)
        if matcher is not None:
            group["matcher"] = matcher
        handlers[host_event] = [group]
    return handlers


def flat_handlers(agent: str) -> dict[str, list[dict[str, Any]]]:
    if agent != "cursor":
        raise HookConfigError(f"unsupported Hook agent: {agent}")
    handlers: dict[str, list[dict[str, Any]]] = {}
    for host_event, normalized_event in _cursor_host_events(agent).items():
        handler = {"command": hook_command(agent, normalized_event)}
        matcher = protocols.event_matcher(agent, normalized_event)
        if matcher is not None:
            handler["matcher"] = matcher
        handlers[host_event] = [handler]
    return handlers


def merged_config(current: dict[str, Any], agent: str) -> dict[str, Any]:
    if agent in {"codex", "claude"}:
        merged = clean_nested_hooks(current, agent)
        hooks = dict(merged.get("hooks") or {})
        for event, groups in nested_handlers(agent).items():
            existing = hooks.get(event)
            hooks[event] = (list(existing) if isinstance(existing, list) else []) + groups
        merged["hooks"] = hooks
        return merged

    if agent == "cursor":
        merged = clean_flat_hooks(current)
        merged.setdefault("version", 1)
        hooks = dict(merged.get("hooks") or {})
        for event, handlers in flat_handlers(agent).items():
            existing = hooks.get(event)
            hooks[event] = (list(existing) if isinstance(existing, list) else []) + handlers
        merged["hooks"] = hooks
        return merged

    raise HookConfigError(f"unsupported Hook agent: {agent}")


def removed_config(current: dict[str, Any], agent: str) -> dict[str, Any]:
    if agent in {"codex", "claude"}:
        return clean_nested_hooks(current, agent)
    if agent == "cursor":
        return clean_flat_hooks(current)
    raise HookConfigError(f"unsupported Hook agent: {agent}")


def _extract_event_commands_nested(data: dict[str, Any], agent: str) -> dict[str, list[str]]:
    nested_events = set(_nested_host_events(agent))
    hooks = data.get("hooks")
    found: dict[str, list[str]] = {event: [] for event in nested_events}
    if not isinstance(hooks, dict):
        return found
    for event, groups_value in hooks.items():
        if event not in nested_events or not isinstance(groups_value, list):
            continue
        for group in groups_value:
            if not isinstance(group, dict):
                continue
            handlers = group.get("hooks")
            if not isinstance(handlers, list):
                continue
            found[event].extend(
                str(handler["command"])
                for handler in handlers
                if is_managed_handler(handler)
            )
    return found


def _extract_event_commands_flat(data: dict[str, Any], agent: str) -> dict[str, list[str]]:
    cursor_events = set(_cursor_host_events(agent))
    hooks = data.get("hooks")
    found: dict[str, list[str]] = {event: [] for event in cursor_events}
    if not isinstance(hooks, dict):
        return found
    for event, handlers_value in hooks.items():
        if event not in cursor_events or not isinstance(handlers_value, list):
            continue
        found[event].extend(
            str(handler["command"])
            for handler in handlers_value
            if is_managed_handler(handler)
        )
    return found


def _managed_groups_nested(data: dict[str, Any], agent: str) -> dict[str, list[dict[str, Any]]]:
    nested_events = set(_nested_host_events(agent))
    found: dict[str, list[dict[str, Any]]] = {event: [] for event in nested_events}
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return found
    for event, groups_value in hooks.items():
        if event not in nested_events or not isinstance(groups_value, list):
            continue
        for group in groups_value:
            if not isinstance(group, dict):
                continue
            handlers = group.get("hooks")
            if isinstance(handlers, list) and any(
                is_managed_handler(handler) for handler in handlers
            ):
                found[event].append(group)
    return found


def _managed_handlers_flat(data: dict[str, Any], agent: str) -> dict[str, list[dict[str, Any]]]:
    cursor_events = set(_cursor_host_events(agent))
    found: dict[str, list[dict[str, Any]]] = {event: [] for event in cursor_events}
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return found
    for event, handlers_value in hooks.items():
        if event not in cursor_events or not isinstance(handlers_value, list):
            continue
        found[event].extend(
            handler
            for handler in handlers_value
            if isinstance(handler, dict) and is_managed_handler(handler)
        )
    return found


def _managed_events_outside_current(data: dict[str, Any], agent: str) -> set[str]:
    current_events: set[str]
    if agent in {"codex", "claude"}:
        current_events = set(_nested_host_events(agent))
        hooks = data.get("hooks")
        if not isinstance(hooks, dict):
            return set()
        outside: set[str] = set()
        for event, groups_value in hooks.items():
            if event in current_events or not isinstance(groups_value, list):
                continue
            for group in groups_value:
                if not isinstance(group, dict):
                    continue
                handlers = group.get("hooks")
                if isinstance(handlers, list) and any(is_managed_handler(handler) for handler in handlers):
                    outside.add(event)
                    break
        return outside

    if agent == "cursor":
        current_events = set(_cursor_host_events(agent))
        hooks = data.get("hooks")
        if not isinstance(hooks, dict):
            return set()
        outside: set[str] = set()
        for event, handlers_value in hooks.items():
            if event in current_events or not isinstance(handlers_value, list):
                continue
            if any(is_managed_handler(handler) for handler in handlers_value):
                outside.add(event)
        return outside

    raise HookConfigError(f"unsupported Hook agent: {agent}")


def configured_commands(data: dict[str, Any], agent: str) -> dict[str, list[str]]:
    if agent not in AGENTS:
        raise HookConfigError(f"unsupported Hook agent: {agent}")
    if not isinstance(data, dict):
        raise HookConfigError("Hook configuration must be an object")
    if agent in {"codex", "claude"}:
        return _extract_event_commands_nested(data, agent)
    if agent == "cursor":
        return _extract_event_commands_flat(data, agent)
    raise HookConfigError(f"unsupported Hook agent: {agent}")


def install_hook_config(path: Path, agent: str, *, dry_run: bool) -> bool:
    if agent == "kimi":
        return install_kimi_hook_config(path, dry_run=dry_run)
    current = read_json_object(path)
    updated = merged_config(current, agent)
    changed = updated != current
    if changed and not dry_run:
        atomic_write_json(path, updated)
    return changed


def uninstall_hook_config(path: Path, agent: str, *, dry_run: bool) -> bool:
    if agent == "kimi":
        return uninstall_kimi_hook_config(path, dry_run=dry_run)
    if not path.exists():
        return False
    current = read_json_object(path)
    updated = removed_config(current, agent)
    changed = updated != current
    if changed and not dry_run:
        atomic_write_json(path, updated)
    return changed


def hook_config_status(path: Path, agent: str) -> tuple[bool, str]:
    if not path.is_file():
        return False, "managed Hook configuration is missing"
    if agent == "kimi":
        try:
            current = path.read_text(encoding="utf-8")
        except OSError:
            return False, "cannot read Hook configuration"
        if current != merged_kimi_config(clean_kimi_hooks(current)):
            return False, "expected exactly one current Better Plan handler for each Kimi lifecycle event"
        return True, "managed Hook configuration verified"
    try:
        data = read_json_object(path)
        if agent in {"codex", "claude"}:
            clean_nested_hooks(data, agent)
        elif agent == "cursor":
            clean_flat_hooks(data)
            if data.get("version") != 1:
                return False, "expected Cursor Hook configuration version 1"
        else:
            raise HookConfigError(f"unsupported Hook agent: {agent}")
    except HookConfigError as exc:
        return False, str(exc)

    host_events = protocols.host_events(agent)
    outside = _managed_events_outside_current(data, agent)
    if outside:
        return False, "managed Better Plan handler exists outside the current lifecycle event set"

    if agent in {"codex", "claude"}:
        current_groups = _managed_groups_nested(data, agent)
        expected_groups = nested_handlers(agent)
        for host_event in host_events:
            if current_groups.get(host_event) != expected_groups[host_event]:
                return False, f"expected exactly one current Better Plan handler for {host_event}"
    else:
        current_handlers = _managed_handlers_flat(data, agent)
        expected_handlers = flat_handlers(agent)
        for host_event in host_events:
            if current_handlers.get(host_event) != expected_handlers[host_event]:
                return False, f"expected exactly one current Better Plan handler for {host_event}"
    return True, "managed Hook configuration verified"
