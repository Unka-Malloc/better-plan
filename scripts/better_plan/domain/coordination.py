"""Pure multi-plan coordination policy and readiness evaluation.

Source plans keep their own lifecycle and receipts.  This module only adds
cross-plan execution gates, authorization checks, and a bounded dispatch batch.
"""

from __future__ import annotations

from collections import deque
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple
import fnmatch
import hashlib
import re

from .models import (
    OPAQUE_EVENT_ID_PATTERN,
    SHA256_PATTERN,
    ToolError,
    canonical_json_bytes,
    is_relative_workspace_path,
    normalize_workspace_path,
    public_summary,
)


COORDINATION_SCHEMA = "better-plan.coordination/v1"
EVALUATION_SCHEMA = "better-plan.coordination-evaluation/v1"
LANE_KINDS = frozenset({"mainline", "collaboration"})
HOST_ROLES = frozenset({"worker-standard", "worker-complex", "frontend-worker"})
UNIT_STATES = frozenset(
    {
        "pending",
        "running",
        "awaiting_acceptance",
        "completed",
        "blocked",
        "unknown",
        "correction",
    }
)
OCCUPYING_STATES = frozenset(
    {"running", "awaiting_acceptance", "unknown", "correction"}
)
SLUG_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62})$")
RESOURCE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}$")
GLOB_CHARS = frozenset("*?[")


def _fail(message: str) -> None:
    raise ToolError(message)


def _object(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail("%s must be an object" % field)
    return value


def _exact_fields(
    value: Mapping[str, Any], field: str, required: Set[str], optional: Set[str] = frozenset()
) -> None:
    keys = set(value)
    if not required <= keys:
        _fail("%s is missing required fields" % field)
    if keys - required - optional:
        _fail("%s contains unsupported fields" % field)


def _safe_identifier(
    value: Any, field: str, *, slug: bool = False, unavailable: bool = False
) -> str:
    if not isinstance(value, str):
        _fail("%s must be a string" % field)
    text = public_summary(value, field)
    pattern = SLUG_PATTERN if slug else OPAQUE_EVENT_ID_PATTERN
    if unavailable and text.endswith("/<unavailable>"):
        prefix = text[: -len("/<unavailable>")]
        if OPAQUE_EVENT_ID_PATTERN.fullmatch(prefix) is not None:
            return text
    if pattern.fullmatch(text) is None:
        _fail("%s has an invalid identifier" % field)
    return text


def _relative(value: Any, field: str, *, json_file: bool = False) -> str:
    if not is_relative_workspace_path(value):
        _fail("%s must be a workspace-relative path" % field)
    text = normalize_workspace_path(str(value))
    if json_file and not text.casefold().endswith(".json"):
        _fail("%s must name a JSON file" % field)
    return text


def _safe_value(value: Any, field: str) -> None:
    """Validate persisted display metadata without reflecting rejected content."""

    if value is None or isinstance(value, (bool, int, float)):
        return
    if isinstance(value, str):
        public_summary(value, field)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _safe_value(item, "%s[%d]" % (field, index))
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str) or not key or len(key) > 128:
                _fail("%s contains an invalid field name" % field)
            _safe_value(item, "%s.%s" % (field, key))
        return
    _fail("%s contains an unsupported value" % field)


