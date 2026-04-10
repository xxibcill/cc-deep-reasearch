"""Orchestrator for the content generation workflow."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from cc_deep_research.content_gen.models import (
    PIPELINE_STAGE_LABELS,
    PIPELINE_STAGES,
    AngleDefinition,
    ArgumentMap,
    BeatIntent,
    BeatIntentMap,
    ClaimTraceEntry,
    ClaimTraceLedger,
    ClaimTraceStage,
    ClaimTraceStatus,
    CoreInputs,
    IterationState,
    OpportunityBrief,
    PipelineCandidate,
    PipelineContext,
    PipelineLaneContext,
    PipelineStageTrace,
    QualityEvaluation,
    ResearchPack,
    RevisionMode,
    ScoringOutput,
    ScriptClaimStatement,
    ScriptingContext,
    ScriptStructure,
    ScriptVersion,
    StageTraceMetadata,
    StrategyMemory,
    TargetedRevisionPlan,
)

if TYPE_CHECKING:
    from cc_deep_research.config import Config

logger = logging.getLogger(__name__)


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
    if ctx.selected_idea_id:
        candidates.append(ctx.selected_idea_id)
    candidates.extend(_active_candidate_ids(ctx))
    if ctx.scoring:
        if ctx.scoring.selected_idea_id:
            candidates.append(ctx.scoring.selected_idea_id)
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
        item = next((candidate for candidate in ctx.backlog.items if candidate.idea_id == idea_id), None)
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
            (option for option in ctx.angles.angle_options if option.angle_id == ctx.angles.selected_angle_id),
            None,
        )
        if angle is not None:
            return angle
    return ctx.angles.angle_options[0] if ctx.angles.angle_options else None


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
    lane = _resolve_lane_context(ctx, idea_id)
    if lane is None or lane.angles is None:
        return None
    if lane.angles.selected_angle_id:
        angle = next(
            (option for option in lane.angles.angle_options if option.angle_id == lane.angles.selected_angle_id),
            None,
        )
        if angle is not None:
            return angle
    return lane.angles.angle_options[0] if lane.angles.angle_options else None


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

    ctx.angles = primary_lane.angles
    ctx.research_pack = primary_lane.research_pack
    ctx.argument_map = primary_lane.argument_map
    ctx.scripting = primary_lane.scripting
    ctx.visual_plan = primary_lane.visual_plan
    ctx.production_brief = primary_lane.production_brief
    ctx.packaging = primary_lane.packaging
    ctx.qc_gate = primary_lane.qc_gate
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
    return any(
        lane.packaging is not None and lane.qc_gate is not None and lane.qc_gate.approved_for_publish
        for lane in ctx.lane_contexts
    )


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


def _build_claim_ledger(
    research_pack: ResearchPack | None,
    argument_map: ArgumentMap | None,
    scripting: ScriptingContext | None,
) -> ClaimTraceLedger:
    """Build claim traceability ledger from research pack, argument map, and scripting context."""
    from datetime import UTC, datetime

    # Initialize from research pack
    ledger = ClaimTraceLedger()
    claim_text_to_id: dict[str, str] = {}

    if research_pack:
        for claim in research_pack.claims:
            entry = ClaimTraceEntry(
                claim_id=claim.claim_id,
                claim_text=claim.claim,
                first_seen_stage=ClaimTraceStage.RESEARCH_PACK,
                research_claim_type=claim.claim_type,
                source_ids=list(claim.source_ids),
                status=ClaimTraceStatus.SUPPORTED if claim.source_ids else ClaimTraceStatus.UNSUPPORTED,
            )
            ledger.entries.append(entry)
            claim_text_to_id[claim.claim] = claim.claim_id

    # Update from argument map
    if argument_map:
        for arg_claim in argument_map.safe_claims:
            if arg_claim.claim in claim_text_to_id:
                existing_entry = ledger.get_claim(claim_text_to_id[arg_claim.claim])
                if existing_entry:
                    existing_entry.present_in_argument_map = True
                    existing_entry.argument_claim_id = arg_claim.claim_id
                    existing_entry.supporting_proof_ids = list(arg_claim.supporting_proof_ids)
                    if not arg_claim.supporting_proof_ids:
                        existing_entry.status = ClaimTraceStatus.UNSUPPORTED
            else:
                entry = ClaimTraceEntry(
                    claim_id=arg_claim.claim_id,
                    claim_text=arg_claim.claim,
                    first_seen_stage=ClaimTraceStage.ARGUMENT_MAP,
                    present_in_argument_map=True,
                    argument_claim_id=arg_claim.claim_id,
                    supporting_proof_ids=list(arg_claim.supporting_proof_ids),
                    status=ClaimTraceStatus.SUPPORTED if arg_claim.supporting_proof_ids else ClaimTraceStatus.UNSUPPORTED,
                )
                ledger.entries.append(entry)
                claim_text_to_id[arg_claim.claim] = arg_claim.claim_id

        for beat in argument_map.beat_claim_plan:
            for claim_id in beat.claim_ids:
                existing_entry = ledger.get_claim(claim_id)
                if existing_entry:
                    existing_entry.present_in_beat_plan = True
                    if beat.beat_id not in existing_entry.beat_ids:
                        existing_entry.beat_ids.append(beat.beat_id)
                else:
                    entry = ClaimTraceEntry(
                        claim_id=claim_id,
                        claim_text="",
                        first_seen_stage=ClaimTraceStage.BEAT_PLAN,
                        present_in_beat_plan=True,
                        beat_ids=[beat.beat_id],
                        status=ClaimTraceStatus.UNKNOWN,
                    )
                    ledger.entries.append(entry)

    # Analyze script for claim traceability
    if scripting:
        final_script = ""
        if scripting.qc and scripting.qc.final_script:
            final_script = scripting.qc.final_script
        elif scripting.tightened:
            final_script = scripting.tightened.content
        elif scripting.draft:
            final_script = scripting.draft.content

        if final_script:
            # Match script claims against known claims from argument map
            arg_claims_by_text = {c.claim: c for c in (argument_map.safe_claims if argument_map else [])}

            for claim_text, arg_claim in arg_claims_by_text.items():
                if claim_text.lower() in final_script.lower():
                    existing_entry = ledger.get_claim(arg_claim.claim_id)
                    if existing_entry:
                        existing_entry.present_in_script = True
                        statement = ScriptClaimStatement(
                            text=claim_text,
                            beat_name=existing_entry.beat_ids[0] if existing_entry.beat_ids else "",
                            claim_ids=[arg_claim.claim_id],
                            proof_anchor_ids=list(arg_claim.supporting_proof_ids),
                            status=ClaimTraceStatus.SUPPORTED if arg_claim.supporting_proof_ids else ClaimTraceStatus.UNSUPPORTED,
                            status_reason="Matched to argument map claim with proof anchors"
                            if arg_claim.supporting_proof_ids
                            else "Matched to argument map claim without proof anchors",
                        )
                        ledger.script_claims.append(statement)
                        existing_entry.script_statement_ids.append(statement.statement_id)

            # Detect introduced late claims (mentioned in script but not in argument map)
            for entry in ledger.entries:
                if (
                    not entry.present_in_argument_map
                    and entry.first_seen_stage == ClaimTraceStage.RESEARCH_PACK
                    and entry.claim_text.lower() in final_script.lower()
                ):
                    entry.status = ClaimTraceStatus.INTRODUCED_LATE
                    entry.status_changed_at = datetime.now(tz=UTC).isoformat()
                    ledger.introduced_late_claims.append(entry.claim_id)
                    statement = ScriptClaimStatement(
                        text=entry.claim_text,
                        claim_ids=[entry.claim_id],
                        status=ClaimTraceStatus.INTRODUCED_LATE,
                        status_reason="Claim from research pack appeared in script but was not in argument map",
                    )
                    ledger.script_claims.append(statement)
                    entry.script_statement_ids.append(statement.statement_id)

            # Detect dropped claims (in argument map but not in script)
            for entry in ledger.entries:
                if entry.present_in_argument_map and not entry.present_in_script:
                    entry.status = ClaimTraceStatus.DROPPED
                    entry.status_changed_at = datetime.now(tz=UTC).isoformat()
                    ledger.dropped_claims.append(entry.claim_id)

            # Flag unsupported script claims
            for stmt in ledger.script_claims:
                if stmt.status == ClaimTraceStatus.UNSUPPORTED:
                    ledger.unsupported_script_claims.append(stmt.statement_id)

    return ledger


class ContentGenOrchestrator:
    """Coordinate content generation modules.

    Each module (scripting, backlog, angle, etc.) can run standalone or as
    part of a full pipeline.
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._agents: dict[str, Any] = {}

    def _get_agent(self, name: str) -> Any:
        if name not in self._agents:
            self._agents[name] = self._create_agent(name)
        return self._agents[name]

    def _create_agent(self, name: str) -> Any:
        from cc_deep_research.content_gen.agents.angle import AngleAgent
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
        from cc_deep_research.content_gen.agents.visual import VisualAgent

        factories: dict[str, Callable[[], Any]] = {
            "scripting": lambda: ScriptingAgent(self._config),
            "opportunity": lambda: OpportunityPlanningAgent(self._config),
            "backlog": lambda: BacklogAgent(self._config),
            "angle": lambda: AngleAgent(self._config),
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
    ) -> PipelineContext:
        """Run the full 14-stage content pipeline with iterative quality loop.

        Phases:
          1. Stages 0-4 (ideation) — run once
          2. Stages 5-11 (content) — iterative loop with quality evaluation
          3. Stages 12-13 (publish) — run once after loop exits
        """
        if initial_context is None:
            ctx = PipelineContext(
                theme=theme,
                created_at=datetime.now(tz=UTC).isoformat(),
                iteration_state=IterationState(
                    max_iterations=self._config.content_gen.max_iterations,
                ),
            )
        else:
            ctx = initial_context.model_copy(deep=True)
            if theme and not ctx.theme:
                ctx.theme = theme
            if not ctx.created_at:
                ctx.created_at = datetime.now(tz=UTC).isoformat()
            if ctx.iteration_state is None:
                ctx.iteration_state = IterationState(
                    max_iterations=self._config.content_gen.max_iterations,
                )
        end = to_stage if to_stage is not None else len(PIPELINE_STAGES) - 1

        # Phase 1: Ideation stages (0-4) — run once
        if bypass_ideation:
            if from_stage == 0 and end >= 0:
                ctx = await self._run_stage(0, ctx, progress_callback, stage_completed_callback)
            ideation_start = max(from_stage, 4)
            for idx in range(ideation_start, min(5, end + 1)):
                ctx = await self._run_stage(idx, ctx, progress_callback, stage_completed_callback)
        else:
            for idx in range(from_stage, min(5, end + 1)):
                ctx = await self._run_stage(idx, ctx, progress_callback, stage_completed_callback)

        # Phase 2: Content stages (5-11) — iterative or single-pass
        if self._config.content_gen.enable_iterative_mode and end >= 7 and from_stage <= 6:
            ctx = await self._run_iterative_loop(ctx, progress_callback, end, stage_completed_callback)
        else:
            for idx in range(max(5, from_stage), min(12, end + 1)):
                ctx = await self._run_stage(idx, ctx, progress_callback, stage_completed_callback)

        # Phase 3: Post-content stages (12-13) — run once
        for idx in range(12, end + 1):
            ctx = await self._run_stage(idx, ctx, progress_callback, stage_completed_callback)

        return ctx

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
        if stage == "build_research_pack" and not any(
            _resolve_lane_item(ctx, candidate.idea_id) is not None
            and _resolve_lane_angle(ctx, candidate.idea_id) is not None
            for candidate in lane_candidates
        ):
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
            and _resolve_lane_item(ctx, candidate.idea_id) is not None
            and _resolve_lane_angle(ctx, candidate.idea_id) is not None
            for candidate in lane_candidates
        ):
            return False, "lane backlog/angles/argument_map missing"
        if stage == "visual_translation" and not any(
            lane.scripting is not None
            and (lane.scripting.tightened or lane.scripting.annotated_script or lane.scripting.draft) is not None
            and lane.scripting.structure is not None
            for lane in ctx.lane_contexts
        ):
            return False, "lane script/structure incomplete"
        if stage == "production_brief" and not any(lane.visual_plan is not None for lane in ctx.lane_contexts):
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

    async def _run_stage(
        self,
        idx: int,
        ctx: PipelineContext,
        progress_callback: Callable[[int, str], None] | None,
        stage_completed_callback: Callable[[int, str, str, PipelineContext], None] | None = None,
        *,
        retrieval_gaps: list[str] | None = None,
    ) -> PipelineContext:
        # retrieval_gaps is forwarded to stage handlers via ctx.iteration_state
        # from the targeted revision path — the base _run_stage does not use it directly
        _ = retrieval_gaps  # noqa: ARG002
        stage_name = PIPELINE_STAGES[idx]
        label = PIPELINE_STAGE_LABELS.get(stage_name, stage_name)
        if progress_callback:
            progress_callback(idx, label)
        ctx.current_stage = idx

        started_at = datetime.now(tz=UTC).isoformat()
        input_summary = self._summarize_input(idx, ctx)

        prereqs_met, skip_reason = self._check_prerequisites(idx, ctx)
        if not prereqs_met:
            warnings = self._collect_trace_warnings(idx, ctx, status="skipped", detail=skip_reason)
            trace = PipelineStageTrace(
                stage_index=idx,
                stage_name=stage_name,
                stage_label=label,
                status="skipped",
                started_at=started_at,
                completed_at=datetime.now(tz=UTC).isoformat(),
                input_summary=input_summary,
                output_summary=skip_reason,
                warnings=warnings,
                decision_summary=self._build_decision_summary(idx, ctx, status="skipped", detail=skip_reason),
                metadata=self._build_trace_metadata(idx, ctx),
            )
            ctx.stage_traces.append(trace)
            if stage_completed_callback:
                stage_completed_callback(idx, "skipped", skip_reason, ctx)
            return ctx

        try:
            ctx = await _PIPELINE_HANDLERS[idx](self, ctx)
            status = "completed"
            output_summary = self._summarize_output(idx, ctx)
            warnings = self._collect_trace_warnings(idx, ctx, status=status)
            decision_summary = self._build_decision_summary(idx, ctx, status=status)
        except Exception as e:
            status = "failed"
            output_summary = str(e)
            warnings = self._collect_trace_warnings(idx, ctx, status=status, detail=str(e))
            completed_at = datetime.now(tz=UTC).isoformat()
            trace = PipelineStageTrace(
                stage_index=idx,
                stage_name=stage_name,
                stage_label=label,
                status=status,
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=int(
                    (datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at))
                    .total_seconds()
                    * 1000
                ),
                input_summary=input_summary,
                output_summary=output_summary,
                warnings=warnings,
                decision_summary=self._build_decision_summary(idx, ctx, status=status, detail=str(e)),
                metadata=self._build_trace_metadata(idx, ctx),
            )
            ctx.stage_traces.append(trace)
            if stage_completed_callback:
                stage_completed_callback(idx, "failed", str(e), ctx)
            raise

        completed_at = datetime.now(tz=UTC).isoformat()
        trace = PipelineStageTrace(
            stage_index=idx,
            stage_name=stage_name,
            stage_label=label,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=int(
                (datetime.fromisoformat(completed_at) - datetime.fromisoformat(started_at))
                .total_seconds()
                * 1000
            ),
            input_summary=input_summary,
            output_summary=output_summary,
            warnings=warnings,
            decision_summary=decision_summary,
            metadata=self._build_trace_metadata(idx, ctx),
        )
        ctx.stage_traces.append(trace)
        if stage_completed_callback:
            stage_completed_callback(idx, "completed", "", ctx)
        return ctx

    async def _run_iterative_loop(
        self,
        ctx: PipelineContext,
        progress_callback: Callable[[int, str], None] | None,
        end_stage: int,
        stage_completed_callback: Callable[[int, str, str, PipelineContext], None] | None = None,
    ) -> PipelineContext:
        iter_state = ctx.iteration_state or IterationState(
            max_iterations=self._config.content_gen.max_iterations,
        )
        ctx.iteration_state = iter_state
        max_iter = iter_state.max_iterations
        threshold = self._config.content_gen.quality_threshold

        while iter_state.current_iteration <= max_iter:
            iteration = iter_state.current_iteration
            logger.info(
                "Content iteration %d/%d", iteration, max_iter,
            )
            if progress_callback:
                progress_callback(-1, f"Iteration {iteration}/{max_iter}")

            # Check for full restart recommendation
            if iter_state.targeted_revision_plan and iter_state.targeted_revision_plan.full_restart_recommended:
                logger.info("Full restart recommended — clearing targeted plan")
                iter_state.targeted_revision_plan = None
                iter_state.revision_mode = RevisionMode.FULL

            # Re-run research if gaps were identified in previous iteration
            if iteration > 1 and iter_state.should_rerun_research:
                ctx = await self._run_stage(5, ctx, progress_callback, stage_completed_callback)
                iter_state.should_rerun_research = False

            # Determine revision mode for this iteration
            revision_mode = iter_state.revision_mode if iteration > 1 else RevisionMode.FULL

            # Run targeted or full content stages
            if revision_mode == RevisionMode.TARGETED and iter_state.targeted_revision_plan:
                ctx = await self._run_targeted_revision(ctx, progress_callback, end_stage, stage_completed_callback)
            else:
                for idx in range(6, min(12, end_stage + 1)):
                    ctx = await self._run_stage(idx, ctx, progress_callback, stage_completed_callback)

            # Re-fetch iter_state in case stage handlers replaced it
            iter_state = ctx.iteration_state

            # Evaluate quality
            quality_eval = await self._evaluate_quality(ctx, iteration, threshold)
            iter_state.quality_history.append(quality_eval)
            iter_state.latest_feedback = self._format_feedback(quality_eval)

            # Check stop conditions
            if self._should_stop_iterating(quality_eval, iter_state):
                iter_state.is_converged = True
                iter_state.convergence_reason = quality_eval.rationale
                break

            # Prepare next iteration
            if quality_eval.research_gaps_identified or (
                quality_eval.targeted_revision_plan and quality_eval.targeted_revision_plan.needs_retrieval
            ):
                iter_state.should_rerun_research = True

            # Transfer targeted revision plan from evaluation to iteration state
            if quality_eval.targeted_revision_plan:
                iter_state.targeted_revision_plan = quality_eval.targeted_revision_plan
                iter_state.revision_mode = quality_eval.revision_mode

            self._inject_feedback(ctx, quality_eval)
            iter_state.current_iteration += 1

        return ctx

    async def _run_targeted_revision(
        self,
        ctx: PipelineContext,
        progress_callback: Callable[[int, str], None] | None,
        end_stage: int,
        stage_completed_callback: Callable[[int, str, str, PipelineContext], None] | None = None,
    ) -> PipelineContext:
        """Run content stages with targeted revision mode.

        Only re-runs research for weak beats' evidence gaps and runs
        scripting only for beats that need repair. Stable beats are preserved.
        """
        plan = ctx.iteration_state.targeted_revision_plan
        if plan is None:
            return ctx

        # Step 1: Targeted research refresh for evidence gaps
        retrieval_gaps = self._extract_retrieval_gaps(plan)
        if retrieval_gaps:
            logger.info("Running targeted research for %d gaps", len(retrieval_gaps))
            ctx = await self._run_stage(5, ctx, progress_callback, stage_completed_callback, retrieval_gaps=retrieval_gaps)

        # Step 2: Re-run argument map to incorporate refreshed evidence
        if retrieval_gaps:
            ctx = await self._run_stage(6, ctx, progress_callback, stage_completed_callback)

        # Step 3: Run scripting and remaining stages (scripting uses the plan
        # to know which beats to preserve and which to rewrite)
        for idx in range(7, min(12, end_stage + 1)):
            ctx = await self._run_stage(idx, ctx, progress_callback, stage_completed_callback)

        return ctx

    async def _evaluate_quality(
        self,
        ctx: PipelineContext,
        iteration: int,
        threshold: float,
    ) -> QualityEvaluation:
        agent = self._get_agent("quality_evaluator")
        previous_feedback = ""
        if ctx.iteration_state and ctx.iteration_state.quality_history:
            prev = ctx.iteration_state.quality_history[-1]
            previous_feedback = self._format_feedback(prev)

        return await agent.evaluate(
            scripting=ctx.scripting or ScriptingContext(),
            visual_plan=ctx.visual_plan,
            packaging=ctx.packaging,
            research_pack=ctx.research_pack,
            argument_map=ctx.argument_map,
            angle=ctx.angles,
            iteration_number=iteration,
            quality_threshold=threshold,
            previous_feedback=previous_feedback,
        )

    def _should_stop_iterating(
        self,
        quality_eval: QualityEvaluation,
        iter_state: IterationState,
    ) -> bool:
        if quality_eval.has_blocking_claim_issues and iter_state.current_iteration < iter_state.max_iterations:
            return False
        if quality_eval.passes_threshold:
            return True
        if iter_state.current_iteration >= iter_state.max_iterations:
            return True
        # Convergence: not improving enough
        if len(iter_state.quality_history) >= 2:
            prev_score = iter_state.quality_history[-2].overall_quality_score
            improvement = quality_eval.overall_quality_score - prev_score
            if improvement < self._config.content_gen.convergence_threshold:
                return True
        return False

    @staticmethod
    def _format_feedback(quality_eval: QualityEvaluation) -> str:
        parts: list[str] = []
        if quality_eval.unsupported_claims:
            parts.append("Unsupported claims to remove, qualify, or prove:")
            parts.extend(f"- {claim}" for claim in quality_eval.unsupported_claims)
        if quality_eval.evidence_actions_required:
            parts.append("Evidence actions required:")
            parts.extend(f"- {action}" for action in quality_eval.evidence_actions_required)
        if quality_eval.critical_issues:
            parts.append("Critical issues:")
            parts.extend(f"- {i}" for i in quality_eval.critical_issues)
        if quality_eval.improvement_suggestions:
            parts.append("Improvement suggestions:")
            parts.extend(f"- {s}" for s in quality_eval.improvement_suggestions)
        if quality_eval.research_gaps_identified:
            parts.append("Research gaps identified:")
            parts.extend(f"- {gap}" for gap in quality_eval.research_gaps_identified)
        if quality_eval.rationale:
            parts.append(f"Rationale: {quality_eval.rationale}")
        return "\n".join(parts)

    @staticmethod
    def _inject_feedback(ctx: PipelineContext, quality_eval: QualityEvaluation) -> None:
        if not ctx.scripting:
            return

        # Handle targeted revision mode
        if ContentGenOrchestrator._should_use_targeted_mode(quality_eval):
            ContentGenOrchestrator._apply_targeted_feedback(ctx, quality_eval)
            return

        # Standard full feedback injection
        feedback_lines = [f"Iteration {quality_eval.iteration_number} feedback:"]
        if quality_eval.unsupported_claims:
            feedback_lines.append("Unsupported claims to remove, qualify, or prove:")
            feedback_lines.extend(f"- {claim}" for claim in quality_eval.unsupported_claims)
        if quality_eval.evidence_actions_required:
            feedback_lines.append("Evidence actions required:")
            feedback_lines.extend(f"- {action}" for action in quality_eval.evidence_actions_required)
        if quality_eval.critical_issues:
            feedback_lines.append("Critical issues to fix:")
            feedback_lines.extend(f"- {i}" for i in quality_eval.critical_issues)
        if quality_eval.improvement_suggestions:
            feedback_lines.append("Improvement suggestions:")
            feedback_lines.extend(f"- {s}" for s in quality_eval.improvement_suggestions)
        if quality_eval.research_gaps_identified:
            feedback_lines.append("Research gaps identified:")
            feedback_lines.extend(f"- {gap}" for gap in quality_eval.research_gaps_identified)
        feedback_text = "\n".join(feedback_lines)
        existing = ctx.scripting.research_context or ""
        ctx.scripting.research_context = f"{feedback_text}\n\n{existing}"
        ctx.iteration_state.revision_mode = RevisionMode.FULL

    # ------------------------------------------------------------------
    # Targeted Revision helpers (Task 18)
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_retrieval_gaps(plan: TargetedRevisionPlan | None) -> list[str]:
        """Extract evidence gaps from a targeted revision plan."""
        if plan is None:
            return []
        gaps = list(plan.retrieval_gaps)
        for action in plan.actions:
            gaps.extend(action.evidence_gaps)
        return gaps

    @staticmethod
    def _build_targeted_feedback(quality_eval: QualityEvaluation) -> str:
        """Build feedback string from a targeted revision plan for the next iteration."""
        if quality_eval.targeted_revision_plan is None:
            return ""
        plan = quality_eval.targeted_revision_plan
        parts: list[str] = []

        if plan.revision_summary:
            parts.append(f"Revision: {plan.revision_summary}")

        for action in plan.actions:
            if action.instruction:
                parts.append(f"[{action.beat_name or action.beat_id}] {action.instruction}")
            elif action.weak_claim_ids:
                parts.append(f"[{action.beat_name or action.beat_id}] Rewrite needed for claims: {', '.join(action.weak_claim_ids)}")

        if plan.full_restart_recommended:
            parts.append("WARNING: Full restart recommended — targeted revision insufficient.")

        return "\n".join(parts)

    @staticmethod
    def _should_use_targeted_mode(quality_eval: QualityEvaluation) -> bool:
        """Decide whether to use targeted or full revision mode."""
        if quality_eval.revision_mode == RevisionMode.FULL:
            return False
        if quality_eval.targeted_revision_plan is None:
            return False
        if quality_eval.targeted_revision_plan.full_restart_recommended:
            return False
        return quality_eval.targeted_revision_plan.has_targeted_actions

    @staticmethod
    def _apply_targeted_feedback(ctx: PipelineContext, quality_eval: QualityEvaluation) -> None:
        """Inject targeted revision feedback into scripting context."""
        if not ctx.scripting or not quality_eval.targeted_revision_plan:
            return

        plan = quality_eval.targeted_revision_plan

        # Build targeted feedback
        targeted_feedback = ContentGenOrchestrator._build_targeted_feedback(quality_eval)
        if not targeted_feedback:
            return

        # Mark stable beats that should be preserved
        stable_ids = plan.stable_beat_ids()

        # Inject into research_context
        existing = ctx.scripting.research_context or ""
        ctx.scripting.research_context = f"TARGETED REVISION:\n{targeted_feedback}\n\nStable beats (preserve unchanged): {', '.join(stable_ids) if stable_ids else 'none'}\n\n{existing}"

        # Store plan in iteration state for scripting agent to use
        ctx.iteration_state.targeted_revision_plan = plan
        ctx.iteration_state.revision_mode = RevisionMode.TARGETED

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
                return (
                    f"selected_idea_id={_resolve_selected_idea_id(ctx) or 'none'}, "
                    f"shortlist={len(ctx.shortlist or ctx.scoring.shortlist)}, "
                    f"active_candidates={len(ctx.active_candidates or ctx.scoring.active_candidates)}"
                )
            return "selected_idea_id=none, shortlist=0, active_candidates=0"
        if stage == "build_research_pack":
            if ctx.angles:
                return f"idea_id={_resolve_selected_idea_id(ctx) or 'none'}"
            return "idea_id=none"
        if stage == "build_argument_map":
            if ctx.research_pack:
                return (
                    f"research_claims={len(ctx.research_pack.claims)}, "
                    f"proof_points={len(ctx.research_pack.proof_points)}"
                )
            return "research_pack=empty"
        if stage == "run_scripting":
            if ctx.argument_map:
                return (
                    f"beats={len(ctx.argument_map.beat_claim_plan)}, "
                    f"safe_claims={len(ctx.argument_map.safe_claims)}"
                )
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
                return f"approved={ctx.qc_gate.approved_for_publish}"
            return "approved=false"
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
                return (
                    f"produce={len(ctx.scoring.produce_now)}, "
                    f"shortlist={len(ctx.scoring.shortlist)}, "
                    f"active_candidates={len(ctx.active_candidates or ctx.scoring.active_candidates)}, "
                    f"selected={ctx.scoring.selected_idea_id or 'none'}, "
                    f"hold={len(ctx.scoring.hold)}, "
                    f"kill={len(ctx.scoring.killed)}"
                )
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
                return (
                    f"proof={len(ctx.argument_map.proof_anchors)}, "
                    f"claims={len(ctx.argument_map.safe_claims)}, "
                    f"beats={len(ctx.argument_map.beat_claim_plan)}"
                )
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
                return f"approved={ctx.qc_gate.approved_for_publish}"
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
        """Build structured metadata for a pipeline stage trace."""
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
                meta.is_degraded = ctx.scoring.is_degraded
                meta.degradation_reason = ctx.scoring.degradation_reason
        elif stage == "generate_angles":
            if ctx.angles:
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
        elif stage == "run_scripting":
            if ctx.scripting:
                meta.selected_idea_id = _resolve_selected_idea_id(ctx)
                angle = _resolve_selected_angle(ctx)
                meta.selected_angle_id = getattr(angle, "angle_id", "")
                if ctx.scripting.step_traces:
                    meta.step_count = len(ctx.scripting.step_traces)
                    meta.llm_call_count = sum(
                        len(st.llm_calls) for st in ctx.scripting.step_traces
                    )
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
        elif stage == "publish_queue":
            if ctx.publish_items:
                meta.selected_idea_id = ctx.publish_items[0].idea_id or _resolve_selected_idea_id(ctx)
                meta.platforms_count = len(ctx.publish_items)
            elif ctx.publish_item:
                meta.selected_idea_id = ctx.publish_item.idea_id or _resolve_selected_idea_id(ctx)
        elif stage == "human_qc" and ctx.qc_gate:
            meta.approved = ctx.qc_gate.approved_for_publish
        elif stage == "performance_analysis" and ctx.performance:
            meta.is_degraded = ctx.performance.is_degraded
            meta.degradation_reason = ctx.performance.degradation_reason

        if ctx.iteration_state:
            meta.current_iteration = ctx.iteration_state.current_iteration
            if ctx.iteration_state.quality_history:
                meta.latest_quality_score = ctx.iteration_state.quality_history[-1].overall_quality_score
            meta.should_rerun_research = ctx.iteration_state.should_rerun_research

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

        if stage == "build_backlog" and ctx.backlog and ctx.backlog.is_degraded:
            reason = ctx.backlog.degradation_reason or "Backlog completed with degraded output."
            warnings.append(f"Backlog degraded: {reason}")
        elif stage == "score_ideas" and ctx.scoring and ctx.scoring.is_degraded:
            reason = ctx.scoring.degradation_reason or "Scoring completed with degraded output."
            warnings.append(f"Scoring degraded: {reason}")
        elif stage == "human_qc" and ctx.qc_gate and ctx.qc_gate.must_fix_items:
            warnings.append(
                f"Human QC blocked publish until {len(ctx.qc_gate.must_fix_items)} must-fix item(s) are resolved."
            )
        elif stage == "build_argument_map" and ctx.argument_map and ctx.argument_map.unsafe_claims:
            warnings.append(
                f"Argument map flagged {len(ctx.argument_map.unsafe_claims)} unsafe claim(s) to avoid in scripting."
            )
        elif stage == "build_research_pack" and ctx.research_pack and ctx.research_pack.is_degraded:
            reason = ctx.research_pack.degradation_reason or "Research pack completed with degraded output."
            warnings.append(f"Research pack degraded: {reason}")
        elif stage == "production_brief" and ctx.production_brief and ctx.production_brief.is_degraded:
            reason = ctx.production_brief.degradation_reason or "Production brief completed with degraded output."
            warnings.append(f"Production brief degraded: {reason}")
        elif stage == "publish_queue":
            has_items = ctx.publish_items or (ctx.publish_item is not None)
            if not has_items:
                warnings.append("Publish queue produced no items; upstream dependency may be incomplete.")
        elif stage == "performance_analysis" and ctx.performance and ctx.performance.is_degraded:
            reason = ctx.performance.degradation_reason or "Performance analysis completed with degraded output."
            warnings.append(f"Performance analysis degraded: {reason}")

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
        if stage == "generate_angles" and ctx.angles:
            return ctx.angles.selection_reasoning
        if stage == "build_research_pack" and ctx.research_pack:
            return ctx.research_pack.research_stop_reason
        if stage == "build_argument_map" and ctx.argument_map:
            return ctx.argument_map.thesis
        if stage == "human_qc" and ctx.qc_gate:
            if ctx.qc_gate.approved_for_publish:
                return "Human QC approved the package for publish."
            if ctx.qc_gate.must_fix_items:
                return f"Human QC requires {len(ctx.qc_gate.must_fix_items)} must-fix item(s) before publish."
            return "Human QC review completed without approval."
        if stage == "run_scripting" and ctx.scripting and ctx.scripting.angle:
            return ctx.scripting.angle.why_it_works
        return ""

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
        return await agent.build_backlog(theme, strategy, count=count, opportunity_brief=opportunity_brief)

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
        self, script: Any, angle: Any, *, platforms: list[str] | None = None, idea_id: str = ""
    ) -> Any:
        from cc_deep_research.content_gen.storage import StrategyStore

        store = StrategyStore()
        strategy = store.load()
        agent = self._get_agent("packaging")
        p = platforms or self._config.content_gen.default_platforms
        return await agent.generate(script, angle, p, strategy=strategy, idea_id=idea_id)

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
        agent = self._get_agent("performance")
        return await agent.analyze(
            video_id=video_id, metrics=metrics, script=script, hook=hook, caption=caption
        )

    # ------------------------------------------------------------------
    # Legacy scripting methods (preserved exactly)
    # ------------------------------------------------------------------

    async def run_scripting(
        self,
        raw_idea: str,
        progress_callback: Callable[[int, str], None] | None = None,
        *,
        llm_route: str | None = None,
    ) -> ScriptingContext:
        """Run the full 10-step scripting pipeline."""
        from cc_deep_research.content_gen.agents.scripting import ScriptingAgent

        agent = ScriptingAgent(self._config, llm_route=llm_route)
        return await agent.run_pipeline(raw_idea, progress_callback=progress_callback)

    async def run_scripting_from_step(
        self,
        ctx: ScriptingContext,
        step: int,
        progress_callback: Callable[[int, str], None] | None = None,
        *,
        llm_route: str | None = None,
    ) -> ScriptingContext:
        """Resume the scripting pipeline from a specific step."""
        from cc_deep_research.content_gen.agents.scripting import ScriptingAgent

        agent = ScriptingAgent(self._config, llm_route=llm_route)
        return await agent.run_from_step(ctx, step, progress_callback=progress_callback)

    async def run_scripting_iterative(
        self,
        raw_idea: str,
        progress_callback: Callable[[int, str], None] | None = None,
        max_iterations: int | None = None,
        *,
        llm_route: str | None = None,
    ) -> tuple[ScriptingContext, IterationState]:
        """Run the scripting pipeline inside an evaluation loop.

        Iteration 1 runs the full pipeline.  Subsequent iterations inject
        feedback into research_context and re-run from step 5 (hooks) onward.
        """
        from cc_deep_research.content_gen.agents.scripting import ScriptingAgent
        from cc_deep_research.content_gen.iterative_loop import (
            LoopConfig,
            run_evaluation_loop,
        )

        agent = ScriptingAgent(self._config, llm_route=llm_route)
        evaluator_agent = self._get_agent("quality_evaluator")
        threshold = self._config.content_gen.quality_threshold
        latest_ctx: ScriptingContext | None = None

        async def producer(feedback: str) -> ScriptingContext:
            nonlocal latest_ctx
            if latest_ctx is None:
                latest_ctx = await agent.run_pipeline(
                    raw_idea,
                    progress_callback=progress_callback,
                    iteration=1,
                )
            else:
                if feedback:
                    existing = latest_ctx.research_context or ""
                    latest_ctx.research_context = f"{feedback}\n\n{existing}"
                latest_ctx = await agent.run_from_step(
                    latest_ctx,
                    5,
                    progress_callback=progress_callback,
                    iteration=latest_ctx.step_traces[-1].iteration + 1 if latest_ctx.step_traces else 2,
                )
            return latest_ctx

        async def evaluator(
            artifact: ScriptingContext, iteration: int, prev_feedback: str
        ) -> QualityEvaluation:
            return await evaluator_agent.evaluate_scripting(
                scripting=artifact,
                iteration_number=iteration,
                quality_threshold=threshold,
                previous_feedback=prev_feedback,
            )

        loop_config = LoopConfig(
            max_iterations=max_iterations or self._config.content_gen.max_iterations,
            quality_threshold=threshold,
            convergence_threshold=self._config.content_gen.convergence_threshold,
        )

        result = await run_evaluation_loop(
            producer=producer,
            evaluator=evaluator,
            config=loop_config,
            progress_callback=progress_callback,
        )
        return result.artifact, result.iteration_state

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


