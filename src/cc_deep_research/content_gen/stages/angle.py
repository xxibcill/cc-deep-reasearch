"""Angle generation stage orchestrator."""

from __future__ import annotations

from typing import Any

from cc_deep_research.config import Config

from .base import BaseStageOrchestrator


class AngleStageOrchestrator(BaseStageOrchestrator):
    """Orchestrator for the angle generation stage.

    Responsible for:
    - Generating content angles from scored ideas
    - Selecting the best angle for production
    """

    def __init__(self, config: Config) -> None:
        super().__init__(config)

    def _create_agent(self, name: str) -> object:
        from cc_deep_research.content_gen.agents.thesis import ThesisAgent

        if name in ("angle", "thesis"):
            return ThesisAgent(self._config)
        raise ValueError(f"Unknown agent: {name}")

    async def run_angle(self, item: Any) -> Any:
        """Generate content angles for an idea."""
        from cc_deep_research.content_gen.storage import StrategyStore

        store = StrategyStore()
        strategy = store.load()
        agent = self._get_agent("angle")
        return await agent.generate(item, strategy)

    # ------------------------------------------------------------------
    # Pipeline-context aware run method (P1-T2, P1-T3)
    # ------------------------------------------------------------------

    async def run_with_context(self, ctx: "PipelineContext") -> "PipelineContext":
        """Run angle generation stage (stage 4) with full pipeline context.

        This handles per-lane thesis artifact generation for the generate_angles stage.
        """
        from cc_deep_research.content_gen.models import PipelineCandidate, StrategyMemory

        # Only run for generate_angles stage (index 4)
        if ctx.current_stage != 4:
            return ctx

        candidates = ctx.active_candidates or (
            ctx.scoring.active_candidates if ctx.scoring else []
        )
        if not candidates:
            # Fall back to selected idea
            selected_idea_id = (
                ctx.scoring.selected_idea_id
                if ctx.scoring and ctx.scoring.selected_idea_id
                else ctx.selected_idea_id
            )
            if selected_idea_id:
                candidates = [PipelineCandidate(idea_id=selected_idea_id, role="primary", status="selected")]
            else:
                return ctx

        strategy = ctx.strategy or StrategyMemory()
        agent = self._get_agent("thesis")
        for candidate in candidates:
            # Resolve lane item
            item = None
            if ctx.backlog:
                for i in ctx.backlog.items:
                    if i.idea_id == candidate.idea_id:
                        item = i
                        break
            if item is None:
                continue
            # Build thesis artifact (unified angle + argument design)
            thesis_artifact = await agent.build(item, strategy)
            # Record in lane context
            self._record_lane_completion(ctx, candidate, stage_index=4, stage_field="thesis_artifact", value=thesis_artifact)
        return ctx

    def _record_lane_completion(
        self,
        ctx: "PipelineContext",
        candidate: "PipelineCandidate",
        *,
        stage_index: int,
        stage_field: str,
        value: object,
    ) -> None:
        """Record stage completion in lane context and sync primary lane."""
        # Find or create lane
        lane = None
        for l in ctx.lane_contexts:
            if l.idea_id == candidate.idea_id:
                lane = l
                break
        if lane is None:
            from cc_deep_research.content_gen.models import PipelineLaneContext
            lane = PipelineLaneContext(
                idea_id=candidate.idea_id,
                role=candidate.role,
                status=candidate.status,
            )
            ctx.lane_contexts.append(lane)
        setattr(lane, stage_field, value)
        lane.last_completed_stage = max(lane.last_completed_stage, stage_index)
        # Sync to primary lane
        self._sync_primary_lane(ctx)

    def _sync_primary_lane(self, ctx: "PipelineContext") -> None:
        """Sync primary lane outputs back to context level."""
        primary_lane = next(
            (l for l in ctx.lane_contexts if l.role == "primary"),
            ctx.lane_contexts[0] if ctx.lane_contexts else None,
        )
        if primary_lane is None:
            return
        ctx.thesis_artifact = primary_lane.thesis_artifact
        ctx.angles = primary_lane.angles
