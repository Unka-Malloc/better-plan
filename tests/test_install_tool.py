from __future__ import annotations

import dataclasses
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.better_plan.adapters import install_cli
from scripts.better_plan.domain.model_routing import (
    load_coding_agent_catalog,
    load_model_catalog,
)
from scripts.better_plan.hooks import config as hook_config
from scripts.better_plan.installation import doctor as install_doctor
from scripts.better_plan.installation import models as install_models
from scripts.better_plan.installation import service as install_service
from scripts.better_plan.installation import skills as install_skills
from scripts.better_plan.installation import targets as install_targets
from scripts.better_plan.installation.assignments import CODEX_DEFAULT_MATRIX
from tests.v3_fixtures import complete_plan, write_workspace


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_TOOL_PATH = REPO_ROOT / "scripts" / "install.py"
RETIRED_HOST_SURFACES = (
    ".config/opencode",
    ".copilot",
    ".gemini",
    ".pi",
    ".craft-agent",
    ".kimi-code",
)
# The exact four-role Codex contract: role, model, effort, benchmark row, score, task cost.
CODEX_PRESET = {
    "designer": ("designer", "gpt-6-astra", "max", "gpt-6-astra", 53, None),
    "worker": ("worker", "gpt-6-luna", "max", "codex-gpt-6-luna-max", 41, 0.17591172304455457),
    "hybrid-worker": ("worker", "gpt-6-astra", "low", "gpt-6-astra-low", 46, None),
    "reviewer": ("reviewer", "gpt-6-astra", "xhigh", "gpt-6-astra-xhigh", 52, None),
}


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


def make_paths(root: Path, *, repo_root: Path = REPO_ROOT) -> object:
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


NATIVE_ROLE_FILES = install_targets.NATIVE_ROLE_FILES
# The packaged source directory for each target; Claude Code keeps its roles under claude-code.
NATIVE_SOURCE_DIRECTORIES = {"codex": "codex", "claude": "claude-code", "cursor": "cursor", "kilo": "kilo"}


def native_role_directory(paths: object, target: str = "codex") -> Path:
    if target == "codex":
        return paths.codex_home / "agents"
    if target == "claude":
        return paths.claude_home / "agents"
    if target == "cursor":
        return paths.cursor_home / "agents"
    raise AssertionError(f"no packaged native roles for {target}")


def rewrite_receipt(receipt: Path, transform) -> None:
    value = json.loads(receipt.read_text(encoding="utf-8"))
    transform(value)
    receipt.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