# ---------------------------------------------------------------------------
# Pipeline stage handlers
# ---------------------------------------------------------------------------


async def _stage_load_strategy(
    _orch: ContentGenOrchestrator, ctx: PipelineContext
) -> PipelineContext:
    from cc_deep_research.content_gen.storage import StrategyStore

    store = StrategyStore()
    ctx.strategy = store.load()
    return ctx


async def _stage_plan_opportunity(
    orch: ContentGenOrchestrator, ctx: PipelineContext
) -> PipelineContext:
    agent = orch._get_agent("opportunity")
    ctx.opportunity_brief = await agent.plan(ctx.theme, ctx.strategy or StrategyMemory())
    return ctx


async def _stage_build_backlog(
    orch: ContentGenOrchestrator, ctx: PipelineContext
) -> PipelineContext:
    from cc_deep_research.content_gen.backlog_service import BacklogService

    agent = orch._get_agent("backlog")
    ctx.backlog = await agent.build_backlog(
        ctx.theme,
        ctx.strategy or StrategyMemory(),
        opportunity_brief=ctx.opportunity_brief,
    )
    service = BacklogService(orch._config)
    ctx.backlog = service.persist_generated(
        ctx.backlog,
        theme=ctx.theme,
        source_pipeline_id=ctx.pipeline_id,
    )
    return ctx


