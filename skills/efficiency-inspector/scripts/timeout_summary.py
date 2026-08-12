#!/usr/bin/env python3
"""Validate and describe normalized Better Plan timeout observations.

The calculator intentionally avoids raw-trace parsing and distribution fitting. Auditors own event
association and model choice.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence


SAMPLE_SCHEMA = "efficiency-inspector/timeout-sample/v1"
CATALOG_SCHEMA = "efficiency-inspector/timeout-catalog/v1"
SUMMARY_SCHEMA = "efficiency-inspector/timeout-summary/v1"
DEFAULT_CATALOG = Path(__file__).resolve().parents[1] / "references" / "timeout-catalog.json"
OUTCOMES = ("completed", "timed_out", "active", "failed", "cancelled", "blocked")
CORRELATIONS = ("direct", "reconstructed", "contextual")
MEASUREMENTS = ("monotonic", "trace_pair", "cutoff", "reconstructed")
SAFE_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
AGENT_LABEL = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


class SummaryError(RuntimeError):
    pass


def _label(value: Any, field: str, pattern: Any = SAFE_LABEL) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise SummaryError("%s is not a safe label" % field)
    return value


def _integer(value: Any, field: str, nullable: bool = False) -> Optional[int]:
    if nullable and value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SummaryError("%s must be a non-negative integer%s" % (field, " or null" if nullable else ""))
    return value


def _ratio(numerator: float, denominator: float) -> Optional[float]:
    return None if denominator == 0 else round(numerator / denominator, 6)


def _quantile(values: Sequence[float], probability: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    low = int(math.floor(position))
    high = int(math.ceil(position))
    if low == high:
        return round(float(ordered[low]), 6)
    weight = position - low
    return round(float(ordered[low]) * (1.0 - weight) + float(ordered[high]) * weight, 6)


def _quantiles(values: Sequence[float]) -> Dict[str, Optional[float]]:
    return {
        "p50": _quantile(values, 0.50),
        "p90": _quantile(values, 0.90),
        "p95": _quantile(values, 0.95),
    }


def _catalog(path: Path) -> List[Dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SummaryError("cannot read timeout catalog") from exc
    if not isinstance(value, dict) or value.get("schema") != CATALOG_SCHEMA:
        raise SummaryError("unexpected timeout catalog schema")
    policies = value.get("policies")
    if not isinstance(policies, list) or not policies:
        raise SummaryError("timeout catalog has no policies")
    keys = [policy.get("key") for policy in policies if isinstance(policy, dict)]
    if len(keys) != len(policies) or len(set(keys)) != len(keys):
        raise SummaryError("timeout catalog policy keys must be unique")
    return policies


def _samples(paths: Sequence[Path], policy_keys: set) -> List[Dict[str, Any]]:
    samples: List[Dict[str, Any]] = []
    sample_ids = set()
    cluster_files: Dict[str, Path] = {}
    for path in paths:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise SummaryError("cannot read input %s" % path) from exc
        for line_number, line in enumerate(lines, 1):
            if not line.strip():
                continue
            try:
                sample = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SummaryError("invalid JSON at %s:%d" % (path, line_number)) from exc
            if not isinstance(sample, dict) or sample.get("schema") != SAMPLE_SCHEMA:
                raise SummaryError("unexpected timeout sample schema at %s:%d" % (path, line_number))
            sample_id = _label(sample.get("sample_id"), "sample_id")
            if sample_id in sample_ids:
                raise SummaryError("duplicate sample_id: %s" % sample_id)
            sample_ids.add(sample_id)
            cluster = _label(sample.get("cluster"), "cluster")
            owner = cluster_files.setdefault(cluster, path)
            if owner != path:
                raise SummaryError("cluster %s is split across input shards" % cluster)
            sample["agent"] = _label(sample.get("agent"), "agent", AGENT_LABEL)
            sample["batch"] = _label(sample.get("batch"), "batch")
            if sample.get("policy_key") not in policy_keys:
                raise SummaryError("unsupported timeout policy: %s" % sample.get("policy_key"))
            configured = sample.get("configured_timeouts_ms")
            if not isinstance(configured, list):
                raise SummaryError("configured_timeouts_ms must be a list")
            sample["configured_timeouts_ms"] = [
                _integer(value, "configured_timeouts_ms") for value in configured
            ]
            expired = _integer(sample.get("expired_timeout_count"), "expired_timeout_count")
            if expired is None or expired > len(configured):
                raise SummaryError("expired_timeout_count exceeds configured observations")
            sample["expired_timeout_count"] = expired
            sample["elapsed_ms"] = _integer(sample.get("elapsed_ms"), "elapsed_ms", nullable=True)
            if sample.get("outcome") not in OUTCOMES:
                raise SummaryError("unsupported outcome: %s" % sample.get("outcome"))
            if sample.get("correlation") not in CORRELATIONS:
                raise SummaryError("unsupported correlation: %s" % sample.get("correlation"))
            if sample.get("measurement") not in MEASUREMENTS:
                raise SummaryError("unsupported measurement: %s" % sample.get("measurement"))
            if not isinstance(sample.get("covariates"), dict):
                raise SummaryError("covariates must be an object")
            samples.append(sample)
    if samples:
        for field in ("agent", "batch"):
            if len({sample[field] for sample in samples}) != 1:
                raise SummaryError("inputs must use exactly one %s" % field)
    return samples


def _nominal(sample: Mapping[str, Any]) -> Optional[float]:
    return _quantile(sample["configured_timeouts_ms"], 0.50)


def _policy_summary(policy: Mapping[str, Any], samples: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    outcomes = Counter(sample["outcome"] for sample in samples)
    correlations = Counter(sample["correlation"] for sample in samples)
    settings = [value for sample in samples for value in sample["configured_timeouts_ms"]]
    direct = [sample for sample in samples if sample["correlation"] == "direct"]
    completed = [
        float(sample["elapsed_ms"])
        for sample in direct
        if sample["outcome"] == "completed" and sample["elapsed_ms"] is not None
    ]
    expired = sum(sample["expired_timeout_count"] for sample in samples)
    aligned = [
        (sample, _nominal(sample))
        for sample in direct
        if sample["outcome"] == "completed"
        and sample["elapsed_ms"] is not None
        and sample["configured_timeouts_ms"]
    ]

    if policy["policy_kind"] == "observation_window":
        ratios = [
            float(sample["elapsed_ms"]) / timeout
            for sample, timeout in aligned
            if timeout not in (None, 0)
        ]
        alignment = {
            "kind": "observation_window",
            "poll_calls_per_execution": _quantiles(
                [float(len(sample["configured_timeouts_ms"])) for sample in direct]
            ),
            "completed_runtime_to_window_ratio": _quantiles(ratios),
        }
    else:
        within = [float(sample["elapsed_ms"]) <= timeout for sample, timeout in aligned if timeout is not None]
        ratios = [
            timeout / float(sample["elapsed_ms"])
            for sample, timeout in aligned
            if timeout is not None and sample["elapsed_ms"] not in (None, 0)
        ]
        terminal = sum(outcomes[name] for name in ("completed", "timed_out", "failed", "cancelled", "blocked"))
        alignment = {
            "kind": "execution_deadline",
            "observed_timeout_rate": _ratio(outcomes["timed_out"], terminal),
            "completed_within_deadline_rate": _ratio(sum(within), len(within)),
            "deadline_to_completed_runtime_ratio": _quantiles(ratios),
        }

    return {
        "policy_key": policy["key"],
        "scope": policy["scope"],
        "policy_kind": policy["policy_kind"],
        "stage": policy["stage"],
        "default_timeout_ms": policy.get("default_timeout_ms"),
        "sample_count": len(samples),
        "cluster_count": len({sample["cluster"] for sample in samples}),
        "outcomes": {name: outcomes[name] for name in OUTCOMES},
        "correlation": {name: correlations[name] for name in CORRELATIONS},
        "timeout_settings": {
            "observation_count": len(settings),
            "expired_count": expired,
            "expiration_rate": _ratio(expired, len(settings)),
            "distinct_ms": sorted(set(settings)),
            "quantiles_ms": _quantiles([float(value) for value in settings]),
        },
        "runtime": {
            "measured_count": sum(sample["elapsed_ms"] is not None for sample in samples),
            "right_censored_count": outcomes["timed_out"] + outcomes["active"],
            "competing_outcome_count": outcomes["failed"] + outcomes["cancelled"] + outcomes["blocked"],
            "completed_direct_count": len(completed),
            "completed_descriptive_quantiles_ms": _quantiles(completed),
            "warning": "completed quantiles ignore censoring; use survival tools for distribution claims",
        },
        "alignment": alignment,
    }


def _summary(catalog: Sequence[Mapping[str, Any]], samples: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    grouped: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for sample in samples:
        grouped[sample["policy_key"]].append(sample)
    return {
        "schema": SUMMARY_SCHEMA,
        "agent": samples[0]["agent"] if samples else None,
        "batch": samples[0]["batch"] if samples else None,
        "catalog_size": len(catalog),
        "sample_count": len(samples),
        "cluster_count": len({sample["cluster"] for sample in samples}),
        "policies": [_policy_summary(policy, grouped[policy["key"]]) for policy in catalog],
        "interpretation": {
            "time_unit": "milliseconds",
            "scope": "descriptive validation only",
            "next_step": "auditor chooses censoring-aware and cluster-aware mathematical tools",
        },
    }


def _write(value: Mapping[str, Any], output: str) -> None:
    content = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    if output == "-":
        sys.stdout.write(content)
    else:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Describe normalized timeout observations; no raw-trace parsing or fitting.")
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    parser.add_argument("--input", nargs="+", required=True)
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    try:
        catalog = _catalog(Path(args.catalog))
        samples = _samples([Path(value) for value in args.input], {policy["key"] for policy in catalog})
        _write(_summary(catalog, samples), args.output)
        return 0
    except (OSError, SummaryError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
