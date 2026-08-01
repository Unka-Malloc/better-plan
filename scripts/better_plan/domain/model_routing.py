"""Network-free role selection over versioned Artificial Analysis snapshots.

The model table ranks non-coding roles by Intelligence Index.  The Coding
Agent table independently routes Worker configurations by task difficulty and
cost.  Runtime dispatch never calls this module: assignments are selected once
while native Better Plan agents are created and are then persisted by the
installer.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from functools import lru_cache
import json
import math
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from .models import ToolError


_MODEL_CATALOG_PATH = Path(__file__).with_name("model_catalog.json")
_CODING_AGENT_CATALOG_PATH = Path(__file__).with_name("coding_agent_catalog.json")
_DIFFICULTIES = ("routine", "standard", "complex", "critical")
_INTELLIGENCE_ROLES = frozenset({"designer", "verifier", "reviewer"})
_MODEL_SELECTION_POLICY = "intelligence_rank_for_non_worker_roles"
_WORKER_SELECTION_POLICY = "lowest_cost_above_task_difficulty_floor"
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
        "selection_policy",
        "model_count",
        "models",
    }
)
_CODING_AGENT_ROW_FIELDS = frozenset(
    {
        "variant_id",
        "harness",
        "model",
        "reasoning_effort",
        "index_score",
        "cost_per_task_usd",
    }
)
_CODING_AGENT_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "catalog_version",
        "as_of",
        "source_url",
        "methodology_url",
        "methodology_version",
        "usage",
        "selection_policy",
        "difficulty_floors",
        "variant_count",
        "variants",
    }
)


@dataclass(frozen=True)
class ModelRecord:
    """One current model-only leaderboard row."""

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
    selection_policy: str
    model_count: int
    models: tuple[ModelRecord, ...]


@dataclass(frozen=True)
class CodingAgentRecord:
    """One measured coding-harness and model configuration."""

    variant_id: str
    harness: str
    model: str
    reasoning_effort: str
    index_score: int
    cost_per_task_usd: float


@dataclass(frozen=True)
class CodingAgentCatalog:
    """Validated immutable Coding Agent snapshot and Worker difficulty policy."""

    schema_version: int
    catalog_version: str
    as_of: str
    source_url: str
    methodology_url: str
    methodology_version: str
    usage: str
    selection_policy: str
    difficulty_floors: Mapping[str, int]
    variant_count: int
    variants: tuple[CodingAgentRecord, ...]


def _catalog_error() -> ToolError:
    return ToolError("role benchmark catalog is invalid")


def _selection_error() -> ToolError:
    return ToolError("no locally available role configuration qualifies")


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
        "selection_policy",
    ):
        if not _string_field(payload.get(field)):
            raise _catalog_error()
    if payload.get("status_filter") != "current":
        raise _catalog_error()
    if payload.get("selection_policy") != _MODEL_SELECTION_POLICY:
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
        selection_policy=str(payload["selection_policy"]),
        model_count=int(count),
        models=tuple(records),
    )


def _parse_difficulty_floors(value: Any) -> Mapping[str, int]:
    if not isinstance(value, dict) or set(value) != set(_DIFFICULTIES):
        raise _catalog_error()
    floors = [value[name] for name in _DIFFICULTIES]
    if any(type(floor) is not int or floor < 0 for floor in floors):
        raise _catalog_error()
    if floors != sorted(floors) or len(set(floors)) != len(floors):
        raise _catalog_error()
    return MappingProxyType({name: int(value[name]) for name in _DIFFICULTIES})


def _parse_coding_agent_catalog(payload: Any) -> CodingAgentCatalog:
    if not isinstance(payload, dict) or set(payload) != _CODING_AGENT_TOP_LEVEL_FIELDS:
        raise _catalog_error()
    if payload.get("schema_version") != 2:
        raise _catalog_error()
    for field in (
        "catalog_version",
        "as_of",
        "source_url",
        "methodology_url",
        "methodology_version",
        "usage",
        "selection_policy",
    ):
        if not _string_field(payload.get(field)):
            raise _catalog_error()
    if payload.get("usage") != "worker_routing_reference":
        raise _catalog_error()
    if payload.get("selection_policy") != _WORKER_SELECTION_POLICY:
        raise _catalog_error()
    floors = _parse_difficulty_floors(payload.get("difficulty_floors"))
    count = payload.get("variant_count")
    rows = payload.get("variants")
    if type(count) is not int or count <= 0 or not isinstance(rows, list) or len(rows) != count:
        raise _catalog_error()
    records: list[CodingAgentRecord] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != _CODING_AGENT_ROW_FIELDS:
            raise _catalog_error()
        if not all(
            _string_field(row.get(field))
            for field in ("variant_id", "harness", "model", "reasoning_effort")
        ):
            raise _catalog_error()
        score = row.get("index_score")
        cost = row.get("cost_per_task_usd")
        if type(score) is not int or score < 0 or not _number_field(cost):
            raise _catalog_error()
        variant_id = str(row["variant_id"])
        if variant_id in seen:
            raise _catalog_error()
        seen.add(variant_id)
        records.append(
            CodingAgentRecord(
                variant_id=variant_id,
                harness=str(row["harness"]),
                model=str(row["model"]),
                reasoning_effort=str(row["reasoning_effort"]),
                index_score=int(score),
                cost_per_task_usd=float(cost),
            )
        )
    return CodingAgentCatalog(
        schema_version=2,
        catalog_version=str(payload["catalog_version"]),
        as_of=str(payload["as_of"]),
        source_url=str(payload["source_url"]),
        methodology_url=str(payload["methodology_url"]),
        methodology_version=str(payload["methodology_version"]),
        usage=str(payload["usage"]),
        selection_policy=str(payload["selection_policy"]),
        difficulty_floors=floors,
        variant_count=int(count),
        variants=tuple(records),
    )


@lru_cache(maxsize=1)
def _load_default_model_catalog() -> ModelCatalog:
    return _parse_model_catalog(_read_json(_MODEL_CATALOG_PATH))


@lru_cache(maxsize=1)
def _load_default_coding_agent_catalog() -> CodingAgentCatalog:
    return _parse_coding_agent_catalog(_read_json(_CODING_AGENT_CATALOG_PATH))


def load_model_catalog(path: Path | None = None) -> ModelCatalog:
    """Load the packaged model table, or validate one isolated snapshot."""

    return (
        _load_default_model_catalog()
        if path is None
        else _parse_model_catalog(_read_json(Path(path)))
    )


def load_coding_agent_catalog(path: Path | None = None) -> CodingAgentCatalog:
    """Load the packaged Coding Agent table, or validate one isolated snapshot."""

    return (
        _load_default_coding_agent_catalog()
        if path is None
        else _parse_coding_agent_catalog(_read_json(Path(path)))
    )


def _available_ids(values: Collection[str] | None) -> frozenset[str] | None:
    if values is None:
        return None
    if isinstance(values, (str, bytes)):
        raise _selection_error()
    try:
        normalized = frozenset(values)
    except TypeError as exc:
        raise _selection_error() from exc
    if not normalized or any(not _string_field(value) for value in normalized):
        raise _selection_error()
    return normalized


def select_worker_agent_from_catalog(
    catalog: CodingAgentCatalog,
    difficulty: str,
    *,
    harness: str | None = None,
    available_variant_ids: Collection[str] | None = None,
) -> CodingAgentRecord:
    """Choose the cheapest measured Worker combination above the difficulty floor."""

    if not isinstance(catalog, CodingAgentCatalog) or difficulty not in _DIFFICULTIES:
        raise _selection_error()
    if harness is not None and not _string_field(harness):
        raise _selection_error()
    allowed = _available_ids(available_variant_ids)
    floor = catalog.difficulty_floors[difficulty]
    candidates = [
        variant
        for variant in catalog.variants
        if variant.index_score >= floor
        and (harness is None or variant.harness == harness)
        and (allowed is None or variant.variant_id in allowed)
    ]
    if not candidates:
        raise _selection_error()
    return min(
        candidates,
        key=lambda variant: (
            variant.cost_per_task_usd,
            -variant.index_score,
            variant.variant_id,
        ),
    )


def select_worker_agent(
    difficulty: str,
    *,
    harness: str | None = None,
    available_variant_ids: Collection[str] | None = None,
) -> CodingAgentRecord:
    """Select one Worker combination from the packaged Coding Agent table."""

    return select_worker_agent_from_catalog(
        load_coding_agent_catalog(),
        difficulty,
        harness=harness,
        available_variant_ids=available_variant_ids,
    )


def select_intelligence_model_from_catalog(
    catalog: ModelCatalog,
    role: str,
    *,
    available_model_ids: Collection[str] | None = None,
) -> ModelRecord:
    """Rank locally available non-Worker models without considering price.

    Designer and Reviewer use the highest Intelligence Index.  Verifier uses
    the next distinct score when one exists, reserving the strongest tier for
    the two end-cap roles; a one-tier local installation necessarily reuses it.
    """

    if not isinstance(catalog, ModelCatalog) or role not in _INTELLIGENCE_ROLES:
        raise _selection_error()
    allowed = _available_ids(available_model_ids)
    candidates = [
        model
        for model in catalog.models
        if model.intelligence_index is not None
        and (allowed is None or model.model_id in allowed)
    ]
    if not candidates:
        raise _selection_error()
    scores = sorted(
        {int(model.intelligence_index) for model in candidates},
        reverse=True,
    )
    target_score = scores[1] if role == "verifier" and len(scores) > 1 else scores[0]
    # Cost is deliberately absent from the key.
    return min(
        (model for model in candidates if model.intelligence_index == target_score),
        key=lambda model: model.model_id,
    )


def select_intelligence_model(
    role: str,
    *,
    available_model_ids: Collection[str] | None = None,
) -> ModelRecord:
    """Select one non-Worker role model from the packaged model table."""

    return select_intelligence_model_from_catalog(
        load_model_catalog(),
        role,
        available_model_ids=available_model_ids,
    )
