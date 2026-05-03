"""Publish stage orchestrator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cc_deep_research.config import Config

from .base import BaseStageOrchestrator

if TYPE_CHECKING:
    from cc_deep_research.content_gen.models import PipelineContext


class PublishStageOrchestrator(BaseStageOrchestrator):
    """Orchestrator for the publish stage.

    Responsible for:
    - Scheduling and publishing completed content
    """

    def __init__(self, config: Config) -> None:
        super().__init__(config)

    def _create_agent(self, name: str) -> object:
        from cc_deep_research.content_gen.agents.publish import PublishAgent

        if name == "publish":
            return PublishAgent(self._config)
        raise ValueError(f"Unknown agent: {name}")

    async def run_publish(self, packaging: Any, *, idea_id: str = "") -> Any:
        """Schedule content for publishing."""
        agent = self._get_agent("publish")
        return await agent.schedule(packaging, idea_id=idea_id)

    # ------------------------------------------------------------------
    # Pipeline-context aware run method (P1-T2, P1-T3)
    # ------------------------------------------------------------------

    async def run_with_context(self, ctx: PipelineContext) -> PipelineContext:
        """Run publish queue stage (stage 12) with full pipeline context."""
        from cc_deep_research.content_gen.models import PipelineCandidate, ReleaseState

        if ctx.current_stage != 12:
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

        agent = self._get_agent("publish")

        for candidate in candidates:
            lane = self._resolve_lane_context(ctx, candidate.idea_id)
            if lane is None or lane.packaging is None or lane.qc_gate is None:
                continue

            qc = lane.qc_gate
            effective_approved = False
            effective_state = qc.release_state

            if qc.release_state == ReleaseState.APPROVED or qc.release_state == ReleaseState.APPROVED_WITH_KNOWN_RISKS:
                effective_approved = True
            elif qc.release_state == ReleaseState.BLOCKED and getattr(qc, "approved_for_publish", False):
                effective_approved = True
                effective_state = ReleaseState.APPROVED

            if not effective_approved:
                continue

            # Check fact risk gate
            fact_risk_blocked = (
                lane.fact_risk_gate is not None
                and lane.fact_risk_gate.decision
                not in (ReleaseState.APPROVED, ReleaseState.APPROVED_WITH_KNOWN_RISKS)
            )
            draft_decision = "publish_now" if not fact_risk_blocked else "hold_for_proof"

            publish_items = await agent.schedule(lane.packaging, idea_id=candidate.idea_id)
            if not isinstance(publish_items, list):
                publish_items = [publish_items] if publish_items else []

            lane.publish_items = list(publish_items)
            if publish_items:
                lane.publish_items = publish_items
                ctx.publish_items = list(publish_items)
                ctx.publish_item = publish_items[0] if publish_items else None

            # Record draft lane decision
            from cc_deep_research.content_gen.models import DraftLaneDecision
            lane.draft_decision = DraftLaneDecision(draft_decision)
            lane.decision_reason = f"Based on QC release state={effective_state.value} and fact_risk={getattr(lane.fact_risk_gate, 'decision', 'N/A')}"

        return ctx
