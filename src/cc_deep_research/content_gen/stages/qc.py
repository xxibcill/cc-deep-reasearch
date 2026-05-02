"""QC stage orchestrator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cc_deep_research.config import Config

from .base import BaseStageOrchestrator

if TYPE_CHECKING:
    from cc_deep_research.content_gen.models import PipelineContext


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
