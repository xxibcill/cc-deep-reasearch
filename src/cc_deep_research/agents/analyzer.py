"""Analyzer agent implementation.

The analyzer agent is responsible for:
- Analyzing collected sources and information
- Synthesizing findings from multiple sources
- Identifying key themes and patterns
- Detecting consensus and disagreement across sources
"""

import re
from typing import Any

from cc_deep_research.agents.ai_analysis_service import AIAnalysisService
from cc_deep_research.models import (
    SearchResultItem,
)


class AnalyzerAgent:
    """Agent that analyzes and synthesizes collected information.

    This agent:
    - Analyzes content from collected sources
    - Identifies key themes and findings
    - Detects consensus and disagreement across sources
    - Synthesizes coherent analysis
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the analyzer agent.

        Args:
            config: Agent configuration dictionary.
        """
        self._config = config
        self._ai_service = AIAnalysisService(config)

    def analyze_sources(
        self,
        sources: list[SearchResultItem],
        query: str,
    ) -> dict[str, Any]:
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

        # Use AI-powered analysis
        themes = self._ai_service.extract_themes_semantically(
            sources=cleaned_sources,
            query=query,
            num_themes=self._config.get("ai_num_themes", 8),
        )

        # Perform cross-reference analysis
        cross_ref = self._ai_service.analyze_cross_reference(
            _sources=cleaned_sources, themes=themes
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

        return {
            "key_findings": key_findings,
            "themes": [t["name"] for t in themes],
            "themes_detailed": themes,
            "consensus_points": cross_ref["consensus_points"],
            "contention_points": cross_ref["disagreement_points"],
            "cross_reference_claims": cross_ref.get("cross_reference_claims", []),
            "gaps": gaps,
            "source_count": len(cleaned_sources),
            "analysis_method": "ai_semantic",
        }

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
                cleaned_source.content = self._clean_source_content(
                    cleaned_source.content, is_title=False
                )

            cleaned.append(cleaned_source)

        return cleaned

    def _clean_source_content(self, content: str, is_title: bool = False) -> str:
        """Clean content by removing HTML fragments, navigation text, and artifacts.

        Args:
            content: Content to clean.
            is_title: Whether this is a title (shorter cleaning).

        Returns:
            Cleaned content.
        """
        if not content:
            return ""

        # Remove blob URLs and internal references
        content = re.sub(r'blob:http://[^\s]+', '', content)
        content = re.sub(r'\[Image\s*\d+\]', '', content)
        content = re.sub(r'!\[.*?\]\(.*?\)', '', content)

        # Remove markdown links and their text
        content = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', content)

        # Remove all markdown links completely (they're often navigation)
        content = re.sub(r'\[[^\]]+\]\([^\)]+\)', '', content)

        # Remove social media and navigation patterns
        navigation_patterns = [
            r'\[Log in\]',
            r'\[Cart\]',
            r'\[Sign up\]',
            r'\[Menu\]',
            r'\[Close\]',
            r'\[Share\]',
            r'\(Log in\)',
            r'\(Cart\)',
            r'\(Sign up\)',
            r'\[Skip to content\]',
            r'\[Continue shopping\]',
            r'\[Have an account',
            r'\[Login\]',
            r'\[Sign Up\]',
            r'\*?\s*Twitter',
            r'\*?\s*Facebook',
            r'\*?\s*Instagram',
            r'\*?\s*YouTube',
            r'SHOP\s*\+\s*',
            r'BLOG\s*\+\s*',
            r'ABOUT\s*\+\s*',
            r'REWARDS\s*\+\s*',
            r'CONTACT\s*\+\s*',
            r'REGISTER\s*\+\s*',
        ]

        for pattern in navigation_patterns:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE)

        # Remove common website artifacts
        artifacts = [
            r'Share\s*$',
            r'^\s*Share\n',
            r'Log in\s*Cart',
            r'Cart\s*$',
            r'^\s*Cart\n',
            r'com/@\w+',
            r'Skip to content',
            r'Continue shopping',
            r'Have an account',
            r'Check out faster',
            r'Estimated total',
            r'Your cart is empty',
            r'Best Sellers',
            r'Shop our best selling',
            r'Find Relief Now',
            r'Steeping Accessories',
            r'Who We Are',
            r'What is Matcha',
            r'What is White Tea',
            r'What are the origins',
            r'## Best Sellers',
            r'## Find Relief',
            r'## Steeping',
            r'## Who We Are',
            r'## What is',
            r'## Origins of',
        ]

        for pattern in artifacts:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE | re.MULTILINE)

        # Remove section headers with limited text (they're usually navigation)
        content = re.sub(r'^#{1,3}\s+(Your\s+cart|Estimated\s+total|Continue\s+shopping|Best\s+Sellers|Find\s+Relief|Steeping\s+Accessories|Who\s+We\s+Are|What\s+is\s+Matcha?|Origins\s+of).*$', '', content, flags=re.IGNORECASE | re.MULTILINE)

        # Remove email addresses and URLs from content
        content = re.sub(r'\S+@\S+\.\S+', '', content)
        content = re.sub(r'https?://\S+', '', content)

        # Clean up extra whitespace
        content = re.sub(r'\s+', ' ', content)
        content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)

        # For titles, just trim
        if is_title:
            return content.strip()[:200]

        # For full content, also remove very short/incomplete sentences at start
        lines = content.split('\n')
        cleaned_lines = []

        for line in lines:
            line = line.strip()

            # Skip empty lines or very short lines
            if len(line) < 10:
                continue

            # Skip lines that look like navigation
            if line.lower() in ['log in', 'cart', 'menu', 'search']:
                continue

            # Skip lines that start with ## (markdown headers) unless they're meaningful
            if line.startswith('##') and len(line) < 30:
                continue

            # Skip lines that are just URLs
            if re.match(r'^https?://', line):
                continue

            cleaned_lines.append(line)

        content = ' '.join(cleaned_lines)

        return content.strip()

    def _basic_analysis(
        self, sources: list[SearchResultItem], query: str
    ) -> dict[str, Any]:
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

        return {
            "key_findings": findings,
            "themes": themes,
            "consensus_points": cross_ref["consensus"],
            "contention_points": cross_ref["contention"],
            "gaps": gaps,
            "source_count": len(sources),
            "analysis_method": "basic_keyword",
        }

    def _extract_findings(
        self, sources: list[SearchResultItem], query: str  # noqa: ARG002
    ) -> list[dict[str, str]]:
        """Extract key findings from sources.

        Args:
            sources: List of sources to analyze.
            query: Research query.

        Returns:
            List of findings with titles and descriptions.

        Note: This is a fallback implementation used when content is insufficient.
        """
        findings = []

        # Placeholder: create findings from source titles/snippets
        for _i, source in enumerate(sources[:5]):  # Top 5 sources
            if source.title:
                findings.append(
                    {
                        "title": source.title,
                        "description": source.snippet or "No description available",
                        "source": source.url,
                    }
                )

        return findings

    def _identify_themes(
        self, sources: list[SearchResultItem]
    ) -> list[str]:
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
    ) -> dict[str, list[str]]:
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
        gaps = []

        if len(sources) < 5:
            gaps.append("Limited number of sources collected")

        # Check for content depth
        has_long_content = any(len(s.content or "") > 500 for s in sources)
        if not has_long_content:
            gaps.append("Sources lack detailed content for deep analysis")

        return gaps

    def _empty_analysis(self, _query: str) -> dict[str, Any]:
        """Return empty analysis structure.

        Args:
            query: Research query.

        Returns:
            Empty analysis dictionary.
        """
        return {
            "key_findings": [],
            "themes": [],
            "consensus_points": [],
            "contention_points": [],
            "gaps": ["No sources to analyze"],
            "source_count": 0,
            "analysis_method": "empty",
        }

    def synthesize_report(
        self, analysis: dict[str, Any], query: str  # noqa: ARG002
    ) -> str:
        """Synthesize analysis into a coherent report section.

        Args:
            analysis: Analysis results from analyze_sources.
            query: Research query.

        Returns:
            Synthesized text report.

        Note: This is a placeholder implementation.
        """
        sections = []

        if analysis["key_findings"]:
            sections.append("## Key Findings\n")
            for finding in analysis["key_findings"]:
                sections.append(f"- {finding['title']}")
                sections.append(f"  {finding['description']}\n")

        if analysis["gaps"]:
            sections.append("\n## Gaps\n")
            for gap in analysis["gaps"]:
                sections.append(f"- {gap}\n")

        return "\n".join(sections)


__all__ = ["AnalyzerAgent"]
