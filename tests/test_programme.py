"""Order-only Programme and requirement catalogue over split Tree workspaces."""

from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

from scripts.better_plan.domain.programme import new_programme, programme_report
from scripts.better_plan.domain.requirements import coverage
from scripts.better_plan.infrastructure.workspace import write_json


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "scripts" / "manifest_tool.py"


class ProgrammeTests(unittest.TestCase):
    def run_cli(self, *arguments: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(TOOL), *arguments],
            cwd=str(ROOT),
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_current_programme_has_order_only(self) -> None:
        value = new_programme("P", "Programme")
        self.assertEqual(value, {"schema": "better-plan.programme", "id": "P", "title": "Programme", "deliveries": []})
        self.assertNotIn("history", value)
        self.assertNotIn("revision", value)

    def test_report_derives_delivery_readiness(self) -> None:
        programme = new_programme("P", "Programme")
        programme["deliveries"] = [
            {"id": "A", "title": "A", "tree": "A/Tree.json", "requires": []},
            {"id": "B", "title": "B", "tree": "B/Tree.json", "requires": ["A"]},
        ]
        exports = {
            "A": {"derived": {"status": "completed", "delivery_status": "recorded", "ready": [], "review_nodes": []}},
            "B": {"derived": {"status": "pending", "delivery_status": "unrecorded", "ready": ["N"], "review_nodes": ["N"]}},
        }
        report = programme_report(programme, exports)
        self.assertEqual(report["ready"], ["B"])
        self.assertEqual(report["deliveries"][1]["ready_nodes"], ["N"])
        exports["A"]["derived"]["delivery_status"] = "needs_review"
        stale = programme_report(programme, exports)
        self.assertEqual(stale["deliveries"][1]["blocked_by"], ["A"])
        self.assertNotIn("B", stale["ready"])

    def test_cli_updates_and_reads_split_deliveries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            created = self.run_cli("programme", "init", str(root), "--title", "Programme")
            self.assertEqual(created.returncode, 0, created.stderr)
            update = root / "update.json"
            update.write_text(
                json.dumps(
                    {
                        "operations": [
                            {"op": "add", "id": "A", "title": "A", "tree": "A/Tree.json", "requires": []},
                            {"op": "add", "id": "B", "title": "B", "tree": "B/Tree.json", "requires": ["A"]},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            changed = self.run_cli("programme", "update", str(root), "--input", str(update))
            self.assertEqual(changed.returncode, 0, changed.stderr)
            for delivery, status in (("A", "completed"), ("B", "pending")):
                workspace = root / delivery
                (workspace / "tasks").mkdir(parents=True)
                (workspace / "nodes").mkdir()
                write_json(
                    workspace / "Tree.json",
                    {
                        "schema": "better-plan.checkpoints-tree",
                        "id": delivery,
                        "title": delivery,
                        "goal": "goal",
                        "success": [],
                        "architecture": None,
                        "requirements": [],
                        "open_decisions": [],
                        "checks": [],
                    },
                )
                write_json(workspace / "tasks" / "T.json", {"id": "T", "title": "T", "outcome": "", "requirements": [], "checks": []})
                write_json(
                    workspace / "nodes" / "N.json",
                    {
                        "id": "N",
                        "task": "T",
                        "title": "N",
                        "outcome": "",
                        "after": [],
                        "status": status,
                        "role": None,
                        "executors": [],
                        "resources": [],
                        "contract": {},
                        "review": [],
                        "result": None,
                        "checks": [],
                    },
                )
            for command in (("task", "finish", str(root / "A"), "T", "--summary", "Integrated"),
                            ("tree", "finish", str(root / "A"), "--summary", "Reviewed")):
                completed = self.run_cli(*command)
                self.assertEqual(completed.returncode, 0, completed.stderr)
            result = self.run_cli("programme", "status", str(root), "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["ready"], ["B"])
    def test_report_marks_planned_deliveries_without_making_them_ready(self) -> None:
        programme = new_programme("P", "Programme")
        programme["goal"] = "Rolling wave"
        programme["success"] = ["Delivered"]
        programme["deliveries"] = [
            {"id": "FAR", "title": "Far", "requires": []},
            {"id": "NEAR", "title": "Near", "tree": "near/Tree.json", "requires": ["FAR"]},
            {"id": "EMPTY", "title": "Empty", "tree": "empty/Tree.json", "requires": []},
            {"id": "GO", "title": "Go", "tree": "go/Tree.json", "requires": []},
            {"id": "DANGLE", "title": "Dangle", "requires": ["NOPE"]},
        ]
        exports = {
            "NEAR": {"derived": {"status": "pending", "delivery_status": "unrecorded", "node_counts": {"pending": 1}, "ready": [], "review_nodes": []}},
            "EMPTY": {"derived": {"status": "pending", "delivery_status": "unrecorded", "node_counts": {}, "ready": [], "review_nodes": []}},
            "GO": {"derived": {"status": "pending", "delivery_status": "unrecorded", "node_counts": {"pending": 1}, "ready": ["N"], "review_nodes": []}},
        }
        report = programme_report(programme, exports)
        states = {item["id"]: item for item in report["deliveries"]}
        self.assertEqual(states["FAR"]["state"], "planned")
        self.assertEqual(states["FAR"]["execution_status"], "planned")
        self.assertEqual(states["EMPTY"]["state"], "unrecorded")
        self.assertEqual(states["EMPTY"]["execution_status"], "planned")
        self.assertEqual(states["NEAR"]["blocked_by"], ["FAR"])
        self.assertEqual(report["ready"], ["GO"])
        self.assertEqual(report["ready_to_design"], ["FAR", "EMPTY"])
        self.assertEqual(states["DANGLE"]["blocked_by"], ["NOPE"])
        self.assertNotIn("DANGLE", report["ready_to_design"])
        self.assertEqual(report["counts"]["planned"], 2)
        self.assertEqual(report["goal"], "Rolling wave")
        self.assertEqual(report["success"], ["Delivered"])

    def test_coverage_joins_outline_tree_and_task_references(self) -> None:
        programme = new_programme("P", "Programme")
        programme["deliveries"] = [
            {
                "id": "PLAN",
                "title": "Plan",
                "requires": [],
                "requirements": [{"code": "OUTLINE", "source_ids": ["R1", "R4", "R-MISSING"]}],
            },
            {"id": "NEAR", "title": "Near", "tree": "near/Tree.json", "requires": []},
        ]
        catalogue = {
            "schema": "better-plan.requirements",
            "requirements": [
                {"id": "R1"},
                {"id": "R2"},
                {"id": "R3"},
                {"id": "R4", "exclusion": "not ours"},
                {"id": "R5"},
            ],
        }
        exports = {
            "NEAR": {
                "tree": {
                    "requirements": [{"statement": "Tree-owned", "source_ids": ["R2"]}],
                    "tasks": [{"id": "T1", "requirements": [{"statement": "Task-owned", "source_ids": ["R3"]}]}],
                }
            }
        }
        result = coverage(programme, catalogue, exports)
        self.assertEqual(list(result["by_requirement"]), ["R1", "R2", "R3", "R4", "R5"])
        self.assertEqual(result["by_requirement"]["R1"]["deliveries"], ["PLAN"])
        self.assertEqual(result["by_requirement"]["R2"]["deliveries"], ["NEAR"])
        self.assertEqual(result["by_requirement"]["R3"]["deliveries"], ["NEAR"])
        self.assertEqual(result["by_requirement"]["R3"]["tasks"], [{"delivery": "NEAR", "task": "T1"}])
        self.assertEqual(result["by_requirement"]["R4"]["deliveries"], ["PLAN"])
        self.assertEqual(result["uncovered"], ["R5"])
        self.assertEqual(result["excluded"], ["R4"])
        self.assertEqual(result["unknown_refs"], [{"delivery": "PLAN", "task": None, "ref": "R-MISSING"}])

    def test_cli_elaborates_a_planned_delivery_into_a_tree_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            created = self.run_cli("programme", "init", str(root), "--title", "Programme")
            self.assertEqual(created.returncode, 0, created.stderr)
            update = root / "update.json"
            update.write_text(
                json.dumps(
                    {
                        "operations": [
                            {
                                "op": "add",
                                "id": "DELIVERY-ADAPTER-PACKAGES",
                                "title": "Adapter packages",
                                "requires": [],
                                "goal": "Ship adapters",
                                "success": ["Adapters run"],
                                "requirements": [{"code": "ADAPTERS", "statement": "Support adapters", "source_ids": ["REQ-1"]}],
                                "open_decisions": [{"title": "Which adapters", "status": "open"}],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            self.run_cli("programme", "update", str(root), "--input", str(update))

            elaborated = self.run_cli("programme", "elaborate", str(root), "DELIVERY-ADAPTER-PACKAGES")
            self.assertEqual(elaborated.returncode, 0, elaborated.stderr)
            self.assertEqual(json.loads(elaborated.stdout)["tree"], "adapter-packages/Tree.json")

            workspace = root / "adapter-packages"
            tree = json.loads((workspace / "Tree.json").read_text(encoding="utf-8"))
            self.assertEqual(tree["id"], "TREE-ADAPTER-PACKAGES")
            self.assertEqual(tree["title"], "Adapter packages")
            self.assertEqual(tree["goal"], "Ship adapters")
            self.assertEqual(tree["success"], ["Adapters run"])
            self.assertEqual(tree["requirements"], [{"code": "ADAPTERS", "statement": "Support adapters", "source_ids": ["REQ-1"]}])
            self.assertEqual(tree["open_decisions"], [{"title": "Which adapters", "status": "open"}])
            for directory in ("tasks", "nodes", "history"):
                self.assertTrue((workspace / directory).is_dir())

            delivery = json.loads((root / "Programme.json").read_text(encoding="utf-8"))["deliveries"][0]
            self.assertEqual(delivery["tree"], "adapter-packages/Tree.json")
            for key in ("goal", "success", "requirements", "open_decisions"):
                self.assertNotIn(key, delivery)

            status = json.loads(self.run_cli("programme", "status", str(root), "--json").stdout)
            state = {item["id"]: item for item in status["deliveries"]}["DELIVERY-ADAPTER-PACKAGES"]
            self.assertEqual(state["state"], "unrecorded")
            self.assertEqual(state["execution_status"], "planned")

            again = self.run_cli("programme", "elaborate", str(root), "DELIVERY-ADAPTER-PACKAGES")
            self.assertEqual(again.returncode, 1)
            self.assertIn("already has a Tree", again.stderr)
            unknown = self.run_cli("programme", "elaborate", str(root), "DELIVERY-UNKNOWN")
            self.assertEqual(unknown.returncode, 1)
            self.assertIn("unknown delivery", unknown.stderr)

            other = root / "other.json"
            other.write_text(
                json.dumps({"operations": [{"op": "add", "id": "DELIVERY-OTHER", "title": "Other", "requires": []}]}),
                encoding="utf-8",
            )
            self.run_cli("programme", "update", str(root), "--input", str(other))
            taken = self.run_cli("programme", "elaborate", str(root), "DELIVERY-OTHER", "--tree", "adapter-packages/Tree.json")
            self.assertEqual(taken.returncode, 1)
            self.assertIn("already exists", taken.stderr)

    def test_cli_requirements_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.run_cli("programme", "init", str(root), "--title", "Programme")
            entries = root / "entries.json"
            entries.write_text(
                json.dumps(
                    [
                        {"id": "REQ-2", "title": "Second", "statement": {"en": "Two", "zh": "Second"}, "status": "planned"},
                        {"id": "REQ-1", "title": "First", "priority": "high", "exclusion": "legacy"},
                    ]
                ),
                encoding="utf-8",
            )
            added = self.run_cli("requirements", "add", str(root), "--input", str(entries))
            self.assertEqual(added.returncode, 0, added.stderr)
            catalogue = json.loads((root / "Requirements.json").read_text(encoding="utf-8"))
            self.assertEqual([item["id"] for item in catalogue["requirements"]], ["REQ-2", "REQ-1"])
            self.assertEqual(catalogue["requirements"][0]["statement"], {"en": "Two", "zh": "Second"})

            duplicate = self.run_cli("requirements", "add", str(root), "--input", str(entries))
            self.assertEqual(duplicate.returncode, 1)
            self.assertIn("already exists", duplicate.stderr)

            patch = root / "patch.json"
            patch.write_text(json.dumps({"title": "First updated", "meta": {"a": 1}}), encoding="utf-8")
            self.run_cli("requirements", "update", str(root), "REQ-1", "--input", str(patch))
            patch.write_text(json.dumps({"meta": {"b": 2}}), encoding="utf-8")
            self.run_cli("requirements", "update", str(root), "REQ-1", "--input", str(patch))
            listed = json.loads(self.run_cli("requirements", "list", str(root), "--json").stdout)
            first = {item["id"]: item for item in listed}["REQ-1"]
            self.assertEqual(first["title"], "First updated")
            self.assertEqual(first["meta"], {"a": 1, "b": 2})
            self.assertEqual(first["exclusion"], "legacy")

            removed = self.run_cli("requirements", "remove", str(root), "REQ-2")
            self.assertEqual(removed.returncode, 0, removed.stderr)
            leftover = json.loads((root / "Requirements.json").read_text(encoding="utf-8"))["requirements"]
            self.assertEqual([item["id"] for item in leftover], ["REQ-1"])
            missing = self.run_cli("requirements", "remove", str(root), "REQ-404")
            self.assertEqual(missing.returncode, 1)
            self.assertIn("unknown requirement", missing.stderr)

    def test_cli_programme_export_includes_planned_error_and_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.run_cli("programme", "init", str(root), "--title", "Programme")
            good = root / "good"
            self.run_cli("tree", "init", str(good), "--title", "Good", "--goal", "Ship")
            task = root / "task.json"
            task.write_text(json.dumps({"id": "TASK-001", "title": "Build", "outcome": "Built"}), encoding="utf-8")
            self.run_cli("task", "add", str(good), "--input", str(task))
            node = root / "node.json"
            node.write_text(json.dumps({"id": "NODE-001", "task": "TASK-001", "title": "Scoped", "outcome": "Scoped"}), encoding="utf-8")
            self.run_cli("node", "add", str(good), "--input", str(node))
            checks = root / "checks.json"
            checks.write_text(
                json.dumps(
                    {
                        "checks": [
                            {"id": "CHECK-A", "commands": [], "coverage": {"kind": "tree"}},
                            {"id": "CHECK-B", "commands": [], "coverage": {"kind": "tree"}},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            self.run_cli("tree", "update", str(good), "--input", str(checks))
            first = root / "first.json"
            first.write_text(json.dumps({"status": "passed", "summary": "First", "metrics": {"native_loc": 367511, "suites": 3}}), encoding="utf-8")
            second = root / "second.json"
            second.write_text(json.dumps({"status": "passed", "summary": "Second", "metrics": {"native_loc": 10}}), encoding="utf-8")
            self.run_cli("checks", "record", str(good), "CHECK-A", "--owner", "tree", "--result", str(first))
            self.run_cli("checks", "record", str(good), "CHECK-B", "--owner", "tree", "--result", str(second))
            broken = root / "broken"
            broken.mkdir()
            (broken / "Tree.json").write_text("{not json", encoding="utf-8")
            update = root / "update.json"
            update.write_text(
                json.dumps(
                    {
                        "operations": [
                            {"op": "add", "id": "GOOD", "title": "Good", "tree": "good/Tree.json", "requires": []},
                            {"op": "add", "id": "BROKEN", "title": "Broken", "tree": "broken/Tree.json", "requires": []},
                            {
                                "op": "add",
                                "id": "PLAN",
                                "title": "Plan",
                                "requires": [],
                                "goal": "Later",
                                "success": ["One"],
                                "requirements": [],
                                "open_decisions": [],
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            self.run_cli("programme", "update", str(root), "--input", str(update))

            exported = self.run_cli("programme", "export", str(root))
            self.assertEqual(exported.returncode, 0, exported.stderr)
            payload = json.loads(exported.stdout)
            self.assertEqual(payload["schema"], "better-plan.programme-export")
            self.assertEqual(payload["deliveries"]["GOOD"]["kind"], "tree")
            self.assertEqual(payload["deliveries"]["PLAN"]["kind"], "planned")
            self.assertEqual(payload["deliveries"]["PLAN"]["outline"]["goal"], "Later")
            self.assertEqual(payload["deliveries"]["PLAN"]["outline"]["open_decisions"], [])
            self.assertEqual(payload["deliveries"]["BROKEN"]["kind"], "error")
            self.assertIn("invalid JSON", payload["deliveries"]["BROKEN"]["error"])
            states = {item["id"]: item for item in payload["report"]["deliveries"]}
            self.assertEqual(states["PLAN"]["state"], "planned")
            self.assertEqual(states["PLAN"]["execution_status"], "planned")
            self.assertEqual(states["BROKEN"]["state"], "missing")
            self.assertEqual(payload["report"]["ready"], ["GOOD"])
            self.assertEqual(payload["report"]["ready_to_design"], ["PLAN"])
            self.assertEqual([item["value"] for item in payload["metrics"]["native_loc"]], [367511, 10])
            self.assertEqual(payload["metrics"]["native_loc"][0]["owner"], {"kind": "tree", "id": "TREE-001"})
            self.assertEqual(payload["metrics"]["native_loc"][0]["status"], "passed")
            self.assertEqual([item["value"] for item in payload["metrics"]["suites"]], [3])
            self.assertEqual(payload["requirements"], {"catalogue": [], "coverage": {"by_requirement": {}, "uncovered": [], "excluded": [], "unknown_refs": []}})


if __name__ == "__main__":
    unittest.main()
