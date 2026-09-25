"""Structural execution shape of one compiled Better Plan Task.

These facts describe how much work a Task asks a single Worker session to carry:
how many Nodes it spans, how deep its critical path runs, how wide its parallel
frontier opens, and how many ownership, output, acceptance and verification
surfaces it touches. They are counts, not estimates, and they select nothing:
one Worker role handles every Task.
"""

from __future__ import annotations

from typing import Any, Mapping


def task_execution_shape(task: Mapping[str, Any]) -> dict[str, Any]:
    """Return small, judgment-free facts about one Task's execution shape."""

    nodes = task.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("Task requires a non-empty nodes array")

    by_code: dict[str, Mapping[str, Any]] = {}
    successors: dict[str, list[str]] = {}
    indegree: dict[str, int] = {}
    for node in nodes:
        if not isinstance(node, Mapping) or not isinstance(node.get("code"), str):
            raise ValueError("every Node requires a code")
        code = str(node["code"])
        if code in by_code:
            raise ValueError("Node codes must be unique")
        by_code[code] = node
        successors[code] = []
        indegree[code] = 0

    for code, node in by_code.items():
        prerequisites = node.get("prerequisites", [])
        if not isinstance(prerequisites, list):
            raise ValueError("Node prerequisites must be an array")
        for prerequisite in prerequisites:
            if prerequisite not in by_code:
                raise ValueError("Node prerequisite %s is not in this Task" % prerequisite)
            successors[str(prerequisite)].append(code)
            indegree[code] += 1

    ready = sorted(code for code, degree in indegree.items() if degree == 0)
    depth: dict[str, int] = {}
    processed = 0
    max_frontier = 0
    while ready:
        max_frontier = max(max_frontier, len(ready))
        next_ready: list[str] = []
        for code in ready:
            prerequisites = by_code[code].get("prerequisites", [])
            depth[code] = 1 + max((depth[str(item)] for item in prerequisites), default=0)
            processed += 1
            for successor in successors[code]:
                indegree[successor] -= 1
                if indegree[successor] == 0:
                    next_ready.append(successor)
        ready = sorted(next_ready)
    if processed != len(nodes):
        raise ValueError("Task Node graph contains a cycle")

    ownership = task.get("ownership") if isinstance(task.get("ownership"), Mapping) else {}
    regression = (
        task.get("focused_regression")
        if isinstance(task.get("focused_regression"), Mapping)
        else {}
    )
    return {
        "task": task.get("code"),
        "title": task.get("title"),
        "worker": task.get("worker", "code"),
        "workload": task.get("workload"),
        "node_count": len(nodes),
        "critical_path_nodes": max(depth.values()),
        "max_parallel_frontier": max_frontier,
        "write_path_count": len(ownership.get("write_paths", []) or []),
        "output_count": len(task.get("outputs", []) or []),
        "acceptance_count": len(task.get("acceptance", []) or []),
        "verification_command_count": len(regression.get("commands", []) or []),
    }