async def _stage_score_ideas(orch: ContentGenOrchestrator, ctx: PipelineContext) -> PipelineContext:
    from cc_deep_research.content_gen.backlog_service import BacklogService

    if ctx.backlog is None:
        return ctx
    if not ctx.backlog.items:
        ctx.scoring = ScoringOutput(is_degraded=True, degradation_reason="backlog has zero items")
        ctx.shortlist = []
        ctx.selected_idea_id = ""
        ctx.selection_reasoning = ""
        ctx.runner_up_idea_ids = []
        ctx.active_candidates = []
        ctx.lane_contexts = []
        return ctx
    agent = orch._get_agent("backlog")
    strategy = ctx.strategy or StrategyMemory()
    threshold = orch._config.content_gen.scoring_threshold_produce
    ctx.scoring = await agent.score_ideas(ctx.backlog.items, strategy, threshold=threshold)
    ctx.shortlist = ctx.scoring.shortlist
    ctx.selected_idea_id = ctx.scoring.selected_idea_id
    ctx.selection_reasoning = ctx.scoring.selection_reasoning
    ctx.runner_up_idea_ids = ctx.scoring.runner_up_idea_ids
    ctx.active_candidates = list(ctx.scoring.active_candidates)
    ctx = PipelineContext.model_validate(ctx.model_dump())
    BacklogService(getattr(orch, "_config", None)).apply_scoring(ctx.scoring)
    return ctx


