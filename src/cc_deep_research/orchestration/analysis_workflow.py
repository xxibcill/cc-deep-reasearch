"""Analysis and validation workflow extracted from the orchestrator."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from cc_deep_research.agents import AnalyzerAgent, DeepAnalyzerAgent, ValidatorAgent
from cc_deep_research.config import Config
from cc_deep_research.models import (
    AnalysisResult,
    IterationHistoryRecord,
    PlannerIterationDecision,
    ResearchDepth,
    ResearchSession,
    SearchResultItem,
    StrategyResult,
    ValidationResult,
)
from cc_deep_research.monitoring import ResearchMonitor


class AnalysisWorkflow:
    """Coordinate the iterative research loop after initial source collection."""

    def __init__(self, *, config: Config, monitor: ResearchMonitor) -> None:
        self._config = config
        self._monitor = monitor

    async def analyze_findings(
        self,
        *,
        analyzer: AnalyzerAgent,
        sources: list[SearchResultItem],
        query: str,
    ) -> AnalysisResult:
        """Analyze the current source set."""
        self._monitor.section("Analysis")
        # Log analysis method being used
        self._monitor.log(f"Analysis method: {self._config.research.ai_integration_method}")
        llm_available = hasattr(analyzer, "_ai_service") and (
            analyzer._ai_service._llm_client is not None
        )
        self._monitor.log(f"Routed LLM available: {llm_available}")
        if not llm_available:
            self._monitor.log("Note: Running in heuristic mode (LLM unavailable or disabled)")
        analysis = analyzer.analyze_sources(sources, query)
        self._monitor.log(f"Key findings: {len(analysis.key_findings)}")
        self._monitor.log(f"Themes identified: {len(analysis.themes)}")
        self._monitor.log(f"Gaps: {len(analysis.gaps)}")
        self._monitor.record_reasoning_summary(
            stage="analysis",
            summary=(
                f"Generated {len(analysis.key_findings)} findings, "
                f"{len(analysis.themes)} themes, {len(analysis.gaps)} gaps"
            ),
            agent_id="analyzer",
        )
        return analysis

    async def deep_analysis(
        self,
        *,
        deep_analyzer: DeepAnalyzerAgent,
        sources: list[SearchResultItem],
        query: str,
    ) -> AnalysisResult:
        """Run deep multi-pass analysis for deep research mode."""
        self._monitor.section("Deep Analysis")
        result_dict = deep_analyzer.deep_analyze(sources, query)
        # Build AnalysisResult directly from the dict to avoid validation issues
        deep_analysis = AnalysisResult(
            key_findings=result_dict.get("key_findings", []),
            themes=result_dict.get("themes", []),
            themes_detailed=result_dict.get("themes_detailed", []),
            consensus_points=result_dict.get("consensus_points", []),
            contention_points=result_dict.get("disagreement_points", []),
            cross_reference_claims=result_dict.get("cross_reference_claims", []),
            gaps=result_dict.get("gaps", []),
            source_count=result_dict.get("source_count", 0),
            analysis_method=result_dict.get("analysis_method", "empty"),
            deep_analysis_complete=result_dict.get("deep_analysis_complete", False),
            analysis_passes=result_dict.get("analysis_passes", 0),
            patterns=result_dict.get("patterns", []),
            disagreement_points=result_dict.get("disagreement_points", []),
            implications=result_dict.get("implications", []),
            comprehensive_synthesis=result_dict.get("comprehensive_synthesis", ""),
        )
        self._monitor.log(f"Deep analysis passes: {deep_analysis.analysis_passes}")
        self._monitor.log(f"Deep themes: {len(deep_analysis.themes)}")
        self._monitor.log(f"Consensus points: {len(deep_analysis.consensus_points)}")
        self._monitor.log(f"Disagreement points: {len(deep_analysis.disagreement_points)}")
        self._monitor.record_reasoning_summary(
            stage="deep_analysis",
            summary=(
                f"Deep analysis produced {len(deep_analysis.themes)} themes and "
                f"{len(deep_analysis.consensus_points)} consensus points"
            ),
            agent_id="deep_analyzer",
        )
        return deep_analysis

    async def validate_research(
        self,
        *,
        validator: ValidatorAgent,
        query: str,
        depth: ResearchDepth,
        sources: list[SearchResultItem],
        analysis: AnalysisResult,
    ) -> ValidationResult:
        """Validate the current source set and synthesized analysis."""
        self._monitor.section("Validation")
        session = ResearchSession(session_id="validation", query=query, sources=sources)
        min_sources = self._config.research.min_sources.__dict__[depth.value]
        validation = validator.validate_research(
            session,
            analysis,
            query=query,
            min_sources_override=min_sources,
        )
        self._monitor.log(f"Quality score: {validation.quality_score:.2f}")
        self._monitor.log(f"Valid: {validation.is_valid}")
        self._monitor.record_reasoning_summary(
            stage="validation",
            summary=f"Quality score {validation.quality_score:.2f}, valid={validation.is_valid}",
            agent_id="validator",
        )
        if validation.issues:
            self._monitor.log(f"Issues: {len(validation.issues)}")
        if validation.warnings:
            self._monitor.log(f"Warnings: {len(validation.warnings)}")
        return validation

    def log_validation_results(self, validation: ValidationResult) -> None:
        """Log validation issues, warnings, and recommendations."""
        if validation.issues:
            self._monitor.section("Validation Issues")
            for issue in validation.issues:
                self._monitor.log(f"  - {issue}")

        if validation.warnings:
            self._monitor.section("Validation Warnings")
            for warning in validation.warnings:
                self._monitor.log(f"  - {warning}")

        if validation.recommendations:
            self._monitor.section("Recommendations")
            for recommendation in validation.recommendations:
                self._monitor.log(f"  - {recommendation}")

    async def run(
        self,
        *,
        query: str,
        depth: ResearchDepth,
        strategy: StrategyResult,
        sources: list[SearchResultItem],
        min_sources: int | None,
        phase_hook: Callable[[str, str], None] | None,
        cancellation_check: Callable[[], None] | None,
        run_single_pass: Callable[..., Awaitable[tuple[AnalysisResult, ValidationResult | None]]],
        collect_follow_up_sources: Callable[..., Awaitable[list[SearchResultItem]]],
        plan_iteration: Callable[..., PlannerIterationDecision],
    ) -> tuple[
        AnalysisResult,
        ValidationResult | None,
        list[SearchResultItem],
        list[IterationHistoryRecord],
    ]:
        """Run the Search -> Read -> Hypothesize -> Search-again research loop."""
        analysis = AnalysisResult()
        validation: ValidationResult | None = None
        iteration_history: list[IterationHistoryRecord] = []
        max_iterations = (
            self._config.research.max_iterations
            if self._config.research.enable_iterative_search
            else 1
        )
        analysis_mode = "deep_multi_pass" if depth == ResearchDepth.DEEP else "single_pass"
        self._monitor.record_analysis_mode(
            depth=depth.value,
            mode=analysis_mode,
            deep_analysis_enabled=depth == ResearchDepth.DEEP,
        )

        iteration = 1
        while True:
            self._check_cancelled(cancellation_check)
            analysis, validation = await run_single_pass(
                query=query,
                depth=depth,
                strategy=strategy,
                sources=sources,
                phase_hook=phase_hook,
                cancellation_check=cancellation_check,
            )
            decision = plan_iteration(
                query=query,
                strategy=strategy,
                analysis=analysis,
                validation=validation,
                sources=sources,
                iteration=iteration,
                max_iterations=max_iterations,
                min_sources=min_sources,
                iteration_history=iteration_history,
            )
            iteration_history.append(
                IterationHistoryRecord(
                    iteration=iteration,
                    source_count=len(sources),
                    quality_score=validation.quality_score if validation else None,
                    gap_count=len(analysis.gaps),
                    follow_up_queries=decision.next_queries,
                    current_hypothesis=decision.current_hypothesis,
                    planner_summary=decision.rationale,
                    stop_reason=decision.stop_reason,
                )
            )
            self._monitor.record_reasoning_summary(
                stage="planner_loop",
                summary=decision.rationale,
                agent_id="planner",
                iteration=iteration,
                current_hypothesis=decision.current_hypothesis,
                missing_information=decision.missing_information,
                follow_up_queries=decision.next_queries,
                confidence=decision.confidence,
            )

            if not decision.should_continue:
                self._monitor.record_follow_up_decision(
                    iteration=iteration,
                    reason=decision.reason_code,
                    follow_up_queries=decision.next_queries,
                    failure_modes=validation.failure_modes if validation else [],
                    quality_score=validation.quality_score if validation else None,
                )
                self._monitor.record_iteration_stop(
                    iteration=iteration,
                    stop_reason=decision.stop_reason or "success",
                    detail=decision.rationale,
                    quality_score=validation.quality_score if validation else None,
                    follow_up_queries=decision.next_queries,
                )
                break

            if phase_hook is not None:
                phase_hook("iterative_search", f"Running follow-up research pass {iteration + 1}")
            self._monitor.record_reasoning_summary(
                stage="iterative_search",
                summary=f"Running follow-up pass {iteration + 1} with {len(decision.next_queries)} queries",
                agent_id="planner",
                follow_up_queries=decision.next_queries,
            )
            self._monitor.record_follow_up_decision(
                iteration=iteration,
                reason=decision.reason_code,
                follow_up_queries=decision.next_queries,
                failure_modes=validation.failure_modes if validation else [],
                quality_score=validation.quality_score if validation else None,
            )
            updated_sources = await collect_follow_up_sources(
                existing_sources=sources,
                follow_up_queries=decision.next_queries,
                depth=depth,
                min_sources=min_sources,
            )
            if len(updated_sources) <= len(sources):
                self._monitor.log("Follow-up search produced no new sources; stopping iterations")
                self._monitor.record_iteration_stop(
                    iteration=iteration,
                    stop_reason=(
                        "degraded_execution"
                        if validation and validation.needs_follow_up
                        else "success"
                    ),
                    detail="Follow-up collection did not add any new sources",
                    quality_score=validation.quality_score if validation else None,
                    follow_up_queries=decision.next_queries,
                )
                break

            sources = updated_sources
            iteration += 1

        return analysis, validation, sources, iteration_history

    def _check_cancelled(self, cancellation_check: Callable[[], None] | None) -> None:
        """Raise when the caller has requested the workflow to stop."""
        if cancellation_check is not None:
            cancellation_check()
