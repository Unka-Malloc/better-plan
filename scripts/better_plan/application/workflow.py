"""Application services for Better Plan v3 planning and delivery."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping
import hashlib
import json
import os
import subprocess
import sys
import time

from ..domain.design_compile import (
    DESIGN_TEMPLATE,
    compile_design as compile_design_text,
    source_line_for_field,
)
from ..domain.models import (
    CHECKPOINTS_NAME,
    DESIGN_NAME,
    DESIGN_PRISTINE_NAME,
    DOSSIER_PHASES,
    MANIFEST_NAME,
    PLAN_DOCUMENT,
    OPAQUE_EVENT_ID_PATTERN,
    PLAN_NAME,
    RENDERED_VERIFICATIONS,
    TERMINAL_TASK_STATUSES,
    ToolError,
    checkpoints_template,
    generate_id,
    manifest_template,
    plain_shell_command,
    plan_template,
    public_summary,
    safe_summary_issue,
    semantic_digest,
    semantic_payload,
    sha256_value,
    task_state,
)
from ..domain.validation import (
    authority_expansion_issues,
    plan_readiness_issues,
    reviewer_findings_issues,
    validate_checkpoints_document,
    validate_plan_document,
)
from ..infrastructure.native_roles import resolve_codex_role
from ..infrastructure.plan_render import render_document
from ..infrastructure.workspace import (
    fingerprint_paths,
    load_manifest,
    load_plan,
    plan_paths,
    read_json,
    resolve_plan_entry,
    workspace_lock,
    workspace_root,
    write_json,
    write_text,
)


MAX_DELEGATION_ATTEMPTS = 3
OUTPUT_TAIL_CHARACTERS = 2000
FRONTEND_WORKER_ROLE = "frontend-worker"
WORKER_ASSIGNMENT_PREFIX = (
    "Native main: reuse this instruction prefix byte-for-byte for every eligible Task with the "
    "same returned agent_type, then append only that Task's compiled brief. The stable prefix "
    "improves prompt-cache hits and Token efficiency. Dispatch Tasks separately and concurrently; "
    "never bind one live agent id to multiple Tasks. Worker: implement exactly the supplied Task, "
    "execute every ready Node concurrently, stay inside its ownership, and return focused evidence."
)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _opaque_event_id(value: Any, field: str) -> str:
    if not isinstance(value, str) or OPAQUE_EVENT_ID_PATTERN.fullmatch(value) is None:
        raise ToolError("%s must be an opaque host identifier" % field)
    return value


def _project_root(workspace: Path) -> Path:
    """Return the directory regression commands and fingerprints run against.

    A workspace that lives outside the delivered repository declares
    ``project_root`` in ``Manifest.json`` relative to the workspace root; the
    target must exist. Otherwise the nearest enclosing Git checkout is used,
    falling back to the workspace itself.
    """

    manifest_path = workspace / MANIFEST_NAME
    if manifest_path.is_file():
        declared = load_manifest(workspace).get("project_root")
        if declared is not None:
            project = (workspace / declared).resolve()
            if not project.is_dir():
                raise ToolError("Manifest.json project_root does not name an existing directory")
            return project
    current = workspace.resolve()
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    return workspace.resolve()


def _load_raw_plan(root: Path, selector: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Path]]:
    """Load one structurally valid Plan for mutation.

    Structure is proven on load so a mutator reports every concrete defect at
    once instead of failing later on a missing key. Semantic completeness stays
    deferred to the single readiness gate.
    """

    manifest = load_manifest(root)
    entry = resolve_plan_entry(manifest, selector)
    paths = plan_paths(root, entry)
    value = read_json(paths["plan"])
    if not isinstance(value, dict):
        raise ToolError("Plan.json must be an object")
    if any(value.get(field) != entry.get(field) for field in ("code", "directory")):
        raise ToolError("Manifest and Plan identity do not match")
    issues = validate_plan_document(paths["plan"], value)
    if issues:
        raise ToolError("invalid Plan.json: %s" % "; ".join(issue.message for issue in issues))
    return manifest, value, paths


def _save_plan(paths: Mapping[str, Path], plan: dict[str, Any]) -> None:
    issues = validate_plan_document(paths["plan"], plan)
    if issues:
        raise ToolError("refusing invalid Plan: %s" % "; ".join(issue.message for issue in issues))
    document = render_document(plan)
    write_json(paths["plan"], plan)
    write_text(paths["directory"] / PLAN_DOCUMENT, document)


def _open_compile_items(receipt: Any) -> list[dict[str, Any]]:
    if not isinstance(receipt, Mapping):
        return []
    values = [
        dict(item)
        for item in receipt.get("issues", [])
        if isinstance(item, Mapping) and item.get("status") == "open"
    ]
    values.extend(
        {"kind": "unmapped", **dict(item)}
        for item in receipt.get("unmapped", [])
        if isinstance(item, Mapping) and item.get("status") == "open"
    )
    return values


def _receipt_issues(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {key: item[key] for key in ("kind", "message", "line", "field", "status")}
        for item in result.get("issues", [])
        if isinstance(item, Mapping) and item.get("kind") in {"structure", "content"}
    ]


def _compiler_validation_diagnostic(message: str, result: Mapping[str, Any]) -> dict[str, Any]:
    field, separator, detail = message.partition(": ")
    canonical_field = field[5:] if field.startswith("plan.") else field
    return {
        "kind": "structure",
        "message": detail if separator else message,
        "line": source_line_for_field(result, canonical_field),
        "field": canonical_field,
        "status": "open",
    }


def _unique_compiler_diagnostics(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for item in values:
        key = (item.get("kind"), item.get("message"), item.get("line"), item.get("field"))
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _compile_item_summary(item: Mapping[str, Any]) -> str:
    if item.get("message"):
        return "Design.md:%s %s: %s" % (
            item.get("line"),
            item.get("field"),
            item.get("message"),
        )
    return "Design.md lines %s: unmapped content" % item.get("lines")


def _compile_receipt(
    result: Mapping[str, Any],
    draft: str,
    spec: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "pristine_digest": hashlib.sha256(draft.encode("utf-8")).hexdigest(),
        "compiled_spec_digest": sha256_value(spec),
        "applied_at": _now(),
        "sections_from_plan": list(result.get("sections_from_plan", [])),
        "issues": _receipt_issues(result),
        "unmapped": [
            dict(item) for item in result.get("unmapped", []) if isinstance(item, Mapping)
        ],
    }


def _frozen_design(paths: Mapping[str, Path], receipt: Mapping[str, Any]) -> str:
    if not paths["design"].is_file() or not paths["design_pristine"].is_file():
        raise ToolError("Design.md and Design.pristine.md are required before authorization")
    try:
        draft = paths["design"].read_text(encoding="utf-8")
        pristine = paths["design_pristine"].read_text(encoding="utf-8")
    except OSError:
        raise ToolError("cannot read the archived Designer draft")
    expected = receipt.get("pristine_digest")
    if draft != pristine or hashlib.sha256(draft.encode("utf-8")).hexdigest() != expected:
        raise ToolError("Design.md is read-only after the Designer returns")
    return pristine


def _plan_repair_result(
    plan: Mapping[str, Any],
    paths: Mapping[str, Path],
    receipt: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    updated = deepcopy(dict(receipt))
    readiness = [issue.message for issue in plan_readiness_issues(paths["plan"], plan)]
    if readiness:
        return updated, readiness
    for item in updated.get("issues", []):
        if isinstance(item, dict) and item.get("status") == "open":
            item["status"] = "resolved"
    for item in updated.get("unmapped", []):
        if isinstance(item, dict) and item.get("status") == "open":
            item["status"] = "resolved"
    updated["compiled_spec_digest"] = sha256_value(plan.get("spec", {}))
    updated["applied_at"] = _now()
    return updated, []


def _install_compiled_spec(plan: dict[str, Any], result: dict[str, Any]) -> None:
    candidate = deepcopy(plan)
    candidate["spec"] = deepcopy(result["spec"])
    candidate["phase"] = "ready"
    candidate_session = candidate.get("lifecycle", {}).get("designer_session")
    if isinstance(candidate_session, dict):
        candidate_session["status"] = "completed"
    structural = validate_plan_document(Path("Plan.json"), candidate)
    if structural:
        for issue in structural:
            result["issues"].append(_compiler_validation_diagnostic(issue.message, result))
        result["issues"] = _unique_compiler_diagnostics(result["issues"])
        return
    plan["spec"] = candidate["spec"]


IMMUTABLE_FIELDS = ("intent", "dossier")


def _immutable_snapshot(plan: Mapping[str, Any]) -> dict[str, Any]:
    """Return exactly what no Designer session may change."""

    snapshot = {field: deepcopy(plan.get(field)) for field in IMMUTABLE_FIELDS}
    snapshot["user_decided"] = deepcopy(plan.get("ledger", {}).get("user_decided"))
    snapshot["defaulted"] = deepcopy(plan.get("ledger", {}).get("defaulted"))
    return snapshot


def _selector_payload(role: str, native_host: str | None, codex_home: str | None) -> dict[str, Any]:
    if native_host != "codex":
        return {"agent_type": role}
    home = Path(codex_home) if codex_home else Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    selector = resolve_codex_role(role, home)
    if selector is None:
        return {"agent_type": role, "main_thread_fallback": True}
    return {
        "agent_type": role,
        "model": selector.model,
        "reasoning_effort": selector.reasoning_effort,
        "model_provider": selector.model_provider,
        "selector_source": selector.source,
    }


def _safe_diagnostic_tail(output: str) -> str:
    """Return bounded useful diagnostics without local paths, endpoints, or secrets."""

    values: list[str] = []
    for raw in output[-OUTPUT_TAIL_CHARACTERS:].splitlines():
        line = raw.strip()
        if not line:
            continue
        value = line if safe_summary_issue(line, max_chars=500) is None else "[redacted unsafe diagnostic line]"
        if not values or values[-1] != value:
            values.append(value)
    return "\n".join(values)[-OUTPUT_TAIL_CHARACTERS:]


def _run_commands_with_diagnostics(
    project_root: Path, commands: list[str]
) -> tuple[bool, list[dict[str, Any]], list[dict[str, Any]]]:
    """Run commands and return persistent receipts plus ephemeral safe diagnostics."""

    receipts: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for index, command in enumerate(commands):
        # Observation windows never impose an execution deadline. A declared
        # command may enforce its own project-required limit; cancellation
        # remains controlled by the caller.
        completed = subprocess.run(
            plain_shell_command(command),
            cwd=str(project_root),
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        exit_code = completed.returncode
        outcome = "passed" if exit_code == 0 else "failed"
        output = completed.stdout.decode("utf-8", "replace") if completed.stdout else ""
        receipts.append(
            {
                "command_sha256": hashlib.sha256(command.encode("utf-8")).hexdigest(),
                "outcome": outcome,
                "exit_code": exit_code,
                "recorded_at": _now(),
            }
        )
        if outcome != "passed":
            tail = _safe_diagnostic_tail(output)
            print("command %s (%s)" % (outcome, command), file=sys.stderr)
            if tail:
                print(tail, file=sys.stderr)
            diagnostics.append(
                {
                    "command_index": index,
                    "command_sha256": receipts[-1]["command_sha256"],
                    "outcome": outcome,
                    "exit_code": exit_code,
                    "output_tail": tail,
                }
            )
            return False, receipts, diagnostics
    return True, receipts, diagnostics


def _run_commands(project_root: Path, commands: list[str]) -> tuple[bool, list[dict[str, Any]]]:
    """Run commands while callers persist only privacy-safe receipts."""

    passed, receipts, _ = _run_commands_with_diagnostics(project_root, commands)
    return passed, receipts


def init_plan(args: Any) -> int:
    root = workspace_root(Path(args.root))
    with workspace_lock(root):
        manifest_path = root / MANIFEST_NAME
        manifest = load_manifest(root) if manifest_path.is_file() else manifest_template()
        if any(
            entry.get("directory") == args.directory or entry.get("code") == args.code
            for entry in manifest.get("plans", [])
        ):
            raise ToolError("plan code or directory already exists")
        plan = plan_template()
        plan["code"] = args.code
        plan["title"] = args.title
        plan["directory"] = args.directory
        plan["intent"]["goal"] = args.goal
        plan["intent"]["scope"] = {"in": args.scope_in, "out": args.scope_out}
        plan["intent"]["success"] = args.success
        plan["intent"]["risk_boundary"] = args.risk_boundary
        paths = {
            "directory": root / args.directory,
            "plan": root / args.directory / PLAN_NAME,
            "checkpoints": root / args.directory / CHECKPOINTS_NAME,
        }
        _save_plan(paths, plan)
        manifest["plans"].append(
            {
                "code": plan["code"],
                "title": plan["title"],
                "directory": plan["directory"],
                "plan": "%s/%s" % (plan["directory"], PLAN_NAME),
            }
        )
        write_json(manifest_path, manifest)
    print(json.dumps({"plan": plan["code"], "phase": plan["phase"]}))
    return 0


def _read_input(value: str) -> Any:
    if value == "-":
        return json.load(sys.stdin)
    return json.loads(Path(value).read_text(encoding="utf-8"))


def build_dossier(args: Any) -> int:
    """Load or replace the single Decision Dossier before it is resolved."""

    root = workspace_root(Path(args.root))
    questions = _read_input(args.input)
    if not isinstance(questions, list):
        raise ToolError("Decision Dossier input must be an array of questions")
    with workspace_lock(root):
        _, plan, paths = _load_raw_plan(root, args.plan)
        if plan.get("phase") not in DOSSIER_PHASES:
            raise ToolError("the Decision Dossier belongs to a Plan that is not yet authorized")
        if plan.get("dossier", {}).get("status") == "resolved":
            raise ToolError("the Decision Dossier is already resolved and may not be rebuilt")
        plan["dossier"] = {
            "status": "draft" if questions else "not_required",
            "questions": questions,
        }
        _save_plan(paths, plan)
    print(json.dumps({"questions": len(questions), "status": plan["dossier"]["status"]}))
    return 0


def resolve_dossier(args: Any) -> int:
    """Apply explicit selections and declared defaults exactly once."""

    root = workspace_root(Path(args.root))
    selections = _read_input(args.input)
    if not isinstance(selections, dict):
        raise ToolError("Decision Dossier selections must be an object")
    with workspace_lock(root):
        _, plan, paths = _load_raw_plan(root, args.plan)
        if plan.get("phase") not in DOSSIER_PHASES:
            raise ToolError("the Decision Dossier belongs to a Plan that is not yet authorized")
        dossier = plan.get("dossier", {})
        if dossier.get("status") != "draft":
            raise ToolError("no unresolved Decision Dossier")
        unknown = set(selections) - {
            str(question.get("code")) for question in dossier.get("questions", [])
        }
        if unknown:
            raise ToolError("unknown question codes %s" % ", ".join(sorted(unknown)))
        resolved: set[str] = set()
        for question in dossier.get("questions", []):
            code = str(question.get("code"))
            explicit = code in selections
            chosen = selections.get(code, question.get("default"))
            options = {item.get("id"): item for item in question.get("options", [])}
            if chosen not in options:
                raise ToolError("invalid option for %s" % code)
            question["selected"] = chosen
            plan["ledger"]["user_decided" if explicit else "defaulted"].append(
                {
                    "source": code,
                    "option": chosen,
                    "resolves": list(question.get("resolves", [])),
                    "effects": list(options[chosen].get("effects", [])),
                }
            )
            resolved.update(str(item) for item in question.get("resolves", []))
        plan["ledger"]["unresolved"] = [
            item for item in plan["ledger"]["unresolved"] if item.get("code") not in resolved
        ]
        dossier["status"] = "resolved"
        _save_plan(paths, plan)
    print(json.dumps({"resolved_questions": len(dossier.get("questions", []))}))
    return 0


def open_designer_session(args: Any) -> int:
    root = workspace_root(Path(args.root))
    with workspace_lock(root):
        _, plan, paths = _load_raw_plan(root, args.plan)
        if plan.get("phase") != "draft":
            raise ToolError("the Designer starts from a draft Plan")
        if plan.get("dossier", {}).get("status") not in {"not_required", "resolved"}:
            raise ToolError("resolve the Decision Dossier before the Designer session")
        if plan.get("lifecycle", {}).get("designer_session") is not None:
            raise ToolError("the Designer runs exactly once")
        if paths["design"].exists() and not paths["design"].is_file():
            raise ToolError("Design.md path must be a file")
        if not paths["design"].exists():
            write_text(paths["design"], DESIGN_TEMPLATE)
        dispatch_id = generate_id()
        selector = _selector_payload("designer", args.native_host, args.codex_home)
        plan["lifecycle"]["designer_session"] = {
            "count": 1,
            "id": dispatch_id,
            "status": "active",
            "opened_at": _now(),
            "immutable": _immutable_snapshot(plan),
            "host_agent_id": None,
            "attempts": 1,
            "selector": selector,
            "main_thread_fallback": selector.get("main_thread_fallback", False),
        }
        plan["phase"] = "designing"
        _save_plan(paths, plan)
    plan_path = "%s/%s" % (plan["directory"], PLAN_NAME)
    draft_path = "%s/%s" % (plan["directory"], DESIGN_NAME)
    payload = {
        "action": "dispatch_designer",
        "dispatch_id": dispatch_id,
        "plan_path": plan_path,
        "draft_path": draft_path,
        "assignment": (
            "Write the complete solution design to %s before returning. "
            "Group dependent work inside one Task so every Task is mutually parallel-safe. "
            "Inside each Task, design a minimal Node DAG: branch every independent Node, declare "
            "only real dependencies, and name every predecessor at joins; the Worker will execute "
            "every ready Node concurrently. "
            "Do not edit Plan.json.spec while this draft path is available. "
            "Only if the host cannot create the draft may you complete %s directly."
            % (draft_path, plan_path)
        ),
        "role_reference": "references/designer.md",
        "knowledge_references": ["references/design-format.md", "references/design-patterns.md"],
    }
    payload.update(selector)
    print(json.dumps(payload))
    return 0


def close_designer_session(args: Any) -> int:
    """Close the sole design session on correlation and immutability only.

    Semantic completeness is proven once, at authorization. A Designer that
    touched the authorized intent, Dossier, or resolved decisions has those exact
    subtrees restored from the session receipt, so the delivery can always leave
    the design phase instead of deadlocking on a rejected close.
    """

    root = workspace_root(Path(args.root))
    with workspace_lock(root):
        _, plan, paths = _load_raw_plan(root, args.plan)
        session = plan.get("lifecycle", {}).get("designer_session")
        if not isinstance(session, dict) or session.get("status") != "active":
            raise ToolError("no active Designer session")
        if session.get("id") != args.dispatch_id:
            raise ToolError("Designer session correlation mismatch")
        if session.get("agent_returned") is not True:
            raise ToolError("Designer session has not reached a final role boundary")
        immutable = session.get("immutable")
        if not isinstance(immutable, Mapping):
            raise ToolError("Designer session lost its immutable receipt")
        restored: list[str] = []
        for field in IMMUTABLE_FIELDS:
            if plan.get(field) != immutable.get(field):
                plan[field] = deepcopy(immutable.get(field))
                restored.append(field)
        for name in ("user_decided", "defaulted"):
            if plan.get("ledger", {}).get(name) != immutable.get(name):
                plan["ledger"][name] = deepcopy(immutable.get(name))
                restored.append("ledger.%s" % name)
        compiled = False
        result: dict[str, Any] | None = None
        if paths["design"].is_file():
            try:
                draft = paths["design"].read_text(encoding="utf-8")
            except OSError:
                raise ToolError("cannot read Design.md")
            compiled = draft != DESIGN_TEMPLATE
        if compiled:
            result = compile_design_text(draft, plan.get("spec", {}))
            _install_compiled_spec(plan, result)
            if paths["design_pristine"].exists():
                try:
                    archived = paths["design_pristine"].read_text(encoding="utf-8")
                except (OSError, UnicodeError):
                    result["issues"].append(
                        {
                            "kind": "structure",
                            "message": "Design.pristine.md cannot be read",
                            "line": 1,
                            "field": "document.pristine",
                            "status": "open",
                        }
                    )
                else:
                    if archived != draft:
                        result["issues"].append(
                            {
                                "kind": "structure",
                                "message": "Design.pristine.md differs from the returned draft",
                                "line": 1,
                                "field": "document.pristine",
                                "status": "open",
                            }
                        )
            else:
                write_text(paths["design_pristine"], draft)
        session["status"] = "completed"
        session["closed_at"] = _now()
        if restored:
            session["restored"] = restored
        plan["phase"] = "ready"
        if result is not None:
            session["compile"] = _compile_receipt(result, draft, plan["spec"])
        _save_plan(paths, plan)
        issues = plan_readiness_issues(paths["plan"], plan)
    print(
        json.dumps(
            {
                "phase": "ready",
                "ready": not issues,
                "restored": restored,
                "open_issues": [issue.message for issue in issues],
                "compiled": compiled,
                "structure_issues": sum(
                    1 for item in (result or {}).get("issues", []) if item.get("kind") == "structure"
                ),
                "content_issues": sum(
                    1 for item in (result or {}).get("issues", []) if item.get("kind") == "content"
                ),
                "unmapped": sum(
                    1 for item in (result or {}).get("unmapped", []) if item.get("status") == "open"
                ),
            }
        )
    )
    return 0


def compile_design(args: Any) -> int:
    """Preview draft compilation or validate a main-thread Plan repair."""

    root = workspace_root(Path(args.root))
    with workspace_lock(root):
        _, plan, paths = _load_raw_plan(root, args.plan)
        phase = plan.get("phase")
        if args.apply and phase != "ready":
            raise ToolError("compile-design --apply requires a ready Plan")
        if args.check and phase not in {"designing", "ready"}:
            raise ToolError("compile-design --check requires a designing or ready Plan")
        if not paths["design"].is_file():
            raise ToolError("Design.md is missing")
        try:
            draft = paths["design"].read_text(encoding="utf-8")
        except OSError:
            raise ToolError("cannot read Design.md")
        session = plan.get("lifecycle", {}).get("designer_session")
        if not isinstance(session, dict):
            raise ToolError("the Designer session is unavailable")
        previous = session.get("compile") if isinstance(session.get("compile"), Mapping) else None
        if phase == "designing":
            result = compile_design_text(draft, plan.get("spec", {}))
            candidate = deepcopy(plan)
            candidate["spec"] = deepcopy(result["spec"])
            candidate["phase"] = "ready"
            candidate_session = candidate.get("lifecycle", {}).get("designer_session")
            if isinstance(candidate_session, dict):
                candidate_session["status"] = "completed"
            readiness = plan_readiness_issues(paths["plan"], candidate)
            diagnostics = [dict(item) for item in result["issues"]]
            diagnostics.extend(
                _compiler_validation_diagnostic(issue.message, result)
                for issue in readiness
            )
            diagnostics = _unique_compiler_diagnostics(diagnostics)
            has_unmapped = any(
                item.get("status") == "open" for item in result["unmapped"]
            )
            print(
                json.dumps(
                    {
                        "valid": not diagnostics and not has_unmapped,
                        "issues": diagnostics,
                        "unmapped": result["unmapped"],
                    }
                )
            )
            return 0 if not diagnostics and not has_unmapped else 1
        if previous is None:
            raise ToolError("the ready Plan has no Designer draft compilation receipt")
        _frozen_design(paths, previous)
        updated, problems = _plan_repair_result(plan, paths, previous)
        if args.check:
            print(
                json.dumps(
                    {
                        "valid": not problems,
                        "issues": problems,
                        "unmapped": updated.get("unmapped", []),
                    }
                )
            )
            return 0 if not problems else 1
        session["compile"] = updated
        _save_plan(paths, plan)
        open_items = _open_compile_items(session["compile"])
    print(
        json.dumps(
            {
                "applied": True,
                "open_issues": len(open_items),
            }
        )
    )
    return 0 if not problems and not open_items else 1


def check_readiness(args: Any) -> int:
    """List every remaining readiness issue in one pass."""

    root = workspace_root(Path(args.root))
    _, plan, paths = load_plan(root, args.plan)
    issues = plan_readiness_issues(paths["plan"], plan)
    print(
        json.dumps(
            {
                "ready": not issues,
                "issues": [issue.message for issue in issues],
                "semantic_digest": semantic_digest(plan),
            }
        )
    )
    return 0 if not issues else 1


def authorize_plan(args: Any) -> int:
    """The single gate: prove readiness, optionally the host harness, then seal."""

    root = workspace_root(Path(args.root))
    project = _project_root(root)
    with workspace_lock(root):
        manifest, plan, paths = _load_raw_plan(root, args.plan)
        if plan.get("phase") != "ready":
            raise ToolError("authorization requires a design-ready Plan")
        if plan.get("lifecycle", {}).get("sealed") is not None or paths["checkpoints"].is_file():
            raise ToolError("this Plan is already authorized; revise it through a continuation")
        compile_receipt = plan.get("lifecycle", {}).get("designer_session", {}).get("compile")
        if isinstance(compile_receipt, Mapping):
            _frozen_design(paths, compile_receipt)
        compile_issues = _open_compile_items(compile_receipt)
        if compile_issues:
            raise ToolError(
                "design compilation has open issues: %s"
                % "; ".join(_compile_item_summary(item) for item in compile_issues)
            )
        issues = plan_readiness_issues(paths["plan"], plan)
        if issues:
            raise ToolError("plan is not ready: %s" % "; ".join(issue.message for issue in issues))
        verification: dict[str, Any] | None = None
        if args.verify_command:
            paths_declared = args.verify_path or plan["spec"]["full_regression"]["paths"]
            before = fingerprint_paths(project, paths_declared)
            passed, receipts = _run_commands(project, args.verify_command)
            if fingerprint_paths(project, paths_declared) != before:
                raise ToolError("verification commands changed declared inputs")
            verification = {
                "passed": passed,
                "input_fingerprint": before,
                "commands": receipts,
                "recorded_at": _now(),
            }
            if not passed:
                plan["lifecycle"]["verification"] = verification
                _save_plan(paths, plan)
                raise ToolError("host verification failed; repair the harness before authorizing")
        revision = 1
        digest = semantic_digest(plan)
        plan["phase"] = "authorized"
        plan["lifecycle"]["sealed"] = {
            "revision": revision,
            "semantic_digest": digest,
            "sealed_at": _now(),
        }
        plan["lifecycle"]["authorization"] = {
            "source": args.source,
            "reference_digest": hashlib.sha256(args.reference.encode("utf-8")).hexdigest(),
            "semantic_digest": digest,
            "risk_reasons": [public_summary(value, "risk reason") for value in (args.risk_reason or [])],
            "autonomy": deepcopy(plan.get("intent", {}).get("autonomy", {})),
            "authorized_at": _now(),
        }
        if verification is not None:
            plan["lifecycle"]["verification"] = verification
        _save_plan(paths, plan)
        write_json(paths["checkpoints"], checkpoints_template(plan))
        entry = resolve_plan_entry(manifest, args.plan)
        for candidate in manifest["plans"]:
            if candidate.get("code") == entry.get("code"):
                candidate["checkpoints"] = "%s/%s" % (candidate["directory"], CHECKPOINTS_NAME)
        write_json(root / MANIFEST_NAME, manifest)
    print(json.dumps({"authorized": True, "revision": revision, "verified": verification is not None}))
    return 0


def begin_continuation(args: Any) -> int:
    root = workspace_root(Path(args.root))
    with workspace_lock(root):
        _, plan, paths = _load_raw_plan(root, args.plan)
        if plan.get("phase") != "authorized":
            raise ToolError("continuation requires an authorized Plan")
        if plan.get("lifecycle", {}).get("reviewer_session") is not None:
            raise ToolError("continuation cannot start after the sole Reviewer session opens")
        plan["lifecycle"]["continuation_session"] = {
            "id": generate_id(),
            "reason": public_summary(args.reason, "continuation reason"),
            "opened_at": _now(),
            "prior": {
                "intent": deepcopy(plan.get("intent")),
                "dossier": deepcopy(plan.get("dossier")),
                "ledger": {
                    "user_decided": deepcopy(plan.get("ledger", {}).get("user_decided")),
                    "defaulted": deepcopy(plan.get("ledger", {}).get("defaulted")),
                },
                "spec": {"tasks": deepcopy(plan.get("spec", {}).get("tasks"))},
            },
        }
        plan["phase"] = "revising"
        _save_plan(paths, plan)
    print(json.dumps({"continuation_id": plan["lifecycle"]["continuation_session"]["id"]}))
    return 0


def close_continuation(args: Any) -> int:
    root = workspace_root(Path(args.root))
    with workspace_lock(root):
        _, plan, paths = _load_raw_plan(root, args.plan)
        session = plan.get("lifecycle", {}).get("continuation_session")
        if plan.get("phase") != "revising" or not isinstance(session, Mapping) or session.get("id") != args.continuation_id:
            raise ToolError("continuation correlation mismatch")
        expansion = authority_expansion_issues(paths["plan"], session.get("prior", {}), plan)
        if expansion:
            raise ToolError("continuation exceeds authorization: %s" % "; ".join(issue.message for issue in expansion))
        by_code = {str(task.get("code")): task for task in plan.get("spec", {}).get("tasks", [])}
        prior_tasks = {task["code"]: task for task in session["prior"]["spec"]["tasks"]}
        checkpoints = read_json(paths["checkpoints"])
        corrections: list[dict[str, Any]] = []
        # Dispatch and acceptance cannot run while the Plan is revising.
        # Checkpoints already owns Task status; no second snapshot is needed.
        for state in checkpoints["tasks"]:
            code, status = state["code"], state["status"]
            if status == "pending":
                continue
            before, after = prior_tasks[code], by_code.get(code)
            if before == after:
                continue
            if after is None or status != "in_progress" or {
                key: value for key, value in before.items() if key != "focused_regression"
            } != {key: value for key, value in after.items() if key != "focused_regression"}:
                raise ToolError("continuation changed a started Task's frozen contract")
            dispatch = state.get("dispatch")
            if not isinstance(dispatch, Mapping) or dispatch.get("phase") not in {
                "awaiting_acceptance", "worker_correction"
            }:
                raise ToolError("execution corrections require the Worker's final callback")
            corrections.append({
                "task": code,
                "before": deepcopy(before.get("focused_regression")),
                "after": deepcopy(after.get("focused_regression")),
            })
        revision = int(plan["lifecycle"]["sealed"]["revision"]) + 1
        digest = semantic_digest(plan)
        candidate = deepcopy(plan)
        candidate["phase"] = "authorized"
        candidate["lifecycle"]["sealed"] = {
            "revision": revision,
            "semantic_digest": digest,
            "sealed_at": _now(),
        }
        candidate["lifecycle"]["authorization"]["semantic_digest"] = digest
        candidate["lifecycle"]["continuation_receipts"].append(
            {
                "id": session["id"],
                "reason": session["reason"],
                "revision": revision,
                "recorded_at": _now(),
                "execution_corrections": corrections,
            }
        )
        del candidate["lifecycle"]["continuation_session"]
        issues = plan_readiness_issues(paths["plan"], candidate)
        if issues:
            raise ToolError("continuation is not ready: %s" % "; ".join(issue.message for issue in issues))
        plan = candidate
        _save_plan(paths, plan)
        existing = {str(item.get("code")): item for item in checkpoints.get("tasks", [])}
        checkpoints["tasks"] = [
            existing.get(str(task.get("code")), task_state(task.get("code")))
            for task in plan.get("spec", {}).get("tasks", [])
        ]
        checkpoints.update({"revision": revision, "semantic_digest": digest, "full_regression": None})
        write_json(paths["checkpoints"], checkpoints)
    print(json.dumps({"continued": True, "revision": revision}))
    return 0


def _execution_context(
    root: Path, selector: str, *, phases: frozenset[str] = frozenset({"authorized"})
) -> tuple[dict[str, Any], dict[str, Path], dict[str, Any]]:
    _, plan, paths = load_plan(root, selector)
    if plan.get("phase") not in phases:
        raise ToolError("Plan phase %s does not accept this action" % plan.get("phase"))
    checkpoints = read_json(paths["checkpoints"])
    issues = validate_checkpoints_document(paths["checkpoints"], checkpoints, plan)
    if issues:
        raise ToolError("invalid Checkpoints.json: %s" % "; ".join(issue.message for issue in issues))
    return plan, paths, checkpoints


def _task_by_code(plan: Mapping[str, Any], code: str) -> dict[str, Any]:
    matches = [item for item in plan.get("spec", {}).get("tasks", []) if item.get("code") == code]
    if len(matches) != 1:
        raise ToolError("Task code must resolve exactly once")
    return matches[0]


def _state_by_code(checkpoints: Mapping[str, Any], code: str) -> dict[str, Any]:
    matches = [item for item in checkpoints.get("tasks", []) if item.get("code") == code]
    if len(matches) != 1:
        raise ToolError("Task code must resolve exactly once")
    return matches[0]


def _full_regression_fingerprint(
    project: Path,
    plan: Mapping[str, Any],
    paths: Mapping[str, Path],
) -> str:
    """Fingerprint delivery inputs without hashing Better Plan's mutable receipts."""

    return fingerprint_paths(
        project,
        plan["spec"]["full_regression"]["paths"],
        excluded_paths=(paths["plan"], paths["checkpoints"]),
    )


