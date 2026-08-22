"""Run the complete Better Plan test suite as isolated parallel architecture shards."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
from typing import Callable, Sequence


ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "tests"
SHARDS = {
    "core": (
        "tests.test_design_compile",
        "tests.test_model_routing",
        "tests.test_python_compatibility",
        "tests.test_v3_protocol",
    ),
    "hosts": (
        "tests.test_agent_templates",
        "tests.test_hook_tool",
        "tests.test_native_role_resolution",
    ),
    "installation": ("tests.test_install_tool",),
    "workflow": ("tests.test_v3_workflow",),
    "tooling": (
        "tests.test_efficiency_inspector",
        "tests.test_parallel_test_runner",
        "tests.test_workload_tools",
    ),
}


@dataclass(frozen=True)
class ShardResult:
    name: str
    returncode: int
    output: str


def discover_test_modules() -> set[str]:
    return {"tests.%s" % path.stem for path in TEST_ROOT.glob("test_*.py")}


def shard_catalog_issues() -> list[str]:
    discovered = discover_test_modules()
    listed = [module for modules in SHARDS.values() for module in modules]
    counts = Counter(listed)
    duplicates = sorted(module for module, count in counts.items() if count > 1)
    missing = sorted(discovered - set(listed))
    unknown = sorted(set(listed) - discovered)
    issues = []
    if duplicates:
        issues.append("duplicate test modules: %s" % ", ".join(duplicates))
    if missing:
        issues.append("unsharded test modules: %s" % ", ".join(missing))
    if unknown:
        issues.append("unknown test modules: %s" % ", ".join(unknown))
    return issues


def _run_shard(name: str, modules: Sequence[str]) -> ShardResult:
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "-v", *modules],
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return ShardResult(name, completed.returncode, completed.stdout)


def run_shards(
    names: Sequence[str],
    runner: Callable[[str, Sequence[str]], ShardResult] | None = None,
) -> int:
    selected = list(names)
    if not selected:
        return 0
    execute = runner or _run_shard
    with ThreadPoolExecutor(max_workers=len(selected)) as executor:
        futures = {
            name: executor.submit(execute, name, SHARDS[name])
            for name in selected
        }
        results = [futures[name].result() for name in selected]

    for result in results:
        print("=== %s shard ===" % result.name)
        if result.output:
            print(result.output.rstrip())
    failed = [result.name for result in results if result.returncode != 0]
    if failed:
        print("failed test shards: %s" % ", ".join(failed), file=sys.stderr)
        return 1
    print("all %d test shards passed" % len(results))
    return 0


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run Better Plan tests in isolated parallel process shards."
    )
    parser.add_argument(
        "--shard",
        action="append",
        choices=tuple(SHARDS),
        help="run one named shard; repeat to select multiple shards",
    )
    args = parser.parse_args(arguments)
    issues = shard_catalog_issues()
    if issues:
        for issue in issues:
            print("invalid test shard catalog: %s" % issue, file=sys.stderr)
        return 2
    selected = list(dict.fromkeys(args.shard or SHARDS))
    return run_shards(selected)


if __name__ == "__main__":
    raise SystemExit(main())