async def _stage_generate_angles(
    orch: ContentGenOrchestrator, ctx: PipelineContext
) -> PipelineContext:
    candidates = _lane_candidates(ctx)
    if not candidates:
        return ctx
    strategy = ctx.strategy or StrategyMemory()
    agent = orch._get_agent("angle")
    for candidate in candidates:
        item = _resolve_lane_item(ctx, candidate.idea_id)
        if item is None:
            continue
        angles = await agent.generate(item, strategy)
        _record_lane_completion(ctx, candidate, stage_index=4, stage_field="angles", value=angles)
    return ctx


async def _stage_build_research_pack(
    orch: ContentGenOrchestrator, ctx: PipelineContext
) -> PipelineContext:
    if ctx.backlog is None:
        return ctx
    candidates = _lane_candidates(ctx)
    if not candidates:
        return ctx
    agent = orch._get_agent("research")
    for candidate in candidates:
        item = _resolve_lane_item(ctx, candidate.idea_id)
        angle = _resolve_lane_angle(ctx, candidate.idea_id)
        if item is None or angle is None:
            continue
        feedback = ""
        research_gaps: list[str] | None = None
        if candidate.role == "primary" and ctx.iteration_state and ctx.iteration_state.should_rerun_research:
            if ctx.iteration_state.latest_feedback:
                feedback = ctx.iteration_state.latest_feedback
            if ctx.iteration_state.quality_history:
                latest_eval = ctx.iteration_state.quality_history[-1]
                research_gaps = list(latest_eval.research_gaps_identified)
            # Task 18: also pull in targeted retrieval gaps from revision plan
            if ctx.iteration_state.targeted_revision_plan:
                plan = ctx.iteration_state.targeted_revision_plan
                targeted_gaps = orch._extract_retrieval_gaps(plan)
                if targeted_gaps:
                    research_gaps = (research_gaps or []) + targeted_gaps
        research_pack = await agent.build(item, angle, feedback=feedback, research_gaps=research_gaps)
        _record_lane_completion(
            ctx,
            candidate,
            stage_index=5,
            stage_field="research_pack",
            value=research_pack,
        )
    return ctx


