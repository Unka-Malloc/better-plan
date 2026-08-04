"""Regression layer for Better Plan workflow state."""

from __future__ import annotations

from typing import Any
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import subprocess
import sys
import tempfile
import shlex
import shutil
from ..domain.design import canonical_design_bytes, normalize_design_path, validate_design_contract as _validate_design_contract
from ..domain.models import REGRESSION_COMMAND_TIMEOUT_SECONDS, REGRESSION_REQUIRED_FIELDS, ToolError, expected_regression_scope, is_string_list, normalize_workspace_path, public_summary
from ..domain.validation import validate_regression_contract
from .workspace import NodeLocation as _NodeLocation, locate_node, project_root_for, referenced_checkpoints_files, workspace_manifest_path, write_location_and_sync_plan


FINGERPRINT_CACHE_DIRECTORIES = frozenset(
    {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
)


def current_platform() -> str:
    if sys.platform == "darwin":
        return "macos"
    if sys.platform in {"win32", "cygwin"}:
        return "windows"
    if sys.platform.startswith("linux"):
        return "linux"
    return sys.platform


def platform_matches(declared: Any, actual: str | None = None) -> bool:
    return declared == "any" or declared == (actual or current_platform())


def validated_design_contract(location: _NodeLocation) -> dict[str, Any]:
    """Return one current design contract after pure and repository-bound checks."""
    node = location.checkpoints_data[location.node_index]
    design = node.get("design")
    if not isinstance(design, dict):
        raise ToolError(f"node {node.get('id')}: a valid design contract is required before acceptance preparation")
    issues = _validate_design_contract(design)
    if issues:
        raise ToolError(f"node {node.get('id')}: invalid design contract: {'; '.join(issues)}")

    project_root = project_root_for(location.manifest.parent).resolve()
    removal_paths = {
        normalize_design_path(str(symbol["path"]))
        for symbol in design["symbols"]
        if isinstance(symbol, dict)
        and symbol.get("operation") == "remove"
        and isinstance(symbol.get("path"), str)
    }
    declared = [
        normalize_design_path(str(design["artifact"])),
        *[normalize_design_path(str(value)) for value in design["owned_paths"]],
        *[normalize_design_path(str(value)) for value in design["scaffold_paths"]],
        *[normalize_design_path(str(value)) for value in design["acceptance_paths"]],
    ]
    for relative in sorted(set(declared)):
        candidate = project_root / relative
        if candidate.is_symlink():
            raise ToolError(f"design path {relative!r} is a symbolic link")
        if not candidate.exists() and relative in removal_paths:
            continue
        if not candidate.exists():
            raise ToolError(f"design path {relative!r} does not exist")
        try:
            candidate.resolve().relative_to(project_root)
        except (OSError, ValueError) as exc:
            raise ToolError(f"design path {relative!r} escapes the project root") from exc
    return design


def _artifact_fingerprint(project_root: Path, paths: list[str]) -> str:
    digest = hashlib.sha256()
    stack = [project_root / value for value in reversed(sorted(set(paths)))]
    while stack:
        entry = stack.pop()
        relative = entry.relative_to(project_root).as_posix()
        if entry.is_symlink():
            raise ToolError(f"design path {relative!r} contains a symbolic link")
        try:
            if entry.is_dir():
                digest.update(b"D\0" + relative.encode("utf-8") + b"\0")
                stack.extend(reversed(sorted(entry.iterdir(), key=lambda child: child.name)))
                continue
            if entry.is_file():
                digest.update(b"F\0" + relative.encode("utf-8") + b"\0")
                with entry.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1 << 20), b""):
                        digest.update(chunk)
                digest.update(b"\0")
                continue
        except OSError as exc:
            raise ToolError(f"design path {relative!r} could not be fingerprinted") from exc
        raise ToolError(f"design path {relative!r} is not a regular file or directory")
    return digest.hexdigest()


