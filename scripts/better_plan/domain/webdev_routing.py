"""Network-free visual-role selection over a versioned Arena WebDev snapshot."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from functools import lru_cache
import json
import math
from pathlib import Path
from typing import Any

from .models import ToolError


_CATALOG_PATH = Path(__file__).with_name("webdev_model_catalog.json")
_SOURCE_URL = "https://arena.ai/leaderboard/code/webdev"
_SELECTION_POLICY = "highest_webdev_score_for_visual_roles"
_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "catalog_version",
        "as_of",
        "source_url",
        "leaderboard_id",
        "category",
        "selection_policy",
        "model_count",
        "models",
    }
)
_ROW_FIELDS = frozenset(
    {
        "entry_id",
        "model_id",
        "model",
        "rank",
        "rank_upper",
        "rank_lower",
        "score",
        "votes",
    }
)


@dataclass(frozen=True)
class WebDevRecord:
    """One Arena WebDev leaderboard row mapped to a native selector identity."""

    entry_id: str
    model_id: str
    model: str
    rank: int
    rank_upper: int
    rank_lower: int
    score: float
    votes: int


@dataclass(frozen=True)
class WebDevCatalog:
    """Validated immutable Arena WebDev snapshot."""

    schema_version: int
    catalog_version: str
    as_of: str
    source_url: str
    leaderboard_id: str
    category: str
    selection_policy: str
    model_count: int
    models: tuple[WebDevRecord, ...]


def _catalog_error() -> ToolError:
    return ToolError("Arena WebDev benchmark catalog is invalid")


def _selection_error() -> ToolError:
    return ToolError("no locally available visual role configuration qualifies")


def _string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and "\x00" not in value


def _positive_int(value: Any) -> bool:
    return type(value) is int and value > 0


def _parse(payload: Any) -> WebDevCatalog:
    if not isinstance(payload, dict) or set(payload) != _TOP_LEVEL_FIELDS:
        raise _catalog_error()
    if payload.get("schema_version") != 1:
        raise _catalog_error()
    for field in (
        "catalog_version",
        "as_of",
        "source_url",
        "leaderboard_id",
        "category",
        "selection_policy",
    ):
        if not _string(payload.get(field)):
            raise _catalog_error()
    if payload["source_url"] != _SOURCE_URL or payload["category"] != "overall":
        raise _catalog_error()
    if payload["selection_policy"] != _SELECTION_POLICY:
        raise _catalog_error()
    rows = payload.get("models")
    count = payload.get("model_count")
    if not _positive_int(count) or not isinstance(rows, list) or len(rows) != count:
        raise _catalog_error()

    records: list[WebDevRecord] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != _ROW_FIELDS:
            raise _catalog_error()
        if not all(_string(row.get(field)) for field in ("entry_id", "model_id", "model")):
            raise _catalog_error()
        if not all(_positive_int(row.get(field)) for field in ("rank", "rank_upper", "rank_lower", "votes")):
            raise _catalog_error()
        score = row.get("score")
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or score <= 0:
            raise _catalog_error()
        entry_id = str(row["entry_id"])
        if entry_id in seen:
            raise _catalog_error()
        seen.add(entry_id)
        records.append(
            WebDevRecord(
                entry_id=entry_id,
                model_id=str(row["model_id"]),
                model=str(row["model"]),
                rank=int(row["rank"]),
                rank_upper=int(row["rank_upper"]),
                rank_lower=int(row["rank_lower"]),
                score=float(score),
                votes=int(row["votes"]),
            )
        )
    return WebDevCatalog(
        schema_version=1,
        catalog_version=str(payload["catalog_version"]),
        as_of=str(payload["as_of"]),
        source_url=str(payload["source_url"]),
        leaderboard_id=str(payload["leaderboard_id"]),
        category=str(payload["category"]),
        selection_policy=str(payload["selection_policy"]),
        model_count=int(count),
        models=tuple(records),
    )


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise _catalog_error() from exc


@lru_cache(maxsize=1)
def _load_default_webdev_catalog() -> WebDevCatalog:
    return _parse(_read_json(_CATALOG_PATH))


def load_webdev_catalog(path: Path | None = None) -> WebDevCatalog:
    """Load the packaged Arena snapshot, or validate one isolated snapshot."""

    return _load_default_webdev_catalog() if path is None else _parse(_read_json(path))


def select_webdev_model_from_catalog(
    catalog: WebDevCatalog,
    *,
    available_model_ids: Collection[str] | None = None,
) -> WebDevRecord:
    """Choose the highest-scoring locally available Arena WebDev entry."""

    if not isinstance(catalog, WebDevCatalog):
        raise _selection_error()
    allowed = None if available_model_ids is None else frozenset(available_model_ids)
    candidates = [
        record
        for record in catalog.models
        if allowed is None or record.model_id in allowed
    ]
    if not candidates:
        raise _selection_error()
    return min(candidates, key=lambda record: (-record.score, record.rank, record.entry_id))


def select_webdev_model(
    *,
    available_model_ids: Collection[str] | None = None,
) -> WebDevRecord:
    return select_webdev_model_from_catalog(
        load_webdev_catalog(),
        available_model_ids=available_model_ids,
    )
