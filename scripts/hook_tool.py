"""Thin Better Plan lifecycle Hook entrypoint."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.better_plan.hooks import runtime


if __name__ == "__main__":
    raise SystemExit(runtime.hook_main())
