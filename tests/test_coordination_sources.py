"""Native source adapters preserve source authority and private receipts."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import json
import sqlite3
import subprocess
import sys
import time
import unittest
from unittest import mock

from scripts.better_plan.adapters.coordination_sources import NativeSources
from scripts.better_plan.adapters.coordination_portfolio import _digest
from tests.v3_fixtures import complete_plan, write_workspace


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "scripts" / "manifest_tool.py"


class CoordinationSourceTests(unittest.TestCase):
    def portfolio(self, root: Path, source: dict) -> Path:
        path = root / "portfolio.json"
        path.write_text(json.dumps({
            "schema": "better-plan.coordination-portfolio/v1",
            "namespace": "test",
            "sources": [source],
        }), encoding="utf-8")
        return path

    def test_v3_prepare_is_idempotent_and_native_finish_accepts(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "repo" / "docs" / "plans"
            write_workspace(workspace, complete_plan())
            manifest_path = workspace / "Manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["project_root"] = "../.."
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            (root / "repo" / "source.txt").write_text("fixture\n", encoding="utf-8")
            subprocess.run([
                sys.executable, str(TOOL), "authorize-plan", str(workspace),
                "--plan", "PLAN-001", "--source", "inherited_implementation_request",
                "--reference", "authorized-test",
            ], cwd=str(ROOT), check=True, capture_output=True, text=True)
            portfolio = self.portfolio(root, {
                "id": "repo", "kind": "better-plan-v3", "path": "repo/docs/plans/delivery/Plan.json",
            })
            sources = NativeSources(root, portfolio, [{
                "id": "main", "kind": "mainline", "repository": "repo", "source": "repo",
            }])

            unit = sources.snapshot()["repo/TASK-001"]
            self.assertTrue(unit["authorized"])
            self.assertEqual(unit["state"], "pending")
            self.assertEqual(unit["writes"], ["repo/source.txt"])
            self.assertEqual(unit["brief"]["agent_type"], "worker-standard")
            first = sources.prepare("repo/TASK-001", "operation-001")
            second = sources.prepare("repo/TASK-001", "operation-001")
            self.assertEqual(first["dispatch_id"], second["dispatch_id"])
            self.assertEqual(first["brief"], second["brief"])
            self.assertNotIn("claim_token", json.dumps(first["brief"]))
            sources.bind("repo/TASK-001", first, "worker/001")
            # The coordinator persists the receipt before bind; v3 renew is a
            # no-op and completion correlation is verified by native binding.
            persisted = json.loads(json.dumps(first))
            self.assertEqual(sources.renew("repo/TASK-001", persisted), persisted)
            result = sources.finish("repo/TASK-001", persisted, "worker/001")
            self.assertTrue(result["accepted"])
            self.assertEqual(sources.snapshot()["repo/TASK-001"]["state"], "completed")

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["project_root"] = ".."
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            stale = sources.snapshot()["repo/TASK-001"]
            self.assertEqual(stale["state"], "unknown")
            self.assertFalse(stale["authorized"])
            self.assertEqual(sources.source_errors["repo"], "source unavailable or unsupported")

    def test_unavailable_source_is_isolated_and_exposes_sanitized_source_error(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "repo").mkdir()
            portfolio = self.portfolio(root, {
                "id": "missing", "kind": "better-plan-v3", "path": "repo/missing/Plan.json",
            })
            sources = NativeSources(root, portfolio, [{
                "id": "side", "kind": "collaboration", "repository": "repo", "source": "missing",
            }])
            snapshot = sources.snapshot()
            self.assertEqual(snapshot["missing/<unavailable>"]["state"], "unknown")
            self.assertEqual(snapshot["missing/<unavailable>"]["binding"], "unavailable")
            self.assertFalse(snapshot["missing/<unavailable>"]["authorized"])
            self.assertEqual(sources.source_errors, {"missing": "source unavailable or unsupported"})
            self.assertNotIn(str(root), json.dumps(snapshot))

    def test_v7_snapshot_and_same_owner_claim_recovery_keep_token_private(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            graph_dir = root / "repo" / "plans" / "graph"
            (graph_dir / "generated").mkdir(parents=True)
            task = {
                "id": "A", "title": "A", "depends_on": [], "predecessors": [],
                "resources": ["shared"], "write_scopes": ["src/a"],
                "deliverables": ["result"], "implementation": ["implement"],
                "acceptance": ["AC-1"], "completion_contract": "evidence",
                "authorization": "local", "fingerprints": {"task_fingerprint": "fingerprint-A"},
                "acceptance_specs": [{"id": "AC-1", "required_level": "repository"}],
            }
            graph = {
                "schema_version": 1, "revision": "v7.1.0", "architecture_revision": "v7.1.0",
                "cases": [{"id": "AC-1"}], "tasks": [{
                    "id": "A", "title": "A", "depends_on": [], "resources": ["shared"],
                    "write_scopes": ["src/a"], "acceptance": ["AC-1"],
                }],
            }
            architecture = {"revision": "v7.1.0"}
            project = {"schema_version": 1, "execution": "execution.json", "architecture": "architecture.json"}
            artifact = {
                "schema_version": 1, "kind": "development-work-items-not-native-workflow",
                "graph_digest": _digest({"architecture": architecture, "execution": graph, "distribution": None}),
                "items": [task],
            }
            for name, value in (("project.json", project), ("execution.json", graph),
                                ("architecture.json", architecture), ("generated/work-items.json", artifact)):
                (graph_dir / name).write_text(json.dumps(value), encoding="utf-8")
            state = root / "repo" / "plans" / "state.sqlite3"
            database = sqlite3.connect(state)
            database.execute("""CREATE TABLE tasks(
                id TEXT PRIMARY KEY,status TEXT,fingerprint TEXT,lease_until REAL,
                write_scopes TEXT,resources TEXT,owner TEXT,token TEXT,
                generation INTEGER,input_digest TEXT)""")
            database.execute("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?)", (
                "A", "running", "fingerprint-A", time.time() + 600,
                "[\"src/a\"]", "[\"shared\"]", "operation-001", "private-claim-token",
                3, "input-digest",
            ))
            database.commit()
            database.close()
            portfolio = self.portfolio(root, {
                "id": "repo", "kind": "execution-graph-v7", "path": "repo/plans/graph/project.json",
                "state": "repo/plans/state.sqlite3",
            })
            sources = NativeSources(root, portfolio, [{
                "id": "main", "kind": "mainline", "repository": "repo", "source": "repo",
            }])

            unit = sources.snapshot()["repo/A"]
            self.assertEqual(unit["state"], "running")
            self.assertEqual(unit["writes"], ["repo/src/a"])
            self.assertNotIn("private-claim-token", json.dumps(unit))
            receipt = sources.prepare("repo/A", "operation-001")
            self.assertEqual(receipt["claim"]["claim_token"], "private-claim-token")
            self.assertNotIn("private-claim-token", json.dumps(receipt["brief"]))
            self.assertEqual(receipt["brief"]["role_reference"], "references/worker.md")
            self.assertEqual(receipt["brief"]["brief"]["id"], "A")
            self.assertEqual(receipt["brief"]["brief"]["write_scopes"], ["src/a"])
            self.assertEqual(receipt["brief"]["brief"]["acceptance_specs"][0]["id"], "AC-1")

            sources.bind("repo/A", receipt, "worker/001")
            evidence_dir = root / "repo" / "evidence"
            evidence_dir.mkdir()
            evidence = evidence_dir / "receipt.json"
            evidence.write_text(json.dumps({
                "status": "passed", "source_revision": "a" * 40,
                "producer": "test", "checks": [{"case_id": "AC-1"}],
            }), encoding="utf-8")
            captured = {}

            def accept(source, *arguments):
                temporary = Path(arguments[-1])
                captured["path"] = temporary
                captured["value"] = json.loads(temporary.read_text(encoding="utf-8"))
                return {"status": "accepted"}

            with mock.patch.object(sources, "_v7_command", side_effect=accept):
                result = sources.finish("repo/A", receipt, "worker/001", "evidence/receipt.json")
            self.assertTrue(result["accepted"])
            self.assertEqual(captured["value"]["claim_token"], "private-claim-token")
            self.assertEqual(captured["value"]["generation"], 3)
            self.assertEqual(captured["value"]["checks"], [{"case_id": "AC-1"}])
            self.assertFalse(captured["path"].exists())


if __name__ == "__main__":
    unittest.main()
