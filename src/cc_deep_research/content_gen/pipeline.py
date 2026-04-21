"""Content generation pipeline coordinator.

This module provides ContentGenPipeline, which coordinates per-stage
orchestrators to execute the full content generation pipeline.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from cc_deep_research.config import Config
from cc_deep_research.content_gen.models import (
    PIPELINE_STAGE_LABELS,
    PIPELINE_STAGES,
    BriefExecutionGate,
    BriefLifecycleState,
    FactRiskDecision,
    PipelineContext,
    PipelineStageTrace,
    StageTraceMetadata,
    get_phase_for_stage,
    get_phase_policy,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class _StubStageOrchestrator:
    """No-op stage orchestrator for stages 12-13 that have no real implementation."""

    def __init__(self, config: Config) -> None:
        self._config = config

    async def run_with_context(self, ctx: Any) -> Any:
        return ctx


def _resolve_lane_item(ctx: PipelineContext, idea_id: str) -> Any | None:
    """Resolve a backlog item by idea_id."""
    if ctx.backlog is None:
        return None
    return next((item for item in ctx.backlog.items if item.idea_id == idea_id), None)


def _resolve_lane_angle(ctx: PipelineContext, idea_id: str) -> Any | None:
    """Resolve the angle for a lane."""
    lane = next((l for l in ctx.lane_contexts if l.idea_id == idea_id), None)
    if lane is None:
        return None
    # P3-T2: Check thesis_artifact first
    if lane.thesis_artifact is not None:
        from cc_deep_research.content_gen.models import AngleOption
        th = lane.thesis_artifact
        return AngleOption(
            angle_id=th.angle_id,
            target_audience=th.target_audience,
            viewer_problem=th.viewer_problem,
            core_promise=th.core_promise,
            primary_takeaway=th.primary_takeaway,
            lens=th.lens if hasattr(th, "lens") else "",
            format=th.format if hasattr(th, "format") else "",
            tone=th.tone if hasattr(th, "tone") else "",
            cta=th.cta if hasattr(th, "cta") else "",
            why_this_version_should_exist=th.what_this_contributes,
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


def _resolve_lane_context(ctx: PipelineContext, idea_id: str) -> Any | None:
    return next((lane for lane in ctx.lane_contexts if lane.idea_id == idea_id), None)


def _ensure_lane_context(ctx: PipelineContext, idea_id: str, role: str, status: str) -> Any:
    """Ensure a lane context exists for the given idea_id."""
    lane = _resolve_lane_context(ctx, idea_id)
    if lane is not None:
        lane.role = role
        lane.status = status
        return lane
    from cc_deep_research.content_gen.models import PipelineLaneContext
    lane = PipelineLaneContext(idea_id=idea_id, role=role, status=status)
    ctx.lane_contexts.append(lane)
    return lane


def _lane_candidates(ctx: PipelineContext) -> list[Any]:
    """Get lane candidates from context."""
    candidates = ctx.active_candidates or (ctx.scoring.active_candidates if ctx.scoring else [])
    if candidates:
        return candidates
    selected_idea_id = _resolve_selected_idea_id(ctx)
    if not selected_idea_id:
        return []
    from cc_deep_research.content_gen.models import PipelineCandidate
    return [PipelineCandidate(idea_id=selected_idea_id, role="primary", status="selected")]


def _resolve_selected_idea_id(ctx: PipelineContext) -> str:
    if ctx.scoring and ctx.scoring.selected_idea_id:
        return ctx.scoring.selected_idea_id
    return ctx.selected_idea_id


def _record_lane_completion(
    ctx: PipelineContext,
    candidate: Any,
    *,
    stage_index: int,
    stage_field: str,
    value: Any,
) -> None:
    lane = _ensure_lane_context(ctx, candidate.idea_id, candidate.role, candidate.status)
    setattr(lane, stage_field, value)
    lane.last_completed_stage = max(lane.last_completed_stage, stage_index)
    _sync_primary_lane(ctx)


def _sync_primary_lane(ctx: PipelineContext) -> None:
    primary_lane = next(
        (l for l in ctx.lane_contexts if l.role == "primary"),
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


def _use_combined_execution_brief(ctx: PipelineContext) -> bool:
    """Check if the current content type should use combined execution brief."""
    if ctx.run_constraints is None or not ctx.run_constraints.content_type:
        return False
    from cc_deep_research.content_gen.models import get_content_type_profile
    profile = get_content_type_profile(ctx.run_constraints.content_type)
    return profile.use_combined_execution_brief


def _lane_publish_prereqs_met(ctx: PipelineContext) -> bool:
    from cc_deep_research.content_gen.models import ReleaseState
    def _is_approved(lane: Any) -> bool:
        qc = lane.qc_gate
        if qc is None:
            return False
        if qc.release_state in (ReleaseState.APPROVED, ReleaseState.APPROVED_WITH_KNOWN_RISKS):
            return True
        if qc.release_state == ReleaseState.BLOCKED and qc.approved_for_publish:
            return True
        return False
    return any(lane.packaging is not None and _is_approved(lane) for lane in ctx.lane_contexts)


# ---------------------------------------------------------------------------
# Stage orchestrator registry
# ---------------------------------------------------------------------------

_STAGE_ORCHESTRATORS: dict[int, str] = {
    0: "strategy",
    1: "opportunity",
    2: "backlog",
    3: "backlog",
    4: "angle",
    5: "research",
    6: "argument_map",
    7: "scripting",
    8: "visual",
    9: "production",
    10: "packaging",
    11: "qc",
    12: "publish",
    13: "performance",
}


# ---------------------------------------------------------------------------
# Pipeline coordinator
# ---------------------------------------------------------------------------

class ContentGenPipeline:
    """P1-T2/P1-T3: Owns stage sequencing, prerequisites, gate checks, traces.

    Replaces ContentGenOrchestrator._run_stage() for normal pipeline execution.
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._stage_orchestrators: dict[str, Any] = {}

    def _get_stage(self, name: str) -> Any:
        if name not in self._stage_orchestrators:
            self._stage_orchestrators[name] = self._create_stage(name)
        return self._stage_orchestrators[name]

    def _create_stage(self, name: str) -> Any:
        from cc_deep_research.content_gen.stages.angle import AngleStageOrchestrator
        from cc_deep_research.content_gen.stages.argument_map import ArgumentMapStageOrchestrator
        from cc_deep_research.content_gen.stages.backlog import BacklogStageOrchestrator
        from cc_deep_research.content_gen.stages.opportunity import OpportunityStageOrchestrator
        from cc_deep_research.content_gen.stages.packaging import PackagingStageOrchestrator
        from cc_deep_research.content_gen.stages.production import ProductionStageOrchestrator
        from cc_deep_research.content_gen.stages.publish import PublishStageOrchestrator
        from cc_deep_research.content_gen.stages.qc import QCStageOrchestrator
        from cc_deep_research.content_gen.stages.research import ResearchStageOrchestrator
        from cc_deep_research.content_gen.stages.scripting import ScriptingStageOrchestrator
        from cc_deep_research.content_gen.stages.strategy import StrategyStageOrchestrator
        from cc_deep_research.content_gen.stages.visual import VisualStageOrchestrator

        stages: dict[str, type] = {
            "angle": AngleStageOrchestrator,
            "argument_map": ArgumentMapStageOrchestrator,
            "backlog": BacklogStageOrchestrator,
            "opportunity": OpportunityStageOrchestrator,
            "research": ResearchStageOrchestrator,
            "scripting": ScriptingStageOrchestrator,
            "strategy": StrategyStageOrchestrator,
            "visual": VisualStageOrchestrator,
            "production": ProductionStageOrchestrator,
            "packaging": PackagingStageOrchestrator,
            "qc": QCStageOrchestrator,
            "publish": PublishStageOrchestrator,
            # Stages 12-13 are stubs without full implementations;
            # provide no-op stand-ins so the pipeline can run end-to-end in tests.
            "performance": _StubStageOrchestrator,
        }

        orchestrator_class = stages.get(name)
        if orchestrator_class is None:
            raise ValueError(f"Unknown stage: {name}")
        return orchestrator_class(self._config)

    def _check_prerequisites(self, idx: int, ctx: PipelineContext) -> tuple[bool, str]:
        """Check if prerequisites for a stage are met. Returns (met, reason_if_not)."""
        stage = PIPELINE_STAGES[idx]
        lane_candidates = _lane_candidates(ctx)
        if stage == "score_ideas" and ctx.backlog is None:
            return False, "backlog missing"
        if stage == "generate_angles" and ctx.backlog is None:
            return False, "backlog missing"
        if stage == "generate_angles" and not any(
            _resolve_lane_item(ctx, candidate.idea_id) is not None for candidate in lane_candidates
        ):
            return False, "scoring/selected idea missing"
        if stage == "build_research_pack" and ctx.backlog is None:
            return False, "backlog missing"
        if stage == "build_research_pack":
            has_item = any(
                _resolve_lane_item(ctx, candidate.idea_id) is not None for candidate in lane_candidates
            )
            has_angle = any(
                _resolve_lane_angle(ctx, candidate.idea_id) is not None for candidate in lane_candidates
            )
            if has_item and not has_angle:
                return False, "selected angle missing"
            if not has_item:
                return False, "lane backlog/angles missing"
        if stage == "build_argument_map" and not any(
            (lane := _resolve_lane_context(ctx, candidate.idea_id)) is not None
            and lane.research_pack is not None
            and _resolve_lane_item(ctx, candidate.idea_id) is not None
            and _resolve_lane_angle(ctx, candidate.idea_id) is not None
            for candidate in lane_candidates
        ):
            return False, "lane research_pack/backlog/angles missing"
        if stage == "run_scripting" and not any(
            (lane := _resolve_lane_context(ctx, candidate.idea_id)) is not None
            and lane.argument_map is not None
            and lane.fact_risk_gate is not None
            and lane.fact_risk_gate.decision
            in (FactRiskDecision.APPROVED, FactRiskDecision.PROCEED_WITH_UNCERTAINTY)
            and _resolve_lane_item(ctx, candidate.idea_id) is not None
            and _resolve_lane_angle(ctx, candidate.idea_id) is not None
            for candidate in lane_candidates
        ):
            return False, "lane backlog/angles/argument_map missing or fact-risk gate blocked drafting"
        if stage == "visual_translation" and _use_combined_execution_brief(ctx):
            return False, "using combined execution brief"
        if stage == "visual_translation" and not any(
            lane.scripting is not None
            and (lane.scripting.tightened or lane.scripting.annotated_script or lane.scripting.draft)
            is not None
            and lane.scripting.structure is not None
            for lane in ctx.lane_contexts
        ):
            return False, "lane script/structure incomplete"
        if stage == "production_brief":
            if _use_combined_execution_brief(ctx):
                if not any(
                    lane.scripting is not None
                    and (lane.scripting.tightened or lane.scripting.annotated_script or lane.scripting.draft)
                    is not None
                    for lane in ctx.lane_contexts
                ):
                    return False, "lane script missing for combined execution brief"
                return True, ""
            elif not any(lane.visual_plan is not None for lane in ctx.lane_contexts):
                return False, "lane visual_plan missing"
        if stage == "packaging" and not any(
            lane.scripting is not None
            and _resolve_lane_angle(ctx, lane.idea_id) is not None
            and (
                (lane.scripting.qc and lane.scripting.qc.final_script)
                or (lane.scripting.tightened and lane.scripting.tightened.content)
                or (lane.scripting.draft and lane.scripting.draft.content)
            )
            for lane in ctx.lane_contexts
        ):
            return False, "lane scripting/angles missing or script empty"
        if stage == "human_qc" and not any(
            lane.scripting is not None
            and (
                (lane.scripting.qc and lane.scripting.qc.final_script)
                or (lane.scripting.tightened and lane.scripting.tightened.content)
                or (lane.scripting.draft and lane.scripting.draft.content)
            )
            for lane in ctx.lane_contexts
        ):
            return False, "lane script empty"
        if stage == "publish_queue" and not _lane_publish_prereqs_met(ctx):
            return False, "lane packaging empty, qc_gate missing, or not approved"
        return True, ""

    def check_stage_gate(
        self,
        ctx: PipelineContext,
        stage_name: str,
    ) -> tuple[bool, str]:
        """Check if execution can proceed for the given stage."""
        brief_state = BriefLifecycleState.DRAFT
        if ctx.brief_reference is not None:
            brief_state = ctx.brief_reference.lifecycle_state
        else:
            return True, "Gate bypassed: no managed brief reference (legacy/inline run)"

        if ctx.brief_reference.was_generated_in_run:
            return True, "Gate bypassed: brief was generated in this pipeline run"

        if ctx.brief_gate is None:
            ctx.brief_gate = self._initialize_brief_gate(brief_state=brief_state)
            ctx.brief_gate.checked_at_stage = (
                PIPELINE_STAGES.index(stage_name) if stage_name in PIPELINE_STAGES else -1
            )

        if ctx.brief_gate.was_blocked:
            return False, ctx.brief_gate.error_message

        can_proceed, message = ctx.brief_gate.check_gate(brief_state, stage_name)
        ctx.brief_gate.checked_at_stage = (
            PIPELINE_STAGES.index(stage_name) if stage_name in PIPELINE_STAGES else -1
        )

        if not can_proceed:
            ctx.brief_gate.was_blocked = True
            ctx.brief_gate.error_message = message

        return can_proceed, message

    def _initialize_brief_gate(
        self,
        brief_state: BriefLifecycleState = BriefLifecycleState.DRAFT,
    ) -> BriefExecutionGate:
        from cc_deep_research.content_gen.models import BriefExecutionPolicyMode
        policy_mode = getattr(self._config.content_gen, "brief_gate_policy", None) or BriefExecutionPolicyMode.PERMISSIVE
        gate = BriefExecutionGate(policy_mode=policy_mode, brief_state_at_start=brief_state)
        can_proceed, message = gate.check_gate(brief_state, "plan_opportunity")
        if not can_proceed:
            gate.was_blocked = True
            gate.error_message = message
        elif brief_state == BriefLifecycleState.DRAFT:
            gate.warnings.append(f"Pipeline starting with {brief_state.value} brief. Consider approving before running production stages.")
        return gate

    def _summarize_input(self, idx: int, ctx: PipelineContext) -> str:
        stage = PIPELINE_STAGES[idx]
        if stage == "plan_opportunity":
            return f"theme={ctx.theme}"
        if stage == "build_backlog":
            return f"theme={ctx.theme}"
        if stage == "score_ideas":
            if ctx.backlog:
                return f"items={len(ctx.backlog.items)}"
            return "items=0"
        if stage == "generate_angles":
            if ctx.scoring:
                selected_id = _resolve_selected_idea_id(ctx) or "none"
                shortlist = len(ctx.shortlist or ctx.scoring.shortlist)
                active = len(ctx.active_candidates or ctx.scoring.active_candidates)
                return f"selected_idea_id={selected_id}, shortlist={shortlist}, active_candidates={active}"
            return "selected_idea_id=none, shortlist=0, active_candidates=0"
        if stage == "build_research_pack":
            if ctx.angles:
                return f"idea_id={_resolve_selected_idea_id(ctx) or 'none'}"
            return "idea_id=none"
        if stage == "build_argument_map":
            if ctx.research_pack:
                return f"research_claims={len(ctx.research_pack.claims)}, proof_points={len(ctx.research_pack.proof_points)}"
            return "research_pack=empty"
        if stage == "run_scripting":
            if ctx.argument_map:
                return f"beats={len(ctx.argument_map.beat_claim_plan)}, safe_claims={len(ctx.argument_map.safe_claims)}"
            return "argument_map=empty"
        if stage == "visual_translation":
            if ctx.scripting and ctx.scripting.tightened:
                return f"script_words={ctx.scripting.tightened.word_count}"
            return "script=empty"
        if stage == "packaging":
            if ctx.scripting and ctx.scripting.qc:
                return f"script={len(ctx.scripting.qc.final_script)} chars"
            return "script=empty"
        if stage == "human_qc":
            return "ready_for_review"
        if stage == "publish_queue":
            if ctx.qc_gate:
                return f"release_state={ctx.qc_gate.release_state.value}"
            return "release_state=not_reviewed"
        return ""

    def _summarize_output(self, idx: int, ctx: PipelineContext) -> str:
        stage = PIPELINE_STAGES[idx]
        if stage == "load_strategy":
            if ctx.strategy:
                return f"niche={ctx.strategy.niche or 'none'}"
            return "niche=none"
        if stage == "plan_opportunity":
            if ctx.opportunity_brief:
                return f"goal={ctx.opportunity_brief.goal or 'none'}, angles={len(ctx.opportunity_brief.sub_angles)}"
            return "brief=none"
        if stage == "build_backlog":
            if ctx.backlog:
                return f"items={len(ctx.backlog.items)}, rejected={ctx.backlog.rejected_count}"
            return "items=0"
        if stage == "score_ideas":
            if ctx.scoring:
                return f"shortlist={len(ctx.scoring.shortlist)}, active_candidates={len(ctx.active_candidates or ctx.scoring.active_candidates)}, selected={ctx.scoring.selected_idea_id or 'none'}"
            return "no scores"
        if stage == "generate_angles":
            if ctx.angles:
                return f"options={len(ctx.angles.angle_options)}, selected={ctx.angles.selected_angle_id or 'none'}"
            return "options=0"
        if stage == "build_research_pack":
            if ctx.research_pack:
                return f"facts={len(ctx.research_pack.key_facts)}, proof={len(ctx.research_pack.proof_points)}"
            return "empty"
        if stage == "build_argument_map":
            if ctx.argument_map:
                return f"proof={len(ctx.argument_map.proof_anchors)}, claims={len(ctx.argument_map.safe_claims)}, beats={len(ctx.argument_map.beat_claim_plan)}"
            return "empty"
        if stage == "run_scripting":
            if ctx.scripting and ctx.scripting.qc:
                return f"script={ctx.scripting.qc.final_script[:50]}..."
            return "incomplete"
        if stage == "visual_translation":
            if ctx.visual_plan:
                return f"beats={len(ctx.visual_plan.visual_plan)}"
            return "empty"
        if stage == "production_brief":
            if ctx.production_brief:
                return f"location={ctx.production_brief.location or 'none'}"
            return "empty"
        if stage == "packaging":
            if ctx.packaging:
                return f"platforms={len(ctx.packaging.platform_packages)}"
            return "empty"
        if stage == "human_qc":
            if ctx.qc_gate:
                return f"release_state={ctx.qc_gate.release_state.value}"
            return "not_reviewed"
        if stage == "publish_queue":
            if ctx.publish_items:
                first_item = ctx.publish_items[0]
                return f"idea_id={first_item.idea_id}, platforms={len(ctx.publish_items)}"
            if ctx.publish_item:
                return f"idea_id={ctx.publish_item.idea_id}, platform={ctx.publish_item.platform}"
            return "not_created"
        return ""

    def _build_trace_metadata(self, idx: int, ctx: PipelineContext) -> StageTraceMetadata:
        stage = PIPELINE_STAGES[idx]
        meta = StageTraceMetadata()

        if stage == "build_backlog":
            if ctx.backlog:
                meta.is_degraded = ctx.backlog.is_degraded
                meta.degradation_reason = ctx.backlog.degradation_reason
        elif stage == "score_ideas":
            if ctx.scoring:
                meta.selected_idea_id = ctx.scoring.selected_idea_id or ""
                meta.shortlist_count = len(ctx.scoring.shortlist)
                meta.active_candidate_count = len(ctx.active_candidates or ctx.scoring.active_candidates)
                meta.is_degraded = getattr(ctx.scoring, "is_degraded", False)
                meta.degradation_reason = getattr(ctx.scoring, "degradation_reason", "")
        elif stage == "plan_opportunity":
            if ctx.opportunity_brief:
                meta.parse_mode = getattr(ctx.opportunity_brief, "_parse_mode", "") or ""
        elif stage == "generate_angles":
            if ctx.thesis_artifact:
                meta.selected_idea_id = ctx.thesis_artifact.idea_id or _resolve_selected_idea_id(ctx)
                meta.selected_angle_id = ctx.thesis_artifact.angle_id or ""
                meta.option_count = 1
            elif ctx.angles:
                meta.selected_idea_id = ctx.angles.idea_id or _resolve_selected_idea_id(ctx)
                meta.selected_angle_id = ctx.angles.selected_angle_id or ""
                meta.option_count = len(ctx.angles.angle_options)
            meta.active_candidate_count = len(ctx.active_candidates)
        elif stage == "build_research_pack":
            if ctx.research_pack:
                meta.selected_idea_id = ctx.research_pack.idea_id or _resolve_selected_idea_id(ctx)
                meta.selected_angle_id = ctx.research_pack.angle_id or ""
                meta.fact_count = len(ctx.research_pack.key_facts)
                meta.proof_count = len(ctx.research_pack.proof_points)
                meta.cache_reused = "cache" in ctx.research_pack.research_stop_reason.lower()
                meta.is_degraded = ctx.research_pack.is_degraded
                meta.degradation_reason = ctx.research_pack.degradation_reason
        elif stage == "build_argument_map":
            if ctx.argument_map:
                meta.selected_idea_id = ctx.argument_map.idea_id or _resolve_selected_idea_id(ctx)
                meta.selected_angle_id = ctx.argument_map.angle_id or ""
                meta.proof_count = len(ctx.argument_map.proof_anchors)
                meta.claim_count = len(ctx.argument_map.safe_claims)
                meta.unsafe_claim_count = len(ctx.argument_map.unsafe_claims)
                meta.beats_count = len(ctx.argument_map.beat_claim_plan)
            primary_lane = next((l for l in ctx.lane_contexts if l.role == "primary"), None)
            if primary_lane and primary_lane.fact_risk_gate:
                meta.fact_risk_decision = primary_lane.fact_risk_gate.decision.value
                meta.progressive_issue_count = len(primary_lane.progressive_qc_issues)
                meta.checkpoint_count = len(primary_lane.progressive_qc_checkpoints)
        elif stage == "run_scripting":
            if ctx.scripting:
                meta.selected_idea_id = _resolve_selected_idea_id(ctx)
                angle = _resolve_selected_angle(ctx)
                meta.selected_angle_id = getattr(angle, "angle_id", "")
                if ctx.scripting.step_traces:
                    meta.step_count = len(ctx.scripting.step_traces)
                    meta.llm_call_count = sum(len(st.llm_calls) for st in ctx.scripting.step_traces)
                final_script = ""
                if ctx.scripting.qc:
                    final_script = ctx.scripting.qc.final_script
                elif ctx.scripting.tightened:
                    final_script = ctx.scripting.tightened.content
                elif ctx.scripting.draft:
                    final_script = ctx.scripting.draft.content
                if final_script:
                    meta.final_word_count = len(final_script.split())
                if ctx.scripting.argument_map:
                    meta.proof_count = len(ctx.scripting.argument_map.proof_anchors)
                    meta.claim_count = len(ctx.scripting.argument_map.safe_claims)
                    meta.beats_count = len(ctx.scripting.argument_map.beat_claim_plan)
            primary_lane = next((l for l in ctx.lane_contexts if l.role == "primary"), None)
            if primary_lane:
                meta.progressive_issue_count = len(primary_lane.progressive_qc_issues)
                meta.checkpoint_count = len(primary_lane.progressive_qc_checkpoints)
        elif stage == "visual_translation":
            if ctx.visual_plan:
                meta.selected_idea_id = ctx.visual_plan.idea_id or _resolve_selected_idea_id(ctx)
                meta.selected_angle_id = ctx.visual_plan.angle_id or ""
                meta.beats_count = len(ctx.visual_plan.visual_plan)
        elif stage == "packaging":
            if ctx.packaging:
                meta.selected_idea_id = ctx.packaging.idea_id or _resolve_selected_idea_id(ctx)
                meta.platforms_count = len(ctx.packaging.platform_packages)
        elif stage == "production_brief":
            if ctx.production_brief:
                meta.selected_idea_id = ctx.production_brief.idea_id or _resolve_selected_idea_id(ctx)
                meta.is_degraded = ctx.production_brief.is_degraded
                meta.degradation_reason = ctx.production_brief.degradation_reason
            primary_lane = next((l for l in ctx.lane_contexts if l.role == "primary"), None)
            if primary_lane:
                meta.progressive_issue_count = len(primary_lane.progressive_qc_issues)
                meta.checkpoint_count = len(primary_lane.progressive_qc_checkpoints)
        elif stage == "publish_queue":
            if ctx.publish_items:
                meta.selected_idea_id = ctx.publish_items[0].idea_id or _resolve_selected_idea_id(ctx)
                meta.platforms_count = len(ctx.publish_items)
            elif ctx.publish_item:
                meta.selected_idea_id = ctx.publish_item.idea_id or _resolve_selected_idea_id(ctx)
        elif stage == "human_qc" and ctx.qc_gate:
            from cc_deep_research.content_gen.models import ReleaseState
            meta.approved = ctx.qc_gate.release_state in (ReleaseState.APPROVED, ReleaseState.APPROVED_WITH_KNOWN_RISKS)
            primary_lane = next((l for l in ctx.lane_contexts if l.role == "primary"), None)
            if primary_lane:
                meta.progressive_issue_count = len(primary_lane.progressive_qc_issues)
                meta.checkpoint_count = len(primary_lane.progressive_qc_checkpoints)

        return meta

    def _collect_trace_warnings(
        self,
        idx: int,
        ctx: PipelineContext,
        *,
        status: str,
        detail: str = "",
    ) -> list[str]:
        stage = PIPELINE_STAGES[idx]
        warnings: list[str] = []

        if status == "failed" and detail:
            warnings.append(f"Stage failed: {detail}")

        if stage == "plan_opportunity" and ctx.opportunity_brief:
            quality_summary = getattr(ctx.opportunity_brief, "_quality_summary", None)
            is_acceptable = getattr(ctx.opportunity_brief, "_quality_acceptable", True)
            if quality_summary:
                if not is_acceptable:
                    warnings.append(f"Brief quality issues: {quality_summary}")
                else:
                    warnings.append(f"Brief quality: {quality_summary}")
        elif stage == "build_backlog" and ctx.backlog and ctx.backlog.is_degraded:
            warnings.append(f"Backlog degraded: {ctx.backlog.degradation_reason or 'Backlog completed with degraded output.'}")
        elif stage == "score_ideas" and ctx.scoring and getattr(ctx.scoring, "is_degraded", False):
            warnings.append(f"Scoring degraded: {ctx.scoring.degradation_reason or 'Scoring completed with degraded output.'}")
        elif stage == "human_qc" and ctx.qc_gate and ctx.qc_gate.must_fix_items:
            warnings.append(f"Human QC blocked publish until {len(ctx.qc_gate.must_fix_items)} must-fix item(s) are resolved.")
            if ctx.qc_gate.issue_origin_summary:
                warnings.append("Issue origins: " + "; ".join(ctx.qc_gate.issue_origin_summary[:3]))
        elif stage == "build_argument_map" and ctx.argument_map and ctx.argument_map.unsafe_claims:
            warnings.append(f"Argument map flagged {len(ctx.argument_map.unsafe_claims)} unsafe claim(s) to avoid in scripting.")
        elif stage == "build_research_pack" and ctx.research_pack and ctx.research_pack.is_degraded:
            warnings.append(f"Research pack degraded: {ctx.research_pack.degradation_reason or 'Research pack completed with degraded output.'}")
        elif stage == "production_brief" and ctx.production_brief and ctx.production_brief.is_degraded:
            warnings.append(f"Production brief degraded: {ctx.production_brief.degradation_reason or 'Production brief completed with degraded output.'}")
        elif stage == "publish_queue":
            has_items = ctx.publish_items or (ctx.publish_item is not None)
            if not has_items:
                warnings.append("Publish queue produced no items; upstream dependency may be incomplete.")
        elif stage == "performance_analysis" and ctx.performance and ctx.performance.is_degraded:
            warnings.append(f"Performance analysis degraded: {ctx.performance.degradation_reason or 'Performance analysis completed with degraded output.'}")

        return warnings

    def _build_decision_summary(
        self,
        idx: int,
        ctx: PipelineContext,
        *,
        status: str,
        detail: str = "",
    ) -> str:
        if status == "skipped":
            return f"Skipped: {detail}"
        if status == "failed":
            return f"Stage failed: {detail}"

        stage = PIPELINE_STAGES[idx]
        if stage == "score_ideas":
            return ctx.selection_reasoning or (ctx.scoring.selection_reasoning if ctx.scoring else "")
        if stage == "generate_angles":
            if ctx.thesis_artifact and ctx.thesis_artifact.selection_reasoning:
                return ctx.thesis_artifact.selection_reasoning
            if ctx.angles:
                return ctx.angles.selection_reasoning
        if stage == "build_research_pack" and ctx.research_pack:
            return ctx.research_pack.research_stop_reason
        if stage == "build_argument_map" and ctx.argument_map:
            return ctx.argument_map.thesis
        if stage == "human_qc" and ctx.qc_gate:
            from cc_deep_research.content_gen.models import ReleaseState
            rs = ctx.qc_gate.release_state
            if rs == ReleaseState.APPROVED:
                return "Human QC approved the package for publish."
            if rs == ReleaseState.APPROVED_WITH_KNOWN_RISKS:
                reason = ctx.qc_gate.override_reason or "operator accepted known risks"
                return f"Approved with known risks: {reason}"
            if ctx.qc_gate.must_fix_items:
                if ctx.qc_gate.issue_origin_summary:
                    return f"Human QC reduced the final gate to {len(ctx.qc_gate.must_fix_items)} unresolved item(s). First seen earlier in: {'; '.join(ctx.qc_gate.issue_origin_summary[:3])}"
                return f"Human QC requires {len(ctx.qc_gate.must_fix_items)} must-fix item(s) before publish."
            return "Human QC review completed without approval."
        if stage == "run_scripting" and ctx.scripting and ctx.scripting.angle:
            return ctx.scripting.angle.why_it_works
        return ""

    async def run_stage(
        self,
        stage_index: int,
        ctx: PipelineContext,
        progress_callback: Callable[[int, str], None] | None = None,
        stage_completed_callback: Callable[[int, str, str, PipelineContext], None] | None = None,
    ) -> PipelineContext:
        """Run a single pipeline stage with full gate and trace handling.

        P1-T2: Routes to stage orchestrator via run_with_context().
        P1-T3: Owns prerequisites, gate checks, and trace creation.
        """
        stage_name = PIPELINE_STAGES[stage_index]
        label = PIPELINE_STAGE_LABELS.get(stage_name, stage_name)
        phase = get_phase_for_stage(stage_name)
        phase_label = phase.value.replace("_", " ").title()
        policy = get_phase_policy(phase)

        if progress_callback:
            progress_callback(stage_index, label)
        ctx.current_stage = stage_index

        started_at = datetime.now(tz=UTC).isoformat()
        input_summary = self._summarize_input(stage_index, ctx)

        prereqs_met, skip_reason = self._check_prerequisites(stage_index, ctx)
        if not prereqs_met:
            warnings = self._collect_trace_warnings(stage_index, ctx, status="skipped", detail=skip_reason)
            trace = PipelineStageTrace(
                stage_index=stage_index,
                stage_name=stage_name,
                stage_label=label,
                phase=phase,
                phase_label=phase_label,
                policy=policy,
                skip_reason=skip_reason,
                status="skipped",
                started_at=started_at,
                completed_at=datetime.now(tz=UTC).isoformat(),
                input_summary=input_summary,
                output_summary=skip_reason,
                warnings=warnings,
                decision_summary=self._build_decision_summary(stage_index, ctx, status="skipped", detail=skip_reason),
                metadata=self._build_trace_metadata(stage_index, ctx),
            )
            ctx.stage_traces.append(trace)
            if stage_completed_callback:
                stage_completed_callback(stage_index, "skipped", skip_reason, ctx)
            return ctx

        gate_ok, gate_message = self.check_stage_gate(ctx, stage_name)
        if not gate_ok:
            warnings = self._collect_trace_warnings(stage_index, ctx, status="blocked", detail=gate_message)
            trace = PipelineStageTrace(
                stage_index=stage_index,
                stage_name=stage_name,
                stage_label=label,
                phase=phase,
                phase_label=phase_label,
                policy=policy,
                kill_reason=f"Brief gate blocked: {gate_message}",
                status="blocked",
                started_at=started_at,
                completed_at=datetime.now(tz=UTC).isoformat(),
                input_summary=input_summary,
                output_summary=gate_message,
                warnings=warnings,
                decision_summary=f"Brief gate blocked: {gate_message}",
                metadata=self._build_trace_metadata(stage_index, ctx),
            )
            ctx.stage_traces.append(trace)
            if stage_completed_callback:
                stage_completed_callback(stage_index, "blocked", gate_message, ctx)
            raise RuntimeError(gate_message)

        try:
            orchestrator_name = _STAGE_ORCHESTRATORS.get(stage_index)
            if orchestrator_name is None:
                raise RuntimeError(f"No orchestrator registered for stage index {stage_index}")

            stage = self._get_stage(orchestrator_name)
            ctx = await stage.run_with_context(ctx)

            status = "completed"
            output_summary = self._summarize_output(stage_index, ctx)
            warnings = self._collect_trace_warnings(stage_index, ctx, status=status)
            if ctx.brief_gate and ctx.brief_gate.warnings:
                warnings = warnings + [f"Brief gate: {w}" for w in ctx.brief_gate.warnings]
            decision_summary = self._build_decision_summary(stage_index, ctx, status=status)
        except asyncio.CancelledError:
            # Cancellation: record trace before re-raising so trace is preserved
            completed_at = datetime.now(tz=UTC).isoformat()
            started_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            completed_dt = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
            duration_ms = int((completed_dt - started_dt).total_seconds() * 1000)
            trace = PipelineStageTrace(
                stage_index=stage_index,
                stage_name=stage_name,
                stage_label=label,
                phase=phase,
                phase_label=phase_label,
                policy=policy,
                kill_reason="CancelledError: pipeline stage was cancelled",
                status="failed",
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=duration_ms,
                input_summary=input_summary,
                output_summary="CancelledError",
                warnings=["CancelledError: pipeline stage was cancelled"],
                decision_summary="Stage cancelled",
                metadata=self._build_trace_metadata(stage_index, ctx),
            )
            ctx.stage_traces.append(trace)
            if stage_completed_callback:
                stage_completed_callback(stage_index, "failed", "CancelledError", ctx)
            raise
        except Exception as e:
            status = "failed"
            output_summary = str(e)
            warnings = self._collect_trace_warnings(stage_index, ctx, status=status, detail=str(e))
            completed_at = datetime.now(tz=UTC).isoformat()
            started_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            completed_dt = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
            duration_ms = int((completed_dt - started_dt).total_seconds() * 1000)
            trace = PipelineStageTrace(
                stage_index=stage_index,
                stage_name=stage_name,
                stage_label=label,
                phase=phase,
                phase_label=phase_label,
                policy=policy,
                kill_reason=str(e),
                status=status,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=duration_ms,
                input_summary=input_summary,
                output_summary=output_summary,
                warnings=warnings,
                decision_summary=self._build_decision_summary(stage_index, ctx, status=status, detail=str(e)),
                metadata=self._build_trace_metadata(stage_index, ctx),
            )
            ctx.stage_traces.append(trace)
            if stage_completed_callback:
                stage_completed_callback(stage_index, "failed", str(e), ctx)
            raise

        completed_at = datetime.now(tz=UTC).isoformat()
        started_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        completed_dt = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
        duration_ms = int((completed_dt - started_dt).total_seconds() * 1000)
        trace = PipelineStageTrace(
            stage_index=stage_index,
            stage_name=stage_name,
            stage_label=label,
            phase=phase,
            phase_label=phase_label,
            policy=policy,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            input_summary=input_summary,
            output_summary=output_summary,
            warnings=warnings,
            decision_summary=decision_summary,
            metadata=self._build_trace_metadata(stage_index, ctx),
        )
        ctx.stage_traces.append(trace)
        if stage_completed_callback:
            stage_completed_callback(stage_index, "completed", "", ctx)
        return ctx

    # Backward-compatible stage-specific run methods
    async def run_backlog(self, theme: str, *, count: int = 20) -> Any:
        stage = self._get_stage("backlog")
        return await stage.run_backlog(theme, count=count)

    async def run_scoring(self, items: list) -> Any:
        stage = self._get_stage("backlog")
        return await stage.run_scoring(items)

    async def run_angle(self, item: Any) -> Any:
        stage = self._get_stage("angle")
        return await stage.run_angle(item)

    async def run_research(self, item: Any, angle: Any) -> Any:
        stage = self._get_stage("research")
        return await stage.run_research(item, angle)

    async def run_argument_map(self, item: Any, angle: Any, research_pack: Any) -> Any:
        stage = self._get_stage("argument_map")
        return await stage.run_argument_map(item, angle, research_pack)

    async def run_scripting(self, idea: Any, **kwargs: Any) -> Any:
        stage = self._get_stage("scripting")
        return await stage.run_scripting(idea, **kwargs)

    async def run_visual(self, scripting_ctx: Any, **kwargs: Any) -> Any:
        stage = self._get_stage("visual")
        return await stage.run_visual(scripting_ctx, **kwargs)

    async def run_production(self, visual_plan: Any) -> Any:
        stage = self._get_stage("production")
        return await stage.run_production(visual_plan)

    async def run_packaging(self, script: Any, angle: Any, **kwargs: Any) -> Any:
        stage = self._get_stage("packaging")
        return await stage.run_packaging(script, angle, **kwargs)

    async def run_qc(self, script: str, **kwargs: Any) -> Any:
        stage = self._get_stage("qc")
        return await stage.run_qc(script=script, **kwargs)

    async def run_publish(self, packaging: Any, **kwargs: Any) -> Any:
        stage = self._get_stage("publish")
        return await stage.run_publish(packaging, **kwargs)


def _resolve_selected_angle(ctx: PipelineContext) -> Any | None:
    if ctx.angles is None:
        return None
    if ctx.angles.selected_angle_id:
        angle = next(
            (opt for opt in ctx.angles.angle_options if opt.angle_id == ctx.angles.selected_angle_id),
            None,
        )
        if angle is not None:
            return angle
    return ctx.angles.angle_options[0] if ctx.angles.angle_options else None
