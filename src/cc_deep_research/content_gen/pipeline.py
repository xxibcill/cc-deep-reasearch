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
from cc_deep_research.content_gen.lifecycle import (
    StageGatePolicy,
    StagePrerequisitePolicy,
    StageTracePolicy,
)
from cc_deep_research.content_gen.models.pipeline import (
    PIPELINE_STAGE_LABELS,
    PIPELINE_STAGES,
    PipelineContext,
    PipelineStageTrace,
    get_phase_for_stage,
    get_phase_policy,
)
from cc_deep_research.content_gen.models.production import RunConstraints

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
    lane = next((lane_ctx for lane_ctx in ctx.lane_contexts if lane_ctx.idea_id == idea_id), None)
    if lane is None:
        return None
    # P3-T2: Check thesis_artifact first
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


def _resolve_lane_context(ctx: PipelineContext, idea_id: str) -> Any | None:
    return next((lane for lane in ctx.lane_contexts if lane.idea_id == idea_id), None)


def _ensure_lane_context(ctx: PipelineContext, idea_id: str, role: str, status: str) -> Any:
    """Ensure a lane context exists for the given idea_id."""
    lane = _resolve_lane_context(ctx, idea_id)
    if lane is not None:
        lane.role = role
        lane.status = status
        return lane
    from cc_deep_research.content_gen.models.pipeline import PipelineLaneContext
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
    from cc_deep_research.content_gen.models.backlog import PipelineCandidate
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
        (lane_ctx for lane_ctx in ctx.lane_contexts if lane_ctx.role == "primary"),
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
    from cc_deep_research.content_gen.models.production import get_content_type_profile
    profile = get_content_type_profile(ctx.run_constraints.content_type)
    return profile.use_combined_execution_brief


def _lane_publish_prereqs_met(ctx: PipelineContext) -> bool:
    from cc_deep_research.content_gen.models.shared import ReleaseState
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
        self._prereq_policy = StagePrerequisitePolicy()
        self._gate_policy = StageGatePolicy(config)
        self._trace_policy = StageTracePolicy()

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
        brief_snapshot: Any | None = None,
        run_constraints: RunConstraints | None = None,
    ) -> PipelineContext:
        """Run a pipeline through the stage coordinator without legacy dispatch."""
        del brief_id, brief_snapshot
        ctx = self._initial_context(theme, initial_context, run_constraints)
        final_stage = to_stage if to_stage is not None else len(PIPELINE_STAGES) - 1

        for stage_index in self._stage_indices(from_stage, final_stage, bypass_ideation):
            ctx = await self.run_stage(
                stage_index,
                ctx,
                progress_callback=progress_callback,
                stage_completed_callback=stage_completed_callback,
            )
        return ctx

    def validate_resume_context(
        self,
        *,
        from_stage: int,
        ctx: PipelineContext,
        bypass_ideation: bool = False,
    ) -> str | None:
        """Return a validation message when a saved context cannot be resumed."""
        del ctx
        if from_stage < 0 or from_stage >= len(PIPELINE_STAGES):
            return f"from_stage must be between 0 and {len(PIPELINE_STAGES) - 1}."
        if bypass_ideation and 1 <= from_stage <= 3:
            return (
                "--idea bypasses stages 1-3; use --from-stage 0 to reload strategy "
                "or resume from stage 4 or later."
            )
        return None

    def _initial_context(
        self,
        theme: str,
        initial_context: PipelineContext | None,
        run_constraints: RunConstraints | None,
    ) -> PipelineContext:
        if initial_context is None:
            ctx = PipelineContext(theme=theme, created_at=datetime.now(tz=UTC).isoformat())
        else:
            ctx = initial_context.model_copy(deep=True)
            if theme and not ctx.theme:
                ctx.theme = theme
            if not ctx.created_at:
                ctx.created_at = datetime.now(tz=UTC).isoformat()

        if run_constraints is not None:
            ctx.run_constraints = run_constraints
        elif ctx.run_constraints is None:
            ctx.run_constraints = RunConstraints()
        return ctx

    def _stage_indices(
        self,
        from_stage: int,
        to_stage: int,
        bypass_ideation: bool,
    ) -> list[int]:
        final_stage = min(to_stage, len(PIPELINE_STAGES) - 1)
        if not bypass_ideation:
            return list(range(from_stage, final_stage + 1))

        indices: list[int] = []
        if from_stage == 0 and final_stage >= 0:
            indices.append(0)
        indices.extend(range(max(from_stage, 4), final_stage + 1))
        return indices

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
        input_summary = self._trace_policy.summarize_input(stage_index, ctx)

        prereqs_met, skip_reason = self._prereq_policy.check(stage_index, ctx)
        if not prereqs_met:
            warnings = self._trace_policy.collect_warnings(stage_index, ctx, status="skipped", detail=skip_reason)
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
                decision_summary=self._trace_policy.build_decision_summary(stage_index, ctx, status="skipped", detail=skip_reason),
                metadata=self._trace_policy.build_trace_metadata(stage_index, ctx),
            )
            ctx.stage_traces.append(trace)
            if stage_completed_callback:
                stage_completed_callback(stage_index, "skipped", skip_reason, ctx)
            return ctx

        gate_ok, gate_message = self._gate_policy.check(ctx, stage_name)
        if not gate_ok:
            warnings = self._trace_policy.collect_warnings(stage_index, ctx, status="blocked", detail=gate_message)
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
                metadata=self._trace_policy.build_trace_metadata(stage_index, ctx),
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
            output_summary = self._trace_policy.summarize_output(stage_index, ctx)
            warnings = self._trace_policy.collect_warnings(stage_index, ctx, status=status)
            if ctx.brief_gate and ctx.brief_gate.warnings:
                warnings = warnings + [f"Brief gate: {w}" for w in ctx.brief_gate.warnings]
            decision_summary = self._trace_policy.build_decision_summary(stage_index, ctx, status=status)
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
                metadata=self._trace_policy.build_trace_metadata(stage_index, ctx),
            )
            ctx.stage_traces.append(trace)
            if stage_completed_callback:
                stage_completed_callback(stage_index, "failed", "CancelledError", ctx)
            raise
        except Exception as e:
            status = "failed"
            output_summary = str(e)
            warnings = self._trace_policy.collect_warnings(stage_index, ctx, status=status, detail=str(e))
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
                decision_summary=self._trace_policy.build_decision_summary(stage_index, ctx, status=status, detail=str(e)),
                metadata=self._trace_policy.build_trace_metadata(stage_index, ctx),
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
            metadata=self._trace_policy.build_trace_metadata(stage_index, ctx),
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
