"""Publish stage orchestrator."""

from __future__ import annotations

from typing import Any

from cc_deep_research.config import Config

from .base import BaseStageOrchestrator


class PublishStageOrchestrator(BaseStageOrchestrator):
    """Orchestrator for the publish stage.

    Responsible for:
    - Scheduling and publishing completed content
    """

    def __init__(self, config: Config) -> None:
        super().__init__(config)

    def _create_agent(self, name: str) -> object:
        from cc_deep_research.content_gen.agents.publish import PublishAgent

        if name == "publish":
            return PublishAgent(self._config)
        raise ValueError(f"Unknown agent: {name}")

    async def run_publish(self, packaging: Any, *, idea_id: str = "") -> Any:
        """Schedule content for publishing."""
        agent = self._get_agent("publish")
        return await agent.schedule(packaging, idea_id=idea_id)
