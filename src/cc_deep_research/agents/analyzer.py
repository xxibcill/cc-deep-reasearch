"""Analyzer agent implementation.

The analyzer agent is responsible for:
- Analyzing collected sources and information
- Synthesizing findings from multiple sources
- Identifying key themes and patterns
- Detecting consensus and disagreement across sources
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from cc_deep_research.agents.ai_analysis_service import AIAnalysisService
from cc_deep_research.models import (
    AnalysisFinding,
    AnalysisGap,
    AnalysisResult,
    ClaimEvidence,
    CrossReferenceClaim,
    SearchResultItem,
)
from cc_deep_research.text_normalization import normalize_content

if TYPE_CHECKING:
    from cc_deep_research.llm.router import LLMRouter
    from cc_deep_research.monitoring import ResearchMonitor
    from cc_deep_research.prompts import PromptRegistry


class AnalyzerAgent:
    """Agent that analyzes and synthesizes collected information.

    This agent:
    - Analyzes content from collected sources
    - Identifies key themes and findings
    - Detects consensus and disagreement across sources
    - Synthesizes coherent analysis
    """

    def __init__(
        self,
        config: dict[str, Any],
        monitor: ResearchMonitor | None = None,
        llm_router: "LLMRouter | None" = None,
        prompt_registry: "PromptRegistry | None" = None,
    ) -> None:
        """Initialize the analyzer agent.

        Args:
            config: Agent configuration dictionary.
            monitor: Optional research monitor.
            llm_router: Optional LLM router for shared routing layer.
            prompt_registry: Optional prompt registry with overrides.
        """
        self._config = config
        self._ai_service = AIAnalysisService(
            config,
            monitor=monitor,
            llm_router=llm_router,
            agent_id="analyzer",
            prompt_registry=prompt_registry,
        )

    def analyze_sources(
        self,
        sources: list[SearchResultItem],
        query: str,
    ) -> AnalysisResult:
        """Analyze collected sources and extract insights.

        Args:
            sources: List of search result items to analyze.
            query: Original research query.

        Returns:
            Dictionary containing analysis results including:
            - key_findings: List of key findings
            - themes: Identified themes
            - consensus_points: Points where sources agree
            - contention_points: Points where sources disagree
            - gaps: Areas with insufficient information
        """
        if not sources:
            return self._empty_analysis(query)

        # Clean source content before analysis
        cleaned_sources = self._clean_sources_content(sources)

        # Check if we have sufficient content for AI analysis
        has_content = any(s.content and len(s.content) > 200 for s in cleaned_sources)

        if not has_content:
            # Fall back to basic analysis without AI
            return self._basic_analysis(cleaned_sources, query)

        self._ai_service.reset_run_tracking()

        # Use AI-powered analysis
        themes = self._ai_service.extract_themes_semantically(
            sources=cleaned_sources,
            query=query,
            num_themes=self._config.get("ai_num_themes", 8),
        )

        # Perform cross-reference analysis
        cross_ref = self._ai_service.analyze_cross_reference(
            sources=cleaned_sources, themes=themes
        )

        # Identify gaps
        gaps = self._ai_service.identify_gaps(
            sources=cleaned_sources, query=query, themes=themes
        )

        # Synthesize findings
        key_findings = self._ai_service.synthesize_findings(
            sources=cleaned_sources,
            themes=themes,
            cross_ref=cross_ref,
            gaps=gaps,
            query=query,
        )

        typed_claims = self._build_claims(
            raw_claims=cross_ref.get("cross_reference_claims", []),
            sources=cleaned_sources,
            fallback_themes=themes,
        )
        typed_findings = self._build_findings(key_findings, typed_claims)
        analysis_method = (
            "ai_semantic" if self._ai_service.routed_llm_used else "basic_keyword"
        )

        return AnalysisResult(
            key_findings=typed_findings,
            themes=[t["name"] for t in themes],
            themes_detailed=themes,
            consensus_points=self._extract_consensus_claims(cross_ref.get("consensus_points", [])),
            contention_points=self._extract_consensus_claims(cross_ref.get("disagreement_points", [])),
            cross_reference_claims=typed_claims,
            gaps=gaps,
            source_count=len(cleaned_sources),
            analysis_method=analysis_method,
        )

    def _clean_sources_content(
        self, sources: list[SearchResultItem]
    ) -> list[SearchResultItem]:
        """Clean content from all sources.

        Args:
            sources: List of sources to clean.

        Returns:
            List of sources with cleaned content.
        """
        cleaned = []

        for source in sources:
            # Create a copy to avoid modifying the original
            cleaned_source = source.model_copy(deep=True)

            # Clean title
            if cleaned_source.title:
                cleaned_source.title = self._clean_source_content(
                    cleaned_source.title, is_title=True
                )

            # Clean snippet
            if cleaned_source.snippet:
                cleaned_source.snippet = self._clean_source_content(
                    cleaned_source.snippet, is_title=False
                )

            # Clean content
            if cleaned_source.content:
                raw_cleaned = self._clean_source_content(
                    cleaned_source.content, is_title=False
                )
                # Apply truncation detection and repair after content cleaning
                cleaned_source.content = self.detect_and_fix_truncations(raw_cleaned)

            cleaned.append(cleaned_source)

        return cleaned

    def _extract_consensus_claims(self, points: list[str]) -> list[str]:
        """Extract claim strings from consensus/contention point dicts.

        Args:
            points: List of dicts with 'claim' field, or list of strings.

        Returns:
            List of claim strings.
        """
        return [p["claim"] if isinstance(p, dict) else str(p) for p in points]

    def detect_and_fix_truncations(self, text: str) -> str:
        """Detect and repair common truncation patterns in AI-generated text.

        Args:
            text: Text to check and repair.

        Returns:
            Text with common truncation patterns repaired.
        """
        if not text:
            return text

        # Common AI truncation patterns with replacements
        truncation_repairs = [
            (r'\bFor the vast m\.\.', 'For the vast majority'),
            (r'\bFor the vast M\.\.', 'For the vast majority'),
            (r'\b[A-Z][a-z]{1,3}\.\.\.', lambda m: m.group(0) + 'ing'),  # m... -> ...ing
            (r'\b[A-Z][a-z]{1,3}n\.\.\.', lambda m: m.group(0) + 'tion'),  # An... -> ...tion
            (r'\b[A-Z][a-z]{2,3}ut\b', lambda m: m.group(0)),  # ...ut -> remove ut
        ]

        fixed_text = text
        for pattern, replacement in truncation_repairs:
            if callable(replacement):
                fixed_text = re.sub(pattern, replacement, fixed_text, flags=re.IGNORECASE)
            else:
                fixed_text = re.sub(pattern, replacement, fixed_text, flags=re.IGNORECASE)

        return fixed_text

    def _clean_source_content(self, content: str, is_title: bool = False) -> str:
        """Clean content by removing HTML fragments, navigation text, and artifacts.

        Args:
            content: Content to clean.
            is_title: Whether this is a title (shorter cleaning).

        Returns:
            Cleaned content.
        """
        # Use the centralized text normalization helper
        return normalize_content(content, is_title=is_title)

    def _basic_analysis(
        self, sources: list[SearchResultItem], query: str
    ) -> AnalysisResult:
        """Perform basic analysis without AI (fallback).

        Args:
            sources: List of sources.
            query: Research query.

        Returns:
            Basic analysis results.
        """
        # Keep existing placeholder logic as fallback
        # This ensures backward compatibility when content is unavailable
        findings = self._extract_findings(sources, query)
        themes = self._identify_themes(sources)
        cross_ref = self._perform_cross_reference(sources)
        gaps = self._identify_gaps(sources, query)
        typed_claims = self._build_claims(
            raw_claims=cross_ref["claims"],
            sources=sources,
            fallback_themes=[],
        )
        typed_findings = self._attach_claims_to_fallback_findings(findings, typed_claims)

        return AnalysisResult(
            key_findings=typed_findings,
            themes=themes,
            consensus_points=self._extract_consensus_claims(cross_ref.get("consensus", [])),
            contention_points=self._extract_consensus_claims(cross_ref.get("contention", [])),
            cross_reference_claims=typed_claims,
            gaps=gaps,
            source_count=len(sources),
            analysis_method="basic_keyword",
        )

    def _extract_findings(
        self, sources: list[SearchResultItem], query: str  # noqa: ARG002
    ) -> list[AnalysisFinding]:
        """Extract key findings from sources.

        Args:
            sources: List of sources to analyze.
            query: Research query.

        Returns:
            List of findings with titles and descriptions.

        Note: This is a fallback implementation used when content is insufficient.
        """
        findings: list[AnalysisFinding] = []

        # Placeholder: create findings from source titles/snippets
        for _i, source in enumerate(sources[:5]):  # Top 5 sources
            if source.title:
                findings.append(
                    AnalysisFinding(
                        title=source.title,
                        description=source.snippet or "No description available",
                        source=source.url,
                    )
                )

        return findings

    def _identify_themes(
        self, sources: list[SearchResultItem]
    ) -> list[AnalysisGap]:
        """Identify major themes across sources.

        Args:
            sources: List of sources to analyze.

        Returns:
            List of theme names.

        Note: This is a fallback implementation used when content is insufficient.
        """
        # Placeholder: simple keyword-based theme identification
        themes = set()

        for source in sources[:10]:  # Analyze top 10
            words = source.title.lower().split() if source.title else []
            # Use longer words as potential themes
            for word in words:
                if len(word) > 5:
                    themes.add(word.capitalize())

        return list(themes)[:5]  # Return top 5 themes

    def _perform_cross_reference(
        self, sources: list[SearchResultItem]  # noqa: ARG002
    ) -> dict[str, list[str] | list[dict[str, Any]]]:
        """Perform cross-reference analysis across sources.

        Args:
            sources: List of sources to cross-reference.

        Returns:
            Dictionary with consensus and contention points.

        Note: This is a fallback implementation used when content is insufficient.
        """
        # Placeholder results
        return {
            "consensus": ["Sources agree on core concepts"],
            "contention": [],
            "claims": [
                {
                    "claim": source.title or source.snippet or source.url,
                    "supporting_sources": [self._source_to_claim_evidence(source)],
                    "contradicting_sources": [],
                    "consensus_level": 0.2,
                }
                for source in sources[:5]
                if source.title or source.snippet
            ],
        }

    def _identify_gaps(
        self, sources: list[SearchResultItem], query: str  # noqa: ARG002
    ) -> list[str]:
        """Identify information gaps in the research.

        Args:
            sources: List of sources analyzed.
            query: Research query.

        Returns:
            List of identified gaps.

        Note: This is a fallback implementation used when content is insufficient.
        """
        gaps: list[AnalysisGap] = []

        if len(sources) < 5:
            gaps.append(AnalysisGap(gap_description="Limited number of sources collected"))

        # Check for content depth
        has_long_content = any(len(s.content or "") > 500 for s in sources)
        if not has_long_content:
            gaps.append(
                AnalysisGap(
                    gap_description="Sources lack detailed content for deep analysis"
                )
            )

        return gaps

    def _empty_analysis(self, _query: str) -> AnalysisResult:
        """Return empty analysis structure.

        Args:
            query: Research query.

        Returns:
            Empty analysis dictionary.
        """
        return AnalysisResult(
            key_findings=[],
            themes=[],
            consensus_points=[],
            contention_points=[],
            gaps=[AnalysisGap(gap_description="No sources to analyze")],
            source_count=0,
            analysis_method="empty",
        )

    def synthesize_report(
        self, analysis: AnalysisResult | dict[str, Any], query: str  # noqa: ARG002
    ) -> str:
        """Synthesize analysis into a coherent report section.

        Args:
            analysis: Analysis results from analyze_sources.
            query: Research query.

        Returns:
            Synthesized text report.

        Note: This is a placeholder implementation.
        """
        analysis_result = AnalysisResult.model_validate(analysis)
        sections = []

        if analysis_result.key_findings:
            sections.append("## Key Findings\n")
            for finding in analysis_result.key_findings:
                if isinstance(finding, AnalysisFinding):
                    sections.append(f"- {finding.title}")
                    sections.append(f"  {finding.description}\n")
                else:
                    sections.append(f"- {finding}\n")

        if analysis_result.gaps:
            sections.append("\n## Gaps\n")
            for gap in analysis_result.normalized_gaps():
                sections.append(f"- {gap.gap_description}\n")

        return "\n".join(sections)

    def _build_claims(
        self,
        *,
        raw_claims: list[dict[str, Any]],
        sources: list[SearchResultItem],
        fallback_themes: list[dict[str, Any]],
    ) -> list[CrossReferenceClaim]:
        """Normalize raw claim payloads into typed claim models."""
        source_lookup = {source.url: source for source in sources}
        typed_claims: list[CrossReferenceClaim] = []

        for claim in raw_claims:
            supporting = self._claim_evidence_list(
                claim.get("supporting_sources", []),
                source_lookup,
            )
            contradicting = self._claim_evidence_list(
                claim.get("contradicting_sources", []),
                source_lookup,
            )
            typed_claims.append(
                CrossReferenceClaim(
                    claim=str(claim.get("claim", "Unnamed claim")),
                    supporting_sources=supporting,
                    contradicting_sources=contradicting,
                    consensus_level=float(claim.get("consensus_level", 0.0) or 0.0),
                    confidence=claim.get("confidence"),
                    freshness=claim.get("freshness"),
                    evidence_type=claim.get("evidence_type"),
                )
            )

        if typed_claims:
            return typed_claims

        for theme in fallback_themes[:5]:
            supporting = self._claim_evidence_list(
                theme.get("supporting_sources", []),
                source_lookup,
            )
            if not supporting:
                continue
            typed_claims.append(
                CrossReferenceClaim(
                    claim=f"Key findings related to {theme.get('name', 'this topic')}",
                    supporting_sources=supporting,
                    consensus_level=min(1.0, len(supporting) / 5),
                )
            )

        return typed_claims

    def _build_findings(
        self,
        raw_findings: list[dict[str, Any]],
        claims: list[CrossReferenceClaim],
    ) -> list[AnalysisFinding]:
        """Normalize AI finding payloads and link them to evidence-backed claims."""
        findings: list[AnalysisFinding] = []
        for finding in raw_findings:
            evidence_urls = [
                entry.url
                for entry in _normalize_finding_evidence(finding.get("evidence", []))
            ]
            finding_claims = self._match_claims_to_finding(
                title=str(finding.get("title", "")),
                description=str(finding.get("description", "")),
                evidence_urls=evidence_urls,
                claims=claims,
            )
            findings.append(
                AnalysisFinding(
                    title=str(finding.get("title", "Unnamed finding")),
                    summary=str(finding.get("summary", finding.get("description", ""))[:200]),
                    description=str(finding.get("description", "")),
                    detail_points=list(finding.get("detail_points", [])),
                    evidence=evidence_urls,
                    confidence=finding.get("confidence"),
                    claims=finding_claims,
                )
            )
        return findings

    def _attach_claims_to_fallback_findings(
        self,
        findings: list[AnalysisFinding],
        claims: list[CrossReferenceClaim],
    ) -> list[AnalysisFinding]:
        """Link fallback findings to the closest typed claims."""
        linked: list[AnalysisFinding] = []
        for finding in findings:
            finding_claims = self._match_claims_to_finding(
                title=finding.title,
                description=finding.description,
                evidence_urls=list(finding.evidence),
                claims=claims,
            )
            linked.append(
                finding.model_copy(
                    update={
                        "claims": finding_claims,
                        "evidence": (
                            list(finding.evidence)
                            or [
                                evidence.url
                                for claim in finding_claims
                                for evidence in claim.supporting_sources
                            ]
                        ),
                    }
                )
            )
        return linked

    def _match_claims_to_finding(
        self,
        *,
        title: str,
        description: str,
        evidence_urls: list[str],
        claims: list[CrossReferenceClaim],
    ) -> list[CrossReferenceClaim]:
        """Attach the most relevant claims to one finding."""
        title_text = f"{title} {description}".lower()
        evidence_url_set = set(evidence_urls)
        matched: list[CrossReferenceClaim] = []

        for claim in claims:
            claim_urls = {entry.url for entry in claim.supporting_sources}
            if evidence_url_set and claim_urls.intersection(evidence_url_set):
                matched.append(claim)
                continue
            if claim.claim.lower() in title_text or title.lower() in claim.claim.lower():
                matched.append(claim)

        return matched[:3]

    def _claim_evidence_list(
        self,
        entries: list[Any],
        source_lookup: dict[str, SearchResultItem],
    ) -> list[ClaimEvidence]:
        """Convert raw evidence references into typed claim evidence."""
        normalized: list[ClaimEvidence] = []
        for entry in entries:
            if isinstance(entry, str) and entry in source_lookup:
                normalized.append(self._source_to_claim_evidence(source_lookup[entry]))
                continue
            if isinstance(entry, dict):
                url = entry.get("url") or entry.get("source_url")
                if isinstance(url, str) and url in source_lookup:
                    source_evidence = self._source_to_claim_evidence(source_lookup[url])
                    merged = source_evidence.model_copy(
                        update={
                            "title": entry.get("title", source_evidence.title),
                            "snippet": entry.get("snippet", source_evidence.snippet),
                            "published_date": entry.get(
                                "published_date",
                                source_evidence.published_date,
                            ),
                            "source_metadata": {
                                **source_evidence.source_metadata,
                                **(
                                    entry.get("source_metadata", {})
                                    if isinstance(entry.get("source_metadata"), dict)
                                    else {}
                                ),
                            },
                        }
                    )
                    normalized.append(merged)
                    continue
            evidence = ClaimEvidence.model_validate(entry)
            if evidence.url in source_lookup and not evidence.query_provenance:
                source_evidence = self._source_to_claim_evidence(source_lookup[evidence.url])
                evidence = source_evidence.model_copy(
                    update={
                        "title": evidence.title or source_evidence.title,
                        "snippet": evidence.snippet or source_evidence.snippet,
                        "published_date": evidence.published_date or source_evidence.published_date,
                        "source_metadata": {
                            **source_evidence.source_metadata,
                            **evidence.source_metadata,
                        },
                    }
                )
            normalized.append(evidence)
        return normalized

    def _source_to_claim_evidence(self, source: SearchResultItem) -> ClaimEvidence:
        """Project a collected source into claim evidence with provenance."""
        return ClaimEvidence.model_validate(source)


def _normalize_finding_evidence(entries: list[Any]) -> list[ClaimEvidence]:
    """Normalize synthesized finding evidence into typed evidence entries."""
    normalized: list[ClaimEvidence] = []
    for entry in entries:
        try:
            normalized.append(ClaimEvidence.model_validate(entry))
        except Exception:
            continue
    return normalized


__all__ = ["AnalyzerAgent"]