def validate_config(config: Mapping[str, Any]) -> Mapping[str, Any]:
    """Validate one immutable coordination policy and return it unchanged."""

    value = _object(config, "coordination")
    _exact_fields(
        value,
        "coordination",
        {"schema", "namespace", "portfolio", "max_parallel", "lanes", "requires"},
        {"host", "constraints"},
    )
    if value.get("schema") != COORDINATION_SCHEMA:
        _fail("coordination.schema has an unsupported generation")
    _safe_identifier(value.get("namespace"), "coordination.namespace", slug=True)
    _relative(value.get("portfolio"), "coordination.portfolio", json_file=True)
    constraints = value.get("constraints", [])
    if not isinstance(constraints, list):
        _fail("coordination.constraints must be an array")
    for constraint in constraints:
        public_summary(constraint, "coordination constraint")
    maximum = value.get("max_parallel")
    if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum <= 0:
        _fail("coordination.max_parallel must be a positive integer")
    host = value.get("host")
    host_lane_roles: Mapping[str, Any] = {}
    if host is not None:
        host_value = _object(host, "coordination.host")
        _exact_fields(
            host_value, "coordination.host", {"kind", "command", "profiles"}, {"lanes"}
        )
        if host_value.get("kind") != "command":
            _fail("coordination.host.kind is unsupported")
        command = host_value.get("command")
        if not isinstance(command, list) or not command:
            _fail("coordination.host.command must be a non-empty argument array")
        for argument in command:
            if not isinstance(argument, str) or not argument.strip():
                _fail("coordination.host.command arguments must be non-empty strings")
            public_summary(argument, "coordination.host.command argument")
        profiles = host_value.get("profiles")
        if not isinstance(profiles, Mapping) or not profiles:
            _fail("coordination.host.profiles must configure at least one role")
        if set(profiles) - HOST_ROLES:
            _fail("coordination.host.profiles contains an unsupported role")
        for role, profile in profiles.items():
            _safe_identifier(profile, "coordination.host.profiles.%s" % role)
        host_lane_roles = host_value.get("lanes", {})
        if not isinstance(host_lane_roles, Mapping):
            _fail("coordination.host.lanes must be an object")
        for lane_id, role in host_lane_roles.items():
            _safe_identifier(lane_id, "coordination.host.lanes lane", slug=True)
            if role not in HOST_ROLES:
                _fail("coordination.host.lanes contains an unsupported role")
            if role not in profiles:
                _fail("coordination.host.lanes role has no configured profile")
    lanes = value.get("lanes")
    if not isinstance(lanes, list) or not lanes:
        _fail("coordination.lanes must be a non-empty array")
    lane_ids: Set[str] = set()
    sources: Set[str] = set()
    mainlines: Set[str] = set()
    for index, raw in enumerate(lanes):
        field = "coordination.lanes[%d]" % index
        lane = _object(raw, field)
        _exact_fields(lane, field, {"id", "kind", "repository", "source"})
        lane_id = _safe_identifier(lane.get("id"), field + ".id", slug=True)
        source = _safe_identifier(lane.get("source"), field + ".source")
        repository = _relative(lane.get("repository"), field + ".repository")
        if lane.get("kind") not in LANE_KINDS:
            _fail(field + ".kind is unsupported")
        if lane_id in lane_ids:
            _fail("coordination.lanes contains a duplicate id")
        if source in sources:
            _fail("coordination.lanes contains more than one lane for a source")
        lane_ids.add(lane_id)
        sources.add(source)
        if lane.get("kind") == "mainline":
            if repository.casefold() in mainlines:
                _fail("coordination.lanes contains more than one mainline for a repository")
            mainlines.add(repository.casefold())
    if set(host_lane_roles) - lane_ids:
        _fail("coordination.host.lanes references an unknown lane")

    requirements = value.get("requires")
    if not isinstance(requirements, list):
        _fail("coordination.requires must be an array")
    pairs: Set[Tuple[str, str]] = set()
    for index, raw in enumerate(requirements):
        field = "coordination.requires[%d]" % index
        requirement = _object(raw, field)
        _exact_fields(
            requirement, field, {"consumer", "provider", "binding"}, {"materialized"}
        )
        consumer = _safe_identifier(requirement.get("consumer"), field + ".consumer")
        provider = _safe_identifier(requirement.get("provider"), field + ".provider")
        if consumer == provider:
            _fail(field + " cannot require itself")
        binding = requirement.get("binding")
        if not isinstance(binding, str) or not binding.strip():
            _fail(field + ".binding must be a non-empty exact binding")
        public_summary(binding, field + ".binding")
        pair = (consumer, provider)
        if pair in pairs:
            _fail("coordination.requires contains a duplicate gate")
        pairs.add(pair)
        materialized = requirement.get("materialized", [])
        if not isinstance(materialized, list):
            _fail(field + ".materialized must be an array")
        paths: Set[str] = set()
        for item_index, raw_item in enumerate(materialized):
            item_field = "%s.materialized[%d]" % (field, item_index)
            item = _object(raw_item, item_field)
            _exact_fields(item, item_field, {"path", "sha256"})
            path = _relative(item.get("path"), item_field + ".path")
            digest = item.get("sha256")
            if not isinstance(digest, str) or SHA256_PATTERN.fullmatch(digest) is None:
                _fail(item_field + ".sha256 must be a lowercase SHA-256 digest")
            if path in paths:
                _fail(field + ".materialized contains a duplicate path")
            paths.add(path)
    return config


def policy_binding(config: Mapping[str, Any]) -> str:
    """Bind one grant policy to the exact validated coordination document."""

    validate_config(config)
    return hashlib.sha256(canonical_json_bytes(config)).hexdigest()


def _within(root: Path, relative: str, field: str) -> Path:
    base = root.resolve()
    candidate = (base / relative).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        _fail("%s escapes the workspace" % field)
    return candidate


