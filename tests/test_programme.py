"""Programme index: many deliveries, derived state, and honest contention."""

from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

from scripts.better_plan.domain import checkpoints_tree as tree_model
from scripts.better_plan.domain import programme as programme_model
from scripts.better_plan.domain.models import ToolError


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "scripts" / "manifest_tool.py"


def delivery_tree(resource: str | None = None) -> dict:
    """One complete delivery shape: designer, one worker, reviewer."""

    tree = tree_model.new_tree("TREE-001", "Delivery")
    worker = {
        "id": "NODE-002",
        "title": "work",
        "outcome": "The work is done.",
        "role": "worker-1",
        "after": ["NODE-001"],
    }
    if resource:
        worker["resources"] = [resource]
    tree_model.apply_operations(
        tree,
        [
            {
                "op": "task.add",
                "id": "TASK-001",
                "title": "deliver",
                "outcome": "The delivery is visible.",
                "nodes": [
                    {
                        "id": "NODE-001",
                        "title": "design",
                        "outcome": "The approach is fixed.",
                        "role": "designer",
                    },
                    worker,
                    {
                        "id": "NODE-003",
                        "title": "review",
                        "outcome": "The delivery is audited.",
                        "role": "reviewer",
                        "after": ["NODE-002"],
                    },
                ],
            }
        ],
    )
    return tree


def programme_with(deliveries: list[dict]) -> dict:
    programme = programme_model.new_programme("PROGRAMME-001", "Delivery programme")
    programme_model.apply_operations(
        programme,
        [{"op": "delivery.add", **delivery} for delivery in deliveries],
    )
    return programme


class ProgrammeIndexTests(unittest.TestCase):
    def test_the_index_orders_deliveries_and_derives_every_state(self) -> None:
        programme = programme_with(
            [
                {"id": "M10", "title": "platform", "tree": "m10/Tree.json", "requires": []},
                {"id": "M11", "title": "contract", "tree": "m11/Tree.json", "requires": ["M10"]},
                {"id": "M12", "title": "android", "tree": "m12/Tree.json", "requires": ["M11"]},
            ]
        )
        trees = {"M10": delivery_tree(), "M11": delivery_tree(), "M12": None}

        report = programme_model.programme_report(programme, trees)

        self.assertEqual(programme_model.delivery_order(programme), ["M10", "M11", "M12"])
        self.assertEqual([state["id"] for state in report["deliveries"]], ["M10", "M11", "M12"])
        self.assertEqual(report["ready"], ["M10"])
        states = {state["id"]: state for state in report["deliveries"]}
        self.assertEqual(states["M11"]["blocked_by"], ["M10"])
        self.assertEqual(states["M12"]["state"], "missing")
        self.assertEqual(states["M10"]["ready_nodes"], ["NODE-001"])
        self.assertEqual(states["M10"]["reviewer"], "NODE-003")
        self.assertEqual(states["M10"]["gate"], ["NODE-002"])

        # The index carries order only: completing the delivery is what frees the next.
        for code in ("NODE-001", "NODE-002", "NODE-003"):
            tree_model.transition(trees["M10"], code, "complete", note="done")
        report = programme_model.programme_report(programme, trees)
        states = {state["id"]: state for state in report["deliveries"]}
        self.assertEqual(states["M10"]["state"], "completed")
        self.assertEqual(report["ready"], ["M11"])

    def test_a_hand_maintained_state_field_is_rejected(self) -> None:
        programme = programme_with(
            [{"id": "M10", "title": "platform", "tree": "m10/Tree.json", "requires": []}]
        )
        programme["deliveries"][0]["state"] = "delivered"

        issues = programme_model.validate_programme(programme)

        self.assertTrue(any("unknown field" in issue for issue in issues), issues)

    def test_contention_names_resources_the_order_does_not_cover(self) -> None:
        programme = programme_with(
            [
                {"id": "M10", "title": "platform", "tree": "m10/Tree.json", "requires": []},
                {"id": "M11", "title": "contract", "tree": "m11/Tree.json", "requires": ["M10"]},
                {"id": "M12", "title": "android", "tree": "m12/Tree.json", "requires": ["M11"]},
                {"id": "M13", "title": "ios", "tree": "m13/Tree.json", "requires": ["M11"]},
            ]
        )
        trees = {
            "M11": delivery_tree("worktree/"),
            "M12": delivery_tree("worktree/"),
            "M13": delivery_tree("worktree/"),
        }

        contention = programme_model.programme_contention(programme, trees)

        self.assertEqual([item["resource"] for item in contention], ["worktree/"])
        self.assertEqual(
            contention[0]["unordered"],
            [["M12/NODE-002", "M13/NODE-002"]],
        )

    def test_a_programme_batch_is_atomic_and_idempotent(self) -> None:
        programme = programme_model.new_programme("PROGRAMME-001", "Atomic")
        programme_model.apply_operations(
            programme,
            [
                {"op": "delivery.add", "id": "M10", "title": "a", "tree": "m10/Tree.json"},
                {
                    "op": "delivery.add",
                    "id": "M11",
                    "title": "b",
                    "tree": "m11/Tree.json",
                    "requires": ["M10"],
                },
            ],
            batch_id="first",
        )
        before = json.dumps(programme, sort_keys=True)

        with self.assertRaises(ToolError):
            programme_model.apply_operations(
                programme,
                [
                    {"op": "delivery.add", "id": "M12", "title": "c", "tree": "m12/Tree.json"},
                    {"op": "delivery.add", "id": "M10", "title": "duplicate", "tree": "x/Tree.json"},
                ],
            )
        self.assertEqual(json.dumps(programme, sort_keys=True), before)

        replay = programme_model.apply_operations(
            programme,
            [{"op": "delivery.add", "id": "M99", "title": "z", "tree": "m99/Tree.json"}],
            batch_id="first",
        )
        self.assertTrue(replay["idempotent"])
        self.assertEqual([item["id"] for item in programme["deliveries"]], ["M10", "M11"])

        with self.assertRaises(ToolError) as dependent:
            programme_model.apply_operations(
                programme, [{"op": "delivery.remove", "id": "M10"}]
            )
        self.assertIn("required by M11", str(dependent.exception))

        programme_model.apply_operations(
            programme, [{"op": "delivery.remove", "id": "M10", "force": True}]
        )
        self.assertEqual([item["id"] for item in programme["deliveries"]], ["M11"])
        self.assertEqual(programme["deliveries"][0]["requires"], [])