async def _stage_build_argument_map(
    orch: ContentGenOrchestrator, ctx: PipelineContext
) -> PipelineContext:
    if ctx.backlog is None:
        return ctx
    candidates = _lane_candidates(ctx)
    if not candidates:
        return ctx
    agent = orch._get_agent("argument_map")
    for candidate in candidates:
        lane = _resolve_lane_context(ctx, candidate.idea_id)
        item = _resolve_lane_item(ctx, candidate.idea_id)
        angle = _resolve_lane_angle(ctx, candidate.idea_id)
        if lane is None or lane.research_pack is None or item is None or angle is None:
            continue
        argument_map = await agent.build(item, angle, lane.research_pack)
        _record_lane_completion(
            ctx,
            candidate,
            stage_index=6,
            stage_field="argument_map",
            value=argument_map,
        )
    return ctx


async def _stage_run_scripting(
    orch: ContentGenOrchestrator, ctx: PipelineContext
) -> PipelineContext:
    from cc_deep_research.content_gen.backlog_service import BacklogService

    if ctx.backlog is None:
        return ctx
    candidates = _lane_candidates(ctx)
    if not candidates:
        return ctx
    agent = orch._get_agent("scripting")
    service: BacklogService | None = None
    for candidate in candidates:
        lane = _resolve_lane_context(ctx, candidate.idea_id)
        item = _resolve_lane_item(ctx, candidate.idea_id)
        angle = _resolve_lane_angle(ctx, candidate.idea_id)
        if lane is None or lane.argument_map is None:
            continue
        raw_idea = item.idea if item else ctx.theme
        existing_research = ""
        if lane.scripting and lane.scripting.research_context:
            existing_research = lane.scripting.research_context
        research_context = existing_research or _format_research_context(lane.research_pack)
        seeded_ctx = ScriptingContext(
            raw_idea=raw_idea,
            research_context=research_context,
            tone=(angle.tone if angle else ""),
            cta=(angle.cta if angle else ""),
            argument_map=lane.argument_map,
            core_inputs=CoreInputs(
                topic=item.idea if item else raw_idea,
                outcome=((angle.primary_takeaway if angle else "") or (item.problem if item else raw_idea)),
                audience=((angle.target_audience if angle else "") or (item.audience if item else "")),
            ),
            angle=AngleDefinition(
                angle=(angle.core_promise if angle else "") or raw_idea,
                content_type=((angle.format if angle else "") or (angle.lens if angle else "") or "Insight"),
                core_tension=((angle.viewer_problem if angle else "") or (item.problem if item else "") or raw_idea),
                why_it_works=(angle.why_this_version_should_exist if angle else ""),
            ),
            structure=_seed_structure_from_argument_map(lane.argument_map),
            beat_intents=_seed_beat_intents_from_argument_map(lane.argument_map),
        )
        start_step = 5 if seeded_ctx.structure and seeded_ctx.beat_intents else 3
        scripting = await agent.run_from_step(seeded_ctx, start_step)

        # Build claim traceability ledger
        claim_ledger = _build_claim_ledger(lane.research_pack, lane.argument_map, scripting)
        scripting.claim_ledger = claim_ledger

        _record_lane_completion(
            ctx,
            candidate,
            stage_index=7,
            stage_field="scripting",
            value=scripting,
        )
        if service is None:
            service = BacklogService(getattr(orch, "_config", None))
        service.mark_in_production(candidate.idea_id, source_pipeline_id=ctx.pipeline_id)
        _update_candidate_status(ctx, candidate.idea_id, "in_production")
    return ctx


