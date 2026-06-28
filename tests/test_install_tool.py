from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_TOOL_PATH = REPO_ROOT / "scripts" / "install.py"

spec = importlib.util.spec_from_file_location("install_tool", INSTALL_TOOL_PATH)
assert spec is not None
install_tool = importlib.util.module_from_spec(spec)
sys.modules["install_tool"] = install_tool
assert spec.loader is not None
spec.loader.exec_module(install_tool)


def run_command(*args: str | Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(arg) for arg in args],
        cwd=REPO_ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def make_paths(root: Path) -> object:
    home = root / "home"
    return install_tool.InstallPaths(
        repo_root=REPO_ROOT,
        codex_home=home / ".codex",
        shared_home=home / ".agents",
        claude_home=home / ".claude",
        opencode_config=home / ".config" / "opencode",
        gemini_home=home / ".gemini",
        gemini_scope=f"{home}/*",
    )


class InstallToolTests(unittest.TestCase):
    def test_install_creates_all_targets_and_removes_stale_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            stale = paths.codex_skill / "scripts" / "manifest_tool_linux.sh"
            stale.parent.mkdir(parents=True)
            stale.write_text("#!/bin/sh\n", encoding="utf-8")

            messages = install_tool.install_agents(paths, list(install_tool.AGENTS), dry_run=False)

            self.assertTrue(any(message.startswith("codex: updated") for message in messages), messages)
            self.assertTrue((paths.codex_skill / "SKILL.md").is_file())
            self.assertFalse(stale.exists())
            self.assertTrue((paths.shared_skill / "scripts" / "manifest_tool.py").is_file())
            self.assertTrue((paths.claude_plugin / ".claude-plugin" / "plugin.json").is_file())
            self.assertTrue((paths.claude_skill / "SKILL.md").is_file())
            self.assertTrue((paths.opencode_agent).is_file())
            self.assertTrue((paths.gemini_extension / "gemini-extension.json").is_file())

            plugin = json.loads((paths.claude_plugin / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
            self.assertEqual(plugin["name"], "better-plan")

            enablement = json.loads(paths.gemini_enablement.read_text(encoding="utf-8"))
            self.assertEqual(enablement["better-plan"]["overrides"], [paths.gemini_scope])

    def test_doctor_accepts_installed_files_without_optional_clis(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            install_tool.install_agents(paths, list(install_tool.AGENTS), dry_run=False)

            with mock.patch.object(install_tool.shutil, "which", return_value=None):
                checks = install_tool.doctor(paths, list(install_tool.AGENTS))

            self.assertFalse([check for check in checks if check.status == "FAIL"], checks)
            self.assertTrue(any(check.target == "claude" and check.status == "WARN" for check in checks), checks)
            self.assertTrue(any(check.target == "opencode" and check.status == "WARN" for check in checks), checks)

    def test_uninstall_removes_adapters_and_disables_gemini(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            install_tool.install_agents(paths, list(install_tool.AGENTS), dry_run=False)

            install_tool.uninstall_agents(paths, list(install_tool.AGENTS), remove_shared=True, dry_run=False)

            self.assertFalse(paths.codex_skill.exists())
            self.assertFalse(paths.shared_skill.exists())
            self.assertFalse(paths.claude_plugin.exists())
            self.assertFalse(paths.opencode_agent.exists())
            self.assertFalse(paths.gemini_extension.exists())
            enablement = json.loads(paths.gemini_enablement.read_text(encoding="utf-8"))
            self.assertNotIn("better-plan", enablement)

    def test_cli_default_install_and_doctor_support_temp_homes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            home = root / "home"
            codex_home = home / ".codex"
            shared_home = home / ".agents"
            gemini_home = home / ".gemini"

            install_result = run_command(
                sys.executable,
                INSTALL_TOOL_PATH,
                "--agents",
                "codex,gemini",
                "--codex-home",
                codex_home,
                "--shared-home",
                shared_home,
                "--gemini-home",
                gemini_home,
                "--gemini-scope",
                f"{home}/*",
            )
            self.assertEqual(install_result.returncode, 0, install_result.stderr)
            self.assertIn("codex: updated", install_result.stdout)

            doctor_result = run_command(
                sys.executable,
                INSTALL_TOOL_PATH,
                "doctor",
                "--agents",
                "codex,gemini",
                "--codex-home",
                codex_home,
                "--shared-home",
                shared_home,
                "--gemini-home",
                gemini_home,
            )
            self.assertEqual(doctor_result.returncode, 0, doctor_result.stderr)
            self.assertIn("OK: codex:", doctor_result.stdout)
            self.assertIn("OK: gemini:", doctor_result.stdout)


if __name__ == "__main__":
    unittest.main()
