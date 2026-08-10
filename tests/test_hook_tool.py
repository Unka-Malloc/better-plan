"""Focused host Hook contracts for a Better Plan v3 workspace."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.better_plan.hooks import context as hook_context
from scripts.better_plan.hooks import protocols
from scripts.better_plan.hooks import runtime as hook_runtime
from scripts.better_plan.hooks import adapters as hook_adapters
from tests.v3_fixtures import complete_plan, write_workspace


REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK_TOOL = REPO_ROOT / "scripts" / "hook_tool.py"
# Intentionally independent from production code. This exact Hook entry prompt
# is a developer-gated compatibility contract: changing it requires an explicit
# developer request and a deliberate update to this fixture.
PROTECTED_ENTRY_GUIDANCE = (
    "Understand the user's request. Handle simple tasks directly; only enter the Better Plan "
    "workspace for complex tasks, large migrations, or long-term planning."
)


def run_hook(agent: str, payload: dict[str, object], event: str) -> subprocess.CompletedProcess[str]:
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
        cwd=str(REPO_ROOT),
        input=json.dumps(payload),
        check=False,
        text=True,
        capture_output=True,
    )


class HookToolTests(unittest.TestCase):
    def make_project(self, root: Path, with_plan: bool = True) -> Path:
        project = root / "project"
        project.mkdir()
        (project / ".git").mkdir()
        if with_plan:
            plan_root = project / "delivery-plans"
            plan_root.mkdir()
            write_workspace(plan_root, complete_plan())
        return project

    def test_no_workspace_is_a_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self.make_project(Path(tmpdir), with_plan=False)
            for agent in ("codex", "claude", "cursor", "antigravity", "kimi"):
                for event in ("session-start", "prompt-submit", "agent-complete"):
                    with self.subTest(agent=agent, event=event):
                        result = run_hook(agent, {"cwd": str(project)}, event)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertIn(result.stdout.strip(), {"", "{}"})

    def test_hook_entry_guidance_is_developer_gated(self) -> None:
        self.assertEqual(
            hook_context.INTENT_GUIDANCE,
            PROTECTED_ENTRY_GUIDANCE,
            "Hook entry guidance is protected; change it only on an explicit developer request",
        )
        self.assertEqual(hook_context.session_context(), PROTECTED_ENTRY_GUIDANCE)
        self.assertEqual(hook_context.prompt_context(), PROTECTED_ENTRY_GUIDANCE)

    def test_workspace_injects_protected_guidance_without_private_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self.make_project(Path(tmpdir))
            sentinel = "PRIVATE-PROMPT-SENTINEL"
            for agent in ("codex", "claude"):
                with self.subTest(agent=agent):
                    result = run_hook(
                        agent,
                        {"cwd": str(project), "prompt": sentinel},
                        "prompt-submit",
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
                    self.assertEqual(context, PROTECTED_ENTRY_GUIDANCE)
                    self.assertNotIn(sentinel, context)
                    self.assertNotIn(str(project), context)

    def test_cursor_and_kimi_use_native_response_shapes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self.make_project(Path(tmpdir))
            cursor = run_hook("cursor", {"cwd": str(project)}, "session-start")
            kimi = run_hook("kimi", {"cwd": str(project)}, "session-start")
            self.assertEqual(
                json.loads(cursor.stdout),
                {"additional_context": PROTECTED_ENTRY_GUIDANCE},
            )
            self.assertEqual(kimi.stdout.strip(), PROTECTED_ENTRY_GUIDANCE)

    def test_ambiguous_workspaces_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self.make_project(Path(tmpdir))
            second = project / "other-plans"
            second.mkdir()
            second_plan = complete_plan("other")
            second_plan["code"] = "PLAN-002"
            write_workspace(second, second_plan)
            result = run_hook("codex", {"cwd": str(project)}, "session-start")
            self.assertEqual(json.loads(result.stdout), {})

    def test_subagent_lifecycle_does_not_reinject_entry_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self.make_project(Path(tmpdir))
            result = run_hook(
                "codex",
                {"cwd": str(project), "hook_event_name": "SubagentStart"},
                "session-start",
            )
            self.assertEqual(json.loads(result.stdout), {})

    def test_unknown_event_is_rejected_without_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = self.make_project(Path(tmpdir))
            result = run_hook("codex", {"cwd": str(project)}, "unknown-stage")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")

    def test_protocol_event_inventory_is_exact(self) -> None:
        self.assertEqual(
            dict(protocols.host_events("codex")),
            {"SessionStart": "session-start", "UserPromptSubmit": "prompt-submit"},
        )
        self.assertEqual(
            dict(protocols.host_events("claude")),
            {"SessionStart": "session-start", "UserPromptSubmit": "prompt-submit", "SubagentStop": "agent-complete"},
        )
        self.assertEqual(
            dict(protocols.host_events("cursor")),
            {"sessionStart": "session-start", "beforeSubmitPrompt": "prompt-submit", "postToolUse": "agent-complete"},
        )
        self.assertEqual(
            dict(protocols.host_events("kimi")),
            {"SessionStart": "session-start", "UserPromptSubmit": "prompt-submit", "SubagentStop": "agent-complete"},
        )

    def test_codex_completion_hook_is_unsupported_and_fails_closed(self) -> None:
        payload = {
            "hook_event_name": "SubagentStop",
            "cwd": "/not/a/workspace",
            "agent_id": "child-thread-uuid",
            "agent_type": "worker-standard",
            "tool_name": "Agent",
            "final": True,
        }

        self.assertNotIn("agent-complete", protocols.host_events("codex").values())
        self.assertIsNone(protocols.event_matcher("codex", "agent-complete"))
        self.assertEqual(hook_runtime.safe_handle_event("codex", "agent-complete", payload), {})
        with self.assertRaises(protocols.HookProtocolError):
            protocols.context_response("codex", "agent-complete", "ignored")

    def test_each_host_owns_its_completion_protocol_in_one_adapter(self) -> None:
        self.assertEqual(
            set(hook_adapters.BY_NAME),
            {"codex", "claude", "cursor", "antigravity", "kimi"},
        )
        for name, adapter in hook_adapters.BY_NAME.items():
            with self.subTest(agent=name):
                self.assertEqual(adapter.context_encoder.__module__.rsplit(".", 1)[-1], name)

        common = {"agent_id": "child-1", "final": True}
        self.assertIsNone(
            protocols.completion_signal(
                "codex", {**common, "hook_event_name": "SubagentStop"}
            )
        )
        self.assertIsNone(
            protocols.completion_signal(
                "claude", {**common, "hook_event_name": "PostToolUse"}
            )
        )
        self.assertEqual(
            protocols.completion_signal(
                "claude", {**common, "hook_event_name": "SubagentStop"}
            ).agent_id,
            "child-1",
        )
        self.assertEqual(
            protocols.completion_signal("cursor", {**common, "tool_name": "Agent"}).agent_id,
            "child-1",
        )
        self.assertEqual(
            protocols.completion_signal("kimi", {**common, "agent_name": "worker"}).agent_id,
            "child-1",
        )

    def test_completion_context_names_task_target_and_single_sessions(self) -> None:
        value = hook_context.agent_completion_context("TASK-001", "worker_running", "accept_task")
        self.assertIn("target TASK-001", value)
        self.assertIn("focused acceptance", value)
        self.assertIn("dispatch-task once more", value)
        reviewer = hook_context.agent_completion_context("PLAN-001", "active", "close_reviewer_session")
        self.assertIn("sole write-capable Reviewer", reviewer)
        self.assertIn("never dispatch a second Reviewer", reviewer)


if __name__ == "__main__":
    unittest.main()
