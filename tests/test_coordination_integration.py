"""Real native acceptance across independent mainline/collaboration Plans."""

from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

from scripts.better_plan.adapters.coordination_sources import NativeSources
from scripts.better_plan.application.coordinator import Coordinator
from tests.v3_fixtures import complete_plan, task, write_workspace


TOOL = Path(__file__).resolve().parents[1] / "scripts/manifest_tool.py"


class FixtureHost:
    def __init__(self, root):
        self.root = root
        self.calls = {}
        self.results = {}

    def start(self, operation_id, key, brief, repository):
        if operation_id not in self.calls:
            self.calls[operation_id] = {"key": key, "repository": repository, "brief": brief}
        return "host-" + operation_id

    def inspect(self, host_id):
        return {"state": self.results.get(host_id, "running")}

    def complete(self, key, artifact):
        operation_id, call = next((op, value) for op, value in self.calls.items() if value["key"] == key)
        (self.root / call["repository"] / artifact).write_text("verified synthetic output\n")
        self.results["host-" + operation_id] = "succeeded"


class CoordinationIntegrationTests(unittest.TestCase):
    def test_two_mainlines_and_collaboration_advance_only_after_native_acceptance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            selected = [("alpha", "Alpha", "main", "PLAN-001", "alpha.txt"),
                        ("beta", "Beta", "main", "PLAN-001", "beta.txt"),
                        ("bridge", "Beta", "integration", "PLAN-002", "bridge.txt")]
            entries = {}
            for source, repository, delivery, code, artifact in selected:
                workspace = root / repository / "docs/plans"
                workspace.mkdir(parents=True, exist_ok=True)
                plan = complete_plan(delivery)
                plan["code"] = code
                command = 'python3 -c "from pathlib import Path; assert Path(\'%s\').read_text().startswith(\'verified\')"' % artifact
                plan["spec"]["tasks"] = [task(write_paths=[artifact], command=command)]
                write_workspace(workspace, plan)
                manifest_path = workspace / "Manifest.json"
                manifest = json.loads(manifest_path.read_text())
                manifest["project_root"] = "../.."
                entries.setdefault(repository, []).extend(manifest["plans"])
                manifest["plans"] = entries[repository]
                manifest_path.write_text(json.dumps(manifest))
                result = subprocess.run([sys.executable, str(TOOL), "authorize-plan", str(workspace),
                    "--plan", code, "--source", "inherited_implementation_request", "--reference", "synthetic-test"],
                    capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, "synthetic Plan authorization failed")
            portfolio = root / "portfolio.json"
            portfolio.write_text(json.dumps({"schema": "better-plan.coordination-portfolio/v1", "namespace": "example",
                "sources": [{"id": source, "kind": "better-plan-v3", "path": repository + "/docs/plans/" + delivery + "/Plan.json"}
                            for source, repository, delivery, _code, _artifact in selected]}))
            lanes = [{"id": source, "kind": "collaboration" if source == "bridge" else "mainline",
                      "repository": repository, "source": source} for source, repository, *_ in selected]
            sources = NativeSources(root, portfolio, lanes)
            units = sources.snapshot()
            self.assertFalse(sources.source_errors)
            config = {"schema": "better-plan.coordination/v1", "namespace": "example", "portfolio": "portfolio.json",
                      "max_parallel": 2, "lanes": lanes,
                      "constraints": ["Preserve the separately owned appearance changes."],
                      "requires": [{"consumer": "bridge/TASK-001", "provider": "alpha/TASK-001",
                                    "binding": units["alpha/TASK-001"]["binding"]}],
                      "host": {"kind": "command", "command": ["host-adapter"], "profiles": {"worker-standard": "fixture"}}}
            host = FixtureHost(root)
            state = root / ".private/Coordinator.json"
            coordinator = Coordinator(config, root, state, sources, host)
            coordinator.grant(list(units), "Authorized synthetic fixture")
            first = coordinator.tick()
            self.assertEqual(set(first["started"]), {"alpha/TASK-001", "beta/TASK-001"})
            self.assertEqual(len(host.calls), 2)
            self.assertTrue(all(value["brief"]["coordination_constraints"] == config["constraints"]
                                for value in host.calls.values()))
            # A restarted observer retains the two exact host operations.
            restarted = Coordinator(config, root, state, NativeSources(root, portfolio, lanes), host)
            restarted.tick()
            self.assertEqual(len(host.calls), 2)
            host.complete("alpha/TASK-001", "alpha.txt")
            second = restarted.tick()
            self.assertIn("alpha/TASK-001", second["accepted"], second["attention"])
            self.assertIn("bridge/TASK-001", second["started"])
            self.assertEqual(sources.snapshot()["beta/TASK-001"]["state"], "running")
            host.complete("beta/TASK-001", "beta.txt")
            host.complete("bridge/TASK-001", "bridge.txt")
            last = restarted.tick()
            self.assertEqual(set(last["accepted"]), {"beta/TASK-001", "bridge/TASK-001"})
            self.assertEqual({u["state"] for u in sources.snapshot().values()}, {"completed"})
            self.assertEqual(len(host.calls), 3)
            # Whole-Plan review/close remains the source workflow's own stage.
            for _source, repository, delivery, _code, _artifact in selected:
                path = root / repository / "docs/plans" / delivery / "Plan.json"
                self.assertEqual(json.loads(path.read_text())["phase"], "authorized")


if __name__ == "__main__":
    unittest.main()