async def _stage_visual_translation(
    orch: ContentGenOrchestrator, ctx: PipelineContext
) -> PipelineContext:
    candidates = _lane_candidates(ctx)
    if not candidates:
        return ctx
    agent = orch._get_agent("visual")
    for candidate in candidates:
        lane = _resolve_lane_context(ctx, candidate.idea_id)
        if lane is None or lane.scripting is None:
            continue
        source = lane.scripting.tightened or lane.scripting.annotated_script or lane.scripting.draft
        structure = lane.scripting.structure
        if source is None or structure is None:
            continue
        visual_plan = await agent.translate(source, structure)
        _record_lane_completion(
            ctx,
            candidate,
            stage_index=8,
            stage_field="visual_plan",
            value=visual_plan,
        )
    return ctx


async def _stage_production_brief(
    orch: ContentGenOrchestrator, ctx: PipelineContext
) -> PipelineContext:
    candidates = _lane_candidates(ctx)
    if not candidates:
        return ctx
    agent = orch._get_agent("production")
    for candidate in candidates:
        lane = _resolve_lane_context(ctx, candidate.idea_id)
        if lane is None or lane.visual_plan is None:
            continue
        production_brief = await agent.brief(lane.visual_plan)
        _record_lane_completion(
            ctx,
            candidate,
            stage_index=9,
            stage_field="production_brief",
            value=production_brief,
        )
    return ctx


