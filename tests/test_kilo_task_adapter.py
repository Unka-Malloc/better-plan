"""Kilo's namespaced Task roles and opaque child IDs at the CLI boundary."""

from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

from scripts.better_plan.adapters.manifest_cli import build_parser
from tests.v3_fixtures import draft_plan, task, write_workspace


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "scripts" / "manifest_tool.py"
PLAN = "PLAN-001"


class KiloTaskAdapterTests(unittest.TestCase):
    def test_host_option_is_available_on_all_role_dispatch_commands(self) -> None:
        parser = build_parser()
        for command, prefix in (
            ("open-designer-session", []),
            ("dispatch-task", ["TASK-001"]),
            ("open-reviewer-session", []),
        ):
            with self.subTest(command=command):
                args = parser.parse_args([command, *prefix, "--plan", PLAN, "--native-host", "kilo"])
                self.assertEqual(args.native_host, "kilo")

    def test_role_dispatches_bind_and_complete_exact_kilo_task_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = draft_plan()
            plan["spec"]["tasks"].append(
                task("TASK-002", write_paths=["second.txt"], acceptance_code="AC-002")
            )
            # A hybrid Task must reach the namespaced hybrid Worker, not the code Worker.
            plan["spec"]["requirements"].append({
                "code": "REQ-002",
                "statement": "The rendered view matches the authorized design.",
                "source_refs": ["user-request"],
            })
            plan["spec"]["tasks"].append(task(
                "TASK-003", write_paths=["view.py"], requirements=["REQ-002"],
                worker="hybrid", verification="hybrid", acceptance_code="AC-003",
            ))
            write_workspace(root, plan)

            def call(command: str, *arguments: str) -> dict:
                positional = arguments[:1] if command in {"dispatch-task", "accept-task"} else ()
                options = arguments[1:] if positional else arguments
                result = subprocess.run(
                    [sys.executable, str(TOOL), command, *positional, str(root), "--plan", PLAN, *options],
                    cwd=ROOT, capture_output=True, text=True, check=True,
                )
                return json.loads(result.stdout)

            def role(command: str, arguments: tuple[str, ...], expected: str, task_id: str, target: str) -> str:
                dispatched = call(command, *arguments, "--native-host", "kilo")
                self.assertTrue((ROOT / "agents" / "kilo" / f"{expected}.md").is_file())
                self.assertEqual(dispatched["agent_type"], expected)
                self.assertNotIn("model", dispatched)
                self.assertNotIn("reasoning_effort", dispatched)
                self.assertNotIn("main_thread_fallback", dispatched)
                dispatch_id = dispatched["dispatch_id"]
                # The target is positional; Kilo's returned task_id is passed
                # unchanged to both binding and final callback correlation.
                subprocess.run(
                    [sys.executable, str(TOOL), "bind-agent", target, str(root), "--plan", PLAN,
                     "--dispatch-id", dispatch_id, "--agent-id", task_id],
                    cwd=ROOT, capture_output=True, text=True, check=True,
                )
                completed = call("agent-complete", "--agent-id", task_id, "--final")
                self.assertTrue(completed["consumed"])
                self.assertFalse(call("agent-complete", "--agent-id", task_id, "--final")["consumed"])
                return dispatch_id

            designer_id = role(
                "open-designer-session", (), "better-plan-designer", "task_designer-opaque.01", PLAN,
            )
            call("close-designer-session", "--dispatch-id", designer_id)
            call("authorize-plan", "--source", "explicit", "--reference", "fixture-authorization")

            for code, expected, task_id in (
                ("TASK-001", "better-plan-worker", "task_worker_opaque.02"),
                ("TASK-002", "better-plan-worker", "task_worker_opaque.03"),
                ("TASK-003", "better-plan-hybrid-worker", "task_hybrid_opaque.04"),
            ):
                with self.subTest(role=expected):
                    role("dispatch-task", (code,), expected, task_id, code)
                    self.assertTrue(call("accept-task", code)["accepted"])

            self.assertTrue(call("run-full-regression")["passed"])
            reviewer_id = role(
                "open-reviewer-session", (), "better-plan-reviewer", "task_reviewer-opaque.04", PLAN,
            )
            result = subprocess.run(
                [sys.executable, str(TOOL), "record-reviewer-findings", str(root), "--plan", PLAN,
                 "--dispatch-id", reviewer_id, "--input", "-"],
                input="[]", cwd=ROOT, capture_output=True, text=True, check=True,
            )
            self.assertEqual(json.loads(result.stdout)["recorded"], 0)
            self.assertTrue(call("close-reviewer-session", "--dispatch-id", reviewer_id)["completed"])


if __name__ == "__main__":
    unittest.main()
