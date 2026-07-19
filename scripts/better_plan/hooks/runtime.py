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
AGENT_TOOL_NAMES = frozenset({"agent", "spawnagent", "task"})


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


def handle_session_start(agent: str, payload: dict[str, Any]) -> dict[str, Any]:
    if is_subagent_lifecycle(payload):
        return {}
    if detected_manifest(payload) is None:
        return {}
    return protocols.context_response(agent, "session-start", context.session_context())


def handle_prompt_submit(agent: str, payload: dict[str, Any]) -> dict[str, Any]:
    if is_subagent_lifecycle(payload):
        return {}
    if detected_manifest(payload) is None:
        return {}
    if agent == "cursor":
        return protocols.prompt_allow_response(agent)
    return protocols.context_response(agent, "prompt-submit", context.prompt_context())


def handle_agent_complete(agent: str, payload: dict[str, Any]) -> dict[str, Any]:
    tool_name = payload.get("tool_name")
    if not nonempty_string(tool_name):
        return {}
    normalized_tool = str(tool_name).replace("_", "").replace("-", "").lower()
    if normalized_tool not in AGENT_TOOL_NAMES:
        return {}
    manifest = detected_manifest(payload)
    if manifest is None:
        return {}
    directive = reduce_agent_completion(manifest)
    if directive is None:
        return {}
    value = context.agent_completion_context(
        directive.node_id,
        directive.phase,
        directive.action,
    )
    return protocols.context_response(agent, "agent-complete", value)


def safe_handle_event(
    agent: str,
    event: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
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
    print(json.dumps(response, ensure_ascii=False))
    return 0