class ProgrammeCliTests(unittest.TestCase):
    def run_cli(self, *arguments: str, stdin: str | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(TOOL), *arguments],
            cwd=str(ROOT),
            input=stdin,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_the_cli_reports_a_ready_programme_and_a_shared_resource(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            created = self.run_cli("programme-init", str(root), "--title", "LicoUp delivery")
            self.assertEqual(created.returncode, 0, created.stderr)

            batch = {
                "batch_id": "programme-1",
                "operations": [
                    {
                        "op": "delivery.add",
                        "id": "M10",
                        "title": "platform",
                        "tree": "10/Tree.json",
                        "requires": [],
                    },
                    {
                        "op": "delivery.add",
                        "id": "M12",
                        "title": "android",
                        "tree": "12/Tree.json",
                        "requires": ["M10"],
                    },
                    {
                        "op": "delivery.add",
                        "id": "M13",
                        "title": "ios",
                        "tree": "13/Tree.json",
                        "requires": ["M10"],
                    },
                ],
            }
            batch_path = root / "batch.json"
            batch_path.write_text(json.dumps(batch), encoding="utf-8")
            applied = self.run_cli("programme-apply", str(root), "--input", str(batch_path))
            self.assertEqual(applied.returncode, 0, applied.stderr)

            for name in ("10", "12", "13"):
                directory = root / name
                directory.mkdir()
                tree = delivery_tree("worktree/")
                (directory / "Tree.json").write_text(
                    json.dumps(tree, sort_keys=True), encoding="utf-8"
                )

            status = self.run_cli("programme-status", str(root), "--json")
            self.assertEqual(status.returncode, 0, status.stderr)
            report = json.loads(status.stdout)
            self.assertEqual(report["ready"], ["M10"])
            self.assertEqual(
                report["contention"][0]["unordered"], [["M12/NODE-002", "M13/NODE-002"]]
            )

            rendered = self.run_cli("programme", str(root))
            self.assertEqual(rendered.returncode, 0, rendered.stderr)
            self.assertIn("M10 platform tree=10/Tree.json", rendered.stdout)

    def test_a_command_never_invents_a_programme(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "typo"
            refused = self.run_cli("programme-status", str(missing))
            self.assertEqual(refused.returncode, 1)
            self.assertIn("no programme", refused.stderr)
            self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
