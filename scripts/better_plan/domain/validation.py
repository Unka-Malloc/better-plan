"""Semantic and structural validation for the Better Plan v3 protocol.

The validator enforces only the guarantees that keep a delivery executable after
context loss: an honest dependency graph, provably safe parallelism, executable
acceptance for every requirement and handoff, immutable authorization bindings,
and a hard privacy boundary. Bookkeeping that an agent would otherwise spend its
attention satisfying is deliberately absent.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from .models import (
    ABSOLUTE_PATH_PATTERN,
    AUTHORIZED_PHASES,
    CHECKPOINTS_SCHEMA,
    DELIVERY_STATUSES,
    DISPATCH_PHASES,
    ELEVATED_RISKS,
    MANIFEST_SCHEMA,
    NETWORK_ENDPOINT_PATTERN,
    OPTION_ID_PATTERN,
    PLAN_PHASES,
    PLAN_SCHEMA,
    SENSITIVE_TOKEN_PATTERN,
    SHA256_PATTERN,
    TASK_STATUSES,
    VALID_AUTHORIZATION_SOURCES,
    VALID_DIFFICULTIES,
    VALID_RISKS,
    VALID_VERIFICATIONS,
    Issue,
    is_code,
    is_relative_workspace_path,
    normalize_workspace_path,
    safe_summary_issue,
    semantic_digest,
)


TASK_REQUIRED_FIELDS = {
    "code",
    "title",
    "outcome",
    "scope",
    "prerequisites",
    "ownership",
    "difficulty",
    "verification",
    "requirements",
    "risks",
}
TASK_DESIGN_FIELDS = {"inputs", "outputs", "design", "acceptance", "focused_regression"}
TASK_ALLOWED_FIELDS = TASK_REQUIRED_FIELDS | TASK_DESIGN_FIELDS
LIFECYCLE_REQUIRED_FIELDS = {
    "sealed",
    "designer_session",
    "reviewer_session",
    "authorization",
    "continuation_receipts",
}
LIFECYCLE_OPTIONAL_FIELDS = {"continuation_session", "verification"}


def _issue(path: Path, prefix: str, message: str) -> Issue:
    return Issue(path, "%s: %s" % (prefix, message))


def _mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _string_list(value: Any, allow_empty: bool = True) -> bool:
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(isinstance(item, str) and bool(item.strip()) for item in value)
    )


def _safe_lines(value: Any, allow_empty: bool = False) -> bool:
    return _string_list(value, allow_empty) and all(
        safe_summary_issue(item) is None for item in value
    )


def _relative_paths(value: Any, allow_empty: bool = True) -> bool:
    return isinstance(value, list) and (allow_empty or bool(value)) and all(
        is_relative_workspace_path(item) for item in value
    )


def _unknown_fields(path: Path, prefix: str, value: Mapping[str, Any], allowed: set[str]) -> list[Issue]:
    unknown = set(value) - allowed
    return [_issue(path, prefix, "unknown fields %s" % ", ".join(sorted(unknown)))] if unknown else []


def _privacy_issues(path: Path, value: Any, prefix: str = "plan") -> list[Issue]:
    """Reject absolute local paths, runtime endpoints, and secret-shaped text."""

    issues: list[Issue] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            issues.extend(_privacy_issues(path, child, "%s.%s" % (prefix, key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            issues.extend(_privacy_issues(path, child, "%s[%d]" % (prefix, index)))
    elif isinstance(value, str):
        if ABSOLUTE_PATH_PATTERN.search(value):
            issues.append(_issue(path, prefix, "must not expose an absolute local path"))
        if NETWORK_ENDPOINT_PATTERN.search(value):
            issues.append(_issue(path, prefix, "must not expose a runtime endpoint"))
        if SENSITIVE_TOKEN_PATTERN.search(value):
            issues.append(_issue(path, prefix, "must not contain secret-shaped data"))
    return issues


def dependency_cycle(graph: Mapping[str, Sequence[str]]) -> list[str] | None:
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        if node in visiting:
            return stack[stack.index(node):] + [node]
        if node in visited:
            return None
        visiting.add(node)
        stack.append(node)
        for prerequisite in graph.get(node, []):
            found = visit(prerequisite)
            if found is not None:
                return found
        stack.pop()
        visiting.discard(node)
        visited.add(node)
        return None

    for node in graph:
        found = visit(node)
        if found is not None:
            return found
    return None


def _reachable(graph: Mapping[str, Sequence[str]], start: str, target: str) -> bool:
    pending = list(graph.get(start, []))
    seen: set[str] = set()
    while pending:
        current = pending.pop()
        if current == target:
            return True
        if current in seen:
            continue
        seen.add(current)
        pending.extend(graph.get(current, []))
    return False


def _paths_overlap(left: str, right: str) -> bool:
    a = normalize_workspace_path(left).rstrip("/")
    b = normalize_workspace_path(right).rstrip("/")
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def validate_manifest_document(path: Path, data: Any) -> list[Issue]:
    issues: list[Issue] = []
    if not _mapping(data):
        return [_issue(path, "manifest", "top-level value must be an object")]
    if data.get("schema") != MANIFEST_SCHEMA:
        issues.append(_issue(path, "manifest.schema", "unsupported generation"))
    issues.extend(_unknown_fields(path, "manifest", data, {"schema", "plans"}))
    plans = data.get("plans")
    if not isinstance(plans, list):
        return issues + [_issue(path, "manifest.plans", "must be an array")]
    codes: set[str] = set()
    directories: set[str] = set()
    for index, entry in enumerate(plans):
        prefix = "plans[%d]" % index
        if not _mapping(entry):
            issues.append(_issue(path, prefix, "must be an object"))
            continue
        required = {"code", "title", "directory", "plan"}
        missing = required - set(entry)
        if missing:
            issues.append(_issue(path, prefix, "missing fields %s" % ", ".join(sorted(missing))))
            continue
        issues.extend(_unknown_fields(path, prefix, entry, required | {"checkpoints"}))
        code = entry.get("code")
        directory = entry.get("directory")
        if not is_code(code, "PLAN") or code in codes:
            issues.append(_issue(path, prefix + ".code", "must be a unique PLAN-* code"))
        else:
            codes.add(str(code))
        if safe_summary_issue(entry.get("title")) is not None:
            issues.append(_issue(path, prefix + ".title", "must be a concrete safe summary"))
        if not is_relative_workspace_path(directory) or directory in directories:
            issues.append(_issue(path, prefix + ".directory", "must be a unique safe relative path"))
        else:
            directories.add(str(directory))
        if entry.get("plan") != "%s/Plan.json" % directory:
            issues.append(_issue(path, prefix + ".plan", "must equal %s/Plan.json" % directory))
        checkpoints = entry.get("checkpoints")
        if checkpoints is not None and checkpoints != "%s/Checkpoints.json" % directory:
            issues.append(_issue(path, prefix + ".checkpoints", "must use the plan directory"))
    return issues


def _validate_dossier(path: Path, dossier: Any) -> list[Issue]:
    issues: list[Issue] = []
    if not _mapping(dossier):
        return [_issue(path, "dossier", "must be an object")]
    issues.extend(_unknown_fields(path, "dossier", dossier, {"status", "questions"}))
    status = dossier.get("status")
    if status not in {"not_required", "draft", "resolved"}:
        issues.append(_issue(path, "dossier.status", "invalid status"))
    questions = dossier.get("questions")
    if not isinstance(questions, list):
        return issues + [_issue(path, "dossier.questions", "must be an array")]
    if status == "not_required" and questions:
        issues.append(_issue(path, "dossier", "a not_required Dossier must be empty"))
    seen: set[str] = set()
    for index, question in enumerate(questions):
        prefix = "dossier.questions[%d]" % index
        if not _mapping(question):
            issues.append(_issue(path, prefix, "must be an object"))
            continue
        required = {"code", "question", "context", "resolves", "options", "recommended", "default"}
        missing = required - set(question)
        if missing:
            issues.append(_issue(path, prefix, "missing fields %s" % ", ".join(sorted(missing))))
            continue
        issues.extend(_unknown_fields(path, prefix, question, required | {"selected"}))
        code = question.get("code")
        if not is_code(code, "Q") or code in seen:
            issues.append(_issue(path, prefix + ".code", "must be a unique Q-* code"))
        else:
            seen.add(str(code))
        for field in ("question", "context"):
            if safe_summary_issue(question.get(field)) is not None:
                issues.append(_issue(path, prefix + "." + field, "must be a concrete safe summary"))
        resolves = question.get("resolves")
        if not isinstance(resolves, list) or not resolves or any(
            not is_code(item, "DEC") for item in resolves
        ):
            issues.append(_issue(path, prefix + ".resolves", "must name the DEC-* decisions it closes"))
        options = question.get("options")
        if not isinstance(options, list) or not 2 <= len(options) <= 6:
            issues.append(_issue(path, prefix + ".options", "must contain 2 through 6 options"))
            continue
        option_ids: set[str] = set()
        for option_index, option in enumerate(options):
            option_prefix = "%s.options[%d]" % (prefix, option_index)
            if not _mapping(option):
                issues.append(_issue(path, option_prefix, "must be an object"))
                continue
            issues.extend(_unknown_fields(path, option_prefix, option, {"id", "label", "effects"}))
            option_id = option.get("id")
            if not isinstance(option_id, str) or OPTION_ID_PATTERN.fullmatch(option_id) is None or option_id in option_ids:
                issues.append(_issue(path, option_prefix + ".id", "must be a unique lowercase option id"))
            else:
                option_ids.add(option_id)
            if safe_summary_issue(option.get("label")) is not None:
                issues.append(_issue(path, option_prefix + ".label", "must be a concrete safe summary"))
            if not _safe_lines(option.get("effects")):
                issues.append(
                    _issue(path, option_prefix + ".effects", "must state what this option freezes")
                )
        for field in ("recommended", "default"):
            if question.get(field) not in option_ids:
                issues.append(_issue(path, prefix + "." + field, "must reference an option"))
        selected = question.get("selected")
        if selected is not None and selected not in option_ids:
            issues.append(_issue(path, prefix + ".selected", "must reference an option"))
        if status == "resolved" and selected is None:
            issues.append(_issue(path, prefix + ".selected", "a resolved Dossier requires a selection or applied default"))
    return issues


def _validate_ledger(path: Path, ledger: Any, dossier: Any) -> list[Issue]:
    issues: list[Issue] = []
    if not _mapping(ledger) or any(
        not isinstance(ledger.get(key), list)
        for key in ("observed", "user_decided", "defaulted", "unresolved")
    ):
        return [_issue(path, "plan.ledger", "must contain four ledger arrays")]
    issues.extend(
        _unknown_fields(path, "plan.ledger", ledger, {"observed", "user_decided", "defaulted", "unresolved"})
    )
    for index, fact in enumerate(ledger.get("observed", [])):
        prefix = "ledger.observed[%d]" % index
        if not _mapping(fact) or any(
            safe_summary_issue(fact.get(field)) is not None for field in ("fact", "source")
        ):
            issues.append(_issue(path, prefix, "requires a safe fact and its repository source"))
        else:
            issues.extend(_unknown_fields(path, prefix, fact, {"fact", "source"}))
    question_codes = {
        str(item.get("code"))
        for item in (dossier.get("questions", []) if _mapping(dossier) else [])
        if _mapping(item)
    }
    sources: set[str] = set()
    for name in ("user_decided", "defaulted"):
        for index, record in enumerate(ledger.get(name, [])):
            prefix = "ledger.%s[%d]" % (name, index)
            if (
                not _mapping(record)
                or not is_code(record.get("source"), "Q")
                or not isinstance(record.get("option"), str)
                or not record.get("option")
                or not isinstance(record.get("resolves"), list)
                or not record.get("resolves")
                or not _safe_lines(record.get("effects"))
            ):
                issues.append(_issue(path, prefix, "requires a Q-* source, chosen option, resolved decisions, and effects"))
                continue
            issues.extend(_unknown_fields(path, prefix, record, {"source", "option", "resolves", "effects"}))
            source = str(record.get("source"))
            if source in sources:
                issues.append(_issue(path, prefix + ".source", "duplicate decision record"))
            sources.add(source)
            if question_codes and source not in question_codes:
                issues.append(_issue(path, prefix + ".source", "must originate from this Dossier"))
    unresolved: set[str] = set()
    for index, item in enumerate(ledger.get("unresolved", [])):
        prefix = "ledger.unresolved[%d]" % index
        if not _mapping(item) or not is_code(item.get("code"), "DEC") or any(
            safe_summary_issue(item.get(field)) is not None for field in ("statement", "impact")
        ):
            issues.append(_issue(path, prefix, "requires a DEC-* code, statement, and impact"))
            continue
        issues.extend(_unknown_fields(path, prefix, item, {"code", "statement", "impact"}))
        if item.get("code") in unresolved:
            issues.append(_issue(path, prefix + ".code", "duplicate unresolved decision"))
        unresolved.add(str(item.get("code")))
    return issues


def _validate_task(path: Path, task: Any, index: int, require_design: bool) -> list[Issue]:
    prefix = "spec.tasks[%d]" % index
    if not _mapping(task):
        return [_issue(path, prefix, "must be an object")]
    issues: list[Issue] = []
    required = TASK_REQUIRED_FIELDS | (TASK_DESIGN_FIELDS if require_design else set())
    missing = required - set(task)
    if missing:
        return [_issue(path, prefix, "missing fields %s" % ", ".join(sorted(missing)))]
    issues.extend(_unknown_fields(path, prefix, task, TASK_ALLOWED_FIELDS))
    label = task.get("code") if is_code(task.get("code"), "TASK") else prefix
    if not is_code(task.get("code"), "TASK"):
        issues.append(_issue(path, prefix + ".code", "must be a TASK-* code"))
    for field in ("title", "outcome"):
        if safe_summary_issue(task.get(field)) is not None:
            issues.append(_issue(path, "%s.%s" % (label, field), "must be a concrete safe summary"))
    scope = task.get("scope")
    if not _mapping(scope) or not _safe_lines(scope.get("in")) or not _safe_lines(scope.get("out")):
        issues.append(_issue(path, "%s.scope" % label, "must contain non-empty in/out arrays"))
    else:
        issues.extend(_unknown_fields(path, "%s.scope" % label, scope, {"in", "out"}))
        if set(scope.get("in", [])) & set(scope.get("out", [])):
            issues.append(_issue(path, "%s.scope" % label, "in/out boundaries must not overlap"))
    if not isinstance(task.get("prerequisites"), list) or any(
        not is_code(item, "TASK") for item in task.get("prerequisites", [])
    ):
        issues.append(_issue(path, "%s.prerequisites" % label, "must contain TASK-* codes"))
    if not isinstance(task.get("requirements"), list) or any(
        not is_code(item, "REQ") for item in task.get("requirements", [])
    ):
        issues.append(_issue(path, "%s.requirements" % label, "must contain REQ-* codes"))
    risks = task.get("risks")
    if not isinstance(risks, list) or any(item not in VALID_RISKS for item in risks):
        issues.append(_issue(path, "%s.risks" % label, "must contain known risk tags"))
    elif len(set(risks)) != len(risks):
        issues.append(_issue(path, "%s.risks" % label, "must not repeat a risk tag"))
    if task.get("difficulty") not in VALID_DIFFICULTIES:
        issues.append(_issue(path, "%s.difficulty" % label, "must be standard or complex"))
    elif isinstance(risks, list) and set(risks) & ELEVATED_RISKS and task.get("difficulty") != "complex":
        issues.append(_issue(path, "%s.difficulty" % label, "an elevated risk tag requires the complex tier"))
    if task.get("verification") not in VALID_VERIFICATIONS:
        issues.append(_issue(path, "%s.verification" % label, "must be code, visual, or hybrid"))
    ownership = task.get("ownership")
    if not _mapping(ownership):
        issues.append(_issue(path, "%s.ownership" % label, "must be an object"))
    else:
        issues.extend(_unknown_fields(path, "%s.ownership" % label, ownership, {"write_paths", "shared_exclusive"}))
        if not _relative_paths(ownership.get("write_paths"), allow_empty=False):
            issues.append(_issue(path, "%s.ownership.write_paths" % label, "must contain safe relative paths"))
        shared = ownership.get("shared_exclusive")
        if not _safe_lines(shared, allow_empty=True):
            issues.append(_issue(path, "%s.ownership.shared_exclusive" % label, "must contain safe resource names"))
        elif isinstance(shared, list) and len(set(shared)) != len(shared):
            issues.append(_issue(path, "%s.ownership.shared_exclusive" % label, "must not repeat a resource"))
    design = task.get("design")
    if design is not None:
        if not _mapping(design) or not design:
            issues.append(_issue(path, "%s.design" % label, "must be a non-empty object of design decisions"))
        else:
            for key, value in design.items():
                if not isinstance(key, str) or OPTION_ID_PATTERN.fullmatch(key) is None:
                    issues.append(_issue(path, "%s.design" % label, "design keys must be lowercase slugs"))
                elif not _safe_lines(value):
                    issues.append(_issue(path, "%s.design.%s" % (label, key), "must be a non-empty array of concrete safe decisions"))
    outputs = task.get("outputs")
    if outputs is not None:
        if not isinstance(outputs, list):
            issues.append(_issue(path, "%s.outputs" % label, "must be an array"))
        else:
            owned_paths = (
                ownership.get("write_paths", []) or [] if _mapping(ownership) else []
            )
            for output_index, output in enumerate(outputs):
                output_prefix = "%s.outputs[%d]" % (label, output_index)
                if not _mapping(output) or not is_code(output.get("code"), "OUT"):
                    issues.append(_issue(path, output_prefix, "must contain an OUT-* code"))
                    continue
                issues.extend(_unknown_fields(path, output_prefix, output, {"code", "title", "artifact", "guarantee"}))
                artifact = output.get("artifact")
                if (
                    safe_summary_issue(output.get("title")) is not None
                    or not is_relative_workspace_path(artifact)
                    or safe_summary_issue(output.get("guarantee")) is not None
                ):
                    issues.append(_issue(path, output_prefix, "requires a title, relative artifact, and guarantee"))
                elif owned_paths and not any(
                    isinstance(owned, str) and _paths_overlap(str(artifact), owned)
                    for owned in owned_paths
                ):
                    issues.append(
                        _issue(path, output_prefix, "artifact must fall inside this Task's write ownership")
                    )
    inputs = task.get("inputs")
    if inputs is not None and not isinstance(inputs, list):
        issues.append(_issue(path, "%s.inputs" % label, "must be an array"))
    elif isinstance(inputs, list):
        for input_index, item in enumerate(inputs):
            input_prefix = "%s.inputs[%d]" % (label, input_index)
            if (
                not _mapping(item)
                or not is_code(item.get("from"), "TASK")
                or not is_code(item.get("output"), "OUT")
                or safe_summary_issue(item.get("guarantee")) is not None
            ):
                issues.append(_issue(path, input_prefix, "requires from, output, and guarantee"))
            else:
                issues.extend(_unknown_fields(path, input_prefix, item, {"from", "output", "guarantee"}))
    acceptance = task.get("acceptance")
    if acceptance is not None:
        if not isinstance(acceptance, list) or (require_design and not acceptance):
            issues.append(_issue(path, "%s.acceptance" % label, "must be a non-empty array"))
        elif isinstance(acceptance, list):
            for criterion_index, criterion in enumerate(acceptance):
                criterion_prefix = "%s.acceptance[%d]" % (label, criterion_index)
                if not _mapping(criterion) or not is_code(criterion.get("code"), "AC"):
                    issues.append(_issue(path, criterion_prefix, "must contain an AC-* code"))
                    continue
                issues.extend(
                    _unknown_fields(
                        path,
                        criterion_prefix,
                        criterion,
                        {"code", "covers", "given", "when", "then", "oracle", "evidence"},
                    )
                )
                if any(
                    safe_summary_issue(criterion.get(field)) is not None
                    for field in ("given", "when", "then", "oracle")
                ):
                    issues.append(_issue(path, criterion_prefix, "requires safe Given/When/Then and an exact oracle"))
                if not _safe_lines(criterion.get("covers")):
                    issues.append(_issue(path, criterion_prefix + ".covers", "must name what it proves"))
                evidence = criterion.get("evidence")
                if not _mapping(evidence) or any(
                    safe_summary_issue(evidence.get(field)) is not None for field in ("type", "source")
                ):
                    issues.append(_issue(path, criterion_prefix + ".evidence", "requires a concrete type and source"))
                else:
                    issues.extend(_unknown_fields(path, criterion_prefix + ".evidence", evidence, {"type", "source"}))
    for field in ("focused_regression",):
        regression = task.get(field)
        if regression is None:
            continue
        if not _mapping(regression) or not _string_list(regression.get("commands"), False) or not _relative_paths(regression.get("paths"), False):
            issues.append(_issue(path, "%s.%s" % (label, field), "must contain non-empty commands and relative paths"))
        else:
            issues.extend(_unknown_fields(path, "%s.%s" % (label, field), regression, {"commands", "paths"}))
    return issues


def validate_plan_document(path: Path, plan: Any) -> list[Issue]:
    """Validate the structural contract that every write must satisfy."""

    issues: list[Issue] = []
    if not _mapping(plan):
        return [_issue(path, "plan", "top-level value must be an object")]
    issues.extend(_privacy_issues(path, plan))
    if plan.get("schema") != PLAN_SCHEMA:
        issues.append(_issue(path, "plan.schema", "unsupported generation"))
    required = {"schema", "code", "title", "directory", "phase", "intent", "ledger", "dossier", "spec", "lifecycle"}
    missing = required - set(plan)
    if missing:
        return issues + [_issue(path, "plan", "missing fields %s" % ", ".join(sorted(missing)))]
    issues.extend(_unknown_fields(path, "plan", plan, required))
    if not is_code(plan.get("code"), "PLAN"):
        issues.append(_issue(path, "plan.code", "must be a PLAN-* code"))
    if safe_summary_issue(plan.get("title")) is not None:
        issues.append(_issue(path, "plan.title", "must be a concrete safe summary"))
    if not is_relative_workspace_path(plan.get("directory")):
        issues.append(_issue(path, "plan.directory", "must be a safe relative path"))
    phase = plan.get("phase")
    if phase not in PLAN_PHASES:
        issues.append(_issue(path, "plan.phase", "invalid lifecycle phase"))
    issues.extend(_validate_intent(path, plan.get("intent")))
    issues.extend(_validate_ledger(path, plan.get("ledger"), plan.get("dossier")))
    issues.extend(_validate_dossier(path, plan.get("dossier")))
    spec = plan.get("spec")
    if not _mapping(spec):
        return issues + [_issue(path, "plan.spec", "must be an object")]
    issues.extend(
        _unknown_fields(path, "plan.spec", spec, {"requirements", "architecture", "tasks", "full_regression"})
    )
    tasks = spec.get("tasks") if isinstance(spec.get("tasks"), list) else None
    if tasks is None:
        issues.append(_issue(path, "spec.tasks", "must be an array"))
        tasks = []
    require_design = phase in AUTHORIZED_PHASES
    for index, task in enumerate(tasks):
        issues.extend(_validate_task(path, task, index, require_design))
    issues.extend(_validate_graph(path, tasks))
    issues.extend(_validate_coverage(path, tasks))
    issues.extend(_validate_lifecycle(path, plan))
    return issues


def _validate_intent(path: Path, intent: Any) -> list[Issue]:
    if not _mapping(intent) or not _mapping(intent.get("scope")) or not _mapping(intent.get("autonomy")):
        return [_issue(path, "plan.intent", "must contain scope and autonomy")]
    issues = _unknown_fields(path, "plan.intent", intent, {"goal", "scope", "success", "risk_boundary", "autonomy"})
    issues.extend(_unknown_fields(path, "plan.intent.scope", intent["scope"], {"in", "out"}))
    issues.extend(
        _unknown_fields(
            path,
            "plan.intent.autonomy",
            intent["autonomy"],
            {"allow_in_scope_revision", "allow_reviewer_repairs", "forbid_mid_execution_questions", "blocked_branch_policy"},
        )
    )
    if safe_summary_issue(intent.get("goal")) is not None:
        issues.append(_issue(path, "plan.intent.goal", "must be a concrete safe summary"))
    for field in ("success", "risk_boundary"):
        if not _safe_lines(intent.get(field)):
            issues.append(_issue(path, "plan.intent." + field, "must be a non-empty array of concrete safe summaries"))
    scope_in = intent["scope"].get("in")
    scope_out = intent["scope"].get("out")
    if not _safe_lines(scope_in) or not _safe_lines(scope_out) or set(scope_in or []) & set(scope_out or []):
        issues.append(_issue(path, "plan.intent.scope", "must contain disjoint non-empty in/out arrays"))
    autonomy = intent["autonomy"]
    for field in ("allow_in_scope_revision", "allow_reviewer_repairs", "forbid_mid_execution_questions"):
        if autonomy.get(field) is not True:
            issues.append(_issue(path, "plan.intent.autonomy." + field, "must be true"))
    if autonomy.get("blocked_branch_policy") != "continue_independent_work":
        issues.append(_issue(path, "plan.intent.autonomy.blocked_branch_policy", "must continue independent work"))
    return issues


def _validate_graph(path: Path, tasks: Sequence[Any]) -> list[Issue]:
    """Prerequisites are the sole graph and every edge carries a real handoff."""

    issues: list[Issue] = []
    valid = [task for task in tasks if _mapping(task) and is_code(task.get("code"), "TASK")]
    codes = [str(task.get("code")) for task in valid]
    if len(codes) != len(set(codes)):
        issues.append(_issue(path, "spec.tasks", "Task codes must be unique"))
    by_code = {str(task.get("code")): task for task in valid}
    output_owner: dict[str, str] = {}
    for code, task in by_code.items():
        for output in task.get("outputs", []) or []:
            if _mapping(output) and is_code(output.get("code"), "OUT"):
                output_code = str(output.get("code"))
                if output_code in output_owner:
                    issues.append(_issue(path, "%s.outputs" % code, "output code %s is not unique" % output_code))
                output_owner[output_code] = code
    graph: dict[str, list[str]] = {}
    for code, task in by_code.items():
        prerequisites = [
            str(item) for item in task.get("prerequisites", []) or [] if isinstance(item, str)
        ]
        graph[code] = prerequisites
        for prerequisite in prerequisites:
            if prerequisite == code:
                issues.append(_issue(path, "%s.prerequisites" % code, "self dependency"))
            elif prerequisite not in by_code:
                issues.append(_issue(path, "%s.prerequisites" % code, "unknown dependency %s" % prerequisite))
    cycle = dependency_cycle(graph)
    if cycle is not None:
        issues.append(_issue(path, "spec.graph", "dependency cycle %s" % " -> ".join(cycle)))
        return issues
    for code, task in by_code.items():
        mapped: set[str] = set()
        for item in task.get("inputs", []) or []:
            if not _mapping(item):
                continue
            source = str(item.get("from"))
            output_code = str(item.get("output"))
            if source not in by_code or output_owner.get(output_code) != source:
                issues.append(_issue(path, "%s.inputs" % code, "input must name an upstream Task output"))
            elif source not in graph.get(code, []):
                issues.append(_issue(path, "%s.inputs" % code, "%s must be a direct prerequisite" % source))
            else:
                mapped.add(source)
        unmapped = {value for value in graph.get(code, []) if value in by_code} - mapped
        if unmapped and task.get("inputs") is not None:
            issues.append(
                _issue(
                    path,
                    "%s.inputs" % code,
                    "every prerequisite must map at least one input: %s" % ", ".join(sorted(unmapped)),
                )
            )
    ordered = sorted(by_code)
    for left_index, left_code in enumerate(ordered):
        for right_code in ordered[left_index + 1:]:
            if _reachable(graph, left_code, right_code) or _reachable(graph, right_code, left_code):
                continue
            left = by_code[left_code].get("ownership", {})
            right = by_code[right_code].get("ownership", {})
            if not _mapping(left) or not _mapping(right):
                continue
            left_paths = left.get("write_paths", []) or []
            right_paths = right.get("write_paths", []) or []
            if any(
                isinstance(a, str) and isinstance(b, str) and _paths_overlap(a, b)
                for a in left_paths
                for b in right_paths
            ):
                issues.append(
                    _issue(
                        path,
                        "spec.parallel",
                        "%s and %s have overlapping write ownership without a dependency" % (left_code, right_code),
                    )
                )
            shared = {item for item in left.get("shared_exclusive", []) or []} & {
                item for item in right.get("shared_exclusive", []) or []
            }
            if shared:
                issues.append(
                    _issue(
                        path,
                        "spec.parallel",
                        "%s and %s share exclusive resources %s" % (left_code, right_code, ", ".join(sorted(shared))),
                    )
                )
    return issues


def _validate_coverage(path: Path, tasks: Sequence[Any]) -> list[Issue]:
    """Every owned requirement and output needs executable acceptance."""

    issues: list[Issue] = []
    seen_criteria: set[str] = set()
    for task in tasks:
        if not _mapping(task) or not is_code(task.get("code"), "TASK"):
            continue
        code = str(task.get("code"))
        acceptance = task.get("acceptance")
        if acceptance is None:
            continue
        owned = {str(item) for item in task.get("requirements", []) or [] if is_code(item, "REQ")}
        owned.update(
            str(item.get("code"))
            for item in task.get("outputs", []) or []
            if _mapping(item) and is_code(item.get("code"), "OUT")
        )
        covered: set[str] = set()
        for criterion in acceptance if isinstance(acceptance, list) else []:
            if not _mapping(criterion):
                continue
            criterion_code = criterion.get("code")
            if is_code(criterion_code, "AC"):
                if criterion_code in seen_criteria:
                    issues.append(_issue(path, "%s.acceptance" % code, "criterion code %s is not unique" % criterion_code))
                seen_criteria.add(str(criterion_code))
            for item in criterion.get("covers", []) or []:
                if isinstance(item, str):
                    covered.add(item)
        unknown = {item for item in covered if is_code(item, "REQ") or is_code(item, "OUT")} - owned
        if unknown:
            issues.append(
                _issue(path, "%s.acceptance" % code, "covers unowned contracts %s" % ", ".join(sorted(unknown)))
            )
        uncovered = owned - covered
        if uncovered:
            issues.append(
                _issue(path, "%s.acceptance" % code, "coverage missing %s" % ", ".join(sorted(uncovered)))
            )
    return issues


def _validate_session(path: Path, name: str, session: Any) -> list[Issue]:
    if session is None:
        return []
    if not _mapping(session):
        return [_issue(path, "lifecycle." + name, "must be an object")]
    issues: list[Issue] = []
    if session.get("count") != 1:
        issues.append(_issue(path, "lifecycle.%s.count" % name, "must equal one"))
    if session.get("status") not in {"active", "completed", "blocked"}:
        issues.append(_issue(path, "lifecycle.%s.status" % name, "invalid session status"))
    return issues


def _validate_lifecycle(path: Path, plan: Mapping[str, Any]) -> list[Issue]:
    lifecycle = plan.get("lifecycle")
    if not _mapping(lifecycle):
        return [_issue(path, "plan.lifecycle", "must be an object")]
    issues: list[Issue] = []
    missing = LIFECYCLE_REQUIRED_FIELDS - set(lifecycle)
    if missing:
        issues.append(_issue(path, "plan.lifecycle", "missing fields %s" % ", ".join(sorted(missing))))
    issues.extend(
        _unknown_fields(path, "plan.lifecycle", lifecycle, LIFECYCLE_REQUIRED_FIELDS | LIFECYCLE_OPTIONAL_FIELDS)
    )
    designer = lifecycle.get("designer_session")
    reviewer = lifecycle.get("reviewer_session")
    issues.extend(_validate_session(path, "designer_session", designer))
    issues.extend(_validate_session(path, "reviewer_session", reviewer))
    phase = plan.get("phase")
    sealed = lifecycle.get("sealed")
    authorization = lifecycle.get("authorization")
    if phase == "designing" and (not _mapping(designer) or designer.get("status") != "active"):
        issues.append(_issue(path, "lifecycle.designer_session", "designing requires the sole active Designer session"))
    if phase == "revising" and not _mapping(lifecycle.get("continuation_session")):
        issues.append(_issue(path, "lifecycle.continuation_session", "revising requires its continuation receipt"))
    if phase != "revising" and lifecycle.get("continuation_session") is not None:
        issues.append(_issue(path, "lifecycle.continuation_session", "only a revising Plan holds an open continuation"))
    # Receipts only move forward. A sealed revision can never coexist with a
    # pre-authorization phase, so no edit can silently rewind a live delivery.
    if phase in AUTHORIZED_PHASES and not _mapping(sealed):
        issues.append(_issue(path, "lifecycle.sealed", "phase requires a sealed revision"))
    if phase not in AUTHORIZED_PHASES and _mapping(sealed):
        issues.append(_issue(path, "plan.phase", "a sealed revision cannot return to %s" % phase))
    if _mapping(sealed) and not _mapping(designer):
        issues.append(_issue(path, "lifecycle.designer_session", "a sealed revision requires its Designer receipt"))
    if _mapping(sealed):
        issues.extend(_unknown_fields(path, "lifecycle.sealed", sealed, {"revision", "semantic_digest", "sealed_at"}))
        if (
            type(sealed.get("revision")) is not int
            or sealed.get("revision") < 1
            or SHA256_PATTERN.fullmatch(str(sealed.get("semantic_digest", ""))) is None
        ):
            issues.append(_issue(path, "lifecycle.sealed", "invalid revision or digest receipt"))
        elif phase in {"authorized", "completed", "blocked"} and sealed.get("semantic_digest") != semantic_digest(plan):
            issues.append(_issue(path, "lifecycle.sealed.semantic_digest", "stale semantic binding"))
    if phase in AUTHORIZED_PHASES and not _mapping(authorization):
        issues.append(_issue(path, "lifecycle.authorization", "phase requires authorization"))
    if authorization is not None:
        if not _mapping(authorization) or authorization.get("source") not in VALID_AUTHORIZATION_SOURCES:
            issues.append(_issue(path, "lifecycle.authorization", "invalid authorization receipt"))
        elif phase in {"authorized", "completed", "blocked"} and authorization.get("semantic_digest") != semantic_digest(plan):
            issues.append(_issue(path, "lifecycle.authorization", "stale authorization binding"))
    if phase == "completed" and (not _mapping(reviewer) or reviewer.get("status") != "completed"):
        issues.append(_issue(path, "lifecycle.reviewer_session", "completed phase requires the sole completed Reviewer"))
    if phase == "blocked" and (not _mapping(reviewer) or reviewer.get("status") != "blocked"):
        issues.append(_issue(path, "lifecycle.reviewer_session", "blocked phase requires the sole Reviewer blocker conclusion"))
    if not isinstance(lifecycle.get("continuation_receipts"), list):
        issues.append(_issue(path, "lifecycle.continuation_receipts", "must be an array"))
    return issues


def plan_readiness_issues(path: Path, plan: Mapping[str, Any]) -> list[Issue]:
    """The single semantic gate: prove the Plan can start and finish execution."""

    issues = validate_plan_document(path, plan)
    if issues:
        return issues
    dossier = plan.get("dossier", {})
    if dossier.get("status") not in {"not_required", "resolved"}:
        issues.append(_issue(path, "dossier.status", "every question must be resolved before authorization"))
    ledger = plan.get("ledger", {})
    if ledger.get("unresolved"):
        issues.append(_issue(path, "ledger.unresolved", "execution-relevant decisions must be resolved or defaulted"))
    records = {
        str(record.get("source"))
        for name in ("user_decided", "defaulted")
        for record in ledger.get(name, [])
        if _mapping(record)
    }
    for question in dossier.get("questions", []):
        if not _mapping(question):
            continue
        if str(question.get("code")) not in records:
            issues.append(_issue(path, "dossier", "%s has no ledger decision record" % question.get("code")))
    designer = plan.get("lifecycle", {}).get("designer_session")
    if not _mapping(designer) or designer.get("status") != "completed":
        issues.append(_issue(path, "lifecycle.designer_session", "readiness requires the sole Designer session completed"))
    spec = plan.get("spec", {})
    requirements = spec.get("requirements")
    tasks = spec.get("tasks") or []
    if not isinstance(requirements, list) or not requirements:
        issues.append(_issue(path, "spec.requirements", "must be non-empty"))
        requirements = []
    if not tasks:
        issues.append(_issue(path, "spec.tasks", "must be non-empty"))
    requirement_codes: set[str] = set()
    for index, requirement in enumerate(requirements):
        prefix = "spec.requirements[%d]" % index
        if (
            not _mapping(requirement)
            or not is_code(requirement.get("code"), "REQ")
            or safe_summary_issue(requirement.get("statement")) is not None
            or not _safe_lines(requirement.get("source_refs"))
        ):
            issues.append(_issue(path, prefix, "requires a REQ-* code, statement, and source_refs"))
            continue
        issues.extend(_unknown_fields(path, prefix, requirement, {"code", "statement", "source_refs"}))
        if requirement.get("code") in requirement_codes:
            issues.append(_issue(path, prefix + ".code", "duplicate requirement code"))
        requirement_codes.add(str(requirement.get("code")))
    architecture = spec.get("architecture")
    if not _mapping(architecture) or safe_summary_issue(architecture.get("summary")) is not None or not _safe_lines(architecture.get("notes")):
        issues.append(_issue(path, "spec.architecture", "requires a summary and concrete notes"))
    else:
        issues.extend(_unknown_fields(path, "spec.architecture", architecture, {"summary", "notes"}))
    implemented: set[str] = set()
    for task in tasks:
        if not _mapping(task):
            continue
        unknown = {str(item) for item in task.get("requirements", []) or []} - requirement_codes
        if unknown:
            issues.append(_issue(path, "%s.requirements" % task.get("code"), "unknown requirements %s" % ", ".join(sorted(unknown))))
        implemented.update(str(item) for item in task.get("requirements", []) or [])
        missing = TASK_DESIGN_FIELDS - set(task)
        if missing:
            issues.append(_issue(path, "%s" % task.get("code"), "readiness requires %s" % ", ".join(sorted(missing))))
    uncovered = requirement_codes - implemented
    if uncovered:
        issues.append(_issue(path, "spec.requirements", "requirements lack implementing Tasks: %s" % ", ".join(sorted(uncovered))))
    regression = spec.get("full_regression")
    if not _mapping(regression) or not _string_list(regression.get("commands"), False) or not _relative_paths(regression.get("paths"), False):
        issues.append(_issue(path, "spec.full_regression", "must contain non-empty commands and relative paths"))
    else:
        issues.extend(_unknown_fields(path, "spec.full_regression", regression, {"commands", "paths"}))
    return issues


def validate_checkpoints_document(path: Path, checkpoints: Any, plan: Mapping[str, Any] | None = None) -> list[Issue]:
    if not _mapping(checkpoints):
        return [_issue(path, "checkpoints", "top-level value must be an object")]
    issues = _privacy_issues(path, checkpoints, "checkpoints")
    if checkpoints.get("schema") != CHECKPOINTS_SCHEMA:
        issues.append(_issue(path, "checkpoints.schema", "unsupported generation"))
    issues.extend(
        _unknown_fields(
            path,
            "checkpoints",
            checkpoints,
            {"schema", "plan", "revision", "semantic_digest", "delivery_status", "tasks"},
        )
    )
    if not is_code(checkpoints.get("plan"), "PLAN"):
        issues.append(_issue(path, "checkpoints.plan", "must be a PLAN-* code"))
    if type(checkpoints.get("revision")) is not int or checkpoints.get("revision") < 1:
        issues.append(_issue(path, "checkpoints.revision", "must be a positive integer"))
    if SHA256_PATTERN.fullmatch(str(checkpoints.get("semantic_digest", ""))) is None:
        issues.append(_issue(path, "checkpoints.semantic_digest", "must be sha256"))
    if checkpoints.get("delivery_status") not in DELIVERY_STATUSES:
        issues.append(_issue(path, "checkpoints.delivery_status", "invalid status"))
    entries = checkpoints.get("tasks")
    if not isinstance(entries, list):
        issues.append(_issue(path, "checkpoints.tasks", "must be an array"))
        entries = []
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        prefix = "checkpoints.tasks[%d]" % index
        if not _mapping(entry) or not is_code(entry.get("code"), "TASK") or entry.get("status") not in TASK_STATUSES:
            issues.append(_issue(path, prefix, "invalid execution state"))
            continue
        issues.extend(
            _unknown_fields(path, prefix, entry, {"code", "status", "dispatch", "evidence", "status_reason"})
        )
        missing = {"code", "status", "dispatch", "evidence"} - set(entry)
        if missing:
            issues.append(_issue(path, prefix, "missing fields %s" % ", ".join(sorted(missing))))
        if entry.get("code") in seen:
            issues.append(_issue(path, prefix + ".code", "duplicate Task state"))
        seen.add(str(entry.get("code")))
        dispatch = entry.get("dispatch")
        if dispatch is not None and (not _mapping(dispatch) or dispatch.get("phase") not in DISPATCH_PHASES):
            issues.append(_issue(path, prefix + ".dispatch", "invalid dispatch phase"))
    if plan is not None:
        if checkpoints.get("plan") != plan.get("code"):
            issues.append(_issue(path, "checkpoints.plan", "does not match Plan"))
        if checkpoints.get("semantic_digest") != semantic_digest(plan):
            issues.append(_issue(path, "checkpoints.semantic_digest", "stale Plan binding"))
        sealed = plan.get("lifecycle", {}).get("sealed")
        if _mapping(sealed) and checkpoints.get("revision") != sealed.get("revision"):
            issues.append(_issue(path, "checkpoints.revision", "stale Plan binding"))
        expected = {
            str(task.get("code")) for task in plan.get("spec", {}).get("tasks", []) if _mapping(task)
        }
        if expected != seen:
            issues.append(_issue(path, "checkpoints.tasks", "must project every Task exactly once"))
    return issues


def authority_expansion_issues(path: Path, prior: Mapping[str, Any], updated: Mapping[str, Any]) -> list[Issue]:
    """Return changes that cannot inherit an existing authorization."""

    issues: list[Issue] = []
    for field in ("goal", "scope", "success", "risk_boundary", "autonomy"):
        if prior.get("intent", {}).get(field) != updated.get("intent", {}).get(field):
            issues.append(_issue(path, "intent." + field, "continuation may not expand or replace authorized intent"))
    for name in ("user_decided", "defaulted"):
        if prior.get("ledger", {}).get(name) != updated.get("ledger", {}).get(name):
            issues.append(_issue(path, "ledger." + name, "continuation may not alter resolved decisions"))
    if prior.get("dossier") != updated.get("dossier"):
        issues.append(_issue(path, "dossier", "continuation may not reopen the Decision Dossier"))
    prior_risks = {
        risk
        for task in prior.get("spec", {}).get("tasks", [])
        if _mapping(task)
        for risk in task.get("risks", []) or []
    }
    updated_risks = {
        risk
        for task in updated.get("spec", {}).get("tasks", [])
        if _mapping(task)
        for risk in task.get("risks", []) or []
    }
    introduced = (updated_risks - prior_risks) & ELEVATED_RISKS
    if introduced:
        issues.append(
            _issue(path, "spec.tasks", "continuation introduces elevated risks %s" % ", ".join(sorted(introduced)))
        )
    return issues
