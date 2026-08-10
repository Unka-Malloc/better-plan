"""Readable v3 Plan and execution projections."""

from __future__ import annotations

from typing import Any, Mapping


def render_plan_tree(
    plan: Mapping[str, Any],
    checkpoints: Mapping[str, Any] | None = None,
    details: bool = False,
) -> str:
    states = {
        item.get("code"): item
        for item in (checkpoints or {}).get("tasks", [])
        if isinstance(item, Mapping)
    }
    lines = ["%s %s [%s]" % (plan.get("code"), plan.get("title"), plan.get("phase"))]
    tasks = plan.get("spec", {}).get("tasks", [])
    for index, task in enumerate(tasks):
        marker = "└─" if index == len(tasks) - 1 else "├─"
        state = states.get(task.get("code"), {})
        status = state.get("status", "planned")
        dispatch = state.get("dispatch")
        if isinstance(dispatch, Mapping) and dispatch.get("phase"):
            status = "%s/%s" % (status, dispatch.get("phase"))
        line = "  %s %s %s [%s]" % (marker, task.get("code"), task.get("title"), status)
        if details:
            line += " tier=%s verification=%s frontier=parallel" % (
                task.get("difficulty"),
                task.get("verification"),
            )
        lines.append(line)
        if details:
            nodes = task.get("nodes") if isinstance(task.get("nodes"), list) else []
            for node_index, node in enumerate(nodes):
                node_marker = "└─" if node_index == len(nodes) - 1 else "├─"
                prerequisites = ",".join(node.get("prerequisites", []) or ["none"])
                lines.append(
                    "      %s %s %s after=%s"
                    % (node_marker, node.get("code"), node.get("title"), prerequisites)
                )
    return "\n".join(lines)


def status_payload(plan: Mapping[str, Any], checkpoints: Mapping[str, Any] | None = None) -> dict[str, Any]:
    lifecycle = plan.get("lifecycle", {}) if isinstance(plan.get("lifecycle"), Mapping) else {}
    sealed = lifecycle.get("sealed")
    counts: dict[str, int] = {}
    for item in (checkpoints or {}).get("tasks", []):
        status = str(item.get("status"))
        counts[status] = counts.get(status, 0) + 1
    return {
        "code": plan.get("code"),
        "phase": plan.get("phase"),
        "revision": sealed.get("revision") if isinstance(sealed, Mapping) else None,
        "designer_session": _session_status(lifecycle.get("designer_session")),
        "reviewer_session": _session_status(lifecycle.get("reviewer_session")),
        "task_counts": counts,
        "delivery_status": (checkpoints or {}).get("delivery_status"),
    }


def _session_status(session: Any) -> str | None:
    return session.get("status") if isinstance(session, Mapping) else None
