"""Runtime resolution of installed and recommended Codex role selectors."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.better_plan.infrastructure.native_roles import resolve_codex_role


class NativeRoleResolutionTests(unittest.TestCase):
    def test_installed_role_precedes_project_recommendation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            agents = home / "agents"
            agents.mkdir()
            (agents / "worker-complex.toml").write_text(
                'name = "worker-complex"\nmodel = "gpt-5.6-sol"\nmodel_reasoning_effort = "medium"\n',
                encoding="utf-8",
            )

            selector = resolve_codex_role("worker-complex", home)

        self.assertIsNotNone(selector)
        assert selector is not None
        self.assertEqual((selector.model, selector.reasoning_effort), ("gpt-5.6-sol", "medium"))
        self.assertEqual(selector.source, "installed-codex-role")

    def test_missing_or_invalid_installed_role_uses_project_recommendation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            agents = home / "agents"
            agents.mkdir()
            (agents / "worker-complex.toml").write_text('name = "worker-complex"\n', encoding="utf-8")

            selector = resolve_codex_role("worker-complex", home)

        self.assertIsNotNone(selector)
        assert selector is not None
        self.assertEqual((selector.model, selector.reasoning_effort), ("gpt-5.6-sol", "medium"))
        self.assertEqual(selector.source, "project-recommendation")

    def test_unknown_role_has_no_implicit_selector(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertIsNone(resolve_codex_role("unknown-role", Path(tmpdir)))

    def test_missing_installed_and_packaged_roles_return_control_to_main(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.assertIsNone(resolve_codex_role("worker-complex", root / "codex", root / "package"))


if __name__ == "__main__":
    unittest.main()
