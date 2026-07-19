from __future__ import annotations

import hashlib
from typing import Mapping
import unittest

from scripts.better_plan.domain.design import (
    canonical_design_bytes,
    design_digest,
    independent_ownership_issues,
    normalize_design_path,
    paths_overlap,
    validate_design_contract,
)


def _sample_design(
    *, owned_paths=None, scaffold_paths=None, acceptance_paths=None, symbols=None, interfaces=None, dependencies=None, decisions=None
):
    resolved_owned_paths = list(owned_paths) if owned_paths is not None else ["scripts/example.py"]
    default_symbol_path = sorted(resolved_owned_paths)[0]
    return {
        "artifact": "docs/plan/acceptance-state-machine/Architecture.md",
        "owned_paths": resolved_owned_paths,
        "scaffold_paths": list(scaffold_paths) if scaffold_paths is not None else [default_symbol_path],
        "acceptance_paths": list(acceptance_paths) if acceptance_paths is not None else ["docs/plan/acceptance-state-machine/Validation.md", "tests/test_example.py"],
        "symbols": list(symbols) if symbols is not None else [
            {
                "path": default_symbol_path,
                "kind": "function",
                "name": "evaluate",
                "operation": "add",
                "signature": "evaluate(state)",
            }
        ],
        "interfaces": list(interfaces) if interfaces is not None else [
            {
                "name": "evaluate",
                "producer": default_symbol_path,
                "consumers": ["scripts/manifest_tool.py"],
                "inputs": "validated immutable state mapping",
                "outputs": "one bounded action string",
                "errors": ["ValueError"],
            }
        ],
        "dependencies": list(dependencies) if dependencies is not None else [],
        "decisions": dict(decisions) if decisions is not None else {
            "composition": "compose pure functions; no inheritance",
            "algorithms": "constant-time lookup table",
            "data_structures": "tuple and dict",
            "state": "pure adapter boundary",
            "isolation": "disjoint role write paths",
            "concurrency": "serialize Plan state",
        },
        "test_seams": ["pure transition lookup", "atomic adapter boundary"],
    }


