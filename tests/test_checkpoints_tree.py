"""Canonical Checkpoints Tree: nested Tasks, executable Nodes, atomic authoring."""

from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

from scripts.better_plan.domain.checkpoints_tree import (
    apply_operations,
    new_tree,
    next_executor,
    node_index,
    readiness_report,
    ready_codes,
    reported_completions,
    shape_issues,
    shared_resource_groups,
    status_payload,
    transition,
    tried_executors,
    validate_tree,
)
from scripts.better_plan.domain.models import ToolError


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "scripts" / "manifest_tool.py"


def interpreter_command(source: str) -> str:
    """Build a declared command from this interpreter, never an ambient `python3`.

    The runner hands the command to the platform shell, so a bare `python3` would
    depend on whatever the machine happens to expose (Windows ships `python`).
    """

    return '"%s" -c "%s"' % (sys.executable, source)


def direct_batch() -> list[dict]:
    """One complete delivery: a designer opens it, a worker does it, a reviewer closes it."""

    return [
        {
            "op": "tree.update",
            "meta": {"owner": "designer", "notes": []},
        },
        {
            "op": "task.add",
            "id": "TASK-001",
            "title": "deliver",
            "outcome": "The delivery is visible in the Tree.",
        },
        {
            "op": "node.add",
            "task": "TASK-001",
            "id": "NODE-001",
            "title": "design",
            "outcome": "The approach is fixed.",
            "role": "designer",
        },
        {
            "op": "node.add",
            "task": "TASK-001",
            "id": "NODE-002",
            "title": "build",
            "outcome": "Build the result.",
            "role": "worker-1",
            "after": ["NODE-001"],
        },
        {
            "op": "node.add",
            "task": "TASK-001",
            "id": "NODE-003",
            "title": "review",
            "outcome": "The result is audited.",
            "role": "reviewer",
            "after": ["NODE-002"],
        },
    ]


def command_batch() -> list[dict]:
    """One Node the tool can check, one only a person can judge, inside a valid shape."""

    return [
        {
            "op": "task.add",
            "id": "TASK-001",
            "title": "deliver",
            "outcome": "The delivery is verified in the Tree.",
        },
        {
            "op": "node.add",
            "task": "TASK-001",
            "id": "NODE-001",
            "title": "design",
            "outcome": "The approach is fixed.",
            "role": "designer",
        },
        {
            "op": "node.add",
            "task": "TASK-001",
            "id": "NODE-002",
            "title": "check",
            "outcome": "The declared check passes.",
            "role": "worker-1",
            "after": ["NODE-001"],
            "contract": {"commands": [interpreter_command("print(1)")]},
        },
        {
            "op": "node.add",
            "task": "TASK-001",
            "id": "NODE-003",
            "title": "judge",
            "outcome": "A person judges the result.",
            "role": "worker-2",
            "after": ["NODE-001"],
        },
        {
            "op": "node.add",
            "task": "TASK-001",
            "id": "NODE-004",
            "title": "review",
            "outcome": "The result is audited.",
            "role": "reviewer",
            "after": ["NODE-002", "NODE-003"],
        },
    ]


