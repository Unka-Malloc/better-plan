from __future__ import annotations

import hashlib
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
            self.assertIn(f"node {NODE_ID} is already in_progress", blocked_start.stderr)
            self.assertIn("pause", blocked_start.stderr)

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

    def test_pause_yields_the_in_progress_node(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_workspace(
                root,
                plan_status="pending",
                nodes=[
                    checkpoint_node(NODE_ID, status="pending", checked=False),
                    checkpoint_node(SECOND_NODE_ID, status="pending"),
                ],
            )

            start = run_command(sys.executable, PYTHON_TOOL, "start", NODE_ID, tmpdir)
            self.assertEqual(start.returncode, 0, start.stderr)

            pause = run_command(
                sys.executable, PYTHON_TOOL, "pause", NODE_ID, tmpdir, "--reason", "yielding to an urgent insert"
            )
            self.assertEqual(pause.returncode, 0, pause.stderr)
            self.assertIn(f"OK: node {NODE_ID} in_progress -> pending", pause.stdout)

            nodes = read_nodes(root)
            self.assertEqual(nodes[0]["status"], "pending")
            self.assertEqual(nodes[0]["status_reason"], "yielding to an urgent insert")

            start_second = run_command(sys.executable, PYTHON_TOOL, "start", SECOND_NODE_ID, tmpdir)
            self.assertEqual(start_second.returncode, 0, start_second.stderr)

            resume_paused = run_command(sys.executable, PYTHON_TOOL, "start", NODE_ID, tmpdir)
            self.assertNotEqual(resume_paused.returncode, 0, resume_paused.stdout)
            self.assertIn(f"node {SECOND_NODE_ID} is already in_progress", resume_paused.stderr)

    def test_pause_requires_an_in_progress_node(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            write_workspace(Path(tmpdir), plan_status="pending", nodes=[checkpoint_node(NODE_ID, status="pending")])

            result = run_command(sys.executable, PYTHON_TOOL, "pause", NODE_ID, tmpdir)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("requires an 'in_progress' node", result.stderr)

    def test_swapped_node_and_root_arguments_get_a_usage_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            write_workspace(Path(tmpdir), plan_status="pending", nodes=[checkpoint_node(NODE_ID, status="pending")])

            result = run_command(sys.executable, PYTHON_TOOL, "start", tmpdir, NODE_ID)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("looks like a node UUID", result.stderr)
        self.assertIn("<command> <node-id> [root]", result.stderr)

    def test_add_node_splices_into_the_chain(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_workspace(
                root,
                plan_status="in_progress",
                nodes=[
                    checkpoint_node(NODE_ID, status="completed", next_refs=[SECOND_NODE_ID]),
                    checkpoint_node(SECOND_NODE_ID, status="pending", prerequisites=[NODE_ID]),
                ],
            )

            result = run_command(
                sys.executable,
                PYTHON_TOOL,
                "add-node",
                tmpdir,
                "--plan",
                "main-plan",
                "--after",
                NODE_ID,
                "--splice",
                "--goal",
                "Insert a follow-up task between the chain nodes.",
                "--description",
                "Scope: main-plan checkpoints. Context: inserted by the add-node CLI test. Target: sit between both nodes.",
                "--requirements",
                "REQ-001",
                "--criterion",
                "The spliced node validates.",
                "--commit-message",
                "test add-node",
                "--commit-target",
                "tests",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            nodes = read_nodes(root)

        self.assertEqual(len(nodes), 3)
        inserted = nodes[1]
        self.assertEqual(inserted["status"], "pending")
        self.assertEqual(inserted["prerequisites"], [NODE_ID])
        self.assertEqual(inserted["next"], [SECOND_NODE_ID])
        self.assertEqual(nodes[0]["next"], [inserted["id"]])
        self.assertEqual(nodes[2]["prerequisites"], [inserted["id"]])
        self.assertIn("downstream prerequisites rewired", result.stdout)

    def test_add_node_rejects_forward_prerequisites(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_workspace(
                root,
                plan_status="pending",
                nodes=[checkpoint_node(NODE_ID, status="pending")],
            )

            result = run_command(
                sys.executable,
                PYTHON_TOOL,
                "add-node",
                tmpdir,
                "--plan",
                "main-plan",
                "--before",
                NODE_ID,
                "--prerequisites",
                NODE_ID,
                "--goal",
                "Break the topology on purpose.",
                "--description",
                "Scope: enabling test fixture for validated insertion.",
                "--criterion",
                "Never written.",
                "--commit-message",
                "test add-node",
                "--commit-target",
                "tests",
            )

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("must reference an earlier node id", result.stderr)
            self.assertEqual(len(read_nodes(root)), 1)

    def test_rewire_replaces_and_edits_edges(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_workspace(
                root,
                plan_status="in_progress",
                nodes=[
                    checkpoint_node(NODE_ID, status="completed"),
                    checkpoint_node(SECOND_NODE_ID, status="completed"),
                    checkpoint_node(THIRD_NODE_ID, status="pending", prerequisites=[NODE_ID]),
                ],
            )

            replace = run_command(
                sys.executable,
                PYTHON_TOOL,
                "rewire",
                THIRD_NODE_ID,
                tmpdir,
                "--prerequisites",
                f"{NODE_ID},{SECOND_NODE_ID}",
            )
            self.assertEqual(replace.returncode, 0, replace.stderr)
            self.assertEqual(read_nodes(root)[2]["prerequisites"], [NODE_ID, SECOND_NODE_ID])

            incremental = run_command(
                sys.executable,
                PYTHON_TOOL,
                "rewire",
                NODE_ID,
                tmpdir,
                "--add-next",
                THIRD_NODE_ID,
            )
            self.assertEqual(incremental.returncode, 0, incremental.stderr)
            self.assertEqual(read_nodes(root)[0]["next"], [THIRD_NODE_ID])

            missing_removal = run_command(
                sys.executable,
                PYTHON_TOOL,
                "rewire",
                NODE_ID,
                tmpdir,
                "--remove-prerequisite",
                SECOND_NODE_ID,
            )
            self.assertNotEqual(missing_removal.returncode, 0, missing_removal.stdout)
            self.assertIn("it is not present", missing_removal.stderr)

    def test_edit_node_guards_terminal_nodes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_workspace(root, plan_status="completed", nodes=[checkpoint_node(NODE_ID, status="completed")])

            rejected = run_command(
                sys.executable, PYTHON_TOOL, "edit-node", NODE_ID, tmpdir, "--goal", "Rewrite history."
            )
            self.assertNotEqual(rejected.returncode, 0, rejected.stdout)
            self.assertIn("historical snapshots", rejected.stderr)

            backfill = run_command(
                sys.executable, PYTHON_TOOL, "edit-node", NODE_ID, tmpdir, "--add-requirement", "REQ-002"
            )
            self.assertEqual(backfill.returncode, 0, backfill.stderr)
            self.assertEqual(read_nodes(root)[0]["requirements"], ["REQ-001", "REQ-002"])

    def test_edit_node_updates_pending_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_workspace(root, plan_status="pending", nodes=[checkpoint_node(NODE_ID, status="pending")])

            result = run_command(
                sys.executable,
                PYTHON_TOOL,
                "edit-node",
                NODE_ID,
                tmpdir,
                "--goal",
                "Refined goal.",
                "--difficulty",
                "high",
                "--add-criterion",
                "A second concrete check.",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            node = read_nodes(root)[0]

        self.assertEqual(node["goal"], "Refined goal.")
        self.assertEqual(node["difficulty"], "high")
        self.assertEqual(node["acceptance_criteria"][1], {"checked": False, "text": "A second concrete check."})

    def test_check_records_structured_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_workspace(root, plan_status="pending", nodes=[checkpoint_node(NODE_ID, status="pending", checked=False)])
            evidence_file = root / "report.txt"
            evidence_file.write_text("verification report\n", encoding="utf-8")
            expected_sha = hashlib.sha256(evidence_file.read_bytes()).hexdigest()

            start = run_command(sys.executable, PYTHON_TOOL, "start", NODE_ID, tmpdir)
            self.assertEqual(start.returncode, 0, start.stderr)

            passing = run_command(
                sys.executable,
                PYTHON_TOOL,
                "check",
                NODE_ID,
                tmpdir,
                "--criterion",
                "0",
                "--evidence",
                "structured evidence recorded",
                "--evidence-file",
                str(evidence_file),
                "--evidence-cmd",
                f'"{sys.executable}" -c "import sys; sys.exit(0)"',
            )
            self.assertEqual(passing.returncode, 0, passing.stderr)
            self.assertIn("2 evidence reference(s)", passing.stdout)

            criterion = read_nodes(root)[0]["acceptance_criteria"][0]
            self.assertTrue(criterion["checked"])
            refs = criterion["evidence_refs"]
            self.assertEqual(len(refs), 2)
            self.assertEqual(refs[0]["type"], "command")
            self.assertEqual(refs[0]["exit_code"], 0)
            self.assertEqual(refs[1]["type"], "file")
            self.assertEqual(refs[1]["sha256"], expected_sha)

            validate = run_command(sys.executable, PYTHON_TOOL, "validate", tmpdir, "--no-git")
            self.assertEqual(validate.returncode, 0, validate.stderr)

    def test_check_refuses_failing_evidence_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_workspace(root, plan_status="pending", nodes=[checkpoint_node(NODE_ID, status="pending", checked=False)])

            start = run_command(sys.executable, PYTHON_TOOL, "start", NODE_ID, tmpdir)
            self.assertEqual(start.returncode, 0, start.stderr)

            failing = run_command(
                sys.executable,
                PYTHON_TOOL,
                "check",
                NODE_ID,
                tmpdir,
                "--criterion",
                "0",
                "--evidence-cmd",
                f'"{sys.executable}" -c "import sys; sys.exit(3)"',
            )

            self.assertNotEqual(failing.returncode, 0, failing.stdout)
            self.assertIn("exited with 3", failing.stderr)
            self.assertFalse(read_nodes(root)[0]["acceptance_criteria"][0]["checked"])

    def test_validate_plan_scopes_to_one_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            main_dir = root / "main-plan"
            broken_dir = root / "broken-plan"
            main_dir.mkdir(parents=True)
            broken_dir.mkdir(parents=True)
            (main_dir / "Checkpoints.json").write_text(json.dumps([checkpoint_node(NODE_ID)]), encoding="utf-8")
            broken_node = checkpoint_node(SECOND_NODE_ID, status="pending")
            broken_node["requirements"] = []
            (broken_dir / "Checkpoints.json").write_text(json.dumps([broken_node]), encoding="utf-8")
            (root / "Manifest.json").write_text(
                json.dumps(
                    [
                        plan_object("completed"),
                        {
                            "id": CHILD_PLAN_ID,
                            "status": "pending",
                            "title": "Broken Plan",
                            "directory": "broken-plan",
                            "source_files": [],
                            "goal": "Contain a deliberately invalid node.",
                            "description": "Sibling plan used to prove validation scoping.",
                            "checkpoints": "broken-plan/Checkpoints.json",
                        },
                    ]
                ),
                encoding="utf-8",
            )

            full = run_command(sys.executable, PYTHON_TOOL, "validate", tmpdir, "--no-git")
            scoped = run_command(sys.executable, PYTHON_TOOL, "validate", tmpdir, "--no-git", "--plan", "main-plan")
            scoped_by_title = run_command(sys.executable, PYTHON_TOOL, "validate", tmpdir, "--no-git", "--plan", "Broken Plan")

        self.assertNotEqual(full.returncode, 0, full.stdout)
        self.assertIn("must list at least one requirement label", full.stderr)
        self.assertEqual(scoped.returncode, 0, scoped.stderr)
        self.assertIn("OK: validated 2 state file(s)", scoped.stdout)
        self.assertNotEqual(scoped_by_title.returncode, 0, scoped_by_title.stdout)

    def test_validate_check_sources_flags_missing_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_workspace(root)
            plans = read_plans(root)
            plans[0]["source_files"] = [
                "docs/plan.md",
                "missing/never-written.md",
                "owner/repo:path/inside/external.md",
                "https://example.com/spec",
            ]
            (root / "Manifest.json").write_text(json.dumps(plans), encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs" / "plan.md").write_text("# source\n", encoding="utf-8")

            without_flag = run_command(sys.executable, PYTHON_TOOL, "validate", tmpdir, "--no-git")
            with_flag = run_command(sys.executable, PYTHON_TOOL, "validate", tmpdir, "--no-git", "--check-sources")

        self.assertEqual(without_flag.returncode, 0, without_flag.stderr)
        self.assertNotEqual(with_flag.returncode, 0, with_flag.stdout)
        self.assertIn("source_files[1]: not found", with_flag.stderr)
        self.assertNotIn("source_files[0]", with_flag.stderr)
        self.assertNotIn("source_files[2]", with_flag.stderr)
        self.assertNotIn("source_files[3]", with_flag.stderr)

    def test_check_labels_cross_checks_documents_and_nodes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_workspace(
                root,
                plan_status="in_progress",
                nodes=[
                    checkpoint_node(NODE_ID, status="completed"),
                    checkpoint_node(SECOND_NODE_ID, status="pending", prerequisites=[NODE_ID]),
                ],
            )
            nodes = read_nodes(root)
            nodes[1]["requirements"] = ["REQ-003"]
            (root / "main-plan" / "Checkpoints.json").write_text(json.dumps(nodes), encoding="utf-8")
            (root / "main-plan" / "Requirements.md").write_text(
                "# Requirements\n\n- REQ-001 delivered behavior\n- REQ-002 documented but not yet scheduled\n",
                encoding="utf-8",
            )

            failing = run_command(sys.executable, PYTHON_TOOL, "check-labels", tmpdir, "--json")
            payload = json.loads(failing.stdout)

            (root / "main-plan" / "Requirements.md").write_text(
                "# Requirements\n\n- REQ-001 delivered behavior\n- REQ-002 documented but not yet scheduled\n- REQ-003 follow-up behavior\n",
                encoding="utf-8",
            )
            passing = run_command(sys.executable, PYTHON_TOOL, "check-labels", tmpdir)

        self.assertNotEqual(failing.returncode, 0, failing.stdout)
        plan_payload = payload["plans"][0]
        self.assertEqual(list(plan_payload["undefined"].keys()), ["REQ-003"])
        self.assertEqual(plan_payload["uncovered"], ["REQ-002"])
        self.assertEqual(passing.returncode, 0, passing.stderr)
        self.assertIn("warning: label REQ-002", passing.stdout)
        self.assertIn("1 warning(s)", passing.stdout)

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
