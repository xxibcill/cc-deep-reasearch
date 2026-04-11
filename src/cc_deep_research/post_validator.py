"""Post-generation validation for research reports.

This module provides validation functions that run after report generation
to catch quality issues before final output.
"""

import re
from typing import Any

from cc_deep_research.models import AnalysisResult, ResearchSession


class PostReportValidator:
    """Validates generated research reports before final output.

    This class provides:
    - Truncation pattern detection
    - Section completeness validation
    - Citation format checking
    - Safety section validation
    """

    def __init__(self, config: dict[str, Any]):
        """Initialize post-report validator.

        Args:
            config: Configuration dictionary.
        """
        self._config = config
        self._enable_validation = config.get("enable_post_validation", True)

    def validate_report(
        self,
        markdown: str,
        session: ResearchSession,
        analysis: AnalysisResult,
    ) -> dict[str, Any]:
        """Validate complete report for quality issues.

        Args:
            markdown: Generated markdown report.
            session: Research session with sources.
            analysis: Analysis results from analyzer.

        Returns:
            Validation result with issues and warnings.
        """
        issues: list[str] = []
        warnings: list[str] = []

        # Check 1: Truncation patterns
        truncation_issues = self._check_truncation(markdown)
        issues.extend(truncation_issues["issues"])
        warnings.extend(truncation_issues["warnings"])

        # Check 2: Section completeness
        section_issues = self._check_section_completeness(markdown)
        issues.extend(section_issues["issues"])

        # Check 3: Source citations
        citation_issues = self._check_citation_format(markdown, session)
        issues.extend(citation_issues["issues"])

        # Check 4: Safety section specifically
        safety_issues = self._check_safety_section(markdown)
        issues.extend(safety_issues["issues"])
        warnings.extend(safety_issues["warnings"])

        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
        }

    def _check_truncation(self, markdown: str) -> dict[str, list[str]]:
        """Check for AI truncation patterns.

        Args:
            markdown: Report content to check.

        Returns:
            Dictionary with issues list and warnings list.
        """
        warnings: list[str] = []

        # Pattern: Word ending with "..." (e.g., "vast m...", "ut f...")
        truncation_patterns = [
            (r'\b\w{1,3}\.\.\.\s*', "Potential truncated sentence ending"),
        ]

        for pattern, description in truncation_patterns:
            matches = re.findall(pattern, markdown)
            if matches:
                for match in matches:
                    warnings.append(f"{description}: '{match.strip()}'")

        return {"issues": [], "warnings": warnings}

    def _check_section_completeness(self, markdown: str) -> dict[str, list[str]]:
        """Check that all major sections have content.

        Args:
            markdown: Report content to check.

        Returns:
            Dictionary with issues list.
        """
        issues: list[str] = []

        required_sections = [
            "## Key Findings",
            "## Sources",
            "## Safety",
        ]

        for section in required_sections:
            if section not in markdown:
                issues.append(f"Missing required section: {section}")

        return {"issues": issues}

    def _check_citation_format(
        self,
        markdown: str,
        session: ResearchSession,
    ) -> dict[str, list[str]]:
        """Check that citations are properly formatted.

        Args:
            markdown: Report content to check.
            session: Research session with sources.

        Returns:
            Dictionary with issues list.
        """
        issues: list[str] = []

        # Extract citations: [1], [2], etc.
        citation_pattern = r'\[(\d+)\]'
        citations = re.findall(citation_pattern, markdown)
        max_citation = int(max(citations)) if citations else 0

        if max_citation > len(session.sources):
            issues.append(
                f"Citation reference {max_citation} exceeds available sources ({len(session.sources)})"
            )

        return {"issues": issues}

    def _check_safety_section(self, markdown: str) -> dict[str, list[str]]:
        """Specifically validate safety section.

        Args:
            markdown: Report content to check.

        Returns:
            Dictionary with issues and warnings.
        """
        issues: list[str] = []
        warnings: list[str] = []

        # Extract safety section
        safety_match = re.search(
            r'## Safety[^\n]*([^\n]+?)(?=##|$)',
            markdown,
            re.DOTALL | re.IGNORECASE,
        )

        if not safety_match:
            issues.append("Safety section not found")
            return {"issues": issues, "warnings": warnings}

        safety_content = safety_match.group(1)

        # Check for incomplete sentences in safety
        # Look for sentences starting with capital but not ending properly
        sentence_patterns = [
            r'\b[A-Z][a-z]{5,}\s+\b',  # Fragment at line start
            r'\b[A-Z][a-z]{1,3}\s*$',  # Fragment at line end
        ]

        for pattern in sentence_patterns:
            if re.search(pattern, safety_content):
                warnings.append("Safety section contains potential sentence fragments")

        return {"issues": issues, "warnings": warnings}
