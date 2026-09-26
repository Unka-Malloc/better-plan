"""Network-free loading of the packaged model catalog.

The packaged table is reference data: the model table records the one standard
Intelligence Index. The installer reads one row per packaged Codex role pin to
record that pin's ``index_score`` and ``cost_per_task_usd`` provenance. Nothing
here selects a role, a model, or an effort, and runtime dispatch never calls this
module.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
import math
from pathlib import Path
from typing import Any

from .models import ToolError


_MODEL_CATALOG_PATH = Path(__file__).with_name("model_catalog.json")
_MONEY_FIELDS = (
    "cost_per_task_usd",
    "input_price_per_million_usd",
    "output_price_per_million_usd",
    "cache_hit_price_per_million_usd",
    "cache_write_price_per_million_usd",
)
_MODEL_ROW_FIELDS = frozenset(
    {
        "model_id",
        "model",
        "creator",
        "license",
        "context_window",
        "intelligence_index",
        "intelligence_index_estimated",
        *_MONEY_FIELDS,
    }
)
_MODEL_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "catalog_version",
        "as_of",
        "source_url",
        "methodology_url",
        "status_filter",
        "model_count",
        "models",
    }
)


@dataclass(frozen=True)
class ModelRecord:
    """One model-only leaderboard row, including measured historical entries."""

    model_id: str
    model: str
    creator: str
    license: str
    context_window: str
    intelligence_index: int | None
    intelligence_index_estimated: bool
    cost_per_task_usd: float | None
    input_price_per_million_usd: float | None
    output_price_per_million_usd: float | None
    cache_hit_price_per_million_usd: float | None
    cache_write_price_per_million_usd: float | None


@dataclass(frozen=True)
class ModelCatalog:
    """Validated immutable model-only snapshot."""

    schema_version: int
    catalog_version: str
    as_of: str
    source_url: str
    methodology_url: str
    status_filter: str
    model_count: int
    models: tuple[ModelRecord, ...]


def _catalog_error() -> ToolError:
    return ToolError("role benchmark catalog is invalid")


def _string_field(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and "\x00" not in value


def _number_field(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
        and value >= 0
    )


def _money_field(value: Any) -> bool:
    return value is None or _number_field(value)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise _catalog_error() from exc


def _parse_model_catalog(payload: Any) -> ModelCatalog:
    if not isinstance(payload, dict) or set(payload) != _MODEL_TOP_LEVEL_FIELDS:
        raise _catalog_error()
    if payload.get("schema_version") != 3:
        raise _catalog_error()
    for field in (
        "catalog_version",
        "as_of",
        "source_url",
        "methodology_url",
        "status_filter",
    ):
        if not _string_field(payload.get(field)):
            raise _catalog_error()
    if payload.get("status_filter") not in {"current", "all"}:
        raise _catalog_error()

    count = payload.get("model_count")
    rows = payload.get("models")
    if type(count) is not int or count <= 0 or not isinstance(rows, list) or len(rows) != count:
        raise _catalog_error()
    records: list[ModelRecord] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != _MODEL_ROW_FIELDS:
            raise _catalog_error()
        if not all(
            _string_field(row.get(field))
            for field in ("model_id", "model", "creator", "license", "context_window")
        ):
            raise _catalog_error()
        score = row.get("intelligence_index")
        if score is not None and (type(score) is not int or score < 0):
            raise _catalog_error()
        if type(row.get("intelligence_index_estimated")) is not bool:
            raise _catalog_error()
        if any(not _money_field(row.get(field)) for field in _MONEY_FIELDS):
            raise _catalog_error()
        model_id = str(row["model_id"])
        if model_id in seen:
            raise _catalog_error()
        seen.add(model_id)
        records.append(
            ModelRecord(
                model_id=model_id,
                model=str(row["model"]),
                creator=str(row["creator"]),
                license=str(row["license"]),
                context_window=str(row["context_window"]),
                intelligence_index=score,
                intelligence_index_estimated=bool(row["intelligence_index_estimated"]),
                **{
                    field: None if row[field] is None else float(row[field])
                    for field in _MONEY_FIELDS
                },
            )
        )
    return ModelCatalog(
        schema_version=3,
        catalog_version=str(payload["catalog_version"]),
        as_of=str(payload["as_of"]),
        source_url=str(payload["source_url"]),
        methodology_url=str(payload["methodology_url"]),
        status_filter=str(payload["status_filter"]),
        model_count=int(count),
        models=tuple(records),
    )


@lru_cache(maxsize=1)
def _load_default_model_catalog() -> ModelCatalog:
    return _parse_model_catalog(_read_json(_MODEL_CATALOG_PATH))


def load_model_catalog(path: Path | None = None) -> ModelCatalog:
    """Load the packaged model table, or validate one isolated snapshot."""

    return (
        _load_default_model_catalog()
        if path is None
        else _parse_model_catalog(_read_json(Path(path)))
    )
