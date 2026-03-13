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
"""

import logging
import re
from typing import Any

from cc_deep_research.agents.ai_agent_integration import AIAgentIntegration
from cc_deep_research.agents.ai_executor import AIExecutor
from cc_deep_research.agents.reporter import (
    EXECUTIVE_SUMMARY_BANNED_PHRASES,
    EXECUTIVE_SUMMARY_GAPS_POINTER,
    EXECUTIVE_SUMMARY_MAX_CHARACTERS,
)
from cc_deep_research.models import AnalysisResult, ReportEvaluationResult, ResearchSession

logger = logging.getLogger(__name__)


class ReportQualityEvaluatorAgent:
    """Agent that evaluates report quality after generation.

    This agent evaluates:
    - Writing quality (clarity, grammar, coherence)
    - Report structure and flow
    - Technical accuracy of synthesized content
    - User experience aspects (readability, usefulness)
    - Consistency with findings from analysis
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the report quality evaluator.

        Args:
            config: Agent configuration dictionary.
        """
        self._config = config
        self._enabled = config.get("enable_report_quality_evaluation", True)
        self._min_acceptable_score = config.get("min_report_quality_score", 0.6)
        self._integration_method = config.get("ai_integration_method", "heuristic")

        # Initialize AI components
        self._ai_integration = AIAgentIntegration(config)
        self._ai_executor = AIExecutor(config)

    def evaluate_report_quality(
        self,
        markdown: str,
        session: ResearchSession,
        analysis: AnalysisResult,
    ) -> ReportEvaluationResult:
        """Evaluate quality of a generated markdown report.

        Args:
            markdown: Generated markdown report content.
            analysis: Analysis results from analyzer.

        Returns:
            ReportEvaluationResult with quality assessment.
        """
        if not self._enabled:
            return ReportEvaluationResult(overall_quality_score=0.0, is_acceptable=True)

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

        for assessment in [writing_quality, structure_flow, technical_accuracy, user_experience, consistency, executive_summary]:
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
            evaluation_method="llm_analysis" if self._integration_method in ("api", "hybrid") else "heuristic",
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
        sentence_pattern = r'(?<=[.!?])\s+'
        sentences = re.split(sentence_pattern, markdown)
        short_sentences = [s for s in sentences if len(s.strip()) > 0 and len(s.strip()) < 30]

        # Check for excessive sentence length (potential readability issues)
        very_long_sentences = [s for s in sentences if len(s.strip()) > 300]

        # Check for paragraph structure
        paragraph_pattern = r'\n\s*\n'
        paragraphs = [p for p in re.split(paragraph_pattern, markdown) if len(p.strip()) > 50]
        very_short_paragraphs = [p for p in paragraphs if len(p.strip()) < 100]

        # Calculate score
        score = 0.8  # Base score
        if len(short_sentences) > len(sentences) * 0.2:
            score -= 0.1
            warnings.append(f"Many short sentences found ({len(short_sentences)} out of {len(sentences)})")
        if len(very_long_sentences) > 0:
            score -= 0.1
            warnings.append(f"Found {len(very_long_sentences)} very long sentences (>300 chars)")
        if len(very_short_paragraphs) > len(paragraphs) * 0.3:
            score -= 0.1
            warnings.append(f"Many very short paragraphs ({len(very_short_paragraphs)} out of {len(paragraphs)})")

        score = max(0.0, min(1.0, score))

        if score < 0.6:
            recommendations.append("Improve writing clarity by using complete, well-structured sentences")

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
        section_headers = re.findall(r'^#{1,3}\s+.+', markdown, re.MULTILINE)
        has_nested_headers = any(h.startswith("###") for h in section_headers)

        # Check for lists (good for readability)
        has_bullet_lists = bool(re.search(r'^\s*[-*+]\s', markdown, re.MULTILINE))
        has_numbered_lists = bool(re.search(r'^\s*\d+\.\s', markdown, re.MULTILINE))

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
        citations = re.findall(r'\[(\d+)\]', markdown)
        if citations and len(analysis.cross_reference_claims) > 0:
            max_citation = int(max(citations))
            if max_citation > len(analysis.cross_reference_claims) + 5:
                warnings.append("Citation numbering seems inconsistent with available claims")

        if score < 0.7 and finding_count > 0:
            recommendations.append(f"Only {score:.0%} of key findings appear to be referenced in the report")

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
        has_conclusions = bool(re.search(r'## (Conclusions?|Recommendations?)', markdown, re.IGNORECASE))
        has_actionable = any(
            word in markdown.lower()
            for word in ["recommend", "should", "consider", "implement"]
        )

        # Calculate score
        score = (length_score * 0.4) + (1.0 - jargon_density * 5) * 0.3
        if has_conclusions or has_actionable:
            score += 0.3

        score = max(0.0, min(1.0, score))

        if jargon_count > 5:
            warnings.append(f"Potential overuse of jargon ({jargon_count} instances)")
        if not has_conclusions and not has_actionable:
            recommendations.append("Consider adding a conclusions or recommendations section for actionability")

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
            recommendations.append("Ensure major themes and consensus points are covered in the report")

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
            r'## Executive Summary\n(.*?)(?=\n## |\Z)',
            markdown,
            re.DOTALL
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
            has_inline_gaps = any(
                gap.get("gap_description", "")[:30] in exec_summary
                for gap in gaps if isinstance(gap, dict)
            )

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
