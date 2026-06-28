from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_TOOL = REPO_ROOT / "scripts" / "manifest_tool.py"
UUID4_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


PLAN_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
NODE_ID = "11111111-1111-4111-8111-111111111111"
MISSING_NODE_ID = "22222222-2222-4222-8222-222222222222"


def run_command(*args: str | Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(arg) for arg in args],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def write_workspace(root: Path, *, include_bad_next: bool = False) -> None:
    plan_dir = root / "main-plan"
    plan_dir.mkdir()
    next_refs = [MISSING_NODE_ID] if include_bad_next else []
    (plan_dir / "Checkpoints.json").write_text(
        json.dumps(
            [
                {
                    "id": NODE_ID,
                    "status": "completed",
                    "prerequisites": [],
                    "platform": "linux",
                    "difficulty": "medium",
                    "goal": "Validate the CLI happy path.",
                    "description": "Minimal checkpoint node for CLI integration tests.",
                    "acceptance_criteria": [
                        {
                            "checked": True,
                            "text": "The validator accepts the workspace.",
                        }
                    ],
                    "commit": {
                        "repository": ".git",
                        "message": "test cli validation",
                        "target": "tests",
                    },
                    "next": next_refs,
                }
            ]
        ),
        encoding="utf-8",
    )
    (root / "Manifest.json").write_text(
        json.dumps(
            [
                {
                    "id": PLAN_ID,
                    "status": "completed",
                    "title": "Main Plan",
                    "directory": "main-plan",
                    "source_files": ["docs/plan.md"],
                    "goal": "Validate the CLI happy path.",
                    "description": "Minimal workspace for CLI integration tests.",
                    "checkpoints": "main-plan/Checkpoints.json",
                }
            ]
        ),
        encoding="utf-8",
    )


class ManifestToolCliTests(unittest.TestCase):
    def test_python_validate_accepts_minimal_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            write_workspace(Path(tmpdir))

            result = run_command(sys.executable, PYTHON_TOOL, "validate", tmpdir)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OK: validated 2 state file(s), 2 item(s).", result.stdout)

    def test_python_validate_rejects_unknown_next_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            write_workspace(Path(tmpdir), include_bad_next=True)

            result = run_command(sys.executable, PYTHON_TOOL, "validate", tmpdir)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("node[0].next: unknown node id", result.stderr)

    def test_python_transition_cli_reports_invalid_edge(self) -> None:
        result = run_command(sys.executable, PYTHON_TOOL, "transition", "completed", "in_progress")

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("cannot transition from 'completed' to 'in_progress'", result.stderr)

    def test_python_uuid_cli_outputs_uuid4_values(self) -> None:
        result = run_command(sys.executable, PYTHON_TOOL, "uuid", "--count", "2")

        self.assertEqual(result.returncode, 0, result.stderr)
        values = result.stdout.strip().splitlines()
        self.assertEqual(len(values), 2)
        self.assertTrue(all(UUID4_PATTERN.fullmatch(value) for value in values), values)


if __name__ == "__main__":
    unittest.main()
