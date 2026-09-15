"""Runtime resolution of installed and recommended Codex role selectors."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.better_plan.infrastructure.native_roles import resolve_codex_role
from scripts.better_plan.application.workflow import _selector_payload


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
        self.assertEqual((selector.model, selector.reasoning_effort), ("gpt-6-astra", "low"))
        self.assertEqual(selector.source, "project-recommendation")

    def test_dispatch_identity_tracks_current_config_instead_of_stale_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            agents = home / "agents"
            agents.mkdir()
            role = agents / "designer.toml"
            stale_prompt = 'developer_instructions = "assignment: model=old-model"\n'
            role.write_text(
                'model = "first-model"\nmodel_reasoning_effort = "low"\n' + stale_prompt,
                encoding="utf-8",
            )
            first = _selector_payload("designer", "codex", str(home))
            role.write_text(
                'model = "second-model"\nmodel_reasoning_effort = "max"\n' + stale_prompt,
                encoding="utf-8",
            )
            second = _selector_payload("designer", "codex", str(home))

        self.assertIn("model=first-model | reasoning_effort=low", first["assignment_line"])
        self.assertIn("model=second-model | reasoning_effort=max", second["assignment_line"])
        self.assertIn("source=installed-codex-role", second["assignment_line"])
        self.assertNotIn("old-model", second["assignment_line"])

    def test_unknown_role_has_no_implicit_selector(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertIsNone(resolve_codex_role("unknown-role", Path(tmpdir)))

    def test_missing_installed_and_packaged_roles_return_control_to_main(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.assertIsNone(resolve_codex_role("worker-complex", root / "codex", root / "package"))


if __name__ == "__main__":
    unittest.main()
