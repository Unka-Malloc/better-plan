"""Read-only verification of installed Better Plan targets."""

from __future__ import annotations

import shlex
import shutil
import sys

from ..hooks.config import hook_config_status as _hook_config_status
from . import skills as _skills
from . import targets as _targets
from .models import (
    CURRENT_SKILL_FILES,
    OPTIONAL_CLIENT_CLI_COMMANDS,
    SKILL_NAME,
    Check as _Check,
    InstallError as _InstallError,
    InstallPaths as _InstallPaths,
)


def run_manifest_tool(skill_root) -> bool:
    tool = skill_root / "scripts" / "manifest_tool.py"
    if not tool.is_file():
        return False
    result = _targets.run_text_command([sys.executable, str(tool), "uuid"], timeout=10)
    return result.returncode == 0 and bool(result.stdout.strip())


def check_skill_tree(target: str, root) -> _Check:
    missing = [relative for relative in CURRENT_SKILL_FILES if not (root / relative).is_file()]
    if missing:
        return _Check("FAIL", target, f"installed skill is invalid: missing file(s) {', '.join(missing)}")
    if not run_manifest_tool(root):
        return _Check("FAIL", target, "manifest tool validation failed")
    return _Check("OK", target, "installed skill structure verified")


def check_agent_hooks(paths: _InstallPaths, agent: str) -> _Check:
    config = _targets.hook_config_path(paths, agent)
    ok, message = _hook_config_status(config, agent)
    return _Check("OK" if ok else "FAIL", f"{agent} hooks", message)


def check_shared_scan_agent(paths: _InstallPaths, target: str) -> _Check:
    kind, root = _skills.shared_scan_skill_target(paths, target)
    check = check_skill_tree(target, root)
    if check.status != "OK":
        return check
    native_root = _skills.native_skill_path(paths, target)
    if kind == "shared" and native_root.exists():
        return _Check("WARN", target, "shared skill is installed but a duplicate native skill still exists")
    if target in OPTIONAL_CLIENT_CLI_COMMANDS:
        return check_optional_client_cli(target)
    return _Check("OK", target, f"installed via {kind} skill")


def doctor(paths: _InstallPaths, agents: list[str]) -> list[_Check]:
    """Return bounded structural and optional runtime checks for selected agents."""
    checks: list[_Check] = []
    scan_targets = _skills.shared_scan_targets(paths, agents)
    implementation = _skills.implementation_root(paths, scan_targets)
    if _skills.adapter_needs_skill_root(agents) and not any(
        target == implementation for _, target in scan_targets.values()
    ):
        checks.append(check_skill_tree("implementation", implementation))
    if "codex" in agents:
        checks.append(check_shared_scan_agent(paths, "codex"))
        checks.append(check_agent_hooks(paths, "codex"))
    if "claude" in agents:
        checks.append(check_claude(paths))
        checks.append(check_agent_hooks(paths, "claude"))
    if "opencode" in agents:
        checks.extend(check_opencode(paths))
    if "cursor" in agents:
        checks.append(check_shared_scan_agent(paths, "cursor"))
        checks.append(check_agent_hooks(paths, "cursor"))
    if "copilot" in agents:
        checks.append(check_shared_scan_agent(paths, "copilot"))
    if "antigravity" in agents:
        checks.append(check_antigravity(paths))
    if "pi" in agents:
        checks.append(check_shared_scan_agent(paths, "pi"))
    if "craft" in agents:
        checks.append(check_craft(paths))
    if "kimi" in agents:
        checks.append(check_shared_scan_agent(paths, "kimi"))
        checks.append(check_agent_hooks(paths, "kimi"))
    return checks


def check_claude(paths: _InstallPaths) -> _Check:
    manifest = paths.claude_plugin / ".claude-plugin" / "plugin.json"
    if not manifest.is_file():
        return _Check("FAIL", "claude", "plugin manifest is missing")
    skill_check = check_skill_tree("claude", paths.claude_skill)
    if skill_check.status != "OK":
        return skill_check
    claude = shutil.which("claude")
    if claude is None:
        return _Check("WARN", "claude", "plugin structure verified; claude CLI not found for runtime validation")
    result = _targets.run_text_command(
        [claude, "plugin", "validate", str(paths.claude_plugin)], timeout=30
    )
    if result.returncode != 0:
        return _Check("FAIL", "claude", "plugin validation failed")
    return _Check("OK", "claude", "plugin structure and runtime validation passed")


