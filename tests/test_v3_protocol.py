"""Focused semantic contracts for the v3 Plan language."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from scripts.better_plan.adapters.manifest_cli import build_parser
from scripts.better_plan.domain.models import (
    checkpoints_template,
    semantic_digest,
    task_worker_kind,
)
from scripts.better_plan.domain.validation import (
    MAX_TASK_ACCEPTANCE,
    MAX_TASK_CRITICAL_PATH,
    MAX_TASK_NODES,
    MAX_TASK_VERIFICATION_COMMANDS,
    MAX_TASK_WRITE_PATHS,
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

    def test_compile_receipt_rejects_errors_without_line_and_field_locations(self) -> None:
        plan = complete_plan()
        plan["lifecycle"]["designer_session"]["compile"] = {
            "pristine_digest": "0" * 64,
            "compiled_spec_digest": "1" * 64,
            "applied_at": "2026-01-01T00:00:00Z",
            "sections_from_plan": [],
            "issues": [{
                "kind": "structure",
                "message": "Task outcome is missing",
                "status": "open",
            }],
            "unmapped": [],
        }

        issues = validate_plan_document(self.path, plan)
        self.assertTrue(any("missing diagnostic fields field, line" in issue.message for issue in issues))

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

    def test_parallel_frontier_rejects_every_cross_task_dependency(self) -> None:
        plan = complete_plan()
        consumer = task(
            "TASK-002",
            write_paths=["other.txt"],
            prerequisites=["TASK-001"],
            inputs=[
                {
                    "from": "TASK-001",
                    "output": "OUT-001",
                    "guarantee": "The other Task completed first.",
                }
            ],
            acceptance_code="AC-002",
        )
        plan["spec"]["tasks"].append(consumer)
        issues = validate_plan_document(self.path, plan)
        self.assertTrue(any("dependent work belongs inside one parallel-safe Task" in issue.message for issue in issues))
        self.assertTrue(any("parallel Tasks never consume another Task's output" in issue.message for issue in issues))

    def test_task_internal_nodes_support_parallel_branches_and_joins_but_reject_cycles(self) -> None:
        plan = complete_plan()
        plan["spec"]["tasks"][0]["nodes"] = [
            {"code": "NODE-001", "title": "start", "outcome": "Prepare shared inputs.", "prerequisites": []},
            {"code": "NODE-002", "title": "branch-a", "outcome": "Complete branch A.", "prerequisites": ["NODE-001"]},
            {"code": "NODE-003", "title": "branch-b", "outcome": "Complete branch B.", "prerequisites": ["NODE-001"]},
            {
                "code": "NODE-004",
                "title": "join",
                "outcome": "Integrate both branches.",
                "prerequisites": ["NODE-002", "NODE-003"],
            },
        ]
        self.assertEqual(validate_plan_document(self.path, plan), [])

        plan["spec"]["tasks"][0]["nodes"][0]["prerequisites"] = ["NODE-004"]
        issues = validate_plan_document(self.path, plan)
        self.assertTrue(any("Node dependency cycle" in issue.message for issue in issues))

    def test_risk_tags_select_no_worker_role_and_legacy_tier_is_inert(self) -> None:
        plan = complete_plan()
        plan["spec"]["tasks"][0]["risks"] = ["migration"]
        self.assertEqual(validate_plan_document(self.path, plan), [])

        # The removed field stays schema-valid, routes nothing, and is never inspected: no role
        # reads it, so no value of it can be wrong.
        for value in ("complex", "routine", None):
            with self.subTest(difficulty=value):
                plan["spec"]["tasks"][0]["difficulty"] = value
                self.assertEqual(validate_plan_document(self.path, plan), [])
                self.assertEqual(plan_readiness_issues(self.path, plan), [])

    def test_worker_responsibility_defaults_to_code_and_rejects_unknown_values(self) -> None:
        plan = complete_plan()
        plan["spec"]["tasks"][0].pop("worker")
        self.assertEqual(validate_plan_document(self.path, plan), [])

        plan["spec"]["tasks"][0]["worker"] = "backend"
        issues = validate_plan_document(self.path, plan)
        self.assertTrue(any("must be code or hybrid" in issue.message for issue in issues))

        # A Plan sealed before the rename keeps validating and keeps its responsibility.
        for legacy, kind in (("general", "code"), ("frontend", "hybrid")):
            with self.subTest(legacy=legacy):
                plan["spec"]["tasks"][0]["worker"] = legacy
                self.assertEqual(validate_plan_document(self.path, plan), [])
                self.assertEqual(task_worker_kind(plan["spec"]["tasks"][0]), kind)

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

    def _oversized_ready_plan(self) -> dict:
        """Return a ready Plan whose single Task exceeds four single-session ceilings.

        One Task is one Worker dispatch, so its Node DAG, ownership surface and
        verification surface are all carried by a single session. This fixture is the
        shape that made a real delivery grind for thousands of steps instead of
        returning a handoff.
        """

        plan = complete_plan()
        oversized = plan["spec"]["tasks"][0]
        oversized["nodes"] = [
            {
                "code": "NODE-1%02d" % index,
                "title": "slice-%02d" % index,
                "outcome": "Complete one bounded slice of the Task.",
                "prerequisites": [],
            }
            for index in range(MAX_TASK_NODES + 1)
        ]
        oversized["ownership"]["write_paths"] = ["source.txt"] + [
            "slice-%02d.txt" % index for index in range(MAX_TASK_WRITE_PATHS)
        ]
        oversized["focused_regression"]["paths"] = list(oversized["ownership"]["write_paths"])
        oversized["focused_regression"]["commands"] = [
            "run slice %02d" % index for index in range(MAX_TASK_VERIFICATION_COMMANDS + 1)
        ]
        return plan

    def test_oversized_task_shape_is_rejected_before_authorization(self) -> None:
        plan = self._oversized_ready_plan()
        self.assertEqual(validate_plan_document(self.path, plan), [])

        issues = plan_readiness_issues(self.path, plan)
        fields = {issue.message.split(":", 1)[0] for issue in issues}
        self.assertIn("TASK-001.node_count", fields)
        self.assertIn("TASK-001.max_parallel_frontier", fields)
        self.assertIn("TASK-001.write_path_count", fields)
        self.assertIn("TASK-001.verification_command_count", fields)
        ceilings = [issue for issue in issues if "exceeds the single-session ceiling" in issue.message]
        self.assertEqual(len(ceilings), 4)
        self.assertTrue(all("split this Task" in issue.message for issue in ceilings))

    def test_concurrent_nodes_must_declare_the_machine_resources_they_share(self) -> None:
        """A wide intra-Task frontier is a physical contention claim, not just structure.

        Nodes share their Task's ownership, so concurrent Nodes contend on the build
        directory, version-control lock and test stores the Task never assigned away.
        That is a completeness requirement and never predicts how large the Task is.
        """

        plan = complete_plan()
        plan["spec"]["tasks"][0]["nodes"] = [
            {
                "code": "NODE-%03d" % index,
                "title": "branch-%03d" % index,
                "outcome": "Implement one independent branch of the Task.",
                "prerequisites": [],
            }
            for index in range(1, 4)
        ]
        self.assertEqual(validate_plan_document(self.path, plan), [])
        issues = plan_readiness_issues(self.path, plan)
        self.assertEqual(
            [issue.message.split(":", 1)[0] for issue in issues],
            ["TASK-001.ownership.shared_exclusive"],
        )

        plan["spec"]["tasks"][0]["ownership"]["shared_exclusive"] = [
            "build directory — isolated per Node under target/<node>/"
        ]
        self.assertEqual(plan_readiness_issues(self.path, plan), [])

    def test_responsibility_and_evidence_must_agree(self) -> None:
        """`hybrid` means the Task writes code *and* its result is judged visually.

        Responsibility and evidence answer the same question, so a Task that answers it two
        different ways is a design defect. A sealed Plan is never re-judged.
        """

        for worker, verification in (("hybrid", "code"), ("code", "hybrid")):
            with self.subTest(worker=worker, verification=verification):
                plan = complete_plan()
                plan["spec"]["tasks"][0]["worker"] = worker
                plan["spec"]["tasks"][0]["verification"] = verification
                issues = plan_readiness_issues(self.path, plan)
                self.assertEqual(
                    [issue.message.split(":", 1)[0] for issue in issues], ["TASK-001.worker"]
                )
                self.assertIn("make both say hybrid or both say code", issues[0].message)

        for worker, verification in (("code", "code"), ("hybrid", "hybrid")):
            with self.subTest(worker=worker, verification=verification):
                plan = complete_plan()
                plan["spec"]["tasks"][0]["worker"] = worker
                plan["spec"]["tasks"][0]["verification"] = verification
                self.assertEqual(plan_readiness_issues(self.path, plan), [])

        # A sealed Plan is frozen history, not a readiness defect.
        plan = complete_plan()
        plan["spec"]["tasks"][0]["verification"] = "hybrid"
        plan["phase"] = "authorized"
        digest = semantic_digest(plan)
        plan["lifecycle"]["sealed"] = {
            "revision": 1,
            "semantic_digest": digest,
            "sealed_at": "2026-01-01T00:00:00Z",
        }
        plan["lifecycle"]["authorization"] = {
            "source": "explicit",
            "reference_digest": "0" * 64,
            "semantic_digest": digest,
            "risk_reasons": [],
            "autonomy": plan["intent"]["autonomy"],
            "authorized_at": "2026-01-01T00:00:00Z",
        }
        plan["lifecycle"]["reviewer_session"] = None
        self.assertEqual(plan_readiness_issues(self.path, plan), [])

    def test_a_wide_frontier_only_requires_the_resources_to_be_named(self) -> None:
        """Readiness checks that the resources are declared, not how the text describes them.

        The Designer owes concurrent Nodes separate paths, but no wording rule can establish that;
        the Reviewer judges whether the named text actually separates them.
        """

        plan = complete_plan()
        plan["spec"]["tasks"][0]["nodes"] = [
            {
                "code": "NODE-%03d" % index,
                "title": "branch-%03d" % index,
                "outcome": "Implement one independent branch of the Task.",
                "prerequisites": [],
            }
            for index in range(1, 4)
        ]
        plan["spec"]["tasks"][0]["ownership"]["shared_exclusive"] = [
            "build target directory — one per Node",
            "shared cargo registry cache",
        ]
        self.assertEqual(validate_plan_document(self.path, plan), [])
        self.assertEqual(plan_readiness_issues(self.path, plan), [])

    def test_legacy_evidence_value_still_loads_an_authorized_plan(self) -> None:
        """`visual` was the pre-rename evidence value, so a sealed Plan must stay readable.

        The rename maps `frontend`/`visual` onto the hybrid Worker instead of invalidating the
        revision a user already authorized.
        """

        plan = complete_plan()
        plan["spec"]["tasks"][0]["worker"] = "frontend"
        plan["spec"]["tasks"][0]["verification"] = "visual"
        self.assertEqual(validate_plan_document(self.path, plan), [])
        self.assertEqual(plan_readiness_issues(self.path, plan), [])
        self.assertEqual(task_worker_kind(plan["spec"]["tasks"][0]), "hybrid")

    def test_unmeasurable_task_dag_is_reported_by_readiness(self) -> None:
        """An empty or cyclic Node DAG must never pass merely because its size cannot be counted."""

        plan = complete_plan()
        plan["phase"] = "ready"
        plan["spec"]["tasks"][0]["nodes"] = []
        self.assertEqual(validate_plan_document(self.path, plan), [])
        self.assertEqual(
            [issue.message.split(":", 1)[0] for issue in plan_readiness_issues(self.path, plan)],
            ["TASK-001.nodes"],
        )

    def test_deep_or_wide_acceptance_surface_is_rejected_before_authorization(self) -> None:
        """The remaining two ceilings are enforced on their own evidence, not only via Node count."""

        plan = complete_plan()
        target = plan["spec"]["tasks"][0]
        target["nodes"] = [
            {
                "code": "NODE-%03d" % index,
                "title": "step-%03d" % index,
                "outcome": "Complete one ordered step of the Task.",
                "prerequisites": [] if index == 1 else ["NODE-%03d" % (index - 1)],
            }
            for index in range(1, MAX_TASK_CRITICAL_PATH + 2)
        ]
        target["acceptance"] = [
            {
                "code": "AC-%03d" % index,
                "covers": ["REQ-001", "OUT-001"],
                "given": "A valid authorized workspace state",
                "when": "One bounded behavior is exercised",
                "then": "That behavior is observed",
                "oracle": "The observed behavior matches the requirement",
                "evidence": {"type": "command", "source": "focused regression"},
            }
            for index in range(1, MAX_TASK_ACCEPTANCE + 2)
        ]
        self.assertEqual(validate_plan_document(self.path, plan), [])
        fields = {issue.message.split(":", 1)[0] for issue in plan_readiness_issues(self.path, plan)}
        self.assertIn("TASK-001.critical_path_nodes", fields)
        self.assertIn("TASK-001.acceptance_count", fields)

    def test_a_single_ready_node_declares_no_shared_resource(self) -> None:
        """One ready Node has no intra-Task contention, so no declaration is required."""

        plan = complete_plan()
        plan["spec"]["requirements"].append(
            {"code": "REQ-002", "statement": "A second observable behavior is verified.", "source_refs": ["user-request"]}
        )
        plan["spec"]["tasks"].append(
            task("TASK-002", write_paths=["second.txt"], acceptance_code="AC-002", requirements=["REQ-002"])
        )
        self.assertEqual(validate_plan_document(self.path, plan), [])
        self.assertEqual(plan_readiness_issues(self.path, plan), [])

    def test_sealed_plan_is_not_re_judged_against_the_task_size_ceiling(self) -> None:
        plan = self._sealed_oversized_plan()
        # Without execution state the caller cannot tell what began, so nothing is re-judged.
        self.assertEqual(plan_readiness_issues(self.path, plan), [])

    def test_an_unstarted_task_in_a_sealed_plan_is_still_judged(self) -> None:
        """The ceiling is a design-time rule, and a Task that never began is still design work."""

        plan = self._sealed_oversized_plan()
        started = plan_readiness_issues(self.path, plan, frozenset({"TASK-001"}))
        self.assertEqual(started, [])

        unstarted = plan_readiness_issues(self.path, plan, frozenset())
        fields = {issue.message.split(":", 1)[0] for issue in unstarted}
        self.assertIn("TASK-001.node_count", fields)
        self.assertIn("TASK-001.write_path_count", fields)

    def _sealed_oversized_plan(self) -> dict:
        plan = self._oversized_ready_plan()
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
        return plan

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
            self.assertIn("before opening the sole Reviewer", document)
            self.assertNotIn("Run inside the sole Reviewer session", document)
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
                "record-task-input",
                "main-complete",
                "run-full-regression",
                "open-reviewer-session",
                "record-reviewer-findings",
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
