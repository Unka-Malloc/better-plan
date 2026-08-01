"""Acceptance for native role templates and one-time model pinning."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.better_plan.installation.assignments import (
    CODEX_DEFAULT_MATRIX,
    CODEX_FINDER_MATRIX,
    select_role_assignments,
)
from scripts.better_plan.installation.models import CURRENT_SKILL_FILES, InstallError, InstallPaths
from scripts.better_plan.installation.targets import NATIVE_ROLE_FILES, install_role_templates


ROOT = Path(__file__).resolve().parents[1]
DELIVERY_ROLE_NAMES = {
    "designer",
    "worker-routine",
    "worker-standard",
    "worker-complex",
    "worker-critical",
    "verifier",
    "visual-verifier",
    "reviewer",
    "visual-reviewer",
}
CODEX_AGENT_NAMES = DELIVERY_ROLE_NAMES | {"finder", "fallback_finder"}
CATALOG_PATTERNS = (
    "Factory Method",
    "Abstract Factory",
    "Builder",
    "Prototype",
    "Singleton",
    "Adapter",
    "Bridge",
    "Composite",
    "Decorator",
    "Facade",
    "Flyweight",
    "Proxy",
    "Chain of Responsibility",
    "Command",
    "Iterator",
    "Mediator",
    "Memento",
    "Observer",
    "State",
    "Strategy",
    "Template Method",
    "Visitor",
)


def paths(root: Path) -> InstallPaths:
    return InstallPaths(
        repo_root=ROOT,
        codex_home=root / "codex",
        shared_home=root / "shared",
        claude_home=root / "claude",
        opencode_config=root / "opencode",
        cursor_home=root / "cursor",
        copilot_home=root / "copilot",
        antigravity_home=root / "antigravity",
        pi_home=root / "pi",
        craft_home=root / "craft",
        kimi_home=root / "kimi",
    )


class AgentTemplateTests(unittest.TestCase):
    def test_each_native_host_bundles_the_complete_role_shape(self) -> None:
        source_target = {"claude": "claude-code"}
        for target, filenames in NATIVE_ROLE_FILES.items():
            with self.subTest(target=target):
                expected = CODEX_AGENT_NAMES if target == "codex" else DELIVERY_ROLE_NAMES
                self.assertEqual({Path(name).stem for name in filenames}, expected)
                directory = ROOT / "agents" / source_target.get(target, target)
                for filename in filenames:
                    text = (directory / filename).read_text(encoding="utf-8")
                    self.assertIn("ASSIGNMENT_PLACEHOLDER", text)
                    self.assertNotRegex(text, r"(?m)^model\s*[:=]")

    def test_role_contracts_encode_group_endcaps_and_repairing_verification(self) -> None:
        designer = (ROOT / "references" / "designer.md").read_text(encoding="utf-8").lower()
        worker = (ROOT / "references" / "worker.md").read_text(encoding="utf-8").lower()
        verifier = (ROOT / "references" / "verifier.md").read_text(encoding="utf-8").lower()
        reviewer = (ROOT / "references" / "reviewer.md").read_text(encoding="utf-8").lower()
        visual_verifier = (ROOT / "references" / "visual-verifier.md").read_text(encoding="utf-8").lower()
        visual_reviewer = (ROOT / "references" / "visual-reviewer.md").read_text(encoding="utf-8").lower()
        self.assertIn("whole group in one pass", designer)
        self.assertIn("progression between nodes", designer)
        self.assertIn("task difficulty", worker)
        self.assertIn("repair every", verifier)
        self.assertIn("exactly once per task group", reviewer)
        self.assertIn("decision_issues", reviewer)
        self.assertIn("immediate", reviewer)
        self.assertIn("deferred", reviewer)
        self.assertIn("real ui", visual_verifier)
        self.assertIn("rendered evidence", visual_verifier)
        self.assertIn("real ui", visual_reviewer)
        self.assertIn("decision_issues", visual_reviewer)

    def test_local_pattern_catalog_is_complete_and_installed(self) -> None:
        catalog_path = ROOT / "references" / "design-patterns.md"
        catalog = catalog_path.read_text(encoding="utf-8")
        numbered_headings = [
            line for line in catalog.splitlines() if line.startswith("### ") and ". " in line
        ]
        self.assertEqual(len(numbered_headings), 22)
        for pattern in CATALOG_PATTERNS:
            with self.subTest(pattern=pattern):
                self.assertEqual(
                    sum(f"（{pattern}）" in heading for heading in numbered_headings),
                    1,
                )
        self.assertFalse(any("Interpreter" in heading for heading in numbered_headings))
        self.assertIn("references/design-patterns.md", CURRENT_SKILL_FILES)
        self.assertIn("candidate: <模式英文名或 none>", catalog)
        self.assertIn("simpler_alternative", catalog)
        self.assertIn("costs_and_rejections", catalog)

    def test_every_native_designer_template_requires_the_offline_assessment(self) -> None:
        source_target = {"claude": "claude-code"}
        for target, filenames in NATIVE_ROLE_FILES.items():
            designer_filename = next(name for name in filenames if Path(name).stem == "designer")
            template = (
                ROOT / "agents" / source_target.get(target, target) / designer_filename
            ).read_text(encoding="utf-8").lower()
            with self.subTest(target=target):
                self.assertIn("references/design-patterns.md", template)
                self.assertIn("design_pattern_assessment", template)
                self.assertIn("candidate: none", template)
                self.assertIn("do not fetch", template)
                self.assertIn("parallel frontier", template)

    def test_every_native_worker_template_encourages_safe_concurrent_tool_work(self) -> None:
        source_target = {"claude": "claude-code"}
        for target, filenames in NATIVE_ROLE_FILES.items():
            directory = ROOT / "agents" / source_target.get(target, target)
            for filename in filenames:
                if not Path(filename).stem.startswith("worker-"):
                    continue
                template = (directory / filename).read_text(encoding="utf-8").lower()
                with self.subTest(target=target, filename=filename):
                    self.assertIn("independent reads", template)
                    self.assertIn("concurrently", template)

    def test_installer_renders_and_pins_codex_assignments(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            install_paths = paths(Path(tmpdir))
            messages = install_role_templates(install_paths, "codex", dry_run=False)
            directory = install_paths.codex_home / "agents"
            self.assertEqual({path.name for path in directory.iterdir()}, set(NATIVE_ROLE_FILES["codex"]))
            for filename in NATIVE_ROLE_FILES["codex"]:
                text = (directory / filename).read_text(encoding="utf-8")
                self.assertNotIn("ASSIGNMENT_PLACEHOLDER", text)
                self.assertRegex(text, r'(?m)^model = "[^\"]+"$')
                self.assertRegex(text, r"(?m)^assignment: ")
                self.assertNotIn("Pinned identity: assignment:", text)
                self.assertIn("role=", text)
                self.assertIn("basis=", text)
                self.assertIn("source=", text)
            expected_selectors = {
                agent_name: (model, effort)
                for agent_name, (_, model, effort, _) in CODEX_DEFAULT_MATRIX.items()
            }
            expected_selectors.update(CODEX_FINDER_MATRIX)
            for agent_name, (model, effort) in expected_selectors.items():
                with self.subTest(rendered_agent=agent_name):
                    rendered = (directory / f"{agent_name}.toml").read_text(encoding="utf-8")
                    self.assertIn(f'model = "{model}"', rendered)
                    self.assertIn(f'model_reasoning_effort = "{effort}"', rendered)
            self.assertTrue(any("pinned until explicit reinstall" in message for message in messages))
            assignment_message = next(
                message for message in messages if "pinned until explicit reinstall" in message
            )
            self.assertIn("Coding Agent", assignment_message)
            self.assertIn("Intelligence Index", assignment_message)
            self.assertIn("Codex read-only utility", assignment_message)
            self.assertIn("price ignored", assignment_message)
            self.assertIn("source codex-default-matrix", assignment_message)
            receipt = json.loads((install_paths.codex_home / "agents.better-plan.json").read_text(encoding="utf-8"))
            self.assertEqual(receipt["schema_version"], 3)
            self.assertEqual(set(receipt["assignments"]), set(NATIVE_ROLE_FILES["codex"]))

    def test_codex_default_matrix_matches_the_explicit_user_preference(self) -> None:
        self.assertEqual(
            {
                agent_name: (values[1], values[2])
                for agent_name, values in CODEX_DEFAULT_MATRIX.items()
            },
            {
                "designer": ("gpt-5.6-sol", "max"),
                "worker-routine": ("gpt-5.6-luna", "max"),
                "worker-standard": ("gpt-5.6-luna", "max"),
                "worker-complex": ("gpt-5.6-luna", "max"),
                "worker-critical": ("gpt-5.6-luna", "max"),
                "verifier": ("gpt-5.6-sol", "high"),
                "visual-verifier": ("gpt-5.6-sol", "high"),
                "reviewer": ("gpt-5.6-sol", "max"),
                "visual-reviewer": ("gpt-5.6-sol", "max"),
            },
        )
        self.assertEqual(
            dict(CODEX_FINDER_MATRIX),
            {
                "finder": ("gpt-5.3-codex-spark", "xhigh"),
                "fallback_finder": ("gpt-5.4-mini", "xhigh"),
            },
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            assignments = select_role_assignments(
                paths(Path(tmpdir)),
                "codex",
                excluded_names=NATIVE_ROLE_FILES["codex"],
            )

        self.assertEqual(set(assignments), CODEX_AGENT_NAMES)
        for agent_name, (role, model, effort, benchmark_id) in CODEX_DEFAULT_MATRIX.items():
            with self.subTest(agent_name=agent_name):
                assignment = assignments[agent_name]
                self.assertEqual(
                    (
                        assignment.role,
                        assignment.model,
                        assignment.reasoning_effort,
                        assignment.benchmark_id,
                        assignment.source,
                    ),
                    (role, model, effort, benchmark_id, "codex-default-matrix"),
                )
        for agent_name, (model, effort) in CODEX_FINDER_MATRIX.items():
            with self.subTest(agent_name=agent_name):
                assignment = assignments[agent_name]
                self.assertEqual(assignment.role, "finder")
                self.assertEqual((assignment.model, assignment.reasoning_effort), (model, effort))
                self.assertEqual(assignment.source, "codex-default-matrix")

    def test_codex_finder_templates_are_strictly_read_only_and_fallback_is_secondary(self) -> None:
        finder = (ROOT / "agents" / "codex" / "finder.toml").read_text(encoding="utf-8").lower()
        fallback = (ROOT / "agents" / "codex" / "fallback_finder.toml").read_text(encoding="utf-8").lower()
        for payload in (finder, fallback):
            self.assertIn('sandbox_mode = "read-only"', payload)
            self.assertIn("never write", payload)
            self.assertIn("concurrently", payload)
        self.assertIn("exhausted quota", fallback)
        self.assertIn("only when", fallback)

    def test_existing_local_model_configuration_wins_before_first_pin(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            install_paths = paths(Path(tmpdir))
            directory = install_paths.codex_home / "agents"
            directory.mkdir(parents=True)
            (directory / "user-agent.toml").write_text(
                'name = "user"\nmodel = "gpt-5.6-sol"\nmodel_reasoning_effort = "high"\n',
                encoding="utf-8",
            )
            assignments = select_role_assignments(
                install_paths,
                "codex",
                excluded_names=NATIVE_ROLE_FILES["codex"],
            )
            self.assertEqual(set(assignments), CODEX_AGENT_NAMES)
            local = [assignments[name] for name in DELIVERY_ROLE_NAMES]
            self.assertTrue(all(value.model == "gpt-5.6-sol" for value in local))
            self.assertTrue(all(value.reasoning_effort == "high" for value in local))
            self.assertTrue(all(value.source == "local-config" for value in local))
            self.assertTrue(
                all(assignments[name].source == "codex-default-matrix" for name in CODEX_FINDER_MATRIX)
            )
            install_role_templates(install_paths, "codex", dry_run=False)
            rendered_worker = (directory / "worker-routine.toml").read_text(encoding="utf-8")
            self.assertIn('model = "gpt-5.6-sol"', rendered_worker)
            self.assertIn('model_reasoning_effort = "high"', rendered_worker)

    def test_model_only_local_configuration_can_fill_intelligence_roles(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            install_paths = paths(Path(tmpdir))
            directory = install_paths.codex_home / "agents"
            directory.mkdir(parents=True)
            (directory / "user-agent.toml").write_text(
                'name = "user"\nmodel = "gemini-3-6-flash"\n',
                encoding="utf-8",
            )
            assignments = select_role_assignments(
                install_paths,
                "codex",
                excluded_names=NATIVE_ROLE_FILES["codex"],
            )
            self.assertEqual(set(assignments), CODEX_AGENT_NAMES)
            for role in ("designer", "verifier", "visual-verifier", "reviewer", "visual-reviewer"):
                self.assertEqual(assignments[role].model, "gemini-3-6-flash")
                self.assertIsNone(assignments[role].reasoning_effort)
                self.assertEqual(assignments[role].source, "local-config")
            for role in ("worker-routine", "worker-standard", "worker-complex", "worker-critical"):
                self.assertEqual(assignments[role].model, "gpt-5.6-luna")
                self.assertEqual(assignments[role].reasoning_effort, "max")
                self.assertEqual(assignments[role].source, "codex-default-matrix")
            messages = install_role_templates(install_paths, "codex", dry_run=False)
            self.assertTrue(any("host-default" in message for message in messages))
            rendered = (directory / "designer.toml").read_text(encoding="utf-8")
            self.assertIn('model = "gemini-3-6-flash"', rendered)
            self.assertNotIn("model_reasoning_effort", rendered)
            self.assertIn("reasoning_effort=host-default", rendered)

    def test_unspecified_local_effort_does_not_claim_a_tiered_intelligence_score(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            install_paths = paths(Path(tmpdir))
            directory = install_paths.codex_home / "agents"
            directory.mkdir(parents=True)
            (directory / "user-agent.toml").write_text(
                'name = "user"\nmodel = "gpt-5.6-sol"\n',
                encoding="utf-8",
            )

            assignments = select_role_assignments(
                install_paths,
                "codex",
                excluded_names=NATIVE_ROLE_FILES["codex"],
            )

            self.assertEqual(set(assignments), CODEX_AGENT_NAMES)
            for role in ("designer", "verifier", "visual-verifier", "reviewer", "visual-reviewer"):
                self.assertEqual(assignments[role].source, "codex-default-matrix")
            for role in (
                "worker-routine",
                "worker-standard",
                "worker-complex",
                "worker-critical",
            ):
                self.assertEqual(assignments[role].source, "codex-default-matrix")
                self.assertEqual(assignments[role].model, "gpt-5.6-luna")
                self.assertEqual(assignments[role].reasoning_effort, "max")

    def test_claude_visual_scope_keeps_code_and_vision_models_separate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            install_paths = paths(Path(tmpdir))
            directory = install_paths.claude_home / "agents"
            directory.mkdir(parents=True)
            (directory / "code-model.md").write_text(
                "---\nname: code-model\nmodel: deepseek-v4-flash\nreasoning_effort: max\n---\n",
                encoding="utf-8",
            )
            (directory / "vision-model.md").write_text(
                "---\nname: vision-model\nmodel: k3-256k\nreasoning_effort: max\n"
                "better_plan_scope: visual\n---\n",
                encoding="utf-8",
            )

            assignments = select_role_assignments(
                install_paths,
                "claude",
                excluded_names=NATIVE_ROLE_FILES["claude"],
            )

            for role in ("designer", "verifier", "reviewer"):
                self.assertEqual(assignments[role].model, "deepseek-v4-flash")
            for role in ("visual-verifier", "visual-reviewer"):
                self.assertEqual(assignments[role].model, "k3-256k")
                self.assertEqual(assignments[role].source, "local-config")

    def test_obsolete_receipt_is_rejected_without_translation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            install_paths = paths(Path(tmpdir))
            install_role_templates(install_paths, "codex", dry_run=False)
            receipt_path = install_paths.codex_home / "agents.better-plan.json"
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["schema_version"] = 2
            for filename in ("visual-verifier.toml", "visual-reviewer.toml"):
                receipt["files"].pop(filename)
                receipt["assignments"].pop(filename)
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

            with self.assertRaises(InstallError):
                install_role_templates(install_paths, "codex", dry_run=False)

    def test_update_keeps_the_original_assignment_even_if_new_local_models_appear(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            install_paths = paths(Path(tmpdir))
            install_role_templates(install_paths, "codex", dry_run=False)
            receipt_path = install_paths.codex_home / "agents.better-plan.json"
            before = json.loads(receipt_path.read_text(encoding="utf-8"))["assignments"]
            (install_paths.codex_home / "agents" / "later-user-agent.toml").write_text(
                'name = "later"\nmodel = "gpt-5.6-luna"\nmodel_reasoning_effort = "low"\n',
                encoding="utf-8",
            )
            install_role_templates(install_paths, "codex", dry_run=False)
            after = json.loads(receipt_path.read_text(encoding="utf-8"))["assignments"]
            self.assertEqual(before, after)

    def test_unmeasured_host_difficulty_is_omitted_instead_of_guessed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            assignments = select_role_assignments(paths(Path(tmpdir)), "cursor")
            self.assertEqual(set(assignments), {"worker-routine", "worker-standard"})

    def test_single_measured_opencode_model_can_fill_all_intelligence_roles(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            assignments = select_role_assignments(paths(Path(tmpdir)), "opencode")
            self.assertTrue({"designer", "verifier", "reviewer"}.issubset(assignments))
            self.assertTrue(
                all(assignments[role].benchmark_id == "muse-spark-1-1" for role in ("designer", "verifier", "reviewer"))
            )


if __name__ == "__main__":
    unittest.main()
