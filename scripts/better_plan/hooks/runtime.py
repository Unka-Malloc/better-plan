"""Translate supported agent lifecycle events into read-only workflow guidance."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from ..application.agent_completion import reduce_agent_completion
from . import protocols
from . import context, scope


EVENTS = ("session-start", "prompt-submit", "agent-complete")
MANAGED_BY = "better-plan"
SUBAGENT_EVENTS = {"subagentstart", "subagentstop"}
AGENT_TOOL_NAMES = frozenset({"agent", "task"})


def nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_subagent_lifecycle(payload: dict[str, Any]) -> bool:
    event_name = payload.get("hook_event_name")
    if (
        nonempty_string(event_name)
        and str(event_name).replace("_", "").replace("-", "").lower()
        in SUBAGENT_EVENTS
    ):
        return True
    if payload.get("is_subagent") is True:
        return True
    return nonempty_string(payload.get("agent_id")) and nonempty_string(
        payload.get("agent_type")
    )


def detected_manifest(payload: dict[str, Any]) -> Path | None:
    return scope.detect_event_workspace(payload)


def handle_session_start(agent: str, payload: dict[str, Any]) -> dict[str, Any] | str:
    if is_subagent_lifecycle(payload):
        return {}
    if agent == "antigravity" and payload.get("invocationNum") != 0:
        return {}
    if detected_manifest(payload) is None:
        return {}
    return protocols.context_response(agent, "session-start", context.session_context())


def handle_prompt_submit(agent: str, payload: dict[str, Any]) -> dict[str, Any] | str:
    if is_subagent_lifecycle(payload):
        return {}
    if detected_manifest(payload) is None:
        return {}
    if agent == "cursor":
        return protocols.prompt_allow_response(agent)
    return protocols.context_response(agent, "prompt-submit", context.prompt_context())


def is_subagent_stop(payload: dict[str, Any]) -> bool:
    """Return True only for an unambiguous subagent-stop lifecycle signal."""
    event_name = payload.get("hook_event_name")
    if nonempty_string(event_name):
        normalized = str(event_name).replace("_", "").replace("-", "").lower()
        if normalized in {"subagentstop"}:
            return True
        if normalized in {"subagentstart"}:
            return False
    # Claude PostToolUse:Agent payloads can include child identity metadata,
    # but they do not prove that the child has stopped.  Only the explicit
    # SubagentStop protocol event is a final signal.
    return False


def handle_agent_complete(agent: str, payload: dict[str, Any]) -> dict[str, Any] | str:
    if agent == "claude":
        # Claude Code's PostToolUse:Agent hook fires for every Agent tool use,
        # including asynchronous launches, and cannot distinguish a completed
        # leaf from one still running. Only an unambiguous subagent-stop
        # signal may advance the lifecycle.
        if not is_subagent_stop(payload):
            return {}
    else:
        tool_name = payload.get("agent_name") if agent == "kimi" else payload.get("tool_name")
        if not nonempty_string(tool_name):
            return {}
        normalized_tool = str(tool_name).replace("_", "").replace("-", "").lower()
        if agent != "kimi" and normalized_tool not in AGENT_TOOL_NAMES:
            return {}
    manifest = detected_manifest(payload)
    if manifest is None:
        return {}
    agent_id = payload.get("agent_id")
    final = payload.get("final")
    if not nonempty_string(agent_id) or type(final) is not bool or final is not True:
        return {}
    # Native hosts are not consistent about exposing the Better Plan Node.
    # When present, carry it through as a hard correlation constraint; when
    # absent, the reducer finds one uniquely bound active dispatch by child ID.
    expected_node_id = payload.get("node_id") if "node_id" in payload else None
    expected_dispatch_id = payload.get("dispatch_id") if "dispatch_id" in payload else None
    if "node_id" in payload and not nonempty_string(expected_node_id):
        return {}
    if "dispatch_id" in payload and not nonempty_string(expected_dispatch_id):
        return {}
    directive = reduce_agent_completion(
        manifest,
        agent_id=str(agent_id),
        final=final,
        node_id=str(expected_node_id) if expected_node_id is not None else None,
        dispatch_id=str(expected_dispatch_id) if expected_dispatch_id is not None else None,
    )
    if directive is None:
        return {}
    value = context.agent_completion_context(
        directive.node_id,
        directive.phase,
        directive.action,
    )
    return protocols.context_response(
        agent, "agent-complete", value, host_event_name=payload.get("hook_event_name")
    )


def safe_handle_event(
    agent: str,
    event: str,
    payload: dict[str, Any],
) -> dict[str, Any] | str:
    """Translate one lifecycle event, reducing all boundary failures to a safe no-op."""
    try:
        if event == "session-start":
            return handle_session_start(agent, payload)
        if event == "prompt-submit":
            return handle_prompt_submit(agent, payload)
        if event == "agent-complete":
            return handle_agent_complete(agent, payload)
        return {}
    except Exception:
        return {}


def read_payload() -> dict[str, Any]:
    try:
        value = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError, UnicodeError):
        return {}
    return value if isinstance(value, dict) else {}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Better Plan lifecycle Hook adapter")
    parser.add_argument("--agent", required=True, choices=protocols.AGENTS, help="host agent protocol")
    parser.add_argument("--event", required=True, choices=EVENTS, help="normalized lifecycle event")
    parser.add_argument("--managed-by", default=MANAGED_BY, help=argparse.SUPPRESS)
    return parser


def hook_main() -> int:
    args = build_parser().parse_args()
    if args.managed_by != MANAGED_BY:
        print("{}")
        return 0
    payload = read_payload()
    response = safe_handle_event(args.agent, args.event, payload)
    if isinstance(response, str):
        print(response)
    elif args.agent != "kimi" or response:
        print(json.dumps(response, ensure_ascii=False))
    return 0