def _reviewer_findings_recorded(session: Mapping[str, Any]) -> bool:
    return (
        session.get("findings_recorded") is True
        and isinstance(session.get("out_of_scope_findings"), list)
    )


PRE_DELIVERY_ACTIONS = {
    "draft": "open_designer_session",
    "designing": "close_designer_session",
    "ready": "authorize_plan",
    "revising": "close_continuation",
    "completed": "delivery_complete",
    "blocked": "delivery_blocked",
}


def _version_control_handoff(plan: Mapping[str, Any]) -> dict[str, Any]:
    """Return the terminal Git action that only the context-aware native main may perform."""

    return {
        "action": "commit_delivery_if_git",
        "owner": "native_main",
        "condition": "git_repository",
        "target": "current_branch",
        "plan": {"code": plan.get("code"), "title": plan.get("title")},
        "instruction": (
            "If the project is a Git repository, inspect the final worktree, preserve unrelated "
            "changes, and create exactly one commit for this completed Delivery Plan on the "
            "current branch using the repository's normal Git conventions; otherwise skip Git."
        ),
    }


def next_action(args: Any) -> int:
    """Name exactly one next action for the single parallel Task frontier."""

    root = workspace_root(Path(args.root))
    project = _project_root(root)
    with workspace_lock(root):
        _, plan, paths = _load_raw_plan(root, args.plan)
        phase = str(plan.get("phase"))
        if phase == "ready":
            receipt = plan.get("lifecycle", {}).get("designer_session", {}).get("compile")
            compile_issues = _open_compile_items(receipt)
            if compile_issues:
                print(
                    json.dumps(
                        {
                            "action": "repair_plan",
                            "phase": phase,
                            "brief": {
                                "plan_path": "%s/%s" % (plan["directory"], PLAN_NAME),
                                "readonly_design_path": "%s/%s" % (plan["directory"], DESIGN_NAME),
                                "issues": compile_issues,
                                "rules_reference": "references/structure-repair.md",
                            },
                        }
                    )
                )
                return 0
        if phase != "authorized":
            payload = {"action": PRE_DELIVERY_ACTIONS[phase], "phase": phase}
            if phase == "completed":
                payload["version_control_handoff"] = _version_control_handoff(plan)
            print(json.dumps(payload))
            return 0
        checkpoints = read_json(paths["checkpoints"])
    corrections: list[str] = []
    awaiting: list[str] = []
    running: list[str] = []
    exhausted: list[str] = []
    eligible: list[str] = []
    awaiting_input: list[dict[str, str]] = []
    for task in plan.get("spec", {}).get("tasks", []):
        code = str(task.get("code"))
        state = _state_by_code(checkpoints, code)
        status = state.get("status")
        dispatch = state.get("dispatch")
        if state.get("input_request"):
            awaiting_input.append({"task": code, "reason": state["input_request"]})
            continue
        dispatch_phase = dispatch.get("phase") if isinstance(dispatch, Mapping) else None
        if status == "in_progress" and dispatch_phase == "worker_correction":
            corrections.append(code)
        elif status == "in_progress" and dispatch_phase == "awaiting_acceptance":
            awaiting.append(code)
        elif status == "in_progress":
            (exhausted if isinstance(dispatch, Mapping) and dispatch.get("main_thread_fallback") else running).append(code)
        elif status == "pending":
            eligible.append(code)
    reviewer = plan.get("lifecycle", {}).get("reviewer_session")
    reviewer_active = isinstance(reviewer, Mapping) and reviewer.get("status") == "active"
    regression = checkpoints.get("full_regression")
    regression_current = isinstance(regression, Mapping) and regression.get(
        "content_fingerprint"
    ) == _full_regression_fingerprint(project, plan, paths)
    if eligible:
        action = "dispatch_tasks"
    elif corrections:
        action = "repair_tasks"
    elif awaiting:
        action = "accept_tasks"
    elif exhausted:
        action = "complete_in_main"
    elif running:
        action = "await_tasks"
    elif awaiting_input:
        action = "await_user_input"
    elif reviewer is None:
        action = "open_reviewer_session" if regression_current else "run_full_regression"
    else:
        if reviewer_active and reviewer.get("agent_returned") is not True:
            action = "await_reviewer"
        elif reviewer_active and not _reviewer_findings_recorded(reviewer):
            action = "record_reviewer_findings"
        elif regression_current and regression.get("passed") is True:
            action = "close_reviewer_session"
        else:
            action = "run_full_regression"
    print(
        json.dumps(
            {
                "action": action,
                "phase": phase,
                "corrections": corrections,
                "awaiting_acceptance": awaiting,
                "exhausted": exhausted,
                "running": running,
                "eligible": eligible,
                "awaiting_input": awaiting_input,
            }
        )
    )
    return 0


