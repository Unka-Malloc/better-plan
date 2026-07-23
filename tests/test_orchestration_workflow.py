from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = REPO_ROOT / "SKILL.md"
ORCHESTRATION_MAIN_PATH = REPO_ROOT / "references" / "orchestration-main.md"
ACCEPTANCE_DESIGNER_PATH = REPO_ROOT / "references" / "acceptance-designer.md"
EXECUTOR_PATH = REPO_ROOT / "references" / "executor.md"
AUDITOR_PATH = REPO_ROOT / "references" / "auditor.md"
README_PATH = REPO_ROOT / "README.md"
HOOK_TOOL_PATH = REPO_ROOT / "scripts" / "hook_tool.py"
HOOK_CONFIG_PATH = REPO_ROOT / "scripts" / "better_plan" / "hooks" / "config.py"
HOOK_PROTOCOL_PATH = REPO_ROOT / "scripts" / "better_plan" / "hooks" / "protocols.py"
HOOK_RUNTIME_PATH = REPO_ROOT / "scripts" / "better_plan" / "hooks" / "runtime.py"
INSTALL_PATH = REPO_ROOT / "scripts" / "install.py"
INSTALL_TARGETS_PATH = REPO_ROOT / "scripts" / "better_plan" / "installation" / "targets.py"
INSTALL_MODELS_PATH = REPO_ROOT / "scripts" / "better_plan" / "installation" / "models.py"


def normalized_paragraphs(payload: str) -> list[str]:
    return [
        " ".join(paragraph.lower().split())
        for paragraph in re.split(r"\n\s*\n", payload)
        if paragraph.strip()
    ]


class OrchestrationWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = SKILL_PATH.read_text(encoding="utf-8")
        cls.readme = README_PATH.read_text(encoding="utf-8")
        cls.hook_tool = HOOK_TOOL_PATH.read_text(encoding="utf-8")
        cls.hook_config = HOOK_CONFIG_PATH.read_text(encoding="utf-8")
        cls.hook_protocol = HOOK_PROTOCOL_PATH.read_text(encoding="utf-8")
        cls.hook_runtime = HOOK_RUNTIME_PATH.read_text(encoding="utf-8")
        cls.installer = INSTALL_PATH.read_text(encoding="utf-8")
        cls.install_targets = INSTALL_TARGETS_PATH.read_text(encoding="utf-8")
        cls.install_models = INSTALL_MODELS_PATH.read_text(encoding="utf-8")
        cls.reference_main = ORCHESTRATION_MAIN_PATH.read_text(encoding="utf-8")
        cls.reference_acceptance_designer = ACCEPTANCE_DESIGNER_PATH.read_text(encoding="utf-8")
        cls.reference_executor = EXECUTOR_PATH.read_text(encoding="utf-8")
        cls.reference_auditor = AUDITOR_PATH.read_text(encoding="utf-8")

    def test_skill_points_to_orchestration_main_and_leaf_roles(self) -> None:
        self.assertTrue(self.skill.startswith("---\n"))
        self.assertIn("name: better-plan", self.skill)
        self.assertIn("references/orchestration-main.md", self.skill)
        self.assertIn("references/acceptance-designer.md", self.skill)
        self.assertIn("references/executor.md", self.skill)
        self.assertIn("references/auditor.md", self.skill)
        self.assertIn("role references", self.skill)

    def test_role_references_are_leaf_and_separated(self) -> None:
        for payload in (
            self.reference_acceptance_designer,
            self.reference_executor,
            self.reference_auditor,
        ):
            self.assertIn("leaf role", payload.lower())
        self.assertNotIn("leaf role", self.reference_main.lower())

    def test_auditor_reference_is_minimal(self) -> None:
        self.assertLess(len(self.reference_auditor.split()), 600)
        self.assertIn("fingerprint", self.reference_auditor.lower())
        self.assertIn("PASS", self.reference_auditor)
        self.assertIn("findings", self.reference_auditor.lower())
        self.assertNotIn("tutorial", self.reference_auditor.lower())
        self.assertNotIn("how to", self.reference_auditor.lower())

    def test_hook_scope_is_guidance_plus_agent_completion_only(self) -> None:
        self.assertIn("Session and prompt Hooks provide guidance only", self.readme)
        self.assertNotIn("launch", self.hook_tool.lower())
        self.assertNotIn("subprocess", self.hook_tool.lower())
        self.assertNotIn("subprocess", self.hook_runtime.lower())
        self.assertNotIn("openai", self.hook_tool.lower())
        self.assertNotIn("pretooluse", (self.hook_tool + self.hook_config).lower())
        self.assertIn("posttooluse", (self.hook_protocol + self.hook_config).lower())

    def test_cursor_native_lifecycle_host_is_documented_as_current(self) -> None:
        readme = self.readme.lower()
        self.assertIn("codex, claude code, cursor, and kimi code", readme)
        self.assertIn("supported events", readme)
        self.assertIn("NESTED_CONFIG_AGENTS", self.hook_protocol)
        self.assertIn("codex", self.hook_protocol)
        self.assertIn("claude", self.hook_protocol)
        self.assertIn("cursor", self.hook_protocol)
        self.assertIn('"sessionStart": "session-start"', self.hook_protocol)
        self.assertIn('"beforeSubmitPrompt": "prompt-submit"', self.hook_protocol)
        self.assertIn('"sessionStart"', self.hook_protocol)
        self.assertIn("POSTTOOLUSE", self.readme.upper())
        self.assertIn("NESTED_CONFIG_AGENTS", self.hook_protocol)
        self.assertIn("nested_handlers", self.hook_config)
        self.assertIn("flat_handlers", self.hook_config)
        self.assertIn("HOOK_TIMEOUT_SECONDS", self.hook_config)
        self.assertIn("session-start", self.hook_runtime)
        self.assertIn("prompt-submit", self.hook_runtime)
        self.assertIn('EVENTS = ("session-start", "prompt-submit", "agent-complete")', self.hook_runtime)
        self.assertIn(
            'AGENTS=("codex","claude","cursor","antigravity","kimi")',
            self.hook_protocol.replace(" ", ""),
        )

    def test_session_and_prompt_are_detector_gated_guidance(self) -> None:
        detector_terms = self.hook_runtime + self.readme
        self.assertIn("detected_manifest(payload)", self.hook_runtime)
        self.assertIn("detect_event_workspace", self.hook_runtime)
        self.assertIn("session-start", detector_terms)
        self.assertIn("prompt-submit", detector_terms)
        self.assertIn("read-only", self.readme.lower())
        self.assertIn("guidance only", self.readme.lower())
        self.assertIn("detect", self.readme.lower())

    def test_execution_selection_refusal_returns_to_native_main_planning(self) -> None:
        self.assertIn("leaf dispatch", self.reference_main)
        self.assertIn("cannot terminate the user's task", self.reference_main)
        self.assertIn("repair the relevant Plan or planning tool", self.reference_main)
        self.assertIn("never auto-dispatch or loop", self.skill)

    def test_one_user_visible_capability_has_one_lifecycle_and_terminal_completion(self) -> None:
        for payload in (self.skill, self.reference_main):
            lowered = payload.lower()
            self.assertIn("one user-visible capability", lowered)
            self.assertIn("one lifecycle", lowered)
            self.assertRegex(
                lowered,
                re.compile(
                    r"complet(?:e|ion)[\s\S]{0,240}(?:must not|does not|never)[\s\S]{0,120}"
                    r"(?:next|another|different) node",
                ),
            )

    def test_end_to_end_closure_policy_is_shared_by_every_active_role(self) -> None:
        skill = " ".join(self.skill.lower().split())
        self.assertIn("complete one end-to-end user-visible capability in one pass", skill)
        self.assertIn("freeze acceptance exactly once", skill)
        self.assertIn("exactly one independent review", skill)
        self.assertIn("resolve ordinary compiler", skill)
        self.assertIn("real design error or product-semantics error", skill)
        self.assertIn("run the full regression exactly once", skill)
        self.assertIn("after every implementation node", skill)

        self.assertIn("freeze acceptance once", self.reference_main.lower())
        self.assertIn("ordinary compiler", self.reference_executor.lower())
        self.assertIn("same dispatch", self.reference_executor.lower())
        self.assertIn("only independent review", self.reference_auditor.lower())
        self.assertIn("single acceptance freeze", self.reference_acceptance_designer.lower())

    def test_acceptance_dimensions_are_risk_selected_candidates_not_a_checklist(self) -> None:
        dimensions = ("success", "boundary", "negative", "replay", "privacy", "fingerprint")
        designer_clause = next(
            (
                paragraph
                for paragraph in normalized_paragraphs(self.reference_acceptance_designer)
                if all(dimension in paragraph for dimension in dimensions)
                and re.search(r"(?:candidate|候选)", paragraph)
            ),
            "",
        )
        self.assertTrue(designer_clause, "the six dimensions must share one explicit candidate clause")
        self.assertRegex(designer_clause, r"(?:select|choose|选择)")
        self.assertRegex(designer_clause, r"(?:only|仅|只)")
        self.assertRegex(designer_clause, r"(?:applicable|relevant|适用|相关)")
        self.assertRegex(designer_clause, r"(?:risk|风险)")

    def test_unchanged_waiting_is_quiet_heuristic_guidance_not_a_timer_gate(self) -> None:
        for payload in (self.skill, self.reference_main):
            lowered = payload.lower()
            paragraphs = normalized_paragraphs(payload)
            quiet_clause = next(
                (
                    paragraph
                    for paragraph in paragraphs
                    if "unchanged" in paragraph
                    and "repeat" in paragraph
                    and re.search(r"(?:status|progress|update|report)", paragraph)
                ),
                "",
            )
            self.assertTrue(quiet_clause, "unchanged delegated state needs one quiet-report clause")
            self.assertRegex(quiet_clause, r"(?:do not|avoid)")

            lifecycle_clause = next(
                (
                    paragraph
                    for paragraph in paragraphs
                    if "heuristic" in paragraph
                    and "poll" in paragraph
                    and "lifecycle" in paragraph
                    and "gate" in paragraph
                ),
                "",
            )
            self.assertTrue(lifecycle_clause, "quiet waiting needs one explicit non-intervention clause")
            self.assertRegex(lifecycle_clause, r"(?:does not|never).{0,120}(?:time|timer).{0,80}poll")
            self.assertRegex(
                lifecycle_clause,
                r"(?:does not|never).{0,240}(?:interrupt|cancel|replace|interfere)"
                r".{0,160}(?:child|agent).{0,80}lifecycle",
            )
            self.assertRegex(
                lifecycle_clause,
                r"(?:is not|never).{0,120}execution.{0,80}completion.{0,80}failure.{0,40}gate",
            )
            self.assertNotRegex(lowered, r"\b\d+\s*(?:seconds?|minutes?|hours?)\b")

    def test_lifecycle_guidance_contains_no_concrete_project_or_agent_routing_policy(self) -> None:
        payload = "\n".join(
            (
                self.skill,
                self.reference_main,
                self.reference_acceptance_designer,
            )
        ).lower()
        for concrete_name in (
            "licolite",
            "kimi",
            "claude",
            "cursor",
            "codex",
            "copilot",
            "gemini",
            "opencode",
            "macos",
            "windows",
            "linux",
        ):
            self.assertNotIn(concrete_name, payload)

    def test_cursor_protocol_encoding_is_isolated_from_codex_claude_nested_encoding(self) -> None:
        self.assertIn("nested codex and claude", self.readme.lower())
        self.assertIn("cursor receives flat version 1 hooks", self.readme.lower())
        self.assertIn("NESTED_CONFIG_AGENTS", self.hook_protocol)
        self.assertIn('"codex": {', self.hook_protocol.lower())
        self.assertIn('"cursor": {', self.hook_protocol.lower())
        self.assertNotIn("nested cursor", self.hook_protocol.lower())
        nested_section = self.hook_config.split("def nested_handlers", 1)[1].split(
            "def flat_handlers", 1
        )[0]
        self.assertIn('agent not in {"codex", "claude"}', nested_section)
        self.assertNotIn("_cursor_host_events", nested_section)

    def test_workflow_progression_is_explicit_and_event_driven(self) -> None:
        self.assertIn("the completion Hook submits the correlated write-role exit", self.readme)
        self.assertIn("executor-exited", self.readme)
        self.assertIn("dispatch_executor", self.readme)
        self.assertIn("dispatch_auditor", self.readme)
        self.assertNotIn("subprocess", self.hook_tool.lower())
        self.assertNotIn("application.workflow", self.hook_runtime)
        self.assertNotIn("domain.transitions", self.hook_runtime)
        self.assertNotIn("manifest_tool", self.hook_runtime)

    def test_orchestration_readme_contract_surface(self) -> None:
        self.assertIn("native parent", self.readme)
        self.assertIn("dispatch_executor", self.readme)
        self.assertIn("dispatch_auditor", self.readme)
        self.assertIn("fresh read-only auditor", self.readme)
        self.assertIn("references/orchestration-main.md", self.readme)


if __name__ == "__main__":
    unittest.main()
