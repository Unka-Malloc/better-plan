"""Read local native role names without changing host configuration.

The installer needs one fact only: which role names the local Codex configuration
already declares. A role is identified by its TOML ``name``, never by its filename,
so a renamed file still counts as the same role and an unrelated file never does.
Nothing here selects, recommends, or rewrites a model or an effort.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.8–3.10.
    from .._vendor import tomli as tomllib


MAX_ROLE_FILE_BYTES = 262_144


def _role_documents(directory: Path) -> Iterator[tuple[Path, dict[str, Any] | None]]:
    if not directory.is_dir():
        return
    for path in sorted(directory.glob("*.toml")):
        try:
            if not path.is_file() or path.stat().st_size > MAX_ROLE_FILE_BYTES:
                yield path, None
                continue
            yield path, tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            yield path, None


def configured_codex_role_names(codex_home: Path) -> frozenset[str]:
    """Identify personal roles by TOML name, independent of their filenames."""

    return frozenset(
        value["name"]
        for _, value in _role_documents(codex_home / "agents")
        if value is not None and isinstance(value.get("name"), str)
    )
