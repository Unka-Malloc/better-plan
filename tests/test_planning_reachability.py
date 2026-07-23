"""Frozen acceptance surface for deferred work and workspace dependency reachability."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.better_plan.domain.validation import dependency_cycle_path
from tests.test_manifest_tool_cli import (
    PYTHON_TOOL,
    checkpoint_node,
    default_acceptance_design,
    write_design_artifacts,
)


PLAN_A_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
PLAN_B_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
NODE_A_ID = "11111111-1111-4111-8111-111111111111"
NODE_B_ID = "22222222-2222-4222-8222-222222222222"
NODE_C_ID = "33333333-3333-4333-8333-333333333333"


def run_cli(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    command, *values = arguments
    option_index = next(
        (index for index, value in enumerate(values) if value.startswith("-")),
        len(values),
    )
    positioned = [
        command,
        *values[:option_index],
        str(root),
        *values[option_index:],
    ]
    return subprocess.run(
        [sys.executable, str(PYTHON_TOOL), *positioned],
        cwd=PYTHON_TOOL.parents[1],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def plan_entry(
    plan_id: str,
    directory: str,
    status: str,
    *,
    title: str,
) -> dict[str, object]:
    return {
        "id": plan_id,
        "status": status,
        "title": title,
        "directory": directory,
        "source_files": [],
        "goal": f"Exercise {title} planning reachability.",
        "description": "Bounded planning-reachability acceptance fixture.",
        "checkpoints": f"{directory}/Checkpoints.json",
    }


def write_multi_plan_workspace(
    root: Path,
    plans: list[tuple[dict[str, object], list[dict[str, object]]]],
) -> None:
    manifest: list[dict[str, object]] = []
    (root / "tracked.txt").write_text("stable\n", encoding="utf-8")
    for plan, nodes in plans:
        manifest.append(plan)
        directory = root / str(plan["directory"])
        directory.mkdir(parents=True)
        for node in nodes:
            design = node.get("design")
            if isinstance(design, dict):
                write_design_artifacts(root, design)
        (directory / "Checkpoints.json").write_text(
            json.dumps(nodes),
            encoding="utf-8",
        )
    (root / "Manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def foundation_node(
    node_id: str,
    *,
    status: str = "pending",
    prerequisites: list[str] | None = None,
    reason: str | None = None,
) -> dict[str, object]:
    return checkpoint_node(
        node_id,
        status=status,
        role="validation_matrix",
        checked=False,
        prerequisites=prerequisites,
        status_reason=reason,
    )


class PlanningReachabilityAcceptanceTests(unittest.TestCase):
    def test_iterative_cycle_finder_returns_the_exact_closed_path(self) -> None:
        graph = {
            NODE_A_ID: (NODE_B_ID,),
            NODE_B_ID: (NODE_C_ID,),
            NODE_C_ID: (NODE_A_ID,),
        }

        self.assertEqual(
            dependency_cycle_path(graph),
            [NODE_A_ID, NODE_B_ID, NODE_C_ID, NODE_A_ID],
        )

        long_graph = {str(index): (str(index + 1),) for index in range(4096)}
        long_graph["4096"] = ("2048",)
        cycle = dependency_cycle_path(long_graph)
        self.assertIsNotNone(cycle)
        assert cycle is not None
        self.assertEqual(cycle[0], "2048")
        self.assertEqual(cycle[-1], "2048")

    def test_deferred_node_is_visible_not_executable_and_explicitly_activatable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            node = foundation_node(NODE_A_ID)
            write_multi_plan_workspace(
                root,
                [(plan_entry(PLAN_A_ID, "plan-a", "pending", title="Plan A"), [node])],
            )

            deferred = run_cli(root, "defer", NODE_A_ID, "--reason", "Resume after the next planning review.")
            self.assertEqual(deferred.returncode, 0, deferred.stderr)

            status = json.loads(run_cli(root, "status", "--json").stdout)["plans"][0]
            self.assertEqual(status["status"], "deferred")
            self.assertEqual(status["counts"]["deferred"], 1)
            self.assertEqual(status["deferred"][0]["id"], NODE_A_ID)
            self.assertEqual(
                status["deferred"][0]["status_reason"],
                "Resume after the next planning review.",
            )

            selection = json.loads(run_cli(root, "next", "--json").stdout)["plans"][0]
            self.assertEqual(selection["status"], "deferred")
            self.assertEqual(selection["eligible"], [])
            self.assertNotIn(NODE_A_ID, run_cli(root, "next").stdout)

            rejected_start = run_cli(root, "start", NODE_A_ID)
            self.assertNotEqual(rejected_start.returncode, 0)

            activated = run_cli(root, "activate", NODE_A_ID)
            self.assertEqual(activated.returncode, 0, activated.stderr)
            activated_node = json.loads(
                (root / "plan-a" / "Checkpoints.json").read_text(encoding="utf-8")
            )[0]
            self.assertEqual(activated_node["status"], "pending")
            self.assertNotIn("status_reason", activated_node)
            self.assertIn(NODE_A_ID, run_cli(root, "next").stdout)

            skipped = run_cli(root, "skip", NODE_A_ID, "--reason", "Capability waived from this delivery.")
            self.assertEqual(skipped.returncode, 0, skipped.stderr)
            rejected_activation = run_cli(root, "activate", NODE_A_ID)
            self.assertNotEqual(rejected_activation.returncode, 0)

    def test_deferred_implementation_blocks_final_validation_and_plan_completion(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            implementation = checkpoint_node(
                NODE_A_ID,
                status="deferred",
                checked=False,
                status_reason="Resume in the current delivery after review.",
            )
            implementation["design"] = default_acceptance_design("deferred-implementation")
            final = checkpoint_node(
                NODE_B_ID,
                status="pending",
                role="final_validation",
                checked=False,
            )
            final["design"] = default_acceptance_design("deferred-final")
            write_multi_plan_workspace(
                root,
                [
                    (
                        plan_entry(PLAN_A_ID, "plan-a", "deferred", title="Plan A"),
                        [implementation, final],
                    )
                ],
            )

            validation = run_cli(root, "validate", "--no-git")
            self.assertEqual(validation.returncode, 0, validation.stderr)

            dispatch = run_cli(
                root,
                "dispatch",
                NODE_B_ID,
                "--role",
                "acceptance_designer",
            )
            self.assertNotEqual(dispatch.returncode, 0)
            self.assertIn("non-skipped implementation", dispatch.stderr)

            synced = run_cli(root, "sync-plan")
            self.assertEqual(synced.returncode, 0, synced.stderr)
            manifest = json.loads((root / "Manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest[0]["status"], "deferred")

    def test_cross_plan_prerequisite_controls_validation_start_and_next(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            first = foundation_node(NODE_A_ID)
            dependent = foundation_node(NODE_B_ID, prerequisites=[NODE_A_ID])
            write_multi_plan_workspace(
                root,
                [
                    (plan_entry(PLAN_A_ID, "plan-a", "pending", title="Plan A"), [first]),
                    (plan_entry(PLAN_B_ID, "plan-b", "pending", title="Plan B"), [dependent]),
                ],
            )

            validation = run_cli(root, "validate", "--no-git")
            self.assertEqual(validation.returncode, 0, validation.stderr)
            selection = json.loads(run_cli(root, "next", "--json").stdout)["plans"]
            eligible = {
                plan["title"]: [entry["id"] for entry in plan["eligible"]]
                for plan in selection
            }
            self.assertEqual(eligible["Plan A"], [NODE_A_ID])
            self.assertEqual(eligible["Plan B"], [])

            rejected = run_cli(root, "start", NODE_B_ID)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("prerequisites", rejected.stderr)

            self.assertEqual(run_cli(root, "start", NODE_A_ID).returncode, 0)
            self.assertEqual(
                run_cli(root, "check", NODE_A_ID, "--criterion", "0").returncode,
                0,
            )
            self.assertEqual(run_cli(root, "complete", NODE_A_ID).returncode, 0)
            eligible_after = json.loads(run_cli(root, "next", "--json").stdout)["plans"]
            plan_b = next(plan for plan in eligible_after if plan["title"] == "Plan B")
            self.assertEqual([entry["id"] for entry in plan_b["eligible"]], [NODE_B_ID])

    def test_cross_plan_cycle_rewire_is_rejected_without_partial_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            first = foundation_node(NODE_A_ID)
            dependent = foundation_node(NODE_B_ID, prerequisites=[NODE_A_ID])
            write_multi_plan_workspace(
                root,
                [
                    (plan_entry(PLAN_A_ID, "plan-a", "pending", title="Plan A"), [first]),
                    (plan_entry(PLAN_B_ID, "plan-b", "pending", title="Plan B"), [dependent]),
                ],
            )
            before_manifest = (root / "Manifest.json").read_bytes()
            before_a = (root / "plan-a" / "Checkpoints.json").read_bytes()
            before_b = (root / "plan-b" / "Checkpoints.json").read_bytes()

            result = run_cli(root, "rewire", NODE_A_ID, "--add-prerequisite", NODE_B_ID)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                f"{NODE_A_ID} -> {NODE_B_ID} -> {NODE_A_ID}",
                result.stderr,
            )
            self.assertNotIn(str(root), result.stdout + result.stderr)
            self.assertEqual((root / "Manifest.json").read_bytes(), before_manifest)
            self.assertEqual((root / "plan-a" / "Checkpoints.json").read_bytes(), before_a)
            self.assertEqual((root / "plan-b" / "Checkpoints.json").read_bytes(), before_b)

    def test_public_contract_separates_defer_from_terminal_skip(self) -> None:
        repository = PYTHON_TOOL.parents[1]
        text = "\n".join(
            (repository / path).read_text(encoding="utf-8")
            for path in (
                "SKILL.md",
                "README.md",
                "references/orchestration-main.md",
                "references/state-files.md",
            )
        ).lower()

        self.assertIn("deferred", text)
        self.assertIn("activate", text)
        self.assertRegex(text, r"skipped.{0,100}(?:terminal|waiv|not applicable)")
        self.assertNotRegex(text, r"skip.{0,120}defer(?:red|ral)? to (?:a )?follow-up")
