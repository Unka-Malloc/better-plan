"""Select the packaged Codex role matrix once at first installation.

Codex is the only host with packaged native roles, and its matrix is a fixed
preset. The benchmark tables are read for the receipt's provenance only:
``index_score`` and ``cost_per_task_usd`` record which published row justified
each pin. They never choose a role, a model, or an effort. Kilo packages no
preset at all and keeps host-owned model selection.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Mapping

from ..domain.model_routing import (
    CodingAgentCatalog,
    ModelCatalog,
    load_coding_agent_catalog,
    load_model_catalog,
)
from ..domain.models import ToolError
from .models import InstallPaths as _InstallPaths


# Installed agent name -> (delivery role, configured model, effort, benchmark row).
# The order is the installed matrix order: designer, worker, hybrid-worker, reviewer.
CODEX_DEFAULT_MATRIX: Final[Mapping[str, tuple[str, str, str, str]]] = MappingProxyType(
    {
        "designer": ("designer", "gpt-6-astra", "max", "gpt-6-astra"),
        "worker": ("worker", "gpt-6-luna", "max", "codex-gpt-6-luna-max"),
        "hybrid-worker": ("worker", "gpt-6-astra", "low", "gpt-6-astra-low"),
        "reviewer": ("reviewer", "gpt-6-astra", "xhigh", "gpt-6-astra-xhigh"),
    }
)


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
    """Resolve the packaged Codex preset against packaged benchmark rows."""

    variants = {variant.variant_id: variant for variant in agent_catalog.variants}
    models = {model.model_id: model for model in model_catalog.models}
    assignments: dict[str, RoleAssignment] = {}
    for agent_name, (role, configured_model, effort, benchmark_id) in CODEX_DEFAULT_MATRIX.items():
        if role == "worker" and benchmark_id in variants:
            # A measured Coding Agent combination also receipts its task cost.
            benchmark = variants[benchmark_id]
            index_score = benchmark.index_score
            cost_per_task_usd = benchmark.cost_per_task_usd
        else:
            benchmark = models.get(benchmark_id)
            if benchmark is None or benchmark.intelligence_index is None:
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


def select_role_assignments(
    paths: _InstallPaths,
    target: str,
) -> dict[str, RoleAssignment]:
    """Return the packaged Codex matrix; local files never influence it.

    The installer checks for same-name local roles and receipts before calling
    this function, so selection here never inspects or adopts local configuration.
    """

    if target != "codex":
        raise ToolError("native role assignments are unavailable for this target")
    return _codex_default_delivery_assignments(load_coding_agent_catalog(), load_model_catalog())
