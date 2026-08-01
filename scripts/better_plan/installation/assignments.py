"""Select native Better Plan agent assignments once from local capability and tables."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from types import MappingProxyType
from typing import Final, Iterable, Mapping

from ..domain.model_routing import (
    CodingAgentCatalog,
    CodingAgentRecord,
    ModelCatalog,
    ModelRecord,
    load_coding_agent_catalog,
    load_model_catalog,
    select_intelligence_model_from_catalog,
    select_worker_agent_from_catalog,
)
from ..domain.models import ToolError
from .models import InstallPaths as _InstallPaths


HOST_HARNESSES = {
    "codex": "codex",
    "claude": "claude-code",
    "opencode": "opencode",
    "cursor": "cursor-cli",
}
DIFFICULTIES = ("routine", "standard", "complex", "critical")
INTELLIGENCE_ROLES = ("designer", "verifier", "reviewer")
CODEX_DEFAULT_MATRIX: Final[Mapping[str, tuple[str, str, str, str]]] = MappingProxyType(
    {
        "designer": ("designer", "gpt-5.6-sol", "max", "gpt-5-6-sol"),
        "worker-routine": ("worker", "gpt-5.6-luna", "max", "codex-gpt-5-6-luna-max"),
        "worker-standard": ("worker", "gpt-5.6-luna", "max", "codex-gpt-5-6-luna-max"),
        "worker-complex": ("worker", "gpt-5.6-luna", "max", "codex-gpt-5-6-luna-max"),
        "worker-critical": ("worker", "gpt-5.6-luna", "max", "codex-gpt-5-6-luna-max"),
        "verifier": ("verifier", "gpt-5.6-sol", "high", "gpt-5-6-sol-high"),
        "reviewer": ("reviewer", "gpt-5.6-sol", "max", "gpt-5-6-sol"),
    }
)
CODEX_FINDER_MATRIX: Final[Mapping[str, tuple[str, str]]] = MappingProxyType(
    {
        "finder": ("gpt-5.3-codex-spark", "xhigh"),
        "fallback_finder": ("gpt-5.4-mini", "xhigh"),
    }
)
_SAFE_VALUE = re.compile(r"^[A-Za-z0-9._:/+-]{1,128}$")
_TOML_MODEL = re.compile(r'(?m)^model\s*=\s*"([A-Za-z0-9._:/+-]{1,128})"\s*$')
_TOML_EFFORT = re.compile(r'(?m)^model_reasoning_effort\s*=\s*"([A-Za-z0-9._+-]{1,64})"\s*$')
_YAML_MODEL = re.compile(r"(?m)^model:\s*['\"]?([A-Za-z0-9._:/+-]{1,128})['\"]?\s*$")
_YAML_EFFORT = re.compile(r"(?m)^(?:reasoning_effort|model_reasoning_effort):\s*['\"]?([A-Za-z0-9._+-]{1,64})['\"]?\s*$")
_EFFORT_SUFFIXES = ("non-reasoning", "minimal", "medium", "xhigh", "high", "low", "max")


@dataclass(frozen=True)
class LocalModel:
    model: str
    reasoning_effort: str | None


@dataclass(frozen=True)
class RoleAssignment:
    """One persisted host-level role configuration."""

    role: str
    agent_name: str
    model: str
    reasoning_effort: str | None
    benchmark_id: str
    index_score: int
    cost_per_task_usd: float | None
    source: str


def _codex_default_delivery_assignments(
    agent_catalog: CodingAgentCatalog,
    model_catalog: ModelCatalog,
) -> dict[str, RoleAssignment]:
    """Resolve the fixed Codex preference matrix against packaged benchmark rows."""

    variants = {variant.variant_id: variant for variant in agent_catalog.variants}
    models = {model.model_id: model for model in model_catalog.models}
    assignments: dict[str, RoleAssignment] = {}
    for agent_name, (role, configured_model, effort, benchmark_id) in CODEX_DEFAULT_MATRIX.items():
        if role == "worker":
            benchmark = variants.get(benchmark_id)
            if benchmark is None:
                raise ToolError("the Codex default Worker benchmark is unavailable")
            index_score = benchmark.index_score
            cost_per_task_usd = benchmark.cost_per_task_usd
        else:
            benchmark = models.get(benchmark_id)
            if benchmark is None:
                raise ToolError("the Codex default intelligence benchmark is unavailable")
            index_score = int(benchmark.intelligence_index)
            cost_per_task_usd = None
        assignments[agent_name] = RoleAssignment(
            role=role,
            agent_name=agent_name,
            model=configured_model,
            reasoning_effort=effort,
            benchmark_id=benchmark_id,
            index_score=index_score,
            cost_per_task_usd=cost_per_task_usd,
            source="codex-default-matrix",
        )
    return assignments


def _codex_finder_assignments() -> dict[str, RoleAssignment]:
    """Return Codex-only read-only finder utilities outside the delivery lifecycle."""

    return {
        agent_name: RoleAssignment(
            role="finder",
            agent_name=agent_name,
            model=model,
            reasoning_effort=effort,
            benchmark_id=f"codex-utility-{agent_name}",
            index_score=0,
            cost_per_task_usd=None,
            source="codex-default-matrix",
        )
        for agent_name, (model, effort) in CODEX_FINDER_MATRIX.items()
    }


def native_role_directory(paths: _InstallPaths, target: str) -> Path:
    if target == "codex":
        return paths.codex_home / "agents"
    if target == "claude":
        return paths.claude_home / "agents"
    if target == "opencode":
        return paths.opencode_config / "agents"
    if target == "cursor":
        return paths.cursor_home / "agents"
    raise ToolError("native role assignments are unavailable for this target")


def _normalized_model(value: str) -> str:
    return value.strip().lower().split("/")[-1].replace(".", "-")


def _read_local_models(directory: Path, excluded_names: Iterable[str]) -> tuple[LocalModel, ...]:
    """Read only public model selectors from bounded native agent files."""

    if not directory.is_dir():
        return ()
    excluded = set(excluded_names)
    values: list[LocalModel] = []
    seen: set[tuple[str, str | None]] = set()
    for path in sorted(directory.iterdir(), key=lambda item: item.name):
        if path.name in excluded or path.is_symlink() or path.suffix not in {".toml", ".md"}:
            continue
        try:
            if not path.is_file() or path.stat().st_size > 262_144:
                continue
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        model_match = _TOML_MODEL.search(text) or _YAML_MODEL.search(text)
        effort_match = _TOML_EFFORT.search(text) or _YAML_EFFORT.search(text)
        if model_match is None:
            continue
        model = model_match.group(1)
        effort = effort_match.group(1) if effort_match is not None else None
        if _SAFE_VALUE.fullmatch(model) is None or (effort is not None and _SAFE_VALUE.fullmatch(effort) is None):
            continue
        key = (model, effort)
        if key not in seen:
            seen.add(key)
            values.append(LocalModel(model, effort))
    return tuple(values)


def _variant_model_ids(variant: CodingAgentRecord, known_ids: set[str]) -> tuple[str, ...]:
    base = variant.model
    effort = variant.reasoning_effort
    suffixes = {
        "none": ("non-reasoning", ""),
        "max": ("", "max"),
        "max-with-fallback": ("",),
    }.get(effort, (effort,))
    prefixes = (base, f"claude-{base}")
    candidates: list[str] = []
    for prefix in prefixes:
        for suffix in suffixes:
            value = prefix if not suffix else f"{prefix}-{suffix}"
            if value in known_ids and value not in candidates:
                candidates.append(value)
        preview = f"{prefix}-preview"
        if preview in known_ids and preview not in candidates:
            candidates.append(preview)
    if candidates:
        return tuple(candidates)
    return tuple(prefix for prefix in prefixes if prefix in known_ids)


def _local_model_ids(
    local: LocalModel,
    models_by_id: dict[str, ModelRecord],
) -> tuple[str, ...]:
    """Map one native selector to its best model-only benchmark row."""

    base = _normalized_model(local.model)
    known_ids = set(models_by_id)
    effort = local.reasoning_effort
    suffixes = {
        "none": ("non-reasoning",),
        "max": ("", "max"),
        "max-with-fallback": ("", "max-with-fallback"),
    }.get(effort, (effort,) if effort is not None else ())
    prefixes = (base, f"claude-{base}")
    if effort is None:
        for prefix in prefixes:
            record = models_by_id.get(prefix)
            if record is None:
                continue
            display = record.model.lower()
            benchmark_is_tiered = any(f"({name})" in display for name in _EFFORT_SUFFIXES)
            selector_encodes_tier = prefix.endswith(tuple(f"-{name}" for name in _EFFORT_SUFFIXES))
            if not benchmark_is_tiered or selector_encodes_tier:
                return (prefix,)
        return ()
    candidates: list[str] = []
    for prefix in prefixes:
        if prefix in known_ids and prefix.endswith(tuple(f"-{suffix}" for suffix in suffixes if suffix)):
            candidates.append(prefix)
        for suffix in suffixes:
            value = prefix if not suffix else f"{prefix}-{suffix}"
            if value in known_ids and value not in candidates:
                candidates.append(value)
    if candidates:
        return tuple(candidates)
    return tuple(prefix for prefix in prefixes if prefix in known_ids)


def _matching_variants(
    variants: Iterable[CodingAgentRecord],
    local_models: tuple[LocalModel, ...],
) -> tuple[CodingAgentRecord, ...]:
    if not local_models:
        return tuple(variants)
    matched: list[CodingAgentRecord] = []
    for variant in variants:
        variant_model = _normalized_model(variant.model)
        if any(
            _normalized_model(local.model) == variant_model
            and local.reasoning_effort == variant.reasoning_effort
            for local in local_models
        ):
            matched.append(variant)
    return tuple(matched)


def _local_selector_for_variant(
    variant: CodingAgentRecord,
    local_models: tuple[LocalModel, ...],
) -> LocalModel | None:
    """Return the exact public selector that established local Agent availability."""

    variant_model = _normalized_model(variant.model)
    return next(
        (
            local
            for local in local_models
            if _normalized_model(local.model) == variant_model
            and local.reasoning_effort == variant.reasoning_effort
        ),
        None,
    )


def select_role_assignments(
    paths: _InstallPaths,
    target: str,
    *,
    excluded_names: Iterable[str] = (),
) -> dict[str, RoleAssignment]:
    """Select once, preferring matching native agent configuration over table fallback."""

    harness = HOST_HARNESSES.get(target)
    if harness is None:
        raise ToolError("native role assignments are unavailable for this target")
    agent_catalog = load_coding_agent_catalog()
    model_catalog = load_model_catalog()
    harness_variants = tuple(variant for variant in agent_catalog.variants if variant.harness == harness)
    local_models = _read_local_models(native_role_directory(paths, target), excluded_names)
    if target == "codex" and not local_models:
        assignments = _codex_default_delivery_assignments(agent_catalog, model_catalog)
        assignments.update(_codex_finder_assignments())
        return assignments
    eligible_variants = _matching_variants(harness_variants, local_models)
    source = "local-config" if local_models and eligible_variants else "catalog-fallback"
    if local_models and not eligible_variants:
        # Unknown local models are not silently treated as benchmarked Agent combinations.
        eligible_variants = ()

    assignments: dict[str, RoleAssignment] = {}
    variant_ids = {variant.variant_id for variant in eligible_variants}
    for difficulty in DIFFICULTIES:
        try:
            variant = select_worker_agent_from_catalog(
                agent_catalog,
                difficulty,
                harness=harness,
                available_variant_ids=variant_ids,
            )
        except ToolError:
            continue
        role = f"worker-{difficulty}"
        local_selector = _local_selector_for_variant(variant, local_models)
        assignments[role] = RoleAssignment(
            role="worker",
            agent_name=role,
            model=local_selector.model if local_selector is not None else variant.model,
            reasoning_effort=(
                local_selector.reasoning_effort
                if local_selector is not None
                else variant.reasoning_effort
            ),
            benchmark_id=variant.variant_id,
            index_score=variant.index_score,
            cost_per_task_usd=variant.cost_per_task_usd,
            source=source,
        )

    model_by_id = {model.model_id: model for model in model_catalog.models}
    configs_by_model_id: dict[str, tuple[str, str | None, str]] = {}
    if local_models:
        for local in local_models:
            for model_id in _local_model_ids(local, model_by_id):
                configs_by_model_id.setdefault(
                    model_id,
                    (local.model, local.reasoning_effort, "local-config"),
                )
    else:
        for variant in eligible_variants:
            for model_id in _variant_model_ids(variant, set(model_by_id)):
                configs_by_model_id.setdefault(
                    model_id,
                    (variant.model, variant.reasoning_effort, "catalog-fallback"),
                )
    available_model_ids = set(configs_by_model_id)
    for role in INTELLIGENCE_ROLES:
        try:
            model: ModelRecord = select_intelligence_model_from_catalog(
                model_catalog,
                role,
                available_model_ids=available_model_ids,
            )
        except ToolError:
            continue
        configured_model, configured_effort, assignment_source = configs_by_model_id[
            model.model_id
        ]
        assignments[role] = RoleAssignment(
            role=role,
            agent_name=role,
            model=configured_model,
            reasoning_effort=configured_effort,
            benchmark_id=model.model_id,
            index_score=int(model.intelligence_index),
            cost_per_task_usd=None,
            source=assignment_source,
        )
    if target == "codex":
        for agent_name, assignment in _codex_default_delivery_assignments(
            agent_catalog,
            model_catalog,
        ).items():
            assignments.setdefault(agent_name, assignment)
        assignments.update(_codex_finder_assignments())
    return assignments
