"""Deterministically compile a structured Designer draft into a v3 Plan spec."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence
import hashlib
import re

from .models import (
    VALID_RISKS,
    plain_regression_paths,
    plain_shell_command,
    safe_summary_issue,
    sha256_value,
)


_HEADING = re.compile(r"^\s*(#{1,4})\s+(.+?)\s*$")
_LABEL = re.compile(r"^\s*([A-Za-z][A-Za-z0-9 _/-]*):(?:\s*(.*))?$")
_BULLET = re.compile(r"^\s*-\s+(.+?)\s*$")
_EXCLUDE = "<!-- better-plan: exclude -->"
_DASH = re.compile(r"\s+—\s+")
DESIGN_TEMPLATE = """## Requirements

## Architecture
Summary:
Notes:

## Task:
Outcome:
Scope in:
Scope out:
Outputs:
Owns:
Exclusive:
Worker:
Difficulty:
Workload:
Verification:
Risks:
Nodes:
Requirements:
Design:
Acceptance:
Regression:
Commands:
Paths:

## Full regression
Commands:
Paths:
"""

DESIGN_EXAMPLE = """# Delivery design

## Requirements
- observable-behavior: The authorized behavior is observable and verified. — source: user-request

## Architecture
Summary: One bounded design whose Tasks form a single parallel frontier.
Notes:
- Keep dependent implementation steps inside the same Task.

## Task: bounded-delivery
Outcome: The requested behavior passes its focused oracle.
Scope in:
- The bounded capability and its focused verification.
Scope out:
- Unrelated capabilities.
Outputs:
- verified-result: Verified result — artifact: relative/path — guarantee: The delivery can rely on the verified behavior.
Owns:
- relative/path
Exclusive:
Worker: general
Difficulty: standard
Workload: medium
Verification: code
Risks:
Nodes:
- inspect-contracts: Confirm the affected contracts and boundaries.
- implement-behavior: Implement the bounded behavior. — after: inspect-contracts
- verify-behavior: Prepare focused verification. — after: inspect-contracts
- integrate-result: Integrate implementation and verification. — after: implement-behavior, verify-behavior
Requirements:
- observable-behavior
Design:
approach:
- Use the simplest implementation that satisfies the outcome.
Acceptance:
- Given: A valid starting state — When: The behavior is exercised — Then: The observable result occurs — Oracle: The focused command exits zero — Evidence: command: focused regression — Covers: observable-behavior, verified-result
Regression:
Commands:
- python3 -m unittest tests.test_module
Paths:
- relative/path

