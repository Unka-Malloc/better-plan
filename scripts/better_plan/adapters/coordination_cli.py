"""Operator commands and interruptible observation for multi-plan coordination."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from typing import Any, Callable

from ..domain.models import ToolError
from .coordination_portfolio import require, within


def _stamp(path: Path) -> tuple[int, int] | None:
    try:
        value = path.stat()
        return value.st_mtime_ns, value.st_size
    except FileNotFoundError:
        return None


def watch(coordinator: Any, state_path: Path, interval: float,
          emit: Callable[[dict], None], *, sleep: Callable[[float], None] = time.sleep,
          clock: Callable[[], float] = time.monotonic) -> None:
    """Reconcile periodically or when a local owner emits a wake notification.

    The interval is an observation cadence, never an execution deadline. A
    stopped observer leaves existing host work and native ownership intact.
    """
    wake = state_path.with_suffix(state_path.suffix + ".wake")
    last = None
    try:
        while True:
            # Observe the marker before tick, so a notification received while
            # acceptance runs remains visible and immediately triggers a tick.
            observed = _stamp(wake)
            result = coordinator.tick()
            encoded = json.dumps(result, ensure_ascii=False, sort_keys=True)
            if encoded != last:
                emit(result)
                last = encoded
            deadline = clock() + interval
            while _stamp(wake) == observed and clock() < deadline:
                sleep(min(1.0, max(0.0, deadline - clock())))
    except KeyboardInterrupt:
        emit({"observer": "stopped", "running_work": "preserved"})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Coordinate source-owned plans; inspect before enabling execution")
    parser.add_argument("command", choices=("status", "grant", "revoke", "reconcile", "pause", "resume", "tick", "watch", "wake"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--state", required=True, type=Path, help="private, untracked dispatch journal")
    parser.add_argument("--unit", action="append", default=[], help="exact source/Task key; repeatable")
    parser.add_argument("--lane", action="append", default=[], help="explicitly select every unit in this lane")
    parser.add_argument("--reference", help="privacy-safe reference to the existing execution authorization")
    parser.add_argument("--interval", type=float, default=60.0, help="watch reconciliation cadence in seconds")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    def emit(value: dict) -> None:
        print(json.dumps(value, ensure_ascii=False, indent=2), flush=True)

    try:
        from ..domain.coordination import validate_config
        from ..application.coordinator import Coordinator
        from .coordination_sources import NativeSources

        root = args.root.resolve()
        config_path = args.config if args.config.is_absolute() else root / args.config
        config = validate_config(json.loads(config_path.read_text(encoding="utf-8")))
        state_path = (args.state if args.state.is_absolute() else root / args.state).resolve()
        require(args.interval >= 1 and args.interval < float("inf"), "watch interval must be finite and at least one second")
        sources = NativeSources(root, within(root, config["portfolio"]), config["lanes"])
        host = None
        if config.get("host"):
            from .coordination_host import CommandHost
            settings = config["host"]
            host = CommandHost(root, settings["command"], settings["profiles"])
        coordinator = Coordinator(config, root, state_path, sources, host)
        if args.command == "wake":
            # A wake carries no task state or authority. The coordinator always
            # rereads source facts and stored grants before doing any work.
            require(state_path.is_file(), "wake requires an existing coordinator journal")
            wake = state_path.with_suffix(state_path.suffix + ".wake")
            require(not wake.is_symlink(), "wake marker must not be a symlink")
            with wake.open("a", encoding="utf-8"):
                pass
            wake.chmod(0o600)
            wake.touch()
            emit({"notified": True})
            return 0
        if args.command in {"grant", "revoke", "reconcile"}:
            units = sources.snapshot()
            lane_sources = {lane["id"]: lane["source"] for lane in config["lanes"]}
            require(all(lane in lane_sources for lane in args.lane), "unknown lane selector")
            selected = list(dict.fromkeys(args.unit + [key for key, unit in units.items()
                            if unit["source"] in {lane_sources[lane] for lane in args.lane}]))
            require(bool(selected) and all(key in units for key in selected), "select existing execution units or lanes")
            if args.command == "grant":
                require(bool(args.reference), "grant requires a reference to existing user authorization")
                result = coordinator.grant(selected, args.reference)
            else:
                result = getattr(coordinator, args.command)(selected)
        elif args.command == "watch":
            watch(coordinator, state_path, args.interval, emit)
            return 0
        elif args.command == "tick":
            result = coordinator.tick()
        else:
            result = getattr(coordinator, args.command)()
        emit(result)
        return 0
    except ToolError as error:
        emit({"error": str(error)})
        return 1
    except (OSError, ValueError, TypeError, KeyError):
        emit({"error": "invalid coordination configuration or unavailable local resource"})
        return 1