def _fixed_prefix(scope: str) -> str:
    parts = normalize_workspace_path(scope).rstrip("/").split("/")
    fixed: List[str] = []
    for part in parts:
        if any(char in part for char in GLOB_CHARS):
            break
        fixed.append(part)
    return "/".join(fixed)


def _component_prefix(left: str, right: str) -> bool:
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def _scopes_overlap(left: str, right: str) -> bool:
    """Conservative path/glob collision detection for dispatch exclusion."""

    a = normalize_workspace_path(left).rstrip("/")
    b = normalize_workspace_path(right).rstrip("/")
    if not any(char in a for char in GLOB_CHARS) and not any(
        char in b for char in GLOB_CHARS
    ):
        return _component_prefix(a.casefold(), b.casefold())
    if fnmatch.fnmatchcase(a.casefold(), b.casefold()) or fnmatch.fnmatchcase(
        b.casefold(), a.casefold()
    ):
        return True
    prefix_a = _fixed_prefix(a).casefold()
    prefix_b = _fixed_prefix(b).casefold()
    return not prefix_a or not prefix_b or _component_prefix(prefix_a, prefix_b)


def _conflict(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    if set(left["resources"]) & set(right["resources"]):
        return True
    return any(
        _scopes_overlap(a, b) for a in left["writes"] for b in right["writes"]
    )


def _materialized(root: Path, requirement: Mapping[str, Any], index: int) -> bool:
    for item_index, item in enumerate(requirement.get("materialized", [])):
        field = "coordination.requires[%d].materialized[%d].path" % (index, item_index)
        path = _within(root, item["path"], field)
        if not path.is_file():
            return False
        try:
            digest_builder = hashlib.sha256()
            with path.open("rb") as handle:
                while True:
                    chunk = handle.read(1024 * 1024)
                    if not chunk:
                        break
                    digest_builder.update(chunk)
            digest = digest_builder.hexdigest()
        except OSError:
            return False
        if digest != item["sha256"]:
            return False
    return True


def _topology(
    units: Mapping[str, Mapping[str, Any]], requirements: List[Mapping[str, Any]]
) -> None:
    children: Dict[str, List[str]] = {key: [] for key in units}
    indegree: Dict[str, int] = {key: 0 for key in units}
    edges: Set[Tuple[str, str]] = set()
    for key, unit in units.items():
        for parent in unit["parents"]:
            edge = (parent, key)
            if edge not in edges:
                edges.add(edge)
                children[parent].append(key)
                indegree[key] += 1
    for requirement in requirements:
        edge = (requirement["provider"], requirement["consumer"])
        if edge[0] not in units or edge[1] not in units:
            continue
        if edge not in edges:
            edges.add(edge)
            children[edge[0]].append(edge[1])
            indegree[edge[1]] += 1
    ready = deque(key for key, degree in indegree.items() if degree == 0)
    visited = 0
    while ready:
        key = ready.popleft()
        visited += 1
        for child in children[key]:
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
    if visited != len(units):
        _fail("coordination graph contains a dependency cycle")


def _validate_units(
    config: Mapping[str, Any], units: Mapping[str, Any]
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Mapping[str, Any]]]:
    if not isinstance(units, Mapping):
        _fail("units must be an object")
    lane_by_source = {lane["source"]: lane for lane in config["lanes"]}
    normalized: Dict[str, Dict[str, Any]] = {}
    for map_key, raw in units.items():
        key = _safe_identifier(map_key, "units key", unavailable=True)
        field = "units[%s]" % key
        unit = _object(raw, field)
        _exact_fields(
            unit,
            field,
            {"key", "source", "binding", "state", "authorized", "parents", "writes", "resources", "brief"},
        )
        if unit.get("key") != key:
            _fail(field + ".key must match its map identity")
        source = _safe_identifier(unit.get("source"), field + ".source")
        if source not in lane_by_source:
            _fail(field + ".source has no configured lane")
        binding = unit.get("binding")
        if not isinstance(binding, str) or not binding.strip():
            _fail(field + ".binding must be a non-empty source binding")
        public_summary(binding, field + ".binding")
        if unit.get("state") not in UNIT_STATES:
            _fail(field + ".state is unsupported")
        if not isinstance(unit.get("authorized"), bool):
            _fail(field + ".authorized must be a boolean")
        parents = unit.get("parents")
        writes = unit.get("writes")
        resources = unit.get("resources")
        if not isinstance(parents, list) or not isinstance(writes, list) or not isinstance(resources, list):
            _fail(field + " dependency and occupancy fields must be arrays")
        clean_parents = [_safe_identifier(parent, field + ".parents") for parent in parents]
        if len(clean_parents) != len(set(clean_parents)) or key in clean_parents:
            _fail(field + ".parents contains an invalid dependency")
        clean_writes = [_relative(path, field + ".writes") for path in writes]
        if len(clean_writes) != len(set(clean_writes)):
            _fail(field + ".writes contains a duplicate scope")
        clean_resources: List[str] = []
        for resource in resources:
            if not isinstance(resource, str) or RESOURCE_PATTERN.fullmatch(resource) is None:
                _fail(field + ".resources contains an invalid identifier")
            public_summary(resource, field + ".resources")
            clean_resources.append(resource)
        if len(clean_resources) != len(set(clean_resources)):
            _fail(field + ".resources contains a duplicate identifier")
        brief = unit.get("brief")
        if not isinstance(brief, Mapping):
            _fail(field + ".brief must be an object")
        _safe_value(brief, field + ".brief")
        normalized[key] = {
            "key": key,
            "source": source,
            "binding": binding.strip(),
            "state": unit["state"],
            "authorized": unit["authorized"],
            "parents": clean_parents,
            "writes": clean_writes,
            "resources": clean_resources,
            "brief": deepcopy(dict(brief)),
        }
    for key, unit in normalized.items():
        for parent in unit["parents"]:
            if parent not in normalized:
                _fail("units contains an unknown dependency")
            if normalized[parent]["source"] != unit["source"]:
                _fail("cross-source dependencies must use coordination.requires")
    return normalized, lane_by_source


