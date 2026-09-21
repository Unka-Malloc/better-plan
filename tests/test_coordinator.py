from __future__ import annotations

from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import tempfile
import unittest

from scripts.better_plan.application.coordinator import Coordinator


def config(*, maximum: int = 2, profile: str = "dev") -> dict:
    return {
        "schema": "better-plan.coordination/v1",
        "namespace": "portfolio",
        "portfolio": "portfolio.json",
        "max_parallel": maximum,
        "lanes": [
            {
                "id": "repo-main",
                "kind": "mainline",
                "repository": "repo",
                "source": "main",
            },
            {
                "id": "repo-side",
                "kind": "collaboration",
                "repository": "repo",
                "source": "side",
            },
        ],
        "requires": [],
        "host": {
            "kind": "command",
            "command": ["host-adapter"],
            "profiles": {"worker-standard": profile},
            "lanes": {
                "repo-main": "worker-standard",
                "repo-side": "worker-standard",
            },
        },
    }


def unit(key: str, source: str = "main", **changes) -> dict:
    value = {
        "key": key,
        "source": source,
        "binding": "bind-%s-v1" % key.replace("/", "-"),
        "state": "pending",
        "authorized": True,
        "parents": [],
        "writes": ["%s.txt" % key.replace("/", "-")],
        "resources": [],
        "brief": {"title": "Implement %s" % key, "worker": "worker-standard"},
    }
    value.update(changes)
    return value


class FakeSources:
    def __init__(self, units: dict[str, dict]):
        self.units = deepcopy(units)
        self.prepares: list[tuple[str, str]] = []
        self.binds: list[tuple[str, str]] = []
        self.renews: list[str] = []
        self.finishes: list[str] = []
        self.finish_result: dict | None = None
        self.on_prepare = None

    def snapshot(self):
        return deepcopy(self.units)

    def prepare(self, key, operation_id):
        self.prepares.append((key, operation_id))
        current = self.units[key]
        current["state"] = "running"
        if self.on_prepare is not None:
            self.on_prepare(key)
        return {
            "schema": "fake/v1",
            "key": key,
            "source": current["source"],
            "operation_id": operation_id,
            "binding": current["binding"],
            "claim_token": "private-claim-value",
            "brief": {
                "dispatch_prompt": deepcopy(current["brief"]),
                "role_reference": "roles/worker.md",
            },
        }

    def bind(self, key, receipt, host_id):
        self.binds.append((key, host_id))

    def renew(self, key, receipt):
        self.renews.append(key)
        return receipt

    def finish(self, key, receipt, host_id, evidence=None):
        self.finishes.append(key)
        if self.finish_result is not None:
            self.units[key]["state"] = self.finish_result.get("state", "correction")
            return deepcopy(self.finish_result)
        self.units[key]["state"] = "completed"
        return {"accepted": True, "state": "completed"}


class FakeHost:
    def __init__(self):
        self.by_operation: dict[str, str] = {}
        self.starts: list[dict] = []
        self.states: dict[str, dict] = {}

    def start(self, operation_id, key, brief, repository):
        if operation_id in self.by_operation:
            return self.by_operation[operation_id]
        host_id = "host-%d" % (len(self.by_operation) + 1)
        self.by_operation[operation_id] = host_id
        self.starts.append(
            {"operation_id": operation_id, "key": key, "brief": brief, "repository": repository}
        )
        self.states[host_id] = {"state": "running"}
        return host_id

    def inspect(self, host_id):
        return deepcopy(self.states[host_id])


