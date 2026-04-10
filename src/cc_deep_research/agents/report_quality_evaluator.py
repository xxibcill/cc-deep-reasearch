"""Report quality evaluator agent implementation.

This agent evaluates FINAL markdown report content for quality dimensions
that PostReportValidator's regex-based checks cannot detect.

Quality dimensions evaluated:
- Writing quality (clarity, grammar, coherence)
- Report structure and flow
- Technical accuracy of synthesized content
- User experience (readability, usefulness)
- Consistency with analysis findings
- Executive Summary quality (banned phrases, size budget, gap inventory)

LLM Routing:
This agent supports the shared LLM routing layer. When an LLMRouter is provided,
it can use LLM-based evaluation for more nuanced quality assessment. Otherwise,
it falls back to heuristic-based evaluation.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from cc_deep_research.llm.router import LLMRouter
    from cc_deep_research.prompts import PromptRegistry

from cc_deep_research.agents.ai_agent_integration import AIAgentIntegration
from cc_deep_research.agents.ai_executor import AIExecutor
from cc_deep_research.agents.reporter import (
    EXECUTIVE_SUMMARY_BANNED_PHRASES,
    EXECUTIVE_SUMMARY_GAPS_POINTER,
    EXECUTIVE_SUMMARY_MAX_CHARACTERS,
)
from cc_deep_research.models import (
    AnalysisResult,
    ReportEvaluationResult,
    ResearchSession,
)

if TYPE_CHECKING:
    from cc_deep_research.llm.router import LLMRouter
    from cc_deep_research.prompts import PromptRegistry

logger = logging.getLogger(__name__)

# Agent identifier for LLM routing
AGENT_ID = "report_quality_evaluator"


class ReportQualityEvaluatorAgent:
    """Agent that evaluates report quality after generation.

    This agent evaluates:
    - Writing quality (clarity, grammar, coherence)
    - Report structure and flow
    - Technical accuracy of synthesized content
    - User experience aspects (readability, usefulness)
    - Consistency with findings from analysis

    LLM Routing Support:
    When an LLMRouter is provided, this agent can use LLM-based evaluation
    for more nuanced quality assessment. The route is resolved through the
    shared routing layer, which supports:
    - Anthropic API
    - OpenRouter API (for API-based evaluation)
    - Cerebras API (for fast inference)
    - Heuristic fallback (when no LLM available)
    """

    def __init__(
        self,
        config: dict[str, Any],
        *,
        llm_router: LLMRouter | None = None,
        prompt_registry: PromptRegistry | None = None,
    ) -> None:
        """Initialize the report quality evaluator.

        Args:
            config: Agent configuration dictionary.
            llm_router: Optional LLM router for shared routing layer integration.
            prompt_registry: Optional prompt registry with overrides.
        """
        self._config = config
        self._enabled = config.get("enable_report_quality_evaluation", True)
        self._min_acceptable_score = config.get("min_report_quality_score", 0.6)
        self._integration_method = config.get("ai_integration_method", "heuristic")
        self._llm_router = llm_router
        self._prompt_registry = prompt_registry

        # Initialize AI components (legacy support)
        self._ai_integration = AIAgentIntegration(config)
        self._ai_executor = AIExecutor(config)

        # Track which transport was actually used
        self._last_transport_used: str = "heuristic"

    @property
    def last_transport_used(self) -> str:
        """Return the transport type used for the last evaluation."""
        return self._last_transport_used

    async def evaluate_with_llm(
        self,
        markdown: str,
        session: ResearchSession,
        analysis: AnalysisResult,
    ) -> dict[str, Any] | None:
        """Evaluate report quality using LLM via the shared routing layer.

        This method attempts to use the configured LLM transport for more
        nuanced quality assessment. If no LLM is available, returns None
        to signal fallback to heuristic evaluation.

        Args:
            markdown: Generated markdown report content.
            session: The research session.
            analysis: Analysis results from analyzer.

        Returns:
            Dictionary with LLM-based evaluation results, or None if
            LLM evaluation is not available.
        """
        if self._llm_router is None:
            return None

        if not self._llm_router.is_available(AGENT_ID):
            return None

        # Build evaluation prompt
        prompt = self._build_llm_evaluation_prompt(markdown, analysis)

        try:
            response = await self._llm_router.execute(
                agent_id=AGENT_ID,
                prompt=prompt,
                system_prompt=self._get_system_prompt(),
                metadata={
                    "operation": "report_quality_evaluation",
                    "session_id": session.session_id,
                },
            )

            # Track transport used
            self._last_transport_used = response.transport.value

            if response.content:
                return self._parse_llm_response(response.content)

        except Exception as e:
            logger.warning(f"LLM evaluation failed, falling back to heuristic: {e}")
            self._last_transport_used = "heuristic"

        return None

    def _build_llm_evaluation_prompt(
        self,
        markdown: str,
        analysis: AnalysisResult,
    ) -> str:
        """Build the evaluation prompt for the LLM.

        Args:
            markdown: Report content to evaluate.
            analysis: Analysis results for context.

        Returns:
            The evaluation prompt.
        """
        # Truncate markdown if too long
        max_chars = 8000
        truncated_markdown = markdown[:max_chars]
        if len(markdown) > max_chars:
            truncated_markdown += "\n... [truncated]"

        findings_summary = "\n".join(f"- {f}" for f in analysis.key_findings[:5])
        themes_summary = ", ".join(analysis.themes[:5])

        base_prompt = f"""Evaluate the quality of this research report on a scale of 0.0 to 1.0 for each dimension.

