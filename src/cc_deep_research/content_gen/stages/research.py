"""Research pack stage orchestrator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cc_deep_research.config import Config

from .base import BaseStageOrchestrator

if TYPE_CHECKING:
    from cc_deep_research.content_gen.models import PipelineCandidate, PipelineContext


class ResearchStageOrchestrator(BaseStageOrchestrator):
    """Orchestrator for the research pack stage.

    Responsible for:
    - Building research packs from angles and evidence
    """

    def __init__(self, config: Config) -> None:
        super().__init__(config)

    def _create_agent(self, name: str) -> object:
        from cc_deep_research.content_gen.agents.research_pack import ResearchPackAgent

        if name == "research":
            return ResearchPackAgent(self._config)
        raise ValueError(f"Unknown agent: {name}")

    async def run_research(self, item: Any, angle: Any) -> Any:
        """Build a research pack for an angle."""
        agent = self._get_agent("research")
        return await agent.build(item, angle)

    # ------------------------------------------------------------------
    # Pipeline-context aware run method (P1-T2, P1-T3)
    # ------------------------------------------------------------------

    async def run_with_context(self, ctx: PipelineContext) -> PipelineContext:
        """Run research pack stage (stage 5) with full pipeline context."""
        from cc_deep_research.content_gen.models import PipelineCandidate

        if ctx.current_stage != 5:
            return ctx

        if ctx.backlog is None:
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

        agent = self._get_agent("research")

        for candidate in candidates:
            # Resolve lane item and angle
            item = None
            if ctx.backlog:
                for i in ctx.backlog.items:
                    if i.idea_id == candidate.idea_id:
                        item = i
                        break

            angle = self._resolve_lane_angle(ctx, candidate.idea_id)
            if item is None or angle is None:
                continue

            feedback = ""
            research_gaps: list[str] | None = None
            if (
                candidate.role == "primary"
                and ctx.iteration_state
                and ctx.iteration_state.should_rerun_research
            ):
                if ctx.iteration_state.latest_feedback:
                    feedback = ctx.iteration_state.latest_feedback
                if ctx.iteration_state.quality_history:
                    latest_eval = ctx.iteration_state.quality_history[-1]
                    research_gaps = list(latest_eval.research_gaps_identified)
                if ctx.iteration_state.targeted_revision_plan:
                    plan = ctx.iteration_state.targeted_revision_plan
                    targeted_gaps = self._extract_retrieval_gaps(plan)
                    if targeted_gaps:
                        research_gaps = (research_gaps or []) + targeted_gaps

            research_hypotheses = (
                list(ctx.opportunity_brief.research_hypotheses) if ctx.opportunity_brief else None
            )

            # P3-T1: Compute depth routing from scoring outputs
            routing = self._compute_research_depth_routing(ctx, candidate)
            depth_tier = routing.tier

            research_pack = await agent.build(
                item,
                angle,
                feedback=feedback,
                research_gaps=research_gaps,
                research_hypotheses=research_hypotheses,
                depth_tier=depth_tier,
                effort_tier=routing.effort_tier_source,
                expected_upside=routing.expected_upside_source,
                operator_override=routing.operator_override,
                override_reason=routing.override_reason,
            )
            self._record_lane_completion(ctx, candidate, stage_index=5, stage_field="research_pack", value=research_pack)

        return ctx

    def _resolve_lane_angle(self, ctx: PipelineContext, idea_id: str) -> Any | None:
        from cc_deep_research.content_gen.models import AngleOption
        lane = next((lane_ctx for lane_ctx in ctx.lane_contexts if lane_ctx.idea_id == idea_id), None)
        if lane is None:
            return None
        if lane.thesis_artifact is not None:
            th = lane.thesis_artifact
            return AngleOption(
                angle_id=th.angle_id,
                target_audience=th.target_audience,
                viewer_problem=th.viewer_problem,
                core_promise=th.core_promise,
                primary_takeaway=th.primary_takeaway,
                lens=getattr(th, "lens", "") or "",
                format=getattr(th, "format", "") or "",
                tone=getattr(th, "tone", "") or "",
                cta=getattr(th, "cta", "") or "",
                why_this_version_should_exist=getattr(th, "what_this_contributes", ""),
                differentiation_summary=getattr(th, "differentiation_strategy", ""),
                genericity_risks=getattr(th, "genericity_flags", []),
                market_framing_challenged=getattr(th, "audience_belief_to_challenge", ""),
            )
        if lane.angles is None:
            return None
        if lane.angles.selected_angle_id:
            angle = next(
                (opt for opt in lane.angles.options if opt.angle_id == lane.angles.selected_angle_id),
                None,
            )
            if angle is not None:
                return angle
        return lane.angles.options[0] if lane.angles.options else None

    def _compute_research_depth_routing(self, ctx: PipelineContext, candidate: PipelineCandidate) -> Any:
        """Compute research depth routing from scoring outputs."""
        from cc_deep_research.content_gen.models import ResearchDepthRouting, ResearchDepthTier
        routing = ResearchDepthRouting(tier=ResearchDepthTier.STANDARD, effort_tier_source="default")
        if ctx.scoring and candidate.idea_id:
            score = next((s for s in ctx.scoring.scores if s.idea_id == candidate.idea_id), None)
            if score:
                upside = getattr(score, "upside_score", None)
                if upside is not None:
                    routing.expected_upside_source = str(upside)
                    if upside >= 8:
                        routing.tier = ResearchDepthTier.DEEP
                    elif upside <= 3:
                        routing.tier = ResearchDepthTier.QUICK
        return routing

    @staticmethod
    def _extract_retrieval_gaps(plan: Any | None) -> list[str]:
        if plan is None:
            return []
        gaps = list(getattr(plan, "retrieval_gaps", []) or [])
        for action in getattr(plan, "actions", []):
            gaps.extend(getattr(action, "evidence_gaps", []) or [])
        return gaps
