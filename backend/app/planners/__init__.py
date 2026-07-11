"""The Planner (SRS §14).

Deterministic broad planning: every selectable catalog field, with layers and
connectors derived from the catalog. No LLM is involved — ``/ask``'s single
model call is the Synthesizer's. Import the public surface here:

    from app.planners import Planner, ExecutionPlan, build_planner
"""

from __future__ import annotations

from app.metadata.catalog import Catalog, get_catalog
from app.planners.planner import PLANNER_MODEL, Planner, PlanResult
from app.planners.schema import ExecutionPlan


def build_planner(*, catalog: Catalog | None = None) -> Planner:
    """Wire a :class:`Planner` over the active catalog (SRS §14)."""
    return Planner(catalog=catalog or get_catalog())


__all__ = [
    "PLANNER_MODEL",
    "ExecutionPlan",
    "PlanResult",
    "Planner",
    "build_planner",
]
