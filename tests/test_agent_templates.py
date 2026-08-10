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
from scripts.better_plan.installation.models import CURRENT_SKILL_FILES, InstallPaths
from scripts.better_plan.installation.targets import NATIVE_ROLE_FILES, install_role_templates


ROOT = Path(__file__).resolve().parents[1]
DELIVERY_ROLE_NAMES = {"designer", "worker-standard", "worker-complex", "reviewer"}
CODEX_AGENT_NAMES = DELIVERY_ROLE_NAMES | {"finder", "fallback_finder"}
REMOVED_ROLE_NAMES = {
    "worker-routine",
    "worker-critical",
    "visual-verifier",
    "visual-reviewer",
    "verifier",
}
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
                self.assertEqual({path.name for path in directory.iterdir()}, set(filenames))
                for filename in filenames:
                    text = (directory / filename).read_text(encoding="utf-8")
                    self.assertIn("ASSIGNMENT_PLACEHOLDER", text)
                    self.assertNotRegex(text, r"(?m)^model\s*[:=]")

    def test_removed_roles_are_absent_from_the_package(self) -> None:
        for name in REMOVED_ROLE_NAMES:
            with self.subTest(role=name):
                self.assertFalse(any(name in entry for entry in CURRENT_SKILL_FILES))
                self.assertEqual(list((ROOT / "agents").glob("*/%s.*" % name)), [])
                self.assertFalse((ROOT / "references" / ("%s.md" % name)).exists())

    def test_role_contracts_encode_single_writable_sessions(self) -> None:
        designer = (ROOT / "references" / "designer.md").read_text(encoding="utf-8").lower()
        worker = (ROOT / "references" / "worker.md").read_text(encoding="utf-8").lower()
        reviewer = " ".join(
            (ROOT / "references" / "reviewer.md").read_text(encoding="utf-8").lower().split()
        )
        self.assertIn("write the complete solution design", designer)
        self.assertIn("required output", designer)
        self.assertIn("do not write canonical", designer)
        self.assertIn("compiler is its sole write path", designer)
        self.assertIn("final return freezes", designer)
        self.assertIn("there is no second designer", designer)
        self.assertIn("one independently acceptable task", worker)
        self.assertIn("do not ask the user", worker)
        self.assertIn("economical tier", worker)
        self.assertIn("strong tier", worker)
        self.assertIn("directly repair every in-scope defect", reviewer)
        self.assertIn("there is no repair task and no second reviewer", reviewer)
        self.assertIn("rendered evidence", reviewer)
        self.assertIn("browser and vision", reviewer)
        self.assertIn("python owns that deterministic work in a separate `run-full-regression` stage", reviewer)
        self.assertIn("neither reviewer session command runs it", reviewer)

    def test_general_design_principles_preserve_progressive_role_disclosure(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        principles = (ROOT / "references" / "design-principles.md").read_text(
            encoding="utf-8"
        )
        normalized = " ".join(principles.lower().split())

        self.assertIn("references/design-principles.md", CURRENT_SKILL_FILES)
        self.assertIn("references/design-principles.md", skill)
        self.assertIn("only when maintaining or auditing better plan itself", skill.lower())
        self.assertIn("simple, clear, efficient, and economical", normalized)
        self.assertIn("strictly reject labyrinthine state machines", normalized)
        self.assertIn("use progressive disclosure", normalized)
        self.assertIn("smallest complete context", normalized)
        self.assertIn("do not inject this general reference into every leaf role", normalized)
        self.assertIn("spend scarce model intelligence on solution design", normalized)
        self.assertIn("python automation should convert", normalized)
        self.assertIn("make deterministic tools finish diagnostic work", normalized)
        self.assertIn("exact source line or line range", normalized)

        for role in ("designer", "worker", "reviewer"):
            relative = "references/%s.md" % role
            with self.subTest(role=role):
                self.assertIn(relative, CURRENT_SKILL_FILES)
                self.assertIn(relative, skill)
                self.assertTrue((ROOT / relative).is_file())

    def test_local_pattern_catalog_stays_complete_and_on_demand(self) -> None:
        catalog = (ROOT / "references" / "design-patterns.md").read_text(encoding="utf-8")
        numbered_headings = [
            line for line in catalog.splitlines() if line.startswith("### ") and ". " in line
        ]
        self.assertEqual(len(numbered_headings), 22)
        for pattern in CATALOG_PATTERNS:
            with self.subTest(pattern=pattern):
                self.assertEqual(
                    sum(f"（{pattern}）" in heading for heading in numbered_headings), 1
                )
        self.assertFalse(any("Interpreter" in heading for heading in numbered_headings))
        self.assertIn("references/design-patterns.md", CURRENT_SKILL_FILES)
        self.assertIn("references/host-configuration.md", CURRENT_SKILL_FILES)
        self.assertIn("references/workflow.md", CURRENT_SKILL_FILES)
        self.assertIn("references/design-format.md", CURRENT_SKILL_FILES)
        self.assertIn("references/structure-repair.md", CURRENT_SKILL_FILES)
        self.assertIn("scripts/better_plan/domain/design_compile.py", CURRENT_SKILL_FILES)
        self.assertIn("candidate: <模式英文名或 none>", catalog)
        self.assertIn("simpler_alternative", catalog)
        self.assertIn("costs_and_rejections", catalog)
        # Consulted on demand, never a mandatory full read before designing.
        self.assertIn("按需查阅的离线目录", catalog)
        self.assertNotIn("必须完整阅读", catalog)

    def test_host_guidance_separates_framework_invariants_from_native_adapters(self) -> None:
        guidance = " ".join(
            (ROOT / "references" / "host-configuration.md")
            .read_text(encoding="utf-8")
            .lower()
            .split()
        )

        self.assertIn("framework and adapter boundary", guidance)
        self.assertIn("exact opaque identity preservation", guidance)
        self.assertIn("fix defects in those invariants once in the framework", guidance)
        self.assertIn("a host adapter owns only behavior imposed by that host's api", guidance)
        self.assertIn("adding or changing one must not alter another host", guidance)
        self.assertIn("immutable local host configuration", guidance)
        self.assertIn("explicit replacement request", guidance)
        self.assertIn("doctor reports the integrity finding as a warning without a repair proposal", guidance)
        self.assertIn("fork_turns", guidance)
        self.assertIn("not plain openai-compatible message forwarding", guidance)
        self.assertIn("agent_message", guidance)
        self.assertIn("encrypted_content", guidance)
        self.assertIn("an openai-compatible label alone is insufficient", guidance)
        self.assertIn("never strips, decrypts, or downgrades this payload to plaintext", guidance)
        self.assertIn("codex has no better plan completion hook", guidance)

    def test_every_native_designer_template_owns_the_single_design_session(self) -> None:
        source_target = {"claude": "claude-code"}
        for target, filenames in NATIVE_ROLE_FILES.items():
            designer_filename = next(name for name in filenames if Path(name).stem == "designer")
            template = (
                ROOT / "agents" / source_target.get(target, target) / designer_filename
            ).read_text(encoding="utf-8").lower()
            with self.subTest(target=target):
                self.assertIn("design.md", template)
                self.assertIn("required output", template)
                self.assertIn("do not write canonical codes", template)
                self.assertIn("python compiles", template)
                self.assertIn("native main completes", template)
                self.assertIn("return freezes", template)
                self.assertIn("there is no second designer", template)
                self.assertRegex(template, r"do not [^.]*ask the user")
                self.assertIn("does not pre-design tasks", template)
                self.assertIn("mutually parallel-safe", template)
                self.assertIn("minimal node dag", template)
                self.assertRegex(template, r"empty .*prerequisites.*inputs")

    def test_every_native_worker_template_is_a_fresh_context_task_contract(self) -> None:
        source_target = {"claude": "claude-code"}
        for target, filenames in NATIVE_ROLE_FILES.items():
            directory = ROOT / "agents" / source_target.get(target, target)
            for filename in filenames:
                stem = Path(filename).stem
                if not stem.startswith("worker-"):
                    continue
                template = (directory / filename).read_text(encoding="utf-8").lower()
                with self.subTest(target=target, filename=filename):
                    self.assertIn("independently acceptable task", template)
                    self.assertIn("freely inspect better plan guidance", template)
                    self.assertIn("no local guidance is forbidden", template)
                    self.assertIn("do not ask the user", template)
                    self.assertIn("every ready task node concurrently", template)
                    expected_tier = "economical tier" if stem == "worker-standard" else "strong tier"
                    self.assertIn(expected_tier, template)

    def test_every_native_reviewer_template_absorbs_rendered_evidence(self) -> None:
        source_target = {"claude": "claude-code"}
        for target, filenames in NATIVE_ROLE_FILES.items():
            reviewer_filename = next(name for name in filenames if Path(name).stem == "reviewer")
            template = (
                ROOT / "agents" / source_target.get(target, target) / reviewer_filename
            ).read_text(encoding="utf-8").lower()
            with self.subTest(target=target):
                self.assertIn("visual or hybrid", template)
                self.assertIn("rendered evidence", template)
                self.assertIn("no second reviewer", template)
                self.assertIn("separate full-regression stage has already completed", template)
                self.assertIn("reviewer session commands never run it", template)
                self.assertIn("do not run or wait for the complete regression", template)

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
            assignment_message = next(
                message for message in messages if "pinned until explicit reinstall" in message
            )
            self.assertIn("Coding Agent", assignment_message)
            self.assertIn("Intelligence Index", assignment_message)
            self.assertIn("Codex read-only utility", assignment_message)
            self.assertIn("price ignored", assignment_message)
            self.assertIn("source codex-default-matrix", assignment_message)
            self.assertNotIn("Arena WebDev", assignment_message)
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
                "designer": ("gpt-5.6-sol", "xhigh"),
                "worker-standard": ("gpt-5.6-luna", "max"),
                "worker-complex": ("gpt-5.6-sol", "medium"),
                "reviewer": ("gpt-5.6-sol", "max"),
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

    def test_codex_workers_fail_closed_when_the_task_payload_is_absent(self) -> None:
        for role in ("worker-standard", "worker-complex"):
            template = (ROOT / "agents" / "codex" / f"{role}.toml").read_text(
                encoding="utf-8"
            )
            with self.subTest(role=role):
                self.assertIn("Payload has no visible actionable Task", template)
                self.assertIn("do not inspect the workspace or call tools", template)
                self.assertIn("payload-delivery-failed", template)

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
            rendered_worker = (directory / "worker-standard.toml").read_text(encoding="utf-8")
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
            for role in ("designer", "reviewer"):
                self.assertEqual(assignments[role].model, "gemini-3-6-flash")
                self.assertIsNone(assignments[role].reasoning_effort)
                self.assertEqual(assignments[role].source, "local-config")
            for role in ("worker-standard", "worker-complex"):
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
            for role in DELIVERY_ROLE_NAMES:
                self.assertEqual(assignments[role].source, "codex-default-matrix")

    def test_obsolete_receipt_is_reported_without_translation_or_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            install_paths = paths(Path(tmpdir))
            install_role_templates(install_paths, "codex", dry_run=False)
            receipt_path = install_paths.codex_home / "agents.better-plan.json"
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["schema_version"] = 2
            for filename in ("worker-standard.toml", "worker-complex.toml"):
                receipt["files"].pop(filename)
                receipt["assignments"].pop(filename)
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

            before = receipt_path.read_bytes()
            messages = install_role_templates(install_paths, "codex", dry_run=False)

            self.assertEqual(messages, ["native: preserved codex role templates"])
            self.assertEqual(receipt_path.read_bytes(), before)

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

    def test_cursor_defaults_recommend_measured_grok_workers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            assignments = select_role_assignments(paths(Path(tmpdir)), "cursor")
            self.assertEqual(set(assignments), {"worker-standard", "worker-complex"})
            for role in assignments:
                assignment = assignments[role]
                self.assertEqual(
                    (assignment.model, assignment.reasoning_effort, assignment.benchmark_id),
                    ("cursor-grok-4.5-high-fast", "high", "grok-build-grok-4-5-high"),
                )
                self.assertEqual(assignment.source, "cursor-default-matrix")

    def test_unmeasured_host_difficulty_is_omitted_instead_of_guessed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            assignments = select_role_assignments(paths(Path(tmpdir)), "opencode")
            self.assertNotIn("worker-complex", assignments)

    def test_single_measured_opencode_model_can_fill_all_intelligence_roles(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            assignments = select_role_assignments(paths(Path(tmpdir)), "opencode")
            self.assertTrue({"designer", "reviewer"}.issubset(assignments))
            self.assertTrue(
                all(assignments[role].benchmark_id == "muse-spark-1-1" for role in ("designer", "reviewer"))
            )


if __name__ == "__main__":
    unittest.main()
