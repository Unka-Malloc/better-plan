"""CLI workflow for the order-only programme index and its requirement catalogue."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import sys

from ..domain.checkpoints_tree import TREE_NAME, export_payload, safe_id
from ..domain.models import ToolError, deep_patch
from ..domain.programme import (
    OUTLINE_FIELDS,
    PROGRAMME_NAME,
    PROGRAMME_SCHEMA,
    default_tree_id,
    default_tree_path,
    delivery_index,
    new_programme,
    normalize_delivery,
    programme_export,
    programme_report,
)
from ..domain.requirements import (
    REQUIREMENTS_NAME,
    REQUIREMENTS_SCHEMA,
    catalogue_index,
    coverage,
    new_catalogue,
    normalize_requirement,
    requirement_id,
)
from ..infrastructure.workspace import CurrentWorkspace, read_json, workspace_lock, write_json
from .tree_workflow import create_tree_workspace


def _root(args: Any) -> Path:
    path = Path(str(getattr(args, "root", "."))).expanduser()
    if path.is_file() and path.name == PROGRAMME_NAME:
        return path.resolve().parent
    return path.resolve()


def _path(root: Path) -> Path:
    return root / PROGRAMME_NAME


def _catalogue_path(root: Path) -> Path:
    return root / REQUIREMENTS_NAME


def load_programme(root: Path) -> dict[str, Any]:
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


def load_catalogue(root: Path) -> dict[str, Any]:
    path = _catalogue_path(root)
    if not path.is_file():
        return new_catalogue()
    value = read_json(path)
    if not isinstance(value, dict) or value.get("schema") != REQUIREMENTS_SCHEMA:
        raise ToolError("Requirements.json is not a current requirement catalogue")
    value["requirements"] = list(catalogue_index(value).values())
    return value


def _input_text(value: str, root: Path) -> str:
    if value == "-":
        return sys.stdin.read()
    path = Path(value).expanduser()
    if not path.is_absolute() and not path.is_file():
        path = root / path
    if not path.is_file():
        raise ToolError("input is missing at %s" % path)
    return path.read_text(encoding="utf-8")


def _parse(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ToolError("input is not valid JSON: %s" % exc.msg)


def _input(value: str, root: Path) -> dict[str, Any]:
    result = _parse(_input_text(value, root))
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
        value = load_programme(root)
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
    value = load_programme(_root(args))
    print(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


def load_exports(root: Path, programme: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    result, errors = {}, {}
    for delivery in programme.get("deliveries") or []:
        if not delivery.get("tree"):
            continue
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


def elaborate_delivery(args: Any) -> int:
    """Move one planned delivery outline into a new Tree workspace."""

    root = _root(args)
    code = safe_id(args.id, "delivery.id")
    with workspace_lock(root):
        value = load_programme(root)
        index = delivery_index(value)
        if code not in index:
            raise ToolError("unknown delivery %s" % code)
        delivery = index[code]
        if delivery.get("tree"):
            raise ToolError("delivery %s already has a Tree" % code)
        relative = str(args.tree or default_tree_path(code)).replace("\\", "/")
        reference = Path(relative).expanduser()
        tree_root = (reference if reference.is_absolute() else root / reference).parent
        if (tree_root / TREE_NAME).exists():
            raise ToolError("Tree workspace already exists at %s" % tree_root)
        title = str(delivery.get("title") or code)
        fields = {key: delivery[key] for key in ("success", "requirements", "open_decisions") if key in delivery}
    tree = create_tree_workspace(tree_root, default_tree_id(code), title, delivery.get("goal") or "", fields)
    with workspace_lock(root):
        value = load_programme(root)
        index = delivery_index(value)
        if code not in index or index[code].get("tree"):
            raise ToolError(
                "delivery %s changed during elaboration; workspace %s was created but Programme.json was not updated"
                % (code, tree_root)
            )
        delivery = index[code]
        delivery["tree"] = relative
        for key in OUTLINE_FIELDS:
            delivery.pop(key, None)
        write_json(_path(root), value)
    print(json.dumps({"elaborated": code, "tree": relative, "tree_id": tree["id"], "root": str(tree_root)}))
    return 0


def export_programme(args: Any) -> int:
    root = _root(args)
    programme = load_programme(root)
    exports, errors = load_exports(root, programme)
    catalogue = load_catalogue(root)
    payload = programme_export(programme, exports, errors, catalogue, coverage(programme, catalogue, exports))
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def programme_status(args: Any) -> int:
    root = _root(args)
    value = load_programme(root)
    exports, errors = load_exports(root, value)
    report = programme_report(value, exports, errors)
    if getattr(args, "json", False):
        print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print("%s ready=%s design=%s" % (report["title"], ",".join(report["ready"]) or "none", ",".join(report["ready_to_design"]) or "none"))
        for delivery in report["deliveries"]:
            print("  %s [delivery=%s execution=%s] blocked_by=%s" % (delivery["id"], delivery["state"], delivery["execution_status"], ",".join(delivery["blocked_by"]) or "none"))
    return 0


def requirements_list(args: Any) -> int:
    catalogue = load_catalogue(_root(args))
    entries = catalogue["requirements"]
    if getattr(args, "json", False):
        print(json.dumps(entries, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        for item in entries:
            exclusion = " excluded=%s" % item["exclusion"] if "exclusion" in item else ""
            title = item.get("title") or ""
            if isinstance(title, dict):
                title = title.get("en") or next(iter(title.values()), "")
            print("%s [%s] %s%s" % (item["id"], item.get("status") or "unset", title, exclusion))
    return 0


def requirements_add(args: Any) -> int:
    root = _root(args)
    payload = _parse(_input_text(args.input, root))
    entries = [normalize_requirement(item) for item in (payload if isinstance(payload, list) else [payload])]
    with workspace_lock(root, create=True):
        catalogue = load_catalogue(root)
        index = catalogue_index(catalogue)
        added = []
        for entry in entries:
            if entry["id"] in index:
                raise ToolError("requirement %s already exists" % entry["id"])
            index[entry["id"]] = entry
            catalogue["requirements"].append(entry)
            added.append(entry["id"])
        write_json(_catalogue_path(root), catalogue)
    print(json.dumps({"added": added, "path": str(_catalogue_path(root))}))
    return 0


def requirements_update(args: Any) -> int:
    root = _root(args)
    code = requirement_id(args.id)
    patch = _input(args.input, root)
    with workspace_lock(root):
        catalogue = load_catalogue(root)
        index = catalogue_index(catalogue)
        if code not in index:
            raise ToolError("unknown requirement %s" % code)
        if "id" in patch:
            raise ToolError("requirement identity is not an update field")
        updated = deep_patch(index[code], patch)
        updated["id"] = code
        catalogue["requirements"] = [updated if item["id"] == code else item for item in catalogue["requirements"]]
        write_json(_catalogue_path(root), catalogue)
    print(json.dumps({"updated": code}))
    return 0


def requirements_remove(args: Any) -> int:
    root = _root(args)
    code = requirement_id(args.id)
    with workspace_lock(root):
        catalogue = load_catalogue(root)
        kept = [item for item in catalogue["requirements"] if item["id"] != code]
        if len(kept) == len(catalogue["requirements"]):
            raise ToolError("unknown requirement %s" % code)
        catalogue["requirements"] = kept
        write_json(_catalogue_path(root), catalogue)
    print(json.dumps({"removed": code}))
    return 0


def requirements_coverage(args: Any) -> int:
    root = _root(args)
    catalogue = load_catalogue(root)
    programme = load_programme(root)
    exports, _errors = load_exports(root, programme)
    result = coverage(programme, catalogue, exports)
    if getattr(args, "json", False):
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(
            "requirements=%d uncovered=%s excluded=%s unknown_refs=%d"
            % (
                len(catalogue["requirements"]),
                ",".join(result["uncovered"]) or "none",
                ",".join(result["excluded"]) or "none",
                len(result["unknown_refs"]),
            )
        )
        for code, item in result["by_requirement"].items():
            print(
                "  %s deliveries=%s tasks=%s"
                % (
                    code,
                    ",".join(item["deliveries"]) or "none",
                    ",".join("%s/%s" % (task["delivery"], task["task"]) for task in item["tasks"]) or "none",
                )
            )
    return 0