def check_opencode(paths: _InstallPaths) -> list[_Check]:
    if not paths.opencode_agent.is_file():
        return [_Check("FAIL", "opencode", "agent definition is missing")]
    text = paths.opencode_agent.read_text(encoding="utf-8")
    if "installed `better-plan` skill" not in text or "scripts/manifest_tool.py" not in text:
        return [_Check("FAIL", "opencode", "agent definition does not reference the current skill interface")]

    checks: list[_Check] = []
    opencode = shutil.which("opencode")
    if opencode is None:
        checks.append(_Check("WARN", "opencode", "agent definition verified; host opencode CLI not found"))
    else:
        result = _targets.run_text_command([opencode, "agent", "list"], timeout=30)
        if result.returncode != 0:
            checks.append(_Check("FAIL", "opencode", "opencode agent list failed"))
        elif SKILL_NAME not in result.stdout:
            checks.append(_Check("FAIL", "opencode", f"opencode agent list did not include {SKILL_NAME}"))
        else:
            checks.append(_Check("OK", "opencode", "agent definition and runtime listing verified"))

    for runtime in _targets.discover_wsl_opencode():
        wsl = _targets.wsl_executable()
        if wsl is None:
            continue
        script = f"{shlex.quote(runtime.location)} agent list"
        result = _targets.run_wsl_script(wsl, runtime.distro, script, timeout=30)
        target = "opencode (WSL)"
        if result.returncode != 0:
            checks.append(_Check("FAIL", target, "opencode agent list failed"))
        elif SKILL_NAME not in result.stdout:
            checks.append(_Check("FAIL", target, f"opencode agent list did not include {SKILL_NAME}"))
        else:
            checks.append(_Check("OK", target, "agent listing verified in detected runtime"))
    return checks


def check_optional_client_cli(target: str) -> _Check:
    command = OPTIONAL_CLIENT_CLI_COMMANDS[target]
    executable = shutil.which(command[0])
    if executable is None:
        return _Check("WARN", target, f"adapter structure verified; {command[0]} CLI not found for runtime validation")
    result = _targets.run_text_command([executable, *command[1:]], timeout=30)
    if result.returncode != 0:
        return _Check("FAIL", target, f"{command[0]} CLI version check failed")
    return _Check("OK", target, f"adapter structure and {command[0]} CLI verified")


def check_antigravity(paths: _InstallPaths) -> _Check:
    manifest = paths.antigravity_plugin / "plugin.json"
    hooks = paths.antigravity_plugin / "hooks.json"
    if not manifest.is_file():
        return _Check("FAIL", "antigravity", "plugin manifest is missing")
    if not hooks.is_file():
        return _Check("FAIL", "antigravity", "plugin Hook configuration is missing")
    skill_check = check_skill_tree("antigravity", paths.antigravity_skill)
    if skill_check.status != "OK":
        return skill_check
    try:
        manifest_data = _targets.read_json_object(manifest)
        hook_data = _targets.read_json_object(hooks)
    except _InstallError as exc:
        return _Check("FAIL", "antigravity", str(exc))
    if manifest_data.get("name") != SKILL_NAME:
        return _Check("FAIL", "antigravity", "plugin manifest name is invalid")
    expected = _targets.antigravity_hooks()
    if hook_data != expected:
        return _Check("FAIL", "antigravity", "plugin Hook configuration is not current")
    return _Check("OK", "antigravity", "plugin, skill, and lifecycle Hook verified")


def check_craft(paths: _InstallPaths) -> _Check:
    if not paths.craft_skills:
        return _Check("WARN", "craft", "no configured Craft workspace found")
    for root in paths.craft_skills:
        result = check_skill_tree("craft", root)
        if result.status != "OK":
            return result
    return _Check("OK", "craft", f"installed skill verified in {len(paths.craft_skills)} workspace(s)")
