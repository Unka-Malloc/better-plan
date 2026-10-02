"""Refresh prompt examples embedded in the offline workflow presentation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import List, Optional


ROOT = Path(__file__).resolve().parents[1]
DATA_PATTERN = re.compile(
    r'(<script id="prompt-data" type="application/json">)(.*?)(</script>)',
    re.DOTALL,
)
ROLE_NAMES = ("designer", "worker", "reviewer")


def _role_entry(root: Path, role: str) -> str:
    source = (root / "agents" / "codex" / (role + ".toml")).read_text(encoding="utf-8")
    match = re.search(r'developer_instructions\s*=\s*"""(.*?)"""', source, re.DOTALL)
    if match is None:
        raise ValueError("missing Codex developer instructions for %s" % role)
    return match.group(1).strip()


def _main_entry(root: Path) -> str:
    source = (root / "agents" / "kilo" / "better-plan.md").read_text(encoding="utf-8")
    match = re.match(r"\A---\s*\n.*?\n---\s*\n(.*)\Z", source, re.DOTALL)
    if match is None:
        raise ValueError("missing Kilo Main prompt body")
    return match.group(1).strip()


def _briefs(root: Path) -> dict[str, str]:
    source = (root / "references" / "main.md").read_text(encoding="utf-8")
    heading = re.search(r"^## Briefs\s*$", source, re.MULTILINE)
    if heading is None:
        raise ValueError("missing role brief examples in references/main.md")
    tail = source[heading.end() :]
    section = re.split(r"^##\s+", tail, maxsplit=1, flags=re.MULTILINE)[0]
    briefs = {
        role.lower(): value
        for role, value in re.findall(r'^- (Designer|Worker|Reviewer): "(.*)"$', section, re.MULTILINE)
    }
    if set(briefs) != set(ROLE_NAMES):
        raise ValueError("role brief examples in references/main.md are incomplete")
    return briefs


def build_prompt_data(root: Path = ROOT) -> dict[str, object]:
    """Read canonical skill and role sources for the presentation's existing data shape."""

    roles = {
        role: (root / "references" / (role + ".md")).read_text(encoding="utf-8")
        for role in ("main",) + ROLE_NAMES
    }
    return {
        "roles": roles,
        "shared": (root / "SKILL.md").read_text(encoding="utf-8"),
        "briefs": _briefs(root),
        "entries": {
            "main": _main_entry(root),
            **{role: _role_entry(root, role) for role in ROLE_NAMES},
        },
    }


def embedded_prompt_data(html: str) -> dict[str, object]:
    match = DATA_PATTERN.search(html)
    if match is None:
        raise ValueError("presentation is missing its prompt-data script")
    value = json.loads(match.group(2))
    if not isinstance(value, dict):
        raise ValueError("presentation prompt data must be a JSON object")
    return value


def render_presentation(html: str, root: Path = ROOT) -> str:
    match = DATA_PATTERN.search(html)
    if match is None:
        raise ValueError("presentation is missing its prompt-data script")
    payload = json.dumps(build_prompt_data(root), ensure_ascii=False, indent=2)
    return html[: match.start(2)] + "\n" + payload + "\n" + html[match.end(2) :]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report whether embedded prompts match the canonical sources without writing",
    )
    args = parser.parse_args(argv)
    path = ROOT / "docs" / "presentations" / "better-plan-workflow.html"
    original = path.read_text(encoding="utf-8")
    updated = render_presentation(original)
    if args.check:
        if original != updated:
            print("Workflow presentation prompt data is out of date.", file=sys.stderr)
            return 1
        print("Workflow presentation prompt data is current.")
        return 0
    if original != updated:
        path.write_text(updated, encoding="utf-8")
        print("Updated workflow presentation prompt data.")
    else:
        print("Workflow presentation prompt data is current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
