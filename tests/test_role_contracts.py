"""Contract tests for Better Plan role-to-action resolution."""

from __future__ import annotations

import re
import unittest
from types import MappingProxyType

from scripts.better_plan.domain import roles


class RoleContractsTests(unittest.TestCase):
    def test_four_leaf_actions_have_distinct_current_references(self) -> None:
        expected = {
            "dispatch_designer": "references/designer.md",
            "dispatch_worker": "references/worker.md",
            "dispatch_verifier": "references/verifier.md",
            "dispatch_reviewer": "references/reviewer.md",
        }
        self.assertEqual(dict(roles.ROLE_REFERENCES), expected)
        self.assertEqual(
            {roles.reference_for_action(action) for action in expected},
            set(expected.values()),
        )

    def test_native_main_actions_never_resolve_to_a_leaf_reference(self) -> None:
        for action in roles.MAIN_ACTIONS:
            with self.subTest(action=action):
                self.assertIsNone(roles.reference_for_action(action))
                obligation = roles.bounded_main_obligation(
                    "node-123",
                    "reviewer_complete",
                    action,
                )
                self.assertIn(roles.ORCHESTRATION_MAIN_REFERENCE, obligation)

    def test_only_designer_requires_the_local_pattern_catalog(self) -> None:
        self.assertEqual(
            dict(roles.ROLE_KNOWLEDGE_REFERENCES),
            {"dispatch_designer": ("references/design-patterns.md",)},
        )
        self.assertEqual(
            roles.knowledge_references_for_action("dispatch_designer"),
            ("references/design-patterns.md",),
        )
        for action in (
            "dispatch_worker",
            "dispatch_verifier",
            "dispatch_reviewer",
            *roles.MAIN_ACTIONS,
        ):
            with self.subTest(action=action):
                self.assertEqual(roles.knowledge_references_for_action(action), ())

    def test_obligation_is_bounded_and_contains_exactly_one_reference(self) -> None:
        for action, reference in roles.ROLE_REFERENCES.items():
            obligation = roles.bounded_main_obligation(
                "node-123",
                "awaiting_worker",
                action,
            )
            self.assertEqual(
                re.findall(r"references/[A-Za-z0-9._-]+\.md", obligation),
                [reference],
            )
            self.assertNotIn("prompt", obligation.lower())
            self.assertNotIn("/users/", obligation.lower())

    def test_unknown_or_unsafe_values_fail_without_echo(self) -> None:
        for action in ("dispatch_unknown", "future-action"):
            with self.assertRaises(ValueError) as error:
                roles.bounded_main_obligation("node-123", "awaiting_worker", action)
            self.assertNotIn(action, str(error.exception))
        for value in ("/tmp/private", "phase\nnewline", "phase\x00null"):
            with self.assertRaises(ValueError) as error:
                roles.bounded_main_obligation(value, "awaiting_worker", "dispatch_worker")
            self.assertNotIn(value, str(error.exception))

    def test_reference_map_is_immutable(self) -> None:
        self.assertIsInstance(roles.ROLE_REFERENCES, MappingProxyType)
        self.assertIsInstance(roles.ROLE_KNOWLEDGE_REFERENCES, MappingProxyType)
        with self.assertRaises(TypeError):
            roles.ROLE_REFERENCES["dispatch_new"] = "references/new.md"
        with self.assertRaises(TypeError):
            roles.ROLE_KNOWLEDGE_REFERENCES["dispatch_new"] = ("references/new.md",)


if __name__ == "__main__":
    unittest.main()
