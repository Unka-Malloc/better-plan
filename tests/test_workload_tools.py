from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.wait_hint import wait_hint


ROOT = Path(__file__).resolve().parents[1]
TASK_SHAPE = ROOT / "scripts" / "task_shape.py"
WAIT_HINT = ROOT / "scripts" / "wait_hint.py"


class WorkloadToolTests(unittest.TestCase):
    def test_task_shape_reports_dag_facts_without_assigning_workload(self) -> None:
        task = {
            "code": "TASK-001",
            "title": "Representative Task",
            "difficulty": "standard",
            "workload": "heavy",
            "nodes": [
                {"code": "NODE-001", "prerequisites": []},
                {"code": "NODE-002", "prerequisites": ["NODE-001"]},
                {"code": "NODE-003", "prerequisites": ["NODE-001"]},
                {"code": "NODE-004", "prerequisites": ["NODE-002", "NODE-003"]},
            ],
            "ownership": {"write_paths": ["one", "two"]},
            "outputs": [{"code": "OUT-001"}],
            "acceptance": [{"code": "AC-001"}, {"code": "AC-002"}],
            "focused_regression": {"commands": ["first", "second", "third"]},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "task.json"
            path.write_text(json.dumps(task), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(TASK_SHAPE), str(path)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        shape = json.loads(result.stdout)["tasks"][0]
        self.assertEqual(shape["workload"], "heavy")
        self.assertEqual(shape["node_count"], 4)
        self.assertEqual(shape["critical_path_nodes"], 3)
        self.assertEqual(shape["max_parallel_frontier"], 2)
        self.assertEqual(shape["write_path_count"], 2)
        self.assertEqual(shape["acceptance_count"], 2)
        self.assertEqual(shape["verification_command_count"], 3)

    def test_wait_hint_combines_agent_judgment_and_prior_durations(self) -> None:
        hint = wait_hint(
            workload="heavy",
            elapsed=1800,
            progress=50,
            prior_total=4000,
            history=[3600, 4400],
        )

        self.assertEqual(hint["estimated_total_seconds"], 4000)
        self.assertEqual(hint["estimated_remaining_seconds"], 2200)
        self.assertEqual(hint["suggested_next_check_seconds"], 660)
        self.assertEqual(hint["estimate_sources_seconds"]["progress_projection"], 3600)

    def test_wait_hint_cli_is_read_only_json_calculation(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(WAIT_HINT),
                "--workload", "light",
                "--elapsed", "600",
                "--progress", "25",
                "--history", "2400",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        hint = json.loads(result.stdout)
        self.assertEqual(hint["estimated_total_seconds"], 2400)
        self.assertEqual(hint["estimated_remaining_seconds"], 1800)
        self.assertEqual(hint["suggested_next_check_seconds"], 270)


if __name__ == "__main__":
    unittest.main()
