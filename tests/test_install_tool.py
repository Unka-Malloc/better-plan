from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

from scripts.better_plan.adapters import install_cli
from scripts.better_plan.hooks import config as hook_config
from scripts.better_plan.installation import doctor as install_doctor
from scripts.better_plan.installation import models as install_models
from scripts.better_plan.installation import service as install_service
from scripts.better_plan.installation import targets as install_targets


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_TOOL_PATH = REPO_ROOT / "scripts" / "install.py"

def run_command(
    *args: str | Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(arg) for arg in args],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def make_paths(root: Path) -> object:
    home = root / "home"
    return install_models.InstallPaths(
        repo_root=REPO_ROOT,
        codex_home=home / ".codex",
        shared_home=home / ".agents",
        claude_home=home / ".claude",
        opencode_config=home / ".config" / "opencode",
        cursor_home=home / ".cursor",
        copilot_home=home / ".copilot",
        antigravity_home=home / ".gemini" / "config",
        pi_home=home / ".pi" / "agent",
        craft_home=home / ".craft-agent",
        kimi_home=home / ".kimi-code",
    )


class InstallToolTests(unittest.TestCase):
    def setUp(self) -> None:
        wsl_discovery = mock.patch.object(install_targets, "discover_wsl_opencode", return_value=[])
        wsl_discovery.start()
        self.addCleanup(wsl_discovery.stop)

    def test_parse_running_wsl_distros(self) -> None:
        output = "\ufeff  NAME                   STATE           VERSION\r\n* Debian                 Running         2\r\n  Ubuntu                 Stopped         2\r\n  docker-desktop         Running         2\r\n"

        self.assertEqual(install_targets.parse_running_wsl_distros(output), ["Debian", "docker-desktop"])

    def test_retired_gemini_target_is_rejected(self) -> None:
        with self.assertRaises(install_models.InstallError):
            install_cli.parse_agents(["gemini"])

    def test_install_creates_all_current_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            paths.cursor_skill.mkdir(parents=True)
            (paths.cursor_skill / "SKILL.md").write_text("---\nname: better-plan\n---\n", encoding="utf-8")
            paths.copilot_skill.mkdir(parents=True)
            (paths.copilot_skill / "SKILL.md").write_text("---\nname: better-plan\n---\n", encoding="utf-8")
            craft_workspace = paths.craft_home / "workspaces" / "workspace"
            craft_workspace.mkdir(parents=True)
            (craft_workspace / "config.json").write_text("{}\n", encoding="utf-8")

            messages = install_service.install_agents(paths, list(install_models.AGENTS), dry_run=False)

            self.assertTrue(any("native: updated" in message for message in messages), messages)
            self.assertTrue(any("codex: using native skill" in message for message in messages), messages)
            self.assertTrue(any("cursor: using native skill" in message for message in messages), messages)
            self.assertTrue(any("copilot: using native skill" in message for message in messages), messages)
            self.assertTrue(any("kimi: using native skill" in message for message in messages), messages)
            self.assertTrue((paths.codex_skill / "SKILL.md").is_file())
            self.assertTrue((paths.cursor_skill / "SKILL.md").is_file())
            self.assertTrue((paths.copilot_skill / "SKILL.md").is_file())
            self.assertTrue((paths.pi_skill / "SKILL.md").is_file())
            self.assertTrue((paths.kimi_skill / "SKILL.md").is_file())
            self.assertFalse(paths.shared_skill.exists())
            self.assertTrue((paths.claude_plugin / ".claude-plugin" / "plugin.json").is_file())
            self.assertTrue((paths.claude_skill / "SKILL.md").is_file())
            self.assertTrue(paths.codex_hooks.is_file())
            self.assertTrue(paths.claude_settings.is_file())
            self.assertTrue((paths.cursor_home / "hooks.json").is_file())
            self.assertEqual(paths.codex_hooks.read_text(encoding="utf-8").count("--managed-by better-plan"), 3)
            self.assertEqual(paths.claude_settings.read_text(encoding="utf-8").count("--managed-by better-plan"), 3)
            self.assertEqual((paths.cursor_home / "hooks.json").read_text(encoding="utf-8").count("--managed-by better-plan"), 3)
            codex = json.loads(paths.codex_hooks.read_text(encoding="utf-8"))
            claude = json.loads(paths.claude_settings.read_text(encoding="utf-8"))
            cursor = json.loads((paths.cursor_home / "hooks.json").read_text(encoding="utf-8"))
            self.assertEqual(set(codex["hooks"]), {"SessionStart", "UserPromptSubmit", "PostToolUse"})
            self.assertEqual(set(claude["hooks"]), {"SessionStart", "UserPromptSubmit", "PostToolUse"})
            self.assertEqual(set(cursor["hooks"].keys()), {"sessionStart", "beforeSubmitPrompt", "postToolUse"})
            self.assertTrue((paths.opencode_agent).is_file())
            self.assertTrue((paths.antigravity_plugin / "plugin.json").is_file())
            self.assertTrue((paths.antigravity_plugin / "hooks.json").is_file())
            self.assertTrue((craft_workspace / "skills" / "better-plan" / "SKILL.md").is_file())
            kimi = paths.kimi_config.read_text(encoding="utf-8")
            self.assertEqual(
                [
                    line.split("=", 1)[1].strip().strip('"')
                    for line in kimi.splitlines()
                    if line.startswith("event = ")
                ],
                ["SessionStart", "UserPromptSubmit", "SubagentStop"],
            )
            self.assertEqual(
                paths.kimi_config.read_text(encoding="utf-8").count("--managed-by better-plan"),
                3,
            )
            opencode_text = paths.opencode_agent.read_text(encoding="utf-8")
            self.assertIn("installed `better-plan` skill", opencode_text)
            self.assertNotIn(str(Path(tmpdir)), opencode_text)
            self.assertFalse([message for message in messages if str(Path(tmpdir)) in message], messages)

            plugin = json.loads((paths.claude_plugin / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
            self.assertEqual(plugin["name"], "better-plan")
            self.assertEqual(plugin["version"], install_models.VERSION)

            for event in ("sessionStart", "beforeSubmitPrompt", "postToolUse"):
                self.assertIn(event, cursor["hooks"])
                handlers = cursor["hooks"][event]
                self.assertEqual(len(handlers), 1, event)
                payload = handlers[0]
                expected_fields = {"command", "matcher"} if event == "postToolUse" else {"command"}
                self.assertEqual(set(payload), expected_fields)
                self.assertIn("--managed-by better-plan", payload["command"])
                self.assertNotIn(str(Path(tmpdir)), payload["command"])

    def test_managed_lifecycle_hook_command_is_portable_and_detector_gated(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            paths = make_paths(root)
            install_service.install_agents(paths, ["codex", "claude", "cursor"], dry_run=False)
            codex = json.loads(paths.codex_hooks.read_text(encoding="utf-8"))
            claude = json.loads(paths.claude_settings.read_text(encoding="utf-8"))
            cursor = json.loads((paths.cursor_home / "hooks.json").read_text(encoding="utf-8"))
            managed_commands = [
                codex["hooks"]["SessionStart"][0]["hooks"][0]["command"],
                codex["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"],
                codex["hooks"]["PostToolUse"][0]["hooks"][0]["command"],
                claude["hooks"]["SessionStart"][0]["hooks"][0]["command"],
                claude["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"],
                claude["hooks"]["PostToolUse"][0]["hooks"][0]["command"],
                cursor["hooks"]["sessionStart"][0]["command"],
                cursor["hooks"]["beforeSubmitPrompt"][0]["command"],
                cursor["hooks"]["postToolUse"][0]["command"],
            ]
            unrelated = root / "unrelated"
            unrelated.mkdir()
            (unrelated / ".git").mkdir()
            env = os.environ.copy()
            env["BETTER_PLAN_SHARED_HOME"] = str(paths.shared_home)
            env["CODEX_HOME"] = str(paths.codex_home)
            env["CLAUDE_HOME"] = str(paths.claude_home)
            env["CURSOR_HOME"] = str(paths.cursor_home)
            env["PATH"] = str(Path(sys.executable).parent)
            for command in managed_commands:
                result = subprocess.run(
                    command,
                    cwd=unrelated,
                    env=env,
                    input=json.dumps({"cwd": str(unrelated)}),
                    shell=True,
                    check=False,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                self.assertNotIn(str(root), command)
                self.assertNotIn(sys.executable, command)
                self.assertIn("scope.py", command)
                self.assertIn("context.py", command)
                self.assertIn("--event", command)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), {})
            active = root / "active"
            active.mkdir()
            (active / ".git").mkdir()
            plan_workspace = active / "docs" / "plan"
            plan_workspace.mkdir(parents=True)
            (plan_workspace / "Manifest.json").write_text(
                json.dumps([
                    {
                        "id": "11111111-1111-4a5d-9a11-111111111111",
                        "status": "in_progress",
                        "title": "SessionStart fixture",
                        "directory": "main-plan",
                        "source_files": [],
                        "goal": "Test session-start context generation.",
                        "description": "Controlled hook invocation fixture.",
                        "checkpoints": "main-plan/Checkpoints.json",
                    }
                ],),
                encoding="utf-8",
            )
            main_plan = plan_workspace / "main-plan"
            main_plan.mkdir()
            (main_plan / "Checkpoints.json").write_text("[]", encoding="utf-8")

            session_commands = {
                "codex": codex["hooks"]["SessionStart"][0]["hooks"][0]["command"],
                "claude": claude["hooks"]["SessionStart"][0]["hooks"][0]["command"],
                "cursor": cursor["hooks"]["sessionStart"][0]["command"],
            }

            codex_claude_payload = json.dumps({"cwd": str(active)})
            cursor_payload = json.dumps({"cwd": str(active)})
            for command in session_commands.values():
                self.assertNotIn(str(root), command)
                self.assertNotIn(sys.executable, command)

            codex_result = subprocess.run(
                session_commands["codex"],
                cwd=active,
                env=env,
                input=codex_claude_payload,
                shell=True,
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertEqual(codex_result.returncode, 0, codex_result.stderr)
            codex_output = json.loads(codex_result.stdout)
            self.assertEqual(set(codex_output.keys()), {"hookSpecificOutput"})
            self.assertEqual(set(codex_output["hookSpecificOutput"].keys()), {"hookEventName", "additionalContext"})
            self.assertEqual(codex_output["hookSpecificOutput"]["hookEventName"], "SessionStart")

            claude_result = subprocess.run(
                session_commands["claude"],
                cwd=active,
                env=env,
                input=codex_claude_payload,
                shell=True,
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertEqual(claude_result.returncode, 0, claude_result.stderr)
            claude_output = json.loads(claude_result.stdout)
            self.assertEqual(set(claude_output.keys()), {"hookSpecificOutput"})
            self.assertEqual(set(claude_output["hookSpecificOutput"].keys()), {"hookEventName", "additionalContext"})
            self.assertEqual(claude_output["hookSpecificOutput"]["hookEventName"], "SessionStart")

            cursor_result = subprocess.run(
                session_commands["cursor"],
                cwd=active,
                env=env,
                input=cursor_payload,
                shell=True,
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertEqual(cursor_result.returncode, 0, cursor_result.stderr)
            cursor_output = json.loads(cursor_result.stdout)
            self.assertEqual(set(cursor_output.keys()), {"additional_context"})

    def test_doctor_accepts_installed_files_without_optional_clis(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            install_service.install_agents(paths, list(install_models.AGENTS), dry_run=False)

            with mock.patch.object(install_doctor.shutil, "which", return_value=None):
                checks = install_doctor.doctor(paths, list(install_models.AGENTS))

            self.assertFalse([check for check in checks if check.status == "FAIL"], checks)
            self.assertTrue(any(check.target == "claude" and check.status == "WARN" for check in checks), checks)
            self.assertTrue(any(check.target == "opencode" and check.status == "WARN" for check in checks), checks)
            self.assertFalse([check for check in checks if check.target == "cursor lifecycle"], checks)
            self.assertTrue(any(check.target == "cursor hooks" for check in checks), checks)
            self.assertTrue(any(check.target == "cursor hooks" and check.status == "OK" for check in checks), checks)

    def test_install_updates_detected_wsl_opencode_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            runtime = install_models.WslOpenCodeRuntime(
                distro="Debian",
                location="runtime/opencode",
                home="runtime/home",
                version="1.17.11",
            )
            commands: list[list[str]] = []

            def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
                commands.append(command)
                if command[-3:] == ["wslpath", "-a", str(paths.repo_root)]:
                    return subprocess.CompletedProcess(command, 0, stdout="mnt/t/better-plan\n", stderr="")
                if command[:5] == ["wsl.exe", "-d", "Debian", "-e", "bash"]:
                    return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
                raise AssertionError(f"unexpected command: {command}")

            with ExitStack() as stack:
                stack.enter_context(mock.patch.object(install_targets.os, "name", "nt"))
                stack.enter_context(
                    mock.patch.object(
                        install_targets,
                        "wsl_executable",
                        return_value="wsl.exe",
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        install_targets,
                        "discover_wsl_opencode",
                        return_value=[runtime],
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        install_targets,
                        "run_text_command",
                        side_effect=fake_run,
                    )
                )
                messages = install_service.install_agents(paths, ["opencode"], dry_run=False)

            self.assertTrue(any("updated detected WSL runtime" in message for message in messages), messages)
            self.assertTrue(any("scripts/install.py" in command[-1] for command in commands), commands)

    def test_opencode_doctor_validates_detected_wsl_runtime_when_windows_path_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            install_service.install_agents(paths, ["opencode"], dry_run=False)
            runtime = install_models.WslOpenCodeRuntime(
                distro="Debian",
                location="runtime/opencode",
                home="runtime/home",
                version="1.17.11",
            )

            def fake_which(name: str) -> str | None:
                return None

            def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
                if command[:5] == ["wsl.exe", "-d", "Debian", "-e", "bash"]:
                    return subprocess.CompletedProcess(
                        command,
                        0,
                        stdout="better-plan (primary)\n",
                        stderr="",
                    )
                raise AssertionError(f"unexpected command: {command}")

            with ExitStack() as stack:
                stack.enter_context(mock.patch.object(install_targets.os, "name", "nt"))
                stack.enter_context(
                    mock.patch.object(
                        install_doctor.shutil,
                        "which",
                        side_effect=fake_which,
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        install_targets,
                        "wsl_executable",
                        return_value="wsl.exe",
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        install_targets,
                        "discover_wsl_opencode",
                        return_value=[runtime],
                    )
                )
                stack.enter_context(
                    mock.patch.object(
                        install_targets,
                        "run_text_command",
                        side_effect=fake_run,
                    )
                )
                checks = install_doctor.check_opencode(paths)

            self.assertTrue(any(check.target == "opencode" and check.status == "WARN" for check in checks), checks)
            self.assertTrue(
                any(check.target == "opencode (WSL)" and check.status == "OK" for check in checks), checks
            )

    def test_optional_client_cli_validation_has_explicit_success_warning_and_failure(self) -> None:
        with mock.patch.object(install_doctor.shutil, "which", return_value=None):
            warning = install_doctor.check_optional_client_cli("cursor")
        self.assertEqual(warning.status, "WARN")

        with ExitStack() as stack:
            stack.enter_context(
                mock.patch.object(
                    install_doctor.shutil,
                    "which",
                    return_value="cursor",
                )
            )
            stack.enter_context(
                mock.patch.object(
                    install_targets,
                    "run_text_command",
                    return_value=subprocess.CompletedProcess(
                        ["cursor", "--version"],
                        0,
                        stdout="1.0\n",
                        stderr="",
                    ),
                )
            )
            success = install_doctor.check_optional_client_cli("cursor")
        self.assertEqual(success.status, "OK")

        with ExitStack() as stack:
            stack.enter_context(
                mock.patch.object(
                    install_doctor.shutil,
                    "which",
                    return_value="copilot",
                )
            )
            stack.enter_context(
                mock.patch.object(
                    install_targets,
                    "run_text_command",
                    return_value=subprocess.CompletedProcess(
                        ["copilot", "--version"],
                        1,
                        stdout="",
                        stderr="failed",
                    ),
                )
            )
            failure = install_doctor.check_optional_client_cli("copilot")
        self.assertEqual(failure.status, "FAIL")

    def test_antigravity_doctor_requires_current_plugin_skill_and_hook(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            install_service.install_agents(paths, ["antigravity"], dry_run=False)

            check = install_doctor.check_antigravity(paths)
            self.assertEqual(check.status, "OK")
            hooks = json.loads((paths.antigravity_plugin / "hooks.json").read_text(encoding="utf-8"))
            self.assertEqual(set(hooks["better-plan"]), {"PreInvocation"})

    def test_installed_skill_inventory_requires_current_files(self) -> None:
        def build_complete_tree(root: Path) -> None:
            for relative in install_models.CURRENT_SKILL_FILES:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("x\n", encoding="utf-8")

        with tempfile.TemporaryDirectory() as all_current_root:
            root = Path(all_current_root)
            build_complete_tree(root)

            with mock.patch.object(install_doctor, "run_manifest_tool", return_value=True):
                ok = install_doctor.check_skill_tree("implementation", root)

            self.assertEqual(ok.status, "OK", ok.message)
            self.assertEqual(ok.message, "installed skill structure verified")

        for relative in install_models.CURRENT_SKILL_FILES:
            with self.subTest(relative=relative):
                with tempfile.TemporaryDirectory() as sampledir:
                    root = Path(sampledir)
                    build_complete_tree(root)

                    missing = root / relative
                    missing.unlink()

                    with mock.patch.object(install_doctor, "run_manifest_tool", return_value=True):
                        result = install_doctor.check_skill_tree("implementation", root)

                    self.assertEqual(result.status, "FAIL")
                    self.assertIn(str(relative), result.message)
                    self.assertIn("missing", result.message.lower())
                    self.assertNotIn(sampledir, result.message)

    def test_uninstall_removes_all_current_adapters(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            craft_workspace = paths.craft_home / "workspaces" / "workspace"
            craft_workspace.mkdir(parents=True)
            (craft_workspace / "config.json").write_text("{}\n", encoding="utf-8")
            install_service.install_agents(paths, list(install_models.AGENTS), dry_run=False)

            dry_run_messages = install_service.uninstall_agents(
                paths,
                list(install_models.AGENTS),
                remove_shared=True,
                dry_run=True,
            )
            messages = install_service.uninstall_agents(
                paths,
                list(install_models.AGENTS),
                remove_shared=True,
                dry_run=False,
            )

            for emitted in (dry_run_messages, messages):
                self.assertFalse(any(str(Path(tmpdir)) in message for message in emitted), emitted)

            self.assertFalse(paths.shared_skill.exists())
            self.assertFalse(paths.codex_skill.exists())
            self.assertFalse(paths.claude_plugin.exists())
            self.assertFalse(paths.opencode_agent.exists())
            self.assertFalse(paths.cursor_skill.exists())
            self.assertFalse(paths.copilot_skill.exists())
            self.assertFalse(paths.pi_skill.exists())
            self.assertFalse(paths.antigravity_plugin.exists())
            self.assertFalse(paths.kimi_skill.exists())
            self.assertFalse((craft_workspace / "skills" / "better-plan").exists())
            self.assertNotIn("--managed-by better-plan", paths.codex_hooks.read_text(encoding="utf-8"))
            self.assertNotIn("--managed-by better-plan", paths.claude_settings.read_text(encoding="utf-8"))
            self.assertTrue((paths.cursor_home / "hooks.json").is_file())
            self.assertNotIn("--managed-by better-plan", (paths.cursor_home / "hooks.json").read_text(encoding="utf-8"))
            self.assertNotIn("--managed-by better-plan", paths.kimi_config.read_text(encoding="utf-8"))

    def test_kimi_hook_install_and_removal_preserve_unrelated_toml(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            paths.kimi_config.parent.mkdir(parents=True)
            original = """default_model = "local-model"

[[hooks]]
event = "Notification"
matcher = 'task\\.completed'
command = "notify"
"""
            paths.kimi_config.write_text(original, encoding="utf-8")

            for _ in range(2):
                install_service.install_agents(paths, ["kimi"], dry_run=False)

            installed = paths.kimi_config.read_text(encoding="utf-8")
            self.assertIn('default_model = "local-model"', installed)
            self.assertEqual(installed.count("[[hooks]]"), 4)
            self.assertEqual(
                [
                    line.split("=", 1)[1].strip().strip('"')
                    for line in installed.splitlines()
                    if line.startswith("event = ")
                ][1:],
                ["SessionStart", "UserPromptSubmit", "SubagentStop"],
            )
            self.assertEqual(installed.count("--managed-by better-plan"), 3)
            self.assertTrue((paths.shared_skill / "SKILL.md").is_file())

            messages = install_service.uninstall_hooks(paths, ["kimi"], dry_run=False)

            self.assertTrue(any("removed managed handlers" in message for message in messages), messages)
            removed = paths.kimi_config.read_text(encoding="utf-8")
            self.assertIn('default_model = "local-model"', removed)
            self.assertEqual(removed.count("[[hooks]]"), 1)
            self.assertIn('event = "Notification"', removed)
            self.assertIn("command = \"notify\"", removed)
            self.assertTrue((paths.shared_skill / "SKILL.md").is_file())
            self.assertNotIn("--managed-by better-plan", removed)

    def test_supported_hook_install_is_idempotent_and_cursor_config_is_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            paths.codex_hooks.parent.mkdir(parents=True)
            paths.codex_hooks.write_text(
                json.dumps(
                    {
                        "custom": True,
                        "hooks": {
                            "SessionStart": [
                                {"matcher": "Bash", "hooks": [{"type": "command", "command": "custom-codex"}]}
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )
            paths.claude_settings.parent.mkdir(parents=True)
            paths.claude_settings.write_text(
                json.dumps(
                    {
                        "theme": "dark",
                        "hooks": {
                            "Stop": [{"hooks": [{"type": "command", "command": "custom-claude"}]}]
                        },
                    }
                ),
                encoding="utf-8",
            )
            cursor_hooks = paths.cursor_home / "hooks.json"
            cursor_hooks.parent.mkdir(parents=True)
            cursor_hooks.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "custom": "keep",
                        "hooks": {
                            "sessionStart": [{"command": "custom-cursor"}],
                            "beforeSubmitPrompt": [{"command": "custom-cursor-prompt"}],
                            "stop": [{"command": "custom-cursor-stop"}],
                        },
                    }
                ),
                encoding="utf-8",
            )

            for _ in range(2):
                install_service.install_agents(paths, ["codex", "claude", "cursor"], dry_run=False)

            expected_counts = {
                paths.codex_hooks: 3,
                paths.claude_settings: 3,
                cursor_hooks: 3,
            }
            for config, count in expected_counts.items():
                self.assertEqual(config.read_text(encoding="utf-8").count("--managed-by better-plan"), count)

            install_service.uninstall_agents(
                paths,
                ["codex", "claude", "cursor"],
                remove_shared=True,
                dry_run=False,
            )
            install_service.uninstall_hooks(
                paths,
                ["codex", "claude", "cursor"],
                dry_run=False,
            )

            codex = json.loads(paths.codex_hooks.read_text(encoding="utf-8"))
            claude = json.loads(paths.claude_settings.read_text(encoding="utf-8"))
            cursor = json.loads(cursor_hooks.read_text(encoding="utf-8"))
            self.assertTrue(codex["custom"])
            self.assertEqual(codex["hooks"]["SessionStart"][0]["hooks"][0]["command"], "custom-codex")
            self.assertEqual(claude["theme"], "dark")
            self.assertEqual(claude["hooks"]["Stop"][0]["hooks"][0]["command"], "custom-claude")
            self.assertEqual(cursor["custom"], "keep")
            self.assertEqual(cursor["hooks"]["sessionStart"][0]["command"], "custom-cursor")
            self.assertEqual(cursor["hooks"]["beforeSubmitPrompt"][0]["command"], "custom-cursor-prompt")
            self.assertEqual(cursor["hooks"]["stop"][0]["command"], "custom-cursor-stop")
            for value in (codex, claude, cursor):
                self.assertNotIn("--managed-by better-plan", json.dumps(value))

    def test_hook_merge_preserves_unrelated_empty_and_non_array_entries(self) -> None:
        nested = {
            "hooks": {
                "SessionStart": [{"matcher": "keep-empty", "hooks": []}],
                "CustomEvent": {"owner": "other-extension"},
            }
        }
        nested_result = hook_config.merged_config(nested, "codex")
        self.assertEqual(
            nested_result["hooks"]["SessionStart"][0],
            {"matcher": "keep-empty", "hooks": []},
        )
        self.assertEqual(
            nested_result["hooks"]["CustomEvent"],
            {"owner": "other-extension"},
        )

        flat = {
            "version": 1,
            "hooks": {
                "sessionStart": [],
                "customEvent": {"owner": "other-extension"},
            },
        }
        flat_result = hook_config.merged_config(flat, "cursor")
        self.assertEqual(
            flat_result["hooks"]["customEvent"],
            {"owner": "other-extension"},
        )
        self.assertEqual(len(flat_result["hooks"]["sessionStart"]), 1)
        self.assertEqual(set(flat_result["hooks"]["sessionStart"][0]), {"command"})

    def test_hook_only_uninstall_preserves_skills_and_unrelated_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            paths.codex_hooks.parent.mkdir(parents=True, exist_ok=True)
            paths.codex_hooks.write_text(
                json.dumps(
                    {
                        "custom": True,
                        "meta": {"owner": "team-x"},
                        "hooks": {
                            "UserPromptSubmit": [
                                {
                                    "matcher": "Bash",
                                    "hooks": [
                                        {"type": "command", "command": "keep-before-codex"},
                                        {"type": "command", "command": "codex-marker"},
                                    ]
                                }
                            ],
                        },
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            paths.claude_settings.parent.mkdir(parents=True, exist_ok=True)
            paths.claude_settings.write_text(
                json.dumps(
                    {
                        "theme": "dark",
                        "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "keep-before-claude"}]}]},
                        "extras": {"flag": True},
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            cursor_hooks = paths.cursor_home / "hooks.json"
            cursor_hooks.parent.mkdir(parents=True, exist_ok=True)
            cursor_hooks.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "custom": "keep",
                        "hooks": {
                            "sessionStart": [{"command": "keep-before-cursor"}],
                            "beforeSubmitPrompt": [{"command": "keep-before-cursor-prompt"}],
                            "stop": [{"command": "keep-stop-cursor"}],
                            "other": [{"command": "keep-unrelated-cursor"}],
                        },
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            install_service.install_agents(paths, ["codex", "claude", "cursor"], dry_run=False)

            shared_skill = (paths.shared_skill / "SKILL.md").read_bytes()
            claude_plugin_json = (paths.claude_plugin / ".claude-plugin" / "plugin.json").read_bytes()
            codex_config_before = json.loads(paths.codex_hooks.read_text(encoding="utf-8"))
            claude_config_before = json.loads(paths.claude_settings.read_text(encoding="utf-8"))
            cursor_config_before = json.loads(cursor_hooks.read_text(encoding="utf-8"))

            messages = install_service.uninstall_hooks(paths, ["codex", "claude", "cursor"], dry_run=False)

            self.assertFalse(any(str(Path(tmpdir)) in message for message in messages), messages)
            self.assertTrue(any("removed managed handlers" in message for message in messages), messages)
            self.assertEqual(shared_skill, (paths.shared_skill / "SKILL.md").read_bytes(), "skill tree changed on hook-only uninstall")
            self.assertFalse((paths.codex_skill / "SKILL.md").exists(), "native codex skill should not exist for shared install path")
            self.assertFalse((paths.cursor_skill / "SKILL.md").exists(), "native cursor skill should not exist for shared install path")
            codex_config_after = json.loads(paths.codex_hooks.read_text(encoding="utf-8"))
            claude_config_after = json.loads(paths.claude_settings.read_text(encoding="utf-8"))
            self.assertEqual(codex_config_before["meta"], codex_config_after.get("meta"))
            self.assertEqual(codex_config_before["custom"], codex_config_after.get("custom"))
            self.assertEqual(
                codex_config_before["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"],
                codex_config_after["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"],
            )
            self.assertNotIn("SessionStart", codex_config_after["hooks"])
            self.assertIn("UserPromptSubmit", codex_config_after["hooks"])
            self.assertEqual(claude_config_before["theme"], claude_config_after["theme"])
            self.assertEqual(claude_config_before["extras"], claude_config_after.get("extras"))
            self.assertEqual(
                claude_config_before["hooks"]["Stop"][0]["hooks"][0]["command"],
                claude_config_after["hooks"]["Stop"][0]["hooks"][0]["command"],
            )
            self.assertEqual(
                claude_plugin_json,
                (paths.claude_plugin / ".claude-plugin" / "plugin.json").read_bytes(),
                "claude plugin marker changed on hook-only uninstall",
            )
            cursor_config_after = json.loads(cursor_hooks.read_text(encoding="utf-8"))
            self.assertEqual(cursor_config_before["custom"], cursor_config_after["custom"])
            self.assertEqual(
                cursor_config_before["hooks"]["other"],
                cursor_config_after["hooks"]["other"],
            )
            self.assertEqual(
                cursor_config_before["hooks"]["sessionStart"][0]["command"],
                cursor_config_after["hooks"]["sessionStart"][0]["command"],
            )
            self.assertEqual(
                cursor_config_before["hooks"]["beforeSubmitPrompt"][0]["command"],
                cursor_config_after["hooks"]["beforeSubmitPrompt"][0]["command"],
            )
            self.assertEqual(
                cursor_config_before["hooks"]["stop"][0]["command"],
                cursor_config_after["hooks"]["stop"][0]["command"],
            )
            for command in (
                cursor_config_before["hooks"]["sessionStart"][0]["command"],
                cursor_config_before["hooks"]["beforeSubmitPrompt"][0]["command"],
                cursor_config_before["hooks"]["stop"][0]["command"],
            ):
                self.assertNotIn("--managed-by better-plan", command)
                self.assertNotIn("--managed-by better-plan", json.dumps(cursor_config_after))
            self.assertIn("keep-before-codex", paths.codex_hooks.read_text(encoding="utf-8"))
            self.assertIn("keep-before-claude", paths.claude_settings.read_text(encoding="utf-8"))
            self.assertIn("keep-before-cursor", paths.cursor_home.joinpath("hooks.json").read_text(encoding="utf-8"))
            self.assertIn("keep-before-cursor-prompt", paths.cursor_home.joinpath("hooks.json").read_text(encoding="utf-8"))
            self.assertIn("keep-stop-cursor", paths.cursor_home.joinpath("hooks.json").read_text(encoding="utf-8"))
            self.assertIn("keep-unrelated-cursor", paths.cursor_home.joinpath("hooks.json").read_text(encoding="utf-8"))
            self.assertNotIn("--managed-by better-plan", paths.codex_hooks.read_text(encoding="utf-8"))
            self.assertNotIn("--managed-by better-plan", paths.claude_settings.read_text(encoding="utf-8"))
            self.assertNotIn("--managed-by better-plan", paths.cursor_home.joinpath("hooks.json").read_text(encoding="utf-8"))

            parser = install_cli.build_parser()
            parsed = parser.parse_args(["uninstall-hooks", "--agents", "codex,claude"])
            self.assertIs(parsed.func, install_cli.uninstall_hooks_command)

    def test_managed_lifecycle_inventory_is_exact_and_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            install_service.install_agents(paths, ["codex", "claude", "cursor"], dry_run=False)
            self.assertLessEqual(hook_config.HOOK_TIMEOUT_SECONDS, 30)

            for agent, path in [("codex", paths.codex_hooks), ("claude", paths.claude_settings)]:
                handlers = hook_config.nested_handlers(agent)
                self.assertEqual(set(handlers.keys()), {"SessionStart", "UserPromptSubmit", "PostToolUse"})
                for event, groups in handlers.items():
                    self.assertEqual(len(groups), 1)
                    if event == "PostToolUse":
                        self.assertEqual(groups[0]["matcher"], "^Agent$")
                    else:
                        self.assertNotIn("matcher", groups[0])
                    hooks = groups[0]["hooks"]
                    self.assertEqual(len(hooks), 1)
                    payload = hooks[0]
                    self.assertEqual(payload["timeout"], hook_config.HOOK_TIMEOUT_SECONDS)

                config = json.loads(path.read_text(encoding="utf-8"))
                commands = hook_config.configured_commands(config, agent)
                for values in commands.values():
                    self.assertEqual(len(values), 1)

            cursor = json.loads((paths.cursor_home / "hooks.json").read_text(encoding="utf-8"))
            self.assertEqual(cursor.get("version"), 1)
            self.assertEqual(set(cursor["hooks"].keys()), {"sessionStart", "beforeSubmitPrompt", "postToolUse"})
            for event in ("sessionStart", "beforeSubmitPrompt", "postToolUse"):
                hooks = cursor["hooks"][event]
                self.assertEqual(len(hooks), 1)
                self.assertNotIn("hooks", hooks[0])
                expected_fields = {"command", "matcher"} if event == "postToolUse" else {"command"}
                self.assertEqual(set(hooks[0]), expected_fields)


    def test_doctor_fails_when_a_supported_agent_hook_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            required_events = {
                "codex": "SessionStart",
                "claude": "SessionStart",
                "cursor": "sessionStart",
            }
            for agent in ("codex", "claude", "cursor"):
                with self.subTest(agent=agent):
                    paths = make_paths(base / agent)
                    install_service.install_agents(paths, [agent], dry_run=False)
                    path = install_targets.hook_config_path(paths, agent)
                    data = json.loads(path.read_text(encoding="utf-8"))
                    hooks = data.setdefault("hooks", {})
                    hooks.pop(required_events[agent], None)
                    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

                    ok, message = hook_config.hook_config_status(path, agent)
                    self.assertFalse(ok, message)
                    check = install_doctor.check_agent_hooks(paths, agent)
                    self.assertEqual(check.status, "FAIL", check.message)

    def test_managed_hook_validation_fails_for_malformed_missing_and_duplicate_owned_handlers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            required_events = {
                "codex": ["SessionStart", "UserPromptSubmit", "PostToolUse"],
                "claude": ["SessionStart", "UserPromptSubmit", "PostToolUse"],
                "cursor": ["sessionStart", "beforeSubmitPrompt", "postToolUse"],
            }
            for agent in ("codex", "claude", "cursor"):
                with self.subTest(agent=agent):
                    paths = make_paths(base / agent)
                    install_service.install_agents(paths, [agent], dry_run=False)
                    path = install_targets.hook_config_path(paths, agent)

                    path.write_text("{}", encoding="utf-8")
                    ok, message = hook_config.hook_config_status(path, agent)
                    self.assertFalse(ok, message)

                    path.write_text(json.dumps({"hooks": []}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                    with self.assertRaises(hook_config.HookConfigError):
                        hook_config.install_hook_config(path, agent, dry_run=False)

                    path.write_text("{}\n", encoding="utf-8")
                    install_service.install_agents(paths, [agent], dry_run=False)
                    data = json.loads(path.read_text(encoding="utf-8"))
                    event = required_events[agent][0]
                    handlers = data["hooks"][event]
                    self.assertIsInstance(handlers, list)
                    handlers.append(handlers[0])
                    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

                    ok, message = hook_config.hook_config_status(path, agent)
                    self.assertFalse(ok, message)
                    check = install_doctor.check_agent_hooks(paths, agent)
                    self.assertEqual(check.status, "FAIL", check.message)

    def test_doctor_rejects_noncanonical_managed_handler_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            for agent in ("codex", "claude", "cursor"):
                with self.subTest(agent=agent):
                    paths = make_paths(base / agent)
                    install_service.install_agents(paths, [agent], dry_run=False)
                    path = install_targets.hook_config_path(paths, agent)
                    data = json.loads(path.read_text(encoding="utf-8"))
                    if agent == "cursor":
                        data["hooks"]["sessionStart"][0]["type"] = "command"
                    else:
                        data["hooks"]["SessionStart"][0]["hooks"][0]["timeout"] = 999
                    path.write_text(
                        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8",
                    )

                    ok, _ = hook_config.hook_config_status(path, agent)
                    self.assertFalse(ok)

                    install_service.install_agents(paths, [agent], dry_run=False)
                    repaired, message = hook_config.hook_config_status(path, agent)
                    self.assertTrue(repaired, message)

    def test_cli_default_install_and_doctor_support_temp_homes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            home = root / "home"
            codex_home = home / ".codex"
            shared_home = home / ".agents"
            cursor_home = home / ".cursor"
            copilot_home = home / ".copilot"
            antigravity_home = home / ".gemini" / "config"
            pi_home = home / ".pi" / "agent"
            craft_home = home / ".craft-agent"
            kimi_home = home / ".kimi-code"
            craft_workspace = craft_home / "workspaces" / "workspace"
            craft_workspace.mkdir(parents=True)
            (craft_workspace / "config.json").write_text("{}\n", encoding="utf-8")
            isolated_env = os.environ.copy()
            isolated_env["PATH"] = ""

            install_result = run_command(
                sys.executable,
                INSTALL_TOOL_PATH,
                "--agents",
                "codex,cursor,copilot,antigravity,pi,craft,kimi",
                "--codex-home",
                codex_home,
                "--shared-home",
                shared_home,
                "--cursor-home",
                cursor_home,
                "--copilot-home",
                copilot_home,
                "--antigravity-home",
                antigravity_home,
                "--pi-home",
                pi_home,
                "--craft-home",
                craft_home,
                "--kimi-home",
                kimi_home,
                env=isolated_env,
            )
            self.assertEqual(install_result.returncode, 0, install_result.stderr)
            self.assertIn("shared: updated", install_result.stdout)
            self.assertIn("codex: using shared skill", install_result.stdout)
            self.assertIn("cursor: using shared skill", install_result.stdout)
            self.assertIn("copilot: using shared skill", install_result.stdout)
            self.assertIn("pi: using shared skill", install_result.stdout)
            self.assertIn("kimi: using shared skill", install_result.stdout)
            self.assertIn("kimi hooks: updated managed handlers", install_result.stdout)
            self.assertIn("antigravity: updated plugin", install_result.stdout)
            self.assertIn("craft: updated skill in 1 workspace(s)", install_result.stdout)
            self.assertNotIn(str(root), install_result.stdout + install_result.stderr)

            doctor_result = run_command(
                sys.executable,
                INSTALL_TOOL_PATH,
                "doctor",
                "--agents",
                "codex,cursor,copilot,antigravity,pi,craft,kimi",
                "--codex-home",
                codex_home,
                "--shared-home",
                shared_home,
                "--cursor-home",
                cursor_home,
                "--copilot-home",
                copilot_home,
                "--antigravity-home",
                antigravity_home,
                "--pi-home",
                pi_home,
                "--craft-home",
                craft_home,
                "--kimi-home",
                kimi_home,
                env=isolated_env,
            )
            self.assertEqual(doctor_result.returncode, 0, doctor_result.stderr)
            self.assertIn("OK: codex:", doctor_result.stdout)
            self.assertIn("cursor:", doctor_result.stdout)
            self.assertIn("WARN: cursor:", doctor_result.stdout)
            self.assertIn("OK: cursor hooks:", doctor_result.stdout)
            self.assertIn("copilot:", doctor_result.stdout)
            self.assertIn("OK: antigravity:", doctor_result.stdout)
            self.assertIn("OK: pi:", doctor_result.stdout)
            self.assertIn("OK: craft:", doctor_result.stdout)
            self.assertIn("WARN: kimi:", doctor_result.stdout)
            self.assertIn("OK: kimi hooks:", doctor_result.stdout)
            self.assertNotIn("FAIL:", doctor_result.stdout)
            self.assertNotIn(str(root), doctor_result.stdout + doctor_result.stderr)

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

    def test_update_command_keeps_native_only_codex_install_native(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            home = root / "home"
            shared_home = home / ".agents"
            codex_home = home / ".codex"
            native_install = codex_home / "skills" / "better-plan"
            native_install.mkdir(parents=True)
            (native_install / "SKILL.md").write_text("---\nname: better-plan\n---\n", encoding="utf-8")

            update_result = run_command(
                sys.executable,
                INSTALL_TOOL_PATH,
                "update",
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
            self.assertTrue((native_install / "SKILL.md").is_file())

    def test_update_command_removes_native_duplicate_when_shared_install_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            home = root / "home"
            shared_home = home / ".agents"
            codex_home = home / ".codex"
            shared = shared_home / "skills" / "better-plan"
            native_duplicate = codex_home / "skills" / "better-plan"
            shared.mkdir(parents=True)
            native_duplicate.mkdir(parents=True)
            (shared / "SKILL.md").write_text("---\nname: better-plan\n---\n", encoding="utf-8")
            (native_duplicate / "SKILL.md").write_text("---\nname: better-plan\n---\n", encoding="utf-8")

            update_result = run_command(
                sys.executable,
                INSTALL_TOOL_PATH,
                "update",
                "--agents",
                "codex",
                "--shared-home",
                shared_home,
                "--codex-home",
                codex_home,
            )

            self.assertEqual(update_result.returncode, 0, update_result.stderr)
            self.assertIn("shared: updated", update_result.stdout)
            self.assertIn("codex: removed duplicate native skill", update_result.stdout)
            self.assertTrue((shared / "SKILL.md").is_file())
            self.assertFalse(native_duplicate.exists())
            self.assertFalse((codex_home / "skill-backups").exists())

    def test_installer_updates_managed_config_without_backup_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            paths.opencode_agent.parent.mkdir(parents=True)
            paths.opencode_agent.write_text("old\n", encoding="utf-8")
            paths.antigravity_plugin.mkdir(parents=True)
            (paths.antigravity_plugin / "plugin.json").write_text("{}\n", encoding="utf-8")

            install_service.install_agents(paths, ["opencode", "antigravity"], dry_run=False)

            self.assertEqual([], list(Path(tmpdir).rglob("*bak-better-plan-*")))


if __name__ == "__main__":
    unittest.main()
