#!/usr/bin/env python3
"""Aggregate normalized Token observations created by an audit executor."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


SAMPLE_SCHEMA = "efficiency-inspector/token-observation/v1"
SUMMARY_SCHEMA = "efficiency-inspector/token-summary/v1"
SCOPES = ("parent", "child")
KINDS = ("supervision", "task_work")
ASSESSMENTS = ("effective", "inefficient", "mixed", "neutral")
SAFE_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
AGENT_LABEL = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


class SummaryError(RuntimeError):
    pass


def _integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SummaryError("%s must be a non-negative integer" % field)
    return value


def _label(value: Any, field: str, pattern: Any = SAFE_LABEL) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise SummaryError("%s is not a safe label" % field)
    return value


def _empty_vector() -> Dict[str, int]:
    return {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0}


def _add(target: Dict[str, int], source: Mapping[str, int]) -> None:
    for field in target:
        target[field] += source[field]


def _sum(vectors: Iterable[Mapping[str, int]]) -> Dict[str, int]:
    result = _empty_vector()
    for vector in vectors:
        _add(result, vector)
    return result


def _subtract(left: Mapping[str, int], right: Mapping[str, int]) -> Dict[str, int]:
    result = {field: left[field] - right[field] for field in left}
    if min(result.values()) < 0:
        raise SummaryError("derived Token vector would be negative")
    return result


def _report(vector: Mapping[str, int]) -> Dict[str, int]:
    uncached = vector["input_tokens"] - vector["cached_input_tokens"]
    if uncached < 0:
        raise SummaryError("cached input exceeds input")
    return {
        "input_tokens": vector["input_tokens"],
        "cached_input_tokens": vector["cached_input_tokens"],
        "uncached_input_tokens": uncached,
        "output_tokens": vector["output_tokens"],
        "total_tokens": vector["input_tokens"] + vector["output_tokens"],
    }


def _total(vector: Mapping[str, int]) -> int:
    return vector["input_tokens"] + vector["output_tokens"]


def _ratio(numerator: int, denominator: int) -> Optional[float]:
    return None if denominator == 0 else round(numerator / denominator, 6)


def _read(paths: Sequence[Path]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    sample_ids = set()
    root_files: Dict[str, Path] = {}
    for path in paths:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise SummaryError("cannot read input %s" % path) from exc
        for line_number, line in enumerate(lines, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SummaryError("invalid JSON at %s:%d" % (path, line_number)) from exc
            if not isinstance(record, dict) or record.get("schema") != SAMPLE_SCHEMA:
                raise SummaryError("unexpected Token observation schema at %s:%d" % (path, line_number))
            sample_id = _label(record.get("sample_id"), "sample_id")
            if sample_id in sample_ids:
                raise SummaryError("duplicate sample_id: %s" % sample_id)
            sample_ids.add(sample_id)
            root = _label(record.get("root"), "root")
            owner = root_files.setdefault(root, path)
            if owner != path:
                raise SummaryError("root %s is split across input shards" % root)
            record["agent"] = _label(record.get("agent"), "agent", AGENT_LABEL)
            record["batch"] = _label(record.get("batch"), "batch")
            cutoff = record.get("cutoff")
            if not isinstance(cutoff, str) or not cutoff:
                raise SummaryError("cutoff must be a non-empty timestamp")
            if record.get("scope") not in SCOPES:
                raise SummaryError("unsupported scope: %s" % record.get("scope"))
            if record.get("kind") not in KINDS:
                raise SummaryError("unsupported kind: %s" % record.get("kind"))
            if record.get("assessment") not in ASSESSMENTS:
                raise SummaryError("unsupported assessment: %s" % record.get("assessment"))
            record["behavior"] = _label(record.get("behavior"), "behavior")
            vector = {
                field: _integer(record.get(field), field)
                for field in ("input_tokens", "cached_input_tokens", "output_tokens")
            }
            if vector["cached_input_tokens"] > vector["input_tokens"]:
                raise SummaryError("cached input exceeds input in %s" % sample_id)
            record["vector"] = vector
            record["event_count"] = _integer(record.get("event_count"), "event_count")
            records.append(record)
    if not records:
        raise SummaryError("no Token observations found")
    for field in ("agent", "batch", "cutoff"):
        if len({record[field] for record in records}) != 1:
            raise SummaryError("inputs must use exactly one %s" % field)
    return records


def _select(records: Sequence[Mapping[str, Any]], **criteria: str) -> Dict[str, int]:
    return _sum(
        record["vector"]
        for record in records
        if all(record[field] == value for field, value in criteria.items())
    )


def _breakdown(records: Sequence[Mapping[str, Any]], field: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for value in sorted({str(record[field]) for record in records}):
        selected = [record for record in records if record[field] == value]
        result[value] = {
            "event_count": sum(record["event_count"] for record in selected),
            "tokens": _report(_sum(record["vector"] for record in selected)),
        }
    return result


def _summarize(records: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    parent = _select(records, scope="parent")
    children = _select(records, scope="child")
    system = _sum((parent, children))
    supervision = _select(records, scope="parent", kind="supervision")
    effective_supervision = _select(
        records, scope="parent", kind="supervision", assessment="effective"
    )
    inefficient_supervision = _select(
        records, scope="parent", kind="supervision", assessment="inefficient"
    )
    mixed_supervision = _select(
        records, scope="parent", kind="supervision", assessment="mixed"
    )
    inefficient_parent = _select(records, scope="parent", assessment="inefficient")
    effective_system = _subtract(system, inefficient_parent)
    parent_effective = _subtract(parent, inefficient_parent)

    totals = {
        "parent_total": parent,
        "children_total": children,
        "system_total": system,
        "supervision": supervision,
        "effective_supervision": effective_supervision,
        "inefficient_supervision": inefficient_supervision,
        "mixed_supervision": mixed_supervision,
        "inefficient_parent": inefficient_parent,
        "effective_system": effective_system,
    }
    return {
        "schema": SUMMARY_SCHEMA,
        "agent": records[0]["agent"],
        "batch": records[0]["batch"],
        "cutoff": records[0]["cutoff"],
        "root_count": len({record["root"] for record in records}),
        "sample_count": len(records),
        "breakdown": {
            field: _breakdown(records, field)
            for field in ("scope", "kind", "assessment", "behavior")
        },
        "tokens": {name: _report(vector) for name, vector in totals.items()},
        "metrics": {
            "parent_inefficiency_rate": _ratio(_total(inefficient_parent), _total(parent)),
            "system_inefficiency_rate": _ratio(_total(inefficient_parent), _total(system)),
            "parent_token_efficiency": _ratio(_total(parent_effective), _total(parent)),
            "token_efficiency": _ratio(_total(effective_system), _total(system)),
            "supervision_effective_rate": _ratio(_total(effective_supervision), _total(supervision)),
            "supervision_inefficient_rate": _ratio(_total(inefficient_supervision), _total(supervision)),
            "effective_to_inefficient_ratio": _ratio(_total(effective_system), _total(inefficient_parent)),
            "delegation_leverage": _ratio(_total(children), _total(supervision)),
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
    parser = argparse.ArgumentParser(description="Aggregate normalized Token observations.")
    parser.add_argument("--input", nargs="+", required=True)
    parser.add_argument("--output", default="-")
    args = parser.parse_args(argv)
    try:
        _write(_summarize(_read([Path(value) for value in args.input])), args.output)
        return 0
    except (OSError, SummaryError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
