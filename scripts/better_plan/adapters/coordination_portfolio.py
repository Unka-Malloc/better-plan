"""Read explicit coordination sources without importing presentation adapters."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib
import json
import re
import sqlite3

from ..domain.models import (
    ABSOLUTE_PATH_PATTERN, NETWORK_ENDPOINT_PATTERN, SENSITIVE_TOKEN_PATTERN,
    ToolError, is_relative_workspace_path,
)

PORTFOLIO_SCHEMA = "better-plan.coordination-portfolio/v1"
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def require(condition: Any, message: str) -> None:
    if not condition:
        raise ToolError(message)


def safe_text(value: str, field: str) -> str:
    # Check what is actually exported, never dump rejected source text in errors.
    for pattern, reason in ((ABSOLUTE_PATH_PATTERN, "absolute local path"),
                            (NETWORK_ENDPOINT_PATTERN, "runtime endpoint"),
                            (SENSITIVE_TOKEN_PATTERN, "secret-shaped text")):
        require(not pattern.search(value), "%s contains %s" % (field, reason))
    return value


def within(root: Path, relative: str) -> Path:
    require(is_relative_workspace_path(relative), "source paths must be workspace-relative")
    result = (root / relative).resolve()
    require(root.resolve() in result.parents, "source path escapes workspace")
    require(result.is_file(), "a declared source file is missing")
    return result


def read(root: Path, relative: str) -> dict[str, Any]:
    try:
        value = json.loads(within(root, relative).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ToolError("cannot read declared JSON source") from None
    require(isinstance(value, dict), "source must be a JSON object")
    return value


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def _graph_states(root: Path, source: dict[str, Any], project_path: Path,
                  graph: dict[str, Any], architecture: dict[str, Any], distribution: Any) -> dict[str, dict]:
    if not source.get("state"):
        return {t["id"]: {"status": t.get("initial_status", "pending")} for t in graph["tasks"]}
    # The producer's resolved work-items bind SQLite fingerprints to this exact
    # graph. Reuse those receipts instead of reimplementing its task compiler.
    relative = (project_path.parent / "generated/work-items.json").relative_to(root.resolve()).as_posix()
    artifact = read(root, relative)
    require(artifact.get("kind") == "development-work-items-not-native-workflow" and
            artifact.get("schema_version") == 1, "unsupported execution graph work-items")
    require(artifact.get("graph_digest") == _digest({"architecture": architecture,
            "execution": graph, "distribution": distribution}), "generated execution graph is stale")
    fingerprints = {t["id"]: t["fingerprints"]["task_fingerprint"] for t in artifact["items"]}
    try:
        conn = sqlite3.connect(within(root, source["state"]).as_uri() + "?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            states = {row["id"]: dict(row) for row in conn.execute(
                "SELECT id,status,fingerprint,lease_until,write_scopes,resources FROM tasks")}
        finally:
            conn.close()
    except sqlite3.Error:
        raise ToolError("cannot read execution graph ledger") from None
    require(set(states) == {t["id"] for t in graph["tasks"]} == set(fingerprints),
            "execution ledger task set differs from graph")
    require(all(s["fingerprint"] == fingerprints[key] for key, s in states.items()),
            "execution ledger fingerprints are stale")
    return states