def preparation_fingerprints(location: _NodeLocation) -> dict[str, str]:
    """Bind the frozen design and acceptance artifacts without runtime metadata."""
    node = location.checkpoints_data[location.node_index]
    design = validated_design_contract(location)
    project_root = project_root_for(location.manifest.parent).resolve()
    requirements = node.get("requirements") if is_string_list(node.get("requirements")) else []
    canonical_requirements = json.dumps(sorted(requirements), separators=(",", ":")).encode("utf-8")
    artifact_digest = _artifact_fingerprint(project_root, [normalize_design_path(str(design["artifact"]))])
    design_hasher = hashlib.sha256()
    design_hasher.update(canonical_design_bytes(design))
    design_hasher.update(b"\0requirements\0")
    design_hasher.update(canonical_requirements)
    design_hasher.update(b"\0artifact\0")
    design_hasher.update(artifact_digest.encode("ascii"))
    current_design_digest = design_hasher.hexdigest()

    scaffold_paths = [normalize_design_path(str(value)) for value in design["scaffold_paths"]]
    acceptance_paths = [normalize_design_path(str(value)) for value in design["acceptance_paths"]]

    scaffold_hasher = hashlib.sha256()
    scaffold_hasher.update(current_design_digest.encode("ascii"))
    scaffold_hasher.update(b"\0scaffold\0")
    scaffold_hasher.update(_artifact_fingerprint(project_root, scaffold_paths).encode("ascii"))

    acceptance_hasher = hashlib.sha256()
    acceptance_hasher.update(current_design_digest.encode("ascii"))
    acceptance_hasher.update(b"\0acceptance\0")
    acceptance_hasher.update(_artifact_fingerprint(project_root, acceptance_paths).encode("ascii"))
    return {
        "design_digest": current_design_digest,
        "scaffold_fingerprint": scaffold_hasher.hexdigest(),
        "acceptance_fingerprint": acceptance_hasher.hexdigest(),
    }


def validated_regression_contract(location: _NodeLocation) -> dict[str, Any]:
    node = location.checkpoints_data[location.node_index]
    criteria = node.get("acceptance_criteria")
    criterion_count = len(criteria) if isinstance(criteria, list) else 0
    issues = validate_regression_contract(
        location.checkpoints_path,
        f"node[{location.node_index}]",
        node,
        criterion_count,
    )
    regression = node.get("regression")
    if not isinstance(regression, dict):
        role = node.get("role")
        scope = expected_regression_scope(role) or "declared"
        raise ToolError(f"node {node.get('id')}: a {scope} regression contract is required")
    if issues:
        details = "; ".join(issue.message for issue in issues)
        raise ToolError(f"node {node.get('id')}: invalid regression contract: {details}")
    return regression


def regression_contract_digest(regression: dict[str, Any]) -> str:
    fields = set(REGRESSION_REQUIRED_FIELDS)
    if "command_paths" in regression:
        fields.add("command_paths")
    contract = {field: regression[field] for field in sorted(fields)}
    encoded = json.dumps(contract, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def mutable_state_paths(location: _NodeLocation) -> set[Path]:
    paths = {location.manifest.resolve(), location.checkpoints_path.resolve()}
    paths.update(path.resolve() for path in referenced_checkpoints_files(location.manifest))
    return paths


def regression_content_fingerprint(location: _NodeLocation, regression: dict[str, Any]) -> str:
    project_root = project_root_for(location.manifest.parent).resolve()
    forbidden = mutable_state_paths(location)
    declared_paths = regression.get("paths")
    if not is_string_list(declared_paths) or not declared_paths:
        raise ToolError("regression paths must be a non-empty array")

    roots: list[Path] = []
    for value in declared_paths:
        normalized = normalize_workspace_path(value)
        candidate = project_root / normalized
        if candidate.is_symlink():
            raise ToolError(f"regression path {normalized!r} is a symbolic link; declare real repository content")
        if not candidate.exists():
            raise ToolError(f"regression path {normalized!r} does not exist")
        try:
            candidate.relative_to(project_root)
        except ValueError as exc:
            raise ToolError(f"regression path {normalized!r} escapes the project root") from exc
        roots.append(candidate)

    digest = hashlib.sha256()
    stack = list(reversed(sorted(roots, key=lambda entry: entry.relative_to(project_root).as_posix())))
    while stack:
        entry = stack.pop()
        relative = entry.relative_to(project_root).as_posix()
        if entry.is_symlink():
            raise ToolError(f"regression path {relative!r} contains a symbolic link; declare real repository content")
        if entry.resolve() in forbidden:
            raise ToolError(
                f"regression path {relative!r} includes mutable Better Plan state; declare source or test paths instead"
            )

        try:
            if entry.is_dir():
                digest.update(b"D\0")
                digest.update(relative.encode("utf-8"))
                digest.update(b"\0")
                children = sorted(
                    (
                        child
                        for child in entry.iterdir()
                        if child.name not in FINGERPRINT_CACHE_DIRECTORIES
                    ),
                    key=lambda child: child.name,
                )
                stack.extend(reversed(children))
                continue
            if entry.is_file():
                digest.update(b"F\0")
                digest.update(relative.encode("utf-8"))
                digest.update(b"\0")
                digest.update(str(entry.stat().st_size).encode("ascii"))
                digest.update(b"\0")
                with entry.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1 << 20), b""):
                        digest.update(chunk)
                digest.update(b"\0")
                continue
        except OSError as exc:
            raise ToolError(f"regression path {relative!r} could not be fingerprinted") from exc
        raise ToolError(f"regression path {relative!r} is not a regular file or directory")
    return digest.hexdigest()


