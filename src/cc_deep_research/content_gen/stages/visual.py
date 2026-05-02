"""Visual translation stage orchestrator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cc_deep_research.config import Config
from cc_deep_research.content_gen.models import ScriptingContext

from .base import BaseStageOrchestrator

if TYPE_CHECKING:
    from cc_deep_research.content_gen.models import PipelineCandidate, PipelineContext


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

    # ------------------------------------------------------------------
    # Pipeline-context aware run method (P1-T2, P1-T3)
    # ------------------------------------------------------------------

    async def run_with_context(self, ctx: PipelineContext) -> PipelineContext:
        """Run visual translation stage (stage 8) with full pipeline context."""
        from cc_deep_research.content_gen.models import PipelineCandidate

        if ctx.current_stage != 8:
            return ctx

        candidates = ctx.active_candidates or (
            ctx.scoring.active_candidates if ctx.scoring else []
        )
        if not candidates:
            selected_idea_id = (
                ctx.scoring.selected_idea_id
                if ctx.scoring and ctx.scoring.selected_idea_id
                else ctx.selected_idea_id
            )
            if selected_idea_id:
                candidates = [PipelineCandidate(idea_id=selected_idea_id, role="primary", status="selected")]
            else:
                return ctx

        agent = self._get_agent("visual")

        for candidate in candidates:
            lane = self._resolve_lane_context(ctx, candidate.idea_id)
            if lane is None or lane.scripting is None:
                continue
            source = lane.scripting.tightened or lane.scripting.annotated_script or lane.scripting.draft
            structure = lane.scripting.structure
            if source is None or structure is None:
                continue

            idea_id = getattr(lane.thesis_artifact, "idea_id", "") if lane.thesis_artifact else ""
            angle_id = getattr(lane.thesis_artifact, "angle_id", "") if lane.thesis_artifact else ""
            visual_plan = await agent.translate(source, structure, idea_id=idea_id, angle_id=angle_id)
            self._record_lane_completion(ctx, candidate, stage_index=8, stage_field="visual_plan", value=visual_plan)

        return ctx
