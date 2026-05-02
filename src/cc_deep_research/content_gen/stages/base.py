"""Base class for per-stage orchestrators."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cc_deep_research.config import Config

if TYPE_CHECKING:
    from cc_deep_research.content_gen.models import PipelineCandidate, PipelineContext


class BaseStageOrchestrator:
    """Base class for per-stage orchestrators.

    Provides common functionality for stage-specific orchestrators,
    including agent management and configuration access.
    """

    def __init__(self, config: Config) -> None:
        """Initialize the stage orchestrator.

        Args:
            config: Application configuration.
        """
        self._config = config
        self._agents: dict[str, object] = {}

    def _get_agent(self, name: str) -> object:
        """Get or create a cached agent instance."""
        if name not in self._agents:
            self._agents[name] = self._create_agent(name)
        return self._agents[name]

    def _create_agent(self, name: str) -> object:
        """Create a new agent instance. Override in subclasses for custom agent creation."""
        raise NotImplementedError

    async def run_with_context(self, ctx: PipelineContext) -> PipelineContext:
        """Run this stage with full pipeline context.

        Override in subclasses to integrate with the content-gen pipeline.
        The default implementation raises NotImplementedError.

        Args:
            ctx: The current pipeline context.

        Returns:
            Updated pipeline context after running the stage.
        """
        raise NotImplementedError(
            f"Stage {self.__class__.__name__} does not implement run_with_context. "
            "Use stage-specific run methods for standalone operation."
        )

    # ------------------------------------------------------------------
    # Canonical lane helpers (P9-T1)
    # All stage orchestrators delegate to these instead of duplicating logic.
    # ------------------------------------------------------------------

    def _resolve_lane_context(self, ctx: PipelineContext, idea_id: str) -> Any | None:
        """Find a lane context by idea_id."""
        return next((lane for lane in ctx.lane_contexts if lane.idea_id == idea_id), None)

    def _resolve_lane_angle(self, ctx: PipelineContext, idea_id: str) -> Any | None:
        """Resolve the angle for a lane.

        Checks thesis_artifact first (unified P3-T2 flow), then falls back to
        lane.angles. Returns an AngleOption-compatible object or None.
        """
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
            return next(
                (opt for opt in lane.angles.options if opt.angle_id == lane.angles.selected_angle_id),
                None,
            )
        return lane.angles.options[0] if lane.angles.options else None

    def _ensure_lane_context(
        self, ctx: PipelineContext, idea_id: str, role: str, status: str
    ) -> Any:
        """Find or create a lane context for the given idea_id."""
        from cc_deep_research.content_gen.models.pipeline import PipelineLaneContext
        lane = self._resolve_lane_context(ctx, idea_id)
        if lane is not None:
            lane.role = role
            lane.status = status
            return lane
        lane = PipelineLaneContext(idea_id=idea_id, role=role, status=status)
        ctx.lane_contexts.append(lane)
        return lane

    def _record_lane_completion(
        self,
        ctx: PipelineContext,
        candidate: PipelineCandidate,
        *,
        stage_index: int,
        stage_field: str,
        value: Any,
    ) -> None:
        """Record that a stage produced an artifact in the lane context and sync primary."""
        lane = self._ensure_lane_context(
            ctx, candidate.idea_id, candidate.role, candidate.status
        )
        setattr(lane, stage_field, value)
        lane.last_completed_stage = max(lane.last_completed_stage, stage_index)
        self._sync_primary_lane(ctx)

    def _sync_primary_lane(self, ctx: PipelineContext) -> None:
        """Sync primary lane outputs back to top-level context fields."""
        primary_lane = next(
            (lane for lane in ctx.lane_contexts if lane.role == "primary"),
            ctx.lane_contexts[0] if ctx.lane_contexts else None,
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
