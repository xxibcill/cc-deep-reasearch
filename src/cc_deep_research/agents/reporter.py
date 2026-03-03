"""Reporter agent implementation.

The reporter agent is responsible for:
- Generating final research reports in various formats
- Structuring reports according to specifications
- Ensuring proper citation formatting
- Including all required sections and metadata
"""

import json
from datetime import datetime
from typing import Any

from cc_deep_research.models import ResearchSession


class ReporterAgent:
    """Agent that generates research reports.

    This agent:
    - Generates Markdown reports with proper structure
    - Generates JSON reports for programmatic use
    - Formats citations correctly
    - Includes all required sections (executive summary, findings, analysis, etc.)
    """

    def __init__(self, config: dict) -> None:
        """Initialize the reporter agent.

        Args:
            config: Agent configuration dictionary.
        """
        self._config = config

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

        Report structure follows deep-research-features.md specification:
        # Research Report: [Query]
        ## Executive Summary
        ## Key Findings
        ## Detailed Analysis
        ## Cross-Reference Analysis
        ## Sources
        ## Research Metadata
        """
        sections = []

        # Title
        sections.append(f"# Research Report: {session.query}\n")

        # Executive Summary
        sections.append("## Executive Summary\n")
        sections.append(self._generate_executive_summary(session, analysis))
        sections.append("\n")

        # Key Findings
        sections.append("## Key Findings\n")
        for i, finding in enumerate(analysis.get("key_findings", []), 1):
            sections.append(f"### Finding {i}: {finding['title']}")
            sections.append(f"{finding['description']}\n")

        # Detailed Analysis
        sections.append("## Detailed Analysis\n")
        sections.append(self._generate_detailed_analysis(session, analysis))
        sections.append("\n")

        # Cross-Reference Analysis
        sections.append("## Cross-Reference Analysis\n")
        sections.append(self._generate_cross_reference_section(analysis))
        sections.append("\n")

        # Sources
        sections.append("## Sources\n")
        for i, source in enumerate(session.sources, 1):
            sections.append(f"[{i}] {source.title} - {source.url}")

        # Metadata
        sections.append("\n## Research Metadata\n")
        sections.append(self._generate_metadata_section(session))

        return "\n".join(sections)

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
        report = {
            "query": session.query,
            "session_id": session.session_id,
            "depth": session.depth.value,
            "started_at": session.started_at.isoformat(),
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "execution_time_seconds": session.execution_time_seconds,
            "total_sources": session.total_sources,
            "analysis": analysis,
            "sources": [
                {
                    "url": s.url,
                    "title": s.title,
                    "snippet": s.snippet,
                    "score": s.score,
                    "metadata": s.source_metadata,
                }
                for s in session.sources
            ],
            "metadata": session.metadata,
        }

        return json.dumps(report, indent=2)

    def _generate_executive_summary(
        self,
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
            paragraphs.append(
                f"Areas requiring additional investigation include: {', '.join(gaps)}."
            )

        return "\n\n".join(paragraphs)

    def _generate_detailed_analysis(
        self,
        session: ResearchSession,
        analysis: dict[str, Any],
    ) -> str:
        """Generate detailed analysis section.

        Args:
            session: Research session.
            analysis: Analysis results.

        Returns:
            Detailed analysis text.
        """
        sections = []

        # Group by themes
        themes = analysis.get("themes", [])
        for theme in themes:
            sections.append(f"### {theme}")
            sections.append(f"Analysis related to {theme} is based on multiple sources. ")
            sections.append("Further investigation may provide additional insights.\n")

        return "\n".join(sections)

    def _generate_cross_reference_section(
        self,
        analysis: dict[str, Any],
    ) -> str:
        """Generate cross-reference analysis section.

        Args:
            analysis: Analysis results.

        Returns:
            Cross-reference analysis text.
        """
        sections = []

        # Consensus points
        sections.append("### Consensus Points")
        consensus = analysis.get("consensus_points", [])
        if consensus:
            for point in consensus:
                sections.append(f"- {point}")
        else:
            sections.append("- No clear consensus points identified")
        sections.append("")

        # Contention points
        sections.append("### Points of Contention")
        contention = analysis.get("contention_points", [])
        if contention:
            for point in contention:
                sections.append(f"- {point}")
        else:
            sections.append("- No major points of contention identified")

        return "\n".join(sections)

    def _generate_metadata_section(
        self,
        session: ResearchSession,
    ) -> str:
        """Generate metadata section.

        Args:
            session: Research session.

        Returns:
            Metadata text.
        """
        metadata = [
            f"- Query: {session.query}",
            f"- Depth: {session.depth.value}",
            f"- Sources Found: {session.total_sources}",
            f"- Execution Time: {session.execution_time_seconds:.1f}s",
            f"- Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
        ]

        # Add providers from searches
        if session.searches:
            providers = list(set(s.provider for s in session.searches))
            metadata.append(f"- Providers Used: {', '.join(providers)}")

        return "\n".join(metadata)


__all__ = ["ReporterAgent"]
