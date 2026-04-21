"""Argument map stage orchestrator."""

from __future__ import annotations

from typing import Any

from cc_deep_research.config import Config
from cc_deep_research.content_gen.models import ResearchPack

from .base import BaseStageOrchestrator


class ArgumentMapStageOrchestrator(BaseStageOrchestrator):
    """Orchestrator for the argument map stage.

    Responsible for:
    - Building argument maps from research packs
    """

    def __init__(self, config: Config) -> None:
        super().__init__(config)

    def _create_agent(self, name: str) -> object:
        from cc_deep_research.content_gen.agents.argument_map import ArgumentMapAgent

        if name == "argument_map":
            return ArgumentMapAgent(self._config)
        raise ValueError(f"Unknown agent: {name}")

    async def run_argument_map(self, item: Any, angle: Any, research_pack: ResearchPack) -> Any:
        """Build an argument map from research."""
        agent = self._get_agent("argument_map")
        return await agent.build(item, angle, research_pack)
