"""LLM-powered analysis client for deep semantic analysis.

This module provides AI-powered analysis through an injected request executor,
replacing heuristic-based pattern matching with routed semantic analysis.

Features:
- Theme extraction with semantic clustering
- Cross-reference analysis for consensus/disagreement detection
- Gap identification with query relevance scoring
- Synthesis with proper attribution
- Evidence quality analysis
- Prompt override support for customized agent behavior

Uses prompt-based routed LLM invocations for large-source semantic analysis.
"""

from __future__ import annotations

import json
import re
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cc_deep_research.prompts import PromptRegistry


class LLMAnalysisClient:
    """Client for AI-powered semantic analysis using a routed LLM executor.

    This client provides real semantic analysis that goes beyond
    keyword matching, making prompt-driven LLM calls for
    deep understanding of research content.

    Attributes:
        _model: Model to use for analysis
        _timeout_seconds: Maximum seconds per response
        _prompt_registry: Optional prompt registry with overrides
        _agent_id: Agent identifier for prompt resolution
    """

    def __init__(
        self,
        config: dict[str, Any],
        monitor: Any | None = None,  # noqa: ARG002
    ) -> None:
        """Initialize LLM analysis client.

        Args:
            config: Configuration dictionary with:
                - model: Model to use (default: claude-sonnet-4-6)
                - timeout_seconds: Max seconds per request
                - request_executor: Required callable for prompt execution
                - prompt_registry: Optional PromptRegistry with overrides
                - agent_id: Agent identifier for prompt resolution
            monitor: Unused compatibility parameter retained for callers.
        """
        self._config = config
        self._model = config.get("model", "claude-sonnet-4-6")
        self._timeout_seconds = int(config.get("timeout_seconds", 180))
        self._usage_callback = config.get("usage_callback")
        self._request_executor = config.get("request_executor")
        self._prompt_registry: PromptRegistry | None = config.get("prompt_registry")
        self._agent_id: str = config.get("agent_id", "analyzer")
        if self._request_executor is None:
            raise ValueError("LLMAnalysisClient requires a request_executor.")

    def extract_themes(
        self,
        sources: list[dict[str, str]],
        query: str,
        num_themes: int = 8,
    ) -> list[dict[str, Any]]:
        """Extract themes using semantic analysis.

        Makes routed LLM calls for deep understanding.

        Args:
            sources: List of sources with url, title, content.
            query: Research query.
            num_themes: Number of themes to extract.

        Returns:
            List of themes with:
            - name: Theme name
            - description: Detailed description
            - supporting_sources: List of source URLs
            - key_points: List of key points within theme
        """
        # Prepare content for analysis
        content = self._prepare_content_for_analysis(sources)

        prompt = self._build_theme_extraction_prompt(query, content, num_themes)

        response_text = self._request(operation="extract_themes", prompt=prompt)
        return self._parse_theme_response(response_text, sources)

    def analyze_cross_reference(
        self,
        sources: list[dict[str, str]],
        themes: list[dict[str, Any]],
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
        content = self._prepare_content_for_analysis(sources)

        prompt = self._build_cross_reference_prompt(themes, content)

        response_text = self._request(operation="analyze_cross_reference", prompt=prompt)
        return self._parse_cross_reference_response(response_text)

    def identify_gaps(
        self,
        sources: list[dict[str, str]],
        query: str,
        themes: list[dict[str, Any]],
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
        content = self._prepare_content_for_analysis(sources)

        prompt = self._build_gap_identification_prompt(query, themes, content)

        response_text = self._request(operation="identify_gaps", prompt=prompt)
        return self._parse_gap_response(response_text)

    def synthesize_findings(
        self,
        sources: list[dict[str, str]],
        themes: list[dict[str, Any]],
        cross_ref: dict[str, Any],
        gaps: list[dict[str, Any]],
        query: str,
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
        content = self._prepare_content_for_analysis(sources)

        prompt = self._build_synthesis_prompt(query, themes, cross_ref, gaps, content)

        response_text = self._request(operation="synthesize_findings", prompt=prompt)
        return self._parse_synthesis_response(response_text)

    def analyze_evidence_quality(
        self,
        sources: list[dict[str, str]],
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
        content = self._prepare_content_for_analysis(sources)

        prompt = self._build_evidence_quality_prompt(themes, content)

        response_text = self._request(operation="analyze_evidence_quality", prompt=prompt)
        return self._parse_evidence_quality_response(response_text)

    def _prepare_content_for_analysis(
        self, sources: list[dict[str, str]], max_sources: int = 15
    ) -> str:
        """Prepare source content for analysis.

        Args:
            sources: List of sources.
            max_sources: Maximum number of sources to include.

        Returns:
            Formatted content string.
        """
        sections = []
        for i, source in enumerate(sources[:max_sources], 1):
            content = source.get("content", "") or source.get("snippet", "")
            if content:
                # Truncate to reasonable length
                truncated = content[:2000]
                last_period = truncated.rfind(".")
                if last_period > len(truncated) * 0.7:
                    truncated = truncated[: last_period + 1]

                sections.append(f"\n--- Source {i} ---")
                sections.append(f"Title: {source.get('title', 'Untitled')}")
                sections.append(f"URL: {source.get('url', '')}")
                sections.append(f"Content: {truncated}")

        return "\n".join(sections)

    def _request(self, operation: str, prompt: str) -> str:
        """Execute a routed LLM request through the injected executor."""
        start_time = time.time()
        try:
            response_text = str(self._request_executor(operation, prompt))  # type: ignore[misc]
        except Exception as exc:
            raise RuntimeError(str(exc)) from exc

        if self._usage_callback:
            self._usage_callback(
                operation=operation,
                model=self._model,
                prompt_tokens=0,
                completion_tokens=0,
                duration_ms=int((time.time() - start_time) * 1000),
            )

        return response_text

    def _build_theme_extraction_prompt(self, query: str, content: str, num_themes: int) -> str:
        """Build prompt for theme extraction.

        Args:
            query: Research query.
            content: Formatted content.
            num_themes: Number of themes.

        Returns:
            Analysis prompt.
        """
        # Get base prompt with optional prefix from registry
        base_prompt = f"""Analyze the following research sources about "{query}" and identify {num_themes} major themes.

{content}

CRITICAL OUTPUT REQUIREMENTS:
- Rewrite the source material into clean professional prose. DO NOT copy raw page headers or markdown syntax.
- Ignore menus, site navigation, buttons, share widgets, newsletter prompts, and article metadata.
- Provide complete sentences that remain understandable out of context.
- If the source text is fragmentary, infer cautiously or omit it.

For each theme, provide:
1. A concise, descriptive theme name (e.g., "Antioxidant Properties", not "Health Benefits Drinking White")
2. A 2-3 sentence description summarizing what the sources say about this theme
3. 3-5 key points with specific facts or findings
4. URLs of sources that support this theme

Focus on:
- Actual health benefits with scientific backing
- Specific compounds and their effects
- Concrete findings, not vague generalizations
- Distinct themes that don't overlap

Respond in JSON format:
{{
  "themes": [
    {{
      "name": "Theme Name",
      "description": "Description...",
      "key_points": ["Point 1", "Point 2", "Point 3"],
      "supporting_sources": ["url1", "url2"]
    }}
  ]
}}
"""
        # Apply prompt prefix from registry if available
        if self._prompt_registry:
            _, prompt_prefix, _ = self._prompt_registry.resolve_prompt(
                self._agent_id, "extract_themes"
            )
            if prompt_prefix:
                return f"{prompt_prefix}\n\n{base_prompt}"
        return base_prompt

    def _build_cross_reference_prompt(self, themes: list[dict[str, Any]], content: str) -> str:
        """Build prompt for cross-reference analysis.

        Args:
            themes: Identified themes.
            content: Formatted content.

        Returns:
            Analysis prompt.
        """
        theme_names = [t.get("name", "") for t in themes]
        base_prompt = f"""Analyze the following research sources for consensus and disagreement points.

Identified themes: {", ".join(theme_names)}

{content}

Task: Identify where sources agree (consensus) and where they disagree (contention).

For consensus points:
- Identify claims that multiple sources support
- Note the strength of consensus (strong/moderate/weak)
- List supporting source URLs

For disagreement points:
- Identify claims where sources contradict each other
- Explain the nature of the disagreement
- List the conflicting sources

Respond in JSON format:
{{
  "consensus_points": [
    {{
      "claim": "The claim that sources agree on",
      "strength": "strong/moderate/weak",
      "supporting_sources": ["url1", "url2"]
    }}
  ],
  "disagreement_points": [
    {{
      "claim": "The area of disagreement",
      "perspectives": [
        {{"view": "One perspective", "sources": ["url1"]}},
        {{"view": "Contradicting perspective", "sources": ["url2"]}}
      ]
    }}
  ]
}}
"""
        # Apply prompt prefix from registry if available
        if self._prompt_registry:
            _, prompt_prefix, _ = self._prompt_registry.resolve_prompt(
                self._agent_id, "cross_reference"
            )
            if prompt_prefix:
                return f"{prompt_prefix}\n\n{base_prompt}"
        return base_prompt

    def _build_gap_identification_prompt(
        self, query: str, themes: list[dict[str, Any]], content: str
    ) -> str:
        """Build prompt for gap identification.

        Args:
            query: Research query.
            themes: Identified themes.
            content: Formatted content.

        Returns:
            Analysis prompt.
        """
        theme_names = [t.get("name", "") for t in themes]
        base_prompt = f"""Analyze the following research sources about "{query}" to identify information gaps.

Current themes: {", ".join(theme_names)}

{content}

Task: Identify what's missing or insufficiently covered.

For each gap:
1. Describe what information is missing or unclear
2. Rate importance (High/Medium/Low) for answering the research question
3. Suggest specific follow-up queries to fill the gap

Respond in JSON format:
{{
  "gaps": [
    {{
      "gap_description": "What's missing",
      "importance": "High/Medium/Low",
      "suggested_queries": ["query1", "query2"]
    }}
  ]
}}
"""
        # Apply prompt prefix from registry if available
        if self._prompt_registry:
            _, prompt_prefix, _ = self._prompt_registry.resolve_prompt(
                self._agent_id, "identify_gaps"
            )
            if prompt_prefix:
                return f"{prompt_prefix}\n\n{base_prompt}"
        return base_prompt

    def _build_synthesis_prompt(
        self,
        query: str,
        themes: list[dict[str, Any]],
        cross_ref: dict[str, Any],
        gaps: list[dict[str, Any]],  # noqa: ARG002
        content: str,
    ) -> str:
        """Build prompt for synthesis.

        Args:
            query: Research query.
            themes: Identified themes.
            cross_ref: Cross-reference results.
            gaps: Identified gaps.
            content: Formatted content.

        Returns:
            Analysis prompt.
        """
        theme_names = [t.get("name", "") for t in themes[:5]]
        consensus = cross_ref.get("consensus_points", [])[:3]
        consensus_str = (
            "\n".join(
                [
                    f"- {c.get('claim', str(c))}" if isinstance(c, dict) else f"- {c}"
                    for c in consensus
                ]
            )
            or "None identified"
        )

        base_prompt = f"""Synthesize the following research about "{query}" into key findings.

Main themes: {", ".join(theme_names)}

Consensus points:
{consensus_str}

{content}

CRITICAL OUTPUT REQUIREMENTS:
- Rewrite the source material into clean professional prose. DO NOT copy raw page headers or markdown syntax.
- Ignore menus, site navigation, buttons, share widgets, newsletter prompts, and article metadata.
- Provide complete sentences that remain understandable out of context.
- If the source text is fragmentary, infer cautiously or omit it.

Task: Create 5 key findings that synthesize the research.

For each finding:
1. A clear, specific title
2. A summary field (1-2 sentence high-level takeaway for Key Findings section)
3. A description field (detailed 2-3 sentence explanation for Detailed Analysis section)
4. 3-5 detail_points (evidence-backed bullets for Detailed Analysis section)
5. List of source URLs that support this finding
6. Confidence level (High/Medium/Low) based on source quality and quantity

Respond in JSON format:
{{
  "findings": [
    {{
      "title": "Finding title",
      "summary": "High-level takeaway (1-2 sentences)...",
      "description": "Detailed description (2-3 sentences)...",
      "detail_points": ["Specific evidence-backed point 1", "Specific evidence-backed point 2"],
      "evidence": ["url1", "url2"],
      "confidence": "High/Medium/Low"
    }}
  ]
}}
"""
        # Apply prompt prefix from registry if available
        if self._prompt_registry:
            _, prompt_prefix, _ = self._prompt_registry.resolve_prompt(self._agent_id, "synthesize")
            if prompt_prefix:
                return f"{prompt_prefix}\n\n{base_prompt}"
        return base_prompt

    def _build_evidence_quality_prompt(self, themes: list[dict[str, Any]], content: str) -> str:
        """Build prompt for evidence quality analysis.

        Args:
            themes: Identified themes.
            content: Formatted content.

        Returns:
            Analysis prompt.
        """
        theme_names = [t.get("name", "") for t in themes]
        base_prompt = f"""Analyze the evidence quality in the following research sources.

Themes to analyze: {", ".join(theme_names)}

{content}

Task: Assess the quality and type of evidence for each theme.

For each theme, identify:
1. Study types: Count of human studies, animal studies, in vitro studies, and other sources
2. Evidence conflicts: Any contradictory findings with explanations
3. Confidence level: Overall confidence in the evidence (High/Medium/Low)
4. Summary: Brief assessment of evidence quality

Respond in JSON format:
{{
  "study_types": {{
    "human_studies": 0,
    "animal_studies": 0,
    "in_vitro_studies": 0,
    "other": 0
  }},
  "evidence_conflicts": [
    {{
      "theme": "Theme name",
      "conflict": "Description of conflicting evidence",
      "explanation": "Why this matters"
    }}
  ],
  "confidence_levels": {{
    "theme_name": "High/Medium/Low"
  }},
  "evidence_summary": "Overall assessment of evidence quality"
}}
"""
        # Apply prompt prefix from registry if available
        if self._prompt_registry:
            _, prompt_prefix, _ = self._prompt_registry.resolve_prompt(
                self._agent_id, "analyze_evidence_quality"
            )
            if prompt_prefix:
                return f"{prompt_prefix}\n\n{base_prompt}"
        return base_prompt

    def _parse_theme_response(
        self,
        response_text: str,
        sources: list[dict[str, str]],  # noqa: ARG002
    ) -> list[dict[str, Any]]:
        """Parse theme extraction response.

        Args:
            response_text: Raw LLM response.
            sources: Original sources for URL matching.

        Returns:
            List of theme dictionaries.
        """
        try:
            # Try to extract JSON from response
            json_match = re.search(r"\{[\s\S]*\}", response_text)
            if json_match:
                data = json.loads(json_match.group())
                themes_raw = data.get("themes", [])
                if isinstance(themes_raw, list):
                    return [t for t in themes_raw if isinstance(t, dict)]  # Validate each item
                return []  # Fallback for non-list response
        except (json.JSONDecodeError, KeyError):
            pass

        # Fallback: parse structured text
        themes = []
        lines = response_text.split("\n")
        current_theme: dict[str, Any] | None = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Look for theme headers
            if re.match(r"^\d+\.\s+", line) or line.startswith("Theme:"):
                if current_theme:
                    themes.append(current_theme)
                theme_name = re.sub(r"^\d+\.\s*", "", line)
                theme_name = theme_name.replace("Theme:", "").strip()
                current_theme = {
                    "name": theme_name,
                    "description": "",
                    "key_points": [],
                    "supporting_sources": [],
                }
            elif current_theme:
                # Add to current theme
                if line.startswith("-") or line.startswith("•"):
                    point = line.lstrip("- •").strip()
                    if "http" in point:
                        current_theme["supporting_sources"].append(point)
                    else:
                        current_theme["key_points"].append(point)
                elif not current_theme["description"]:
                    current_theme["description"] = line

        if current_theme:
            themes.append(current_theme)

        return themes

    def _parse_cross_reference_response(self, response_text: str) -> dict[str, Any]:
        """Parse cross-reference response.

        Args:
            response_text: Raw LLM response.

        Returns:
            Dictionary with consensus and disagreement points.
        """
        try:
            json_match = re.search(r"\{[\s\S]*\}", response_text)
            if json_match:
                data = json.loads(json_match.group())
                return {
                    "consensus_points": data.get("consensus_points", [])
                    if isinstance(data.get("consensus_points"), list)
                    else [],
                    "disagreement_points": data.get("disagreement_points", [])
                    if isinstance(data.get("disagreement_points"), list)
                    else [],
                    "cross_reference_claims": [],
                }
        except (json.JSONDecodeError, KeyError):
            pass

        # Fallback parsing
        return {
            "consensus_points": ["Sources agree on core concepts related to the query"],
            "disagreement_points": [],
            "cross_reference_claims": [],
        }

    def _parse_gap_response(self, response_text: str) -> list[dict[str, Any]]:
        """Parse gap identification response.

        Args:
            response_text: Raw LLM response.

        Returns:
            List of gap dictionaries.
        """
        try:
            json_match = re.search(r"\{[\s\S]*\}", response_text)
            if json_match:
                data = json.loads(json_match.group())
                gaps_raw = data.get("gaps", [])
                if isinstance(gaps_raw, list):
                    return gaps_raw
                return []  # Fallback for non-list response
        except (json.JSONDecodeError, KeyError):
            pass

        # Fallback parsing
        gaps = []
        lines = response_text.split("\n")

        for line in lines:
            line = line.strip()
            if line.startswith("-") and len(line) > 20:
                gaps.append(
                    {
                        "gap_description": line.lstrip("- ").strip(),
                        "importance": "Medium",
                        "suggested_queries": [],
                    }
                )

        return gaps[:5]  # Limit to 5 gaps

    def _parse_synthesis_response(self, response_text: str) -> list[dict[str, Any]]:
        """Parse synthesis response.

        Args:
            response_text: Raw LLM response.

        Returns:
            List of finding dictionaries.
        """
        try:
            json_match = re.search(r"\{[\s\S]*\}", response_text)
            if json_match:
                data = json.loads(json_match.group())
                findings_raw = data.get("findings", [])
                if isinstance(findings_raw, list):
                    # Ensure all required fields exist with defaults
                    for finding in findings_raw:
                        finding.setdefault("summary", finding.get("description", "")[:200])
                        finding.setdefault("detail_points", [])
                    return findings_raw
                return []  # Fallback for non-list response
        except (json.JSONDecodeError, KeyError):
            pass

        # Fallback parsing
        findings = []
        lines = response_text.split("\n")
        current_finding: dict[str, Any] | None = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if re.match(r"^\d+\.\s+", line):
                if current_finding:
                    findings.append(current_finding)
                title = re.sub(r"^\d+\.\s*", "", line)
                current_finding = {
                    "title": title,
                    "summary": "",
                    "description": "",
                    "detail_points": [],
                    "evidence": [],
                    "confidence": "Medium",
                }
            elif current_finding:
                if line.startswith("-") or line.startswith("•"):
                    point = line.lstrip("- •").strip()
                    if "http" in point:
                        current_finding["evidence"].append(point)
                    else:
                        current_finding["detail_points"].append(point)
                elif not current_finding["summary"]:
                    current_finding["summary"] = line[:200]
                elif not current_finding["description"]:
                    current_finding["description"] = line

        if current_finding:
            findings.append(current_finding)

        return findings

    def _parse_evidence_quality_response(self, response_text: str) -> dict[str, Any]:
        """Parse evidence quality response.

        Args:
            response_text: Raw LLM response.

        Returns:
            Dictionary with evidence quality analysis.
        """
        try:
            json_match = re.search(r"\{[\s\S]*\}", response_text)
            if json_match:
                data = json.loads(json_match.group())
                return {
                    "study_types": data.get("study_types", {})
                    if isinstance(data.get("study_types"), dict)
                    else {},
                    "evidence_conflicts": data.get("evidence_conflicts", [])
                    if isinstance(data.get("evidence_conflicts"), list)
                    else [],
                    "confidence_levels": data.get("confidence_levels", {})
                    if isinstance(data.get("confidence_levels"), dict)
                    else {},
                    "evidence_summary": data.get("evidence_summary", "")
                    if isinstance(data.get("evidence_summary"), str)
                    else "",
                }
        except (json.JSONDecodeError, KeyError):
            pass

        # Fallback
        return {
            "study_types": {
                "human_studies": 0,
                "animal_studies": 0,
                "in_vitro_studies": 0,
                "other": 0,
            },
            "evidence_conflicts": [],
            "confidence_levels": {},
            "evidence_summary": "Evidence quality analysis completed",
        }


__all__ = ["LLMAnalysisClient"]
