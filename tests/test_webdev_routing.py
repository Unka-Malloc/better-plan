"""Acceptance for Arena WebDev routing of visual delivery roles."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.better_plan.domain.models import ToolError
from scripts.better_plan.domain.webdev_routing import (
    load_webdev_catalog,
    select_webdev_model,
)


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "scripts" / "better_plan" / "domain" / "webdev_model_catalog.json"


class WebDevRoutingTests(unittest.TestCase):
    def test_packaged_snapshot_is_the_complete_arena_webdev_reference(self) -> None:
        payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        catalog = load_webdev_catalog()

        self.assertEqual(payload["source_url"], "https://arena.ai/leaderboard/code/webdev")
        self.assertEqual(payload["category"], "overall")
        self.assertEqual(payload["selection_policy"], "highest_webdev_score_for_visual_roles")
        self.assertEqual(payload["model_count"], 107)
        self.assertEqual(catalog.model_count, 107)
        self.assertEqual((catalog.models[0].rank, catalog.models[0].model), (1, "claude-opus-5-max"))

    def test_visual_selection_uses_highest_local_webdev_score(self) -> None:
        selected = select_webdev_model(
            available_model_ids={"gpt-5-6-sol-xhigh", "gpt-5-6-terra-xhigh"}
        )
        self.assertEqual((selected.model_id, selected.rank), ("gpt-5-6-sol-xhigh", 5))

        selected = select_webdev_model(
            available_model_ids={"claude-opus-5", "gpt-5-6-sol-xhigh"}
        )
        self.assertEqual((selected.model_id, selected.rank), ("claude-opus-5", 1))

    def test_unknown_local_selector_and_malformed_snapshot_fail_closed(self) -> None:
        with self.assertRaises(ToolError):
            select_webdev_model(available_model_ids={"not-on-arena"})

        payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        broken = copy.deepcopy(payload)
        broken["models"][0]["score"] = -1
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "catalog.json"
            path.write_text(json.dumps(broken), encoding="utf-8")
            with self.assertRaises(ToolError):
                load_webdev_catalog(path)


if __name__ == "__main__":
    unittest.main()
