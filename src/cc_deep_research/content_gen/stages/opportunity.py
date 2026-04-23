"""Opportunity planning stage orchestrator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cc_deep_research.config import Config

from .base import BaseStageOrchestrator

if TYPE_CHECKING:
    from cc_deep_research.content_gen.models import PipelineContext


class OpportunityStageOrchestrator(BaseStageOrchestrator):
    """Orchestrator for the opportunity planning stage (stage 1).

    Responsible for:
    - Creating opportunity brief from theme and strategy
    """

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self._agents: dict[str, object] = {}

    def _get_agent(self, name: str) -> object:
        if name not in self._agents:
            self._agents[name] = self._create_agent(name)
        return self._agents[name]

    def _create_agent(self, name: str) -> object:
        from cc_deep_research.content_gen.agents.opportunity import OpportunityPlanningAgent

        if name == "opportunity":
            return OpportunityPlanningAgent(self._config)
        raise ValueError(f"Unknown agent: {name}")

    # ------------------------------------------------------------------
    # Pipeline-context aware run method (P1-T2, P1-T3)
    # ------------------------------------------------------------------

    async def run_with_context(self, ctx: PipelineContext) -> PipelineContext:
        """Run opportunity planning stage (stage 1) with full pipeline context.

        Creates opportunity brief from theme and strategy.
        """
        from cc_deep_research.content_gen.agents.opportunity import (
            format_quality_summary,
            validate_opportunity_brief_quality,
        )
        from cc_deep_research.content_gen.models import StrategyMemory

        if ctx.current_stage != 1:
            return ctx

        agent = self._get_agent("opportunity")
        ctx.opportunity_brief = await agent.plan(ctx.theme, ctx.strategy or StrategyMemory())

        if ctx.opportunity_brief:
            warnings, is_acceptable = validate_opportunity_brief_quality(ctx.opportunity_brief)
            ctx.opportunity_brief._quality_summary = format_quality_summary(warnings)  # type: ignore[attr-defined]
            ctx.opportunity_brief._quality_acceptable = is_acceptable  # type: ignore[attr-defined]

        return ctx
