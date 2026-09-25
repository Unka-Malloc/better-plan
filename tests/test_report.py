"""HTML report projection over live workspace state."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from unittest import mock
import json
import re
import sys
import tempfile
import unittest

from scripts.better_plan.adapters import manifest_cli
from scripts.better_plan.adapters.manifest_cli import report_command
from scripts.better_plan.domain.models import CHECKPOINTS_SCHEMA
from scripts.better_plan.domain.report import DATA_MARKER, render_report_html
from scripts.better_plan.infrastructure.workspace import write_json
from tests.v3_fixtures import complete_plan, draft_plan, write_workspace


PAYLOAD_PATTERN = re.compile(
    r'<script id="bp-data" type="application/json">(.*?)</script>', re.DOTALL
)


def extract_payload(html: str) -> dict:
    match = PAYLOAD_PATTERN.search(html)
    assert match, "report must embed exactly one payload block"
    return json.loads(match.group(1))


class ReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.out = self.root / "report.html"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_report(self, *extra: str) -> str:
        result = report_command(
            Namespace(root=str(self.root), plan=extra[0] if extra else None, out=str(self.out))
        )
        self.assertEqual(result, 0)
        return self.out.read_text(encoding="utf-8")

    def write_checkpoints(self) -> None:
        write_json(
            self.root / "delivery" / "Checkpoints.json",
            {
                "schema": CHECKPOINTS_SCHEMA,
                "plan": "PLAN-001",
                "revision": 1,
                "semantic_digest": "0" * 64,
                "delivery_status": "in_progress",
                "full_regression": None,
                "tasks": [
                    {
                        "code": "TASK-001",
                        "status": "in_progress",
                        "dispatch": {
                            "id": "dispatch-1",
                            "role": "worker",
                            "attempts": 1,
                            "host_agent_id": None,
                            "selector": {},
                            "main_thread_fallback": False,
                            "phase": "worker_running",
                        },
                        "evidence": [],
                    }
                ],
            },
        )

    def test_report_embeds_plan_and_paired_checkpoints(self) -> None:
        write_workspace(self.root, complete_plan())
        self.write_checkpoints()

        html = self.run_report()

        self.assertNotIn(DATA_MARKER, html)
        payload = extract_payload(html)
        self.assertEqual(payload["schema"], "better-plan.report/v3")
        self.assertEqual(len(payload["plans"]), 1)
        self.assertEqual(payload["plans"][0]["plan"]["code"], "PLAN-001")
        checkpoints = payload["plans"][0]["checkpoints"]
        self.assertEqual(checkpoints["delivery_status"], "in_progress")
        self.assertEqual(checkpoints["tasks"][0]["dispatch"]["phase"], "worker_running")

    def test_report_tolerates_missing_checkpoints(self) -> None:
        write_workspace(self.root, draft_plan())

        html = self.run_report()

        payload = extract_payload(html)
        self.assertEqual(payload["plans"][0]["plan"]["phase"], "draft")
        self.assertIsNone(payload["plans"][0]["checkpoints"])

    def test_embedded_payload_cannot_break_out_of_its_script_tag(self) -> None:
        payload = {"schema": "better-plan.report/v3", "plans": [], "title": "x</script><script>alert(1)</script>"}

        html = render_report_html(payload, '<script id="bp-data" type="application/json">%s</script>' % DATA_MARKER)

        self.assertIn("\\u003c/script>", html)
        self.assertEqual(extract_payload(html), payload)


INIT_PLAN_ARGV = [
    "manifest_tool.py",
    "init-plan",
    "--code", "PLAN-001",
    "--title", "Bounded delivery",
    "--directory", "delivery",
    "--goal", "One observable outcome",
    "--scope-in", "The bounded capability",
    "--scope-out", "Unrelated work",
    "--success", "The behavior is observable",
    "--risk-boundary", "No irreversible side effects",
]


class AutoReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_cli(self, *argv: str) -> int:
        with mock.patch.object(sys, "argv", list(argv)):
            return manifest_cli.main()

    def test_state_changing_command_writes_the_plan_report_projection(self) -> None:
        result = self.run_cli(*INIT_PLAN_ARGV, str(self.root))

        self.assertEqual(result, 0)
        report = self.root / "delivery" / "Report.html"
        self.assertTrue(report.is_file())
        payload = extract_payload(report.read_text(encoding="utf-8"))
        self.assertEqual(len(payload["plans"]), 1)
        self.assertEqual(payload["plans"][0]["plan"]["code"], "PLAN-001")
        self.assertIsNone(payload["plans"][0]["checkpoints"])

    def test_projection_failure_never_breaks_the_state_changing_command(self) -> None:
        with mock.patch(
            "scripts.better_plan.adapters.manifest_cli.load_template",
            side_effect=OSError("template gone"),
        ):
            result = self.run_cli(*INIT_PLAN_ARGV, str(self.root))

        self.assertEqual(result, 0)
        self.assertFalse((self.root / "delivery" / "Report.html").exists())
        self.assertTrue((self.root / "delivery" / "Plan.json").is_file())

    def test_inspection_commands_do_not_write_a_projection(self) -> None:
        self.run_cli(*INIT_PLAN_ARGV, str(self.root))
        report = self.root / "delivery" / "Report.html"
        report.unlink()

        self.assertEqual(self.run_cli("manifest_tool.py", "status", str(self.root)), 0)
        self.assertFalse(report.exists())


if __name__ == "__main__":
    unittest.main()
