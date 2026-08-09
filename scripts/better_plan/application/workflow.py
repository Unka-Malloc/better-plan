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

from ..domain.models import (
    CHECKPOINTS_NAME,
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
    plan_template,
    public_summary,
    semantic_digest,
    sha256_value,
    task_state,
)
from ..domain.validation import (
    authority_expansion_issues,
    plan_readiness_issues,
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
COMMAND_TIMEOUT_SECONDS = 1800
OUTPUT_TAIL_CHARACTERS = 2000


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _opaque_event_id(value: Any, field: str) -> str:
    if not isinstance(value, str) or OPAQUE_EVENT_ID_PATTERN.fullmatch(value) is None:
        raise ToolError("%s must be an opaque host identifier" % field)
    return value


def _project_root(workspace: Path) -> Path:
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


def _run_commands(project_root: Path, commands: list[str]) -> tuple[bool, list[dict[str, Any]]]:
    """Run commands, persisting only receipts while surfacing failures to the operator."""

    receipts: list[dict[str, Any]] = []
    for command in commands:
        try:
            completed = subprocess.run(
                command,
                cwd=str(project_root),
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=COMMAND_TIMEOUT_SECONDS,
            )
            exit_code: int | None = completed.returncode
            outcome = "passed" if exit_code == 0 else "failed"
            output = completed.stdout.decode("utf-8", "replace") if completed.stdout else ""
        except subprocess.TimeoutExpired:
            exit_code = None
            outcome = "timeout"
            output = ""
        receipts.append(
            {
                "command_sha256": hashlib.sha256(command.encode("utf-8")).hexdigest(),
                "outcome": outcome,
                "exit_code": exit_code,
                "recorded_at": _now(),
            }
        )
        if outcome != "passed":
            tail = output[-OUTPUT_TAIL_CHARACTERS:]
            print("command %s (%s)" % (outcome, command), file=sys.stderr)
            if tail.strip():
                print(tail, file=sys.stderr)
            return False, receipts
    return True, receipts


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
    payload = {
        "action": "dispatch_designer",
        "dispatch_id": dispatch_id,
        "plan_path": "%s/%s" % (plan["directory"], PLAN_NAME),
        "role_reference": "references/designer.md",
        "knowledge_references": ["references/design-patterns.md"],
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
        session["status"] = "completed"
        session["closed_at"] = _now()
        if restored:
            session["restored"] = restored
        plan["phase"] = "ready"
        _save_plan(paths, plan)
        issues = plan_readiness_issues(paths["plan"], plan)
    print(
        json.dumps(
            {
                "phase": "ready",
                "ready": not issues,
                "restored": restored,
                "open_issues": [issue.message for issue in issues],
            }
        )
    )
    return 0


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
        checkpoints = read_json(paths["checkpoints"])
        started = {
            str(item.get("code"))
            for item in checkpoints.get("tasks", [])
            if item.get("status") != "pending"
        }
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
            "started_task_digests": {
                str(task.get("code")): sha256_value(task)
                for task in plan.get("spec", {}).get("tasks", [])
                if str(task.get("code")) in started
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
        for code, digest in session.get("started_task_digests", {}).items():
            if code not in by_code or sha256_value(by_code[code]) != digest:
                raise ToolError("continuation changed a started Task")
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
            }
        )
        del candidate["lifecycle"]["continuation_session"]
        issues = plan_readiness_issues(paths["plan"], candidate)
        if issues:
            raise ToolError("continuation is not ready: %s" % "; ".join(issue.message for issue in issues))
        plan = candidate
        _save_plan(paths, plan)
        checkpoints = read_json(paths["checkpoints"])
        existing = {str(item.get("code")): item for item in checkpoints.get("tasks", [])}
        checkpoints["tasks"] = [
            existing.get(str(task.get("code")), task_state(task.get("code")))
            for task in plan.get("spec", {}).get("tasks", [])
        ]
        checkpoints.update({"revision": revision, "semantic_digest": digest})
        # A revision may add work behind an already blocked prerequisite; keep the
        # blocked frontier closed so no Task is left permanently unreachable.
        for state in list(checkpoints["tasks"]):
            status = str(state.get("status", ""))
            if status.startswith("blocked_by_"):
                _propagate_blocker(
                    plan, checkpoints, str(state.get("code")), status, str(state.get("status_reason", "upstream blocker"))
                )
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


def _eligible(task: Mapping[str, Any], checkpoints: Mapping[str, Any]) -> bool:
    states = {str(item.get("code")): item.get("status") for item in checkpoints.get("tasks", [])}
    return all(states.get(str(code)) == "completed" for code in task.get("prerequisites", []))


def _propagate_blocker(
    plan: Mapping[str, Any],
    checkpoints: dict[str, Any],
    seed: str,
    status: str,
    reason: str,
) -> set[str]:
    affected = {seed}
    changed = True
    while changed:
        changed = False
        for task in plan.get("spec", {}).get("tasks", []):
            state = _state_by_code(checkpoints, str(task.get("code")))
            if state.get("status") == "pending" and affected.intersection(task.get("prerequisites", [])):
                state.update(
                    {
                        "status": status,
                        "status_reason": "upstream blocker: %s" % reason,
                        "dispatch": None,
                    }
                )
                affected.add(str(task.get("code")))
                changed = True
    return affected


PRE_DELIVERY_ACTIONS = {
    "draft": "open_designer_session",
    "designing": "close_designer_session",
    "ready": "authorize_plan",
    "revising": "close_continuation",
    "completed": "delivery_complete",
    "blocked": "delivery_blocked",
}


def next_action(args: Any) -> int:
    """Name exactly one next action for every reachable delivery state."""

    root = workspace_root(Path(args.root))
    with workspace_lock(root):
        _, plan, paths = _load_raw_plan(root, args.plan)
        phase = str(plan.get("phase"))
        if phase != "authorized":
            print(json.dumps({"action": PRE_DELIVERY_ACTIONS[phase], "phase": phase}))
            return 0
        checkpoints = read_json(paths["checkpoints"])
    corrections: list[str] = []
    awaiting: list[str] = []
    running: list[str] = []
    exhausted: list[str] = []
    eligible: list[str] = []
    unreachable: list[str] = []
    for task in plan.get("spec", {}).get("tasks", []):
        code = str(task.get("code"))
        state = _state_by_code(checkpoints, code)
        status = state.get("status")
        dispatch = state.get("dispatch")
        dispatch_phase = dispatch.get("phase") if isinstance(dispatch, Mapping) else None
        if status == "in_progress" and dispatch_phase == "worker_correction":
            corrections.append(code)
        elif status == "in_progress" and dispatch_phase == "awaiting_acceptance":
            awaiting.append(code)
        elif status == "in_progress":
            (exhausted if isinstance(dispatch, Mapping) and dispatch.get("main_thread_fallback") else running).append(code)
        elif status == "pending" and _eligible(task, checkpoints):
            eligible.append(code)
        elif status == "pending":
            unreachable.append(code)
    reviewer = plan.get("lifecycle", {}).get("reviewer_session")
    reviewer_active = isinstance(reviewer, Mapping) and reviewer.get("status") == "active"
    if corrections:
        action = "repair_tasks"
    elif awaiting:
        action = "accept_tasks"
    elif exhausted:
        action = "complete_in_main"
    elif running:
        action = "await_tasks"
    elif eligible:
        action = "dispatch_tasks"
    elif unreachable:
        # Every remaining Task sits behind a blocked prerequisite. Record the
        # blockers so delivery can still close through the sole Reviewer.
        action = "block_unreachable_tasks"
    elif reviewer is None:
        action = "open_reviewer_session"
    else:
        action = "await_reviewer" if reviewer_active and reviewer.get("agent_returned") is not True else "close_reviewer_session"
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
                "unreachable": unreachable,
            }
        )
    )
    return 0


