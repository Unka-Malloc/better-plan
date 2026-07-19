"""Acceptance oracles for the current Hook architecture."""

from __future__ import annotations

from pathlib import Path
import ast
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
HOOK_TOOL = ROOT / "scripts" / "hook_tool.py"
HOOK_PACKAGE = ROOT / "scripts" / "better_plan" / "hooks"


def hook_architecture_violations(sources: dict[str, str]) -> list[str]:
    """Pure fault-fixture oracle for a non-thin executable."""
    findings: list[str] = []
    entry = sources.get("scripts/hook_tool.py")
    if entry is not None:
        tree = ast.parse(entry)
        if any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            for node in tree.body
        ):
            findings.append("hook_tool contains business definitions")
    return findings


class HookArchitectureAcceptance(unittest.TestCase):
    def test_package_owns_lifecycle_symbols(self) -> None:
        expected = {
            "detect_event_workspace": HOOK_PACKAGE / "scope.py",
            "safe_handle_event": HOOK_PACKAGE / "runtime.py",
        }
        definitions: dict[str, list[Path]] = {name: [] for name in expected}
        for path in HOOK_PACKAGE.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if node.name in definitions:
                        definitions[node.name].append(path)
        for name, owner in expected.items():
            with self.subTest(name=name):
                self.assertEqual(definitions[name], [owner])

    def test_hook_tool_is_a_thin_executable(self) -> None:
        tree = ast.parse(HOOK_TOOL.read_text(encoding="utf-8"))
        self.assertFalse(
            any(
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Try))
                for node in tree.body
            )
        )
        imports_runtime = any(
            isinstance(node, ast.ImportFrom)
            and node.module == "scripts.better_plan.hooks"
            and {alias.name for alias in node.names} == {"runtime"}
            for node in tree.body
        )
        self.assertTrue(imports_runtime)
        completed = subprocess.run(
            [sys.executable, str(HOOK_TOOL), "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("usage:", completed.stdout.lower())

    def test_hook_package_has_no_state_write_dependency(self) -> None:
        forbidden = {"write_state_entries", "write_location_and_sync_plan", "run_node_mutation"}
        for path in HOOK_PACKAGE.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            loaded = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
            attributes = {
                node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
            }
            imported = {
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom)
                for alias in node.names
            }
            self.assertTrue(forbidden.isdisjoint(loaded | attributes | imported), path)

    def test_fault_oracle_detects_business_entry(self) -> None:
        findings = hook_architecture_violations(
            {
                "scripts/hook_tool.py": "def handle_event():\n    return {}\n",
            }
        )
        self.assertTrue(any("business definitions" in item for item in findings))


if __name__ == "__main__":
    unittest.main()
