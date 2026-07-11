from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_TOOL_PATH = REPO_ROOT / "scripts" / "manifest_tool.py"

spec = importlib.util.spec_from_file_location("manifest_tool", MANIFEST_TOOL_PATH)
assert spec is not None
manifest_tool = importlib.util.module_from_spec(spec)
sys.modules["manifest_tool"] = manifest_tool
assert spec.loader is not None
spec.loader.exec_module(manifest_tool)


PLAN_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
NODE_A_ID = "11111111-1111-4111-8111-111111111111"
NODE_B_ID = "22222222-2222-4222-8222-222222222222"
NODE_C_ID = "33333333-3333-4333-8333-333333333333"
NODE_D_ID = "44444444-4444-4444-8444-444444444444"


def make_node(
    node_id: str,
    status: str,
    *,
    role: str = "implementation",
    prerequisites: list[str] | None = None,
    difficulty: str = "medium",
    checked: bool = True,
    requirements: list[str] | None = None,
    description: str = "Test node for Better Plan state machine rules.",
    status_reason: str | None = None,
) -> dict[str, object]:
    node: dict[str, object] = {
        "id": node_id,
        "status": status,
        "role": role,
        "prerequisites": prerequisites or [],
        "platform": "any",
        "difficulty": difficulty,
        "goal": "Exercise state machine validation.",
        "description": description,
        "requirements": ["REQ-001"] if requirements is None else requirements,
        "acceptance_criteria": [
            {
                "checked": checked,
                "text": "State machine validation has evidence.",
            }
        ],
        "commit": {
            "repository": ".git",
            "message": "test state machine",
            "target": "tests",
        },
        "next": [],
    }
    if status_reason is not None:
        node["status_reason"] = status_reason
    return node


def make_plan(status: str) -> dict[str, object]:
    return {
        "id": PLAN_ID,
        "status": status,
        "title": "Main Plan",
        "directory": "main-plan",
        "source_files": ["docs/plan.md"],
        "goal": "Exercise plan state validation.",
        "description": "Test plan for Better Plan state machine rules.",
        "checkpoints": "main-plan/Checkpoints.json",
    }


def plan_snapshot_issues(plan_status: str, nodes: list[dict[str, object]]) -> list[object]:
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        plan_dir = workspace / "main-plan"
        plan_dir.mkdir()
        (plan_dir / "Checkpoints.json").write_text(json.dumps(nodes), encoding="utf-8")
        manifest = [make_plan(plan_status)]
        manifest_path = workspace / "Manifest.json"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        _, issues = manifest_tool.validate_plan_manifest_data(manifest_path, manifest)
    return issues


