"""Analysis and validation workflow extracted from the orchestrator."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from cc_deep_research.agents import AnalyzerAgent, DeepAnalyzerAgent, ValidatorAgent
from cc_deep_research.config import Config
from cc_deep_research.models import (
    AnalysisResult,
    IterationHistoryRecord,
    ResearchDepth,
    ResearchSession,
    SearchResultItem,
    StrategyResult,
    ValidationResult,
)
from cc_deep_research.monitoring import ResearchMonitor
from cc_deep_research.orchestration.helpers import build_follow_up_queries


class AnalysisWorkflow:
    """Coordinate analysis, validation, and iterative follow-up search."""

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
        # Check CLI availability safely (may not exist in test fixtures)
        cli_available = hasattr(analyzer, "_ai_service") and (
            analyzer._ai_service._llm_client is not None
        )
        self._monitor.log(f"Claude CLI available: {cli_available}")
        if not cli_available:
            self._monitor.log("Note: Running in heuristic mode (CLI unavailable or disabled)")
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
        run_single_pass: Callable[..., Awaitable[tuple[AnalysisResult, ValidationResult | None]]],
        collect_follow_up_sources: Callable[..., Awaitable[list[SearchResultItem]]],
    ) -> tuple[
        AnalysisResult,
        ValidationResult | None,
        list[SearchResultItem],
        list[IterationHistoryRecord],
    ]:
        """Run analysis, validation, and iterative follow-up search."""
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

        for iteration in range(1, max_iterations + 1):
            analysis, validation = await run_single_pass(
                query=query,
                depth=depth,
                strategy=strategy,
                sources=sources,
                phase_hook=phase_hook,
            )
            iteration_history.append(
                IterationHistoryRecord(
                    iteration=iteration,
                    source_count=len(sources),
                    quality_score=validation.quality_score if validation else None,
                    gap_count=len(analysis.gaps),
                    follow_up_queries=validation.follow_up_queries if validation else [],
                )
            )

            if iteration >= max_iterations:
                detail = f"Reached iteration limit ({max_iterations})"
                self._monitor.record_follow_up_decision(
                    iteration=iteration,
                    reason="iteration_limit_reached",
                    follow_up_queries=[],
                    failure_modes=validation.failure_modes if validation else [],
                    quality_score=validation.quality_score if validation else None,
                )
                self._monitor.record_iteration_stop(
                    iteration=iteration,
                    stop_reason="limit_reached",
                    detail=detail,
                    quality_score=validation.quality_score if validation else None,
                )
                break

            follow_up_queries = build_follow_up_queries(
                query=query,
                analysis=analysis,
                validation=validation,
                enable_iterative_search=self._config.research.enable_iterative_search,
            )
            if not follow_up_queries:
                reason = (
                    "validation_low_quality_no_queries"
                    if validation and validation.needs_follow_up
                    else "quality_sufficient"
                )
                stop_reason = "low_quality" if validation and validation.needs_follow_up else "success"
                detail = (
                    "Validation requested follow-up but no follow-up queries were generated"
                    if validation and validation.needs_follow_up
                    else "No follow-up queries were required"
                )
                self._monitor.record_follow_up_decision(
                    iteration=iteration,
                    reason=reason,
                    follow_up_queries=[],
                    failure_modes=validation.failure_modes if validation else [],
                    quality_score=validation.quality_score if validation else None,
                )
                self._monitor.record_iteration_stop(
                    iteration=iteration,
                    stop_reason=stop_reason,
                    detail=detail,
                    quality_score=validation.quality_score if validation else None,
                )
                break

            if phase_hook is not None:
                phase_hook("iterative_search", f"Running follow-up research pass {iteration + 1}")
            self._monitor.record_reasoning_summary(
                stage="iterative_search",
                summary=f"Running follow-up pass {iteration + 1} with {len(follow_up_queries)} queries",
                agent_id="orchestrator",
                follow_up_queries=follow_up_queries,
            )
            self._monitor.record_follow_up_decision(
                iteration=iteration,
                reason="validation_requested_follow_up",
                follow_up_queries=follow_up_queries,
                failure_modes=validation.failure_modes if validation else [],
                quality_score=validation.quality_score if validation else None,
            )
            updated_sources = await collect_follow_up_sources(
                existing_sources=sources,
                follow_up_queries=follow_up_queries,
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
                    follow_up_queries=follow_up_queries,
                )
                break

            sources = updated_sources

        return analysis, validation, sources, iteration_history
