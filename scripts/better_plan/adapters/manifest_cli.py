"""Public CLI for the Checkpoints Tree and the programme index."""

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
    name = getattr(args, "name", None) or "tree"
    template = tree_template() if name == "tree" else programme_template()
    print(json.dumps(template, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def version_command(args: argparse.Namespace) -> int:
    print("better-plan %s (%s)" % (__version__, tree_template()["schema"]))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="manifest_tool.py",
        description="Author and run one Checkpoints Tree, and index many of them.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="better-plan %s (%s)" % (__version__, tree_template()["schema"]),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    schema = subparsers.add_parser("schema", help="print a canonical shape")
    schema.add_argument(
        "name",
        nargs="?",
        default="tree",
        choices=("tree", "programme"),
        help="which shape to print (default: tree)",
    )
    schema.set_defaults(func=schema_command)

    tree_init = subparsers.add_parser("tree-init", help="create one empty Checkpoints Tree")
    tree_init.add_argument("root", nargs="?", default=".")
    tree_init.add_argument("--id", help="Tree id (default: TREE-001, or the replaced Tree's id)")
    tree_init.add_argument("--title", help="delivery title; required unless a Tree is replaced")
    tree_init.add_argument(
        "--replace",
        action="store_true",
        help="re-author an existing Tree, carrying its identity and history forward",
    )
    tree_init.add_argument("--reason", help="why the existing Tree is replaced (with --replace)")
    tree_init.set_defaults(func=tree_workflow.init_tree)

    tree_apply = subparsers.add_parser(
        "tree-apply", help="apply one atomic batch of Tasks and Nodes to Tree.json"
    )
    tree_apply.add_argument("root", nargs="?", default=".")
    tree_apply.add_argument("--input", required=True, help="JSON batch file, or - for stdin")
    tree_apply.add_argument("--dry-run", action="store_true", help="validate the batch without writing")
    tree_apply.add_argument("--json", action="store_true")
    tree_apply.set_defaults(func=tree_workflow.apply_batch)

    tree_next = subparsers.add_parser(
        "tree-next", help="list executable Nodes whose prerequisites are complete"
    )
    tree_next.add_argument("root", nargs="?", default=".")
    tree_next.add_argument("--limit", type=int, default=0)
    tree_next.add_argument("--explain", action="store_true", help="include blockers and running Nodes")
    tree_next.add_argument("--json", action="store_true")
    tree_next.set_defaults(func=tree_workflow.next_nodes)

    tree_transition = subparsers.add_parser(
        "tree-transition",
        help="apply one state transition to one Node (a Node with contract.commands completes via tree-verify)",
    )
    tree_transition.add_argument("root", nargs="?", default=".")
    tree_transition.add_argument("node")
    tree_transition.add_argument(
        "action", choices=("start", "complete", "fail", "block", "cancel", "reset")
    )
    tree_transition.add_argument("--executor", help="which executor is running or ran this Node")
    tree_transition.add_argument("--evidence", help="JSON evidence value")
    tree_transition.add_argument("--note")
    tree_transition.add_argument("--json", action="store_true")
    tree_transition.set_defaults(func=tree_workflow.transition_node)

    tree_verify = subparsers.add_parser(
        "tree-verify",
        help="run one Node's declared contract.commands and complete it on tool-produced evidence",
    )
    tree_verify.add_argument("root", nargs="?", default=".")
    tree_verify.add_argument("node")
    tree_verify.add_argument("--executor", help="which executor is running this Node")
    tree_verify.add_argument(
        "--cwd", help="directory to run the commands in; defaults to the Tree's directory"
    )
    tree_verify.add_argument("--json", action="store_true")
    tree_verify.set_defaults(func=tree_workflow.verify_node)

    tree_status = subparsers.add_parser("tree-status", help="show Tree state and who owns which Node")
    tree_status.add_argument("root", nargs="?", default=".")
    tree_status.add_argument("--json", action="store_true")
    tree_status.set_defaults(func=tree_workflow.tree_status)

    tree_validate = subparsers.add_parser("tree-validate", help="validate one Checkpoints Tree")
    tree_validate.add_argument("root", nargs="?", default=".")
    tree_validate.add_argument("--json", action="store_true")
    tree_validate.add_argument("--quiet", action="store_true")
    tree_validate.set_defaults(func=tree_workflow.validate_tree_command)

    tree = subparsers.add_parser("tree", help="render the Tree as text")
    tree.add_argument("root", nargs="?", default=".")
    tree.add_argument("--details", action="store_true")
    tree.add_argument("--json", action="store_true", help="export the Tree and its derived state")
    tree.set_defaults(func=tree_workflow.show_tree)

    programme_init = subparsers.add_parser(
        "programme-init", help="create one empty programme index over many deliveries"
    )
    programme_init.add_argument("root", nargs="?", default=".")
    programme_init.add_argument("--id", default="PROGRAMME-001")
    programme_init.add_argument("--title", required=True)
    programme_init.set_defaults(func=programme_workflow.init_programme)

    programme_apply = subparsers.add_parser(
        "programme-apply", help="apply one atomic batch of deliveries to Programme.json"
    )
    programme_apply.add_argument("root", nargs="?", default=".")
    programme_apply.add_argument("--input", required=True, help="JSON batch file, or - for stdin")
    programme_apply.add_argument("--dry-run", action="store_true")
    programme_apply.add_argument("--json", action="store_true")
    programme_apply.set_defaults(func=programme_workflow.apply_programme_batch)

    programme_status = subparsers.add_parser(
        "programme-status", help="derive every delivery's state from its Tree"
    )
    programme_status.add_argument("root", nargs="?", default=".")
    programme_status.add_argument("--json", action="store_true")
    programme_status.set_defaults(func=programme_workflow.programme_status)

    programme_validate = subparsers.add_parser(
        "programme-validate", help="validate the programme index"
    )
    programme_validate.add_argument("root", nargs="?", default=".")
    programme_validate.add_argument("--json", action="store_true")
    programme_validate.add_argument("--quiet", action="store_true")
    programme_validate.set_defaults(func=programme_workflow.programme_validate_command)

    programme = subparsers.add_parser("programme", help="render the programme index as text")
    programme.add_argument("root", nargs="?", default=".")
    programme.set_defaults(func=programme_workflow.show_programme)

    return parser


def _configure_stdio() -> None:
    """Keep Tree markers and JSON printable on Windows cp1252 consoles."""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            continue


def main() -> int:
    _configure_stdio()
    parser = build_parser()
    args = parser.parse_args()
    try:
        result = args.func(args)
    except Exception as exc:  # ToolError is caller-fixable; anything else is named, not traced.
        print("error: %s" % exc, file=sys.stderr)
        return 1
    return result


if __name__ == "__main__":
    raise SystemExit(main())
