"""Public CLI for the Better Plan v3 protocol."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import argparse
import json
import sys

from ..application import workflow
from ..domain.models import (
    CHECKPOINTS_SCHEMA,
    MANIFEST_TEMPLATE,
    PLAN_TEMPLATE,
    ToolError,
    question_template,
    task_template,
)
from ..domain.tree import render_plan_tree, status_payload
from ..infrastructure.workspace import (
    load_manifest,
    load_plan,
    read_json,
    validate_workspace,
    workspace_root,
)


def validate_command(args: argparse.Namespace) -> int:
    root = workspace_root(Path(args.root))
    issues = validate_workspace(root)
    if args.json:
        print(json.dumps({"valid": not issues, "issues": issues}))
    elif issues:
        for issue in issues:
            print("error: %s" % issue)
    elif not args.quiet:
        print("OK: Better Plan v3 workspace is valid")
    return 0 if not issues else 1


def schema_command(args: argparse.Namespace) -> int:
    payloads: dict[str, Any] = {
        "manifest": MANIFEST_TEMPLATE,
        "plan": PLAN_TEMPLATE,
        "task": task_template(),
        "question": question_template(),
        "checkpoints": {
            "schema": CHECKPOINTS_SCHEMA,
            "plan": "PLAN-001",
            "revision": 1,
            "semantic_digest": "SHA256",
            "delivery_status": "pending",
            "tasks": [],
        },
    }
    print(json.dumps(payloads[args.kind], indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def tree_command(args: argparse.Namespace) -> int:
    root = workspace_root(Path(args.root))
    entries = load_manifest(root).get("plans", [])
    if args.plan:
        entries = [
            entry
            for entry in entries
            if args.plan in {entry.get("code"), entry.get("title"), entry.get("directory")}
        ]
    if not entries:
        raise ToolError("no matching Plan")
    rendered: list[str] = []
    for entry in entries:
        _, plan, paths = load_plan(root, str(entry.get("code")))
        checkpoints = read_json(paths["checkpoints"]) if paths["checkpoints"].is_file() else None
        rendered.append(render_plan_tree(plan, checkpoints, details=args.details))
    print("\n\n".join(rendered))
    return 0


def status_command(args: argparse.Namespace) -> int:
    root = workspace_root(Path(args.root))
    values = []
    for entry in load_manifest(root).get("plans", []):
        _, plan, paths = load_plan(root, str(entry.get("code")))
        checkpoints = read_json(paths["checkpoints"]) if paths["checkpoints"].is_file() else None
        values.append(status_payload(plan, checkpoints))
    if args.json:
        print(json.dumps({"plans": values}))
    else:
        for value in values:
            print("%(code)s [%(phase)s] tasks=%(task_counts)s" % value)
    return 0


def _add_plan(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--plan", required=True)


def _add_host(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--native-host", choices=("codex",))
    parser.add_argument("--codex-home", help=argparse.SUPPRESS)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Better Plan v3 utility")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="validate one v3 workspace")
    validate.add_argument("root", nargs="?", default=".")
    validate.add_argument("--quiet", action="store_true")
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(func=validate_command)

    schema = subparsers.add_parser("schema", help="print one canonical shape")
    schema.add_argument("kind", choices=("manifest", "plan", "task", "question", "checkpoints"))
    schema.set_defaults(func=schema_command)

    init = subparsers.add_parser("init-plan", help="create one draft Delivery Plan")
    init.add_argument("root", nargs="?", default=".")
    init.add_argument("--code", required=True)
    init.add_argument("--title", required=True)
    init.add_argument("--directory", required=True)
    init.add_argument("--goal", required=True)
    init.add_argument("--scope-in", action="append", required=True)
    init.add_argument("--scope-out", action="append", required=True)
    init.add_argument("--success", action="append", required=True)
    init.add_argument("--risk-boundary", action="append", required=True)
    init.set_defaults(func=workflow.init_plan)

    build = subparsers.add_parser("build-dossier", help="load the single Decision Dossier")
    _add_plan(build)
    build.add_argument("--input", required=True)
    build.set_defaults(func=workflow.build_dossier)

    resolve = subparsers.add_parser("resolve-dossier", help="apply selections and defaults once")
    _add_plan(resolve)
    resolve.add_argument("--input", required=True)
    resolve.set_defaults(func=workflow.resolve_dossier)

    open_designer = subparsers.add_parser("open-designer-session", help="dispatch the sole Designer")
    _add_plan(open_designer)
    _add_host(open_designer)
    open_designer.set_defaults(func=workflow.open_designer_session)

    close_designer = subparsers.add_parser("close-designer-session", help="close the sole Designer")
    _add_plan(close_designer)
    close_designer.add_argument("--dispatch-id", required=True)
    close_designer.set_defaults(func=workflow.close_designer_session)

    readiness = subparsers.add_parser("check-readiness", help="list every remaining readiness issue")
    _add_plan(readiness)
    readiness.set_defaults(func=workflow.check_readiness)

    authorize = subparsers.add_parser("authorize-plan", help="gate readiness, seal, and start execution")
    _add_plan(authorize)
    authorize.add_argument(
        "--source",
        required=True,
        choices=("explicit", "inherited_host_plan", "inherited_implementation_request"),
    )
    authorize.add_argument("--reference", required=True)
    authorize.add_argument("--risk-reason", action="append")
    authorize.add_argument("--verify-command", action="append")
    authorize.add_argument("--verify-path", action="append")
    authorize.set_defaults(func=workflow.authorize_plan)

    begin = subparsers.add_parser("begin-continuation", help="revise unstarted in-scope work")
    _add_plan(begin)
    begin.add_argument("--reason", required=True)
    begin.set_defaults(func=workflow.begin_continuation)

    close = subparsers.add_parser("close-continuation", help="reseal an inherited continuation")
    _add_plan(close)
    close.add_argument("--continuation-id", required=True)
    close.set_defaults(func=workflow.close_continuation)

    next_action = subparsers.add_parser("next-action", help="name the next delivery action")
    _add_plan(next_action)
    next_action.set_defaults(func=workflow.next_action)

    dispatch = subparsers.add_parser("dispatch-task", help="dispatch or re-dispatch one Worker")
    dispatch.add_argument("task")
    _add_plan(dispatch)
    _add_host(dispatch)
    dispatch.set_defaults(func=workflow.dispatch_task)

    bind = subparsers.add_parser("bind-agent", help="bind one host agent id to one dispatch")
    bind.add_argument("target")
    _add_plan(bind)
    bind.add_argument("--dispatch-id", required=True)
    bind.add_argument("--agent-id", required=True)
    bind.set_defaults(func=workflow.bind_agent)

    failed = subparsers.add_parser("delegation-failed", help="record a conclusive delegation failure")
    failed.add_argument("target")
    _add_plan(failed)
    failed.add_argument("--dispatch-id", required=True)
    failed.add_argument("--reason", required=True)
    failed.set_defaults(func=workflow.delegation_failed)

    complete = subparsers.add_parser("agent-complete", help="consume one exact final callback")
    _add_plan(complete)
    complete.add_argument("--agent-id", required=True)
    complete.add_argument("--final", action="store_true")
    complete.set_defaults(func=workflow.agent_complete)

    main_complete = subparsers.add_parser("main-complete", help="record native-main fallback completion")
    main_complete.add_argument("target")
    _add_plan(main_complete)
    main_complete.add_argument("--dispatch-id", required=True)
    main_complete.set_defaults(func=workflow.main_complete)

    accept = subparsers.add_parser("accept-task", help="run focused regression and complete one Task")
    accept.add_argument("task")
    _add_plan(accept)
    accept.set_defaults(func=workflow.accept_task)

    block = subparsers.add_parser("block-task", help="record a hard Task blocker")
    block.add_argument("task")
    _add_plan(block)
    block.add_argument("--kind", required=True, choices=("authority", "environment"))
    block.add_argument("--reason", required=True)
    block.set_defaults(func=workflow.block_task)

    open_reviewer = subparsers.add_parser("open-reviewer-session", help="dispatch the sole Reviewer")
    _add_plan(open_reviewer)
    _add_host(open_reviewer)
    open_reviewer.set_defaults(func=workflow.open_reviewer_session)

    close_reviewer = subparsers.add_parser("close-reviewer-session", help="close after full regression")
    _add_plan(close_reviewer)
    close_reviewer.add_argument("--dispatch-id", required=True)
    close_reviewer.add_argument("--blocked-reason")
    close_reviewer.set_defaults(func=workflow.close_reviewer_session)

    tree = subparsers.add_parser("tree", help="render live Plan structure and status")
    tree.add_argument("root", nargs="?", default=".")
    tree.add_argument("--plan")
    tree.add_argument("--details", action="store_true")
    tree.set_defaults(func=tree_command)

    status = subparsers.add_parser("status", help="summarize every Delivery Plan")
    status.add_argument("root", nargs="?", default=".")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=status_command)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except ToolError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    except Exception as exc:
        # Name the defect without leaking a traceback path: an autonomous loop
        # must be able to tell a repairable state error from a crash.
        print(
            "error: operation could not be completed safely (%s: %s)" % (type(exc).__name__, exc),
            file=sys.stderr,
        )
        return 1
