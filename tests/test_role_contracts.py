"""Tests for Better Plan role contracts.

These tests intentionally validate the acceptance contracts for role delegation
and bounded main obligations.
"""

from __future__ import annotations

import re
import unittest
from types import MappingProxyType

from scripts.better_plan.domain import roles as role_contracts


class RoleContractsTests(unittest.TestCase):
    """Contract tests for the canonical role contract module."""

    def test_four_delegating_actions_each_map_to_distinct_relative_reference(self) -> None:
        expected_map = {
            "dispatch_acceptance_designer": "references/acceptance-designer.md",
            "dispatch_acceptance_reviewer": "references/acceptance-reviewer.md",
            "dispatch_executor": "references/executor.md",
            "dispatch_auditor": "references/auditor.md",
        }

        resolved = {
            action: role_contracts.reference_for_action(action)
            for action in expected_map
        }

        self.assertEqual(set(resolved.keys()), set(expected_map.keys()))
        self.assertEqual(set(resolved.values()), set(expected_map.values()))
        self.assertEqual(len(set(resolved.values())), 4)

        for action, expected_reference in expected_map.items():
            self.assertEqual(resolved[action], expected_reference)
            self.assertFalse(expected_reference.startswith("/"))
            self.assertTrue(expected_reference.startswith("references/"))

    def test_non_delegating_action_returns_none(self) -> None:
        for action in [
            "run_regression",
            "main_acceptance_decision",
            "dispatch_unknown",
            "executor-exited",
            "none",
            "",
            "dispatch",
        ]:
            self.assertIsNone(role_contracts.reference_for_action(action))

    def test_main_acceptance_decision_routes_to_the_main_contract(self) -> None:
        action = "main_acceptance_decision"

        self.assertIn(action, role_contracts.MAIN_ACTIONS)
        self.assertIsNone(role_contracts.reference_for_action(action))
        obligation = role_contracts.bounded_main_obligation(
            "node-123",
            "acceptance_revision_required",
            action,
        )

        self.assertIn(action, obligation)
        self.assertIn(role_contracts.ORCHESTRATION_MAIN_REFERENCE, obligation)
        self.assertNotIn("references/acceptance-designer.md", obligation)

    def test_unknown_action_raises_value_error_without_echoed_input(self) -> None:
        for action in ("dispatch_future_unknown", "future_state_action"):
            with self.subTest(action=action):
                with self.assertRaises(ValueError) as error:
                    role_contracts.bounded_main_obligation(
                        "node-123",
                        "awaiting_executor",
                        action,
                    )

                self.assertNotIn(action, str(error.exception))
                self.assertIsNone(role_contracts.reference_for_action(action))

    def test_bounded_main_obligation_rejects_malicious_node_id_or_phase_inputs(self) -> None:
        action = "dispatch_auditor"
        safe_node_id = "node-123"
        safe_phase = "awaiting_executor"
        malicious_cases = [
            ("node_id", "/tmp/private"),
            ("node_id", "C:\\private\\x"),
            ("node_id", "//server/share"),
            ("phase", "phase-with-\n-newline"),
            ("phase", "phase-with-\r-newline"),
            ("phase", "phase-with-\x00-null"),
        ]

        for target_field, value in malicious_cases:
            with self.subTest(target_field=target_field, value=value):
                if target_field == "node_id":
                    args = (value, safe_phase, action)
                else:
                    args = (safe_node_id, value, action)

                with self.assertRaises(ValueError) as error:
                    role_contracts.bounded_main_obligation(*args)

                self.assertNotIn(value, str(error.exception))

    def test_bounded_main_obligation_contains_only_node_phase_action_and_one_reference(self) -> None:
        for action in role_contracts.ROLE_REFERENCES:
            obligation = role_contracts.bounded_main_obligation(
                "node-123",
                "awaiting_executor",
                action,
            )

            self.assertIn("node-123", obligation)
            self.assertIn("awaiting_executor", obligation)
            self.assertIn(action, obligation)
            self.assertEqual(obligation.count(action), 1)

            references = re.findall(r"references/[A-Za-z0-9._-]+\.md", obligation)
            self.assertEqual(len(references), 1)
            self.assertIn(references[0], role_contracts.ROLE_REFERENCES.values())

            lowered = obligation.lower()
            forbidden = [
                "prompt",
                "output",
                "runtime",
                "machine",
                "credential",
                "server",
                "absolute",
                "path",
                "/users/",
                "/home/",
                "http://",
                "https://",
            ]
            for token in forbidden:
                self.assertNotIn(token, lowered)

            self.assertNotIn("you are", lowered)
            self.assertNotIn("must produce", lowered)

    def test_role_references_is_immutable_mapping_proxy(self) -> None:
        self.assertIsInstance(role_contracts.ROLE_REFERENCES, MappingProxyType)
        with self.assertRaises(TypeError):
            role_contracts.ROLE_REFERENCES["dispatch_new"] = "references/new.md"

        with self.assertRaises(TypeError):
            del role_contracts.ROLE_REFERENCES["dispatch_executor"]


if __name__ == "__main__":
    unittest.main()
