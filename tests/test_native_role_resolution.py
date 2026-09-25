"""Runtime resolution of installed and recommended Codex role selectors."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.better_plan.infrastructure.native_roles import resolve_codex_role
from scripts.better_plan.application.workflow import _selector_payload
from scripts.better_plan.domain.models import ToolError


class NativeRoleResolutionTests(unittest.TestCase):
    def test_installed_role_precedes_project_recommendation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            agents = home / "agents"
            agents.mkdir()
            (agents / "worker.toml").write_text(
                'name = "worker"\nmodel = "gpt-5.6-sol"\nmodel_reasoning_effort = "medium"\n',
                encoding="utf-8",
            )

            selector = resolve_codex_role("worker", home)

        self.assertIsNotNone(selector)
        assert selector is not None
        self.assertEqual((selector.model, selector.reasoning_effort), ("gpt-5.6-sol", "medium"))
        self.assertEqual(selector.source, "installed-codex-role")

    def test_model_less_role_inherits_host_instead_of_using_package_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            agents = home / "agents"
            agents.mkdir()
            (agents / "custom.toml").write_text(
                "name = 'worker' # identity is independent of filename\n"
                'developer_instructions = """\nmodel = "example-only"\n"""\n',
                encoding="utf-8",
            )

            selector = resolve_codex_role("worker", home)

        self.assertIsNotNone(selector)
        assert selector is not None
        self.assertIsNone(selector.model)
        self.assertEqual(selector.source, "installed-codex-role")

    def test_project_role_precedes_personal_role_for_the_packaged_hybrid_worker(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            home = root / "home"
            project = root / "project"
            personal = home / "agents"
            personal.mkdir(parents=True)
            (personal / "utility.toml").write_text(
                "name = 'hybrid-worker'\nmodel = 'personal-model'\n", encoding="utf-8"
            )
            self.assertEqual(resolve_codex_role("hybrid-worker", home).model, "personal-model")
            scoped = project / ".codex" / "agents"
            scoped.mkdir(parents=True)
            (scoped / "override.toml").write_text(
                "name = 'hybrid-worker'\nmodel = 'project-model' # public pin\n"
                "model_reasoning_effort = 'low'\n", encoding="utf-8"
            )
            selector = resolve_codex_role("hybrid-worker", home, project_root=project)
        self.assertEqual((selector.model, selector.reasoning_effort), ("project-model", "low"))
        self.assertEqual(selector.source, "project-codex-role")

    def test_packaged_hybrid_worker_recommendation_matches_the_installed_preset(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            selector = resolve_codex_role("hybrid-worker", Path(tmpdir))

        self.assertIsNotNone(selector)
        assert selector is not None
        self.assertEqual((selector.model, selector.reasoning_effort), ("gpt-6-astra", "low"))
        self.assertEqual(selector.source, "project-recommendation")

    def test_removed_finder_roles_have_no_packaged_recommendation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            for role in ("finder", "fallback_finder"):
                with self.subTest(role=role):
                    self.assertIsNone(resolve_codex_role(role, Path(tmpdir)))

    def test_malformed_config_is_reported_without_substituting_a_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            (home / "agents").mkdir()
            (home / "agents" / "worker.toml").write_text('model = [invalid', encoding="utf-8")
            with self.assertRaises(ToolError):
                resolve_codex_role("worker", home)

    def test_dispatch_identity_tracks_current_config_instead_of_stale_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            home = Path(tmpdir)
            agents = home / "agents"
            agents.mkdir()
            role = agents / "designer.toml"
            stale_prompt = 'name = "designer"\ndeveloper_instructions = "assignment: model=old-model"\n'
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
            self.assertIsNone(resolve_codex_role("worker", root / "codex", root / "package"))


if __name__ == "__main__":
    unittest.main()