class DesignContractValidationTests(unittest.TestCase):
    def test_normalize_design_path_rejects_invalid(self):
        for invalid in (
            None,
            42,
            "",
            "   ",
            "/tmp/x",
            "a/../b",
            "a/./b",
            "./a",
            "../a",
            "a//b",
            "a/\x00b",
        ):
            with self.subTest(value=invalid):
                with self.assertRaises(ValueError):
                    normalize_design_path(invalid)

    def test_normalize_design_path_accepts_repository_relative(self):
        self.assertEqual(normalize_design_path("docs/plan/Architecture.md"), "docs/plan/Architecture.md")
        canonical = "scripts/better_plan/domain/design.py"
        self.assertEqual(normalize_design_path(canonical), canonical)

    def test_validate_design_contract_rejects_missing_and_unknown_fields(self):
        issues = validate_design_contract({})
        self.assertIn("required field: artifact", issues)
        self.assertIn("required field: owned_paths", issues)
        self.assertIn("required field: scaffold_paths", issues)
        self.assertIn("required field: acceptance_paths", issues)
        self.assertIn("required field: symbols", issues)
        self.assertIn("required field: interfaces", issues)
        self.assertIn("required field: dependencies", issues)
        self.assertIn("required field: decisions", issues)
        self.assertIn("required field: test_seams", issues)

        bad_extra = _sample_design()
        bad_extra["unexpected_field"] = "not allowed"
        issues = validate_design_contract(bad_extra)
        self.assertTrue(any("unexpected field" in issue for issue in issues))

    def test_validate_design_contract_allows_complete_valid_design(self):
        issues = validate_design_contract(_sample_design())
        self.assertEqual(issues, ())

    def test_validate_design_contract_enforces_symbol_schema(self):
        invalid = _sample_design(
            symbols=[
                {
                    "path": "scripts/example.py",
                    "kind": "invalid-kind",
                    "name": "evaluate",
                    "operation": "add",
                    "signature": "evaluate(state)",
                }
            ]
        )
        issues = validate_design_contract(invalid)
        self.assertTrue(any("symbol" in issue and "kind" in issue for issue in issues))

        invalid_op = _sample_design(
            symbols=[
                {
                    "path": "scripts/example.py",
                    "kind": "function",
                    "name": "evaluate",
                    "operation": "upgrade",
                    "signature": "evaluate(state)",
                }
            ]
        )
        issues = validate_design_contract(invalid_op)
        self.assertTrue(any("symbol" in issue and "operation" in issue for issue in issues))

    def test_validate_design_contract_enforces_interface_schema(self):
        bad_consumers = _sample_design(
            interfaces=[
                {
                    "name": "evaluate",
                    "producer": "scripts/example.py",
                    "consumers": "scripts/manifest_tool.py",
                    "inputs": "validated immutable state mapping",
                    "outputs": "one bounded action string",
                    "errors": ["ValueError"],
                }
            ]
        )
        issues = validate_design_contract(bad_consumers)
        self.assertTrue(any("interface" in issue and "consumers" in issue for issue in issues))

        bad_errors = _sample_design(
            interfaces=[
                {
                    "name": "evaluate",
                    "producer": "scripts/example.py",
                    "consumers": ["scripts/manifest_tool.py"],
                    "inputs": "validated immutable state mapping",
                    "outputs": "one bounded action string",
                    "errors": [1, 2, 3],
                }
            ]
        )
        issues = validate_design_contract(bad_errors)
        self.assertTrue(any("interface" in issue and "errors" in issue for issue in issues))

    def test_validate_design_contract_enforces_decision_schema(self):
        bad_decisions = _sample_design(
            decisions={
                "composition": "compose",
                "algorithms": "constant-time",
                "data_structures": "tuple and dict",
                "state": "state owner",
                "isolation": "disjoint",
                "concurrency": "serialize",
                "unknown_area": "forbidden",
            }
        )
        issues = validate_design_contract(bad_decisions)
        self.assertTrue(any("decision" in issue for issue in issues))

    def test_design_digest_is_stable_and_deterministic(self):
        base = _sample_design(owned_paths=["scripts/b.py", "scripts/a.py"])
        permuted = _sample_design(owned_paths=["scripts/a.py", "scripts/b.py"])

        base_issues = validate_design_contract(base)
        permuted_issues = validate_design_contract(permuted)
        self.assertEqual(base_issues, ())
        self.assertEqual(permuted_issues, ())
        self.assertEqual(canonical_design_bytes(base), canonical_design_bytes(permuted))
        self.assertEqual(design_digest(base), design_digest(permuted))

        changed = _sample_design(owned_paths=["scripts/b.py"])
        self.assertNotEqual(design_digest(base), design_digest(changed))

    def test_paths_overlap_uses_component_ancestry(self):
        self.assertTrue(paths_overlap("a/b.py", "a/b.py"))
        self.assertTrue(paths_overlap("a", "a/b.py"))
        self.assertTrue(paths_overlap("a/b/c.py", "a/b"))
        self.assertFalse(paths_overlap("a/b.py", "a/bc.py"))
        self.assertFalse(paths_overlap("a/b/c.py", "a/bd/c.py"))

    def test_independent_ownership_issues_respects_dependency_order(self):
        nodes = [
            {"id": "node-a", "owned_paths": ["services/a.py"]},
            {"id": "node-b", "owned_paths": ["services/a/b.py"]},
        ]

        def reachable(from_node: str, to_node: str) -> bool:
            # Node B depends on Node A, so overlap is allowed.
            return from_node == "node-b" and to_node == "node-a"

        issues = independent_ownership_issues(nodes, reachable)
        self.assertEqual(issues, ())

    def test_independent_ownership_issues_rejects_overlap_without_dependency(self):
        nodes = [
            {"id": "node-a", "owned_paths": ["services/a.py"]},
            {"id": "node-b", "owned_paths": ["services/a/b.py"]},
        ]

        def reachable(from_node: str, to_node: str) -> bool:
            return False

        issues = independent_ownership_issues(nodes, reachable)
        self.assertEqual(len(issues), 1)
        self.assertTrue(any("ownership collision" in issue for issue in issues))
