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
        deep_analysis = AnalysisResult.model_validate(deep_analyzer.deep_analyze(sources, query))
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
                break

            follow_up_queries = build_follow_up_queries(
                query=query,
                analysis=analysis,
                validation=validation,
                enable_iterative_search=self._config.research.enable_iterative_search,
            )
            if not follow_up_queries:
                break

            if phase_hook is not None:
                phase_hook("iterative_search", f"Running follow-up research pass {iteration + 1}")
            self._monitor.record_reasoning_summary(
                stage="iterative_search",
                summary=f"Running follow-up pass {iteration + 1} with {len(follow_up_queries)} queries",
                agent_id="orchestrator",
                follow_up_queries=follow_up_queries,
            )
            updated_sources = await collect_follow_up_sources(
                existing_sources=sources,
                follow_up_queries=follow_up_queries,
                depth=depth,
                min_sources=min_sources,
            )
            if len(updated_sources) <= len(sources):
                self._monitor.log("Follow-up search produced no new sources; stopping iterations")
                break

            sources = updated_sources

        return analysis, validation, sources, iteration_history
