"""Exact native child-completion boundary tests."""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.better_plan.application.agent_completion import reduce_agent_completion


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_TOOL = ROOT / "scripts" / "manifest_tool.py"
HOOK_TOOL = ROOT / "scripts" / "hook_tool.py"
PLAN_ID = "718a7541-4e80-46ce-9acc-e77a68d1f406"
DESIGN_ID = "1ec7bbc3-88af-4df8-ad4f-468550bdc4c1"
WORK_ID = "4ec7bbc3-88af-4df8-ad4f-468550bdc4c1"
FINAL_ID = "5ec7bbc3-88af-4df8-ad4f-468550bdc4c2"
PLAN_TWO_ID = "818a7541-4e80-46ce-9acc-e77a68d1f407"
DESIGN_TWO_ID = "2ec7bbc3-88af-4df8-ad4f-468550bdc4c1"
WORK_TWO_ID = "6ec7bbc3-88af-4df8-ad4f-468550bdc4c1"
FINAL_TWO_ID = "7ec7bbc3-88af-4df8-ad4f-468550bdc4c2"


def command(program: str) -> str:
    values = [sys.executable, "-c", program]
    return subprocess.list2cmdline(values) if sys.platform == "win32" else shlex.join(values)


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
        self._write_workspace()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _design(self, stem: str) -> dict[str, object]:
        artifact = f"tests/agent-completion/{stem}-design.md"
        owned = f"src/{stem}.py"
        acceptance = f"tests/agent-completion/{stem}-acceptance.md"
        for relative, content in (
            (artifact, "design\n"),
            (owned, "VALUE = 1\n"),
            (acceptance, "acceptance\n"),
        ):
            path = self.project / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return {
            "artifact": artifact,
            "owned_paths": [owned],
            "scaffold_paths": [owned],
            "acceptance_paths": [acceptance],
            "symbols": [
                {
                    "path": owned,
                    "kind": "module",
                    "name": stem,
                    "operation": "modify",
                    "signature": f"{stem}() -> int",
                }
            ],
            "interfaces": [
                {
                    "name": stem,
                    "producer": owned,
                    "consumers": [acceptance],
                    "inputs": "one bounded request",
                    "outputs": "one bounded result",
                    "errors": ["ValueError for invalid input"],
                }
            ],
            "dependencies": [],
            "decisions": {
                "composition": "one reducer",
                "algorithms": "constant-time phase routing",
                "data_structures": "bounded mapping",
                "state": "state tool owns writes",
                "isolation": "one fresh child",
                "concurrency": "manifest lock",
            },
            "test_seams": [acceptance],
        }

    def _node(
        self,
        node_id: str,
        role: str,
        stem: str,
        prerequisites: list[str],
        *,
        status: str = "pending",
        accepted: bool = False,
    ) -> dict[str, object]:
        node: dict[str, object] = {
            "id": node_id,
            "status": status,
            "role": role,
            "prerequisites": prerequisites,
            "platform": "any",
            "difficulty": "critical" if role != "implementation" else "standard",
            "goal": f"Exercise {role} child completion.",
            "description": (
                f"Scope: Closure: scenario - {stem}. Context: a native child exists. "
                "Target: accept only its exact final callback. Design Considerations: bind opaque identity. "
                "Design Value: prevents early asynchronous completion. Constraints & Risks: no raw output."
            ),
            "requirements": ["REQ-001"],
            "acceptance_criteria": [
                {"checked": accepted, "text": "Only an exact final callback advances state."}
            ],
            "commit": {"repository": ".git", "message": f"test: {stem}", "target": stem},
            "next": [],
        }
        if not accepted:
            node["design"] = self._design(stem)
        if role in {"implementation", "final_validation"}:
            node["regression"] = {
                "scope": "full" if role == "final_validation" else "focused",
                "commands": [command("pass")],
                "criteria": [0],
                "paths": [f"src/{stem}.py"],
            }
        if accepted:
            node["acceptance"] = {"phase": "accepted", "attempt": 0, "outcome": "accepted"}
        return node

    def _write_workspace(self) -> None:
        design = self._node(
            DESIGN_ID,
            "group_design",
            "group_design",
            [],
            status="completed",
            accepted=True,
        )
        work = self._node(WORK_ID, "implementation", "worker", [DESIGN_ID])
        final = self._node(FINAL_ID, "final_validation", "final", [WORK_ID])
        design["next"] = [WORK_ID]
        work["next"] = [FINAL_ID]
        self.checkpoints.write_text(json.dumps([design, work, final]), encoding="utf-8")
        manifest = [
            {
                "id": PLAN_ID,
                "status": "in_progress",
                "title": "Agent completion fixture",
                "directory": "agent-completion",
                "source_files": [],
                "purpose": "Exercise exact child completion correlation.",
                "goal": "Validate native final callback handling.",
                "description": "One isolated task group.",
                "checkpoints": "agent-completion/Checkpoints.json",
                "kind": "group",
                "decision_issues": [],
            }
        ]
        (self.workspace / "Manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def _append_second_group(self) -> None:
        plan_dir = self.workspace / "agent-completion-two"
        plan_dir.mkdir()
        design = self._node(
            DESIGN_TWO_ID,
            "group_design",
            "group_design_two",
            [],
            status="completed",
            accepted=True,
        )
        work = self._node(
            WORK_TWO_ID,
            "implementation",
            "worker_two",
            [DESIGN_TWO_ID],
        )
        final = self._node(
            FINAL_TWO_ID,
            "final_validation",
            "final_two",
            [WORK_TWO_ID],
        )
        design["next"] = [WORK_TWO_ID]
        work["next"] = [FINAL_TWO_ID]
        (plan_dir / "Checkpoints.json").write_text(
            json.dumps([design, work, final]),
            encoding="utf-8",
        )
        manifest_path = self.workspace / "Manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.append(
            {
                "id": PLAN_TWO_ID,
                "status": "pending",
                "title": "Second completion fixture",
                "directory": "agent-completion-two",
                "source_files": [],
                "purpose": "Exercise exact completion across concurrent task groups.",
                "goal": "Correlate one of multiple active native children.",
                "description": "A second isolated task group.",
                "checkpoints": "agent-completion-two/Checkpoints.json",
                "kind": "group",
                "decision_issues": [],
            }
        )
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    def cli(self, *arguments: str) -> dict[str, object]:
        result = subprocess.run(
            [sys.executable, str(MANIFEST_TOOL), *arguments],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def state(self, node_id: str = WORK_ID) -> dict[str, object]:
        values = json.loads(self.checkpoints.read_text(encoding="utf-8"))
        return next(value for value in values if value["id"] == node_id)

    def dispatch_and_bind(self, node_id: str, role: str, agent_id: str) -> str:
        dispatch = self.cli(
            "dispatch",
            node_id,
            str(self.workspace),
            "--role",
            role,
        )
        dispatch_id = str(dispatch["dispatch_id"])
        self.cli(
            "bind-agent",
            node_id,
            str(self.workspace),
            "--dispatch-id",
            dispatch_id,
            "--agent-id",
            agent_id,
        )
        return dispatch_id

    def run_hook(
        self,
        payload: dict[str, object],
        *,
        agent: str = "codex",
    ) -> dict[str, object]:
        result = subprocess.run(
            [
                sys.executable,
                str(HOOK_TOOL),
                "--agent",
                agent,
                "--event",
                "agent-complete",
                "--managed-by",
                "better-plan",
            ],
            cwd=ROOT,
            input=json.dumps({"cwd": str(self.project), **payload}),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def codex_callback(
        self,
        agent_id: str,
        *,
        final: object = True,
        node_id: str | None = None,
        dispatch_id: str | None = None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Agent",
            "agent_id": agent_id,
            "final": final,
        }
        if node_id is not None:
            payload["node_id"] = node_id
        if dispatch_id is not None:
            payload["dispatch_id"] = dispatch_id
        return self.run_hook(payload)

    def close_implementation(self) -> None:
        worker_id = self.dispatch_and_bind(WORK_ID, "worker", "host.worker-1")
        self.codex_callback(
            "host.worker-1",
            node_id=WORK_ID,
            dispatch_id=worker_id,
        )
        verifier_id = self.dispatch_and_bind(WORK_ID, "verifier", "host.verifier-1")
        self.codex_callback(
            "host.verifier-1",
            node_id=WORK_ID,
            dispatch_id=verifier_id,
        )

    def test_spawn_return_nonfinal_wrong_id_and_wrong_node_are_noops(self) -> None:
        dispatch_id = self.dispatch_and_bind(WORK_ID, "worker", "host.worker-1")
        before = self.checkpoints.read_bytes()
        for payload in (
            self.codex_callback("host.worker-1", final=False),
            self.codex_callback("host.unrelated-1"),
            self.codex_callback(
                "host.worker-1",
                node_id=FINAL_ID,
                dispatch_id=dispatch_id,
            ),
            self.codex_callback(
                "host.worker-1",
                node_id=WORK_ID,
                dispatch_id="wrong-dispatch",
            ),
        ):
            self.assertEqual(payload, {})
            self.assertEqual(self.checkpoints.read_bytes(), before)
        self.assertIsNone(
            reduce_agent_completion(
                self.workspace / "Manifest.json",
                agent_id="host.worker-1",
                final=False,
            )
        )

    def test_exact_bound_worker_final_routes_verifier_and_replay_is_noop(self) -> None:
        dispatch_id = self.dispatch_and_bind(WORK_ID, "worker", "host.worker-1")
        response = self.codex_callback(
            "host.worker-1",
            node_id=WORK_ID,
            dispatch_id=dispatch_id,
        )
        self.assertEqual(self.state()["acceptance"]["phase"], "awaiting_verifier")
        context = response["hookSpecificOutput"]["additionalContext"]
        self.assertIn("action dispatch_verifier", context)
        self.assertIn("write-capable Verifier", context)
        after = self.checkpoints.read_bytes()
        self.assertEqual(self.codex_callback("host.worker-1"), {})
        self.assertEqual(self.checkpoints.read_bytes(), after)

    def test_bound_agent_id_selects_one_of_multiple_active_task_groups(self) -> None:
        first_dispatch = self.dispatch_and_bind(WORK_ID, "worker", "host.worker-1")
        self._append_second_group()
        second_dispatch = self.dispatch_and_bind(
            WORK_TWO_ID,
            "worker",
            "host.worker-2",
        )

        first = self.codex_callback(
            "host.worker-1",
            dispatch_id=first_dispatch,
        )

        self.assertIn("hookSpecificOutput", first)
        self.assertEqual(self.state(WORK_ID)["acceptance"]["phase"], "awaiting_verifier")
        second_state = json.loads(
            (self.workspace / "agent-completion-two" / "Checkpoints.json").read_text(
                encoding="utf-8"
            )
        )[1]
        self.assertEqual(second_state["acceptance"]["phase"], "worker_running")
        second = self.codex_callback(
            "host.worker-2",
            node_id=WORK_TWO_ID,
            dispatch_id=second_dispatch,
        )
        self.assertIn("hookSpecificOutput", second)

    def test_exact_bound_verifier_final_completes_implementation(self) -> None:
        worker_id = self.dispatch_and_bind(WORK_ID, "worker", "host.worker-1")
        self.codex_callback("host.worker-1", dispatch_id=worker_id)
        verifier_id = self.dispatch_and_bind(WORK_ID, "verifier", "host.verifier-1")
        response = self.codex_callback(
            "host.verifier-1",
            node_id=WORK_ID,
            dispatch_id=verifier_id,
        )
        self.assertEqual(self.state()["status"], "completed")
        self.assertIn("action complete_node", response["hookSpecificOutput"]["additionalContext"])

    def test_reviewer_final_returns_decisions_to_main_and_is_replay_safe(self) -> None:
        self.close_implementation()
        self.cli(
            "advance",
            FINAL_ID,
            str(self.workspace),
            "--event",
            "regression-requested",
        )
        reviewer_id = self.dispatch_and_bind(FINAL_ID, "reviewer", "host.reviewer-1")
        response = self.codex_callback(
            "host.reviewer-1",
            node_id=FINAL_ID,
            dispatch_id=reviewer_id,
        )
        state = self.state(FINAL_ID)
        self.assertEqual(state["acceptance"]["phase"], "reviewer_complete")
        self.assertEqual(state["acceptance"]["review"]["dispatch_id"], reviewer_id)
        context = response["hookSpecificOutput"]["additionalContext"]
        self.assertIn("action main_reviewer_decision", context)
        self.assertIn("report immediate items", context)
        after = self.checkpoints.read_bytes()
        self.assertEqual(self.codex_callback("host.reviewer-1"), {})
        self.assertEqual(self.checkpoints.read_bytes(), after)

    def test_claude_advances_only_on_explicit_subagent_stop(self) -> None:
        dispatch_id = self.dispatch_and_bind(WORK_ID, "worker", "host.worker-1")
        before = self.checkpoints.read_bytes()
        post_tool = self.run_hook(
            {
                "hook_event_name": "PostToolUse",
                "agent_id": "host.worker-1",
                "agent_type": "worker-standard",
                "final": True,
                "dispatch_id": dispatch_id,
                "node_id": WORK_ID,
            },
            agent="claude",
        )
        self.assertEqual(post_tool, {})
        self.assertEqual(self.checkpoints.read_bytes(), before)
        stopped = self.run_hook(
            {
                "hook_event_name": "SubagentStop",
                "agent_id": "host.worker-1",
                "agent_type": "worker-standard",
                "final": True,
                "dispatch_id": dispatch_id,
                "node_id": WORK_ID,
            },
            agent="claude",
        )
        self.assertIn("hookSpecificOutput", stopped)
        self.assertEqual(self.state()["acceptance"]["phase"], "awaiting_verifier")


if __name__ == "__main__":
    unittest.main()
