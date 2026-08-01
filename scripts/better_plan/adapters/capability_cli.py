"""CLI adapter for the durable Better Plan capability fact map."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import argparse

from ..domain.capabilities import (
    VALID_CAPABILITY_BASES,
    VALID_CAPABILITY_DISCLOSURES,
    VALID_CAPABILITY_KINDS,
    VALID_CAPABILITY_TOUCHES,
    capability_index,
    make_root_capability,
    plan_capability_binding_issues,
    promote_capability,
    render_capability_tree,
    upsert_capability,
    validate_capability_data,
)
from ..domain.models import CAPABILITIES_NAME, ToolError
from ..infrastructure.workspace import (
    load_state_entries,
    resolve_plan_entry,
    validate_plan_manifest_data,
    workspace_manifest_lock,
    workspace_manifest_path,
    write_state_entries,
)


def _catalog_path(root: str) -> tuple[Path, Path]:
    manifest = workspace_manifest_path(Path(root))
    return manifest, manifest.parent / CAPABILITIES_NAME


def _raise_catalog_issues(path: Path, entries: list[Any]) -> None:
    _, issues = validate_capability_data(path, entries)
    if issues:
        details = "; ".join(issue.message for issue in issues)
        raise ToolError(f"invalid {CAPABILITIES_NAME}: {details}")


def init_capabilities_command(args: argparse.Namespace) -> int:
    manifest, path = _catalog_path(args.root)
    requested = make_root_capability(
        key=args.key,
        title=args.title,
        description=args.description,
        basis=args.basis,
        source_files=args.source or [],
    )
    _raise_catalog_issues(path, [requested])

    with workspace_manifest_lock(manifest):
        if path.exists():
            current = load_state_entries(path)
            _raise_catalog_issues(path, current)
            if current == [requested]:
                print(f"OK: reused existing capability root {requested['key']}")
                return 0
            raise ToolError(f"{CAPABILITIES_NAME} already exists; reuse and extend its stable capability keys")
        write_state_entries(path, [requested])
    print(f"OK: initialized capability root {requested['key']}")
    return 0


def upsert_capability_command(args: argparse.Namespace) -> int:
    manifest, path = _catalog_path(args.root)
    with workspace_manifest_lock(manifest):
        if not path.is_file():
            raise ToolError(f"No {CAPABILITIES_NAME} found; run init-capabilities first")
        current = load_state_entries(path)
        _raise_catalog_issues(path, current)
        updated, created, changed = upsert_capability(
            current,
            key=args.key,
            parent=args.parent,
            title=args.title,
            kind=args.kind,
            basis=args.basis,
            description=args.description,
            source_files=args.source or [],
            disclosure=args.disclosure,
            touch=args.touch,
        )
        _raise_catalog_issues(path, updated)
        if changed:
            write_state_entries(path, updated)
    verb = "created" if created else "updated" if changed else "reused"
    print(f"OK: {verb} capability {args.key.strip().casefold()}")
    return 0


def promote_capability_command(args: argparse.Namespace) -> int:
    manifest, path = _catalog_path(args.root)
    with workspace_manifest_lock(manifest):
        if not path.is_file():
            raise ToolError(f"No {CAPABILITIES_NAME} found; disclose the capability path first")
        current = load_state_entries(path)
        _raise_catalog_issues(path, current)
        updated, changed = promote_capability(current, args.key, args.touch)
        _raise_catalog_issues(path, updated)
        if changed:
            write_state_entries(path, updated)
    verb = "promoted" if changed else "reused"
    print(f"OK: {verb} capability {args.key.strip().casefold()} as {args.touch}")
    return 0


def bind_plan_capability_command(args: argparse.Namespace) -> int:
    manifest, path = _catalog_path(args.root)
    with workspace_manifest_lock(manifest):
        if not path.is_file():
            raise ToolError(f"No {CAPABILITIES_NAME} found; disclose the capability path first")
        capabilities = load_state_entries(path)
        _raise_catalog_issues(path, capabilities)
        indexed = capability_index(capabilities)
        target = indexed.get(args.capability)
        if target is None:
            raise ToolError("cannot bind an unknown capability key")
        if target.get("disclosure") != "examined" or target.get("touch") not in {"in_scope", "modified"}:
            raise ToolError("task delivery may bind only an examined in_scope or modified capability")

        plans = load_state_entries(manifest)
        plan_index, plan = resolve_plan_entry(manifest, plans, args.plan)
        if plan.get("kind") != "group":
            raise ToolError("bind-plan-capability requires a task-group Plan")
        prior = plan.get("capability_key")
        if prior is not None and prior != args.capability:
            raise ToolError("Plan already binds a different capability; reuse its scope or create a genuinely distinct group")
        plan["capability_key"] = args.capability
        _, plan_issues = validate_plan_manifest_data(manifest, plans)
        binding_issues = plan_capability_binding_issues(manifest, plans, capabilities)
        if plan_issues or binding_issues:
            details = "; ".join(issue.message for issue in [*plan_issues, *binding_issues])
            raise ToolError(f"refusing invalid Plan capability binding: {details}")
        if prior != args.capability:
            write_state_entries(manifest, plans)
    verb = "reused" if prior == args.capability else "bound"
    print(f"OK: {verb} plan[{plan_index}] capability {args.capability}")
    return 0


def capability_tree_command(args: argparse.Namespace) -> int:
    _, path = _catalog_path(args.root)
    if not path.is_file():
        raise ToolError(f"No {CAPABILITIES_NAME} found at the supplied workspace root")
    entries = load_state_entries(path)
    _raise_catalog_issues(path, entries)
    print(render_capability_tree(entries, details=args.details))
    return 0


def capability_projection(root: Path, *, details: bool) -> str | None:
    path = root / CAPABILITIES_NAME
    if not path.is_file():
        return None
    entries = load_state_entries(path)
    _raise_catalog_issues(path, entries)
    return render_capability_tree(entries, details=details)


def register_capability_commands(subparsers: Any) -> None:
    init = subparsers.add_parser(
        "init-capabilities",
        help="create the one durable repository capability root",
    )
    init.add_argument("root", nargs="?", default=".", help="Better Plan workspace root")
    init.add_argument("--key", required=True, help="stable one-segment repository key")
    init.add_argument("--title", required=True, help="repository or core-capability title")
    init.add_argument("--description", required=True, help="bounded observed or designed root fact")
    init.add_argument("--basis", default="observed", choices=sorted(VALID_CAPABILITY_BASES))
    init.add_argument("--source", action="append", help="repository-relative evidence reference; repeatable")
    init.set_defaults(func=init_capabilities_command)

    upsert = subparsers.add_parser(
        "upsert-capability",
        help="create or monotonically enrich one root-to-leaf capability fact",
    )
    upsert.add_argument("root", nargs="?", default=".", help="Better Plan workspace root")
    upsert.add_argument("--key", required=True, help="stable hierarchical capability key")
    upsert.add_argument("--parent", required=True, help="existing immediate parent key")
    upsert.add_argument("--title", required=True, help="human-readable capability title")
    upsert.add_argument(
        "--kind",
        required=True,
        choices=sorted(VALID_CAPABILITY_KINDS - {"repository"}),
    )
    upsert.add_argument("--basis", default="observed", choices=sorted(VALID_CAPABILITY_BASES))
    upsert.add_argument("--description", required=True, help="bounded fact, not speculative detail")
    upsert.add_argument("--source", action="append", help="repository-relative evidence reference; repeatable")
    upsert.add_argument(
        "--disclosure",
        default="known",
        choices=sorted(VALID_CAPABILITY_DISCLOSURES),
    )
    upsert.add_argument("--touch", default="untouched", choices=sorted(VALID_CAPABILITY_TOUCHES))
    upsert.set_defaults(func=upsert_capability_command)

    promote = subparsers.add_parser(
        "promote-capability",
        help="promote an existing lightweight fact when it enters delivery scope",
    )
    promote.add_argument("key", help="stable capability key")
    promote.add_argument("root", nargs="?", default=".", help="Better Plan workspace root")
    promote.add_argument("--touch", default="in_scope", choices=("in_scope", "modified"))
    promote.set_defaults(func=promote_capability_command)

    bind = subparsers.add_parser(
        "bind-plan-capability",
        help="bind one task-group Plan to its examined delivery capability",
    )
    bind.add_argument("root", nargs="?", default=".", help="Better Plan workspace root")
    bind.add_argument("--plan", required=True, help="plan id, directory, or title")
    bind.add_argument("--capability", required=True, help="examined in-scope stable capability key")
    bind.set_defaults(func=bind_plan_capability_command)

    tree = subparsers.add_parser(
        "capability-tree",
        help="render the durable progressive-disclosure capability facts",
    )
    tree.add_argument("root", nargs="?", default=".", help="Better Plan workspace root")
    tree.add_argument("--details", action="store_true", help="include description and source references")
    tree.set_defaults(func=capability_tree_command)