REPORT CONTENT:
{truncated_markdown}

EXPECTED FINDINGS (from analysis):
{findings_summary}

EXPECTED THEMES:
{themes_summary}

Provide your evaluation in this exact JSON format:
{{
    "writing_quality": {{
        "score": <0.0-1.0>,
        "issues": ["issue1", ...],
        "recommendations": ["rec1", ...]
    }},
    "structure_flow": {{
        "score": <0.0-1.0>,
        "issues": ["issue1", ...],
        "recommendations": ["rec1", ...]
    }},
    "technical_accuracy": {{
        "score": <0.0-1.0>,
        "issues": ["issue1", ...],
        "recommendations": ["rec1", ...]
    }},
    "user_experience": {{
        "score": <0.0-1.0>,
        "issues": ["issue1", ...],
        "recommendations": ["rec1", ...]
    }},
    "consistency": {{
        "score": <0.0-1.0>,
        "issues": ["issue1", ...],
        "recommendations": ["rec1", ...]
    }},
    "executive_summary": {{
        "score": <0.0-1.0>,
        "issues": ["issue1", ...],
        "recommendations": ["rec1", ...]
    }}
}}

Focus on:
- Writing quality: clarity, grammar, coherence
- Structure: logical flow, proper sections
- Technical accuracy: correct representation of findings
- User experience: readability, actionability
- Consistency: alignment with analysis findings
- Executive summary: concise, insight-focused"""

        # Apply prompt prefix from registry if available
        if self._prompt_registry:
            _, prompt_prefix, _ = self._prompt_registry.resolve_prompt(AGENT_ID, "evaluate")
            if prompt_prefix:
                return f"{prompt_prefix}\n\n{base_prompt}"
        return base_prompt

    def _get_system_prompt(self) -> str:
        """Get the system prompt for LLM evaluation."""
        default_system_prompt = """You are an expert research report quality evaluator. Your task is to assess research reports for quality across multiple dimensions. Provide objective, constructive feedback with specific scores and actionable recommendations. Always respond with valid JSON in the exact format requested."""

        # Use override from registry if available
        if self._prompt_registry:
            system_prompt, _, _ = self._prompt_registry.resolve_prompt(AGENT_ID, "evaluate")
            if system_prompt:
                return system_prompt
        return default_system_prompt

    def _parse_llm_response(self, content: str) -> dict[str, Any]:
        """Parse the LLM response into structured evaluation data.

        Args:
            content: The LLM response content.

        Returns:
            Parsed evaluation dictionary.
        """
        import json

        # Try to extract JSON from the response
        try:
            # Find JSON object in response
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = content[start:end]
                return cast(dict[str, Any], json.loads(json_str))
        except json.JSONDecodeError:
            pass

        # Return empty structure if parsing fails
        return {
            "writing_quality": {"score": 0.5, "issues": [], "recommendations": []},
            "structure_flow": {"score": 0.5, "issues": [], "recommendations": []},
            "technical_accuracy": {"score": 0.5, "issues": [], "recommendations": []},
            "user_experience": {"score": 0.5, "issues": [], "recommendations": []},
            "consistency": {"score": 0.5, "issues": [], "recommendations": []},
            "executive_summary": {"score": 0.5, "issues": [], "recommendations": []},
        }

    async def evaluate_report_quality(
        self,
        markdown: str,
        session: ResearchSession,
        analysis: AnalysisResult,
    ) -> ReportEvaluationResult:
        """Evaluate quality of a generated markdown report.

        This method first attempts LLM-based evaluation if an LLMRouter is
        configured and available. If LLM evaluation fails or is unavailable,
        it falls back to heuristic-based evaluation.

        Args:
            markdown: Generated markdown report content.
            session: The research session.
            analysis: Analysis results from analyzer.

        Returns:
            ReportEvaluationResult with quality assessment.
        """
        if not self._enabled:
            self._last_transport_used = "disabled"
            return ReportEvaluationResult(overall_quality_score=0.0, is_acceptable=True)

        # Try LLM-based evaluation first
        llm_result = await self.evaluate_with_llm(markdown, session, analysis)

        if llm_result is not None:
            # Use LLM-based evaluation
            return self._build_result_from_llm(llm_result, markdown, analysis)

        # Fall back to heuristic evaluation
        self._last_transport_used = "heuristic"
        return self._evaluate_with_heuristics(markdown, analysis)

    def evaluate_report_quality_sync(
        self,
        markdown: str,
        session: ResearchSession,
        analysis: AnalysisResult,
    ) -> ReportEvaluationResult:
        """Synchronous wrapper for evaluate_report_quality.

        This method provides backward compatibility for code that cannot
        use async/await. It runs the async evaluation in a new event loop.

        Args:
            markdown: Generated markdown report content.
            session: The research session.
            analysis: Analysis results from analyzer.

        Returns:
            ReportEvaluationResult with quality assessment.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None:
            # Already in an async context - create a task
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self.evaluate_report_quality(markdown, session, analysis),
                )
                return future.result()
        else:
            # No running loop - create one
            return asyncio.run(self.evaluate_report_quality(markdown, session, analysis))

    def _build_result_from_llm(
        self,
        llm_result: dict[str, Any],
        markdown: str,
        analysis: AnalysisResult,
    ) -> ReportEvaluationResult:
        """Build a ReportEvaluationResult from LLM evaluation output.

        Args:
            llm_result: Parsed LLM evaluation result.
            markdown: Original markdown for any additional checks.
            analysis: Analysis results.

        Returns:
            ReportEvaluationResult with LLM-based scores.
        """
        # Extract scores from LLM result
        writing_quality = llm_result.get("writing_quality", {})
        structure_flow = llm_result.get("structure_flow", {})
        technical_accuracy = llm_result.get("technical_accuracy", {})
        user_experience = llm_result.get("user_experience", {})
        consistency = llm_result.get("consistency", {})
        executive_summary = llm_result.get("executive_summary", {})

        # Also run executive summary guardrails check
        exec_summary_guardrails = self._evaluate_executive_summary(markdown, analysis)

        dimension_scores = {
            "writing_quality": writing_quality.get("score", 0.5),
            "structure_flow": structure_flow.get("score", 0.5),
            "technical_accuracy": technical_accuracy.get("score", 0.5),
            "user_experience": user_experience.get("score", 0.5),
            "consistency": consistency.get("score", 0.5),
            "executive_summary": executive_summary.get("score", 0.5),
        }

        overall_score = self._calculate_overall_score(dimension_scores)
        is_acceptable = overall_score >= self._min_acceptable_score

        # Collect issues and recommendations
        critical_issues = exec_summary_guardrails.get("critical_issues", [])
        warnings = []
        recommendations = []

        for _dimension_name, dimension_data in llm_result.items():
            if isinstance(dimension_data, dict):
                warnings.extend(dimension_data.get("issues", []))
                recommendations.extend(dimension_data.get("recommendations", []))

        # Add guardrails warnings
        warnings.extend(exec_summary_guardrails.get("warnings", []))

        return ReportEvaluationResult(
            overall_quality_score=overall_score,
            is_acceptable=is_acceptable,
            writing_quality_score=dimension_scores["writing_quality"],
            structure_flow_score=dimension_scores["structure_flow"],
            technical_accuracy_score=dimension_scores["technical_accuracy"],
            user_experience_score=dimension_scores["user_experience"],
            consistency_score=dimension_scores["consistency"],
            critical_issues=critical_issues,
            warnings=warnings,
            recommendations=recommendations,
            dimension_assessments=llm_result,
            evaluation_method="llm_analysis",
        )

    def _evaluate_with_heuristics(
        self,
        markdown: str,
        analysis: AnalysisResult,
    ) -> ReportEvaluationResult:
        """Evaluate report quality using heuristic methods.

        This is the fallback evaluation when LLM is not available.

        Args:
            markdown: Report content to evaluate.
            analysis: Analysis results from analyzer.

        Returns:
            ReportEvaluationResult with heuristic-based assessment.
        """
        # Evaluate each quality dimension
        writing_quality = self._evaluate_writing_quality(markdown)
        structure_flow = self._evaluate_structure_and_flow(markdown)
        technical_accuracy = self._evaluate_technical_accuracy(markdown, analysis)
        user_experience = self._evaluate_user_experience(markdown)
        consistency = self._evaluate_consistency(markdown, analysis)
        executive_summary = self._evaluate_executive_summary(markdown, analysis)

        # Collect issues and warnings from all dimensions
        critical_issues = []
        warnings = []
        recommendations = []

        for assessment in [
            writing_quality,
            structure_flow,
            technical_accuracy,
            user_experience,
            consistency,
            executive_summary,
        ]:
            critical_issues.extend(assessment.get("critical_issues", []))
            warnings.extend(assessment.get("warnings", []))
            recommendations.extend(assessment.get("recommendations", []))

        # Calculate overall quality score (weighted average)
        dimension_scores = {
            "writing_quality": writing_quality["score"],
            "structure_flow": structure_flow["score"],
            "technical_accuracy": technical_accuracy["score"],
            "user_experience": user_experience["score"],
            "consistency": consistency["score"],
            "executive_summary": executive_summary["score"],
        }
        overall_score = self._calculate_overall_score(dimension_scores)

        # Determine if report is acceptable
        is_acceptable = overall_score >= self._min_acceptable_score

        # Collect detailed assessments
        dimension_assessments = {
            "writing_quality": writing_quality,
            "structure_flow": structure_flow,
            "technical_accuracy": technical_accuracy,
            "user_experience": user_experience,
            "consistency": consistency,
            "executive_summary": executive_summary,
        }

        return ReportEvaluationResult(
            overall_quality_score=overall_score,
            is_acceptable=is_acceptable,
            writing_quality_score=dimension_scores["writing_quality"],
            structure_flow_score=dimension_scores["structure_flow"],
            technical_accuracy_score=dimension_scores["technical_accuracy"],
            user_experience_score=dimension_scores["user_experience"],
            consistency_score=dimension_scores["consistency"],
            critical_issues=critical_issues,
            warnings=warnings,
            recommendations=recommendations,
            dimension_assessments=dimension_assessments,
            evaluation_method="heuristic",
        )

    def _evaluate_writing_quality(self, markdown: str) -> dict[str, Any]:
        """Evaluate clarity, grammar, and coherence.

        Args:
            markdown: Report content to evaluate.

        Returns:
            Dictionary with score, issues, warnings, recommendations.
        """
        issues: list[str] = []
        warnings: list[str] = []
        recommendations: list[str] = []

        # Check for very short sentences (potential clarity issues)
        sentence_pattern = r"(?<=[.!?])\s+"
        sentences = re.split(sentence_pattern, markdown)
        short_sentences = [s for s in sentences if len(s.strip()) > 0 and len(s.strip()) < 30]

        # Check for excessive sentence length (potential readability issues)
        very_long_sentences = [s for s in sentences if len(s.strip()) > 300]

        # Check for paragraph structure
        paragraph_pattern = r"\n\s*\n"
        paragraphs = [p for p in re.split(paragraph_pattern, markdown) if len(p.strip()) > 50]
        very_short_paragraphs = [p for p in paragraphs if len(p.strip()) < 100]

        # Calculate score
        score = 0.8  # Base score
        if len(short_sentences) > len(sentences) * 0.2:
            score -= 0.1
            warnings.append(
                f"Many short sentences found ({len(short_sentences)} out of {len(sentences)})"
            )
        if len(very_long_sentences) > 0:
            score -= 0.1
            warnings.append(f"Found {len(very_long_sentences)} very long sentences (>300 chars)")
        if len(very_short_paragraphs) > len(paragraphs) * 0.3:
            score -= 0.1
            warnings.append(
                f"Many very short paragraphs ({len(very_short_paragraphs)} out of {len(paragraphs)})"
            )

        score = max(0.0, min(1.0, score))

        if score < 0.6:
            recommendations.append(
                "Improve writing clarity by using complete, well-structured sentences"
            )

        return {
            "score": score,
            "critical_issues": issues,
            "warnings": warnings,
            "recommendations": recommendations,
        }

    def _evaluate_structure_and_flow(self, markdown: str) -> dict[str, Any]:
        """Evaluate logical flow and section organization.

        Args:
            markdown: Report content to evaluate.

        Returns:
            Dictionary with score, issues, warnings, recommendations.
        """
        issues: list[str] = []
        warnings: list[str] = []
        recommendations: list[str] = []

        # Check for required sections
        required_sections = ["## Executive Summary", "## Key Findings", "## Sources", "## Safety"]
        missing_sections = [s for s in required_sections if s not in markdown]

        # Check section structure
        section_headers = re.findall(r"^#{1,3}\s+.+", markdown, re.MULTILINE)
        has_nested_headers = any(h.startswith("###") for h in section_headers)

        # Check for lists (good for readability)
        has_bullet_lists = bool(re.search(r"^\s*[-*+]\s", markdown, re.MULTILINE))
        has_numbered_lists = bool(re.search(r"^\s*\d+\.\s", markdown, re.MULTILINE))

        # Calculate score
        score = 0.8  # Base score
        if missing_sections:
            score -= 0.2 * len(missing_sections)
            issues.extend([f"Missing required section: {s}" for s in missing_sections])
        if not has_nested_headers:
            score -= 0.1
            warnings.append("No nested headers found - consider using ### for subsections")
        if not has_bullet_lists and not has_numbered_lists:
            score -= 0.1
            warnings.append("No bulleted or numbered lists found - lists improve readability")

        score = max(0.0, min(1.0, score))

        if missing_sections:
            recommendations.append("Ensure all required sections are present in the report")

        return {
            "score": score,
            "critical_issues": issues,
            "warnings": warnings,
            "recommendations": recommendations,
        }

    def _evaluate_technical_accuracy(
        self,
        markdown: str,
        analysis: AnalysisResult,
    ) -> dict[str, Any]:
        """Check synthesized content accuracy against analysis.

        Args:
            markdown: Report content to evaluate.
            analysis: Analysis results from analyzer.

        Returns:
            Dictionary with score, issues, warnings, recommendations.
        """
        issues: list[str] = []
        warnings: list[str] = []
        recommendations: list[str] = []

        # Check if key findings are referenced
        finding_count = len(analysis.key_findings)
        if finding_count > 0:
            # Check if findings are mentioned in the report
            findings_mentioned = 0
            for finding in analysis.key_findings:
                finding_text = str(finding).lower()[:100]
                if finding_text in markdown.lower():
                    findings_mentioned += 1

            findings_ratio = findings_mentioned / finding_count
            score = findings_ratio
        else:
            score = 1.0  # No findings to check

        # Check citation format
        citations = re.findall(r"\[(\d+)\]", markdown)
        if citations and len(analysis.cross_reference_claims) > 0:
            max_citation = int(max(citations))
            if max_citation > len(analysis.cross_reference_claims) + 5:
                warnings.append("Citation numbering seems inconsistent with available claims")

        if score < 0.7 and finding_count > 0:
            recommendations.append(
                f"Only {score:.0%} of key findings appear to be referenced in the report"
            )

        return {
            "score": score,
            "critical_issues": issues,
            "warnings": warnings,
            "recommendations": recommendations,
        }

    def _evaluate_user_experience(
        self,
        markdown: str,
    ) -> dict[str, Any]:
        """Assess readability and usefulness.

        Args:
            markdown: Report content to evaluate.

        Returns:
            Dictionary with score, issues, warnings, recommendations.
        """
        issues: list[str] = []
        warnings: list[str] = []
        recommendations: list[str] = []

        # Check report length
        report_length = len(markdown)
        ideal_length = 3000  # Target ~3k characters for good balance
        length_score = 1.0 - abs(report_length - ideal_length) / (ideal_length * 2)
        length_score = max(0.3, min(1.0, length_score))

        # Check for jargon density (rough heuristic)
        common_jargon = ["utilize", "leverage", "paradigm", "synergistic", "holistic"]
        jargon_count = sum(1 for word in common_jargon if word.lower() in markdown.lower())
        jargon_density = jargon_count / (len(markdown.split()) + 1)

        # Check for actionable insights
        has_conclusions = bool(
            re.search(r"## (Conclusions?|Recommendations?)", markdown, re.IGNORECASE)
        )
        has_actionable = any(
            word in markdown.lower() for word in ["recommend", "should", "consider", "implement"]
        )

        # Calculate score
        score = (length_score * 0.4) + (1.0 - jargon_density * 5) * 0.3
        if has_conclusions or has_actionable:
            score += 0.3

        score = max(0.0, min(1.0, score))

        if jargon_count > 5:
            warnings.append(f"Potential overuse of jargon ({jargon_count} instances)")
        if not has_conclusions and not has_actionable:
            recommendations.append(
                "Consider adding a conclusions or recommendations section for actionability"
            )

        return {
            "score": score,
            "critical_issues": issues,
            "warnings": warnings,
            "recommendations": recommendations,
        }

    def _evaluate_consistency(
        self,
        markdown: str,
        analysis: AnalysisResult,
    ) -> dict[str, Any]:
        """Verify report matches analysis findings.

        Args:
            markdown: Report content to evaluate.
            analysis: Analysis results from analyzer.

        Returns:
            Dictionary with score, issues, warnings, recommendations.
        """
        issues: list[str] = []
        warnings: list[str] = []
        recommendations: list[str] = []

        # Check theme consistency
        themes_mentioned = 0
        for theme in analysis.themes[:5]:  # Check top 5 themes
            if theme.lower()[:50] in markdown.lower():
                themes_mentioned += 1

        theme_score = themes_mentioned / max(len(analysis.themes), 1)

        # Check consensus points
        consensus_mentioned = 0
        for consensus in analysis.consensus_points[:3]:  # Check top 3
            if consensus.lower()[:50] in markdown.lower():
                consensus_mentioned += 1

        consensus_score = consensus_mentioned / max(len(analysis.consensus_points), 1)

        # Calculate overall consistency score
        score = (theme_score + consensus_score) / 2

        if score < 0.7:
            warnings.append("Report may not fully reflect analysis themes and consensus points")
            recommendations.append(
                "Ensure major themes and consensus points are covered in the report"
            )

        return {
            "score": score,
            "critical_issues": issues,
            "warnings": warnings,
            "recommendations": recommendations,
        }

    def _evaluate_executive_summary(
        self,
        markdown: str,
        analysis: AnalysisResult,
    ) -> dict[str, Any]:
        """Evaluate Executive Summary quality against guardrails.

        This method checks for:
        - Banned boilerplate phrases (prompt restatement, methodology chatter)
        - Summary length exceeding the configured budget
        - Inline gap inventories instead of brief pointer

        Args:
            markdown: Report content to evaluate.
            analysis: Analysis results from analyzer.

        Returns:
            Dictionary with score, issues, warnings, recommendations.
        """
        issues: list[str] = []
        warnings: list[str] = []
        recommendations: list[str] = []

        # Extract the Executive Summary section
        exec_summary_match = re.search(
            r"## Executive Summary\n(.*?)(?=\n## |\Z)", markdown, re.DOTALL
        )

        if not exec_summary_match:
            issues.append("Executive Summary section not found")
            return {
                "score": 0.0,
                "critical_issues": issues,
                "warnings": warnings,
                "recommendations": recommendations,
            }

        exec_summary = exec_summary_match.group(1).strip()
        score = 1.0  # Start with perfect score

        # Check for banned boilerplate phrases
        for banned_phrase in EXECUTIVE_SUMMARY_BANNED_PHRASES:
            if banned_phrase in exec_summary:
                score -= 0.3
                warnings.append(
                    f"Executive Summary contains banned boilerplate phrase: '{banned_phrase}'"
                )

        # Check for length exceeding budget
        if len(exec_summary) > EXECUTIVE_SUMMARY_MAX_CHARACTERS:
            score -= 0.2
            warnings.append(
                f"Executive Summary exceeds character budget "
                f"({len(exec_summary)} > {EXECUTIVE_SUMMARY_MAX_CHARACTERS})"
            )

        # Check for inline gap inventory (listing gaps instead of pointer)
        # If there are gaps in analysis and the summary doesn't use the pointer
        # but contains gap-related phrases
        gaps = analysis.normalized_gaps()
        if gaps:
            # Check if summary has gap descriptions inline instead of pointer
            has_pointer = EXECUTIVE_SUMMARY_GAPS_POINTER[:50] in exec_summary
            has_inline_gaps = any(gap.gap_description[:30] in exec_summary for gap in gaps)

            if has_inline_gaps and not has_pointer:
                score -= 0.2
                warnings.append(
                    "Executive Summary lists gaps inline instead of using a brief pointer"
                )

        # Ensure score is within bounds
        score = max(0.0, min(1.0, score))

        if score < 0.7:
            recommendations.append(
                "Rewrite Executive Summary to be insight-only: remove prompt restatement, "
                "methodology chatter, and use brief pointer for gaps"
            )

        return {
            "score": score,
            "critical_issues": issues,
            "warnings": warnings,
            "recommendations": recommendations,
        }

    def _calculate_overall_score(self, dimension_scores: dict[str, float]) -> float:
        """Calculate weighted overall quality score.

        Args:
            dimension_scores: Dictionary of dimension scores.

        Returns:
            Overall quality score (0-1).
        """
        # Weights based on importance
        weights = {
            "writing_quality": 0.20,
            "structure_flow": 0.15,
            "technical_accuracy": 0.20,
            "user_experience": 0.15,
            "consistency": 0.15,
            "executive_summary": 0.15,
        }

        total_score = sum(dimension_scores[dim] * weights[dim] for dim in weights)

        return max(0.0, min(1.0, total_score))


__all__ = ["ReportQualityEvaluatorAgent"]
