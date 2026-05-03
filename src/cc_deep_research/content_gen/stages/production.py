"""Production brief stage orchestrator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cc_deep_research.config import Config

from .base import BaseStageOrchestrator

if TYPE_CHECKING:
    from cc_deep_research.content_gen.models import PipelineContext


class ProductionStageOrchestrator(BaseStageOrchestrator):
    """Orchestrator for the production brief stage.

    Responsible for:
    - Creating production briefs from visual plans
    """

    def __init__(self, config: Config) -> None:
        super().__init__(config)

    def _create_agent(self, name: str) -> object:
        from cc_deep_research.content_gen.agents.production import ProductionAgent

        if name == "production":
            return ProductionAgent(self._config)
        raise ValueError(f"Unknown agent: {name}")

    async def run_production(self, visual_plan: Any) -> Any:
        """Create a production brief from a visual plan."""
        agent = self._get_agent("production")
        return await agent.brief(visual_plan)

    # ------------------------------------------------------------------
    # Pipeline-context aware run method (P1-T2, P1-T3)
    # ------------------------------------------------------------------

    async def run_with_context(self, ctx: PipelineContext) -> PipelineContext:
        """Run production brief stage (stage 9) with full pipeline context."""
        from cc_deep_research.content_gen.models import PipelineCandidate

        if ctx.current_stage != 9:
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

        agent = self._get_agent("production")

        for candidate in candidates:
            lane = self._resolve_lane_context(ctx, candidate.idea_id)
            if lane is None:
                continue

            # P5-T2: Use visual_plan or scripting context depending on content type
            if lane.visual_plan is not None:
                production_brief = await agent.brief(lane.visual_plan)
                self._record_lane_completion(ctx, candidate, stage_index=9, stage_field="production_brief", value=production_brief)
            elif lane.scripting is not None:
                # Combined execution brief flow: build from scripting context
                from cc_deep_research.content_gen.models import (
                    VisualProductionExecutionBrief,
                    get_content_type_profile,
                )
                profile = get_content_type_profile(ctx.run_constraints.content_type if ctx.run_constraints else "")
                source = lane.scripting.tightened or lane.scripting.annotated_script or lane.scripting.draft
                if source is None:
                    continue
                execution_brief = VisualProductionExecutionBrief(
                    idea_id=getattr(lane.thesis_artifact, "idea_id", "") if lane.thesis_artifact else "",
                    visual_plan=[],
                    location="",
                    props=[],
                    pickup_lines=[],
                    existing_assets=[],
                    missing_asset_decisions=[],
                    is_degraded=False,
                )
                self._record_lane_completion(ctx, candidate, stage_index=9, stage_field="execution_brief", value=execution_brief)

        return ctx