## Full regression
Commands:
- python3 -m unittest discover -s tests -p 'test_*.py'
Paths:
- relative/path
"""


def _slug(value: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", value.strip().lower())).strip("-")


def _digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _values(value: str, *, commas: bool = False) -> list[str]:
    text = value.strip()
    if not text:
        return []
    if commas:
        return [item.strip() for item in text.split(",") if item.strip()]
    return [text]


def _issue(kind: str, message: str, line: int, field: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "message": message,
        "line": line,
        "field": field,
        "status": "open",
    }


def _locate(context: dict[str, Any], line: int, field: str) -> None:
    context["line"] = line
    context["field"] = field


def source_line_for_field(result: Mapping[str, Any], field: str) -> int:
    """Return the nearest Design.md source line for a canonical diagnostic field."""

    locations = result.get("locations") if isinstance(result.get("locations"), Mapping) else {}
    candidate = field[5:] if field.startswith("plan.") else field
    while candidate:
        value = locations.get(candidate)
        if type(value) is int and value > 0:
            return value
        shortened = re.sub(r"(?:\.[^.\[]+|\[\d+\])$", "", candidate)
        if shortened == candidate:
            break
        candidate = shortened
    return 1


def _unmapped(lines: Sequence[tuple[int, str]], excluded: bool = False) -> dict[str, Any]:
    start = lines[0][0]
    end = lines[-1][0]
    raw = "\n".join(value for _, value in lines)
    return {
        "lines": [start, end],
        "digest": _digest_text(raw),
        "status": "excluded" if excluded else "open",
    }


def _consume_section_exclusion(lines: list[tuple[int, str]]) -> bool:
    for index in range(len(lines) - 1, -1, -1):
        stripped = lines[index][1].strip()
        if not stripped:
            continue
        if stripped != _EXCLUDE:
            return False
        del lines[index]
        return True
    return False


def _sections(text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    lines = text.splitlines()
    sections: list[dict[str, Any]] = []
    unmapped: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    prefix: list[tuple[int, str]] = []
    for number, line in enumerate(lines, 1):
        stripped = line.strip()
        match = _HEADING.match(line)
        if match and len(match.group(1)) >= 2:
            previous = current["body"] if current is not None else prefix
            excluded = _consume_section_exclusion(previous)
            if current is not None:
                sections.append(current)
            elif prefix:
                unmapped.append(_unmapped(prefix))
            current = {
                "title": match.group(2).strip(),
                "line": number,
                "body": [],
                "excluded": excluded,
            }
            continue
        if match and len(match.group(1)) == 1 and current is None:
            continue
        if current is None:
            if stripped:
                prefix.append((number, line))
        else:
            current["body"].append((number, line))
    if current is not None:
        sections.append(current)
    elif prefix:
        unmapped.append(_unmapped(prefix))
    return sections, unmapped


_TASK_ALIASES = {
    "outcome": "outcome",
    "scope in": "scope_in",
    "scope out": "scope_out",
    "outputs": "outputs",
    "owns": "owns",
    "write paths": "owns",
    "exclusive": "exclusive",
    "worker": "worker",
    "difficulty": "difficulty",
    "tier": "difficulty",
    "workload": "workload",
    "verification": "verification",
    "risks": "risks",
    "nodes": "nodes",
    "requirements": "requirements",
    "design": "design",
    "acceptance": "acceptance",
    "regression": "regression",
}
_FORBIDDEN_TASK_FIELDS = {
    "depends on": "prerequisites",
    "prerequisites": "prerequisites",
    "uses": "inputs",
}


def _task_field(prefix: str, name: str) -> str:
    fields = {
        "scope_in": "scope.in",
        "scope_out": "scope.out",
        "owns": "ownership.write_paths",
        "exclusive": "ownership.shared_exclusive",
        "regression.commands": "focused_regression.commands",
        "regression.paths": "focused_regression.paths",
    }
    if name.startswith("design."):
        return "%s.%s" % (prefix, name)
    return "%s.%s" % (prefix, fields.get(name, name))


def _task_blocks(
    body: Sequence[tuple[int, str]],
    prefix: str,
) -> tuple[dict[str, list[tuple[int, str]]], list[dict[str, Any]], list[dict[str, Any]]]:
    blocks: dict[str, list[tuple[int, str]]] = {}
    issues: list[dict[str, Any]] = []
    unmapped: list[dict[str, Any]] = []
    current: str | None = None
    nested: str | None = None
    exclude_next = False
    for number, raw in body:
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped == _EXCLUDE:
            exclude_next = True
            continue
        if exclude_next:
            unmapped.append(_unmapped([(number, raw)], True))
            exclude_next = False
            continue
        label = _LABEL.match(raw)
        key = label.group(1).strip().lower() if label else None
        if label and key in _FORBIDDEN_TASK_FIELDS:
            field = _FORBIDDEN_TASK_FIELDS[key]
            issues.append(
                _issue(
                    "structure",
                    "cross-Task dependencies are not allowed; merge dependent work into one Task",
                    number,
                    "%s.%s" % (prefix, field),
                )
            )
            current = "forbidden"
            nested = None
            continue
        if label and key in _TASK_ALIASES:
            current = _TASK_ALIASES[key]
            nested = None
            if current in blocks:
                issues.append(_issue(
                    "structure",
                    "duplicate Task field %s" % key,
                    number,
                    _task_field(prefix, current),
                ))
            blocks.setdefault(current, [])
            if label.group(2):
                blocks[current].append((number, label.group(2).strip()))
            continue
        if current == "design" and label:
            design_key = _slug(label.group(1))
            if not design_key:
                issues.append(_issue("structure", "invalid Design key", number, prefix + ".design"))
                continue
            nested = "design.%s" % design_key
            blocks.setdefault(nested, [])
            if label.group(2):
                blocks[nested].append((number, label.group(2).strip()))
            continue
        if current == "regression" and label and key in {"commands", "paths"}:
            nested = "regression.%s" % key
            blocks.setdefault(nested, [])
            if label.group(2):
                blocks[nested].append((number, label.group(2).strip()))
            continue
        bullet = _BULLET.match(raw)
        if bullet and (nested or current):
            target = nested or current
            blocks.setdefault(target, []).append((number, bullet.group(1).strip()))
            continue
        entry = _unmapped([(number, raw)])
        unmapped.append(entry)
        issues.append(_issue("unmapped", "unmapped Design.md content", number, prefix))
    return blocks, issues, unmapped


def _block_values(blocks: Mapping[str, Sequence[tuple[int, str]]], name: str) -> list[str]:
    return [value for _, value in blocks.get(name, []) if value.strip()]


def _parse_requirement(
    value: str,
    line: int,
    field: str,
    issues: list[dict[str, Any]],
) -> tuple[str, dict[str, Any]] | None:
    parts = _DASH.split(value)
    if ":" not in parts[0]:
        issues.append(_issue("structure", "Requirement must be 'name: statement'", line, field))
        return None
    name, statement = [item.strip() for item in parts[0].split(":", 1)]
    slug = _slug(name)
    missing = []
    if not slug:
        missing.append("name")
    if not statement:
        missing.append("statement")
    for name in missing:
        issues.append(_issue(
            "structure",
            "Requirement requires %s" % name,
            line,
            "%s.%s" % (field, name),
        ))
    if missing:
        return None
    refs = ["Design.md"]
    for part in parts[1:]:
        if part.lower().startswith("source:"):
            refs = _values(part.split(":", 1)[1], commas=True) or refs
        else:
            issues.append(_issue("structure", "unknown Requirement field", line, field))
    return slug, {"statement": statement, "source_refs": refs}


def _parse_architecture(
    body: Sequence[tuple[int, str]],
    section_line: int,
    issues: list[dict[str, Any]],
    unmapped: list[dict[str, Any]],
    locations: dict[str, int],
) -> dict[str, Any]:
    summary = ""
    notes: list[str] = []
    current: str | None = None
    exclude_next = False
    for number, raw in body:
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped == _EXCLUDE:
            exclude_next = True
            continue
        if exclude_next:
            unmapped.append(_unmapped([(number, raw)], True))
            exclude_next = False
            continue
        label = _LABEL.match(raw)
        key = label.group(1).strip().lower() if label else None
        if label and key == "summary":
            summary = (label.group(2) or "").strip()
            locations["spec.architecture.summary"] = number
            current = "summary"
            continue
        if label and key == "notes":
            locations["spec.architecture.notes"] = number
            current = "notes"
            if label.group(2):
                notes.append(label.group(2).strip())
            continue
        bullet = _BULLET.match(raw)
        if bullet and current == "notes":
            locations["spec.architecture.notes[%d]" % len(notes)] = number
            notes.append(bullet.group(1).strip())
            continue
        unmapped.append(_unmapped([(number, raw)]))
        issues.append(_issue("unmapped", "unmapped Architecture content", number, "spec.architecture"))
    if not summary:
        issues.append(_issue(
            "structure",
            "Architecture requires Summary",
            section_line,
            "spec.architecture.summary",
        ))
    if not notes:
        issues.append(_issue(
            "structure",
            "Architecture requires Notes",
            section_line,
            "spec.architecture.notes",
        ))
    return {"summary": summary, "notes": notes}


def _regression_values(key: str, text: str) -> list[str]:
    """Normalize one Commands or Paths entry into executable plain values."""

    if key == "paths":
        return plain_regression_paths([text])
    value = plain_shell_command(text)
    return [value] if value else []


def _parse_regression(
    body: Sequence[tuple[int, str]],
    section_line: int,
    issues: list[dict[str, Any]],
    unmapped: list[dict[str, Any]],
    locations: dict[str, int],
    label: str,
    prefix: str,
) -> dict[str, list[str]]:
    blocks: dict[str, list[str]] = {"commands": [], "paths": []}
    current: str | None = None
    exclude_next = False
    for number, raw in body:
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped == _EXCLUDE:
            exclude_next = True
            continue
        if exclude_next:
            unmapped.append(_unmapped([(number, raw)], True))
            exclude_next = False
            continue
        match = _LABEL.match(raw)
        key = match.group(1).strip().lower() if match else None
        if match and key in blocks:
            current = key
            locations["%s.%s" % (prefix, key)] = number
            if match.group(2):
                for value in _regression_values(key, match.group(2)):
                    locations["%s.%s[%d]" % (prefix, key, len(blocks[key]))] = number
                    blocks[key].append(value)
            continue
        bullet = _BULLET.match(raw)
        if bullet and current:
            for value in _regression_values(current, bullet.group(1)):
                locations["%s.%s[%d]" % (prefix, current, len(blocks[current]))] = number
                blocks[current].append(value)
            continue
        issues.append(_issue("structure", "unrecognized %s field" % label, number, prefix))
    if not blocks["commands"]:
        issues.append(_issue(
            "structure",
            "%s requires Commands" % label,
            section_line,
            prefix + ".commands",
        ))
    if not blocks["paths"]:
        issues.append(_issue(
            "structure",
            "%s requires Paths" % label,
            section_line,
            prefix + ".paths",
        ))
    return blocks


def _parse_output(
    value: str,
    line: int,
    field: str,
    issues: list[dict[str, Any]],
) -> tuple[str, dict[str, str]] | None:
    parts = _DASH.split(value)
    if ":" not in parts[0]:
        issues.append(_issue("structure", "Output must begin 'name: title'", line, field))
        return None
    name, title = [item.strip() for item in parts[0].split(":", 1)]
    slug = _slug(name)
    fields: dict[str, str] = {"title": title}
    for part in parts[1:]:
        if ":" not in part:
            issues.append(_issue("structure", "Output field requires a label", line, field))
            continue
        key, content = [item.strip() for item in part.split(":", 1)]
        fields[key.lower()] = content
    missing = []
    if not slug:
        missing.append("name")
    if not title:
        missing.append("title")
    if not fields.get("artifact"):
        missing.append("artifact")
    if not fields.get("guarantee"):
        missing.append("guarantee")
    for name in missing:
        issues.append(_issue("structure", "Output requires %s" % name, line, "%s.%s" % (field, name)))
    if missing:
        return None
    return slug, {
        "title": title,
        "artifact": fields["artifact"],
        "guarantee": fields["guarantee"],
    }


def _parse_node(
    value: str,
    line: int,
    field: str,
    issues: list[dict[str, Any]],
) -> tuple[str, dict[str, Any], list[str]] | None:
    parts = _DASH.split(value)
    if ":" not in parts[0]:
        issues.append(_issue("structure", "Node must be 'name: outcome'", line, field))
        return None
    title, outcome = [item.strip() for item in parts[0].split(":", 1)]
    slug = _slug(title)
    after: list[str] = []
    saw_after = False
    missing = []
    if not slug:
        missing.append("name")
    if not outcome:
        missing.append("outcome")
    for part in parts[1:]:
        if ":" not in part:
            issues.append(_issue("structure", "Node option requires a label", line, field))
            continue
        label, raw = [item.strip() for item in part.split(":", 1)]
        if label.lower() != "after":
            issues.append(_issue("structure", "unknown Node option %s" % label, line, field))
            continue
        if saw_after:
            issues.append(_issue("structure", "duplicate Node after option", line, field + ".prerequisites"))
            continue
        saw_after = True
        if raw.lower() != "none":
            after = [_slug(item) for item in raw.split(",") if item.strip()]
            if any(not item for item in after):
                issues.append(_issue("structure", "Node after requires names", line, field + ".prerequisites"))
    for name in missing:
        issues.append(_issue("structure", "Node requires %s" % name, line, "%s.%s" % (field, name)))
    if missing:
        return None
    return slug, {"title": title, "outcome": outcome}, after


def _parse_acceptance(
    value: str,
    line: int,
    field: str,
    issues: list[dict[str, Any]],
) -> dict[str, Any] | None:
    fields: dict[str, str] = {}
    for part in _DASH.split(value):
        if ":" not in part:
            issues.append(_issue("structure", "Acceptance field requires a label", line, field))
            return None
        key, content = [item.strip() for item in part.split(":", 1)]
        fields[key.lower()] = content
    required = {"given", "when", "then", "oracle", "evidence"}
    missing = sorted(required - set(fields))
    for name in missing:
        issues.append(_issue(
            "structure",
            "Acceptance requires %s" % name.title(),
            line,
            "%s.%s" % (field, name),
        ))
    if missing:
        return None
    if ":" not in fields["evidence"]:
        issues.append(_issue(
            "structure",
            "Evidence must be 'type: source'",
            line,
            field + ".evidence",
        ))
        return None
    evidence_type, evidence_source = [item.strip() for item in fields["evidence"].split(":", 1)]
    return {
        "given": fields["given"],
        "when": fields["when"],
        "then": fields["then"],
        "oracle": fields["oracle"],
        "evidence": {"type": evidence_type, "source": evidence_source},
        "cover_names": _values(fields.get("covers", ""), commas=True),
        "line": line,
    }


def _content_issues(
    value: Any,
    locations: Mapping[str, int],
    prefix: str = "spec",
    inherited_line: int = 1,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    line = locations.get(prefix, inherited_line)
    if isinstance(value, Mapping):
        for key, child in value.items():
            issues.extend(_content_issues(child, locations, "%s.%s" % (prefix, key), line))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            issues.extend(_content_issues(child, locations, "%s[%d]" % (prefix, index), line))
    elif isinstance(value, str) and not re.match(r"^(?:REQ|TASK|OUT|AC)-", value):
        problem = safe_summary_issue(value)
        if problem is not None:
            issues.append(_issue("content", problem, line, prefix))
    return issues


def compile_design(
    text: str,
    fallback_spec: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a deterministic candidate and issue receipt for every input string."""

    fallback = deepcopy(dict(fallback_spec or {}))
    context: dict[str, Any] = {"line": 1, "field": "document"}
    try:
        return _compile_design(text, fallback, context)
    except Exception as exc:
        line = context["line"] if type(context.get("line")) is int else 1
        field = str(context.get("field") or "document")
        return {
            "spec": fallback,
            "issues": [_issue(
                "structure",
                "Design compiler failed while processing %s (%s)" % (field, type(exc).__name__),
                line,
                field,
            )],
            "unmapped": [],
            "sections_from_plan": [],
            "locations": {"spec": line},
            "compiled_spec_digest": sha256_value(fallback),
        }


