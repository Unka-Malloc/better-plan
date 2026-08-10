"""Focused contracts for deterministic Design.md compilation."""

from __future__ import annotations

from copy import deepcopy
from unittest.mock import patch
import unittest

from scripts.better_plan.domain.design_compile import DESIGN_EXAMPLE as DESIGN_TEMPLATE, compile_design
from tests.v3_fixtures import complete_plan


SECOND_TASK = """

## Task: publish-result
Outcome: The compiled result is published through its independent boundary.
Scope in:
- The result publishing boundary.
Scope out:
- Unrelated delivery behavior.
Outputs:
- published-result: Published result — artifact: published/result.txt — guarantee: Consumers receive the verified result.
Owns:
- published
Exclusive:
Difficulty: standard
Verification: code
Risks:
- public_interface
Nodes:
- publish-result: Publish and verify the independent result.
Requirements:
- observable-behavior
Design:
approach:
- Publish the verified result inside this independently executable Task.
Acceptance:
- Given: A valid publishing state — When: Publishing runs — Then: The result is available — Oracle: The published artifact exists — Evidence: command: focused regression — Covers: observable-behavior, published-result
Regression:
Commands:
- python3 -m unittest tests.test_publish
Paths:
- published
"""

EXPECTED_SPEC = {
    "requirements": [{
        "code": "REQ-001",
        "statement": "The authorized behavior is observable and verified.",
        "source_refs": ["user-request"],
    }],
    "architecture": {
        "summary": "One bounded design whose Tasks form a single parallel frontier.",
        "notes": ["Keep dependent implementation steps inside the same Task."],
    },
    "tasks": [{
        "code": "TASK-001",
        "title": "bounded-delivery",
        "outcome": "The requested behavior passes its focused oracle.",
        "scope": {
            "in": ["The bounded capability and its focused verification."],
            "out": ["Unrelated capabilities."],
        },
        "prerequisites": [],
        "inputs": [],
        "outputs": [{
            "code": "OUT-001",
            "title": "Verified result",
            "artifact": "relative/path",
            "guarantee": "The delivery can rely on the verified behavior.",
        }],
        "ownership": {"write_paths": ["relative/path"], "shared_exclusive": []},
        "difficulty": "standard",
        "verification": "code",
        "requirements": ["REQ-001"],
        "risks": [],
        "nodes": [
            {
                "code": "NODE-001",
                "title": "inspect-contracts",
                "outcome": "Confirm the affected contracts and boundaries.",
                "prerequisites": [],
            },
            {
                "code": "NODE-002",
                "title": "implement-behavior",
                "outcome": "Implement the bounded behavior.",
                "prerequisites": ["NODE-001"],
            },
            {
                "code": "NODE-003",
                "title": "verify-behavior",
                "outcome": "Prepare focused verification.",
                "prerequisites": ["NODE-001"],
            },
            {
                "code": "NODE-004",
                "title": "integrate-result",
                "outcome": "Integrate implementation and verification.",
                "prerequisites": ["NODE-002", "NODE-003"],
            },
        ],
        "design": {"approach": ["Use the simplest implementation that satisfies the outcome."]},
        "acceptance": [{
            "code": "AC-001",
            "covers": ["REQ-001", "OUT-001"],
            "given": "A valid starting state",
            "when": "The behavior is exercised",
            "then": "The observable result occurs",
            "oracle": "The focused command exits zero",
            "evidence": {"type": "command", "source": "focused regression"},
        }],
        "focused_regression": {
            "commands": ["python3 -m unittest tests.test_module"],
            "paths": ["relative/path"],
        },
    }],
    "full_regression": {
        "commands": ["python3 -m unittest discover -s tests -p 'test_*.py'"],
        "paths": ["relative/path"],
    },
}


