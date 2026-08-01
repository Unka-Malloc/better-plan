"""Cross-surface acceptance for the current grouped role workflow."""

from __future__ import annotations

import unittest
from pathlib import Path

from scripts.better_plan.application.workflow import bounded_acceptance_payload


ROOT = Path(__file__).resolve().parents[1]


def design(owned: str, acceptance: str) -> dict[str, object]:
    return {
        "artifact": "docs/design.md",
        "owned_paths": [owned],
        "scaffold_paths": [owned],
        "acceptance_paths": [acceptance],
    }


def node(
    node_id: str,
    role: str,
    phase: str,
    *,
    difficulty: str = "standard",
    verification_profile: str = "code",
    owned: str = "src/current.py",
) -> dict[str, object]:
    return {
        "id": node_id,
        "status": "pending" if phase.startswith("awaiting_") else "in_progress",
        "role": role,
        "difficulty": difficulty,
        "verification_profile": verification_profile,
        "goal": "TRANSCRIPT_SENTINEL remains outside dispatch payloads.",
        "conversation_history": "TRANSCRIPT_SENTINEL",
        "design": design(owned, f"tests/test_{node_id}.py"),
        "regression": {
            "scope": "full" if role == "final_validation" else "focused",
            "commands": ["true"],
            "criteria": [0],
            "paths": [owned],
        },
        "acceptance": {"phase": phase, "attempt": 0, "outcome": "none"},
    }


class OrchestrationWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        cls.readme = (ROOT / "README.md").read_text(encoding="utf-8")
        cls.main = (ROOT / "references" / "orchestration-main.md").read_text(encoding="utf-8")
        cls.rules = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        cls.hook_context = (ROOT / "scripts" / "better_plan" / "hooks" / "context.py").read_text(encoding="utf-8")

    def test_current_role_names_are_complete(self) -> None:
        combined = "\n".join((self.skill, self.readme, self.main)).lower()
        for role in ("designer", "worker", "verifier", "reviewer"):
            self.assertIn(f"references/{role}.md", combined)

    def test_repository_self_maintenance_exemption_is_active(self) -> None:
        for payload in (self.rules, self.skill, self.readme, self.main):
            normalized = " ".join(payload.lower().split())
            self.assertIn("better plan source repository", normalized)
            self.assertRegex(normalized, r"(?:ordinary|native).+workflow")
        self.assertIn("do not create or maintain a repository-local better plan workspace", self.rules.lower())

    def test_first_use_mentions_native_templates_but_hooks_do_not(self) -> None:
        skill = self.skill.lower()
        normalized = " ".join(skill.split())
        self.assertIn("first better plan activation", skill)
        for host in ("codex", "claude code", "opencode", "cursor"):
            self.assertIn(host, skill)
        self.assertIn("first-use role confirmation gate", normalized)
        self.assertIn("inspect the current host's installed better plan role files and receipt read-only", normalized)
        self.assertIn("show the user one markdown table containing every role", normalized)
        self.assertIn("installed and recommended model provider when explicitly pinned", normalized)
        self.assertIn("never infer a provider or inspect credentials", normalized)
        self.assertIn("ask whether to keep the installed matrix or use the recommended matrix", normalized)
        self.assertIn("then stop and wait for an explicit choice", normalized)
        self.assertIn("does not authorize replacing existing files", normalized)
        self.assertIn(
            "before discovering or mutating plan state or dispatching any role agent",
            normalized,
        )
        hook = self.hook_context.lower()
        self.assertNotIn("template", hook)
        self.assertNotIn("manually imported", hook)

    def test_host_integration_is_strictly_additive(self) -> None:
        normalized = " ".join(self.skill.lower().split())
        self.assertIn("additive host integration — iron rule", normalized)
        self.assertIn("every pre-existing host or user file as immutable", normalized)
        self.assertIn("never converts a pre-existing file into a managed file", normalized)
        self.assertIn("fail closed, leave the original untouched", normalized)
        self.assertIn("general installation, update, provider, model, or routing requests never do", normalized)

    def test_every_role_change_repeats_the_full_comparison_and_waits(self) -> None:
        normalized = " ".join(self.skill.lower().split())
        self.assertIn("role-change reconfirmation gate", normalized)
        self.assertIn("whenever the user requests any change to a native role configuration", normalized)
        self.assertIn("repeat the complete installed-versus-recommended role table", normalized)
        self.assertIn("include every role, not only the requested roles", normalized)
        self.assertIn("client-specific overrides and the package recommendation as separate", normalized)
        self.assertIn("never describe a local override as a recommendation change", normalized)
        self.assertIn("ask the user to confirm them, then stop and wait", normalized)
        self.assertIn("a prior confirmation never satisfies a later role-change request", normalized)
        self.assertIn("this gate always repeats", normalized)
        self.assertIn("do not edit role files, provider configuration, receipts, templates", normalized)

    def test_worker_payload_uses_difficulty_agent_and_fresh_context_without_model(self) -> None:
        payload = bounded_acceptance_payload(
            node(
                "worker-node",
                "implementation",
                "awaiting_worker",
                difficulty="critical",
            )
        )
        self.assertEqual(payload["action"], "dispatch_worker")
        self.assertEqual(payload["agent_type"], "worker-critical")
        self.assertEqual(payload["fork_turns"], "none")
        self.assertEqual(payload["role_reference"], "references/worker.md")
        self.assertNotIn("knowledge_references", payload)
        self.assertNotIn("required_outputs", payload)
        self.assertNotIn("model", payload)
        self.assertNotIn("recommendation", payload)
        self.assertNotIn("TRANSCRIPT_SENTINEL", str(payload))

    def test_group_endcaps_receive_group_ids_and_union_of_needed_paths(self) -> None:
        group = [
            node("design", "group_design", "awaiting_designer", owned="docs/group.md"),
            node("one", "implementation", "awaiting_worker", owned="src/one.py"),
            node("two", "implementation", "awaiting_worker", owned="src/two.py"),
            node("final", "final_validation", "awaiting_reviewer", owned="tests/full.py"),
        ]
        for selected, action, agent_type, reference in (
            (group[0], "dispatch_designer", "designer", "references/designer.md"),
            (group[-1], "dispatch_reviewer", "reviewer", "references/reviewer.md"),
        ):
            payload = bounded_acceptance_payload(
                selected,
                action=action,
                group_nodes=group,
            )
            self.assertEqual(payload["agent_type"], agent_type)
            self.assertEqual(payload["fork_turns"], "none")
            self.assertEqual(payload["role_reference"], reference)
            self.assertEqual(payload["group_node_ids"], ["design", "one", "two", "final"])
            if action == "dispatch_designer":
                self.assertEqual(
                    payload["knowledge_references"],
                    ["references/design-patterns.md"],
                )
                self.assertEqual(
                    payload["required_outputs"],
                    ["design_pattern_assessment"],
                )
            else:
                self.assertNotIn("knowledge_references", payload)
                self.assertNotIn("required_outputs", payload)
            for path in ("docs/group.md", "src/one.py", "src/two.py", "tests/full.py"):
                self.assertIn(path, payload["repository_paths"])

    def test_visual_profiles_route_to_browser_and_vision_roles(self) -> None:
        verifier = bounded_acceptance_payload(
            node(
                "visual-node",
                "implementation",
                "awaiting_verifier",
                verification_profile="visual",
            )
        )
        self.assertEqual(verifier["agent_type"], "visual-verifier")
        self.assertEqual(verifier["role_reference"], "references/visual-verifier.md")
        self.assertEqual(verifier["required_capabilities"], ["code_reasoning", "vision", "browser"])
        self.assertIn("rendered browser output", verifier["required_evidence"])

        reviewer = bounded_acceptance_payload(
            node(
                "hybrid-final",
                "final_validation",
                "awaiting_reviewer",
                difficulty="critical",
                verification_profile="hybrid",
            ),
            action="dispatch_reviewer",
        )
        self.assertEqual(reviewer["agent_type"], "visual-reviewer")
        self.assertEqual(reviewer["role_reference"], "references/visual-reviewer.md")
        self.assertIn("vision", reviewer["required_capabilities"])

    def test_code_profile_keeps_rigorous_code_verifier(self) -> None:
        payload = bounded_acceptance_payload(
            node("code-node", "implementation", "awaiting_verifier")
        )
        self.assertEqual(payload["agent_type"], "verifier")
        self.assertEqual(payload["role_reference"], "references/verifier.md")
        self.assertEqual(payload["required_capabilities"], ["code_reasoning"])
        self.assertNotIn("required_evidence", payload)

    def test_docs_encode_one_designer_one_reviewer_and_repairing_verifier(self) -> None:
        normalized = " ".join((self.skill + self.main + self.readme).lower().split())
        self.assertIn("whole ordered group", normalized)
        self.assertIn("reviewer runs once", normalized)
        self.assertIn("directly repairs", normalized)
        self.assertIn('fork_turns: "none"', normalized)
        self.assertIn("spawn return is not completion", normalized)

    def test_docs_require_parallel_plans_and_concurrent_independent_workers(self) -> None:
        normalized = " ".join((self.skill + self.main + self.readme).lower().split())
        self.assertIn("widest safe parallel frontier", normalized)
        self.assertIn("artificial prerequisite", normalized)
        self.assertIn("spawn calls concurrently", normalized)
        self.assertIn("execute concurrently", normalized)
        self.assertIn("state mutations", normalized)
        self.assertIn("serialized", normalized)

    def test_docs_require_offline_pattern_assessment_without_pattern_forcing(self) -> None:
        designer = (ROOT / "references" / "designer.md").read_text(encoding="utf-8").lower()
        normalized = " ".join((self.skill + self.main + self.readme + designer).lower().split())
        self.assertIn("references/design-patterns.md", normalized)
        self.assertIn("design_pattern_assessment", normalized)
        self.assertIn("candidate: none", normalized)
        self.assertIn("simplest direct", normalized)
        self.assertIn("do not fetch", normalized)

    def test_docs_explain_two_tables_and_one_time_local_first_pinning(self) -> None:
        normalized = " ".join((self.skill + self.readme).lower().split())
        self.assertIn("coding_agent_catalog.json", normalized)
        self.assertIn("model_catalog.json", normalized)
        self.assertIn("local", normalized)
        self.assertIn("pins", normalized)
        self.assertIn("normal updates", normalized)
        self.assertIn("missing agent combinations are ignored", normalized)


if __name__ == "__main__":
    unittest.main()
