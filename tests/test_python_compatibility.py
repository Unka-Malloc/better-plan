"""Frozen acceptance contract for the Python 3.8 runtime floor."""

from __future__ import annotations

import ast
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILTIN_GENERIC_NAMES = frozenset(
    {"dict", "frozenset", "list", "set", "tuple", "type"}
)


def runtime_builtin_generic_aliases() -> list[str]:
    """Return top-level aliases that Python 3.8 would evaluate as invalid subscriptions."""
    findings: list[str] = []
    for path in sorted((ROOT / "scripts").rglob("*.py")):
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for statement in module.body:
            if not isinstance(statement, ast.Assign):
                continue
            value = statement.value
            if (
                isinstance(value, ast.Subscript)
                and isinstance(value.value, ast.Name)
                and value.value.id in BUILTIN_GENERIC_NAMES
            ):
                relative = path.relative_to(ROOT).as_posix()
                findings.append(f"{relative}:{statement.lineno}")
    return findings


class PythonCompatibilityContractTests(unittest.TestCase):
    def test_public_guidance_declares_python_38_or_newer(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertRegex(
            readme,
            re.compile(r"Python 3\.8(?:\+| or newer)", re.IGNORECASE),
        )

    def test_ci_exercises_both_lower_bound_platforms_and_current_python(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        jobs = set(
            re.findall(
                r"- os:\s*([^\s]+)\s+python-version:\s*[\"']([^\"']+)[\"']",
                workflow,
            )
        )

        self.assertTrue(
            {
                ("ubuntu-latest", "3.8"),
                ("windows-latest", "3.8"),
                ("ubuntu-latest", "3.x"),
            }.issubset(jobs)
        )
        self.assertIn("python -m unittest discover -s tests -v", workflow)
        self.assertIn("python scripts/manifest_tool.py schema plan", workflow)
        self.assertIn("python scripts/manifest_tool.py schema node", workflow)

    def test_running_interpreter_is_within_the_supported_range(self) -> None:
        self.assertGreaterEqual(sys.version_info[:2], (3, 8))

    def test_production_has_no_runtime_builtin_generic_aliases(self) -> None:
        self.assertEqual(runtime_builtin_generic_aliases(), [])


if __name__ == "__main__":
    unittest.main()
