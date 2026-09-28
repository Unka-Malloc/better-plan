"""CLI workflow for the order-only programme index."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import sys

from ..domain.checkpoints_tree import export_payload
from ..domain.models import ToolError
from ..domain.programme import (
    PROGRAMME_NAME,
    PROGRAMME_SCHEMA,
    delivery_index,
    new_programme,
    normalize_delivery,
    programme_report,
)
from ..infrastructure.workspace import CurrentWorkspace, read_json, workspace_lock, write_json


def _root(args: Any) -> Path:
    path = Path(str(getattr(args, "root", "."))).expanduser()
    if path.is_file() and path.name == PROGRAMME_NAME:
        return path.resolve().parent
    return path.resolve()


def _path(root: Path) -> Path:
    return root / PROGRAMME_NAME


def _load(root: Path) -> dict[str, Any]:
    path = _path(root)
    if not path.is_file():
        raise ToolError("no programme at %s" % path)
    value = read_json(path)
    if not isinstance(value, dict) or value.get("schema") != PROGRAMME_SCHEMA:
        raise ToolError("Programme.json is not a current programme")
    values = [normalize_delivery(item) for item in value.get("deliveries") or []]
    if len({item["id"] for item in values}) != len(values):
        raise ToolError("programme has duplicate delivery ids")
    value["deliveries"] = values
    return value


def _input(value: str, root: Path) -> dict[str, Any]:
    if value == "-":
        text = sys.stdin.read()
    else:
        path = Path(value).expanduser()
        if not path.is_absolute() and not path.is_file():
            path = root / path
        if not path.is_file():
            raise ToolError("input is missing at %s" % path)
        text = path.read_text(encoding="utf-8")
    try:
        result = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ToolError("input is not valid JSON: %s" % exc.msg)
    if not isinstance(result, dict):
        raise ToolError("input must contain an object")
    return result


def init_programme(args: Any) -> int:
    root = _root(args)
    with workspace_lock(root, create=True):
        if _path(root).exists():
            raise ToolError("Programme.json already exists")
        value = new_programme(args.id or "PROGRAMME-001", args.title)
        write_json(_path(root), value)
    print(json.dumps({"created": value["id"], "path": str(_path(root))}))
    return 0


def update_programme(args: Any) -> int:
    root = _root(args)
    patch = _input(args.input, root)
    with workspace_lock(root):
        value = _load(root)
        if "id" in patch or "schema" in patch:
            raise ToolError("programme identity is not an update field")
        operations = patch.pop("operations", None)
        value.update(patch)
        if "deliveries" in value:
            value["deliveries"] = [normalize_delivery(item) for item in value["deliveries"]]
        if operations is not None:
            if not isinstance(operations, list):
                raise ToolError("operations must be an array")
            index = delivery_index(value)
            for operation in operations:
                if not isinstance(operation, dict):
                    raise ToolError("programme operation must be an object")
                action = operation.get("op")
                code = operation.get("id")
                if action == "add":
                    delivery = normalize_delivery({key: item for key, item in operation.items() if key != "op"})
                    if delivery["id"] in index:
                        raise ToolError("delivery %s already exists" % delivery["id"])
                    value["deliveries"].append(delivery)
                    index[delivery["id"]] = delivery
                elif action == "update" and code in index:
                    index[code].update({key: item for key, item in operation.items() if key not in ("op", "id")})
                    normalized = normalize_delivery(index[code])
                    index[code].clear()
                    index[code].update(normalized)
                elif action == "remove" and code in index:
                    value["deliveries"] = [item for item in value["deliveries"] if item["id"] != code]
                    for item in value["deliveries"]:
                        item["requires"] = [required for required in item["requires"] if required != code]
                    index.pop(code)
                else:
                    raise ToolError("unknown programme operation or delivery")
        write_json(_path(root), value)
    print(json.dumps({"updated": value["id"], "deliveries": [item["id"] for item in value["deliveries"]]}))
    return 0


def show_programme(args: Any) -> int:
    value = _load(_root(args))
    print(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def _exports(root: Path, programme: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    result, errors = {}, {}
    for delivery in programme.get("deliveries") or []:
        reference = Path(delivery["tree"]).expanduser()
        tree_path = reference if reference.is_absolute() else root / reference
        workspace = CurrentWorkspace(tree_path.parent)
        try:
            with workspace_lock(workspace.root):
                tree, tasks, nodes = workspace.load()
            result[delivery["id"]] = export_payload(tree, tasks, nodes)
        except ToolError as exc:
            result[delivery["id"]] = None
            errors[delivery["id"]] = str(exc)
    return result, errors


def programme_status(args: Any) -> int:
    root = _root(args)
    value = _load(root)
    exports, errors = _exports(root, value)
    report = programme_report(value, exports, errors)
    if getattr(args, "json", False):
        print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print("%s ready=%s" % (report["title"], ",".join(report["ready"]) or "none"))
        for delivery in report["deliveries"]:
            print("  %s [delivery=%s execution=%s] blocked_by=%s" % (delivery["id"], delivery["state"], delivery["execution_status"], ",".join(delivery["blocked_by"]) or "none"))
    return 0