class CanonicalTreeModelTests(unittest.TestCase):
    def test_new_tree_is_nested_and_versionless(self) -> None:
        tree = new_tree("TREE-001", "Canonical")
        self.assertEqual(tree["schema"], "better-plan.checkpoints-tree")
        self.assertEqual(tree["tasks"], [])
        self.assertEqual(tree["meta"], {})
        self.assertNotIn("nodes", tree)
        self.assertNotIn("status", tree)
        self.assertEqual(validate_tree(tree), [])

    def test_designer_writes_tasks_nodes_and_edges_directly(self) -> None:
        tree = new_tree("TREE-001", "Direct")
        receipt = apply_operations(tree, direct_batch(), actor="designer/any", batch_id="batch-1")

        self.assertTrue(receipt["applied"])
        self.assertEqual(validate_tree(tree), [])
        self.assertEqual([task["id"] for task in tree["tasks"]], ["TASK-001"])
        nodes = tree["tasks"][0]["nodes"]
        self.assertEqual([node["id"] for node in nodes], ["NODE-001", "NODE-002", "NODE-003"])
        self.assertEqual(nodes[1]["after"], ["NODE-001"])
        self.assertEqual(ready_codes(tree), ["NODE-001"])
        self.assertEqual(tree["meta"], {"owner": "designer", "notes": []})

        replay = apply_operations(
            tree,
            [{"op": "task.remove", "id": "TASK-001", "force": True}],
            batch_id="batch-1",
            base_revision=0,
        )
        self.assertTrue(replay["idempotent"])
        self.assertEqual([task["id"] for task in tree["tasks"]], ["TASK-001"])

        # A genuinely stale batch is still a conflict, named as one.
        with self.assertRaises(ToolError) as stale:
            apply_operations(
                tree,
                [{"op": "tree.update", "title": "stale"}],
                batch_id="batch-2",
                base_revision=0,
            )
        self.assertIn("base_revision mismatch", str(stale.exception))

    def test_invalid_batch_is_atomic(self) -> None:
        tree = new_tree("TREE-001", "Atomic")
        apply_operations(tree, direct_batch())
        before = json.dumps(tree, sort_keys=True)
        with self.assertRaises(ToolError):
            apply_operations(
                tree,
                [
                    {"op": "tree.update", "title": "renamed by a rejected batch"},
                    {
                        "op": "after.add",
                        "node": "NODE-001",
                        "after": "NODE-002",
                    },
                ],
            )
        # Neither the invalid operation nor the valid one before it was applied.
        self.assertEqual(json.dumps(tree, sort_keys=True), before)

    def test_dependency_defects_are_reported_by_name(self) -> None:
        tree = new_tree("TREE-001", "Dependencies")
        apply_operations(tree, direct_batch())

        with self.assertRaises(ToolError) as cyclic:
            apply_operations(
                tree, [{"op": "after.add", "node": "NODE-001", "after": "NODE-003"}]
            )
        self.assertIn("after cycle", str(cyclic.exception))

        with self.assertRaises(ToolError) as dangling:
            apply_operations(
                tree,
                [
                    {
                        "op": "node.add",
                        "task": "TASK-001",
                        "id": "NODE-009",
                        "title": "extra",
                        "outcome": "The extra result exists.",
                        "role": "worker-2",
                        "after": ["NODE-404"],
                    }
                ],
            )
        self.assertIn("NODE-404", str(dangling.exception))

    def test_the_privacy_guard_refuses_what_must_not_be_stored(self) -> None:
        tree = new_tree("TREE-001", "Privacy")
        apply_operations(tree, command_batch())
        before = json.dumps(tree, sort_keys=True)

        refusals = (
            ({"note": "unblocked with /Users/operator/private/deploy.key"}, "absolute local path"),
            ({"executor": "https://internal.example.com/api"}, "network endpoint"),
            ({"evidence": {"key": "sk-abcdefghijklmnopqrst"}}, "secret-shaped data"),
        )
        for fields, reason in refusals:
            with self.subTest(reason=reason):
                with self.assertRaises(ToolError) as raised:
                    transition(tree, "NODE-001", "block", **fields)
                self.assertIn(reason, str(raised.exception))

        with self.assertRaises(ToolError) as designed:
            apply_operations(
                tree,
                [
                    {
                        "op": "node.add",
                        "task": "TASK-001",
                        "id": "NODE-009",
                        "title": "open /etc/hosts",
                        "outcome": "The entry exists.",
                        "role": "worker-2",
                    }
                ],
            )
        self.assertIn("node.title", str(designed.exception))
        self.assertEqual(json.dumps(tree, sort_keys=True), before)

        transition(
            tree, "NODE-001", "block", note="waiting on the operator", executor="acct-7/model-a"
        )
        self.assertEqual(node_index(tree)["NODE-001"]["status"], "blocked")

    def test_dry_run_previews_without_writing(self) -> None:
        tree = new_tree("TREE-001", "Dry")
        receipt = apply_operations(tree, direct_batch(), dry_run=True)
        self.assertEqual(receipt["dry_run"], True)
        self.assertEqual(receipt["ready"], ["NODE-001"])
        self.assertEqual(tree["tasks"], [])
        self.assertEqual(tree["generation"], 0)

    def test_after_edges_control_ready_frontier(self) -> None:
        tree = new_tree("TREE-001", "Edges")
        apply_operations(tree, direct_batch())
        self.assertEqual(ready_codes(tree), ["NODE-001"])

        apply_operations(tree, [{"op": "after.remove", "node": "NODE-002", "after": "NODE-001"}])
        self.assertEqual(ready_codes(tree), ["NODE-001", "NODE-002"])

        apply_operations(tree, [{"op": "after.add", "node": "NODE-002", "after": "NODE-001"}])
        self.assertEqual(ready_codes(tree), ["NODE-001"])
        report = readiness_report(tree)
        self.assertEqual([item["id"] for item in report["ready"]], ["NODE-001"])
        self.assertEqual(report["waiting"][0]["blockers"], ["NODE-001"])

    def test_failure_keeps_independent_work_ready(self) -> None:
        tree = new_tree("TREE-001", "Failure")
        apply_operations(
            tree,
            [
                {"op": "task.add", "id": "TASK-001", "title": "task", "outcome": "o"},
                {
                    "op": "node.add",
                    "task": "TASK-001",
                    "id": "NODE-001",
                    "title": "design",
                    "outcome": "d",
                    "role": "designer",
                },
                {
                    "op": "node.add",
                    "task": "TASK-001",
                    "id": "NODE-002",
                    "title": "a",
                    "outcome": "a",
                    "role": "worker-1",
                    "after": ["NODE-001"],
                },
                {
                    "op": "node.add",
                    "task": "TASK-001",
                    "id": "NODE-003",
                    "title": "b",
                    "outcome": "b",
                    "role": "worker-2",
                    "after": ["NODE-001"],
                },
                {
                    "op": "node.add",
                    "task": "TASK-001",
                    "id": "NODE-004",
                    "title": "review",
                    "outcome": "r",
                    "role": "reviewer",
                    "after": ["NODE-002", "NODE-003"],
                },
            ],
        )
        transition(tree, "NODE-001", "start")
        transition(tree, "NODE-001", "complete", note="designed")
        transition(tree, "NODE-002", "start", executor="any")
        transition(tree, "NODE-002", "fail", note="boom")

        self.assertEqual(tree["tasks"][0]["nodes"][1]["status"], "failed")
        self.assertIn("NODE-003", ready_codes(tree))
        report = readiness_report(tree)
        self.assertEqual([item["id"] for item in report["ready"]], ["NODE-002", "NODE-003"])

    def test_reset_and_cancel_follow_downstream_nodes(self) -> None:
        tree = new_tree("TREE-001", "Downstream")
        apply_operations(tree, direct_batch())
        for code in ("NODE-001", "NODE-002", "NODE-003"):
            transition(tree, code, "start")
            transition(tree, code, "complete", evidence={"id": code})
        self.assertEqual(ready_codes(tree), [])

        transition(tree, "NODE-001", "reset")
        self.assertEqual(ready_codes(tree), ["NODE-001"])
        nodes = tree["tasks"][0]["nodes"]
        self.assertEqual([node["status"] for node in nodes], ["pending", "pending", "pending"])

        transition(tree, "NODE-001", "cancel")
        nodes = tree["tasks"][0]["nodes"]
        self.assertEqual(
            [node["status"] for node in nodes], ["cancelled", "cancelled", "cancelled"]
        )


    def test_strict_validation_rejects_unknown_structure(self) -> None:
        tree = new_tree("TREE-001", "Strict")
        tree["nodes"] = []
        issues = validate_tree(tree)
        self.assertTrue(any("unknown field" in issue for issue in issues), issues)

    def test_a_checked_node_refuses_evidence_its_author_reported(self) -> None:
        tree = new_tree("TREE-001", "Boundary")
        apply_operations(tree, command_batch())
        transition(tree, "NODE-001", "start")
        transition(tree, "NODE-001", "complete", note="designed")
        transition(tree, "NODE-002", "start")
        with self.assertRaises(ToolError) as raised:
            transition(tree, "NODE-002", "complete", evidence={"exit": 0})
        self.assertIn("tree-verify", str(raised.exception))
        self.assertEqual(node_index(tree)["NODE-002"]["status"], "running")

        transition(tree, "NODE-002", "complete", evidence={"verified": True}, origin="cli")
        self.assertEqual(node_index(tree)["NODE-002"]["status"], "completed")
        self.assertEqual(reported_completions(tree), ["NODE-001"])

    def test_a_judged_node_records_that_its_completion_was_reported(self) -> None:
        tree = new_tree("TREE-001", "Judgement")
        apply_operations(tree, command_batch())
        transition(tree, "NODE-001", "start")
        transition(tree, "NODE-001", "complete", note="designed")
        transition(tree, "NODE-003", "start")
        transition(tree, "NODE-003", "complete", note="reviewed")
        self.assertEqual(node_index(tree)["NODE-003"]["status"], "completed")
        self.assertEqual(reported_completions(tree), ["NODE-001", "NODE-003"])

    def test_only_a_node_may_declare_executable_commands(self) -> None:
        tree = new_tree("TREE-001", "Placement")
        with self.assertRaises(ToolError):
            apply_operations(
                tree,
                [
                    {
                        "op": "task.add",
                        "id": "TASK-001",
                        "title": "deliver",
                        "outcome": "The result is delivered.",
                        "contract": {"commands": ["echo no"]},
                    },
                    {
                        "op": "node.add",
                        "task": "TASK-001",
                        "id": "NODE-001",
                        "title": "build",
                        "outcome": "The result builds.",
                        "role": "worker",
                    },
                ],
            )

    def test_every_node_must_name_the_role_that_executes_it(self) -> None:
        tree = new_tree("TREE-001", "Roles")
        with self.assertRaises(ToolError) as raised:
            apply_operations(
                tree,
                [
                    {"op": "task.add", "id": "TASK-001", "title": "t", "outcome": "o"},
                    {"op": "node.add", "task": "TASK-001", "id": "NODE-001", "title": "a", "outcome": "a"},
                ],
            )
        self.assertIn("needs a role", str(raised.exception))

        for role, executors in (("intern", None), ("worker-alpha", None), ("worker", ["same/x", "same/x"])):
            with self.subTest(role=role, executors=executors):
                with self.assertRaises(ToolError):
                    apply_operations(
                        tree,
                        [
                            {"op": "task.add", "id": "TASK-001", "title": "t", "outcome": "o"},
                            {
                                "op": "node.add",
                                "task": "TASK-001",
                                "id": "NODE-001",
                                "title": "a",
                                "outcome": "a",
                                "role": role,
                                "executors": executors,
                            },
                        ],
                    )
        self.assertEqual(tree["tasks"], [])


    def test_a_half_built_tree_is_writable_but_not_runnable(self) -> None:
        tree = new_tree("TREE-001", "Growing")
        apply_operations(
            tree,
            [
                {"op": "task.add", "id": "TASK-001", "title": "t", "outcome": "o"},
                {
                    "op": "node.add",
                    "task": "TASK-001",
                    "id": "NODE-001",
                    "title": "design",
                    "outcome": "d",
                    "role": "designer",
                },
            ],
        )
        self.assertEqual(validate_tree(tree), [])
        self.assertEqual(shape_issues(tree), ["needs exactly one reviewer Node, found 0"])
        with self.assertRaises(ToolError) as raised:
            transition(tree, "NODE-001", "start")
        self.assertIn("not runnable yet", str(raised.exception))

        apply_operations(
            tree,
            [
                {
                    "op": "node.add",
                    "task": "TASK-001",
                    "id": "NODE-002",
                    "title": "review",
                    "outcome": "r",
                    "role": "reviewer",
                    "after": ["NODE-001"],
                }
            ],
        )
        self.assertEqual(shape_issues(tree), [])
        self.assertEqual(
            status_payload(tree)["role_nodes"],
            {"designer": ["NODE-001"], "reviewer": ["NODE-002"]},
        )
        transition(tree, "NODE-001", "start")
        self.assertEqual(node_index(tree)["NODE-001"]["status"], "running")



    def test_a_spent_executor_hands_over_to_the_next_candidate(self) -> None:
        tree = new_tree("TREE-001", "Fallback")
        apply_operations(tree, command_batch())
        apply_operations(
            tree,
            [
                {
                    "op": "node.update",
                    "id": "NODE-003",
                    "set": {"executors": ["provider-a/model-x", "provider-b/model-x", "provider-c/model-y"]},
                }
            ],
        )
        transition(tree, "NODE-001", "start")
        transition(tree, "NODE-001", "complete", note="designed")

        transition(tree, "NODE-003", "start", executor="provider-a/model-x")
        first = transition(tree, "NODE-003", "fail", note="no quota")
        self.assertEqual(first["next_executor"], "provider-b/model-x")

        transition(tree, "NODE-003", "start", executor="provider-b/model-x")
        second = transition(tree, "NODE-003", "fail", note="no quota")
        self.assertEqual(second["next_executor"], "provider-c/model-y")

        transition(tree, "NODE-003", "start", executor="provider-c/model-y")
        third = transition(tree, "NODE-003", "fail", note="no quota")
        self.assertIsNone(third["next_executor"])

        # Adding another place to run does not redefine the work; replacing the chain does.
        apply_operations(
            tree,
            [
                {
                    "op": "node.update",
                    "id": "NODE-003",
                    "set": {
                        "executors": [
                            "provider-a/model-x",
                            "provider-b/model-x",
                            "provider-c/model-y",
                            "provider-d/model-z",
                        ]
                    },
                }
            ],
        )
        self.assertEqual(next_executor(tree, node_index(tree)["NODE-003"]), "provider-d/model-z")
        with self.assertRaises(ToolError):
            apply_operations(
                tree,
                [{"op": "node.update", "id": "NODE-003", "set": {"executors": ["other/model"]}}],
            )
        self.assertEqual(
            third["tried_executors"],
            ["provider-a/model-x", "provider-b/model-x", "provider-c/model-y"],
        )

    def test_appending_a_fallback_needs_no_reset_while_replacing_the_chain_does(self) -> None:
        tree = new_tree("TREE-001", "Append")
        apply_operations(tree, command_batch())
        apply_operations(
            tree,
            [{"op": "node.update", "id": "NODE-003", "set": {"executors": ["provider-a/model-x"]}}],
        )
        transition(tree, "NODE-001", "start")
        transition(tree, "NODE-001", "complete", note="designed")
        transition(tree, "NODE-003", "start", executor="provider-a/model-x")

        apply_operations(
            tree,
            [
                {
                    "op": "node.update",
                    "id": "NODE-003",
                    "set": {"executors": ["provider-a/model-x", "provider-b/model-x"]},
                }
            ],
        )
        self.assertEqual(node_index(tree)["NODE-003"]["status"], "running")
        self.assertEqual(next_executor(tree, node_index(tree)["NODE-003"]), "provider-b/model-x")

        with self.assertRaises(ToolError):
            apply_operations(
                tree,
                [{"op": "node.update", "id": "NODE-003", "set": {"executors": ["other/model"]}}],
            )

    def test_pinning_a_chain_a_node_never_declared_needs_a_reset(self) -> None:
        tree = new_tree("TREE-001", "Pin")
        apply_operations(tree, command_batch())
        transition(tree, "NODE-001", "start")
        transition(tree, "NODE-001", "complete", note="designed")
        transition(tree, "NODE-003", "start", executor="any/agent")

        # An empty chain means "any executor", so naming one is a replacement.
        with self.assertRaises(ToolError) as raised:
            apply_operations(
                tree,
                [
                    {
                        "op": "node.update",
                        "id": "NODE-003",
                        "set": {"executors": ["provider-a/model-x"]},
                    }
                ],
            )
        self.assertIn("reset", str(raised.exception))
        self.assertEqual(node_index(tree)["NODE-003"]["status"], "running")

    def test_changing_a_role_on_a_started_node_requires_a_reset(self) -> None:
        tree = new_tree("TREE-001", "Roles")
        apply_operations(tree, direct_batch())
        transition(tree, "NODE-001", "start")
        transition(tree, "NODE-001", "complete", note="designed")
        transition(tree, "NODE-002", "start", executor="any/agent")

        with self.assertRaises(ToolError) as raised:
            apply_operations(
                tree, [{"op": "node.update", "id": "NODE-002", "set": {"role": "worker-4"}}]
            )
        self.assertIn("reset", str(raised.exception))
        self.assertEqual(node_index(tree)["NODE-002"]["role"], "worker-1")

        apply_operations(
            tree,
            [{"op": "node.update", "id": "NODE-002", "set": {"role": "worker-4"}, "reset": True}],
        )
        self.assertEqual(node_index(tree)["NODE-002"]["role"], "worker-4")
        self.assertEqual(node_index(tree)["NODE-002"]["status"], "pending")
        # Redefining a Node resets everything that waits on it.
        self.assertEqual(node_index(tree)["NODE-003"]["status"], "pending")

    def test_a_shared_resource_without_an_order_is_reported_not_refused(self) -> None:
        tree = new_tree("TREE-001", "Contention")
        apply_operations(
            tree,
            [
                {
                    "op": "task.add",
                    "id": "T1",
                    "title": "t",
                    "outcome": "o",
                    "nodes": [
                        {
                            "id": "D",
                            "title": "d",
                            "outcome": "o",
                            "role": "designer",
                        },
                        {
                            "id": "W1",
                            "title": "w1",
                            "outcome": "o",
                            "role": "worker",
                            "after": ["D"],
                            "resources": ["build/", "crates/"],
                        },
                        {
                            "id": "W2",
                            "title": "w2",
                            "outcome": "o",
                            "role": "worker",
                            "after": ["D"],
                            "resources": ["build/"],
                        },
                        {
                            "id": "R",
                            "title": "r",
                            "outcome": "o",
                            "role": "reviewer",
                            "after": ["W1", "W2"],
                        },
                    ],
                }
            ],
        )

        groups = shared_resource_groups(tree)
        self.assertEqual([group["resource"] for group in groups], ["build/"])
        self.assertEqual(groups[0]["unordered"], [["W1", "W2"]])
        # Contention is a design report, never a data error.
        self.assertEqual(validate_tree(tree), [])
        # Ordering the two Nodes resolves it.
        apply_operations(tree, [{"op": "after.add", "node": "W2", "after": "W1"}])
        self.assertEqual(shared_resource_groups(tree), [])

    def test_nested_authoring_writes_a_whole_task_in_one_operation(self) -> None:
        tree = new_tree("TREE-001", "Nested")
        receipt = apply_operations(
            tree,
            [
                {
                    "op": "task.add",
                    "id": "T1",
                    "title": "deliver",
                    "outcome": "The delivery is visible.",
                    "nodes": [
                        {
                            "id": "N1",
                            "title": "design",
                            "outcome": "The approach is fixed.",
                            "role": "designer",
                        },
                        {
                            "id": "N2",
                            "title": "work",
                            "outcome": "The work is done.",
                            "role": "worker-2",
                            "after": ["N1"],
                            "contract": {"commands": ["true"]},
                        },
                        {
                            "id": "N3",
                            "title": "review",
                            "outcome": "The delivery is audited.",
                            "role": "reviewer",
                            "after": ["N2"],
                        },
                    ],
                }
            ],
        )

        self.assertEqual(receipt["operations"], 1)
        self.assertEqual(validate_tree(tree), [])
        self.assertEqual(shape_issues(tree), [])
        self.assertEqual([node["id"] for node in tree["tasks"][0]["nodes"]], ["N1", "N2", "N3"])
        self.assertEqual(node_index(tree)["N2"]["after"], ["N1"])

        with self.assertRaises(ToolError) as repeated:
            apply_operations(
                tree,
                [
                    {
                        "op": "task.add",
                        "id": "T2",
                        "title": "t",
                        "outcome": "o",
                        "nodes": [
                            {"id": "N9", "title": "x", "outcome": "o", "role": "worker", "task": "T1"}
                        ],
                    }
                ],
            )
        self.assertIn("must not repeat the task", str(repeated.exception))

    def test_the_shape_gate_names_every_missing_piece(self) -> None:
        empty = new_tree("TREE-002", "Empty")
        issues = shape_issues(empty)
        self.assertIn("needs exactly one designer Node, found 0", issues)
        self.assertIn("needs exactly one reviewer Node, found 0", issues)

        tree = new_tree("TREE-001", "Shape")
        apply_operations(
            tree,
            [
                {"op": "task.add", "id": "T1", "title": "t", "outcome": "o"},
                {
                    "op": "node.add",
                    "task": "T1",
                    "id": "A",
                    "title": "a",
                    "outcome": "o",
                    "role": "designer",
                },
                {
                    "op": "node.add",
                    "task": "T1",
                    "id": "B",
                    "title": "b",
                    "outcome": "o",
                    "role": "designer",
                    "after": ["A"],
                },
                {
                    "op": "node.add",
                    "task": "T1",
                    "id": "C",
                    "title": "c",
                    "outcome": "o",
                    "role": "reviewer",
                    "after": ["B"],
                },
                {
                    "op": "node.add",
                    "task": "T1",
                    "id": "D",
                    "title": "d",
                    "outcome": "o",
                    "role": "worker",
                    "after": ["C"],
                },
            ],
        )
        issues = shape_issues(tree)
        self.assertIn("needs exactly one designer Node, found 2", issues)
        self.assertTrue(any("must open the tree" in issue for issue in issues), issues)
        self.assertTrue(any("must close the tree" in issue for issue in issues), issues)

        with self.assertRaises(ToolError) as raised:
            transition(tree, "A", "start")
        self.assertIn("not runnable yet", str(raised.exception))


