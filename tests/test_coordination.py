"""Focused contracts for multi-plan coordination policy."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.better_plan.domain.coordination import evaluate, policy_binding, validate_config
from scripts.better_plan.domain.models import ToolError


class CoordinationTests(unittest.TestCase):
    def config(self):
        return {
            "schema": "better-plan.coordination/v1",
            "namespace": "licoland",
            "portfolio": "plans/portfolio.json",
            "max_parallel": 3,
            "host": {
                "kind": "command",
                "command": ["host-adapter"],
                "profiles": {"worker-standard": "default-worker"},
                "lanes": {
                    "arc-main": "worker-standard",
                    "up-main": "worker-standard",
                },
            },
            "lanes": [
                {"id": "arc-main", "kind": "mainline", "repository": "LicoArc", "source": "arc"},
                {"id": "up-main", "kind": "mainline", "repository": "LicoUp", "source": "up"},
                {"id": "up-arc", "kind": "collaboration", "repository": "LicoUp", "source": "up-arc"},
                {"id": "tower-arc", "kind": "collaboration", "repository": "BadTower", "source": "tower-arc"},
            ],
            "requires": [
                {"consumer": "up-arc/consume", "provider": "arc/publish", "binding": "arc-r1"},
                {"consumer": "tower-arc/consume", "provider": "arc/publish", "binding": "arc-r1"},
            ],
        }

    def unit(self, key, source, state="pending", binding=None, parents=None, writes=None, resources=None):
        return {
            "key": key,
            "source": source,
            "binding": binding or key + "-r1",
            "state": state,
            "authorized": True,
            "parents": parents or [],
            "writes": writes or [source + "/" + key.rsplit("/", 1)[-1]],
            "resources": resources or [],
            "brief": {"title": "Safe unit"},
        }

    def test_mainline_and_collaboration_branches_progress_independently(self):
        config = self.config()
        units = {
            "arc/publish": self.unit("arc/publish", "arc", state="completed", binding="arc-r1"),
            "up/local": self.unit("up/local", "up"),
            "up-arc/consume": self.unit("up-arc/consume", "up-arc"),
            "tower-arc/consume": self.unit("tower-arc/consume", "tower-arc"),
        }
        before = deepcopy((config, units))
        grants = {
            key: unit["binding"]
            for key, unit in units.items()
            if not key.endswith("/<unavailable>")
        }
        with TemporaryDirectory() as tmp:
            result = evaluate(config, units, Path(tmp), grants, set())
        self.assertEqual(result["ready"], ["tower-arc/consume", "up/local", "up-arc/consume"])
        self.assertEqual(set(result["batch"]), {"up/local", "up-arc/consume", "tower-arc/consume"})
        self.assertEqual((config, units), before)
        self.assertEqual(result["policy_binding"], policy_binding(config))

    def test_unknown_or_pin_mismatch_waits_without_blocking_unrelated_work(self):
        config = self.config()
        units = {
            "arc/publish": self.unit("arc/publish", "arc", state="unknown", binding="arc-r2"),
            "up/local": self.unit("up/local", "up"),
            "up-arc/consume": self.unit("up-arc/consume", "up-arc"),
            "tower-arc/consume": self.unit("tower-arc/consume", "tower-arc"),
        }
        grants = {
            key: unit["binding"]
            for key, unit in units.items()
            if not key.endswith("/<unavailable>")
        }
        with TemporaryDirectory() as tmp:
            result = evaluate(config, units, Path(tmp), grants, set())
        states = {item["key"]: item["readiness"] for item in result["units"]}
        self.assertEqual(states["up-arc/consume"], "waiting_external")
        self.assertEqual(states["tower-arc/consume"], "waiting_external")
        self.assertEqual(result["batch"], ["up/local"])

    def test_materialized_pin_and_scope_collision_control_dispatch(self):
        config = self.config()
        payload = b"accepted artifact"
        digest = sha256(payload).hexdigest()
        config["requires"][0]["materialized"] = [{"path": "LicoUp/vendor/arc.bin", "sha256": digest}]
        units = {
            "arc/publish": self.unit("arc/publish", "arc", state="completed", binding="arc-r1"),
            "up/local": self.unit("up/local", "up", state="running", writes=["LicoUp/src/**"]),
            "up-arc/consume": self.unit("up-arc/consume", "up-arc", writes=["LicoUp/src/arc.py"]),
            "tower-arc/consume": self.unit("tower-arc/consume", "tower-arc"),
        }
        grants = {key: unit["binding"] for key, unit in units.items()}
        with TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "LicoUp/vendor/arc.bin"
            artifact.parent.mkdir(parents=True)
            artifact.write_bytes(payload)
            result = evaluate(config, units, Path(tmp), grants, set())
        states = {item["key"]: item["readiness"] for item in result["units"]}
        self.assertEqual(states["up-arc/consume"], "waiting_resource")
        self.assertEqual(result["batch"], ["tower-arc/consume"])

    def test_combined_cycle_and_authorization_mismatch_fail_closed(self):
        config = self.config()
        units = {
            "arc/publish": self.unit("arc/publish", "arc", state="completed", binding="arc-r1"),
            "up/local": self.unit("up/local", "up"),
            "up-arc/consume": self.unit("up-arc/consume", "up-arc"),
            "tower-arc/consume": self.unit("tower-arc/consume", "tower-arc"),
        }
        grants = {key: unit["binding"] for key, unit in units.items()}
        grants["up/local"] = "stale-binding"
        with TemporaryDirectory() as tmp:
            result = evaluate(config, units, Path(tmp), grants, set())
        states = {item["key"]: item["readiness"] for item in result["units"]}
        self.assertEqual(states["up/local"], "unauthorized")
        cycle = deepcopy(config)
        cycle["requires"].append(
            {"consumer": "arc/publish", "provider": "up-arc/consume", "binding": "up-arc/consume-r1"}
        )
        with TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ToolError, "cycle"):
                evaluate(cycle, units, Path(tmp), grants, set())

    def test_config_rejects_duplicate_source_and_unsafe_paths(self):
        config = self.config()
        self.assertIs(validate_config(config), config)
        config["lanes"][1]["source"] = "arc"
        with self.assertRaises(ToolError):
            validate_config(config)
        config = self.config()
        config["portfolio"] = "../private.json"
        with self.assertRaises(ToolError) as error:
            validate_config(config)
        self.assertNotIn("private.json", str(error.exception))
        config = self.config()
        config["host"]["lanes"]["arc-main"] = "worker-complex"
        with self.assertRaisesRegex(ToolError, "no configured profile"):
            validate_config(config)
        config = self.config()
        config["host"]["command"] = "adapter --start"
        with self.assertRaisesRegex(ToolError, "argument array"):
            validate_config(config)

    def test_policy_without_host_is_observable_but_cannot_dispatch(self):
        config = self.config()
        config.pop("host")
        units = {"up/local": self.unit("up/local", "up")}
        # Keep only the source represented by this focused snapshot.
        config["lanes"] = [lane for lane in config["lanes"] if lane["source"] == "up"]
        config["requires"] = []
        with TemporaryDirectory() as tmp:
            result = evaluate(
                config, units, Path(tmp), {"up/local": units["up/local"]["binding"]}, set()
            )
        self.assertFalse(result["dispatch_enabled"])
        self.assertEqual(result["ready"], ["up/local"])
        self.assertEqual(result["batch"], [])
        self.assertEqual(result["waiting"], ["up/local"])

    def test_unavailable_provider_is_external_wait_and_active_invalidation_needs_review(self):
        config = self.config()
        config["max_parallel"] = 2
        units = {
            "arc/<unavailable>": self.unit(
                "arc/<unavailable>", "arc", state="unknown", writes=[]
            ),
            "up/local": self.unit("up/local", "up"),
            "up-arc/consume": self.unit("up-arc/consume", "up-arc"),
            "tower-arc/consume": self.unit("tower-arc/consume", "tower-arc"),
        }
        grants = {
            key: unit["binding"]
            for key, unit in units.items()
            if not key.endswith("/<unavailable>")
        }
        with TemporaryDirectory() as tmp:
            result = evaluate(
                config,
                units,
                Path(tmp),
                grants,
                {"up-arc/consume"},
                {"arc": "source unavailable"},
            )
        states = {item["key"]: item["readiness"] for item in result["units"]}
        self.assertEqual(states["up-arc/consume"], "needs_review")
        self.assertEqual(states["tower-arc/consume"], "waiting_external")
        self.assertEqual(states["up/local"], "ready")

        typo_units = deepcopy(units)
        typo_units.pop("arc/<unavailable>")
        with TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ToolError, "unknown unit"):
                evaluate(config, typo_units, Path(tmp), grants, set(), {})


if __name__ == "__main__":
    unittest.main()
