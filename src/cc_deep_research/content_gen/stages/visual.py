"""Visual translation stage orchestrator."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from cc_deep_research.config import Config
from cc_deep_research.content_gen.models import ScriptingContext

from .base import BaseStageOrchestrator

if TYPE_CHECKING:
    from cc_deep_research.content_gen.models import PipelineContext


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

    async def run_with_context(self, ctx: "PipelineContext") -> "PipelineContext":
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

    def _resolve_lane_context(self, ctx: "PipelineContext", idea_id: str) -> Any | None:
        return next((l for l in ctx.lane_contexts if l.idea_id == idea_id), None)

    def _record_lane_completion(
        self,
        ctx: "PipelineContext",
        candidate: "PipelineCandidate",
        *,
        stage_index: int,
        stage_field: str,
        value: Any,
    ) -> None:
        lane = self._ensure_lane_context(ctx, candidate.idea_id, candidate.role, candidate.status)
        setattr(lane, stage_field, value)
        lane.last_completed_stage = max(lane.last_completed_stage, stage_index)
        self._sync_primary_lane(ctx)

    def _ensure_lane_context(self, ctx: "PipelineContext", idea_id: str, role: str, status: str) -> Any:
        from cc_deep_research.content_gen.models import PipelineLaneContext
        lane = self._resolve_lane_context(ctx, idea_id)
        if lane is not None:
            lane.role = role
            lane.status = status
            return lane
        lane = PipelineLaneContext(idea_id=idea_id, role=role, status=status)
        ctx.lane_contexts.append(lane)
        return lane

    def _sync_primary_lane(self, ctx: "PipelineContext") -> None:
        primary_lane = next((l for l in ctx.lane_contexts if l.role == "primary"), None) or (
            ctx.lane_contexts[0] if ctx.lane_contexts else None
        )
        if primary_lane is None:
            return
        ctx.thesis_artifact = primary_lane.thesis_artifact
        ctx.angles = primary_lane.angles
        ctx.research_pack = primary_lane.research_pack
        ctx.argument_map = primary_lane.argument_map
        ctx.scripting = primary_lane.scripting
        ctx.visual_plan = primary_lane.visual_plan
        ctx.production_brief = primary_lane.production_brief
        ctx.execution_brief = primary_lane.execution_brief
        ctx.packaging = primary_lane.packaging
        ctx.qc_gate = primary_lane.qc_gate
        ctx.fact_risk_gate = primary_lane.fact_risk_gate
        ctx.publish_items = list(primary_lane.publish_items)
        ctx.publish_item = ctx.publish_items[0] if ctx.publish_items else None
