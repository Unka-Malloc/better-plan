from __future__ import annotations

import json
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.better_plan.hooks import protocols
from scripts.better_plan.hooks import context as hook_context
from scripts.better_plan.hooks import runtime as hook_tool


REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK_TOOL = REPO_ROOT / "scripts" / "hook_tool.py"
PLAN_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
NODE_A_ID = "11111111-1111-4111-8111-111111111111"
ENTRY_LIFECYCLE_POLICY_TERMS = (
    "acceptance",
    "node",
    "lifecycle",
    "focused test",
    "regression",
    "repair",
    "audit",
    "completion",
    "selector",
)


def command_line(*values: str) -> str:
    arguments = list(values)
    return subprocess.list2cmdline(arguments) if sys.platform == "win32" else shlex.join(arguments)


def active_node(
    node_id: str,
    *,
    goal: str = "Exercise the lifecycle Hook.",
    status: str = "in_progress",
    platform: str = "any",
    command: str | None = None,
    role: str = "implementation",
    scope: str = "focused",
    with_design: bool = True,
) -> dict[str, object]:
    node = {
        "id": node_id,
        "status": status,
        "role": role,
        "prerequisites": [],
        "platform": platform,
        "difficulty": "high",
        "goal": goal,
        "description": "Scope: Closure: module - Hook test fixture. Context: test. Target: deterministic behavior.",
        "requirements": ["REQ-004"],
        "acceptance_criteria": [{"checked": False, "text": "The declared regression passes."}],
        "commit": {"repository": ".git", "message": "test Hook", "target": "tests"},
        "regression": {
            "scope": scope,
            "commands": [command or command_line(sys.executable, "-c", "pass")],
            "criteria": [0],
            "paths": ["tracked.txt"],
        },
        "next": [],
    }
    if with_design and role in {"implementation", "final_validation"}:
        node["design"] = {
            "artifact": "docs/plan/acceptance-state-machine/Architecture.md",
            "owned_paths": ["scripts/hook_tool.py", "scripts/manifest_tool.py"],
            "scaffold_paths": ["scripts/manifest_tool.py"],
            "acceptance_paths": ["tests/test_hook_tool.py", "docs/plan/acceptance-state-machine/Architecture.md"],
            "symbols": [
                {
                    "path": "scripts/hook_tool.py",
                    "kind": "function",
                    "name": "next_action_response",
                    "operation": "modify",
                    "signature": "next_action_response(state: dict[str, object]) -> dict[str, object]",
                }
            ],
            "interfaces": [
                {
                    "name": "next_action_response",
                    "producer": "scripts/hook_tool.py",
                    "consumers": ["scripts/manifest_tool.py"],
                    "inputs": "validated immutable state",
                    "outputs": "bounded next-action payload",
                    "errors": ["ValueError for an invalid state"],
                }
            ],
            "dependencies": [
                {
                    "from": "scripts/manifest_tool.py",
                    "to": "scripts/hook_tool.py",
                    "reason": "reads design and acceptance bindings for bounded handoff",
                }
            ],
            "decisions": {
                "composition": "compose pure transition lookup from immutable tables",
                "algorithms": "constant-time transition lookup",
                "data_structures": "mapping",
                "state": "single serialized Plan snapshot",
                "isolation": "role-specific writable boundaries",
                "concurrency": "serialise writes per Plan",
            },
            "test_seams": ["tests/test_hook_tool.py"],
        }
    return node


def plan(directory: str) -> dict[str, object]:
    return {
        "id": PLAN_ID,
        "status": "in_progress",
        "title": "Hook fixture",
        "directory": directory,
        "source_files": [],
        "goal": "Exercise Hook behavior.",
        "description": "Temporary structural Better Plan workspace.",
        "checkpoints": f"{directory}/Checkpoints.json",
    }


def write_workspace(project: Path, nodes: list[dict[str, object]], *, workspace_name: str = "docs/plan") -> Path:
    workspace = project / workspace_name
    plan_dir = workspace / "main-plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "Checkpoints.json").write_text(json.dumps(nodes), encoding="utf-8")
    (workspace / "Manifest.json").write_text(json.dumps([plan("main-plan")]), encoding="utf-8")
    return workspace


def run_hook(
    agent: str,
    payload: dict[str, object],
    *,
    event: str = "session-start",
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(HOOK_TOOL),
            "--agent",
            agent,
            "--event",
            event,
            "--managed-by",
            "better-plan",
        ],
        cwd=REPO_ROOT,
        input=json.dumps(payload),
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


