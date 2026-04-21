"""Angle generation stage orchestrator."""

from __future__ import annotations

from typing import Any

from cc_deep_research.config import Config

from .base import BaseStageOrchestrator


class AngleStageOrchestrator(BaseStageOrchestrator):
    """Orchestrator for the angle generation stage.

    Responsible for:
    - Generating content angles from scored ideas
    - Selecting the best angle for production
    """

    def __init__(self, config: Config) -> None:
        super().__init__(config)

    def _create_agent(self, name: str) -> object:
        from cc_deep_research.content_gen.agents.thesis import ThesisAgent

        if name in ("angle", "thesis"):
            return ThesisAgent(self._config)
        raise ValueError(f"Unknown agent: {name}")

    async def run_angle(self, item: Any) -> Any:
        """Generate content angles for an idea."""
        from cc_deep_research.content_gen.storage import StrategyStore

        store = StrategyStore()
        strategy = store.load()
        agent = self._get_agent("angle")
        return await agent.generate(item, strategy)
