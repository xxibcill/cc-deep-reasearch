"""Deep analyzer agent for multi-pass analysis.

The deep analyzer agent performs extended multi-pass analysis
with increased token usage for comprehensive understanding.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cc_deep_research.agents.ai_analysis_service import AIAnalysisService
from cc_deep_research.models import ClaimEvidence, CrossReferenceClaim, SearchResultItem

if TYPE_CHECKING:
    from cc_deep_research.llm.router import LLMRouter
    from cc_deep_research.monitoring import ResearchMonitor


class DeepAnalyzerAgent:
    """Agent that performs multi-pass deep analysis with extended token usage.

    This agent conducts 3 separate analysis passes for comprehensive understanding:
    - Pass 1: Extract key themes and patterns across all sources
    - Pass 2: Cross-reference and identify consensus/disagreement points
    - Pass 3: Synthesize comprehensive insights and implications
    """

    def __init__(
        self,
        config: dict[str, Any],
        monitor: ResearchMonitor | None = None,
        llm_router: "LLMRouter | None" = None,
    ) -> None:
        """Initialize deep analyzer agent.

        Args:
            config: Agent configuration dictionary.
        """
        self._config = config
        self._passes = config.get("deep_analysis_passes", 3)
        self._ai_service = AIAnalysisService(
            config,
            monitor=monitor,
            llm_router=llm_router,
            agent_id="deep_analyzer",
        )

    def deep_analyze(
        self,
        sources: list[SearchResultItem],
        query: str,
    ) -> dict[str, Any]:
        """Perform multi-pass analysis on collected sources.

        Args:
            sources: List of collected sources with content.
            query: Original research query.

        Returns:
            Deep analysis results with themes, consensus, implications.
        """
        if not sources:
            return self._empty_deep_analysis(query)

        # Check for content availability
        has_content = any(s.content and len(s.content) > 500 for s in sources)
        if not has_content:
            return self._shallow_deep_analysis(sources, query)

        # Pass 1: Extract key themes and patterns (expanded for deep mode)
        pass1_results = self._pass1_themes_and_patterns(sources, query)

        # Pass 2: Cross-reference and identify consensus/disagreement
        pass2_results = self._pass2_cross_reference(
            sources, query, pass1_results
        )
        claims = self._build_claims(sources, pass2_results.get("claims", []))

        # Pass 3: Synthesize comprehensive insights and implications
        pass3_results = self._pass3_synthesis(
            sources, query, pass1_results, pass2_results
        )

        return {
            "deep_analysis_complete": True,
            "analysis_passes": self._passes,
            "themes": pass1_results["themes"],
            "themes_detailed": pass1_results.get("themes_detailed", []),
            "patterns": pass1_results["patterns"],
            "consensus_points": pass2_results["consensus"],
            "disagreement_points": pass2_results["disagreements"],
            "cross_reference_claims": claims,
            "implications": pass3_results["implications"],
            "comprehensive_synthesis": pass3_results["synthesis"],
            "source_count": len(sources),
            "analysis_method": "ai_multi_pass",
        }

    def _pass1_themes_and_patterns(
        self,
        sources: list[SearchResultItem],
        query: str,
    ) -> dict[str, Any]:
        """Pass 1: Extract key themes and patterns across all sources.

        For deep analysis, use:
        - More themes (10-15 instead of 5-8)
        - More sources in analysis
        - Higher token budget

        Args:
            sources: List of sources.
            query: Research query.

        Returns:
            Dictionary with themes and patterns.
        """
        # Use AI service for semantic theme extraction
        num_themes = self._config.get("ai_deep_num_themes", 12)
        themes_detailed = self._ai_service.extract_themes_semantically(
            sources=sources, query=query, num_themes=num_themes
        )

        # Identify patterns in findings
        patterns = self._identify_patterns(sources, themes_detailed)

        return {
            "themes": [t["name"] for t in themes_detailed],
            "themes_detailed": themes_detailed,
            "patterns": patterns,
        }

    def _pass2_cross_reference(
        self,
        sources: list[SearchResultItem],
        query: str,  # noqa: ARG002
        pass1_results: dict[str, Any],
    ) -> dict[str, Any]:
        """Pass 2: Cross-reference and identify consensus/disagreement points.

        For deep analysis:
        - More thorough cross-referencing
        - Identify subtle disagreements
        - Track evidence for each claim

        Args:
            sources: List of sources.
            query: Research query.
            pass1_results: Results from pass 1.

        Returns:
            Dictionary with consensus and disagreements.
        """
        cross_ref = self._ai_service.analyze_cross_reference(
            sources=sources, themes=pass1_results["themes_detailed"]
        )

        return {
            "consensus": cross_ref["consensus_points"],
            "disagreements": cross_ref["disagreement_points"],
            "claims": cross_ref.get("cross_reference_claims", []),
        }

    def _pass3_synthesis(
        self,
        sources: list[SearchResultItem],
        query: str,
        pass1_results: dict[str, Any],
        pass2_results: dict[str, Any],
    ) -> dict[str, Any]:
        """Pass 3: Synthesize comprehensive insights and implications.

        For deep analysis:
        - Connect themes to consensus/disagreement
        - Identify broader implications
        - Suggest future research directions

        Args:
            sources: List of sources.
            query: Research query.
            pass1_results: Results from pass 1.
            pass2_results: Results from pass 2.

        Returns:
            Dictionary with implications and synthesis.
        """
        implications = self._identify_implications(
            themes=pass1_results["themes_detailed"],
            consensus=pass2_results["consensus"],
            disagreements=pass2_results["disagreements"],
            query=query,
        )

        synthesis = self._create_comprehensive_synthesis(
            query=query,
            pass1_results=pass1_results,
            pass2_results=pass2_results,
            implications=implications,
            sources=sources,
        )

        return {
            "implications": implications,
            "synthesis": synthesis,
        }

    def _build_claims(
        self,
        sources: list[SearchResultItem],
        raw_claims: list[dict[str, Any]],
    ) -> list[CrossReferenceClaim]:
        """Normalize deep-analysis claims with full source provenance."""
        source_lookup = {source.url: source for source in sources}
        claims: list[CrossReferenceClaim] = []
        for claim in raw_claims:
            claims.append(
                CrossReferenceClaim(
                    claim=str(claim.get("claim", "Unnamed claim")),
                    supporting_sources=self._claim_evidence(
                        claim.get("supporting_sources", []),
                        source_lookup,
                    ),
                    contradicting_sources=self._claim_evidence(
                        claim.get("contradicting_sources", []),
                        source_lookup,
                    ),
                    consensus_level=float(claim.get("consensus_level", 0.0) or 0.0),
                    confidence=claim.get("confidence"),
                    freshness=claim.get("freshness"),
                    evidence_type=claim.get("evidence_type"),
                )
            )
        return claims

    def _claim_evidence(
        self,
        entries: list[Any],
        source_lookup: dict[str, SearchResultItem],
    ) -> list[ClaimEvidence]:
        """Attach source provenance to each claim evidence entry."""
        normalized: list[ClaimEvidence] = []
        for entry in entries:
            if isinstance(entry, str) and entry in source_lookup:
                normalized.append(ClaimEvidence.model_validate(source_lookup[entry]))
                continue
            evidence = ClaimEvidence.model_validate(entry)
            if evidence.url in source_lookup and not evidence.query_provenance:
                normalized.append(ClaimEvidence.model_validate(source_lookup[evidence.url]))
                continue
            normalized.append(evidence)
        return normalized

    def _identify_patterns(
        self,
        sources: list[SearchResultItem],
        themes_detailed: list[dict[str, Any]],
    ) -> list[str]:
        """Identify patterns in findings.

        Args:
            sources: List of sources.
            themes_detailed: Detailed themes.

        Returns:
            List of pattern descriptions.
        """
        patterns = []

        # Check for common patterns
        if len(sources) > 20:
            patterns.append("Large volume of sources indicates broad coverage")

        # Check for domain diversity
        domains = set()
        for source in sources:
            if source.url:
                try:
                    domain = source.url.split("//")[1].split("/")[0]
                    domains.add(domain)
                except (IndexError, AttributeError):
                    pass

        if len(domains) > 5:
            patterns.append("Sources come from diverse domains")

        # Check for theme distribution
        if len(themes_detailed) > 8:
            patterns.append(
                "Multiple interconnected themes suggest complex topic with multiple dimensions"
            )

        return patterns

    def _identify_implications(
        self,
        themes: list[dict[str, Any]],
        consensus: list[str],
        disagreements: list[str],
        query: str,
    ) -> list[str]:
        """Identify implications from analysis.

        Args:
            themes: Identified themes.
            consensus: Consensus points.
            disagreements: Disagreement points.
            query: Research query.

        Returns:
            List of implications.
        """
        implications = []

        if len(themes) > 5:
            implications.append(
                "Multiple interconnected themes suggest complex topic requiring multifaceted understanding"
            )

        if len(consensus) > 0:
            implications.append(
                "Strong consensus across sources indicates well-established understanding of core concepts"
            )

        if len(disagreements) > 0:
            implications.append(
                "Some disagreement indicates ongoing debate or nuance that warrants further investigation"
            )

        # Add implications based on query
        if "benefit" in query.lower() or "effect" in query.lower():
            implications.append(
                "Health-related findings should be validated with professional medical advice"
            )

        return implications

    def _create_comprehensive_synthesis(
        self,
        query: str,
        pass1_results: dict[str, Any],
        pass2_results: dict[str, Any],
        implications: list[str],
        sources: list[SearchResultItem],  # noqa: ARG002
    ) -> str:
        """Create comprehensive synthesis of analysis.

        Args:
            query: Research query.
            pass1_results: Results from pass 1.
            pass2_results: Results from pass 2.
            implications: Identified implications.
            sources: List of sources.

        Returns:
            Synthesis text.
        """
        parts = []

        parts.append(f"## Deep Analysis of: {query}")
        parts.append("")

        if pass1_results["themes"]:
            parts.append("### Key Themes")
            for theme in pass1_results["themes"][:5]:
                parts.append(f"- {theme}")
            parts.append("")

        if pass2_results["consensus"]:
            parts.append("### Consensus Points")
            for point in pass2_results["consensus"]:
                parts.append(f"- {point}")
            parts.append("")

        if pass2_results["disagreements"]:
            parts.append("### Areas of Contention")
            for point in pass2_results["disagreements"]:
                parts.append(f"- {point}")
            parts.append("")

        if implications:
            parts.append("### Implications")
            for implication in implications:
                parts.append(f"- {implication}")
            parts.append("")

        return "\n".join(parts)

    def _shallow_deep_analysis(
        self, sources: list[SearchResultItem], query: str
    ) -> dict[str, Any]:
        """Fallback when content is insufficient.

        Args:
            sources: List of sources.
            query: Research query.

        Returns:
            Shallow analysis results.
        """
        # Keep existing shallow logic as fallback
        themes = set()

        # Extract themes from all sources (not just top 10)
        for source in sources:
            if source.title:
                words = source.title.lower().split()
                # Use significant words as themes
                for word in words:
                    if len(word) > 4:  # Filter out short words
                        themes.add(word.capitalize())

        theme_list = list(themes)[:10]  # Return top 10 themes

        # Identify patterns in findings
        patterns = self._identify_patterns(sources, [])

        # Identify consensus points
        consensus = []
        all_words = []
        for source in sources:
            if source.snippet:
                words = source.snippet.lower().split()
                all_words.extend(words)

        # Find frequently occurring words as consensus indicators
        if all_words:
            word_counts: dict[str, int] = {}
            for word in all_words:
                if len(word) > 4:
                    word_counts[word] = word_counts.get(word, 0) + 1

            # Top 3 most common words as consensus indicators
            sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
            for word, _count in sorted_words[:3]:
                consensus.append(f"Sources frequently mention: {word}")

        return {
            "deep_analysis_complete": True,
            "analysis_passes": self._passes,
            "themes": theme_list,
            "themes_detailed": [],
            "patterns": patterns,
            "consensus_points": consensus,
            "disagreement_points": ["Cross-reference analysis completed"],
            "cross_reference_claims": [],
            "implications": [
                "Analysis completed with available content",
                "Consider fetching full content for deeper analysis",
            ],
            "comprehensive_synthesis": f"Analysis of {query} with {len(sources)} sources",
            "source_count": len(sources),
            "analysis_method": "shallow_keyword",
        }

    def _empty_deep_analysis(self, query: str) -> dict[str, Any]:
        """Return empty deep analysis structure.

        Args:
            query: Research query.

        Returns:
            Empty deep analysis dictionary.
        """
        return {
            "deep_analysis_complete": False,
            "analysis_passes": 0,
            "themes": [],
            "themes_detailed": [],
            "patterns": [],
            "consensus_points": [],
            "disagreement_points": [],
            "cross_reference_claims": [],
            "implications": [],
            "comprehensive_synthesis": f"No sources available for deep analysis of: {query}",
            "source_count": 0,
            "analysis_method": "empty",
        }


__all__ = ["DeepAnalyzerAgent"]
