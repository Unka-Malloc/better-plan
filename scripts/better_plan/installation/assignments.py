"""Select the packaged Codex role presets when first creating profiles.

Codex is the only host with packaged model pins. Its five pins are a fixed preset.
Pins without a matching benchmark row explicitly record unavailable provenance.
One benchmark table is read, for the receipt's provenance only: the
Intelligence Index row behind each benchmarked pin records ``index_score`` and
``cost_per_task_usd``. Nothing here selects a role, a model, or an effort, and
no second index is consulted. Kilo packages no preset at all and keeps
host-owned model selection.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Mapping

from ..domain.model_routing import ModelCatalog, load_model_catalog
from ..domain.models import ToolError
from .models import InstallPaths as _InstallPaths


# Installed agent name -> (delivery role, configured model, effort, benchmark row). The matrix is
# written and receipted in this order; the packaged role names themselves sort alphabetically.
CODEX_DEFAULT_MATRIX: Final[Mapping[str, tuple[str, str, str, str | None]]] = MappingProxyType(
    {
        "designer": ("designer", "gpt-6-astra", "xhigh", "gpt-6-astra-xhigh"),
        "worker": ("worker", "gpt-6-luna", "max", "gpt-6-luna"),
        "reviewer": ("reviewer", "gpt-6-astra", "xhigh", "gpt-6-astra-xhigh"),
        "verifier": ("verifier", "gpt-6-luna", "max", "gpt-6-luna"),
        "adversary": ("adversary", "gpt-6.1-sol", "high", None),
    }
)


@dataclass(frozen=True)
class RoleAssignment:
    """One persisted host-level role configuration."""

    role: str
    agent_name: str
    model: str | None
    reasoning_effort: str | None
    benchmark_id: str | None
    # The one standard evaluation basis: the model row's Intelligence Index score and its
    # published task cost from the same table.
    index_score: int | None
    cost_per_task_usd: float | None
    source: str


def _codex_default_delivery_assignments(
    model_catalog: ModelCatalog,
) -> dict[str, RoleAssignment]:
    """Resolve the packaged Codex preset against the packaged Intelligence Index rows."""

    models = {model.model_id: model for model in model_catalog.models}
    assignments: dict[str, RoleAssignment] = {}
    for agent_name, (role, configured_model, effort, benchmark_id) in CODEX_DEFAULT_MATRIX.items():
        benchmark = models.get(benchmark_id)
        if benchmark_id is not None and (benchmark is None or benchmark.intelligence_index is None):
            raise ToolError("the Codex default intelligence benchmark is unavailable")
        assignments[agent_name] = RoleAssignment(
            role=role,
            agent_name=agent_name,
            model=configured_model,
            reasoning_effort=effort,
            benchmark_id=benchmark_id,
            index_score=int(benchmark.intelligence_index) if benchmark is not None else None,
            cost_per_task_usd=benchmark.cost_per_task_usd if benchmark is not None else None,
            source="codex-default-matrix" if benchmark is not None else "codex-preset-unbenchmarked",
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
    return _codex_default_delivery_assignments(load_model_catalog())
