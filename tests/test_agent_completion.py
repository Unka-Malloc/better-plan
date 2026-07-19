from __future__ import annotations

import json
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_TOOL = ROOT / "scripts" / "manifest_tool.py"
HOOK_TOOL = ROOT / "scripts" / "hook_tool.py"
PLAN_ID = "718a7541-4e80-46ce-9acc-e77a68d1f406"
NODE_ID = "4ec7bbc3-88af-4df8-ad4f-468550bdc4c1"


def command(*values: str) -> str:
    arguments = list(values)
    return subprocess.list2cmdline(arguments) if sys.platform == "win32" else shlex.join(arguments)


class AgentCompletionHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / "project"
        self.project.mkdir()
        (self.project / ".git").mkdir()
        self.workspace = self.project / "docs" / "plan"
        self.plan_dir = self.workspace / "agent-completion"
        self.plan_dir.mkdir(parents=True)
        self.checkpoints = self.plan_dir / "Checkpoints.json"
        (self.project / "tracked.txt").write_text("stable\n", encoding="utf-8")
        fixtures = self.project / "tests" / "agent-completion"
        fixtures.mkdir(parents=True)
        (fixtures / "design.md").write_text("design\n", encoding="utf-8")
        (fixtures / "scaffold.py").write_text("VALUE = 1\n", encoding="utf-8")
        (fixtures / "acceptance.md").write_text("acceptance\n", encoding="utf-8")
        self._write_workspace(failing=False)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write_workspace(self, *, failing: bool) -> None:
        regression = command(sys.executable, "-c", "import sys; sys.exit(7)" if failing else "pass")
        node = {
            "id": NODE_ID,
            "status": "pending",
            "role": "implementation",
            "prerequisites": [],
            "platform": "any",
            "difficulty": "high",
            "goal": "Exercise automatic Agent completion reduction.",
            "description": (
                "Scope: Closure: scenario - correlated Agent completion. Context: a leaf Agent "
                "has returned to its native parent. Target: run deterministic regression and "
                "route the next role. Design Considerations: one active Node and one dispatch. "
                "Design Value: Review begins without continuing a stopped child. Constraints & "
                "Risks: bounded context, no raw output, and no generic Stop continuation."
            ),
            "requirements": ["REQ-001"],
            "design": {
                "artifact": "tests/agent-completion/design.md",
                "owned_paths": ["tests/agent-completion/scaffold.py"],
                "scaffold_paths": ["tests/agent-completion/scaffold.py"],
                "acceptance_paths": ["tests/agent-completion/acceptance.md"],
                "symbols": [
                    {
                        "path": "tests/agent-completion/scaffold.py",
                        "kind": "module",
                        "name": "agent_completion_fixture",
                        "operation": "modify",
                        "signature": "agent_completion_fixture() -> int",
                    }
                ],
                "interfaces": [
                    {
                        "name": "agent_completion_fixture",
                        "producer": "tests/agent-completion/scaffold.py",
                        "consumers": ["scripts/hook_tool.py"],
                        "inputs": "one correlated Agent completion",
                        "outputs": "one bounded next action",
                        "errors": ["invalid state returns a no-op"],
                    }
                ],
                "dependencies": [
                    {
                        "from": "scripts/hook_tool.py",
                        "to": "tests/agent-completion/scaffold.py",
                        "reason": "exercises the completion boundary",
                    }
                ],
                "decisions": {
                    "composition": "one reducer after one Agent return",
                    "algorithms": "constant-time phase routing",
                    "data_structures": "bounded immutable directive",
                    "state": "manifest application owns writes",
                    "isolation": "one outstanding dispatch",
                    "concurrency": "serialized Node transitions",
                },
                "test_seams": ["tests/test_agent_completion.py"],
            },
            "acceptance_criteria": [
                {"checked": False, "text": "The correlated Agent completion selects Review safely."}
            ],
            "commit": {
                "repository": ".git",
                "message": "test: agent completion",
                "target": "agent completion fixture",
            },
            "regression": {
                "scope": "focused",
                "commands": [regression],
                "criteria": [0],
                "paths": ["tracked.txt"],
            },
            "next": [],
        }
        self.checkpoints.write_text(json.dumps([node]), encoding="utf-8")
        manifest = [
            {
                "id": PLAN_ID,
                "status": "pending",
                "title": "Agent completion fixture",
                "directory": "agent-completion",
                "source_files": [],
                "goal": "Exercise automatic Agent completion reduction.",
                "description": "A complete temporary Better Plan workflow.",
                "checkpoints": "agent-completion/Checkpoints.json",
            }
        ]
        (self.workspace / "Manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def cli(self, *arguments: str) -> dict[str, object]:
        result = subprocess.run(
            [sys.executable, str(MANIFEST_TOOL), *arguments, str(self.workspace)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def state(self) -> dict[str, object]:
        return json.loads(self.checkpoints.read_text(encoding="utf-8"))[0]

    def dispatch(self, role: str) -> str:
        payload = self.cli("dispatch", NODE_ID, "--role", role)
        return str(payload["dispatch_id"])

    def advance(self, event: str, dispatch_id: str) -> None:
        self.cli("advance", NODE_ID, "--event", event, "--dispatch-id", dispatch_id)

    def prime_executor(self) -> None:
        self.cli("next-action", NODE_ID)
        designer = self.dispatch("acceptance_designer")
        self.advance("acceptance-designer-exited", designer)
        reviewer = self.dispatch("acceptance_reviewer")
        self.advance("acceptance-approved", reviewer)
        self.dispatch("executor")

    def run_completion_hook(self) -> dict[str, object]:
        result = subprocess.run(
            [
                sys.executable,
                str(HOOK_TOOL),
                "--agent",
                "codex",
                "--event",
                "agent-complete",
                "--managed-by",
                "better-plan",
            ],
            cwd=ROOT,
            input=json.dumps({"cwd": str(self.project), "tool_name": "spawn_agent"}),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_executor_completion_runs_regression_then_routes_review(self) -> None:
        self.prime_executor()

        response = self.run_completion_hook()

        self.assertEqual(self.state()["acceptance"]["phase"], "awaiting_auditor")
        context = response["hookSpecificOutput"]["additionalContext"]
        self.assertIn("action dispatch_auditor", context)
        self.assertIn("Focused regression passed", context)
        self.assertNotIn(str(self.project), context)
        self.assertEqual(self.run_completion_hook(), {})

    def test_first_regression_failure_returns_control_to_main(self) -> None:
        self._write_workspace(failing=True)
        self.prime_executor()

        response = self.run_completion_hook()

        self.assertEqual(self.state()["acceptance"]["phase"], "repair_required")
        self.assertIn(
            "action main_repair_decision",
            response["hookSpecificOutput"]["additionalContext"],
        )
        self.assertNotIn(
            "dispatch exactly one fresh repair executor",
            response["hookSpecificOutput"]["additionalContext"].lower(),
        )

    def test_auditor_completion_reports_to_main_without_deciding(self) -> None:
        self.prime_executor()
        self.run_completion_hook()
        self.dispatch("auditor")
        before = self.checkpoints.read_bytes()

        response = self.run_completion_hook()

        self.assertEqual(self.checkpoints.read_bytes(), before)
        self.assertEqual(self.state()["acceptance"]["phase"], "auditor_running")
        context = response["hookSpecificOutput"]["additionalContext"]
        self.assertIn("action main_audit_decision", context)
        self.assertIn("choose audit-passed, audit-failed for repair, or pause to defer", context)


if __name__ == "__main__":
    unittest.main()