class DesignCompileTests(unittest.TestCase):
    def test_complete_draft_compiles_to_exact_v3_mechanics(self) -> None:
        result = compile_design(DESIGN_TEMPLATE, complete_plan()["spec"])

        self.assertEqual(result["issues"], [])
        self.assertEqual(result["unmapped"], [])
        self.assertEqual(result["spec"], EXPECTED_SPEC)

    def test_alias_defaults_risk_tier_and_parallel_fields_are_derived(self) -> None:
        aliased_task = SECOND_TASK.replace(
            "Owns:\n- published",
            "Write paths: published",
        ).replace(
            "Difficulty: standard",
            "Tier: standard",
        ).replace(
            "Requirements:\n- observable-behavior",
            "Requirements: observable-behavior",
        )
        draft = DESIGN_TEMPLATE.replace("## Full regression", aliased_task + "\n## Full regression")
        result = compile_design(draft, complete_plan()["spec"])

        self.assertEqual(result["issues"], [])
        first, second = result["spec"]["tasks"]
        self.assertEqual(second["difficulty"], "complex")
        self.assertEqual(first["prerequisites"], [])
        self.assertEqual(first["inputs"], [])
        self.assertEqual(second["prerequisites"], [])
        self.assertEqual(second["inputs"], [])

        defaults = DESIGN_TEMPLATE.replace("Scope out:\n- Unrelated capabilities.\n", "").replace(
            "Difficulty: standard\nVerification: code\nRisks:\n",
            "",
        )
        default_task = compile_design(defaults, complete_plan()["spec"])["spec"]["tasks"][0]
        self.assertEqual(default_task["scope"]["out"], [])
        self.assertEqual(default_task["risks"], [])
        self.assertEqual(default_task["difficulty"], "standard")
        self.assertEqual(default_task["verification"], "code")

    def test_representative_structure_residue_is_reported(self) -> None:
        duplicate_task = DESIGN_TEMPLATE.replace(
            "## Full regression",
            "## Task: bounded-delivery\nOutcome: Duplicate Task.\n\n## Full regression",
        )
        cross_task_dependency = DESIGN_TEMPLATE.replace(
            "Outputs:",
            "Depends on:\n- another-task\nOutputs:",
        )
        multiple_acceptance = DESIGN_TEMPLATE.replace(
            " — Covers: observable-behavior, verified-result",
            "",
        ).replace(
            "Regression:\nCommands:",
            "- Given: Another state — When: Another behavior runs — Then: Another result occurs — Oracle: Another command exits zero — Evidence: command: focused regression\nRegression:\nCommands:",
        )

        for draft, expected in (
            (duplicate_task, "duplicate Task name"),
            (cross_task_dependency, "cross-Task dependencies are not allowed"),
            (multiple_acceptance, "multiple Acceptance criteria require Covers"),
        ):
            with self.subTest(expected=expected):
                result = compile_design(draft, complete_plan()["spec"])
                self.assertTrue(any(expected in issue["message"] for issue in result["issues"]))

    def test_missing_semantics_are_not_replaced_with_compiler_prose(self) -> None:
        draft = DESIGN_TEMPLATE.replace(
            "Outcome: The requested behavior passes its focused oracle.",
            "Outcome:",
        ).replace(
            "- verified-result: Verified result — artifact: relative/path — guarantee: The delivery can rely on the verified behavior.\n",
            "",
        ).replace(
            "- Use the simplest implementation that satisfies the outcome.\n",
            "",
        )
        result = compile_design(draft, complete_plan()["spec"])
        task = result["spec"]["tasks"][0]

        self.assertEqual(task["outcome"], "")
        self.assertEqual(task["outputs"], [])
        self.assertEqual(task["design"], {})
        self.assertTrue(any("requires Outcome" in issue["message"] for issue in result["issues"]))
        self.assertTrue(any("requires Outputs" in issue["message"] for issue in result["issues"]))
        self.assertTrue(any("requires Design" in issue["message"] for issue in result["issues"]))

    def test_residue_exclusion_and_content_classification_are_fail_closed(self) -> None:
        draft = DESIGN_TEMPLATE.replace(
            "## Architecture",
            "## Unknown notes\nUnmapped prose.\n\n<!-- better-plan: exclude -->\n## Ignored notes\nAudited but excluded.\n\n## Architecture",
        ).replace("One bounded design", "Bearer abcdefghijklmnopqrstuvwxyz")
        result = compile_design(draft, complete_plan()["spec"])

        self.assertTrue(any(issue["kind"] == "unmapped" for issue in result["issues"]))
        self.assertTrue(any("unknown top-level section" in issue["message"] for issue in result["issues"]))
        self.assertTrue(any(issue["kind"] == "content" for issue in result["issues"]))
        self.assertEqual({item["status"] for item in result["unmapped"]}, {"open", "excluded"})
        self.assertTrue(all("Unmapped prose" not in str(item) for item in result["unmapped"]))

    def test_exclusion_applies_to_the_next_item_without_leaking_to_the_next_section(self) -> None:
        draft = DESIGN_TEMPLATE.replace(
            "Acceptance:\n",
            "<!-- better-plan: exclude -->\nDeliberately excluded compiler note.\nAcceptance:\n",
        )
        result = compile_design(draft, complete_plan()["spec"])

        self.assertEqual(result["issues"], [])
        self.assertEqual(len(result["unmapped"]), 1)
        self.assertEqual(result["unmapped"][0]["status"], "excluded")
        self.assertEqual(result["sections_from_plan"], [])
        self.assertEqual(
            result["spec"]["full_regression"]["commands"],
            ["python3 -m unittest discover -s tests -p 'test_*.py'"],
        )

    def test_every_error_identifies_its_design_line_and_canonical_field(self) -> None:
        draft = DESIGN_TEMPLATE.replace(
            "Outcome: The requested behavior passes its focused oracle.",
            "Outcome:",
        ).replace(
            "Risks:\n",
            "Risks:\n- unknown-risk\n",
        ).replace(
            "One bounded design",
            "Bearer abcdefghijklmnopqrstuvwxyz",
        )
        result = compile_design(draft, complete_plan()["spec"])

        self.assertTrue(result["issues"])
        for issue in result["issues"]:
            self.assertIs(type(issue["line"]), int)
            self.assertGreater(issue["line"], 0)
            self.assertTrue(issue["field"])
        self.assertTrue(any(
            issue["field"] == "spec.tasks[0].outcome"
            for issue in result["issues"]
        ))
        self.assertTrue(any(
            issue["field"] == "spec.architecture.summary" and issue["line"] > 1
            for issue in result["issues"]
        ))

        with patch(
            "scripts.better_plan.domain.design_compile._parse_output",
            side_effect=RuntimeError("internal failure"),
        ):
            fallback = compile_design(DESIGN_TEMPLATE, complete_plan()["spec"])
        self.assertGreater(fallback["issues"][0]["line"], 1)
        self.assertEqual(fallback["issues"][0]["field"], "spec.tasks[0].outputs[0]")
        self.assertIn("while processing spec.tasks[0].outputs[0]", fallback["issues"][0]["message"])

    def test_compilation_is_deterministic(self) -> None:
        fallback = deepcopy(complete_plan()["spec"])
        first = compile_design(DESIGN_TEMPLATE, fallback)
        second = compile_design(DESIGN_TEMPLATE, fallback)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
