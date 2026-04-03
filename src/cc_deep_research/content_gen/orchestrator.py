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
    CoreInputs,
    IterationState,
    OpportunityBrief,
    PipelineContext,
    PipelineStageTrace,
    QualityEvaluation,
    ResearchPack,
    ScoringOutput,
    ScriptingContext,
    ScriptVersion,
    StrategyMemory,
)

if TYPE_CHECKING:
    from cc_deep_research.config import Config

logger = logging.getLogger(__name__)


def _selected_idea_candidates(ctx: PipelineContext) -> list[str]:
    candidates: list[str] = []
    if ctx.selected_idea_id:
        candidates.append(ctx.selected_idea_id)
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
        progress_callback: Callable[[int, str], None] | None = None,
        stage_completed_callback: Callable[[int, str, str], None] | None = None,
    ) -> PipelineContext:
        """Run the full 13-stage content pipeline with iterative quality loop.

        Phases:
          1. Stages 0-4 (ideation) — run once
          2. Stages 5-10 (content) — iterative loop with quality evaluation
          3. Stages 11-12 (publish) — run once after loop exits
        """
        ctx = PipelineContext(
            theme=theme,
            created_at=datetime.now(tz=UTC).isoformat(),
            iteration_state=IterationState(
                max_iterations=self._config.content_gen.max_iterations,
            ),
        )
        end = to_stage if to_stage is not None else len(PIPELINE_STAGES) - 1

        # Phase 1: Ideation stages (0-4) — run once
        for idx in range(from_stage, min(5, end + 1)):
            ctx = await self._run_stage(idx, ctx, progress_callback, stage_completed_callback)

        # Phase 2: Content stages (5-10) — iterative or single-pass
        if self._config.content_gen.enable_iterative_mode and end >= 6 and from_stage <= 5:
            ctx = await self._run_iterative_loop(ctx, progress_callback, end, stage_completed_callback)
        else:
            for idx in range(max(5, from_stage), min(11, end + 1)):
                ctx = await self._run_stage(idx, ctx, progress_callback, stage_completed_callback)

        # Phase 3: Post-content stages (11-12) — run once
        for idx in range(11, end + 1):
            ctx = await self._run_stage(idx, ctx, progress_callback, stage_completed_callback)

        return ctx

    def _check_prerequisites(self, idx: int, ctx: PipelineContext) -> tuple[bool, str]:
        """Check if prerequisites for a stage are met. Returns (met, reason_if_not)."""
        stage = PIPELINE_STAGES[idx]
        if stage == "score_ideas":
            if ctx.backlog is None:
                return False, "backlog missing"
        if stage == "generate_angles":
            if ctx.backlog is None:
                return False, "backlog missing"
            if _resolve_selected_item(ctx) is None:
                return False, "scoring/selected idea missing"
        if stage == "build_research_pack":
            if ctx.backlog is None or ctx.angles is None:
                return False, "backlog/angles missing"
            if _resolve_selected_item(ctx) is None:
                return False, "selected idea not found"
        if stage == "run_scripting":
            if ctx.backlog is None or ctx.angles is None:
                return False, "backlog/angles missing"
        if stage == "visual_translation":
            if ctx.scripting is None:
                return False, "scripting missing"
            source = ctx.scripting.tightened or ctx.scripting.annotated_script or ctx.scripting.draft
            if source is None or ctx.scripting.structure is None:
                return False, "script/structure incomplete"
        if stage == "production_brief":
            if ctx.visual_plan is None:
                return False, "visual_plan missing"
        if stage == "packaging":
            if ctx.scripting is None or ctx.angles is None:
                return False, "scripting/angles missing"
            source = ""
            if ctx.scripting.qc:
                source = ctx.scripting.qc.final_script
            elif ctx.scripting.tightened:
                source = ctx.scripting.tightened.content
            elif ctx.scripting.draft:
                source = ctx.scripting.draft.content
            if not source:
                return False, "script empty"
        if stage == "human_qc":
            if ctx.scripting is None:
                return False, "scripting missing"
            source = ""
            if ctx.scripting.qc:
                source = ctx.scripting.qc.final_script
            elif ctx.scripting.tightened:
                source = ctx.scripting.tightened.content
            elif ctx.scripting.draft:
                source = ctx.scripting.draft.content
            if not source:
                return False, "script empty"
        if stage == "publish_queue":
            if ctx.packaging is None or ctx.qc_gate is None or not ctx.qc_gate.approved_for_publish:
                return False, "packaging/qc_gate missing or not approved"
        return True, ""

    async def _run_stage(
        self,
        idx: int,
        ctx: PipelineContext,
        progress_callback: Callable[[int, str], None] | None,
        stage_completed_callback: Callable[[int, str, str], None] | None = None,
    ) -> PipelineContext:
        stage_name = PIPELINE_STAGES[idx]
        label = PIPELINE_STAGE_LABELS.get(stage_name, stage_name)
        if progress_callback:
            progress_callback(idx, label)
        ctx.current_stage = idx

        started_at = datetime.now(tz=UTC).isoformat()
        input_summary = self._summarize_input(idx, ctx)

        prereqs_met, skip_reason = self._check_prerequisites(idx, ctx)
        if not prereqs_met:
            trace = PipelineStageTrace(
                stage_index=idx,
                stage_name=stage_name,
                stage_label=label,
                status="skipped",
                started_at=started_at,
                completed_at=datetime.now(tz=UTC).isoformat(),
                input_summary=input_summary,
                output_summary=skip_reason,
                decision_summary=f"Skipped: {skip_reason}",
            )
            ctx.stage_traces.append(trace)
            if stage_completed_callback:
                stage_completed_callback(idx, "skipped", skip_reason)
            return ctx

        try:
            ctx = await _PIPELINE_HANDLERS[idx](self, ctx)
            status = "completed"
            output_summary = self._summarize_output(idx, ctx)
            warnings: list[str] = []
        except Exception as e:
            status = "failed"
            output_summary = str(e)
            warnings = [f"Stage failed: {e}"]
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
            )
            ctx.stage_traces.append(trace)
            if stage_completed_callback:
                stage_completed_callback(idx, "failed", str(e))
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
        )
        ctx.stage_traces.append(trace)
        if stage_completed_callback:
            stage_completed_callback(idx, "completed", "")
        return ctx

    async def _run_iterative_loop(
        self,
        ctx: PipelineContext,
        progress_callback: Callable[[int, str], None] | None,
        end_stage: int,
        stage_completed_callback: Callable[[int, str, str], None] | None = None,
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

            # Re-run research if gaps were identified in previous iteration
            if iteration > 1 and iter_state.should_rerun_research:
                ctx = await self._run_stage(5, ctx, progress_callback, stage_completed_callback)
                iter_state.should_rerun_research = False

            # Run content stages 6-10
            for idx in range(6, min(11, end_stage + 1)):
                ctx = await self._run_stage(idx, ctx, progress_callback, stage_completed_callback)

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
            if quality_eval.research_gaps_identified:
                iter_state.should_rerun_research = True
            self._inject_feedback(ctx, quality_eval)
            iter_state.current_iteration += 1

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
        if quality_eval.critical_issues:
            parts.append("Critical issues:")
            parts.extend(f"- {i}" for i in quality_eval.critical_issues)
        if quality_eval.improvement_suggestions:
            parts.append("Improvement suggestions:")
            parts.extend(f"- {s}" for s in quality_eval.improvement_suggestions)
        if quality_eval.rationale:
            parts.append(f"Rationale: {quality_eval.rationale}")
        return "\n".join(parts)

    @staticmethod
    def _inject_feedback(ctx: PipelineContext, quality_eval: QualityEvaluation) -> None:
        if not ctx.scripting:
            return
        feedback_lines = [f"Iteration {quality_eval.iteration_number} feedback:"]
        if quality_eval.critical_issues:
            feedback_lines.append("Critical issues to fix:")
            feedback_lines.extend(f"- {i}" for i in quality_eval.critical_issues)
        if quality_eval.improvement_suggestions:
            feedback_lines.append("Improvement suggestions:")
            feedback_lines.extend(f"- {s}" for s in quality_eval.improvement_suggestions)
        feedback_text = "\n".join(feedback_lines)
        existing = ctx.scripting.research_context or ""
        ctx.scripting.research_context = f"{feedback_text}\n\n{existing}"

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
                    f"shortlist={len(ctx.shortlist or ctx.scoring.shortlist)}"
                )
            return "selected_idea_id=none, shortlist=0"
        if stage == "build_research_pack":
            if ctx.angles:
                return f"idea_id={_resolve_selected_idea_id(ctx) or 'none'}"
            return "idea_id=none"
        if stage == "run_scripting":
            if ctx.research_pack:
                return f"research_context={len(ctx.research_pack.key_facts)} facts"
            return "research_context=empty"
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
            if ctx.publish_item:
                return f"idea_id={ctx.publish_item.idea_id}, platform={ctx.publish_item.platform}"
            return "not_created"
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
        self, *, script: str, visual_summary: str = "", packaging_summary: str = ""
    ) -> Any:
        agent = self._get_agent("qc")
        return await agent.review(
            script=script, visual_summary=visual_summary, packaging_summary=packaging_summary
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
    agent = orch._get_agent("backlog")
    ctx.backlog = await agent.build_backlog(
        ctx.theme,
        ctx.strategy or StrategyMemory(),
        opportunity_brief=ctx.opportunity_brief,
    )
    if ctx.backlog and ctx.backlog.is_degraded and ctx.stage_traces:
        ctx.stage_traces[-1].warnings.append(f"Backlog degraded: {ctx.backlog.degradation_reason}")
    return ctx


async def _stage_score_ideas(orch: ContentGenOrchestrator, ctx: PipelineContext) -> PipelineContext:
    if ctx.backlog is None:
        return ctx
    if not ctx.backlog.items:
        ctx.scoring = ScoringOutput(is_degraded=True, degradation_reason="backlog has zero items")
        ctx.shortlist = []
        ctx.selected_idea_id = ""
        ctx.selection_reasoning = ""
        ctx.runner_up_idea_ids = []
        return ctx
    agent = orch._get_agent("backlog")
    strategy = ctx.strategy or StrategyMemory()
    threshold = orch._config.content_gen.scoring_threshold_produce
    ctx.scoring = await agent.score_ideas(ctx.backlog.items, strategy, threshold=threshold)
    ctx.shortlist = ctx.scoring.shortlist
    ctx.selected_idea_id = ctx.scoring.selected_idea_id
    ctx.selection_reasoning = ctx.scoring.selection_reasoning
    ctx.runner_up_idea_ids = ctx.scoring.runner_up_idea_ids
    if ctx.scoring and ctx.scoring.is_degraded and ctx.stage_traces:
        ctx.stage_traces[-1].warnings.append(f"Scoring degraded: {ctx.scoring.degradation_reason}")
    return ctx


async def _stage_generate_angles(
    orch: ContentGenOrchestrator, ctx: PipelineContext
) -> PipelineContext:
    item = _resolve_selected_item(ctx)
    if item is None:
        return ctx
    strategy = ctx.strategy or StrategyMemory()
    agent = orch._get_agent("angle")
    ctx.angles = await agent.generate(item, strategy)
    return ctx


async def _stage_build_research_pack(
    orch: ContentGenOrchestrator, ctx: PipelineContext
) -> PipelineContext:
    if ctx.backlog is None or ctx.angles is None:
        return ctx
    item = _resolve_selected_item(ctx)
    angle = _resolve_selected_angle(ctx)
    if item is None or angle is None:
        return ctx
    agent = orch._get_agent("research")
    feedback = ""
    if ctx.iteration_state and ctx.iteration_state.should_rerun_research and ctx.iteration_state.latest_feedback:
        feedback = ctx.iteration_state.latest_feedback
    ctx.research_pack = await agent.build(item, angle, feedback=feedback)
    return ctx


async def _stage_run_scripting(
    orch: ContentGenOrchestrator, ctx: PipelineContext
) -> PipelineContext:
    if ctx.backlog is None or ctx.angles is None:
        return ctx
    item = _resolve_selected_item(ctx)
    angle = _resolve_selected_angle(ctx)
    raw_idea = item.idea if item else ctx.theme
    agent = orch._get_agent("scripting")
    # Preserve existing research context (includes feedback from prior iterations)
    existing_research = ""
    if ctx.scripting and ctx.scripting.research_context:
        existing_research = ctx.scripting.research_context
    research_context = existing_research or _format_research_context(ctx.research_pack)
    seeded_ctx = ScriptingContext(
        raw_idea=raw_idea,
        research_context=research_context,
        tone=(angle.tone if angle else ""),
        cta=(angle.cta if angle else ""),
        core_inputs=CoreInputs(
            topic=item.idea if item else raw_idea,
            outcome=(
                (angle.primary_takeaway if angle else "")
                or (item.problem if item else raw_idea)
            ),
            audience=(
                (angle.target_audience if angle else "")
                or (item.audience if item else "")
            ),
        ),
        angle=AngleDefinition(
            angle=(angle.core_promise if angle else "") or raw_idea,
            content_type=(
                (angle.format if angle else "")
                or (angle.lens if angle else "")
                or "Insight"
            ),
            core_tension=(
                (angle.viewer_problem if angle else "")
                or (item.problem if item else "")
                or raw_idea
            ),
            why_it_works=(angle.why_this_version_should_exist if angle else ""),
        ),
    )
    ctx.scripting = await agent.run_from_step(seeded_ctx, 3)
    return ctx


async def _stage_visual_translation(
    orch: ContentGenOrchestrator, ctx: PipelineContext
) -> PipelineContext:
    if ctx.scripting is None:
        return ctx
    source = ctx.scripting.tightened or ctx.scripting.annotated_script or ctx.scripting.draft
    structure = ctx.scripting.structure
    if source is None or structure is None:
        return ctx
    agent = orch._get_agent("visual")
    ctx.visual_plan = await agent.translate(source, structure)
    return ctx


async def _stage_production_brief(
    orch: ContentGenOrchestrator, ctx: PipelineContext
) -> PipelineContext:
    if ctx.visual_plan is None:
        return ctx
    agent = orch._get_agent("production")
    ctx.production_brief = await agent.brief(ctx.visual_plan)
    return ctx


async def _stage_packaging(orch: ContentGenOrchestrator, ctx: PipelineContext) -> PipelineContext:
    if ctx.scripting is None or ctx.angles is None:
        return ctx
    source = ctx.scripting.qc.final_script if ctx.scripting.qc else ""
    if not source:
        source = ctx.scripting.tightened.content if ctx.scripting.tightened else ""
    if not source:
        source = ctx.scripting.draft.content if ctx.scripting.draft else ""
    if not source:
        return ctx

    script = ScriptVersion(content=source, word_count=len(source.split()))
    angle = _resolve_selected_angle(ctx)
    if angle is None:
        return ctx
    agent = orch._get_agent("packaging")
    platforms = orch._config.content_gen.default_platforms
    strategy = ctx.strategy or StrategyMemory()
    ctx.packaging = await agent.generate(script, angle, platforms, strategy=strategy)
    return ctx


async def _stage_human_qc(orch: ContentGenOrchestrator, ctx: PipelineContext) -> PipelineContext:
    if ctx.scripting is None:
        return ctx
    script = ctx.scripting.qc.final_script if ctx.scripting.qc else ""
    if not script:
        script = ctx.scripting.tightened.content if ctx.scripting.tightened else ""
    if not script:
        script = ctx.scripting.draft.content if ctx.scripting.draft else ""
    if not script:
        return ctx
    visual_summary = ""
    if ctx.visual_plan:
        visual_summary = "; ".join(
            f"{bv.beat}: {bv.visual}" for bv in ctx.visual_plan.visual_plan[:5]
        )
    packaging_summary = ""
    if ctx.packaging:
        parts = [f"{p.platform}: {p.primary_hook}" for p in ctx.packaging.platform_packages]
        packaging_summary = "; ".join(parts)
    agent = orch._get_agent("qc")
    ctx.qc_gate = await agent.review(
        script=script, visual_summary=visual_summary, packaging_summary=packaging_summary
    )
    return ctx


async def _stage_publish_queue(
    orch: ContentGenOrchestrator, ctx: PipelineContext
) -> PipelineContext:
    if ctx.packaging is None or ctx.qc_gate is None or not ctx.qc_gate.approved_for_publish:
        return ctx
    idea_id = _resolve_selected_idea_id(ctx)
    agent = orch._get_agent("publish")
    items = await agent.schedule(ctx.packaging, idea_id=idea_id)
    # Store first publish item in context
    if items:
        ctx.publish_item = items[0]
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
