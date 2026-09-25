"""Acceptance for the packaged benchmark reference tables."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.better_plan.domain import model_routing
from scripts.better_plan.domain.model_routing import load_model_catalog
from scripts.better_plan.domain.models import ToolError


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "scripts" / "better_plan" / "domain" / "model_catalog.json"


class CatalogReferenceTests(unittest.TestCase):
    def test_model_table_is_complete_primary_intelligence_reference(self) -> None:
        payload = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
        catalog = load_model_catalog()
        self.assertEqual(payload["schema_version"], 3)
        self.assertEqual(payload["status_filter"], "all")
        self.assertNotIn("selection_policy", payload)
        self.assertNotIn("difficulty_floors", payload)
        self.assertEqual(payload["model_count"], 673)
        self.assertEqual(catalog.model_count, 673)
        by_id = {model.model_id: model for model in catalog.models}
        self.assertEqual(by_id["gpt-6-astra"].intelligence_index, 53)
        self.assertEqual(by_id["gpt-6-astra-xhigh"].intelligence_index, 52)
        sol_high = by_id["gpt-6-sol-high"]
        self.assertEqual(sol_high.intelligence_index, 43)
        self.assertFalse(sol_high.intelligence_index_estimated)
        self.assertAlmostEqual(sol_high.cost_per_task_usd, 0.3746326907148203)
        self.assertEqual(by_id["gpt-6-luna"].intelligence_index, 37)

    def test_one_standard_index_is_the_only_evaluation_basis(self) -> None:
        """Models are judged by one standard index; no second table or basis ships."""

        self.assertEqual(
            sorted(path.name for path in MODEL_PATH.parent.glob("*catalog*.json")),
            ["model_catalog.json"],
        )
        for name in ("CodingAgentRecord", "CodingAgentCatalog", "load_coding_agent_catalog"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(model_routing, name), name)

    def test_no_role_or_model_selection_survives_in_the_routing_module(self) -> None:
        for name in (
            "select_worker_agent",
            "select_worker_agent_from_catalog",
            "select_intelligence_model",
            "select_intelligence_model_from_catalog",
            "_WORKER_SELECTION_POLICY",
            "_INTELLIGENCE_ROLES",
        ):
            with self.subTest(name=name):
                self.assertFalse(hasattr(model_routing, name), name)

    def test_packaged_codex_preset_rows_supply_receipted_provenance(self) -> None:
        """Every preset pin receipts one Intelligence Index row and the cost that row publishes."""

        models = {model.model_id: model for model in load_model_catalog().models}
        self.assertEqual(models["gpt-6-astra"].intelligence_index, 53)
        self.assertEqual(models["gpt-6-astra-low"].intelligence_index, 46)
        self.assertEqual(models["gpt-6-astra-xhigh"].intelligence_index, 52)
        self.assertEqual(models["gpt-6-luna"].intelligence_index, 37)
        self.assertAlmostEqual(models["gpt-6-luna"].cost_per_task_usd, 0.06809498628701058)

    def test_catalog_validation_fails_closed(self) -> None:
        payload = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
        broken_values = {}
        stale_schema = copy.deepcopy(payload)
        stale_schema["schema_version"] = 2
        broken_values["stale schema version"] = stale_schema
        restored_floor = copy.deepcopy(payload)
        restored_floor["difficulty_floors"] = {"standard": 42}
        broken_values["restored difficulty floor"] = restored_floor
        negative_index = copy.deepcopy(payload)
        negative_index["models"][0]["intelligence_index"] = -1
        broken_values["negative intelligence index"] = negative_index
        unknown_row_field = copy.deepcopy(payload)
        unknown_row_field["models"][0]["selection_policy"] = "cheapest"
        broken_values["unknown model field"] = unknown_row_field
        for label, broken in broken_values.items():
            with self.subTest(case=label), tempfile.TemporaryDirectory() as tmpdir:
                path = Path(tmpdir) / "catalog.json"
                path.write_text(json.dumps(broken), encoding="utf-8")
                with self.assertRaises(ToolError):
                    load_model_catalog(path)


if __name__ == "__main__":
    unittest.main()
