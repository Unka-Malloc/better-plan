"""Focused semantic contracts for the v3 Plan language."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from scripts.better_plan.adapters.manifest_cli import build_parser
from scripts.better_plan.domain.models import checkpoints_template, semantic_digest
from scripts.better_plan.domain.validation import (
    plan_readiness_issues,
    validate_checkpoints_document,
    validate_plan_document,
)
from scripts.better_plan.infrastructure.plan_render import render_document, render_plan
from tests.v3_fixtures import complete_plan, task


class V3ProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.path = Path("Plan.json")

    def test_complete_plan_is_semantically_ready(self) -> None:
        self.assertEqual(plan_readiness_issues(self.path, complete_plan()), [])

    def test_earlier_generations_and_unknown_fields_fail_closed(self) -> None:
        issues = validate_plan_document(self.path, [{"id": "legacy-record"}])
        self.assertTrue(any("top-level" in issue.message for issue in issues))
        legacy = complete_plan()
        legacy["schema"] = "better-plan.plan/v2"
        legacy["spec"]["gates"] = []
        issues = validate_plan_document(self.path, legacy)
        self.assertTrue(any("unsupported generation" in issue.message for issue in issues))
        self.assertTrue(any("unknown fields gates" in issue.message for issue in issues))

    def test_privacy_boundary_rejects_machine_and_runtime_text_but_allows_public_docs(self) -> None:
        plan = complete_plan()
        plan["ledger"]["observed"] = [
            {"fact": "The module is here.", "source": "/private/workspace/file"},
            {"fact": "The service runs locally.", "source": "http://localhost:9000/health"},
        ]
        issues = validate_plan_document(self.path, plan)
        self.assertTrue(any("absolute local path" in issue.message for issue in issues))
        self.assertTrue(any("runtime endpoint" in issue.message for issue in issues))

        allowed = complete_plan()
        allowed["spec"]["requirements"][0]["source_refs"] = [
            "https://example.com/spec#section-3",
            "docs/design.md",
        ]
        self.assertEqual(plan_readiness_issues(self.path, allowed), [])

    def test_secret_shaped_data_is_rejected_but_prose_is_not(self) -> None:
        plan = complete_plan()
        plan["intent"]["success"].append("Send header Bearer sk-abcdefghijklmnopqrstuvwxyz012345")
        issues = validate_plan_document(self.path, plan)
        self.assertTrue(any("secret-shaped data" in issue.message for issue in issues))

        allowed = complete_plan()
        allowed["intent"]["success"].append("Bearer authentication is required by the public API.")
        self.assertEqual(plan_readiness_issues(self.path, allowed), [])

    def test_portable_commands_and_arithmetic_are_not_absolute_paths(self) -> None:
        plan = complete_plan()
        plan["spec"]["full_regression"]["commands"] = [
            "python3 -m pytest tests/**/*.py -q",
            "coverage report --fail-under 80",
            "compare ratio 3 / 4",
        ]
        self.assertEqual(plan_readiness_issues(self.path, plan), [])

        for leaked in ("/usr/bin/python3 run.py", "~/scripts/run.sh", "C:\\tools\\run.exe"):
            broken = complete_plan()
            broken["spec"]["full_regression"]["commands"] = [leaked]
            issues = validate_plan_document(self.path, broken)
            with self.subTest(command=leaked):
                self.assertTrue(any("absolute local path" in issue.message for issue in issues))

    def test_dot_directories_survive_path_normalization(self) -> None:
        plan = complete_plan()
        plan["spec"]["tasks"][0]["ownership"]["write_paths"] = [".github/workflows"]
        plan["spec"]["tasks"][0]["outputs"][0]["artifact"] = ".github/workflows/ci.yml"
        plan["spec"]["tasks"][0]["focused_regression"]["paths"] = [".github/workflows/ci.yml"]
        second = task("TASK-002", write_paths=[".githubbackup"], acceptance_code="AC-002")
        plan["spec"]["tasks"].append(second)
        # `.github/workflows` and `.githubbackup` are disjoint; a naive prefix
        # strip would have collapsed both to `github...` and reported a conflict.
        self.assertEqual(validate_plan_document(self.path, plan), [])

    def test_output_artifacts_must_stay_inside_write_ownership(self) -> None:
        plan = complete_plan()
        plan["spec"]["tasks"][0]["outputs"][0]["artifact"] = "unowned.txt"
        issues = validate_plan_document(self.path, plan)
        self.assertTrue(any("inside this Task's write ownership" in issue.message for issue in issues))

    def test_a_sealed_revision_cannot_coexist_with_an_unauthorized_phase(self) -> None:
        plan = complete_plan()
        plan["lifecycle"]["sealed"] = {
            "revision": 1,
            "semantic_digest": semantic_digest(plan),
            "sealed_at": "2026-01-01T00:00:00Z",
        }
        issues = validate_plan_document(self.path, plan)
        self.assertTrue(any("cannot return to ready" in issue.message for issue in issues))

    def test_revising_requires_its_continuation_receipt(self) -> None:
        plan = complete_plan()
        plan["phase"] = "revising"
        digest = semantic_digest(plan)
        plan["lifecycle"]["sealed"] = {"revision": 1, "semantic_digest": digest, "sealed_at": "2026-01-01T00:00:00Z"}
        plan["lifecycle"]["authorization"] = {
            "source": "explicit",
            "reference_digest": "0" * 64,
            "semantic_digest": digest,
            "risk_reasons": [],
            "autonomy": plan["intent"]["autonomy"],
            "authorized_at": "2026-01-01T00:00:00Z",
        }
        issues = validate_plan_document(self.path, plan)
        self.assertTrue(any("requires its continuation receipt" in issue.message for issue in issues))

    def test_dossier_resolution_requires_selection_and_one_ledger_record(self) -> None:
        plan = complete_plan()
        plan["ledger"]["unresolved"] = [
            {"code": "DEC-001", "statement": "Choose the boundary.", "impact": "It changes scope."}
        ]
        plan["dossier"] = {
            "status": "resolved",
            "questions": [
                {
                    "code": "Q-001",
                    "question": "Which delivery boundary applies?",
                    "context": "Both boundaries are supported.",
                    "resolves": ["DEC-001"],
                    "options": [
                        {"id": "safe", "label": "Keep both surfaces", "effects": ["Old callers keep working."]},
                        {"id": "replace", "label": "Remove the old surface", "effects": ["Old callers are migrated."]},
                    ],
                    "recommended": "safe",
                    "default": "safe",
                }
            ],
        }
        issues = validate_plan_document(self.path, plan)
        self.assertTrue(any("requires a selection" in issue.message for issue in issues))

        plan["dossier"]["questions"][0]["selected"] = "safe"
        issues = plan_readiness_issues(self.path, plan)
        self.assertTrue(any("must be resolved or defaulted" in issue.message for issue in issues))
        self.assertTrue(any("no ledger decision record" in issue.message for issue in issues))

    def test_missing_coverage_and_unowned_coverage_are_both_rejected(self) -> None:
        plan = complete_plan()
        plan["spec"]["tasks"][0]["acceptance"][0]["covers"] = ["REQ-001"]
        issues = validate_plan_document(self.path, plan)
        self.assertTrue(any("coverage missing OUT-001" in issue.message for issue in issues))

        plan = complete_plan()
        plan["spec"]["tasks"][0]["acceptance"][0]["covers"].append("REQ-404")
        issues = validate_plan_document(self.path, plan)
        self.assertTrue(any("covers unowned contracts REQ-404" in issue.message for issue in issues))

    def test_parallel_write_and_exclusive_resource_collisions_are_rejected(self) -> None:
        plan = complete_plan()
        plan["spec"]["tasks"].append(task("TASK-002", acceptance_code="AC-002"))
        issues = validate_plan_document(self.path, plan)
        self.assertTrue(any("overlapping write ownership" in issue.message for issue in issues))

        plan = complete_plan()
        second = task("TASK-002", write_paths=["other.txt"], acceptance_code="AC-002")
        plan["spec"]["tasks"][0]["ownership"]["shared_exclusive"] = ["release channel"]
        second["ownership"]["shared_exclusive"] = ["release channel"]
        plan["spec"]["tasks"].append(second)
        issues = validate_plan_document(self.path, plan)
        self.assertTrue(any("share exclusive resources" in issue.message for issue in issues))

    def test_prerequisites_are_the_only_graph_and_every_edge_maps_one_input(self) -> None:
        plan = complete_plan()
        consumer = task(
            "TASK-002",
            write_paths=["other.txt"],
            prerequisites=["TASK-001"],
            acceptance_code="AC-002",
        )
        plan["spec"]["tasks"].append(deepcopy(consumer))
        issues = validate_plan_document(self.path, plan)
        self.assertTrue(any("must map at least one input" in issue.message for issue in issues))

        consumer["inputs"] = [
            {"from": "TASK-001", "output": "OUT-001", "guarantee": "The upstream behavior holds."}
        ]
        plan["spec"]["tasks"][1] = consumer
        self.assertEqual(validate_plan_document(self.path, plan), [])

        plan["spec"]["tasks"][0]["prerequisites"] = ["TASK-002"]
        plan["spec"]["tasks"][0]["inputs"] = [
            {"from": "TASK-002", "output": "OUT-002", "guarantee": "The downstream behavior holds."}
        ]
        issues = validate_plan_document(self.path, plan)
        self.assertTrue(any("dependency cycle" in issue.message for issue in issues))

    def test_elevated_risk_requires_the_strong_worker_tier(self) -> None:
        plan = complete_plan()
        plan["spec"]["tasks"][0]["risks"] = ["migration"]
        issues = validate_plan_document(self.path, plan)
        self.assertTrue(any("requires the complex tier" in issue.message for issue in issues))
        plan["spec"]["tasks"][0]["difficulty"] = "complex"
        self.assertEqual(validate_plan_document(self.path, plan), [])

    def test_authorized_phase_binds_the_semantic_digest(self) -> None:
        plan = complete_plan()
        plan["phase"] = "authorized"
        digest = semantic_digest(plan)
        plan["lifecycle"]["sealed"] = {"revision": 1, "semantic_digest": digest, "sealed_at": "2026-01-01T00:00:00Z"}
        plan["lifecycle"]["authorization"] = {
            "source": "explicit",
            "reference_digest": "0" * 64,
            "semantic_digest": digest,
            "risk_reasons": [],
            "autonomy": plan["intent"]["autonomy"],
            "authorized_at": "2026-01-01T00:00:00Z",
        }
        plan["lifecycle"]["reviewer_session"] = None
        self.assertEqual(validate_plan_document(self.path, plan), [])

        plan["spec"]["requirements"][0]["statement"] = "A silently expanded requirement."
        issues = validate_plan_document(self.path, plan)
        self.assertTrue(any("stale semantic binding" in issue.message for issue in issues))

    def test_checkpoints_project_every_task_exactly_once(self) -> None:
        plan = complete_plan()
        plan["lifecycle"]["sealed"] = {
            "revision": 1,
            "semantic_digest": semantic_digest(plan),
            "sealed_at": "2026-01-01T00:00:00Z",
        }
        checkpoints = checkpoints_template(plan)
        self.assertEqual(validate_checkpoints_document(Path("Checkpoints.json"), checkpoints, plan), [])
        checkpoints["tasks"] = []
        issues = validate_checkpoints_document(Path("Checkpoints.json"), checkpoints, plan)
        self.assertTrue(any("every Task exactly once" in issue.message for issue in issues))

    def test_projection_is_deterministic_and_render_only(self) -> None:
        plan = complete_plan()
        with tempfile.TemporaryDirectory() as tmpdir:
            directory = Path(tmpdir)
            first = render_plan(directory, plan)
            second = render_plan(directory, plan)
            self.assertEqual(first, second)
            self.assertEqual(sorted(item.name for item in directory.iterdir()), ["Plan.md"])
            document = (directory / "Plan.md").read_text(encoding="utf-8")
            self.assertEqual(document, render_document(plan))
            self.assertIn("render-only projection", document)
            self.assertIn("TASK-001", document)
            self.assertNotIn("better-plan:begin", document)

    def test_cli_exposes_only_the_v3_lifecycle(self) -> None:
        action = next(item for item in build_parser()._actions if item.dest == "command")
        commands = set(action.choices)
        self.assertTrue(
            {
                "init-plan",
                "build-dossier",
                "resolve-dossier",
                "open-designer-session",
                "close-designer-session",
                "check-readiness",
                "authorize-plan",
                "begin-continuation",
                "next-action",
                "dispatch-task",
                "accept-task",
                "main-complete",
                "open-reviewer-session",
            }.issubset(commands)
        )
        self.assertTrue(
            {
                "seal-plan",
                "render-plan",
                "import-plan-edits",
                "check-host-readiness",
                "task-ready",
                "open-visual-verifier",
                "complete-gate",
                "block-gate",
                "init-capabilities",
                "upsert-capability",
                "promote-capability",
                "capability-tree",
                "discover",
                "uuid",
                "dispatch",
                "rewire",
                "repair-plan",
                "decision-session",
                "set-status",
                "transition",
            }.isdisjoint(commands)
        )


if __name__ == "__main__":
    unittest.main()
