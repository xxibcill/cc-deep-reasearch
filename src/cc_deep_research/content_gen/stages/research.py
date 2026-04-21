"""Research pack stage orchestrator."""

from __future__ import annotations

from typing import Any

from cc_deep_research.config import Config
from cc_deep_research.content_gen.models import ResearchPack

from .base import BaseStageOrchestrator


class ResearchStageOrchestrator(BaseStageOrchestrator):
    """Orchestrator for the research pack stage.

    Responsible for:
    - Building research packs from angles and evidence
    """

    def __init__(self, config: Config) -> None:
        super().__init__(config)

    def _create_agent(self, name: str) -> object:
        from cc_deep_research.content_gen.agents.research_pack import ResearchPackAgent

        if name == "research":
            return ResearchPackAgent(self._config)
        raise ValueError(f"Unknown agent: {name}")

    async def run_research(self, item: Any, angle: Any) -> Any:
        """Build a research pack for an angle."""
        agent = self._get_agent("research")
        return await agent.build(item, angle)
