"""Summarize structural workload facts from a compiled Better Plan Task."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any
import argparse
import json
import sys


def analyze_task(task: Mapping[str, Any]) -> dict[str, Any]:
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
        "difficulty": task.get("difficulty"),
        "workload": task.get("workload"),
        "node_count": len(nodes),
        "critical_path_nodes": max(depth.values()),
        "max_parallel_frontier": max_frontier,
        "write_path_count": len(ownership.get("write_paths", []) or []),
        "output_count": len(task.get("outputs", []) or []),
        "acceptance_count": len(task.get("acceptance", []) or []),
        "verification_command_count": len(regression.get("commands", []) or []),
    }


def _tasks(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, Mapping) and isinstance(payload.get("spec"), Mapping):
        values = payload["spec"].get("tasks")
    elif isinstance(payload, Mapping) and isinstance(payload.get("tasks"), list):
        values = payload.get("tasks")
    elif isinstance(payload, Mapping) and isinstance(payload.get("nodes"), list):
        values = [payload]
    else:
        values = None
    if not isinstance(values, list) or any(not isinstance(item, Mapping) for item in values):
        raise ValueError("input must be a compiled Plan, task collection, or Task JSON object")
    return values


def _read(path: str) -> Any:
    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    return json.loads(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize compiled Task structure")
    parser.add_argument("input", help="Plan or Task JSON path; use - for stdin")
    parser.add_argument("--task", help="optional Task code or title")
    args = parser.parse_args(argv)
    try:
        tasks = _tasks(_read(args.input))
        if args.task:
            tasks = [
                task
                for task in tasks
                if args.task in {task.get("code"), task.get("title")}
            ]
            if len(tasks) != 1:
                raise ValueError("--task must select exactly one Task")
        print(json.dumps({"tasks": [analyze_task(task) for task in tasks]}, indent=2, sort_keys=True))
        return 0
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
