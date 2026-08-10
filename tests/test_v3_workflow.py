"""One normal v3 delivery plus the repair paths that must never stall."""

from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

from scripts.better_plan.application.agent_completion import reduce_agent_completion
from scripts.better_plan.domain.design_compile import DESIGN_EXAMPLE, DESIGN_TEMPLATE
from tests.v3_fixtures import MARKER_COMMAND, draft_plan, task, write_workspace


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "scripts" / "manifest_tool.py"
PLAN = "PLAN-001"


class V3WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.plan = write_workspace(self.root, draft_plan())

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def cli(self, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(TOOL), *arguments],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            check=check,
        )

    def payload(self, *arguments: str) -> dict:
        return json.loads(self.cli(*arguments).stdout)

    def read_plan(self) -> dict:
        return json.loads((self.root / "delivery" / "Plan.json").read_text(encoding="utf-8"))

    def write_plan(self, value: dict) -> None:
        (self.root / "delivery" / "Plan.json").write_text(json.dumps(value), encoding="utf-8")

    def write_design(self, value: str) -> None:
        (self.root / "delivery" / "Design.md").write_text(value, encoding="utf-8")

    def design_and_authorize(self, *extra: str) -> None:
        opened = self.payload("open-designer-session", str(self.root), "--plan", PLAN)
        dispatch = opened["dispatch_id"]
        self.cli("bind-agent", PLAN, str(self.root), "--plan", PLAN, "--dispatch-id", dispatch, "--agent-id", "designer.agent")
        self.cli("agent-complete", str(self.root), "--plan", PLAN, "--agent-id", "designer.agent", "--final")
        self.cli("close-designer-session", str(self.root), "--plan", PLAN, "--dispatch-id", dispatch)
        self.cli(
            "authorize-plan",
            str(self.root),
            "--plan",
            PLAN,
            "--source",
            "inherited_implementation_request",
            "--reference",
            "authorized-request",
            *extra,
        )

    def run_worker(self, code: str, agent: str) -> None:
        dispatched = self.payload("dispatch-task", code, str(self.root), "--plan", PLAN)
        self.cli("bind-agent", code, str(self.root), "--plan", PLAN, "--dispatch-id", dispatched["dispatch_id"], "--agent-id", agent)
        self.cli("agent-complete", str(self.root), "--plan", PLAN, "--agent-id", agent, "--final")

    def close_review(self, agent: str, *extra: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        self.payload("run-full-regression", str(self.root), "--plan", PLAN)
        review = self.payload("open-reviewer-session", str(self.root), "--plan", PLAN)
        self.cli("bind-agent", PLAN, str(self.root), "--plan", PLAN, "--dispatch-id", review["dispatch_id"], "--agent-id", agent)
        self.cli("agent-complete", str(self.root), "--plan", PLAN, "--agent-id", agent, "--final")
        return self.cli(
            "close-reviewer-session",
            str(self.root),
            "--plan",
            PLAN,
            "--dispatch-id",
            review["dispatch_id"],
            *extra,
            check=check,
        )

    def test_one_designer_and_one_reviewer_complete_without_more_questions(self) -> None:
        value = self.read_plan()
        value["spec"]["full_regression"] = {
            "commands": [
                "python3 -c \"from pathlib import Path; p=Path('full-count.txt'); "
                "p.write_text(str((int(p.read_text()) if p.exists() else 0)+1))\""
            ],
            "paths": ["full-count.txt"],
        }
        self.write_plan(value)
        opened = self.payload("open-designer-session", str(self.root), "--plan", PLAN)
        dispatch = opened["dispatch_id"]
        self.assertEqual(opened["role_reference"], "references/designer.md")
        self.cli("bind-agent", PLAN, str(self.root), "--plan", PLAN, "--dispatch-id", dispatch, "--agent-id", "designer.agent")
        self.cli("agent-complete", str(self.root), "--plan", PLAN, "--agent-id", "designer.agent", "--final")
        closed = self.payload("close-designer-session", str(self.root), "--plan", PLAN, "--dispatch-id", dispatch)
        self.assertEqual((closed["phase"], closed["ready"]), ("ready", True))
        self.assertNotEqual(
            self.cli("open-designer-session", str(self.root), "--plan", PLAN, check=False).returncode, 0
        )

        self.assertTrue(self.payload("check-readiness", str(self.root), "--plan", PLAN)["ready"])
        authorized = self.payload(
            "authorize-plan",
            str(self.root),
            "--plan",
            PLAN,
            "--source",
            "explicit",
            "--reference",
            "user-approval",
        )
        self.assertEqual(authorized["revision"], 1)

        dispatched = self.payload("dispatch-task", "TASK-001", str(self.root), "--plan", PLAN)
        self.assertEqual(dispatched["agent_type"], "worker-standard")
        self.assertFalse(dispatched["correction"])
        self.assertIn("Do not ask the user", json.dumps(dispatched["brief"]))
        self.assertIn("Execute every currently ready Task Node concurrently", json.dumps(dispatched["brief"]))
        self.assertTrue(dispatched["brief"]["task"]["nodes"])
        self.cli("bind-agent", "TASK-001", str(self.root), "--plan", PLAN, "--dispatch-id", dispatched["dispatch_id"], "--agent-id", "worker.agent")
        returned = self.payload("agent-complete", str(self.root), "--plan", PLAN, "--agent-id", "worker.agent", "--final")
        self.assertEqual(returned["action"], "accept_task")
        self.cli("accept-task", "TASK-001", str(self.root), "--plan", PLAN)

        self.assertEqual(
            self.payload("next-action", str(self.root), "--plan", PLAN)["action"], "run_full_regression"
        )
        premature = self.cli("open-reviewer-session", str(self.root), "--plan", PLAN, check=False)
        self.assertNotEqual(premature.returncode, 0)
        self.assertIn("independent full regression", premature.stderr)
        result = self.close_review("reviewer.agent")
        self.assertTrue(json.loads(result.stdout)["completed"])
        self.assertNotEqual(
            self.cli("open-reviewer-session", str(self.root), "--plan", PLAN, check=False).returncode, 0
        )
        final = self.read_plan()
        self.assertEqual(final["phase"], "completed")
        self.assertEqual(final["lifecycle"]["designer_session"]["count"], 1)
        self.assertEqual(final["lifecycle"]["reviewer_session"]["count"], 1)
        checkpoints = json.loads((self.root / "delivery" / "Checkpoints.json").read_text(encoding="utf-8"))
        self.assertTrue(checkpoints["full_regression"]["passed"])
        self.assertEqual((self.root / "full-count.txt").read_text(encoding="utf-8"), "1")
        self.assertEqual(self.cli("validate", str(self.root)).returncode, 0)

    def test_incomplete_design_closes_and_reports_issues_instead_of_trapping_the_session(self) -> None:
        value = self.read_plan()
        value["spec"]["tasks"][0].pop("acceptance")
        value["spec"]["tasks"][0].pop("focused_regression")
        self.write_plan(value)
        opened = self.payload("open-designer-session", str(self.root), "--plan", PLAN)
        dispatch = opened["dispatch_id"]
        self.cli("bind-agent", PLAN, str(self.root), "--plan", PLAN, "--dispatch-id", dispatch, "--agent-id", "designer.partial")
        self.cli("agent-complete", str(self.root), "--plan", PLAN, "--agent-id", "designer.partial", "--final")

        closed = self.payload("close-designer-session", str(self.root), "--plan", PLAN, "--dispatch-id", dispatch)
        self.assertEqual(closed["phase"], "ready")
        self.assertFalse(closed["ready"])
        self.assertTrue(any("acceptance" in issue for issue in closed["open_issues"]))
        rejected = self.cli(
            "authorize-plan", str(self.root), "--plan", PLAN,
            "--source", "explicit", "--reference", "user-approval", check=False,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("plan is not ready", rejected.stderr)

        repaired = self.read_plan()
        repaired["spec"]["tasks"][0] = task()
        self.write_plan(repaired)
        self.assertTrue(self.payload("check-readiness", str(self.root), "--plan", PLAN)["ready"])
        self.cli("authorize-plan", str(self.root), "--plan", PLAN, "--source", "explicit", "--reference", "user-approval")
        self.assertEqual(self.read_plan()["phase"], "authorized")

    def test_designer_draft_compiles_and_authorizes_without_manual_spec_bookkeeping(self) -> None:
        value = self.read_plan()
        value["spec"] = {
            "requirements": [],
            "architecture": {"summary": "", "notes": []},
            "tasks": [],
            "full_regression": {"commands": [], "paths": []},
        }
        self.write_plan(value)
        opened = self.payload("open-designer-session", str(self.root), "--plan", PLAN)
        self.assertEqual(opened["draft_path"], "delivery/Design.md")
        self.assertEqual(
            (self.root / "delivery" / "Design.md").read_text(encoding="utf-8"),
            DESIGN_TEMPLATE,
        )
        self.assertNotIn("bounded-delivery", DESIGN_TEMPLATE)
        self.assertNotIn("observable-behavior", DESIGN_TEMPLATE)
        self.assertIn("references/design-format.md", opened["knowledge_references"])
        self.assertIn("Write the complete solution design to delivery/Design.md", opened["assignment"])
        self.assertIn("every Task is mutually parallel-safe", opened["assignment"])
        self.assertIn("design a minimal Node DAG", opened["assignment"])
        self.assertIn("branch every independent Node", opened["assignment"])
        self.assertIn("every ready Node concurrently", opened["assignment"])
        self.assertIn("Do not edit Plan.json.spec", opened["assignment"])
        self.assertIn("complete delivery/Plan.json directly", opened["assignment"])
        self.write_design(DESIGN_EXAMPLE)
        dispatch = opened["dispatch_id"]
        self.cli("bind-agent", PLAN, str(self.root), "--plan", PLAN, "--dispatch-id", dispatch, "--agent-id", "designer.draft")
        self.cli("agent-complete", str(self.root), "--plan", PLAN, "--agent-id", "designer.draft", "--final")

        closed = self.payload("close-designer-session", str(self.root), "--plan", PLAN, "--dispatch-id", dispatch)
        self.assertTrue(closed["compiled"])
        self.assertEqual((closed["structure_issues"], closed["content_issues"], closed["unmapped"]), (0, 0, 0))
        compiled = self.read_plan()
        self.assertEqual(compiled["spec"]["tasks"][0]["code"], "TASK-001")
        self.assertEqual(compiled["spec"]["tasks"][0]["outputs"][0]["code"], "OUT-001")
        self.assertEqual(
            (self.root / "delivery" / "Design.pristine.md").read_text(encoding="utf-8"),
            DESIGN_EXAMPLE,
        )
        authorized = self.payload(
            "authorize-plan", str(self.root), "--plan", PLAN,
            "--source", "inherited_implementation_request", "--reference", "draft-compiler",
        )
        self.assertTrue(authorized["authorized"])

    def test_structure_residue_routes_to_plan_repair_without_changing_design(self) -> None:
        opened = self.payload("open-designer-session", str(self.root), "--plan", PLAN)
        residue = "## Notes from Designer\nPreserve this design note.\n\n"
        self.write_design(DESIGN_EXAMPLE.replace("## Architecture", residue + "## Architecture"))
        checked = self.cli(
            "compile-design", str(self.root), "--plan", PLAN, "--check", check=False,
        )
        self.assertNotEqual(checked.returncode, 0)
        diagnostics = json.loads(checked.stdout)["issues"]
        self.assertTrue(diagnostics)
        self.assertTrue(all(
            type(item.get("line")) is int and item.get("field")
            for item in diagnostics
        ))
        dispatch = opened["dispatch_id"]
        self.cli("bind-agent", PLAN, str(self.root), "--plan", PLAN, "--dispatch-id", dispatch, "--agent-id", "designer.residue")
        self.cli("agent-complete", str(self.root), "--plan", PLAN, "--agent-id", "designer.residue", "--final")
        closed = self.payload("close-designer-session", str(self.root), "--plan", PLAN, "--dispatch-id", dispatch)
        self.assertEqual(closed["unmapped"], 1)
        action = self.payload("next-action", str(self.root), "--plan", PLAN)
        self.assertEqual(action["action"], "repair_plan")
        self.assertEqual(action["brief"]["plan_path"], "delivery/Plan.json")
        self.assertEqual(action["brief"]["rules_reference"], "references/structure-repair.md")
        rejected = self.cli(
            "authorize-plan", str(self.root), "--plan", PLAN,
            "--source", "explicit", "--reference", "approval", check=False,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("design compilation has open issues", rejected.stderr)

        frozen = (self.root / "delivery" / "Design.md").read_text(encoding="utf-8")
        self.write_design(frozen + "\n")
        immutable = self.cli("compile-design", str(self.root), "--plan", PLAN, "--apply", check=False)
        self.assertNotEqual(immutable.returncode, 0)
        self.assertIn("Design.md is read-only", immutable.stderr)
        self.write_design(frozen)

        current = self.read_plan()
        current["spec"]["architecture"]["notes"].append("Preserve this design note.")
        self.write_plan(current)
        repaired = self.payload("compile-design", str(self.root), "--plan", PLAN, "--apply")
        self.assertEqual(repaired["open_issues"], 0)
        self.assertEqual(
            (self.root / "delivery" / "Design.md").read_text(encoding="utf-8"),
            frozen,
        )
        self.assertEqual(self.payload("next-action", str(self.root), "--plan", PLAN)["action"], "authorize_plan")
        self.cli(
            "authorize-plan", str(self.root), "--plan", PLAN,
            "--source", "explicit", "--reference", "approval",
        )

    def test_failed_acceptance_has_a_scripted_correction_path(self) -> None:
        value = self.read_plan()
        value["spec"]["tasks"][0]["focused_regression"]["commands"] = [MARKER_COMMAND]
        self.write_plan(value)
        self.design_and_authorize()
        self.run_worker("TASK-001", "worker.first")

        failed = self.cli("accept-task", "TASK-001", str(self.root), "--plan", PLAN, check=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("focused acceptance failed", failed.stderr)
        state = self.payload("next-action", str(self.root), "--plan", PLAN)
        self.assertEqual(state["action"], "repair_tasks")
        self.assertEqual(state["corrections"], ["TASK-001"])

        correction = self.payload("dispatch-task", "TASK-001", str(self.root), "--plan", PLAN)
        self.assertTrue(correction["correction"])
        checkpoints = json.loads((self.root / "delivery" / "Checkpoints.json").read_text(encoding="utf-8"))
        self.assertEqual(checkpoints["tasks"][0]["dispatch"]["attempts"], 2)
        self.assertEqual(len(checkpoints["tasks"][0]["evidence"]), 1)

        # The correction Worker produces the missing artifact; the Plan stays frozen.
        (self.root / "marker.txt").write_text("repaired\n", encoding="utf-8")
        self.cli("bind-agent", "TASK-001", str(self.root), "--plan", PLAN, "--dispatch-id", correction["dispatch_id"], "--agent-id", "worker.second")
        self.cli("agent-complete", str(self.root), "--plan", PLAN, "--agent-id", "worker.second", "--final")
        self.cli("accept-task", "TASK-001", str(self.root), "--plan", PLAN)
        self.assertEqual(
            self.payload("next-action", str(self.root), "--plan", PLAN)["action"], "run_full_regression"
        )

    def test_dossier_can_be_rebuilt_before_resolution_and_resolves_once(self) -> None:
        value = self.read_plan()
        value["ledger"]["unresolved"] = [
            {"code": "DEC-001", "statement": "Choose the delivery boundary.", "impact": "It changes policy."}
        ]
        self.write_plan(value)
        broken = self.root / "broken.json"
        broken.write_text(json.dumps([{"code": "Q-001"}]), encoding="utf-8")
        self.assertNotEqual(
            self.cli("build-dossier", str(self.root), "--plan", PLAN, "--input", str(broken), check=False).returncode, 0
        )

        questions = [
            {
                "code": "Q-001",
                "question": "Which delivery boundary applies?",
                "context": "Both boundaries exist in the repository.",
                "resolves": ["DEC-001"],
                "options": [
                    {"id": "safe", "label": "Keep both surfaces", "effects": ["Old callers keep working.", "Acceptance covers both paths."]},
                    {"id": "replace", "label": "Remove the old surface", "effects": ["Old callers are migrated.", "Acceptance proves no caller remains."]},
                ],
                "recommended": "safe",
                "default": "safe",
            }
        ]
        good = self.root / "dossier.json"
        good.write_text(json.dumps(questions), encoding="utf-8")
        self.assertEqual(
            self.payload("build-dossier", str(self.root), "--plan", PLAN, "--input", str(good))["status"], "draft"
        )
        good.write_text(json.dumps(questions), encoding="utf-8")
        self.cli("build-dossier", str(self.root), "--plan", PLAN, "--input", str(good))

        selections = self.root / "selections.json"
        selections.write_text("{}", encoding="utf-8")
        self.cli("resolve-dossier", str(self.root), "--plan", PLAN, "--input", str(selections))
        plan = self.read_plan()
        self.assertEqual(plan["dossier"]["questions"][0]["selected"], "safe")
        self.assertEqual(plan["ledger"]["defaulted"][0]["source"], "Q-001")
        self.assertEqual(plan["ledger"]["user_decided"], [])
        self.assertEqual(plan["ledger"]["unresolved"], [])
        for command in ("build-dossier", "resolve-dossier"):
            self.assertNotEqual(
                self.cli(command, str(self.root), "--plan", PLAN, "--input", str(good), check=False).returncode, 0
            )

    def test_in_scope_continuation_inherits_authorization_but_scope_change_fails(self) -> None:
        self.design_and_authorize()
        opened = self.payload("begin-continuation", str(self.root), "--plan", PLAN, "--reason", "new repository fact")
        value = self.read_plan()
        value["spec"]["tasks"][0]["title"] = "Deliver the newly discovered bounded behavior"
        self.write_plan(value)
        closed = self.payload("close-continuation", str(self.root), "--plan", PLAN, "--continuation-id", opened["continuation_id"])
        self.assertEqual(closed["revision"], 2)
        self.assertEqual(self.read_plan()["phase"], "authorized")

        second = self.payload("begin-continuation", str(self.root), "--plan", PLAN, "--reason", "attempted expansion")
        value = self.read_plan()
        value["intent"]["scope"]["in"].append("New unauthorized capability")
        self.write_plan(value)
        rejected = self.cli(
            "close-continuation", str(self.root), "--plan", PLAN, "--continuation-id", second["continuation_id"], check=False
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("exceeds authorization", rejected.stderr)

    def test_continuation_cannot_rewrite_a_started_task(self) -> None:
        self.design_and_authorize()
        self.cli("dispatch-task", "TASK-001", str(self.root), "--plan", PLAN)
        continuation = self.payload("begin-continuation", str(self.root), "--plan", PLAN, "--reason", "parallel discovery")
        value = self.read_plan()
        value["spec"]["tasks"][0]["title"] = "Illegally rewritten active Task"
        self.write_plan(value)
        result = self.cli(
            "close-continuation", str(self.root), "--plan", PLAN, "--continuation-id", continuation["continuation_id"], check=False
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("changed a started Task", result.stderr)

    def test_hard_blocker_isolated_to_one_parallel_task_and_delivery_finishes(self) -> None:
        value = draft_plan()
        independent = task(
            "TASK-002",
            write_paths=["other.txt"],
            acceptance_code="AC-002",
        )
        value["spec"]["tasks"].append(independent)
        self.plan = write_workspace(self.root, value)
        (self.root / "other.txt").write_text("fixture\n", encoding="utf-8")
        self.design_and_authorize()

        blocked = self.payload(
            "block-task", "TASK-001", str(self.root), "--plan", PLAN,
            "--kind", "environment", "--reason", "required external system unavailable",
        )
        self.assertEqual(blocked["affected_tasks"], ["TASK-001"])
        self.assertEqual(
            self.payload("next-action", str(self.root), "--plan", PLAN)["eligible"], ["TASK-002"]
        )
        self.run_worker("TASK-002", "worker.independent")
        self.cli("accept-task", "TASK-002", str(self.root), "--plan", PLAN)
        self.assertEqual(
            self.payload("next-action", str(self.root), "--plan", PLAN)["action"], "run_full_regression"
        )
        refused = self.close_review("reviewer.blocked", check=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("require --blocked-reason", refused.stderr)

        plan = self.read_plan()
        session = plan["lifecycle"]["reviewer_session"]
        self.cli("agent-complete", str(self.root), "--plan", PLAN, "--agent-id", "reviewer.blocked", "--final")
        result = self.cli(
            "close-reviewer-session", str(self.root), "--plan", PLAN, "--dispatch-id", session["id"],
            "--blocked-reason", "external dependency could not be reached",
        )
        self.assertTrue(json.loads(result.stdout)["blocked"])
        self.assertEqual(self.read_plan()["phase"], "blocked")

    def test_exhausted_delegation_falls_back_to_the_same_native_session(self) -> None:
        opened = self.payload("open-designer-session", str(self.root), "--plan", PLAN)
        dispatch = opened["dispatch_id"]
        for _ in range(2):
            self.cli(
                "delegation-failed", PLAN, str(self.root), "--plan", PLAN,
                "--dispatch-id", dispatch, "--reason", "host delegation unavailable",
            )
        fallback = self.payload("main-complete", PLAN, str(self.root), "--plan", PLAN, "--dispatch-id", dispatch)
        self.assertEqual(fallback["action"], "close_designer_session")
        self.cli("close-designer-session", str(self.root), "--plan", PLAN, "--dispatch-id", dispatch)
        self.assertEqual(self.read_plan()["lifecycle"]["designer_session"]["count"], 1)

    def test_rendered_evidence_requirement_reaches_the_sole_reviewer(self) -> None:
        value = draft_plan()
        value["spec"]["tasks"][0]["verification"] = "hybrid"
        self.plan = write_workspace(self.root, value)
        self.design_and_authorize()
        dispatched = self.payload("dispatch-task", "TASK-001", str(self.root), "--plan", PLAN)
        self.assertIn("rendered evidence", json.dumps(dispatched["brief"]["execution_policy"]))
        self.cli("bind-agent", "TASK-001", str(self.root), "--plan", PLAN, "--dispatch-id", dispatched["dispatch_id"], "--agent-id", "worker.visual")
        self.cli("agent-complete", str(self.root), "--plan", PLAN, "--agent-id", "worker.visual", "--final")
        self.cli("accept-task", "TASK-001", str(self.root), "--plan", PLAN)
        regression = self.payload("run-full-regression", str(self.root), "--plan", PLAN)
        review = self.payload("open-reviewer-session", str(self.root), "--plan", PLAN)
        self.assertEqual(review["agent_type"], "reviewer")
        self.assertEqual(review["brief"]["rendered_evidence_tasks"], ["TASK-001"])
        self.assertEqual(review["brief"]["plan"]["code"], PLAN)
        self.assertEqual(review["brief"]["checkpoints"]["tasks"][0]["status"], "completed")
        self.assertTrue(review["brief"]["full_regression"]["result"]["passed"])
        self.assertEqual(regression["action"], "open_reviewer_session")

    def test_authorization_can_prove_the_host_harness_without_mutating_inputs(self) -> None:
        self.design_and_authorize("--verify-command", 'python3 -c "raise SystemExit(0)"')
        self.assertTrue(self.read_plan()["lifecycle"]["verification"]["passed"])

    def test_native_callback_reducer_advances_exactly_one_bound_dispatch(self) -> None:
        self.design_and_authorize()
        dispatched = self.payload("dispatch-task", "TASK-001", str(self.root), "--plan", PLAN)
        self.cli("bind-agent", "TASK-001", str(self.root), "--plan", PLAN, "--dispatch-id", dispatched["dispatch_id"], "--agent-id", "callback.worker")
        self.assertIsNone(
            reduce_agent_completion(self.root / "Manifest.json", agent_id="callback.worker", final=False)
        )
        directive = reduce_agent_completion(
            self.root / "Manifest.json",
            agent_id="callback.worker",
            final=True,
            target_id="TASK-001",
            dispatch_id=dispatched["dispatch_id"],
        )
        assert directive is not None
        self.assertEqual((directive.action, directive.phase), ("accept_task", "awaiting_acceptance"))
        self.assertIsNone(
            reduce_agent_completion(self.root / "Manifest.json", agent_id="unbound.agent", final=True)
        )

    def test_reviewer_cannot_open_during_a_continuation_or_close_with_pending_work(self) -> None:
        self.design_and_authorize()
        self.run_worker("TASK-001", "worker.only")
        self.cli("accept-task", "TASK-001", str(self.root), "--plan", PLAN)
        opened = self.payload("begin-continuation", str(self.root), "--plan", PLAN, "--reason", "late discovery")
        refused = self.cli("open-reviewer-session", str(self.root), "--plan", PLAN, check=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("no open continuation", refused.stderr)

        value = self.read_plan()
        value["spec"]["tasks"].append(
            task("TASK-002", write_paths=["other.txt"], acceptance_code="AC-002")
        )
        self.write_plan(value)
        (self.root / "other.txt").write_text("fixture\n", encoding="utf-8")
        self.cli("close-continuation", str(self.root), "--plan", PLAN, "--continuation-id", opened["continuation_id"])
        self.assertEqual(
            self.payload("next-action", str(self.root), "--plan", PLAN)["action"], "dispatch_tasks"
        )
        still_refused = self.cli("open-reviewer-session", str(self.root), "--plan", PLAN, check=False)
        self.assertNotEqual(still_refused.returncode, 0)
        self.assertIn("every Task terminal", still_refused.stderr)

    def test_failed_final_regression_keeps_the_same_reviewer_session_closable(self) -> None:
        value = self.read_plan()
        value["spec"]["full_regression"]["commands"] = [
            "python3 -c \"import pathlib, sys; print('marker artifact is missing'); "
            "print(chr(47)+'private/runtime/path'); "
            "sys.exit(0 if pathlib.Path('marker.txt').is_file() else 1)\""
        ]
        self.write_plan(value)
        self.design_and_authorize()
        self.run_worker("TASK-001", "worker.only")
        self.cli("accept-task", "TASK-001", str(self.root), "--plan", PLAN)
        baseline_run = self.payload("run-full-regression", str(self.root), "--plan", PLAN)
        review = self.payload("open-reviewer-session", str(self.root), "--plan", PLAN)
        baseline = baseline_run["full_regression"]
        self.assertFalse(baseline["result"]["passed"])
        self.assertIn("marker artifact is missing", baseline["diagnostics"][0]["output_tail"])
        self.assertIn("[redacted unsafe diagnostic line]", baseline["diagnostics"][0]["output_tail"])
        self.assertNotIn("/private/runtime/path", json.dumps(baseline))
        persisted = (self.root / "delivery" / "Checkpoints.json").read_text(encoding="utf-8")
        self.assertNotIn("marker artifact is missing", persisted)
        self.assertNotIn("private/runtime/path", persisted)
        self.cli(
            "bind-agent", PLAN, str(self.root), "--plan", PLAN,
            "--dispatch-id", review["dispatch_id"], "--agent-id", "reviewer.retry",
        )
        self.cli("agent-complete", str(self.root), "--plan", PLAN, "--agent-id", "reviewer.retry", "--final")
        self.assertEqual(
            self.payload("next-action", str(self.root), "--plan", PLAN)["action"],
            "run_full_regression",
        )
        retry = self.payload("run-full-regression", str(self.root), "--plan", PLAN)
        self.assertEqual(retry["action"], "resume_reviewer")
        self.assertIn("marker artifact is missing", json.dumps(retry["full_regression"]))
        session = self.read_plan()["lifecycle"]["reviewer_session"]
        self.assertTrue(session["repair_required"])
        self.assertFalse(session["agent_returned"])

        # The same Reviewer repairs and the very same session closes; no second Reviewer.
        (self.root / "marker.txt").write_text("repaired\n", encoding="utf-8")
        self.cli("agent-complete", str(self.root), "--plan", PLAN, "--agent-id", "reviewer.retry", "--final")
        verified = self.payload("run-full-regression", str(self.root), "--plan", PLAN)
        self.assertEqual(verified["action"], "close_reviewer_session")
        result = self.cli(
            "close-reviewer-session", str(self.root), "--plan", PLAN, "--dispatch-id", session["id"]
        )
        self.assertTrue(json.loads(result.stdout)["completed"])
        final = self.read_plan()
        self.assertEqual(final["phase"], "completed")
        self.assertEqual(final["lifecycle"]["reviewer_session"]["count"], 1)
        self.assertNotIn("repair_required", final["lifecycle"]["reviewer_session"])

    def test_designer_edits_to_authorized_intent_are_restored_instead_of_trapping(self) -> None:
        opened = self.payload("open-designer-session", str(self.root), "--plan", PLAN)
        value = self.read_plan()
        value["intent"]["goal"] = "A goal the Designer invented on its own."
        self.write_plan(value)
        self.cli("bind-agent", PLAN, str(self.root), "--plan", PLAN, "--dispatch-id", opened["dispatch_id"], "--agent-id", "designer.drift")
        self.cli("agent-complete", str(self.root), "--plan", PLAN, "--agent-id", "designer.drift", "--final")
        closed = self.payload("close-designer-session", str(self.root), "--plan", PLAN, "--dispatch-id", opened["dispatch_id"])
        self.assertEqual(closed["phase"], "ready")
        self.assertEqual(closed["restored"], ["intent"])
        self.assertEqual(self.read_plan()["intent"]["goal"], draft_plan()["intent"]["goal"])

    def test_a_sealed_plan_cannot_be_rewound_or_reauthorized(self) -> None:
        self.design_and_authorize()
        self.run_worker("TASK-001", "worker.only")
        self.cli("accept-task", "TASK-001", str(self.root), "--plan", PLAN)
        value = self.read_plan()
        value["phase"] = "ready"
        self.write_plan(value)
        rejected = self.cli(
            "authorize-plan", str(self.root), "--plan", PLAN,
            "--source", "explicit", "--reference", "second-approval", check=False,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("cannot return to ready", rejected.stderr)
        self.assertNotEqual(self.cli("validate", str(self.root), check=False).returncode, 0)

        value["phase"] = "draft"
        value["lifecycle"]["designer_session"] = None
        self.write_plan(value)
        reopened = self.cli("open-designer-session", str(self.root), "--plan", PLAN, check=False)
        self.assertNotEqual(reopened.returncode, 0)
        self.assertIn("cannot return to draft", reopened.stderr)

    def test_one_agent_id_cannot_own_two_live_dispatches(self) -> None:
        value = draft_plan()
        value["spec"]["tasks"].append(
            task("TASK-002", write_paths=["other.txt"], acceptance_code="AC-002")
        )
        self.plan = write_workspace(self.root, value)
        (self.root / "other.txt").write_text("fixture\n", encoding="utf-8")
        self.design_and_authorize()
        first = self.payload("dispatch-task", "TASK-001", str(self.root), "--plan", PLAN)
        remaining = self.payload("next-action", str(self.root), "--plan", PLAN)
        self.assertEqual(remaining["action"], "dispatch_tasks")
        self.assertEqual(remaining["eligible"], ["TASK-002"])
        second = self.payload("dispatch-task", "TASK-002", str(self.root), "--plan", PLAN)
        self.cli("bind-agent", "TASK-001", str(self.root), "--plan", PLAN, "--dispatch-id", first["dispatch_id"], "--agent-id", "same.agent")
        rejected = self.cli(
            "bind-agent", "TASK-002", str(self.root), "--plan", PLAN,
            "--dispatch-id", second["dispatch_id"], "--agent-id", "same.agent", check=False,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("already owns another live dispatch", rejected.stderr)
        returned = self.payload("agent-complete", str(self.root), "--plan", PLAN, "--agent-id", "same.agent", "--final")
        self.assertEqual(returned["task"], "TASK-001")
        checkpoints = json.loads((self.root / "delivery" / "Checkpoints.json").read_text(encoding="utf-8"))
        phases = {item["code"]: item["dispatch"]["phase"] for item in checkpoints["tasks"]}
        self.assertEqual(phases, {"TASK-001": "awaiting_acceptance", "TASK-002": "worker_running"})

    def test_independent_task_acceptance_runs_concurrently_outside_the_workspace_lock(self) -> None:
        barrier = self.root / "acceptance_barrier.py"
        barrier.write_text(
            "from pathlib import Path\n"
            "import sys, time\n"
            "mine, other = Path(sys.argv[1]), Path(sys.argv[2])\n"
            "mine.parent.mkdir(parents=True, exist_ok=True)\n"
            "mine.write_text('ready', encoding='utf-8')\n"
            "deadline = time.monotonic() + 5\n"
            "while not other.is_file() and time.monotonic() < deadline:\n"
            "    time.sleep(0.02)\n"
            "raise SystemExit(0 if other.is_file() else 1)\n",
            encoding="utf-8",
        )
        value = draft_plan()
        value["spec"]["tasks"] = [
            task(
                "TASK-001",
                write_paths=["task-a"],
                command="python3 acceptance_barrier.py task-a/ready task-b/ready",
            ),
            task(
                "TASK-002",
                write_paths=["task-b"],
                acceptance_code="AC-002",
                command="python3 acceptance_barrier.py task-b/ready task-a/ready",
            ),
        ]
        self.plan = write_workspace(self.root, value)
        self.design_and_authorize()
        self.run_worker("TASK-001", "worker.first")
        self.run_worker("TASK-002", "worker.second")
        self.assertEqual(
            self.payload("next-action", str(self.root), "--plan", PLAN)["awaiting_acceptance"],
            ["TASK-001", "TASK-002"],
        )

        processes = [
            subprocess.Popen(
                [sys.executable, str(TOOL), "accept-task", code, str(self.root), "--plan", PLAN],
                cwd=str(ROOT),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            for code in ("TASK-001", "TASK-002")
        ]
        results = [process.communicate(timeout=10) for process in processes]

        self.assertEqual(
            [(process.returncode, stderr) for process, (_, stderr) in zip(processes, results)],
            [(0, ""), (0, "")],
        )
        self.assertEqual(
            self.payload("next-action", str(self.root), "--plan", PLAN)["action"],
            "run_full_regression",
        )

    def test_a_greenfield_task_can_be_dispatched_and_accepted(self) -> None:
        value = draft_plan()
        value["spec"]["tasks"][0]["ownership"]["write_paths"] = ["created.txt"]
        value["spec"]["tasks"][0]["outputs"][0]["artifact"] = "created.txt"
        value["spec"]["tasks"][0]["focused_regression"]["paths"] = ["created.txt"]
        value["spec"]["full_regression"]["paths"] = ["created.txt"]
        self.plan = write_workspace(self.root, value)
        self.design_and_authorize()
        self.run_worker("TASK-001", "worker.greenfield")
        (self.root / "created.txt").write_text("new module\n", encoding="utf-8")
        self.cli("accept-task", "TASK-001", str(self.root), "--plan", PLAN)
        self.assertEqual(
            self.payload("next-action", str(self.root), "--plan", PLAN)["action"], "run_full_regression"
        )

    def test_dossier_cannot_reopen_after_authorization(self) -> None:
        self.design_and_authorize()
        self.payload("begin-continuation", str(self.root), "--plan", PLAN, "--reason", "late discovery")
        questions = self.root / "late.json"
        questions.write_text(
            json.dumps(
                [
                    {
                        "code": "Q-009",
                        "question": "Should the boundary change now?",
                        "context": "A late discovery suggests a different boundary.",
                        "resolves": ["DEC-009"],
                        "options": [
                            {"id": "keep", "label": "Keep it", "effects": ["Nothing changes."]},
                            {"id": "change", "label": "Change it", "effects": ["The boundary moves."]},
                        ],
                        "recommended": "keep",
                        "default": "keep",
                    }
                ]
            ),
            encoding="utf-8",
        )
        rejected = self.cli(
            "build-dossier", str(self.root), "--plan", PLAN, "--input", str(questions), check=False
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("not yet authorized", rejected.stderr)

    def test_next_action_names_every_phase_and_the_exhausted_fallback(self) -> None:
        self.assertEqual(self.payload("next-action", str(self.root), "--plan", PLAN)["action"], "open_designer_session")
        opened = self.payload("open-designer-session", str(self.root), "--plan", PLAN)
        self.assertEqual(self.payload("next-action", str(self.root), "--plan", PLAN)["action"], "close_designer_session")
        self.cli("bind-agent", PLAN, str(self.root), "--plan", PLAN, "--dispatch-id", opened["dispatch_id"], "--agent-id", "designer.phase")
        self.cli("agent-complete", str(self.root), "--plan", PLAN, "--agent-id", "designer.phase", "--final")
        self.cli("close-designer-session", str(self.root), "--plan", PLAN, "--dispatch-id", opened["dispatch_id"])
        self.assertEqual(self.payload("next-action", str(self.root), "--plan", PLAN)["action"], "authorize_plan")
        self.cli("authorize-plan", str(self.root), "--plan", PLAN, "--source", "explicit", "--reference", "ref")

        dispatched = self.payload("dispatch-task", "TASK-001", str(self.root), "--plan", PLAN)
        self.assertEqual(self.payload("next-action", str(self.root), "--plan", PLAN)["action"], "await_tasks")
        for _ in range(2):
            self.cli(
                "delegation-failed", "TASK-001", str(self.root), "--plan", PLAN,
                "--dispatch-id", dispatched["dispatch_id"], "--reason", "host delegation unavailable",
            )
        self.assertEqual(self.payload("next-action", str(self.root), "--plan", PLAN)["action"], "complete_in_main")
        self.cli("main-complete", "TASK-001", str(self.root), "--plan", PLAN, "--dispatch-id", dispatched["dispatch_id"])
        self.assertEqual(self.payload("next-action", str(self.root), "--plan", PLAN)["action"], "accept_tasks")
        self.cli("accept-task", "TASK-001", str(self.root), "--plan", PLAN)
        self.assertEqual(self.payload("next-action", str(self.root), "--plan", PLAN)["action"], "run_full_regression")
        self.payload("run-full-regression", str(self.root), "--plan", PLAN)
        review = self.payload("open-reviewer-session", str(self.root), "--plan", PLAN)
        self.assertEqual(self.payload("next-action", str(self.root), "--plan", PLAN)["action"], "await_reviewer")
        self.cli("bind-agent", PLAN, str(self.root), "--plan", PLAN, "--dispatch-id", review["dispatch_id"], "--agent-id", "rev.phase")
        self.cli("agent-complete", str(self.root), "--plan", PLAN, "--agent-id", "rev.phase", "--final")
        self.assertEqual(self.payload("next-action", str(self.root), "--plan", PLAN)["action"], "close_reviewer_session")
        self.cli("close-reviewer-session", str(self.root), "--plan", PLAN, "--dispatch-id", review["dispatch_id"])
        self.assertEqual(self.payload("next-action", str(self.root), "--plan", PLAN)["action"], "delivery_complete")

    def test_status_and_tree_report_live_v3_state(self) -> None:
        self.design_and_authorize()
        status = json.loads(self.cli("status", str(self.root), "--json").stdout)["plans"][0]
        self.assertEqual((status["code"], status["phase"], status["revision"]), (PLAN, "authorized", 1))
        self.assertEqual(status["designer_session"], "completed")
        tree = self.cli("tree", str(self.root), "--details").stdout
        self.assertIn("TASK-001", tree)
        self.assertIn("tier=standard", tree)


if __name__ == "__main__":
    unittest.main()
