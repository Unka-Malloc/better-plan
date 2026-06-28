#!/usr/bin/env python3
"""Update Better Plan installs for local coding agents."""

from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from install import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main(["update", *sys.argv[1:]]))
