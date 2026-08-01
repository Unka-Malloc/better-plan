"""Durable progressive-disclosure capability facts for Better Plan."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence
import re

from .models import (
    CAPABILITIES_NAME,
    EXTERNAL_SOURCE_PATTERN,
    Issue,
    ToolError,
    WORKFLOW_STATE_MACHINE,
    is_relative_workspace_path,
    normalize_workspace_path,
    safe_summary_issue,
)


CAPABILITY_REQUIRED_FIELDS = {
    "key",
    "parent",
    "title",
    "kind",
    "basis",
    "disclosure",
    "touch",
    "source_files",
    "description",
}

CAPABILITY_OPTIONAL_FIELDS: set[str] = set()

VALID_CAPABILITY_KINDS = {
    "repository",
    "domain",
    "module",
    "component",
    "service",
    "interface",
    "feature",
    "capability",
}

VALID_CAPABILITY_BASES = {"observed", "designed"}
VALID_CAPABILITY_DISCLOSURES = {"known", "examined"}
VALID_CAPABILITY_TOUCHES = {"untouched", "in_scope", "modified"}

_DISCLOSURE_RANK = {"known": 0, "examined": 1}
_TOUCH_RANK = {"untouched": 0, "in_scope": 1, "modified": 2}
_KEY_SEGMENT = r"[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?"
CAPABILITY_KEY_PATTERN = re.compile(rf"^{_KEY_SEGMENT}(?:/{_KEY_SEGMENT})*$")
MAX_CAPABILITY_KEY_CHARS = 255


def is_capability_key(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) <= MAX_CAPABILITY_KEY_CHARS
        and CAPABILITY_KEY_PATTERN.fullmatch(value) is not None
    )


def normalize_capability_key(value: str) -> str:
    normalized = value.strip().replace("\\", "/").strip("/").casefold()
    if not is_capability_key(normalized):
        raise ToolError(
            "capability key must be a lowercase slash path of letters, digits, dots, underscores, or hyphens"
        )
    return normalized


def immediate_parent_key(key: str) -> str | None:
    if "/" not in key:
        return None
    return key.rsplit("/", 1)[0]


def capability_index(entries: Sequence[Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(entry["key"]): entry
        for entry in entries
        if isinstance(entry, Mapping) and is_capability_key(entry.get("key"))
    }


def validate_capability_data(path: Path, data: list[Any]) -> tuple[int, list[Issue]]:
    """Validate the orthogonal capability fact tree without lifecycle semantics."""

    issues: list[Issue] = []
    if path.name != CAPABILITIES_NAME:
        issues.append(Issue(path, f"capability catalog must be named {CAPABILITIES_NAME}"))
    if not data:
        issues.append(Issue(path, "capability catalog must contain one repository root"))
        return 0, issues

    keys: dict[str, int] = {}
    sibling_titles: dict[tuple[str | None, str], int] = {}
    root_indexes: list[int] = []

    for index, entry in enumerate(data):
        prefix = f"capability[{index}]"
        if not isinstance(entry, dict):
            issues.append(Issue(path, f"{prefix}: must be an object"))
            continue

        for field in sorted(CAPABILITY_REQUIRED_FIELDS - set(entry)):
            issues.append(Issue(path, f"{prefix}.{field}: missing required field"))
        for field in sorted(set(entry) - CAPABILITY_REQUIRED_FIELDS - CAPABILITY_OPTIONAL_FIELDS):
            issues.append(Issue(path, f"{prefix}.{field}: unknown field"))

        key = entry.get("key")
        if not is_capability_key(key):
            issues.append(
                Issue(
                    path,
                    f"{prefix}.key: must be a lowercase slash path no longer than {MAX_CAPABILITY_KEY_CHARS} characters",
                )
            )
        elif str(key) in keys:
            issues.append(Issue(path, f"{prefix}.key: duplicate key {key!r}"))
        else:
            keys[str(key)] = index

        parent = entry.get("parent")
        if parent is None:
            root_indexes.append(index)
        elif not is_capability_key(parent):
            issues.append(Issue(path, f"{prefix}.parent: must be null or a valid capability key"))

        for field in ("title", "description"):
            summary_issue = safe_summary_issue(entry.get(field))
            if summary_issue is not None:
                issues.append(Issue(path, f"{prefix}.{field}: {summary_issue}"))

        title = entry.get("title")
        if isinstance(title, str) and title.strip():
            title_identity = (str(parent) if parent is not None else None, title.strip().casefold())
            previous = sibling_titles.get(title_identity)
            if previous is not None:
                issues.append(
                    Issue(
                        path,
                        f"{prefix}.title: duplicates sibling capability[{previous}] title; reuse its stable key",
                    )
                )
            else:
                sibling_titles[title_identity] = index

        kind = entry.get("kind")
        if kind not in VALID_CAPABILITY_KINDS:
            issues.append(Issue(path, f"{prefix}.kind: must be one of {', '.join(sorted(VALID_CAPABILITY_KINDS))}"))
        basis = entry.get("basis")
        if basis not in VALID_CAPABILITY_BASES:
            issues.append(Issue(path, f"{prefix}.basis: must be observed or designed"))
        disclosure = entry.get("disclosure")
        if disclosure not in VALID_CAPABILITY_DISCLOSURES:
            issues.append(Issue(path, f"{prefix}.disclosure: must be known or examined"))
        touch = entry.get("touch")
        if touch not in VALID_CAPABILITY_TOUCHES:
            issues.append(Issue(path, f"{prefix}.touch: must be untouched, in_scope, or modified"))
        if disclosure == "known" and touch != "untouched":
            issues.append(Issue(path, f"{prefix}: known capabilities must remain untouched until examined"))
        if touch in {"in_scope", "modified"} and disclosure != "examined":
            issues.append(Issue(path, f"{prefix}: touched capabilities must be examined"))

        source_files = entry.get("source_files")
        if not isinstance(source_files, list) or not all(isinstance(value, str) for value in source_files):
            issues.append(Issue(path, f"{prefix}.source_files: must be an array of strings"))
        else:
            normalized_sources: set[str] = set()
            for source_index, source in enumerate(source_files):
                value = source.strip()
                if not value:
                    issues.append(Issue(path, f"{prefix}.source_files[{source_index}]: must not be empty"))
                    continue
                identity = value.replace("\\", "/")
                if identity in normalized_sources:
                    issues.append(Issue(path, f"{prefix}.source_files[{source_index}]: duplicate source reference"))
                normalized_sources.add(identity)
                if "://" in value or EXTERNAL_SOURCE_PATTERN.match(value):
                    continue
                if not is_relative_workspace_path(value):
                    issues.append(
                        Issue(
                            path,
                            f"{prefix}.source_files[{source_index}]: local sources must be repository-relative",
                        )
                    )

    if len(root_indexes) != 1:
        issues.append(Issue(path, "capability catalog must contain exactly one parentless repository root"))

    for index, entry in enumerate(data):
        if not isinstance(entry, dict):
            continue
        key = entry.get("key")
        parent = entry.get("parent")
        if not is_capability_key(key):
            continue
        if parent is None:
            if entry.get("kind") != "repository":
                issues.append(Issue(path, f"capability[{index}].kind: the root must use repository"))
            if "/" in str(key):
                issues.append(Issue(path, f"capability[{index}].key: the root key must be one segment"))
            if entry.get("disclosure") != "examined":
                issues.append(Issue(path, f"capability[{index}].disclosure: the repository root must be examined"))
            continue
        if not is_capability_key(parent):
            continue
        if str(parent) not in keys:
            issues.append(Issue(path, f"capability[{index}].parent: unknown capability key {parent!r}"))
        expected_parent = immediate_parent_key(str(key))
        if parent != expected_parent:
            issues.append(
                Issue(
                    path,
                    f"capability[{index}].parent: must be immediate key parent {expected_parent!r}",
                )
            )
        parent_index = keys.get(str(parent))
        if parent_index is not None and parent_index >= index:
            issues.append(Issue(path, f"capability[{index}].parent: parent must appear before its child"))

    return len(data), issues


def make_root_capability(
    *,
    key: str,
    title: str,
    description: str,
    basis: str,
    source_files: Sequence[str],
) -> dict[str, Any]:
    return {
        "key": normalize_capability_key(key),
        "parent": None,
        "title": title.strip(),
        "kind": "repository",
        "basis": basis,
        "disclosure": "examined",
        "touch": "untouched",
        "source_files": _normalized_sources(source_files),
        "description": description.strip(),
    }


def _normalized_sources(values: Sequence[str]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        candidate = value.strip().replace("\\", "/")
        if candidate and candidate not in normalized:
            normalized.append(candidate)
    return normalized


def upsert_capability(
    entries: list[Any],
    *,
    key: str,
    parent: str,
    title: str,
    kind: str,
    basis: str,
    description: str,
    source_files: Sequence[str],
    disclosure: str,
    touch: str,
) -> tuple[list[Any], bool, bool]:
    """Create or monotonically enrich one stable-key capability fact."""

    normalized_key = normalize_capability_key(key)
    normalized_parent = normalize_capability_key(parent)
    indexed = capability_index(entries)
    if normalized_parent not in indexed:
        raise ToolError("capability parent is unknown; disclose the root-to-leaf path in order")
    if immediate_parent_key(normalized_key) != normalized_parent:
        raise ToolError("capability key must be an immediate child of --parent")
    if kind not in VALID_CAPABILITY_KINDS or kind == "repository":
        raise ToolError("non-root capability kind is invalid")
    if basis not in VALID_CAPABILITY_BASES:
        raise ToolError("capability basis must be observed or designed")
    if disclosure not in VALID_CAPABILITY_DISCLOSURES:
        raise ToolError("capability disclosure must be known or examined")
    if touch not in VALID_CAPABILITY_TOUCHES:
        raise ToolError("capability touch must be untouched, in_scope, or modified")
    if touch != "untouched":
        disclosure = "examined"

    existing = indexed.get(normalized_key)
    if existing is None:
        entry = {
            "key": normalized_key,
            "parent": normalized_parent,
            "title": title.strip(),
            "kind": kind,
            "basis": basis,
            "disclosure": disclosure,
            "touch": touch,
            "source_files": _normalized_sources(source_files),
            "description": description.strip(),
        }
        return [*entries, entry], True, True

    mutable = dict(existing)
    if mutable.get("parent") != normalized_parent:
        raise ToolError("stable capability key already belongs to a different parent")
    if mutable.get("kind") != kind:
        raise ToolError("stable capability key already has a different kind")
    if mutable.get("basis") != basis:
        raise ToolError("stable capability key already has a different observed/designed basis")

    mutable["title"] = title.strip()
    mutable["description"] = description.strip()
    mutable["source_files"] = _normalized_sources(
        [*list(mutable.get("source_files", [])), *source_files]
    )
    current_disclosure = str(mutable.get("disclosure"))
    current_touch = str(mutable.get("touch"))
    if _DISCLOSURE_RANK.get(disclosure, -1) > _DISCLOSURE_RANK.get(current_disclosure, -1):
        mutable["disclosure"] = disclosure
    if _TOUCH_RANK.get(touch, -1) > _TOUCH_RANK.get(current_touch, -1):
        mutable["touch"] = touch
        mutable["disclosure"] = "examined"

    changed = mutable != existing
    updated = [mutable if entry is existing else entry for entry in entries]
    return updated, False, changed


def promote_capability(entries: list[Any], key: str, touch: str) -> tuple[list[Any], bool]:
    normalized_key = normalize_capability_key(key)
    if touch not in {"in_scope", "modified"}:
        raise ToolError("promotion touch must be in_scope or modified")
    indexed = capability_index(entries)
    existing = indexed.get(normalized_key)
    if existing is None:
        raise ToolError("capability key is unknown; disclose it before promotion")
    mutable = dict(existing)
    mutable["disclosure"] = "examined"
    if _TOUCH_RANK[touch] > _TOUCH_RANK.get(str(mutable.get("touch")), -1):
        mutable["touch"] = touch
    changed = mutable != existing
    return [mutable if entry is existing else entry for entry in entries], changed


def capability_scope(entries: Sequence[Any], target_key: str) -> dict[str, Any] | None:
    """Return the examined target path and touched descendants, never untouched siblings."""

    indexed = capability_index(entries)
    target = indexed.get(target_key)
    if target is None:
        return None

    path_keys: list[str] = []
    cursor: Mapping[str, Any] | None = target
    while cursor is not None:
        key = str(cursor.get("key"))
        path_keys.append(key)
        parent = cursor.get("parent")
        cursor = indexed.get(str(parent)) if parent is not None else None
    path_keys.reverse()

    prefix = f"{target_key}/"
    touched_descendants = [
        entry
        for entry in entries
        if isinstance(entry, Mapping)
        and str(entry.get("key", "")).startswith(prefix)
        and entry.get("disclosure") == "examined"
        and entry.get("touch") != "untouched"
    ]
    omitted = sum(
        1
        for entry in entries
        if isinstance(entry, Mapping)
        and str(entry.get("key", "")).startswith(prefix)
        and entry.get("disclosure") == "known"
        and entry.get("touch") == "untouched"
    )

    def public_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "key": entry.get("key"),
            "title": entry.get("title"),
            "kind": entry.get("kind"),
            "basis": entry.get("basis"),
            "disclosure": entry.get("disclosure"),
            "touch": entry.get("touch"),
            "source_files": list(entry.get("source_files", [])),
        }

    return {
        "target_key": target_key,
        "path": [public_entry(indexed[key]) for key in path_keys],
        "touched_descendants": [public_entry(entry) for entry in touched_descendants],
        "known_untouched_descendants_omitted": omitted,
    }


def plan_capability_binding_issues(
    manifest_path: Path,
    plans: Sequence[Any],
    entries: Sequence[Any] | None,
) -> list[Issue]:
    """Keep active delivery unique and bound only to disclosed, touched facts."""

    if entries is None:
        return [
            Issue(
                manifest_path,
                f"plan[{index}].capability_key: {CAPABILITIES_NAME} is required when a Plan binds a capability",
            )
            for index, plan in enumerate(plans)
            if isinstance(plan, Mapping) and "capability_key" in plan
        ]

    indexed = capability_index(entries)
    issues: list[Issue] = []
    active_owner: dict[str, int] = {}
    for index, plan in enumerate(plans):
        if not isinstance(plan, Mapping):
            continue
        kind = plan.get("kind")
        status = plan.get("status")
        key = plan.get("capability_key")
        nonterminal_group = kind == "group" and status not in WORKFLOW_STATE_MACHINE.terminal_statuses
        if key is None:
            if nonterminal_group:
                issues.append(
                    Issue(
                        manifest_path,
                        f"plan[{index}].capability_key: active task groups must bind one examined in-scope capability",
                    )
                )
            continue
        if not is_capability_key(key):
            continue
        entry = indexed.get(str(key))
        if entry is None:
            issues.append(Issue(manifest_path, f"plan[{index}].capability_key: unknown capability {key!r}"))
            continue
        if kind == "group" and (
            entry.get("disclosure") != "examined"
            or entry.get("touch") not in {"in_scope", "modified"}
        ):
            issues.append(
                Issue(
                    manifest_path,
                    f"plan[{index}].capability_key: task groups may bind only examined in_scope or modified capabilities",
                )
            )
        if not nonterminal_group:
            continue
        previous = active_owner.get(str(key))
        if previous is not None:
            issues.append(
                Issue(
                    manifest_path,
                    f"plan[{index}].capability_key: duplicates active plan[{previous}] for {key!r}; reuse or extend the existing Plan",
                )
            )
        else:
            active_owner[str(key)] = index
    return issues


def render_capability_tree(entries: Sequence[Any], *, details: bool = False) -> str:
    indexed = capability_index(entries)
    children: dict[str | None, list[str]] = {}
    for entry in entries:
        if not isinstance(entry, Mapping) or not is_capability_key(entry.get("key")):
            continue
        parent = entry.get("parent")
        children.setdefault(str(parent) if parent is not None else None, []).append(str(entry["key"]))

    lines = ["🧭 Capability Facts (unknown capabilities are intentionally absent)"]
    roots = children.get(None, [])
    stack: list[tuple[str, str, bool]] = [
        (key, "", index == len(roots) - 1)
        for index, key in reversed(list(enumerate(roots)))
    ]
    while stack:
        key, prefix, is_last = stack.pop()
        entry = indexed[key]
        branch = "\\-- " if is_last else "+-- "
        lines.append(
            f"{prefix}{branch}{entry.get('title')} [{entry.get('disclosure')}/{entry.get('touch')}; {entry.get('basis')}] <{key}>"
        )
        extension = "    " if is_last else "|   "
        if details:
            lines.append(f"{prefix}{extension}description: {entry.get('description')}")
            sources = entry.get("source_files")
            source_labels = [
                (
                    "<external reference>"
                    if "://" in source or EXTERNAL_SOURCE_PATTERN.match(source)
                    else normalize_workspace_path(source)
                )
                if isinstance(source, str)
                else "<invalid source>"
                for source in sources
            ] if isinstance(sources, list) else []
            lines.append(
                f"{prefix}{extension}sources: {', '.join(source_labels) if source_labels else 'none'}"
            )
        child_keys = children.get(key, [])
        for index in range(len(child_keys) - 1, -1, -1):
            stack.append((child_keys[index], f"{prefix}{extension}", index == len(child_keys) - 1))
    if not roots:
        lines.append("\\-- <invalid or empty capability catalog>")
    return "\n".join(lines)


def capability_schema_payload() -> dict[str, Any]:
    return {
        "kind": "capability",
        "file": CAPABILITIES_NAME,
        "required_fields": sorted(CAPABILITY_REQUIRED_FIELDS),
        "optional_fields": sorted(CAPABILITY_OPTIONAL_FIELDS),
        "kinds": sorted(VALID_CAPABILITY_KINDS),
        "bases": sorted(VALID_CAPABILITY_BASES),
        "disclosures": sorted(VALID_CAPABILITY_DISCLOSURES),
        "touches": sorted(VALID_CAPABILITY_TOUCHES),
        "template": {
            "key": "repository/module",
            "parent": "repository",
            "title": "Observed module",
            "kind": "module",
            "basis": "observed",
            "disclosure": "known",
            "touch": "untouched",
            "source_files": ["src/module"],
            "description": "A lightweight fact discovered while following another path.",
        },
    }
