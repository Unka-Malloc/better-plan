"""Pure interfaces for Better Plan design contracts.

The main design stage fixes this boundary before acceptance tests are authored.
Behavior is implemented only after the acceptance contract is frozen once.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from collections import OrderedDict
import hashlib
import json
from typing import Any, Final


DESIGN_REQUIRED_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "artifact",
        "owned_paths",
        "scaffold_paths",
        "acceptance_paths",
        "symbols",
        "interfaces",
        "dependencies",
        "decisions",
        "test_seams",
    }
)
SYMBOL_KINDS: Final[frozenset[str]] = frozenset(
    {"module", "function", "class", "interface", "type"}
)
SYMBOL_OPERATIONS: Final[frozenset[str]] = frozenset({"add", "modify", "remove"})
DECISION_FIELDS: Final[frozenset[str]] = frozenset(
    {"composition", "algorithms", "data_structures", "state", "isolation", "concurrency"}
)


def _canonical_overlap_tokens(path: str) -> tuple[str, ...]:
    normalized = normalize_design_path(path)
    return tuple(part.split(".", 1)[0] for part in normalized.split("/"))


def normalize_design_path(value: object) -> str:
    """Return one canonical repository-relative design path."""
    if not isinstance(value, str):
        raise ValueError("design path must be a string")
    if value != value.strip() or not value:
        raise ValueError("design path must be non-empty")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError("design path contains invalid character")
    if value.startswith(("/", "~")) or (len(value) >= 3 and value[1] == ":" and value[2] == "/"):
        raise ValueError("design path must be repository-relative")
    if "\\" in value:
        raise ValueError("design path must use / separators")

    parts = value.split("/")
    if "" in parts:
        raise ValueError("design path must not contain empty components")
    for part in parts:
        if part in {".", ".."}:
            raise ValueError("design path must not contain . or .. components")
    return value


def validate_design_contract(design: Mapping[str, object]) -> tuple[str, ...]:
    """Return deterministic field-level issues without filesystem access."""
    if not isinstance(design, Mapping):
        return ("design must be a mapping",)

    issues: list[str] = []
    keys = set(design.keys())
    for required in DESIGN_REQUIRED_FIELDS:
        if required not in keys:
            issues.append(f"required field: {required}")

    for key in sorted(keys - DESIGN_REQUIRED_FIELDS):
        issues.append(f"unexpected field: {key}")

    def _must_be_non_empty_str(
        namespace: str, value: object, field: str
    ) -> None:
        if not isinstance(value, str):
            issues.append(f"{namespace} {field}: expected non-empty string")
        elif not value.strip():
            issues.append(f"{namespace} {field}: expected non-empty string")

    def _path_sequence(namespace: str, value: object) -> list[str] | None:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            issues.append(f"{namespace}: expected sequence of repository-relative paths")
            return None
        paths: list[str] = []
        for index, raw in enumerate(value):
            if not isinstance(raw, str):
                issues.append(f"{namespace}[{index}] path must be a string")
                continue
            try:
                paths.append(normalize_design_path(raw))
            except ValueError:
                issues.append(f"{namespace}[{index}] path is invalid")
        return paths

    artifact = design.get("artifact")
    _must_be_non_empty_str("artifact", artifact, "artifact")
    if isinstance(artifact, str):
        try:
            normalize_design_path(artifact)
        except ValueError:
            issues.append("artifact is invalid")

    owned_paths = _path_sequence("owned_paths", design.get("owned_paths"))
    scaffold_paths = _path_sequence("scaffold_paths", design.get("scaffold_paths"))
    acceptance_paths = _path_sequence(
        "acceptance_paths", design.get("acceptance_paths")
    )
    if owned_paths is not None and len(owned_paths) == 0:
        issues.append("owned_paths must be non-empty")
    if scaffold_paths is not None and len(scaffold_paths) == 0:
        issues.append("scaffold_paths must be non-empty")
    if acceptance_paths is not None and len(acceptance_paths) == 0:
        issues.append("acceptance_paths must be non-empty")

    if owned_paths is not None and scaffold_paths is not None:
        owned_set = set(owned_paths)
        for path in scaffold_paths:
            if path not in owned_set:
                issues.append(f"scaffold path not owned: {path}")

    symbols = design.get("symbols")
    if not isinstance(symbols, Sequence) or isinstance(symbols, (str, bytes)):
        issues.append("symbols: expected sequence")
    else:
        for symbol in symbols:
            if not isinstance(symbol, Mapping):
                issues.append("symbol must be mapping")
                continue
            required = {"path", "kind", "name", "operation", "signature"}
            for field in required:
                if field not in symbol:
                    issues.append(f"symbol missing field: {field}")
            if "path" in symbol:
                if not isinstance(symbol["path"], str):
                    issues.append("symbol path must be string")
                else:
                    try:
                        symbol_path = normalize_design_path(symbol["path"])
                    except ValueError:
                        issues.append("symbol path is invalid")
                    else:
                        if owned_paths is not None and symbol_path not in owned_paths:
                            issues.append(
                                f"symbol path outside ownership: {symbol_path}"
                            )
            if "kind" in symbol and symbol["kind"] not in SYMBOL_KINDS:
                issues.append(f"symbol kind invalid: {symbol['kind']}")
            if "operation" in symbol and symbol["operation"] not in SYMBOL_OPERATIONS:
                issues.append(f"symbol operation invalid: {symbol['operation']}")
            _must_be_non_empty_str("symbol", symbol.get("name"), "name")
            _must_be_non_empty_str("symbol", symbol.get("signature"), "signature")

    interfaces = design.get("interfaces")
    if not isinstance(interfaces, Sequence) or isinstance(interfaces, (str, bytes)):
        issues.append("interfaces: expected sequence")
    else:
        for interface in interfaces:
            if not isinstance(interface, Mapping):
                issues.append("interface must be mapping")
                continue
            required = {"name", "producer", "consumers", "inputs", "outputs", "errors"}
            for field in required:
                if field not in interface:
                    issues.append(f"interface missing field: {field}")
            if "name" in interface:
                _must_be_non_empty_str("interface", interface.get("name"), "name")
            if "producer" in interface:
                if not isinstance(interface["producer"], str):
                    issues.append("interface producer must be string")
                else:
                    try:
                        producer = normalize_design_path(interface["producer"])
                    except ValueError:
                        issues.append("interface producer is invalid")
                    else:
                        if owned_paths is not None and producer not in owned_paths:
                            issues.append(
                                f"interface producer outside ownership: {producer}"
                            )
            if "consumers" in interface:
                if not isinstance(interface["consumers"], Sequence) or isinstance(
                    interface["consumers"], (str, bytes)
                ):
                    issues.append("interface consumers: expected sequence")
                else:
                    for consumer in interface["consumers"]:
                        if not isinstance(consumer, str):
                            issues.append("interface consumer must be string")
                            continue
                        try:
                            normalize_design_path(consumer)
                        except ValueError:
                            issues.append("interface consumer is invalid")
            if "inputs" in interface:
                _must_be_non_empty_str("interface", interface.get("inputs"), "inputs")
            if "outputs" in interface:
                _must_be_non_empty_str("interface", interface.get("outputs"), "outputs")
            if "errors" in interface:
                errors = interface["errors"]
                if not isinstance(errors, Sequence) or isinstance(errors, (str, bytes)):
                    issues.append("interface errors: expected sequence")
                else:
                    for error in errors:
                        _must_be_non_empty_str("interface error", error, "errors")

    dependencies = design.get("dependencies")
    if not isinstance(dependencies, Sequence) or isinstance(dependencies, (str, bytes)):
        issues.append("dependencies: expected sequence")
    else:
        for dependency in dependencies:
            if not isinstance(dependency, Mapping):
                issues.append("dependency must be mapping")
                continue
            for field in ("from", "to", "reason"):
                if field not in dependency:
                    issues.append(f"dependency missing field: {field}")
            if isinstance(dependency.get("from"), str):
                try:
                    normalize_design_path(dependency["from"])
                except ValueError:
                    issues.append("dependency from is invalid")
            elif "from" in dependency:
                issues.append("dependency from must be string")
            if isinstance(dependency.get("to"), str):
                try:
                    normalize_design_path(dependency["to"])
                except ValueError:
                    issues.append("dependency to is invalid")
            elif "to" in dependency:
                issues.append("dependency to must be string")
            if not isinstance(dependency.get("reason"), str) or not str(
                dependency.get("reason")
            ).strip():
                issues.append("dependency reason must be non-empty string")

    decisions = design.get("decisions")
    if not isinstance(decisions, Mapping):
        issues.append("decisions: expected mapping")
    else:
        keys = set(decisions.keys())
        for required in DECISION_FIELDS:
            if required not in keys:
                issues.append(f"decision required field: {required}")
        for extra in sorted(keys - DECISION_FIELDS):
            issues.append(f"decision unexpected field: {extra}")
        for key in DECISION_FIELDS:
            if key in decisions:
                if not isinstance(decisions[key], str) or not decisions[key].strip():
                    issues.append(f"decision {key} must be non-empty string")

    if not isinstance(design.get("test_seams"), Sequence) or isinstance(
        design.get("test_seams"), (str, bytes)
    ):
        issues.append("test_seams: expected sequence")
    else:
        for seam in design["test_seams"]:
            _must_be_non_empty_str("test seam", seam, "")

    return tuple(issues)


def canonical_design_bytes(design: Mapping[str, object]) -> bytes:
    """Encode a validated design contract deterministically."""
    issues = validate_design_contract(design)
    if issues:
        raise ValueError("invalid design contract: " + ", ".join(sorted(issues)))

    normalized_paths = {
        "owned_paths": sorted(
            {normalize_design_path(path) for path in design["owned_paths"]}
        ),
        "scaffold_paths": sorted(
            {normalize_design_path(path) for path in design["scaffold_paths"]}
        ),
        "acceptance_paths": sorted(
            {normalize_design_path(path) for path in design["acceptance_paths"]}
        ),
        "artifact": normalize_design_path(design["artifact"]),
    }

    symbols = [
        {
            "path": normalize_design_path(symbol["path"]),
            "kind": symbol["kind"],
            "name": symbol["name"],
            "operation": symbol["operation"],
            "signature": symbol["signature"],
        }
        for symbol in sorted(
            design["symbols"],
            key=lambda value: (
                value.get("path", ""),
                value.get("kind", ""),
                value.get("name", ""),
                value.get("operation", ""),
            ),
        )
    ]
    interfaces = [
        {
            "name": interface["name"],
            "producer": normalize_design_path(interface["producer"]),
            "consumers": sorted({normalize_design_path(consumer) for consumer in interface["consumers"]}),
            "inputs": interface["inputs"],
            "outputs": interface["outputs"],
            "errors": sorted(interface["errors"]),
        }
        for interface in sorted(
            design["interfaces"],
            key=lambda value: (
                value.get("producer", ""),
                value.get("name", ""),
            ),
        )
    ]
    dependencies = [
        {
            "from": normalize_design_path(dependency["from"]),
            "to": normalize_design_path(dependency["to"]),
            "reason": dependency["reason"],
        }
        for dependency in sorted(
            design["dependencies"],
            key=lambda value: (value.get("from", ""), value.get("to", "")),
        )
    ]

    normalized = OrderedDict(
        (
            ("artifact", normalized_paths["artifact"]),
            ("owned_paths", normalized_paths["owned_paths"]),
            ("scaffold_paths", normalized_paths["scaffold_paths"]),
            ("acceptance_paths", normalized_paths["acceptance_paths"]),
            ("symbols", symbols),
            ("interfaces", interfaces),
            ("dependencies", dependencies),
            ("decisions", dict(sorted((k, design["decisions"][k]) for k in DECISION_FIELDS))),
            ("test_seams", sorted({str(seam) for seam in design["test_seams"]})),
        )
    )
    return json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def design_digest(design: Mapping[str, object]) -> str:
    """Return the SHA-256 digest of canonical design bytes."""
    return hashlib.sha256(canonical_design_bytes(design)).hexdigest()


def paths_overlap(left: str, right: str) -> bool:
    """Return whether normalized paths are equal or one contains the other."""
    left_parts = _canonical_overlap_tokens(left)
    right_parts = _canonical_overlap_tokens(right)
    if left_parts == right_parts:
        return True
    if len(left_parts) < len(right_parts):
        return right_parts[: len(left_parts)] == left_parts
    if len(right_parts) < len(left_parts):
        return left_parts[: len(right_parts)] == right_parts
    return False


def independent_ownership_issues(
    nodes: Sequence[Mapping[str, Any]],
    reachable: Callable[[str, str], bool],
) -> tuple[str, ...]:
    """Return ownership collisions for Nodes not ordered by dependency."""
    items: list[tuple[str, tuple[str, ...], str]] = []
    for index, node in enumerate(nodes):
        node_id = node.get("id")
        if not isinstance(node_id, str):
            continue
        raw_paths = node.get("owned_paths", [])
        if not isinstance(raw_paths, Sequence) or isinstance(raw_paths, (str, bytes)):
            continue
        for raw in raw_paths:
            if not isinstance(raw, str):
                continue
            try:
                parts = _canonical_overlap_tokens(raw)
            except ValueError:
                continue
            items.append((node_id, parts, raw))

    items.sort(key=lambda entry: entry[1])
    issues: list[str] = []
    active_ancestors: list[tuple[str, tuple[str, ...], str]] = []
    for node_id, parts, raw in items:
        active_ancestors = [
            entry
            for entry in active_ancestors
            if len(entry[1]) <= len(parts) and parts[: len(entry[1])] == entry[1]
        ]
        for other_node_id, _, other_raw in active_ancestors:
            if node_id == other_node_id:
                continue
            if reachable(node_id, other_node_id) or reachable(other_node_id, node_id):
                continue
            issues.append(
                f"ownership collision: {other_node_id} owns {other_raw} and {node_id} owns {raw}"
            )
        active_ancestors.append((node_id, parts, raw))
    return tuple(sorted(set(issues)))
