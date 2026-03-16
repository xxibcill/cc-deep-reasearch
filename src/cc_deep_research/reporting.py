"""Report generation for CC Deep Research CLI.

This module provides report generation functionality for research sessions,
supporting multiple output formats (Markdown, JSON, HTML).
"""

import logging
from typing import Any

from cc_deep_research.agents.report_quality_evaluator import ReportQualityEvaluatorAgent
from cc_deep_research.agents.report_refiner import ReportRefinerAgent
from cc_deep_research.agents.reporter import ReporterAgent
from cc_deep_research.config import Config
from cc_deep_research.html_report_renderer import HTMLReportRenderer
from cc_deep_research.llm import LLMRouteRegistry, LLMRouter
from cc_deep_research.llm.base import LLMProviderType, LLMTransportType
from cc_deep_research.models.analysis import AnalysisResult, ValidationResult
from cc_deep_research.models.session import ResearchSession
from cc_deep_research.models.support import ReportEvaluationResult
from cc_deep_research.post_validator import PostReportValidator

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates research reports in various formats.

    This class provides:
    - Markdown report generation with proper structure
    - JSON report generation for programmatic use
    - HTML report generation (optional)
    - Citation formatting
    - Metadata inclusion
    - Report quality evaluation and refinement
    """

    def __init__(self, config: Config) -> None:
        """Initialize the report generator.

        Args:
            config: Application configuration.
        """
        self._config = config
        self._reporter = ReporterAgent({})
        self._llm_registry = LLMRouteRegistry(config.llm)
        self._llm_router = LLMRouter(self._llm_registry)
        self._report_quality_evaluator = ReportQualityEvaluatorAgent(
            config.model_dump(),
            llm_router=self._llm_router,
        )
        self._post_validator = PostReportValidator(config.model_dump())
        self._report_refiner = ReportRefinerAgent(config.model_dump())

    def generate_markdown_report(
        self,
        session: ResearchSession,
        analysis: dict[str, Any],
    ) -> str:
        """Generate a Markdown format research report.

        The report pipeline:
        1. Generate initial report from analysis
        2. Evaluate report quality
        3. Run post-validation (regex-based checks)
        4. Refine report if enabled and issues detected

        Args:
            session: Research session with sources and metadata.
            analysis: Analysis results from analyzer agent.

        Returns:
            Complete Markdown report string.
        """
        analysis_result = AnalysisResult.model_validate(analysis)
        self._configure_report_quality_route(session)
        markdown = self._reporter.generate_markdown_report(session, analysis)

        # Evaluate report quality (before post-validation)
        quality_result = ReportEvaluationResult(overall_quality_score=0.0, is_acceptable=True)
        if self._config.research.quality.enable_report_quality_evaluation:
            quality_result = self._report_quality_evaluator.evaluate_report_quality_sync(
                markdown,
                session,
                analysis_result,
            )

            logger.info(
                f"Report quality score: {quality_result.overall_quality_score:.2f} "
                f"(threshold: {self._config.research.quality.min_report_quality_score})"
            )

            if quality_result.critical_issues:
                logger.warning(
                    f"Report quality evaluation found {len(quality_result.critical_issues)} critical issues"
                )
                for issue in quality_result.critical_issues:
                    logger.warning(f"  - {issue}")

            if quality_result.warnings:
                logger.info(
                    f"Report quality evaluation found {len(quality_result.warnings)} warnings"
                )
                for warning in quality_result.warnings[:3]:  # Log first 3 warnings
                    logger.info(f"  - {warning}")

        # Run post-validation (regex-based checks)
        validation_result = self._post_validator.validate_report(markdown, session, analysis_result)

        if validation_result.get("issues"):
            logger.warning(f"Post-validation found {len(validation_result['issues'])} issues in the report")

        # Run refinement (Writer/Editor pass) if enabled
        if self._config.research.quality.enable_report_refinement:
            # Only refine if there are issues to address
            has_issues = (
                bool(quality_result.critical_issues)
                or bool(quality_result.warnings)
                or bool(validation_result.get("issues"))
            )

            if has_issues:
                logger.info("Running report refinement pass to address detected issues")
                validation_result_typed = ValidationResult(
                    is_valid=not bool(validation_result.get("issues")),
                    issues=validation_result.get("issues", []),
                    warnings=validation_result.get("warnings", []),
                    recommendations=validation_result.get("recommendations", []),
                )

                markdown = self._report_refiner.refine_report(
                    original_markdown=markdown,
                    validation_result=validation_result_typed,
                    evaluation_result=quality_result,
                    session=session,
                    analysis=analysis_result,
                )
                logger.info("Report refinement pass completed")

        self._update_session_route_metadata(session)
        return markdown

    def _configure_report_quality_route(self, session: ResearchSession) -> None:
        """Apply any planner-selected route for report evaluation."""
        self._llm_registry.clear()
        planned_routes = session.metadata.get("llm_routes", {}).get("planned_routes", {})
        route_data = planned_routes.get("report_quality_evaluator")
        if not isinstance(route_data, dict):
            return

        transport = self._transport_from_value(route_data.get("transport"))
        provider = self._provider_from_value(route_data.get("provider"))
        if transport is None or provider is None:
            return

        route = self._llm_registry.get_route_for_transport(transport)
        route.provider = provider
        route.model = str(route_data.get("model", route.model))
        self._llm_registry.set_route(
            "report_quality_evaluator",
            route,
        )

    def _update_session_route_metadata(self, session: ResearchSession) -> None:
        """Mirror report-evaluation route usage into session metadata."""
        transport = self._report_quality_evaluator.last_transport_used
        if transport in {"disabled", ""}:
            return

        llm_routes = session.metadata.setdefault("llm_routes", {})
        actual_routes = llm_routes.setdefault("actual_routes", {})
        planned_routes = llm_routes.get("planned_routes", {})
        planned = planned_routes.get("report_quality_evaluator", {})
        provider = planned.get("provider", "heuristic")
        model = planned.get("model", "heuristic")

        if transport == "heuristic":
            provider = "heuristic"
            model = "heuristic"

        actual_routes["report_quality_evaluator"] = {
            "transport": transport,
            "provider": provider,
            "model": model,
            "source": "actual",
        }

    @staticmethod
    def _transport_from_value(value: Any) -> LLMTransportType | None:
        try:
            return LLMTransportType(str(value))
        except ValueError:
            return None

    @staticmethod
    def _provider_from_value(value: Any) -> LLMProviderType | None:
        try:
            return LLMProviderType(str(value))
        except ValueError:
            return None

    def generate_json_report(
        self,
        session: ResearchSession,
        analysis: dict[str, Any],
    ) -> str:
        """Generate a JSON format research report.

        Args:
            session: Research session with sources and metadata.
            analysis: Analysis results from analyzer agent.

        Returns:
            JSON string with complete research data.
        """
        return self._reporter.generate_json_report(session, analysis)

    def generate_html_report(
        self,
        session: ResearchSession,
        analysis: dict[str, Any],
    ) -> str:
        """Generate a styled HTML report from the canonical markdown report."""
        markdown_report = self.generate_markdown_report(session, analysis)
        return self.render_html_report(markdown_report)

    def render_html_report(
        self,
        markdown_report: str,
        title: str | None = None,
    ) -> str:
        """Render a markdown report as a styled HTML document."""
        renderer = HTMLReportRenderer()
        return renderer.render_document(markdown_report, title=title)

    def save_report(
        self,
        report: str,
        _output_format: str,
        output_path: str | None = None,
    ) -> str:
        """Save report to file or return it.

        Args:
            report: Report content string.
            output_format: Format of the report (markdown, json, html).
            output_path: Optional file path to save to.

        Returns:
            File path if saved, empty string otherwise.
        """
        if output_path:
            from pathlib import Path

            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(report)
            return str(path)
        return ""


def format_citation(sources: list[Any], index: int) -> str:
    """Format a citation for a source.

    Args:
        sources: List of sources.
        index: Index of the source to cite.

    Returns:
        Formatted citation string.
    """
    if 0 <= index < len(sources):
        source = sources[index]
        return f"[{index + 1}]({source.url})"
    return "[?]"


def generate_executive_summary(
    session: ResearchSession,
    analysis: dict[str, Any],
) -> str:
    """Generate executive summary section.

    This function is a thin wrapper around the canonical ReporterAgent implementation.
    It exists for backwards compatibility with the public API.

    Args:
        session: Research session.
        analysis: Analysis results.

    Returns:
        Executive summary text (2-3 paragraphs).

    Note:
        For new code, prefer using ReportGenerator which handles the full report pipeline.
        The canonical implementation is in ReporterAgent._generate_executive_summary.
    """
    reporter = ReporterAgent({})
    analysis_result = AnalysisResult.model_validate(analysis)
    return reporter._generate_executive_summary(session, analysis_result)


def format_sources_list(sources: list[Any]) -> str:
    """Format sources list with proper numbering.

    Args:
        sources: List of sources to format.

    Returns:
            Formatted sources list string.
    """
    lines = []
    for i, source in enumerate(sources, 1):
        title = source.title or "Untitled"
        lines.append(f"[{i}] {title} - {source.url}")

    return "\n".join(lines)


__all__ = [
    "ReportGenerator",
    "format_citation",
    "generate_executive_summary",
    "format_sources_list",
]
