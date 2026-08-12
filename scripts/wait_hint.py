"""Combine agent-supplied progress and prior durations into one wait hint."""

from __future__ import annotations

from statistics import median
from typing import Any
import argparse
import json
import sys


_WORKLOAD_MULTIPLIER = {"light": 0.75, "medium": 1.0, "heavy": 1.5}


def wait_hint(
    *,
    workload: str,
    elapsed: float,
    progress: float,
    prior_total: float | None = None,
    history: list[float] | None = None,
) -> dict[str, Any]:
    """Return an estimate; the caller remains responsible for the judgment inputs."""

    if workload not in _WORKLOAD_MULTIPLIER:
        raise ValueError("workload must be light, medium, or heavy")
    if elapsed < 0:
        raise ValueError("elapsed must be non-negative")
    if not 0 <= progress <= 100:
        raise ValueError("progress must be between 0 and 100")
    if prior_total is not None and prior_total <= 0:
        raise ValueError("prior-total must be positive")
    history = history or []
    if any(value <= 0 for value in history):
        raise ValueError("history durations must be positive")

    sources: dict[str, float] = {}
    if 0 < progress < 100:
        sources["progress_projection"] = elapsed / (progress / 100.0)
    elif progress == 100:
        sources["progress_projection"] = elapsed
    if prior_total is not None:
        sources["prior_total"] = prior_total
    if history:
        sources["history_median"] = float(median(history))
    if not sources:
        raise ValueError("provide progress above zero, prior-total, or at least one history duration")

    estimated_total = max(elapsed, float(median(sources.values())))
    remaining = 0.0 if progress == 100 else max(0.0, estimated_total - elapsed)
    if progress < 25:
        remaining_fraction = 0.30
    elif progress < 75:
        remaining_fraction = 0.20
    else:
        remaining_fraction = 0.10
    suggested = min(
        remaining,
        remaining * remaining_fraction * _WORKLOAD_MULTIPLIER[workload],
    )
    if remaining > 0:
        suggested = max(1.0, suggested)

    return {
        "workload": workload,
        "progress_percent": progress,
        "estimated_total_seconds": round(estimated_total),
        "estimated_remaining_seconds": round(remaining),
        "suggested_next_check_seconds": round(suggested),
        "estimate_sources_seconds": {key: round(value) for key, value in sources.items()},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Suggest the next Worker observation window")
    parser.add_argument("--workload", required=True, choices=tuple(_WORKLOAD_MULTIPLIER))
    parser.add_argument("--elapsed", required=True, type=float, help="elapsed seconds")
    parser.add_argument("--progress", required=True, type=float, help="agent-estimated percent complete")
    parser.add_argument("--prior-total", type=float, help="optional prior total-duration estimate")
    parser.add_argument("--history", type=float, action="append", default=[], help="comparable completed duration; repeatable")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(wait_hint(
            workload=args.workload,
            elapsed=args.elapsed,
            progress=args.progress,
            prior_total=args.prior_total,
            history=args.history,
        ), indent=2, sort_keys=True))
        return 0
    except ValueError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
