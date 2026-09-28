"""Order-only Programme over split Tree workspaces."""

from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

from scripts.better_plan.domain.programme import new_programme, programme_report
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


if __name__ == "__main__":
    unittest.main()
