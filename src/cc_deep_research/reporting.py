"""Report generation for CC Deep Research CLI.

This module provides report generation functionality for research sessions,
supporting multiple output formats (Markdown, JSON, HTML).
"""

from typing import Any

from cc_deep_research.agents.reporter import ReporterAgent
from cc_deep_research.config import Config
from cc_deep_research.models import ResearchSession


class ReportGenerator:
    """Generates research reports in various formats.

    This class provides:
    - Markdown report generation with proper structure
    - JSON report generation for programmatic use
    - HTML report generation (optional)
    - Citation formatting
    - Metadata inclusion
    """

    def __init__(self, config: Config) -> None:
        """Initialize the report generator.

        Args:
            config: Application configuration.
        """
        self._config = config
        self._reporter = ReporterAgent({})

    def generate_markdown_report(
        self,
        session: ResearchSession,
        analysis: dict[str, Any],
    ) -> str:
        """Generate a Markdown format research report.

        Args:
            session: Research session with sources and metadata.
            analysis: Analysis results from analyzer agent.

        Returns:
            Complete Markdown report string.
        """
        return self._reporter.generate_markdown_report(session, analysis)

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

    def save_report(
        self,
        report: str,
        _output_format: str,
        output_path: str | None = None,
    ) -> str:
        """Save report to file or return it.

        Args:
            report: Report content string.
            output_format: Format of the report (markdown, json).
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

    Args:
        session: Research session.
        analysis: Analysis results.

    Returns:
        Executive summary text (2-3 paragraphs).
    """
    paragraphs = []

    # Paragraph 1: Overview
    paragraphs.append(
        f"This research investigated '{session.query}' using "
        f"{session.total_sources} sources. The analysis focused on "
        f"identifying key themes, consensus points, and areas of contention."
    )

    # Paragraph 2: Key findings
    if analysis.get("key_findings"):
        key_count = len(analysis["key_findings"])
        paragraphs.append(
            f"The research identified {key_count} key findings. "
            f"Main themes include: "
            f"{', '.join(analysis.get('themes', [])[:3])}."
        )

    # Paragraph 3: Notes
    gaps = analysis.get("gaps", [])
    if gaps:
        paragraphs.append(f"Areas requiring additional investigation include: {', '.join(gaps)}.")

    return "\n\n".join(paragraphs)


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
