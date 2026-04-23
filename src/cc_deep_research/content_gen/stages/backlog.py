"""Backlog stage orchestrator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cc_deep_research.config import Config
from cc_deep_research.content_gen.models import OpportunityBrief

from .base import BaseStageOrchestrator

if TYPE_CHECKING:
    from cc_deep_research.content_gen.models import PipelineContext


class BacklogStageOrchestrator(BaseStageOrchestrator):
    """Orchestrator for the backlog building stage.

    Responsible for:
    - Building the backlog of content ideas from a theme
    - Scoring ideas for prioritization
    """

    def __init__(self, config: Config) -> None:
        super().__init__(config)

    def _create_agent(self, name: str) -> object:
        from cc_deep_research.content_gen.agents.backlog import BacklogAgent

        if name == "backlog":
            return BacklogAgent(self._config)
        raise ValueError(f"Unknown agent: {name}")

    async def run_backlog(
        self,
        theme: str,
        *,
        count: int = 20,
        opportunity_brief: OpportunityBrief | None = None,
    ) -> Any:
        """Build a backlog of content ideas for a theme."""
        from cc_deep_research.content_gen.storage import StrategyStore

        store = StrategyStore()
        strategy = store.load()
        agent = self._get_agent("backlog")
        return await agent.build_backlog(
            theme, strategy, count=count, opportunity_brief=opportunity_brief
        )

    async def run_scoring(self, items: list) -> Any:
        """Score and prioritize backlog items."""
        from cc_deep_research.content_gen.storage import StrategyStore

        store = StrategyStore()
        strategy = store.load()
        agent = self._get_agent("backlog")
        return await agent.score_ideas(items, strategy)

    # ------------------------------------------------------------------
    # Pipeline-context aware run method (P1-T2, P1-T3)
    # ------------------------------------------------------------------

    async def run_with_context(self, ctx: PipelineContext) -> PipelineContext:
        """Run backlog stages (build_backlog, score_ideas) with full pipeline context.

        This method handles both stage 2 (build_backlog) and stage 3 (score_ideas).
        The stage index is determined from ctx.current_stage.
        """
        from cc_deep_research.content_gen.backlog_service import BacklogService
        from cc_deep_research.content_gen.models import StrategyMemory
        from cc_deep_research.content_gen.storage import StrategyStore

        idx = ctx.current_stage

        if idx == 2:  # build_backlog
            store = StrategyStore()
            strategy = ctx.strategy or store.load()
            agent = self._get_agent("backlog")
            ctx.backlog = await agent.build_backlog(
                ctx.theme,
                strategy,
                opportunity_brief=ctx.opportunity_brief,
            )
            service = BacklogService(self._config)
            ctx.backlog = service.persist_generated(
                ctx.backlog,
                theme=ctx.theme,
                source_pipeline_id=ctx.pipeline_id,
            )
            return ctx

        elif idx == 3:  # score_ideas
            if ctx.backlog is None:
                return ctx
            if not ctx.backlog.items:
                from cc_deep_research.content_gen.models import ScoringOutput
                ctx.scoring = ScoringOutput(is_degraded=True, degradation_reason="backlog has zero items")
                ctx.shortlist = []
                ctx.selected_idea_id = ""
                ctx.selection_reasoning = ""
                ctx.runner_up_idea_ids = []
                ctx.active_candidates = []
                ctx.lane_contexts = []
                return ctx
            agent = self._get_agent("backlog")
            strategy = ctx.strategy or StrategyMemory()
            threshold = self._config.content_gen.scoring_threshold_produce
            content_type_profile = ""
            if ctx.run_constraints and ctx.run_constraints.content_type:
                from cc_deep_research.content_gen.models import get_content_type_profile
                profile = get_content_type_profile(ctx.run_constraints.content_type)
                content_type_profile = profile.profile_key
            min_upside = getattr(self._config.content_gen, "scoring_min_upside_threshold", 2)
            effort_cap = getattr(self._config.content_gen, "scoring_effort_tier_cap", "deep")
            ctx.scoring = await agent.score_ideas(
                ctx.backlog.items,
                strategy,
                threshold=threshold,
                min_upside_threshold=min_upside,
                effort_tier_cap=effort_cap,
                content_type_profile=content_type_profile,
            )
            ctx.shortlist = ctx.scoring.shortlist
            ctx.selected_idea_id = ctx.scoring.selected_idea_id
            ctx.selection_reasoning = ctx.scoring.selection_reasoning
            ctx.runner_up_idea_ids = ctx.scoring.runner_up_idea_ids
            ctx.active_candidates = list(ctx.scoring.active_candidates)
            BacklogService(self._config).apply_scoring(ctx.scoring)
            return ctx

        return ctx
