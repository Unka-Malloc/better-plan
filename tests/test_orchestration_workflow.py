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
        "goal": f"Complete the bounded {node_id} role contract.",
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
        cls.host = (ROOT / "references" / "host-configuration.md").read_text(encoding="utf-8")
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

    def test_first_use_reports_roles_and_keeps_valid_local_matrix_authoritative(self) -> None:
        host = self.host.lower()
        normalized = " ".join(host.split())
        self.assertIn("first better plan activation", host)
        for host in ("codex", "claude code", "opencode", "cursor"):
            self.assertIn(host, self.host.lower())
        self.assertIn("first-use role visibility gate", normalized)
        self.assertIn("inspect the current host's installed better plan role files and receipt read-only", normalized)
        self.assertIn("compare every installed role with the package recommendation", normalized)
        self.assertIn("one localized markdown table", normalized)
        self.assertIn("render selectors as `model / effort`", normalized)
        self.assertIn("| 角色 | 用途 | 已安装选择器 | 推荐选择器 | 差异 |", self.host)
        self.assertIn("otherwise omit provider cells", normalized)
        self.assertNotIn("已安装 provider", host)
        self.assertNotIn("推荐 provider", host)
        self.assertIn("never infer a provider or inspect credentials", normalized)
        self.assertIn("a complete valid installed matrix is authoritative", normalized)
        self.assertIn("do not ask the user to choose between installed and recommended matrices", normalized)
        self.assertIn("or pause for that choice", normalized)
        self.assertIn("never overrides or mutates an installed role", normalized)
        self.assertIn("do not solicit configuration changes unless requested", normalized)
        self.assertIn(
            "before discovering or mutating plan state or dispatching any role agent",
            normalized,
        )
        hook = self.hook_context.lower()
        self.assertNotIn("template", hook)
        self.assertNotIn("manually imported", hook)

        main = " ".join(self.main.lower().split())
        readme = " ".join(self.readme.lower().split())
        for payload in (main, readme):
            self.assertIn("complete valid installed", payload)
            self.assertIn("never ask the user to choose", payload)
            self.assertIn("per-role fallback", payload)

    def test_host_integration_is_strictly_additive(self) -> None:
        normalized = " ".join(self.host.lower().split())
        self.assertIn("additive host integration — iron rule", normalized)
        self.assertIn("every pre-existing host or user file as immutable", normalized)
        self.assertIn("never converts a pre-existing file into a managed file", normalized)
        self.assertIn("fail closed and leave the original untouched", normalized)
        self.assertIn("general installation, update, provider, model, routing", normalized)

    def test_every_role_change_repeats_the_full_comparison_and_waits(self) -> None:
        normalized = " ".join(self.host.lower().split())
        self.assertIn("role-change reconfirmation gate", normalized)
        self.assertIn("whenever the user requests any native role configuration change", normalized)
        self.assertIn("repeat the complete installed-versus-recommended table", normalized)
        self.assertIn("include every role", normalized)
        self.assertIn("same five-column selector format", normalized)
        self.assertIn("client-specific overrides separately from package recommendations", normalized)
        self.assertIn("never describe a local override as a recommendation change", normalized)
        self.assertIn("ask the user to confirm them, then stop and wait", normalized)
        self.assertIn("a prior confirmation never satisfies a later role-change request", normalized)
        self.assertIn("do not edit role files, provider configuration, receipts, templates", normalized)

    def test_skill_uses_relevance_based_progressive_disclosure(self) -> None:
        normalized = " ".join(self.skill.lower().split())
        self.assertIn("progressive-disclosure router", normalized)
        self.assertIn("information-relevance rule", normalized)
        self.assertIn("never a token, word, character, or line quota", normalized)
        self.assertIn("tell each role every material fact", normalized)
        self.assertIn("omit only information that is irrelevant or redundant", normalized)
        self.assertIn("never hide useful context merely to shorten a prompt", normalized)
        self.assertIn("may inspect any accessible skill, reference, repository file", normalized)
        self.assertIn("never block useful self-directed reading", normalized)
        self.assertNotIn("additive host integration — iron rule", normalized)
        self.assertNotIn("role-change reconfirmation gate", normalized)
        for reference in (
            "references/host-configuration.md",
            "references/state-files.md",
            "references/orchestration-main.md",
            "references/designer.md",
            "references/worker.md",
            "references/verifier.md",
            "references/visual-verifier.md",
            "references/reviewer.md",
            "references/visual-reviewer.md",
            "references/design-patterns.md",
        ):
            self.assertIn(reference, self.skill)

    def test_worker_payload_uses_difficulty_agent_and_continuation_key_without_model(self) -> None:
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
        self.assertRegex(payload["worker_continuation_key"], r"^[0-9a-f]{64}$")
        self.assertEqual(
            payload["continuation_policy"],
            "prefer_idle_compatible_worker_after_acceptance",
        )
        self.assertEqual(payload["work_items"][0]["goal"], "Complete the bounded worker-node role contract.")
        self.assertNotIn("TRANSCRIPT_SENTINEL", str(payload))

    def test_worker_continuation_key_is_stable_only_for_compatible_lanes(self) -> None:
        scope = {"target_key": "repository/group"}
        first = bounded_acceptance_payload(
            node("one", "implementation", "awaiting_worker", difficulty="standard"),
            capability_context=scope,
        )
        second = bounded_acceptance_payload(
            node("two", "implementation", "awaiting_worker", difficulty="standard"),
            capability_context=scope,
        )
        different_difficulty = bounded_acceptance_payload(
            node("three", "implementation", "awaiting_worker", difficulty="complex"),
            capability_context=scope,
        )
        different_capability = bounded_acceptance_payload(
            node("four", "implementation", "awaiting_worker", difficulty="standard"),
            capability_context={"target_key": "repository/other"},
        )
        self.assertEqual(first["worker_continuation_key"], second["worker_continuation_key"])
        self.assertNotEqual(first["worker_continuation_key"], different_difficulty["worker_continuation_key"])
        self.assertNotEqual(first["worker_continuation_key"], different_capability["worker_continuation_key"])

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
            self.assertEqual(
                [item["id"] for item in payload["work_items"]],
                ["design", "one", "two", "final"],
            )
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
                difficulty="critical",
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
            node("code-node", "implementation", "awaiting_verifier", difficulty="critical")
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
        self.assertIn("routine, standard, or complex node", normalized)
        self.assertIn("never dispatches a verifier", normalized)
        self.assertIn("a critical node dispatches the code or visual verifier", normalized)
        self.assertIn("must not override this mechanical gate", normalized)
        self.assertIn('fork_turns: "none"', normalized)
        self.assertIn("spawn or continuation return is not completion", normalized)
        self.assertIn("worker_continuation_key", normalized)
        self.assertIn("followup_task", normalized)
        self.assertIn("a leaf may inspect `skill.md`", normalized)
        self.assertIn("never prevent such self-directed reading", normalized)

    def test_docs_require_parallel_plans_and_concurrent_independent_workers(self) -> None:
        normalized = " ".join((self.skill + self.main + self.readme).lower().split())
        self.assertIn("widest safe parallel frontier", normalized)
        self.assertIn("artificial prerequisite", normalized)
        self.assertIn("spawn calls concurrently", normalized)
        self.assertIn("execute concurrently", normalized)
        self.assertIn("serialize the short better plan `dispatch` mutations", normalized)
        self.assertIn("serialize the short `bind-agent` mutations", normalized)

    def test_docs_bound_delegation_retries_and_fallback_to_native_main(self) -> None:
        normalized = " ".join((self.skill + self.main + self.readme).lower().split())
        self.assertIn("delegation and recovery kernel", normalized)
        self.assertIn("a short wait", normalized)
        self.assertIn("missing artifacts", normalized)
        self.assertIn("context compaction", normalized)
        self.assertIn("never interrupt", normalized)
        self.assertIn("main-initiated `interrupted` or `cancelled`", normalized)
        self.assertIn("terminal-failed-agent-id", normalized)
        self.assertIn("concrete ongoing progress means the role is still working", normalized)
        self.assertIn("at most three delegation attempts", normalized)
        self.assertIn("main-complete", normalized)
        self.assertIn("never bind a fabricated main-thread agent id", normalized)
        self.assertIn("delegation failure alone never blocks an authorized task", normalized)
        self.assertIn("configured-model unavailability", normalized)
        self.assertIn("reports no task body indicates payload-delivery failure", normalized)
        self.assertIn("not quota exhaustion", normalized)
        self.assertIn("exercise native-main judgment", normalized)
        self.assertIn("compact task brief", normalized)
        self.assertIn("do not merely forward json", normalized)
        self.assertIn("--spawn-refused", normalized)
        self.assertIn("rejects an unqualified failure record", normalized)
        for role in ("designer", "worker", "verifier", "reviewer"):
            self.assertIn(role, normalized)

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
        self.assertIn("pinned", normalized)
        self.assertIn("normal updates", normalized)
        self.assertIn("missing agent combinations are ignored", normalized)


if __name__ == "__main__":
    unittest.main()