async def _stage_packaging(orch: ContentGenOrchestrator, ctx: PipelineContext) -> PipelineContext:
    candidates = _lane_candidates(ctx)
    if not candidates:
        return ctx
    agent = orch._get_agent("packaging")
    platforms = orch._config.content_gen.default_platforms
    strategy = ctx.strategy or StrategyMemory()
    for candidate in candidates:
        lane = _resolve_lane_context(ctx, candidate.idea_id)
        angle = _resolve_lane_angle(ctx, candidate.idea_id)
        if lane is None or lane.scripting is None or angle is None:
            continue
        source = lane.scripting.qc.final_script if lane.scripting.qc else ""
        if not source:
            source = lane.scripting.tightened.content if lane.scripting.tightened else ""
        if not source:
            source = lane.scripting.draft.content if lane.scripting.draft else ""
        if not source:
            continue
        script = ScriptVersion(content=source, word_count=len(source.split()))
        packaging = await agent.generate(script, angle, platforms, strategy=strategy)
        _record_lane_completion(
            ctx,
            candidate,
            stage_index=10,
            stage_field="packaging",
            value=packaging,
        )
    return ctx


async def _stage_human_qc(orch: ContentGenOrchestrator, ctx: PipelineContext) -> PipelineContext:
    candidates = _lane_candidates(ctx)
    if not candidates:
        return ctx
    agent = orch._get_agent("qc")
    for candidate in candidates:
        lane = _resolve_lane_context(ctx, candidate.idea_id)
        if lane is None or lane.scripting is None:
            continue
        script = lane.scripting.qc.final_script if lane.scripting.qc else ""
        if not script:
            script = lane.scripting.tightened.content if lane.scripting.tightened else ""
        if not script:
            script = lane.scripting.draft.content if lane.scripting.draft else ""
        if not script:
            continue
        visual_summary = ""
        if lane.visual_plan:
            visual_summary = "; ".join(f"{bv.beat}: {bv.visual}" for bv in lane.visual_plan.visual_plan[:5])
        packaging_summary = ""
        if lane.packaging:
            parts = [f"{p.platform}: {p.primary_hook}" for p in lane.packaging.platform_packages]
            packaging_summary = "; ".join(parts)
        research_summary = _format_qc_research_summary(lane.research_pack)
        argument_map_summary = _format_qc_argument_map_summary(lane.argument_map)

        # Build claim traceability summary from ledger
        claim_trace_summary = ""
        if lane.scripting and lane.scripting.claim_ledger:
            ledger = lane.scripting.claim_ledger
            claim_trace_parts = ["Claim Traceability Analysis:"]
            if ledger.unsupported_script_claims:
                claim_trace_parts.append(f"Unsupported claims detected: {len(ledger.unsupported_script_claims)}")
                claim_trace_parts.extend(f"- {c}" for c in ledger.unsupported_claims_for_qc()[:5])
            if ledger.introduced_late_claims:
                claim_trace_parts.append(f"Introduced late (not in argument map): {len(ledger.introduced_late_claims)}")
            if ledger.dropped_claims:
                claim_trace_parts.append(f"Dropped from argument map: {len(ledger.dropped_claims)}")
            if ledger.weakened_claims:
                claim_trace_parts.append(f"Lost proof support: {len(ledger.weakened_claims)}")
            claim_trace_summary = "\n".join(claim_trace_parts)
            if claim_trace_summary == "Claim Traceability Analysis:":
                claim_trace_summary = "Claim Traceability Analysis: All script claims traceable to argument map."

        # Combine summaries, with claim traceability first as it's most important for QC
        full_research_summary = claim_trace_summary + "\n\n" + research_summary if claim_trace_summary else research_summary

        qc_gate = await agent.review(
            script=script,
            visual_summary=visual_summary,
            packaging_summary=packaging_summary,
            research_summary=full_research_summary,
            argument_map_summary=argument_map_summary,
        )
        _record_lane_completion(
            ctx,
            candidate,
            stage_index=11,
            stage_field="qc_gate",
            value=qc_gate,
        )
    return ctx