def _command_input_fingerprint(
    location: _NodeLocation,
    regression: dict[str, Any],
    command_index: int,
) -> str:
    command_paths = regression.get("command_paths")
    paths = command_paths[command_index] if isinstance(command_paths, list) else regression["paths"]
    return regression_content_fingerprint(location, {**regression, "paths": paths})


def _safe_command_summary(handle: Any, fallback: str) -> str:
    handle.seek(0, 2)
    size = handle.tell()
    handle.seek(max(0, size - 8192))
    decoded = handle.read().decode("utf-8", errors="replace")
    lines = [" ".join(line.split()) for line in decoded.splitlines() if line.strip()]
    candidate = " | ".join(lines[-3:])[-400:]
    return public_summary(candidate, fallback)


def regression_receipt_status(location: _NodeLocation) -> tuple[bool, str]:
    try:
        regression = validated_regression_contract(location)
    except ToolError as exc:
        return False, str(exc)
    receipt = regression.get("last_pass")
    if not isinstance(receipt, dict):
        return False, "no passing regression receipt is recorded"
    if receipt.get("contract_digest") != regression_contract_digest(regression):
        return False, "the regression contract changed after its last passing run"
    try:
        fingerprint = regression_content_fingerprint(location, regression)
    except ToolError as exc:
        return False, str(exc)
    if receipt.get("content_fingerprint") != fingerprint:
        return False, "declared regression paths changed after their last passing run"
    return True, "passing regression receipt is current"


