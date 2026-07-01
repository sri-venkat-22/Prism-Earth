"""The Planner (SRS §14).

Natural-language question → catalog-constrained :class:`ExecutionPlan`. The
Planner selects only registered, selectable fields and never fetches data,
answers, or invents fields (SRS §14.12, §14.15). Import the public surface here:

    from app.planners import Planner, ExecutionPlan, build_planner
"""

from __future__ import annotations

from app.llm import LLMClient, build_llm_client
from app.metadata.catalog import Catalog, get_catalog
from app.planners.planner import Planner, PlanResult
from app.planners.schema import ExecutionPlan, LLMPlanProposal


def build_planner(*, llm: LLMClient | None = None, catalog: Catalog | None = None) -> Planner:
    """Wire a :class:`Planner` with the production LLM client (SRS §9, §14)."""
    return Planner(llm=llm or build_llm_client(), catalog=catalog or get_catalog())


__all__ = [
    "ExecutionPlan",
    "LLMPlanProposal",
    "PlanResult",
    "Planner",
    "build_planner",
]
