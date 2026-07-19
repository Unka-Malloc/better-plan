"""Red-first public contract for deterministic acceptance progression."""

from __future__ import annotations

import importlib
import json
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.better_plan.adapters import manifest_cli


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_TOOL = ROOT / "scripts" / "manifest_tool.py"
PLAN_ID = "9b1e2d3c-4a5b-4c6d-8e9f-0123456789ab"
NODE_ID = "2c3d4e5f-6a7b-48c9-9d0e-123456789abc"
HISTORY_ID = "3d4e5f60-7a8b-49c0-8d1e-23456789abcd"
REPAIR_ID = "4e5f6071-8b9c-4ad1-9e2f-3456789abcde"
WRONG_ID = "5f607182-9cad-4be2-af30-456789abcdef"
PLAN_DIR = Path("docs/plan/acceptance-fixture")


def command(*arguments: str) -> str:
    """Make an executable command string that is portable across supported hosts."""
    return subprocess.list2cmdline(arguments) if sys.platform == "win32" else shlex.join(arguments)


class AcceptanceMachineContract(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tmp.name)
        self.plan_root = self.workspace / PLAN_DIR
        self.checkpoints = self.plan_root / "Checkpoints.json"
        self.artifact = self.workspace / "relative-artifact.txt"
        self.artifact.parent.mkdir(parents=True, exist_ok=True)
        self.artifact.write_text("initial", encoding="utf-8")
        self._write_workspace()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write_workspace(
        self,
        *,
        final: bool = False,
        regression: str | None = None,
        status: str = "pending",
        with_history: bool = False,
    ) -> None:
        self.plan_root.mkdir(parents=True, exist_ok=True)
        scope = "full" if final else "focused"
        prerequisites = [HISTORY_ID] if with_history else []
        node = {
            "id": NODE_ID,
            "status": status,
            "role": "final_validation" if final else "implementation",
            "prerequisites": prerequisites,
            "platform": "any",
            "difficulty": "high",
            "goal": "Exercise the deterministic acceptance fixture.",
            "description": (
                "Scope: tests/test_acceptance_state_machine.py and temporary acceptance workspace. "
                "Closure: scenario - acceptance state-machine public contract. "
                "Context: production acceptance transitions are intentionally absent. "
                "Target: exercise the public transition and CLI contract. "
                "Design Considerations: use a complete relative-path fixture and portable Python commands. "
                "Design Value: the fixture isolates missing production behavior from manifest validity. "
                "Constraints & Risks: no production mutation, host data, or raw output persistence."
            ),
            "requirements": ["REQ-001", "REQ-002", "REQ-003", "REQ-004", "REQ-005", "REQ-006", "REQ-007", "REQ-008", "REQ-009"],
            "acceptance_criteria": [{"checked": False, "text": "Automated acceptance is recorded by the state tool."}],
            "commit": {"repository": ".git", "message": "test: acceptance fixture", "target": "acceptance fixture"},
            "next": [],
            "regression": {
                "scope": scope,
                "commands": [regression or self._success_command()],
                "criteria": [0],
                "paths": ["relative-artifact.txt"],
            },
        }
        nodes = [self._historical_node(), node] if with_history else [node]
        self.checkpoints.write_text(json.dumps(nodes), encoding="utf-8")
        plan_status = "in_progress" if status == "in_progress" or with_history else "pending"
        manifest = [{
            "id": PLAN_ID,
            "status": plan_status,
            "title": "Acceptance state-machine fixture",
            "directory": str(PLAN_DIR),
            "source_files": [str(PLAN_DIR / "Checkpoints.json")],
            "goal": "Acceptance state-machine fixture.",
            "description": "A complete temporary plan for public acceptance-machine contracts.",
            "checkpoints": str(PLAN_DIR / "Checkpoints.json"),
        }]
        (self.workspace / "Manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def _historical_node(self) -> dict:
        return {
            "id": HISTORY_ID,
            "status": "completed",
            "role": "implementation",
            "prerequisites": [],
            "platform": "any",
            "difficulty": "high",
            "goal": "Represent immutable completed implementation history.",
            "description": (
                "Scope: relative-artifact.txt. Closure: scenario - completed implementation history. "
                "Context: final repair must not reopen or rewrite terminal delivery. "
                "Target: remain byte-for-byte unchanged throughout repair orchestration. "
                "Design Considerations: expose only a valid terminal prerequisite. "
                "Design Value: proves repair is additive instead of historical mutation. "
                "Constraints & Risks: no terminal-state edits or private evidence."
            ),
            "requirements": ["REQ-009"],
            "acceptance_criteria": [{"checked": True, "text": "Historical delivery remains terminal."}],
            "commit": {"repository": ".git", "message": "test: historical fixture", "target": "history fixture"},
            "next": [NODE_ID],
            "regression": {
                "scope": "focused",
                "commands": [self._success_command()],
                "criteria": [0],
                "paths": ["relative-artifact.txt"],
            },
        }

    def _repair_node(self) -> dict:
        return {
            "id": REPAIR_ID,
            "status": "pending",
            "role": "implementation",
            "prerequisites": [HISTORY_ID],
            "platform": "any",
            "difficulty": "high",
            "goal": "Repair the defect found by final acceptance.",
            "description": (
                "Scope: relative-artifact.txt. Closure: scenario - repair the final-acceptance defect. "
                "Context: a final regression failure requires new implementation work. "
                "Target: update the relative artifact through a fresh executor. "
                "Design Considerations: use the normal automated implementation cycle. "
                "Design Value: preserves completed history and releases the final Node's active slot. "
                "Constraints & Risks: the state tool validates this Node but never invents it."
            ),
            "requirements": ["REQ-009"],
            "acceptance_criteria": [{"checked": False, "text": "The repair passes independent acceptance."}],
            "commit": {"repository": ".git", "message": "fix: acceptance fixture", "target": "repair fixture"},
            "next": [NODE_ID],
            "regression": {
                "scope": "focused",
                "commands": [self._success_command()],
                "criteria": [0],
                "paths": ["relative-artifact.txt"],
            },
            "design": self._design_contract(acceptance_id="repair"),
        }

    def _planner_adds_repair_prerequisite(self) -> None:
        nodes = json.loads(self.checkpoints.read_text(encoding="utf-8"))
        final = next(node for node in nodes if node["id"] == NODE_ID)
        final["prerequisites"].append(REPAIR_ID)
        nodes.insert(len(nodes) - 1, self._repair_node())
        self.checkpoints.write_text(json.dumps(nodes), encoding="utf-8")

    def _success_command(self) -> str:
        return command(sys.executable, "-c", "from pathlib import Path; Path('success.marker').write_text('pass')")

    def _marker_command(self, marker: str) -> str:
        program = f"from pathlib import Path; p=Path({marker!r}); p.write_text(str(int(p.read_text()) + 1) if p.exists() else '1')"
        return command(sys.executable, "-c", program)

    def _repairable_final_command(self, marker: str) -> str:
        program = (
            "from pathlib import Path; import sys; "
            f"p=Path({marker!r}); p.write_text(str(int(p.read_text()) + 1) if p.exists() else '1'); "
            "sys.exit(0 if Path('relative-artifact.txt').read_text() == 'repaired' else 7)"
        )
        return command(sys.executable, "-c", program)

    def _failure_command(self, token: str) -> str:
        sensitive_values = (
            token,
            "/synthetic/private/acceptance-output",
            "https://synthetic.invalid/private",
        )
        runtime_values = ["''.join(chr(code) for code in %r)" % [ord(char) for char in value] for value in sensitive_values]
        # The persisted command has only numeric character codes; Python reconstructs
        # the sensitive values only while producing intentionally discarded output.
        program = "import sys; print(%s); sys.exit(7)" % " + ' ' + ".join(runtime_values)
        return command(sys.executable, "-c", program)

    def cli(self, *args: str, ok: bool = True) -> subprocess.CompletedProcess[str]:
        arguments = list(args)
        arguments.insert(2, str(self.workspace))
        result = subprocess.run(
            [sys.executable, str(MANIFEST_TOOL), *arguments],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def state(self, node_id: str = NODE_ID) -> dict:
        nodes = json.loads(self.checkpoints.read_text(encoding="utf-8"))
        return next(node for node in nodes if node["id"] == node_id)

    def state_bytes(self) -> bytes:
        return self.checkpoints.read_bytes()

    def workspace_state_bytes(self) -> tuple[bytes, bytes]:
        return ((self.workspace / "Manifest.json").read_bytes(), self.checkpoints.read_bytes())

    def dispatch(self, role: str, node_id: str = NODE_ID) -> str:
        result = self.cli("dispatch", node_id, "--role", role)
        return json.loads(result.stdout)["dispatch_id"]

    def advance(
        self,
        event: str,
        dispatch_id: str | None = None,
        *,
        node_id: str = NODE_ID,
        repair_node_id: str | None = None,
        ok: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        arguments = ["advance", node_id, "--event", event]
        if dispatch_id is not None:
            arguments.extend(["--dispatch-id", dispatch_id])
        if repair_node_id is not None:
            arguments.extend(["--repair-node", repair_node_id])
        return self.cli(*arguments, ok=ok)

    def next_action(self, node_id: str = NODE_ID) -> str:
        return json.loads(self.cli("next-action", node_id).stdout)["action"]

    def test_node_parser_preserves_windows_roots_and_rejects_unknown_options(self) -> None:
        parser = manifest_cli.build_parser()
        separator = "\\"
        drive_root = "X:" + separator + separator.join(("synthetic-workspace", "docs", "plan"))
        unc_root = separator * 2 + separator.join(("synthetic-server", "share", "docs", "plan"))
        roots = (drive_root, unc_root)

        for root in roots:
            with self.subTest(root=root):
                args = parser.parse_args(["dispatch", NODE_ID, root, "--role", "executor"])
                self.assertEqual(args.root, root)

        with self.assertRaises(SystemExit):
            parser.parse_args(["dispatch", NODE_ID, roots[0], "--rolee", "executor"])

    def assert_automated_proof_cleared(self, node: dict) -> None:
        regression = node["regression"]
        self.assertNotIn("last_pass", regression)
        for criterion_index in regression["criteria"]:
            criterion = node["acceptance_criteria"][criterion_index]
            self.assertFalse(criterion["checked"])
            self.assertNotIn("evidence", criterion)
            self.assertNotIn("evidence_refs", criterion)

        acceptance = node.get("acceptance")
        if acceptance is not None:
            self.assertNotIn("dispatch", acceptance)
            self.assertNotIn("audit", acceptance)
            serialized = json.dumps(acceptance, sort_keys=True)
            for forbidden in ("output", "finding", "path", "prompt", "transcript"):
                self.assertNotIn(forbidden, serialized)

    def assert_preparation_binding(self, node: dict) -> None:
        acceptance = node["acceptance"]
        self.assertEqual(len(acceptance["design_digest"]), 64)
        self.assertEqual(len(acceptance["acceptance_fingerprint"]), 64)

    def assert_advance_rejected_without_change(
        self,
        event: str,
        dispatch_id: str | None = None,
        *,
        node_id: str = NODE_ID,
        repair_node_id: str | None = None,
    ) -> None:
        before = self.workspace_state_bytes()
        self.advance(
            event,
            dispatch_id,
            node_id=node_id,
            repair_node_id=repair_node_id,
            ok=False,
        )
        self.assertEqual(self.workspace_state_bytes(), before)

    def test_public_transition_table_and_next_action_are_pure_and_guarded(self) -> None:
        machine = importlib.import_module("scripts.better_plan.domain.transitions")
        self.assertEqual(machine.transition("awaiting_executor", "executor-dispatched", "executor"), "executor_running")
        self.assertEqual(machine.next_action("repair_required", "executor"), "main_repair_decision")
        self.assertEqual(
            machine.transition("repair_plan_required", "repair-registered", "final_validation"),
            "awaiting_repair",
        )
        self.assertEqual(machine.next_action("awaiting_repair", "final_validation"), "await_repair_completion")
        self.assertEqual(
            machine.transition("awaiting_repair", "repair-completed", "final_validation"),
            "awaiting_regression",
        )
        self.assertEqual(
            machine.transition("awaiting_acceptance_design", "acceptance-designer-dispatched", "acceptance_designer"),
            "acceptance_designer_running",
        )
        self.assertEqual(
            machine.transition("acceptance_designer_running", "acceptance-designer-exited", "acceptance_designer"),
            "awaiting_acceptance_review",
        )
        self.assertEqual(
            machine.transition(
                "awaiting_acceptance_review",
                "acceptance-reviewer-dispatched",
                "acceptance_reviewer",
            ),
            "acceptance_reviewer_running",
        )
        self.assertEqual(
            machine.transition("acceptance_reviewer_running", "acceptance-approved", "acceptance_reviewer"),
            "awaiting_executor",
        )
        self.assertEqual(
            machine.transition("acceptance_reviewer_running", "acceptance-rejected", "acceptance_reviewer"),
            "acceptance_revision_required",
        )
        self.assertEqual(machine.next_action("awaiting_acceptance_design", "implementation"), "dispatch_acceptance_designer")
        self.assertEqual(
            machine.next_action("acceptance_designer_running", "implementation"),
            "await_acceptance_designer_exit",
        )
        self.assertEqual(machine.next_action("awaiting_acceptance_review", "implementation"), "dispatch_acceptance_reviewer")
        self.assertEqual(
            machine.next_action("acceptance_reviewer_running", "implementation"),
            "await_acceptance_reviewer_verdict",
        )
        self.assertEqual(
            machine.next_action("acceptance_revision_required", "implementation"),
            "main_acceptance_decision",
        )
        with self.assertRaises(ValueError):
            machine.transition("awaiting_auditor", "executor-exited", "executor")

    def _design_contract(self, *, acceptance_id: str = "acceptance") -> dict[str, object]:
        design_path = "tests/acceptance-fixture/design.md"
        scaffold_path = "tests/acceptance-fixture/scaffold.py"
        acceptance_path = f"tests/acceptance-fixture/{acceptance_id}.md"
        (self.workspace / design_path).parent.mkdir(parents=True, exist_ok=True)
        (self.workspace / design_path).write_text("design", encoding="utf-8")
        (self.workspace / scaffold_path).write_text("import pathlib\n", encoding="utf-8")
        (self.workspace / acceptance_path).write_text("acceptance checks", encoding="utf-8")
        return {
            "artifact": design_path,
            "owned_paths": [scaffold_path],
            "scaffold_paths": [scaffold_path],
            "acceptance_paths": [acceptance_path],
            "symbols": [
                {
                    "path": scaffold_path,
                    "kind": "module",
                    "name": "acceptance_scaffold",
                    "operation": "modify",
                    "signature": "acceptance_scaffold(input_data: object) -> str",
                }
            ],
            "interfaces": [
                {
                    "name": "acceptance_scaffold",
                    "producer": scaffold_path,
                    "consumers": ["scripts/manifest_tool.py"],
                    "inputs": "validated node and plan payload",
                    "outputs": "bounded acceptance action",
                    "errors": ["ValueError for malformed state"],
                }
            ],
            "dependencies": [
                {"from": "scripts/manifest_tool.py", "to": scaffold_path, "reason": "reads design and acceptance paths"}
            ],
            "decisions": {
                "composition": "function-by-function",
                "algorithms": "constant-time transition lookup",
                "data_structures": "normalized mapping",
                "state": "state file writer only",
                "isolation": "role-specific artifacts only",
                "concurrency": "serialized Plan state mutations",
            },
            "test_seams": ["tests/acceptance_state_machine.py"],
        }

    def _write_workspace_with_design(
        self,
        *,
        final: bool = False,
        status: str = "pending",
        acceptance_id: str = "acceptance",
        regression: str | None = None,
    ) -> None:
        self._write_workspace(final=final, status=status, regression=regression)
        nodes = json.loads(self.checkpoints.read_text(encoding="utf-8"))
        node = next(item for item in nodes if item["id"] == NODE_ID)
        node["design"] = self._design_contract(acceptance_id=acceptance_id)
        self.checkpoints.write_text(json.dumps(nodes), encoding="utf-8")

    def _ensure_design(self, node_id: str = NODE_ID) -> None:
        node = self.state(node_id)
        if "design" in node:
            return
        nodes = json.loads(self.checkpoints.read_text(encoding="utf-8"))
        target = next(item for item in nodes if item["id"] == node_id)
        target["design"] = self._design_contract()
        self.checkpoints.write_text(json.dumps(nodes), encoding="utf-8")

    def _prime_acceptance(self, node_id: str = NODE_ID) -> None:
        self._ensure_design(node_id=node_id)
        action = self.next_action(node_id)
        if action == "dispatch_acceptance_designer":
            designer = self.dispatch("acceptance_designer", node_id=node_id)
            self.assertEqual(self.state(node_id)["acceptance"]["phase"], "acceptance_designer_running")
            self.advance("acceptance-designer-exited", designer, node_id=node_id)
            self.assertEqual(self.next_action(node_id), "dispatch_acceptance_reviewer")
        if self.next_action(node_id) == "dispatch_acceptance_reviewer":
            reviewer = self.dispatch("acceptance_reviewer", node_id=node_id)
            self.assertEqual(self.state(node_id)["acceptance"]["phase"], "acceptance_reviewer_running")
            self.advance("acceptance-approved", reviewer, node_id=node_id)

    def _dispatch_executor(self, node_id: str = NODE_ID) -> str:
        self._prime_acceptance(node_id=node_id)
        phase = self.state(node_id)["acceptance"]["phase"]
        expected_action = "main_repair_decision" if phase == "repair_required" else "dispatch_executor"
        self.assertEqual(self.next_action(node_id), expected_action)
        return self.dispatch("executor", node_id=node_id)

    def _run_full_regression(self, node_id: str = NODE_ID, token: str = "auto-run") -> subprocess.CompletedProcess[str]:
        self._prime_acceptance(node_id=node_id)
        self.assertEqual(self.next_action(node_id), "run_regression")
        return self.advance("regression-requested", token, node_id=node_id)

    def test_next_action_and_dispatch_start_from_acceptance_preparation(self) -> None:
        self._write_workspace_with_design()
        self.assertEqual(self.next_action(), "dispatch_acceptance_designer")
        self.assertNotIn("acceptance", self.state())
        designer = self.dispatch("acceptance_designer")
        self.assertEqual(self.state()["acceptance"]["phase"], "acceptance_designer_running")
        self.assertEqual(self.state()["acceptance"]["attempt"], 0)
        self.assertEqual(self.next_action(), "await_acceptance_designer_exit")
        self.advance("acceptance-designer-exited", designer)
        self.assertEqual(self.state()["acceptance"]["phase"], "awaiting_acceptance_review")
        self.assertEqual(self.next_action(), "dispatch_acceptance_reviewer")
        reviewer = self.dispatch("acceptance_reviewer")
        self.assertEqual(self.state()["acceptance"]["phase"], "acceptance_reviewer_running")
        self.assertEqual(self.next_action(), "await_acceptance_reviewer_verdict")
        self.advance("acceptance-approved", reviewer)
        self.assertEqual(self.state()["acceptance"]["phase"], "awaiting_executor")
        self.assertEqual(self.next_action(), "dispatch_executor")

    def test_reviewer_event_requires_distinct_dispatch_and_executor_gates_before_approval(self) -> None:
        self._write_workspace_with_design()
        self.assertEqual(self.next_action(), "dispatch_acceptance_designer")
        designer = self.dispatch("acceptance_designer")
        self.advance("acceptance-designer-exited", designer)
        self.assertEqual(self.next_action(), "dispatch_acceptance_reviewer")
        self.cli("dispatch", NODE_ID, "--role", "executor", ok=False)
        reviewer = self.dispatch("acceptance_reviewer")
        self.advance("acceptance-approved", reviewer)
        self.assertEqual(self.state()["acceptance"]["phase"], "awaiting_executor")
        self.advance("acceptance-approved", "stale-review", ok=False)
        self.advance("acceptance-designer-exited", "stale-review", ok=False)
        self.cli("dispatch", NODE_ID, "--role", "executor")
        self.assertEqual(self.state()["acceptance"]["phase"], "executor_running")

    def test_inputs_change_invalidation_returns_to_main_acceptance_decision(self) -> None:
        self._write_workspace_with_design(acceptance_id="initial")
        self.assertEqual(self.next_action(), "dispatch_acceptance_designer")
        designer = self.dispatch("acceptance_designer")
        self.advance("acceptance-designer-exited", designer)
        reviewer = self.dispatch("acceptance_reviewer")
        self.advance("acceptance-approved", reviewer)
        self.assertEqual(self.next_action(), "dispatch_executor")
        path = str(self.state()["design"]["acceptance_paths"][0])  # type: ignore[index]
        (self.workspace / str(path)).write_text("changed acceptance mapping", encoding="utf-8")
        self.assertEqual(self.next_action(), "main_acceptance_decision")
        state = self.state()
        self.assertEqual(state["status"], "pending")
        self.assertEqual(state["acceptance"]["phase"], "acceptance_revision_required")
        self.assertEqual(state["acceptance"]["attempt"], 0)
        self.assertEqual(state["acceptance"]["outcome"], "none")
        self.assert_automated_proof_cleared(state)

    def test_repair_required_path_drift_returns_to_main_acceptance_decision(self) -> None:
        self._write_workspace(regression=self._failure_command("acceptance-repair-token"))
        self._ensure_design()
        self._prime_acceptance()
        executor = self._dispatch_executor()
        self.advance("executor-exited", executor)
        self.assertEqual(self.state()["acceptance"]["phase"], "repair_required")
        self.assertEqual(self.next_action(), "main_repair_decision")

        acceptance_path = str(self.state()["design"]["acceptance_paths"][0])  # type: ignore[index]
        (self.workspace / acceptance_path).write_text("updated acceptance contract text", encoding="utf-8")

        self.assertEqual(self.next_action(), "main_acceptance_decision")
        state = self.state()
        self.assertEqual(state["status"], "pending")
        self.assertEqual(state["acceptance"]["phase"], "acceptance_revision_required")
        self.assertEqual(state["acceptance"]["attempt"], 1)
        self.assertEqual(state["acceptance"]["outcome"], "none")
        self.assert_automated_proof_cleared(state)

    def test_scaffold_drift_before_executor_dispatch_returns_to_main_acceptance_decision(self) -> None:
        self._write_workspace_with_design()
        self._prime_acceptance()
        self.assertEqual(self.next_action(), "dispatch_executor")

        scaffold_path = str(self.state()["design"]["scaffold_paths"][0])  # type: ignore[index]
        (self.workspace / scaffold_path).write_text("implemented before executor dispatch\n", encoding="utf-8")

        self.assertEqual(self.next_action(), "main_acceptance_decision")
        state = self.state()
        self.assertEqual(state["status"], "pending")
        self.assertEqual(state["acceptance"]["phase"], "acceptance_revision_required")
        self.assertEqual(state["acceptance"]["attempt"], 0)
        self.assertEqual(state["acceptance"]["outcome"], "none")
        self.assertNotIn("dispatch", state["acceptance"])
        self.assert_automated_proof_cleared(state)

    def test_scaffold_changes_after_acceptance_do_not_reopen_design(self) -> None:
        self._write_workspace_with_design()
        self._prime_acceptance()
        executor = self._dispatch_executor()
        scaffold_path = str(self.state()["design"]["scaffold_paths"][0])  # type: ignore[index]
        (self.workspace / scaffold_path).write_text("implemented scaffold within execution", encoding="utf-8")
        self.advance("executor-exited", executor)
        self.assertEqual(self.next_action(), "dispatch_auditor")
        self.assertEqual(self.state()["acceptance"]["phase"], "awaiting_auditor")

    def test_acceptance_path_drift_after_executor_dispatch_parks_for_main_decision(self) -> None:
        marker = "acceptance-path-drift.marker"
        self._write_workspace_with_design(regression=self._marker_command(marker))
        self._prime_acceptance()
        executor = self._dispatch_executor()
        acceptance_path = str(self.state()["design"]["acceptance_paths"][0])  # type: ignore[index]
        (self.workspace / acceptance_path).write_text("drifted acceptance artifact", encoding="utf-8")
        self.advance("executor-exited", executor)
        self.assertFalse((self.workspace / marker).exists())
        self.assertEqual(self.next_action(), "main_acceptance_decision")
        state = self.state()
        self.assertEqual(state["status"], "pending")
        self.assertEqual(state["acceptance"]["phase"], "acceptance_revision_required")
        self.assertEqual(state["acceptance"]["attempt"], 1)
        self.assertEqual(state["acceptance"]["outcome"], "none")
        self.assertNotIn("dispatch", state["acceptance"])
        self.assert_automated_proof_cleared(state)

    def test_unrelated_file_change_after_acceptance_approval_remains_executor_flow(self) -> None:
        self._write_workspace_with_design(acceptance_id="initial")
        self._prime_acceptance()
        self.assertEqual(self.next_action(), "dispatch_executor")
        unrelated_file = self.workspace / "docs/notes/engineering-notes.txt"
        unrelated_file.parent.mkdir(parents=True, exist_ok=True)
        unrelated_file.write_text("unrelated update", encoding="utf-8")
        self.assertEqual(self.next_action(), "dispatch_executor")
        self.assertEqual(self.state()["acceptance"]["phase"], "awaiting_executor")

    def test_next_action_and_dispatch_lazily_enroll_pending_node(self) -> None:
        before = self.workspace_state_bytes()
        next_action = self.cli("next-action", NODE_ID, ok=False)
        self.assertIn("design", next_action.stderr.lower())
        self.assertEqual(self.workspace_state_bytes(), before)
        self.cli("dispatch", NODE_ID, "--role", "executor", ok=False)
        self.assertEqual(self.workspace_state_bytes(), before)

        self._prime_acceptance()
        self.assertEqual(self.next_action(), "dispatch_executor")
        dispatch_id = self._dispatch_executor()
        state = self.state()
        self.assertEqual(state["status"], "in_progress")
        self.assertEqual(state["acceptance"]["phase"], "executor_running")
        self.assertEqual(state["acceptance"]["attempt"], 1)
        before = self.state_bytes()
        self.assertEqual(self.dispatch("executor"), dispatch_id)
        self.assertEqual(self.state_bytes(), before)

    def test_executor_exit_automatically_routes_regression_pass_and_failure(self) -> None:
        executor = self._dispatch_executor()
        self.advance("executor-exited", executor)
        self.assertEqual(self.state()["acceptance"]["phase"], "awaiting_auditor")
        self._write_workspace(regression=self._failure_command("synthetic-regression-token"))
        executor = self._dispatch_executor()
        self.advance("executor-exited", executor)
        self.assertEqual(self.state()["acceptance"]["phase"], "repair_required")

    def test_audit_failure_repairs_and_fresh_pass_automatically_completes(self) -> None:
        executor = self._dispatch_executor()
        self.advance("executor-exited", executor)
        auditor = self.dispatch("auditor")
        self.advance("audit-failed", auditor)
        self.assertEqual(self.state()["acceptance"]["phase"], "repair_required")
        self.assertEqual(self.next_action(), "main_repair_decision")
        executor = self._dispatch_executor()
        self.advance("executor-exited", executor)
        auditor = self.dispatch("auditor")
        self.advance("audit-passed", auditor)
        self.assertEqual(self.state()["status"], "completed")

    def test_manual_stale_and_duplicate_events_are_rejected_without_mutation(self) -> None:
        executor = self._dispatch_executor()
        self.cli("check", NODE_ID, "--criterion", "0", ok=False)
        self.cli("complete", NODE_ID, ok=False)
        self.advance("executor-exited", "stale-dispatch", ok=False)
        self.advance("executor-exited", executor)
        auditor = self.dispatch("auditor")
        self.artifact.write_text("changed-after-regression", encoding="utf-8")
        before = self.state_bytes()
        self.advance("audit-passed", auditor, ok=False)
        self.assertEqual(self.state_bytes(), before)
        # Restore the fingerprint, accept once, then prove replay is byte-for-byte inert.
        self.artifact.write_text("initial", encoding="utf-8")
        self.advance("audit-passed", auditor)
        before = self.state_bytes()
        self.advance("audit-passed", auditor, ok=False)
        self.assertEqual(self.state_bytes(), before)

    def test_delivery_manual_commands_are_rejected_before_enrollment_without_effects(self) -> None:
        commands = (
            ("start", ("start", NODE_ID)),
            ("regress", ("regress", NODE_ID)),
            ("check", ("check", NODE_ID, "--criterion", "0")),
            ("complete", ("complete", NODE_ID)),
        )
        for final in (False, True):
            for status in ("pending", "in_progress"):
                for name, arguments in commands:
                    with self.subTest(role="final_validation" if final else "implementation", status=status, command=name):
                        marker = f"manual-{int(final)}-{status}-{name}.marker"
                        self._write_workspace(
                            final=final,
                            regression=self._marker_command(marker),
                            status=status,
                        )
                        before = self.workspace_state_bytes()
                        result = self.cli(*arguments, ok=False)
                        self.assertIn("automated acceptance", result.stderr.lower())
                        self.assertEqual(self.workspace_state_bytes(), before)
                        self.assertFalse((self.workspace / marker).exists())

    def test_foundation_role_keeps_its_real_manual_evidence_path(self) -> None:
        self._write_workspace()
        node = self.state()
        node["role"] = "validation_matrix"
        node.pop("regression")
        self.checkpoints.write_text(json.dumps([node]), encoding="utf-8")
        self.cli("check", NODE_ID, "--criterion", "0", "--evidence", "Validation artifact reviewed.")
        self.assertTrue(self.state()["acceptance_criteria"][0]["checked"])

    def test_final_full_runs_once_then_needs_fresh_audit_and_failure_plans_repair(self) -> None:
        marker = "full.marker"
        self._write_workspace(final=True, regression=self._marker_command(marker))
        self._run_full_regression(token="full-1")
        self.assertEqual((self.workspace / marker).read_text(encoding="utf-8"), "1")
        self.assertEqual(self.state()["acceptance"]["phase"], "awaiting_auditor")
        before = self.state_bytes()
        self.advance("regression-requested", "full-1", ok=False)
        self.assertEqual(self.state_bytes(), before)
        self.assertEqual((self.workspace / marker).read_text(encoding="utf-8"), "1")
        auditor = self.dispatch("auditor")
        self.advance("audit-passed", auditor)
        self.assertEqual(self.state()["status"], "completed")
        self._write_workspace(final=True, regression=self._failure_command("synthetic-full-token"))
        self._run_full_regression(token="full-fail")
        self.assertEqual(self.state()["acceptance"]["phase"], "repair_plan_required")
        self.assertEqual(self.state()["status"], "pending")
        action = json.loads(self.cli("next-action", NODE_ID).stdout)
        self.assertEqual(action["action"], "create_repair_plan")

    def test_final_audit_failure_parks_pending_and_releases_the_active_slot(self) -> None:
        self._write_workspace(final=True)
        self._run_full_regression(token="full-pass")
        auditor = self.dispatch("auditor")
        self.advance("audit-failed", auditor)
        self.assertEqual(self.state()["status"], "pending")
        self.assertEqual(self.state()["acceptance"]["phase"], "repair_plan_required")
        self.assertNotIn("last_pass", self.state()["regression"])
        self.assertEqual(json.loads(self.cli("next-action", NODE_ID).stdout)["action"], "create_repair_plan")

    def test_final_repair_registration_and_automatic_reacceptance_do_not_deadlock(self) -> None:
        marker = "repairable-full.marker"
        self._write_workspace(
            final=True,
            regression=self._repairable_final_command(marker),
            with_history=True,
        )
        historical_before = json.dumps(self.state(HISTORY_ID), sort_keys=True)

        self._run_full_regression(token="final-attempt-1")
        self.assertEqual((self.workspace / marker).read_text(encoding="utf-8"), "1")
        self.assertEqual(self.state()["status"], "pending")
        self.assertEqual(self.state()["acceptance"]["phase"], "repair_plan_required")

        before = self.workspace_state_bytes()
        self.advance("repair-registered", repair_node_id=WRONG_ID, ok=False)
        self.assertEqual(self.workspace_state_bytes(), before)

        self._planner_adds_repair_prerequisite()
        before = self.workspace_state_bytes()
        self.advance("repair-registered", repair_node_id=HISTORY_ID, ok=False)
        self.assertEqual(self.workspace_state_bytes(), before)

        registered = self.advance("repair-registered", repair_node_id=REPAIR_ID)
        self.assertEqual(json.loads(registered.stdout)["action"], "await_repair_completion")
        self.assertEqual(self.state()["status"], "pending")
        registered_state = self.state()
        self.assertEqual(registered_state["acceptance"]["phase"], "awaiting_repair")
        self.assertEqual(registered_state["acceptance"]["attempt"], 0)
        self.assertEqual(registered_state["acceptance"]["outcome"], "regression_failed")
        self.assertEqual(registered_state["acceptance"]["repair_node_id"], REPAIR_ID)
        self.assert_preparation_binding(registered_state)

        before = self.workspace_state_bytes()
        self.advance("repair-completed", repair_node_id=WRONG_ID, ok=False)
        self.assertEqual(self.workspace_state_bytes(), before)
        self.advance("repair-completed", repair_node_id=REPAIR_ID, ok=False)
        self.assertEqual(self.workspace_state_bytes(), before)

        executor = self._dispatch_executor(node_id=REPAIR_ID)
        self.artifact.write_text("repaired", encoding="utf-8")
        self.advance("executor-exited", executor, node_id=REPAIR_ID)
        auditor = self.dispatch("auditor", REPAIR_ID)
        self.advance("audit-passed", auditor, node_id=REPAIR_ID)
        self.assertEqual(self.state(REPAIR_ID)["status"], "completed")

        resumed = self.advance("repair-completed", repair_node_id=REPAIR_ID)
        self.assertEqual(json.loads(resumed.stdout)["action"], "run_regression")
        self.assertEqual(self.state()["status"], "pending")
        self.assertEqual(self.state()["acceptance"]["phase"], "awaiting_regression")
        before = self.workspace_state_bytes()
        self.advance("repair-completed", repair_node_id=REPAIR_ID, ok=False)
        self.assertEqual(self.workspace_state_bytes(), before)

        self._run_full_regression(token="final-attempt-2")
        self.assertEqual((self.workspace / marker).read_text(encoding="utf-8"), "2")
        auditor = self.dispatch("auditor")
        self.advance("audit-passed", auditor)
        self.assertEqual(self.state()["status"], "completed")
        self.assertEqual(json.dumps(self.state(HISTORY_ID), sort_keys=True), historical_before)

    def test_failure_output_and_cli_response_never_persist_sensitive_text(self) -> None:
        token = "synthetic-credential-7f3e9b"
        self._write_workspace(regression=self._failure_command(token))
        executor = self._dispatch_executor()
        response = self.advance("executor-exited", executor)
        persisted = self.state_bytes().decode("utf-8")
        for forbidden in (token, "/synthetic/private/acceptance-output", "https://synthetic.invalid/private"):
            self.assertNotIn(forbidden, persisted)
            self.assertNotIn(forbidden, response.stdout + response.stderr)

    def test_pause_and_block_cancel_implementation_dispatches_before_fresh_resume(self) -> None:
        for command_name, expected_status in (("pause", "pending"), ("block", "blocked")):
            for phase in ("executor_running", "auditor_running"):
                with self.subTest(command=command_name, phase=phase):
                    self._write_workspace()
                    executor = self._dispatch_executor()
                    stale_event = "executor-exited"
                    stale_dispatch = executor
                    if phase == "auditor_running":
                        self.advance("executor-exited", executor)
                        stale_dispatch = self.dispatch("auditor")
                        stale_event = "audit-passed"
                        self.assertTrue(self.state()["acceptance_criteria"][0]["checked"])

                    reason = "Yield for another scoped task." if command_name == "pause" else "External approval pending."
                    self.cli(command_name, NODE_ID, "--reason", reason)
                    state = self.state()
                    self.assertEqual(state["status"], expected_status)
                    self.assertEqual(state["acceptance"]["phase"], "awaiting_executor")
                    self.assertEqual(state["acceptance"]["attempt"], 1)
                    self.assertEqual(state["acceptance"]["outcome"], "none")
                    self.assert_preparation_binding(state)
                    self.assertEqual(state["status_reason"], reason)
                    self.assertEqual(self.next_action(), "dispatch_executor")
                    self.assert_automated_proof_cleared(state)
                    self.assert_advance_rejected_without_change(stale_event, stale_dispatch)

                    if command_name == "pause":
                        before = self.workspace_state_bytes()
                        self.cli("pause", NODE_ID, "--reason", reason, ok=False)
                        self.assertEqual(self.workspace_state_bytes(), before)
                    else:
                        before = self.workspace_state_bytes()
                        self.cli("block", NODE_ID, "--reason", reason)
                        self.assertEqual(self.workspace_state_bytes(), before)

                    fresh_executor = self._dispatch_executor()
                    resumed = self.state()
                    self.assertEqual(resumed["status"], "in_progress")
                    self.assertEqual(resumed["acceptance"]["phase"], "executor_running")
                    self.assertEqual(resumed["acceptance"]["attempt"], 2)
                    self.assertNotEqual(fresh_executor, stale_dispatch)
                    self.assertNotIn("status_reason", resumed)
                    self.assert_advance_rejected_without_change(stale_event, stale_dispatch)

    def test_pause_and_block_reset_final_auditor_to_a_fresh_full_regression(self) -> None:
        for command_name, expected_status in (("pause", "pending"), ("block", "blocked")):
            with self.subTest(command=command_name):
                marker = f"final-{command_name}.marker"
                self._write_workspace(final=True, regression=self._marker_command(marker))
                self._run_full_regression(token=f"initial-{command_name}")
                stale_auditor = self.dispatch("auditor")
                self.assertTrue(self.state()["acceptance_criteria"][0]["checked"])

                reason = "Yield for another scoped task." if command_name == "pause" else "External approval pending."
                self.cli(command_name, NODE_ID, "--reason", reason)
                state = self.state()
                self.assertEqual(state["status"], expected_status)
                self.assertEqual(state["acceptance"]["phase"], "awaiting_regression")
                self.assertEqual(state["acceptance"]["attempt"], 0)
                self.assertEqual(state["acceptance"]["outcome"], "none")
                self.assert_preparation_binding(state)
                self.assertEqual(self.next_action(), "run_regression")
                self.assert_automated_proof_cleared(state)
                self.assert_advance_rejected_without_change("audit-passed", stale_auditor)

                self._run_full_regression(token=f"resumed-{command_name}")
                resumed = self.state()
                self.assertEqual(resumed["status"], "in_progress")
                self.assertEqual(resumed["acceptance"]["phase"], "awaiting_auditor")
                self.assertNotIn("status_reason", resumed)
                self.assertEqual((self.workspace / marker).read_text(encoding="utf-8"), "2")
                self.assert_advance_rejected_without_change("audit-passed", stale_auditor)

    def test_skip_cancels_active_cycles_and_is_terminal(self) -> None:
        for final in (False, True):
            with self.subTest(role="final_validation" if final else "implementation"):
                self._write_workspace(final=final)
                if final:
                    self._run_full_regression(token="active-final")
                    stale_dispatch = self.dispatch("auditor")
                    stale_event = "audit-passed"
                else:
                    stale_dispatch = self._dispatch_executor()
                    stale_event = "executor-exited"

                reason = "Delivery intentionally removed from this plan."
                self.cli("skip", NODE_ID, "--reason", reason)
                state = self.state()
                self.assertEqual(state["status"], "skipped")
                self.assertEqual(state["status_reason"], reason)
                self.assertNotIn("acceptance", state)
                self.assertEqual(self.next_action(), "none")
                self.assert_automated_proof_cleared(state)
                self.assert_advance_rejected_without_change(stale_event, stale_dispatch)

                before = self.workspace_state_bytes()
                self.cli("skip", NODE_ID, "--reason", reason)
                self.assertEqual(self.workspace_state_bytes(), before)

                before = self.workspace_state_bytes()
                self.cli("block", NODE_ID, "--reason", "Cannot reopen skipped delivery.", ok=False)
                self.assertEqual(self.workspace_state_bytes(), before)
                if final:
                    self.assert_advance_rejected_without_change("regression-requested", "new-final")
                else:
                    before = self.workspace_state_bytes()
                    self.cli("dispatch", NODE_ID, "--role", "executor", ok=False)
                    self.assertEqual(self.workspace_state_bytes(), before)

    def test_unenrolled_delivery_can_block_resume_or_skip_without_manual_acceptance(self) -> None:
        for final in (False, True):
            role = "final_validation" if final else "implementation"
            expected_action = "dispatch_acceptance_designer"
            with self.subTest(role=role, route="resume"):
                self._write_workspace(final=final)
                self._ensure_design()
                before = self.workspace_state_bytes()
                self.cli("pause", NODE_ID, "--reason", "Nothing has started.", ok=False)
                self.assertEqual(self.workspace_state_bytes(), before)

                reason = "External decision pending."
                self.cli("block", NODE_ID, "--reason", reason)
                self.assertEqual(self.state()["status"], "blocked")
                self.assertNotIn("acceptance", self.state())
                self.assertEqual(self.next_action(), expected_action)
                before = self.workspace_state_bytes()
                self.cli("block", NODE_ID, "--reason", reason)
                self.assertEqual(self.workspace_state_bytes(), before)

                if final:
                    self._run_full_regression(token="blocked-final-resume")
                    self.assertEqual(self.state()["acceptance"]["phase"], "awaiting_auditor")
                else:
                    self._dispatch_executor()
                    self.assertEqual(self.state()["acceptance"]["phase"], "executor_running")
                self.assertEqual(self.state()["status"], "in_progress")
                self.assertNotIn("status_reason", self.state())

            for initially_blocked in (False, True):
                with self.subTest(role=role, route="skip", initially_blocked=initially_blocked):
                    self._write_workspace(final=final)
                    self._ensure_design()
                    if initially_blocked:
                        self.cli("block", NODE_ID, "--reason", "External decision pending.")
                    self.cli("skip", NODE_ID, "--reason", "Delivery intentionally removed from this plan.")
                    state = self.state()
                    self.assertEqual(state["status"], "skipped")
                    self.assertNotIn("acceptance", state)
                    self.assertEqual(self.next_action(), "none")
                    self.assert_automated_proof_cleared(state)

    def test_blocked_final_repair_handoff_resumes_without_losing_its_binding(self) -> None:
        self._write_workspace(
            final=True,
            regression=self._failure_command("synthetic-repair-block-token"),
            with_history=True,
        )
        self._run_full_regression(token="repair-plan-attempt")
        failed = dict(self.state()["acceptance"])
        self.cli("block", NODE_ID, "--reason", "Repair design awaits approval.")
        blocked = self.state()
        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(blocked["acceptance"], failed)
        self.assertEqual(self.next_action(), "create_repair_plan")

        self._planner_adds_repair_prerequisite()
        registered = self.advance("repair-registered", repair_node_id=REPAIR_ID)
        self.assertEqual(json.loads(registered.stdout)["action"], "await_repair_completion")
        state = self.state()
        self.assertEqual(state["status"], "pending")
        self.assertNotIn("status_reason", state)
        self.assertEqual(state["acceptance"]["outcome"], failed["outcome"])
        self.assertEqual(state["acceptance"]["repair_node_id"], REPAIR_ID)
        self.assert_advance_rejected_without_change("repair-registered", repair_node_id=REPAIR_ID)

        reason = "Repair execution is externally blocked."
        self.cli("block", NODE_ID, "--reason", reason)
        state = self.state()
        self.assertEqual(state["status"], "blocked")
        self.assertEqual(state["acceptance"]["phase"], "awaiting_repair")
        self.assertEqual(state["acceptance"]["repair_node_id"], REPAIR_ID)
        self.assertEqual(state["acceptance"]["outcome"], failed["outcome"])
        self.assertEqual(self.next_action(), "await_repair_completion")
        self.assert_advance_rejected_without_change("repair-completed", repair_node_id=REPAIR_ID)

        executor = self._dispatch_executor(node_id=REPAIR_ID)
        self.advance("executor-exited", executor, node_id=REPAIR_ID)
        auditor = self.dispatch("auditor", REPAIR_ID)
        self.advance("audit-passed", auditor, node_id=REPAIR_ID)
        self.assertEqual(self.state(REPAIR_ID)["status"], "completed")

        resumed = self.advance("repair-completed", repair_node_id=REPAIR_ID)
        self.assertEqual(json.loads(resumed.stdout)["action"], "run_regression")
        state = self.state()
        self.assertEqual(state["status"], "pending")
        self.assertEqual(state["acceptance"]["phase"], "awaiting_regression")
        self.assertEqual(state["acceptance"]["attempt"], failed["attempt"])
        self.assertNotIn("status_reason", state)
        self.assert_advance_rejected_without_change("repair-completed", repair_node_id=REPAIR_ID)

    def test_skip_terminates_final_repair_phases(self) -> None:
        for phase in ("repair_plan_required", "awaiting_repair"):
            with self.subTest(phase=phase):
                self._write_workspace(
                    final=True,
                    regression=self._failure_command("synthetic-repair-skip-token"),
                    with_history=True,
                )
                self._run_full_regression(token=f"skip-{phase}")
                if phase == "awaiting_repair":
                    self._planner_adds_repair_prerequisite()
                    self.advance("repair-registered", repair_node_id=REPAIR_ID)

                self.cli("skip", NODE_ID, "--reason", "Final repair work intentionally removed.")
                state = self.state()
                self.assertEqual(state["status"], "skipped")
                self.assertNotIn("acceptance", state)
                self.assertEqual(self.next_action(), "none")
                self.assert_automated_proof_cleared(state)

                if phase == "repair_plan_required":
                    self.assert_advance_rejected_without_change("repair-registered", repair_node_id=REPAIR_ID)
                else:
                    self.assert_advance_rejected_without_change("repair-completed", repair_node_id=REPAIR_ID)


if __name__ == "__main__":
    unittest.main()
