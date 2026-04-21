"""Strategy loading stage orchestrator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cc_deep_research.config import Config

from .base import BaseStageOrchestrator

if TYPE_CHECKING:
    from cc_deep_research.content_gen.models import PipelineContext


class StrategyStageOrchestrator(BaseStageOrchestrator):
    """Orchestrator for the strategy loading stage (stage 0).

    Responsible for:
    - Loading the strategy memory from storage
    """

    def __init__(self, config: Config) -> None:
        super().__init__(config)

    def _create_agent(self, name: str) -> object:
        raise ValueError(f"StrategyStageOrchestrator does not use agents (got: {name})")

    # ------------------------------------------------------------------
    # Pipeline-context aware run method (P1-T2, P1-T3)
    # ------------------------------------------------------------------

    async def run_with_context(self, ctx: PipelineContext) -> PipelineContext:
        """Run strategy loading stage (stage 0) with full pipeline context.

        Loads strategy from storage into ctx.strategy.
        """
        from cc_deep_research.content_gen.storage import StrategyStore

        if ctx.current_stage != 0:
            return ctx

        store = StrategyStore()
        ctx.strategy = store.load()
        return ctx
