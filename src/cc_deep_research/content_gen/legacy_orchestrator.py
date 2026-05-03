"""Orchestrator for the content generation workflow.

.. deprecated::
    This module is retained as a backward-compatible import path.
    Normal execution routes through ``ContentGenPipeline`` in ``pipeline.py``.
    ``ContentGenOrchestrator`` methods are preserved as thin compatibility
    wrappers that delegate to ``ContentGenPipeline`` or dedicated services.
    New code should use ``ContentGenPipeline`` directly.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from cc_deep_research.content_gen.models import (
    PIPELINE_STAGE_LABELS,
    PIPELINE_STAGES,
    ArgumentMap,
    BeatIntent,
    BeatIntentMap,
    BriefExecutionGate,
    BriefExecutionPolicyMode,
    BriefLifecycleState,
    ClaimStatus,
    ContentGenRunMetrics,
    ContentTypeProfile,
    FactRiskDecision,
    FactRiskGate,
    IterationState,
    ManagedOpportunityBrief,
    OpportunityBrief,
    PipelineBriefReference,
    PipelineCandidate,
    PipelineContext,
    PipelineLaneContext,
    ProgressiveQCCheckpoint,
    ProgressiveQCIssue,
    QualityEvaluation,
    ReleaseState,
    ResearchDepthRouting,
    ResearchDepthTier,
    ResearchPack,
    RunConstraints,
    ScriptingContext,
    ScriptStructure,
    StrategyMemory,
    TargetedRevisionPlan,
    ThesisArtifact,
)

if TYPE_CHECKING:
    from cc_deep_research.config import Config

logger = logging.getLogger(__name__)

from cc_deep_research.content_gen.brief_run_reference_service import (
    BriefRunReferenceService,
)
from cc_deep_research.content_gen.pipeline import ContentGenPipeline
from cc_deep_research.content_gen.scripting_run_service import ScriptingRunService
from cc_deep_research.content_gen.targeted_revision import (
    apply_targeted_feedback as _apply_targeted_feedback,
)
from cc_deep_research.content_gen.targeted_revision import (
    build_targeted_feedback as _build_targeted_feedback,
)
from cc_deep_research.content_gen.targeted_revision import (
    extract_retrieval_gaps as _extract_retrieval_gaps,
)
from cc_deep_research.content_gen.targeted_revision import (
    should_use_targeted_mode as _should_use_targeted_mode,
)


def _parse_timestamp_with_tz(value: str) -> datetime:
    """Parse an ISO timestamp, ensuring it always has timezone info."""
    if not value:
        return datetime.now(tz=UTC)
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _active_candidate_ids(ctx: PipelineContext) -> list[str]:
    candidate_groups = [
        ctx.active_candidates,
        ctx.scoring.active_candidates if ctx.scoring else [],
    ]
    ordered: list[str] = []
    for group in candidate_groups:
        for candidate in group:
            if candidate.idea_id and candidate.idea_id not in ordered:
                ordered.append(candidate.idea_id)
    return ordered


def _selected_idea_candidates(ctx: PipelineContext) -> list[str]:
    candidates: list[str] = []
    # scoring.selected_idea_id takes precedence over ctx.selected_idea_id
    if ctx.scoring and ctx.scoring.selected_idea_id:
        candidates.append(ctx.scoring.selected_idea_id)
    if ctx.selected_idea_id:
        candidates.append(ctx.selected_idea_id)
    candidates.extend(_active_candidate_ids(ctx))
    if ctx.scoring:
        candidates.extend(ctx.shortlist or ctx.scoring.shortlist)
        candidates.extend(ctx.scoring.produce_now)

    ordered: list[str] = []
    for idea_id in candidates:
        if idea_id and idea_id not in ordered:
            ordered.append(idea_id)
    return ordered


def _resolve_selected_item(ctx: PipelineContext) -> Any | None:
    if ctx.backlog is None:
        return None

    for idea_id in _selected_idea_candidates(ctx):
        item = next(
            (candidate for candidate in ctx.backlog.items if candidate.idea_id == idea_id), None
        )
        if item is not None:
            return item
    return None


def _resolve_selected_idea_id(ctx: PipelineContext) -> str:
    item = _resolve_selected_item(ctx)
    if item is not None:
        return item.idea_id
    candidates = _selected_idea_candidates(ctx)
    return candidates[0] if candidates else ""


def _resolve_selected_angle(ctx: PipelineContext) -> Any | None:
    if ctx.angles is None:
        return None
    if ctx.angles.selected_angle_id:
        angle = next(
            (
                option
                for option in ctx.angles.options
                if option.angle_id == ctx.angles.selected_angle_id
            ),
            None,
        )
        if angle is not None:
            return angle
    return ctx.angles.options[0] if ctx.angles.options else None


def _lane_candidates(ctx: PipelineContext) -> list[PipelineCandidate]:
    candidates = ctx.active_candidates or (ctx.scoring.active_candidates if ctx.scoring else [])
    if candidates:
        return candidates

    selected_idea_id = _resolve_selected_idea_id(ctx)
    if not selected_idea_id:
        return []
    return [PipelineCandidate(idea_id=selected_idea_id, role="primary", status="selected")]


def _resolve_lane_context(ctx: PipelineContext, idea_id: str) -> PipelineLaneContext | None:
    return next((lane for lane in ctx.lane_contexts if lane.idea_id == idea_id), None)


def _ensure_lane_context(ctx: PipelineContext, candidate: PipelineCandidate) -> PipelineLaneContext:
    lane = _resolve_lane_context(ctx, candidate.idea_id)
    if lane is not None:
        lane.role = candidate.role
        lane.status = candidate.status
        return lane

    lane = PipelineLaneContext(
        idea_id=candidate.idea_id,
        role=candidate.role,
        status=candidate.status,
    )
    ctx.lane_contexts.append(lane)
    return lane


def _resolve_lane_item(ctx: PipelineContext, idea_id: str) -> Any | None:
    if ctx.backlog is None:
        return None
    return next((item for item in ctx.backlog.items if item.idea_id == idea_id), None)


def _resolve_lane_angle(ctx: PipelineContext, idea_id: str) -> Any | None:
    """Resolve the angle for a lane.

    P3-T2: First checks if thesis_artifact is available (new flow),
    and constructs an AngleOption-compatible object from it.
    Falls back to legacy lane.angles for backward compatibility.
    """
    lane = _resolve_lane_context(ctx, idea_id)
    if lane is None:
        return None

    # P3-T2: Check thesis_artifact first (new unified flow)
    if lane.thesis_artifact is not None:
        thesis = lane.thesis_artifact
        # Construct an AngleOption-compatible object from thesis_artifact
        return _thesis_to_angle_option_like(thesis)

    # Backward compatibility: use legacy lane.angles
    if lane.angles is None:
        return None
    if lane.angles.selected_angle_id:
        angle = next(
            (
                option
                for option in lane.angles.options
                if option.angle_id == lane.angles.selected_angle_id
            ),
            None,
        )
        if angle is not None:
            return angle
    return lane.angles.options[0] if lane.angles.options else None


def _thesis_to_angle_option_like(thesis: ThesisArtifact) -> Any:
    """Convert a ThesisArtifact to an AngleOption-compatible object for backward compatibility.

    P3-T2: The ThesisArtifact contains all angle fields directly, so we construct
    an object that exposes the same interface that downstream code expects.
    """
    from cc_deep_research.content_gen.models import AngleOption

    return AngleOption(
        angle_id=thesis.angle_id,
        target_audience=thesis.target_audience,
        viewer_problem=thesis.viewer_problem,
        core_promise=thesis.core_promise,
        primary_takeaway=thesis.primary_takeaway,
        lens=thesis.lens,
        format=thesis.format,
        tone=thesis.tone,
        cta=thesis.cta,
        why_this_version_should_exist=thesis.what_this_contributes,
        differentiation_summary=thesis.differentiation_strategy,
        genericity_risks=thesis.genericity_flags,
        market_framing_challenged=thesis.audience_belief_to_challenge,
    )


# P5-T2: Helper to get content type profile
def _get_content_type_profile(ctx: PipelineContext) -> ContentTypeProfile:
    """Get the content type profile for the current run."""
    from cc_deep_research.content_gen.models import get_content_type_profile

    content_type = ctx.run_constraints.content_type if ctx.run_constraints else ""
    return get_content_type_profile(content_type)


def _use_combined_execution_brief(ctx: PipelineContext) -> bool:
    """Check if the current content type should use combined execution brief."""
    profile = _get_content_type_profile(ctx)
    return profile.use_combined_execution_brief


def _update_candidate_status(ctx: PipelineContext, idea_id: str, status: str) -> None:
    if not idea_id:
        return

    def _update(candidates: list[PipelineCandidate]) -> list[PipelineCandidate]:
        updated: list[PipelineCandidate] = []
        for candidate in candidates:
            if candidate.idea_id == idea_id:
                updated.append(candidate.model_copy(update={"status": status}))
            else:
                updated.append(candidate)
        return updated

    if ctx.active_candidates:
        ctx.active_candidates = _update(ctx.active_candidates)
    if ctx.scoring and ctx.scoring.active_candidates:
        ctx.scoring.active_candidates = _update(ctx.scoring.active_candidates)
    lane = _resolve_lane_context(ctx, idea_id)
    if lane is not None:
        lane.status = status


def _sync_primary_lane(ctx: PipelineContext) -> None:
    primary_lane = next(
        (lane for lane in ctx.lane_contexts if lane.role == "primary"),
        ctx.lane_contexts[0] if ctx.lane_contexts else None,
    )
    if primary_lane is None:
        return

    # P3-T2: Sync thesis_artifact from primary lane
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


def _record_lane_completion(
    ctx: PipelineContext,
    candidate: PipelineCandidate,
    *,
    stage_index: int,
    stage_field: str,
    value: Any,
) -> None:
    lane = _ensure_lane_context(ctx, candidate)
    setattr(lane, stage_field, value)
    lane.last_completed_stage = max(lane.last_completed_stage, stage_index)
    _sync_primary_lane(ctx)


def _lane_publish_prereqs_met(ctx: PipelineContext) -> bool:
    # P6-T2: Check release_state for publish readiness
    # P6-T2 backward compat: also accept approved_for_publish=True when release_state is BLOCKED
    from cc_deep_research.content_gen.models import ReleaseState

    def _is_approved(lane: PipelineLaneContext) -> bool:
        qc = lane.qc_gate
        if qc is None:
            return False
        if qc.release_state in (ReleaseState.APPROVED, ReleaseState.APPROVED_WITH_KNOWN_RISKS):
            return True
        # Backward compatibility: treat approved_for_publish=True with BLOCKED as APPROVED
        if qc.release_state == ReleaseState.BLOCKED and qc.approved_for_publish:
            return True
        return False

    return any(lane.packaging is not None and _is_approved(lane) for lane in ctx.lane_contexts)


def _seed_structure_from_argument_map(argument_map: ArgumentMap | None) -> ScriptStructure | None:
    if argument_map is None or not argument_map.beat_claim_plan:
        return None
    return ScriptStructure(
        chosen_structure="Argument map guided flow",
        why_it_fits="Derived directly from the evidence-backed beat claim plan.",
        beat_list=[beat.beat_name for beat in argument_map.beat_claim_plan],
    )


def _seed_beat_intents_from_argument_map(argument_map: ArgumentMap | None) -> BeatIntentMap | None:
    if argument_map is None or not argument_map.beat_claim_plan:
        return None
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


def _compute_research_depth_routing(
    ctx: PipelineContext,
    candidate: PipelineCandidate,
    config: Any,
) -> ResearchDepthRouting:
    """P3-T1: Compute research depth routing from scoring outputs and config.

    Routes research time and validation depth to expected upside and claim risk
    instead of using one default level. Preserves operator override path.
    """
    effort_tier_str = ""
    expected_upside = 0
    idea_score: Any = None

    # Look up the score for this candidate from scoring output
    if ctx.scoring:
        for score in ctx.scoring.scores:
            if score.idea_id == candidate.idea_id:
                idea_score = score
                break

    if idea_score:
        effort_tier_str = (
            idea_score.effort_tier.value
            if hasattr(idea_score.effort_tier, "value")
            else str(idea_score.effort_tier)
        )
        expected_upside = idea_score.expected_upside

    # Map effort tier to depth tier using config
    effort_to_depth = getattr(config.content_gen, "research_depth_by_effort_tier", None)
    if effort_to_depth is None:
        effort_to_depth = {"quick": "light", "standard": "standard", "deep": "deep"}

    base_tier_str = effort_to_depth.get(effort_tier_str, "standard")

    # Check if upside bumps tier to deep
    upside_deep_threshold = getattr(config.content_gen, "research_upside_deep_threshold", 4)
    if expected_upside >= upside_deep_threshold:
        base_tier_str = "deep"

    # Check if effort tier itself mandates deep
    effort_deep_threshold = getattr(config.content_gen, "research_effort_deep_threshold", "deep")
    if effort_tier_str == effort_deep_threshold or effort_tier_str == "deep":
        base_tier_str = "deep"

    if ctx.run_constraints and ctx.run_constraints.research_depth_override:
        try:
            override_tier = ResearchDepthTier(ctx.run_constraints.research_depth_override)
            return ResearchDepthRouting(
                tier=override_tier,
                routing_basis="operator_override",
                effort_tier_source=effort_tier_str,
                expected_upside_source=expected_upside,
                operator_override=True,
                override_reason=ctx.run_constraints.research_override_reason,
            )
        except ValueError:
            pass

    try:
        tier = ResearchDepthTier(base_tier_str)
    except ValueError:
        tier = ResearchDepthTier.STANDARD

    routing = ResearchDepthRouting(
        tier=tier,
        routing_basis="effort_upside_routing",
        effort_tier_source=effort_tier_str,
        expected_upside_source=expected_upside,
    )

    return routing


def _upsert_progressive_issue(
    lane: PipelineLaneContext,
    *,
    category: Literal["fact", "brand", "packaging", "execution"],
    summary: str,
    severity: Literal["low", "medium", "high"],
    first_seen_stage: str,
) -> str:
    for issue in lane.progressive_qc_issues:
        if issue.summary == summary and issue.category == category:
            return issue.issue_id

    issue = ProgressiveQCIssue(
        category=category,
        summary=summary,
        severity=severity,
        first_seen_stage=first_seen_stage,
    )
    lane.progressive_qc_issues.append(issue)
    return issue.issue_id


def _record_progressive_checkpoint(
    lane: PipelineLaneContext,
    *,
    checkpoint_name: Literal["research", "draft", "execution"],
    stage_name: str,
    summary: str,
    issue_ids: list[str],
) -> None:
    status: Literal["pass", "warning", "blocked"] = "pass"
    unresolved = [
        issue
        for issue in lane.progressive_qc_issues
        if issue.issue_id in issue_ids and not issue.is_resolved
    ]
    if any(issue.severity == "high" for issue in unresolved):
        status = "blocked"
    elif unresolved:
        status = "warning"

    lane.progressive_qc_checkpoints.append(
        ProgressiveQCCheckpoint(
            checkpoint_name=checkpoint_name,
            stage_name=stage_name,
            status=status,
            summary=summary,
            issue_ids=issue_ids,
            created_at=datetime.now(tz=UTC).isoformat(),
        )
    )


def _evaluate_fact_risk_gate(
    lane: PipelineLaneContext,
    *,
    item: Any,
    angle: Any,
    strategy: StrategyMemory | None,
) -> FactRiskGate:
    argument_map = lane.argument_map
    research_pack = lane.research_pack

    gate = FactRiskGate(
        idea_id=lane.idea_id,
        angle_id=getattr(angle, "angle_id", ""),
        thesis=argument_map.thesis if argument_map else "",
    )
    if argument_map is None:
        gate.decision = FactRiskDecision.HOLD
        gate.decision_reason = "Argument map missing; cannot validate claims before drafting."
        gate.hold_resolution_requirements.append(
            "Create a thesis artifact with claim-level support."
        )
        return gate

    uncertainty_claims = {
        flag.claim.strip()
        for flag in (research_pack.uncertainty_flags if research_pack else [])
        if flag.claim.strip()
    }
    proof_ids = {proof.proof_id for proof in argument_map.proof_anchors}

    for claim in argument_map.safe_claims:
        status = "supported"
        if not claim.supporting_proof_ids:
            status = "missing"
            gate.missing_claims.append(claim.claim_id or claim.claim)
            gate.hold_resolution_requirements.append(
                f"Add direct evidence for claim '{claim.claim[:80]}'"
            )
        elif any(proof_id not in proof_ids for proof_id in claim.supporting_proof_ids):
            status = "weak"
            gate.weak_claims.append(claim.claim_id or claim.claim)
            gate.hold_resolution_requirements.append(
                f"Repair proof linkage for claim '{claim.claim[:80]}'"
            )
        elif claim.claim.strip() in uncertainty_claims:
            status = "acceptable_with_disclosure"
            gate.acceptable_uncertainty_claims.append(claim.claim_id or claim.claim)
        else:
            gate.supported_claims.append(claim.claim_id or claim.claim)

        gate.claim_statuses.append(ClaimStatus(status))

    for claim in argument_map.unsafe_claims:
        reason = claim.claim_id or claim.claim
        if claim.claim.strip() in uncertainty_claims:
            gate.acceptable_uncertainty_claims.append(reason)
            claim_status = "acceptable_with_disclosure"
        else:
            gate.disputed_claims.append(reason)
            claim_status = "disputed"
            gate.hold_resolution_requirements.append(
                f"Remove or reframe unsafe claim '{claim.claim[:80]}'"
            )
        gate.claim_statuses.append(ClaimStatus(claim_status))

    gate.proof_check_results = [
        f"{claim.claim_id or claim.claim[:40]} -> {status.value}"
        for status, claim in zip(
            gate.claim_statuses,
            [*argument_map.safe_claims, *argument_map.unsafe_claims],
            strict=False,
        )
    ]

    if gate.missing_claims or gate.weak_claims:
        gate.decision = FactRiskDecision.HOLD
        gate.decision_reason = f"{len(gate.missing_claims)} missing and {len(gate.weak_claims)} weak claim(s) must be resolved before drafting."
    elif gate.disputed_claims or gate.acceptable_uncertainty_claims:
        risk_constraints = str(getattr(item, "constraints", "") or "").lower()
        strategy_rules = " ".join(getattr(strategy, "proof_rules", []) if strategy else []).lower()
        policy_text = f"{risk_constraints} {strategy_rules}".strip()
        can_disclose_uncertainty = any(
            token in policy_text for token in ("qualify", "disclose", "uncertain", "hypothesis")
        )
        limited_dispute = (
            bool(gate.disputed_claims)
            and not gate.acceptable_uncertainty_claims
            and len(gate.disputed_claims) <= 1
            and len(gate.supported_claims) >= 1
            and not gate.missing_claims
            and not gate.weak_claims
        )
        if can_disclose_uncertainty or limited_dispute:
            gate.decision = FactRiskDecision.PROCEED_WITH_UNCERTAINTY
            gate.required_disclosure = (
                "State the uncertainty explicitly and avoid categorical delivery."
            )
            gate.uncertainty_policy = (
                "Allowed only when the script discloses uncertainty and avoids overstated claims."
            )
            gate.decision_reason = f"{len(gate.acceptable_uncertainty_claims) + len(gate.disputed_claims)} claim(s) may proceed with disclosure."
        else:
            if gate.disputed_claims:
                gate.decision = FactRiskDecision.KILL
                gate.decision_reason = (
                    f"{len(gate.disputed_claims)} disputed claim(s) remain in the thesis artifact."
                )
            else:
                gate.decision = FactRiskDecision.HOLD
                gate.decision_reason = (
                    "Known uncertainty exists but no disclosure policy is configured for this run."
                )
                gate.hold_resolution_requirements.append(
                    "Either strengthen evidence or declare an uncertainty policy before drafting."
                )
    else:
        gate.decision = FactRiskDecision.APPROVED
        gate.decision_reason = "All thesis claims are backed by the current proof set."

    return gate


def _build_run_metrics(ctx: PipelineContext) -> ContentGenRunMetrics:
    phase_durations: dict[str, int] = {
        "phase_01_strategy_ms": 0,
        "phase_02_opportunity_ms": 0,
        "phase_03_research_ms": 0,
        "phase_04_draft_ms": 0,
        "phase_05_visual_ms": 0,
        "phase_06_qc_ms": 0,
        "phase_07_publish_ms": 0,
    }
    for trace in ctx.stage_traces:
        phase_key = {
            "phase_01_strategy": "phase_01_strategy_ms",
            "phase_02_opportunity": "phase_02_opportunity_ms",
            "phase_03_research": "phase_03_research_ms",
            "phase_04_draft": "phase_04_draft_ms",
            "phase_05_visual": "phase_05_visual_ms",
            "phase_06_qc": "phase_06_qc_ms",
            "phase_07_publish": "phase_07_publish_ms",
        }.get(trace.phase.value)
        if phase_key:
            phase_durations[phase_key] += trace.duration_ms

    primary_lane = next((lane for lane in ctx.lane_contexts if lane.role == "primary"), None)
    selected_score = None
    if ctx.scoring:
        selected_id = _resolve_selected_idea_id(ctx)
        selected_score = next(
            (score for score in ctx.scoring.scores if score.idea_id == selected_id),
            None,
        )

    release_state = "unknown"
    kill_reason = ""
    kill_phase = ""
    if primary_lane and primary_lane.publish_items:
        release_state = "published"
    elif (
        primary_lane
        and primary_lane.draft_decision
        and primary_lane.draft_decision.value == "recycle_for_reuse"
    ):
        release_state = "recycled_for_reuse"
    elif (
        primary_lane
        and primary_lane.draft_decision
        and primary_lane.draft_decision.value == "hold_for_proof"
    ):
        release_state = "held"
        kill_reason = primary_lane.decision_reason
        kill_phase = "phase_07_publish"
    elif (
        primary_lane
        and primary_lane.fact_risk_gate
        and primary_lane.fact_risk_gate.decision == FactRiskDecision.HOLD
    ):
        release_state = "held"
        kill_reason = primary_lane.fact_risk_gate.decision_reason
        kill_phase = "phase_03_research"
    elif (
        primary_lane
        and primary_lane.fact_risk_gate
        and primary_lane.fact_risk_gate.decision == FactRiskDecision.KILL
    ):
        release_state = "killed_early"
        kill_reason = primary_lane.fact_risk_gate.decision_reason
        kill_phase = "phase_03_research"
    elif ctx.qc_gate and ctx.qc_gate.must_fix_items:
        release_state = "killed_late"
        kill_reason = "; ".join(ctx.qc_gate.must_fix_items[:3])
        kill_phase = "phase_06_qc"

    llm_call_count = 0
    if ctx.scripting and ctx.scripting.step_traces:
        llm_call_count += sum(len(step.llm_calls) for step in ctx.scripting.step_traces)

    script_word_count = 0
    if ctx.scripting and ctx.scripting.qc and ctx.scripting.qc.final_script:
        script_word_count = len(ctx.scripting.qc.final_script.split())
    elif ctx.scripting and ctx.scripting.tightened:
        script_word_count = ctx.scripting.tightened.word_count
    elif ctx.scripting and ctx.scripting.draft:
        script_word_count = ctx.scripting.draft.word_count

    production_asset_count = 0
    if ctx.execution_brief:
        production_asset_count = len(ctx.execution_brief.assets_to_prepare) + len(
            ctx.execution_brief.existing_assets
        )
    elif ctx.production_brief:
        production_asset_count = len(ctx.production_brief.assets_to_prepare) + len(
            ctx.production_brief.props
        )

    packaging_variant_count = len(ctx.packaging.platform_packages) if ctx.packaging else 0

    return ContentGenRunMetrics(
        run_id=ctx.pipeline_id,
        brief_id=ctx.brief_reference.brief_id if ctx.brief_reference else "",
        idea_id=_resolve_selected_idea_id(ctx),
        angle_id=(getattr(_resolve_selected_angle(ctx), "angle_id", "") or ""),
        idea_score=float(selected_score.total_score if selected_score else 0.0),
        content_type=ctx.run_constraints.content_type if ctx.run_constraints else "",
        effort_tier=(
            ctx.run_constraints.effort_tier.value
            if ctx.run_constraints and hasattr(ctx.run_constraints.effort_tier, "value")
            else str(ctx.run_constraints.effort_tier)
            if ctx.run_constraints
            else ""
        ),
        release_queue_state=ctx.qc_gate.release_state.value if ctx.qc_gate else "",
        release_state=release_state,
        kill_reason=kill_reason,
        kill_phase=kill_phase,
        reuse_recommended=bool(
            ctx.scoring and _resolve_selected_idea_id(ctx) in ctx.scoring.reuse_recommended
        ),
        derivative_count=len(primary_lane.derivative_opportunities) if primary_lane else 0,
        approved_with_known_risks=bool(
            ctx.qc_gate and ctx.qc_gate.release_state == ReleaseState.APPROVED_WITH_KNOWN_RISKS
        ),
        script_word_count=script_word_count,
        production_asset_count=production_asset_count,
        packaging_variant_count=packaging_variant_count,
        llm_call_count=llm_call_count,
        estimated_cost_cents=0.0,
        created_at=ctx.created_at,
        published_at=(ctx.publish_items[0].publish_datetime if ctx.publish_items else ""),
        **phase_durations,
        total_cycle_time_ms=sum(phase_durations.values()),
    )


class ContentGenOrchestrator:
    """Coordinate content generation modules.

    Each module (scripting, backlog, angle, etc.) can run standalone or as
    part of a full pipeline.

    .. deprecated::
        All pipeline execution now routes through ``ContentGenPipeline``.
        Use ``ContentGenPipeline`` directly for new code.
        This class is retained as a backward-compatible shim.
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._agents: dict[str, Any] = {}

    def _get_agent(self, name: str) -> Any:
        if name not in self._agents:
            self._agents[name] = self._create_agent(name)
        return self._agents[name]

    def _create_agent(self, name: str) -> Any:
        from cc_deep_research.content_gen.agents.argument_map import ArgumentMapAgent
        from cc_deep_research.content_gen.agents.backlog import BacklogAgent
        from cc_deep_research.content_gen.agents.opportunity import OpportunityPlanningAgent
        from cc_deep_research.content_gen.agents.packaging import PackagingAgent
        from cc_deep_research.content_gen.agents.performance import PerformanceAgent
        from cc_deep_research.content_gen.agents.production import ProductionAgent
        from cc_deep_research.content_gen.agents.publish import PublishAgent
        from cc_deep_research.content_gen.agents.qc import QCAgent
        from cc_deep_research.content_gen.agents.quality_evaluator import QualityEvaluatorAgent
        from cc_deep_research.content_gen.agents.research_pack import ResearchPackAgent
        from cc_deep_research.content_gen.agents.scripting import ScriptingAgent
        from cc_deep_research.content_gen.agents.thesis import ThesisAgent
        from cc_deep_research.content_gen.agents.visual import VisualAgent

        factories: dict[str, Callable[[], Any]] = {
            "scripting": lambda: ScriptingAgent(self._config),
            "opportunity": lambda: OpportunityPlanningAgent(self._config),
            "backlog": lambda: BacklogAgent(self._config),
            "angle": lambda: ThesisAgent(self._config),  # P3-T2: now uses ThesisAgent
            "thesis": lambda: ThesisAgent(self._config),  # P3-T2: explicit thesis agent
            "research": lambda: ResearchPackAgent(self._config),
            "argument_map": lambda: ArgumentMapAgent(self._config),
            "visual": lambda: VisualAgent(self._config),
            "production": lambda: ProductionAgent(self._config),
            "packaging": lambda: PackagingAgent(self._config),
            "qc": lambda: QCAgent(self._config),
            "publish": lambda: PublishAgent(self._config),
            "performance": lambda: PerformanceAgent(self._config),
            "quality_evaluator": lambda: QualityEvaluatorAgent(self._config),
        }
        factory = factories.get(name)
        if factory is None:
            msg = f"Unknown agent: {name}"
            raise ValueError(msg)
        return factory()

    def _get_brief_service(self) -> BriefRunReferenceService:
        """Get or create a BriefRunReferenceService instance."""
        return BriefRunReferenceService(config=self._config)

    def establish_brief_reference(
        self,
        *,
        brief_id: str | None = None,
        managed_brief: ManagedOpportunityBrief | None = None,
        revision_id: str | None = None,
        revision_version: int | None = None,
        snapshot: OpportunityBrief | None = None,
        reference_type: str = "managed",
        seeded_from_revision_id: str = "",
    ) -> PipelineBriefReference:
        """Establish a brief reference from a managed brief or inline data.

        This is the canonical way to create a PipelineBriefReference for a run.
        If managed_brief is provided, we extract the revision metadata from it.
        If only an inline snapshot is provided, we create an inline_fallback reference.

        Args:
            brief_id: The managed brief resource ID.
            managed_brief: The managed brief resource (preferred).
            revision_id: Specific revision ID to pin to (for resume/seeded runs).
            revision_version: Human-readable version number.
            snapshot: The OpportunityBrief content for this run.
            reference_type: "managed", "inline_fallback", or "imported".
            seeded_from_revision_id: For seeded runs, the revision that was explicitly chosen.

        Returns:
            A PipelineBriefReference ready for PipelineContext.brief_reference.
        """
        return self._get_brief_service().establish_brief_reference(
            brief_id=brief_id,
            managed_brief=managed_brief,
            revision_id=revision_id,
            revision_version=revision_version,
            snapshot=snapshot,
            reference_type=reference_type,
            seeded_from_revision_id=seeded_from_revision_id,
        )

    def _build_brief_snapshot(self, managed: ManagedOpportunityBrief) -> OpportunityBrief:
        """Build an OpportunityBrief snapshot from a managed brief's current head."""
        return self._get_brief_service()._build_brief_snapshot(managed)

    def get_brief_for_run(
        self,
        *,
        brief_id: str | None = None,
        revision_id: str | None = None,
        snapshot: OpportunityBrief | None = None,
    ) -> tuple[PipelineBriefReference, OpportunityBrief | None]:
        """Get the brief reference and resolved brief content for starting a run."""
        return self._get_brief_service().get_brief_for_run(
            brief_id=brief_id,
            revision_id=revision_id,
            snapshot=snapshot,
        )

    def _load_brief_revision_content(
        self,
        managed: ManagedOpportunityBrief,
        revision_id: str,
    ) -> OpportunityBrief | None:
        """Load the OpportunityBrief content for a specific revision."""
        return self._get_brief_service()._load_brief_revision_content(managed, revision_id)

    # ------------------------------------------------------------------
    # P2-T3: Resume, Clone, and Seeded Run Flows
    # ------------------------------------------------------------------

    def validate_resume_context(
        self,
        ctx: PipelineContext,
        *,
        allow_stale_brief: bool = False,
    ) -> tuple[bool, str]:
        """Validate whether a saved pipeline context can be safely resumed.

        This checks:
        1. The brief revision is still available
        2. If the brief has changed since the original run, operator is warned
        3. Resume behavior is pinned to the original revision (no silent rebinding)

        Args:
            ctx: The pipeline context to validate.
            allow_stale_brief: If True, allow resuming even if brief has changed.

        Returns:
            Tuple of (is_valid, message) where:
            - is_valid is True if resume can proceed
            - message explains any warnings or issues
        """
        if ctx.brief_reference is None:
            # No brief reference - this is a legacy context, allow resume
            return True, "Resume allowed: legacy context without managed brief"

        brief_id = ctx.brief_reference.brief_id
        pinned_revision_id = ctx.brief_reference.revision_id

        if not brief_id:
            return True, "Resume allowed: no brief_id in reference"

        # Load current brief state
        service = self._get_brief_service()
        managed = service.get_brief(brief_id)

        if managed is None:
            return False, (
                f"Resume blocked: managed brief '{brief_id}' no longer exists. "
                f"The brief may have been deleted."
            )

        # Check if pinned revision is still available
        if pinned_revision_id and pinned_revision_id != managed.current_revision_id:
            if pinned_revision_id == managed.latest_revision_id:
                # Revision was incorporated but current head moved on
                warning = (
                    f"Warning: Brief '{brief_id}' has advanced past revision {pinned_revision_id}. "
                    f"Current head is {managed.current_revision_id}. "
                    f"Resume will use the pinned revision (not the latest)."
                )
            else:
                warning = (
                    f"Warning: Brief '{brief_id}' revision {pinned_revision_id} is no longer the latest. "
                    f"Latest is {managed.latest_revision_id}, current head is {managed.current_revision_id}. "
                    f"Resume will use the pinned revision."
                )

            if not allow_stale_brief:
                return False, warning + " Use allow_stale_brief=True to override."

            return True, warning + " Resume allowed (override)."

        # Check if brief state has changed
        original_state = ctx.brief_reference.lifecycle_state
        current_state = managed.lifecycle_state

        if original_state != current_state:
            warning = (
                f"Warning: Brief '{brief_id}' state changed from '{original_state.value}' "
                f"to '{current_state.value}' since original run."
            )
            if not allow_stale_brief and current_state == BriefLifecycleState.APPROVED:
                # State improved - might be OK
                pass
            elif not allow_stale_brief:
                return False, warning + " Use allow_stale_brief=True to override."
            return True, warning + " Resume allowed."

        return (
            True,
            f"Resume allowed: brief '{brief_id}' revision {pinned_revision_id or 'head'} is unchanged",
        )

    def get_brief_revisions_info(
        self,
        brief_id: str,
    ) -> dict[str, Any] | None:
        """Get information about available revisions for a managed brief."""
        return self._get_brief_service().get_brief_revisions_info(brief_id=brief_id)

    def create_seeded_run_reference(
        self,
        brief_id: str,
        *,
        revision_id: str | None = None,
        revision_version: int | None = None,
        snapshot: OpportunityBrief | None = None,
    ) -> PipelineBriefReference | None:
        """Create a brief reference for starting a new run from a specific revision."""
        return self._get_brief_service().create_seeded_run_reference(
            brief_id=brief_id,
            revision_id=revision_id,
            revision_version=revision_version,
            snapshot=snapshot,
        )

    def create_clone_reference(
        self,
        source_brief_id: str,
        *,
        source_revision_id: str | None = None,
        snapshot: OpportunityBrief | None = None,
    ) -> tuple[PipelineBriefReference, str | None]:
        """Create a brief reference by cloning from an existing brief."""
        return self._get_brief_service().create_clone_reference(
            source_brief_id=source_brief_id,
            source_revision_id=source_revision_id,
            snapshot=snapshot,
        )

    # ------------------------------------------------------------------
    # P2-T2: Brief Execution Gates
    # ------------------------------------------------------------------

    def initialize_brief_gate(
        self,
        *,
        brief_state: BriefLifecycleState = BriefLifecycleState.DRAFT,
        policy_mode: BriefExecutionPolicyMode | None = None,
    ) -> BriefExecutionGate:
        """Initialize the brief execution gate for a pipeline run."""
        return self._get_brief_service().initialize_brief_gate(
            brief_state=brief_state,
            policy_mode=policy_mode,
        )

    def _get_default_gate_policy(self) -> BriefExecutionPolicyMode:
        """Get the default gate policy from config."""
        return self._get_brief_service().get_default_gate_policy()

    def check_stage_gate(
        self,
        ctx: PipelineContext,
        stage_name: str,
    ) -> tuple[bool, str]:
        """Check if execution can proceed for the given stage.

        Args:
            ctx: Current pipeline context.
            stage_name: Name of the stage to check.

        Returns:
            Tuple of (can_proceed, message).

        Note:
            The gate only enforces approval requirements when a brief_reference
            is present (indicating a managed brief run). Older saved jobs or
            inline-only runs bypass the gate to maintain backward compatibility.
            Briefs generated in the same pipeline run also bypass gating since
            they're actively being developed.
        """
        # Get current brief state
        brief_state = BriefLifecycleState.DRAFT
        if ctx.brief_reference is not None:
            brief_state = ctx.brief_reference.lifecycle_state
        else:
            # No managed brief reference - this is an older saved job or inline-only run
            # Gate is not enforced in this case for backward compatibility
            return True, "Gate bypassed: no managed brief reference (legacy/inline run)"

        # P2-T2: If brief was generated in this pipeline run, don't gate
        # The brief is still being developed, not an externally-sourced brief
        if ctx.brief_reference.was_generated_in_run:
            return True, "Gate bypassed: brief was generated in this pipeline run"

        if ctx.brief_gate is None:
            # Gate not initialized - initialize it now
            ctx.brief_gate = self.initialize_brief_gate(brief_state=brief_state)
            ctx.brief_gate.checked_at_stage = (
                PIPELINE_STAGES.index(stage_name) if stage_name in PIPELINE_STAGES else -1
            )

        if ctx.brief_gate.was_blocked:
            return False, ctx.brief_gate.error_message

        # Check gate for this stage
        can_proceed, message = ctx.brief_gate.check_gate(brief_state, stage_name)

        # Update gate state
        ctx.brief_gate.checked_at_stage = (
            PIPELINE_STAGES.index(stage_name) if stage_name in PIPELINE_STAGES else -1
        )

        if not can_proceed:
            ctx.brief_gate.was_blocked = True
            ctx.brief_gate.error_message = message

        return can_proceed, message

    def get_gate_status_message(self, ctx: PipelineContext) -> str:
        """Get a human-readable gate status for display.

        Returns a message suitable for logging or operator visibility.
        """
        if ctx.brief_gate is None:
            return "Gate not initialized"

        gate = ctx.brief_gate
        stage_label = (
            PIPELINE_STAGE_LABELS.get(PIPELINE_STAGES[gate.checked_at_stage], "unknown")
            if gate.checked_at_stage >= 0
            else "not checked"
        )

        parts = [
            f"Gate status: {gate.get_gate_status()}",
            f"Policy: {gate.policy_mode.value}",
            f"Checked at stage: {stage_label}",
        ]

        if gate.warnings:
            parts.append(f"Warnings ({len(gate.warnings)}):")
            for warning in gate.warnings:
                parts.append(f"  - {warning}")

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Full pipeline
    # ------------------------------------------------------------------

    async def run_full_pipeline(
        self,
        theme: str,
        *,
        from_stage: int = 0,
        to_stage: int | None = None,
        initial_context: PipelineContext | None = None,
        bypass_ideation: bool = False,
        progress_callback: Callable[[int, str], None] | None = None,
        stage_completed_callback: Callable[[int, str, str, PipelineContext], None] | None = None,
        brief_id: str | None = None,
        brief_snapshot: OpportunityBrief | None = None,
        run_constraints: RunConstraints | None = None,
    ) -> PipelineContext:
        """Run the full pipeline.

        Delegates to ContentGenPipeline for canonical execution.
        """
        pipeline = ContentGenPipeline(self._config)
        return await pipeline.run_full_pipeline(
            theme,
            from_stage=from_stage,
            to_stage=to_stage,
            initial_context=initial_context,
            bypass_ideation=bypass_ideation,
            progress_callback=progress_callback,
            stage_completed_callback=stage_completed_callback,
            brief_id=brief_id,
            brief_snapshot=brief_snapshot,
            run_constraints=run_constraints,
        )

    def _persist_run_metrics(self, ctx: PipelineContext) -> None:
        """Persist always-on run metrics for operating-fitness analysis."""
        try:
            from cc_deep_research.content_gen.storage import ContentGenTelemetryStore

            store = ContentGenTelemetryStore(config=self._config)
            store.upsert_run_metrics(_build_run_metrics(ctx))
        except Exception:
            logger.warning("Failed to persist content-gen run metrics", exc_info=True)

    def validate_resume_context(
        self,
        *,
        from_stage: int,
        ctx: PipelineContext,
        bypass_ideation: bool = False,
    ) -> str | None:
        """Return a user-facing validation error when a resume request cannot run."""
        if bypass_ideation and 1 <= from_stage <= 3:
            return (
                "--idea bypasses stages 1-3; use --from-stage 0 to reload strategy "
                "or resume from stage 4 or later."
            )
        if from_stage == 0:
            return None
        prereqs_met, reason = self._check_prerequisites(from_stage, ctx)
        if prereqs_met:
            return None
        label = PIPELINE_STAGE_LABELS.get(PIPELINE_STAGES[from_stage], PIPELINE_STAGES[from_stage])
        return f"Cannot resume from stage {from_stage} ({label}): {reason}"

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
                _resolve_lane_item(ctx, candidate.idea_id) is not None
                for candidate in lane_candidates
            )
            has_angle = any(
                _resolve_lane_angle(ctx, candidate.idea_id) is not None
                for candidate in lane_candidates
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
            in (
                FactRiskDecision.APPROVED,
                FactRiskDecision.PROCEED_WITH_UNCERTAINTY,
            )
            and _resolve_lane_item(ctx, candidate.idea_id) is not None
            and _resolve_lane_angle(ctx, candidate.idea_id) is not None
            for candidate in lane_candidates
        ):
            return (
                False,
                "lane backlog/angles/argument_map missing or fact-risk gate blocked drafting",
            )
        # P5-T2: Skip visual_translation when using combined execution brief
        if stage == "visual_translation" and _use_combined_execution_brief(ctx):
            return False, "using combined execution brief"
        if stage == "visual_translation" and not any(
            lane.scripting is not None
            and (
                lane.scripting.tightened or lane.scripting.annotated_script or lane.scripting.draft
            )
            is not None
            and lane.scripting.structure is not None
            for lane in ctx.lane_contexts
        ):
            return False, "lane script/structure incomplete"
        # P5-T2: For production_brief, check if we're using combined execution brief
        # If so, we generate it from scripting context directly
        if stage == "production_brief":
            if _use_combined_execution_brief(ctx):
                # Combined execution brief uses scripting context directly
                if not any(
                    lane.scripting is not None
                    and (
                        lane.scripting.tightened
                        or lane.scripting.annotated_script
                        or lane.scripting.draft
                    )
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

    # ------------------------------------------------------------------
    # Targeted revision helpers — delegate to module-level functions
    # (preserved as staticmethod wrappers for backward compatibility)
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_retrieval_gaps(plan: TargetedRevisionPlan | None) -> list[str]:
        return _extract_retrieval_gaps(plan)

    @staticmethod
    def _build_targeted_feedback(quality_eval: QualityEvaluation) -> str:
        return _build_targeted_feedback(quality_eval)

    @staticmethod
    def _should_use_targeted_mode(quality_eval: QualityEvaluation) -> bool:
        return _should_use_targeted_mode(quality_eval)

    @staticmethod
    def _apply_targeted_feedback(ctx: PipelineContext, quality_eval: QualityEvaluation) -> None:
        _apply_targeted_feedback(ctx, quality_eval)

    # ------------------------------------------------------------------
    # Individual stage runners
    # ------------------------------------------------------------------

    async def run_backlog(
        self,
        theme: str,
        *,
        count: int = 20,
        opportunity_brief: OpportunityBrief | None = None,
    ) -> Any:
        from cc_deep_research.content_gen.storage import StrategyStore

        store = StrategyStore()
        strategy = store.load()
        agent = self._get_agent("backlog")
        return await agent.build_backlog(
            theme, strategy, count=count, opportunity_brief=opportunity_brief
        )

    async def run_scoring(self, items: list) -> Any:
        from cc_deep_research.content_gen.storage import StrategyStore

        store = StrategyStore()
        strategy = store.load()
        agent = self._get_agent("backlog")
        return await agent.score_ideas(items, strategy)

    async def run_angle(self, item: Any) -> Any:
        from cc_deep_research.content_gen.storage import StrategyStore

        store = StrategyStore()
        strategy = store.load()
        agent = self._get_agent("angle")
        return await agent.generate(item, strategy)

    async def run_research(self, item: Any, angle: Any) -> Any:
        agent = self._get_agent("research")
        return await agent.build(item, angle)

    async def run_argument_map(self, item: Any, angle: Any, research_pack: ResearchPack) -> Any:
        agent = self._get_agent("argument_map")
        return await agent.build(item, angle, research_pack)

    async def run_visual(
        self, scripting_ctx: ScriptingContext, *, idea_id: str = "", angle_id: str = ""
    ) -> Any:
        agent = self._get_agent("visual")
        source = scripting_ctx.tightened or scripting_ctx.annotated_script or scripting_ctx.draft
        structure = scripting_ctx.structure
        if source is None or structure is None:
            msg = "Visual translation requires a completed script with structure."
            raise ValueError(msg)
        return await agent.translate(source, structure, idea_id=idea_id, angle_id=angle_id)

    async def run_production(self, visual_plan: Any) -> Any:
        agent = self._get_agent("production")
        return await agent.brief(visual_plan)

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

    async def run_qc(
        self,
        *,
        script: str,
        visual_summary: str = "",
        packaging_summary: str = "",
        research_summary: str = "",
        argument_map_summary: str = "",
    ) -> Any:
        agent = self._get_agent("qc")
        return await agent.review(
            script=script,
            visual_summary=visual_summary,
            packaging_summary=packaging_summary,
            research_summary=research_summary,
            argument_map_summary=argument_map_summary,
        )

    async def run_publish(self, packaging: Any, *, idea_id: str = "") -> Any:
        agent = self._get_agent("publish")
        return await agent.schedule(packaging, idea_id=idea_id)

    async def run_performance(
        self, *, video_id: str, metrics: dict, script: str = "", hook: str = "", caption: str = ""
    ) -> Any:
        """Run performance analysis and extract structured learnings.

        This method:
        1. Runs the performance analysis agent
        2. Extracts structured learnings from the analysis
        3. Stores learnings in the performance learning store for future use

        Returns the PerformanceAnalysis result. Use get_performance_learnings()
        to retrieve the extracted learnings.
        """
        from cc_deep_research.content_gen.storage import PerformanceLearningStore

        agent = self._get_agent("performance")
        analysis = await agent.analyze(
            video_id=video_id, metrics=metrics, script=script, hook=hook, caption=caption
        )

        # Extract and store learnings
        try:
            store = PerformanceLearningStore()
            learning_set = store.extract_learnings_from_analysis(
                video_id=video_id,
                analysis=analysis,
            )
            logger.info(
                "Extracted %d performance learnings from video %s",
                len(learning_set.learnings),
                video_id,
            )
        except Exception as e:
            logger.warning("Failed to extract performance learnings: %s", e)

        return analysis

    # ------------------------------------------------------------------
    # Legacy scripting methods (delegated to ScriptingRunService)
    # ------------------------------------------------------------------

    async def run_scripting(
        self,
        raw_idea: str,
        progress_callback: Callable[[int, str], None] | None = None,
        *,
        llm_route: str | None = None,
    ) -> ScriptingContext:
        """Run the full 10-step scripting pipeline."""
        svc = ScriptingRunService(self._config)
        return await svc.run_scripting(raw_idea, progress_callback, llm_route=llm_route)

    async def run_scripting_from_step(
        self,
        ctx: ScriptingContext,
        step: int,
        progress_callback: Callable[[int, str], None] | None = None,
        *,
        llm_route: str | None = None,
    ) -> ScriptingContext:
        """Resume the scripting pipeline from a specific step."""
        svc = ScriptingRunService(self._config)
        return await svc.run_scripting_from_step(ctx, step, progress_callback, llm_route=llm_route)

    async def run_scripting_iterative(
        self,
        raw_idea: str,
        progress_callback: Callable[[int, str], None] | None = None,
        max_iterations: int | None = None,
        *,
        llm_route: str | None = None,
    ) -> tuple[ScriptingContext, IterationState]:
        """Run the scripting pipeline inside an evaluation loop."""
        svc = ScriptingRunService(self._config)
        return await svc.run_scripting_iterative(
            raw_idea, progress_callback, max_iterations, llm_route=llm_route
        )

    async def run_module(
        self,
        module: str,
        input_data: dict[str, Any],
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> ScriptingContext:
        """Run a single content gen module.

        Args:
            module: Module name (e.g. 'scripting').
            input_data: Module-specific input. For scripting, requires
                'raw_idea' or 'context' + 'from_step'.
        """
        if module == "scripting":
            ctx_data = input_data.get("context")
            from_step = input_data.get("from_step")

            if ctx_data and from_step is not None:
                ctx = (
                    ScriptingContext.model_validate(ctx_data)
                    if isinstance(ctx_data, dict)
                    else ctx_data
                )
                return await self.run_scripting_from_step(ctx, from_step, progress_callback)

            return await self.run_scripting(input_data["raw_idea"], progress_callback)

        msg = f"Unknown module: {module}"
        raise ValueError(msg)
