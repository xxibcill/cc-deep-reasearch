"""Report refinement agent implementation.

This agent takes the original report along with validation and evaluation results
to generate a refined version that addresses identified issues.
"""

import logging
import re
from typing import Any

from cc_deep_research.models import AnalysisResult, ReportEvaluationResult, ResearchSession, ValidationResult


logger = logging.getLogger(__name__)


class ReportRefinerAgent:
    """Agent that refines reports based on validation and evaluation feedback.

    This agent:
    - Takes original report, validation results, and evaluation results
    - Generates refined report addressing identified issues
    - Preserves good content while fixing problems
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize report refiner agent.

        Args:
            config: Agent configuration dictionary.
        """
        self._config = config

    def refine_report(
        self,
        original_markdown: str,
        validation_result: ValidationResult,
        evaluation_result: ReportEvaluationResult,
        session: ResearchSession,
        analysis: AnalysisResult,
    ) -> str:
        """Refine a report based on validation and evaluation feedback.

        Args:
            original_markdown: Original report content.
            validation_result: Research validation results.
            evaluation_result: Report quality evaluation results.
            session: Research session with sources.
            analysis: Analysis results from analyzer.

        Returns:
            Refined markdown report.
        """
        # Start with original report
        refined = original_markdown

        # Collect all issues to address
        all_issues = list(validation_result.issues) + list(validation_result.warnings)
        all_issues.extend(evaluation_result.critical_issues)
        all_issues.extend(evaluation_result.warnings)

        # Log what we're addressing
        if all_issues:
            logger.info(f"Refining report to address {len(all_issues)} issues")
            for i, issue in enumerate(all_issues[:5], 1):
                logger.info(f"  {i}. {issue}")
            if len(all_issues) > 5:
                logger.info(f"  ... and {len(all_issues) - 5} more issues")

        # Apply fixes in priority order
        refined = self._fix_critical_issues(refined, validation_result, evaluation_result, session, analysis)
        refined = self._fix_warnings(refined, validation_result, evaluation_result, session, analysis)
        refined = self._improve_low_scores(refined, evaluation_result, session, analysis)

        return refined

    def _fix_critical_issues(
        self,
        markdown: str,
        validation_result: ValidationResult,
        evaluation_result: ReportEvaluationResult,
        session: ResearchSession,
        analysis: AnalysisResult,
    ) -> str:
        """Fix critical issues that make the report unusable.

        Args:
            markdown: Current report content.
            validation_result: Research validation results.
            evaluation_result: Report quality evaluation results.
            session: Research session.
            analysis: Analysis results.

        Returns:
            Markdown with critical issues fixed.
        """
        result = markdown

        # Fix missing sections from evaluation
        for issue in evaluation_result.critical_issues:
            if "Missing required section" in issue:
                result = self._ensure_section_exists(result, "## Executive Summary")
                result = self._ensure_section_exists(result, "## Key Findings")
                result = self._ensure_section_exists(result, "## Sources")
                result = self._ensure_section_exists(result, "## Safety")

        # Fix content depth issues from validation
        for issue in validation_result.issues:
            if "Limited content depth" in issue:
                result = self._expand_short_sections(result)

        # Fix missing citations from validation
        for issue in validation_result.issues:
            if "Findings lack source citations" in issue:
                result = self._add_citations_to_findings(result, analysis)

        return result

    def _fix_warnings(
        self,
        markdown: str,
        validation_result: ValidationResult,
        evaluation_result: ReportEvaluationResult,
        session: ResearchSession,
        analysis: AnalysisResult,
    ) -> str:
        """Fix warning-level issues to improve report quality.

        Args:
            markdown: Current report content.
            validation_result: Research validation results.
            evaluation_result: Report quality evaluation results.
            session: Research session.
            analysis: Analysis results.

        Returns:
            Markdown with warnings addressed.
        """
        result = markdown

        # Improve writing quality from evaluation warnings
        for issue in evaluation_result.warnings:
            if "short sentences" in issue.lower():
                result = self._improve_sentence_structure(result)
            elif "long sentences" in issue.lower():
                result = self._improve_sentence_structure(result)
            elif "very short paragraphs" in issue.lower():
                result = self._improve_paragraph_structure(result)
            elif "No nested headers" in issue:
                result = self._add_nested_headers(result)
            elif "No bulleted or numbered lists" in issue:
                result = self._add_lists(result)

        # Improve diversity issues from validation
        for issue in validation_result.warnings:
            if "limited domain diversity" in issue.lower():
                result = self._add_domain_diversity_note(result)
            elif "limited content depth" in issue.lower():
                result = self._expand_short_sections(result)

        return result

    def _improve_low_scores(
        self,
        markdown: str,
        evaluation_result: ReportEvaluationResult,
        session: ResearchSession,
        analysis: AnalysisResult,
    ) -> str:
        """Improve report sections with low quality scores.

        Args:
            markdown: Current report content.
            evaluation_result: Report quality evaluation results.
            session: Research session.
            analysis: Analysis results.

        Returns:
            Markdown with improvements to low-scoring sections.
        """
        result = markdown

        # Improve writing quality if low
        if evaluation_result.writing_quality_score < 0.6:
            result = self._enhance_writing_clarity(result)

        # Improve structure if low
        if evaluation_result.structure_flow_score < 0.6:
            result = self._enhance_organization(result)

        # Improve consistency if low
        if evaluation_result.consistency_score < 0.6:
            result = self._ensure_consistency(result, analysis)

        return result

    def _ensure_section_exists(self, markdown: str, section: str) -> str:
        """Ensure a section exists in the report.

        Args:
            markdown: Report content.
            section: Section header to check for.

        Returns:
            Markdown with section added if missing.
        """
        if section not in markdown:
            # Find where to insert (before Sources section usually)
            sources_match = re.search(r'## Sources', markdown)
            if sources_match:
                insert_pos = sources_match.start()
                return f"{markdown[:insert_pos]}\n\n{section}\n\n<!-- TODO: Add content here -->\n\n{markdown[insert_pos:]}"
            else:
                return f"{markdown}\n\n{section}\n\n<!-- TODO: Add content here -->\n"
        return markdown

    def _expand_short_sections(self, markdown: str) -> str:
        """Expand sections that are too short by adding placeholder suggestions.

        Args:
            markdown: Report content.

        Returns:
            Markdown with expanded sections.
        """
        # Find sections that are very short (< 100 chars)
        section_pattern = r'## ([^\n]+)\n([^\n]+?)(?=\n##|$)'
        sections = re.findall(section_pattern, markdown)

        result = markdown
        offset = 0

        for section in sections:
            header, section_name, content = section
            section_start = result.find(header, offset)
            section_end = section_start + len(header) + len(content) + len(header)

            if len(content.strip()) < 100 and len(content.strip()) > 10:
                # Add expansion suggestion
                expansion = "\n\n  **Note: This section could be expanded with more details and analysis.**\n"
                result = result[:section_end] + expansion + result[section_end:]
                offset = section_end + len(expansion)

        return result

    def _add_citations_to_findings(self, markdown: str, analysis: AnalysisResult) -> str:
        """Add source citations to findings that lack them.

        Args:
            markdown: Report content.
            analysis: Analysis results.

        Returns:
            Markdown with citations added.
        """
        # This is a placeholder - actual implementation would parse findings
        # and add appropriate source references based on the finding
        return markdown + "\n<!-- TODO: Review and add source citations to findings -->\n"

    def _improve_sentence_structure(self, markdown: str) -> str:
        """Improve sentence structure by connecting short fragments.

        Args:
            markdown: Report content.

        Returns:
            Markdown with improved sentence structure.
        """
        # Find very short sentences and connect them
        lines = markdown.split('\n')
        result = []

        for i, line in enumerate(lines):
            if len(line.strip()) > 10 and len(line.strip()) < 40:
                # This is a short sentence that could be connected
                if i > 0 and len(lines[i-1].strip()) < 100:
                    # Connect to previous line if it has space
                    result[-1] = lines[i-1].rstrip() + ' ' + line.strip()
                    continue
            result.append(line)

        return '\n'.join(result)

    def _improve_paragraph_structure(self, markdown: str) -> str:
        """Improve paragraph structure by combining short paragraphs.

        Args:
            markdown: Report content.

        Returns:
            Markdown with improved paragraph structure.
        """
        lines = markdown.split('\n')
        result = []
        current_paragraph = []
        min_paragraph_length = 100

        for line in lines:
            stripped = line.strip()
            if not stripped:
                if len('\n'.join(current_paragraph).strip()) < min_paragraph_length:
                    result.append('\n'.join(current_paragraph))
                current_paragraph = []
            elif stripped.startswith('#'):
                if current_paragraph:
                    result.append('\n'.join(current_paragraph))
                result.append(line)
                current_paragraph = []
            else:
                current_paragraph.append(line)

        if current_paragraph:
            result.append('\n'.join(current_paragraph))

        return '\n'.join(result)

    def _add_nested_headers(self, markdown: str) -> str:
        """Add nested headers for better organization.

        Args:
            markdown: Report content.

        Returns:
            Markdown with nested headers added.
        """
        # Find main sections and add subsections
        result = markdown

        # Add nested headers under Key Findings if missing
        if "###" not in markdown and "## Key Findings" in markdown:
            insert_pos = result.find("## Key Findings")
            if insert_pos >= 0:
                result = (
                    result[:insert_pos]
                    + "## Key Findings\n\n"
                    + "### Primary Findings\n\n"
                    + "### Secondary Findings\n\n"
                    + result[insert_pos + 18:]
                )

        return result

    def _add_lists(self, markdown: str) -> str:
        """Convert text paragraphs to bulleted lists where appropriate.

        Args:
            markdown: Report content.

        Returns:
            Markdown with lists added.
        """
        # This is a placeholder - would analyze content and convert
        # appropriate text to bullet points
        return markdown + "\n<!-- TODO: Consider converting key points to bulleted lists -->\n"

    def _add_domain_diversity_note(self, markdown: str) -> str:
        """Add note about domain diversity to sources section.

        Args:
            markdown: Report content.

        Returns:
            Markdown with domain diversity note.
        """
        if "## Sources" in markdown:
            sources_pos = markdown.find("## Sources")
            if sources_pos >= 0:
                note = "\n\n  **Note: This research may benefit from additional source diversity across different domains.**\n"
                return markdown[:sources_pos + 15] + note + markdown[sources_pos + 15:]

        return markdown

    def _enhance_writing_clarity(self, markdown: str) -> str:
        """Enhance writing clarity through minor improvements.

        Args:
            markdown: Report content.

        Returns:
            Markdown with enhanced clarity.
        """
        # Remove redundant phrases
        redundancies = [
            r'\bvery important\b',
            r'\bit is worth noting that\b',
            r'\bshould be noted that\b',
        ]
        result = markdown
        for pattern in redundancies:
            result = re.sub(pattern, '', result, flags=re.IGNORECASE)

        # Improve transitions
        result = re.sub(r'\.(\s[A-Z])', r'. \1', result)

        return result

    def _enhance_organization(self, markdown: str) -> str:
        """Enhance document organization and structure.

        Args:
            markdown: Report content.

        Returns:
            Markdown with enhanced organization.
        """
        result = markdown

        # Ensure consistent spacing after headers
        result = re.sub(r'(#+\s+[^\n]+)\n*', r'\1\n\n', result)

        return result

    def _ensure_consistency(self, markdown: str, analysis: AnalysisResult) -> str:
        """Ensure report is consistent with analysis findings.

        Args:
            markdown: Report content.
            analysis: Analysis results.

        Returns:
            Markdown with improved consistency.
        """
        result = markdown

        # Check if all key findings are mentioned
        for finding in analysis.key_findings[:5]:
            finding_text = str(finding).lower()[:100]
            if finding_text not in markdown.lower():
                # Add finding as a note
                if "## Key Findings" in result:
                    findings_pos = result.find("## Key Findings")
                    if findings_pos >= 0:
                        note = f"\n  - {str(finding)}"
                        result = result[:findings_pos + 17] + note + result[findings_pos + 17:]

        return result


__all__ = ["ReportRefinerAgent"]
