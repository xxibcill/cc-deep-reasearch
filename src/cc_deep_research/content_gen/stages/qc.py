"""QC stage orchestrator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cc_deep_research.config import Config

from .base import BaseStageOrchestrator

if TYPE_CHECKING:
    from cc_deep_research.content_gen.models import PipelineCandidate, PipelineContext


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

    # ------------------------------------------------------------------
    # Pipeline-context aware run method (P1-T2, P1-T3)
    # ------------------------------------------------------------------

    async def run_with_context(self, ctx: PipelineContext) -> PipelineContext:
        """Run human QC stage (stage 11) with full pipeline context."""
        from cc_deep_research.content_gen.models import PipelineCandidate

        if ctx.current_stage != 11:
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

        agent = self._get_agent("qc")

        for candidate in candidates:
            lane = self._resolve_lane_context(ctx, candidate.idea_id)
            if lane is None or lane.scripting is None:
                continue

            script = ""
            if lane.scripting.qc and lane.scripting.qc.final_script:
                script = lane.scripting.qc.final_script
            elif lane.scripting.tightened and lane.scripting.tightened.content:
                script = lane.scripting.tightened.content
            elif lane.scripting.draft and lane.scripting.draft.content:
                script = lane.scripting.draft.content
            if not script:
                continue

            visual_summary = ""
            if lane.visual_plan:
                beats = getattr(lane.visual_plan, "visual_plan", []) or []
                visual_summary = f"{len(beats)} visual beats planned"
            packaging_summary = ""
            if lane.packaging:
                platforms = getattr(lane.packaging, "platform_packages", []) or []
                packaging_summary = f"{len(platforms)} platform packages"
            research_summary = ""
            if lane.research_pack:
                claims = getattr(lane.research_pack, "claims", []) or []
                research_summary = f"{len(claims)} research claims"
            argument_map_summary = ""
            if lane.argument_map:
                beats = getattr(lane.argument_map, "beat_claim_plan", []) or []
                argument_map_summary = f"{len(beats)} argument map beats"

            qc_gate = await agent.review(
                script=script,
                visual_summary=visual_summary,
                packaging_summary=packaging_summary,
                research_summary=research_summary,
                argument_map_summary=argument_map_summary,
            )
            self._record_lane_completion(ctx, candidate, stage_index=11, stage_field="qc_gate", value=qc_gate)

        return ctx

    def _resolve_lane_context(self, ctx: PipelineContext, idea_id: str) -> Any | None:
        return next((lane_ctx for lane_ctx in ctx.lane_contexts if lane_ctx.idea_id == idea_id), None)

    def _record_lane_completion(
        self,
        ctx: PipelineContext,
        candidate: PipelineCandidate,
        *,
        stage_index: int,
        stage_field: str,
        value: Any,
    ) -> None:
        lane = self._ensure_lane_context(ctx, candidate.idea_id, candidate.role, candidate.status)
        setattr(lane, stage_field, value)
        lane.last_completed_stage = max(lane.last_completed_stage, stage_index)
        self._sync_primary_lane(ctx)

    def _ensure_lane_context(self, ctx: PipelineContext, idea_id: str, role: str, status: str) -> Any:
        from cc_deep_research.content_gen.models import PipelineLaneContext
        lane = self._resolve_lane_context(ctx, idea_id)
        if lane is not None:
            lane.role = role
            lane.status = status
            return lane
        lane = PipelineLaneContext(idea_id=idea_id, role=role, status=status)
        ctx.lane_contexts.append(lane)
        return lane

    def _sync_primary_lane(self, ctx: PipelineContext) -> None:
        primary_lane = next((lane_ctx for lane_ctx in ctx.lane_contexts if lane_ctx.role == "primary"), None) or (
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
