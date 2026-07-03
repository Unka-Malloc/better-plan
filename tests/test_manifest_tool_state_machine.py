from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_TOOL_PATH = REPO_ROOT / "scripts" / "manifest_tool.py"

spec = importlib.util.spec_from_file_location("manifest_tool", MANIFEST_TOOL_PATH)
assert spec is not None
manifest_tool = importlib.util.module_from_spec(spec)
sys.modules["manifest_tool"] = manifest_tool
assert spec.loader is not None
spec.loader.exec_module(manifest_tool)


PLAN_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
NODE_A_ID = "11111111-1111-4111-8111-111111111111"
NODE_B_ID = "22222222-2222-4222-8222-222222222222"


def make_node(
    node_id: str,
    status: str,
    *,
    role: str = "implementation",
    prerequisites: list[str] | None = None,
    difficulty: str = "medium",
    checked: bool = True,
) -> dict[str, object]:
    return {
        "id": node_id,
        "status": status,
        "role": role,
        "prerequisites": prerequisites or [],
        "platform": "macos",
        "difficulty": difficulty,
        "goal": "Exercise state machine validation.",
        "description": "Test node for Better Plan state machine rules.",
        "acceptance_criteria": [
            {
                "checked": checked,
                "text": "State machine validation has evidence.",
            }
        ],
        "commit": {
            "repository": ".git",
            "message": "test state machine",
            "target": "tests",
        },
        "next": [],
    }


class WorkflowStateMachineTests(unittest.TestCase):
    def test_transition_rules_allow_expected_edges(self) -> None:
        machine = manifest_tool.WORKFLOW_STATE_MACHINE

        self.assertTrue(machine.can_transition("pending", "in_progress"))
        self.assertTrue(machine.can_transition("in_progress", "completed"))
        self.assertTrue(machine.can_transition("blocked", "in_progress"))
        self.assertFalse(machine.can_transition("completed", "in_progress"))
        self.assertFalse(machine.can_transition("skipped", "pending"))

    def test_in_progress_node_requires_completed_prerequisites(self) -> None:
        data = [
            make_node(NODE_A_ID, "pending"),
            make_node(NODE_B_ID, "in_progress", prerequisites=[NODE_A_ID]),
        ]

        _, issues = manifest_tool.validate_checkpoints_data(Path("Checkpoints.json"), data)

        self.assertTrue(
            any("cannot be 'in_progress' until prerequisites are completed" in issue.message for issue in issues),
            [issue.message for issue in issues],
        )

    def test_completed_node_requires_checked_acceptance_criteria(self) -> None:
        data = [make_node(NODE_A_ID, "completed", checked=False)]

        _, issues = manifest_tool.validate_checkpoints_data(Path("Checkpoints.json"), data)

        self.assertTrue(
            any("cannot be 'completed' with unchecked acceptance criteria" in issue.message for issue in issues),
            [issue.message for issue in issues],
        )

    def test_only_one_checkpoint_node_may_be_in_progress(self) -> None:
        data = [
            make_node(NODE_A_ID, "in_progress"),
            make_node(NODE_B_ID, "in_progress"),
        ]

        _, issues = manifest_tool.validate_checkpoints_data(Path("Checkpoints.json"), data)

        self.assertTrue(
            any("only one node may be in_progress" in issue.message for issue in issues),
            [issue.message for issue in issues],
        )

    def test_completed_plan_requires_terminal_checkpoint_nodes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            plan_dir = workspace / "main-plan"
            plan_dir.mkdir()
            (plan_dir / "Checkpoints.json").write_text(
                json.dumps([make_node(NODE_A_ID, "pending")]),
                encoding="utf-8",
            )
            manifest = [
                {
                    "id": PLAN_ID,
                    "status": "completed",
                    "title": "Main Plan",
                    "directory": "main-plan",
                    "source_files": ["docs/plan.md"],
                    "goal": "Exercise plan state validation.",
                    "description": "Test plan for Better Plan state machine rules.",
                    "checkpoints": "main-plan/Checkpoints.json",
                }
            ]
            manifest_path = workspace / "Manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            _, issues = manifest_tool.validate_plan_manifest_data(manifest_path, manifest)

        self.assertTrue(
            any("cannot be 'completed' while checkpoints contain non-terminal nodes" in issue.message for issue in issues),
            [issue.message for issue in issues],
        )

    def test_product_requirements_role_requires_deep_difficulty(self) -> None:
        data = [make_node(NODE_A_ID, "pending", role="product_requirements", difficulty="high")]

        _, issues = manifest_tool.validate_checkpoints_data(Path("Checkpoints.json"), data)

        self.assertTrue(
            any("role 'product_requirements' must use 'deep'" in issue.message for issue in issues),
            [issue.message for issue in issues],
        )

    def test_architecture_role_requires_prior_validation_matrix(self) -> None:
        data = [
            make_node(NODE_A_ID, "pending", role="architecture_scaffold", difficulty="high"),
            make_node(NODE_B_ID, "pending", role="validation_matrix", difficulty="deep"),
        ]

        _, issues = manifest_tool.validate_checkpoints_data(Path("Checkpoints.json"), data)

        self.assertTrue(
            any("'architecture_scaffold' must not appear before 'validation_matrix'" in issue.message for issue in issues),
            [issue.message for issue in issues],
        )


if __name__ == "__main__":
    unittest.main()
