"""AI-powered analysis service for deep research.

This service provides semantic analysis capabilities using routed LLM models:
- Theme extraction with semantic clustering
- Cross-reference analysis for consensus/disagreement
- Gap identification with query relevance scoring
- Synthesis with proper attribution

Supports multiple integration methods:
- 'api': Requires the shared routed LLM layer for semantic analysis
- 'heuristic': Uses pattern matching and heuristics (fast, no API cost)
- 'hybrid': Tries the shared routed LLM layer first, falls back to heuristic
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import TYPE_CHECKING, Any, TypeVar, cast

from cc_deep_research.agents.ai_agent_integration import AIAgentIntegration
from cc_deep_research.agents.ai_executor import AIExecutor
from cc_deep_research.models import SearchResultItem

if TYPE_CHECKING:
    from cc_deep_research.agents.llm_analysis_client import LLMAnalysisClient
    from cc_deep_research.llm.router import LLMRouter
    from cc_deep_research.monitoring import ResearchMonitor
    from cc_deep_research.prompts import PromptRegistry

T = TypeVar("T")

logger = logging.getLogger(__name__)


class AIAnalysisService:
    """Service for AI-powered semantic analysis of research sources.

    This service leverages routed LLM models through multiple integration methods:
    - API: Shared routed LLM calls for deep semantic understanding
    - Heuristic: Pattern matching and heuristics for fast analysis
    - Hybrid: Routed LLM with heuristic fallback
    """

    def __init__(
        self,
        config: dict[str, Any],
        monitor: ResearchMonitor | None = None,
        llm_router: "LLMRouter | None" = None,
        agent_id: str = "analyzer",
        prompt_registry: "PromptRegistry | None" = None,
    ) -> None:
        """Initialize AI analysis service.

        Args:
            config: Agent configuration dictionary with:
                - ai_integration_method: 'api', 'heuristic', or 'hybrid'
                - model: Model to use
                - deep_analysis_tokens: Token limit
            monitor: Optional research monitor for telemetry.
            llm_router: Optional LLM router for shared routing layer.
            agent_id: Agent identifier for LLM routing.
            prompt_registry: Optional prompt registry with overrides.
        """
        self._config = config
        self._model = config.get("model", "claude-sonnet-4-6")
        self._max_tokens = config.get("deep_analysis_tokens", 150000)
        self._num_themes = config.get("ai_num_themes", 8)
        self._deep_num_themes = config.get("ai_deep_num_themes", 12)
        self._integration_method = config.get("ai_integration_method", "heuristic")
        self._monitor = monitor
        self._llm_router = llm_router
        self._agent_id = agent_id
        self._prompt_registry = prompt_registry
        self._routed_llm_used = False

        # Initialize heuristic-based components
        self._ai_integration = AIAgentIntegration(config)
        self._ai_executor = AIExecutor(config)

        # Initialize routed LLM client when semantic analysis is enabled.
        self._llm_client: LLMAnalysisClient | None = None
        if self._integration_method in ("api", "hybrid"):
            self._initialize_llm_client()

    @property
    def routed_llm_used(self) -> bool:
        """Return whether the current analysis run used the routed LLM path."""
        return self._routed_llm_used

    def reset_run_tracking(self) -> None:
        """Reset per-run routed LLM usage tracking."""
        self._routed_llm_used = False

    def _mark_routed_llm_used(self) -> None:
        """Record that the routed LLM path executed successfully."""
        self._routed_llm_used = True

    def _record_routed_llm_fallback(self, *, operation: str, error: Exception) -> None:
        """Emit a degradation event when routed LLM analysis falls back."""
        if self._monitor is None:
            return

        self._monitor.emit_decision_made(
            decision_type="mitigation",
            reason_code="llm_analysis_fallback",
            chosen_option="heuristic_analysis",
            rejected_options=["routed_llm"],
            inputs={
                "operation": operation,
                "error": f"{type(error).__name__}: {error}",
            },
            actor_id=self._agent_id,
            phase="analysis",
            operation=f"analysis.fallback.{operation}",
        )
        self._monitor.emit_degradation_detected(
            reason_code="llm_analysis_fallback",
            scope="analysis",
            recoverable=True,
            mitigation="Falling back to heuristic analysis",
            impact=f"Routed LLM operation '{operation}' failed and heuristic analysis was used instead",
            phase="analysis",
            actor_id=self._agent_id,
        )

    def _initialize_llm_client(self) -> None:
        """Initialize the routed LLM client when a shared router is available."""
        if self._llm_router is None:
            if self._integration_method == "api":
                raise ValueError("ai_integration_method='api' requires an LLM router.")
            return

        if not self._llm_router.is_available(self._agent_id):
            if self._integration_method == "api":
                raise ValueError(f"No LLM route is available for agent '{self._agent_id}'.")
            return

        try:
            from cc_deep_research.agents.llm_analysis_client import LLMAnalysisClient

            llm_config = {
                **self._config,
                "timeout_seconds": self._config.get("llm_timeout_seconds", 180),
                "request_executor": self._execute_via_router,
                "prompt_registry": self._prompt_registry,
                "agent_id": self._agent_id,
            }
            self._llm_client = LLMAnalysisClient(llm_config, monitor=self._monitor)
            logger.info("Shared LLM router initialized for semantic analysis")
        except Exception as e:  # pragma: no cover - defensive fallback
            logger.warning(f"Routed LLM unavailable. Falling back to heuristic analysis: {e}")
            if self._integration_method == "api":
                raise

    def _execute_via_router(self, operation: str, prompt: str) -> str:
        """Execute one analysis prompt through the shared LLM router."""
        if self._llm_router is None:
            raise RuntimeError("LLM router is not configured")

        async def _run() -> str:
            assert self._llm_router is not None
            response = await self._llm_router.execute(
                agent_id=self._agent_id,
                prompt=prompt,
                metadata={"operation": operation, "agent_id": self._agent_id},
            )
            return response.content

        return cast(str, self._run_coroutine(_run()))

    @staticmethod
    def _run_coroutine(coroutine: Any) -> Any:
        """Run a coroutine from synchronous code."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is None:
            return asyncio.run(coroutine)

        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, coroutine)
            return future.result()

    def extract_themes_semantically(
        self,
        sources: list[SearchResultItem],
        query: str,
        num_themes: int | None = None,
    ) -> list[dict[str, Any]]:
        """Extract themes using semantic analysis.

        Uses the routed LLM when available for deep semantic understanding,
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

        # Try routed LLM first if available.
        if self._llm_client and sources_dict:
            try:
                logger.info("Using routed LLM for deep semantic theme extraction")
                themes = self._llm_client.extract_themes(
                    sources=sources_dict,
                    query=query,
                    num_themes=num_themes,
                )
                if themes:
                    logger.info(f"Routed LLM extracted {len(themes)} themes")
                    self._mark_routed_llm_used()
                    return themes
            except Exception as e:
                logger.warning(f"Routed LLM theme extraction failed: {e}")
                self._record_routed_llm_fallback(operation="extract_themes", error=e)
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

        Uses the routed LLM when available for deep cross-reference analysis,
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
                logger.info("Using routed LLM for cross-reference analysis")
                print(
                    f"[DEBUG] Using routed LLM for cross-reference analysis "
                    f"({len(sources_dict)} sources, {len(themes)} themes)"
                )
                result = self._llm_client.analyze_cross_reference(
                    sources=sources_dict,
                    themes=themes,
                )
                logger.info(
                    f"Routed LLM found {len(result.get('consensus_points', []))} consensus points, "
                    f"{len(result.get('disagreement_points', []))} disagreement points"
                )
                self._mark_routed_llm_used()
                return result
            except Exception as e:
                logger.warning(f"Routed LLM cross-reference analysis failed: {e}")
                print(f"[DEBUG] Routed LLM failed, falling back to heuristic analysis: {e}")
                self._record_routed_llm_fallback(operation="analyze_cross_reference", error=e)
                if self._integration_method == "api":
                    raise

        # Fallback to AI integration heuristics
        logger.info("Using heuristic-based cross-reference analysis")
        print("[DEBUG] Using heuristic-based cross-reference analysis")
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

        Uses the routed LLM when available for deep gap identification,
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
                logger.info("Using routed LLM for gap identification")
                gaps = self._llm_client.identify_gaps(
                    sources=sources_dict,
                    query=query,
                    themes=themes,
                )
                logger.info(f"Routed LLM identified {len(gaps)} gaps")
                self._mark_routed_llm_used()
                return gaps
            except Exception as e:
                logger.warning(f"Routed LLM gap identification failed: {e}")
                self._record_routed_llm_fallback(operation="identify_gaps", error=e)
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

        Uses the routed LLM when available for deep synthesis,
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
                logger.info("Using routed LLM for findings synthesis")
                findings = self._llm_client.synthesize_findings(
                    sources=sources_dict,
                    themes=themes,
                    cross_ref=cross_ref,
                    gaps=gaps,
                    query=query,
                )
                logger.info(f"Routed LLM synthesized {len(findings)} findings")
                self._mark_routed_llm_used()
                return findings
            except Exception as e:
                logger.warning(f"Routed LLM synthesis failed: {e}")
                self._record_routed_llm_fallback(operation="synthesize_findings", error=e)
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

    def detect_research_gaps(
        self,
        *,
        themes: list[dict[str, Any]],
        sources: list[SearchResultItem],
        query: str,
    ) -> list[dict[str, Any]]:
        """Automatically detect research gaps from analysis.

        Args:
            themes: List of identified themes.
            sources: List of collected sources.
            query: Original research query.

        Returns:
            List of detected gaps with metadata.
        """
        gaps = []

        # Combine all content for pattern matching
        all_content = " ".join([s.content or "" for s in sources])
        all_content_lower = all_content.lower()

        # Gap 1: Missing quantitative data
        if not re.search(r'\d+\s*(mg|g|µg|mg\/g|percent|%)\s*(per|\/|of|dose)', all_content):
            gaps.append({
                "type": "missing_quantitative_data",
                "importance": "medium",
                "description": "Quantitative measurements (mg/g, percentages, dosages) not found in sources",
                "suggested_queries": [
                    f"{query} quantitative analysis",
                    f"{query} concentration mg g",
                    f"{query} dosage recommendations",
                ],
            })

        # Gap 2: Missing comparative studies
        for theme in themes:
            theme_name = theme["name"].lower()
            if not re.search(
                rf'{theme_name}.*(vs|compared|versus|relative to|difference between)',
                all_content,
                re.IGNORECASE,
            ):
                gaps.append({
                    "type": "missing_comparative_studies",
                    "importance": "high",
                    "theme": theme_name,
                    "description": f"Comparative studies for {theme_name} not found (e.g., vs green tea, vs black tea)",
                    "suggested_queries": [
                        f"{theme_name} vs green tea study",
                        f"{theme_name} vs black tea study",
                        f"{theme_name} comparative effectiveness",
                    ],
                })

        # Gap 3: Missing mechanism details
        mechanism_keywords = ["mechanism", "pathway", "biochemical", "molecular", "how", "why"]
        has_mechanism = any(keyword in all_content_lower for keyword in mechanism_keywords)

        if not has_mechanism:
            gaps.append({
                "type": "missing_mechanism_details",
                "importance": "medium",
                "description": "Mechanism of action not explained (biochemical pathways, molecular mechanisms)",
                "suggested_queries": [
                    f"{query} mechanism of action",
                    f"{query} biochemical pathways",
                    f"{query} how it works",
                ],
            })

        # Gap 4: Missing safety data
        safety_keywords = ["contraindication", "interaction", "adverse", "side effect", "pregnant", "children", "elderly"]
        has_safety = any(keyword in all_content_lower for keyword in safety_keywords)

        if not has_safety:
            gaps.append({
                "type": "missing_safety_data",
                "importance": "medium",
                "description": "Safety information not found (contraindications, drug interactions, side effects)",
                "suggested_queries": [
                    f"{query} safety contraindications",
                    f"{query} drug interactions",
                    f"{query} side effects clinical",
                ],
            })

        # Gap 5: Missing clinical trials
        clinical_keywords = ["randomized", "controlled trial", "clinical trial", "human study", "participants"]
        has_clinical = any(keyword in all_content_lower for keyword in clinical_keywords)

        if not has_clinical:
            gaps.append({
                "type": "missing_clinical_trials",
                "importance": "high",
                "description": "Human clinical trial data not found (randomized controlled trials, human studies)",
                "suggested_queries": [
                    f"{query} randomized controlled trial",
                    f"{query} clinical study results",
                    f"{query} human intervention study",
                ],
            })

        return gaps

__all__ = ["AIAnalysisService"]