def _compile_design(
    text: str,
    fallback: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    _locate(context, 1, "document")
    sections, unmapped = _sections(text)
    issues: list[dict[str, Any]] = []
    sections_from_plan: list[str] = []
    locations: dict[str, int] = {"spec": 1}
    known: dict[str, dict[str, Any]] = {}
    tasks_raw: list[dict[str, Any]] = []
    for section in sections:
        title = str(section["title"])
        lowered = title.lower()
        _locate(context, section["line"], "document.sections")
        if section["excluded"]:
            block = [(section["line"], "## " + title)] + list(section["body"])
            unmapped.append(_unmapped(block, True))
        elif lowered in {"requirements", "architecture", "full regression"}:
            if lowered in known:
                issues.append(_issue(
                    "structure",
                    "duplicate %s section" % title,
                    section["line"],
                    "spec.%s" % lowered.replace(" ", "_"),
                ))
            else:
                known[lowered] = section
        elif lowered.startswith("task:"):
            tasks_raw.append(section)
        else:
            block = [(section["line"], "## " + title)] + list(section["body"])
            unmapped.append(_unmapped(block))
            issues.append(_issue(
                "unmapped",
                "unknown top-level section %s" % title,
                section["line"],
                "document.sections",
            ))

    requirements: list[dict[str, Any]] = []
    requirement_codes: dict[str, str] = {}
    requirement_section = known.get("requirements")
    if requirement_section is None:
        locations["spec.requirements"] = 1
        requirements = deepcopy(fallback.get("requirements", []))
        sections_from_plan.append("requirements")
        for item in requirements:
            if isinstance(item, Mapping):
                requirement_codes[_slug(str(item.get("statement", "")))] = str(item.get("code"))
    else:
        locations["spec.requirements"] = requirement_section["line"]
        seen: set[str] = set()
        exclude_next = False
        for number, raw in requirement_section["body"]:
            _locate(context, number, "spec.requirements")
            if not raw.strip():
                continue
            if raw.strip() == _EXCLUDE:
                exclude_next = True
                continue
            if exclude_next:
                unmapped.append(_unmapped([(number, raw)], True))
                exclude_next = False
                continue
            bullet = _BULLET.match(raw)
            if bullet is None:
                issues.append(_issue(
                    "structure",
                    "Requirement entries must be list items",
                    number,
                    "spec.requirements",
                ))
                continue
            item_field = "spec.requirements[%d]" % len(requirements)
            locations[item_field] = number
            parsed = _parse_requirement(bullet.group(1), number, item_field, issues)
            if parsed is None:
                continue
            slug, value = parsed
            if slug in seen:
                issues.append(_issue(
                    "structure",
                    "duplicate Requirement name %s" % slug,
                    number,
                    item_field,
                ))
                continue
            seen.add(slug)
            code = "REQ-%03d" % (len(requirements) + 1)
            requirement_codes[slug] = code
            requirements.append({"code": code, **value})

    architecture_section = known.get("architecture")
    if architecture_section is None:
        locations["spec.architecture"] = 1
        architecture = deepcopy(fallback.get("architecture", {"summary": "", "notes": []}))
        sections_from_plan.append("architecture")
    else:
        locations["spec.architecture"] = architecture_section["line"]
        _locate(context, architecture_section["line"], "spec.architecture")
        architecture = _parse_architecture(
            architecture_section["body"],
            architecture_section["line"],
            issues,
            unmapped,
            locations,
        )

    task_names: dict[str, str] = {}
    valid_task_sections: list[tuple[str, dict[str, Any]]] = []
    for section in tasks_raw:
        task_field = "spec.tasks[%d]" % len(valid_task_sections)
        _locate(context, section["line"], task_field)
        name = str(section["title"]).split(":", 1)[1].strip()
        slug = _slug(name)
        if not slug:
            issues.append(_issue("structure", "Task requires an ASCII name", section["line"], task_field))
            continue
        if slug in task_names:
            issues.append(_issue(
                "structure",
                "duplicate Task name %s" % slug,
                section["line"],
                task_field,
            ))
            continue
        code = "TASK-%03d" % (len(valid_task_sections) + 1)
        task_names[slug] = code
        locations[task_field] = section["line"]
        valid_task_sections.append((slug, section))
    if not tasks_raw:
        issues.append(_issue("structure", "Design requires at least one Task section", 1, "spec.tasks"))

    parsed_tasks: list[dict[str, Any]] = []
    parsed_metadata: list[dict[str, Any]] = []
    output_counter = 0
    node_counter = 0
    acceptance_counter = 0
    output_codes_by_task: dict[str, dict[str, str]] = {}
    for task_index, (task_slug, section) in enumerate(valid_task_sections, 1):
        task_prefix = "spec.tasks[%d]" % (task_index - 1)
        _locate(context, section["line"], task_prefix)
        blocks, block_issues, block_unmapped = _task_blocks(section["body"], task_prefix)
        issues.extend(block_issues)
        unmapped.extend(block_unmapped)
        for name, entries in blocks.items():
            field = _task_field(task_prefix, name)
            if entries:
                locations[field] = entries[0][0]
                for index, (number, _) in enumerate(entries):
                    locations["%s[%d]" % (field, index)] = number
        outputs: list[dict[str, Any]] = []
        output_names: dict[str, str] = {}
        for source_index, (number, raw) in enumerate(blocks.get("outputs", [])):
            output_field = "%s.outputs[%d]" % (task_prefix, source_index)
            locations[output_field] = number
            _locate(context, number, output_field)
            parsed = _parse_output(raw, number, output_field, issues)
            if parsed is None:
                continue
            output_slug, output = parsed
            if output_slug in output_names:
                issues.append(_issue(
                    "structure",
                    "duplicate Output name %s" % output_slug,
                    number,
                    output_field,
                ))
                continue
            output_counter += 1
            output_code = "OUT-%03d" % output_counter
            output_names[output_slug] = output_code
            outputs.append({"code": output_code, **output})
        output_codes_by_task[task_slug] = output_names
        nodes: list[dict[str, Any]] = []
        node_names: dict[str, str] = {}
        node_dependencies: list[tuple[int, list[str]]] = []
        for source_index, (number, raw) in enumerate(blocks.get("nodes", [])):
            node_field = "%s.nodes[%d]" % (task_prefix, source_index)
            locations[node_field] = number
            locations[node_field + ".prerequisites"] = number
            _locate(context, number, node_field)
            parsed = _parse_node(raw, number, node_field, issues)
            if parsed is None:
                continue
            node_slug, node, after_names = parsed
            if node_slug in node_names:
                issues.append(_issue(
                    "structure",
                    "duplicate Node name %s" % node_slug,
                    number,
                    node_field,
                ))
                continue
            node_counter += 1
            node_code = "NODE-%03d" % node_counter
            node_names[node_slug] = node_code
            nodes.append({"code": node_code, **node, "prerequisites": []})
            node_dependencies.append((number, after_names))
        for node_index, (node, (number, after_names)) in enumerate(zip(nodes, node_dependencies)):
            for name in after_names:
                dependency = node_names.get(name)
                if dependency is None:
                    issues.append(_issue(
                        "structure",
                        "unknown Node prerequisite %s" % name,
                        number,
                        "%s.nodes[%d].prerequisites" % (task_prefix, node_index),
                    ))
                elif dependency == node["code"]:
                    issues.append(_issue(
                        "structure",
                        "Node cannot depend on itself",
                        number,
                        "%s.nodes[%d].prerequisites" % (task_prefix, node_index),
                    ))
                elif dependency not in node["prerequisites"]:
                    node["prerequisites"].append(dependency)
        risks = []
        for number, value in blocks.get("risks", []):
            for risk in _values(value, commas=True):
                if risk not in VALID_RISKS:
                    issues.append(_issue(
                        "structure",
                        "unknown risk tag %s" % risk,
                        number,
                        task_prefix + ".risks",
                    ))
                elif risk not in risks:
                    risks.append(risk)
        worker_entries = blocks.get("worker", [])
        requested_worker = ([value for _, value in worker_entries] or ["general"])[0].lower()
        worker = requested_worker if requested_worker in {"general", "frontend"} else "general"
        if requested_worker not in {"general", "frontend"}:
            issues.append(_issue(
                "structure",
                "Worker must be general or frontend",
                worker_entries[0][0] if worker_entries else section["line"],
                task_prefix + ".worker",
            ))
        difficulty_entries = blocks.get("difficulty", [])
        requested_difficulty = ([value for _, value in difficulty_entries] or ["standard"])[0].lower()
        difficulty = requested_difficulty if requested_difficulty in {"standard", "complex"} else "standard"
        if requested_difficulty not in {"standard", "complex"}:
            issues.append(_issue(
                "structure",
                "Difficulty must be standard or complex",
                difficulty_entries[0][0] if difficulty_entries else section["line"],
                task_prefix + ".difficulty",
            ))
        workload_entries = blocks.get("workload", [])
        requested_workload = ([value for _, value in workload_entries] or [""])[0].lower()
        workload = requested_workload if requested_workload in {"light", "medium", "heavy"} else "medium"
        if requested_workload not in {"light", "medium", "heavy"}:
            issues.append(_issue(
                "structure",
                "Workload must be light, medium, or heavy",
                workload_entries[0][0] if workload_entries else section["line"],
                task_prefix + ".workload",
            ))
        verification_entries = blocks.get("verification", [])
        verification = ([value for _, value in verification_entries] or ["code"])[0].lower()
        if verification not in {"code", "visual", "hybrid"}:
            issues.append(_issue(
                "structure",
                "Verification must be code, visual, or hybrid",
                verification_entries[0][0] if verification_entries else section["line"],
                task_prefix + ".verification",
            ))
            verification = "code"
        task_requirement_codes: list[str] = []
        for number, raw in blocks.get("requirements", []):
            for name in _values(raw, commas=True):
                code = requirement_codes.get(_slug(name))
                if code is None:
                    issues.append(_issue(
                        "structure",
                        "unknown Requirement %s" % name,
                        number,
                        task_prefix + ".requirements",
                    ))
                elif code not in task_requirement_codes:
                    task_requirement_codes.append(code)
        ownership = _block_values(blocks, "owns")
        design = {
            key.split(".", 1)[1]: _block_values(blocks, key)
            for key in blocks
            if key.startswith("design.") and _block_values(blocks, key)
        }
        if not design:
            issues.append(_issue(
                "structure",
                "Task %s requires Design decisions" % task_slug,
                section["line"],
                task_prefix + ".design",
            ))
        parsed_acceptance = []
        for source_index, (number, raw) in enumerate(blocks.get("acceptance", [])):
            acceptance_field = "%s.acceptance[%d]" % (task_prefix, source_index)
            locations[acceptance_field] = number
            _locate(context, number, acceptance_field)
            criterion = _parse_acceptance(raw, number, acceptance_field, issues)
            if criterion is not None:
                parsed_acceptance.append(criterion)
        task = {
            "code": task_names[task_slug],
            "title": str(section["title"]).split(":", 1)[1].strip(),
            "outcome": (_block_values(blocks, "outcome") or [""])[0],
            "scope": {
                "in": _block_values(blocks, "scope_in"),
                "out": _block_values(blocks, "scope_out"),
            },
            "prerequisites": [],
            "inputs": [],
            "outputs": outputs,
            "ownership": {
                "write_paths": ownership,
                "shared_exclusive": _block_values(blocks, "exclusive"),
            },
            "worker": worker,
            "difficulty": difficulty,
            "workload": workload,
            "verification": verification,
            "requirements": task_requirement_codes,
            "risks": risks,
            "nodes": nodes,
            "design": design,
            "acceptance": [],
            "focused_regression": {
                "commands": [
                    command
                    for value in _block_values(blocks, "regression.commands")
                    for command in _regression_values("commands", value)
                ],
                "paths": plain_regression_paths(_block_values(blocks, "regression.paths")),
            },
        }
        if not _block_values(blocks, "outcome"):
            issues.append(_issue(
                "structure",
                "Task %s requires Outcome" % task_slug,
                section["line"],
                task_prefix + ".outcome",
            ))
        if not _block_values(blocks, "scope_in"):
            issues.append(_issue(
                "structure",
                "Task %s requires Scope in" % task_slug,
                section["line"],
                task_prefix + ".scope.in",
            ))
        if not outputs:
            issues.append(_issue(
                "structure",
                "Task %s requires Outputs" % task_slug,
                section["line"],
                task_prefix + ".outputs",
            ))
        if not nodes:
            issues.append(_issue(
                "structure",
                "Task %s requires Nodes" % task_slug,
                section["line"],
                task_prefix + ".nodes",
            ))
        if not _block_values(blocks, "regression.commands"):
            issues.append(_issue(
                "structure",
                "Task %s requires Regression Commands" % task_slug,
                section["line"],
                task_prefix + ".focused_regression.commands",
            ))
        if not _block_values(blocks, "regression.paths"):
            issues.append(_issue(
                "structure",
                "Task %s requires Regression Paths" % task_slug,
                section["line"],
                task_prefix + ".focused_regression.paths",
            ))
        parsed_tasks.append(task)
        parsed_metadata.append({
            "slug": task_slug,
            "prefix": task_prefix,
            "line": section["line"],
            "acceptance": parsed_acceptance,
        })

    for task, metadata in zip(parsed_tasks, parsed_metadata):
        task_slug = metadata["slug"]
        task_prefix = metadata["prefix"]
        task_line = metadata["line"]
        _locate(context, task_line, task_prefix)
        owned_codes = list(task["requirements"]) + [item["code"] for item in task["outputs"]]
        acceptance = metadata["acceptance"]
        if not acceptance:
            issues.append(_issue(
                "structure",
                "Task %s requires Acceptance" % task_slug,
                task_line,
                task_prefix + ".acceptance",
            ))
        for criterion_index, criterion in enumerate(acceptance):
            criterion_line = criterion["line"]
            criterion_field = "%s.acceptance[%d]" % (task_prefix, criterion_index)
            locations[criterion_field] = criterion_line
            _locate(context, criterion_line, criterion_field)
            names = criterion.pop("cover_names")
            criterion.pop("line")
            covers: list[str] = []
            if names:
                for name in names:
                    slug = _slug(name)
                    code = requirement_codes.get(slug) or output_codes_by_task.get(task_slug, {}).get(slug)
                    if code is None:
                        issues.append(_issue(
                            "structure",
                            "unknown Acceptance cover %s" % name,
                            criterion_line,
                            criterion_field + ".covers",
                        ))
                    elif code not in covers:
                        covers.append(code)
            elif len(acceptance) == 1:
                covers = owned_codes
            else:
                issues.append(_issue(
                    "structure",
                    "multiple Acceptance criteria require Covers",
                    criterion_line,
                    criterion_field + ".covers",
                ))
            acceptance_counter += 1
            task["acceptance"].append({"code": "AC-%03d" % acceptance_counter, "covers": covers, **criterion})

    regression_section = known.get("full regression")
    if regression_section is None:
        locations["spec.full_regression"] = 1
        full_regression = deepcopy(fallback.get("full_regression", {"commands": [], "paths": []}))
        sections_from_plan.append("full_regression")
    else:
        locations["spec.full_regression"] = regression_section["line"]
        _locate(context, regression_section["line"], "spec.full_regression")
        full_regression = _parse_regression(
            regression_section["body"],
            regression_section["line"],
            issues,
            unmapped,
            locations,
            "Full regression",
            "spec.full_regression",
        )

    spec = {
        "requirements": requirements,
        "architecture": architecture,
        "tasks": parsed_tasks,
        "full_regression": full_regression,
    }
    issues.extend(_content_issues(spec, locations))
    unique: list[dict[str, Any]] = []
    seen_issues: set[tuple[Any, ...]] = set()
    for issue in issues:
        key = (issue.get("kind"), issue.get("message"), issue.get("line"), issue.get("field"))
        if key not in seen_issues:
            seen_issues.add(key)
            unique.append(issue)
    return {
        "spec": spec,
        "issues": unique,
        "unmapped": unmapped,
        "sections_from_plan": sections_from_plan,
        "locations": locations,
        "compiled_spec_digest": sha256_value(spec),
    }
