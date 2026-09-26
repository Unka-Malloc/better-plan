"""The packaged host templates carry exactly the three delivery roles."""

from __future__ import annotations

from pathlib import Path
import unittest

from scripts.better_plan.installation.assignments import CODEX_DEFAULT_MATRIX
from scripts.better_plan.installation.models import AGENTS, CURRENT_SKILL_FILES
from scripts.better_plan.installation.targets import KILO_AGENT_FILES, NATIVE_ROLE_FILES


ROOT = Path(__file__).resolve().parents[1]
ROLE_FILES = {
    "codex": ("designer.toml", "worker.toml", "reviewer.toml"),
    "claude-code": ("designer.md", "worker.md", "reviewer.md"),
    "cursor": ("designer.md", "worker.md", "reviewer.md"),
}
REMOVED_ROLES = (
    "hybrid-worker",
    "worker-standard",
    "worker-complex",
    "worker-routine",
    "worker-critical",
)


class PackagedRoleTests(unittest.TestCase):
    def test_every_native_host_packages_the_three_roles(self) -> None:
        for host, filenames in ROLE_FILES.items():
            with self.subTest(host=host):
                self.assertEqual(
                    sorted(name.name for name in (ROOT / "agents" / host).iterdir() if name.is_file()),
                    sorted(filenames),
                )
        self.assertEqual(NATIVE_ROLE_FILES["codex"], ROLE_FILES["codex"])
        self.assertEqual(NATIVE_ROLE_FILES["claude"], ROLE_FILES["claude-code"])
        self.assertEqual(NATIVE_ROLE_FILES["cursor"], ROLE_FILES["cursor"])

    def test_no_removed_role_is_still_packaged(self) -> None:
        for host in ROLE_FILES:
            for removed in REMOVED_ROLES:
                with self.subTest(host=host, role=removed):
                    self.assertFalse((ROOT / "agents" / host / ("%s.md" % removed)).exists())
                    self.assertFalse((ROOT / "agents" / host / ("%s.toml" % removed)).exists())
        for removed in REMOVED_ROLES:
            self.assertNotIn("agents/kilo/better-plan-%s.md" % removed, CURRENT_SKILL_FILES)

    def test_every_role_template_points_at_its_own_reference(self) -> None:
        for host, filenames in ROLE_FILES.items():
            for filename in filenames:
                with self.subTest(host=host, template=filename):
                    text = (ROOT / "agents" / host / filename).read_text(encoding="utf-8")
                    role = Path(filename).stem
                    self.assertIn("references/%s.md" % role, text)
                    self.assertIn("ASSIGNMENT_PLACEHOLDER", text)

    def test_codex_is_the_only_host_with_presets(self) -> None:
        self.assertEqual(set(CODEX_DEFAULT_MATRIX), {"designer", "worker", "reviewer"})
        self.assertEqual(AGENTS, ("codex", "claude", "cursor", "kilo", "dsh"))

    def test_unpinned_role_files_declare_no_selector(self) -> None:
        for host in ("claude-code", "cursor"):
            for filename in ROLE_FILES[host]:
                with self.subTest(host=host, template=filename):
                    text = (ROOT / "agents" / host / filename).read_text(encoding="utf-8")
                    self.assertNotIn("model =", text)
                    self.assertNotIn("model:", text)

    def test_kilo_installs_one_primary_and_three_leaf_subagents(self) -> None:
        self.assertEqual(len(KILO_AGENT_FILES), 4)
        primary = (ROOT / "agents" / "kilo" / "better-plan.md").read_text(encoding="utf-8")
        self.assertIn("mode: primary", primary)
        for filename in KILO_AGENT_FILES[1:]:
            with self.subTest(template=filename):
                text = (ROOT / "agents" / "kilo" / filename).read_text(encoding="utf-8")
                self.assertIn("mode: subagent", text)
                self.assertIn("task: deny", text)

    def test_the_payload_ships_prompts_and_tools_only(self) -> None:
        """The reference set is prose; benchmark data belongs to the tool, not the skill."""

        payload_data = sorted(
            name
            for name in CURRENT_SKILL_FILES
            if name.startswith("references/") and not name.endswith(".md")
        )
        self.assertEqual(payload_data, [])
        on_disk = sorted(
            path.name for path in (ROOT / "references").iterdir() if path.suffix != ".md"
        )
        self.assertEqual(on_disk, [])


if __name__ == "__main__":
    unittest.main()
