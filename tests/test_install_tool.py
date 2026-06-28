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
UPDATE_TOOL_PATH = REPO_ROOT / "scripts" / "update.py"

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
        cursor_home=home / ".cursor",
        copilot_home=home / ".copilot",
        gemini_home=home / ".gemini",
        gemini_scope=f"{home}/*",
    )


class InstallToolTests(unittest.TestCase):
    def test_parse_running_wsl_distros(self) -> None:
        output = "\ufeff  NAME                   STATE           VERSION\r\n* Debian                 Running         2\r\n  Ubuntu                 Stopped         2\r\n  docker-desktop         Running         2\r\n"

        self.assertEqual(install_tool.parse_running_wsl_distros(output), ["Debian", "docker-desktop"])

    def test_install_creates_all_targets_and_removes_stale_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            stale = paths.codex_skill / "scripts" / "manifest_tool_linux.sh"
            stale.parent.mkdir(parents=True)
            stale.write_text("#!/bin/sh\n", encoding="utf-8")
            paths.cursor_skill.mkdir(parents=True)
            (paths.cursor_skill / "SKILL.md").write_text("---\nname: better-plan\n---\n", encoding="utf-8")
            paths.copilot_skill.mkdir(parents=True)
            (paths.copilot_skill / "SKILL.md").write_text("---\nname: better-plan\n---\n", encoding="utf-8")

            messages = install_tool.install_agents(paths, list(install_tool.AGENTS), dry_run=False)

            self.assertTrue(any("native: updated" in message for message in messages), messages)
            self.assertTrue(any("codex: using native skill" in message for message in messages), messages)
            self.assertTrue(any("cursor: using native skill" in message for message in messages), messages)
            self.assertTrue(any("copilot: using native skill" in message for message in messages), messages)
            self.assertTrue((paths.codex_skill / "SKILL.md").is_file())
            self.assertTrue((paths.cursor_skill / "SKILL.md").is_file())
            self.assertTrue((paths.copilot_skill / "SKILL.md").is_file())
            self.assertFalse(stale.exists())
            self.assertFalse(paths.shared_skill.exists())
            self.assertTrue((paths.claude_plugin / ".claude-plugin" / "plugin.json").is_file())
            self.assertTrue((paths.claude_skill / "SKILL.md").is_file())
            self.assertTrue((paths.opencode_agent).is_file())
            self.assertTrue((paths.gemini_extension / "gemini-extension.json").is_file())
            self.assertIn(str(paths.codex_skill / "SKILL.md"), paths.opencode_agent.read_text(encoding="utf-8"))
            self.assertIn(str(paths.codex_skill / "SKILL.md"), (paths.gemini_extension / "GEMINI.md").read_text(encoding="utf-8"))

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

    def test_opencode_doctor_reports_wsl_runtime_when_windows_path_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            install_tool.install_agents(paths, ["opencode"], dry_run=False)

            def fake_which(name: str) -> str | None:
                return "wsl.exe" if name == "wsl.exe" else None

            def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
                if command == ["wsl.exe", "-l", "-v"]:
                    output = "  NAME      STATE           VERSION\r\n* Debian    Running         2\r\n".encode("utf-16le")
                    return subprocess.CompletedProcess(command, 0, stdout=output, stderr=b"")
                if command[:4] == ["wsl.exe", "-d", "Debian", "-e"]:
                    return subprocess.CompletedProcess(
                        command,
                        0,
                        stdout="/home/unka/.opencode/bin/opencode\n1.17.11\n",
                        stderr="",
                    )
                raise AssertionError(f"unexpected command: {command}")

            with (
                mock.patch.object(install_tool.os, "name", "nt"),
                mock.patch.object(install_tool.shutil, "which", side_effect=fake_which),
                mock.patch.object(install_tool.subprocess, "run", side_effect=fake_run),
            ):
                check = install_tool.check_opencode(paths, paths.shared_skill)

            self.assertEqual(check.status, "WARN")
            self.assertIn("WSL Debian", check.message)
            self.assertIn("1.17.11", check.message)

    def test_opencode_doctor_reports_running_docker_container_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            install_tool.install_agents(paths, ["opencode"], dry_run=False)

            def fake_which(name: str) -> str | None:
                if name == "docker":
                    return "docker"
                return None

            def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
                if command[:3] == ["docker", "ps", "--format"]:
                    return subprocess.CompletedProcess(command, 0, stdout="abc123\tdevbox\n", stderr="")
                if command[:3] == ["docker", "exec", "abc123"]:
                    return subprocess.CompletedProcess(command, 0, stdout="/usr/local/bin/opencode\n1.17.11\n", stderr="")
                raise AssertionError(f"unexpected command: {command}")

            with (
                mock.patch.object(install_tool.os, "name", "posix"),
                mock.patch.object(install_tool.shutil, "which", side_effect=fake_which),
                mock.patch.object(install_tool.subprocess, "run", side_effect=fake_run),
            ):
                check = install_tool.check_opencode(paths, paths.shared_skill)

            self.assertEqual(check.status, "WARN")
            self.assertIn("Docker devbox", check.message)
            self.assertIn("/usr/local/bin/opencode", check.message)

    def test_uninstall_removes_adapters_and_disables_gemini(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            install_tool.install_agents(paths, list(install_tool.AGENTS), dry_run=False)

            install_tool.uninstall_agents(paths, list(install_tool.AGENTS), remove_shared=True, dry_run=False)

            self.assertFalse(paths.shared_skill.exists())
            self.assertFalse(paths.codex_skill.exists())
            self.assertFalse(paths.claude_plugin.exists())
            self.assertFalse(paths.opencode_agent.exists())
            self.assertFalse(paths.cursor_skill.exists())
            self.assertFalse(paths.copilot_skill.exists())
            self.assertFalse(paths.gemini_extension.exists())
            enablement = json.loads(paths.gemini_enablement.read_text(encoding="utf-8"))
            self.assertNotIn("better-plan", enablement)

    def test_cli_default_install_and_doctor_support_temp_homes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            home = root / "home"
            codex_home = home / ".codex"
            shared_home = home / ".agents"
            cursor_home = home / ".cursor"
            copilot_home = home / ".copilot"
            gemini_home = home / ".gemini"

            install_result = run_command(
                sys.executable,
                INSTALL_TOOL_PATH,
                "--agents",
                "codex,cursor,vscode-copilot,gemini",
                "--codex-home",
                codex_home,
                "--shared-home",
                shared_home,
                "--cursor-home",
                cursor_home,
                "--copilot-home",
                copilot_home,
                "--gemini-home",
                gemini_home,
                "--gemini-scope",
                f"{home}/*",
            )
            self.assertEqual(install_result.returncode, 0, install_result.stderr)
            self.assertIn("shared: updated", install_result.stdout)
            self.assertIn("codex: using shared skill", install_result.stdout)
            self.assertIn("cursor: using shared skill", install_result.stdout)
            self.assertIn("copilot: using shared skill", install_result.stdout)

            doctor_result = run_command(
                sys.executable,
                INSTALL_TOOL_PATH,
                "doctor",
                "--agents",
                "codex,cursor,copilot,gemini",
                "--codex-home",
                codex_home,
                "--shared-home",
                shared_home,
                "--cursor-home",
                cursor_home,
                "--copilot-home",
                copilot_home,
                "--gemini-home",
                gemini_home,
            )
            self.assertEqual(doctor_result.returncode, 0, doctor_result.stderr)
            self.assertIn("OK: codex:", doctor_result.stdout)
            self.assertIn("OK: cursor:", doctor_result.stdout)
            self.assertIn("OK: copilot:", doctor_result.stdout)
            self.assertIn("OK: gemini:", doctor_result.stdout)

    def test_existing_install_routes_installer_to_update(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            home = root / "home"
            shared_home = home / ".agents"
            codex_home = home / ".codex"
            (shared_home / "skills" / "better-plan").mkdir(parents=True)

            install_result = run_command(
                sys.executable,
                INSTALL_TOOL_PATH,
                "--agents",
                "codex",
                "--shared-home",
                shared_home,
                "--codex-home",
                codex_home,
            )

            self.assertEqual(install_result.returncode, 0, install_result.stderr)
            self.assertIn("existing Better Plan install found; switching installer to update", install_result.stdout)
            self.assertIn("codex: using shared skill", install_result.stdout)
            self.assertTrue((shared_home / "skills" / "better-plan" / "SKILL.md").is_file())

    def test_update_script_keeps_native_only_codex_install_native(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            home = root / "home"
            shared_home = home / ".agents"
            codex_home = home / ".codex"
            legacy = codex_home / "skills" / "better-plan"
            legacy.mkdir(parents=True)
            (legacy / "SKILL.md").write_text("---\nname: better-plan\n---\n", encoding="utf-8")

            update_result = run_command(
                sys.executable,
                UPDATE_TOOL_PATH,
                "--agents",
                "codex",
                "--shared-home",
                shared_home,
                "--codex-home",
                codex_home,
            )

            self.assertEqual(update_result.returncode, 0, update_result.stderr)
            self.assertIn("native: updated", update_result.stdout)
            self.assertIn("codex: using native skill", update_result.stdout)
            self.assertFalse((shared_home / "skills" / "better-plan").exists())
            self.assertTrue((legacy / "SKILL.md").is_file())

    def test_update_script_moves_native_duplicate_when_shared_install_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            home = root / "home"
            shared_home = home / ".agents"
            codex_home = home / ".codex"
            shared = shared_home / "skills" / "better-plan"
            legacy = codex_home / "skills" / "better-plan"
            shared.mkdir(parents=True)
            legacy.mkdir(parents=True)
            (shared / "SKILL.md").write_text("---\nname: better-plan\n---\n", encoding="utf-8")
            (legacy / "SKILL.md").write_text("---\nname: better-plan\n---\n", encoding="utf-8")

            update_result = run_command(
                sys.executable,
                UPDATE_TOOL_PATH,
                "--agents",
                "codex",
                "--shared-home",
                shared_home,
                "--codex-home",
                codex_home,
            )

            self.assertEqual(update_result.returncode, 0, update_result.stderr)
            self.assertIn("shared: updated", update_result.stdout)
            self.assertIn("codex: moved duplicate native skill", update_result.stdout)
            self.assertTrue((shared / "SKILL.md").is_file())
            self.assertFalse(legacy.exists())


if __name__ == "__main__":
    unittest.main()
