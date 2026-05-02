"""Lifecycle policies for pipeline stage execution.

Provides isolated, testable policies for prerequisite checking, gate
checking, and trace construction that are independent of stage dispatch.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cc_deep_research.content_gen.models.brief import BriefExecutionGate
from cc_deep_research.content_gen.models.pipeline import (
    PIPELINE_STAGES,
    PipelineContext,
    StageTraceMetadata,
)
from cc_deep_research.content_gen.models.shared import (
    BriefLifecycleState,
    FactRiskDecision,
)

if TYPE_CHECKING:
    from cc_deep_research.config import Config


# ---------------------------------------------------------------------------
# Helper resolvers (same logic as pipeline.py, needed by prerequisite checks)
# ---------------------------------------------------------------------------


def _resolve_lane_item(ctx: PipelineContext, idea_id: str) -> any | None:
    if ctx.backlog is None:
        return None
    return next((item for item in ctx.backlog.items if item.idea_id == idea_id), None)


def _resolve_lane_angle(ctx: PipelineContext, idea_id: str) -> any | None:
    lane = next((lane_ctx for lane_ctx in ctx.lane_contexts if lane_ctx.idea_id == idea_id), None)
    if lane is None:
        return None
    if lane.thesis_artifact is not None:
        from cc_deep_research.content_gen.models.angle import AngleOption

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


def _resolve_lane_context(ctx: PipelineContext, idea_id: str) -> any | None:
    return next((lane for lane in ctx.lane_contexts if lane.idea_id == idea_id), None)


def _lane_candidates(ctx: PipelineContext) -> list[any]:
    candidates = ctx.active_candidates or (ctx.scoring.active_candidates if ctx.scoring else [])
    if candidates:
        return candidates
    selected_idea_id = _resolve_selected_idea_id(ctx)
    if not selected_idea_id:
        return []
    from cc_deep_research.content_gen.models.backlog import PipelineCandidate

    return [PipelineCandidate(idea_id=selected_idea_id, role="primary", status="selected")]


def _resolve_selected_idea_id(ctx: PipelineContext) -> str:
    if ctx.scoring and ctx.scoring.selected_idea_id:
        return ctx.scoring.selected_idea_id
    return ctx.selected_idea_id


def _use_combined_execution_brief(ctx: PipelineContext) -> bool:
    if ctx.run_constraints is None or not ctx.run_constraints.content_type:
        return False
    from cc_deep_research.content_gen.models.production import get_content_type_profile

    profile = get_content_type_profile(ctx.run_constraints.content_type)
    return profile.use_combined_execution_brief


def _lane_publish_prereqs_met(ctx: PipelineContext) -> bool:
    from cc_deep_research.content_gen.models.shared import ReleaseState

    def _is_approved(lane: any) -> bool:
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
# StagePrerequisitePolicy
# ---------------------------------------------------------------------------


class StagePrerequisitePolicy:
    """Determines whether a stage's prerequisites are met for a given context.

    Isolated from stage dispatch so prerequisite logic can be tested
    without running the full pipeline.
    """

    def check(self, stage_index: int, ctx: PipelineContext) -> tuple[bool, str]:
        """Check if prerequisites for a stage are met. Returns (met, reason_if_not)."""
        stage = PIPELINE_STAGES[stage_index]
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


# ---------------------------------------------------------------------------
# StageGatePolicy
# ---------------------------------------------------------------------------


class StageGatePolicy:
    """Determines whether a stage can execute based on brief gate state.

    Isolated from stage dispatch so gate logic can be tested independently.
    """

    def __init__(self, config: Config) -> None:
        self._config = config

    def check(self, ctx: PipelineContext, stage_name: str) -> tuple[bool, str]:
        """Check if execution can proceed for the given stage."""
        from cc_deep_research.content_gen.models.shared import BriefLifecycleState

        brief_state = BriefLifecycleState.DRAFT
        if ctx.brief_reference is not None:
            brief_state = ctx.brief_reference.lifecycle_state
        else:
            return True, "Gate bypassed: no managed brief reference (legacy/inline run)"

        if ctx.brief_reference.was_generated_in_run:
            return True, "Gate bypassed: brief was generated in this pipeline run"

        if ctx.brief_gate is None:
            ctx.brief_gate = self._initialize_brief_gate(ctx, brief_state=brief_state)
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
        ctx: PipelineContext,
        brief_state: BriefLifecycleState = BriefLifecycleState.DRAFT,
    ) -> BriefExecutionGate:
        from cc_deep_research.content_gen.models.brief import BriefExecutionGate
        from cc_deep_research.content_gen.models.shared import BriefExecutionPolicyMode

        policy_mode = (
            getattr(self._config.content_gen, "brief_gate_policy", None)
            or BriefExecutionPolicyMode.PERMISSIVE
        )
        gate = BriefExecutionGate(policy_mode=policy_mode, brief_state_at_start=brief_state)
        can_proceed, message = gate.check_gate(brief_state, "plan_opportunity")
        if not can_proceed:
            gate.was_blocked = True
            gate.error_message = message
        elif brief_state == BriefLifecycleState.DRAFT:
            gate.warnings.append(
                f"Pipeline starting with {brief_state.value} brief. Consider approving before running production stages."
            )
        return gate


# ---------------------------------------------------------------------------
# StageTracePolicy
# ---------------------------------------------------------------------------


class StageTracePolicy:
    """Builds trace components: input/output summaries, warnings, and metadata.

    Isolated from execution control flow so trace construction can be tested
    with representative stage inputs and outputs without running actual stages.
    """

    def summarize_input(self, stage_index: int, ctx: PipelineContext) -> str:
        """Return a human-readable string describing the stage input."""
        stage = PIPELINE_STAGES[stage_index]
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

    def summarize_output(self, stage_index: int, ctx: PipelineContext) -> str:
        """Return a human-readable string describing the stage output."""
        stage = PIPELINE_STAGES[stage_index]
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

    def build_trace_metadata(self, stage_index: int, ctx: PipelineContext) -> StageTraceMetadata:
        """Build StageTraceMetadata for the given stage and context."""
        stage = PIPELINE_STAGES[stage_index]
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
            primary_lane = next(
                (lane_ctx for lane_ctx in ctx.lane_contexts if lane_ctx.role == "primary"),
                None,
            )
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
            primary_lane = next(
                (lane_ctx for lane_ctx in ctx.lane_contexts if lane_ctx.role == "primary"),
                None,
            )
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
            primary_lane = next(
                (lane_ctx for lane_ctx in ctx.lane_contexts if lane_ctx.role == "primary"),
                None,
            )
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
            from cc_deep_research.content_gen.models.shared import ReleaseState

            meta.approved = ctx.qc_gate.release_state in (
                ReleaseState.APPROVED,
                ReleaseState.APPROVED_WITH_KNOWN_RISKS,
            )
            primary_lane = next(
                (lane_ctx for lane_ctx in ctx.lane_contexts if lane_ctx.role == "primary"),
                None,
            )
            if primary_lane:
                meta.progressive_issue_count = len(primary_lane.progressive_qc_issues)
                meta.checkpoint_count = len(primary_lane.progressive_qc_checkpoints)

        return meta

    def collect_warnings(
        self,
        stage_index: int,
        ctx: PipelineContext,
        *,
        status: str,
        detail: str = "",
    ) -> list[str]:
        """Collect warnings for a stage trace based on status and stage-specific conditions."""
        stage = PIPELINE_STAGES[stage_index]
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
            warnings.append(
                f"Backlog degraded: {ctx.backlog.degradation_reason or 'Backlog completed with degraded output.'}"
            )
        elif stage == "score_ideas" and ctx.scoring and getattr(ctx.scoring, "is_degraded", False):
            warnings.append(
                f"Scoring degraded: {ctx.scoring.degradation_reason or 'Scoring completed with degraded output.'}"
            )
        elif stage == "human_qc" and ctx.qc_gate and ctx.qc_gate.must_fix_items:
            warnings.append(
                f"Human QC blocked publish until {len(ctx.qc_gate.must_fix_items)} must-fix item(s) are resolved."
            )
            if ctx.qc_gate.issue_origin_summary:
                warnings.append("Issue origins: " + "; ".join(ctx.qc_gate.issue_origin_summary[:3]))
        elif stage == "build_argument_map" and ctx.argument_map and ctx.argument_map.unsafe_claims:
            warnings.append(
                f"Argument map flagged {len(ctx.argument_map.unsafe_claims)} unsafe claim(s) to avoid in scripting."
            )
        elif stage == "build_research_pack" and ctx.research_pack and ctx.research_pack.is_degraded:
            warnings.append(
                f"Research pack degraded: {ctx.research_pack.degradation_reason or 'Research pack completed with degraded output.'}"
            )
        elif stage == "production_brief" and ctx.production_brief and ctx.production_brief.is_degraded:
            warnings.append(
                f"Production brief degraded: {ctx.production_brief.degradation_reason or 'Production brief completed with degraded output.'}"
            )
        elif stage == "publish_queue":
            has_items = ctx.publish_items or (ctx.publish_item is not None)
            if not has_items:
                warnings.append("Publish queue produced no items; upstream dependency may be incomplete.")
        elif stage == "performance_analysis" and ctx.performance and ctx.performance.is_degraded:
            warnings.append(
                f"Performance analysis degraded: {ctx.performance.degradation_reason or 'Performance analysis completed with degraded output.'}"
            )

        return warnings

    def build_decision_summary(
        self,
        stage_index: int,
        ctx: PipelineContext,
        *,
        status: str,
        detail: str = "",
    ) -> str:
        """Build a human-readable decision summary string for the stage."""
        if status == "skipped":
            return f"Skipped: {detail}"
        if status == "failed":
            return f"Stage failed: {detail}"

        stage = PIPELINE_STAGES[stage_index]
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
            from cc_deep_research.content_gen.models.shared import ReleaseState

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


def _resolve_selected_angle(ctx: PipelineContext) -> any | None:
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