def evaluate(
    config: Mapping[str, Any],
    units: Mapping[str, Any],
    root: Path,
    grants: Mapping[str, str],
    active: Set[str],
    source_errors: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Evaluate one recoverable, bounded dispatch frontier without mutation."""

    validate_config(config)
    if not isinstance(root, Path):
        root = Path(root)
    if not isinstance(grants, Mapping) or not isinstance(active, set):
        _fail("grants and active dispatches have invalid containers")
    if source_errors is None:
        source_errors = {}
    if not isinstance(source_errors, Mapping):
        _fail("source_errors must be an object")
    normalized, lane_by_source = _validate_units(config, units)
    configured_sources = set(lane_by_source)
    for source, error in source_errors.items():
        if source not in configured_sources:
            _fail("source_errors contains an unknown source")
        public_summary(error, "source_errors.%s" % source)
    for key in normalized:
        if key.endswith("/<unavailable>"):
            source = key[: -len("/<unavailable>")]
            if source not in source_errors or normalized[key]["source"] != source:
                _fail("an unavailable source sentinel lacks a matching source error")
    for key, binding in grants.items():
        _safe_identifier(key, "grants key")
        if key not in normalized or not isinstance(binding, str):
            _fail("grants contains an invalid unit binding")
        public_summary(binding, "grants binding")
    for key in active:
        if key not in normalized:
            _fail("active dispatches contain an unknown unit")

    requirements = list(config["requires"])
    required_by: Dict[str, List[Tuple[int, Mapping[str, Any]]]] = {
        key: [] for key in normalized
    }

    def unavailable_source(key: str) -> Optional[str]:
        matches = [source for source in source_errors if key.startswith(source + "/")]
        return max(matches, key=len) if matches else None

    for index, requirement in enumerate(requirements):
        consumer = requirement["consumer"]
        provider = requirement["provider"]
        consumer_unavailable = consumer not in normalized and unavailable_source(consumer)
        provider_unavailable = provider not in normalized and unavailable_source(provider)
        if consumer not in normalized and not consumer_unavailable:
            _fail("coordination.requires references an unknown unit")
        if provider not in normalized and not provider_unavailable:
            _fail("coordination.requires references an unknown unit")
        if consumer_unavailable:
            continue
        # Retain a provider-missing requirement for external_ok.  Its known
        # source error means unavailable, not a misspelled execution owner.
        if provider in normalized and normalized[consumer]["source"] == normalized[provider]["source"]:
            _fail("coordination.requires must connect different sources")
        required_by[consumer].append((index, requirement))
    _topology(normalized, requirements)

    # Resolve every configured path now, including paths whose provider is not
    # complete, so a symlink escape can never hide behind transient state.
    _within(root, config["portfolio"], "coordination.portfolio")
    for index, lane in enumerate(config["lanes"]):
        _within(root, lane["repository"], "coordination.lanes[%d].repository" % index)
    for index, requirement in enumerate(requirements):
        for item_index, item in enumerate(requirement.get("materialized", [])):
            _within(
                root,
                item["path"],
                "coordination.requires[%d].materialized[%d].path" % (index, item_index),
            )

    occupied_keys = set(active) | {
        key
        for key, unit in normalized.items()
        if unit["state"] in OCCUPYING_STATES
        # A whole-source sentinel is not a dispatched execution owner and has
        # no declared occupancy.  It must not consume capacity from unrelated
        # healthy lanes.
        and not (unit["state"] == "unknown" and key.endswith("/<unavailable>"))
    }
    occupied = [normalized[key] for key in sorted(occupied_keys)]

    def external_ok(key: str) -> bool:
        for index, requirement in required_by[key]:
            provider = normalized.get(requirement["provider"])
            if provider is None:
                return False
            if (
                provider["state"] != "completed"
                or provider["binding"] != requirement["binding"]
                or not _materialized(root, requirement, index)
            ):
                return False
        return True

    def source_ready(unit: Mapping[str, Any]) -> bool:
        return all(normalized[parent]["state"] == "completed" for parent in unit["parents"])

    projections: Dict[str, Dict[str, Any]] = {}
    ready: List[str] = []
    lane_order = {
        lane["source"]: (lane["source"], lane["id"]) for lane in config["lanes"]
    }
    ordered_keys = sorted(normalized, key=lambda key: lane_order[normalized[key]["source"]] + (key,))
    for key in ordered_keys:
        unit = normalized[key]
        state = unit["state"]
        reason = "source state is pending"
        if state == "completed":
            readiness, reason = "accepted", "source accepted the unit"
        elif state == "blocked":
            readiness, reason = "blocked", "source reports a hard blocker"
        elif state == "unknown":
            readiness, reason = "unknown", "source progress is unavailable"
        elif key in active:
            readiness, reason = "running", "dispatcher has an active receipt"
        elif state in {"running", "correction"}:
            readiness, reason = "running", "source reports active execution"
        elif state == "awaiting_acceptance":
            readiness, reason = "awaiting_acceptance", "source is awaiting acceptance"
        else:
            readiness = "ready"

        checks_gates = (
            state in {"pending", "running", "correction", "awaiting_acceptance"}
            or key in active
        )
        dependency_ready = source_ready(unit) if checks_gates else True
        external_ready = external_ok(key) if checks_gates and dependency_ready else not checks_gates
        gates_valid = dependency_ready and external_ready
        if (state in {"running", "correction", "awaiting_acceptance"} or key in active) and not gates_valid:
            readiness, reason = "needs_review", "an active unit has an invalidated prerequisite"
        elif state == "pending" and key not in active:
            if not dependency_ready:
                readiness, reason = "waiting_dependency", "a source-owned dependency is unfinished"
            elif not external_ready:
                readiness, reason = "waiting_external", "an external accepted binding is unavailable"
            elif not unit["authorized"] or grants.get(key) != unit["binding"]:
                readiness, reason = "unauthorized", "an exact execution grant is unavailable"
            elif any(_conflict(unit, holder) for holder in occupied if holder["key"] != key):
                readiness, reason = "waiting_resource", "an active unit holds an overlapping scope"
            else:
                readiness, reason = "ready", "authorized prerequisites and resources are available"
                ready.append(key)

        lane = lane_by_source[unit["source"]]
        projections[key] = {
            "key": key,
            "lane": lane["id"],
            "source": unit["source"],
            "binding": unit["binding"],
            "state": state,
            "readiness": readiness,
            "reason": reason,
            "authorized": unit["authorized"],
            "parents": list(unit["parents"]),
            "writes": list(unit["writes"]),
            "resources": list(unit["resources"]),
            "brief": deepcopy(unit["brief"]),
        }

    dispatch_enabled = config.get("host") is not None
    capacity = max(0, config["max_parallel"] - len(occupied_keys)) if dispatch_enabled else 0
    batch: List[str] = []
    chosen: List[Mapping[str, Any]] = []
    for key in ready:
        unit = normalized[key]
        if len(batch) >= capacity:
            break
        if any(_conflict(unit, other) for other in chosen):
            continue
        batch.append(key)
        chosen.append(unit)
    waiting = [
        key
        for key in ordered_keys
        if normalized[key]["state"] == "pending" and key not in batch and key not in active
    ]
    return {
        "schema": EVALUATION_SCHEMA,
        "namespace": config["namespace"],
        "policy_binding": policy_binding(config),
        "dispatch_enabled": dispatch_enabled,
        "units": [projections[key] for key in ordered_keys],
        "ready": ready,
        "batch": batch,
        "waiting": waiting,
    }
