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
from cc_deep_research.models import (
    AnalysisFinding,
    AnalysisResult,
    ClaimEvidence,
    ClaimFreshness,
    CrossReferenceClaim,
    EvidenceType,
    QualityScore,
    ResearchSession,
    SearchResultItem,
    ValidationResult,
)
from cc_deep_research.aggregation import sanitize_url


# Executive Summary constraints
# These constants define the size and structure limits for the Executive Summary section
EXECUTIVE_SUMMARY_MAX_PARAGRAPHS = 3
EXECUTIVE_SUMMARY_MAX_THEMES = 3
EXECUTIVE_SUMMARY_MAX_CHARACTERS = 800  # Target length for PDF page fit

# Phrases that should NOT appear in the Executive Summary (banned boilerplate)
EXECUTIVE_SUMMARY_BANNED_PHRASES = [
    "This research investigated",
    "Analysis was performed",
    "Areas requiring additional investigation include",
]

# Pointer text for gaps section (used instead of listing gaps inline)
EXECUTIVE_SUMMARY_GAPS_POINTER = (
    "See the Research Gaps and Limitations section for details on areas "
    "requiring additional investigation."
)


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
        analysis_result = AnalysisResult.model_validate(analysis)
        validation_result = self._validation_result(session)
        claims = self._collect_claims(analysis_result)
        evidence_annotations = self._build_evidence_annotations(
            session=session,
            analysis=analysis_result,
            validation=validation_result,
            claims=claims,
        )
        sections = []

        # Title
        sections.append(f"# Research Report: {session.query}\n")

        # Executive Summary
        sections.append("## Executive Summary\n")
        sections.append(self._generate_executive_summary(session, analysis_result))
        sections.append("\n")

        # Methodology
        sections.append("## Methodology\n")
        sections.append(self._generate_methodology_section(session, analysis_result))
        sections.append("\n")

        # Key Findings - render summary-only content for executive overview
        sections.append("## Key Findings\n")
        for i, finding in enumerate(analysis_result.key_findings, 1):
            finding_obj = self._coerce_finding(finding)
            sections.append(f"### Finding {i}: {finding_obj.title}")
            # Use summary field for high-level takeaway (1-2 sentences)
            summary_text = finding_obj.summary or finding_obj.description
            if summary_text:
                # Truncate to 1-2 sentences if summary is too long
                summary_sentences = summary_text.split(". ")
                if len(summary_sentences) > 2:
                    summary_text = ". ".join(summary_sentences[:2]) + "."
                sections.append(f"{summary_text}\n")
            if finding_obj.confidence:
                sections.append(f"**Confidence:** {finding_obj.confidence.capitalize()}\n")
            sections.append("")  # Blank line between findings

        # Detailed Analysis - include description, detail_points, and evidence
        sections.append("## Detailed Analysis\n")
        sections.append(self._generate_detailed_analysis(session, analysis_result))
        sections.append("\n")

        # Evidence Quality Analysis (NEW)
        sections.append("## Evidence Quality Analysis\n")
        sections.append(
            self._generate_evidence_quality_section(
                session,
                analysis_result,
                evidence_annotations,
            )
        )
        sections.append("\n")

        # Cross-Reference Analysis
        sections.append("## Cross-Reference Analysis\n")
        sections.append(self._generate_cross_reference_section(analysis_result))
        sections.append("\n")

        # Safety and Contraindications (NEW)
        safety_section = self._generate_safety_section(session)
        if safety_section:
            sections.append("## Safety and Contraindications\n")
            sections.append(safety_section)
            sections.append("\n")

        # Research Gaps
        if analysis_result.gaps:
            sections.append("## Research Gaps and Limitations\n")
            for gap in analysis_result.normalized_gaps():
                sections.append(f"### {gap.gap_description}")
                sections.append(f"**Importance:** {gap.importance or 'Medium'}")
                if gap.suggested_queries:
                    sections.append("**Suggested follow-up queries:**")
                    for q in gap.suggested_queries:
                        sections.append(f"- {q}")
                sections.append("")
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
        analysis_result = AnalysisResult.model_validate(analysis)
        validation_result = self._validation_result(session)
        claims = self._collect_claims(analysis_result)

        # Get evidence quality analysis
        themes = analysis_result.themes_detailed
        if not themes:
            themes = [{"name": t, "supporting_sources": []} for t in analysis_result.themes]

        evidence_quality = self._ai_integration.analyze_evidence_quality(
            session.sources,
            themes,
        )

        # Get safety information
        safety_info = self._ai_integration.extract_safety_information(session.sources)
        evidence_annotations = self._build_evidence_annotations(
            session=session,
            analysis=analysis_result,
            validation=validation_result,
            claims=claims,
        )

        report = {
            "query": session.query,
            "session_id": session.session_id,
            "depth": session.depth.value,
            "started_at": session.started_at.isoformat(),
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "execution_time_seconds": session.execution_time_seconds,
            "total_sources": session.total_sources,
            "analysis": analysis_result.model_dump(mode="python"),
            "claims": evidence_annotations["claims"],
            "evidence_strength": evidence_annotations["summary"],
            "unresolved_gaps": evidence_annotations["unresolved_gaps"],
            "validation_rationale": evidence_annotations["validation_rationale"],
            "iteration_summary": evidence_annotations["iteration_summary"],
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
        analysis: AnalysisResult,
    ) -> str:
        """Generate executive summary section.

        This is the canonical implementation for Executive Summary generation.
        All summary generation should flow through this method.

        The summary presents research insights directly, avoiding:
        - Prompt restatement ("This research investigated...")
        - Methodology chatter ("Analysis was performed...")
        - Inline gap inventories

        Args:
            session: Research session.
            analysis: Analysis results.

        Returns:
            Executive summary text (at most 2 short paragraphs).

        Note:
            Summary constraints are defined by module-level constants:
            - EXECUTIVE_SUMMARY_MAX_PARAGRAPHS: Maximum number of paragraphs
            - EXECUTIVE_SUMMARY_MAX_THEMES: Maximum themes to list
            - EXECUTIVE_SUMMARY_MAX_CHARACTERS: Target character budget
            - EXECUTIVE_SUMMARY_BANNED_PHRASES: Phrases that should not appear
            - EXECUTIVE_SUMMARY_GAPS_POINTER: Text to use for gaps reference
        """
        paragraphs = []

        # Paragraph 1: Key findings and themes (insight-first approach)
        if analysis.key_findings:
            key_count = len(analysis.key_findings)
            themes = analysis.themes[:EXECUTIVE_SUMMARY_MAX_THEMES]

            # Build insight-first paragraph
            finding_summary = f"Analysis identified {key_count} key finding"
            if key_count != 1:
                finding_summary += "s"
            finding_summary += "."

            if themes:
                finding_summary += f" Primary themes: {', '.join(themes)}."
            paragraphs.append(finding_summary)
        elif analysis.themes:
            # No findings but have themes
            themes = analysis.themes[:EXECUTIVE_SUMMARY_MAX_THEMES]
            paragraphs.append(f"Key themes identified: {', '.join(themes)}.")
        else:
            # Minimal case: just note the scope
            paragraphs.append(
                f"Analysis reviewed {session.total_sources} sources."
            )

        # Paragraph 2: Brief gaps pointer (if gaps exist)
        # Use at most one sentence pointing to the gaps section
        gaps = analysis.normalized_gaps()
        if gaps:
            paragraphs.append(EXECUTIVE_SUMMARY_GAPS_POINTER)

        # Enforce character budget by truncating if necessary
        result = "\n\n".join(paragraphs)
        if len(result) > EXECUTIVE_SUMMARY_MAX_CHARACTERS:
            result = result[:EXECUTIVE_SUMMARY_MAX_CHARACTERS].rsplit(" ", 1)[0] + "."

        return result

    def _generate_detailed_analysis(
        self,
        session: ResearchSession,
        analysis: AnalysisResult,
    ) -> str:
        """Generate detailed analysis section.

        Args:
            session: Research session.
            analysis: Analysis results.

        Returns:
            Detailed analysis text.
        """
        sections = []

        # Add key findings with detailed analysis first
        if analysis.key_findings:
            sections.append("### Detailed Key Findings\n")

            for i, finding in enumerate(analysis.key_findings, 1):
                finding_obj = self._coerce_finding(finding)

                # Finding title
                sections.append(f"#### Finding {i}: {finding_obj.title}")

                # Detailed description
                if finding_obj.description:
                    description = self._clean_description(finding_obj.description)
                    sections.append(description)

                # Detail points (evidence-backed bullets)
                if finding_obj.detail_points:
                    sections.append("\n**Evidence-backed Details:**")
                    for point in finding_obj.detail_points:
                        clean_point = self._clean_description(str(point))
                        if clean_point and len(clean_point) > 10:
                            sections.append(f"- {clean_point}")

                # Supporting sources
                if finding_obj.evidence:
                    sections.append("\n**Supporting Sources:**")
                    for url in finding_obj.evidence:
                        sanitized_url = sanitize_url(url)
                        for j, source in enumerate(session.sources, 1):
                            if source.url == url or source.url == sanitized_url:
                                title = self._clean_title(source.title or "Untitled")
                                sections.append(f"- [{title}]({sanitized_url}) [{j}]")
                                break

                # Claim annotation for evidence strength
                claim_annotation = self._claim_annotation_summary(finding_obj.claims)
                if claim_annotation:
                    sections.append("\n")
                    sections.append(f"**Evidence Strength:** {claim_annotation['strength_label']}")
                    sections.append(f"**Freshness:** {claim_annotation['freshness_note']}")
                    sections.append(
                        f"**Primary-Source Coverage:** {claim_annotation['primary_source_note']}"
                    )
                    sections.append(f"**Contradiction Note:** {claim_annotation['contradiction_note']}")
                elif finding_obj.confidence:
                    sections.append("\n")
                    sections.append(f"**Confidence:** {finding_obj.confidence.capitalize()}")

                sections.append("\n\n")

        # Then use detailed theme data if available
        themes_detailed = analysis.themes_detailed

        if themes_detailed:
            sections.append("### Thematic Analysis\n")

            # Use AI-generated detailed themes with deduplication
            cited_sources: set[str] = set()  # Track which sources have been cited

            for theme in themes_detailed:
                sections.append(f"#### {theme['name']}\n")

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
                                # Use sanitized URL
                                sanitized_url = sanitize_url(url)
                                sections.append(f"- [{title}]({sanitized_url})")
                                cited_sources.add(url)
                                break
                    sections.append("")
        elif analysis.themes and not analysis.key_findings:
            # Fallback to basic theme names if no detailed themes or findings
            sections.append("### Thematic Analysis\n")
            themes = analysis.themes
            for theme in themes:
                sections.append(f"#### {theme}")
                sections.append(
                    f"Analysis related to {theme} is based on multiple sources. "
                    "Further investigation may provide additional insights.\n"
                )

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
        analysis: AnalysisResult,
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
        consensus = analysis.consensus_points
        if consensus:
            for point in consensus:
                sections.append(f"- {point}")
        else:
            sections.append("- No clear consensus points identified")
        sections.append("")

        # Contention points
        sections.append("### Points of Contention")
        contention = analysis.contention_points
        if contention:
            for point in contention:
                sections.append(f"- {point}")
        else:
            sections.append("- No major points of contention identified")

        # ENHANCED: Cross-reference claims with evidence
        claims = analysis.cross_reference_claims
        if claims:
            sections.append("\n### Detailed Claims Analysis")
            for claim in claims:
                sections.append(f"\n**Claim:** {claim.claim}")
                if claim.supporting_sources:
                    sections.append(
                        f"- **Supporting:** {len(claim.supporting_sources)} sources"
                    )
                if claim.contradicting_sources:
                    sections.append(
                        f"- **Contradicting:** {len(claim.contradicting_sources)} sources"
                    )
                if claim.consensus_level:
                    consensus_pct = claim.consensus_level * 100
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
        analysis: AnalysisResult,
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
        method = analysis.analysis_method or "basic"

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
        analysis: AnalysisResult,
        evidence_annotations: dict[str, Any],
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
        themes = analysis.themes_detailed
        if not themes:
            themes = [{"name": t, "supporting_sources": []} for t in analysis.themes]

        evidence_quality = self._ai_integration.analyze_evidence_quality(
            session.sources,
            themes,
        )

        summary = evidence_annotations["summary"]
        lines.append("### Evidence Strength\n")
        lines.append(
            f"- Strong findings: {summary['strong_claims']}"
        )
        lines.append(
            f"- Moderate findings: {summary['moderate_claims']}"
        )
        lines.append(
            f"- Weak findings: {summary['weak_claims']}"
        )
        lines.append(
            f"- Contested findings: {summary['contested_claims']}"
        )
        lines.append("")

        lines.append("### Freshness Notes\n")
        lines.append(summary["freshness_note"])
        lines.append("")

        lines.append("### Primary-Source Coverage\n")
        lines.append(summary["primary_source_note"])
        lines.append("")

        lines.append("### Contradiction Notes\n")
        lines.append(summary["contradiction_note"])
        lines.append("")

        if evidence_annotations["iteration_summary"]:
            iteration_summary = evidence_annotations["iteration_summary"]
            lines.append("### Iteration Summary\n")
            lines.append(iteration_summary["summary"])
            for delta in iteration_summary["deltas"]:
                lines.append(f"- {delta}")
            lines.append("")

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

    def _validation_result(self, session: ResearchSession) -> ValidationResult | None:
        """Return typed validation metadata when the session contains it."""
        validation = session.metadata.get("validation", {})
        if not validation:
            return None
        return ValidationResult.model_validate(validation)

    def _coerce_finding(self, finding: AnalysisFinding | str) -> AnalysisFinding:
        """Normalize mixed finding shapes into a typed finding."""
        if isinstance(finding, AnalysisFinding):
            return finding
        return AnalysisFinding(title=str(finding), description=str(finding))

    def _collect_claims(self, analysis: AnalysisResult) -> list[CrossReferenceClaim]:
        """Return all claims attached to the analysis and its findings."""
        claims: list[CrossReferenceClaim] = list(analysis.cross_reference_claims)
        for finding in analysis.key_findings:
            finding_obj = self._coerce_finding(finding)
            claims.extend(finding_obj.claims)
        return claims

    def _build_evidence_annotations(
        self,
        *,
        session: ResearchSession,
        analysis: AnalysisResult,
        validation: ValidationResult | None,
        claims: list[CrossReferenceClaim],
    ) -> dict[str, Any]:
        """Build shared evidence annotation data for markdown and JSON reports."""
        claim_annotations = [self._serialize_claim(claim) for claim in claims]
        strength_counts = {
            "strong": sum(1 for claim in claim_annotations if claim["evidence_strength"] == "strong"),
            "moderate": sum(1 for claim in claim_annotations if claim["evidence_strength"] == "moderate"),
            "weak": sum(1 for claim in claim_annotations if claim["evidence_strength"] == "weak"),
            "contested": sum(1 for claim in claim_annotations if claim["is_contested"]),
        }
        freshness_values = [claim["freshness"] for claim in claim_annotations]
        primary_coverages = [claim["primary_source_coverage_ratio"] for claim in claim_annotations]
        contradiction_values = [claim["contradicting_source_count"] for claim in claim_annotations]
        iteration_summary = self._build_iteration_summary(session)

        unresolved_gaps = [
            {
                "gap": gap.gap_description,
                "importance": gap.importance or "medium",
                "suggested_queries": gap.suggested_queries,
            }
            for gap in analysis.normalized_gaps()
        ]
        if validation:
            for issue in validation.issues:
                unresolved_gaps.append({"gap": issue, "importance": "high", "suggested_queries": []})
            for warning in validation.warnings:
                unresolved_gaps.append({"gap": warning, "importance": "medium", "suggested_queries": []})

        summary = {
            "strong_claims": strength_counts["strong"],
            "moderate_claims": strength_counts["moderate"],
            "weak_claims": strength_counts["weak"],
            "contested_claims": strength_counts["contested"],
            "freshness_note": self._freshness_summary_note(freshness_values),
            "primary_source_note": self._primary_source_summary_note(primary_coverages),
            "contradiction_note": self._contradiction_summary_note(claim_annotations, contradiction_values),
        }

        validation_rationale = {
            "status": validation.evidence_diagnosis if validation else "unknown",
            "quality_score": validation.quality_score if validation else None,
            "failure_modes": validation.failure_modes if validation else [],
            "recommendations": validation.recommendations if validation else [],
            "rationale": self._validation_rationale_text(validation, summary, unresolved_gaps),
        }

        return {
            "claims": claim_annotations,
            "summary": summary,
            "unresolved_gaps": unresolved_gaps,
            "validation_rationale": validation_rationale,
            "iteration_summary": iteration_summary,
        }

    def _serialize_claim(self, claim: CrossReferenceClaim) -> dict[str, Any]:
        """Serialize one claim into an evidence-oriented report payload."""
        supporting = claim.supporting_sources
        contradicting = claim.contradicting_sources
        support_count = len(supporting)
        contradiction_count = len(contradicting)
        primary_ratio = self._primary_source_ratio(supporting)
        evidence_strength = self._claim_strength_label(claim, primary_ratio)
        return {
            "claim": claim.claim,
            "confidence": claim.confidence or "unknown",
            "consensus_level": claim.consensus_level,
            "evidence_strength": evidence_strength,
            "supporting_source_count": support_count,
            "contradicting_source_count": contradiction_count,
            "is_contested": contradiction_count > 0,
            "freshness": (claim.freshness or ClaimFreshness.UNKNOWN).value,
            "freshness_note": self._freshness_note(claim.freshness or ClaimFreshness.UNKNOWN),
            "primary_source_coverage_ratio": round(primary_ratio, 2),
            "primary_source_note": self._primary_source_note(primary_ratio),
            "contradiction_note": self._contradiction_note(support_count, contradiction_count),
            "validation_rationale": self._claim_validation_rationale(
                claim=claim,
                evidence_strength=evidence_strength,
                primary_ratio=primary_ratio,
            ),
            "supporting_sources": [self._serialize_evidence_item(item) for item in supporting],
            "contradicting_sources": [self._serialize_evidence_item(item) for item in contradicting],
        }

    def _serialize_evidence_item(self, evidence: ClaimEvidence) -> dict[str, Any]:
        """Serialize evidence details needed for downstream tooling."""
        return {
            "url": evidence.url,
            "title": evidence.title,
            "freshness": evidence.freshness.value,
            "evidence_type": evidence.evidence_type.value,
            "published_date": evidence.published_date,
        }

    def _claim_annotation_summary(self, claims: list[CrossReferenceClaim]) -> dict[str, str] | None:
        """Collapse multiple claims into one compact finding-level annotation."""
        if not claims:
            return None
        serialized = [self._serialize_claim(claim) for claim in claims]
        strong_count = sum(1 for claim in serialized if claim["evidence_strength"] == "strong")
        weak_count = sum(1 for claim in serialized if claim["evidence_strength"] == "weak")
        contested_count = sum(1 for claim in serialized if claim["is_contested"])
        return {
            "strength_label": (
                "strong"
                if strong_count == len(serialized)
                else "weak" if weak_count else "mixed"
            ),
            "freshness_note": self._freshness_summary_note(
                [claim["freshness"] for claim in serialized]
            ),
            "primary_source_note": self._primary_source_summary_note(
                [claim["primary_source_coverage_ratio"] for claim in serialized]
            ),
            "contradiction_note": (
                "Some evidence is contested across sources."
                if contested_count
                else "No direct contradictions were attached to this finding."
            ),
        }

    def _build_iteration_summary(self, session: ResearchSession) -> dict[str, Any] | None:
        """Summarize iterative follow-up search when it materially changed the run."""
        history = session.metadata.get("iteration_history", [])
        if len(history) < 2:
            return None

        first = history[0]
        last = history[-1]
        deltas: list[str] = []
        source_delta = int(last.get("source_count", 0)) - int(first.get("source_count", 0))
        if source_delta > 0:
            deltas.append(f"Sources increased by {source_delta} across follow-up iterations.")

        first_quality = first.get("quality_score")
        last_quality = last.get("quality_score")
        if first_quality is not None and last_quality is not None:
            quality_delta = float(last_quality) - float(first_quality)
            if abs(quality_delta) >= 0.05:
                direction = "improved" if quality_delta > 0 else "declined"
                deltas.append(f"Validation quality {direction} by {abs(quality_delta):.2f}.")

        gap_delta = int(first.get("gap_count", 0)) - int(last.get("gap_count", 0))
        if gap_delta > 0:
            deltas.append(f"Open gaps decreased by {gap_delta}.")

        if not deltas:
            return None

        return {
            "iterations": len(history),
            "summary": "Follow-up search materially changed the final report.",
            "deltas": deltas,
        }

    def _claim_strength_label(self, claim: CrossReferenceClaim, primary_ratio: float) -> str:
        """Classify evidence strength for one claim."""
        support_count = len(claim.supporting_sources)
        contradiction_count = len(claim.contradicting_sources)
        confidence = (claim.confidence or "low").lower()
        if (
            support_count >= 3
            and contradiction_count == 0
            and primary_ratio >= 0.5
            and confidence == "high"
        ):
            return "strong"
        if support_count >= 2 and contradiction_count <= 1 and confidence in {"high", "medium"}:
            return "moderate"
        return "weak"

    def _primary_source_ratio(self, evidence: list[ClaimEvidence]) -> float:
        """Return the share of supporting evidence from primary-like sources."""
        if not evidence:
            return 0.0
        primary_like = {
            EvidenceType.PRIMARY,
            EvidenceType.OFFICIAL,
            EvidenceType.RESEARCH,
        }
        count = sum(1 for item in evidence if item.evidence_type in primary_like)
        return count / len(evidence)

    def _freshness_note(self, freshness: ClaimFreshness) -> str:
        """Describe the freshness bucket in plain language."""
        mapping = {
            ClaimFreshness.CURRENT: "Backed by current evidence.",
            ClaimFreshness.RECENT: "Backed by recent evidence.",
            ClaimFreshness.DATED: "Relies on older evidence.",
            ClaimFreshness.UNKNOWN: "Evidence freshness could not be determined.",
        }
        return mapping[freshness]

    def _primary_source_note(self, ratio: float) -> str:
        """Describe primary-source coverage as a short sentence."""
        if ratio >= 0.7:
            return "Mostly supported by primary, official, or research sources."
        if ratio >= 0.35:
            return "Partially supported by primary, official, or research sources."
        return "Relies heavily on secondary or unattributed sources."

    def _contradiction_note(self, support_count: int, contradiction_count: int) -> str:
        """Describe contradiction pressure for one claim."""
        if contradiction_count == 0:
            return "No direct contradictory evidence was attached."
        if contradiction_count >= support_count:
            return "Contradictory evidence is as strong as or stronger than the support."
        return "Some contradictory evidence remains unresolved."

    def _claim_validation_rationale(
        self,
        *,
        claim: CrossReferenceClaim,
        evidence_strength: str,
        primary_ratio: float,
    ) -> str:
        """Explain why a claim received its evidence annotation."""
        return (
            f"Rated {evidence_strength} because it has {len(claim.supporting_sources)} supporting "
            f"source(s), {len(claim.contradicting_sources)} contradicting source(s), "
            f"{primary_ratio:.0%} primary-source coverage, and "
            f"{(claim.freshness or ClaimFreshness.UNKNOWN).value} freshness."
        )

    def _freshness_summary_note(self, freshness_values: list[str]) -> str:
        """Summarize freshness across all claims."""
        if not freshness_values:
            return "No claim-level freshness annotations were available."
        if all(value == ClaimFreshness.CURRENT.value for value in freshness_values):
            return "All annotated claims are backed by current evidence."
        if any(value == ClaimFreshness.DATED.value for value in freshness_values):
            return "Some annotated claims rely on dated evidence and should be revisited."
        if any(value == ClaimFreshness.UNKNOWN.value for value in freshness_values):
            return "Some evidence lacks publish dates, so freshness is only partially known."
        return "Most annotated claims are backed by recent evidence."

    def _primary_source_summary_note(self, primary_coverages: list[float]) -> str:
        """Summarize primary-source coverage across all claims."""
        if not primary_coverages:
            return "Primary-source coverage could not be estimated."
        average = sum(primary_coverages) / len(primary_coverages)
        return self._primary_source_note(average)

    def _contradiction_summary_note(
        self,
        claim_annotations: list[dict[str, Any]],
        contradiction_values: list[int],
    ) -> str:
        """Summarize contradiction pressure across the report."""
        if not claim_annotations:
            return "No structured claim-level contradiction analysis was available."
        if all(value == 0 for value in contradiction_values):
            return "No direct contradictions were attached to the structured claims."
        contested = sum(1 for claim in claim_annotations if claim["is_contested"])
        return f"{contested} claim(s) include contradictory evidence that remains unresolved."

    def _validation_rationale_text(
        self,
        validation: ValidationResult | None,
        summary: dict[str, Any],
        unresolved_gaps: list[dict[str, Any]],
    ) -> str:
        """Create one high-level rationale sentence for downstream consumers."""
        if validation is None:
            return "No validation metadata was captured for this report."
        rationale = (
            f"Validation diagnosed the report as {validation.evidence_diagnosis} "
            f"with quality score {validation.quality_score:.2f}."
        )
        if summary["contested_claims"]:
            rationale += f" {summary['contested_claims']} contested claim(s) lowered confidence."
        if unresolved_gaps:
            rationale += f" {len(unresolved_gaps)} unresolved gap(s) remain."
        return rationale

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

        # Sources Summary
        lines.append("### Sources Summary\n")
        total_sources = len(session.sources)
        lines.append(f"- **Total Sources:** {total_sources}\n")
        lines.append("- **Top Source Types:**")
        # Sort types by count and show top 3
        type_counts = {t: len(s) for t, s in sources_by_type.items()}
        top_types = sorted(type_counts.items(), key=lambda x: -x[1])[:3]
        for source_type, count in top_types:
            lines.append(f"  - {source_type}: {count}")
        lines.append("\nSee the full catalog below for detailed source listings.\n")

        # Full Catalog
        lines.append("### Full Catalog\n")

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
