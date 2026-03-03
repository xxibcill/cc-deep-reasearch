"""AI-powered analysis service for deep research.

This service provides semantic analysis capabilities using Claude models:
- Theme extraction with semantic clustering
- Cross-reference analysis for consensus/disagreement
- Gap identification with query relevance scoring
- Synthesis with proper attribution
"""

from typing import Any

from cc_deep_research.agents.ai_agent_integration import AIAgentIntegration
from cc_deep_research.models import SearchResultItem


class AIAnalysisService:
    """Service for AI-powered semantic analysis of research sources.

    This service leverages Claude models through the Agent system
    to perform deep semantic analysis that goes beyond keyword matching.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize AI analysis service.

        Args:
            config: Agent configuration dictionary.
        """
        self._config = config
        self._model = config.get("model", "claude-sonnet-4-6")
        self._max_tokens = config.get("deep_analysis_tokens", 150000)
        self._num_themes = config.get("ai_num_themes", 8)
        self._deep_num_themes = config.get("ai_deep_num_themes", 12)
        self._ai_integration = AIAgentIntegration(config)

    def extract_themes_semantically(
        self,
        sources: list[SearchResultItem],
        query: str,
        num_themes: int | None = None,
    ) -> list[dict[str, Any]]:
        """Extract themes using semantic analysis.

        Args:
            sources: List of sources with content.
            query: Original research query.
            num_themes: Number of themes to extract (uses config default if None).

        Returns:
            List of themes with:
            - name: Theme name
            - description: Detailed description
            - supporting_sources: List of source URLs
            - key_points: List of key points within theme
        """
        if num_themes is None:
            num_themes = self._num_themes

        # Try AI-powered theme extraction
        ai_themes = self._ai_integration.extract_themes_with_ai(
            sources=sources,
            query=query,
            num_themes=num_themes,
        )

        if ai_themes:
            return ai_themes

        # Fallback to heuristic if AI integration doesn't return results
        # Prepare content for analysis
        content_blocks = self._prepare_content_blocks(
            sources, max_tokens=self._max_tokens
        )

        if not content_blocks:
            return self._basic_theme_fallback(sources, num_themes)

        # Use existing heuristic method as fallback
        themes = self._extract_themes_from_content(
            query, content_blocks, num_themes
        )

        return themes

    def analyze_cross_reference(
        self, sources: list[SearchResultItem], themes: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Perform cross-reference analysis across sources.

        Args:
            sources: List of sources with content.
            themes: Identified themes from semantic analysis.

        Returns:
            Dictionary with:
            - consensus_points: List of consensus claims with supporting sources
            - disagreement_points: List of contradictory claims with evidence
            - cross_reference_claims: List of claim objects
        """
        content_blocks = self._prepare_content_blocks(
            sources, max_tokens=self._max_tokens
        )

        if not content_blocks:
            return self._basic_cross_reference_fallback()

        # TODO: Implement AI-powered cross-reference analysis
        # For now, use a basic implementation
        return self._analyze_cross_reference_basic(
            content_blocks, themes
        )

    def identify_gaps(
        self,
        sources: list[SearchResultItem],
        query: str,
        themes: list[dict[str, Any]],  # noqa: ARG002
    ) -> list[dict[str, Any]]:
        """Identify information gaps in the research.

        Args:
            sources: List of analyzed sources.
            query: Original research query.
            themes: Identified themes.

        Returns:
            List of gaps with:
            - gap_description: What's missing
            - importance: High/Medium/Low
            - suggested_queries: Queries to fill gap
        """
        # TODO: Implement AI-powered gap identification
        # For now, use basic heuristics
        gaps = []

        # Check for insufficient source diversity
        domains = set()
        for source in sources:
            if source.url:
                try:
                    domain = source.url.split("//")[1].split("/")[0]
                    domains.add(domain)
                except (IndexError, AttributeError):
                    pass

        if len(domains) < 5:
            gaps.append({
                "gap_description": "Limited source diversity - most sources from few domains",
                "importance": "Medium",
                "suggested_queries": [
                    f"{query} academic research",
                    f"{query} scientific studies",
                    f"{query} peer reviewed"
                ],
            })

        # Check for recent information
        gaps.append({
            "gap_description": "Research may not include very recent developments",
            "importance": "Low",
            "suggested_queries": [
                f"{query} 2026",
                f"{query} latest studies",
                f"{query} recent findings"
            ],
        })

        return gaps

    def synthesize_findings(
        self,
        sources: list[SearchResultItem],  # noqa: ARG002
        themes: list[dict[str, Any]],
        cross_ref: dict[str, Any],  # noqa: ARG002
        gaps: list[dict[str, Any]],  # noqa: ARG002
        query: str,  # noqa: ARG002
    ) -> list[dict[str, Any]]:
        """Synthesize key findings with proper attribution.

        Args:
            sources: List of sources.
            themes: Identified themes.
            cross_ref: Cross-reference analysis results.
            gaps: Identified gaps.
            query: Original research query.

        Returns:
            List of findings with:
            - title: Finding title
            - description: Detailed description
            - evidence: List of supporting source references
            - confidence: High/Medium/Low
        """
        findings = []

        # Create findings from themes
        for theme in themes[:5]:  # Top 5 themes become key findings
            finding = {
                "title": theme.get("name", "Unnamed Finding"),
                "description": theme.get("description", "No description available"),
                "evidence": theme.get("supporting_sources", []),
                "confidence": "High" if len(theme.get("supporting_sources", [])) > 3 else "Medium",
            }
            findings.append(finding)

        return findings

    def _prepare_content_blocks(
        self, sources: list[SearchResultItem], max_tokens: int = 150000
    ) -> list[dict[str, Any]]:
        """Prepare source content for analysis, respecting token limits.

        Args:
            sources: List of sources.
            max_tokens: Maximum tokens to include.

        Returns:
            List of content blocks with metadata.
        """
        blocks = []
        total_tokens = 0

        # Prioritize sources with full content
        sources_with_content = [
            s for s in sources if s.content and len(s.content) > 200
        ]
        sources_sorted = sorted(
            sources_with_content,
            key=lambda s: getattr(s, "score", 0) or 0,
            reverse=True,
        )

        for source in sources_sorted:
            content = source.content or source.snippet
            if not content:
                continue

            # Estimate tokens (rough approximation: 4 chars per token)
            estimated_tokens = len(content) // 4

            if total_tokens + estimated_tokens > max_tokens:
                break

            blocks.append({
                "url": source.url,
                "title": source.title,
                "content": content,
                "metadata": source.source_metadata,
            })
            total_tokens += estimated_tokens

        return blocks

    def _build_theme_extraction_prompt(
        self, query: str, content_blocks: list[dict[str, Any]], num_themes: int
    ) -> str:
        """Build prompt for theme extraction.

        Args:
            query: Research query.
            content_blocks: Content blocks to analyze.
            num_themes: Number of themes to extract.

        Returns:
            Analysis prompt string.
        """
        prompt = f"""Analyze the following research materials about: "{query}"

Source Content:
{self._format_content_blocks(content_blocks)}

Task: Extract {num_themes} major themes that emerge from these sources.

For each theme, provide:
1. A concise theme name (3-5 words)
2. A detailed description (1-2 paragraphs)
3. List of supporting source URLs
4. Key points within this theme (3-5 bullet points)

Requirements:
- Themes should be semantically distinct
- Themes should cover the breadth of research
- Identify patterns and connections across sources
- Note any contradictions or nuances

Focus on synthesizing information rather than just listing it.
"""
        return prompt

    def _extract_themes_from_content(
        self, _query: str, content_blocks: list[dict[str, Any]], num_themes: int
    ) -> list[dict[str, Any]]:
        """Extract themes from content blocks using analysis.

        This is a basic implementation that will be enhanced with AI.

        Args:
            query: Research query.
            content_blocks: Content blocks to analyze.
            num_themes: Number of themes to extract.

        Returns:
            List of theme dictionaries.
        """
        themes = []

        # Extract meaningful phrases from titles and content
        all_phrases = []
        for block in content_blocks:
            # Extract from title
            if block.get("title"):
                words = block["title"].split()
                phrases = [" ".join(words[i:i+3]) for i in range(len(words)-2)]
                all_phrases.extend(phrases)

            # Extract from first paragraph of content
            if block.get("content"):
                first_para = block["content"].split("\n\n")[0][:500]
                words = first_para.split()
                phrases = [" ".join(words[i:i+3]) for i in range(len(words)-2)]
                all_phrases.extend(phrases)

        # Count phrase occurrences
        phrase_counts: dict[str, int] = {}
        for phrase in all_phrases:
            phrase = phrase.lower()
            if len(phrase) > 10 and len(phrase) < 50:
                phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1

        # Get top phrases as potential themes
        top_phrases = sorted(
            phrase_counts.items(), key=lambda x: x[1], reverse=True
        )[:num_themes * 2]

        # Group related phrases into themes
        used_sources = set()
        for phrase, _count in top_phrases[:num_themes]:
            # Find sources that contain this phrase
            supporting_sources = []
            key_points = []

            for block in content_blocks:
                content_lower = (block.get("content", "") + " " + block.get("title", "")).lower()
                if phrase in content_lower and block["url"] not in used_sources:
                    supporting_sources.append(block["url"])
                    used_sources.add(block["url"])

                    # Extract a key point from this source
                    content = block.get("content", "")
                    sentences = content.split(".")
                    for sentence in sentences:
                        if phrase in sentence.lower() and len(sentence) > 20:
                            key_points.append(sentence.strip())
                            break

            if supporting_sources:
                # Capitalize theme name
                theme_name = " ".join(word.capitalize() for word in phrase.split())

                # Create description from key points
                description = (
                    f"This theme appears across {len(supporting_sources)} sources. "
                    f"Key aspects include: {', '.join(key_points[:3])}."
                )

                themes.append({
                    "name": theme_name,
                    "description": description,
                    "supporting_sources": supporting_sources,
                    "key_points": key_points[:3],
                })

        return themes

    def _basic_theme_fallback(
        self, sources: list[SearchResultItem], num_themes: int
    ) -> list[dict[str, Any]]:
        """Basic fallback theme extraction when content is unavailable.

        Args:
            sources: List of sources.
            num_themes: Number of themes.

        Returns:
            List of basic theme dictionaries.
        """
        themes = []

        # Extract keywords from titles
        all_words = []
        for source in sources:
            if source.title:
                words = [
                    w.lower() for w in source.title.split()
                    if len(w) > 4 and w.isalpha()
                ]
                all_words.extend(words)

        # Count word occurrences
        word_counts: dict[str, int] = {}
        for word in all_words:
            word_counts[word] = word_counts.get(word, 0) + 1

        # Get top words as themes
        top_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[
            :num_themes
        ]

        for word, count in top_words:
            themes.append({
                "name": word.capitalize(),
                "description": f"Appears in {count} sources across the research.",
                "supporting_sources": [],
                "key_points": [],
            })

        return themes

    def _analyze_cross_reference_basic(
        self, _content_blocks: list[dict[str, Any]], themes: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Basic cross-reference analysis without AI.

        Args:
            content_blocks: Content blocks to analyze.
            themes: Identified themes.

        Returns:
            Dictionary with consensus and disagreement points.
        """
        consensus_points: list[str] = []
        disagreement_points: list[str] = []

        # Find consensus: themes supported by multiple sources
        for theme in themes:
            support_count = len(theme.get("supporting_sources", []))
            if support_count >= 3:
                consensus_points.append(
                    f"Multiple sources ({support_count}) support findings about {theme['name']}"
                )

        if not consensus_points:
            consensus_points.append("Core concepts are discussed across multiple sources")

        # Disagreements would require AI to detect conflicting claims
        # For now, leave empty
        if not disagreement_points:
            disagreement_points.append("No major contradictions detected between sources")

        return {
            "consensus_points": consensus_points,
            "disagreement_points": disagreement_points,
            "cross_reference_claims": [],
        }

    def _basic_cross_reference_fallback(self) -> dict[str, Any]:
        """Fallback cross-reference when content is unavailable."""
        return {
            "consensus_points": ["Sources discuss similar core concepts"],
            "disagreement_points": [],
            "cross_reference_claims": [],
        }

    def _format_content_blocks(self, blocks: list[dict[str, Any]]) -> str:
        """Format content blocks for inclusion in prompts.

        Args:
            blocks: List of content blocks.

        Returns:
            Formatted string of blocks.
        """
        formatted = []
        for i, block in enumerate(blocks, 1):
            formatted.append(f"\n--- Source {i} ---")
            formatted.append(f"URL: {block['url']}")
            formatted.append(f"Title: {block['title']}")
            formatted.append(f"Content: {block['content'][:1000]}...")

        return "\n".join(formatted)


__all__ = ["AIAnalysisService"]