def _leaf_brief(plan: Mapping[str, Any], task: Mapping[str, Any]) -> dict[str, Any]:
    ledger = plan.get("ledger", {})
    policy = [
        "Do not ask the user directly; promptly report missing input or authority to the native main.",
        "Resolve ordinary implementation decisions within existing authorization, without confirmation.",
        "Execute every currently ready Task Node concurrently; wait only at declared Node joins.",
        "Never serialize independent Nodes merely for convenience.",
        "Resolve local choices from the frozen contract, then the simplest safe implementation.",
        "Return every changed repository-relative path and focused evidence.",
    ]
    if task.get("verification") in RENDERED_VERIFICATIONS:
        policy.append("This Task's acceptance requires real rendered evidence, not source inspection.")
    return {
        "goal": plan.get("intent", {}).get("goal"),
        "authorized_scope": plan.get("intent", {}).get("scope"),
        "decisions": list(ledger.get("user_decided", [])) + list(ledger.get("defaulted", [])),
        "task": task,
        "execution_policy": policy,
    }


def _task_worker_selector(
    task: Mapping[str, Any],
    native_host: str | None,
    codex_home: str | None,
) -> tuple[str, dict[str, Any]]:
    """Prefer the optional configured Codex Frontend Worker for frontend Tasks."""

    tier_role = "worker-%s" % task.get("difficulty")
    if task.get("worker") == "frontend" and native_host == "codex":
        frontend = _selector_payload(FRONTEND_WORKER_ROLE, native_host, codex_home)
        if frontend.get("main_thread_fallback") is not True:
            return FRONTEND_WORKER_ROLE, frontend
    return tier_role, _selector_payload(tier_role, native_host, codex_home)


