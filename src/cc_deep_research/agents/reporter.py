"""Reporter agent implementation.

The reporter agent is responsible for:
- Generating final research reports in various formats
- Structuring reports according to specifications
- Ensuring proper citation formatting
- Including all required sections and metadata
- Displaying source credibility information
- Showing evidence quality analysis
- Including safety and contraindication information
"""

import json
from collections import defaultdict
from datetime import datetime
from typing import Any

from cc_deep_research.agents.ai_agent_integration import AIAgentIntegration
from cc_deep_research.credibility import (
    SourceCredibilityScorer,
    format_credibility_badge,
)
from cc_deep_research.models import QualityScore, ResearchSession, SearchResultItem


class ReporterAgent:
    """Agent that generates research reports.

    This agent:
    - Generates Markdown reports with proper structure
    - Generates JSON reports for programmatic use
    - Formats citations correctly
    - Includes all required sections (executive summary, findings, analysis, etc.)
    - Displays source credibility scores and types
    - Shows evidence quality analysis (human/animal/in vitro studies)
    - Includes safety and contraindication information
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize reporter agent.

        Args:
            config: Agent configuration dictionary.
        """
        self._config = config
        self._credibility_scorer = SourceCredibilityScorer()
        self._ai_integration = AIAgentIntegration(config)

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
        ## Methodology
        ## Key Findings
        ## Detailed Analysis
        ## Evidence Quality Analysis
        ## Cross-Reference Analysis
        ## Safety and Contraindications
        ## Research Gaps and Limitations
        ## Sources (with credibility scores)
        ## Research Metadata
        """
        sections = []

        # Title
        sections.append(f"# Research Report: {session.query}\n")

        # Executive Summary
        sections.append("## Executive Summary\n")
        sections.append(self._generate_executive_summary(session, analysis))
        sections.append("\n")

        # Methodology
        sections.append("## Methodology\n")
        sections.append(self._generate_methodology_section(session, analysis))
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

        # Evidence Quality Analysis (NEW)
        sections.append("## Evidence Quality Analysis\n")
        sections.append(self._generate_evidence_quality_section(session, analysis))
        sections.append("\n")

        # Cross-Reference Analysis
        sections.append("## Cross-Reference Analysis\n")
        sections.append(self._generate_cross_reference_section(analysis))
        sections.append("\n")

        # Safety and Contraindications (NEW)
        safety_section = self._generate_safety_section(session)
        if safety_section:
            sections.append("## Safety and Contraindications\n")
            sections.append(safety_section)
            sections.append("\n")

        # Research Gaps
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

        # Sources (with credibility scoring)
        sections.append("## Sources\n")
        sections.append(self._generate_sources_section(session))

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
        # Get evidence quality analysis
        themes = analysis.get("themes_detailed", [])
        if not themes:
            themes = [{"name": t, "supporting_sources": []} for t in analysis.get("themes", [])]

        evidence_quality = self._ai_integration.analyze_evidence_quality(
            session.sources,
            themes,
        )

        # Get safety information
        safety_info = self._ai_integration.extract_safety_information(session.sources)

        report = {
            "query": session.query,
            "session_id": session.session_id,
            "depth": session.depth.value,
            "started_at": session.started_at.isoformat(),
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "execution_time_seconds": session.execution_time_seconds,
            "total_sources": session.total_sources,
            "analysis": analysis,
            "evidence_quality": evidence_quality,
            "safety_info": safety_info,
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

    def _generate_methodology_section(
        self,
        session: ResearchSession,
        analysis: dict[str, Any],
    ) -> str:
        """Generate methodology section.

        Args:
            session: Research session.
            analysis: Analysis results.

        Returns:
            Methodology text describing how research was conducted.
        """
        lines = []

        # Research approach
        lines.append("### Research Approach")
        lines.append(
            f"This report was generated using the **{session.depth.value.title()}** "
            "research depth mode, which determines the comprehensiveness of the search."
        )
        lines.append("")

        # Depth explanation
        depth_descriptions = {
            "quick": (
                "Quick mode provides rapid fact-checking with 3-5 sources, "
                "suitable for basic queries and verification."
            ),
            "standard": (
                "Standard mode provides general research with 10-15 sources, "
                "suitable for overviews and introductory analysis."
            ),
            "deep": (
                "Deep mode provides thorough research with 20+ sources, "
                "suitable for comprehensive understanding and detailed analysis."
            ),
        }
        lines.append(depth_descriptions.get(
            session.depth.value,
            "Custom research depth mode."
        ))
        lines.append("")

        # Search strategy
        lines.append("### Search Strategy")
        if session.searches:
            providers = {s.provider for s in session.searches}
            lines.append(
                f"Sources were collected from: {', '.join(providers)}. "
                "Results were aggregated, deduplicated by URL, and sorted by relevance."
            )
        else:
            lines.append("Sources were collected using configured search providers.")

        lines.append(f"Total unique sources after deduplication: {session.total_sources}")
        lines.append("")

        # Analysis method
        lines.append("### Analysis Method")
        method = analysis.get("analysis_method", "basic")

        method_descriptions = {
            "ai_semantic": (
                "AI-powered semantic analysis was used to identify themes, extract key points, "
                "and analyze cross-source relationships. This approach enables nuanced understanding "
                "of content beyond simple keyword matching."
            ),
            "ai_multi_pass": (
                "Multi-pass AI analysis was performed to ensure comprehensive theme extraction "
                "and cross-reference analysis. This involves multiple processing passes to identify "
                "both obvious and subtle patterns in the source material."
            ),
            "basic_keyword": (
                "Keyword-based analysis was used due to limited source content availability. "
                "For deeper analysis, ensure full webpage content is accessible during search."
            ),
        }
        lines.append(method_descriptions.get(
            method,
            f"Analysis was performed using {method} methodology."
        ))
        lines.append("")

        # Credibility assessment
        lines.append("### Credibility Assessment")
        lines.append(
            "Sources are scored on credibility based on domain reputation, content relevance, "
            "publication freshness, and source diversity. High-credibility sources include "
            "peer-reviewed journals, government agencies, and established academic institutions. "
            "Source types are indicated in the Sources section to help readers assess reliability."
        )
        lines.append("")

        # Limitations
        lines.append("### Limitations")
        lines.append(
            "- This research is limited to publicly available web sources and may not include "
            "paywalled academic content or subscription databases."
        )
        lines.append(
            "- Source credibility scores are heuristic-based and should not be considered "
            "definitive assessments of accuracy."
        )
        lines.append(
            "- The analysis reflects the state of available information at the time of research "
            f"({datetime.utcnow().strftime('%Y-%m-%d')})."
        )

        return "\n".join(lines)

    def _generate_evidence_quality_section(
        self,
        session: ResearchSession,
        analysis: dict[str, Any],
    ) -> str:
        """Generate evidence quality analysis section.

        Args:
            session: Research session.
            analysis: Analysis results.

        Returns:
            Evidence quality analysis text.
        """
        lines = []

        # Get evidence quality analysis
        themes = analysis.get("themes_detailed", [])
        if not themes:
            themes = [{"name": t, "supporting_sources": []} for t in analysis.get("themes", [])]

        evidence_quality = self._ai_integration.analyze_evidence_quality(
            session.sources,
            themes,
        )

        # Study types breakdown
        study_types = evidence_quality.get("study_types", {})
        lines.append("### Study Types\n")

        type_descriptions = {
            "review_meta": "Meta-Analyses and Systematic Reviews",
            "human_clinical": "Human Clinical Trials",
            "human_observational": "Human Observational Studies",
            "animal": "Animal Studies",
            "in_vitro": "In Vitro / Laboratory Studies",
            "other": "Other Sources",
        }

        has_studies = False
        for study_type, sources in study_types.items():
            if sources:
                has_studies = True
                desc = type_descriptions.get(study_type, study_type.replace("_", " ").title())
                lines.append(f"- **{desc}**: {len(sources)} source(s)")

        if not has_studies:
            lines.append("- Study type classification not available for these sources")

        lines.append("")

        # Evidence summary
        evidence_summary = evidence_quality.get("evidence_summary", "")
        if evidence_summary:
            lines.append("### Evidence Summary\n")
            lines.append(evidence_summary)
            lines.append("")

        # Confidence levels by theme
        confidence_levels = evidence_quality.get("confidence_levels", [])
        if confidence_levels:
            lines.append("### Confidence by Theme\n")
            for cl in confidence_levels[:5]:  # Top 5 themes
                theme = cl.get("theme", "Unknown")
                confidence = cl.get("confidence", "Unknown")
                score = cl.get("evidence_score", 0)
                explanation = cl.get("explanation", "")

                lines.append(f"**{theme}**: {confidence} confidence (score: {score})")
                if explanation:
                    lines.append(f"  {explanation}")
                lines.append("")

        # Evidence conflicts
        conflicts = evidence_quality.get("evidence_conflicts", [])
        if conflicts:
            lines.append("### Identified Evidence Conflicts\n")
            for conflict in conflicts[:5]:  # Top 5 conflicts
                conflict_type = conflict.get("type", "Conflict")
                context = conflict.get("context", "No context available")
                lines.append(f"- **{conflict_type}**: {context}")
            lines.append("")

        return "\n".join(lines)

    def _generate_safety_section(
        self,
        session: ResearchSession,
    ) -> str:
        """Generate safety and contraindications section.

        Args:
            session: Research session.

        Returns:
            Safety section text or empty string if no safety info found.
        """
        # Extract safety information
        safety_info = self._ai_integration.extract_safety_information(session.sources)

        if not safety_info.get("has_safety_info"):
            # Return a brief note even if no safety info found
            return (
                "No specific safety information was found in the analyzed sources. "
                "Always consult with a healthcare professional before making significant "
                "changes to your diet or supplement regimen.\n"
            )

        lines = []

        # Side effects
        side_effects = safety_info.get("side_effects", [])
        if side_effects:
            lines.append("### Potential Side Effects\n")
            for se in side_effects:
                lines.append(f"- {se['description']}")
                if se.get("source_title"):
                    lines.append(f"  *Source: {se['source_title']}*")
            lines.append("")

        # Contraindications
        contraindications = safety_info.get("contraindications", [])
        if contraindications:
            lines.append("### Contraindications\n")
            for ci in contraindications:
                lines.append(f"- {ci['description']}")
                if ci.get("source_title"):
                    lines.append(f"  *Source: {ci['source_title']}*")
            lines.append("")

        # Drug interactions
        drug_interactions = safety_info.get("drug_interactions", [])
        if drug_interactions:
            lines.append("### Drug Interactions\n")
            for di in drug_interactions:
                lines.append(f"- {di['description']}")
                if di.get("source_title"):
                    lines.append(f"  *Source: {di['source_title']}*")
            lines.append("")

        # Precautions
        precautions = safety_info.get("precautions", [])
        if precautions:
            lines.append("### Precautions\n")
            for pc in precautions:
                lines.append(f"- {pc['description']}")
                if pc.get("source_title"):
                    lines.append(f"  *Source: {pc['source_title']}*")
            lines.append("")

        # Dosage information
        dosage_info = safety_info.get("dosage_info", [])
        if dosage_info:
            lines.append("### Dosage Information\n")
            for di in dosage_info:
                lines.append(f"- {di['description']}")
                if di.get("source_title"):
                    lines.append(f"  *Source: {di['source_title']}*")
            lines.append("")

        # Disclaimer
        lines.append("**Important Disclaimer:** This safety information is extracted from the analyzed sources and should not be considered medical advice. Always consult with a qualified healthcare professional before starting any new supplement or making significant dietary changes, especially if you have existing health conditions or are taking medications.\n")

        return "\n".join(lines)

    def _generate_sources_section(
        self,
        session: ResearchSession,
    ) -> str:
        """Generate sources section with credibility scoring and grouping.

        Args:
            session: Research session.

        Returns:
            Sources section text with credibility badges.
        """
        lines = []

        # Score all sources
        scored_sources = self._credibility_scorer.score_sources(
            session.sources,
            session.query,
        )

        # Group sources by type
        sources_by_type: dict[str, list[tuple[SearchResultItem, QualityScore]]] = defaultdict(list)
        for source, score in scored_sources:
            source_type = self._credibility_scorer.get_source_type(source.url)
            sources_by_type[source_type].append((source, score))

        # Order source types by credibility
        type_order = [
            "Peer-Reviewed", "Preprint", "Academic", "Government",
            "Medical Institution", "Medical Reference", "Medical News",
            "News Agency", "News", "Business News",
            "Encyclopedia", "Reference",
            "Organization", "Commercial", "Web Source",
            "Blog Platform", "Social Media", "Video Platform",
        ]

        # Credibility summary
        summary = self._credibility_scorer.get_credibility_summary(session.sources)
        high_cred = summary["credibility_distribution"]["high"]
        med_cred = summary["credibility_distribution"]["medium"]
        low_cred = summary["credibility_distribution"]["low"]

        lines.append(
            f"**Credibility Distribution:** {high_cred} high-credibility, "
            f"{med_cred} medium-credibility, {low_cred} low-credibility sources.\n"
        )

        # Display sources grouped by type
        displayed_types = set()
        source_index = 1

        for source_type in type_order:
            if source_type in sources_by_type:
                displayed_types.add(source_type)
                lines.append(f"\n### {source_type}\n")

                for source, score in sources_by_type[source_type]:
                    badge = format_credibility_badge(score)
                    title = self._clean_title(source.title or "Untitled")
                    lines.append(f"[{source_index}] {badge} [{title}]({source.url})")
                    source_index += 1

        # Display any remaining types not in our order
        for source_type, sources in sources_by_type.items():
            if source_type not in displayed_types:
                lines.append(f"\n### {source_type}\n")
                for source, score in sources:
                    badge = format_credibility_badge(score)
                    title = self._clean_title(source.title or "Untitled")
                    lines.append(f"[{source_index}] {badge} [{title}]({source.url})")
                    source_index += 1

        return "\n".join(lines)


__all__ = ["ReporterAgent"]
