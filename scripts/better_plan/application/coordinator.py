"""Recoverable, source-owned coordination for authorized work units.

The journal in this module is deliberately private and small.  It records only
authorization bindings and transport correlation needed to resume a dispatch;
the source adapters remain the sole owners of task progress.
"""

from __future__ import annotations

from contextlib import contextmanager
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping
import copy
import json
import os
import tempfile
import uuid

if os.name == "nt":
    import msvcrt as _native_lock
else:
    import fcntl as _native_lock

from ..domain.coordination import evaluate, policy_binding, validate_config
from ..domain.models import SENSITIVE_TOKEN_PATTERN, ToolError, safe_summary_issue


JOURNAL_SCHEMA = "better-plan.coordination-journal/v1"
STATUS_SCHEMA = "better-plan.coordination-status/v1"
TICK_SCHEMA = "better-plan.coordination-tick/v1"
_PRIVATE_FIELDS = {
    "claim_token",
    "access_token",
    "auth_token",
    "credential",
    "credentials",
    "secret",
    "secrets",
}


def _empty_journal() -> dict[str, Any]:
    return {
        "schema": JOURNAL_SCHEMA,
        "paused": False,
        "grants": {},
        "operations": {},
    }


def _safe_reference(value: Any) -> str:
    issue = safe_summary_issue(value, max_chars=500)
    if issue is not None:
        raise ToolError("authorization reference is not privacy-safe")
    return str(value).strip()


def _reason(value: Any, fallback: str) -> str:
    text = str(value or "").strip().lower().replace("-", "_")
    if text and len(text) <= 64 and all(char.isalnum() or char == "_" for char in text):
        return text
    return fallback


def _public_brief(value: Any) -> Any:
    """Return dispatch material without accidentally forwarding private fields."""

    if isinstance(value, Mapping):
        result = {}
        for key, item in value.items():
            name = str(key)
            lowered = name.lower()
            if lowered in _PRIVATE_FIELDS:
                continue
            result[name] = _public_brief(item)
        return result
    if isinstance(value, list):
        return [_public_brief(item) for item in value]
    if isinstance(value, tuple):
        return [_public_brief(item) for item in value]
    if isinstance(value, str):
        if SENSITIVE_TOKEN_PATTERN.search(value):
            return "[redacted]"
        return value
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)


