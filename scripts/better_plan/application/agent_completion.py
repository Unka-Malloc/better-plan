"""Exact host callback reduction for v3 sessions and Task dispatches."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
import time

from ..infrastructure.workspace import (
    load_manifest,
    plan_paths,
    read_json,
    workspace_lock,
    workspace_root,
    write_json,
)


@dataclass(frozen=True)
class CompletionDirective:
    target: str
    phase: str
    action: str


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def reduce_agent_completion(
    manifest_path: Path,
    *,
    agent_id: str,
    final: bool,
    target_id: str | None = None,
    dispatch_id: str | None = None,
) -> CompletionDirective | None:
    """Advance exactly one bound dispatch, or nothing at all.

    Spawn return is not completion, and an ambiguous match never advances state.
    """

    if final is not True:
        return None
    root = workspace_root(manifest_path)
    with workspace_lock(root):
        manifest = load_manifest(root)
        matches: list[tuple[str, dict[str, Any], Path, str, dict[str, Any] | None]] = []
        for entry in manifest.get("plans", []):
            paths = plan_paths(root, entry)
            plan = read_json(paths["plan"])
            for name, action in (
                ("designer_session", "close_designer_session"),
                ("reviewer_session", "record_reviewer_findings"),
            ):
                session = plan.get("lifecycle", {}).get(name)
                if (
                    isinstance(session, Mapping)
                    and session.get("status") == "active"
                    and session.get("agent_returned") is not True
                    and session.get("host_agent_id") == agent_id
                    and (dispatch_id is None or session.get("id") == dispatch_id)
                    and (target_id is None or plan.get("code") == target_id)
                ):
                    matches.append((str(plan.get("code")), plan, paths["plan"], action, None))
            if not paths["checkpoints"].is_file():
                continue
            checkpoints = read_json(paths["checkpoints"])
            for state in checkpoints.get("tasks", []):
                dispatch = state.get("dispatch")
                if (
                    isinstance(dispatch, Mapping)
                    and dispatch.get("phase") == "worker_running"
                    and dispatch.get("host_agent_id") == agent_id
                    and (dispatch_id is None or dispatch.get("id") == dispatch_id)
                    and (target_id is None or state.get("code") == target_id)
                ):
                    matches.append(
                        (str(state.get("code")), checkpoints, paths["checkpoints"], "accept_task", state)
                    )
        if len(matches) != 1:
            return None
        target, document, path, action, state = matches[0]
        if state is None:
            name = "designer_session" if action == "close_designer_session" else "reviewer_session"
            session = document["lifecycle"][name]
            session["agent_returned"] = True
            session["agent_returned_at"] = _now()
            if name == "reviewer_session":
                session["findings_recorded"] = False
                session.pop("findings_recorded_at", None)
            write_json(path, document)
            return CompletionDirective(target, "agent_returned", action)
        dispatch = state["dispatch"]
        dispatch["phase"] = "awaiting_acceptance"
        dispatch["agent_returned_at"] = _now()
        write_json(path, document)
        return CompletionDirective(target, dispatch["phase"], action)
