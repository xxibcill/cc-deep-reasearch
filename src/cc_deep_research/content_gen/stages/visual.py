"""Visual translation stage orchestrator."""

from __future__ import annotations

from typing import Any

from cc_deep_research.config import Config
from cc_deep_research.content_gen.models import ScriptingContext

from .base import BaseStageOrchestrator


class VisualStageOrchestrator(BaseStageOrchestrator):
    """Orchestrator for the visual translation stage.

    Responsible for:
    - Translating scripts into visual plans
    """

    def __init__(self, config: Config) -> None:
        super().__init__(config)

    def _create_agent(self, name: str) -> object:
        from cc_deep_research.content_gen.agents.visual import VisualAgent

        if name == "visual":
            return VisualAgent(self._config)
        raise ValueError(f"Unknown agent: {name}")

    async def run_visual(
        self,
        scripting_ctx: ScriptingContext,
        *,
        idea_id: str = "",
        angle_id: str = "",
    ) -> Any:
        """Run visual translation from a completed script."""
        agent = self._get_agent("visual")
        source = scripting_ctx.tightened or scripting_ctx.annotated_script or scripting_ctx.draft
        structure = scripting_ctx.structure
        if source is None or structure is None:
            msg = "Visual translation requires a completed script with structure."
            raise ValueError(msg)
        return await agent.translate(source, structure, idea_id=idea_id, angle_id=angle_id)