class Coordinator:
    """Coordinate source-native work without becoming a second task ledger."""

    def __init__(
        self,
        config: Mapping[str, Any],
        root: Path,
        state_path: Path,
        sources: Any,
        host: Any = None,
    ) -> None:
        self.config = dict(validate_config(config))
        self.root = Path(root).resolve()
        self.state_path = Path(state_path)
        self.sources = sources
        self.host = host
        self._host_policy = (
            dict(self.config["host"])
            if isinstance(self.config.get("host"), Mapping)
            else None
        )
        self._policy_binding = policy_binding(self.config)
        self._lanes = {
            str(lane["id"]): dict(lane)
            for lane in self.config.get("lanes", [])
            if isinstance(lane, Mapping) and isinstance(lane.get("id"), str)
        }
        self._lanes_by_source = {
            str(lane["source"]): dict(lane)
            for lane in self.config.get("lanes", [])
            if isinstance(lane, Mapping) and isinstance(lane.get("source"), str)
        }

    def _ensure_storage(self) -> None:
        parent = self.state_path.parent
        created = not parent.exists()
        parent.mkdir(parents=True, exist_ok=True)
        if created and os.name != "nt":
            os.chmod(parent, 0o700)
        if self.state_path.exists() and os.name != "nt":
            os.chmod(self.state_path, 0o600)

    @property
    def _lock_path(self) -> Path:
        return self.state_path.with_name(self.state_path.name + ".lock")

    @contextmanager
    def _lock(self) -> Iterator[None]:
        stream = self._lock_path.open("a+b")
        if os.name != "nt":
            os.chmod(self._lock_path, 0o600)
            _native_lock.flock(stream.fileno(), _native_lock.LOCK_EX)
        else:
            stream.seek(0)
            if stream.read(1) == b"":
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            _native_lock.locking(stream.fileno(), _native_lock.LK_LOCK, 1)
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                _native_lock.locking(stream.fileno(), _native_lock.LK_UNLCK, 1)
            else:
                _native_lock.flock(stream.fileno(), _native_lock.LOCK_UN)
            stream.close()

    @contextmanager
    def _operation_lock(self, operation_id: str) -> Iterator[bool]:
        path = self.state_path.with_name(".%s.operation.lock" % operation_id)
        stream = path.open("a+b")
        acquired = False
        try:
            if os.name == "nt":
                stream.seek(0)
                if stream.read(1) == b"":
                    stream.write(b"0")
                    stream.flush()
                stream.seek(0)
                try:
                    _native_lock.locking(stream.fileno(), _native_lock.LK_NBLCK, 1)
                    acquired = True
                except OSError:
                    acquired = False
            else:
                os.chmod(path, 0o600)
                try:
                    _native_lock.flock(
                        stream.fileno(), _native_lock.LOCK_EX | _native_lock.LOCK_NB
                    )
                    acquired = True
                except BlockingIOError:
                    acquired = False
            yield acquired
        finally:
            if acquired:
                if os.name == "nt":
                    stream.seek(0)
                    _native_lock.locking(stream.fileno(), _native_lock.LK_UNLCK, 1)
                else:
                    _native_lock.flock(stream.fileno(), _native_lock.LOCK_UN)
            stream.close()

    def _read_unlocked(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return _empty_journal()
        try:
            value = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raise ToolError("cannot read coordination journal")
        if not isinstance(value, Mapping) or value.get("schema") != JOURNAL_SCHEMA:
            raise ToolError("invalid coordination journal")
        if not isinstance(value.get("grants"), Mapping) or not isinstance(
            value.get("operations"), Mapping
        ):
            raise ToolError("invalid coordination journal")
        return copy.deepcopy(dict(value))

    def _write_unlocked(self, value: Mapping[str, Any]) -> None:
        descriptor, temporary = tempfile.mkstemp(
            prefix=".%s." % self.state_path.name, dir=str(self.state_path.parent)
        )
        try:
            if os.name != "nt":
                os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.state_path)
            if os.name != "nt":
                os.chmod(self.state_path, 0o600)
                directory = os.open(str(self.state_path.parent), os.O_RDONLY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _read(self) -> dict[str, Any]:
        # Atomic replacement makes a lock-free read complete and consistent.
        # This also keeps status genuinely read-only when no journal exists.
        return self._read_unlocked()

    def _change(self, edit: Callable[[dict[str, Any]], Any]) -> Any:
        self._ensure_storage()
        with self._lock():
            journal = self._read_unlocked()
            before = copy.deepcopy(journal)
            result = edit(journal)
            if journal != before:
                self._write_unlocked(journal)
            return result

    def _snapshot(self) -> dict[str, dict[str, Any]]:
        try:
            value = self.sources.snapshot()
        except Exception as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            raise ToolError("cannot read coordination sources")
        if not isinstance(value, Mapping):
            raise ToolError("invalid coordination source snapshot")
        return {
            str(key): dict(unit)
            for key, unit in value.items()
            if isinstance(key, str) and isinstance(unit, Mapping)
        }

    def _units_with_holds(
        self,
        journal: Mapping[str, Any],
        units: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        combined = {key: dict(unit) for key, unit in units.items()}
        for key, operation in journal.get("operations", {}).items():
            if not isinstance(operation, Mapping):
                continue
            if key in combined:
                # An unreleased operation retains every originally declared
                # occupancy even if a newer source revision narrows its scopes.
                combined[key]["writes"] = sorted(
                    set(combined[key].get("writes", []))
                    | set(operation.get("writes", []))
                )
                combined[key]["resources"] = sorted(
                    set(combined[key].get("resources", []))
                    | set(operation.get("resources", []))
                )
                continue
            source = operation.get("source")
            if not isinstance(source, str) or source not in self._lanes_by_source:
                continue
            combined[key] = {
                "key": key,
                "source": source,
                "binding": str(operation.get("binding", "unavailable")),
                "state": "unknown",
                "authorized": False,
                "parents": [],
                "writes": list(operation.get("writes", [])),
                "resources": list(operation.get("resources", [])),
                "brief": {},
            }
        return combined

    def _effective_grants(
        self, journal: Mapping[str, Any], units: Mapping[str, Mapping[str, Any]]
    ) -> dict[str, str]:
        effective: dict[str, str] = {}
        for key, record in journal.get("grants", {}).items():
            unit = units.get(key)
            if not isinstance(record, Mapping) or unit is None:
                continue
            binding = unit.get("binding")
            if (
                isinstance(binding, str)
                and record.get("binding") == binding
                and record.get("policy_binding") == self._policy_binding
            ):
                effective[key] = binding
        return effective

    def _evaluation(
        self, journal: Mapping[str, Any], units: Mapping[str, Mapping[str, Any]]
    ) -> dict[str, Any]:
        active = {
            str(key) for key in journal.get("operations", {}) if str(key) in units
        }
        arguments = (
            self.config,
            units,
            self.root,
            self._effective_grants(journal, units),
            active,
        )
        source_errors = getattr(self.sources, "source_errors", None)
        if isinstance(source_errors, Mapping):
            return evaluate(*arguments, source_errors=dict(source_errors))
        return evaluate(*arguments)

    def grant(self, keys: list[str], reference: str) -> dict[str, Any]:
        safe_reference = _safe_reference(reference)
        units = self._snapshot()
        selected = []
        for key in keys:
            if key not in units:
                raise ToolError("authorization key is not in the current source snapshot")
            binding = units[key].get("binding")
            if not isinstance(binding, str) or not binding:
                raise ToolError("authorization key has no source binding")
            selected.append((key, binding))

        def edit(journal: dict[str, Any]) -> None:
            grants = journal["grants"]
            for key, binding in selected:
                grants[key] = {
                    "binding": binding,
                    "policy_binding": self._policy_binding,
                    "reference": safe_reference,
                }

        self._change(edit)
        return {"granted": sorted(key for key, _binding in selected)}

    def revoke(self, keys: list[str]) -> dict[str, Any]:
        def edit(journal: dict[str, Any]) -> None:
            for key in keys:
                journal["grants"].pop(key, None)
                operation = journal["operations"].get(key)
                if isinstance(operation, dict):
                    operation["stage"] = "needs_review"
                    operation["reason"] = "authorization_revoked"

        self._change(edit)
        return {"revoked": sorted(set(keys))}

    def pause(self) -> dict[str, Any]:
        self._change(lambda journal: journal.__setitem__("paused", True))
        return {"paused": True}

    def resume(self) -> dict[str, Any]:
        self._change(lambda journal: journal.__setitem__("paused", False))
        return {"paused": False}

    def reconcile(self, keys: list[str]) -> dict[str, Any]:
        """Retry observation of quarantined work without creating a new operation."""

        units = self._snapshot()

        def edit(journal: dict[str, Any]) -> list[str]:
            effective = self._effective_grants(journal, units)
            changed: list[str] = []
            for key in keys:
                operation = journal["operations"].get(key)
                unit = units.get(key)
                if (
                    not isinstance(operation, dict)
                    or operation.get("stage") != "needs_review"
                    or unit is None
                    or unit.get("binding") != operation.get("binding")
                    or effective.get(key) != operation.get("binding")
                ):
                    continue
                if operation.get("host_id"):
                    operation["stage"] = "host_started"
                elif operation.get("receipt"):
                    operation["stage"] = "prepared"
                else:
                    operation["stage"] = "intent"
                operation["reason"] = None
                changed.append(key)
            return changed

        return {"reconciled": sorted(self._change(edit))}

    def status(self) -> dict[str, Any]:
        journal = self._read()
        units = self._units_with_holds(journal, self._snapshot())
        evaluation = self._evaluation(journal, units)
        operations = []
        for key, operation in sorted(journal["operations"].items()):
            operations.append(
                {
                    "key": key,
                    "stage": str(operation.get("stage", "needs_review")),
                    "reason": operation.get("reason"),
                }
            )
        return {
            "schema": STATUS_SCHEMA,
            "paused": bool(journal.get("paused")),
            "host_configured": self.host is not None and self._host_policy is not None,
            "grants": sorted(self._effective_grants(journal, units)),
            "operations": operations,
            "evaluation": evaluation,
        }

    def _set_operation(
        self,
        key: str,
        operation_id: str,
        *,
        expected_stages: set[str] | None = None,
        **fields: Any,
    ) -> bool:
        def edit(journal: dict[str, Any]) -> bool:
            operation = journal["operations"].get(key)
            if not isinstance(operation, dict) or operation.get("operation_id") != operation_id:
                return False
            if expected_stages is not None and operation.get("stage") not in expected_stages:
                return False
            if "stage" in fields and expected_stages is None:
                return False
            operation.update(fields)
            return True

        return bool(self._change(edit))

    def _drop_operation(self, key: str, operation_id: str) -> bool:
        def edit(journal: dict[str, Any]) -> bool:
            operation = journal["operations"].get(key)
            if not isinstance(operation, dict) or operation.get("operation_id") != operation_id:
                return False
            del journal["operations"][key]
            return True

        return bool(self._change(edit))

    def _grant_matches(
        self, journal: Mapping[str, Any], key: str, binding: Any
    ) -> bool:
        grant = journal.get("grants", {}).get(key)
        return (
            isinstance(grant, Mapping)
            and grant.get("binding") == binding
            and grant.get("policy_binding") == self._policy_binding
        )

    def _commit_prepared(
        self,
        key: str,
        operation_id: str,
        receipt: Mapping[str, Any],
        dispatch_role: str,
    ) -> bool:
        """Persist the private receipt and CAS intent to prepared."""

        def edit(journal: dict[str, Any]) -> bool:
            operation = journal["operations"].get(key)
            if not isinstance(operation, dict) or operation.get("operation_id") != operation_id:
                return False
            operation["receipt"] = copy.deepcopy(dict(receipt))
            operation["dispatch_role"] = dispatch_role
            if operation.get("stage") != "intent":
                return False
            if not self._grant_matches(journal, key, operation.get("binding")):
                operation["stage"] = "needs_review"
                operation["reason"] = "authorization_changed"
                return False
            operation["stage"] = "prepared"
            operation["reason"] = None
            return not bool(journal.get("paused"))

        return bool(self._change(edit))

    def _prepared_may_start(self, key: str, operation_id: str) -> bool:
        journal = self._read()
        operation = journal["operations"].get(key)
        return (
            isinstance(operation, Mapping)
            and operation.get("operation_id") == operation_id
            and operation.get("stage") == "prepared"
            and not journal.get("paused")
            and self._grant_matches(journal, key, operation.get("binding"))
        )

    def _commit_host_started(
        self, key: str, operation_id: str, host_id: str
    ) -> bool:
        """Always retain host correlation; advance only from current prepared state."""

        def edit(journal: dict[str, Any]) -> bool:
            operation = journal["operations"].get(key)
            if not isinstance(operation, dict) or operation.get("operation_id") != operation_id:
                return False
            operation["host_id"] = host_id
            if (
                operation.get("stage") != "prepared"
                or journal.get("paused")
                or not self._grant_matches(journal, key, operation.get("binding"))
            ):
                return False
            operation["stage"] = "host_started"
            operation["reason"] = None
            return True

        return bool(self._change(edit))

    def _attention(
        self, key: str, operation_id: str, reason: str, attention: list[dict[str, str]]
    ) -> None:
        safe = _reason(reason, "coordination_error")
        self._set_operation(
            key,
            operation_id,
            expected_stages={"intent", "prepared", "host_started", "live", "finishing"},
            stage="needs_review",
            reason=safe,
        )
        attention.append({"key": key, "reason": safe})

    def _repository(self, unit: Mapping[str, Any]) -> str:
        lane = self._lanes.get(str(unit.get("lane"))) or self._lanes_by_source.get(
            str(unit.get("source"))
        )
        if lane is None:
            raise ToolError("coordination unit has no configured lane")
        return str(lane["repository"])

    def _lane(self, unit: Mapping[str, Any]) -> Mapping[str, Any] | None:
        return self._lanes.get(str(unit.get("lane"))) or self._lanes_by_source.get(
            str(unit.get("source"))
        )

    def _dispatch_role(self, unit: Mapping[str, Any]) -> str | None:
        if self._host_policy is None:
            return None
        brief = unit.get("brief")
        native = brief.get("agent_type") if isinstance(brief, Mapping) else None
        lane = self._lane(unit)
        configured = None
        if lane is not None and isinstance(self._host_policy.get("lanes"), Mapping):
            configured = self._host_policy["lanes"].get(lane.get("id"))
        role = native if isinstance(native, str) and native else configured
        profiles = self._host_policy.get("profiles", {})
        return role if isinstance(role, str) and role in profiles else None

    def _resume_operation(
        self,
        key: str,
        unit: Mapping[str, Any],
        operation: Mapping[str, Any],
        summary: dict[str, Any],
        *,
        allow_start: bool = True,
    ) -> None:
        operation_id = str(operation.get("operation_id", ""))
        if not operation_id:
            return
        with self._operation_lock(operation_id) as acquired:
            if acquired:
                self._resume_operation_locked(
                    key, unit, operation, summary, allow_start=allow_start
                )

    def _resume_operation_locked(
        self,
        key: str,
        unit: Mapping[str, Any],
        operation: Mapping[str, Any],
        summary: dict[str, Any],
        *,
        allow_start: bool = True,
    ) -> None:
        operation_id = str(operation.get("operation_id", ""))
        if not operation_id:
            return
        if unit.get("binding") != operation.get("binding"):
            self._attention(key, operation_id, "binding_changed", summary["attention"])
            return
        if unit.get("state") == "completed":
            if self._drop_operation(key, operation_id):
                summary["released"].append(key)
            return
        if operation.get("stage") == "needs_review":
            summary["attention"].append(
                {"key": key, "reason": _reason(operation.get("reason"), "needs_review")}
            )
            return

        stage = operation.get("stage")
        receipt = operation.get("receipt")
        if stage == "intent":
            if not allow_start:
                return
            expected_role = self._dispatch_role(unit)
            if expected_role is None:
                self._attention(
                    key, operation_id, "dispatch_role_unconfigured", summary["attention"]
                )
                return
            try:
                receipt = self.sources.prepare(key, operation_id)
            except Exception as exc:
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    raise
                summary["attention"].append({"key": key, "reason": "prepare_error"})
                return
            if not isinstance(receipt, Mapping) or any(
                receipt.get(field) != expected
                for field, expected in (
                    ("key", key),
                    ("operation_id", operation_id),
                    ("binding", operation.get("binding")),
                )
            ):
                self._attention(key, operation_id, "receipt_mismatch", summary["attention"])
                return
            receipt = copy.deepcopy(dict(receipt))
            receipt_brief = receipt.get("brief")
            receipt_role = (
                receipt_brief.get("agent_type")
                if isinstance(receipt_brief, Mapping)
                else None
            )
            if receipt_role is not None and receipt_role != expected_role:
                self._set_operation(
                    key,
                    operation_id,
                    expected_stages={"intent"},
                    stage="needs_review",
                    receipt=receipt,
                    dispatch_role=expected_role,
                    reason="dispatch_role_mismatch",
                )
                summary["attention"].append(
                    {"key": key, "reason": "dispatch_role_mismatch"}
                )
                return
            allow_start = allow_start and self._commit_prepared(
                key, operation_id, receipt, expected_role
            )
            stage = "prepared"

        if self.host is None or self._host_policy is None:
            summary["attention"].append({"key": key, "reason": "host_not_configured"})
            return

        if stage == "prepared":
            if not isinstance(receipt, Mapping) or "brief" not in receipt:
                self._attention(key, operation_id, "receipt_mismatch", summary["attention"])
                return
            try:
                renewed = self.sources.renew(key, receipt)
            except Exception as exc:
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    raise
                summary["attention"].append(
                    {"key": key, "reason": "source_renew_error"}
                )
                return
            if isinstance(renewed, Mapping):
                receipt = copy.deepcopy(dict(renewed))
                self._set_operation(key, operation_id, receipt=receipt)
            summary["renewed"].append(key)
            if not allow_start or not self._prepared_may_start(key, operation_id):
                return
            dispatch_brief = _public_brief(receipt["brief"])
            if isinstance(dispatch_brief, Mapping) and self.config.get("constraints"):
                dispatch_brief = dict(dispatch_brief)
                dispatch_brief["coordination_constraints"] = list(self.config["constraints"])
            if isinstance(dispatch_brief, Mapping) and not dispatch_brief.get("agent_type"):
                dispatch_brief = dict(dispatch_brief)
                dispatch_brief["agent_type"] = operation.get("dispatch_role") or self._read()[
                    "operations"
                ].get(key, {}).get("dispatch_role")
            try:
                host_id = self.host.start(
                    operation_id,
                    key,
                    dispatch_brief,
                    self._repository(unit),
                )
            except Exception as exc:
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    raise
                summary["attention"].append({"key": key, "reason": "host_start_error"})
                return
            if not isinstance(host_id, str) or not host_id:
                self._attention(key, operation_id, "host_identity_invalid", summary["attention"])
                return
            if not self._commit_host_started(key, operation_id, host_id):
                return
            stage = "host_started"
            operation = dict(operation)
            operation["host_id"] = host_id

        host_id = operation.get("host_id")
        if stage == "host_started":
            current = self._read()["operations"].get(key, {})
            receipt = current.get("receipt")
            host_id = current.get("host_id")
            try:
                renewed = self.sources.renew(key, receipt)
            except Exception as exc:
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    raise
                summary["attention"].append({"key": key, "reason": "source_renew_error"})
                return
            if isinstance(renewed, Mapping):
                receipt = copy.deepcopy(dict(renewed))
                self._set_operation(key, operation_id, receipt=receipt)
            summary["renewed"].append(key)
            try:
                self.sources.bind(key, receipt, host_id)
            except Exception as exc:
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    raise
                summary["attention"].append({"key": key, "reason": "source_bind_error"})
                return
            if not self._set_operation(
                key,
                operation_id,
                expected_stages={"host_started"},
                stage="live",
                reason=None,
            ):
                return
            summary["started"].append(key)
            stage = "live"

        if stage not in {"live", "finishing"}:
            return
        current = self._read()["operations"].get(key, {})
        receipt = current.get("receipt")
        host_id = current.get("host_id")
        try:
            host_state = self.host.inspect(host_id)
        except Exception as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            self._attention(key, operation_id, "host_inspect_error", summary["attention"])
            return
        if not isinstance(host_state, Mapping):
            self._attention(key, operation_id, "host_state_invalid", summary["attention"])
            return
        state = host_state.get("state")
        if state in {"pending", "running"}:
            try:
                renewed = self.sources.renew(key, receipt)
            except Exception as exc:
                if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                    raise
                summary["attention"].append({"key": key, "reason": "source_renew_error"})
                return
            if isinstance(renewed, Mapping):
                self._set_operation(key, operation_id, receipt=copy.deepcopy(dict(renewed)))
            summary["renewed"].append(key)
            return
        if state in {"failed", "unknown"}:
            self._attention(key, operation_id, "host_%s" % state, summary["attention"])
            return
        if state != "succeeded":
            self._attention(key, operation_id, "host_state_invalid", summary["attention"])
            return

        if not self._set_operation(
            key,
            operation_id,
            expected_stages={"live", "finishing"},
            stage="finishing",
            reason=None,
        ):
            return
        try:
            result = self.sources.finish(
                key, receipt, host_id, evidence=host_state.get("evidence")
            )
        except Exception as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            summary["attention"].append({"key": key, "reason": "source_finish_error"})
            return
        if isinstance(result, Mapping) and result.get("accepted") is True:
            if self._drop_operation(key, operation_id):
                summary["accepted"].append(key)
            return
        result_reason = result.get("reason") if isinstance(result, Mapping) else None
        self._attention(
            key,
            operation_id,
            _reason(result_reason, "source_acceptance_pending"),
            summary["attention"],
        )

    def _reserve_batch(
        self, units: Mapping[str, Mapping[str, Any]]
    ) -> list[str]:
        """Reserve one freshly re-evaluated batch in a single short write."""

        if self.host is None or self._host_policy is None:
            return []
        preview = self._read()
        if preview.get("paused"):
            return []
        preview_units = self._units_with_holds(preview, units)
        if not self._evaluation(preview, preview_units).get("batch"):
            return []

        def edit(journal: dict[str, Any]) -> list[str]:
            if journal.get("paused") or self.host is None or self._host_policy is None:
                return []
            current_units = self._units_with_holds(journal, units)
            evaluation = self._evaluation(journal, current_units)
            reserved: list[str] = []
            for key in evaluation.get("batch", []):
                if key in journal["operations"] or key not in current_units:
                    continue
                source_unit = current_units[key]
                journal["operations"][key] = {
                    "operation_id": str(uuid.uuid4()),
                    "binding": source_unit["binding"],
                    "source": source_unit["source"],
                    "writes": list(source_unit.get("writes", [])),
                    "resources": list(source_unit.get("resources", [])),
                    "stage": "intent",
                    "reason": None,
                }
                reserved.append(key)
            return reserved

        return self._change(edit)

    def _quarantine_invalid_gates(
        self,
        journal: Mapping[str, Any],
        units: Mapping[str, Mapping[str, Any]],
        attention: list[dict[str, str]],
    ) -> None:
        held_units = self._units_with_holds(journal, units)
        source_errors = getattr(self.sources, "source_errors", None)
        arguments = (
            self.config,
            held_units,
            self.root,
            self._effective_grants(journal, held_units),
            set(),
        )
        if isinstance(source_errors, Mapping):
            gate_evaluation = evaluate(*arguments, source_errors=dict(source_errors))
        else:
            gate_evaluation = evaluate(*arguments)
        projections = {
            item["key"]: item
            for item in gate_evaluation.get("units", [])
            if isinstance(item, Mapping) and isinstance(item.get("key"), str)
        }
        invalid = {
            "waiting_dependency",
            "waiting_external",
            "blocked",
            "unknown",
            "needs_review",
        }
        for key, operation in journal.get("operations", {}).items():
            projection = projections.get(key)
            if (
                isinstance(operation, Mapping)
                and operation.get("stage") != "needs_review"
                and isinstance(projection, Mapping)
                and projection.get("readiness") in invalid
            ):
                self._attention(
                    key,
                    str(operation.get("operation_id", "")),
                    "prerequisite_changed",
                    attention,
                )

    @staticmethod
    def _merge_summary(target: dict[str, Any], source: Mapping[str, Any]) -> None:
        for field in ("started", "accepted", "renewed", "released", "attention"):
            target[field].extend(source.get(field, []))

    def _maintain_live(self, excluded: set[str], summary: dict[str, Any]) -> None:
        journal = self._read()
        for key, operation in journal.get("operations", {}).items():
            if (
                not isinstance(operation, Mapping)
                or operation.get("stage") != "live"
                or operation.get("operation_id") in excluded
            ):
                continue
            operation_id = str(operation.get("operation_id", ""))
            with self._operation_lock(operation_id) as acquired:
                if not acquired:
                    continue
                try:
                    renewed = self.sources.renew(key, operation.get("receipt"))
                except Exception:
                    summary["attention"].append(
                        {"key": key, "reason": "source_renew_error"}
                    )
                    continue
                if isinstance(renewed, Mapping):
                    self._set_operation(
                        key, operation_id, receipt=copy.deepcopy(dict(renewed))
                    )
                summary["renewed"].append(key)

    def _advance_parallel(
        self,
        keys: list[str],
        units: Mapping[str, Mapping[str, Any]],
        paused: bool,
        summary: dict[str, Any],
    ) -> None:
        if not keys:
            return

        def advance(key: str) -> dict[str, Any]:
            local = {
                "started": [],
                "accepted": [],
                "renewed": [],
                "released": [],
                "attention": [],
            }
            try:
                current = self._read()["operations"].get(key)
                unit = units.get(key)
                if isinstance(current, Mapping) and unit is not None:
                    self._resume_operation(
                        key, unit, current, local, allow_start=not paused
                    )
            except Exception:
                local["attention"].append(
                    {"key": key, "reason": "coordination_error"}
                )
            return local

        workers = max(1, min(len(keys), int(self.config["max_parallel"])))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(advance, key): key for key in keys}
            pending = set(futures)
            while pending:
                done, pending = wait(pending, timeout=30.0, return_when=FIRST_COMPLETED)
                for future in done:
                    self._merge_summary(summary, future.result())
                if pending:
                    excluded = {
                        str(
                            self._read()["operations"].get(futures[future], {}).get(
                                "operation_id", ""
                            )
                        )
                        for future in pending
                    }
                    self._maintain_live(excluded, summary)

    def tick(self) -> dict[str, Any]:
        """Reconcile live work, then start one newly eligible conflict-free batch."""

        summary: dict[str, Any] = {
            "schema": TICK_SCHEMA,
            "started": [],
            "accepted": [],
            "renewed": [],
            "released": [],
            "attention": [],
        }
        journal = self._read()
        raw_units = self._snapshot()
        units = self._units_with_holds(journal, raw_units)

        effective = self._effective_grants(journal, units)
        for key, operation in sorted(journal["operations"].items()):
            if key in units and effective.get(key) != operation.get("binding"):
                reason = (
                    "binding_changed"
                    if units[key].get("binding") != operation.get("binding")
                    else "authorization_changed"
                )
                self._attention(
                    key,
                    str(operation.get("operation_id", "")),
                    reason,
                    summary["attention"],
                )
        journal = self._read()
        self._quarantine_invalid_gates(journal, units, summary["attention"])
        journal = self._read()
        paused = bool(journal.get("paused"))

        # Reserve independent work before acceptance begins. A slow focused
        # regression therefore cannot prevent unrelated ready work from starting.
        reserved = self._reserve_batch(raw_units) if not paused else []
        journal = self._read()
        units = self._units_with_holds(journal, raw_units)
        first_wave = sorted(set(journal["operations"]) | set(reserved))
        self._advance_parallel(first_wave, units, paused, summary)

        # Acceptance can expose a new frontier. Re-read source truth and reserve
        # that frontier once, while preserving any quarantined occupancy.
        journal = self._read()
        raw_units = self._snapshot()
        units = self._units_with_holds(journal, raw_units)
        newly_reserved = self._reserve_batch(raw_units) if not journal.get("paused") else []
        if newly_reserved:
            journal = self._read()
            units = self._units_with_holds(journal, raw_units)
            self._advance_parallel(newly_reserved, units, False, summary)

        journal = self._read()
        evaluation = self._evaluation(
            journal, self._units_with_holds(journal, self._snapshot())
        )
        if (
            not journal.get("paused")
            and (self.host is None or self._host_policy is None)
            and evaluation.get("ready")
        ):
            summary["attention"].extend(
                {"key": key, "reason": "host_not_configured"}
                for key in evaluation.get("ready", [])
            )

        final_journal = self._read()
        final_units = self._units_with_holds(final_journal, self._snapshot())
        summary["paused"] = bool(final_journal.get("paused"))
        summary["evaluation"] = self._evaluation(final_journal, final_units)
        for field in ("started", "accepted", "renewed", "released"):
            summary[field] = sorted(set(summary[field]))
        unique_attention = {
            (item["key"], item["reason"]): item for item in summary["attention"]
        }
        summary["attention"] = [
            unique_attention[key] for key in sorted(unique_attention)
        ]
        return summary
