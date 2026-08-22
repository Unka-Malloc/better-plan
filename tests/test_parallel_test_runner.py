"""Contracts for complete, process-isolated parallel test scheduling."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import unittest
from unittest import mock

from scripts import run_tests


class ParallelTestRunnerTests(unittest.TestCase):
    def test_shards_partition_every_test_module_exactly_once(self) -> None:
        self.assertEqual(run_tests.shard_catalog_issues(), [])

    def test_all_shards_are_submitted_before_results_are_collected(self) -> None:
        submitted = []
        expected = list(run_tests.SHARDS)
        test_case = self

        class Future:
            def __init__(self, result: run_tests.ShardResult) -> None:
                self._result = result

            def result(self) -> run_tests.ShardResult:
                test_case.assertEqual(
                    [name for name, _ in submitted],
                    expected,
                    "the runner collected a result before submitting every shard",
                )
                return self._result

        class Executor:
            def __init__(self, max_workers: int) -> None:
                test_case.assertEqual(max_workers, len(expected))

            def __enter__(self) -> "Executor":
                return self

            def __exit__(self, *_: object) -> None:
                return None

            def submit(self, _function: object, name: str, modules: object) -> Future:
                submitted.append((name, tuple(modules)))
                return Future(run_tests.ShardResult(name, 0, ""))

        with mock.patch.object(run_tests, "ThreadPoolExecutor", Executor):
            with redirect_stdout(io.StringIO()):
                result = run_tests.run_shards(expected)

        self.assertEqual(result, 0)
        self.assertEqual(
            submitted,
            [(name, run_tests.SHARDS[name]) for name in expected],
        )

    def test_any_failed_shard_fails_the_complete_run(self) -> None:
        def runner(name: str, _modules: object) -> run_tests.ShardResult:
            return run_tests.ShardResult(
                name,
                1 if name == "installation" else 0,
                "representative output",
            )

        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            result = run_tests.run_shards(("core", "installation"), runner=runner)

        self.assertEqual(result, 1)
        self.assertIn("failed test shards: installation", output.getvalue())


if __name__ == "__main__":
    unittest.main()
