"""Acceptance for the packaged benchmark reference tables."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.better_plan.domain import model_routing
from scripts.better_plan.domain.model_routing import (
    load_coding_agent_catalog,
    load_model_catalog,
)
from scripts.better_plan.domain.models import ToolError


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "scripts" / "better_plan" / "domain" / "model_catalog.json"
AGENT_PATH = ROOT / "scripts" / "better_plan" / "domain" / "coding_agent_catalog.json"


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

    def test_coding_agent_table_is_a_reference_table_without_a_floor(self) -> None:
        payload = json.loads(AGENT_PATH.read_text(encoding="utf-8"))
        catalog = load_coding_agent_catalog()
        self.assertEqual(payload["schema_version"], 4)
        self.assertNotIn("worker_floor", payload)
        self.assertEqual(catalog.schema_version, 4)
        self.assertEqual(catalog.variant_count, 19)
        self.assertEqual(len(catalog.variants), 19)

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
        models = {model.model_id: model for model in load_model_catalog().models}
        variants = {variant.variant_id: variant for variant in load_coding_agent_catalog().variants}
        self.assertEqual(models["gpt-6-astra"].intelligence_index, 53)
        self.assertEqual(models["gpt-6-astra-low"].intelligence_index, 46)
        self.assertEqual(models["gpt-6-astra-xhigh"].intelligence_index, 52)
        self.assertEqual(models["gpt-6-luna"].intelligence_index, 37)
        worker = variants["codex-gpt-6-luna-max"]
        self.assertEqual(
            (worker.harness, worker.model, worker.reasoning_effort, worker.index_score),
            ("codex", "gpt-6-luna", "max", 41),
        )
        self.assertAlmostEqual(worker.cost_per_task_usd, 0.17591172304455457)

    def test_catalog_validation_fails_closed(self) -> None:
        payload = json.loads(AGENT_PATH.read_text(encoding="utf-8"))
        broken_values = {}
        stale_schema = copy.deepcopy(payload)
        stale_schema["schema_version"] = 3
        broken_values["stale schema version"] = stale_schema
        restored_floor = copy.deepcopy(payload)
        restored_floor["worker_floor"] = 42
        broken_values["restored worker floor"] = restored_floor
        negative_cost = copy.deepcopy(payload)
        negative_cost["variants"][0]["cost_per_task_usd"] = -1
        broken_values["negative measured cost"] = negative_cost
        unknown_row_field = copy.deepcopy(payload)
        unknown_row_field["variants"][0]["selection_policy"] = "cheapest"
        broken_values["unknown variant field"] = unknown_row_field
        for label, broken in broken_values.items():
            with self.subTest(case=label), tempfile.TemporaryDirectory() as tmpdir:
                path = Path(tmpdir) / "catalog.json"
                path.write_text(json.dumps(broken), encoding="utf-8")
                with self.assertRaises(ToolError):
                    load_coding_agent_catalog(path)

        model_payload = json.loads(MODEL_PATH.read_text(encoding="utf-8"))
        model_payload["models"][0]["intelligence_index"] = -1
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "catalog.json"
            path.write_text(json.dumps(model_payload), encoding="utf-8")
            with self.assertRaises(ToolError):
                load_model_catalog(path)


if __name__ == "__main__":
    unittest.main()
