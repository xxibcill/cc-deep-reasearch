"""AI-powered analysis service for deep research.

This service provides semantic analysis capabilities using Claude models:
- Theme extraction with semantic clustering
- Cross-reference analysis for consensus/disagreement
- Gap identification with query relevance scoring
- Synthesis with proper attribution

Supports multiple integration methods:
- 'api': Uses the Claude Code CLI for deep semantic analysis
- 'heuristic': Uses pattern matching and heuristics (fast, no API cost)
- 'hybrid': Tries the Claude Code CLI first, falls back to heuristic

Note: When running inside a Claude Code session (CLAUDECODE env var is set),
the CLI-based analysis is automatically disabled to avoid nested session errors.
"""

import logging
import os
from typing import TYPE_CHECKING, Any

from cc_deep_research.agents.ai_agent_integration import AIAgentIntegration
from cc_deep_research.agents.ai_executor import AIExecutor
from cc_deep_research.models import SearchResultItem

if TYPE_CHECKING:
    from cc_deep_research.agents.llm_analysis_client import LLMAnalysisClient

logger = logging.getLogger(__name__)


class AIAnalysisService:
    """Service for AI-powered semantic analysis of research sources.

    This service leverages Claude models through multiple integration methods:
    - API: Claude Code CLI calls for deep semantic understanding
    - Heuristic: Pattern matching and heuristics for fast analysis
    - Hybrid: Claude Code CLI with heuristic fallback
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize AI analysis service.

        Args:
            config: Agent configuration dictionary with:
                - ai_integration_method: 'api', 'heuristic', or 'hybrid'
                - claude_cli_path: Optional Claude CLI path override
                - model: Model to use
                - deep_analysis_tokens: Token limit
        """
        self._config = config
        self._model = config.get("model", "claude-sonnet-4-6")
        self._max_tokens = config.get("deep_analysis_tokens", 150000)
        self._num_themes = config.get("ai_num_themes", 8)
        self._deep_num_themes = config.get("ai_deep_num_themes", 12)
        self._integration_method = config.get("ai_integration_method", "heuristic")

        # Initialize heuristic-based components
        self._ai_integration = AIAgentIntegration(config)
        self._ai_executor = AIExecutor(config)

        # Initialize LLM client if using CLI-backed API or hybrid mode
        self._llm_client: LLMAnalysisClient | None = None
        if self._integration_method in ("api", "hybrid"):
            self._initialize_llm_client()

    def _initialize_llm_client(self) -> None:
        """Initialize the LLM client for Claude CLI-based analysis.

        Skips initialization if running inside another Claude Code session
        (detected via CLAUDECODE environment variable) to avoid nested session errors.
        """
        # Check if running inside another Claude Code session
        if os.environ.get("CLAUDECODE"):
            logger.info(
                "Running inside Claude Code session (CLAUDECODE=1). "
                "Skipping CLI-based analysis to avoid nested session errors. "
                "Using heuristic-based analysis instead."
            )
            return

        try:
            from cc_deep_research.agents.llm_analysis_client import LLMAnalysisClient

            llm_config = {
                **self._config,
                "timeout_seconds": self._config.get("claude_cli_timeout_seconds", 180),
            }
            self._llm_client = LLMAnalysisClient(llm_config)
            logger.info("Claude CLI client initialized for deep semantic analysis")
        except ImportError as e:
            logger.warning(f"Failed to import LLMAnalysisClient: {e}")
            if self._integration_method == "api":
                raise
        except ValueError as e:
            logger.warning(f"Claude CLI unavailable. Falling back to heuristic analysis: {e}")
            if self._integration_method == "api":
                raise

    def extract_themes_semantically(
        self,
        sources: list[SearchResultItem],
        query: str,
        num_themes: int | None = None,
    ) -> list[dict[str, Any]]:
        """Extract themes using semantic analysis.

        Uses the Claude CLI when available for deep semantic understanding,
        falls back to heuristic-based extraction.

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

        # Convert SearchResultItem to dict
        sources_dict = [
            {
                "url": s.url,
                "title": s.title or "",
                "content": s.content or s.snippet or "",
                "snippet": s.snippet or "",
            }
            for s in sources
            if s.content or s.snippet
        ]

        # Try LLM client first if available (CLI or hybrid mode)
        if self._llm_client and sources_dict:
            try:
                logger.info("Using Claude CLI for deep semantic theme extraction")
                themes = self._llm_client.extract_themes(
                    sources=sources_dict,
                    query=query,
                    num_themes=num_themes,
                )
                if themes:
                    logger.info(f"Claude CLI extracted {len(themes)} themes")
                    return themes
            except Exception as e:
                logger.warning(f"Claude CLI theme extraction failed: {e}")
                if self._integration_method == "api":
                    raise
                # Fall through to heuristic for hybrid mode

        # Fallback to heuristic-based AI executor
        if sources_dict:
            ai_themes = self._ai_executor.extract_themes(
                sources=sources_dict,
                query=query,
                num_themes=num_themes,
            )

            if ai_themes:
                return ai_themes

        # Fallback to AI integration heuristics
        ai_themes = self._ai_integration.extract_themes_with_ai(
            sources=sources,
            query=query,
            num_themes=num_themes,
        )

        if ai_themes:
            return ai_themes

        # Final fallback to basic theme extraction
        content_blocks = self._prepare_content_blocks(
            sources, max_tokens=self._max_tokens
        )

        if not content_blocks:
            return self._basic_theme_fallback(sources, num_themes)

        # Use existing heuristic method as final fallback
        themes = self._extract_themes_from_content(
            query, content_blocks, num_themes
        )

        return themes

    def analyze_cross_reference(
        self, sources: list[SearchResultItem], themes: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Perform cross-reference analysis across sources.

        Uses the Claude CLI when available for deep cross-reference analysis,
        falls back to heuristic-based analysis.

        Args:
            sources: List of sources with content.
            themes: Identified themes from semantic analysis.

        Returns:
            Dictionary with:
            - consensus_points: List of consensus claims with supporting sources
            - disagreement_points: List of contradictory claims with evidence
            - cross_reference_claims: List of claim objects
        """
        # Convert SearchResultItem to dict
        sources_dict = [
            {
                "url": s.url,
                "title": s.title or "",
                "content": s.content or s.snippet or "",
                "snippet": s.snippet or "",
            }
            for s in sources
            if s.content or s.snippet
        ]

        # Try LLM client first if available
        if self._llm_client and sources_dict and themes:
            try:
                logger.info("Using Claude CLI for cross-reference analysis")
                result = self._llm_client.analyze_cross_reference(
                    sources=sources_dict,
                    themes=themes,
                )
                logger.info(
                    f"Claude CLI found {len(result.get('consensus_points', []))} consensus points, "
                    f"{len(result.get('disagreement_points', []))} disagreement points"
                )
                return result
            except Exception as e:
                logger.warning(f"Claude CLI cross-reference analysis failed: {e}")
                if self._integration_method == "api":
                    raise

        # Fallback to AI integration heuristics
        return self._ai_integration.analyze_cross_reference_with_ai(
            _sources=sources,
            themes=themes,
        )

    def analyze_evidence_quality(
        self,
        sources: list[SearchResultItem],
        themes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Analyze evidence quality across sources.

        Distinguishes between human studies, animal studies, and in vitro studies.
        Identifies conflicting evidence and assigns confidence levels.

        Args:
            sources: List of sources with content.
            themes: Identified themes from semantic analysis.

        Returns:
            Dictionary with:
            - study_types: Breakdown of human/animal/in vitro/other studies
            - evidence_conflicts: List of identified conflicts with explanations
            - confidence_levels: Confidence assessment for each theme
            - evidence_summary: Overall evidence quality summary
        """
        return self._ai_integration.analyze_evidence_quality(
            sources=sources,
            themes=themes,
        )

    def identify_gaps(
        self,
        sources: list[SearchResultItem],
        query: str,
        themes: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Identify information gaps in the research.

        Uses the Claude CLI when available for deep gap identification,
        falls back to heuristic-based analysis.

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
        # Convert SearchResultItem to dict
        sources_dict = [
            {
                "url": s.url,
                "title": s.title or "",
                "content": s.content or s.snippet or "",
                "snippet": s.snippet or "",
            }
            for s in sources
            if s.content or s.snippet
        ]

        # Try LLM client first if available
        if self._llm_client and sources_dict and themes:
            try:
                logger.info("Using Claude CLI for gap identification")
                gaps = self._llm_client.identify_gaps(
                    sources=sources_dict,
                    query=query,
                    themes=themes,
                )
                logger.info(f"Claude CLI identified {len(gaps)} gaps")
                return gaps
            except Exception as e:
                logger.warning(f"Claude CLI gap identification failed: {e}")
                if self._integration_method == "api":
                    raise

        # Fallback to AI integration for gap identification
        return self._ai_integration.identify_gaps_with_ai(
            sources=sources,
            query=query,
            themes=themes,
        )

    def synthesize_findings(
        self,
        sources: list[SearchResultItem],
        themes: list[dict[str, Any]],
        cross_ref: dict[str, Any],
        gaps: list[dict[str, Any]],
        query: str,
    ) -> list[dict[str, Any]]:
        """Synthesize key findings with proper attribution.

        Uses the Claude CLI when available for deep synthesis,
        falls back to heuristic-based synthesis.

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
        # Convert sources to dict format
        sources_dict = [
            {
                "url": s.url,
                "title": s.title or "",
                "content": s.content or s.snippet or "",
            }
            for s in sources
        ]

        # Try LLM client first if available
        if self._llm_client and sources_dict and themes:
            try:
                logger.info("Using Claude CLI for findings synthesis")
                findings = self._llm_client.synthesize_findings(
                    sources=sources_dict,
                    themes=themes,
                    cross_ref=cross_ref,
                    gaps=gaps,
                    query=query,
                )
                logger.info(f"Claude CLI synthesized {len(findings)} findings")
                return findings
            except Exception as e:
                logger.warning(f"Claude CLI synthesis failed: {e}")
                if self._integration_method == "api":
                    raise

        # Fallback to AI executor for synthesis
        findings = self._ai_executor.synthesize_findings(themes, sources_dict)

        if findings:
            return findings

        # Final fallback to basic synthesis
        findings = []
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
        """Basic cross-reference analysis without AI (deprecated, now uses AI integration).

        Args:
            content_blocks: Content blocks to analyze.
            themes: Identified themes.

        Returns:
            Dictionary with consensus and disagreement points.
        """
        # This method is now a fallback for the AI integration
        return self._ai_integration.analyze_cross_reference_with_ai(
            _sources=[],
            themes=themes,
        )

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
