from __future__ import annotations

import hashlib
import json
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.better_plan.domain import models
from scripts.better_plan.infrastructure import workspace


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_TOOL = REPO_ROOT / "scripts" / "manifest_tool.py"
UUID4_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
OPAQUE_EVENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


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


def command_line(*values: str) -> str:
    arguments = list(values)
    return subprocess.list2cmdline(arguments) if sys.platform == "win32" else shlex.join(arguments)


def passing_regression_command() -> str:
    values = [sys.executable, "-c", "pass"]
    return command_line(*values)


def marker_regression_command(marker: str = "regression-runs.txt") -> str:
    script = (
        "from pathlib import Path; "
        f"path = Path({marker!r}); "
        "previous = path.read_text(encoding='utf-8') if path.exists() else ''; "
        "path.write_text(previous + 'run\\n', encoding='utf-8')"
    )
    return command_line(sys.executable, "-c", script)


def absolute_summary_tokens(root: Path) -> list[tuple[str, str]]:
    segment = root.name
    return [
        ("posix-root", "/"),
        ("posix-double-root", "//"),
        ("home-root", "~/"),
        ("drive-backslash-root", "C:\\"),
        ("drive-slash-root", "C:/"),
        ("unc-root", "\\\\"),
        ("posix", str(root / "private-artifact.txt")),
        ("posix-double-root-path", f"/{root / 'private-artifact.txt'}"),
        ("home", f"~/{segment}/private-artifact.txt"),
        ("drive-backslash", f"C:\\{segment}\\private-artifact.txt"),
        ("drive-slash", f"C:/{segment}/private-artifact.txt"),
        ("unc", f"\\\\{segment}\\share\\private-artifact.txt"),
        ("unc-forward-slash", f"//{segment}/share/private-artifact.txt"),
    ]


def default_acceptance_design(fixture_name: str = "acceptance-fixture") -> dict[str, object]:
    fixture_root = f"tests/{fixture_name}"
    return {
        "artifact": f"{fixture_root}/design.md",
        "owned_paths": [f"{fixture_root}/scaffold.py"],
        "scaffold_paths": [f"{fixture_root}/scaffold.py"],
        "acceptance_paths": [f"{fixture_root}/acceptance.md"],
        "symbols": [
            {
                "path": f"{fixture_root}/scaffold.py",
                "kind": "module",
                "name": "acceptance_scaffold",
                "operation": "modify",
                "signature": "acceptance_scaffold(state: object) -> str",
            }
        ],
        "interfaces": [
            {
                "name": "acceptance_scaffold",
                "producer": f"{fixture_root}/scaffold.py",
                "consumers": ["scripts/manifest_tool.py"],
                "inputs": "validated node and plan payload",
                "outputs": "next action and acceptance state",
                "errors": ["ValueError for malformed state"],
            }
        ],
        "dependencies": [],
        "decisions": {
            "composition": "pure boundaries",
            "algorithms": "constant-time transition lookup",
            "data_structures": "normalized mappings",
            "state": "state file writer only",
            "isolation": "role-specific artifacts only",
            "concurrency": "serialized node mutation",
        },
        "test_seams": ["tests/acceptance-state-machine"],
    }


def write_design_artifacts(root: Path, design: dict[str, object]) -> None:
    path_entries = {str(design["artifact"])}
    path_entries.update(str(path) for path in design.get("owned_paths", []))
    path_entries.update(str(path) for path in design.get("scaffold_paths", []))
    path_entries.update(str(path) for path in design.get("acceptance_paths", []))
    fallback_content = {
        "design.md": "design",
        "acceptance.md": "cases",
        "scaffold.py": "pass\n",
    }
    for value in sorted(path_entries):
        if not value:
            continue
        target = root / value
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            continue
        target.write_text(fallback_content.get(target.name, "test fixture\n"), encoding="utf-8")


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
        "difficulty": (
            "deep"
            if role in {
                "product_requirements",
                "evidence",
                "validation_matrix",
                "architecture_scaffold",
                "final_validation",
            }
            else "medium"
        ),
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
    scope = "focused" if role == "implementation" else "full" if role == "final_validation" else None
    if scope is not None:
        node["regression"] = {
            "scope": scope,
            "commands": [passing_regression_command()],
            "criteria": [0],
            "paths": ["tracked.txt"],
        }
    if role in {"implementation", "final_validation"} and status not in {"completed", "skipped"}:
        node["design"] = default_acceptance_design()
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
    for node in nodes:
        if "design" in node:
            write_design_artifacts(root, dict(node["design"]))
    (root / "tracked.txt").write_text("stable\n", encoding="utf-8")
    (plan_dir / "Checkpoints.json").write_text(json.dumps(nodes), encoding="utf-8")
    (root / "Manifest.json").write_text(json.dumps([plan_object(plan_status)]), encoding="utf-8")


def read_nodes(root: Path) -> list[dict[str, object]]:
    return json.loads((root / "main-plan" / "Checkpoints.json").read_text(encoding="utf-8"))


def read_plans(root: Path) -> list[dict[str, object]]:
    return json.loads((root / "Manifest.json").read_text(encoding="utf-8"))


