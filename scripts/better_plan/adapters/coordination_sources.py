"""Native, source-owned execution adapters for the portfolio coordinator.

Snapshots are public and privacy bounded.  Receipts returned by ``prepare``
are private coordinator state: v7 receipts deliberately contain the native
claim token required to renew and accept the claim.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Optional
import json
import hashlib
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time

from ..domain.models import (
    OPAQUE_EVENT_ID_PATTERN,
    ToolError,
    is_relative_workspace_path,
    semantic_digest,
)
from ..infrastructure.workspace import read_json
from .coordination_portfolio import (
    PORTFOLIO_SCHEMA, SAFE_ID, _digest, _graph_states, read, require, safe_text, within,
)


RECEIPT_SCHEMA = "better-plan.coordination-source-receipt/v1"
_RESOURCE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}$")
V7_ASSIGNMENT = (
    "Implement exactly this source-owned execution item within its declared write scopes. "
    "Return the repository-relative native evidence manifest produced by the real verification; "
    "host success alone is not acceptance."
)


def _safe_value(value: Any, field: str) -> Any:
    """Reject private-shaped source prose before exposing it in a snapshot."""

    safe_text(json.dumps(value, ensure_ascii=False, sort_keys=True), field)
    return value


def _relative_repository(value: Any) -> str:
    require(is_relative_workspace_path(value), "lane repository must be workspace-relative")
    return str(Path(str(value)).as_posix()).rstrip("/")


def _prefix(repository: str, value: Any) -> str:
    require(is_relative_workspace_path(value), "source write path must be relative")
    return (Path(repository) / str(value)).as_posix()


def _resource(value: Any) -> str:
    require(isinstance(value, str) and value.strip(), "source resource must be a string")
    text = safe_text(value.strip(), "source resource")
    if _RESOURCE_ID.fullmatch(text):
        return text
    # Older v3 Plans used descriptive prose where the coordinator requires a
    # compact global identifier. Equal descriptions retain equal occupancy;
    # raw prose is not persisted in the coordinator journal.
    return "resource/" + hashlib.sha256(text.encode("utf-8")).hexdigest()


class NativeSources:
    """Read and advance only explicitly selected native plan sources."""

    def __init__(self, root: Path, portfolio_path: Path, lanes: list[dict[str, Any]]):
        self.root = root.resolve()
        try:
            portfolio = portfolio_path.resolve()
            require(portfolio.is_file() and self.root in portfolio.parents,
                    "portfolio must be a file below the workspace root")
            config = json.loads(portfolio.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise ToolError("cannot read coordination portfolio") from None
        require(isinstance(config, dict) and config.get("schema") == PORTFOLIO_SCHEMA,
                "unsupported coordination portfolio")
        sources = config.get("sources")
        require(isinstance(sources, list), "coordination portfolio requires sources")
        self._sources = {
            item["id"]: dict(item)
            for item in sources
            if isinstance(item, dict) and SAFE_ID.fullmatch(str(item.get("id", "")))
        }
        require(len(self._sources) == len(sources), "invalid or duplicate coordination source")
        self._lanes: dict[str, dict[str, Any]] = {}
        for lane in lanes:
            require(isinstance(lane, dict), "lane must be an object")
            require(set(lane) == {"id", "kind", "repository", "source"}, "invalid lane fields")
            require(SAFE_ID.fullmatch(str(lane.get("id", ""))), "invalid lane id")
            require(lane.get("kind") in {"mainline", "collaboration"}, "invalid lane kind")
            require(lane.get("source") in self._sources, "lane references an unknown source")
            require(lane["source"] not in self._lanes, "one source may belong to only one lane")
            repository = _relative_repository(lane["repository"])
            require((self.root / repository).resolve().is_dir(), "lane repository is missing")
            require((self.root / repository).resolve() == self.root / repository,
                    "lane repository escapes through a symbolic link")
            self._lanes[lane["source"]] = {**lane, "repository": repository}
        self.source_errors: dict[str, str] = {}
        self._last_snapshot: dict[str, dict[str, Any]] = {}

    def _source_for_key(self, key: str) -> tuple[dict[str, Any], dict[str, Any], str]:
        source_id, separator, unit = key.partition("/")
        if not separator or source_id not in self._lanes or not unit:
            raise ToolError("unknown coordination unit")
        return self._sources[source_id], self._lanes[source_id], unit

    def _v3_context(self, source: Mapping[str, Any], lane: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], Path]:
        plan_path = within(self.root, str(source["path"]))
        plan = read(self.root, str(source["path"]))
        require(plan.get("schema") == "better-plan.plan/v3", "unsupported Better Plan source")
        cp_path = plan_path.with_name("Checkpoints.json")
        require(cp_path.is_file(), "Better Plan source has no Checkpoints")
        checkpoints = read_json(cp_path)
        sealed = plan.get("lifecycle", {}).get("sealed") or {}
        require(
            isinstance(checkpoints, dict)
            and checkpoints.get("schema") == "better-plan.checkpoints/v3"
            and checkpoints.get("plan") == plan.get("code")
            and checkpoints.get("revision") == sealed.get("revision")
            and checkpoints.get("semantic_digest") == sealed.get("semantic_digest") == semantic_digest(plan),
            "Better Plan source binding is stale",
        )
        require(
            {item.get("code") for item in checkpoints.get("tasks", [])}
            == {item.get("code") for item in plan.get("spec", {}).get("tasks", [])},
            "Better Plan source Task set differs from Checkpoints",
        )
        require(
            len(checkpoints.get("tasks", []))
            == len({item.get("code") for item in checkpoints.get("tasks", [])}),
            "Better Plan source has duplicate Task state",
        )
        workspace = plan_path.parent
        repository_root = (self.root / str(lane["repository"])).resolve()
        while workspace != repository_root.parent and not (workspace / "Manifest.json").is_file():
            workspace = workspace.parent
        require(
            (workspace / "Manifest.json").is_file()
            and (workspace == repository_root or repository_root in workspace.parents),
            "Better Plan source has no native workspace",
        )
        # The source Plan must be indexed by the selected native workspace.
        manifest = read_json(workspace / "Manifest.json")
        declared_project = manifest.get("project_root")
        if declared_project is not None:
            require(isinstance(declared_project, str) and declared_project.strip(),
                    "Better Plan native project root is invalid")
            native_project = (workspace / declared_project).resolve()
            require(native_project.is_dir(), "Better Plan native project root is missing")
        else:
            native_project = workspace.resolve()
            current = workspace.resolve()
            while current != current.parent:
                if (current / ".git").exists():
                    native_project = current
                    break
                current = current.parent
        require(
            native_project == repository_root,
            "Better Plan native project root differs from its coordination lane",
        )
        matches = [
            entry
            for entry in manifest.get("plans", [])
            if isinstance(entry, Mapping) and entry.get("code") == plan.get("code")
        ]
        require(len(matches) == 1, "Better Plan source is not indexed exactly once by its Manifest")
        indexed_path = matches[0].get("plan")
        require(
            is_relative_workspace_path(indexed_path)
            and (workspace / str(indexed_path)).resolve() == plan_path,
            "Better Plan Manifest indexes a different Plan path",
        )
        return plan, checkpoints, workspace

    @staticmethod
    def _v3_authorized(plan: Mapping[str, Any]) -> bool:
        lifecycle = plan.get("lifecycle", {})
        sealed = lifecycle.get("sealed") or {}
        authorization = lifecycle.get("authorization") or {}
        digest = semantic_digest(plan)
        return (
            plan.get("phase") in {"authorized", "completed", "blocked"}
            and sealed.get("semantic_digest") == digest
            and authorization.get("semantic_digest") == digest
        )

    def _v3_snapshot(self, source: dict[str, Any], lane: dict[str, Any]) -> dict[str, dict[str, Any]]:
        plan, checkpoints, _ = self._v3_context(source, lane)
        states = {item["code"]: item for item in checkpoints["tasks"]}
        units: dict[str, dict[str, Any]] = {}
        for task in plan["spec"]["tasks"]:
            code = str(task["code"])
            state = states[code]
            native = state.get("status")
            dispatch = state.get("dispatch") or {}
            if native == "completed":
                projected = "completed"
            elif str(native).startswith("blocked_by_") or state.get("input_request"):
                projected = "blocked"
            elif native == "pending":
                projected = "pending"
            elif native == "in_progress" and dispatch.get("phase") == "worker_running":
                projected = "running"
            elif native == "in_progress" and dispatch.get("phase") == "awaiting_acceptance":
                projected = "awaiting_acceptance"
            elif native == "in_progress" and dispatch.get("phase") == "worker_correction":
                projected = "correction"
            else:
                projected = "unknown"
            ownership = task.get("ownership") or {}
            difficulty = task.get("difficulty")
            brief = {
                "code": code,
                "title": task.get("title"),
                "outcome": task.get("outcome"),
                "worker": task.get("worker"),
                "difficulty": difficulty,
                "workload": task.get("workload"),
                "verification": task.get("verification"),
                # This adapter dispatches through the neutral native host, so
                # the authoritative selector is the Task tier.  A Codex native
                # main may separately prefer its optional frontend role.
                "agent_type": (
                    "worker-" + str(difficulty)
                    if difficulty in {"standard", "complex"}
                    else None
                ),
            }
            key = source["id"] + "/" + code
            units[key] = {
                "key": key,
                "source": source["id"],
                "binding": semantic_digest(plan),
                "state": projected,
                "authorized": self._v3_authorized(plan),
                "parents": [],
                "writes": [_prefix(lane["repository"], item) for item in ownership.get("write_paths", [])],
                "resources": [_resource(item) for item in ownership.get("shared_exclusive", [])],
                "brief": _safe_value(brief, "Better Plan Task brief"),
            }
        return units

    def _v7_parts(
        self, source: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, dict[str, Any]], str]:
        project_path = within(self.root, source["path"])
        project = read(self.root, source["path"])
        require(project.get("schema_version") == 1, "unsupported execution graph source")

        def sibling(name: str) -> dict[str, Any]:
            require(is_relative_workspace_path(name), "execution graph member must be relative")
            relative = (project_path.parent / name).resolve().relative_to(self.root).as_posix()
            return read(self.root, relative)

        graph = sibling(project["execution"])
        architecture = sibling(project["architecture"])
        distribution = sibling(project["distribution"]) if project.get("distribution") else None
        require(graph.get("schema_version") == 1 and str(graph.get("revision", "")).startswith("v7."),
                "unsupported execution graph revision")
        states = _graph_states(self.root, source, project_path, graph, architecture, distribution)
        artifact_relative = (project_path.parent / "generated/work-items.json").resolve().relative_to(self.root).as_posix()
        artifact = read(self.root, artifact_relative)
        require(artifact.get("graph_digest") == _digest({
            "architecture": architecture, "execution": graph, "distribution": distribution,
        }), "generated execution graph is stale")
        items = {str(item["id"]): item for item in artifact.get("items", [])}
        require(set(items) == set(states), "execution graph export differs from ledger")
        return graph, items, states, str(artifact["graph_digest"])

    def _v7_snapshot(self, source: dict[str, Any], lane: dict[str, Any]) -> dict[str, dict[str, Any]]:
        _, items, states, _ = self._v7_parts(source)
        units: dict[str, dict[str, Any]] = {}
        now = time.time()
        for code, task in items.items():
            row = states[code]
            native = row.get("status")
            if native == "accepted":
                state = "completed"
            elif native == "running" and float(row.get("lease_until") or 0) > now:
                state = "running"
            elif native in {"running", "needs_review"}:
                state = "correction"
            elif native in {"pending", "invalidated"}:
                state = "pending"
            elif native == "blocked":
                state = "blocked"
            else:
                state = "unknown"
            # The producer export is the execution contract.  Forward the
            # complete safe work item so the Worker sees its scopes, resource
            # exclusions, acceptance specs, and evidence binding rules.
            brief = dict(task)
            key = source["id"] + "/" + code
            units[key] = {
                "key": key,
                "source": source["id"],
                "binding": task["fingerprints"]["task_fingerprint"],
                "state": state,
                "authorized": True,
                "parents": [source["id"] + "/" + parent for parent in task.get("predecessors", [])],
                "writes": [_prefix(lane["repository"], item) for item in task.get("write_scopes", [])],
                "resources": [_resource(item) for item in task.get("resources", [])],
                "brief": _safe_value(brief, "execution graph Task brief"),
            }
        return units

    def snapshot(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        errors: dict[str, str] = {}
        for source_id, lane in self._lanes.items():
            source = self._sources[source_id]
            try:
                if source.get("kind") == "better-plan-v3":
                    units = self._v3_snapshot(source, lane)
                elif source.get("kind") == "execution-graph-v7":
                    units = self._v7_snapshot(source, lane)
                else:
                    raise ToolError("unsupported native source kind")
                result.update(units)
            except (ToolError, OSError, ValueError, KeyError, TypeError, sqlite3.Error):
                errors[source_id] = "source unavailable or unsupported"
                known = {
                    key: {**unit, "state": "unknown", "authorized": False}
                    for key, unit in self._last_snapshot.items()
                    if unit.get("source") == source_id
                }
                if known:
                    result.update(known)
                else:
                    key = source_id + "/<unavailable>"
                    result[key] = {
                        "key": key, "source": source_id, "binding": "unavailable", "state": "unknown",
                        "authorized": False, "parents": [], "writes": [], "resources": [],
                        "brief": {"title": "Source unavailable"},
                    }
        self.source_errors = errors
        self._last_snapshot = {key: dict(value) for key, value in result.items()}
        return result

    @staticmethod
    def _manifest_command(workspace: Path, *arguments: str, json_output: bool = True) -> dict[str, Any]:
        """Use the public CLI so parallel accepts never redirect process stdout."""

        tool = Path(__file__).resolve().parents[2] / "manifest_tool.py"
        completed = subprocess.run(
            [sys.executable, str(tool), *arguments],
            cwd=str(workspace),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode != 0:
            raise ToolError("native Better Plan command rejected the operation")
        if not json_output:
            return {}
        try:
            value = json.loads(completed.stdout)
        except ValueError:
            raise ToolError("native Better Plan command returned an invalid receipt") from None
        require(isinstance(value, dict), "native Better Plan receipt must be an object")
        return value

    def _v7_command(self, source: Mapping[str, Any], *arguments: str) -> dict[str, Any]:
        project_path = within(self.root, str(source["path"]))
        tool = project_path.parent.parent / "tools" / "planctl.py"
        require(tool.is_file(), "execution graph native tool is missing")
        state = within(self.root, str(source["state"]))
        completed = subprocess.run(
            [sys.executable, str(tool), "--project", str(project_path), "--state", str(state), *arguments],
            cwd=str((self.root / self._lanes[str(source["id"])]["repository"]).resolve()),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode != 0:
            raise ToolError("execution graph native command rejected the operation")
        try:
            value = json.loads(completed.stdout)
        except ValueError:
            raise ToolError("execution graph native command returned an invalid receipt") from None
        require(isinstance(value, dict), "execution graph receipt must be an object")
        return value

    def prepare(self, key: str, operation_id: str) -> dict[str, Any]:
        require(OPAQUE_EVENT_ID_PATTERN.fullmatch(operation_id or "") is not None,
                "operation id must be an opaque identifier")
        source, lane, unit = self._source_for_key(key)
        current = self.snapshot().get(key)
        require(current is not None and current["authorized"], "coordination unit is not authorized")
        require(current["state"] in {"pending", "correction", "running"},
                "coordination unit is not eligible for preparation")
        if source["kind"] == "better-plan-v3":
            plan, _, workspace = self._v3_context(source, lane)
            try:
                payload = self._manifest_command(
                    workspace, "dispatch-task", unit, str(workspace),
                    "--plan", str(plan["code"]), "--request-id", operation_id,
                )
            except ToolError:
                raise ToolError("native Better Plan dispatch rejected the operation") from None
            public_brief = _safe_value({name: payload.get(name) for name in (
                "assignment", "role_reference", "brief", "agent_type", "role",
                "prompt_cache_group", "main_thread_fallback",
            ) if name in payload}, "native dispatch brief")
            return {
                "schema": RECEIPT_SCHEMA, "kind": "better-plan-v3", "key": key,
                "source": source["id"], "operation_id": operation_id,
                "binding": current["binding"], "dispatch_id": payload["dispatch_id"],
                "brief": public_brief,
            }

        # Recover only this coordinator operation's still-live native claim.
        _, _, _, graph_digest = self._v7_parts(source)
        state_path = within(self.root, source["state"])
        try:
            connection = sqlite3.connect(state_path.as_uri() + "?mode=ro", uri=True)
            connection.row_factory = sqlite3.Row
            try:
                row = connection.execute(
                    "SELECT id,status,owner,token,lease_until,fingerprint,generation,input_digest "
                    "FROM tasks WHERE id=?", (unit,)
                ).fetchone()
            finally:
                connection.close()
        except sqlite3.Error:
            raise ToolError("cannot inspect execution graph claim") from None
        require(row is not None and row["fingerprint"] == current["binding"], "execution graph claim is stale")
        if row["status"] == "running":
            require(float(row["lease_until"] or 0) > time.time(), "execution graph claim is expired")
            require(row["owner"] == operation_id, "execution graph unit is owned by another operation")
            claim = {
                "task_id": unit, "owner": row["owner"], "claim_token": row["token"],
                "lease_until": row["lease_until"], "generation": row["generation"],
                "input_digest": row["input_digest"], "task_digest": row["fingerprint"],
                "graph_digest": graph_digest,
            }
        else:
            require(row["status"] in {"pending", "invalidated"}, "execution graph unit is not claimable")
            claim = self._v7_command(source, "claim", unit, "--owner", operation_id)
        return {
            "schema": RECEIPT_SCHEMA, "kind": "execution-graph-v7", "key": key,
            "source": source["id"], "operation_id": operation_id,
            "binding": current["binding"], "claim": claim,
            "brief": {
                "assignment": V7_ASSIGNMENT,
                "role_reference": "references/worker.md",
                "brief": current["brief"],
            },
        }

    @staticmethod
    def _receipt(receipt: Mapping[str, Any], key: str) -> None:
        require(isinstance(receipt, Mapping) and receipt.get("schema") == RECEIPT_SCHEMA,
                "invalid private source receipt")
        require(receipt.get("key") == key, "private source receipt belongs to another unit")

    def bind(self, key: str, receipt: dict[str, Any], host_id: str) -> None:
        self._receipt(receipt, key)
        require(OPAQUE_EVENT_ID_PATTERN.fullmatch(host_id or "") is not None,
                "host id must be an opaque identifier")
        source, lane, unit = self._source_for_key(key)
        if receipt.get("kind") == "better-plan-v3":
            plan, _, workspace = self._v3_context(source, lane)
            try:
                self._manifest_command(
                    workspace, "bind-agent", unit, str(workspace),
                    "--plan", str(plan["code"]), "--dispatch-id", str(receipt["dispatch_id"]),
                    "--agent-id", host_id, json_output=False,
                )
            except ToolError:
                raise ToolError("native Better Plan bind rejected the host") from None

    def renew(self, key: str, receipt: dict[str, Any]) -> dict[str, Any]:
        self._receipt(receipt, key)
        source, _, unit = self._source_for_key(key)
        if receipt.get("kind") == "better-plan-v3":
            # Better Plan dispatches are durable and have no source lease.  A
            # coordinator heartbeat is therefore a successful no-op.
            return receipt
        require(receipt.get("kind") == "execution-graph-v7", "unsupported native source receipt")
        try:
            claim = receipt["claim"]
            result = self._v7_command(
                source, "heartbeat", unit, "--owner", str(claim["owner"]),
                "--token", str(claim["claim_token"]),
            )
        except (KeyError, ToolError):
            raise ToolError("execution graph lease renewal was rejected") from None
        receipt["claim"]["lease_until"] = result.get("lease_until")
        return receipt

    def finish(
        self,
        key: str,
        receipt: dict[str, Any],
        host_id: str,
        evidence: Optional[str] = None,
    ) -> dict[str, Any]:
        self._receipt(receipt, key)
        require(OPAQUE_EVENT_ID_PATTERN.fullmatch(host_id or "") is not None,
                "host id must be an opaque identifier")
        source, lane, unit = self._source_for_key(key)
        current = self.snapshot().get(key)
        require(current is not None and current.get("binding") == receipt.get("binding"),
                "source binding changed before completion")
        if current["state"] == "completed":
            return {"accepted": True, "state": "completed", "idempotent": True}
        if receipt.get("kind") == "better-plan-v3":
            plan, _, workspace = self._v3_context(source, lane)
            try:
                if current["state"] == "running":
                    self._manifest_command(
                        workspace, "agent-complete", str(workspace), "--plan", str(plan["code"]),
                        "--agent-id", host_id, "--final",
                    )
                self._manifest_command(
                    workspace, "accept-task", unit, str(workspace), "--plan", str(plan["code"]),
                )
                return {"accepted": True, "state": "completed"}
            except ToolError:
                after = self.snapshot().get(key, {})
                if after.get("state") == "correction":
                    return {"accepted": False, "state": "correction", "reason": "focused_acceptance_failed"}
                raise ToolError("native Better Plan completion was rejected") from None

        if evidence is None:
            return {"accepted": False, "state": "awaiting_acceptance", "reason": "awaiting_evidence"}
        require(is_relative_workspace_path(evidence), "evidence path must be repository-relative")
        repository = (self.root / lane["repository"]).resolve()
        evidence_path = (repository / evidence).resolve()
        require(repository in evidence_path.parents and evidence_path.is_file(), "evidence file is missing")
        try:
            supplied = json.loads(evidence_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise ToolError("evidence file is not a JSON object") from None
        require(isinstance(supplied, dict), "evidence file is not a JSON object")
        try:
            claim = receipt["claim"]
            injected = dict(supplied)
            for field in (
                "task_id", "task_digest", "input_digest", "claim_token", "owner", "generation"
            ):
                injected[field] = claim[field]
        except KeyError:
            raise ToolError("private execution graph claim receipt is incomplete") from None
        descriptor, temporary = tempfile.mkstemp(
            prefix=".coordination-evidence-", suffix=".json", dir=str(evidence_path.parent)
        )
        try:
            if os.name != "nt":
                os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(injected, stream, ensure_ascii=False, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            try:
                result = self._v7_command(source, "accept", "--evidence", temporary)
            except ToolError:
                return {"accepted": False, "state": "correction", "reason": "native_acceptance_rejected"}
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return {"accepted": result.get("status") == "accepted", "state": "completed"}
