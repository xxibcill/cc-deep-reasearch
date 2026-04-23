"""Argument map stage orchestrator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cc_deep_research.config import Config
from cc_deep_research.content_gen.models import ResearchPack

from .base import BaseStageOrchestrator

if TYPE_CHECKING:
    from cc_deep_research.content_gen.models import PipelineCandidate, PipelineContext


class ArgumentMapStageOrchestrator(BaseStageOrchestrator):
    """Orchestrator for the argument map stage.

    Responsible for:
    - Building argument maps from research packs
    """

    def __init__(self, config: Config) -> None:
        super().__init__(config)

    def _create_agent(self, name: str) -> object:
        from cc_deep_research.content_gen.agents.argument_map import ArgumentMapAgent

        if name == "argument_map":
            return ArgumentMapAgent(self._config)
        raise ValueError(f"Unknown agent: {name}")

    async def run_argument_map(self, item: Any, angle: Any, research_pack: ResearchPack) -> Any:
        """Build an argument map from research."""
        agent = self._get_agent("argument_map")
        return await agent.build(item, angle, research_pack)

    # ------------------------------------------------------------------
    # Pipeline-context aware run method (P1-T2, P1-T3)
    # ------------------------------------------------------------------

    async def run_with_context(self, ctx: PipelineContext) -> PipelineContext:
        """Run argument map stage (stage 6) with full pipeline context."""
        from cc_deep_research.content_gen.models import PipelineCandidate

        if ctx.current_stage != 6:
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

        agent = self._get_agent("argument_map")

        for candidate in candidates:
            lane = self._resolve_lane_context(ctx, candidate.idea_id)
            item = self._resolve_lane_item(ctx, candidate.idea_id)
            if lane is None or item is None:
                continue

            # P3-T2: If thesis_artifact is available, derive argument_map from it
            if lane.thesis_artifact is not None:
                from cc_deep_research.content_gen.models import ArgumentMap
                th = lane.thesis_artifact
                from cc_deep_research.content_gen.models import (
                    ArgumentBeatClaim,
                    ArgumentClaim,
                    ArgumentProofAnchor,
                )

                # Build proof anchors from thesis
                proof_anchors = [
                    ArgumentProofAnchor(proof_id=f"proof_{i}", text=anchor, source_ids=[])
                    for i, anchor in enumerate(th.proof_anchors or [])
                ]

                # Build safe claims from thesis safe_claims
                safe_claims = [
                    ArgumentClaim(claim_id=f"claim_{i}", claim=c, claim_type="main", supporting_proof_ids=[])
                    for i, c in enumerate(th.safe_claims or [])
                ]

                # Build unsafe claims
                unsafe_claims = [
                    ArgumentClaim(claim_id=f"unsafe_{i}", claim=c, claim_type="unsafe", supporting_proof_ids=[])
                    for i, c in enumerate(th.unsafe_claims or [])
                ]

                # Build beat claim plan from thesis beat_plan
                beat_claim_plan = [
                    ArgumentBeatClaim(
                        beat_id=f"beat_{i}",
                        beat_name=beat,
                        goal="",
                        claim_ids=[],
                        proof_anchor_ids=[],
                        counterargument_ids=[],
                    )
                    for i, beat in enumerate(th.beat_plan or [])
                ]

                argument_map = ArgumentMap(
                    idea_id=th.idea_id,
                    angle_id=th.angle_id,
                    thesis=th.thesis,
                    audience_belief_to_challenge=getattr(th, "audience_belief_to_challenge", ""),
                    core_mechanism=getattr(th, "core_mechanism", ""),
                    proof_anchors=proof_anchors,
                    counterarguments=[],
                    safe_claims=safe_claims,
                    unsafe_claims=unsafe_claims,
                    beat_claim_plan=beat_claim_plan,
                    what_this_contributes=getattr(th, "what_this_contributes", ""),
                    genericity_flags=getattr(th, "genericity_flags", []),
                    differentiation_stategy=getattr(th, "differentiation_strategy", ""),
                )
                self._record_lane_completion(ctx, candidate, stage_index=6, stage_field="argument_map", value=argument_map)
                continue

            # Fall back to agent.build() for legacy angle-based flow
            angle = self._resolve_lane_angle(ctx, candidate.idea_id)
            if lane.research_pack is None or angle is None:
                continue

            argument_map = await agent.build(item, angle, lane.research_pack)
            self._record_lane_completion(ctx, candidate, stage_index=6, stage_field="argument_map", value=argument_map)

        return ctx

    def _resolve_lane_item(self, ctx: PipelineContext, idea_id: str) -> Any | None:
        if ctx.backlog is None:
            return None
        return next((i for i in ctx.backlog.items if i.idea_id == idea_id), None)

    def _resolve_lane_angle(self, ctx: PipelineContext, idea_id: str) -> Any | None:
        from cc_deep_research.content_gen.models import AngleOption
        lane = self._resolve_lane_context(ctx, idea_id)
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
                (opt for opt in lane.angles.angle_options if opt.angle_id == lane.angles.selected_angle_id),
                None,
            )
            if angle is not None:
                return angle
        return lane.angles.angle_options[0] if lane.angles.angle_options else None

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
