"""Acceptance for the independent model and Coding Agent routing tables."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.better_plan.domain.model_routing import (
    load_coding_agent_catalog,
    load_model_catalog,
    select_intelligence_model,
    select_worker_agent,
)
from scripts.better_plan.domain.models import ToolError


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "scripts" / "better_plan" / "domain" / "model_catalog.json"
AGENT_PATH = ROOT / "scripts" / "better_plan" / "domain" / "coding_agent_catalog.json"


class RoleRoutingTests(unittest.TestCase):
    def test_model_table_is_complete_current_primary_intelligence_reference(self) -> None:
        payload = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
        catalog = load_model_catalog()
        self.assertEqual(payload["schema_version"], 3)
        self.assertEqual(payload["selection_policy"], "intelligence_rank_for_non_worker_roles")
        self.assertNotIn("difficulty_floors", payload)
        self.assertEqual(payload["model_count"], 260)
        self.assertEqual(catalog.model_count, 260)
        by_id = {model.model_id: model for model in catalog.models}
        self.assertEqual(by_id["gemini-3-5-flash"].intelligence_index, 50)
        self.assertEqual(by_id["gemini-3-6-flash"].intelligence_index, 50)

    def test_coding_agent_table_is_the_worker_reference_with_task_floors(self) -> None:
        payload = json.loads(AGENT_PATH.read_text(encoding="utf-8"))
        catalog = load_coding_agent_catalog()
        self.assertEqual(payload["schema_version"], 2)
        self.assertEqual(payload["usage"], "worker_routing_reference")
        self.assertEqual(
            dict(catalog.difficulty_floors),
            {"routine": 25, "standard": 42, "complex": 55, "critical": 64},
        )
        self.assertEqual(catalog.variant_count, 52)

    def test_codex_worker_uses_cheapest_measured_agent_above_each_floor(self) -> None:
        expected = {
            "routine": ("codex-gpt-5-6-luna-low", 25, 0.04),
            "standard": ("codex-gpt-5-6-luna-medium", 42, 0.09),
            "complex": ("codex-gpt-5-6-luna-xhigh", 55, 0.25),
            "critical": ("codex-gpt-5-6-sol-high", 64, 4.14),
        }
        for difficulty, values in expected.items():
            with self.subTest(difficulty=difficulty):
                selected = select_worker_agent(difficulty, harness="codex")
                self.assertEqual(
                    (selected.variant_id, selected.index_score, selected.cost_per_task_usd),
                    values,
                )

    def test_worker_ignores_unlisted_or_unavailable_agent_combinations(self) -> None:
        selected = select_worker_agent(
            "standard",
            harness="claude-code",
            available_variant_ids={
                "not-in-the-table",
                "claude-code-opus-4-8-medium",
                "claude-code-opus-4-6-medium",
            },
        )
        self.assertEqual(selected.variant_id, "claude-code-opus-4-6-medium")
        with self.assertRaises(ToolError):
            select_worker_agent(
                "critical",
                harness="cursor-cli",
                available_variant_ids={"cursor-cli-composer-2-5"},
            )

    def test_non_worker_roles_rank_intelligence_without_cost(self) -> None:
        designer = select_intelligence_model("designer")
        reviewer = select_intelligence_model("reviewer")
        self.assertEqual((designer.model_id, designer.intelligence_index), ("claude-opus-5", 61))
        self.assertEqual((reviewer.model_id, reviewer.intelligence_index), ("claude-opus-5", 61))

    def test_removed_verifier_is_not_an_intelligence_role(self) -> None:
        with self.assertRaises(ToolError):
            select_intelligence_model("verifier")

    def test_catalog_validation_fails_closed(self) -> None:
        payload = json.loads(AGENT_PATH.read_text(encoding="utf-8"))
        broken = copy.deepcopy(payload)
        broken["difficulty_floors"]["critical"] = 42
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "catalog.json"
            path.write_text(json.dumps(broken), encoding="utf-8")
            with self.assertRaises(ToolError):
                load_coding_agent_catalog(path)


if __name__ == "__main__":
    unittest.main()