def serialized_node_bytes(root: Path, node_id: str) -> bytes:
    node = next(item for item in read_nodes(root) if item["id"] == node_id)
    return json.dumps(node, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def prepare_node_with_acceptance(root: Path, node_id: str = NODE_ID) -> str:
    designer = run_command(
        sys.executable,
        PYTHON_TOOL,
        "dispatch",
        node_id,
        str(root),
        "--role",
        "acceptance_designer",
    )
    if designer.returncode != 0:
        raise AssertionError(f"dispatch acceptance_designer failed: {designer.stderr or designer.stdout}")

    designer_id = json.loads(designer.stdout)["dispatch_id"]
    designer_exit = run_command(
        sys.executable,
        PYTHON_TOOL,
        "advance",
        node_id,
        str(root),
        "--event",
        "acceptance-designer-exited",
        "--dispatch-id",
        designer_id,
    )
    if designer_exit.returncode != 0:
        raise AssertionError(f"acceptance-designer-exited failed: {designer_exit.stderr or designer_exit.stdout}")

    next_action = run_command(sys.executable, PYTHON_TOOL, "next-action", node_id, str(root))
    if next_action.returncode != 0:
        raise AssertionError(f"next-action after acceptance freeze failed: {next_action.stderr or next_action.stdout}")
    return json.loads(next_action.stdout)["action"]


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
    def test_read_only_workspace_semantics_cover_current_state_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_workspace(
                root,
                plan_status="blocked",
                nodes=[
                    checkpoint_node(
                        NODE_ID,
                        status="blocked",
                        checked=False,
                        status_reason="Waiting for an external decision.",
                    ),
                    checkpoint_node(SECOND_NODE_ID, status="in_progress", checked=False),
                ],
            )
            manifest_path = root / "Manifest.json"
            checkpoints_path = root / "main-plan" / "Checkpoints.json"
            plans = read_plans(root)
            nodes = read_nodes(root)
            plans[0]["id"] = SECOND_NODE_ID
            plans[0]["source_files"] = ["missing/current-source.md"]
            nodes[1]["next"] = [MISSING_NODE_ID]
            nodes[1]["regression"]["scope"] = "full"  # type: ignore[index]
            manifest_path.write_text(json.dumps(plans), encoding="utf-8")
            checkpoints_path.write_text(json.dumps(nodes), encoding="utf-8")
            before = (manifest_path.read_bytes(), checkpoints_path.read_bytes())

            issues = workspace.workspace_semantic_issues(manifest_path)
            messages = "\n".join(issue.message for issue in issues)

            self.assertIn("duplicates id", messages)
            self.assertIn("does not match derived status 'in_progress'", messages)
            self.assertIn("unknown node id", messages)
            self.assertIn("must use 'focused'", messages)
            self.assertIn("source_files[0]: not found", messages)
            self.assertEqual(before, (manifest_path.read_bytes(), checkpoints_path.read_bytes()))

    def test_python_validate_accepts_minimal_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            write_workspace(Path(tmpdir))

            result = run_command(sys.executable, PYTHON_TOOL, "validate", tmpdir)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OK: validated 2 state file(s), 2 item(s).", result.stdout)

    def test_validate_rejects_absolute_state_paths_without_echoing_them(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_workspace(root)
            plans = read_plans(root)
            plans[0]["source_files"] = [str(root / "private-plan.md")]
            (root / "Manifest.json").write_text(json.dumps(plans), encoding="utf-8")

            result = run_command(sys.executable, PYTHON_TOOL, "validate", tmpdir, "--no-git")

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("repository-relative", result.stderr)
        self.assertNotIn(str(root), result.stdout + result.stderr)

    def test_python_validate_json_reports_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            write_workspace(Path(tmpdir))

            result = run_command(sys.executable, PYTHON_TOOL, "validate", tmpdir, "--json")

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["state_files"], 2)
        self.assertEqual(payload["issues"], [])

    def test_python_validate_rejects_noncanonical_requirement_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            nodes = [checkpoint_node(NODE_ID)]
            nodes[0]["requirements"] = ["PLAN-REQ-001"]
            write_workspace(root, nodes=nodes)

            result = run_command(sys.executable, PYTHON_TOOL, "validate", tmpdir, "--no-git")

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("canonical format", result.stderr)

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
        self.assertIn("delivery-roadmap", result.stdout.strip().splitlines())
        self.assertNotIn(str(project.resolve()), result.stdout)

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

    def test_platform_command_and_automated_start_gate_use_the_same_runtime_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_workspace(
                root,
                plan_status="pending",
                nodes=[checkpoint_node(NODE_ID, status="pending", platform=other_platform())],
            )
            before = (root / "Manifest.json").read_bytes(), (root / "main-plan" / "Checkpoints.json").read_bytes()

            platform_result = run_command(sys.executable, PYTHON_TOOL, "platform", "--json")
            next_action = run_command(sys.executable, PYTHON_TOOL, "next-action", NODE_ID, tmpdir)

            self.assertEqual(platform_result.returncode, 0, platform_result.stderr)
            self.assertEqual(json.loads(platform_result.stdout)["platform"], current_platform())
            self.assertNotEqual(next_action.returncode, 0, next_action.stdout)
            self.assertIn("declared platform does not match the current runtime platform", next_action.stderr)
            self.assertEqual(read_nodes(root)[0]["status"], "pending")
            self.assertEqual(
                before,
                ((root / "Manifest.json").read_bytes(), (root / "main-plan" / "Checkpoints.json").read_bytes()),
            )

    def test_next_action_lazily_enrolls_to_acceptance_designer_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            node = checkpoint_node(NODE_ID, status="pending")
            design = {
                "artifact": "tests/acceptance-fixture/design.md",
                "owned_paths": ["tests/acceptance-fixture/scaffold.py"],
                "scaffold_paths": ["tests/acceptance-fixture/scaffold.py"],
                "acceptance_paths": ["tests/acceptance-fixture/acceptance.md"],
                "symbols": [
                    {
                        "path": "tests/acceptance-fixture/scaffold.py",
                        "kind": "module",
                        "name": "acceptance_scaffold",
                        "operation": "modify",
                        "signature": "acceptance_scaffold(state: object) -> str",
                    }
                ],
                "interfaces": [
                    {
                        "name": "acceptance_scaffold",
                        "producer": "tests/acceptance-fixture/scaffold.py",
                        "consumers": ["scripts/manifest_tool.py"],
                        "inputs": "validated node and plan payload",
                        "outputs": "next action and acceptance state",
                        "errors": ["ValueError for malformed state"],
                    }
                ],
                "dependencies": [],
                "decisions": {
                    "composition": "pure boundaries",
                    "algorithms": "constant-time transition lookup",
                    "data_structures": "normalized mappings",
                    "state": "state file writer only",
                    "isolation": "role-specific artifacts only",
                    "concurrency": "serialized node mutation",
                },
                "test_seams": ["tests/acceptance-state-machine"],
            }
            node["design"] = design
            write_design_artifacts(root, design)
            write_workspace(root, plan_status="pending", nodes=[node])

            next_action = run_command(sys.executable, PYTHON_TOOL, "next-action", NODE_ID, tmpdir)
            self.assertEqual(next_action.returncode, 0, next_action.stderr)
            self.assertEqual(json.loads(next_action.stdout)["action"], "dispatch_acceptance_designer")

            designer = run_command(sys.executable, PYTHON_TOOL, "dispatch", NODE_ID, tmpdir, "--role", "acceptance_designer")
            self.assertEqual(designer.returncode, 0, designer.stderr)
            designer_id = json.loads(designer.stdout)["dispatch_id"]
            self.assertTrue(UUID4_PATTERN.fullmatch(designer_id))
            after_designer = run_command(sys.executable, PYTHON_TOOL, "next-action", NODE_ID, tmpdir)
            self.assertEqual(after_designer.returncode, 0, after_designer.stderr)
            self.assertEqual(json.loads(after_designer.stdout)["action"], "await_acceptance_designer_exit")

            wrong_exit = run_command(
                sys.executable,
                PYTHON_TOOL,
                "advance",
                NODE_ID,
                tmpdir,
                "--event",
                "acceptance-designer-exited",
                "--dispatch-id",
                "stale-designer-id",
            )
            self.assertNotEqual(wrong_exit.returncode, 0, wrong_exit.stdout)
            exit_event = run_command(
                sys.executable,
                PYTHON_TOOL,
                "advance",
                NODE_ID,
                tmpdir,
                "--event",
                "acceptance-designer-exited",
                "--dispatch-id",
                designer_id,
            )
            self.assertEqual(exit_event.returncode, 0, exit_event.stderr)
            self.assertEqual(json.loads(exit_event.stdout)["phase"], "awaiting_executor")
            prepared = run_command(sys.executable, PYTHON_TOOL, "next-action", NODE_ID, tmpdir)
            self.assertEqual(prepared.returncode, 0, prepared.stderr)
            self.assertEqual(json.loads(prepared.stdout)["action"], "dispatch_executor")

    def test_frozen_preparation_changes_have_freshness_gates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            node = checkpoint_node(NODE_ID, status="pending")
            node["design"] = {
                "artifact": "tests/acceptance-fixture/design.md",
                "owned_paths": ["tests/acceptance-fixture/scaffold.py"],
                "scaffold_paths": ["tests/acceptance-fixture/scaffold.py"],
                "acceptance_paths": ["tests/acceptance-fixture/acceptance.md", "tests/acceptance-fixture/acceptance-2.md"],
                "symbols": [
                    {
                        "path": "tests/acceptance-fixture/scaffold.py",
                        "kind": "module",
                        "name": "acceptance_scaffold",
                        "operation": "modify",
                        "signature": "acceptance_scaffold(state: object) -> str",
                    }
                ],
                "interfaces": [
                    {
                        "name": "acceptance_scaffold",
                        "producer": "tests/acceptance-fixture/scaffold.py",
                        "consumers": ["scripts/manifest_tool.py"],
                        "inputs": "validated node and plan payload",
                        "outputs": "next action and acceptance state",
                        "errors": ["ValueError for malformed state"],
                    }
                ],
                "dependencies": [],
                "decisions": {
                    "composition": "pure boundaries",
                    "algorithms": "constant-time transition lookup",
                    "data_structures": "normalized mappings",
                    "state": "state file writer only",
                    "isolation": "role-specific artifacts only",
                    "concurrency": "serialized node mutation",
                },
                "test_seams": ["tests/acceptance-state-machine"],
            }
            write_design_artifacts(root, node["design"])
            write_workspace(root, plan_status="pending", nodes=[node])

            designer = run_command(sys.executable, PYTHON_TOOL, "dispatch", NODE_ID, tmpdir, "--role", "acceptance_designer")
            self.assertEqual(designer.returncode, 0, designer.stderr)
            designer_id = json.loads(designer.stdout)["dispatch_id"]
            self.assertTrue(UUID4_PATTERN.fullmatch(designer_id))
            self.assertTrue(OPAQUE_EVENT_ID_PATTERN.fullmatch(designer_id))
            designer_exit = run_command(
                sys.executable,
                PYTHON_TOOL,
                "advance",
                NODE_ID,
                tmpdir,
                "--event",
                "acceptance-designer-exited",
                "--dispatch-id",
                designer_id,
            )
            self.assertEqual(designer_exit.returncode, 0, designer_exit.stderr)
            self.assertEqual(
                json.loads(run_command(sys.executable, PYTHON_TOOL, "next-action", NODE_ID, tmpdir).stdout)["action"],
                "dispatch_executor",
            )
            stale_acceptance = (root / "tests/acceptance-fixture/acceptance.md")
            stale_acceptance.write_text("updated cases", encoding="utf-8")
            self.assertEqual(
                json.loads(run_command(sys.executable, PYTHON_TOOL, "next-action", NODE_ID, tmpdir).stdout)["action"],
                "main_acceptance_decision",
            )
            self.assertEqual(read_nodes(root)[0]["acceptance"]["phase"], "acceptance_revision_required")


    def test_completed_capability_is_terminal_without_enrolling_another_eligible_node(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            second_node = checkpoint_node(
                SECOND_NODE_ID,
                status="pending",
                goal="Remain eligible after the selected capability completes.",
                checked=False,
            )
            second_node["design"] = default_acceptance_design("second-acceptance-fixture")
            write_workspace(
                root,
                plan_status="pending",
                nodes=[
                    checkpoint_node(NODE_ID, status="pending", checked=False),
                    second_node,
                ],
            )
            second_node_before = serialized_node_bytes(root, SECOND_NODE_ID)
            self.assertEqual(prepare_node_with_acceptance(root, NODE_ID), "dispatch_executor")

            executor = run_command(
                sys.executable,
                PYTHON_TOOL,
                "dispatch",
                NODE_ID,
                tmpdir,
                "--role",
                "executor",
            )
            self.assertEqual(executor.returncode, 0, executor.stderr)
            executor_exit = run_command(
                sys.executable,
                PYTHON_TOOL,
                "advance",
                NODE_ID,
                tmpdir,
                "--event",
                "executor-exited",
                "--dispatch-id",
                json.loads(executor.stdout)["dispatch_id"],
            )
            self.assertEqual(executor_exit.returncode, 0, executor_exit.stderr)
            self.assertEqual(json.loads(executor_exit.stdout)["action"], "dispatch_auditor")

            auditor = run_command(
                sys.executable,
                PYTHON_TOOL,
                "dispatch",
                NODE_ID,
                tmpdir,
                "--role",
                "auditor",
            )
            self.assertEqual(auditor.returncode, 0, auditor.stderr)
            audit_passed = run_command(
                sys.executable,
                PYTHON_TOOL,
                "advance",
                NODE_ID,
                tmpdir,
                "--event",
                "audit-passed",
                "--dispatch-id",
                json.loads(auditor.stdout)["dispatch_id"],
            )
            self.assertEqual(audit_passed.returncode, 0, audit_passed.stderr)

            terminal = run_command(sys.executable, PYTHON_TOOL, "next-action", NODE_ID, tmpdir)
            self.assertEqual(terminal.returncode, 0, terminal.stderr)
            terminal_payload = json.loads(terminal.stdout)
            self.assertEqual(terminal_payload["node_id"], NODE_ID)
            self.assertEqual(terminal_payload["phase"], "accepted")
            self.assertEqual(terminal_payload["action"], "none")
            self.assertFalse(terminal_payload["action"].startswith("dispatch_"))

            selected, untouched = read_nodes(root)
            self.assertEqual(selected["status"], "completed")
            self.assertEqual(untouched["status"], "pending")
            self.assertEqual(untouched["prerequisites"], [])
            self.assertEqual(untouched["platform"], "any")
            self.assertNotIn("acceptance", untouched)
            self.assertEqual(serialized_node_bytes(root, SECOND_NODE_ID), second_node_before)

    def test_executor_exit_records_a_current_focused_receipt_and_binds_auditor(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_workspace(root, plan_status="pending", nodes=[checkpoint_node(NODE_ID, status="pending", checked=False)])
            self.assertEqual(prepare_node_with_acceptance(root), "dispatch_executor")

            dispatch = run_command(
                sys.executable,
                PYTHON_TOOL,
                "dispatch",
                NODE_ID,
                tmpdir,
                "--role",
                "executor",
            )
            self.assertEqual(dispatch.returncode, 0, dispatch.stderr)
            executor_id = json.loads(dispatch.stdout)["dispatch_id"]
            advance = run_command(
                sys.executable,
                PYTHON_TOOL,
                "advance",
                NODE_ID,
                tmpdir,
                "--event",
                "executor-exited",
                "--dispatch-id",
                executor_id,
            )

            self.assertEqual(advance.returncode, 0, advance.stderr)
            self.assertEqual(json.loads(advance.stdout)["phase"], "awaiting_auditor")
            node = read_nodes(root)[0]
            criterion = node["acceptance_criteria"][0]
            receipt = node["regression"]["last_pass"]
            self.assertTrue(criterion["checked"])
            self.assertEqual(criterion["evidence_refs"][0]["exit_code"], 0)
            self.assertEqual(len(criterion["evidence_refs"][0]["command_sha256"]), 64)
            self.assertNotIn("command", criterion["evidence_refs"][0])
            self.assertEqual(len(receipt["contract_digest"]), 64)
            self.assertEqual(len(receipt["content_fingerprint"]), 64)

            auditor = run_command(
                sys.executable,
                PYTHON_TOOL,
                "dispatch",
                NODE_ID,
                tmpdir,
                "--role",
                "auditor",
            )
            self.assertEqual(auditor.returncode, 0, auditor.stderr)
            audit_dispatch = read_nodes(root)[0]["acceptance"]["dispatch"]
            self.assertEqual(audit_dispatch["contract_digest"], receipt["contract_digest"])
            self.assertEqual(audit_dispatch["content_fingerprint"], receipt["content_fingerprint"])

    def test_final_regression_event_runs_full_once_and_audit_completes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            node = checkpoint_node(NODE_ID, status="pending", role="final_validation", checked=False)
            node["regression"]["commands"] = [marker_regression_command()]  # type: ignore[index]
            write_workspace(root, plan_status="pending", nodes=[node])
            self.assertEqual(prepare_node_with_acceptance(root), "run_regression")

            first = run_command(
                sys.executable,
                PYTHON_TOOL,
                "advance",
                NODE_ID,
                tmpdir,
                "--event",
                "regression-requested",
                "--dispatch-id",
                "full-attempt-1",
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            receipt = read_nodes(root)[0]["regression"]["last_pass"]
            before = (root / "main-plan" / "Checkpoints.json").read_bytes()
            repeated = run_command(
                sys.executable,
                PYTHON_TOOL,
                "advance",
                NODE_ID,
                tmpdir,
                "--event",
                "regression-requested",
                "--dispatch-id",
                "full-attempt-1",
            )

            self.assertNotEqual(repeated.returncode, 0, repeated.stdout)
            self.assertIn("out of order", repeated.stderr)
            self.assertEqual((root / "regression-runs.txt").read_text(encoding="utf-8"), "run\n")
            self.assertEqual(read_nodes(root)[0]["regression"]["last_pass"], receipt)
            self.assertEqual((root / "main-plan" / "Checkpoints.json").read_bytes(), before)

            auditor = run_command(
                sys.executable,
                PYTHON_TOOL,
                "dispatch",
                NODE_ID,
                tmpdir,
                "--role",
                "auditor",
            )
            self.assertEqual(auditor.returncode, 0, auditor.stderr)
            auditor_id = json.loads(auditor.stdout)["dispatch_id"]
            completed = run_command(
                sys.executable,
                PYTHON_TOOL,
                "advance",
                NODE_ID,
                tmpdir,
                "--event",
                "audit-passed",
                "--dispatch-id",
                auditor_id,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(read_nodes(root)[0]["status"], "completed")
            self.assertEqual(read_plans(root)[0]["status"], "completed")

    def test_stale_full_receipt_rejects_bound_audit_without_rerunning(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            node = checkpoint_node(NODE_ID, status="pending", role="final_validation", checked=False)
            node["regression"]["commands"] = [marker_regression_command()]  # type: ignore[index]
            write_workspace(root, plan_status="pending", nodes=[node])
            self.assertEqual(prepare_node_with_acceptance(root), "run_regression")

            first = run_command(
                sys.executable,
                PYTHON_TOOL,
                "advance",
                NODE_ID,
                tmpdir,
                "--event",
                "regression-requested",
                "--dispatch-id",
                "full-attempt-1",
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            auditor = run_command(
                sys.executable,
                PYTHON_TOOL,
                "dispatch",
                NODE_ID,
                tmpdir,
                "--role",
                "auditor",
            )
            self.assertEqual(auditor.returncode, 0, auditor.stderr)
            auditor_id = json.loads(auditor.stdout)["dispatch_id"]
            (root / "tracked.txt").write_text("changed\n", encoding="utf-8")
            before = (root / "main-plan" / "Checkpoints.json").read_bytes()
            verdict = run_command(
                sys.executable,
                PYTHON_TOOL,
                "advance",
                NODE_ID,
                tmpdir,
                "--event",
                "audit-passed",
                "--dispatch-id",
                auditor_id,
            )

            self.assertNotEqual(verdict.returncode, 0, verdict.stdout)
            self.assertIn("current passing regression fingerprint", verdict.stderr)
            self.assertEqual((root / "regression-runs.txt").read_text(encoding="utf-8"), "run\n")
            self.assertEqual((root / "main-plan" / "Checkpoints.json").read_bytes(), before)

    def test_failed_executor_regression_persists_only_the_safe_repair_state(self) -> None:
        sentinel = "PRIVATE-RUNTIME-SENTINEL"
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            node = checkpoint_node(NODE_ID, status="pending", checked=False)
            encoded_sentinel = ",".join(str(ord(character)) for character in sentinel)
            node["regression"]["commands"] = [  # type: ignore[index]
                command_line(
                    sys.executable,
                    "-c",
                    f"import sys; print(''.join(chr(value) for value in [{encoded_sentinel}])); sys.exit(7)",
                )
            ]
            write_workspace(root, plan_status="pending", nodes=[node])
            self.assertEqual(prepare_node_with_acceptance(root), "dispatch_executor")

            dispatch = run_command(
                sys.executable,
                PYTHON_TOOL,
                "dispatch",
                NODE_ID,
                tmpdir,
                "--role",
                "executor",
            )
            self.assertEqual(dispatch.returncode, 0, dispatch.stderr)
            executor_id = json.loads(dispatch.stdout)["dispatch_id"]
            advance = run_command(
                sys.executable,
                PYTHON_TOOL,
                "advance",
                NODE_ID,
                tmpdir,
                "--event",
                "executor-exited",
                "--dispatch-id",
                executor_id,
            )

            self.assertEqual(advance.returncode, 0, advance.stderr)
            self.assertEqual(json.loads(advance.stdout)["action"], "main_correction_decision")
            self.assertNotIn(sentinel, advance.stdout + advance.stderr)
            stored = read_nodes(root)[0]
            self.assertEqual(stored["acceptance"]["phase"], "correction_required")
            self.assertEqual(stored["acceptance"]["outcome"], "regression_failed")
            self.assertFalse(stored["acceptance_criteria"][0]["checked"])
            self.assertNotIn("evidence_refs", stored["acceptance_criteria"][0])
            self.assertNotIn("last_pass", stored["regression"])
            self.assertNotIn(sentinel, json.dumps(stored))

    def test_mutation_commands_drive_node_and_plan_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            first = checkpoint_node(
                NODE_ID,
                status="pending",
                role="validation_matrix",
            )
            first["acceptance_criteria"].append(  # type: ignore[index]
                {"checked": False, "text": "A manual acceptance check also passes."}
            )
            write_workspace(
                root,
                plan_status="pending",
                nodes=[
                    first,
                    checkpoint_node(
                        SECOND_NODE_ID,
                        status="pending",
                        role="architecture_scaffold",
                        prerequisites=[NODE_ID],
                    ),
                ],
            )

            start = run_command(sys.executable, PYTHON_TOOL, "start", NODE_ID, tmpdir)
            self.assertEqual(start.returncode, 0, start.stderr)
            self.assertIn(f"OK: node {NODE_ID} pending -> in_progress", start.stdout)
            self.assertIn("OK: plan 'Main Plan' pending -> in_progress", start.stdout)

            blocked_start = run_command(sys.executable, PYTHON_TOOL, "start", SECOND_NODE_ID, tmpdir)
            self.assertNotEqual(blocked_start.returncode, 0, blocked_start.stdout)
            self.assertIn(f"node {NODE_ID} is already in_progress", blocked_start.stderr)
            self.assertIn("main-plan/Checkpoints.json", blocked_start.stderr)
            self.assertNotIn(str(root), blocked_start.stdout + blocked_start.stderr)
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
                "1",
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
                sys.executable,
                PYTHON_TOOL,
                "skip",
                SECOND_NODE_ID,
                tmpdir,
                "--reason",
                "waived from this delivery",
            )
            self.assertEqual(skip.returncode, 0, skip.stderr)
            self.assertIn("OK: plan 'Main Plan' in_progress -> completed", skip.stdout)

            nodes = read_nodes(root)
            self.assertEqual(nodes[0]["status"], "completed")
            self.assertEqual(nodes[0]["commit"]["delivered"], "abc1234")
            self.assertEqual(nodes[0]["acceptance_criteria"][0]["checked"], True)
            self.assertEqual(nodes[0]["acceptance_criteria"][1]["evidence"], "unit tests passed")
            self.assertNotIn("status_reason", nodes[0])
            self.assertEqual(nodes[1]["status"], "skipped")
            self.assertEqual(nodes[1]["status_reason"], "waived from this delivery")
            self.assertEqual(read_plans(root)[0]["status"], "completed")

            restart = run_command(sys.executable, PYTHON_TOOL, "start", NODE_ID, tmpdir)
            self.assertNotEqual(restart.returncode, 0, restart.stdout)
            self.assertIn("cannot transition from 'completed' to 'in_progress'", restart.stderr)

    def test_block_requires_reason_argument(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            write_workspace(
                Path(tmpdir),
                plan_status="pending",
                nodes=[checkpoint_node(NODE_ID, status="pending", role="validation_matrix")],
            )

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
                    checkpoint_node(NODE_ID, status="completed", role="validation_matrix"),
                    checkpoint_node(
                        SECOND_NODE_ID,
                        status="blocked",
                        role="architecture_scaffold",
                        prerequisites=[NODE_ID],
                        status_reason="waiting on credentials",
                    ),
                ],
            )

            result = run_command(sys.executable, PYTHON_TOOL, "status", tmpdir, "--json")

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["workspace"], ".")
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
                    checkpoint_node(NODE_ID, status="completed", role="validation_matrix"),
                    checkpoint_node(
                        SECOND_NODE_ID,
                        status="pending",
                        role="architecture_scaffold",
                        prerequisites=[NODE_ID],
                    ),
                    checkpoint_node(
                        THIRD_NODE_ID,
                        status="pending",
                        role="architecture_scaffold",
                        platform=other_platform(),
                    ),
                ],
            )

            result = run_command(sys.executable, PYTHON_TOOL, "next", tmpdir, "--json")

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["workspace"], ".")
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
                    checkpoint_node(NODE_ID, status="in_progress", role="validation_matrix"),
                    checkpoint_node(SECOND_NODE_ID, status="pending", role="architecture_scaffold"),
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
        self.assertIn("regression", node_schema["optional_fields"])
        self.assertIn("acceptance", node_schema["optional_fields"])
        self.assertEqual(node_schema["regression_scopes"], ["focused", "full"])
        self.assertIn("content_fingerprint", node_schema["regression_receipt_fields"])
        self.assertEqual(node_schema["acceptance_required_fields"], ["attempt", "outcome", "phase"])
        self.assertIn("awaiting_repair", node_schema["acceptance_phases"])
        self.assertIn("awaiting_acceptance_design", node_schema["acceptance_phases"])
        self.assertIn("acceptance_designer_running", node_schema["acceptance_phases"])
        self.assertIn("awaiting_executor", node_schema["acceptance_phases"])
        self.assertIn("audit_failed", node_schema["acceptance_outcomes"])
        self.assertIn("any", node_schema["platforms"])
        self.assertEqual(node_schema["requirement_label_pattern"], r"^REQ(?:-[A-Za-z0-9]+)+$")
        self.assertIn("Scope: Closure: module -", node_schema["template"]["description"])

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
                    checkpoint_node(NODE_ID, status="pending", role="validation_matrix", checked=False),
                    checkpoint_node(SECOND_NODE_ID, status="pending", role="architecture_scaffold"),
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
            write_workspace(
                Path(tmpdir),
                plan_status="pending",
                nodes=[checkpoint_node(NODE_ID, status="pending", role="validation_matrix")],
            )

            result = run_command(sys.executable, PYTHON_TOOL, "pause", NODE_ID, tmpdir)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("requires an 'in_progress' node", result.stderr)

    def test_swapped_node_and_root_arguments_get_a_usage_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            write_workspace(
                Path(tmpdir),
                plan_status="pending",
                nodes=[checkpoint_node(NODE_ID, status="pending", role="validation_matrix")],
            )

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
            design = default_acceptance_design()
            write_design_artifacts(root, design)

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
                "--design-json",
                json.dumps(design),
                "--criterion",
                "The spliced node validates.",
                "--commit-message",
                "test add-node",
                "--commit-target",
                "tests",
                "--regression-command",
                passing_regression_command(),
                "--regression-path",
                "tracked.txt",
                "--regression-criterion",
                "0",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            nodes = read_nodes(root)

        self.assertEqual(len(nodes), 3)
        inserted = nodes[1]
        self.assertEqual(inserted["status"], "pending")
        self.assertEqual(inserted["prerequisites"], [NODE_ID])
        self.assertEqual(inserted["next"], [SECOND_NODE_ID])
        self.assertEqual(inserted["regression"]["scope"], "focused")
        self.assertEqual(inserted["regression"]["criteria"], [0])
        self.assertEqual(nodes[0]["next"], [inserted["id"]])
        self.assertEqual(nodes[2]["prerequisites"], [inserted["id"]])
        self.assertIn("downstream prerequisites rewired", result.stdout)

    def test_add_node_accepts_forward_prerequisites_when_the_workspace_graph_is_acyclic(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_workspace(
                root,
                plan_status="pending",
                nodes=[checkpoint_node(NODE_ID, status="pending")],
            )
            design = default_acceptance_design()
            write_design_artifacts(root, design)

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
                "Depend on a later serialized node.",
                "--description",
                "Scope: enabling test fixture for workspace-level dependency validation.",
                "--design-json",
                json.dumps(design),
                "--criterion",
                "The forward prerequisite is preserved.",
                "--commit-message",
                "test add-node",
                "--commit-target",
                "tests",
                "--regression-command",
                passing_regression_command(),
                "--regression-path",
                "tracked.txt",
                "--regression-criterion",
                "0",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            nodes = read_nodes(root)
            self.assertEqual(len(nodes), 2)
            self.assertEqual(nodes[0]["prerequisites"], [NODE_ID])

    def test_add_node_rejects_noncanonical_requirement_labels_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_workspace(root, plan_status="pending", nodes=[checkpoint_node(NODE_ID, status="pending")])
            design = default_acceptance_design()
            write_design_artifacts(root, design)
            before = read_nodes(root)

            result = run_command(
                sys.executable,
                PYTHON_TOOL,
                "add-node",
                tmpdir,
                "--plan",
                "main-plan",
                "--requirements",
                "PLAN-REQ-001",
                "--design-json",
                json.dumps(design),
                "--goal",
                "Attempt to add an invalid requirement label.",
                "--description",
                "Scope: label validation. Context: regression test. Target: reject invalid labels.",
                "--criterion",
                "The invalid node is not written.",
                "--commit-message",
                "test invalid requirement label",
                "--commit-target",
                "tests",
                "--regression-command",
                passing_regression_command(),
                "--regression-path",
                "tracked.txt",
                "--regression-criterion",
                "0",
            )

            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("canonical format", result.stderr)
            self.assertEqual(read_nodes(root), before)

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
            node = checkpoint_node(NODE_ID, status="pending", role="validation_matrix")
            node["acceptance_criteria"][0] = {
                "checked": True,
                "text": "Stable baseline evidence was captured.",
                "evidence": "previous evidence",
                "evidence_refs": [{"type": "command", "exit_code": 0, "command_sha256": "f" * 64}],
            }
            write_workspace(root, plan_status="pending", nodes=[node])

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
                "--criterion",
                "A second concrete check.",
                "--criterion",
                "A replacement check.",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            node = read_nodes(root)[0]

        self.assertEqual(node["goal"], "Refined goal.")
        self.assertEqual(node["difficulty"], "high")
        self.assertEqual(
            node["acceptance_criteria"],
            [
                {"checked": False, "text": "A second concrete check."},
                {"checked": False, "text": "A replacement check."},
            ],
        )

    def test_edit_node_replaces_delivery_criteria_and_clears_active_proof(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_workspace(root, plan_status="pending", nodes=[checkpoint_node(NODE_ID, status="pending")])
            self.assertEqual(prepare_node_with_acceptance(root), "dispatch_executor")

            dispatch = run_command(
                sys.executable,
                PYTHON_TOOL,
                "dispatch",
                NODE_ID,
                tmpdir,
                "--role",
                "executor",
            )
            self.assertEqual(dispatch.returncode, 0, dispatch.stderr)
            executor_id = json.loads(dispatch.stdout)["dispatch_id"]
            advance = run_command(
                sys.executable,
                PYTHON_TOOL,
                "advance",
                NODE_ID,
                tmpdir,
                "--event",
                "executor-exited",
                "--dispatch-id",
                executor_id,
            )
            self.assertEqual(advance.returncode, 0, advance.stderr)

            auditor = run_command(sys.executable, PYTHON_TOOL, "dispatch", NODE_ID, tmpdir, "--role", "auditor")
            self.assertEqual(auditor.returncode, 0, auditor.stderr)

            result = run_command(
                sys.executable,
                PYTHON_TOOL,
                "edit-node",
                NODE_ID,
                tmpdir,
                "--criterion",
                "Manual replacement criterion A.",
                "--criterion",
                "Manual replacement criterion B.",
                "--regression-criterion",
                "0",
                "--regression-criterion",
                "1",
            )

            self.assertEqual(result.returncode, 0, result.stderr)

            next_action = run_command(sys.executable, PYTHON_TOOL, "next-action", NODE_ID, tmpdir)
            self.assertEqual(next_action.returncode, 0, next_action.stderr)
            self.assertEqual(json.loads(next_action.stdout)["action"], "main_acceptance_decision")

            node = read_nodes(root)[0]
            self.assertEqual(node["status"], "pending")
            self.assertEqual(
                node["acceptance_criteria"],
                [
                    {"checked": False, "text": "Manual replacement criterion A."},
                    {"checked": False, "text": "Manual replacement criterion B."},
                ],
            )
            self.assertEqual(node["regression"]["criteria"], [0, 1])
            self.assertNotIn("last_pass", node["regression"])
            self.assertEqual(
                node["acceptance"],
                {"phase": "acceptance_revision_required", "attempt": 1, "outcome": "none"},
            )

    def test_edit_node_fails_atomically_when_edit_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_workspace(root, plan_status="pending", nodes=[checkpoint_node(NODE_ID, status="pending")])
            before = read_nodes(root)

            rejected = run_command(
                sys.executable,
                PYTHON_TOOL,
                "edit-node",
                NODE_ID,
                tmpdir,
                "--goal",
                "Refined goal.",
                "--difficulty",
                "super",
            )

            self.assertNotEqual(rejected.returncode, 0, rejected.stdout)
            self.assertEqual(read_nodes(root), before)

    def test_edit_node_rejects_noncanonical_requirement_labels_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_workspace(root, plan_status="pending", nodes=[checkpoint_node(NODE_ID, status="pending")])
            before = read_nodes(root)

            replacement = run_command(
                sys.executable,
                PYTHON_TOOL,
                "edit-node",
                NODE_ID,
                tmpdir,
                "--requirements",
                "PLAN-REQ-001",
            )
            addition = run_command(
                sys.executable,
                PYTHON_TOOL,
                "edit-node",
                NODE_ID,
                tmpdir,
                "--add-requirement",
                "PLAN-REQ-001",
            )

            self.assertNotEqual(replacement.returncode, 0, replacement.stdout)
            self.assertNotEqual(addition.returncode, 0, addition.stdout)
            self.assertIn("canonical format", replacement.stderr)
            self.assertIn("canonical format", addition.stderr)
            self.assertEqual(read_nodes(root), before)

    def test_check_records_structured_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_workspace(
                root,
                plan_status="pending",
                nodes=[checkpoint_node(NODE_ID, status="pending", role="validation_matrix", checked=False)],
            )
            evidence_file = root / "report.txt"
            evidence_file.write_text("verification report\n", encoding="utf-8")
            expected_sha = hashlib.sha256(evidence_file.read_bytes()).hexdigest()
            evidence_command = f'"{sys.executable}" -c "import sys; sys.exit(0)"'

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
                "report.txt",
                "--evidence-cmd",
                evidence_command,
            )
            self.assertEqual(passing.returncode, 0, passing.stderr)
            self.assertIn("2 evidence reference(s)", passing.stdout)

            criterion = read_nodes(root)[0]["acceptance_criteria"][0]
            self.assertTrue(criterion["checked"])
            refs = criterion["evidence_refs"]
            self.assertEqual(len(refs), 2)
            self.assertEqual(refs[0]["type"], "command")
            self.assertEqual(refs[0]["exit_code"], 0)
            self.assertEqual(
                refs[0]["command_sha256"],
                hashlib.sha256(evidence_command.encode("utf-8")).hexdigest(),
            )
            self.assertNotIn("command", refs[0])
            self.assertEqual(refs[1]["type"], "file")
            self.assertEqual(refs[1]["path"], "report.txt")
            self.assertEqual(refs[1]["sha256"], expected_sha)

            validate = run_command(sys.executable, PYTHON_TOOL, "validate", tmpdir, "--no-git")
            self.assertEqual(validate.returncode, 0, validate.stderr)

    def test_check_refuses_failing_evidence_command(self) -> None:
        sentinel = "PRIVATE-EVIDENCE-RUNTIME-SENTINEL"
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_workspace(
                root,
                plan_status="pending",
                nodes=[checkpoint_node(NODE_ID, status="pending", role="validation_matrix", checked=False)],
            )

            start = run_command(sys.executable, PYTHON_TOOL, "start", NODE_ID, tmpdir)
            self.assertEqual(start.returncode, 0, start.stderr)
            encoded_sentinel = ",".join(str(ord(character)) for character in sentinel)

            failing = run_command(
                sys.executable,
                PYTHON_TOOL,
                "check",
                NODE_ID,
                tmpdir,
                "--criterion",
                "0",
                "--evidence-cmd",
                command_line(
                    sys.executable,
                    "-c",
                    f"import sys; print(''.join(chr(value) for value in [{encoded_sentinel}])); sys.exit(3)",
                ),
            )

            self.assertNotEqual(failing.returncode, 0, failing.stdout)
            self.assertIn("exited with 3", failing.stderr)
            self.assertNotIn(sentinel, failing.stdout + failing.stderr)
            self.assertFalse(read_nodes(root)[0]["acceptance_criteria"][0]["checked"])

    def test_safe_summary_rejects_absolute_path_tokens_at_every_supported_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wrappers = [
                ("start", lambda token: token),
                ("whitespace", lambda token: f"artifact {token}"),
                ("quote", lambda token: f"artifact '{token}'"),
                ("assignment", lambda token: f"key={token}"),
                ("label", lambda token: f"path:{token}"),
                ("parenthesis", lambda token: f"artifact({token})"),
                ("punctuation", lambda token: f"artifact,{token}"),
            ]

            for path_kind, token in absolute_summary_tokens(root):
                for boundary_kind, wrapper in wrappers:
                    issue = models.safe_summary_issue(wrapper(token))
                    self.assertIsNotNone(
                        issue,
                        f"{path_kind} path at {boundary_kind} boundary was accepted",
                    )

            relative_summaries = [
                "pass/fail",
                "scripts/file.py",
                "dir-/file",
                "dir+/file",
                "ordinary input/output text",
                "module=tests/test_manifest_tool_cli.py",
                "path:docs/plan",
                "reviewed (scripts/file.py)",
            ]
            for index, summary in enumerate(relative_summaries):
                self.assertIsNone(
                    models.safe_summary_issue(summary),
                    f"safe repository-relative summary {index} was rejected",
                )

            dynamic_segment = root.name
            sensitive_summaries = [
                ("endpoint", f"https://{dynamic_segment}.invalid/private"),
                ("server", f"server={dynamic_segment}.invalid"),
                ("credential", f"password={dynamic_segment}-private"),
            ]
            for summary_kind, summary in sensitive_summaries:
                self.assertIsNotNone(
                    models.safe_summary_issue(summary),
                    f"{summary_kind} summary was accepted",
                )

    def test_persisted_summaries_reject_absolute_paths_without_echo_or_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_workspace(
                root,
                plan_status="pending",
                nodes=[checkpoint_node(NODE_ID, status="pending", role="validation_matrix", checked=False)],
            )
            start = run_command(sys.executable, PYTHON_TOOL, "start", NODE_ID, tmpdir)
            self.assertEqual(start.returncode, 0, start.stderr)
            baseline = read_nodes(root)

            for path_kind, token in absolute_summary_tokens(root):
                evidence_summary = f"artifact={token}"
                rejected_evidence = run_command(
                    sys.executable,
                    PYTHON_TOOL,
                    "check",
                    NODE_ID,
                    tmpdir,
                    "--criterion",
                    "0",
                    "--evidence",
                    evidence_summary,
                )
                evidence_output = rejected_evidence.stdout + rejected_evidence.stderr
                self.assertNotEqual(rejected_evidence.returncode, 0, f"{path_kind} evidence was accepted")
                self.assertFalse(token in evidence_output, f"{path_kind} evidence was echoed")
                self.assertIn("concrete absolute path", rejected_evidence.stderr)
                self.assertTrue(read_nodes(root) == baseline, f"{path_kind} evidence mutated state")
                self.assertFalse(
                    evidence_summary in json.dumps(read_nodes(root)),
                    f"{path_kind} evidence was persisted",
                )

                reason_summary = f"path:{token}"
                rejected_reason = run_command(
                    sys.executable,
                    PYTHON_TOOL,
                    "pause",
                    NODE_ID,
                    tmpdir,
                    "--reason",
                    reason_summary,
                )
                reason_output = rejected_reason.stdout + rejected_reason.stderr
                self.assertNotEqual(rejected_reason.returncode, 0, f"{path_kind} reason was accepted")
                self.assertFalse(token in reason_output, f"{path_kind} reason was echoed")
                self.assertIn("concrete absolute path", rejected_reason.stderr)
                self.assertTrue(read_nodes(root) == baseline, f"{path_kind} reason mutated state")
                self.assertFalse(
                    reason_summary in json.dumps(read_nodes(root)),
                    f"{path_kind} reason was persisted",
                )

            safe_evidence = "verified scripts/file.py and docs/plan"
            accepted_evidence = run_command(
                sys.executable,
                PYTHON_TOOL,
                "check",
                NODE_ID,
                tmpdir,
                "--criterion",
                "0",
                "--evidence",
                safe_evidence,
            )
            self.assertEqual(accepted_evidence.returncode, 0, accepted_evidence.stderr)
            self.assertEqual(read_nodes(root)[0]["acceptance_criteria"][0]["evidence"], safe_evidence)

            safe_reason = "yield after reviewing docs/plan"
            accepted_reason = run_command(
                sys.executable,
                PYTHON_TOOL,
                "pause",
                NODE_ID,
                tmpdir,
                "--reason",
                safe_reason,
            )
            self.assertEqual(accepted_reason.returncode, 0, accepted_reason.stderr)
            stored = read_nodes(root)[0]
            self.assertEqual(stored["status"], "pending")
            self.assertEqual(stored["status_reason"], safe_reason)

    def test_check_rejects_absolute_file_paths_and_sensitive_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_workspace(
                root,
                plan_status="pending",
                nodes=[checkpoint_node(NODE_ID, status="pending", role="validation_matrix", checked=False)],
            )
            (root / "report.txt").write_text("verification report\n", encoding="utf-8")
            start = run_command(sys.executable, PYTHON_TOOL, "start", NODE_ID, tmpdir)
            absolute = run_command(
                sys.executable,
                PYTHON_TOOL,
                "check",
                NODE_ID,
                tmpdir,
                "--criterion",
                "0",
                "--evidence-file",
                str(root / "report.txt"),
            )
            sensitive = run_command(
                sys.executable,
                PYTHON_TOOL,
                "check",
                NODE_ID,
                tmpdir,
                "--criterion",
                "0",
                "--evidence",
                "server=internal.example",
            )

        self.assertNotEqual(absolute.returncode, 0, absolute.stdout)
        self.assertIn("repository-relative", absolute.stderr)
        self.assertNotIn(str(root), absolute.stdout + absolute.stderr)
        self.assertNotEqual(sensitive.returncode, 0, sensitive.stdout)
        self.assertIn("server identifier", sensitive.stderr)

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

    def test_check_labels_rejects_noncanonical_node_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_workspace(root)
            nodes = read_nodes(root)
            nodes[0]["requirements"] = ["PLAN-REQ-001"]
            (root / "main-plan" / "Checkpoints.json").write_text(json.dumps(nodes), encoding="utf-8")
            (root / "main-plan" / "Requirements.md").write_text(
                "# Requirements\n\n- REQ-001 canonical behavior\n",
                encoding="utf-8",
            )

            result = run_command(sys.executable, PYTHON_TOOL, "check-labels", tmpdir, "--json")
            payload = json.loads(result.stdout)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        plan_payload = payload["plans"][0]
        self.assertEqual(list(plan_payload["invalid_node_labels"].keys()), ["PLAN-REQ-001"])
        self.assertEqual(plan_payload["node_labels"], 0)

    def test_check_labels_rejects_prefixed_document_labels_without_substring_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_workspace(root)
            (root / "main-plan" / "Requirements.md").write_text(
                "# Requirements\n\n- PLAN-REQ-001 noncanonical behavior\n",
                encoding="utf-8",
            )

            result = run_command(sys.executable, PYTHON_TOOL, "check-labels", tmpdir, "--json")
            payload = json.loads(result.stdout)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        plan_payload = payload["plans"][0]
        self.assertEqual(plan_payload["doc_labels"], 0)
        self.assertEqual(plan_payload["invalid_document_labels"], ["PLAN-REQ-001"])
        self.assertNotIn("REQ-001", plan_payload.get("undefined", {}))

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