def dispatch_task(args: Any) -> int:
    """Dispatch one pending parallel Task, or re-dispatch a failed acceptance."""

    root = workspace_root(Path(args.root))
    with workspace_lock(root):
        plan, paths, checkpoints = _execution_context(root, args.plan)
        task = _task_by_code(plan, args.task)
        state = _state_by_code(checkpoints, args.task)
        if state.get("input_request"):
            raise ToolError("resolve this Task's recorded user input before dispatch")
        prior = state.get("dispatch")
        correction = (
            state.get("status") == "in_progress"
            and isinstance(prior, Mapping)
            and prior.get("phase") == "worker_correction"
        )
        if not correction and state.get("status") != "pending":
            raise ToolError("Task is not eligible for dispatch")
        attempts = int(prior.get("attempts", 0)) + 1 if correction and isinstance(prior, Mapping) else 1
        role, selector = _task_worker_selector(task, args.native_host, args.codex_home)
        dispatch_id = generate_id()
        state.update(
            {
                "status": "in_progress",
                "dispatch": {
                    "id": dispatch_id,
                    "role": role,
                    "attempts": attempts,
                    "host_agent_id": None,
                    "selector": selector,
                    "main_thread_fallback": selector.get("main_thread_fallback", False),
                    "phase": "worker_running",
                },
            }
        )
        checkpoints["delivery_status"] = "in_progress"
        write_json(paths["checkpoints"], checkpoints)
    payload = {
        "action": "dispatch_worker",
        "dispatch_id": dispatch_id,
        "task": args.task,
        "correction": correction,
        "assignment": WORKER_ASSIGNMENT_PREFIX,
        "prompt_cache_group": role,
        "role_reference": "references/worker.md",
        "brief": _leaf_brief(plan, task),
    }
    payload.update(selector)
    print(json.dumps(payload))
    return 0


