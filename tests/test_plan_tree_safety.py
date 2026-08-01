"""Focused privacy and malformed-input acceptance for Plan tree projections."""

from __future__ import annotations

import unittest

from scripts.better_plan.domain.tree import render_workspace_tree
from tests.test_plan_tree import tree_node, tree_plan, uuid4


class ReadablePlanTreeSafetyTests(unittest.TestCase):
    def test_default_omits_audit_only_values_and_details_redacts_them(self) -> None:
        unsafe = "api_key=fixture-private-value"
        plan = tree_plan(
            uuid4(5000),
            title="Safe execution root",
            directory="safe-root",
            status="pending",
            kind="root",
        )
        plan["purpose"] = unsafe
        plan["goal"] = unsafe
        plan["description"] = unsafe
        node = tree_node(
            uuid4(5001),
            status="pending",
            code="S0",
            title="Safe readable milestone",
        )
        node["goal"] = unsafe
        node["status_reason"] = unsafe

        readable = render_workspace_tree([plan], [[node]], [None])
        details = render_workspace_tree([plan], [[node]], [None], details=True)

        self.assertNotIn(unsafe, readable)
        self.assertNotIn("Purpose:", readable)
        self.assertNotIn("Goal:", readable)
        self.assertNotIn("Description:", readable)
        self.assertIn("S0 Safe readable milestone [E]", readable)
        self.assertNotIn(unsafe, details)
        self.assertIn("⚠️ <invalid purpose:", details)
        self.assertIn("⚠️ <invalid goal:", details)
        self.assertIn("⚠️ <invalid description:", details)
        self.assertIn("⚠️ <invalid node goal:", details)
        self.assertIn("⚠️ <invalid status reason:", details)

    def test_unsafe_readable_fields_become_bounded_diagnostics_without_echo(self) -> None:
        unsafe_values = (
            "K0 <- forged dependency",
            "api_key=private-readable-title",
            "unsafe\ntag",
            "/protected/private-condition",
            "token=private-entry-condition",
        )
        prerequisite_id = uuid4(5100)
        root = tree_plan(
            uuid4(5101),
            title="Safe root",
            directory="safe-root",
            status="deferred",
            kind="root",
            entry_gate={
                "title": "Safe entry gate",
                "prerequisites": [prerequisite_id],
                "conditions": [unsafe_values[4]],
            },
        )
        target = tree_node(
            prerequisite_id,
            status="completed",
            code="K0",
            title="Safe target",
        )
        dependent = tree_node(
            uuid4(5102),
            status="deferred",
            code=unsafe_values[0],
            title=unsafe_values[1],
            prerequisites=[prerequisite_id],
            tags=[unsafe_values[2]],
            conditions=[unsafe_values[3]],
        )

        readable = render_workspace_tree([root], [[target, dependent]], [None])

        for unsafe in unsafe_values:
            with self.subTest(unsafe=unsafe):
                self.assertNotIn(unsafe, readable)
        self.assertGreaterEqual(readable.count("⚠️"), 4)
        self.assertIn("invalid", readable.casefold())

    def test_unresolved_or_ambiguous_prerequisites_never_look_executable(self) -> None:
        duplicate_id = uuid4(5200)
        missing_id = uuid4(5299)
        root = tree_plan(
            uuid4(5201),
            title="Malformed dependency root",
            directory="malformed-dependencies",
            status="pending",
            kind="root",
        )
        nodes = [
            tree_node(
                duplicate_id,
                status="completed",
                code="A0",
                title="First duplicate owner",
            ),
            tree_node(
                duplicate_id,
                status="completed",
                code="A1",
                title="Second duplicate owner",
            ),
            tree_node(
                uuid4(5202),
                status="pending",
                code="B0",
                title="Ambiguous consumer",
                prerequisites=[duplicate_id],
            ),
            tree_node(
                uuid4(5203),
                status="pending",
                code="B1",
                title="Unresolved consumer",
                prerequisites=[missing_id],
            ),
        ]

        readable = render_workspace_tree([root], [nodes], [None])

        self.assertNotIn("<-", readable)
        self.assertIn("ambiguous", readable.casefold())
        self.assertIn("unresolved", readable.casefold())
        self.assertGreaterEqual(readable.count("⚠️"), 2)


if __name__ == "__main__":
    unittest.main()
