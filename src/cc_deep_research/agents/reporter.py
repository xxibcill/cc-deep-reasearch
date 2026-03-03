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

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize reporter agent.

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
            if finding.get("evidence"):
                sections.append("**Supporting Sources:**")
                for url in finding["evidence"]:
                    # Find source index
                    for j, source in enumerate(session.sources, 1):
                        if source.url == url:
                            sections.append(f"- [{source.title}]({url}) [{j}]")
                            break
                sections.append("")
            if finding.get("confidence"):
                sections.append(f"**Confidence:** {finding['confidence'].capitalize()}\n")

        # Detailed Analysis
        sections.append("## Detailed Analysis\n")
        sections.append(self._generate_detailed_analysis(session, analysis))
        sections.append("\n")

        # Cross-Reference Analysis
        sections.append("## Cross-Reference Analysis\n")
        sections.append(self._generate_cross_reference_section(analysis))
        sections.append("\n")

        # Research Gaps (NEW)
        if analysis.get("gaps"):
            sections.append("## Research Gaps and Limitations\n")
            for gap in analysis.get("gaps", []):
                if isinstance(gap, dict):
                    sections.append(f"### {gap.get('gap_description', 'Gap')}")
                    sections.append(f"**Importance:** {gap.get('importance', 'Medium')}")
                    if gap.get("suggested_queries"):
                        sections.append("**Suggested follow-up queries:**")
                        for q in gap["suggested_queries"]:
                            sections.append(f"- {q}")
                    sections.append("")
                else:
                    sections.append(f"- {gap}")
            sections.append("")

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
                    "content": s.content,
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

        # Paragraph 2: Key findings (ENHANCED)
        if analysis.get("key_findings"):
            key_count = len(analysis["key_findings"])
            themes = analysis.get("themes", [])[:3]
            paragraphs.append(
                f"The research identified {key_count} key findings. "
                f"Main themes include: "
                f"{', '.join(themes)}. "
            )

            # Add method information
            method = analysis.get("analysis_method", "basic")
            if method == "ai_semantic" or method == "ai_multi_pass":
                paragraphs.append(
                    "Analysis was performed using AI-powered semantic analysis, "
                    "enabling identification of nuanced patterns and cross-source relationships."
                )
            elif method == "basic_keyword":
                paragraphs.append(
                    "Analysis was performed using keyword-based extraction due to limited source content availability. "
                    "For deeper analysis, ensure full webpage content is accessible."
                )

        # Paragraph 3: Notes
        gaps = analysis.get("gaps", [])
        if gaps:
            if isinstance(gaps[0], dict):
                gap_descriptions = [g.get("gap_description", g) for g in gaps]
            else:
                gap_descriptions = gaps
            paragraphs.append(
                f"Areas requiring additional investigation include: {', '.join(gap_descriptions)}."
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

        # Use detailed theme data if available
        themes_detailed = analysis.get("themes_detailed", [])

        if not themes_detailed:
            # Fallback to basic theme names
            themes = analysis.get("themes", [])
            for theme in themes:
                sections.append(f"### {theme}")
                sections.append(
                    f"Analysis related to {theme} is based on multiple sources. "
                    "Further investigation may provide additional insights.\n"
                )
        else:
            # Use AI-generated detailed themes with deduplication
            cited_sources: set[str] = set()  # Track which sources have been cited

            for theme in themes_detailed:
                sections.append(f"### {theme['name']}\n")

                # Theme description
                description = theme.get("description", "")

                # Clean description to remove navigation artifacts
                description = self._clean_description(description)
                sections.append(description)
                sections.append("\n")

                # Key points
                if theme.get("key_points"):
                    sections.append("**Key Points:**\n")
                    for point in theme["key_points"]:
                        # Clean key points
                        clean_point = self._clean_description(str(point))
                        if clean_point and len(clean_point) > 10:
                            sections.append(f"- {clean_point}")
                    sections.append("\n")

                # Supporting sources (with deduplication)
                if theme.get("supporting_sources"):
                    sections.append("**Supporting Sources:**\n")
                    for url in theme["supporting_sources"]:
                        # Skip if already cited
                        if url in cited_sources:
                            continue

                        # Find source details
                        for source in session.sources:
                            if source.url == url:
                                # Clean title
                                title = self._clean_title(source.title or "Untitled")
                                sections.append(f"- [{title}]({url})")
                                cited_sources.add(url)
                                break
                    sections.append("")

        return "\n".join(sections)

    def _clean_description(self, description: str) -> str:
        """Clean description text from artifacts.

        Args:
            description: Description text to clean.

        Returns:
            Cleaned description.
        """
        if not description:
            return ""

        # Remove navigation and UI text
        import re

        description = re.sub(r'\[Log in\]', '', description)
        description = re.sub(r'\[Cart\]', '', description)
        description = re.sub(r'\[Share\]', '', description)
        description = re.sub(r'com/@\w+', '', description)

        # Remove image references
        description = re.sub(r'!\[.*?\]\(.*?\)', '', description)

        # Clean up whitespace
        description = re.sub(r'\s+', ' ', description)

        # Remove incomplete sentences at the start
        sentences = description.split('.')
        clean_sentences = []

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 20:
                clean_sentences.append(sentence)

        return '. '.join(clean_sentences).strip()

    def _clean_title(self, title: str) -> str:
        """Clean title from artifacts.

        Args:
            title: Title to clean.

        Returns:
            Cleaned title.
        """
        if not title:
            return "Untitled"

        # Remove navigation patterns
        import re

        title = re.sub(r'\[Log in\]', '', title)
        title = re.sub(r'\[Cart\]', '', title)
        title = re.sub(r'com/@\w+', '', title)
        title = re.sub(r'\|.*$', '', title)  # Remove pipe-delimited suffixes

        return title.strip()

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

        # ENHANCED: Cross-reference claims with evidence
        claims = analysis.get("cross_reference_claims", [])
        if claims:
            sections.append("\n### Detailed Claims Analysis")
            for claim in claims:
                sections.append(f"\n**Claim:** {claim.get('claim', 'Unnamed claim')}")
                if claim.get("supporting_sources"):
                    sections.append(
                        f"- **Supporting:** {len(claim['supporting_sources'])} sources"
                    )
                if claim.get("contradicting_sources"):
                    sections.append(
                        f"- **Contradicting:** {len(claim['contradicting_sources'])} sources"
                    )
                if claim.get("consensus_level"):
                    consensus_pct = claim["consensus_level"] * 100
                    sections.append(f"- **Consensus Level:** {consensus_pct:.0f}%")

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
            providers = {s.provider for s in session.searches}
            metadata.append(f"- Providers Used: {', '.join(providers)}")

        # Add analysis method if available
        if session.metadata and session.metadata.get("analysis"):
            analysis = session.metadata["analysis"]
            method = analysis.get("analysis_method", "unknown")
            metadata.append(f"- Analysis Method: {method}")

        return "\n".join(metadata)


__all__ = ["ReporterAgent"]
