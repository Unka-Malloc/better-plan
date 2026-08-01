"""End-to-end contracts for grouped Designer/Worker/Verifier/Reviewer state."""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.better_plan.domain import transitions


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "scripts" / "manifest_tool.py"
PLAN_ID = "9b1e2d3c-4a5b-4c6d-8e9f-0123456789ab"
DESIGN_ID = "1b2c3d4e-5f6a-478b-9c0d-123456789abc"
WORK_ID = "2c3d4e5f-6a7b-48c9-9d0e-123456789abc"
WORK_TWO_ID = "5f607182-9cad-4be2-8f30-456789abcdef"
FINAL_ID = "3d4e5f60-7a8b-49c0-8d1e-23456789abcd"
REPAIR_ID = "4e5f6071-8b9c-4ad1-9e2f-3456789abcde"
PLAN_DIR = Path("docs/plan/group-fixture")


def shell_command(program: str) -> str:
    values = [sys.executable, "-c", program]
    return subprocess.list2cmdline(values) if sys.platform == "win32" else shlex.join(values)


class GroupLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.plan_dir = self.root / PLAN_DIR
        self.plan_dir.mkdir(parents=True)
        self.checkpoints = self.plan_dir / "Checkpoints.json"
        self.bound_agents: dict[str, str] = {}
        self._write_workspace()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _design(self, stem: str) -> dict[str, object]:
        artifact = f"docs/{stem}-design.md"
        owned = f"src/{stem}.py"
        acceptance = f"tests/{stem}-acceptance.md"
        for relative, content in (
            (artifact, "design"),
            (owned, "VALUE = 1\n"),
            (acceptance, "acceptance"),
        ):
            path = self.root / relative
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
                    "signature": f"{stem}(value: object) -> str",
                }
            ],
            "interfaces": [
                {
                    "name": stem,
                    "producer": owned,
                    "consumers": [acceptance],
                    "inputs": "validated input",
                    "outputs": "bounded result",
                    "errors": ["ValueError for invalid input"],
                }
            ],
            "dependencies": [],
            "decisions": {
                "composition": "small functions",
                "algorithms": "constant-time lookup",
                "data_structures": "bounded mapping",
                "state": "explicit state only",
                "isolation": "fresh child context",
                "concurrency": "serialized state writes",
            },
            "test_seams": [acceptance],
        }

    def _base_node(
        self,
        node_id: str,
        role: str,
        stem: str,
        prerequisites: list[str],
        *,
        difficulty: str,
    ) -> dict[str, object]:
        node: dict[str, object] = {
            "id": node_id,
            "status": "pending",
            "role": role,
            "prerequisites": prerequisites,
            "platform": "any",
            "difficulty": difficulty,
            "goal": f"Exercise the {role} lifecycle.",
            "description": (
                f"Scope: Closure: scenario - {stem}; isolated fixture files. "
                "Context: exercise current grouped orchestration. "
                "Target: complete only this bounded Node. "
                "Design Considerations: deterministic state and exact child identity. "
                "Design Value: makes lifecycle regressions observable. "
                "Constraints & Risks: no external data or unrelated work."
            ),
            "requirements": ["REQ-001"],
            "acceptance_criteria": [
                {"checked": False, "text": f"The {role} contract completes with current evidence."}
            ],
            "commit": {
                "repository": ".git",
                "message": f"test: {stem}",
                "target": f"{stem} fixture",
            },
            "next": [],
            "design": self._design(stem),
        }
        if role in {"implementation", "final_validation"}:
            node["regression"] = {
                "scope": "full" if role == "final_validation" else "focused",
                "commands": [shell_command("pass")],
                "criteria": [0],
                "paths": [f"src/{stem}.py"],
            }
        return node

    def _write_workspace(self, *, final_program: str = "pass") -> None:
        designer = self._base_node(
            DESIGN_ID,
            "group_design",
            "group_design",
            [],
            difficulty="critical",
        )
        worker = self._base_node(
            WORK_ID,
            "implementation",
            "implementation",
            [DESIGN_ID],
            difficulty="standard",
        )
        final = self._base_node(
            FINAL_ID,
            "final_validation",
            "full_regression",
            [WORK_ID],
            difficulty="critical",
        )
        final["regression"]["commands"] = [shell_command(final_program)]
        designer["next"] = [WORK_ID]
        worker["next"] = [FINAL_ID]
        self.checkpoints.write_text(json.dumps([designer, worker, final]), encoding="utf-8")
        manifest = [
            {
                "id": PLAN_ID,
                "status": "pending",
                "title": "Grouped lifecycle fixture",
                "directory": PLAN_DIR.as_posix(),
                "source_files": [(PLAN_DIR / "Checkpoints.json").as_posix()],
                "purpose": "Exercise grouped automated delivery behavior.",
                "goal": "Validate the four-role lifecycle.",
                "description": "One isolated high-cohesion task group.",
                "checkpoints": (PLAN_DIR / "Checkpoints.json").as_posix(),
                "kind": "group",
                "decision_issues": [],
            }
        ]
        (self.root / "Manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def cli(self, *args: str, ok: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [sys.executable, str(TOOL), *args],
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

    def state(self, node_id: str) -> dict[str, object]:
        values = json.loads(self.checkpoints.read_text(encoding="utf-8"))
        return next(value for value in values if value["id"] == node_id)

    def next_action(self, node_id: str) -> dict[str, object]:
        return json.loads(
            self.cli("next-action", node_id, str(self.root)).stdout
        )

    def dispatch(self, node_id: str, role: str) -> tuple[str, str]:
        payload = json.loads(
            self.cli(
                "dispatch",
                node_id,
                str(self.root),
                "--role",
                role,
            ).stdout
        )
        dispatch_id = str(payload["dispatch_id"])
        agent_id = f"host.{role}.{len(self.bound_agents) + 1}"
        self.cli(
            "bind-agent",
            node_id,
            str(self.root),
            "--dispatch-id",
            dispatch_id,
            "--agent-id",
            agent_id,
        )
        self.bound_agents[dispatch_id] = agent_id
        return dispatch_id, agent_id

    def complete(self, node_id: str, dispatch_id: str, agent_id: str) -> dict[str, object]:
        return json.loads(
            self.cli(
                "agent-complete",
                node_id,
                str(self.root),
                "--dispatch-id",
                dispatch_id,
                "--agent-id",
                agent_id,
                "--final",
            ).stdout
        )

    def complete_role(self, node_id: str, role: str) -> dict[str, object]:
        dispatch_id, agent_id = self.dispatch(node_id, role)
        return self.complete(node_id, dispatch_id, agent_id)

    def complete_opening_and_implementation(self) -> None:
        self.complete_role(DESIGN_ID, "designer")
        worker = self.complete_role(WORK_ID, "worker")
        self.assertEqual(worker["action"], "dispatch_verifier")
        verifier = self.complete_role(WORK_ID, "verifier")
        self.assertEqual(verifier["action"], "complete_node")

    def test_transition_table_matches_grouped_role_sequence(self) -> None:
        self.assertEqual(
            transitions.transition("awaiting_designer", "designer-dispatched", "designer"),
            "designer_running",
        )
        self.assertEqual(
            transitions.transition("worker_running", "regression-passed", "system"),
            "awaiting_verifier",
        )
        self.assertEqual(
            transitions.transition("verifier_running", "regression-passed", "verifier"),
            "accepted",
        )
        self.assertEqual(
            transitions.transition("awaiting_regression", "regression-failed", "system"),
            "awaiting_reviewer",
        )
        self.assertEqual(
            transitions.transition("reviewer_complete", "regression-passed", "system"),
            "accepted",
        )
        self.assertEqual(
            transitions.transition(
                "awaiting_repair_regression",
                "regression-passed",
                "system",
            ),
            "accepted",
        )
        with self.assertRaises(ValueError):
            transitions.transition("awaiting_verifier", "agent-complete", "worker")

    def test_designer_plans_group_without_a_regression_contract(self) -> None:
        payload = self.next_action(DESIGN_ID)
        self.assertEqual(payload["action"], "dispatch_designer")
        self.assertEqual(payload["fork_turns"], "none")
        self.assertEqual(payload["group_node_ids"], [DESIGN_ID, WORK_ID, FINAL_ID])
        result = self.complete_role(DESIGN_ID, "designer")
        self.assertEqual(result["action"], "complete_node")
        state = self.state(DESIGN_ID)
        self.assertEqual(state["status"], "completed")
        self.assertEqual(state["acceptance"]["phase"], "accepted")

    def test_bound_capability_scope_omits_known_untouched_siblings(self) -> None:
        self.cli(
            "init-capabilities",
            str(self.root),
            "--key",
            "repository",
            "--title",
            "Repository core",
            "--description",
            "Observed mature repository foundation.",
        )
        for key, title, disclosure, touch in (
            ("repository/group", "Selected group", "examined", "in_scope"),
            ("repository/sibling", "Known sibling", "known", "untouched"),
        ):
            self.cli(
                "upsert-capability",
                str(self.root),
                "--key",
                key,
                "--parent",
                "repository",
                "--title",
                title,
                "--kind",
                "capability",
                "--description",
                f"Bounded fact for {title}.",
                "--disclosure",
                disclosure,
                "--touch",
                touch,
            )
        self.cli(
            "bind-plan-capability",
            str(self.root),
            "--plan",
            PLAN_DIR.as_posix(),
            "--capability",
            "repository/group",
        )

        payload = self.next_action(DESIGN_ID)
        scope = payload["capability_scope"]
        self.assertEqual(scope["target_key"], "repository/group")
        self.assertEqual(scope["known_untouched_descendants_omitted"], 0)
        serialized = json.dumps(scope)
        self.assertIn("repository/group", serialized)
        self.assertNotIn("repository/sibling", serialized)

    def test_worker_then_repairing_verifier_closes_one_node(self) -> None:
        self.complete_role(DESIGN_ID, "designer")
        payload = self.next_action(WORK_ID)
        self.assertEqual(payload["action"], "dispatch_worker")
        self.assertEqual(payload["agent_type"], "worker-standard")
        worker = self.complete_role(WORK_ID, "worker")
        self.assertEqual(worker["action"], "dispatch_verifier")
        self.assertEqual(self.state(WORK_ID)["acceptance"]["phase"], "awaiting_verifier")
        verifier = self.complete_role(WORK_ID, "verifier")
        self.assertEqual(verifier["action"], "complete_node")
        state = self.state(WORK_ID)
        self.assertEqual(state["status"], "completed")
        self.assertTrue(state["acceptance_criteria"][0]["checked"])

    def test_independent_workers_and_verifiers_run_concurrently_in_one_group(self) -> None:
        nodes = json.loads(self.checkpoints.read_text(encoding="utf-8"))
        second_worker = self._base_node(
            WORK_TWO_ID,
            "implementation",
            "implementation_two",
            [DESIGN_ID],
            difficulty="complex",
        )
        nodes.insert(-1, second_worker)
        nodes[-1]["prerequisites"] = [WORK_ID, WORK_TWO_ID]
        self.checkpoints.write_text(json.dumps(nodes), encoding="utf-8")

        self.complete_role(DESIGN_ID, "designer")
        first_dispatch, first_agent = self.dispatch(WORK_ID, "worker")
        ready = json.loads(
            self.cli("next", str(self.root), "--json").stdout
        )["plans"][0]
        self.assertEqual([entry["id"] for entry in ready["active"]], [WORK_ID])
        self.assertEqual([entry["id"] for entry in ready["eligible"]], [WORK_TWO_ID])
        second_dispatch, second_agent = self.dispatch(WORK_TWO_ID, "worker")
        self.assertEqual(self.state(WORK_ID)["status"], "in_progress")
        self.assertEqual(self.state(WORK_TWO_ID)["status"], "in_progress")

        self.assertEqual(
            self.complete(WORK_TWO_ID, second_dispatch, second_agent)["action"],
            "dispatch_verifier",
        )
        self.assertEqual(
            self.complete(WORK_ID, first_dispatch, first_agent)["action"],
            "dispatch_verifier",
        )
        first_verifier, first_verifier_agent = self.dispatch(WORK_ID, "verifier")
        second_verifier, second_verifier_agent = self.dispatch(WORK_TWO_ID, "verifier")

        self.assertEqual(
            self.complete(WORK_ID, first_verifier, first_verifier_agent)["action"],
            "complete_node",
        )
        self.assertEqual(
            self.complete(WORK_TWO_ID, second_verifier, second_verifier_agent)["action"],
            "complete_node",
        )
        self.assertEqual(self.state(WORK_ID)["status"], "completed")
        self.assertEqual(self.state(WORK_TWO_ID)["status"], "completed")

    def test_reviewer_runs_once_and_post_review_full_regression_closes_group(self) -> None:
        self.complete_opening_and_implementation()
        first = json.loads(
            self.cli(
                "advance",
                FINAL_ID,
                str(self.root),
                "--event",
                "regression-requested",
            ).stdout
        )
        self.assertEqual(first["action"], "dispatch_reviewer")
        reviewer_id, agent_id = self.dispatch(FINAL_ID, "reviewer")
        returned = self.complete(FINAL_ID, reviewer_id, agent_id)
        self.assertEqual(returned["action"], "main_reviewer_decision")
        duplicate = self.cli(
            "record-decision",
            str(self.root),
            "--plan",
            PLAN_ID,
            "--urgency",
            "immediate",
            "--question",
            "Which contract should be selected?",
            "--context",
            "The alternatives must be distinct.",
            "--option",
            "Keep the contract.",
            "--option",
            "Keep the contract.",
            ok=False,
        )
        self.assertIn("distinct", duplicate.stderr)
        self.cli(
            "record-decision",
            str(self.root),
            "--plan",
            PLAN_ID,
            "--urgency",
            "immediate",
            "--question",
            "Which storage contract should the repaired interface expose?",
            "--context",
            "The choice changes the public contract and must be made before closure.",
            "--option",
            "Keep the existing storage contract.",
            "--option",
            "Adopt the repaired storage contract.",
        )
        self.cli(
            "record-decision",
            str(self.root),
            "--plan",
            PLAN_ID,
            "--urgency",
            "deferred",
            "--question",
            "Which optional presentation should be selected?",
            "--context",
            "Both choices are valid and do not block safe closure.",
            "--option",
            "Keep the compact presentation.",
            "--option",
            "Use the expanded presentation.",
        )
        decisions = json.loads((self.root / "Manifest.json").read_text(encoding="utf-8"))[0][
            "decision_issues"
        ]
        immediate_id = next(
            str(decision["id"])
            for decision in decisions
            if decision["urgency"] == "immediate"
        )
        status = self.cli("status", str(self.root)).stdout
        self.assertIn("REPORT NOW", status)
        self.assertIn("report at final handoff", status)

        before = self.state(FINAL_ID)
        blocked = self.cli(
            "advance",
            FINAL_ID,
            str(self.root),
            "--event",
            "reviewer-finished",
            "--dispatch-id",
            reviewer_id,
            ok=False,
        )
        self.assertIn("immediate developer decision", blocked.stderr)
        self.assertEqual(self.state(FINAL_ID), before)
        self.cli(
            "resolve-decision",
            immediate_id,
            str(self.root),
            "--plan",
            PLAN_ID,
            "--resolution",
            "Keep the existing storage contract.",
        )
        finished = json.loads(
            self.cli(
                "advance",
                FINAL_ID,
                str(self.root),
                "--event",
                "reviewer-finished",
                "--dispatch-id",
                reviewer_id,
            ).stdout
        )
        self.assertEqual(finished["action"], "none")
        state = self.state(FINAL_ID)
        self.assertEqual(state["status"], "completed")
        self.assertEqual(state["acceptance"]["review"]["dispatch_id"], reviewer_id)
        second = self.cli(
            "dispatch",
            FINAL_ID,
            str(self.root),
            "--role",
            "reviewer",
            ok=False,
        )
        self.assertIn("out of order", second.stderr)

    def test_failed_initial_full_regression_still_routes_to_reviewer(self) -> None:
        self._write_workspace(final_program="raise SystemExit(7)")
        self.complete_opening_and_implementation()
        payload = json.loads(
            self.cli(
                "advance",
                FINAL_ID,
                str(self.root),
                "--event",
                "regression-requested",
            ).stdout
        )
        self.assertEqual(payload["action"], "dispatch_reviewer")
        self.assertEqual(self.state(FINAL_ID)["acceptance"]["outcome"], "regression_failed")

    def test_deferring_after_reviewer_preserves_the_once_only_review_receipt(self) -> None:
        self.complete_opening_and_implementation()
        self.cli(
            "advance",
            FINAL_ID,
            str(self.root),
            "--event",
            "regression-requested",
        )
        reviewer_id, agent_id = self.dispatch(FINAL_ID, "reviewer")
        self.complete(FINAL_ID, reviewer_id, agent_id)
        self.cli(
            "record-decision",
            str(self.root),
            "--plan",
            PLAN_ID,
            "--urgency",
            "immediate",
            "--question",
            "Should the resumed group retain the reviewed contract?",
            "--context",
            "The answer controls the post-review regression target.",
            "--option",
            "Retain the reviewed contract.",
            "--option",
            "Replace the reviewed contract.",
        )
        decision_id = json.loads(
            (self.root / "Manifest.json").read_text(encoding="utf-8")
        )[0]["decision_issues"][0]["id"]

        self.cli(
            "defer",
            FINAL_ID,
            str(self.root),
            "--reason",
            "Resume the post-review regression later.",
        )
        deferred = self.state(FINAL_ID)
        self.assertEqual(deferred["status"], "deferred")
        self.assertEqual(deferred["acceptance"]["phase"], "awaiting_repair_regression")
        self.assertEqual(deferred["acceptance"]["review"]["dispatch_id"], reviewer_id)

        self.cli("activate", FINAL_ID, str(self.root))
        self.assertEqual(self.next_action(FINAL_ID)["action"], "run_regression")
        blocked = self.cli(
            "advance",
            FINAL_ID,
            str(self.root),
            "--event",
            "regression-requested",
            ok=False,
        )
        self.assertIn("immediate developer decision", blocked.stderr)
        self.cli(
            "resolve-decision",
            decision_id,
            str(self.root),
            "--plan",
            PLAN_ID,
            "--resolution",
            "Retain the reviewed contract.",
        )
        duplicate = self.cli(
            "dispatch",
            FINAL_ID,
            str(self.root),
            "--role",
            "reviewer",
            ok=False,
        )
        self.assertIn("out of order", duplicate.stderr)
        closed = json.loads(
            self.cli(
                "advance",
                FINAL_ID,
                str(self.root),
                "--event",
                "regression-requested",
            ).stdout
        )
        self.assertEqual(closed["action"], "none")
        self.assertEqual(self.state(FINAL_ID)["status"], "completed")

    def test_post_review_failure_repairs_then_regresses_without_second_reviewer(self) -> None:
        final_file = self.root / "src" / "full_regression.py"
        program = (
            "from pathlib import Path; import sys; "
            "sys.exit(0 if Path('src/full_regression.py').read_text() == 'fixed' else 7)"
        )
        self._write_workspace(final_program=program)
        final_file.write_text("broken", encoding="utf-8")
        self.complete_opening_and_implementation()
        self.cli(
            "advance",
            FINAL_ID,
            str(self.root),
            "--event",
            "regression-requested",
        )
        reviewer_id, agent_id = self.dispatch(FINAL_ID, "reviewer")
        self.complete(FINAL_ID, reviewer_id, agent_id)
        post = json.loads(
            self.cli(
                "advance",
                FINAL_ID,
                str(self.root),
                "--event",
                "reviewer-finished",
                "--dispatch-id",
                reviewer_id,
            ).stdout
        )
        self.assertEqual(post["action"], "create_repair_plan")
        nodes = json.loads(self.checkpoints.read_text(encoding="utf-8"))
        repair = self._base_node(
            REPAIR_ID,
            "implementation",
            "repair",
            [DESIGN_ID],
            difficulty="standard",
        )
        repair["next"] = [FINAL_ID]
        final = next(item for item in nodes if item["id"] == FINAL_ID)
        final["prerequisites"].append(REPAIR_ID)
        nodes.insert(len(nodes) - 1, repair)
        self.checkpoints.write_text(json.dumps(nodes), encoding="utf-8")
        self.cli(
            "advance",
            FINAL_ID,
            str(self.root),
            "--event",
            "repair-registered",
            "--repair-node",
            REPAIR_ID,
        )
        self.complete_role(REPAIR_ID, "worker")
        self.complete_role(REPAIR_ID, "verifier")
        self.cli(
            "advance",
            FINAL_ID,
            str(self.root),
            "--event",
            "repair-completed",
            "--repair-node",
            REPAIR_ID,
        )
        final_file.write_text("fixed", encoding="utf-8")
        closed = json.loads(
            self.cli(
                "advance",
                FINAL_ID,
                str(self.root),
                "--event",
                "regression-requested",
            ).stdout
        )
        self.assertEqual(closed["action"], "none")
        state = self.state(FINAL_ID)
        self.assertEqual(state["status"], "completed")
        self.assertEqual(state["acceptance"]["review"]["dispatch_id"], reviewer_id)


if __name__ == "__main__":
    unittest.main()
