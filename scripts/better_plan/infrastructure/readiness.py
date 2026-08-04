"""Host-repository readiness check for Better Plan state."""

from __future__ import annotations

from typing import Any
import hashlib
import json
import subprocess
import tempfile

from ..domain.models import ToolError, is_relative_workspace_path, normalize_workspace_path, public_summary, safe_summary_issue
from .regression import evidence_timestamp
from .workspace import NodeLocation, project_root_for, write_state_entries


def _contract_digest(readiness_check: dict[str, Any]) -> str:
    payload = {field: readiness_check[field] for field in ("commands", "paths")}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _state_fingerprint(location: NodeLocation, readiness_check: dict[str, Any]) -> str:
    digest = hashlib.sha256()
    plan = dict(location.manifest_data[location.plan_index])
    plan.pop("readiness_check", None)
    digest.update(json.dumps(plan, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())
    digest.update(json.dumps(location.checkpoints_data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())
    root = project_root_for(location.manifest.parent).resolve()
    for relative in sorted(set(readiness_check["paths"])):
        candidate = root / normalize_workspace_path(relative)
        if not candidate.exists() or candidate.is_symlink():
            raise ToolError(f"plan readiness path {relative!r} is missing or unsafe")
        if candidate.is_dir():
            discovered = list(candidate.rglob("*"))
            symlink = next((path for path in discovered if path.is_symlink()), None)
            if symlink is not None:
                raise ToolError(f"plan readiness path {relative!r} contains a symbolic link")
            entries = sorted(path for path in discovered if path.is_file())
        else:
            entries = [candidate]
        for entry in entries:
            digest.update(entry.relative_to(root).as_posix().encode())
            digest.update(entry.read_bytes())
    return digest.hexdigest()


def ensure_plan_readiness_current(location: NodeLocation) -> None:
    plan = location.manifest_data[location.plan_index]
    readiness_check = plan.get("readiness_check")
    if readiness_check is None:
        return
    if not isinstance(readiness_check, dict):
        raise ToolError("the selected Plan has an invalid host readiness contract")
    receipt = readiness_check.get("last_pass")
    if not isinstance(receipt, dict):
        raise ToolError("the selected Plan must pass check-plan-readiness before delivery dispatch")
    if receipt.get("contract_digest") != _contract_digest(readiness_check):
        raise ToolError("the selected Plan readiness contract changed after its passing receipt")
    if receipt.get("state_fingerprint") != _state_fingerprint(location, readiness_check):
        raise ToolError("the selected Plan or its readiness paths changed after the last readiness check")


def run_plan_readiness_check(location: NodeLocation, commands: list[str], paths: list[str]) -> dict[str, Any]:
    if not commands or not paths:
        raise ToolError("check-plan-readiness requires at least one command and one repository-relative path")
    for command in commands:
        issue = safe_summary_issue(command)
        if issue is not None:
            raise ToolError(f"plan readiness command {issue}")
    if any(not is_relative_workspace_path(path) for path in paths):
        raise ToolError("plan readiness paths must be safe repository-relative paths")
    plan = location.manifest_data[location.plan_index]
    readiness_check: dict[str, Any] = {"commands": commands, "paths": paths}
    plan["readiness_check"] = readiness_check
    before = _state_fingerprint(location, readiness_check)
    root = project_root_for(location.manifest.parent)
    failures: list[str] = []
    for index, command in enumerate(commands):
        with tempfile.TemporaryFile() as output:
            try:
                result = subprocess.run(command, cwd=root, shell=True, stdout=output, stderr=subprocess.STDOUT, timeout=300, check=False)
            except (OSError, subprocess.TimeoutExpired):
                failures.append(f"command[{index}] unavailable or timed out")
                continue
            if result.returncode != 0:
                output.seek(0, 2)
                size = output.tell()
                output.seek(max(0, size - 4096))
                raw = " ".join(output.read().decode("utf-8", errors="replace").split())[-300:]
                failures.append(public_summary(raw, f"command[{index}] failed; details withheld"))
    after = _state_fingerprint(location, readiness_check)
    if before != after:
        failures.append("readiness paths changed while the check was running")
    if failures:
        readiness_check["last_failure"] = " | ".join(failures)[:500]
        readiness_check.pop("last_pass", None)
    else:
        readiness_check.pop("last_failure", None)
        readiness_check["last_pass"] = {
            "recorded_at": evidence_timestamp(),
            "contract_digest": _contract_digest(readiness_check),
            "state_fingerprint": after,
        }
    write_state_entries(location.manifest, location.manifest_data)
    if failures:
        raise ToolError(f"plan readiness check failed: {readiness_check['last_failure']}")
    return readiness_check
