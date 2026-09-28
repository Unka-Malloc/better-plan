"""Single grouped CLI for Better Plan current state and immutable history."""

from __future__ import annotations

from typing import Any
import argparse
import json
import sys

from .. import __version__
from ..application import programme_workflow, tree_workflow
from ..domain.checkpoints_tree import tree_template
from ..domain.programme import programme_template


def schema_command(args: argparse.Namespace) -> int:
    value = programme_template() if args.name == "programme" else tree_template()
    print(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def _root(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("root", nargs="?", default=".")


def _json(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true")


def _group(subparsers: Any, name: str, help_text: str):
    parser = subparsers.add_parser(name, help=help_text)
    return parser.add_subparsers(dest="%s_command" % name, required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="manifest_tool.py",
        description="Maintain a long-lived Checkpoints Tree through local tree operations.",
    )
    parser.add_argument("--version", action="version", version="better-plan %s" % __version__)
    commands = parser.add_subparsers(dest="command", required=True)

    schema = commands.add_parser("schema", help="print a canonical current-state shape")
    schema.add_argument("name", nargs="?", choices=("tree", "programme"), default="tree")
    schema.set_defaults(func=schema_command)

    tree = _group(commands, "tree", "create, inspect and update a Tree")
    item = tree.add_parser("init")
    _root(item)
    item.add_argument("--id")
    item.add_argument("--title", required=True)
    item.add_argument("--goal")
    item.set_defaults(func=tree_workflow.init_tree)
    item = tree.add_parser("show")
    _root(item)
    _json(item)
    item.set_defaults(func=tree_workflow.show_tree)
    item = tree.add_parser("next")
    _root(item)
    item.add_argument("--limit", type=int, default=0)
    _json(item)
    item.set_defaults(func=tree_workflow.next_nodes)
    item = tree.add_parser("status")
    _root(item)
    _json(item)
    item.set_defaults(func=tree_workflow.tree_status)
    item = tree.add_parser("export")
    _root(item)
    item.set_defaults(func=tree_workflow.export_tree)
    item = tree.add_parser("refresh")
    _root(item)
    item.set_defaults(func=tree_workflow.refresh_tree)
    item = tree.add_parser("update")
    _root(item)
    item.add_argument("--input", required=True)
    item.set_defaults(func=tree_workflow.update_tree)

    item = tree.add_parser("finish", help="record engineering delivery; keep PRs Draft")
    _root(item)
    result = item.add_mutually_exclusive_group(required=True)
    result.add_argument("--summary")
    result.add_argument("--result", help="JSON delivery result including any exceptions")
    item.set_defaults(func=tree_workflow.finish_delivery)

    task = _group(commands, "task", "operate on Task groups")
    item = task.add_parser("add")
    _root(item)
    item.add_argument("--input", required=True)
    item.set_defaults(func=tree_workflow.add_task)
    item = task.add_parser("update")
    _root(item)
    item.add_argument("id")
    item.add_argument("--input", required=True)
    item.set_defaults(func=tree_workflow.update_task)
    item = task.add_parser("show")
    _root(item)
    item.add_argument("id")
    item.set_defaults(func=tree_workflow.show_task)
    item = task.add_parser("remove")
    _root(item)
    item.add_argument("id")
    item.add_argument("--with-nodes", action="store_true")
    item.set_defaults(func=tree_workflow.remove_task)

    item = task.add_parser("finish", help="record engineering delivery; keep PRs Draft")
    _root(item)
    item.add_argument("id")
    result = item.add_mutually_exclusive_group(required=True)
    result.add_argument("--summary")
    result.add_argument("--result", help="JSON delivery result including any exceptions")
    item.set_defaults(func=tree_workflow.finish_delivery)

    node = _group(commands, "node", "operate on individual Nodes")
    item = node.add_parser("add")
    _root(item)
    item.add_argument("--input", required=True)
    item.add_argument("--between", nargs=2, metavar=("PREDECESSOR", "SUCCESSOR"))
    item.set_defaults(func=tree_workflow.add_node)
    item = node.add_parser("update")
    _root(item)
    item.add_argument("id")
    item.add_argument("--input", required=True)
    item.set_defaults(func=tree_workflow.update_node)
    item = node.add_parser("edit")
    _root(item)
    item.add_argument("id")
    item.add_argument("--input", help="replacement Node JSON captured before editing")
    item.add_argument("--editor", help="editor command; runs on a temporary Node copy outside the lock")
    item.set_defaults(func=tree_workflow.edit_node)
    item = node.add_parser("move")
    _root(item)
    item.add_argument("id")
    item.add_argument("--task")
    item.add_argument("--after", nargs="*")
    item.set_defaults(func=tree_workflow.move_node)
    item = node.add_parser("remove")
    _root(item)
    item.add_argument("id")
    item.add_argument("--disconnect", action="store_true")
    item.set_defaults(func=tree_workflow.remove_node)
    item = node.add_parser("start")
    _root(item)
    item.add_argument("id")
    item.set_defaults(func=tree_workflow.start_node)
    item = node.add_parser("finish")
    _root(item)
    item.add_argument("id")
    item.add_argument("--result", help="JSON result file, or -")
    item.add_argument("--summary")
    item.add_argument("--commit", help="current commit reference for this Node")
    item.set_defaults(func=tree_workflow.finish_node)
    item = node.add_parser("review-done")
    _root(item)
    item.add_argument("id")
    item.add_argument("--source-kind", choices=("tree", "task", "node"))
    item.add_argument("--source-id")
    item.set_defaults(func=tree_workflow.review_done)
    item = node.add_parser("show")
    _root(item)
    item.add_argument("id")
    item.set_defaults(func=tree_workflow.show_node)

    edge = _group(commands, "edge", "add or remove dependency edges")
    for action, handler in (("add", tree_workflow.add_edge), ("remove", tree_workflow.remove_edge)):
        item = edge.add_parser(action)
        _root(item)
        item.add_argument("predecessor")
        item.add_argument("successor")
        item.set_defaults(func=handler)

    subtree = _group(commands, "subtree", "operate on a branch while preserving external joins")
    item = subtree.add_parser("show")
    _root(item)
    item.add_argument("id")
    item.add_argument("--entry", action="append", help="additional entry boundary")
    item.add_argument("--exit", action="append", help="explicit included exit boundary")
    item.set_defaults(func=tree_workflow.show_subtree)
    item = subtree.add_parser("attach")
    _root(item)
    item.add_argument("id")
    item.add_argument("--entry", action="append")
    item.add_argument("--exit", action="append")
    item.add_argument("--after", nargs="*")
    item.add_argument("--before", nargs="*")
    item.set_defaults(func=tree_workflow.attach_subtree)
    item = subtree.add_parser("move")
    _root(item)
    item.add_argument("id")
    item.add_argument("--entry", action="append")
    item.add_argument("--exit", action="append")
    item.add_argument("--after", nargs="*")
    item.add_argument("--before", nargs="*")
    item.set_defaults(func=tree_workflow.move_subtree)
    item = subtree.add_parser("remove")
    _root(item)
    item.add_argument("id")
    item.add_argument("--entry", action="append")
    item.add_argument("--exit", action="append")
    item.set_defaults(func=tree_workflow.remove_subtree)

    history = _group(commands, "history", "append and query immutable history archives")
    item = history.add_parser("archive")
    _root(item)
    item.add_argument("--input", required=True)
    item.add_argument("--kind", choices=("transcript", "summary"), required=True)
    item.add_argument("--source", required=True)
    item.add_argument("--id")
    item.add_argument("--summary")
    item.add_argument("--attach", nargs="*")
    item.set_defaults(func=tree_workflow.archive_history)
    item = history.add_parser("list")
    _root(item)
    item.set_defaults(func=tree_workflow.list_history)
    item = history.add_parser("search")
    _root(item)
    item.add_argument("query")
    item.set_defaults(func=tree_workflow.search_history)
    item = history.add_parser("show")
    _root(item)
    item.add_argument("id")
    item.add_argument("--attachment", help="emit one archived attachment's original bytes")
    item.set_defaults(func=tree_workflow.show_history)

    checks = _group(commands, "checks", "collect, run or record scoped checks")
    item = checks.add_parser("list")
    _root(item)
    item.add_argument("--node")
    item.set_defaults(func=tree_workflow.list_checks)
    item = checks.add_parser("run")
    _root(item)
    item.add_argument("id")
    item.add_argument("--owner", required=True, help="tree, task:<id>, or node:<id>")
    item.add_argument("--cwd")
    item.set_defaults(func=tree_workflow.run_check)
    item = checks.add_parser("record")
    _root(item)
    item.add_argument("id")
    item.add_argument("--owner", required=True)
    item.add_argument("--result")
    item.add_argument("--status", default="recorded")
    item.add_argument("--summary")
    item.set_defaults(func=tree_workflow.record_check)

    item = checks.add_parser("recover", help="confirm leftover commands have ended and clear an interrupted execution")
    _root(item)
    item.add_argument("id")
    item.add_argument("--owner", required=True)
    item.set_defaults(func=tree_workflow.recover_check)

    programme = _group(commands, "programme", "maintain an order-only delivery index")
    item = programme.add_parser("init")
    _root(item)
    item.add_argument("--id")
    item.add_argument("--title", required=True)
    item.set_defaults(func=programme_workflow.init_programme)
    item = programme.add_parser("update")
    _root(item)
    item.add_argument("--input", required=True)
    item.set_defaults(func=programme_workflow.update_programme)
    item = programme.add_parser("show")
    _root(item)
    item.set_defaults(func=programme_workflow.show_programme)
    item = programme.add_parser("status")
    _root(item)
    _json(item)
    item.set_defaults(func=programme_workflow.programme_status)
    return parser


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


def main() -> int:
    _configure_stdio()
    args = build_parser().parse_args()
    try:
        return args.func(args)
    except Exception as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
