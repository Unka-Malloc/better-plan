from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.better_plan.application import workflow
from scripts.better_plan.hooks import config as hook_config


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "efficiency-inspector"
TOKEN_SCRIPT = SKILL_ROOT / "scripts" / "token_totals.py"
TIMEOUT_SCRIPT = SKILL_ROOT / "scripts" / "timeout_summary.py"
TIMEOUT_CATALOG = SKILL_ROOT / "references" / "timeout-catalog.json"
EFFICIENCY_SKILL = SKILL_ROOT / "SKILL.md"
PARALLEL_PROTOCOL = SKILL_ROOT / "references" / "parallel-audit.md"
EFFICIENCY_METADATA = SKILL_ROOT / "agents" / "openai.yaml"
ADAPTER_BOUNDARY = SKILL_ROOT / "references" / "adapter-boundary.md"
DATA_LAYOUT = SKILL_ROOT / "references" / "data-layout.md"
CUTOFF = "2026-08-11T12:00:00Z"


def _write_jsonl(path, records):
    path.write_text(
        "".join(json.dumps(record, separators=(",", ":")) + "\n" for record in records),
        encoding="utf-8",
    )


def _token_sample(
    sample_id,
    root,
    scope,
    kind,
    behavior,
    assessment,
    input_tokens,
    cached,
    output,
    events=1,
):
    return {
        "schema": "efficiency-inspector/token-observation/v1",
        "sample_id": sample_id,
        "agent": "codex",
        "batch": "snapshot-001",
        "root": root,
        "cutoff": CUTOFF,
        "scope": scope,
        "kind": kind,
        "behavior": behavior,
        "assessment": assessment,
        "input_tokens": input_tokens,
        "cached_input_tokens": cached,
        "output_tokens": output,
        "event_count": events,
    }


def _timeout_sample(sample_id, cluster, policy_key, configured, expired, elapsed, outcome):
    return {
        "schema": "efficiency-inspector/timeout-sample/v1",
        "sample_id": sample_id,
        "agent": "codex",
        "batch": "snapshot-001",
        "cluster": cluster,
        "policy_key": policy_key,
        "configured_timeouts_ms": configured,
        "expired_timeout_count": expired,
        "elapsed_ms": elapsed,
        "outcome": outcome,
        "correlation": "direct",
        "measurement": "cutoff" if outcome == "active" else "trace_pair",
        "covariates": {},
    }


