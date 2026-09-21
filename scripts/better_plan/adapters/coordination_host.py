"""Host-neutral JSON command transport for durable asynchronous execution."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from typing import Any, Mapping

from ..domain.models import OPAQUE_EVENT_ID_PATTERN, ToolError, is_relative_workspace_path
from .coordination_portfolio import require


HOST_REQUEST_SCHEMA = "better-plan.coordination-host/v1"
HOST_STATES = frozenset({"pending", "running", "succeeded", "failed", "unknown"})


class CommandHost:
    """Invoke a configured adapter without coupling coordination to its scheduler.

    The adapter must durably deduplicate start requests by operation_id and return
    the same opaque host_id after restart. Start submits asynchronous work; neither
    an adapter invocation nor the worker is given an execution deadline here.
    """

    def __init__(self, root: Path, command: list[str], profiles: Mapping[str, str]):
        self.root = root.resolve()
        self.command = list(command)
        self.profiles = dict(profiles)

    def _call(self, action: str, **payload: Any) -> dict[str, Any]:
        request = {"schema": HOST_REQUEST_SCHEMA, "action": action, **payload}
        try:
            result = subprocess.run(
                self.command,
                cwd=str(self.root),
                input=json.dumps(request, ensure_ascii=False),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        except OSError:
            raise ToolError("execution host command is unavailable") from None
        # Never expose the host's stdout/stderr, exceptions, or runtime metadata.
        require(result.returncode == 0, "execution host command failed")
        try:
            value = json.loads(result.stdout)
        except ValueError:
            raise ToolError("execution host returned an invalid response") from None
        require(isinstance(value, dict), "execution host response must be an object")
        return value

    def start(self, operation_id: str, key: str, brief: Mapping[str, Any], repository: str) -> str:
        require(OPAQUE_EVENT_ID_PATTERN.fullmatch(operation_id or "") is not None,
                "operation id must be an opaque identifier")
        require(is_relative_workspace_path(repository), "repository must be workspace-relative")
        role = brief.get("agent_type")
        require(role in self.profiles, "execution role has no configured profile")
        value = self._call(
            "start", operation_id=operation_id, key=key, brief=dict(brief),
            repository=repository, profile=self.profiles[role],
        )
        host_id = value.get("host_id")
        require(isinstance(host_id, str) and OPAQUE_EVENT_ID_PATTERN.fullmatch(host_id) is not None,
                "execution host returned an invalid identity")
        return host_id

    def inspect(self, host_id: str) -> dict[str, Any]:
        require(OPAQUE_EVENT_ID_PATTERN.fullmatch(host_id or "") is not None,
                "host id must be an opaque identifier")
        value = self._call("inspect", host_id=host_id)
        require(isinstance(value.get("state"), str) and value["state"] in HOST_STATES,
                "execution host returned an invalid state")
        state = {"state": value["state"]}
        if value.get("evidence") is not None:
            require(is_relative_workspace_path(value["evidence"]),
                    "execution evidence must be repository-relative")
            state["evidence"] = value["evidence"]
        return state
