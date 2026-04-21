"""Backlog stage orchestrator."""

from __future__ import annotations

from typing import Any

from cc_deep_research.config import Config
from cc_deep_research.content_gen.models import OpportunityBrief

from .base import BaseStageOrchestrator


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
