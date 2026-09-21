"""Observer boundaries of the coordination command."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts.better_plan.adapters.coordination_cli import watch


class CoordinationCliTests(unittest.TestCase):
    def test_wake_during_tick_is_not_lost_and_stop_preserves_host_work(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "Coordinator.json"
            wake = state.with_suffix(".json.wake")
            coordinator = mock.Mock()

            def first_tick():
                wake.write_text("")
                return {"accepted": ["upstream/TASK-001"]}

            calls = []

            def tick():
                if calls:
                    raise KeyboardInterrupt
                calls.append(True)
                return first_tick()

            coordinator.tick.side_effect = tick
            emitted = []
            sleep = mock.Mock(side_effect=AssertionError("wake should be immediate"))
            watch(coordinator, state, 60, emitted.append, sleep=sleep)
            self.assertEqual(coordinator.tick.call_count, 2)
            self.assertEqual(emitted[-1], {"observer": "stopped", "running_work": "preserved"})
            sleep.assert_not_called()



if __name__ == "__main__":
    unittest.main()
