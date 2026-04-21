"""Production brief stage orchestrator."""

from __future__ import annotations

from typing import Any

from cc_deep_research.config import Config

from .base import BaseStageOrchestrator


class ProductionStageOrchestrator(BaseStageOrchestrator):
    """Orchestrator for the production brief stage.

    Responsible for:
    - Creating production briefs from visual plans
    """

    def __init__(self, config: Config) -> None:
        super().__init__(config)

    def _create_agent(self, name: str) -> object:
        from cc_deep_research.content_gen.agents.production import ProductionAgent

        if name == "production":
            return ProductionAgent(self._config)
        raise ValueError(f"Unknown agent: {name}")

    async def run_production(self, visual_plan: Any) -> Any:
        """Create a production brief from a visual plan."""
        agent = self._get_agent("production")
        return await agent.brief(visual_plan)
