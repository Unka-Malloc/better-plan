"""Installation, Doctor, and uninstall for the five supported hosts."""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.better_plan.adapters import install_cli
from scripts.better_plan.installation import doctor as install_doctor
from scripts.better_plan.installation import models as install_models
from scripts.better_plan.installation import service as install_service
from scripts.better_plan.installation import targets as install_targets
from scripts.better_plan.installation.assignments import CODEX_DEFAULT_MATRIX
from scripts.better_plan.installation.models import Check


REPO_ROOT = Path(__file__).resolve().parents[1]
ROLES = ("designer", "worker", "reviewer", "verifier", "adversary")


def make_paths(root: Path, repo_root: Path = REPO_ROOT) -> install_models.InstallPaths:
    home = root / "home"
    return install_models.InstallPaths(
        repo_root=repo_root,
        codex_home=home / ".codex",
        shared_home=home / ".agents",
        claude_home=home / ".claude",
        cursor_home=home / ".cursor",
        kilo_home=home / ".kilo",
        kilo_config=home / ".config" / "kilo",
    )


class InstallTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.paths = make_paths(Path(self.temporary.name))

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def install_all(self, dry_run: bool = False) -> list[str]:
        return install_service.install_agents(
            self.paths, list(install_models.AGENTS), dry_run=dry_run
        )

    def protected_role_state(self) -> list[Path]:
        """Every protected artifact: role files and managed receipts."""

        return [
            *[self.paths.codex_home / "agents" / ("%s.toml" % role) for role in ROLES],
            *[self.paths.claude_home / "agents" / ("%s.md" % role) for role in ROLES],
            *[self.paths.cursor_home / "agents" / ("%s.md" % role) for role in ROLES],
            *[self.paths.kilo_agents / name for name in install_targets.KILO_AGENT_FILES],
            install_targets._native_receipt_path(self.paths.codex_home / "agents"),
            install_targets._native_receipt_path(self.paths.kilo_agents),
            install_targets._native_receipt_path(self.paths.claude_home / "agents"),
            install_targets._native_receipt_path(self.paths.cursor_home / "agents"),
        ]

    def test_a_fresh_install_writes_the_shared_skill_and_five_roles(self) -> None:
        self.install_all()
        self.assertTrue((self.paths.shared_skill / "SKILL.md").is_file())
        for role in ROLES:
            with self.subTest(role=role):
                self.assertTrue((self.paths.codex_home / "agents" / ("%s.toml" % role)).is_file())
                self.assertTrue((self.paths.claude_home / "agents" / ("%s.md" % role)).is_file())
                self.assertTrue((self.paths.cursor_home / "agents" / ("%s.md" % role)).is_file())

    def test_no_removed_role_file_is_ever_written(self) -> None:
        self.install_all()
        for host in ("codex", "claude", "cursor"):
            directory = install_targets._native_role_directory(self.paths, host)
            for removed in ("hybrid-worker", "worker-standard", "worker-critical"):
                with self.subTest(host=host, role=removed):
                    self.assertFalse((directory / removed).with_suffix(".toml").exists())
                    self.assertFalse((directory / removed).with_suffix(".md").exists())

    def test_codex_records_the_three_preset_assignments(self) -> None:
        self.install_all()
        receipt = install_targets._load_native_receipt(
            install_targets._native_receipt_path(self.paths.codex_home / "agents"), "codex"
        )
        self.assertIsNotNone(receipt)
        assert receipt is not None
        self.assertEqual(set(receipt["assignments"]), set(ROLES))
        for role in CODEX_DEFAULT_MATRIX:
            with self.subTest(role=role):
                self.assertEqual(receipt["assignments"][role].model, CODEX_DEFAULT_MATRIX[role][1])
                prompt = (self.paths.codex_home / "agents" / ("%s.toml" % role)).read_text(
                    encoding="utf-8"
                )
                instructions = prompt.split('developer_instructions = """', 1)[1].split(
                    '\n"""', 1
                )[0]
                self.assertNotIn("assignment:", instructions.lower())
                self.assertNotIn("reasoning_effort", instructions)
                self.assertNotIn("model=", instructions)

    def test_additive_roles_inherit_host_defaults_without_invented_provenance(self) -> None:
        self.install_all()
        receipt = install_targets._load_native_receipt(
            install_targets._native_receipt_path(self.paths.codex_home / "agents"), "codex"
        )
        for role in ("verifier", "adversary"):
            path = self.paths.codex_home / "agents" / f"{role}.toml"
            document = install_targets.tomllib.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(document["name"], role)
            self.assertNotIn("model", document)
            self.assertNotIn("model_reasoning_effort", document)
            self.assertIn(f"references/{role}.md", document["developer_instructions"])
            assignment = receipt["assignments"][role]
            self.assertEqual(assignment.source, "host-default")
            for field in ("model", "reasoning_effort", "benchmark_id", "index_score", "cost_per_task_usd"):
                self.assertIsNone(getattr(assignment, field))
            self.assertTrue((self.paths.shared_skill / "references" / f"{role}.md").is_file())
        checks = {item.target: item for item in install_doctor.doctor(self.paths, ["claude", "cursor"])}
        for host in ("claude", "cursor"):
            self.assertEqual(checks[host + " role receipt"].status, "OK")

    def test_three_role_legacy_matrices_add_both_profiles_and_refresh_receipts(self) -> None:
        self.install_all()
        # Represent the previously shipped file sets and provenance faithfully.
        for host in ("codex", "claude", "cursor", "kilo"):
            directory = (self.paths.kilo_agents if host == "kilo" else
                         install_targets._native_role_directory(self.paths, host))
            receipt_path = install_targets._native_receipt_path(directory)
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            for role in ("verifier", "adversary"):
                filename = install_targets._role_filename(host, role)
                (directory / filename).unlink()
                receipt["files"].pop(filename)
                if "assignments" in receipt:
                    receipt["assignments"].pop(filename)
            if host in ("claude", "cursor"):
                receipt_path.unlink()
            else:
                receipt_path.write_text(json.dumps(receipt) + "\n", encoding="utf-8")
            for path in directory.iterdir():
                # Mutate prompts only, not untouched host-owned newline bytes.
                path.write_bytes(path.read_bytes().replace(
                    b"You are the", b"Outdated prompt: You are the"
                ))
        before = {path: path.read_bytes() for path in self.protected_role_state() if path.exists()}
        self.install_all(dry_run=True)
        self.assertEqual({path: path.read_bytes() for path in self.protected_role_state() if path.exists()}, before)
        messages = self.install_all()
        self.assertEqual(sum("added missing profile" in message for message in messages), 8)
        self.assertTrue(all(path.exists() for path in self.protected_role_state()))
        for host in ("codex", "kilo", "claude", "cursor"):
            self.assertEqual(install_targets.role_receipt_status(self.paths, host)[0], True)
        for host in ("codex", "claude", "cursor"):
            ok, message = install_targets.native_role_status(self.paths, host)
            if host == "codex":
                self.assertTrue(ok, message)
            else:
                # Raw line endings remain host-owned; compare prompt content without
                # requiring byte equality with the LF-only packaged templates.
                directory = install_targets._native_role_directory(self.paths, host)
                for name, expected in install_targets.unpinned_role_payload(self.paths, host).items():
                    self.assertEqual((directory / name).read_text(encoding="utf-8"),
                                     expected.decode("utf-8"))
        self.assertTrue(install_targets.kilo_agent_status(self.paths)[0])

    def legacy_receipted_matrix(self, host: str) -> tuple[Path, Path, dict]:
        install_service.install_agents(self.paths, [host], dry_run=False)
        directory = (self.paths.kilo_agents if host == "kilo" else
                     install_targets._native_role_directory(self.paths, host))
        filename = install_targets._role_filename(host, "adversary")
        (directory / filename).unlink()
        receipt_path = install_targets._native_receipt_path(directory)
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["files"].pop(filename)
        if "assignments" in receipt:
            receipt["assignments"].pop(filename)
        receipt_path.write_text(json.dumps(receipt) + "\n", encoding="utf-8")
        return directory, receipt_path, receipt

    def test_four_role_upgrade_preserves_custom_fields_and_original_provenance(self) -> None:
        for host in ("codex", "kilo", "claude", "cursor"):
            directory, receipt_path, receipt = self.legacy_receipted_matrix(host)
            worker = directory / install_targets._role_filename(host, "verifier")
            text = worker.read_text(encoding="utf-8")
            text = (text.replace('sandbox_mode = ', 'model = "local-choice"\nsandbox_mode = ') if host == "codex"
                    else text.replace("\n---\n", "\nmodel: local-choice\n---\n", 1))
            if host == "codex":
                receipt["assignments"]["worker.toml"]["index_basis"] = "intelligence"
                receipt_path.write_text(json.dumps(receipt) + "\n", encoding="utf-8")
            worker.write_text(text, encoding="utf-8")
            before = {path.name: path.read_bytes() for path in directory.iterdir()}
            messages = install_service.install_agents(self.paths, [host], dry_run=False)
            self.assertIn("added missing profile", " ".join(messages))
            for name, content in before.items():
                self.assertEqual((directory / name).read_bytes(), content)
            updated = json.loads(receipt_path.read_text(encoding="utf-8"))
            for key in ("files", "assignments"):
                for name, value in receipt.get(key, {}).items():
                    self.assertEqual(updated[key][name], value)
            self.assertFalse(install_targets.role_receipt_status(self.paths, host)[0])

    def test_uncertain_receipts_never_authorize_adversary_addition(self) -> None:
        for host in ("codex", "kilo", "claude", "cursor"):
            directory, receipt_path, _ = self.legacy_receipted_matrix(host)
            for broken in (("invalid receipt",) if host in ("claude", "cursor") else
                           (None, "invalid receipt")):
                if broken is None:
                    receipt_path.unlink()
                else:
                    receipt_path.write_text(broken, encoding="utf-8")
                before = {path.name: path.read_bytes() for path in directory.iterdir()}
                messages = install_service.install_agents(self.paths, [host], dry_run=False)
                self.assertIn("receipt", " ".join(messages))
                self.assertEqual({path.name: path.read_bytes() for path in directory.iterdir()}, before)

    def test_custom_adversary_collisions_are_reported_without_refresh_or_adoption(self) -> None:
        for host in ("codex", "kilo", "claude", "cursor"):
            directory, receipt_path, _ = self.legacy_receipted_matrix(host)
            filename = install_targets._role_filename(host, "adversary")
            custom = directory / filename
            source_host = "claude-code" if host == "claude" else host
            source = (REPO_ROOT / "agents" / source_host / filename).read_text(encoding="utf-8")
            custom.write_text(source.replace("You are the", "Custom instruction: You are the"),
                              encoding="utf-8")
            before = custom.read_bytes(), receipt_path.read_bytes()
            messages = install_service.install_agents(self.paths, [host], dry_run=False)
            self.assertIn("collision", " ".join(messages))
            self.assertEqual((custom.read_bytes(), receipt_path.read_bytes()), before)
            if host == "codex":
                renamed = directory / "my-own-adversary.toml"
                custom.rename(renamed)
                messages = install_service.install_agents(self.paths, [host], dry_run=False)
                self.assertIn("collision", " ".join(messages))
                self.assertFalse(custom.exists())
                self.assertEqual((renamed.read_bytes(), receipt_path.read_bytes()), before)

    def test_renamed_unpinned_role_prevents_fresh_install_collision(self) -> None:
        for host in ("claude", "cursor"):
            directory = install_targets._native_role_directory(self.paths, host)
            directory.mkdir(parents=True)
            custom = directory / "my-auditor.md"
            content = b'---\nname: "adversary"\nmodel: my-model\n---\nMy custom instructions\n'
            custom.write_bytes(content)
            messages = install_service.install_agents(self.paths, [host], dry_run=False)
            self.assertIn("Adversary", " ".join(messages))
            self.assertIn("collision", " ".join(messages))
            self.assertEqual(list(directory.iterdir()), [custom])
            self.assertEqual(custom.read_bytes(), content)
            self.assertFalse(install_targets._native_receipt_path(directory).exists())

    def test_oversized_codex_identity_prevents_fresh_install_collision(self) -> None:
        directory = self.paths.codex_home / "agents"
        directory.mkdir(parents=True)
        custom = directory / "my-auditor.toml"
        from scripts.better_plan.infrastructure.native_roles import MAX_ROLE_FILE_BYTES
        content = ('name = "adversary"\n# ' + "x" * MAX_ROLE_FILE_BYTES + "\n").encode("utf-8")
        self.assertEqual(install_targets.tomllib.loads(content.decode("utf-8"))["name"], "adversary")
        custom.write_bytes(content)
        messages = install_service.install_agents(self.paths, ["codex"], dry_run=False)
        self.assertIn("unreadable or ambiguous", " ".join(messages))
        self.assertEqual(list(directory.iterdir()), [custom])
        self.assertEqual(custom.read_bytes(), content)
        self.assertFalse(install_targets._native_receipt_path(directory).exists())

    def test_receipt_symlink_cannot_authorize_additive_upgrade(self) -> None:
        directory, receipt_path, _ = self.legacy_receipted_matrix("codex")
        external = receipt_path.with_name("external-receipt.json")
        receipt_path.rename(external)
        try:
            receipt_path.symlink_to(external)
        except OSError:
            self.skipTest("symlink creation unavailable")
        before = external.read_bytes()
        messages = install_service.install_agents(self.paths, ["codex"], dry_run=False)
        self.assertIn("valid legacy receipt required", " ".join(messages))
        self.assertFalse((directory / "adversary.toml").exists())
        self.assertEqual(external.read_bytes(), before)

    def test_unreceipted_unpinned_verifier_is_never_adopted(self) -> None:
        for host in ("claude", "cursor"):
            install_service.install_agents(self.paths, [host], dry_run=False)
            directory = install_targets._native_role_directory(self.paths, host)
            install_targets._native_receipt_path(directory).unlink()
            verifier = directory / "verifier.md"
            verifier.write_text(verifier.read_text(encoding="utf-8").replace(
                "You are the", "My custom instructions: You are the"), encoding="utf-8")
            before = verifier.read_bytes()
            messages = install_service.install_agents(self.paths, [host], dry_run=False)
            self.assertIn("collision", " ".join(messages))
            self.assertEqual(verifier.read_bytes(), before)
            self.assertFalse(install_targets._native_receipt_path(directory).exists())

    def test_renamed_unpinned_adversary_blocks_addition_and_receipt_creation(self) -> None:
        for host in ("claude", "cursor"):
            install_service.install_agents(self.paths, [host], dry_run=False)
            directory = install_targets._native_role_directory(self.paths, host)
            receipt_path = install_targets._native_receipt_path(directory)
            receipt_path.unlink()
            adversary = directory / "adversary.md"
            renamed = directory / "my-custom-adversary.md"
            adversary.rename(renamed)
            renamed.write_text(renamed.read_text(encoding="utf-8").replace(
                "name: adversary", 'name: "adversary"').replace(
                "You are the", "My custom instructions: You are the"), encoding="utf-8")
            before = renamed.read_bytes()
            messages = install_service.install_agents(self.paths, [host], dry_run=False)
            self.assertIn("collision", " ".join(messages))
            self.assertEqual(renamed.read_bytes(), before)
            self.assertFalse(adversary.exists())
            self.assertFalse(receipt_path.exists())

    def test_ambiguous_unpinned_native_identity_blocks_verifier_addition(self) -> None:
        install_service.install_agents(self.paths, ["claude"], dry_run=False)
        directory = self.paths.claude_home / "agents"
        receipt_path = install_targets._native_receipt_path(directory)
        receipt_path.unlink()
        (directory / "verifier.md").unlink()
        custom = directory / "custom.md"
        custom.write_text("---\nname: >-\n  verifier\n---\nCustom instructions\n", encoding="utf-8")
        before = custom.read_bytes()
        messages = install_service.install_agents(self.paths, ["claude"], dry_run=False)
        self.assertIn("unreadable or ambiguous", " ".join(messages))
        self.assertEqual(custom.read_bytes(), before)
        self.assertFalse((directory / "verifier.md").exists())
        self.assertFalse(receipt_path.exists())

    def test_prompt_refresh_preserves_raw_host_newlines_and_hashes_written_bytes(self) -> None:
        for host, filename, format in (("codex", "verifier.toml", "codex"),
                                       ("claude-code", "verifier.md", "markdown")):
            expected = (REPO_ROOT / "agents" / host / filename).read_text(encoding="utf-8")
            original = expected.replace("You are the", "Old prompt: You are the").replace("\n", "\r\n")
            if format == "codex":
                marker = 'sandbox_mode = "workspace-write"\r\n'
                fields = marker + 'model = "custom"\nlocal_key = "preserve"\r\n'
            else:
                marker = 'tools: Read, Edit, Write, Glob, Grep, Bash\r\n'
                fields = marker + 'model: custom\nlocal_key: preserve\r\n'
            original = original.replace(marker, fields).encode("utf-8")
            destination = Path(self.temporary.name) / host
            destination.mkdir()
            path = destination / filename
            path.write_bytes(original)
            changed, digests, complete = install_targets._refresh_prompt_files(
                destination, {filename: expected}, format=format, dry_run=True)
            self.assertEqual(path.read_bytes(), original)
            changed, digests, complete = install_targets._refresh_prompt_files(
                destination, {filename: expected}, format=format, dry_run=False)
            written = path.read_bytes()
            self.assertTrue(complete)
            self.assertEqual(changed, [filename])
            self.assertIn(fields.encode("utf-8"), written)
            self.assertNotIn(b"Old prompt", written)
            self.assertEqual(written, original.replace(b"Old prompt: ", b""))
            self.assertEqual(digests[filename], install_targets._content_digest(written))
            changed, digests, _ = install_targets._refresh_prompt_files(
                destination, {filename: expected}, format=format, dry_run=False)
            self.assertEqual(changed, [])
            self.assertEqual(path.read_bytes(), written)
            self.assertEqual(digests[filename], install_targets._content_digest(written))

    def test_adversary_refresh_preserves_custom_host_fields_byte_for_byte(self) -> None:
        self.install_all()
        for host in ("codex", "claude", "cursor", "kilo"):
            directory = (self.paths.kilo_agents if host == "kilo" else
                         install_targets._native_role_directory(self.paths, host))
            filename = install_targets._role_filename(host, "adversary")
            path = directory / filename
            original = path.read_text(encoding="utf-8")
            if host == "codex":
                custom = original.replace('sandbox_mode = "read-only"',
                    'sandbox_mode = "local-sandbox"\nmodel = "custom"\n'
                    'model_reasoning_effort = "medium"\nprovider = "local"\ncustom_key = 42')
            else:
                custom = original.replace("\n---\n", "\nmodel: custom\nvariant: local\n"
                    "reasoning_effort: medium\ncustom_key: 42\n---\n", 1)
            path.write_text(custom.replace("You are the", "Outdated prompt: You are the"),
                            encoding="utf-8")
            install_service.install_agents(self.paths, [host], dry_run=False)
            self.assertEqual(path.read_text(encoding="utf-8"), custom)

    def test_a_local_role_without_a_prompt_structure_is_left_untouched(self) -> None:
        agents = self.paths.codex_home / "agents"
        agents.mkdir(parents=True)
        local = agents / "worker.toml"
        local.write_text('name = "worker"\nmodel = "my-own-model"\n', encoding="utf-8")
        before = local.read_bytes()

        self.install_all()

        self.assertEqual(local.read_bytes(), before)
        self.assertIn(
            "native: preserved codex role templates",
            install_service.install_agents(self.paths, ["codex"], dry_run=False),
        )

    def test_unpinned_hosts_get_no_selector(self) -> None:
        self.install_all()
        for host in ("claude", "cursor"):
            for role in ROLES:
                with self.subTest(host=host, role=role):
                    text = (
                        install_targets._native_role_directory(self.paths, host) / ("%s.md" % role)
                    ).read_text(encoding="utf-8")
                    self.assertNotIn("assignment:", text)
                    self.assertNotIn("Pinned identity", text)
                    self.assertNotIn("host-inherited", text)
                    self.assertNotIn("model =", text)
                    self.assertNotIn("reasoning_effort", text)

    def test_deepseek_harness_installs_the_skill_only(self) -> None:
        messages = install_service.install_agents(self.paths, ["dsh"], dry_run=False)
        self.assertTrue((self.paths.shared_skill / "SKILL.md").is_file())
        self.assertIn("skill only", " ".join(messages))
        self.assertFalse((self.paths.codex_home / "agents").exists())

    def test_kilo_installs_one_primary_and_five_subagents(self) -> None:
        install_service.install_agents(self.paths, ["kilo"], dry_run=False)
        agents = self.paths.kilo_agents
        self.assertTrue((agents / "better-plan.md").is_file())
        primary = (agents / "better-plan.md").read_text(encoding="utf-8")
        self.assertIn("understand the user's requested outcome", primary.lower())
        self.assertNotIn("assignment:", primary)
        for role in ROLES:
            with self.subTest(role=role):
                path = agents / ("better-plan-%s.md" % role)
                self.assertTrue(path.is_file())
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("assignment:", text)
                self.assertNotIn("model=", text)
                self.assertNotIn("reasoning_effort=", text)

    def test_doctor_reports_only_a_real_duplicate_native_skill(self) -> None:
        self.install_all()

        # DeepSeek Harness has no native skill tree, so its own path *is* the shared
        # directory: that is not a duplicate, and Doctor must not warn about it.
        dsh_checks = install_doctor.doctor(self.paths, ["dsh"])
        self.assertNotIn(
            "duplicate",
            " ".join(check.message for check in dsh_checks),
            dsh_checks,
        )

        # A host with its own skill path keeps a real duplicate until install removes it.
        duplicate = self.paths.kilo_skill
        duplicate.parent.mkdir(parents=True, exist_ok=True)
        duplicate.mkdir()
        (duplicate / "SKILL.md").write_text("stale", encoding="utf-8")
        warnings = [
            check
            for check in install_doctor.doctor(self.paths, ["kilo"])
            if check.status == "WARN"
        ]
        self.assertTrue(
            any("duplicate native skill" in check.message for check in warnings),
            warnings,
        )

    def test_doctor_passes_for_a_fresh_install_and_fails_without_one(self) -> None:
        empty = install_doctor.doctor(self.paths, ["dsh"])
        self.assertTrue(any(check.status == "FAIL" for check in empty), empty)

        self.install_all()
        # Doctor may validate a host CLI when one is installed; the check itself must
        # not depend on what this machine happens to have.
        with mock.patch.object(install_doctor.shutil, "which", return_value=None):
            checks = install_doctor.doctor(self.paths, list(install_models.AGENTS))
        failures = [check for check in checks if check.status == "FAIL"]
        self.assertEqual(failures, [], failures)
        self.assertTrue(any(check.status == "WARN" for check in checks), checks)

    def test_doctor_separates_receipts_templates_and_skill_without_rewriting_roles(self) -> None:
        self.install_all()
        original = self.protected_role_state()
        before = {path: path.read_bytes() for path in original}
        sources = install_targets._validate_native_sources(self.paths, "codex")
        sources["worker"] = sources["worker"].replace("You are the", "Current template: You are the")
        with mock.patch.object(install_targets, "_validate_native_sources", return_value=sources):
            checks = {item.target: item for item in install_doctor.doctor(self.paths, ["codex"])}
        self.assertEqual(checks["codex role receipt"].status, "OK")
        self.assertEqual(checks["codex role templates"].status, "WARN")
        self.assertIn("does not establish", checks["codex role templates"].message)
        self.assertEqual(checks["shared skill source"].status, "OK")
        self.assertEqual({path: path.read_bytes() for path in original}, before)
        # A user-owned selector change affects integrity, but not the instruction comparison.
        worker = self.paths.codex_home / "agents" / "worker.toml"
        worker.write_text(worker.read_text(encoding="utf-8").replace('model = "gpt-6-luna"', 'model = "local-choice"'), encoding="utf-8")
        custom = worker.read_bytes()
        checks = {item.target: item for item in install_doctor.doctor(self.paths, ["codex"])}
        self.assertEqual(checks["codex role receipt"].status, "WARN")
        self.assertEqual(checks["codex role templates"].status, "OK")
        self.assertEqual(worker.read_bytes(), custom)
        self.assertEqual({path: path.read_bytes() for path in original if path != worker},
                         {path: value for path, value in before.items() if path != worker})

    def test_uninstall_removes_the_skill_and_keeps_local_roles(self) -> None:
        self.install_all()
        role = self.paths.codex_home / "agents" / "worker.toml"
        before = role.read_bytes()

        install_service.uninstall_agents(
            self.paths, list(install_models.AGENTS), remove_shared=True, dry_run=False
        )

        self.assertFalse(self.paths.shared_skill.exists())
        self.assertEqual(role.read_bytes(), before)

    def test_an_update_refreshes_role_prompts_and_preserves_local_configuration(self) -> None:
        source = Path(self.temporary.name) / "source"
        shutil.copytree(
            REPO_ROOT, source, ignore=shutil.ignore_patterns(".git", "__pycache__", ".kilo")
        )
        paths = make_paths(Path(self.temporary.name), repo_root=source)
        install_service.install_agents(paths, list(install_models.AGENTS), dry_run=False)

        worker = paths.codex_home / "agents" / "worker.toml"
        worker.write_text(
            worker.read_text(encoding="utf-8")
            .replace('model = "gpt-6-luna"', 'model = "local-choice"')
            .replace('model_reasoning_effort = "max"', 'model_reasoning_effort = "medium"')
            .replace('sandbox_mode = "workspace-write"', 'sandbox_mode = "local-sandbox"')
            + 'model_provider = "local-provider"\ncustom_local = "keep-me"\n',
            encoding="utf-8",
        )
        claude = paths.claude_home / "agents" / "designer.md"
        claude.write_text(
            claude.read_text(encoding="utf-8").replace(
                "  bash: allow", "  bash: allow\n  custom: keep"
            ).replace(
                "tools: Read, Edit, Write, Glob, Grep, Bash",
                "tools: Read, Write, Bash, LocalTool",
            ),
            encoding="utf-8",
        )
        kilo = paths.kilo_agents / "better-plan-reviewer.md"
        kilo.write_text(
            kilo.read_text(encoding="utf-8")
            .replace("  edit: allow", "  edit: deny\n  local_permission: keep")
            .replace("temperature: 0.1", "temperature: 0.7"),
            encoding="utf-8",
        )

        for relative in (
            "agents/codex/worker.toml",
            "agents/claude-code/designer.md",
            "agents/kilo/better-plan-reviewer.md",
        ):
            template = source / relative
            template.write_text(
                template.read_text(encoding="utf-8").replace(
                    "You are the", "Updated prompt: You are the"
                ),
                encoding="utf-8",
            )

        install_service.install_agents(paths, list(install_models.AGENTS), dry_run=False)

        worker_text = worker.read_text(encoding="utf-8")
        self.assertIn('model = "local-choice"', worker_text)
        self.assertIn('model_reasoning_effort = "medium"', worker_text)
        self.assertIn('sandbox_mode = "local-sandbox"', worker_text)
        self.assertIn('model_provider = "local-provider"', worker_text)
        self.assertIn('custom_local = "keep-me"', worker_text)
        self.assertIn("Updated prompt: You are the", worker_text)
        claude_text = claude.read_text(encoding="utf-8")
        self.assertIn("custom: keep", claude_text)
        self.assertIn("tools: Read, Write, Bash, LocalTool", claude_text)
        self.assertIn("Updated prompt: You are the", claude_text)
        kilo_text = kilo.read_text(encoding="utf-8")
        self.assertIn("edit: deny", kilo_text)
        self.assertIn("local_permission: keep", kilo_text)
        self.assertIn("temperature: 0.7", kilo_text)
        self.assertIn("Updated prompt: You are the", kilo_text)

        checks = {item.target: item for item in install_doctor.doctor(paths, ["codex", "kilo"])}
        self.assertEqual(checks["codex role templates"].status, "OK")
        self.assertEqual(checks["codex role receipt"].status, "OK")
        self.assertEqual(checks["kilo role receipt"].status, "OK")

    def test_prompt_refresh_keeps_unrelated_receipt_drift_and_legacy_provenance(self) -> None:
        install_service.install_agents(self.paths, ["codex"], dry_run=False)
        directory = self.paths.codex_home / "agents"
        receipt_path = install_targets._native_receipt_path(directory)
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["assignments"]["worker.toml"]["index_basis"] = "intelligence"
        receipt_path.write_text(json.dumps(receipt) + "\n", encoding="utf-8")
        worker = directory / "worker.toml"
        worker.write_text(worker.read_text(encoding="utf-8").replace(
            'model = "gpt-6-luna"', 'model = "local-choice"'), encoding="utf-8")
        adversary = directory / "adversary.toml"
        adversary.write_text(adversary.read_text(encoding="utf-8").replace(
            "You are the", "Outdated: You are the"), encoding="utf-8")
        install_service.install_agents(self.paths, ["codex"], dry_run=False)
        refreshed = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(refreshed["assignments"], receipt["assignments"])
        self.assertEqual(refreshed["files"]["worker.toml"], receipt["files"]["worker.toml"])
        self.assertEqual(refreshed["files"]["adversary.toml"],
                         install_targets._content_digest(adversary.read_bytes()))
        self.assertFalse(install_targets.role_receipt_status(self.paths, "codex")[0])

    def test_a_repeated_install_keeps_current_prompts_and_receipts_byte_identical(self) -> None:
        self.install_all()
        protected = self.protected_role_state()
        before = {path: path.read_bytes() for path in protected}

        self.install_all()
        install_service.install_agents(self.paths, ["codex"], dry_run=True)
        install_service.uninstall_agents(
            self.paths, ["codex", "kilo"], remove_shared=False, dry_run=False
        )

        self.assertEqual({path: path.read_bytes() for path in protected}, before)
        self.assertTrue((self.paths.shared_skill / "SKILL.md").is_file())

    def test_uninstall_reports_only_the_skill_it_actually_removed(self) -> None:
        nothing = install_service.uninstall_agents(
            self.paths, ["codex"], remove_shared=False, dry_run=False
        )
        self.assertIn("codex: no skill to remove", nothing)

        self.install_all()
        kept = install_service.uninstall_agents(
            self.paths, ["codex"], remove_shared=False, dry_run=False
        )
        self.assertTrue((self.paths.shared_skill / "SKILL.md").is_file())
        self.assertIn("codex: skill is the shared scan path; kept", " ".join(kept))

        removed = install_service.uninstall_agents(
            self.paths, ["codex"], remove_shared=True, dry_run=False
        )
        self.assertFalse(self.paths.shared_skill.exists())
        self.assertIn("codex: removed the shared scan skill", removed)


class InstallerCliContractTests(unittest.TestCase):
    def test_the_installer_exposes_only_its_four_verbs(self) -> None:
        parser = install_cli.build_parser()

        parser.parse_args(["install"])
        parser.parse_args(["update"])
        parser.parse_args(["doctor"])
        parser.parse_args(["uninstall"])
        for removed in ("uninstall-hooks", "status"):
            with self.subTest(verb=removed):
                with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                    parser.parse_args([removed])

    def test_doctor_exit_code_follows_failures_only(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(install_cli.print_checks([Check("WARN", "host", "drift")]), 0)
            self.assertEqual(install_cli.print_checks([Check("OK", "host", "verified")]), 0)
            self.assertEqual(install_cli.print_checks([Check("FAIL", "host", "missing")]), 1)


if __name__ == "__main__":
    unittest.main()
