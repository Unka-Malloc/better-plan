"""Focused acceptance for native milestone-gate execution semantics."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Optional, Sequence

from tests.test_manifest_tool_cli import (
    CHILD_NODE_ID,
    NODE_ID,
    PYTHON_TOOL,
    read_nodes,
    read_plans,
    run_command,
    write_hierarchical_workspace,
    write_workspace,
    checkpoint_node,
)


GATE_ID = "66666666-6666-4666-8666-666666666666"
OTHER_ID = "77777777-7777-4777-8777-777777777777"
REPO_ROOT = PYTHON_TOOL.parents[1]


def gate_leaf(
    *,
    node_id: str = NODE_ID,
    status: str = "completed",
    prerequisites: Optional[Sequence[str]] = None,
) -> dict[str, object]:
    node = checkpoint_node(
        node_id,
        status=status,
        role="evidence",
        prerequisites=list(prerequisites or ()),
        checked=status == "completed",
        goal="Produce exact evidence consumed by one aggregate milestone gate.",
    )
    node["tags"] = ["GATE_LEAF"]
    return node


def milestone_gate(
    *,
    status: str = "pending",
    prerequisites: Optional[Sequence[str]] = None,
    checked: bool = False,
    tags: Optional[Sequence[str]] = None,
) -> dict[str, object]:
    reason = (
        "Wait until the gate has a canonical leaf prerequisite."
        if status in {"blocked", "deferred"}
        else None
    )
    node = checkpoint_node(
        GATE_ID,
        status=status,
        role="milestone_gate",
        prerequisites=list(prerequisites or ()),
        checked=checked,
        status_reason=reason,
        goal="Aggregate accepted leaf evidence into one milestone decision.",
    )
    node["difficulty"] = "complex"
    if tags is not None:
        node["tags"] = list(tags)
    return node


class MilestoneGateTests(unittest.TestCase):
    def test_guidance_preserves_leaf_lifecycle_and_prerequisite_authority(self) -> None:
        documents = (
            (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8"),
            (REPO_ROOT / "references" / "state-files.md").read_text(
                encoding="utf-8"
            ),
        )

        for content in documents:
            normalized = " ".join(content.split())
            self.assertIn("milestone_gate", normalized)
            self.assertIn("GATE_LEAF", normalized)
            self.assertIn("same-Plan", normalized)
            self.assertIn("start", normalized)
            self.assertIn("check", normalized)
            self.assertIn("complete", normalized)
            self.assertRegex(
                normalized,
                r"prerequisites.{0,180}(sole|exclusively)",
            )
            self.assertRegex(
                normalized,
                r"(prose task card|task card).{0,180}(not|insufficient)",
            )

    def test_schema_declares_non_delivery_gate_role_and_reserved_leaf_tag(self) -> None:
        result = run_command(sys.executable, PYTHON_TOOL, "schema", "node")

        self.assertEqual(result.returncode, 0, result.stderr)
        schema = json.loads(result.stdout)
        self.assertIn("milestone_gate", schema["roles"])
        self.assertEqual(schema["reserved_tags"], ["GATE_LEAF"])

    def test_pending_gate_requires_complex_difficulty_and_a_direct_same_plan_leaf(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            indirect = checkpoint_node(
                OTHER_ID,
                status="completed",
                role="evidence",
                prerequisites=[NODE_ID],
            )
            gate = milestone_gate(prerequisites=[OTHER_ID])
            gate["difficulty"] = "standard"
            write_workspace(
                root,
                plan_status="in_progress",
                nodes=[gate_leaf(), indirect, gate],
            )

            result = run_command(
                sys.executable,
                PYTHON_TOOL,
                "validate",
                root,
                "--no-git",
            )

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(
            "role 'milestone_gate' must use 'complex' or 'critical'",
            result.stderr,
        )
        self.assertIn(
            "must directly reference at least one same-Plan GATE_LEAF node",
            result.stderr,
        )

    def test_blocked_and_deferred_gates_may_wait_without_a_leaf(self) -> None:
        for status in ("blocked", "deferred"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                write_workspace(
                    root,
                    plan_status=status,
                    nodes=[milestone_gate(status=status)],
                )

                result = run_command(
                    sys.executable,
                    PYTHON_TOOL,
                    "validate",
                    root,
                    "--no-git",
                )

                self.assertEqual(result.returncode, 0, result.stderr)

    def test_pending_active_and_completed_gates_require_a_leaf(self) -> None:
        for status in ("pending", "in_progress", "completed"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                write_workspace(
                    root,
                    plan_status=status,
                    nodes=[
                        milestone_gate(
                            status=status,
                            checked=status == "completed",
                        )
                    ],
                )

                result = run_command(
                    sys.executable,
                    PYTHON_TOOL,
                    "validate",
                    root,
                    "--no-git",
                )

                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn(
                    "must directly reference at least one same-Plan GATE_LEAF node",
                    result.stderr,
                )

    def test_gate_leaf_tag_is_for_non_gate_nodes_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_workspace(
                root,
                plan_status="deferred",
                nodes=[
                    milestone_gate(
                        status="deferred",
                        tags=["GATE_LEAF"],
                    )
                ],
            )

            result = run_command(
                sys.executable,
                PYTHON_TOOL,
                "validate",
                root,
                "--no-git",
            )

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(
            "GATE_LEAF may be used only on non-milestone_gate nodes",
            result.stderr,
        )

    def test_cross_plan_gate_leaf_cannot_satisfy_a_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_hierarchical_workspace(root)
            common_path = root / "common" / "Checkpoints.json"
            child_path = root / "common" / "a" / "Checkpoints.json"
            common_nodes = json.loads(common_path.read_text(encoding="utf-8"))
            common_nodes[0]["tags"] = ["GATE_LEAF"]
            common_path.write_text(json.dumps(common_nodes), encoding="utf-8")
            child_path.write_text(
                json.dumps([milestone_gate(prerequisites=[NODE_ID])]),
                encoding="utf-8",
            )
            plans = read_plans(root)
            plans[1]["status"] = "pending"
            (root / "Manifest.json").write_text(
                json.dumps(plans),
                encoding="utf-8",
            )

            result = run_command(
                sys.executable,
                PYTHON_TOOL,
                "validate",
                root,
                "--no-git",
            )

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("same-Plan GATE_LEAF node", result.stderr)
        self.assertIn(
            "GATE_LEAF prerequisite must be owned by the same Plan",
            result.stderr,
        )

    def test_next_hides_an_invalid_gate_and_lists_a_valid_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_workspace(
                root,
                plan_status="pending",
                nodes=[milestone_gate()],
            )

            invalid = run_command(
                sys.executable,
                PYTHON_TOOL,
                "next",
                root,
                "--json",
            )
            invalid_tree = run_command(
                sys.executable,
                PYTHON_TOOL,
                "tree",
                root,
            )

            self.assertEqual(invalid.returncode, 0, invalid.stderr)
            self.assertEqual(
                [
                    entry
                    for plan in json.loads(invalid.stdout)["plans"]
                    for entry in plan["eligible"]
                ],
                [],
            )
            self.assertEqual(invalid_tree.returncode, 0, invalid_tree.stderr)
            self.assertNotIn("<== CURRENT", invalid_tree.stdout)

            write_workspace(
                root,
                plan_status="in_progress",
                nodes=[gate_leaf(), milestone_gate(prerequisites=[NODE_ID])],
            )
            valid = run_command(
                sys.executable,
                PYTHON_TOOL,
                "next",
                root,
                "--json",
            )
            valid_tree = run_command(
                sys.executable,
                PYTHON_TOOL,
                "tree",
                root,
            )

        self.assertEqual(valid.returncode, 0, valid.stderr)
        eligible = [
            entry["id"]
            for plan in json.loads(valid.stdout)["plans"]
            for entry in plan["eligible"]
        ]
        self.assertEqual(eligible, [GATE_ID])
        self.assertEqual(valid_tree.returncode, 0, valid_tree.stderr)
        self.assertEqual(valid_tree.stdout.count("<== CURRENT"), 1)
        self.assertIn(
            "Aggregate accepted leaf evidence into one milestone decision. [E]",
            valid_tree.stdout,
        )

    def test_gate_leaf_remains_a_directly_executable_foundation_node(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_workspace(
                root,
                plan_status="pending",
                nodes=[gate_leaf(status="pending")],
            )

            next_result = run_command(
                sys.executable,
                PYTHON_TOOL,
                "next",
                root,
                "--json",
            )
            started = run_command(
                sys.executable,
                PYTHON_TOOL,
                "start",
                NODE_ID,
                root,
            )

        self.assertEqual(next_result.returncode, 0, next_result.stderr)
        eligible = [
            entry["id"]
            for plan in json.loads(next_result.stdout)["plans"]
            for entry in plan["eligible"]
        ]
        self.assertEqual(eligible, [NODE_ID])
        self.assertEqual(started.returncode, 0, started.stderr)

    def test_activate_and_start_fail_closed_without_a_gate_leaf(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_workspace(
                root,
                plan_status="deferred",
                nodes=[milestone_gate(status="deferred")],
            )
            checkpoint_path = root / "main-plan" / "Checkpoints.json"
            before_activate = checkpoint_path.read_bytes()

            activated = run_command(
                sys.executable,
                PYTHON_TOOL,
                "activate",
                GATE_ID,
                root,
            )

            self.assertNotEqual(activated.returncode, 0, activated.stdout)
            self.assertIn("same-Plan GATE_LEAF", activated.stderr)
            self.assertEqual(checkpoint_path.read_bytes(), before_activate)

            write_workspace(
                root,
                plan_status="pending",
                nodes=[milestone_gate()],
            )
            before_start = checkpoint_path.read_bytes()
            started = run_command(
                sys.executable,
                PYTHON_TOOL,
                "start",
                GATE_ID,
                root,
            )

            self.assertNotEqual(started.returncode, 0, started.stdout)
            self.assertIn("same-Plan GATE_LEAF", started.stderr)
            self.assertEqual(checkpoint_path.read_bytes(), before_start)

    def test_valid_gate_uses_manual_start_check_complete_not_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_workspace(
                root,
                plan_status="in_progress",
                nodes=[gate_leaf(), milestone_gate(prerequisites=[NODE_ID])],
            )

            dispatch = run_command(
                sys.executable,
                PYTHON_TOOL,
                "dispatch",
                GATE_ID,
                root,
                "--role",
                "worker",
            )
            started = run_command(
                sys.executable,
                PYTHON_TOOL,
                "start",
                GATE_ID,
                root,
            )
            checked = run_command(
                sys.executable,
                PYTHON_TOOL,
                "check",
                GATE_ID,
                root,
                "--criterion",
                "0",
                "--evidence",
                "All canonical leaf evidence was accepted.",
            )
            completed = run_command(
                sys.executable,
                PYTHON_TOOL,
                "complete",
                GATE_ID,
                root,
            )
            nodes = read_nodes(root)
            plans = read_plans(root)

        self.assertNotEqual(dispatch.returncode, 0, dispatch.stdout)
        self.assertIn(
            "delivery commands require a group_design, implementation, or final_validation node",
            dispatch.stderr,
        )
        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(nodes[1]["status"], "completed")
        self.assertNotIn("acceptance", nodes[1])
        self.assertNotIn("regression", nodes[1])
        self.assertEqual(plans[0]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