class HookToolTests(unittest.TestCase):
    def assert_entry_only_guidance(self, context: str) -> None:
        lowered = " ".join(context.lower().split())

        self.assertLessEqual(len(context.split()), 50)
        self.assertIn("better plan", lowered)
        self.assertRegex(lowered, r"\bplanning\b")
        self.assertRegex(lowered, r"\b(?:code|coding)\b")
        self.assertRegex(lowered, r"\bexplicit implementation\b")
        self.assertRegex(
            lowered,
            r"\b(?:otherwise|other (?:requests?|work|tasks?)|all other)\b",
        )
        self.assertRegex(lowered, r"\buser(?:'s)? (?:request|instructions?|direction)\b")
        self.assertRegex(lowered, r"\b(?:answer|respond|native workflow)\b")
        self.assertRegex(lowered, r"\botherwise\b[^.]*\baccordingly\b")
        self.assertNotRegex(lowered, r"\bnormally\b")
        for policy_term in ENTRY_LIFECYCLE_POLICY_TERMS:
            self.assertNotIn(policy_term, lowered)

    def make_project(self, root: Path) -> Path:
        project = root / "project"
        project.mkdir()
        (project / ".git").mkdir()
        (project / "tracked.txt").write_text("stable\n", encoding="utf-8")
        return project

    def test_no_workspace_is_a_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            payload = {"cwd": tmpdir}
            results = [
                run_hook(
                    agent,
                    {**payload, **({"tool_name": "Agent"} if event == "agent-complete" else {})},
                    event=event,
                )
                for event in ("session-start", "prompt-submit", "agent-complete")
                for agent in ("codex", "claude", "cursor", "antigravity", "kimi")
            ]

        for index, result in enumerate(results):
            self.assertEqual(result.returncode, 0, result.stderr)
            if index % 5 == 4:
                self.assertEqual(result.stdout, "")
            else:
                self.assertEqual(json.loads(result.stdout), {})

    def test_session_start_injects_only_short_intent_guidance(self) -> None:
        for agent in ("codex", "claude"):
            with self.subTest(agent=agent), tempfile.TemporaryDirectory() as tmpdir:
                project = self.make_project(Path(tmpdir))
                write_workspace(project, [active_node(NODE_A_ID)])

                result = run_hook(agent, {"cwd": str(project)}, event="session-start")

                self.assertEqual(result.returncode, 0, result.stderr)
                response = json.loads(result.stdout)
                specific = response["hookSpecificOutput"]
                self.assertEqual(specific["hookEventName"], "SessionStart")
                context = specific["additionalContext"]
                self.assertEqual(context, hook_context.INTENT_GUIDANCE)
                self.assert_entry_only_guidance(context)

    def test_intent_guidance_contains_only_progressive_entry_routing(self) -> None:
        context = hook_context.INTENT_GUIDANCE

        self.assert_entry_only_guidance(context)
        for concrete_name in (
            "licolite",
            "kimi",
            "claude",
            "cursor",
            "codex",
            "copilot",
            "gemini",
            "opencode",
        ):
            self.assertNotIn(concrete_name, context)

    def test_prompt_submit_injects_only_short_intent_guidance(self) -> None:
        sentinel = "PRIVATE-PROMPT-AND-PLAN-SENTINEL"
        for agent in ("codex", "claude"):
            with self.subTest(agent=agent), tempfile.TemporaryDirectory() as tmpdir:
                project = self.make_project(Path(tmpdir))
                workspace = write_workspace(project, [active_node(NODE_A_ID)])
                manifest = json.loads((workspace / "Manifest.json").read_text(encoding="utf-8"))
                manifest[0]["goal"] = sentinel
                (workspace / "Manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

                result = run_hook(agent, {"cwd": str(project), "prompt": sentinel}, event="prompt-submit")

                self.assertEqual(result.returncode, 0, result.stderr)
                response = json.loads(result.stdout)["hookSpecificOutput"]
                self.assertEqual(response["hookEventName"], "UserPromptSubmit")
                context = response["additionalContext"]
                self.assertEqual(context, hook_context.INTENT_GUIDANCE)
                self.assert_entry_only_guidance(context)
                self.assertNotIn(sentinel, context)

    def test_hook_cli_rejects_unknown_event_and_keeps_stdout_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self.make_project(Path(tmpdir))
            payload = {"cwd": str(project)}
            result = run_hook("codex", payload, event="unknown-stage")

            self.assertNotEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")

    def test_cursor_session_context_uses_flat_additional_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self.make_project(Path(tmpdir))
            write_workspace(project, [active_node(NODE_A_ID)])

            result = run_hook("cursor", {"cwd": str(project)}, event="session-start")

            self.assertEqual(result.returncode, 0, result.stderr)
            response = json.loads(result.stdout)
            self.assertEqual(set(response.keys()), {"additional_context"})
            context = response["additional_context"]
            self.assertEqual(context, hook_context.INTENT_GUIDANCE)

    def test_antigravity_injects_guidance_only_on_first_invocation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self.make_project(Path(tmpdir))
            write_workspace(project, [active_node(NODE_A_ID)])
            payload = {"workspacePaths": [str(project)], "invocationNum": 0}

            first = run_hook("antigravity", payload, event="session-start")
            later = run_hook(
                "antigravity",
                {**payload, "invocationNum": 1},
                event="session-start",
            )

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(
                json.loads(first.stdout),
                {"injectSteps": [{"ephemeralMessage": hook_context.INTENT_GUIDANCE}]},
            )
            self.assertEqual(json.loads(later.stdout), {})

    def test_cursor_prompt_submit_returns_continue_only(self) -> None:
        sentinel = "private-cursor-prompt"
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self.make_project(Path(tmpdir))
            write_workspace(project, [active_node(NODE_A_ID)])

            result = run_hook(
                "cursor",
                {"cwd": str(project), "prompt": sentinel},
                event="prompt-submit",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), {"continue": True})

    def test_kimi_lifecycle_uses_native_plain_text_and_empty_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self.make_project(Path(tmpdir))
            write_workspace(project, [active_node(NODE_A_ID)])

            session = run_hook("kimi", {"cwd": str(project)}, event="session-start")
            prompt = run_hook(
                "kimi",
                {"cwd": str(project), "prompt": "implement the requested change"},
                event="prompt-submit",
            )
            unrelated_completion = run_hook(
                "kimi",
                {"cwd": str(project)},
                event="agent-complete",
            )

            self.assertEqual(session.returncode, 0, session.stderr)
            self.assertEqual(session.stdout.strip(), hook_context.INTENT_GUIDANCE)
            self.assertEqual(prompt.returncode, 0, prompt.stderr)
            self.assertEqual(prompt.stdout.strip(), hook_context.INTENT_GUIDANCE)
            self.assertEqual(unrelated_completion.returncode, 0, unrelated_completion.stderr)
            self.assertEqual(unrelated_completion.stdout, "")

    def test_protocol_event_inventory_is_exact(self) -> None:
        self.assertEqual(
            dict(protocols.host_events("codex")),
            {
                "SessionStart": "session-start",
                "UserPromptSubmit": "prompt-submit",
                "PostToolUse": "agent-complete",
            },
        )
        self.assertEqual(
            dict(protocols.host_events("claude")),
            {
                "SessionStart": "session-start",
                "UserPromptSubmit": "prompt-submit",
                "PostToolUse": "agent-complete",
            },
        )
        self.assertEqual(
            dict(protocols.host_events("cursor")),
            {
                "sessionStart": "session-start",
                "beforeSubmitPrompt": "prompt-submit",
                "postToolUse": "agent-complete",
            },
        )
        self.assertEqual(
            dict(protocols.host_events("kimi")),
            {
                "SessionStart": "session-start",
                "UserPromptSubmit": "prompt-submit",
                "SubagentStop": "agent-complete",
            },
        )

    def test_protocols_reject_unknown_agent(self) -> None:
        with self.assertRaises(protocols.HookProtocolError):
            protocols.host_events("ghost_agent")

        with self.assertRaises(protocols.HookProtocolError):
            protocols.context_response("ghost_agent", "prompt-submit", "prompt")

        with self.assertRaises(protocols.HookProtocolError):
            protocols.prompt_allow_response("ghost_agent")

    def test_recognized_subagent_lifecycle_events_are_noops(self) -> None:
        cases = (
            ("codex", "session-start", {"hook_event_name": "SubagentStart"}),
            ("codex", "session-start", {"hook_event_name": "SubagentStop"}),
            ("claude", "prompt-submit", {"agent_id": "agent-child", "agent_type": "Explore"}),
            ("cursor", "session-start", {"is_subagent": True}),
        )
        for agent, event, marker in cases:
            with self.subTest(agent=agent, event=event), tempfile.TemporaryDirectory() as tmpdir:
                project = self.make_project(Path(tmpdir))
                write_workspace(project, [active_node(NODE_A_ID)])

                result = run_hook(
                    agent,
                    {"cwd": str(project), "status": "completed", **marker},
                    event=event,
                )

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), {})


if __name__ == "__main__":
    unittest.main()
