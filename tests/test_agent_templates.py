"""Packaged role templates delegate to the maintained delivery guidance."""

from __future__ import annotations

from pathlib import Path
import re
import unittest

from scripts.better_plan.installation.assignments import CODEX_DEFAULT_MATRIX
from scripts.better_plan.installation.models import AGENTS, CURRENT_SKILL_FILES
from scripts.better_plan.installation.targets import KILO_AGENT_FILES, NATIVE_ROLE_FILES
from scripts.generate_workflow_presentation import build_prompt_data, embedded_prompt_data


ROOT = Path(__file__).resolve().parents[1]
ROLE_FILES = {
    "codex": ("designer.toml", "worker.toml", "verifier.toml", "reviewer.toml", "adversary.toml"),
    "claude-code": ("designer.md", "worker.md", "verifier.md", "reviewer.md", "adversary.md"),
    "cursor": ("designer.md", "worker.md", "verifier.md", "reviewer.md", "adversary.md"),
}
REMOVED_ROLES = (
    "hybrid-worker",
    "worker-standard",
    "worker-complex",
    "worker-routine",
    "worker-critical",
)


class PackagedRoleTests(unittest.TestCase):
    def test_presentation_prompt_data_matches_the_canonical_sources(self) -> None:
        html = (ROOT / "docs" / "presentations" / "better-plan-workflow.html").read_text(
            encoding="utf-8"
        )
        data = embedded_prompt_data(html)
        self.assertEqual(data, build_prompt_data(ROOT))
        self.assertEqual(set(data["roles"]), {"main", "designer", "worker", "verifier", "reviewer", "adversary"})
        self.assertEqual(set(data["entries"]), {"main", "designer", "worker", "verifier", "reviewer", "adversary"})
        self.assertEqual(set(data["briefs"]), {"designer", "worker", "verifier", "reviewer", "adversary"})
        self.assertEqual(set(re.findall(r'data-role="([a-z]+)"', html)), set(data["roles"]))

    def test_every_native_host_packages_the_five_roles(self) -> None:
        for host, filenames in ROLE_FILES.items():
            with self.subTest(host=host):
                self.assertEqual(
                    sorted(name.name for name in (ROOT / "agents" / host).iterdir() if name.is_file()),
                    sorted(filenames),
                )
        self.assertEqual(sorted(NATIVE_ROLE_FILES["codex"]), sorted(ROLE_FILES["codex"]))
        self.assertEqual(sorted(NATIVE_ROLE_FILES["claude"]), sorted(ROLE_FILES["claude-code"]))
        self.assertEqual(sorted(NATIVE_ROLE_FILES["cursor"]), sorted(ROLE_FILES["cursor"]))

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

    def test_host_prompts_delegate_workflow_to_current_skill(self) -> None:
        for host in (*ROLE_FILES, "kilo"):
            for role in ("designer", "worker", "verifier", "reviewer", "adversary"):
                filename = ("better-plan-" if host == "kilo" else "") + role + (".toml" if host == "codex" else ".md")
                with self.subTest(host=host, role=role):
                    text = (ROOT / "agents" / host / filename).read_text(encoding="utf-8")
                    self.assertIn("SKILL.md", text)
                    self.assertIn("references/%s.md" % role, text)

    def test_codex_is_the_only_host_with_presets(self) -> None:
        self.assertEqual(set(CODEX_DEFAULT_MATRIX), {"designer", "worker", "reviewer", "verifier", "adversary"})
        verifier = (ROOT / "agents" / "codex" / "verifier.toml").read_text(encoding="utf-8")
        self.assertNotRegex(verifier, r"(?m)^\s*(model|model_reasoning_effort)\s*=")
        self.assertEqual(AGENTS, ("codex", "claude", "cursor", "kilo", "dsh"))

    def test_adversary_prompt_sources_offer_read_only_inspection(self) -> None:
        codex = (ROOT / "agents/codex/adversary.toml").read_text(encoding="utf-8")
        self.assertIn('sandbox_mode = "read-only"', codex)
        self.assertNotRegex(codex, r"(?m)^\s*(model|model_reasoning_effort)\s*=")
        claude = (ROOT / "agents/claude-code/adversary.md").read_text(encoding="utf-8")
        self.assertIn("tools: Read, Glob, Grep, WebFetch, WebSearch, SendMessage", claude)
        cursor = (ROOT / "agents/cursor/adversary.md").read_text(encoding="utf-8")
        self.assertIn("readonly: true", cursor)
        kilo = (ROOT / "agents/kilo/better-plan-adversary.md").read_text(encoding="utf-8")
        self.assertIn('  "*": deny', kilo)
        for tool in ("read", "glob", "grep", "webfetch"):
            self.assertIn("  %s: allow" % tool, kilo)
        for tool in ("edit", "write", "bash", "task"):
            self.assertIn("  %s: deny" % tool, kilo)

    def test_installed_guidance_links_resolve_inside_the_payload(self) -> None:
        # Progressive disclosure works only if every linked guide ships with the skill.
        payload = set(CURRENT_SKILL_FILES)
        for relative in CURRENT_SKILL_FILES:
            if not relative.endswith(".md"):
                continue
            path = ROOT / relative
            for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
                if "://" in target or target.startswith("#"):
                    continue
                target_path = (path.parent / target.split("#", 1)[0]).resolve()
                with self.subTest(source=relative, target=target):
                    self.assertIn(target_path.relative_to(ROOT).as_posix(), payload)
                    self.assertTrue(target_path.is_file())

    def test_unpinned_role_files_declare_no_selector(self) -> None:
        for host in ("claude-code", "cursor"):
            for filename in ROLE_FILES[host]:
                with self.subTest(host=host, template=filename):
                    text = (ROOT / "agents" / host / filename).read_text(encoding="utf-8")
                    self.assertNotIn("model =", text)
                    self.assertNotIn("model:", text)

    def test_kilo_installs_one_primary_and_five_leaf_subagents(self) -> None:
        self.assertEqual(len(KILO_AGENT_FILES), 6)
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
