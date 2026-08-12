"""Deterministic single-document human projection of a Delivery Plan.

`Plan.json` is the only editable semantic source. `Plan.md` is a render-only
review projection: it is never parsed back, so no managed blocks, per-document
receipts, or reverse-sync rules exist.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from ..domain.models import PLAN_DOCUMENT
from .workspace import write_text


def _lines(values: Any) -> list[str]:
    return [str(item) for item in values] if isinstance(values, list) else []


def _bullets(values: Any, indent: str = "") -> list[str]:
    return ["%s- %s" % (indent, value) for value in _lines(values)] or ["%s- none" % indent]


def _section(title: str) -> list[str]:
    return ["", "## %s" % title, ""]


def _intent(plan: Mapping[str, Any]) -> list[str]:
    intent = plan.get("intent", {}) if isinstance(plan.get("intent"), Mapping) else {}
    scope = intent.get("scope", {}) if isinstance(intent.get("scope"), Mapping) else {}
    lines = _section("Intent")
    lines.append("**Goal**: %s" % intent.get("goal", ""))
    lines.extend(["", "**In scope**"])
    lines.extend(_bullets(scope.get("in")))
    lines.extend(["", "**Out of scope**"])
    lines.extend(_bullets(scope.get("out")))
    lines.extend(["", "**Success**"])
    lines.extend(_bullets(intent.get("success")))
    lines.extend(["", "**Risk boundary**"])
    lines.extend(_bullets(intent.get("risk_boundary")))
    return lines


def _decisions(plan: Mapping[str, Any]) -> list[str]:
    dossier = plan.get("dossier", {}) if isinstance(plan.get("dossier"), Mapping) else {}
    ledger = plan.get("ledger", {}) if isinstance(plan.get("ledger"), Mapping) else {}
    explicit = {
        str(record.get("source")): record
        for record in ledger.get("user_decided", [])
        if isinstance(record, Mapping)
    }
    defaulted = {
        str(record.get("source")): record
        for record in ledger.get("defaulted", [])
        if isinstance(record, Mapping)
    }
    lines = _section("Decisions")
    lines.append("Dossier status: %s" % dossier.get("status"))
    questions = dossier.get("questions") if isinstance(dossier.get("questions"), list) else []
    if not questions:
        lines.extend(["", "No non-discoverable user decision was required."])
    for question in questions:
        if not isinstance(question, Mapping):
            continue
        code = str(question.get("code"))
        origin = "user selection" if code in explicit else ("applied default" if code in defaulted else "unresolved")
        lines.extend(["", "### %s %s" % (code, question.get("question"))])
        lines.extend(["", "Context: %s" % question.get("context"), "", "Resolution: %s (%s)" % (question.get("selected"), origin), ""])
        for option in question.get("options", []) if isinstance(question.get("options"), list) else []:
            if not isinstance(option, Mapping):
                continue
            marker = "x" if option.get("id") == question.get("selected") else " "
            lines.append("- [%s] `%s` %s" % (marker, option.get("id"), option.get("label")))
            lines.extend(_bullets(option.get("effects"), indent="  "))
    observed = ledger.get("observed") if isinstance(ledger.get("observed"), list) else []
    lines.extend(["", "### Observed repository facts", ""])
    if not observed:
        lines.append("- none")
    for fact in observed:
        if isinstance(fact, Mapping):
            lines.append("- %s (source: %s)" % (fact.get("fact"), fact.get("source")))
    unresolved = ledger.get("unresolved") if isinstance(ledger.get("unresolved"), list) else []
    if unresolved:
        lines.extend(["", "### Unresolved", ""])
        for item in unresolved:
            if isinstance(item, Mapping):
                lines.append("- %s %s (impact: %s)" % (item.get("code"), item.get("statement"), item.get("impact")))
    return lines


def _requirements(spec: Mapping[str, Any]) -> list[str]:
    lines = _section("Requirements")
    requirements = spec.get("requirements") if isinstance(spec.get("requirements"), list) else []
    if not requirements:
        lines.append("None recorded yet.")
        return lines
    lines.extend(["| Code | Statement | Sources |", "| --- | --- | --- |"])
    for requirement in requirements:
        if isinstance(requirement, Mapping):
            lines.append(
                "| %s | %s | %s |"
                % (
                    requirement.get("code"),
                    requirement.get("statement"),
                    ", ".join(_lines(requirement.get("source_refs"))),
                )
            )
    return lines


def _architecture(spec: Mapping[str, Any]) -> list[str]:
    architecture = spec.get("architecture", {}) if isinstance(spec.get("architecture"), Mapping) else {}
    lines = _section("Architecture")
    lines.append(str(architecture.get("summary", "")))
    lines.append("")
    lines.extend(_bullets(architecture.get("notes")))
    return lines


def _task(task: Mapping[str, Any]) -> list[str]:
    scope = task.get("scope", {}) if isinstance(task.get("scope"), Mapping) else {}
    ownership = task.get("ownership", {}) if isinstance(task.get("ownership"), Mapping) else {}
    lines = ["", "### %s %s" % (task.get("code"), task.get("title")), ""]
    lines.append(
        "Tier: %s · Workload: %s · Verification: %s · Frontier: parallel"
        % (task.get("difficulty"), task.get("workload"), task.get("verification"))
    )
    lines.extend(["", "Outcome: %s" % task.get("outcome"), ""])
    lines.append("Risks: %s" % (", ".join(_lines(task.get("risks"))) or "none"))
    lines.append("Requirements: %s" % (", ".join(_lines(task.get("requirements"))) or "none"))
    lines.append("Writes: %s" % (", ".join(_lines(ownership.get("write_paths"))) or "none"))
    exclusive = _lines(ownership.get("shared_exclusive"))
    if exclusive:
        lines.append("Exclusive resources: %s" % ", ".join(exclusive))
    lines.extend(["", "In scope"])
    lines.extend(_bullets(scope.get("in")))
    lines.extend(["", "Out of scope"])
    lines.extend(_bullets(scope.get("out")))
    outputs = task.get("outputs") if isinstance(task.get("outputs"), list) else []
    if outputs:
        lines.extend(["", "Outputs"])
        for item in outputs:
            if isinstance(item, Mapping):
                lines.append(
                    "- %s %s (`%s`): %s"
                    % (item.get("code"), item.get("title"), item.get("artifact"), item.get("guarantee"))
                )
    nodes = task.get("nodes") if isinstance(task.get("nodes"), list) else []
    if nodes:
        lines.extend(["", "Internal Node graph"])
        for node in nodes:
            if isinstance(node, Mapping):
                prerequisites = ", ".join(_lines(node.get("prerequisites"))) or "none"
                lines.append(
                    "- %s %s · after: %s · %s"
                    % (node.get("code"), node.get("title"), prerequisites, node.get("outcome"))
                )
    design = task.get("design") if isinstance(task.get("design"), Mapping) else {}
    if design:
        lines.extend(["", "Design"])
        for key in sorted(design):
            lines.append("- %s" % key)
            lines.extend(_bullets(design.get(key), indent="  "))
    acceptance = task.get("acceptance") if isinstance(task.get("acceptance"), list) else []
    if acceptance:
        lines.extend(["", "Acceptance"])
        for criterion in acceptance:
            if not isinstance(criterion, Mapping):
                continue
            evidence = criterion.get("evidence", {}) if isinstance(criterion.get("evidence"), Mapping) else {}
            lines.append("- %s covers %s" % (criterion.get("code"), ", ".join(_lines(criterion.get("covers")))))
            lines.append("  - Given %s" % criterion.get("given"))
            lines.append("  - When %s" % criterion.get("when"))
            lines.append("  - Then %s" % criterion.get("then"))
            lines.append("  - Oracle: %s" % criterion.get("oracle"))
            lines.append("  - Evidence: %s from %s" % (evidence.get("type"), evidence.get("source")))
    regression = task.get("focused_regression") if isinstance(task.get("focused_regression"), Mapping) else {}
    if regression:
        lines.extend(["", "Focused regression"])
        for command in _lines(regression.get("commands")):
            lines.append("- `%s`" % command)
        lines.append("- paths: %s" % (", ".join(_lines(regression.get("paths"))) or "none"))
    return lines


def _tasks(spec: Mapping[str, Any]) -> list[str]:
    lines = _section("Tasks")
    tasks: Sequence[Any] = spec.get("tasks") if isinstance(spec.get("tasks"), list) else []
    if not tasks:
        lines.append("None recorded yet.")
        return lines
    lines.append("Every Task belongs to the same mutually independent parallel frontier.")
    for task in tasks:
        if isinstance(task, Mapping):
            lines.extend(_task(task))
    return lines


def _validation(spec: Mapping[str, Any]) -> list[str]:
    regression = spec.get("full_regression", {}) if isinstance(spec.get("full_regression"), Mapping) else {}
    lines = _section("Full regression")
    lines.append("Run inside the sole Reviewer session after every repair is integrated.")
    lines.append("")
    for command in _lines(regression.get("commands")) or ["none"]:
        lines.append("- `%s`" % command)
    lines.append("- paths: %s" % (", ".join(_lines(regression.get("paths"))) or "none"))
    return lines


def render_document(plan: Mapping[str, Any]) -> str:
    """Return the deterministic Markdown projection of one Plan."""

    sealed = plan.get("lifecycle", {}).get("sealed")
    revision = sealed.get("revision") if isinstance(sealed, Mapping) else None
    spec = plan.get("spec", {}) if isinstance(plan.get("spec"), Mapping) else {}
    lines = [
        "# %s %s" % (plan.get("code"), plan.get("title")),
        "",
        "Phase: %s · Revision: %s" % (plan.get("phase"), revision if revision is not None else "unsealed"),
        "",
        "This document is a render-only projection of `Plan.json`. Edit `Plan.json`; never edit this file.",
    ]
    lines.extend(_intent(plan))
    lines.extend(_decisions(plan))
    lines.extend(_requirements(spec))
    lines.extend(_architecture(spec))
    lines.extend(_tasks(spec))
    lines.extend(_validation(spec))
    lines.append("")
    return "\n".join(lines)


def render_plan(plan_dir: Path, plan: Mapping[str, Any]) -> str:
    document = render_document(plan)
    write_text(plan_dir / PLAN_DOCUMENT, document)
    return document
