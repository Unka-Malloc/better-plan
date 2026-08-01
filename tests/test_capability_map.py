"""Acceptance for progressive capability disclosure and delivery binding."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.better_plan.application.workflow import bounded_acceptance_payload
from scripts.better_plan.domain.capabilities import (
    capability_scope,
    plan_capability_binding_issues,
    render_capability_tree,
    validate_capability_data,
)
from tests.test_manifest_tool_cli import (
    NODE_ID,
    PYTHON_TOOL,
    checkpoint_node,
    run_command,
    write_workspace,
)


ROOT_CAPABILITY = {
    "key": "repository",
    "parent": None,
    "title": "Repository core",
    "kind": "repository",
    "basis": "observed",
    "disclosure": "examined",
    "touch": "untouched",
    "source_files": ["src"],
    "description": "Observed mature repository foundation accepted as current fact.",
}


def capability(
    key: str,
    parent: str,
    title: str,
    *,
    disclosure: str = "known",
    touch: str = "untouched",
) -> dict[str, object]:
    return {
        "key": key,
        "parent": parent,
        "title": title,
        "kind": "module",
        "basis": "observed",
        "disclosure": disclosure,
        "touch": touch,
        "source_files": [f"src/{key.rsplit('/', 1)[-1]}"],
        "description": f"Bounded fact for {title}.",
    }


class CapabilityMapTests(unittest.TestCase):
    def test_catalog_requires_one_ordered_examined_repository_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "Capabilities.json"
            entries = [
                capability("repository/child", "repository", "Child"),
                ROOT_CAPABILITY,
            ]
            _, issues = validate_capability_data(path, entries)
            messages = [issue.message for issue in issues]
            self.assertTrue(any("parent must appear before" in message for message in messages))

            invalid_known = [ROOT_CAPABILITY, capability("repository/child", "repository", "Child", touch="in_scope")]
            _, issues = validate_capability_data(path, invalid_known)
            self.assertTrue(any("known capabilities must remain untouched" in issue.message for issue in issues))

    def test_cli_discloses_idempotently_and_promotes_only_when_touched(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_workspace(root)

            initialized = run_command(
                sys.executable,
                PYTHON_TOOL,
                "init-capabilities",
                root,
                "--key",
                "repository",
                "--title",
                "Repository core",
                "--description",
                "Observed mature repository foundation accepted as current fact.",
                "--source",
                "src",
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)

            common = (
                sys.executable,
                PYTHON_TOOL,
                "upsert-capability",
                root,
                "--parent",
                "repository",
                "--kind",
                "module",
                "--basis",
                "observed",
            )
            target = run_command(
                *common,
                "--key",
                "repository/a",
                "--title",
                "Module A",
                "--description",
                "Module selected for the current change.",
                "--disclosure",
                "examined",
                "--touch",
                "in_scope",
                "--source",
                "src/a",
            )
            self.assertEqual(target.returncode, 0, target.stderr)
            for _ in range(2):
                sibling = run_command(
                    *common,
                    "--key",
                    "repository/b",
                    "--title",
                    "Module B",
                    "--description",
                    "Sibling observed but not explored for this change.",
                    "--source",
                    "src/b",
                )
                self.assertEqual(sibling.returncode, 0, sibling.stderr)

            entries = json.loads((root / "Capabilities.json").read_text(encoding="utf-8"))
            self.assertEqual([entry["key"] for entry in entries].count("repository/b"), 1)
            sibling_entry = next(entry for entry in entries if entry["key"] == "repository/b")
            self.assertEqual((sibling_entry["disclosure"], sibling_entry["touch"]), ("known", "untouched"))

            promoted = run_command(
                sys.executable,
                PYTHON_TOOL,
                "promote-capability",
                "repository/b",
                root,
                "--touch",
                "in_scope",
            )
            self.assertEqual(promoted.returncode, 0, promoted.stderr)
            entries = json.loads((root / "Capabilities.json").read_text(encoding="utf-8"))
            sibling_entry = next(entry for entry in entries if entry["key"] == "repository/b")
            self.assertEqual((sibling_entry["disclosure"], sibling_entry["touch"]), ("examined", "in_scope"))

            validated = run_command(sys.executable, PYTHON_TOOL, "validate", root, "--no-git")
            self.assertEqual(validated.returncode, 0, validated.stderr)
            self.assertIn("3 state file(s)", validated.stdout)
            rendered = run_command(sys.executable, PYTHON_TOOL, "tree", root)
            self.assertEqual(rendered.returncode, 0, rendered.stderr)
            self.assertLess(rendered.stdout.index("Capability Facts"), rendered.stdout.index("Legend:"))

    def test_missing_parent_is_rejected_without_mutating_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_workspace(root)
            (root / "Capabilities.json").write_text(json.dumps([ROOT_CAPABILITY]), encoding="utf-8")
            before = (root / "Capabilities.json").read_bytes()
            result = run_command(
                sys.executable,
                PYTHON_TOOL,
                "upsert-capability",
                root,
                "--key",
                "repository/missing/leaf",
                "--parent",
                "repository/missing",
                "--title",
                "Leaf",
                "--kind",
                "feature",
                "--description",
                "Leaf whose path has not been disclosed.",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((root / "Capabilities.json").read_bytes(), before)

    def test_active_groups_require_unique_examined_in_scope_binding(self) -> None:
        path = Path("Manifest.json")
        entries = [
            ROOT_CAPABILITY,
            capability("repository/a", "repository", "Module A", disclosure="examined", touch="in_scope"),
            capability("repository/b", "repository", "Module B"),
        ]
        plans = [
            {"kind": "group", "status": "pending"},
            {"kind": "group", "status": "pending", "capability_key": "repository/b"},
            {"kind": "group", "status": "pending", "capability_key": "repository/a"},
            {"kind": "group", "status": "in_progress", "capability_key": "repository/a"},
        ]
        issues = plan_capability_binding_issues(path, plans, entries)
        messages = [issue.message for issue in issues]
        self.assertTrue(any("must bind" in message for message in messages))
        self.assertTrue(any("only examined" in message for message in messages))
        self.assertTrue(any("reuse or extend" in message for message in messages))

    def test_dispatch_scope_omits_known_untouched_descendants(self) -> None:
        entries = [
            ROOT_CAPABILITY,
            capability("repository/a", "repository", "Module A", disclosure="examined", touch="in_scope"),
            capability("repository/a/feature", "repository/a", "Touched feature", disclosure="examined", touch="modified"),
            capability("repository/a/other", "repository/a", "Known sibling"),
        ]
        scope = capability_scope(entries, "repository/a")
        self.assertIsNotNone(scope)
        assert scope is not None
        serialized = json.dumps(scope)
        self.assertIn("repository/a/feature", serialized)
        self.assertNotIn("repository/a/other", serialized)
        self.assertEqual(scope["known_untouched_descendants_omitted"], 1)

        node = checkpoint_node(NODE_ID, status="pending", role="implementation", checked=False)
        payload = bounded_acceptance_payload(node, capability_context=scope)
        self.assertEqual(payload["capability_scope"]["target_key"], "repository/a")

        rendered = render_capability_tree(entries)
        self.assertIn("Known sibling [known/untouched; observed]", rendered)

    def test_invalid_catalog_never_renders_or_escapes_direct_manifest_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_workspace(root)
            unsafe = dict(ROOT_CAPABILITY)
            unsafe["title"] = str(root / "private-capability")
            (root / "Capabilities.json").write_text(json.dumps([unsafe]), encoding="utf-8")

            for command in (
                ("tree", str(root)),
                ("validate", str(root / "Manifest.json"), "--no-git"),
            ):
                result = run_command(sys.executable, PYTHON_TOOL, *command)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(str(root), result.stdout)
                self.assertNotIn(str(root), result.stderr)

        external = dict(ROOT_CAPABILITY)
        external["source_files"] = ["https://example.invalid/private-source"]
        rendered = render_capability_tree([external], details=True)
        self.assertIn("<external reference>", rendered)
        self.assertNotIn("example.invalid", rendered)


if __name__ == "__main__":
    unittest.main()
