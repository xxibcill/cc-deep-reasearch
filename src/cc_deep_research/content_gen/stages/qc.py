"""QC stage orchestrator."""

from __future__ import annotations

from typing import Any

from cc_deep_research.config import Config

from .base import BaseStageOrchestrator


class QCStageOrchestrator(BaseStageOrchestrator):
    """Orchestrator for the human QC stage.

    Responsible for:
    - Quality control checks on scripts
    """

    def __init__(self, config: Config) -> None:
        super().__init__(config)

    def _create_agent(self, name: str) -> object:
        from cc_deep_research.content_gen.agents.qc import QCAgent

        if name == "qc":
            return QCAgent(self._config)
        raise ValueError(f"Unknown agent: {name}")

    async def run_qc(
        self,
        *,
        script: str,
        visual_summary: str = "",
        packaging_summary: str = "",
        research_summary: str = "",
        argument_map_summary: str = "",
    ) -> Any:
        """Run quality control checks on a script."""
        agent = self._get_agent("qc")
        return await agent.review(
            script=script,
            visual_summary=visual_summary,
            packaging_summary=packaging_summary,
            research_summary=research_summary,
            argument_map_summary=argument_map_summary,
        )
