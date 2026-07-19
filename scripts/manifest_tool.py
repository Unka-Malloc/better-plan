"""Thin Better Plan manifest tool entrypoint."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.better_plan.adapters import manifest_cli


if __name__ == "__main__":
    raise SystemExit(manifest_cli.main())