class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "repo").mkdir()
        (self.root / "portfolio.json").write_text("{}\n", encoding="utf-8")
        self.private = self.root / "private" / "coordination.json"

    def tearDown(self):
        self.temporary.cleanup()

    def coordinator(self, configuration, sources, host):
        return Coordinator(configuration, self.root, self.private, sources, host)

    def grant_all(self, coordinator, keys):
        coordinator.grant(list(keys), "User requested implementation in this conversation.")

    def test_parallel_start_and_restart_do_not_duplicate_dispatch(self):
        units = {"main/A": unit("main/A"), "main/B": unit("main/B")}
        sources = FakeSources(units)
        host = FakeHost()
        coordinator = self.coordinator(config(), sources, host)
        self.grant_all(coordinator, units)

        first = coordinator.tick()
        restarted = self.coordinator(config(), sources, host)
        second = restarted.tick()

        self.assertEqual(first["started"], ["main/A", "main/B"])
        self.assertEqual(len(host.starts), 2)
        self.assertEqual(host.starts[0]["brief"]["agent_type"], "worker-standard")
        self.assertNotIn("claim_token", host.starts[0]["brief"])
        self.assertEqual(second["started"], [])
        self.assertEqual(sorted(second["renewed"]), ["main/A", "main/B"])
        self.assertNotIn("private-claim-value", json.dumps(restarted.status()))
        self.assertEqual(self.private.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.private.parent.stat().st_mode & 0o777, 0o700)

    def test_source_acceptance_unlocks_and_starts_collaboration_lane(self):
        provider = unit("main/provider")
        consumer = unit("side/consumer", source="side")
        configuration = config(maximum=1)
        configuration["requires"] = [
            {
                "consumer": consumer["key"],
                "provider": provider["key"],
                "binding": provider["binding"],
            }
        ]
        sources = FakeSources({provider["key"]: provider, consumer["key"]: consumer})
        host = FakeHost()
        coordinator = self.coordinator(configuration, sources, host)
        self.grant_all(coordinator, sources.units)
        coordinator.tick()
        provider_host = host.by_operation[next(iter(host.by_operation))]
        host.states[provider_host] = {"state": "succeeded", "evidence": "evidence/provider.json"}

        result = coordinator.tick()

        self.assertEqual(result["accepted"], [provider["key"]])
        self.assertEqual(result["started"], [consumer["key"]])
        self.assertEqual([item["key"] for item in host.starts], [provider["key"], consumer["key"]])

    def test_pause_reconciles_live_work_without_starting_new_work(self):
        first = unit("main/A")
        second = unit("main/B", parents=[first["key"]])
        sources = FakeSources({first["key"]: first, second["key"]: second})
        host = FakeHost()
        coordinator = self.coordinator(config(maximum=1), sources, host)
        self.grant_all(coordinator, sources.units)
        coordinator.tick()
        first_host = next(iter(host.states))
        host.states[first_host] = {"state": "succeeded", "evidence": "evidence/a.json"}
        coordinator.pause()

        result = coordinator.tick()

        self.assertEqual(result["accepted"], [first["key"]])
        self.assertEqual(result["started"], [])
        self.assertEqual(len(host.starts), 1)
        self.assertTrue(result["paused"])

    def test_unknown_host_retains_hold_while_independent_work_progresses(self):
        first = unit("main/A")
        second = unit("main/B")
        sources = FakeSources({first["key"]: first, second["key"]: second})
        host = FakeHost()
        coordinator = self.coordinator(config(maximum=2), sources, host)
        coordinator.grant([first["key"]], "Authorized first unit.")
        coordinator.tick()
        first_host = next(iter(host.states))
        host.states[first_host] = {"state": "unknown"}
        coordinator.grant([second["key"]], "Authorized independent unit.")
        coordinator.grant([second["key"]], "Authorized under current routing policy.")

        result = coordinator.tick()

        self.assertIn({"key": first["key"], "reason": "host_unknown"}, result["attention"])
        self.assertEqual(result["started"], [second["key"]])
        operations = {item["key"]: item for item in coordinator.status()["operations"]}
        self.assertEqual(operations[first["key"]]["stage"], "needs_review")

    def test_binding_and_policy_changes_invalidate_grants(self):
        work = unit("main/A")
        sources = FakeSources({work["key"]: work})
        host = FakeHost()
        coordinator = self.coordinator(config(), sources, host)
        coordinator.grant([work["key"]], "Authorized exact current work.")
        sources.units[work["key"]]["binding"] = "bind-main-A-v2"

        changed_binding = coordinator.tick()
        self.assertEqual(changed_binding["started"], [])
        projection = changed_binding["evaluation"]["units"][0]
        self.assertEqual(projection["readiness"], "unauthorized")

        sources.units[work["key"]]["binding"] = work["binding"]
        changed_policy = self.coordinator(config(profile="new-dev"), sources, host)
        policy_status = changed_policy.status()
        self.assertEqual(policy_status["grants"], [])
        self.assertEqual(policy_status["evaluation"]["units"][0]["readiness"], "unauthorized")

    def test_no_host_is_read_only_and_reports_missing_runtime(self):
        configuration = config()
        configuration.pop("host")
        work = unit("main/A")
        sources = FakeSources({work["key"]: work})
        coordinator = self.coordinator(configuration, sources, None)
        coordinator.grant([work["key"]], "Authorized exact current work.")

        result = coordinator.tick()

        self.assertEqual(result["started"], [])
        self.assertFalse(result["evaluation"]["dispatch_enabled"])
        self.assertEqual(sources.prepares, [])

    def test_status_does_not_create_a_private_journal(self):
        work = unit("main/A")
        coordinator = self.coordinator(config(), FakeSources({work["key"]: work}), FakeHost())

        status = coordinator.status()

        self.assertEqual(status["operations"], [])
        self.assertFalse(self.private.exists())
        self.assertFalse(self.private.parent.exists())

    def test_concurrent_ticks_reserve_and_start_each_unit_once(self):
        work = unit("main/A")
        sources = FakeSources({work["key"]: work})
        host = FakeHost()
        coordinator = self.coordinator(config(maximum=1), sources, host)
        coordinator.grant([work["key"]], "Authorized concurrent observation.")

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _index: coordinator.tick(), range(2)))

        self.assertEqual(len(host.starts), 1)
        self.assertEqual(len(sources.prepares), 1)
        self.assertEqual(sum(work["key"] in result["started"] for result in results), 1)

    def test_external_gate_change_quarantines_live_operation(self):
        provider = unit("main/provider", state="completed")
        consumer = unit("side/consumer", source="side")
        configuration = config(maximum=1)
        configuration["requires"] = [
            {
                "consumer": consumer["key"],
                "provider": provider["key"],
                "binding": provider["binding"],
            }
        ]
        sources = FakeSources({provider["key"]: provider, consumer["key"]: consumer})
        host = FakeHost()
        coordinator = self.coordinator(configuration, sources, host)
        coordinator.grant([consumer["key"]], "Authorized collaboration while gate is accepted.")
        coordinator.tick()
        sources.units[provider["key"]]["state"] = "pending"

        result = coordinator.tick()

        self.assertIn(
            {"key": consumer["key"], "reason": "prerequisite_changed"},
            result["attention"],
        )
        operation = coordinator.status()["operations"][0]
        self.assertEqual(operation["stage"], "needs_review")

    def test_reconcile_reobserves_same_unknown_host_without_redispatch(self):
        work = unit("main/A")
        sources = FakeSources({work["key"]: work})
        host = FakeHost()
        coordinator = self.coordinator(config(maximum=1), sources, host)
        coordinator.grant([work["key"]], "Authorized exact work.")
        coordinator.tick()
        host_id = next(iter(host.states))
        host.states[host_id] = {"state": "unknown"}
        coordinator.tick()
        host.states[host_id] = {"state": "running"}

        self.assertEqual(coordinator.reconcile([work["key"]]), {"reconciled": [work["key"]]})
        result = coordinator.tick()

        self.assertEqual(len(host.starts), 1)
        self.assertEqual(result["renewed"], [work["key"]])

    def test_failed_source_acceptance_enters_review_without_repair_loop(self):
        work = unit("main/A")
        sources = FakeSources({work["key"]: work})
        sources.finish_result = {
            "accepted": False,
            "state": "correction",
            "reason": "focused_acceptance_failed",
        }
        host = FakeHost()
        coordinator = self.coordinator(config(maximum=1), sources, host)
        coordinator.grant([work["key"]], "Authorized exact work.")
        coordinator.tick()
        host_id = next(iter(host.states))
        host.states[host_id] = {"state": "succeeded"}

        first = coordinator.tick()
        second = coordinator.tick()

        self.assertIn(
            {"key": work["key"], "reason": "focused_acceptance_failed"},
            first["attention"],
        )
        self.assertEqual(len(sources.finishes), 1)
        self.assertEqual(second["started"], [])
        self.assertEqual(coordinator.status()["operations"][0]["stage"], "needs_review")

    def test_missing_source_unit_retains_unknown_occupancy(self):
        first = unit("main/A")
        second = unit("main/B")
        sources = FakeSources({first["key"]: first, second["key"]: second})
        host = FakeHost()
        coordinator = self.coordinator(config(maximum=1), sources, host)
        coordinator.grant([first["key"]], "Authorized first work.")
        coordinator.tick()
        del sources.units[first["key"]]
        coordinator.grant([second["key"]], "Authorized independent work.")

        result = coordinator.tick()

        self.assertEqual(len(host.starts), 1)
        projection = {item["key"]: item for item in result["evaluation"]["units"]}
        self.assertEqual(projection[first["key"]]["readiness"], "unknown")
        self.assertNotIn(second["key"], result["started"])

    def test_binding_drift_keeps_original_occupancy_and_cannot_release_old_run(self):
        first = unit("main/A", writes=["shared/original"])
        second = unit("main/B", writes=["shared/original/next"])
        sources = FakeSources({first["key"]: first, second["key"]: second})
        host = FakeHost()
        coordinator = self.coordinator(config(maximum=2), sources, host)
        coordinator.grant([first["key"]], "Authorized original binding.")
        coordinator.tick()
        sources.units[first["key"]].update(
            {"binding": "bind-main-A-v2", "state": "completed", "writes": ["narrow/new"]}
        )
        coordinator.grant([second["key"]], "Authorized independent candidate.")

        result = coordinator.tick()

        self.assertNotIn(second["key"], result["started"])
        operations = {item["key"]: item for item in coordinator.status()["operations"]}
        self.assertEqual(operations[first["key"]]["stage"], "needs_review")
        projection = {item["key"]: item for item in result["evaluation"]["units"]}
        self.assertEqual(projection[second["key"]]["readiness"], "waiting_resource")

    def test_pause_or_revoke_during_prepare_prevents_host_start(self):
        for action in ("pause", "revoke"):
            with self.subTest(action=action):
                state = self.root / ("private-" + action) / "coordination.json"
                work = unit("main/A")
                sources = FakeSources({work["key"]: work})
                host = FakeHost()
                coordinator = Coordinator(config(), self.root, state, sources, host)
                coordinator.grant([work["key"]], "Authorized exact current work.")
                if action == "pause":
                    sources.on_prepare = lambda _key: coordinator.pause()
                else:
                    sources.on_prepare = lambda _key: coordinator.revoke([work["key"]])

                result = coordinator.tick()

                self.assertEqual(host.starts, [])
                self.assertEqual(result["started"], [])
                operation = coordinator.status()["operations"][0]
                expected = "prepared" if action == "pause" else "needs_review"
                self.assertEqual(operation["stage"], expected)


if __name__ == "__main__":
    unittest.main()
