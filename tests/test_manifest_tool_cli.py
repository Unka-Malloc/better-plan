from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_TOOL = REPO_ROOT / "scripts" / "manifest_tool.py"
UUID4_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


PLAN_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
CHILD_PLAN_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
NODE_ID = "11111111-1111-4111-8111-111111111111"
SECOND_NODE_ID = "22222222-2222-4222-8222-222222222222"
CHILD_NODE_ID = "33333333-3333-4333-8333-333333333333"
THIRD_NODE_ID = "44444444-4444-4444-8444-444444444444"
MISSING_NODE_ID = "55555555-5555-4555-8555-555555555555"


def current_platform() -> str:
    if sys.platform == "darwin":
        return "macos"
    if sys.platform in {"win32", "cygwin"}:
        return "windows"
    return "linux"


def other_platform() -> str:
    return "windows" if current_platform() != "windows" else "linux"


def run_command(*args: str | Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(arg) for arg in args],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def checkpoint_node(
    node_id: str,
    *,
    status: str = "completed",
    goal: str = "Validate the CLI happy path.",
    target: str = "tests",
    role: str = "implementation",
    prerequisites: list[str] | None = None,
    platform: str = "any",
    checked: bool = True,
    next_refs: list[str] | None = None,
    status_reason: str | None = None,
) -> dict[str, object]:
    node: dict[str, object] = {
        "id": node_id,
        "status": status,
        "role": role,
        "prerequisites": prerequisites or [],
        "platform": platform,
        "difficulty": "medium",
        "goal": goal,
        "description": "Minimal checkpoint node for CLI integration tests.",
        "requirements": ["REQ-001"],
        "acceptance_criteria": [
            {
                "checked": checked,
                "text": "The validator accepts the workspace.",
            }
        ],
        "commit": {
            "repository": ".git",
            "message": "test cli validation",
            "target": target,
        },
        "next": next_refs or [],
    }
    if status_reason is not None:
        node["status_reason"] = status_reason
    return node


def plan_object(plan_status: str) -> dict[str, object]:
    return {
        "id": PLAN_ID,
        "status": plan_status,
        "title": "Main Plan",
        "directory": "main-plan",
        "source_files": ["docs/plan.md"],
        "goal": "Validate the CLI happy path.",
        "description": "Minimal workspace for CLI integration tests.",
        "checkpoints": "main-plan/Checkpoints.json",
    }


def write_workspace(root: Path, *, plan_status: str = "completed", nodes: list[dict[str, object]] | None = None) -> None:
    plan_dir = root / "main-plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    if nodes is None:
        nodes = [checkpoint_node(NODE_ID)]
    (plan_dir / "Checkpoints.json").write_text(json.dumps(nodes), encoding="utf-8")
    (root / "Manifest.json").write_text(json.dumps([plan_object(plan_status)]), encoding="utf-8")


def read_nodes(root: Path) -> list[dict[str, object]]:
    return json.loads((root / "main-plan" / "Checkpoints.json").read_text(encoding="utf-8"))


def read_plans(root: Path) -> list[dict[str, object]]:
    return json.loads((root / "Manifest.json").read_text(encoding="utf-8"))


def write_hierarchical_workspace(root: Path) -> None:
    common_dir = root / "common"
    child_dir = common_dir / "a"
    child_dir.mkdir(parents=True)
    (common_dir / "Checkpoints.json").write_text(
        json.dumps([checkpoint_node(NODE_ID, goal="Validate a shared foundation plan.", target="common")]),
        encoding="utf-8",
    )
    (child_dir / "Checkpoints.json").write_text(
        json.dumps([checkpoint_node(CHILD_NODE_ID, goal="Validate a child business-line plan.", target="common/a")]),
        encoding="utf-8",
    )
    (root / "Manifest.json").write_text(
        json.dumps(
            [
                {
                    "id": PLAN_ID,
                    "status": "completed",
                    "title": "Common",
                    "directory": "common",
                    "source_files": ["docs/common-plan.md"],
                    "goal": "Validate a shared foundation plan.",
                    "description": "Parent plan for business-line child plans.",
                    "checkpoints": "common/Checkpoints.json",
                },
                {
                    "id": CHILD_PLAN_ID,
                    "status": "completed",
                    "title": "A",
                    "directory": "common/a",
                    "source_files": ["docs/a-plan.md"],
                    "goal": "Validate a child business-line plan.",
                    "description": "Child plan under the Common foundation.",
                    "checkpoints": "common/a/Checkpoints.json",
                },
            ]
        ),
        encoding="utf-8",
    )


