"""The execution command boundary uses private JSON transport and opaque receipts."""

from pathlib import Path
import json
import sys
import tempfile
import unittest

from scripts.better_plan.adapters.coordination_host import CommandHost
from scripts.better_plan.domain.models import ToolError


ADAPTER = '''
from pathlib import Path
import json
import sys

request = json.load(sys.stdin)
assert request["schema"] == "better-plan.coordination-host/v1"
if request["action"] == "start":
    host_id = "job-" + request["operation_id"]
    receipt = Path(host_id + ".json")
    if not receipt.exists():
        receipt.write_text(json.dumps(request))
    print(json.dumps({"host_id": host_id}))
else:
    assert Path(request["host_id"] + ".json").is_file()
    print(json.dumps({"state": "succeeded", "evidence": "evidence/result.json",
                      "private_runtime_log": "not public"}))
'''


class CommandHostTests(unittest.TestCase):
    def test_start_and_inspect_use_the_configured_adapter_across_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "adapter.py").write_text(ADAPTER)
            command = [sys.executable, "adapter.py"]
            profiles = {"worker-standard": "selected-profile"}
            host = CommandHost(root, command, profiles)
            brief = {"agent_type": "worker-standard", "assignment": "Implement bounded work"}
            job = host.start("operation-1", "source/TASK-001", brief, "Repo")
            restarted = CommandHost(root, command, profiles)
            self.assertEqual(restarted.start("operation-1", "source/TASK-001", brief, "Repo"), job)
            self.assertEqual(len(list(root.glob("job-*.json"))), 1)
            receipt = json.loads((root / (job + ".json")).read_text())
            self.assertEqual(receipt["profile"], "selected-profile")
            self.assertEqual(receipt["brief"], brief)
            self.assertEqual(receipt["repository"], "Repo")
            self.assertEqual(restarted.inspect(job), {
                "state": "succeeded", "evidence": "evidence/result.json",
            })

    def test_invalid_response_and_failed_command_do_not_expose_runtime_output(self):
        with tempfile.TemporaryDirectory() as directory:
            for script, expected in (
                ('print("private runtime output")', "invalid response"),
                ('import sys; print("private runtime output"); sys.exit(1)', "command failed"),
            ):
                with self.subTest(expected=expected):
                    host = CommandHost(Path(directory), [sys.executable, "-c", script], {})
                    with self.assertRaisesRegex(ToolError, expected) as raised:
                        host.inspect("job-1")
                    self.assertNotIn("private runtime output", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