def _plan_role_sessions(plan: Mapping[str, Any]) -> list[Any]:
    lifecycle = plan.get("lifecycle", {})
    return [lifecycle.get("designer_session"), lifecycle.get("reviewer_session")]


def _live_dispatches(plan: Mapping[str, Any], paths: Mapping[str, Path]) -> list[dict[str, Any]]:
    """Return every dispatch that a final callback could still advance."""

    live = [
        item
        for item in _plan_role_sessions(plan)
        if isinstance(item, dict) and item.get("status") == "active"
    ]
    if paths["checkpoints"].is_file():
        checkpoints = read_json(paths["checkpoints"])
        live.extend(
            state["dispatch"]
            for state in checkpoints.get("tasks", [])
            if isinstance(state.get("dispatch"), dict)
            and state["dispatch"].get("phase") == "worker_running"
        )
    return live


def _reject_reused_agent(
    plan: Mapping[str, Any], paths: Mapping[str, Path], agent_id: str, dispatch_id: str
) -> None:
    """One host agent id may never own two live dispatches at once.

    Without this, a single final callback could not be attributed to exactly one
    dispatch, and one child return would advance unrelated work.
    """

    for dispatch in _live_dispatches(plan, paths):
        if dispatch.get("id") != dispatch_id and dispatch.get("host_agent_id") == agent_id:
            raise ToolError("this agent id already owns another live dispatch")