def _leaf_brief(plan: Mapping[str, Any], task: Mapping[str, Any]) -> dict[str, Any]:
    upstream_codes = set(task.get("prerequisites", []))
    upstream = [
        {"code": candidate.get("code"), "outcome": candidate.get("outcome"), "outputs": candidate.get("outputs")}
        for candidate in plan.get("spec", {}).get("tasks", [])
        if candidate.get("code") in upstream_codes
    ]
    ledger = plan.get("ledger", {})
    policy = [
        "Do not ask the user questions after authorization.",
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
        "upstream": upstream,
        "execution_policy": policy,
    }


def dispatch_task(args: Any) -> int:
    """Dispatch an eligible Task, or re-dispatch one that failed acceptance."""

    root = workspace_root(Path(args.root))
    with workspace_lock(root):
        plan, paths, checkpoints = _execution_context(root, args.plan)
        task = _task_by_code(plan, args.task)
        state = _state_by_code(checkpoints, args.task)
        prior = state.get("dispatch")
        correction = (
            state.get("status") == "in_progress"
            and isinstance(prior, Mapping)
            and prior.get("phase") == "worker_correction"
        )
        if not correction and (state.get("status") != "pending" or not _eligible(task, checkpoints)):
            raise ToolError("Task is not eligible for dispatch")
        attempts = int(prior.get("attempts", 0)) + 1 if correction and isinstance(prior, Mapping) else 1
        role = "worker-%s" % task.get("difficulty")
        selector = _selector_payload(role, args.native_host, args.codex_home)
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
                and session.get("host_agent_id") == agent_id
            ):
                matches.append(("close_%s" % name, session, "plan"))
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
                ),
                None,
            )
            if target is None:
                raise ToolError("main completion requires an active exhausted Plan-role delegation")
            target["agent_returned"] = True
            target["agent_returned_at"] = _now()
            write_json(paths["plan"], plan)
            action = (
                "close_reviewer_session"
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


def accept_task(args: Any) -> int:
    """Run the frozen focused regression and complete exactly one Task."""

    root = workspace_root(Path(args.root))
    project = _project_root(root)
    with workspace_lock(root):
        plan, paths, checkpoints = _execution_context(root, args.plan)
        task = _task_by_code(plan, args.task)
        state = _state_by_code(checkpoints, args.task)
        dispatch = state.get("dispatch")
        if state.get("status") != "in_progress" or not isinstance(dispatch, dict):
            raise ToolError("Task is not awaiting acceptance")
        if dispatch.get("phase") not in {"awaiting_acceptance", "worker_correction"}:
            raise ToolError("Task is not awaiting acceptance")
        passed, receipts = _run_commands(project, task["focused_regression"]["commands"])
        state["evidence"].append(
            {
                "kind": "focused_regression",
                "passed": passed,
                "commands": receipts,
                "content_fingerprint": fingerprint_paths(project, task["focused_regression"]["paths"]),
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


def block_task(args: Any) -> int:
    root = workspace_root(Path(args.root))
    status = "blocked_by_authority" if args.kind == "authority" else "blocked_by_environment"
    reason = public_summary(args.reason, "Task blocker")
    with workspace_lock(root):
        plan, paths, checkpoints = _execution_context(root, args.plan)
        state = _state_by_code(checkpoints, args.task)
        if state.get("status") == "completed":
            raise ToolError("a completed Task is frozen")
        state.update({"status": status, "status_reason": reason, "dispatch": None})
        affected = _propagate_blocker(plan, checkpoints, args.task, status, reason)
        write_json(paths["checkpoints"], checkpoints)
    print(json.dumps({"blocked": True, "status": status, "affected_tasks": sorted(affected)}))
    return 0


def open_reviewer_session(args: Any) -> int:
    root = workspace_root(Path(args.root))
    with workspace_lock(root):
        _, plan, paths = _load_raw_plan(root, args.plan)
        if plan.get("phase") != "authorized":
            raise ToolError("the Reviewer opens only on an authorized Plan with no open continuation")
        checkpoints = read_json(paths["checkpoints"])
        if any(item.get("status") not in TERMINAL_TASK_STATUSES for item in checkpoints.get("tasks", [])):
            raise ToolError("the Reviewer requires every Task terminal")
        if plan.get("lifecycle", {}).get("reviewer_session") is not None:
            raise ToolError("the Reviewer runs exactly once")
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
        }
        write_json(paths["plan"], plan)
    payload = {
        "action": "dispatch_reviewer",
        "dispatch_id": dispatch_id,
        "plan": plan["code"],
        "role_reference": "references/reviewer.md",
        "rendered_evidence_tasks": rendered,
        "tasks": [task.get("code") for task in plan.get("spec", {}).get("tasks", [])],
    }
    payload.update(selector)
    print(json.dumps(payload))
    return 0


def close_reviewer_session(args: Any) -> int:
    root = workspace_root(Path(args.root))
    project = _project_root(root)
    with workspace_lock(root):
        _, plan, paths = _load_raw_plan(root, args.plan)
        session = plan.get("lifecycle", {}).get("reviewer_session")
        if not isinstance(session, dict) or session.get("status") != "active" or session.get("id") != args.dispatch_id:
            raise ToolError("Reviewer session correlation mismatch")
        if session.get("agent_returned") is not True:
            raise ToolError("Reviewer session has not reached a final role boundary")
        checkpoints = read_json(paths["checkpoints"])
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
            _save_plan(paths, plan)
            checkpoints["delivery_status"] = "blocked"
            write_json(paths["checkpoints"], checkpoints)
            print(json.dumps({"blocked": True, "reviewer_session_count": 1}))
            return 0
        if blocked:
            raise ToolError("blocked Tasks require --blocked-reason and cannot be reported as completed")
        passed, receipts = _run_commands(project, plan["spec"]["full_regression"]["commands"])
        session["full_regression"] = {
            "passed": passed,
            "commands": receipts,
            "content_fingerprint": fingerprint_paths(project, plan["spec"]["full_regression"]["paths"]),
            "recorded_at": _now(),
        }
        if not passed:
            # The session stays open and closable: the same Reviewer repairs the
            # failure and this command is rerun. Clearing the returned flag here
            # would strand a delivery whose child cannot emit a second callback.
            session["repair_required"] = True
            write_json(paths["plan"], plan)
            raise ToolError(
                "final regression failed; repair inside this same Reviewer session and rerun close-reviewer-session"
            )
        session.pop("repair_required", None)
        session["status"] = "completed"
        session["closed_at"] = _now()
        plan["phase"] = "completed"
        _save_plan(paths, plan)
        checkpoints["delivery_status"] = "completed"
        write_json(paths["checkpoints"], checkpoints)
    print(json.dumps({"completed": True, "reviewer_session_count": 1}))
    return 0
