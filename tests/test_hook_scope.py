from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.better_plan.hooks import scope as hook_scope


PLAN_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
NODE_ID = "11111111-1111-4111-8111-111111111111"

def write_workspace(root: Path) -> Path:
    plan_dir = root / "main-plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "Checkpoints.json").write_text(
        json.dumps(
            [
                {
                    "id": NODE_ID,
                    "status": "pending",
                    "role": "implementation",
                    "prerequisites": [],
                    "platform": "any",
                    "difficulty": "low",
                    "goal": "Detection fixture.",
                    "description": "Scope: Closure: module - detection fixture.",
                    "requirements": ["REQ-001"],
                    "acceptance_criteria": [{"checked": False, "text": "Detected."}],
                    "commit": {"repository": ".git", "message": "test", "target": "tests"},
                    "regression": {"scope": "focused", "commands": ["true"], "criteria": [0], "paths": ["tracked.txt"]},
                    "next": [],
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
                    "status": "pending",
                    "title": "Detection fixture",
                    "directory": "main-plan",
                    "source_files": [],
                    "goal": "Detect Better Plan.",
                    "description": "Structural fixture.",
                    "checkpoints": "main-plan/Checkpoints.json",
                }
            ]
        ),
        encoding="utf-8",
    )
    return root


class HookScopeTests(unittest.TestCase):
    def make_project(self, root: Path, name: str = "project") -> Path:
        project = root / name
        project.mkdir()
        (project / ".git").mkdir()
        (project / "tracked.txt").write_text("stable\n", encoding="utf-8")
        return project

    def test_detects_one_structural_workspace_from_a_nested_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self.make_project(Path(tmpdir))
            workspace = write_workspace(project / "docs" / "plan")
            nested = project / "src" / "feature"
            nested.mkdir(parents=True)

            detected = hook_scope.detect_workspace(nested)

        self.assertEqual(detected.resolve() if detected is not None else None, (workspace / "Manifest.json").resolve())

    def test_repository_without_better_plan_is_inactive(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self.make_project(Path(tmpdir))

            detected = hook_scope.detect_workspace(project)

        self.assertIsNone(detected)

    def test_multiple_structural_workspaces_are_inactive(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self.make_project(Path(tmpdir))
            write_workspace(project / "plans" / "one")
            write_workspace(project / "plans" / "two")

            detected = hook_scope.detect_workspace(project)

        self.assertIsNone(detected)

    def test_parent_development_directory_is_not_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project = self.make_project(root)
            write_workspace(project / "docs" / "plan")

            detected = hook_scope.detect_workspace(root)

        self.assertIsNone(detected)

    def test_event_detection_rejects_ambiguous_workspace_roots(self) -> None:
        payload = {"workspace_roots": ["project-one", "project-two"]}

        self.assertIsNone(hook_scope.detect_event_workspace(payload))

    def test_event_detection_unifies_consistent_cwd_and_workspace_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self.make_project(Path(tmpdir))
            workspace = write_workspace(project / "docs" / "plan")
            nested = project / "src"
            nested.mkdir()

            detected = hook_scope.detect_event_workspace(
                {"cwd": str(nested), "workspace_roots": [str(project)]}
            )

        self.assertEqual(detected.resolve() if detected is not None else None, (workspace / "Manifest.json").resolve())

    def test_event_detection_rejects_cwd_with_multiple_workspace_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project = self.make_project(root)
            write_workspace(project / "docs" / "plan")
            second = self.make_project(root, "second-project")

            detected = hook_scope.detect_event_workspace(
                {"cwd": str(project), "workspace_roots": [str(project), str(second)]}
            )

        self.assertIsNone(detected)

    def test_event_detection_rejects_conflicting_cwd_and_workspace_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project = self.make_project(root)
            write_workspace(project / "docs" / "plan")
            second = self.make_project(root, "second-project")

            detected = hook_scope.detect_event_workspace(
                {"cwd": str(project), "workspace_roots": [str(second)]}
            )

        self.assertIsNone(detected)

    def test_event_detection_rejects_direct_manifest_outside_a_repository(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = write_workspace(Path(tmpdir) / "standalone")

            detected = hook_scope.detect_event_workspace({"cwd": str(workspace / "Manifest.json")})

        self.assertIsNone(detected)

if __name__ == "__main__":
    unittest.main()
