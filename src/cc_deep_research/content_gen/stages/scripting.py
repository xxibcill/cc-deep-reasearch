"""Scripting stage orchestrator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cc_deep_research.config import Config
from cc_deep_research.content_gen.claim_trace import build_claim_ledger, format_research_context
from cc_deep_research.content_gen.models import ScriptingContext

from .base import BaseStageOrchestrator

if TYPE_CHECKING:
    from cc_deep_research.content_gen.models import PipelineCandidate, PipelineContext


class ScriptingStageOrchestrator(BaseStageOrchestrator):
    """Orchestrator for the scripting stage.

    Responsible for:
    - Running the multi-step scripting pipeline
    - Iterative refinement of scripts
    """

    def __init__(self, config: Config) -> None:
        super().__init__(config)

    def _create_agent(self, name: str) -> object:
        from cc_deep_research.content_gen.agents.scripting import ScriptingAgent

        if name == "scripting":
            return ScriptingAgent(self._config)
        raise ValueError(f"Unknown agent: {name}")

    async def run_scripting(
        self,
        idea: Any,
        *,
        llm_route: dict[str, str] | None = None,
        constraints: dict[str, Any] | None = None,
    ) -> ScriptingContext:
        """Run the scripting pipeline for an idea."""
        agent = self._get_agent("scripting")
        return await agent.run(idea, llm_route=llm_route, constraints=constraints)

    # ------------------------------------------------------------------
    # Pipeline-context aware run method (P1-T2, P1-T3)
    # ------------------------------------------------------------------

    async def run_with_context(self, ctx: PipelineContext) -> PipelineContext:
        """Run scripting stage (stage 7) with full pipeline context."""
        from cc_deep_research.content_gen.models import PipelineCandidate

        if ctx.current_stage != 7:
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

        agent = self._get_agent("scripting")

        for candidate in candidates:
            lane = self._resolve_lane_context(ctx, candidate.idea_id)
            item = self._resolve_lane_item(ctx, candidate.idea_id)
            if lane is None or lane.argument_map is None:
                continue

            # Build ScriptingContext from lane data
            seeded_ctx = self._build_scripting_context(lane, item, ctx.theme)
            start_step = 5 if seeded_ctx.structure and seeded_ctx.beat_intents else 3
            scripting = await agent.run_from_step(seeded_ctx, start_step)

            # Build claim traceability ledger
            claim_ledger = build_claim_ledger(lane.research_pack, lane.argument_map, scripting)
            scripting.claim_ledger = claim_ledger

            # P4-T1: Capture draft hooks for packaging selection
            draft_hooks = []
            if scripting.hooks:
                draft_hooks = scripting.hooks.hooks[:5]

            self._record_lane_completion(ctx, candidate, stage_index=7, stage_field="scripting", value=scripting)

            # Store early packaging signals on lane
            if lane.thesis_artifact is not None:
                from cc_deep_research.content_gen.models import EarlyPackagingSignals
                th = lane.thesis_artifact
                lane.early_packaging_signals = EarlyPackagingSignals(
                    target_channel=getattr(th, "format", "") or "",
                    content_type=getattr(th, "lens", "") or "",
                    tone_hint=getattr(th, "tone", "") or "",
                    cta_hint=getattr(th, "cta", "") or "",
                )
            elif lane.angles:
                from cc_deep_research.content_gen.models import EarlyPackagingSignals
                angle_opt = self._resolve_lane_angle(ctx, candidate.idea_id)
                if angle_opt:
                    lane.early_packaging_signals = EarlyPackagingSignals(
                        target_channel=getattr(angle_opt, "format", "") or "",
                        content_type=getattr(angle_opt, "lens", "") or "",
                        tone_hint=getattr(angle_opt, "tone", "") or "",
                        cta_hint=getattr(angle_opt, "cta", "") or "",
                    )

            self._record_progressive_checkpoint(lane, "draft", "run_scripting", "Draft QC checkpoint completed.", [])

        return ctx

    def _build_scripting_context(self, lane: Any, item: Any, theme: str) -> ScriptingContext:
        from cc_deep_research.content_gen.models import (
            AngleDefinition,
            CoreInputs,
            ScriptingContext,
        )

        raw_idea = item.idea if item else theme
        research_context = ""
        if lane.scripting and lane.scripting.research_context:
            research_context = lane.scripting.research_context
        elif lane.research_pack:
            research_context = format_research_context(lane.research_pack)

        # P3-T2: Use thesis_artifact fields when available
        if lane.thesis_artifact is not None:
            th = lane.thesis_artifact
            return ScriptingContext(
                raw_idea=raw_idea,
                research_context=research_context,
                tone=getattr(th, "tone", "") or "",
                cta=getattr(th, "cta", "") or "",
                argument_map=lane.argument_map,
                core_inputs=CoreInputs(
                    topic=item.idea if item else raw_idea,
                    outcome=getattr(th, "primary_takeaway", "") or (getattr(item, "problem", "") if item else raw_idea),
                    audience=getattr(th, "target_audience", "") or (getattr(item, "audience", "") if item else ""),
                ),
                angle=AngleDefinition(
                    angle=getattr(th, "core_promise", "") or raw_idea,
                    content_type=getattr(th, "format", "") or getattr(th, "lens", "") or "Insight",
                    core_tension=getattr(th, "viewer_problem", "") or (getattr(item, "problem", "") if item else "") or raw_idea,
                    why_it_works=getattr(th, "what_this_contributes", "") or "",
                ),
                structure=self._seed_structure_from_argument_map(lane.argument_map),
                beat_intents=self._seed_beat_intents_from_argument_map(lane.argument_map),
            )
        else:
            angle = self._resolve_lane_angle_from_lane(lane)
            return ScriptingContext(
                raw_idea=raw_idea,
                research_context=research_context,
                tone=getattr(angle, "tone", "") if angle else "",
                cta=getattr(angle, "cta", "") if angle else "",
                argument_map=lane.argument_map,
                core_inputs=CoreInputs(
                    topic=item.idea if item else raw_idea,
                    outcome=(getattr(angle, "primary_takeaway", "") if angle else "") or (getattr(item, "problem", "") if item else raw_idea),
                    audience=(getattr(angle, "target_audience", "") if angle else "") or (getattr(item, "audience", "") if item else ""),
                ),
                angle=AngleDefinition(
                    angle=(getattr(angle, "core_promise", "") if angle else "") or raw_idea,
                    content_type=(getattr(angle, "format", "") if angle else "") or (getattr(angle, "lens", "") if angle else "") or "Insight",
                    core_tension=(getattr(angle, "viewer_problem", "") if angle else "") or (getattr(item, "problem", "") if item else "") or raw_idea,
                    why_it_works=(getattr(angle, "why_this_version_should_exist", "") if angle else ""),
                ),
                structure=self._seed_structure_from_argument_map(lane.argument_map),
                beat_intents=self._seed_beat_intents_from_argument_map(lane.argument_map),
            )

    def _resolve_lane_angle_from_lane(self, lane: Any) -> Any | None:
        from cc_deep_research.content_gen.models import AngleOption
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
            return next((opt for opt in lane.angles.angle_options if opt.angle_id == lane.angles.selected_angle_id), None)
        return lane.angles.angle_options[0] if lane.angles.angle_options else None

    def _resolve_lane_item(self, ctx: PipelineContext, idea_id: str) -> Any | None:
        if ctx.backlog is None:
            return None
        return next((i for i in ctx.backlog.items if i.idea_id == idea_id), None)

    def _resolve_lane_angle(self, ctx: PipelineContext, idea_id: str) -> Any | None:
        lane = self._resolve_lane_context(ctx, idea_id)
        if lane is None:
            return None
        return self._resolve_lane_angle_from_lane(lane)

    def _resolve_lane_context(self, ctx: PipelineContext, idea_id: str) -> Any | None:
        return next((lane_ctx for lane_ctx in ctx.lane_contexts if lane_ctx.idea_id == idea_id), None)

    def _seed_structure_from_argument_map(self, argument_map: Any | None) -> Any | None:
        if argument_map is None or not argument_map.beat_claim_plan:
            return None
        from cc_deep_research.content_gen.models import ScriptStructure
        return ScriptStructure(
            chosen_structure="Argument map guided flow",
            why_it_fits="Derived directly from the evidence-backed beat claim plan.",
            beat_list=[beat.beat_name for beat in argument_map.beat_claim_plan],
        )

    def _seed_beat_intents_from_argument_map(self, argument_map: Any | None) -> Any | None:
        if argument_map is None or not argument_map.beat_claim_plan:
            return None
        from cc_deep_research.content_gen.models import BeatIntent, BeatIntentMap
        return BeatIntentMap(
            beats=[
                BeatIntent(
                    beat_id=beat.beat_id,
                    beat_name=beat.beat_name,
                    intent=beat.goal,
                    claim_ids=list(beat.claim_ids),
                    proof_anchor_ids=list(beat.proof_anchor_ids),
                    counterargument_ids=list(beat.counterargument_ids),
                    transition_note=beat.transition_note,
                )
                for beat in argument_map.beat_claim_plan
            ]
        )

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

    def _record_progressive_checkpoint(
        self,
        lane: Any,
        checkpoint_name: str,
        stage_name: str,
        summary: str,
        issue_ids: list[str],
    ) -> None:
        from cc_deep_research.content_gen.models import ProgressiveQCCheckpoint
        checkpoint = ProgressiveQCCheckpoint(
            checkpoint_name=checkpoint_name,
            stage_name=stage_name,
            summary=summary,
            issue_ids=issue_ids,
        )
        lane.progressive_qc_checkpoints.append(checkpoint)
