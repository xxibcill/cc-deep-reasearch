"""Packaging stage orchestrator."""

from __future__ import annotations

from typing import Any

from cc_deep_research.config import Config

from .base import BaseStageOrchestrator


class PackagingStageOrchestrator(BaseStageOrchestrator):
    """Orchestrator for the packaging stage.

    Responsible for:
    - Generating platform-specific packaging
    """

    def __init__(self, config: Config) -> None:
        super().__init__(config)

    def _create_agent(self, name: str) -> object:
        from cc_deep_research.content_gen.agents.packaging import PackagingAgent

        if name == "packaging":
            return PackagingAgent(self._config)
        raise ValueError(f"Unknown agent: {name}")

    async def run_packaging(
        self,
        script: Any,
        angle: Any,
        *,
        platforms: list[str] | None = None,
        idea_id: str = "",
        early_packaging_signals: Any | None = None,
        draft_hooks: list[str] | None = None,
    ) -> Any:
        """Generate packaging for a script."""
        from cc_deep_research.content_gen.storage import StrategyStore

        store = StrategyStore()
        strategy = store.load()
        agent = self._get_agent("packaging")
        p = platforms or self._config.content_gen.default_platforms
        return await agent.generate(
            script,
            angle,
            p,
            strategy=strategy,
            idea_id=idea_id,
            early_packaging_signals=early_packaging_signals,
            draft_hooks=draft_hooks,
        )