def bind_agent(args: Any) -> int:
    root = workspace_root(Path(args.root))
    agent_id = _opaque_event_id(args.agent_id, "agent id")
    with workspace_lock(root):
        _, plan, paths = _load_raw_plan(root, args.plan)
        if args.target == plan.get("code"):
            session = next(
                (
                    item
                    for item in _plan_role_sessions(plan)
                    if isinstance(item, dict) and item.get("id") == args.dispatch_id and item.get("status") == "active"
                ),
                None,
            )
            if session is None:
                raise ToolError("no matching Plan role dispatch")
            if session.get("host_agent_id") not in {None, agent_id}:
                raise ToolError("dispatch already binds another agent")
            _reject_reused_agent(plan, paths, agent_id, args.dispatch_id)
            session["host_agent_id"] = agent_id
            write_json(paths["plan"], plan)
        else:
            checkpoints = read_json(paths["checkpoints"])
            dispatch = _state_by_code(checkpoints, args.target).get("dispatch")
            if not isinstance(dispatch, dict) or dispatch.get("id") != args.dispatch_id:
                raise ToolError("no matching Task dispatch")
            if dispatch.get("host_agent_id") not in {None, agent_id}:
                raise ToolError("dispatch already binds another agent")
            _reject_reused_agent(plan, paths, agent_id, args.dispatch_id)
            dispatch["host_agent_id"] = agent_id
            write_json(paths["checkpoints"], checkpoints)
    print("OK: bound")
    return 0


def delegation_failed(args: Any) -> int:
    """Record a conclusive delegation failure.

    Silence and elapsed time are never failures. A host-confirmed terminated
    child without a final callback is conclusive and belongs here.
    """

    root = workspace_root(Path(args.root))
    with workspace_lock(root):
        _, plan, paths = _load_raw_plan(root, args.plan)
        if args.target == plan.get("code"):
            target = next(
                (
                    item
                    for item in _plan_role_sessions(plan)
                    if isinstance(item, dict)
                    and item.get("id") == args.dispatch_id
                    and item.get("status") == "active"
                ),
                None,
            )
            document, path = plan, paths["plan"]
        else:
            checkpoints = read_json(paths["checkpoints"])
            dispatch = _state_by_code(checkpoints, args.target).get("dispatch")
            target = (
                dispatch
                if isinstance(dispatch, dict)
                and dispatch.get("id") == args.dispatch_id
                and dispatch.get("phase") == "worker_running"
                else None
            )
            document, path = checkpoints, paths["checkpoints"]
        if not isinstance(target, dict):
            raise ToolError("delegation failure does not match an active dispatch")
        target["attempts"] = int(target.get("attempts", 1)) + 1
        target["host_agent_id"] = None
        target["last_failure"] = public_summary(args.reason, "delegation failure")
        if target["attempts"] >= MAX_DELEGATION_ATTEMPTS:
            target["main_thread_fallback"] = True
        write_json(path, document)
    print(json.dumps({"attempts": target["attempts"], "main_thread_fallback": target.get("main_thread_fallback", False)}))
    return 0


def agent_complete(args: Any) -> int:
    """Consume one exact final callback, or nothing at all.

    An ambiguous match never advances state: one child return may only ever
    advance the single dispatch it is bound to.
    """

    root = workspace_root(Path(args.root))
    agent_id = _opaque_event_id(args.agent_id, "agent id")
    if not args.final:
        print(json.dumps({"consumed": False}))
        return 0
    with workspace_lock(root):
        _, plan, paths = _load_raw_plan(root, args.plan)
        checkpoints = read_json(paths["checkpoints"]) if paths["checkpoints"].is_file() else {}
        matches: list[tuple[str, dict[str, Any], str]] = []
        for name in ("designer_session", "reviewer_session"):
            session = plan.get("lifecycle", {}).get(name)
            if (
                isinstance(session, dict)
                and session.get("status") == "active"
                and session.get("agent_returned") is not True
                and session.get("host_agent_id") == agent_id
            ):
                action = (
                    "record_reviewer_findings"
                    if name == "reviewer_session"
                    else "close_designer_session"
                )
                matches.append((action, session, "plan"))
        for state in checkpoints.get("tasks", []):
            dispatch = state.get("dispatch")
            if (
                isinstance(dispatch, dict)
                and dispatch.get("host_agent_id") == agent_id
                and dispatch.get("phase") == "worker_running"
            ):
                matches.append(("accept_task", dispatch, str(state.get("code"))))
        if len(matches) != 1:
            print(json.dumps({"consumed": False, "matches": len(matches)}))
            return 0
        action, target, owner = matches[0]
        if owner == "plan":
            target["agent_returned"] = True
            target["agent_returned_at"] = _now()
            if target.get("role") == "reviewer":
                target["findings_recorded"] = False
                target.pop("findings_recorded_at", None)
            write_json(paths["plan"], plan)
            print(json.dumps({"consumed": True, "action": action}))
            return 0
        target["phase"] = "awaiting_acceptance"
        target["agent_returned_at"] = _now()
        write_json(paths["checkpoints"], checkpoints)
    print(json.dumps({"consumed": True, "action": action, "task": owner}))
    return 0


def main_complete(args: Any) -> int:
    """Record completion when the native main owns an exhausted delegation."""

    root = workspace_root(Path(args.root))
    with workspace_lock(root):
        _, plan, paths = _load_raw_plan(root, args.plan)
        if args.target == plan.get("code"):
            target = next(
                (
                    item
                    for item in _plan_role_sessions(plan)
                    if isinstance(item, dict)
                    and item.get("id") == args.dispatch_id
                    and item.get("status") == "active"
                    and item.get("main_thread_fallback") is True
                    and item.get("agent_returned") is not True
                ),
                None,
            )
            if target is None:
                raise ToolError("main completion requires an active exhausted Plan-role delegation")
            target["agent_returned"] = True
            target["agent_returned_at"] = _now()
            if target.get("role") == "reviewer":
                target["findings_recorded"] = False
                target.pop("findings_recorded_at", None)
            write_json(paths["plan"], plan)
            action = (
                "record_reviewer_findings"
                if target.get("role") in {"reviewer"}
                else "close_designer_session"
            )
        else:
            checkpoints = read_json(paths["checkpoints"])
            dispatch = _state_by_code(checkpoints, args.target).get("dispatch")
            if (
                not isinstance(dispatch, dict)
                or dispatch.get("id") != args.dispatch_id
                or dispatch.get("phase") != "worker_running"
                or dispatch.get("main_thread_fallback") is not True
            ):
                raise ToolError("main completion requires an active exhausted Task delegation")
            dispatch["phase"] = "awaiting_acceptance"
            dispatch["agent_returned_at"] = _now()
            write_json(paths["checkpoints"], checkpoints)
            action = "accept_task"
    print(json.dumps({"completed_by_main": True, "action": action, "target": args.target}))
    return 0


def record_reviewer_findings(args: Any) -> int:
    """Persist the sole Reviewer's complete privacy-safe out-of-scope handoff."""

    findings = _read_input(args.input)
    finding_issues = reviewer_findings_issues(
        Path("ReviewerFindings.json"),
        findings,
        persisted=False,
    )
    if finding_issues:
        raise ToolError(
            "invalid Reviewer findings: %s"
            % "; ".join(issue.message for issue in finding_issues)
        )
    persisted = [
        {**deepcopy(dict(finding)), "followup_plan": None}
        for finding in findings
    ]
    root = workspace_root(Path(args.root))
    with workspace_lock(root):
        _, plan, paths = _load_raw_plan(root, args.plan)
        session = plan.get("lifecycle", {}).get("reviewer_session")
        if (
            not isinstance(session, dict)
            or session.get("status") != "active"
            or session.get("id") != args.dispatch_id
        ):
            raise ToolError("Reviewer session correlation mismatch")
        if session.get("agent_returned") is not True:
            raise ToolError("Reviewer findings require a final role return")
        if session.get("findings_recorded") is True:
            raise ToolError("Reviewer findings are already recorded for this return")
        session["out_of_scope_findings"] = persisted
        session["findings_recorded"] = True
        session["findings_recorded_at"] = _now()
        issues = validate_plan_document(paths["plan"], plan)
        if issues:
            raise ToolError(
                "refusing invalid Reviewer findings: %s"
                % "; ".join(issue.message for issue in issues)
            )
        write_json(paths["plan"], plan)
    print(
        json.dumps(
            {
                "recorded": len(persisted),
                "dispatch_id": args.dispatch_id,
                "action": "next_action",
            }
        )
    )
    return 0


