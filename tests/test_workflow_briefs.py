"""Fresh-context briefs retain binding contracts without repeated role guidance."""

from copy import deepcopy
import unittest

from scripts.better_plan.application.workflow import _leaf_brief, _reviewer_brief
from scripts.better_plan.domain.models import checkpoints_template, semantic_payload
from tests.v3_fixtures import complete_plan, task


class WorkflowBriefTests(unittest.TestCase):
    def test_worker_keeps_global_constraints_and_decisions_with_only_its_requirements(self) -> None:
        plan = complete_plan("plans/delivery")
        plan["ledger"]["user_decided"] = [{
            "source": "Q-001", "option": "preserve", "resolves": ["DEC-001"],
            "effects": ["Preserve the public interface across the delivery."],
        }]
        plan["ledger"]["defaulted"] = [{
            "source": "Q-002", "option": "local", "resolves": ["DEC-002"],
            "effects": ["Keep all processing local."],
        }]
        plan["spec"]["requirements"].append({
            "code": "REQ-002", "statement": "Render the separate view.", "source_refs": ["user-request"],
        })
        plan["spec"]["tasks"].append(task(
            "TASK-002", write_paths=["view.py"], requirements=["REQ-002"],
            verification="hybrid", worker="frontend", acceptance_code="AC-002",
        ))
        original = deepcopy(plan)

        brief = _leaf_brief(plan, plan["spec"]["tasks"][0])

        self.assertEqual(brief["plan_path"], "plans/delivery/Plan.json")
        for field in ("goal", "success", "risk_boundary"):
            self.assertEqual(brief[field], plan["intent"][field])
        self.assertEqual(brief["authorized_scope"], plan["intent"]["scope"])
        self.assertEqual(brief["requirements"], [plan["spec"]["requirements"][0]])
        self.assertEqual(brief["architecture"], plan["spec"]["architecture"])
        self.assertEqual(brief["decisions"], plan["ledger"]["user_decided"] + plan["ledger"]["defaulted"])
        self.assertEqual(brief["task"], plan["spec"]["tasks"][0])
        self.assertEqual(plan, original)

    def test_reviewer_keeps_semantics_and_all_evidence_without_duplicate_regression_or_dispatch(self) -> None:
        plan = complete_plan()
        plan["spec"]["tasks"][0]["verification"] = "hybrid"
        plan["spec"]["tasks"][0]["worker"] = "frontend"
        plan["spec"]["tasks"].append(task("TASK-002", write_paths=["export.py"], acceptance_code="AC-002"))
        checkpoints = checkpoints_template(plan)
        regression = {
            "passed": False,
            "commands": [{
                "command_sha256": "a" * 64, "outcome": "failed", "exit_code": 1,
                "recorded_at": "2026-09-23T00:00:00Z",
            }],
            "content_fingerprint": "b" * 64,
            "recorded_at": "2026-09-23T00:00:00Z",
        }
        checkpoints["full_regression"] = regression
        checkpoints["tasks"][0].update(status="completed", evidence=[
            {"kind": "focused_regression", "passed": False, "commands": regression["commands"]},
            {"kind": "user_input", "request": "Supply a fixture.", "resolution": "Fixture supplied."},
            {"kind": "focused_regression", "passed": True, "commands": []},
        ])
        checkpoints["tasks"][1].update(
            status="blocked_by_environment", status_reason="The external test service is unavailable.",
            dispatch={"id": "transport-only", "phase": "awaiting_acceptance"},
        )
        original = deepcopy((plan, checkpoints, regression))

        brief = _reviewer_brief(plan, checkpoints, regression, ["TASK-001"])

        self.assertEqual(brief["plan_path"], "delivery/Plan.json")
        self.assertEqual(brief["checkpoints_path"], "delivery/Checkpoints.json")
        self.assertEqual(brief["plan"], semantic_payload(plan))
        self.assertEqual(brief["full_regression"]["result"], regression)
        self.assertNotIn("contract", brief["full_regression"])
        self.assertNotIn("full_regression", brief["checkpoints"])
        self.assertEqual(len(brief["checkpoints"]["tasks"]), len(checkpoints["tasks"]))
        for actual, state in zip(brief["checkpoints"]["tasks"], checkpoints["tasks"]):
            self.assertNotIn("dispatch", actual)
            for field, value in state.items():
                if field != "dispatch":
                    self.assertEqual(actual[field], value)
        self.assertEqual(brief["rendered_evidence_tasks"], ["TASK-001"])
        self.assertIn("ephemeral diagnostics", brief["full_regression"]["diagnostics_handoff"])
        self.assertEqual((plan, checkpoints, regression), original)


if __name__ == "__main__":
    unittest.main()