class InstallToolTests(unittest.TestCase):
    def test_four_hosts_are_supported_and_only_codex_packages_presets(self) -> None:
        self.assertEqual(install_models.AGENTS, ("codex", "claude", "cursor", "kilo"))
        self.assertEqual(set(install_models.SHARED_SCAN_AGENTS), {"codex", "cursor", "kilo"})
        self.assertEqual(install_cli.parse_agents(["all"]), ["codex", "claude", "cursor", "kilo"])
        self.assertEqual(install_cli.parse_agents(["kilo,codex"]), ["kilo", "codex"])
        self.assertEqual(install_cli.parse_agents(["claude", "cursor"]), ["claude", "cursor"])
        # Only Codex carries a packaged selector, so only Codex has preset constants.
        self.assertTrue(hasattr(install_models, "OPTIONAL_CLIENT_CLI_COMMANDS"))
        self.assertTrue(hasattr(install_models, "CURSOR_APP_BUNDLE_CLI"))
        self.assertFalse(hasattr(install_models, "ADAPTER_SKILL_AGENTS"))
        self.assertEqual(set(install_targets.UNPINNED_HOSTS), {"claude", "cursor"})
        for retired in ("opencode", "copilot", "antigravity", "pi", "craft", "kimi", "gemini"):
            with self.subTest(target=retired), self.assertRaises(install_models.InstallError):
                install_cli.parse_agents([retired])

    def test_install_paths_keep_exactly_the_four_host_surfaces(self) -> None:
        self.assertEqual(install_models.VERSION, "3.2.0")
        self.assertEqual(
            {field.name for field in dataclasses.fields(install_models.InstallPaths)},
            {
                "repo_root",
                "codex_home",
                "shared_home",
                "claude_home",
                "cursor_home",
                "kilo_home",
                "kilo_config",
            },
        )
        paths = make_paths(Path("/tmp/better-plan-install-paths-probe"))
        for removed in (
            "opencode_config",
            "copilot_home",
            "antigravity_home",
            "pi_home",
            "craft_home",
            "kimi_home",
        ):
            with self.subTest(attribute=removed):
                self.assertFalse(hasattr(paths, removed), removed)
        self.assertFalse(hasattr(install_models, "WslOpenCodeRuntime"))

    def test_failed_tree_publication_restores_the_previous_installation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            parent = Path(tmpdir)
            target = parent / "installation"
            target.mkdir()
            original = target / "SKILL.md"
            original.write_text("usable previous installation\n", encoding="utf-8")
            before = original.read_bytes()
            rename = Path.rename

            def fail_publication(path, destination):
                if path.name == "prepared" and destination == target:
                    raise OSError("simulated publication failure")
                return rename(path, destination)

            with mock.patch.object(Path, "rename", fail_publication):
                with self.assertRaises(install_models.InstallError):
                    with install_skills.staged_tree(target) as prepared:
                        (prepared / "SKILL.md").write_text("replacement\n", encoding="utf-8")

            self.assertEqual(original.read_bytes(), before)
            self.assertEqual(set(parent.iterdir()), {target})

    def test_first_role_installation_preserves_a_collision_after_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            directory = native_role_directory(paths)
            payload = install_targets._native_payload(paths, "codex")
            role = directory / payload[0][0]

            def discover_with_new_local_role(*args):
                directory.mkdir(parents=True)
                role.write_bytes(b"local role created during discovery\n")
                return payload

            with mock.patch.object(install_targets, "_native_payload", side_effect=discover_with_new_local_role):
                with self.assertRaises(install_models.InstallError):
                    install_targets.install_role_templates(paths, "codex", dry_run=False)

            self.assertEqual(role.read_bytes(), b"local role created during discovery\n")
            self.assertEqual(set(directory.iterdir()), {role})
            self.assertFalse(directory.with_name("agents.better-plan.json").exists())

    def test_codex_installs_exactly_four_preset_roles(self) -> None:
        self.assertEqual(
            NATIVE_ROLE_FILES["codex"],
            ("designer.toml", "worker.toml", "hybrid-worker.toml", "reviewer.toml"),
        )
        self.assertEqual(
            tuple(CODEX_DEFAULT_MATRIX),
            ("designer", "worker", "hybrid-worker", "reviewer"),
        )
        self.assertFalse(hasattr(install_targets, "CODEX_FINDER_MATRIX"))
        self.assertFalse(any("finder" in name for name in install_models.CURRENT_SKILL_FILES))
        self.assertFalse([path.name for path in (REPO_ROOT / "agents" / "codex").iterdir() if "finder" in path.name])

        models = {model.model_id: model for model in load_model_catalog().models}
        variants = {variant.variant_id: variant for variant in load_coding_agent_catalog().variants}
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            messages = install_service.install_agents(paths, ["codex"], dry_run=False)
            directory = native_role_directory(paths)
            receipt = json.loads(
                directory.with_name("agents.better-plan.json").read_text(encoding="utf-8")
            )

            self.assertEqual({path.name for path in directory.iterdir()}, set(NATIVE_ROLE_FILES["codex"]))
            self.assertEqual(set(receipt["assignments"]), set(NATIVE_ROLE_FILES["codex"]))
            for agent_name, (role, model, effort, benchmark_id, score, cost) in CODEX_PRESET.items():
                with self.subTest(agent=agent_name):
                    assignment = receipt["assignments"][f"{agent_name}.toml"]
                    self.assertEqual(
                        (
                            assignment["role"],
                            assignment["agent_name"],
                            assignment["model"],
                            assignment["reasoning_effort"],
                            assignment["benchmark_id"],
                            assignment["index_score"],
                            assignment["source"],
                        ),
                        (role, agent_name, model, effort, benchmark_id, score, "codex-default-matrix"),
                    )
                    if cost is None:
                        self.assertIsNone(assignment["cost_per_task_usd"])
                    else:
                        self.assertAlmostEqual(assignment["cost_per_task_usd"], cost)
                    text = (directory / f"{agent_name}.toml").read_text(encoding="utf-8")
                    self.assertNotIn("ASSIGNMENT_PLACEHOLDER", text)
                    self.assertIn(f'model = "{model}"', text)
                    self.assertIn(f'model_reasoning_effort = "{effort}"', text)
                    prompt = text.split('developer_instructions = """', 1)[1].rsplit('"""', 1)[0]
                    self.assertIn(f"Role identity: agent={agent_name} | role={role}", prompt)
                    self.assertIn("host-provided runtime metadata", prompt)
                    self.assertNotIn("benchmark=", prompt)
                    self.assertNotIn(model, prompt)

            # The receipt records provenance from the packaged rows themselves.
            self.assertEqual(
                receipt["assignments"]["designer.toml"]["index_score"],
                models["gpt-6-astra"].intelligence_index,
            )
            self.assertEqual(
                receipt["assignments"]["reviewer.toml"]["index_score"],
                models["gpt-6-astra-xhigh"].intelligence_index,
            )
            self.assertEqual(
                receipt["assignments"]["hybrid-worker.toml"]["index_score"],
                models["gpt-6-astra-low"].intelligence_index,
            )
            self.assertEqual(
                receipt["assignments"]["worker.toml"]["cost_per_task_usd"],
                variants["codex-gpt-6-luna-max"].cost_per_task_usd,
            )
            # The two published indices are different scales, so the receipt names the one it used.
            self.assertEqual(
                {
                    name: receipt["assignments"][f"{name}.toml"]["index_basis"]
                    for name in ("designer", "hybrid-worker", "reviewer", "worker")
                },
                {
                    "designer": "intelligence",
                    "hybrid-worker": "intelligence",
                    "reviewer": "intelligence",
                    "worker": "coding_agent",
                },
            )
            assignment_message = next(
                message for message in messages if "immutable after first installation" in message
            )
            self.assertIn("worker -> worker, gpt-6-luna/max, Coding Agent score 41", assignment_message)
            self.assertIn("hybrid-worker -> worker, gpt-6-astra/low", assignment_message)
            self.assertIn("Intelligence Index proxy score 46", assignment_message)
            self.assertIn("source codex-default-matrix", assignment_message)

    def test_native_role_templates_use_exact_paths_and_survive_updates_and_uninstall(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            for target, filenames in NATIVE_ROLE_FILES.items():
                with self.subTest(target=target):
                    directory = native_role_directory(paths, target)
                    directory.mkdir(parents=True, exist_ok=True)
                    unrelated = directory / "user-owned-agent.toml"
                    unrelated.write_text('name = "user-owned"\n', encoding="utf-8")

                    install_targets.install_role_templates(paths, target, dry_run=False)
                    # Only Codex keeps a selector receipt; the unpinned hosts have none by design.
                    receipt_path = directory.with_name("agents.better-plan.json")
                    unpinned = target in install_targets.UNPINNED_HOSTS
                    receipt_before = None if unpinned else receipt_path.read_bytes()
                    if unpinned:
                        self.assertFalse(receipt_path.exists())
                        installed_filenames = filenames
                    else:
                        receipt = json.loads(receipt_before)
                        installed_filenames = tuple(receipt["files"])
                    first = {
                        filename: (directory / filename).read_bytes()
                        for filename in installed_filenames
                    }
                    self.assertTrue(first)
                    self.assertTrue(all(b"ASSIGNMENT_PLACEHOLDER" not in content for content in first.values()))
                    if unpinned:
                        self.assertTrue(
                            all(b"model=host-inherited" in content for content in first.values())
                        )
                    else:
                        self.assertTrue(all(b"Role identity:" in content for content in first.values()))
                    self.assertEqual(
                        {path.name for path in directory.iterdir()},
                        set(installed_filenames) | {unrelated.name},
                    )

                    install_targets.install_role_templates(paths, target, dry_run=False)
                    self.assertEqual(
                        {
                            filename: (directory / filename).read_bytes()
                            for filename in installed_filenames
                        },
                        first,
                    )
                    self.assertEqual(unrelated.read_text(encoding="utf-8"), 'name = "user-owned"\n')

                    dry_run_messages = install_targets.remove_target(
                        paths, target, dry_run=True
                    )
                    self.assertTrue(all((directory / name).is_file() for name in installed_filenames))
                    self.assertTrue(unrelated.is_file())
                    self.assertFalse(
                        any(str(Path(tmpdir)) in message for message in dry_run_messages)
                    )

                    install_targets.remove_target(paths, target, dry_run=False)
                    self.assertTrue(unrelated.is_file())
                    self.assertEqual(
                        {name: (directory / name).read_bytes() for name in installed_filenames},
                        first,
                    )
                    if receipt_before is not None:
                        self.assertEqual(receipt_path.read_bytes(), receipt_before)

    def test_dry_run_validates_each_native_source_without_writing_destinations(self) -> None:
        for target, filenames in NATIVE_ROLE_FILES.items():
            with self.subTest(target=target), tempfile.TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                source_root = root / "source"
                source_directory = NATIVE_SOURCE_DIRECTORIES[target]
                shutil.copytree(
                    REPO_ROOT / "agents" / source_directory,
                    source_root / "agents" / source_directory,
                )
                (source_root / "agents" / source_directory / filenames[1]).write_text(
                    "malformed native agent payload\n",
                    encoding="utf-8",
                )
                paths = make_paths(root, repo_root=source_root)

                with self.assertRaises(install_models.InstallError) as error:
                    install_targets.install_role_templates(paths, target, dry_run=True)

                self.assertFalse(native_role_directory(paths, target).exists())
                self.assertNotIn(tmpdir, str(error.exception))

    def test_installing_one_target_does_not_create_the_other_host_surface(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            codex_paths = make_paths(root / "codex")
            install_service.install_agents(codex_paths, ["codex"], dry_run=False)
            self.assertEqual(
                {path.name for path in native_role_directory(codex_paths).iterdir()},
                set(NATIVE_ROLE_FILES["codex"]),
            )
            self.assertFalse(codex_paths.kilo_agents.exists())
            self.assertFalse(codex_paths.kilo_skill.exists())

            kilo_paths = make_paths(root / "kilo")
            install_service.install_agents(kilo_paths, ["kilo"], dry_run=False)
            self.assertEqual(
                {path.name for path in kilo_paths.kilo_agents.iterdir()},
                set(install_targets.KILO_AGENT_FILES),
            )
            self.assertFalse(native_role_directory(kilo_paths).exists())
            self.assertFalse(kilo_paths.codex_hooks.exists())

    def test_existing_same_name_role_is_never_adopted_or_completed_into_a_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            directory = native_role_directory(paths)
            directory.mkdir(parents=True)
            local_role = directory / "designer.toml"
            local_role.write_text("local host configuration\n", encoding="utf-8")

            messages = install_service.install_agents(paths, ["codex"], dry_run=False)

            self.assertIn("native: preserved codex role templates", messages)
            self.assertEqual(local_role.read_text(encoding="utf-8"), "local host configuration\n")
            self.assertEqual({path.name for path in directory.iterdir()}, {"designer.toml"})
            self.assertFalse(directory.with_name("agents.better-plan.json").exists())
            self.assertTrue((paths.shared_skill / "SKILL.md").is_file())
            self.assertTrue(paths.codex_hooks.is_file())

    def test_update_always_repairs_skill_and_hooks_without_touching_existing_roles(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            install_service.install_agents(paths, ["codex"], dry_run=False)
            role = native_role_directory(paths) / "worker.toml"
            receipt = native_role_directory(paths).with_name("agents.better-plan.json")
            role.write_text("locally modified role\n", encoding="utf-8")
            role_before = role.read_bytes()
            receipt_before = receipt.read_bytes()
            (paths.shared_skill / "SKILL.md").write_text("stale skill\n", encoding="utf-8")

            hooks = json.loads(paths.codex_hooks.read_text(encoding="utf-8"))
            hooks["hooks"]["PostToolUse"] = [
                {
                    "matcher": "^Agent$",
                    "hooks": [
                        {
                            "type": "command",
                            "command": hook_config.hook_command("codex", "agent-complete"),
                            "timeout": hook_config.HOOK_TIMEOUT_SECONDS,
                        }
                    ],
                }
            ]
            paths.codex_hooks.write_text(
                json.dumps(hooks, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            messages = install_service.install_agents(
                paths,
                ["codex"],
                dry_run=False,
            )

            self.assertIn("native: preserved codex role templates", messages)
            self.assertEqual(role.read_bytes(), role_before)
            self.assertEqual(receipt.read_bytes(), receipt_before)
            self.assertEqual(
                (paths.shared_skill / "SKILL.md").read_bytes(),
                (REPO_ROOT / "SKILL.md").read_bytes(),
            )
            repaired_hooks = json.loads(paths.codex_hooks.read_text(encoding="utf-8"))
            self.assertEqual(set(repaired_hooks["hooks"]), {"SessionStart", "UserPromptSubmit"})

    def test_install_creates_only_the_two_host_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            home = paths.codex_home.parent

            messages = install_service.install_agents(paths, list(install_models.AGENTS), dry_run=False)

            self.assertIn("shared: updated skill", messages)
            self.assertIn("codex: using shared skill", messages)
            self.assertIn("kilo: using shared skill", messages)
            self.assertIn("native: installed codex role templates", messages)
            self.assertIn("native: installed kilo Agent matrix", messages)
            self.assertIn("codex hooks: updated managed handlers", messages)
            self.assertIn("codex: no duplicate native skill", messages)
            self.assertIn("kilo: no duplicate native skill", messages)
            self.assertTrue((paths.shared_skill / "SKILL.md").is_file())
            self.assertTrue((paths.shared_skill / "references" / "design-patterns.md").is_file())
            self.assertFalse(paths.codex_skill.exists())
            self.assertFalse(paths.kilo_skill.exists())
            self.assertEqual(
                {path.name for path in native_role_directory(paths).iterdir()},
                set(NATIVE_ROLE_FILES["codex"]),
            )
            self.assertEqual(
                {path.name for path in paths.kilo_agents.iterdir()},
                set(install_targets.KILO_AGENT_FILES),
            )
            self.assertTrue(paths.kilo_agents.with_name("agents.better-plan.json").is_file())
            self.assertEqual(
                paths.codex_hooks.read_text(encoding="utf-8").count("--managed-by better-plan"),
                2,
            )
            for relative in RETIRED_HOST_SURFACES:
                with self.subTest(surface=relative):
                    self.assertFalse((home / relative).exists(), relative)
            self.assertFalse([message for message in messages if str(Path(tmpdir)) in message], messages)

    def test_kilo_matrix_is_installed_once_and_never_adopted_or_rewritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            messages = install_service.install_agents(paths, ["kilo"], dry_run=False)
            receipt = paths.kilo_agents.with_name("agents.better-plan.json")
            expected = set(install_targets.KILO_AGENT_FILES)

            self.assertIn("native: installed kilo Agent matrix", messages)
            self.assertEqual({path.name for path in paths.kilo_agents.iterdir()}, expected)
            self.assertTrue((paths.shared_skill / "SKILL.md").is_file())
            self.assertFalse(paths.kilo_skill.exists())
            self.assertTrue(receipt.is_file())
            for filename in install_targets.KILO_SUBAGENTS:
                text = (paths.kilo_agents / filename).read_text(encoding="utf-8")
                self.assertNotIn("model:", text)
                self.assertNotIn("variant:", text)
                self.assertNotIn("reasoning_effort:", text)
                self.assertNotIn("reasoningEffort:", text)
                self.assertIn("model=parent-inherited", text)
                self.assertIn("reasoning_effort=host-default", text)
            listing = "\n".join(Path(name).stem for name in install_targets.KILO_AGENT_FILES)
            with mock.patch.object(install_doctor.shutil, "which", return_value="kilo"), mock.patch.object(
                install_targets,
                "run_text_command",
                return_value=subprocess.CompletedProcess(
                    ["kilo", "agent", "list"],
                    0,
                    stdout=listing,
                    stderr="",
                ),
            ):
                runtime_check = install_doctor.check_kilo_agents(paths)
            self.assertEqual(runtime_check.status, "OK")
            receipt_before = receipt.read_bytes()
            role = paths.kilo_agents / "better-plan-worker.md"
            role.write_text("local Kilo customization\n", encoding="utf-8")
            role_before = role.read_bytes()

            update_messages = install_service.install_agents(paths, ["kilo"], dry_run=False)

            self.assertIn("native: preserved kilo Agent matrix", update_messages)
            self.assertEqual(role.read_bytes(), role_before)
            self.assertEqual(receipt.read_bytes(), receipt_before)
            check = install_doctor.check_kilo_agents(paths)
            self.assertEqual(check.status, "WARN")
            self.assertNotIn(tmpdir, check.message)

            uninstall_messages = install_service.uninstall_agents(
                paths,
                ["kilo"],
                remove_shared=True,
                dry_run=False,
            )
            self.assertIn("kilo: preserved immutable native Agent matrix", uninstall_messages)
            self.assertTrue(role.is_file())
            self.assertTrue(receipt.is_file())
            self.assertFalse(paths.shared_skill.exists())

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            paths.kilo_agents.mkdir(parents=True)
            local = paths.kilo_agents / "better-plan-designer.md"
            local.write_text("user-owned Kilo Agent\n", encoding="utf-8")

            messages = install_service.install_agents(paths, ["kilo"], dry_run=False)

            self.assertIn("native: preserved kilo Agent matrix", messages)
            self.assertEqual(local.read_text(encoding="utf-8"), "user-owned Kilo Agent\n")
            self.assertEqual({path.name for path in paths.kilo_agents.iterdir()}, {local.name})
            self.assertFalse(paths.kilo_agents.with_name("agents.better-plan.json").exists())

    def test_kilo_subagent_templates_with_a_selector_pin_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_root = root / "source"
            shutil.copytree(REPO_ROOT / "agents" / "kilo", source_root / "agents" / "kilo")
            pinned = source_root / "agents" / "kilo" / "better-plan-worker.md"
            pinned.write_text(
                pinned.read_text(encoding="utf-8").replace(
                    "mode: subagent\n", "mode: subagent\nmodel: kilo/some-model\n", 1
                ),
                encoding="utf-8",
            )
            paths = make_paths(root, repo_root=source_root)

            with self.assertRaises(install_models.InstallError):
                install_targets.install_kilo_agent_matrix(paths, dry_run=True)

            self.assertFalse(paths.kilo_agents.exists())

    def test_uninstall_hooks_reports_no_managed_lifecycle_config_for_kilo(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            self.assertEqual(
                install_service.uninstall_hooks(paths, ["kilo"], dry_run=False),
                ["kilo: no managed lifecycle config"],
            )

    def test_managed_lifecycle_hook_command_is_portable_and_detector_gated(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            paths = make_paths(root)
            install_service.install_agents(paths, ["codex"], dry_run=False)
            codex = json.loads(paths.codex_hooks.read_text(encoding="utf-8"))
            managed_commands = [
                codex["hooks"]["SessionStart"][0]["hooks"][0]["command"],
                codex["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"],
            ]
            unrelated = root / "unrelated"
            unrelated.mkdir()
            (unrelated / ".git").mkdir()
            env = os.environ.copy()
            env["BETTER_PLAN_SHARED_HOME"] = str(paths.shared_home)
            env["CODEX_HOME"] = str(paths.codex_home)
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
            write_workspace(plan_workspace, complete_plan("main-plan"))

            result = subprocess.run(
                managed_commands[0],
                cwd=active,
                env=env,
                input=json.dumps({"cwd": str(active)}),
                shell=True,
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            output = json.loads(result.stdout)
            self.assertEqual(set(output.keys()), {"hookSpecificOutput"})
            self.assertEqual(set(output["hookSpecificOutput"].keys()), {"hookEventName", "additionalContext"})
            self.assertEqual(output["hookSpecificOutput"]["hookEventName"], "SessionStart")

    def test_doctor_accepts_installed_files_without_optional_clis(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            install_service.install_agents(paths, list(install_models.AGENTS), dry_run=False)

            with mock.patch.object(install_doctor.shutil, "which", return_value=None), mock.patch.object(
                install_doctor, "OPTIONAL_CLIENT_CLI_COMMANDS", {}
            ):
                checks = install_doctor.doctor(paths, list(install_models.AGENTS))

            self.assertFalse([check for check in checks if check.status == "FAIL"], checks)
            # A host may report more than one check under the same target label, so compare pairs.
            statuses = [(check.target, check.status) for check in checks]
            for expected in (
                ("codex native roles", "OK"),
                ("codex", "OK"),
                ("codex hooks", "OK"),
                ("claude native roles", "OK"),
                ("claude", "WARN"),
                ("claude hooks", "OK"),
                ("cursor native roles", "OK"),
                ("cursor", "OK"),
                ("cursor hooks", "OK"),
                ("kilo native Agents", "WARN"),
                ("kilo", "OK"),
                ("shared skill source", "OK"),
            ):
                with self.subTest(expected=expected):
                    self.assertIn(expected, statuses)

    def test_doctor_warns_about_tampered_local_roles_without_repairing_them(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            install_service.install_agents(paths, ["codex"], dry_run=False)
            directory = native_role_directory(paths)
            tampered_role = directory / "worker.toml"
            tampered_role.write_text("tampered\n", encoding="utf-8")
            receipt = directory.with_name("agents.better-plan.json")
            receipt_before = receipt.read_bytes()

            check = install_doctor.check_native_roles(paths, "codex")

            self.assertEqual(check.status, "WARN")
            self.assertEqual(check.target, "codex native roles")
            self.assertIn("local roles preserved", check.message)
            self.assertIn("changed outside Better Plan", check.message)
            self.assertNotIn(tmpdir, check.message)
            self.assertEqual(tampered_role.read_text(encoding="utf-8"), "tampered\n")
            self.assertEqual(receipt.read_bytes(), receipt_before)

    def test_doctor_warns_when_the_managed_receipt_records_no_roles(self) -> None:
        """An emptied receipt verifies nothing and must never be reported as a verified matrix."""

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            install_service.install_agents(paths, ["codex"], dry_run=False)
            directory = native_role_directory(paths)
            receipt = directory.with_name("agents.better-plan.json")
            roles_before = {path.name: path.read_bytes() for path in directory.iterdir()}

            def empty_receipt(value: dict) -> None:
                value["files"] = {}
                value["assignments"] = {}

            rewrite_receipt(receipt, empty_receipt)
            receipt_before = receipt.read_bytes()

            check = install_doctor.check_native_roles(paths, "codex")

            self.assertEqual(check.status, "WARN")
            self.assertEqual(check.target, "codex native roles")
            self.assertIn("records no role files", check.message)
            self.assertNotIn(tmpdir, check.message)
            self.assertEqual(receipt.read_bytes(), receipt_before)
            self.assertEqual({path.name: path.read_bytes() for path in directory.iterdir()}, roles_before)

    def test_a_receipt_written_before_index_basis_still_verifies(self) -> None:
        """The receipt is immutable: an older record must keep working after the format grows."""

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            install_service.install_agents(paths, ["codex"], dry_run=False)
            directory = native_role_directory(paths)
            receipt = directory.with_name("agents.better-plan.json")

            def drop_basis(value: dict) -> None:
                for assignment in value["assignments"].values():
                    assignment.pop("index_basis")

            rewrite_receipt(receipt, drop_basis)
            receipt_before = receipt.read_bytes()

            check = install_doctor.check_native_roles(paths, "codex")

            self.assertEqual(check.status, "OK")
            self.assertIn("local roles verified", check.message)
            self.assertEqual(receipt.read_bytes(), receipt_before)

    def test_kilo_status_reports_a_receipt_that_disagrees_without_repairing_it(self) -> None:
        """The Kilo receipt is report-only context: it is read, never rewritten or acted on."""

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            install_service.install_agents(paths, ["kilo"], dry_run=False)
            receipt = paths.kilo_agents.with_name("agents.better-plan.json")
            agents_before = {path.name: path.read_bytes() for path in paths.kilo_agents.iterdir()}

            def stale_digest(value: dict) -> None:
                value["files"]["better-plan-worker.md"] = "0" * 64

            rewrite_receipt(receipt, stale_digest)
            receipt_before = receipt.read_bytes()

            ok, message = install_targets.kilo_agent_status(paths)

            self.assertTrue(ok)
            self.assertIn("changed outside Better Plan", message)
            self.assertIn("report only", message)
            self.assertEqual(receipt.read_bytes(), receipt_before)
            self.assertEqual(
                {path.name: path.read_bytes() for path in paths.kilo_agents.iterdir()}, agents_before
            )

    def test_doctor_reports_a_stale_role_inventory_as_one_bounded_sentence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            install_service.install_agents(paths, ["codex"], dry_run=False)
            directory = native_role_directory(paths)
            receipt = directory.with_name("agents.better-plan.json")

            def drop_hybrid_worker(value: dict) -> None:
                value["files"].pop("hybrid-worker.toml")
                value["assignments"].pop("hybrid-worker.toml")

            rewrite_receipt(receipt, drop_hybrid_worker)
            (directory / "hybrid-worker.toml").unlink()
            receipt_before = receipt.read_bytes()
            roles_before = {path.name: path.read_bytes() for path in directory.iterdir()}

            check = install_doctor.check_native_roles(paths, "codex")

            self.assertEqual(check.status, "WARN")
            self.assertEqual(check.target, "codex native roles")
            self.assertEqual(
                check.message,
                "local roles preserved; missing packaged role(s): hybrid-worker",
            )
            self.assertNotIn(tmpdir, check.message)
            self.assertEqual(receipt.read_bytes(), receipt_before)
            self.assertEqual({path.name: path.read_bytes() for path in directory.iterdir()}, roles_before)

            def rename_reviewer_to_finder(value: dict) -> None:
                value["files"]["finder.toml"] = value["files"].pop("reviewer.toml")
                assignment = value["assignments"].pop("reviewer.toml")
                assignment["agent_name"] = "finder"
                value["assignments"]["finder.toml"] = assignment

            rewrite_receipt(receipt, rename_reviewer_to_finder)
            (directory / "reviewer.toml").rename(directory / "finder.toml")

            check = install_doctor.check_native_roles(paths, "codex")

            self.assertEqual(check.status, "WARN")
            self.assertEqual(
                check.message,
                "local roles preserved; missing packaged role(s): hybrid-worker "
                "(managed receipt records role(s) no longer installed: finder; report only)",
            )

    def test_doctor_fails_for_a_missing_install_without_local_roles(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))

            check = install_doctor.check_native_roles(paths, "codex")

            self.assertEqual(check.status, "FAIL")
            self.assertEqual(check.message, "no local Codex role files are installed")

    def test_doctor_distinguishes_valid_installation_from_source_equality(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            install_service.install_agents(paths, ["codex"], dry_run=False)
            reference = paths.shared_skill / "references" / "worker.md"
            reference.write_text("An earlier, structurally valid role contract.\n", encoding="utf-8")
            before = reference.read_bytes()

            checks = {check.target: check for check in install_doctor.doctor(paths, ["codex"])}

            self.assertEqual(checks["codex"].status, "OK")
            self.assertEqual(checks["shared skill source"].status, "WARN")
            self.assertIn("1 packaged file(s) differ", checks["shared skill source"].message)
            self.assertEqual(reference.read_bytes(), before)
            self.assertNotIn(tmpdir, checks["shared skill source"].message)
            install_service.install_agents(paths, ["codex"], dry_run=False)
            current = install_doctor.check_skill_source("shared", paths.shared_skill, REPO_ROOT)
            self.assertEqual(current.status, "OK")
            self_comparison = install_doctor.check_skill_source("shared", paths.shared_skill, paths.shared_skill)
            self.assertEqual(self_comparison.status, "WARN")
            self.assertIn("independent source tree", self_comparison.message)

    def test_installed_skill_inventory_requires_current_files(self) -> None:
        expected_runtime_payload = {
            "references/worker.md",
            "scripts/better_plan/domain/model_catalog.json",
            "scripts/better_plan/domain/coding_agent_catalog.json",
            "scripts/better_plan/domain/model_routing.py",
            "scripts/better_plan/domain/task_shape.py",
        }
        for target, filenames in NATIVE_ROLE_FILES.items():
            expected_runtime_payload.update(
                f"agents/{NATIVE_SOURCE_DIRECTORIES[target]}/{filename}" for filename in filenames
            )
        expected_runtime_payload.update(
            f"agents/kilo/{filename}" for filename in install_targets.KILO_AGENT_FILES
        )
        self.assertTrue(
            expected_runtime_payload <= set(install_models.CURRENT_SKILL_FILES),
            sorted(expected_runtime_payload - set(install_models.CURRENT_SKILL_FILES)),
        )

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
            self.assertFalse(paths.kilo_skill.exists())
            self.assertTrue((paths.kilo_agents / "better-plan.md").is_file())
            self.assertTrue(paths.kilo_agents.with_name("agents.better-plan.json").is_file())
            self.assertNotIn("--managed-by better-plan", paths.codex_hooks.read_text(encoding="utf-8"))
            self.assertIn("codex: preserved immutable native role templates", messages)
            self.assertIn("kilo: preserved immutable native Agent matrix", messages)

    def test_supported_hook_install_is_idempotent_and_preserves_unrelated_configuration(self) -> None:
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

            for _ in range(2):
                install_service.install_agents(paths, ["codex"], dry_run=False)

            self.assertEqual(
                paths.codex_hooks.read_text(encoding="utf-8").count("--managed-by better-plan"),
                2,
            )

            install_service.uninstall_agents(
                paths,
                ["codex"],
                remove_shared=True,
                dry_run=False,
            )
            install_service.uninstall_hooks(
                paths,
                ["codex"],
                dry_run=False,
            )

            codex = json.loads(paths.codex_hooks.read_text(encoding="utf-8"))
            self.assertTrue(codex["custom"])
            self.assertEqual(codex["hooks"]["SessionStart"][0]["hooks"][0]["command"], "custom-codex")
            self.assertNotIn("--managed-by better-plan", json.dumps(codex))

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
                                    ],
                                }
                            ],
                        },
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )

            install_service.install_agents(paths, ["codex"], dry_run=False)

            shared_skill = (paths.shared_skill / "SKILL.md").read_bytes()
            codex_config_before = json.loads(paths.codex_hooks.read_text(encoding="utf-8"))
            role_directory = native_role_directory(paths)
            roles_before = {path.name: path.read_bytes() for path in role_directory.iterdir()}
            receipt_before = role_directory.with_name("agents.better-plan.json").read_bytes()

            messages = install_service.uninstall_hooks(paths, ["codex"], dry_run=False)

            self.assertFalse(any(str(Path(tmpdir)) in message for message in messages), messages)
            self.assertTrue(any("removed managed handlers" in message for message in messages), messages)
            self.assertEqual(shared_skill, (paths.shared_skill / "SKILL.md").read_bytes(), "skill tree changed on hook-only uninstall")
            self.assertFalse((paths.codex_skill / "SKILL.md").exists(), "native codex skill should not exist for shared install path")
            self.assertEqual(
                {path.name: path.read_bytes() for path in role_directory.iterdir()},
                roles_before,
                "native roles changed on hook-only uninstall",
            )
            self.assertEqual(
                role_directory.with_name("agents.better-plan.json").read_bytes(),
                receipt_before,
                "native role receipt changed on hook-only uninstall",
            )
            codex_config_after = json.loads(paths.codex_hooks.read_text(encoding="utf-8"))
            self.assertEqual(codex_config_before["meta"], codex_config_after.get("meta"))
            self.assertEqual(codex_config_before["custom"], codex_config_after.get("custom"))
            self.assertEqual(
                codex_config_before["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"],
                codex_config_after["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"],
            )
            self.assertNotIn("SessionStart", codex_config_after["hooks"])
            self.assertIn("UserPromptSubmit", codex_config_after["hooks"])
            self.assertIn("keep-before-codex", paths.codex_hooks.read_text(encoding="utf-8"))
            self.assertNotIn("--managed-by better-plan", paths.codex_hooks.read_text(encoding="utf-8"))

            parser = install_cli.build_parser()
            parsed = parser.parse_args(["uninstall-hooks", "--agents", "codex"])
            self.assertIs(parsed.func, install_cli.uninstall_hooks_command)

    def test_managed_lifecycle_inventory_is_exact_and_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            install_service.install_agents(paths, ["codex"], dry_run=False)
            self.assertLessEqual(hook_config.HOOK_TIMEOUT_SECONDS, 30)

            handlers = hook_config.nested_handlers("codex")
            self.assertEqual(set(handlers.keys()), {"SessionStart", "UserPromptSubmit"})
            for _event, groups in handlers.items():
                self.assertEqual(len(groups), 1)
                self.assertNotIn("matcher", groups[0])
                hooks = groups[0]["hooks"]
                self.assertEqual(len(hooks), 1)
                self.assertEqual(hooks[0]["timeout"], hook_config.HOOK_TIMEOUT_SECONDS)

            config = json.loads(paths.codex_hooks.read_text(encoding="utf-8"))
            commands = hook_config.configured_commands(config, "codex")
            for values in commands.values():
                self.assertEqual(len(values), 1)

    def test_doctor_fails_when_the_codex_hook_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            install_service.install_agents(paths, ["codex"], dry_run=False)
            path = install_targets.hook_config_path(paths, "codex")
            data = json.loads(path.read_text(encoding="utf-8"))
            data.setdefault("hooks", {}).pop("SessionStart", None)
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

            ok, message = hook_config.hook_config_status(path, "codex")
            self.assertFalse(ok, message)
            check = install_doctor.check_agent_hooks(paths, "codex")
            self.assertEqual(check.status, "FAIL", check.message)

    def test_managed_hook_validation_fails_for_malformed_missing_and_duplicate_owned_handlers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            install_service.install_agents(paths, ["codex"], dry_run=False)
            path = install_targets.hook_config_path(paths, "codex")

            path.write_text("{}", encoding="utf-8")
            ok, message = hook_config.hook_config_status(path, "codex")
            self.assertFalse(ok, message)

            path.write_text(json.dumps({"hooks": []}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            with self.assertRaises(hook_config.HookConfigError):
                hook_config.install_hook_config(path, "codex", dry_run=False)

            path.write_text("{}\n", encoding="utf-8")
            install_service.install_agents(paths, ["codex"], dry_run=False)
            data = json.loads(path.read_text(encoding="utf-8"))
            handlers = data["hooks"]["SessionStart"]
            self.assertIsInstance(handlers, list)
            handlers.append(handlers[0])
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

            ok, message = hook_config.hook_config_status(path, "codex")
            self.assertFalse(ok, message)
            check = install_doctor.check_agent_hooks(paths, "codex")
            self.assertEqual(check.status, "FAIL", check.message)

    def test_doctor_rejects_noncanonical_managed_handler_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = make_paths(Path(tmpdir))
            install_service.install_agents(paths, ["codex"], dry_run=False)
            path = install_targets.hook_config_path(paths, "codex")
            data = json.loads(path.read_text(encoding="utf-8"))
            data["hooks"]["SessionStart"][0]["hooks"][0]["timeout"] = 999
            path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            ok, _ = hook_config.hook_config_status(path, "codex")
            self.assertFalse(ok)

            install_service.install_agents(paths, ["codex"], dry_run=False)
            repaired, message = hook_config.hook_config_status(path, "codex")
            self.assertTrue(repaired, message)

    def test_cli_default_install_and_doctor_support_temp_homes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            home = root / "home"
            codex_home = home / ".codex"
            shared_home = home / ".agents"
            kilo_home = home / ".kilo"
            kilo_config = home / ".config" / "kilo"
            isolated_env = os.environ.copy()
            isolated_env["PATH"] = ""

            install_result = run_command(
                sys.executable,
                INSTALL_TOOL_PATH,
                "--agents",
                "codex,kilo",
                "--codex-home",
                codex_home,
                "--shared-home",
                shared_home,
                "--kilo-home",
                kilo_home,
                "--kilo-config",
                kilo_config,
                env=isolated_env,
            )
            self.assertEqual(install_result.returncode, 0, install_result.stderr)
            self.assertIn("shared: updated", install_result.stdout)
            self.assertIn("codex: using shared skill", install_result.stdout)
            self.assertIn("kilo: using shared skill", install_result.stdout)
            self.assertIn("native: installed codex role templates", install_result.stdout)
            self.assertIn("native: installed kilo Agent matrix", install_result.stdout)
            self.assertIn("codex hooks: updated managed handlers", install_result.stdout)
            for relative in RETIRED_HOST_SURFACES:
                self.assertFalse((home / relative).exists(), relative)
            self.assertNotIn(str(root), install_result.stdout + install_result.stderr)

            doctor_result = run_command(
                sys.executable,
                INSTALL_TOOL_PATH,
                "doctor",
                "--agents",
                "codex,kilo",
                "--codex-home",
                codex_home,
                "--shared-home",
                shared_home,
                "--kilo-home",
                kilo_home,
                "--kilo-config",
                kilo_config,
                env=isolated_env,
            )
            self.assertEqual(doctor_result.returncode, 0, doctor_result.stderr)
            self.assertIn("OK: codex native roles:", doctor_result.stdout)
            self.assertIn("OK: codex:", doctor_result.stdout)
            self.assertIn("OK: codex hooks:", doctor_result.stdout)
            self.assertIn("WARN: kilo native Agents:", doctor_result.stdout)
            self.assertIn("OK: kilo:", doctor_result.stdout)
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
            self.assertIn("native: installed", update_result.stdout)
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
            paths.codex_hooks.parent.mkdir(parents=True)
            paths.codex_hooks.write_text("{}\n", encoding="utf-8")
            (paths.shared_skill / "SKILL.md").parent.mkdir(parents=True)
            (paths.shared_skill / "SKILL.md").write_text("stale\n", encoding="utf-8")

            install_service.install_agents(paths, ["codex", "kilo"], dry_run=False)

            self.assertEqual([], list(Path(tmpdir).rglob("*bak-better-plan-*")))


if __name__ == "__main__":
    unittest.main()
