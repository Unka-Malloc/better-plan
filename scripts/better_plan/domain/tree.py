"""Pure readable and Emoji-audit Better Plan ASCII tree rendering."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Sequence
import re

from .models import (
    GATE_LEAF_TAG,
    MILESTONE_GATE_ROLE,
    VALID_NODE_STATUS_MODES,
    VALID_PLAN_KINDS,
    VALID_TREE_MODES,
    WORKFLOW_STATE_MACHINE,
    is_gate_leaf_node,
    is_manifest_id,
    is_relative_workspace_path,
    is_string_list,
    node_has_tag,
    normalize_workspace_path,
    safe_summary_issue,
)

_STATUS_EMOJI: Mapping[str, str] = MappingProxyType(
    {
        "pending": "🟡",
        "in_progress": "🔵",
        "blocked": "⛔",
        "deferred": "⏸️",
        "completed": "✅",
        "skipped": "🚫",
    }
)

_WORKSPACE_LABEL = "🌳 Better Plan Workspace"
_PLAN_LABEL = "📋 Plan"
_ID_LABEL = "🆔 ID"
_PURPOSE_LABEL = "🎯 Purpose"
_GOAL_LABEL = "🏁 Goal"
_DESCRIPTION_LABEL = "📝 Description"
_NODE_LABEL = "🔹 Node"
_ROLE_LABEL = "🧩 Role"
_PREREQUISITE_LABEL = "🔗 Prerequisite (execution)"
_EMPTY_PREREQUISITES_LABEL = "🔓 Prerequisites (execution)"
_NAVIGATION_LABEL = "🧭 Next (navigation only)"
_STATUS_REASON_LABEL = "💬 Status reason"
_KIND_LABEL = "🏷️ Kind"
_TREE_MODE_LABEL = "🪟 Tree mode"
_NODE_STATUS_MODE_LABEL = "👁️ Node status"
_ENTRY_GATE_LABEL = "🚪 Entry gate"
_ENTRY_GATE_PREREQUISITE_LABEL = "🔗 Entry gate prerequisite"
_ENTRY_GATE_CONDITIONS_LABEL = "🚦 Entry gate conditions"
_DECISION_ISSUE_LABEL = "🗳️ User decision"
_CAPABILITY_LABEL = "🧭 Capability"
_CODE_LABEL = "🔤 Code"
_TITLE_LABEL = "🏷️ Title"
_TAGS_LABEL = "🏷️ Tags"
_CONDITIONS_LABEL = "🚦 Conditions"
_WARNING_LABEL = "⚠️"

_READABLE_HEADER = (
    "Legend: [E] eligible   [B] blocked   [D] deferred\n"
    "        [G] gate       [R] rule\n"
    "\n"
    "Lifecycle:\n"
    "DEFERRED --activate--> ELIGIBLE --dispatch--> ACTIVE --accept--> ACCEPTED"
)

_CODE_PATTERN = re.compile(r"^(.*?)(\d+)$")


@dataclass(frozen=True)
class PlanBlock:
    """One Plan label, its flat owned records, and its child Plans."""

    label: str
    owned_lines: tuple[str, ...]
    child_plans: tuple["PlanBlock", ...]


@dataclass(frozen=True)
class _OwnedNode:
    """One indexed Node together with its privacy-safe owning Plan directory."""

    owner_directory: str
    node: Mapping[str, Any]


@dataclass(frozen=True)
class ReadableBlock:
    """One source-grounded readable label and its projected descendants."""

    label: str
    children: tuple["ReadableBlock", ...] = ()
    leading_spacer: bool = False
    sibling_spacers: bool = False
    eligible_node_id: str | None = None


def _display_issue(value: Any) -> str | None:
    issue = safe_summary_issue(value)
    if issue is not None:
        return issue
    if "<-" in str(value).strip():
        return "must not contain the execution dependency marker"
    return None


def _summary(value: Any, field: str) -> str:
    issue = _display_issue(value)
    if issue is not None:
        return f"{_WARNING_LABEL} <invalid {field}: {issue}>"
    return str(value).strip()


def _summary_list(value: Any, field: str) -> str:
    if not isinstance(value, list) or not all(
        isinstance(item, str) for item in value
    ):
        return f"{_WARNING_LABEL} <invalid {field}: must be an array of strings>"
    if not value:
        return "none"
    summaries = [_summary(item, field) for item in value]
    return " + ".join(summaries)


def _identifier(value: Any) -> str:
    return (
        str(value)
        if is_manifest_id(value)
        else f"{_WARNING_LABEL} <invalid id>"
    )


def _status(value: Any) -> str:
    if not WORKFLOW_STATE_MACHINE.is_status(value):
        return f"{_WARNING_LABEL} <invalid status>"
    status = str(value)
    return f"{_STATUS_EMOJI[status]} {status}"


def _directory(value: Any) -> str:
    issue = _display_issue(value)
    if issue is not None:
        return f"{_WARNING_LABEL} <invalid directory: {issue}>"
    if not is_relative_workspace_path(value):
        return (
            f"{_WARNING_LABEL} "
            "<invalid directory: must be a relative workspace path>"
        )
    return normalize_workspace_path(str(value))


def _node_records(
    plans: Sequence[Any],
    checkpoints: Sequence[Sequence[Any] | None],
) -> dict[str, tuple[_OwnedNode, ...]]:
    buckets: dict[str, list[_OwnedNode]] = {}
    for plan_index, nodes in enumerate(checkpoints):
        if nodes is None:
            continue
        plan = plans[plan_index] if plan_index < len(plans) else None
        directory = _directory(
            plan.get("directory") if isinstance(plan, Mapping) else None
        )
        for node in nodes:
            if not isinstance(node, Mapping):
                continue
            node_id = node.get("id")
            if not is_manifest_id(node_id):
                continue
            buckets.setdefault(str(node_id), []).append(_OwnedNode(directory, node))
    return {
        node_id: tuple(owned_nodes)
        for node_id, owned_nodes in buckets.items()
    }


def _navigation_reference(
    reference: str,
    records: Mapping[str, tuple[_OwnedNode, ...]],
) -> str:
    if not is_manifest_id(reference):
        return f"{_WARNING_LABEL} Next (navigation only): <invalid reference id>"
    matches = records.get(reference, ())
    if not matches:
        return (
            f"{_WARNING_LABEL} Next (navigation only): "
            f"{reference} :: <unresolved>"
        )
    if len(matches) != 1:
        return (
            f"{_WARNING_LABEL} Next (navigation only): "
            f"{reference} :: <ambiguous: {len(matches)} matches>"
        )
    target = matches[0].node
    goal = _summary(target.get("goal"), "node goal")
    return (
        f"{_NAVIGATION_LABEL}: {reference} :: {goal} "
        f"[{_status(target.get('status'))}]"
    )


def _navigation_lines(
    references: Any,
    records: Mapping[str, tuple[_OwnedNode, ...]],
) -> tuple[str, ...]:
    if not is_string_list(references):
        return (f"{_WARNING_LABEL} Next (navigation only): <invalid references>",)
    if not references:
        return (f"{_NAVIGATION_LABEL}: none",)
    return tuple(
        _navigation_reference(reference, records) for reference in references
    )


def _prerequisite_reference(
    dependent: Any,
    reference: str,
    records: Mapping[str, tuple[_OwnedNode, ...]],
) -> str:
    if not is_manifest_id(reference):
        return (
            f"{_WARNING_LABEL} Prerequisite (execution): "
            "<invalid reference id>"
        )
    matches = records.get(reference, ())
    if not matches:
        return (
            f"{_WARNING_LABEL} Prerequisite (execution): "
            f"{reference} :: <unresolved>"
        )
    if len(matches) != 1:
        return (
            f"{_WARNING_LABEL} Prerequisite (execution): "
            f"{reference} :: <ambiguous: {len(matches)} matches>"
        )
    if not is_manifest_id(dependent):
        return (
            f"{_WARNING_LABEL} Prerequisite (execution): "
            f"<invalid dependent id> :: {reference}"
        )

    target = matches[0]
    goal = _summary(target.node.get("goal"), "node goal")
    status = _status(target.node.get("status"))
    return (
        f"{_PREREQUISITE_LABEL}: "
        f"{dependent} <- {target.owner_directory} :: {reference} :: "
        f"{goal} [{status}]"
    )


def _prerequisite_lines(
    node: Mapping[str, Any],
    records: Mapping[str, tuple[_OwnedNode, ...]],
) -> tuple[str, ...]:
    references = node.get("prerequisites")
    if not is_string_list(references):
        return (
            f"{_WARNING_LABEL} Prerequisites (execution): <invalid references>",
        )
    if not references:
        return (f"{_EMPTY_PREREQUISITES_LABEL}: none",)
    dependent = node.get("id")
    return tuple(
        _prerequisite_reference(dependent, reference, records)
        for reference in references
    )


def _node_lines(
    node: Any,
    index: int,
    records: Mapping[str, tuple[_OwnedNode, ...]],
) -> tuple[str, ...]:
    if not isinstance(node, Mapping):
        return (f"{_WARNING_LABEL} Node: <invalid node[{index}]>",)

    lines = [
        f"{_NODE_LABEL}: {_summary(node.get('goal'), 'node goal')} "
        f"[{_status(node.get('status'))}]",
        f"{_ID_LABEL}: {_identifier(node.get('id'))}",
        f"{_ROLE_LABEL}: {_summary(node.get('role'), 'node role')}",
    ]
    if "code" in node:
        lines.append(f"{_CODE_LABEL}: {_summary(node.get('code'), 'code')}")
    if "title" in node:
        lines.append(f"{_TITLE_LABEL}: {_summary(node.get('title'), 'title')}")
    if "tags" in node:
        lines.append(f"{_TAGS_LABEL}: {_summary_list(node.get('tags'), 'tags')}")
    if "conditions" in node:
        lines.append(
            f"{_CONDITIONS_LABEL}: "
            f"{_summary_list(node.get('conditions'), 'conditions')}"
        )
    lines.extend(_prerequisite_lines(node, records))
    lines.extend(_navigation_lines(node.get("next"), records))
    if "status_reason" in node:
        lines.append(
            f"{_STATUS_REASON_LABEL}: "
            f"{_summary(node.get('status_reason'), 'status reason')}"
        )
    return tuple(lines)


def _checkpoint_lines(
    nodes: Sequence[Any] | None,
    error: str | None,
    records: Mapping[str, tuple[_OwnedNode, ...]],
) -> tuple[str, ...]:
    if nodes is None:
        detail = _summary(error, "checkpoints") if error is not None else "unavailable"
        return (f"{_WARNING_LABEL} Node: <invalid checkpoints: {detail}>",)
    if not nodes:
        return (f"{_NODE_LABEL}: none",)

    lines: list[str] = []
    for index, node in enumerate(nodes):
        lines.extend(_node_lines(node, index, records))
    return tuple(lines)


def _plan_presentation_lines(plan: Mapping[str, Any]) -> tuple[str, ...]:
    lines: list[str] = []
    if "kind" in plan:
        lines.append(f"{_KIND_LABEL}: {_summary(plan.get('kind'), 'kind')}")
    if "capability_key" in plan:
        lines.append(
            f"{_CAPABILITY_LABEL}: "
            f"{_summary(plan.get('capability_key'), 'capability key')}"
        )
    if "tree_mode" in plan:
        lines.append(
            f"{_TREE_MODE_LABEL}: {_summary(plan.get('tree_mode'), 'tree mode')}"
        )
    if "node_status" in plan:
        lines.append(
            f"{_NODE_STATUS_MODE_LABEL}: "
            f"{_summary(plan.get('node_status'), 'node status')}"
        )
    if "decision_issues" in plan:
        decisions = plan.get("decision_issues")
        if not isinstance(decisions, list):
            lines.append(f"{_DECISION_ISSUE_LABEL}: {_WARNING_LABEL} <invalid decisions>")
        elif not decisions:
            lines.append(f"{_DECISION_ISSUE_LABEL}: none")
        else:
            for decision in decisions:
                if not isinstance(decision, Mapping):
                    lines.append(f"{_DECISION_ISSUE_LABEL}: {_WARNING_LABEL} <invalid decision>")
                    continue
                lines.append(
                    f"{_DECISION_ISSUE_LABEL}: "
                    f"[{_summary(decision.get('urgency'), 'decision urgency')}/"
                    f"{_summary(decision.get('status'), 'decision status')}] "
                    f"{_summary(decision.get('question'), 'decision question')}"
                )
    if "entry_gate" not in plan:
        return tuple(lines)

    entry_gate = plan.get("entry_gate")
    if not isinstance(entry_gate, Mapping):
        lines.append(
            f"{_ENTRY_GATE_LABEL}: "
            f"{_WARNING_LABEL} <invalid entry gate: must be an object>"
        )
        return tuple(lines)

    lines.append(
        f"{_ENTRY_GATE_LABEL}: "
        f"{_summary(entry_gate.get('title'), 'entry gate title')}"
    )
    prerequisites = entry_gate.get("prerequisites")
    if not is_string_list(prerequisites):
        lines.append(
            f"{_ENTRY_GATE_PREREQUISITE_LABEL}: "
            f"{_WARNING_LABEL} <invalid references>"
        )
    elif not prerequisites:
        lines.append(f"{_ENTRY_GATE_PREREQUISITE_LABEL}: none")
    else:
        lines.extend(
            f"{_ENTRY_GATE_PREREQUISITE_LABEL}: {_identifier(reference)}"
            for reference in prerequisites
        )
    lines.append(
        f"{_ENTRY_GATE_CONDITIONS_LABEL}: "
        f"{_summary_list(entry_gate.get('conditions'), 'entry gate conditions')}"
    )
    return tuple(lines)


def _plan_hierarchy(
    plans: Sequence[Any],
) -> tuple[list[int], list[list[int]], list[int]]:
    directories: list[str | None] = []
    directory_index: dict[str, int] = {}
    for index, plan in enumerate(plans):
        value = plan.get("directory") if isinstance(plan, Mapping) else None
        normalized = (
            normalize_workspace_path(str(value))
            if _display_issue(value) is None
            and is_relative_workspace_path(value)
            else None
        )
        directories.append(normalized)
        if normalized is not None:
            directory_index.setdefault(normalized, index)

    roots: list[int] = []
    children: list[list[int]] = [[] for _ in plans]
    depths: list[int] = []
    for index, directory in enumerate(directories):
        depths.append(len(directory.split("/")) if directory is not None else 0)
        parent: int | None = None
        if directory is not None:
            parts = directory.split("/")
            for end in range(len(parts) - 1, 0, -1):
                candidate = "/".join(parts[:end])
                candidate_index = directory_index.get(candidate)
                if candidate_index is not None and candidate_index != index:
                    parent = candidate_index
                    break
        if parent is None:
            roots.append(index)
        else:
            children[parent].append(index)
    return roots, children, depths


def _render_ascii(root_plans: Sequence[PlanBlock]) -> str:
    lines = [_WORKSPACE_LABEL]
    stack: list[tuple[Any, str, bool]] = []
    last_root = len(root_plans) - 1
    for index in range(last_root, -1, -1):
        stack.append((root_plans[index], "", index == last_root))

    while stack:
        item, prefix, is_last = stack.pop()
        branch = "\\-- " if is_last else "+-- "
        label = item.label if isinstance(item, PlanBlock) else item
        lines.append(f"{prefix}{branch}{label}")
        if not isinstance(item, PlanBlock):
            continue

        extension = "    " if is_last else "|   "
        child_prefix = f"{prefix}{extension}"
        child_count = len(item.owned_lines) + len(item.child_plans)
        for position in range(child_count - 1, -1, -1):
            if position < len(item.owned_lines):
                child: Any = item.owned_lines[position]
            else:
                child = item.child_plans[position - len(item.owned_lines)]
            stack.append((child, child_prefix, position == child_count - 1))
    return "\n".join(lines)


def _render_details_tree(
    plans: Sequence[Any],
    checkpoints: Sequence[Sequence[Any] | None],
    checkpoint_errors: Sequence[str | None],
    *,
    selected_index: int | None = None,
) -> str:
    """Render every canonical field through the Emoji-annotated audit grammar."""
    records = _node_records(plans, checkpoints)
    roots, plan_children, depths = _plan_hierarchy(plans)
    plan_blocks: dict[int, PlanBlock] = {}

    for index in sorted(range(len(plans)), key=lambda item: depths[item], reverse=True):
        plan = plans[index]
        if not isinstance(plan, Mapping):
            plan_blocks[index] = PlanBlock(
                f"{_WARNING_LABEL} Plan: <invalid plan[{index}]>",
                (),
                (),
            )
            continue

        nodes = checkpoints[index] if index < len(checkpoints) else None
        error = checkpoint_errors[index] if index < len(checkpoint_errors) else None
        owned_lines = (
            f"{_ID_LABEL}: {_identifier(plan.get('id'))}",
            f"{_PURPOSE_LABEL}: {_summary(plan.get('purpose'), 'purpose')}",
            f"{_GOAL_LABEL}: {_summary(plan.get('goal'), 'goal')}",
            (
                f"{_DESCRIPTION_LABEL}: "
                f"{_summary(plan.get('description'), 'description')}"
            ),
            *_plan_presentation_lines(plan),
            *_checkpoint_lines(nodes, error, records),
        )
        plan_blocks[index] = PlanBlock(
            (
                f"{_PLAN_LABEL}: {_summary(plan.get('title'), 'title')} "
                f"[{_status(plan.get('status'))}] ({_directory(plan.get('directory'))})"
            ),
            owned_lines,
            tuple(plan_blocks[child] for child in plan_children[index]),
        )

    if selected_index is not None:
        if not 0 <= selected_index < len(plans):
            raise ValueError("selected plan index is out of range")
        root_indexes = [selected_index]
    else:
        root_indexes = roots
    return _render_ascii(tuple(plan_blocks[index] for index in root_indexes))


def _readable_enum(
    value: Any,
    allowed: set[str],
    fallback: str,
    field: str,
) -> tuple[str, str | None]:
    if value is None:
        return fallback, None
    if isinstance(value, str) and value in allowed:
        return value, None
    return fallback, f"{_WARNING_LABEL} <invalid {field}>"


def _readable_list(
    value: Any,
    field: str,
    *,
    absent_is_empty: bool = True,
) -> tuple[list[str], list[str]]:
    if value is None and absent_is_empty:
        return [], []
    if not isinstance(value, list) or not all(
        isinstance(item, str) for item in value
    ):
        return [], [
            f"{_WARNING_LABEL} <invalid {field}: must be an array of strings>"
        ]

    summaries: list[str] = []
    diagnostics: list[str] = []
    for item in value:
        issue = _display_issue(item)
        if issue is None:
            summaries.append(item.strip())
        else:
            diagnostics.append(
                f"{_WARNING_LABEL} <invalid {field}: {issue}>"
            )
    return summaries, diagnostics


def _code_counts(
    records: Mapping[str, tuple[_OwnedNode, ...]],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for matches in records.values():
        for owned in matches:
            code = owned.node.get("code")
            if _display_issue(code) is not None:
                continue
            normalized = str(code).strip()
            counts[normalized] = counts.get(normalized, 0) + 1
    return counts


def _dependency_codes(
    references: Any,
    records: Mapping[str, tuple[_OwnedNode, ...]],
    code_counts: Mapping[str, int],
) -> tuple[list[str], list[str], bool]:
    """Resolve ordered UUID prerequisites to unique source codes."""
    if not is_string_list(references):
        return (
            [],
            [f"{_WARNING_LABEL} <invalid prerequisites>"],
            False,
        )

    codes: list[str] = []
    diagnostics: list[str] = []
    all_completed = True
    for reference in references:
        if not is_manifest_id(reference):
            diagnostics.append(
                f"{_WARNING_LABEL} <invalid prerequisite id>"
            )
            all_completed = False
            continue
        matches = records.get(reference, ())
        if not matches:
            diagnostics.append(
                f"{_WARNING_LABEL} <unresolved prerequisite>"
            )
            all_completed = False
            continue
        if len(matches) != 1:
            diagnostics.append(
                f"{_WARNING_LABEL} <ambiguous prerequisite>"
            )
            all_completed = False
            continue

        target = matches[0].node
        if target.get("status") != "completed":
            all_completed = False
        code = target.get("code")
        issue = _display_issue(code)
        if issue is not None:
            diagnostics.append(
                f"{_WARNING_LABEL} <invalid prerequisite code: {issue}>"
            )
            continue
        normalized = str(code).strip()
        if code_counts.get(normalized, 0) != 1:
            diagnostics.append(
                f"{_WARNING_LABEL} <ambiguous prerequisite code>"
            )
            continue
        codes.append(normalized)
    return codes, diagnostics, all_completed


def _compress_code_runs(codes: Sequence[str]) -> list[str]:
    """Compress only complete consecutive runs already present in source order."""
    compressed: list[str] = []
    index = 0
    while index < len(codes):
        first = codes[index]
        first_match = _CODE_PATTERN.fullmatch(first)
        if first_match is None or not first_match.group(1):
            compressed.append(first)
            index += 1
            continue

        prefix = first_match.group(1)
        previous_number = int(first_match.group(2))
        end = index + 1
        while end < len(codes):
            candidate = codes[end]
            match = _CODE_PATTERN.fullmatch(candidate)
            if (
                match is None
                or match.group(1) != prefix
                or int(match.group(2)) != previous_number + 1
            ):
                break
            previous_number = int(match.group(2))
            end += 1

        if end - index >= 2:
            compressed.append(f"{first}-{codes[end - 1]}")
        else:
            compressed.append(first)
        index = end
    return compressed


def _state_token(status: Any, *, eligible: bool = False) -> str:
    if status == "pending":
        return "E" if eligible else "B"
    if status == "blocked":
        return "B"
    if status == "deferred":
        return "D"
    if status == "in_progress":
        return "ACTIVE"
    if status == "completed":
        return "ACCEPTED"
    if status == "skipped":
        return "SKIPPED"
    return f"{_WARNING_LABEL} <invalid status>"


def _node_eligible(
    node: Mapping[str, Any],
    records: Mapping[str, tuple[_OwnedNode, ...]],
) -> bool:
    if node.get("status") != "pending":
        return False
    prerequisites = node.get("prerequisites")
    if not is_string_list(prerequisites):
        return False
    if node.get("role") == MILESTONE_GATE_ROLE:
        if node_has_tag(node, GATE_LEAF_TAG):
            return False
        node_id = node.get("id")
        owners = records.get(str(node_id), ()) if is_manifest_id(node_id) else ()
        if len(owners) != 1:
            return False
        owner_directory = owners[0].owner_directory
        has_same_plan_leaf = False
        for reference in prerequisites:
            matches = records.get(reference, ())
            if len(matches) != 1 or not is_gate_leaf_node(matches[0].node):
                continue
            if matches[0].owner_directory != owner_directory:
                return False
            has_same_plan_leaf = True
        if not has_same_plan_leaf:
            return False
    for reference in prerequisites:
        if not is_manifest_id(reference):
            return False
        matches = records.get(reference, ())
        if len(matches) != 1 or matches[0].node.get("status") != "completed":
            return False
    return True


def _readable_node_label(node: Mapping[str, Any]) -> tuple[str, list[str]]:
    diagnostics: list[str] = []
    parts: list[str] = []

    if "code" in node:
        code_issue = _display_issue(node.get("code"))
        if code_issue is None:
            parts.append(str(node.get("code")).strip())
        else:
            diagnostics.append(
                f"{_WARNING_LABEL} <invalid code: {code_issue}>"
            )

    if "title" in node:
        title_issue = _display_issue(node.get("title"))
        if title_issue is None:
            parts.append(str(node.get("title")).strip())
        else:
            diagnostics.append(
                f"{_WARNING_LABEL} <invalid title: {title_issue}>"
            )
    else:
        goal_issue = _display_issue(node.get("goal"))
        if goal_issue is None:
            parts.append(str(node.get("goal")).strip())
        else:
            diagnostics.append(
                f"{_WARNING_LABEL} <invalid node goal: {goal_issue}>"
            )

    if not parts:
        parts.append(f"{_WARNING_LABEL} <unreadable node>")
    return " ".join(parts), diagnostics


def _readable_node_block(
    node: Any,
    index: int,
    records: Mapping[str, tuple[_OwnedNode, ...]],
    code_counts: Mapping[str, int],
    *,
    show_status: bool,
) -> ReadableBlock:
    if not isinstance(node, Mapping):
        return ReadableBlock(
            f"{_WARNING_LABEL} <invalid node[{index}]>"
        )

    label, diagnostics = _readable_node_label(node)
    eligible = _node_eligible(node, records)
    if show_status:
        tags, tag_diagnostics = _readable_list(node.get("tags"), "tags")
        conditions, condition_diagnostics = _readable_list(
            node.get("conditions"),
            "conditions",
        )
        codes, dependency_diagnostics, _ = _dependency_codes(
            node.get("prerequisites"),
            records,
            code_counts,
        )
        state_parts = [_state_token(node.get("status"), eligible=eligible), *tags]
        compressed = _compress_code_runs(codes)
        if dependency_diagnostics:
            diagnostics.extend(dependency_diagnostics)
        elif compressed:
            state_parts[-1] = (
                f"{state_parts[-1]} <- "
                f"{' + '.join([*compressed, *conditions])}"
            )
            conditions = []
        if conditions:
            state_parts.append(f"condition: {' + '.join(conditions)}")
        diagnostics.extend(tag_diagnostics)
        diagnostics.extend(condition_diagnostics)
        label = f"{label} [{', '.join(state_parts)}]"

    if diagnostics:
        label = f"{label} {' '.join(diagnostics)}"
    node_id = node.get("id")
    eligible_id = (
        str(node_id)
        if eligible
        and is_manifest_id(node_id)
        and len(records.get(str(node_id), ())) == 1
        else None
    )
    return ReadableBlock(label, eligible_node_id=eligible_id)


def _plan_status_token(
    plan: Mapping[str, Any],
    nodes: Sequence[Any] | None,
    records: Mapping[str, tuple[_OwnedNode, ...]],
) -> str:
    status = plan.get("status")
    if status != "pending":
        return _state_token(status)
    if nodes is None:
        return "B"
    return "E" if any(
        isinstance(node, Mapping) and _node_eligible(node, records)
        for node in nodes
    ) else "B"


def _gate_block(
    plan: Mapping[str, Any],
    nodes: Sequence[Any] | None,
    children: Sequence[ReadableBlock],
    records: Mapping[str, tuple[_OwnedNode, ...]],
    code_counts: Mapping[str, int],
) -> ReadableBlock:
    title = _summary(plan.get("title"), "title")
    if nodes is None or len(nodes) != 1 or not isinstance(nodes[0], Mapping):
        diagnostic = ReadableBlock(
            f"{_WARNING_LABEL} <invalid gate checkpoint>"
        )
        return ReadableBlock(
            f"{title} [G, B]",
            (diagnostic, *children),
        )

    node = nodes[0]
    eligible = _node_eligible(node, records)
    state = _state_token(node.get("status"), eligible=eligible)
    codes, dependency_diagnostics, _ = _dependency_codes(
        node.get("prerequisites"),
        records,
        code_counts,
    )
    conditions, condition_diagnostics = _readable_list(
        node.get("conditions"),
        "conditions",
    )
    diagnostics = [*dependency_diagnostics, *condition_diagnostics]
    requirements = [*_compress_code_runs(codes), *conditions]
    if diagnostics:
        requirement_label = " ".join(diagnostics)
    else:
        requirement_label = (
            f"requires: {' + '.join(requirements)}"
            if requirements
            else "requires: none"
        )
    node_id = node.get("id")
    eligible_id = (
        str(node_id)
        if eligible
        and is_manifest_id(node_id)
        and len(records.get(str(node_id), ())) == 1
        else None
    )
    return ReadableBlock(
        f"{title} [G, {state}]",
        (ReadableBlock(requirement_label), *children),
        eligible_node_id=eligible_id,
    )


def _entry_gate_block(
    plan: Mapping[str, Any],
    entry_gate: Any,
    children: Sequence[ReadableBlock],
    records: Mapping[str, tuple[_OwnedNode, ...]],
    code_counts: Mapping[str, int],
) -> ReadableBlock:
    if not isinstance(entry_gate, Mapping):
        return ReadableBlock(
            f"{_WARNING_LABEL} <invalid entry gate>",
            tuple(children),
            leading_spacer=bool(children),
            sibling_spacers=True,
        )

    title = _summary(entry_gate.get("title"), "entry gate title")
    codes, dependency_diagnostics, all_completed = _dependency_codes(
        entry_gate.get("prerequisites"),
        records,
        code_counts,
    )
    conditions, condition_diagnostics = _readable_list(
        entry_gate.get("conditions"),
        "entry gate conditions",
        absent_is_empty=False,
    )
    status = plan.get("status")
    eligible = status == "pending" and all_completed
    state = _state_token(status, eligible=eligible)
    diagnostics = [*dependency_diagnostics, *condition_diagnostics]
    requirements = [*_compress_code_runs(codes), *conditions]
    if dependency_diagnostics:
        state_label = (
            f"{state}, condition: {' + '.join(conditions)}"
            if conditions
            else state
        )
        label = f"{title} [{state_label}] {' '.join(diagnostics)}"
    elif codes:
        label = f"{title} [{state} <- {' + '.join(requirements)}]"
        if condition_diagnostics:
            label = f"{label} {' '.join(condition_diagnostics)}"
    elif conditions:
        label = f"{title} [{state}, condition: {' + '.join(conditions)}]"
        if diagnostics:
            label = f"{label} {' '.join(diagnostics)}"
    else:
        label = f"{title} [{state}]"
        if diagnostics:
            label = f"{label} {' '.join(diagnostics)}"
    return ReadableBlock(
        label,
        tuple(children),
        leading_spacer=bool(children),
        sibling_spacers=True,
    )


def _plan_title(plan: Mapping[str, Any]) -> str:
    return _summary(plan.get("title"), "title")


def _project_readable_forest(
    plans: Sequence[Any],
    checkpoints: Sequence[Sequence[Any] | None],
    checkpoint_errors: Sequence[str | None],
    *,
    selected_index: int | None,
) -> tuple[ReadableBlock, ...]:
    records = _node_records(plans, checkpoints)
    code_counts = _code_counts(records)
    roots, plan_children, _ = _plan_hierarchy(plans)

    def project(index: int, *, force_show: bool = False) -> tuple[ReadableBlock, ...]:
        plan = plans[index]
        if not isinstance(plan, Mapping):
            return (
                ReadableBlock(
                    f"{_WARNING_LABEL} <invalid plan[{index}]>"
                ),
            )

        mode, mode_diagnostic = _readable_enum(
            plan.get("tree_mode"),
            VALID_TREE_MODES,
            "show",
            "tree mode",
        )
        if force_show:
            mode = "show"
        if mode == "hide":
            return ()

        kind, kind_diagnostic = _readable_enum(
            plan.get("kind"),
            VALID_PLAN_KINDS,
            "plan",
            "kind",
        )
        node_status, node_status_diagnostic = _readable_enum(
            plan.get("node_status"),
            VALID_NODE_STATUS_MODES,
            "show",
            "node status",
        )
        nodes = checkpoints[index] if index < len(checkpoints) else None
        error = checkpoint_errors[index] if index < len(checkpoint_errors) else None

        owned: list[ReadableBlock] = []
        if nodes is None:
            detail = _summary(error, "checkpoints") if error is not None else "unavailable"
            owned.append(
                ReadableBlock(
                    f"{_WARNING_LABEL} <invalid checkpoints: {detail}>"
                )
            )
        elif kind != "gate":
            owned.extend(
                _readable_node_block(
                    node,
                    node_index,
                    records,
                    code_counts,
                    show_status=node_status == "show",
                )
                for node_index, node in enumerate(nodes)
            )

        projected_children: list[ReadableBlock] = []
        for child_index in plan_children[index]:
            projected_children.extend(project(child_index))

        if "entry_gate" in plan:
            projected_children = [
                _entry_gate_block(
                    plan,
                    plan.get("entry_gate"),
                    projected_children,
                    records,
                    code_counts,
                )
            ]

        diagnostics = [
            value
            for value in (
                mode_diagnostic,
                kind_diagnostic,
                node_status_diagnostic,
            )
            if value is not None
        ]
        diagnostic_blocks = [ReadableBlock(value) for value in diagnostics]

        if mode == "flatten":
            # Flatten removes only the structural Plan from the reading view.
            # Its child Plans are promoted, while its own Nodes remain available
            # through --details or an explicitly selected (force-shown) subtree.
            return tuple([*diagnostic_blocks, *projected_children])

        child_blocks = [*diagnostic_blocks, *owned, *projected_children]
        if kind == "gate":
            block = _gate_block(
                plan,
                nodes,
                projected_children,
                records,
                code_counts,
            )
            if diagnostic_blocks:
                block = ReadableBlock(
                    block.label,
                    (*diagnostic_blocks, *block.children),
                    block.leading_spacer,
                    block.sibling_spacers,
                    block.eligible_node_id,
                )
            return (block,)

        title = _plan_title(plan)
        if kind == "rule":
            label = f"{title} [R]"
        elif kind in {"branch", "context", "release"}:
            label = f"{title} [{_plan_status_token(plan, nodes, records)}]"
        else:
            label = title
        leading_spacer = bool(child_blocks) and kind in {
            "context",
            "group",
            "plan",
            "release",
            "root",
            "stage",
        }
        return (
            ReadableBlock(
                label,
                tuple(child_blocks),
                leading_spacer=leading_spacer,
                sibling_spacers=kind == "root",
            ),
        )

    if selected_index is not None:
        if not 0 <= selected_index < len(plans):
            raise ValueError("selected plan index is out of range")
        return project(selected_index, force_show=True)

    forest: list[ReadableBlock] = []
    for root_index in roots:
        forest.extend(project(root_index))
    return tuple(forest)


def _eligible_block_ids(blocks: Sequence[ReadableBlock]) -> list[str]:
    eligible: list[str] = []
    stack = list(reversed(blocks))
    while stack:
        block = stack.pop()
        if block.eligible_node_id is not None:
            eligible.append(block.eligible_node_id)
        stack.extend(reversed(block.children))
    return eligible


def _render_readable_connected(
    block: ReadableBlock,
    prefix: str,
    is_last: bool,
    current_id: str | None,
    lines: list[str],
) -> None:
    branch = "\\-- " if is_last else "+-- "
    current = (
        "  <== CURRENT"
        if block.eligible_node_id is not None
        and block.eligible_node_id == current_id
        else ""
    )
    lines.append(f"{prefix}{branch}{block.label}{current}")
    if not block.children:
        return

    child_prefix = f"{prefix}{'    ' if is_last else '|   '}"
    for child_index, child in enumerate(block.children):
        if (
            (child_index == 0 and block.leading_spacer)
            or (child_index > 0 and block.sibling_spacers)
        ):
            lines.append(f"{child_prefix}|")
        _render_readable_connected(
            child,
            child_prefix,
            child_index == len(block.children) - 1,
            current_id,
            lines,
        )


def _render_readable_forest(blocks: Sequence[ReadableBlock]) -> str:
    eligible = _eligible_block_ids(blocks)
    current_id = eligible[0] if len(eligible) == 1 else None
    lines = _READABLE_HEADER.splitlines()
    if not blocks:
        return "\n".join(
            [*lines, "", f"{_WARNING_LABEL} <no visible Plans>"]
        )

    for root_index, root in enumerate(blocks):
        lines.append("")
        current = (
            "  <== CURRENT"
            if root.eligible_node_id is not None
            and root.eligible_node_id == current_id
            else ""
        )
        lines.append(f"{root.label}{current}")
        for child_index, child in enumerate(root.children):
            if (
                (child_index == 0 and root.leading_spacer)
                or (child_index > 0 and root.sibling_spacers)
            ):
                lines.append("|")
            _render_readable_connected(
                child,
                "",
                child_index == len(root.children) - 1,
                current_id,
                lines,
            )
        if root_index < len(blocks) - 1:
            lines.append("")
    return "\n".join(lines)


def render_workspace_tree(
    plans: Sequence[Any],
    checkpoints: Sequence[Sequence[Any] | None],
    checkpoint_errors: Sequence[str | None],
    *,
    selected_index: int | None = None,
    details: bool = False,
) -> str:
    """Render a pure readable projection or the explicit complete audit view."""
    if details:
        return _render_details_tree(
            plans,
            checkpoints,
            checkpoint_errors,
            selected_index=selected_index,
        )
    return _render_readable_forest(
        _project_readable_forest(
            plans,
            checkpoints,
            checkpoint_errors,
            selected_index=selected_index,
        )
    )