def preflight_regression_at_location(location: _NodeLocation, probes: list[str]) -> list[str]:
    """Reject broken command/path contracts before a delivery role starts."""

    regression = validated_regression_contract(location)
    regression_content_fingerprint(location, regression)
    shell_builtins = {".", ":", "alias", "cd", "command", "eval", "exec", "export", "set", "test", "unset"}
    messages: list[str] = []
    for index, command in enumerate(regression["commands"]):
        try:
            tokens = shlex.split(command, posix=True)
        except ValueError as exc:
            raise ToolError(f"regression command[{index}] has invalid shell syntax") from exc
        executable = next((token for token in tokens if "=" not in token or token.startswith(("/", "./"))), "")
        if not executable:
            raise ToolError(f"regression command[{index}] has no executable")
        if executable not in shell_builtins and "/" not in executable and shutil.which(executable) is None:
            raise ToolError(f"regression command[{index}] executable is unavailable")
        messages.append(f"OK: regression command[{index}] executable and declared paths are available")
    root = project_root_for(location.manifest.parent)
    for index, probe in enumerate(probes):
        result = subprocess.run(probe, cwd=root, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        if result.returncode != 0:
            raise ToolError(f"regression preflight probe[{index}] exited with {result.returncode}")
        messages.append(f"OK: regression preflight probe[{index}] passed")
    return messages


def run_regression_at_location(location: _NodeLocation, *, persist: bool = True) -> list[str]:
    node = location.checkpoints_data[location.node_index]
    node_id = str(node.get("id"))
    if node.get("status") != "in_progress":
        raise ToolError(f"node {node_id}: regression requires an 'in_progress' node")
    actual_platform = current_platform()
    if not platform_matches(node.get("platform"), actual_platform):
        raise ToolError(
            f"node {node_id}: platform {node.get('platform')!r} does not match current runtime {actual_platform!r}"
        )

    regression = validated_regression_contract(location)
    project_root = project_root_for(location.manifest.parent)
    before = regression_content_fingerprint(location, regression)
    commands = list(regression["commands"])
    prior_receipts = {
        (receipt.get("command_sha256"), receipt.get("input_fingerprint")): receipt
        for receipt in regression.get("command_receipts", [])
        if isinstance(receipt, dict)
    }
    passing_receipts: list[dict[str, str]] = []
    failures: list[dict[str, Any]] = []
    for index, command in enumerate(commands):
        command_sha = hashlib.sha256(command.strip().encode("utf-8")).hexdigest()
        input_fingerprint = _command_input_fingerprint(location, regression, index)
        prior = prior_receipts.get((command_sha, input_fingerprint))
        if prior is not None:
            passing_receipts.append(dict(prior))
            continue
        recorded_at = evidence_timestamp()
        with tempfile.TemporaryFile() as output:
            failure: dict[str, Any] | None = None
            try:
                result = subprocess.run(
                    command,
                    cwd=project_root,
                    shell=True,
                    check=False,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    timeout=REGRESSION_COMMAND_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired:
                failure = {
                    "command_index": index,
                    "kind": "timeout",
                    "summary": _safe_command_summary(output, "command timed out; details withheld"),
                }
            except OSError:
                failure = {
                    "command_index": index,
                    "kind": "unavailable",
                    "summary": "command could not be started; details withheld",
                }
            else:
                if result.returncode != 0:
                    failure = {
                        "command_index": index,
                        "kind": "exit",
                        "summary": _safe_command_summary(output, f"command exited with {result.returncode}; details withheld"),
                    }
            if failure is not None:
                failures.append(failure)
                continue
        passing_receipts.append(
            {
                "command_sha256": command_sha,
                "input_fingerprint": input_fingerprint,
                "recorded_at": recorded_at,
            }
        )

    after = regression_content_fingerprint(location, regression)
    if before != after:
        passing_receipts = []
        failures.append(
            {
                "command_index": len(commands),
                "kind": "exit",
                "summary": "declared regression paths changed while commands were running",
            }
        )
    regression["command_receipts"] = passing_receipts
    if failures:
        regression["last_failure"] = failures
        details = "; ".join(
            f"command[{failure['command_index']}] {failure['kind']}: {failure['summary']}"
            for failure in failures
        )
        raise ToolError(f"node {node_id}: regression commands failed: {details}")
    regression.pop("last_failure", None)

    recorded_at = evidence_timestamp()
    command_digests = {
        hashlib.sha256(command.strip().encode("utf-8")).hexdigest()
        for command in commands
    }
    command_refs = [
        {
            "type": "command",
            "command_sha256": hashlib.sha256(command.strip().encode("utf-8")).hexdigest(),
            "exit_code": 0,
            "recorded_at": recorded_at,
        }
        for command in commands
    ]
    criteria = node["acceptance_criteria"]
    for criterion_index in regression["criteria"]:
        criterion = criteria[criterion_index]
        existing = criterion.get("evidence_refs")
        preserved = [
            ref
            for ref in existing
            if isinstance(ref, dict)
            and not (ref.get("type") == "command" and ref.get("command_sha256") in command_digests)
        ] if isinstance(existing, list) else []
        criterion["evidence_refs"] = preserved + [dict(ref) for ref in command_refs]
        criterion["checked"] = True

    regression["last_pass"] = {
        "recorded_at": recorded_at,
        "contract_digest": regression_contract_digest(regression),
        "content_fingerprint": after,
    }
    messages = [
        f"OK: node {node_id} {regression['scope']} regression passed ({len(commands)} command(s)); command output discarded"
    ]
    if persist:
        messages.extend(write_location_and_sync_plan(location))
    return messages


def run_node_regression(root: str | Path, node_id: str, *, force: bool = True) -> list[str]:
    manifest = workspace_manifest_path(Path(root))
    location = locate_node(manifest, node_id)
    node = location.checkpoints_data[location.node_index]
    regression = validated_regression_contract(location)
    may_reuse = (
        node.get("status") == "in_progress"
        and platform_matches(node.get("platform"))
        and (not force or regression.get("scope") == "full")
    )
    if may_reuse:
        fresh, _ = regression_receipt_status(location)
        if fresh:
            return [f"OK: node {node_id} already has a current passing regression receipt"]
    return run_regression_at_location(location)


def ensure_node_regression(root: str | Path, node_id: str) -> list[str]:
    manifest = workspace_manifest_path(Path(root))
    location = locate_node(manifest, node_id)
    node = location.checkpoints_data[location.node_index]
    if expected_regression_scope(node.get("role")) is None:
        return []
    fresh, reason = regression_receipt_status(location)
    if fresh:
        return [f"OK: node {node_id} already has a current passing regression receipt"]
    if node.get("role") == "final_validation":
        raise ToolError(
            f"node {node_id}: final_validation complete requires a current passing full regression receipt "
            f"from explicit regress; {reason}"
        )
    return run_regression_at_location(location)


def evidence_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
