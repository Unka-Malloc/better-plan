"""Local Codex roles are identified by their TOML name, never by a filename."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.better_plan.infrastructure.native_roles import configured_codex_role_names


class ConfiguredRoleNameTests(unittest.TestCase):
    def _home_with(self, files: dict[str, str]) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        home = Path(temporary.name)
        agents = home / "agents"
        agents.mkdir()
        for filename, content in files.items():
            (agents / filename).write_text(content, encoding="utf-8")
        return home

    def test_configured_role_names_reads_the_local_matrix(self) -> None:
        home = self._home_with(
            {
                "renamed.toml": 'name = "designer"\nmodel = "local-model"\n',
                "reviewer.toml": 'name = "reviewer"\n',
            }
        )

        self.assertEqual(configured_codex_role_names(home), {"designer", "reviewer"})

    def test_a_malformed_role_file_is_ignored_rather_than_guessed(self) -> None:
        home = self._home_with(
            {
                "worker.toml": "this is not toml = = =\n",
                "reviewer.toml": 'name = "reviewer"\n',
            }
        )

        self.assertEqual(configured_codex_role_names(home), {"reviewer"})

    def test_a_host_without_an_agent_directory_declares_no_roles(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            self.assertEqual(configured_codex_role_names(Path(temporary)), frozenset())


if __name__ == "__main__":
    unittest.main()
