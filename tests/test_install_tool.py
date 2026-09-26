"""Installation, Doctor, and uninstall for the five supported hosts."""

from __future__ import annotations

import contextlib
import io
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
ROLES = ("designer", "worker", "reviewer")


def make_paths(root: Path) -> install_models.InstallPaths:
    home = root / "home"
    return install_models.InstallPaths(
        repo_root=REPO_ROOT,
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
        """Every immutable artifact: role files and the two managed receipts."""

        return [
            *[self.paths.codex_home / "agents" / ("%s.toml" % role) for role in ROLES],
            *[self.paths.claude_home / "agents" / ("%s.md" % role) for role in ROLES],
            *[self.paths.cursor_home / "agents" / ("%s.md" % role) for role in ROLES],
            *[self.paths.kilo_agents / name for name in install_targets.KILO_AGENT_FILES],
            install_targets._native_receipt_path(self.paths.codex_home / "agents"),
            install_targets._native_receipt_path(self.paths.kilo_agents),
        ]

    def test_a_fresh_install_writes_the_shared_skill_and_three_roles(self) -> None:
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
        for role in ROLES:
            with self.subTest(role=role):
                self.assertEqual(receipt["assignments"][role].model, CODEX_DEFAULT_MATRIX[role][1])

    def test_a_local_role_file_is_never_overwritten(self) -> None:
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
                    self.assertIn("source=host-inheritance", text)
                    self.assertNotIn("model =", text)

    def test_deepseek_harness_installs_the_skill_only(self) -> None:
        messages = install_service.install_agents(self.paths, ["dsh"], dry_run=False)
        self.assertTrue((self.paths.shared_skill / "SKILL.md").is_file())
        self.assertIn("skill only", " ".join(messages))
        self.assertFalse((self.paths.codex_home / "agents").exists())

    def test_kilo_installs_one_primary_and_three_subagents(self) -> None:
        install_service.install_agents(self.paths, ["kilo"], dry_run=False)
        agents = self.paths.kilo_agents
        self.assertTrue((agents / "better-plan.md").is_file())
        for role in ROLES:
            with self.subTest(role=role):
                self.assertTrue((agents / ("better-plan-%s.md" % role)).is_file())

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

    def test_uninstall_removes_the_skill_and_keeps_local_roles(self) -> None:
        self.install_all()
        role = self.paths.codex_home / "agents" / "worker.toml"
        before = role.read_bytes()

        install_service.uninstall_agents(
            self.paths, list(install_models.AGENTS), remove_shared=True, dry_run=False
        )

        self.assertFalse(self.paths.shared_skill.exists())
        self.assertEqual(role.read_bytes(), before)

    def test_every_non_initial_installation_keeps_roles_and_receipts_byte_identical(self) -> None:
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