class ManifestToolCliTests(unittest.TestCase):
    def test_python_validate_accepts_minimal_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            write_workspace(Path(tmpdir))

            result = run_command(sys.executable, PYTHON_TOOL, "validate", tmpdir)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OK: validated 2 state file(s), 2 item(s).", result.stdout)

    def test_python_validate_json_reports_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            write_workspace(Path(tmpdir))

            result = run_command(sys.executable, PYTHON_TOOL, "validate", tmpdir, "--json")

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["state_files"], 2)
        self.assertEqual(payload["issues"], [])

    def test_python_validate_accepts_hierarchical_plan_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            write_hierarchical_workspace(Path(tmpdir))

            result = run_command(sys.executable, PYTHON_TOOL, "validate", tmpdir)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OK: validated 3 state file(s), 4 item(s).", result.stdout)

    def test_python_discover_finds_structural_workspace_with_arbitrary_directory_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)
            workspace = project / "delivery-roadmap"
            workspace.mkdir()
            write_workspace(workspace)

            result = run_command(sys.executable, PYTHON_TOOL, "discover", project)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(workspace.resolve()), result.stdout.strip().splitlines())

    def test_python_discover_rejects_manifest_without_plan_checkpoints(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)
            workspace = project / "planning"
            workspace.mkdir()
            (workspace / "Manifest.json").write_text(
                json.dumps(
                    [
                        {
                            "id": PLAN_ID,
                            "status": "pending",
                            "title": "Incomplete",
                            "directory": "incomplete",
                            "source_files": [],
                            "goal": "Exercise structural discovery.",
                            "description": "Manifest without its plan-local checkpoint file.",
                            "checkpoints": "incomplete/Checkpoints.json",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            result = run_command(sys.executable, PYTHON_TOOL, "discover", project)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("No structurally valid Better Plan workspaces found", result.stderr)

    def test_python_validate_rejects_unknown_next_reference(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            write_workspace(Path(tmpdir), nodes=[checkpoint_node(NODE_ID, next_refs=[MISSING_NODE_ID])])

            result = run_command(sys.executable, PYTHON_TOOL, "validate", tmpdir)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("node[0].next: unknown node id", result.stderr)

    def test_python_transition_cli_reports_invalid_edge(self) -> None:
        result = run_command(sys.executable, PYTHON_TOOL, "transition", "completed", "in_progress")

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("cannot transition from 'completed' to 'in_progress'", result.stderr)

    def test_python_uuid_cli_outputs_uuid4_values(self) -> None:
        result = run_command(sys.executable, PYTHON_TOOL, "uuid", "--count", "2")

        self.assertEqual(result.returncode, 0, result.stderr)
        values = result.stdout.strip().splitlines()
        self.assertEqual(len(values), 2)
        self.assertTrue(all(UUID4_PATTERN.fullmatch(value) for value in values), values)

    def test_mutation_commands_drive_node_and_plan_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_workspace(
                root,
                plan_status="pending",
                nodes=[
                    checkpoint_node(NODE_ID, status="pending", checked=False),
                    checkpoint_node(SECOND_NODE_ID, status="pending", prerequisites=[NODE_ID]),
                ],
            )

            start = run_command(sys.executable, PYTHON_TOOL, "start", NODE_ID, tmpdir)
            self.assertEqual(start.returncode, 0, start.stderr)
            self.assertIn(f"OK: node {NODE_ID} pending -> in_progress", start.stdout)
            self.assertIn("OK: plan 'Main Plan' pending -> in_progress", start.stdout)

            blocked_start = run_command(sys.executable, PYTHON_TOOL, "start", SECOND_NODE_ID, tmpdir)
            self.assertNotEqual(blocked_start.returncode, 0, blocked_start.stdout)
            self.assertIn("refusing to write an invalid state file", blocked_start.stderr)

            early_complete = run_command(sys.executable, PYTHON_TOOL, "complete", NODE_ID, tmpdir)
            self.assertNotEqual(early_complete.returncode, 0, early_complete.stdout)
            self.assertIn("unchecked acceptance criteria", early_complete.stderr)

            check = run_command(
                sys.executable,
                PYTHON_TOOL,
                "check",
                NODE_ID,
                tmpdir,
                "--criterion",
                "0",
                "--evidence",
                "unit tests passed",
            )
            self.assertEqual(check.returncode, 0, check.stderr)

            complete = run_command(
                sys.executable, PYTHON_TOOL, "complete", NODE_ID, tmpdir, "--delivered", "abc1234"
            )
            self.assertEqual(complete.returncode, 0, complete.stderr)
            self.assertIn(f"OK: node {NODE_ID} in_progress -> completed", complete.stdout)

            start_second = run_command(sys.executable, PYTHON_TOOL, "start", SECOND_NODE_ID, tmpdir)
            self.assertEqual(start_second.returncode, 0, start_second.stderr)

            block = run_command(
                sys.executable, PYTHON_TOOL, "block", SECOND_NODE_ID, tmpdir, "--reason", "waiting on a user decision"
            )
            self.assertEqual(block.returncode, 0, block.stderr)
            self.assertIn("OK: plan 'Main Plan' in_progress -> blocked", block.stdout)

            resume = run_command(sys.executable, PYTHON_TOOL, "start", SECOND_NODE_ID, tmpdir)
            self.assertEqual(resume.returncode, 0, resume.stderr)

            skip = run_command(
                sys.executable, PYTHON_TOOL, "skip", SECOND_NODE_ID, tmpdir, "--reason", "deferred to a follow-up plan"
            )
            self.assertEqual(skip.returncode, 0, skip.stderr)
            self.assertIn("OK: plan 'Main Plan' in_progress -> completed", skip.stdout)

            nodes = read_nodes(root)
            self.assertEqual(nodes[0]["status"], "completed")
            self.assertEqual(nodes[0]["commit"]["delivered"], "abc1234")
            self.assertEqual(nodes[0]["acceptance_criteria"][0]["checked"], True)
            self.assertEqual(nodes[0]["acceptance_criteria"][0]["evidence"], "unit tests passed")
            self.assertNotIn("status_reason", nodes[0])
            self.assertEqual(nodes[1]["status"], "skipped")
            self.assertEqual(nodes[1]["status_reason"], "deferred to a follow-up plan")
            self.assertEqual(read_plans(root)[0]["status"], "completed")

            restart = run_command(sys.executable, PYTHON_TOOL, "start", NODE_ID, tmpdir)
            self.assertNotEqual(restart.returncode, 0, restart.stdout)
            self.assertIn("cannot transition from 'completed' to 'in_progress'", restart.stderr)

    def test_block_requires_reason_argument(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            write_workspace(Path(tmpdir), plan_status="pending", nodes=[checkpoint_node(NODE_ID, status="pending")])

            result = run_command(sys.executable, PYTHON_TOOL, "block", NODE_ID, tmpdir)

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("--reason", result.stderr)

    def test_sync_plan_re_derives_plan_status_from_nodes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_workspace(root, plan_status="pending", nodes=[checkpoint_node(NODE_ID, status="completed")])

            result = run_command(sys.executable, PYTHON_TOOL, "sync-plan", tmpdir)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("OK: plan 'Main Plan' pending -> completed", result.stdout)
            self.assertEqual(read_plans(root)[0]["status"], "completed")

            unchanged = run_command(sys.executable, PYTHON_TOOL, "sync-plan", tmpdir)
            self.assertEqual(unchanged.returncode, 0, unchanged.stderr)
            self.assertIn("already in sync", unchanged.stdout)

    def test_status_reports_progress_counts_and_blocked_reasons(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            write_workspace(
                Path(tmpdir),
                plan_status="blocked",
                nodes=[
                    checkpoint_node(NODE_ID, status="completed"),
                    checkpoint_node(
                        SECOND_NODE_ID,
                        status="blocked",
                        prerequisites=[NODE_ID],
                        status_reason="waiting on credentials",
                    ),
                ],
            )

            result = run_command(sys.executable, PYTHON_TOOL, "status", tmpdir, "--json")

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        plan = payload["plans"][0]
        self.assertEqual(plan["status"], "blocked")
        self.assertEqual(plan["nodes"], 2)
        self.assertEqual(plan["counts"]["completed"], 1)
        self.assertEqual(plan["counts"]["blocked"], 1)
        self.assertEqual(plan["blocked"][0]["status_reason"], "waiting on credentials")

    def test_next_lists_eligible_nodes_for_current_platform(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            write_workspace(
                Path(tmpdir),
                plan_status="in_progress",
                nodes=[
                    checkpoint_node(NODE_ID, status="completed"),
                    checkpoint_node(SECOND_NODE_ID, status="pending", prerequisites=[NODE_ID]),
                    checkpoint_node(THIRD_NODE_ID, status="pending", platform=other_platform()),
                ],
            )

            result = run_command(sys.executable, PYTHON_TOOL, "next", tmpdir, "--json")

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["platform"], current_platform())
        plan = payload["plans"][0]
        self.assertIsNone(plan["resume"])
        eligible_ids = [entry["id"] for entry in plan["eligible"]]
        self.assertEqual(eligible_ids, [SECOND_NODE_ID])

    def test_next_prefers_resuming_the_in_progress_node(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            write_workspace(
                Path(tmpdir),
                plan_status="in_progress",
                nodes=[
                    checkpoint_node(NODE_ID, status="in_progress"),
                    checkpoint_node(SECOND_NODE_ID, status="pending"),
                ],
            )

            result = run_command(sys.executable, PYTHON_TOOL, "next", tmpdir, "--json")

        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)["plans"][0]
        self.assertEqual(plan["resume"]["id"], NODE_ID)
        self.assertEqual(plan["eligible"], [])

    def test_schema_command_prints_canonical_shapes(self) -> None:
        node_result = run_command(sys.executable, PYTHON_TOOL, "schema", "node")
        plan_result = run_command(sys.executable, PYTHON_TOOL, "schema", "plan")

        self.assertEqual(node_result.returncode, 0, node_result.stderr)
        node_schema = json.loads(node_result.stdout)
        self.assertIn("commit", node_schema["required_fields"])
        self.assertIn("requirements", node_schema["optional_fields"])
        self.assertIn("status_reason", node_schema["optional_fields"])
        self.assertIn("any", node_schema["platforms"])

        self.assertEqual(plan_result.returncode, 0, plan_result.stderr)
        plan_schema = json.loads(plan_result.stdout)
        self.assertIn("checkpoints", plan_schema["required_fields"])

    @unittest.skipUnless(shutil.which("git"), "git is required for transition history validation")
    def test_validate_rejects_illegal_transitions_against_git_head(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_workspace(root, plan_status="completed", nodes=[checkpoint_node(NODE_ID, status="completed")])
            subprocess.run(["git", "init", "--quiet", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(root),
                    "-c",
                    "user.email=test@example.com",
                    "-c",
                    "user.name=Better Plan Tests",
                    "commit",
                    "--quiet",
                    "-m",
                    "snapshot",
                ],
                check=True,
            )
            write_workspace(root, plan_status="in_progress", nodes=[checkpoint_node(NODE_ID, status="in_progress")])

            result = run_command(sys.executable, PYTHON_TOOL, "validate", tmpdir)
            no_git = run_command(sys.executable, PYTHON_TOOL, "validate", tmpdir, "--no-git")

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("cannot change from 'completed' (git HEAD) to 'in_progress'", result.stderr)
        self.assertEqual(no_git.returncode, 0, no_git.stderr)


if __name__ == "__main__":
    unittest.main()