class EfficiencyInspectorTest(unittest.TestCase):
    def _run(self, script, *args):
        return subprocess.run(
            [sys.executable, str(script), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_token_calculator_only_sums_normalized_observations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "one.jsonl"
            second = root / "two.jsonl"
            output = root / "summary.json"
            _write_jsonl(
                first,
                [
                    _token_sample(
                        "one:wait", "conversation-001", "parent", "supervision",
                        "wait", "inefficient", 100, 80, 10,
                    ),
                    _token_sample(
                        "one:review", "conversation-001", "parent", "supervision",
                        "review", "effective", 50, 40, 5,
                    ),
                    _token_sample(
                        "one:dispatch", "conversation-001", "parent", "supervision",
                        "dispatch", "effective", 20, 10, 2,
                    ),
                    _token_sample(
                        "one:main", "conversation-001", "parent", "task_work",
                        "implementation", "neutral", 200, 100, 40,
                    ),
                    _token_sample(
                        "one:child", "conversation-001", "child", "task_work",
                        "implementation", "effective", 300, 200, 50,
                    ),
                ],
            )
            _write_jsonl(
                second,
                [
                    _token_sample(
                        "two:main", "conversation-002", "parent", "task_work",
                        "planning", "neutral", 100, 50, 10,
                    ),
                    _token_sample(
                        "two:child", "conversation-002", "child", "task_work",
                        "implementation", "effective", 100, 50, 20,
                    ),
                ],
            )

            result = self._run(
                TOKEN_SCRIPT,
                "--input",
                str(first),
                str(second),
                "--output",
                str(output),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(summary["agent"], "codex")
            self.assertEqual(summary["root_count"], 2)
            self.assertEqual(summary["tokens"]["parent_total"]["total_tokens"], 537)
            self.assertEqual(summary["tokens"]["children_total"]["total_tokens"], 470)
            self.assertEqual(summary["tokens"]["system_total"]["total_tokens"], 1007)
            self.assertEqual(summary["tokens"]["supervision"]["total_tokens"], 187)
            self.assertEqual(summary["tokens"]["effective_supervision"]["total_tokens"], 77)
            self.assertEqual(summary["tokens"]["inefficient_supervision"]["total_tokens"], 110)
            self.assertEqual(summary["tokens"]["inefficient_parent"]["total_tokens"], 110)
            self.assertEqual(summary["breakdown"]["behavior"]["wait"]["event_count"], 1)
            self.assertEqual(summary["metrics"]["supervision_effective_rate"], 0.411765)

            split = root / "split.jsonl"
            _write_jsonl(
                split,
                [
                    _token_sample(
                        "one:late", "conversation-001", "parent", "task_work",
                        "review", "mixed", 1, 0, 0,
                    )
                ],
            )
            rejected = self._run(TOKEN_SCRIPT, "--input", str(first), str(split))
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("split across input shards", rejected.stderr)

    def test_skill_teaches_executor_judgment_and_prefers_concurrency(self):
        skill = EFFICIENCY_SKILL.read_text(encoding="utf-8")
        protocol = PARALLEL_PROTOCOL.read_text(encoding="utf-8")
        metadata = EFFICIENCY_METADATA.read_text(encoding="utf-8")
        layout = DATA_LAYOUT.read_text(encoding="utf-8")
        token_tool = TOKEN_SCRIPT.read_text(encoding="utf-8")
        timeout_tool = TIMEOUT_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("执行智能体负责发现对话", skill)
        self.assertIn("监督行为与有效性", skill)
        self.assertIn("超时等待只是判断线索，不自动等于低效", skill)
        self.assertIn("优先把它们分成互斥 shard 并发", skill)
        self.assertIn("采用串行或较小波次同样可以完成审计", skill)
        self.assertIn("spawn(A), spawn(B), wait(in-flight set)", protocol)
        self.assertIn("并发是一项优先策略，不是完成审计的前置门禁", protocol)
        self.assertIn("发挥智能", metadata)
        self.assertIn("每个文件只有", skill)
        self.assertIn("一个写入者", skill)
        self.assertIn("observations/token/shard-001.jsonl", layout)
        self.assertIn("coordinator 维护 manifest", layout)
        self.assertIn("Aggregate normalized Token observations", token_tool)
        self.assertIn("avoids raw-trace parsing", timeout_tool)
        self.assertNotIn("rglob(", token_tool)
        self.assertFalse((SKILL_ROOT / "scripts" / "token_efficiency.py").exists())
        self.assertFalse((SKILL_ROOT / "scripts" / "timeout_statistics.py").exists())

    def test_skill_keeps_codex_specific_observation_separate_from_generic_tools(self):
        skill = EFFICIENCY_SKILL.read_text(encoding="utf-8")
        boundary = ADAPTER_BOUNDARY.read_text(encoding="utf-8")

        self.assertIn("当前原始证据支持 Codex", skill)
        self.assertIn("审计智能体的语义判断与标准化观察记录", boundary)
        self.assertIn("执行智能体是链路的控制者", boundary)
        self.assertIn("通用工具接收普通 JSONL/JSON", boundary)
        self.assertIn("scripts/adapters/", boundary)


class TimeoutStatisticsTest(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run(
            [sys.executable, str(TIMEOUT_SCRIPT), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_catalog_matches_framework_timeout_constants(self):
        catalog = json.loads(TIMEOUT_CATALOG.read_text(encoding="utf-8"))
        policies = {item["key"]: item for item in catalog["policies"]}
        self.assertEqual(len(policies), 7)
        for key in (
            "fsm.authorize.verify-command",
            "fsm.task.focused-regression",
            "fsm.delivery.full-regression",
        ):
            self.assertEqual(
                policies[key]["default_timeout_ms"],
                workflow.COMMAND_TIMEOUT_SECONDS * 1000,
            )
        self.assertEqual(
            policies["framework.lifecycle-hook"]["default_timeout_ms"],
            hook_config.HOOK_TIMEOUT_SECONDS * 1000,
        )

    def test_timeout_calculator_emits_all_n_rows_without_fitting_a_distribution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "one.jsonl"
            second = root / "two.jsonl"
            output = root / "summary.json"
            _write_jsonl(
                first,
                [
                    _timeout_sample(
                        "one:worker", "conversation-001", "role.worker.poll",
                        [60000, 60000, 60000], 2, 154200, "completed",
                    ),
                    _timeout_sample(
                        "one:regression", "conversation-001", "fsm.task.focused-regression",
                        [1800000], 0, 100000, "completed",
                    ),
                ],
            )
            _write_jsonl(
                second,
                [
                    _timeout_sample(
                        "two:worker", "conversation-002", "role.worker.poll",
                        [60000], 1, 200000, "active",
                    ),
                    _timeout_sample(
                        "two:regression", "conversation-002", "fsm.task.focused-regression",
                        [1800000], 1, 1800000, "timed_out",
                    ),
                ],
            )

            result = self._run(
                "--input", str(first), str(second), "--output", str(output)
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(summary["catalog_size"], 7)
            self.assertEqual(len(summary["policies"]), 7)
            policies = {item["policy_key"]: item for item in summary["policies"]}
            worker = policies["role.worker.poll"]
            self.assertEqual(worker["sample_count"], 2)
            self.assertEqual(worker["runtime"]["right_censored_count"], 1)
            self.assertEqual(
                worker["runtime"]["completed_descriptive_quantiles_ms"]["p50"],
                154200.0,
            )
            self.assertEqual(worker["timeout_settings"]["expiration_rate"], 0.75)
            regression = policies["fsm.task.focused-regression"]
            self.assertEqual(regression["alignment"]["observed_timeout_rate"], 0.5)
            self.assertEqual(summary["interpretation"]["scope"], "descriptive validation only")

            split = root / "split.jsonl"
            _write_jsonl(
                split,
                [
                    _timeout_sample(
                        "one:late", "conversation-001", "role.designer.poll",
                        [60000], 0, 1000, "completed",
                    )
                ],
            )
            rejected = self._run("--input", str(first), str(split))
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("split across input shards", rejected.stderr)


if __name__ == "__main__":
    unittest.main()