class CanonicalTreeCliTests(unittest.TestCase):
    def run_cli(self, *arguments: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(TOOL), *arguments],
            cwd=str(ROOT),
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_direct_tree_round_trip_without_design_or_host(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            created = self.run_cli("tree-init", str(root), "--id", "TREE-900", "--title", "Smoke")
            self.assertEqual(created.returncode, 0, created.stderr)
            self.assertTrue((root / "Tree.json").is_file())
            self.assertFalse((root / "Plan.json").exists())

            batch = {
                "batch_id": "designer-cli",
                "actor": "designer/any",
                "operations": direct_batch(),
            }
            batch_path = root / "batch.json"
            batch_path.write_text(json.dumps(batch), encoding="utf-8")

            dry = self.run_cli("tree-apply", str(root), "--input", str(batch_path), "--dry-run", "--json")
            self.assertEqual(dry.returncode, 0, dry.stderr)
            self.assertTrue(json.loads(dry.stdout)["dry_run"])
            self.assertEqual(
                json.loads((root / "Tree.json").read_text(encoding="utf-8"))["generation"], 0
            )

            applied = self.run_cli("tree-apply", str(root), "--input", str(batch_path), "--json")
            self.assertEqual(applied.returncode, 0, applied.stderr)

            tree = json.loads((root / "Tree.json").read_text(encoding="utf-8"))
            self.assertEqual(validate_tree(tree), [])
            self.assertEqual(tree["tasks"][0]["nodes"][0]["id"], "NODE-001")

            next_nodes = self.run_cli("tree-next", str(root), "--explain", "--json")
            self.assertEqual(next_nodes.returncode, 0, next_nodes.stderr)
            payload = json.loads(next_nodes.stdout)
            self.assertEqual([item["id"] for item in payload["ready"]], ["NODE-001"])
            self.assertEqual(payload["explain"]["waiting"][0]["blockers"], ["NODE-001"])

            started = self.run_cli("tree-transition", str(root), "NODE-001", "start", "--executor", "any/agent")
            self.assertEqual(started.returncode, 0, started.stderr)
            completed = self.run_cli(
                "tree-transition",
                str(root),
                "NODE-001",
                "complete",
                "--evidence",
                '{"exit":0}',
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)

            valid = self.run_cli("tree-validate", str(root), "--json")
            self.assertEqual(
                json.loads(valid.stdout),
                {
                    "valid": True,
                    "issues": [],
                    "runnable": True,
                    "shape_issues": [],
                    "contention": [],
                },
            )

            exported = self.run_cli("tree", str(root), "--json")
            self.assertEqual(exported.returncode, 0, exported.stderr)
            export = json.loads(exported.stdout)
            self.assertEqual(export["tree"]["tasks"][0]["id"], "TASK-001")
            self.assertEqual(export["derived"]["task_status"], {"TASK-001": "running"})
            self.assertEqual(export["derived"]["contention"], [])

    def test_tree_verify_runs_declared_commands_and_records_both_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.run_cli("tree-init", str(root), "--id", "TREE-901", "--title", "Verify")
            batch = {
                "operations": [
                    {
                        "op": "task.add",
                        "id": "TASK-001",
                        "title": "deliver",
                        "outcome": "Every check is recorded in the Tree.",
                    },
                    {
                        "op": "node.add",
                        "task": "TASK-001",
                        "id": "NODE-001",
                        "title": "design",
                        "outcome": "The approach is fixed.",
                        "role": "designer",
                    },
                    {
                        "op": "node.add",
                        "task": "TASK-001",
                        "id": "NODE-002",
                        "title": "passes",
                        "outcome": "The passing check is recorded.",
                        "role": "worker-1",
                        "after": ["NODE-001"],
                        "contract": {"commands": [interpreter_command("raise SystemExit(0)")]},
                    },
                    {
                        "op": "node.add",
                        "task": "TASK-001",
                        "id": "NODE-003",
                        "title": "fails",
                        "outcome": "The failing check is recorded.",
                        "role": "worker-2",
                        "after": ["NODE-001"],
                        "contract": {"commands": [interpreter_command("raise SystemExit(3)")]},
                    },
                    {
                        "op": "node.add",
                        "task": "TASK-001",
                        "id": "NODE-004",
                        "title": "review",
                        "outcome": "The result is audited.",
                        "role": "reviewer",
                        "after": ["NODE-002", "NODE-003"],
                    },
                ]
            }
            batch_path = root / "batch.json"
            batch_path.write_text(json.dumps(batch), encoding="utf-8")
            applied = self.run_cli("tree-apply", str(root), "--input", str(batch_path))
            self.assertEqual(applied.returncode, 0, applied.stderr)

            self.run_cli("tree-transition", str(root), "NODE-001", "start")
            self.run_cli("tree-transition", str(root), "NODE-001", "complete", "--note", "designed")
            for node in ("NODE-002", "NODE-003"):
                started = self.run_cli("tree-transition", str(root), node, "start")
                self.assertEqual(started.returncode, 0, started.stderr)

            refused = self.run_cli(
                "tree-transition", str(root), "NODE-002", "complete", "--evidence", '{"exit":0}'
            )
            self.assertEqual(refused.returncode, 1)
            self.assertIn("tree-verify", refused.stderr)

            passed = self.run_cli("tree-verify", str(root), "NODE-002", "--json")
            self.assertEqual(passed.returncode, 0, passed.stderr)
            verified = json.loads(passed.stdout)
            self.assertTrue(verified["verified"])
            self.assertEqual(verified["status"], "completed")
            self.assertEqual(verified["commands"][0]["outcome"], "passed")

            failed = self.run_cli("tree-verify", str(root), "NODE-003", "--json")
            self.assertEqual(failed.returncode, 1)
            rejected = json.loads(failed.stdout)
            self.assertFalse(rejected["verified"])
            self.assertEqual(rejected["status"], "failed")
            self.assertEqual(rejected["commands"][0]["exit_code"], 3)

            tree = json.loads((root / "Tree.json").read_text(encoding="utf-8"))
            stored = {node["id"]: node for node in tree["tasks"][0]["nodes"]}
            statuses = {node["id"]: node["status"] for node in tree["tasks"][0]["nodes"]}
            self.assertEqual(
                statuses,
                {
                    "NODE-001": "completed",
                    "NODE-002": "completed",
                    "NODE-003": "failed",
                    "NODE-004": "pending",
                },
            )
            completions = [entry for entry in tree["history"] if entry.get("action") == "complete"]
            self.assertEqual([entry["source"] for entry in completions], ["reported", "cli"])

            # Stored evidence is the record a Reviewer reads: it must not claim a
            # failed verification passed.
            self.assertTrue(stored["NODE-002"]["evidence"][0]["verified"])
            self.assertEqual(stored["NODE-002"]["evidence"][0]["commands"][0]["outcome"], "passed")
            self.assertFalse(stored["NODE-003"]["evidence"][0]["verified"])
            self.assertEqual(stored["NODE-003"]["evidence"][0]["commands"][0]["outcome"], "failed")

    def test_tree_status_shows_the_role_map_and_reported_completions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.run_cli("tree-init", str(root), "--title", "Status")
            batch = root / "batch.json"
            batch.write_text(json.dumps({"operations": direct_batch()}), encoding="utf-8")
            applied = self.run_cli("tree-apply", str(root), "--input", str(batch))
            self.assertEqual(applied.returncode, 0, applied.stderr)
            judged = self.run_cli(
                "tree-transition", str(root), "NODE-001", "complete", "--note", "designed"
            )
            self.assertEqual(judged.returncode, 0, judged.stderr)

            text = self.run_cli("tree-status", str(root))
            self.assertEqual(text.returncode, 0, text.stderr)
            self.assertIn("designer: NODE-001", text.stdout)
            self.assertIn("worker-1: NODE-002", text.stdout)
            self.assertIn("reviewer: NODE-003", text.stdout)
            self.assertIn("reported (not tool-verified) completions: NODE-001", text.stdout)

            payload = json.loads(self.run_cli("tree-status", str(root), "--json").stdout)
            self.assertEqual(payload["role_nodes"]["worker-1"], ["NODE-002"])
            self.assertEqual(payload["reported_completions"], ["NODE-001"])

    def test_a_command_never_creates_a_workspace_it_cannot_find(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "typo"
            refused = self.run_cli("tree-status", str(missing))
            self.assertEqual(refused.returncode, 1)
            self.assertIn("no Checkpoints Tree", refused.stderr)
            self.assertFalse(missing.exists())

            # An existing directory that holds no Tree is refused just as cleanly.
            empty = Path(temporary) / "empty"
            empty.mkdir()
            batch = Path(temporary) / "batch.json"
            batch.write_text(
                json.dumps({"operations": [{"op": "tree.update", "title": "x"}]}),
                encoding="utf-8",
            )
            refused = self.run_cli("tree-apply", str(empty), "--input", str(batch))
            self.assertEqual(refused.returncode, 1)
            self.assertIn("no Checkpoints Tree", refused.stderr)
            self.assertEqual(list(empty.iterdir()), [])

    def test_a_dry_run_changes_nothing_but_the_workspace_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "workspace"
            created = self.run_cli("tree-init", str(root), "--title", "Dry")
            self.assertEqual(created.returncode, 0, created.stderr)
            batch = Path(temporary) / "batch.json"
            batch.write_text(json.dumps({"operations": direct_batch()}), encoding="utf-8")
            before = (root / "Tree.json").read_bytes()

            dry = self.run_cli("tree-apply", str(root), "--input", str(batch), "--dry-run")

            self.assertEqual(dry.returncode, 0, dry.stderr)
            self.assertEqual((root / "Tree.json").read_bytes(), before)
            self.assertEqual(
                sorted(item.name for item in root.iterdir()),
                [".better-plan.lock", "Tree.json"],
            )

    def test_a_replacement_carries_identity_and_history_forward(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            created = self.run_cli("tree-init", str(root), "--id", "TREE-910", "--title", "First")
            self.assertEqual(created.returncode, 0, created.stderr)
            batch = root / "batch.json"
            batch.write_text(
                json.dumps({"batch_id": "first-design", "operations": direct_batch()}),
                encoding="utf-8",
            )
            self.run_cli("tree-apply", str(root), "--input", str(batch))
            before = json.loads((root / "Tree.json").read_text(encoding="utf-8"))
            self.assertEqual(before["generation"], 1)

            unaudited = self.run_cli("tree-init", str(root), "--replace")
            self.assertEqual(unaudited.returncode, 1)
            self.assertIn("--reason", unaudited.stderr)

            replaced = self.run_cli(
                "tree-init", str(root), "--replace", "--reason", "task and node names diverged"
            )
            self.assertEqual(replaced.returncode, 0, replaced.stderr)

            tree = json.loads((root / "Tree.json").read_text(encoding="utf-8"))
            self.assertEqual(tree["id"], "TREE-910")
            self.assertEqual(tree["title"], "First")
            self.assertEqual(tree["generation"], before["generation"] + 1)
            self.assertEqual(tree["tasks"], [])
            self.assertGreaterEqual(len(tree["history"]), len(before["history"]) + 1)
            replace_entry = tree["history"][-1]
            self.assertEqual(replace_entry["action"], "replace")
            self.assertEqual(replace_entry["note"], "task and node names diverged")
            self.assertEqual(replace_entry["replaced"]["nodes"], 3)
            self.assertEqual(len(replace_entry["replaced"]["sha256"]), 64)

            # The replayed batch belongs to the previous graph, and stays recorded.
            replay = self.run_cli("tree-apply", str(root), "--input", str(batch))
            self.assertEqual(replay.returncode, 0, replay.stderr)
            self.assertIn("already applied", replay.stdout)

    def test_tree_verify_does_not_hold_the_lock_and_refuses_a_tree_that_moved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.run_cli("tree-init", str(root), "--id", "TREE-902", "--title", "Moving")
            moved = '"%s" "%s" tree-transition "%s" NODE-003 block --note "moved mid-verify"' % (
                sys.executable,
                TOOL,
                root,
            )
            batch = {
                "operations": [
                    {
                        "op": "task.add",
                        "id": "TASK-001",
                        "title": "deliver",
                        "outcome": "A moved Tree is never completed.",
                    },
                    {
                        "op": "node.add",
                        "task": "TASK-001",
                        "id": "NODE-001",
                        "title": "design",
                        "outcome": "The approach is fixed.",
                        "role": "designer",
                    },
                    {
                        "op": "node.add",
                        "task": "TASK-001",
                        "id": "NODE-002",
                        "title": "slow check",
                        "outcome": "The slow check passes.",
                        "role": "worker-1",
                        "after": ["NODE-001"],
                        "contract": {"commands": [moved]},
                    },
                    {
                        "op": "node.add",
                        "task": "TASK-001",
                        "id": "NODE-003",
                        "title": "review",
                        "outcome": "The result is audited.",
                        "role": "reviewer",
                        "after": ["NODE-002"],
                    },
                ]
            }
            batch_path = root / "batch.json"
            batch_path.write_text(json.dumps(batch), encoding="utf-8")
            applied = self.run_cli("tree-apply", str(root), "--input", str(batch_path))
            self.assertEqual(applied.returncode, 0, applied.stderr)
            self.run_cli("tree-transition", str(root), "NODE-001", "complete", "--note", "designed")

            refused = self.run_cli("tree-verify", str(root), "NODE-002")

            self.assertEqual(refused.returncode, 1)
            self.assertIn("the Tree changed while verification ran", refused.stderr)
            tree = json.loads((root / "Tree.json").read_text(encoding="utf-8"))
            nodes = {node["id"]: node["status"] for node in tree["tasks"][0]["nodes"]}
            # The declared command really did reach the workspace while verify ran.
            self.assertEqual(nodes["NODE-003"], "blocked")
            self.assertEqual(nodes["NODE-002"], "running")


if __name__ == "__main__":
    unittest.main()
