"""Packaging stage orchestrator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cc_deep_research.config import Config

from .base import BaseStageOrchestrator

if TYPE_CHECKING:
    from cc_deep_research.content_gen.models import PipelineCandidate, PipelineContext


class PackagingStageOrchestrator(BaseStageOrchestrator):
    """Orchestrator for the packaging stage.

    Responsible for:
    - Generating platform-specific packaging
    """

    def __init__(self, config: Config) -> None:
        super().__init__(config)

    def _create_agent(self, name: str) -> object:
        from cc_deep_research.content_gen.agents.packaging import PackagingAgent

        if name == "packaging":
            return PackagingAgent(self._config)
        raise ValueError(f"Unknown agent: {name}")

    async def run_packaging(
        self,
        script: Any,
        angle: Any,
        *,
        platforms: list[str] | None = None,
        idea_id: str = "",
        early_packaging_signals: Any | None = None,
        draft_hooks: list[str] | None = None,
    ) -> Any:
        """Generate packaging for a script."""
        from cc_deep_research.content_gen.storage import StrategyStore

        store = StrategyStore()
        strategy = store.load()
        agent = self._get_agent("packaging")
        p = platforms or self._config.content_gen.default_platforms
        return await agent.generate(
            script,
            angle,
            p,
            strategy=strategy,
            idea_id=idea_id,
            early_packaging_signals=early_packaging_signals,
            draft_hooks=draft_hooks,
        )

    # ------------------------------------------------------------------
    # Pipeline-context aware run method (P1-T2, P1-T3)
    # ------------------------------------------------------------------

    async def run_with_context(self, ctx: PipelineContext) -> PipelineContext:
        """Run packaging stage (stage 10) with full pipeline context."""
        from cc_deep_research.content_gen.models import PipelineCandidate, ScriptVersion

        if ctx.current_stage != 10:
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

        agent = self._get_agent("packaging")
        platforms = self._config.content_gen.default_platforms
        from cc_deep_research.content_gen.storage import StrategyStore
        strategy = ctx.strategy or StrategyStore().load()

        for candidate in candidates:
            lane = self._resolve_lane_context(ctx, candidate.idea_id)
            angle = self._resolve_lane_angle(ctx, candidate.idea_id)
            if lane is None or lane.scripting is None or angle is None:
                continue

            source = ""
            if lane.scripting.qc and lane.scripting.qc.final_script:
                source = lane.scripting.qc.final_script
            elif lane.scripting.tightened and lane.scripting.tightened.content:
                source = lane.scripting.tightened.content
            elif lane.scripting.draft and lane.scripting.draft.content:
                source = lane.scripting.draft.content
            if not source:
                continue

            script = ScriptVersion(content=source, word_count=len(source.split()))
            early_signals = getattr(lane, "early_packaging_signals", None)
            draft_hooks = lane.scripting.hooks.hooks[:5] if lane.scripting and lane.scripting.hooks else []

            packaging = await agent.generate(
                script,
                angle,
                platforms,
                strategy=strategy,
                idea_id=candidate.idea_id,
                early_packaging_signals=early_signals,
                draft_hooks=draft_hooks,
            )
            self._record_lane_completion(ctx, candidate, stage_index=10, stage_field="packaging", value=packaging)

        return ctx

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
            return next((opt for opt in lane.angles.options if opt.angle_id == lane.angles.selected_angle_id), None)
        return lane.angles.options[0] if lane.angles.options else None