def accept_task(args: Any) -> int:
    """Run the frozen focused regression and complete exactly one Task."""

    root = workspace_root(Path(args.root))
    project = _project_root(root)
    with workspace_lock(root):
        plan, paths, checkpoints = _execution_context(root, args.plan)
        task = deepcopy(_task_by_code(plan, args.task))
        state = _state_by_code(checkpoints, args.task)
        dispatch = state.get("dispatch")
        if state.get("input_request"):
            raise ToolError("resolve this Task's recorded user input before acceptance")
        if state.get("status") != "in_progress" or not isinstance(dispatch, dict):
            raise ToolError("Task is not awaiting acceptance")
        if dispatch.get("phase") not in {"awaiting_acceptance", "worker_correction"}:
            raise ToolError("Task is not awaiting acceptance")
        dispatch_id = dispatch.get("id")
        task_digest = sha256_value(task)

    passed, receipts = _run_commands(project, task["focused_regression"]["commands"])
    content_fingerprint = fingerprint_paths(project, task["focused_regression"]["paths"])

    with workspace_lock(root):
        plan, paths, checkpoints = _execution_context(root, args.plan)
        current_task = _task_by_code(plan, args.task)
        state = _state_by_code(checkpoints, args.task)
        dispatch = state.get("dispatch")
        if (
            sha256_value(current_task) != task_digest
            or state.get("status") != "in_progress"
            or state.get("input_request")
            or not isinstance(dispatch, dict)
            or dispatch.get("id") != dispatch_id
            or dispatch.get("phase") not in {"awaiting_acceptance", "worker_correction"}
        ):
            raise ToolError("Task acceptance changed while focused regression was running")
        state["evidence"].append(
            {
                "kind": "focused_regression",
                "passed": passed,
                "commands": receipts,
                "content_fingerprint": content_fingerprint,
                "recorded_at": _now(),
            }
        )
        if passed:
            state["status"] = "completed"
            state["dispatch"] = None
        else:
            dispatch["phase"] = "worker_correction"
        write_json(paths["checkpoints"], checkpoints)
    if not passed:
        raise ToolError(
            "focused acceptance failed; repair this Task in the native main and rerun accept-task, "
            "or run dispatch-task again to send one correction Worker"
        )
    print(json.dumps({"accepted": True, "task": args.task}))
    return 0


def record_task_input(args: Any) -> int:
    """Keep missing user input visible across context loss without changing Task history."""

    root = workspace_root(Path(args.root))
    summary = public_summary(args.needed or args.resolved, "user input summary")
    action = "next_action"
    with workspace_lock(root):
        plan, paths, checkpoints = _execution_context(root, args.plan)
        state = _state_by_code(checkpoints, args.task)
        if state.get("status") in {"blocked_by_authority", "blocked_by_environment"}:
            raise ToolError("a hard-blocked Task cannot be reopened by recording input")
        if args.needed:
            state["input_request"] = summary
        else:
            if not state.get("input_request"):
                raise ToolError("this Task has no pending user input")
            state["evidence"].append({
                "kind": "user_input",
                "request": state.pop("input_request"),
                "resolution": summary,
                "recorded_at": _now(),
            })
            reviewer = plan.get("lifecycle", {}).get("reviewer_session")
            if isinstance(reviewer, dict) and reviewer.get("status") == "active":
                reviewer["agent_returned"] = False
                write_json(paths["plan"], plan)
                action = "resume_reviewer"
        write_json(paths["checkpoints"], checkpoints)
    print(json.dumps({"task": args.task, "awaiting_input": bool(args.needed), "action": action}))
    return 0


def _require_resolved_input(checkpoints: Mapping[str, Any]) -> None:
    if any(item.get("input_request") for item in checkpoints.get("tasks", [])):
        raise ToolError("resolve recorded user input before final verification or closure")


def block_task(args: Any) -> int:
    root = workspace_root(Path(args.root))
    status = "blocked_by_authority" if args.kind == "authority" else "blocked_by_environment"
    reason = public_summary(args.reason, "Task blocker")
    with workspace_lock(root):
        plan, paths, checkpoints = _execution_context(root, args.plan)
        state = _state_by_code(checkpoints, args.task)
        reviewer = plan.get("lifecycle", {}).get("reviewer_session")
        review_blocker = (
            isinstance(reviewer, Mapping)
            and reviewer.get("status") == "active"
            and state.get("input_request")
        )
        if state.get("status") == "completed" and not review_blocker:
            raise ToolError("a completed Task is frozen")
        state.pop("input_request", None)
        state.update({"status": status, "status_reason": reason, "dispatch": None})
        write_json(paths["checkpoints"], checkpoints)
    print(json.dumps({"blocked": True, "status": status, "affected_tasks": [args.task]}))
    return 0