async def _stage_publish_queue(
    orch: ContentGenOrchestrator, ctx: PipelineContext
) -> PipelineContext:
    from cc_deep_research.content_gen.backlog_service import BacklogService

    candidates = _lane_candidates(ctx)
    if not candidates:
        return ctx
    agent = orch._get_agent("publish")
    service: BacklogService | None = None
    for candidate in candidates:
        lane = _resolve_lane_context(ctx, candidate.idea_id)
        if (
            lane is None
            or lane.packaging is None
            or lane.qc_gate is None
            or not lane.qc_gate.approved_for_publish
        ):
            continue
        items = await agent.schedule(lane.packaging, idea_id=candidate.idea_id)
        _record_lane_completion(
            ctx,
            candidate,
            stage_index=12,
            stage_field="publish_items",
            value=items,
        )
        if items:
            if service is None:
                service = BacklogService(getattr(orch, "_config", None))
            service.mark_published(candidate.idea_id, source_pipeline_id=ctx.pipeline_id)
            _update_candidate_status(ctx, candidate.idea_id, "published")
    _sync_primary_lane(ctx)
    return ctx


async def _stage_performance(
    _orch: ContentGenOrchestrator, ctx: PipelineContext
) -> PipelineContext:
    # Performance analysis requires metrics from the human — skip in auto pipeline
    return ctx


_PIPELINE_HANDLERS = [
    _stage_load_strategy,
    _stage_plan_opportunity,
    _stage_build_backlog,
    _stage_score_ideas,
    _stage_generate_angles,
    _stage_build_research_pack,
    _stage_build_argument_map,
    _stage_run_scripting,
    _stage_visual_translation,
    _stage_production_brief,
    _stage_packaging,
    _stage_human_qc,
    _stage_publish_queue,
    _stage_performance,
]


def _format_research_context(research_pack: ResearchPack | None) -> str:
    if research_pack is None:
        return ""

    sections: list[str] = []
    if research_pack.audience_insights:
        sections.append("Audience insights:\n- " + "\n- ".join(research_pack.audience_insights[:3]))
    if research_pack.key_facts:
        sections.append("Key facts:\n- " + "\n- ".join(research_pack.key_facts[:3]))
    if research_pack.proof_points:
        sections.append("Proof points:\n- " + "\n- ".join(research_pack.proof_points[:5]))
    if research_pack.examples:
        sections.append("Examples:\n- " + "\n- ".join(research_pack.examples[:3]))
    if research_pack.case_studies:
        sections.append("Case studies:\n- " + "\n- ".join(research_pack.case_studies[:2]))
    if research_pack.gaps_to_exploit:
        sections.append("Competitor gaps:\n- " + "\n- ".join(research_pack.gaps_to_exploit[:2]))
    if research_pack.claims_requiring_verification:
        sections.append(
            "Claims requiring verification:\n- "
            + "\n- ".join(research_pack.claims_requiring_verification[:3])
        )
    if research_pack.unsafe_or_uncertain_claims:
        sections.append(
            "Unsafe or uncertain claims:\n- "
            + "\n- ".join(research_pack.unsafe_or_uncertain_claims[:3])
        )

    return "\n\n".join(sections)


def _format_qc_research_summary(research_pack: ResearchPack | None) -> str:
    if research_pack is None:
        return ""

    sections: list[str] = []
    if research_pack.claims:
        sections.append(
            "Supported claims:\n- "
            + "\n- ".join(claim.claim for claim in research_pack.claims[:4] if claim.claim)
        )
    else:
        if research_pack.key_facts:
            sections.append("Key facts:\n- " + "\n- ".join(research_pack.key_facts[:3]))
        if research_pack.proof_points:
            sections.append("Proof points:\n- " + "\n- ".join(research_pack.proof_points[:3]))
    if research_pack.claims_requiring_verification:
        sections.append(
            "Claims requiring verification:\n- "
            + "\n- ".join(research_pack.claims_requiring_verification[:3])
        )
    if research_pack.unsafe_or_uncertain_claims:
        sections.append(
            "Unsafe or uncertain claims:\n- "
            + "\n- ".join(research_pack.unsafe_or_uncertain_claims[:3])
        )
    return "\n\n".join(sections)


def _format_qc_argument_map_summary(argument_map: ArgumentMap | None) -> str:
    if argument_map is None:
        return ""

    sections: list[str] = []
    if argument_map.thesis:
        sections.append(f"Thesis: {argument_map.thesis}")
    if argument_map.safe_claims:
        safe_claims = [claim.claim for claim in argument_map.safe_claims[:4] if claim.claim]
        if safe_claims:
            sections.append("Safe claims:\n- " + "\n- ".join(safe_claims))
    if argument_map.unsafe_claims:
        unsafe_claims = [claim.claim for claim in argument_map.unsafe_claims[:3] if claim.claim]
        if unsafe_claims:
            sections.append("Claims to qualify or avoid:\n- " + "\n- ".join(unsafe_claims))
    if argument_map.proof_anchors:
        proof_anchors = [anchor.summary for anchor in argument_map.proof_anchors[:4] if anchor.summary]
        if proof_anchors:
            sections.append("Proof anchors:\n- " + "\n- ".join(proof_anchors))
    return "\n\n".join(sections)