class WorkflowStateMachineTests(unittest.TestCase):
    def test_transition_rules_allow_expected_edges(self) -> None:
        machine = manifest_tool.WORKFLOW_STATE_MACHINE

        self.assertTrue(machine.can_transition("pending", "in_progress"))
        self.assertTrue(machine.can_transition("in_progress", "completed"))
        self.assertTrue(machine.can_transition("blocked", "in_progress"))
        self.assertFalse(machine.can_transition("completed", "in_progress"))
        self.assertFalse(machine.can_transition("skipped", "pending"))

    def test_reachability_follows_transition_paths(self) -> None:
        machine = manifest_tool.WORKFLOW_STATE_MACHINE

        self.assertTrue(machine.can_reach("pending", "completed"))
        self.assertTrue(machine.can_reach("blocked", "completed"))
        self.assertTrue(machine.can_reach("pending", "pending"))
        self.assertFalse(machine.can_reach("completed", "in_progress"))
        self.assertFalse(machine.can_reach("skipped", "pending"))
        self.assertFalse(machine.can_reach("completed", "skipped"))

    def test_in_progress_node_requires_completed_prerequisites(self) -> None:
        data = [
            make_node(NODE_A_ID, "pending"),
            make_node(NODE_B_ID, "in_progress", prerequisites=[NODE_A_ID]),
        ]

        _, issues = manifest_tool.validate_checkpoints_data(Path("Checkpoints.json"), data)

        self.assertTrue(
            any("cannot be 'in_progress' until prerequisites are completed" in issue.message for issue in issues),
            [issue.message for issue in issues],
        )

    def test_completed_node_requires_checked_acceptance_criteria(self) -> None:
        data = [make_node(NODE_A_ID, "completed", checked=False)]

        _, issues = manifest_tool.validate_checkpoints_data(Path("Checkpoints.json"), data)

        self.assertTrue(
            any("cannot be 'completed' with unchecked acceptance criteria" in issue.message for issue in issues),
            [issue.message for issue in issues],
        )

    def test_only_one_checkpoint_node_may_be_in_progress(self) -> None:
        data = [
            make_node(NODE_A_ID, "in_progress"),
            make_node(NODE_B_ID, "in_progress"),
        ]

        _, issues = manifest_tool.validate_checkpoints_data(Path("Checkpoints.json"), data)

        self.assertTrue(
            any("only one node may be in_progress" in issue.message for issue in issues),
            [issue.message for issue in issues],
        )

    def test_skipped_prerequisite_makes_dependents_unstartable(self) -> None:
        data = [
            make_node(NODE_A_ID, "skipped", status_reason="Deferred by the user."),
            make_node(NODE_B_ID, "pending", prerequisites=[NODE_A_ID]),
            make_node(NODE_C_ID, "pending", prerequisites=[NODE_B_ID]),
        ]

        _, issues = manifest_tool.validate_checkpoints_data(Path("Checkpoints.json"), data)

        messages = [issue.message for issue in issues]
        self.assertTrue(any("node[1]: unstartable" in message for message in messages), messages)
        self.assertTrue(any("node[2]: unstartable" in message for message in messages), messages)

    def test_terminal_dependents_of_skipped_prerequisites_are_accepted(self) -> None:
        data = [
            make_node(NODE_A_ID, "skipped", status_reason="Deferred by the user."),
            make_node(NODE_B_ID, "skipped", prerequisites=[NODE_A_ID], status_reason="Cascade skipped."),
        ]

        _, issues = manifest_tool.validate_checkpoints_data(Path("Checkpoints.json"), data)

        self.assertFalse([issue.message for issue in issues if "unstartable" in issue.message])

    def test_completed_plan_requires_terminal_checkpoint_nodes(self) -> None:
        issues = plan_snapshot_issues("completed", [make_node(NODE_A_ID, "pending")])

        self.assertTrue(
            any("cannot be 'completed' while checkpoints contain non-terminal nodes" in issue.message for issue in issues),
            [issue.message for issue in issues],
        )

    def test_pending_plan_with_started_work_is_reported_as_drift(self) -> None:
        issues = plan_snapshot_issues(
            "pending",
            [make_node(NODE_A_ID, "completed"), make_node(NODE_B_ID, "pending")],
        )

        self.assertTrue(
            any("cannot stay 'pending' after checkpoint work has started" in issue.message for issue in issues),
            [issue.message for issue in issues],
        )

    def test_pending_plan_with_all_terminal_nodes_is_reported_as_drift(self) -> None:
        issues = plan_snapshot_issues("pending", [make_node(NODE_A_ID, "completed")])

        self.assertTrue(
            any("cannot stay 'pending' when every checkpoint node is terminal" in issue.message for issue in issues),
            [issue.message for issue in issues],
        )

    def test_in_progress_plan_with_all_terminal_nodes_is_reported_as_drift(self) -> None:
        issues = plan_snapshot_issues("in_progress", [make_node(NODE_A_ID, "completed")])

        self.assertTrue(
            any("cannot stay 'in_progress' when every checkpoint node is terminal" in issue.message for issue in issues),
            [issue.message for issue in issues],
        )

    def test_foundation_roles_require_high_or_deep_difficulty(self) -> None:
        data = [make_node(NODE_A_ID, "pending", role="product_requirements", difficulty="medium")]

        _, issues = manifest_tool.validate_checkpoints_data(Path("Checkpoints.json"), data)

        self.assertTrue(
            any("role 'product_requirements' must use 'high' or 'deep'" in issue.message for issue in issues),
            [issue.message for issue in issues],
        )

    def test_foundation_roles_accept_high_difficulty(self) -> None:
        data = [make_node(NODE_A_ID, "pending", role="product_requirements", difficulty="high")]

        _, issues = manifest_tool.validate_checkpoints_data(Path("Checkpoints.json"), data)

        self.assertFalse([issue.message for issue in issues if "difficulty" in issue.message])

    def test_architecture_role_requires_prior_validation_matrix(self) -> None:
        data = [
            make_node(NODE_A_ID, "pending", role="architecture_scaffold", difficulty="high"),
            make_node(NODE_B_ID, "pending", role="validation_matrix", difficulty="deep"),
        ]

        _, issues = manifest_tool.validate_checkpoints_data(Path("Checkpoints.json"), data)

        self.assertTrue(
            any("'architecture_scaffold' must not appear before 'validation_matrix'" in issue.message for issue in issues),
            [issue.message for issue in issues],
        )

    def test_implementation_requires_requirement_labels_or_enabling_description(self) -> None:
        data = [make_node(NODE_A_ID, "pending", requirements=[])]

        _, issues = manifest_tool.validate_checkpoints_data(Path("Checkpoints.json"), data)

        self.assertTrue(
            any("implementation nodes must list at least one requirement label" in issue.message for issue in issues),
            [issue.message for issue in issues],
        )

        enabling = [
            make_node(
                NODE_A_ID,
                "pending",
                requirements=[],
                description="Enabling work that prepares the harness for REQ-002 delivery.",
            )
        ]

        _, issues = manifest_tool.validate_checkpoints_data(Path("Checkpoints.json"), enabling)

        self.assertFalse(
            [issue.message for issue in issues if "must list at least one requirement label" in issue.message]
        )

    def test_final_validation_must_cover_implementation_labels(self) -> None:
        data = [
            make_node(NODE_A_ID, "completed", requirements=["REQ-001", "REQ-002"]),
            make_node(
                NODE_B_ID,
                "pending",
                role="final_validation",
                difficulty="high",
                requirements=["REQ-001"],
            ),
        ]

        _, issues = manifest_tool.validate_checkpoints_data(Path("Checkpoints.json"), data)

        self.assertTrue(
            any("final_validation must cover requirement label(s): REQ-002" in issue.message for issue in issues),
            [issue.message for issue in issues],
        )

    def test_final_validation_must_list_requirement_labels(self) -> None:
        data = [
            make_node(NODE_A_ID, "pending", role="final_validation", difficulty="high", requirements=[]),
        ]

        _, issues = manifest_tool.validate_checkpoints_data(Path("Checkpoints.json"), data)

        self.assertTrue(
            any("final_validation nodes must list the requirement labels they prove" in issue.message for issue in issues),
            [issue.message for issue in issues],
        )

    def test_optional_fields_are_type_checked(self) -> None:
        blocked = make_node(NODE_A_ID, "blocked", status_reason=" ")
        delivered = make_node(NODE_B_ID, "pending")
        delivered["commit"]["delivered"] = "NOT-A-SHA"  # type: ignore[index]
        evidence = make_node(NODE_C_ID, "pending")
        evidence["acceptance_criteria"][0]["evidence"] = ""  # type: ignore[index]
        labels = make_node(NODE_D_ID, "pending", requirements=["REQ 001"])

        _, issues = manifest_tool.validate_checkpoints_data(
            Path("Checkpoints.json"), [blocked, delivered, evidence, labels]
        )

        messages = [issue.message for issue in issues]
        self.assertTrue(any("status_reason: must be a non-empty string" in message for message in messages), messages)
        self.assertTrue(any("commit.delivered: must be a lowercase hex commit sha" in message for message in messages), messages)
        self.assertTrue(any("evidence: must be a non-empty string" in message for message in messages), messages)
        self.assertTrue(
            any("must be a non-empty label without whitespace" in message for message in messages), messages
        )

    def test_derive_plan_status_follows_node_states(self) -> None:
        derive = manifest_tool.derive_plan_status

        self.assertEqual(derive("pending", []), "pending")
        self.assertEqual(
            derive("pending", [make_node(NODE_A_ID, "pending"), make_node(NODE_B_ID, "pending")]),
            "pending",
        )
        self.assertEqual(
            derive("pending", [make_node(NODE_A_ID, "in_progress"), make_node(NODE_B_ID, "pending")]),
            "in_progress",
        )
        self.assertEqual(
            derive("pending", [make_node(NODE_A_ID, "completed"), make_node(NODE_B_ID, "pending")]),
            "in_progress",
        )
        self.assertEqual(
            derive("in_progress", [make_node(NODE_A_ID, "completed"), make_node(NODE_B_ID, "skipped", status_reason="Deferred.")]),
            "completed",
        )
        self.assertEqual(
            derive(
                "pending",
                [
                    make_node(NODE_A_ID, "skipped", status_reason="Deferred."),
                    make_node(NODE_B_ID, "skipped", status_reason="Deferred."),
                ],
            ),
            "skipped",
        )

    def test_derive_plan_status_blocks_only_when_nothing_is_startable(self) -> None:
        derive = manifest_tool.derive_plan_status

        stalled = [
            make_node(NODE_A_ID, "blocked", status_reason="Waiting on a decision."),
            make_node(NODE_B_ID, "pending", prerequisites=[NODE_A_ID]),
        ]
        self.assertEqual(derive("in_progress", stalled), "blocked")

        still_moving = [
            make_node(NODE_A_ID, "blocked", status_reason="Waiting on a decision."),
            make_node(NODE_B_ID, "pending"),
        ]
        self.assertEqual(derive("in_progress", still_moving), "in_progress")

        only_blocked = [make_node(NODE_A_ID, "blocked", status_reason="Waiting on a decision.")]
        self.assertEqual(derive("in_progress", only_blocked), "blocked")

    def test_pause_transition_edge_is_reversible(self) -> None:
        machine = manifest_tool.WORKFLOW_STATE_MACHINE

        self.assertTrue(machine.can_transition("in_progress", "pending"))
        self.assertTrue(machine.can_reach("in_progress", "pending"))
        self.assertFalse(machine.can_transition("completed", "pending"))
        self.assertFalse(machine.can_transition("blocked", "pending"))

    def test_evidence_refs_are_validated(self) -> None:
        node = make_node(NODE_A_ID, "pending")
        node["acceptance_criteria"][0]["evidence_refs"] = [  # type: ignore[index]
            {"type": "file", "path": "report.txt", "sha256": "zz", "recorded_at": "2026-07-11T00:00:00Z"},
            {"type": "command", "command": "pytest", "exit_code": 1, "recorded_at": "2026-07-11T00:00:00Z"},
            {"type": "unknown"},
            {"type": "file", "path": "ok.txt", "sha256": "a" * 64, "recorded_at": "2026-07-11T00:00:00Z", "extra": True},
        ]

        _, issues = manifest_tool.validate_checkpoints_data(Path("Checkpoints.json"), [node])

        messages = [issue.message for issue in issues]
        self.assertTrue(any("sha256: must be a 64-character lowercase hex digest" in message for message in messages), messages)
        self.assertTrue(any("exit_code: must be the integer 0" in message for message in messages), messages)
        self.assertTrue(any(".type: must be one of command, file" in message for message in messages), messages)
        self.assertTrue(any(".extra: unknown field" in message for message in messages), messages)

    def test_valid_evidence_refs_pass_validation(self) -> None:
        node = make_node(NODE_A_ID, "pending")
        node["acceptance_criteria"][0]["evidence_refs"] = [  # type: ignore[index]
            {"type": "file", "path": "report.txt", "sha256": "a" * 64, "recorded_at": "2026-07-11T00:00:00Z"},
            {"type": "command", "command": "pytest -q", "exit_code": 0, "recorded_at": "2026-07-11T00:00:00Z"},
        ]

        _, issues = manifest_tool.validate_checkpoints_data(Path("Checkpoints.json"), [node])

        self.assertFalse([issue.message for issue in issues if "evidence_refs" in issue.message])


if __name__ == "__main__":
    unittest.main()