def _execute_full_regression(
    project: Path,
    plan: Mapping[str, Any],
    paths: Mapping[str, Path],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    regression = plan["spec"]["full_regression"]
    passed, receipts, diagnostics = _run_commands_with_diagnostics(
        project, regression["commands"]
    )
    return (
        {
            "passed": passed,
            "commands": receipts,
            "content_fingerprint": _full_regression_fingerprint(project, plan, paths),
            "recorded_at": _now(),
        },
        diagnostics,
    )


def _reviewer_brief(
    plan: Mapping[str, Any],
    checkpoints: Mapping[str, Any],
    regression: Mapping[str, Any],
    rendered: list[Any],
) -> dict[str, Any]:
    return {
        "plan_path": "%s/%s" % (plan["directory"], PLAN_NAME),
        "checkpoints_path": "%s/%s" % (plan["directory"], CHECKPOINTS_NAME),
        "plan": semantic_payload(plan),
        "checkpoints": deepcopy(dict(checkpoints)),
        "full_regression": {
            "contract": deepcopy(plan["spec"]["full_regression"]),
            "result": deepcopy(dict(regression)),
            "diagnostics_handoff": (
                "Attach the ephemeral diagnostics from the immediately preceding "
                "run-full-regression result; never persist them."
            ),
        },
        "rendered_evidence_tasks": list(rendered),
        "out_of_scope_finding_contract": {
            "rule": (
                "Return one item per cohesive confirmed defect outside the authorized Plan; "
                "return an empty array when there are none."
            ),
            "fields": [
                "title",
                "summary",
                "impact",
                "evidence",
                "paths",
                "scope_reason",
                "success",
                "risk_boundary",
            ],
            "handoff": (
                "The native main records the complete array after every Reviewer return. "
                "Only close-reviewer-session creates separate draft repair Plans."
            ),
        },
        "execution_policy": [
            "Audit the current source, tests, Task evidence, and supplied full-regression diagnostics.",
            "Directly repair every defect inside the authorized Plan, across all Task ownership boundaries.",
            "Do not repair a confirmed defect outside the authorized Plan or create its repair Plan yourself.",
            "A defect required for this Plan's success or safety is in scope, not a follow-up.",
            "Return the complete structured out_of_scope_findings array after every response, including resumes.",
            "Do not run or wait for the full regression; Python runs it outside Reviewer model time.",
            "Use bounded focused checks only when they materially guide a repair.",
            "Do not create or stage a Git commit; the native main owns that action after close.",
            "Do not ask the user directly or create another Reviewer or Repair Task.",
            "Promptly report missing user input or authority to the native main; continue independent repairs.",
        ],
    }


def run_full_regression(args: Any) -> int:
    """Run the complete regression as its own deterministic delivery stage."""

    root = workspace_root(Path(args.root))
    project = _project_root(root)
    with workspace_lock(root):
        plan, paths, checkpoints = _execution_context(root, args.plan)
        _require_resolved_input(checkpoints)
        if any(item.get("status") not in TERMINAL_TASK_STATUSES for item in checkpoints.get("tasks", [])):
            raise ToolError("full regression requires every Task terminal")
        reviewer = plan.get("lifecycle", {}).get("reviewer_session")
        if isinstance(reviewer, Mapping) and (
            reviewer.get("status") != "active" or reviewer.get("agent_returned") is not True
        ):
            raise ToolError("full regression cannot run while the Reviewer is working")
        if isinstance(reviewer, Mapping) and not _reviewer_findings_recorded(reviewer):
            raise ToolError("record Reviewer out-of-scope findings before full regression")
        plan_digest = semantic_digest(plan)
        checkpoints_digest = sha256_value(checkpoints)

    regression, diagnostics = _execute_full_regression(project, plan, paths)

    with workspace_lock(root):
        plan, paths, checkpoints = _execution_context(root, args.plan)
        if (
            semantic_digest(plan) != plan_digest
            or sha256_value(checkpoints) != checkpoints_digest
            or any(
                item.get("status") not in TERMINAL_TASK_STATUSES
                for item in checkpoints.get("tasks", [])
            )
        ):
            raise ToolError("delivery changed while full regression was running")
        checkpoints["full_regression"] = regression
        reviewer = plan.get("lifecycle", {}).get("reviewer_session")
        if isinstance(reviewer, dict):
            if reviewer.get("status") != "active" or reviewer.get("agent_returned") is not True:
                raise ToolError("Reviewer state changed while full regression was running")
            if regression["passed"] is True:
                reviewer.pop("repair_required", None)
                action = "close_reviewer_session"
            else:
                reviewer["repair_required"] = True
                reviewer["agent_returned"] = False
                action = "resume_reviewer"
            write_json(paths["plan"], plan)
        else:
            action = "open_reviewer_session"
        write_json(paths["checkpoints"], checkpoints)
    print(
        json.dumps(
            {
                "completed": True,
                "passed": regression["passed"],
                "action": action,
                "full_regression": {
                    "contract": deepcopy(plan["spec"]["full_regression"]),
                    "result": regression,
                    "diagnostics": diagnostics,
                },
            }
        )
    )
    return 0


def open_reviewer_session(args: Any) -> int:
    root = workspace_root(Path(args.root))
    project = _project_root(root)
    with workspace_lock(root):
        _, current, _ = _load_raw_plan(root, args.plan)
        if current.get("phase") != "authorized":
            raise ToolError("the Reviewer opens only on an authorized Plan with no open continuation")
        plan, paths, checkpoints = _execution_context(root, args.plan)
        _require_resolved_input(checkpoints)
        if any(item.get("status") not in TERMINAL_TASK_STATUSES for item in checkpoints.get("tasks", [])):
            raise ToolError("the Reviewer requires every Task terminal")
        if plan.get("lifecycle", {}).get("reviewer_session") is not None:
            raise ToolError("the Reviewer runs exactly once")
        regression = checkpoints.get("full_regression")
        if not isinstance(regression, Mapping):
            raise ToolError("run the independent full regression before opening the Reviewer")
        if regression.get("content_fingerprint") != _full_regression_fingerprint(
            project, plan, paths
        ):
            raise ToolError("full regression evidence is stale; run it again before opening the Reviewer")
        rendered = [
            task.get("code")
            for task in plan.get("spec", {}).get("tasks", [])
            if task.get("verification") in RENDERED_VERIFICATIONS
        ]
        selector = _selector_payload("reviewer", args.native_host, args.codex_home)
        dispatch_id = generate_id()
        plan["lifecycle"]["reviewer_session"] = {
            "count": 1,
            "id": dispatch_id,
            "role": "reviewer",
            "status": "active",
            "opened_at": _now(),
            "host_agent_id": None,
            "attempts": 1,
            "selector": selector,
            "main_thread_fallback": selector.get("main_thread_fallback", False),
            "out_of_scope_findings": [],
            "findings_recorded": False,
        }
        write_json(paths["plan"], plan)
    payload = {
        "action": "dispatch_reviewer",
        "dispatch_id": dispatch_id,
        "role_reference": "references/reviewer.md",
        "brief": _reviewer_brief(plan, checkpoints, regression, rendered),
    }
    payload.update(selector)
    print(json.dumps(payload))
    return 0


def _materialize_reviewer_followups(
    root: Path,
    manifest: dict[str, Any],
    source_plan: Mapping[str, Any],
    session: dict[str, Any],
) -> list[dict[str, Any]]:
    """Create one unapproved draft Plan per cohesive out-of-scope finding."""

    findings = session.get("out_of_scope_findings", [])
    if not isinstance(findings, list):
        raise ToolError("Reviewer findings must be recorded before close")
    entries = manifest.get("plans", [])
    used_codes = {
        str(entry.get("code")) for entry in entries if isinstance(entry, Mapping)
    }
    used_directories = {
        str(entry.get("directory")) for entry in entries if isinstance(entry, Mapping)
    }
    next_code_number = len(used_codes) + 1
    next_directory_number = 1
    source_reference = "%s/%s" % (source_plan["directory"], PLAN_NAME)
    pending_writes: list[tuple[dict[str, Any], dict[str, Path]]] = []
    handoff: list[dict[str, Any]] = []

    for finding in findings:
        if not isinstance(finding, dict):
            raise ToolError("Reviewer findings must be valid objects")
        while True:
            code = "PLAN-%03d" % next_code_number
            next_code_number += 1
            if code not in used_codes:
                used_codes.add(code)
                break
        while True:
            directory = "%s-review-followup-%02d" % (
                source_plan["directory"],
                next_directory_number,
            )
            next_directory_number += 1
            if directory not in used_directories and not (root / directory).exists():
                used_directories.add(directory)
                break

        draft = plan_template()
        draft["code"] = code
        draft["title"] = finding["title"]
        draft["directory"] = directory
        draft["intent"]["goal"] = finding["summary"]
        draft["intent"]["scope"] = {
            "in": [finding["summary"], *finding["paths"]],
            "out": ["Changes unrelated to %s's confirmed repair outcome." % code],
        }
        draft["intent"]["success"] = deepcopy(finding["success"])
        draft["intent"]["risk_boundary"] = deepcopy(finding["risk_boundary"])
        primary_path = finding["paths"][0]
        draft["ledger"]["observed"] = [
            {"fact": finding["summary"], "source": primary_path},
            {"fact": finding["impact"], "source": primary_path},
            {"fact": finding["evidence"], "source": primary_path},
            {"fact": finding["scope_reason"], "source": source_reference},
        ]
        draft_paths = {
            "directory": root / directory,
            "plan": root / directory / PLAN_NAME,
            "checkpoints": root / directory / CHECKPOINTS_NAME,
        }
        issues = validate_plan_document(draft_paths["plan"], draft)
        if issues:
            raise ToolError(
                "cannot materialize Reviewer follow-up: %s"
                % "; ".join(issue.message for issue in issues)
            )
        entry = {
            "code": code,
            "title": draft["title"],
            "directory": directory,
            "plan": "%s/%s" % (directory, PLAN_NAME),
        }
        entries.append(entry)
        finding["followup_plan"] = code
        pending_writes.append((draft, draft_paths))
        handoff.append(
            {
                "code": code,
                "title": draft["title"],
                "directory": directory,
                "phase": "draft",
                "authorization_required": True,
                "impact": finding["impact"],
            }
        )

    for draft, draft_paths in pending_writes:
        _save_plan(draft_paths, draft)
    return handoff


def close_reviewer_session(args: Any) -> int:
    root = workspace_root(Path(args.root))
    project = _project_root(root)
    with workspace_lock(root):
        manifest = load_manifest(root)
        plan, paths, checkpoints = _execution_context(root, args.plan)
        _require_resolved_input(checkpoints)
        session = plan.get("lifecycle", {}).get("reviewer_session")
        if not isinstance(session, dict) or session.get("status") != "active" or session.get("id") != args.dispatch_id:
            raise ToolError("Reviewer session correlation mismatch")
        if session.get("agent_returned") is not True:
            raise ToolError("Reviewer session has not reached a final role boundary")
        if not _reviewer_findings_recorded(session):
            raise ToolError("record Reviewer out-of-scope findings before close")
        if any(item.get("status") not in TERMINAL_TASK_STATUSES for item in checkpoints.get("tasks", [])):
            raise ToolError("closing review requires every Task terminal")
        blocked = [
            item
            for item in checkpoints.get("tasks", [])
            if str(item.get("status", "")).startswith("blocked_by_")
        ]
        if args.blocked_reason:
            if not blocked:
                raise ToolError("a blocked close requires at least one authority or environment blocker")
            session["status"] = "blocked"
            session["closed_at"] = _now()
            session["blocker_evidence"] = {
                "reason": public_summary(args.blocked_reason, "Reviewer blocker"),
                "targets": [item.get("code") for item in blocked],
            }
            plan["phase"] = "blocked"
            followup_plans = _materialize_reviewer_followups(
                root, manifest, plan, session
            )
            _save_plan(paths, plan)
            checkpoints["delivery_status"] = "blocked"
            write_json(paths["checkpoints"], checkpoints)
            if followup_plans:
                write_json(root / MANIFEST_NAME, manifest)
            print(
                json.dumps(
                    {
                        "blocked": True,
                        "reviewer_session_count": 1,
                        "followup_plans": followup_plans,
                        "pending_repair_plans": len(followup_plans),
                        "user_handoff_required": bool(followup_plans),
                    }
                )
            )
            return 0
        if blocked:
            raise ToolError("blocked Tasks require --blocked-reason and cannot be reported as completed")
        regression = checkpoints.get("full_regression")
        if not isinstance(regression, Mapping):
            raise ToolError("run the independent full regression before closing the Reviewer")
        current_fingerprint = _full_regression_fingerprint(project, plan, paths)
        if regression.get("passed") is not True or current_fingerprint != regression.get("content_fingerprint"):
            raise ToolError("Reviewer repairs require the independent full regression before close")
        session.pop("repair_required", None)
        session["status"] = "completed"
        session["closed_at"] = _now()
        plan["phase"] = "completed"
        followup_plans = _materialize_reviewer_followups(root, manifest, plan, session)
        _save_plan(paths, plan)
        checkpoints["delivery_status"] = "completed"
        write_json(paths["checkpoints"], checkpoints)
        if followup_plans:
            write_json(root / MANIFEST_NAME, manifest)
    print(
        json.dumps(
            {
                "completed": True,
                "reviewer_session_count": 1,
                "followup_plans": followup_plans,
                "pending_repair_plans": len(followup_plans),
                "user_handoff_required": bool(followup_plans),
                "version_control_handoff": _version_control_handoff(plan),
            }
        )
    )
    return 0
