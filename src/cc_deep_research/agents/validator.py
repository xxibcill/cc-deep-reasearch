"""Validator agent implementation.

The validator agent is responsible for:
- Validating research quality and completeness
- Checking for potential biases in sources
- Verifying citation accuracy
- Ensuring research meets quality standards
"""

from typing import Any

from cc_deep_research.models import ResearchSession, SearchResultItem


class ValidatorAgent:
    """Agent that validates research quality and completeness.

    This agent:
    - Validates source diversity and quality
    - Checks for potential bias or echo chambers
    - Verifies citation accuracy and completeness
    - Ensures research meets configured standards
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the validator agent.

        Args:
            config: Agent configuration dictionary.
        """
        self._config = config
        self._min_sources = config.get("min_sources", 5)
        self._require_diverse_domains = config.get("require_diverse_domains", True)

    def validate_research(
        self,
        session: ResearchSession,
        analysis: dict[str, Any],
        query: str | None = None,
        min_sources_override: int | None = None,
    ) -> dict[str, Any]:
        """Validate research session for quality and completeness.

        Args:
            session: Research session to validate.
            analysis: Analysis results from analyzer.

        Returns:
            Validation report containing:
            - is_valid: Overall validity status
            - issues: List of identified issues
            - warnings: List of warnings
            - quality_score: Overall quality score (0-1)
            - recommendations: List of improvement recommendations
        """
        issues = []
        warnings = []
        recommendations = []

        # Check source count
        min_sources = min_sources_override or self._min_sources

        if session.total_sources < min_sources:
            issues.append(f"Insufficient sources: {session.total_sources} < {min_sources}")
            recommendations.append("Increase minimum sources or expand query variations")

        # Check source diversity
        diversity_check = self._check_source_diversity(session.sources)
        if not diversity_check["is_diverse"]:
            warnings.append(diversity_check["reason"])
            recommendations.append(diversity_check["recommendation"])

        # Check for content depth
        depth_check = self._check_content_depth(session.sources)
        if not depth_check["has_depth"]:
            warnings.append(depth_check["reason"])
            recommendations.append(depth_check["recommendation"])

        # Check for gaps in analysis
        gaps = analysis.get("gaps", [])
        if gaps:
            warnings.append(f"Analysis identified {len(gaps)} gap(s)")
            recommendations.append("Address identified gaps with follow-up research")

        # Check citation completeness
        citation_check = self._check_citations(session, analysis)
        if not citation_check["is_complete"]:
            issues.append(citation_check["reason"])

        # Calculate quality score
        quality_score = self._calculate_quality_score(
            len(issues),
            len(warnings),
            session.total_sources,
            diversity_check["score"],
        )

        is_valid = len(issues) == 0
        follow_up_queries = self._build_follow_up_queries(
            query=query or session.query,
            analysis=analysis,
            source_count=session.total_sources,
            min_sources=min_sources,
            diversity_check=diversity_check,
            depth_check=depth_check,
            citation_check=citation_check,
        )
        needs_follow_up = bool(issues or warnings) and bool(follow_up_queries)

        return {
            "is_valid": is_valid,
            "issues": issues,
            "warnings": warnings,
            "recommendations": recommendations,
            "quality_score": quality_score,
            "diversity_score": diversity_check["score"],
            "content_depth_score": depth_check["score"],
            "follow_up_queries": follow_up_queries,
            "needs_follow_up": needs_follow_up,
            "target_source_count": max(min_sources, session.total_sources),
        }

    def _build_follow_up_queries(
        self,
        query: str,
        analysis: dict[str, Any],
        source_count: int,
        min_sources: int,
        diversity_check: dict[str, Any],
        depth_check: dict[str, Any],
        citation_check: dict[str, Any],
    ) -> list[str]:
        """Build follow-up queries that can improve weak research runs."""
        follow_up_queries: list[str] = []

        gaps = analysis.get("gaps", [])
        for gap in gaps:
            if isinstance(gap, dict):
                follow_up_queries.extend(gap.get("suggested_queries", []))
                description = gap.get("gap_description")
                if description:
                    follow_up_queries.append(f"{query} {description}")
            elif gap:
                follow_up_queries.append(f"{query} {gap}")

        if source_count < min_sources:
            follow_up_queries.extend(
                [
                    f"{query} expert analysis",
                    f"{query} primary sources",
                ]
            )

        if not diversity_check["is_diverse"]:
            follow_up_queries.extend(
                [
                    f"{query} independent review",
                    f"{query} academic analysis",
                ]
            )

        if not depth_check["has_depth"]:
            follow_up_queries.extend(
                [
                    f"{query} report pdf",
                    f"{query} study whitepaper",
                ]
            )

        if not citation_check["is_complete"]:
            follow_up_queries.append(f"{query} source evidence")

        deduplicated: list[str] = []
        seen = set()
        for candidate in follow_up_queries:
            cleaned = candidate.strip()
            normalized = cleaned.lower()
            if cleaned and normalized not in seen:
                seen.add(normalized)
                deduplicated.append(cleaned)
        return deduplicated[:8]

    def _check_source_diversity(
        self,
        sources: list[SearchResultItem],
    ) -> dict[str, Any]:
        """Check source diversity across domains.

        Args:
            sources: List of sources to check.

        Returns:
            Dictionary with diversity check results.
        """
        if not sources:
            return {
                "is_diverse": False,
                "reason": "No sources to analyze",
                "score": 0.0,
                "recommendation": "Collect more sources",
            }

        # Extract domains
        domains = set()
        for source in sources:
            try:
                domain = source.url.split("/")[2]  # Extract domain
                domains.add(domain)
            except (IndexError, AttributeError):
                continue

        # Calculate diversity score
        domain_count = len(domains)
        total_sources = len(sources)
        diversity_ratio = domain_count / max(total_sources, 1)

        # Diversity threshold: at least 30% unique domains
        is_diverse = diversity_ratio >= 0.3 or domain_count >= 3

        # Score based on ratio (capped at 1.0)
        score = min(diversity_ratio, 1.0)

        reason = ""
        recommendation = ""

        if not is_diverse:
            if domain_count == 1:
                reason = f"All sources from single domain: {list(domains)[0]}"
                recommendation = "Include sources from diverse domains"
            else:
                reason = f"Limited domain diversity: {domain_count} domain(s) for {total_sources} sources"
                recommendation = "Add sources from additional domains"

        return {
            "is_diverse": is_diverse,
            "reason": reason,
            "score": score,
            "domains": list(domains),
            "recommendation": recommendation,
        }

    def _check_content_depth(
        self,
        sources: list[SearchResultItem],
    ) -> dict[str, Any]:
        """Check if sources have sufficient content depth.

        Args:
            sources: List of sources to check.

        Returns:
            Dictionary with depth check results.
        """
        if not sources:
            return {
                "has_depth": False,
                "reason": "No sources to analyze",
                "score": 0.0,
                "recommendation": "Collect more sources",
            }

        # Count sources with meaningful content
        sources_with_content = sum(1 for s in sources if s.content and len(s.content) > 200)

        content_ratio = sources_with_content / max(len(sources), 1)

        # Depth threshold: at least 50% sources have content
        has_depth = content_ratio >= 0.5

        # Score based on ratio
        score = content_ratio

        reason = ""
        recommendation = ""

        if not has_depth:
            reason = f"Limited content depth: {sources_with_content}/{len(sources)} sources have meaningful content"
            recommendation = "Collect sources with more detailed content"

        return {
            "has_depth": has_depth,
            "reason": reason,
            "score": score,
            "sources_with_content": sources_with_content,
            "recommendation": recommendation,
        }

    def _check_citations(
        self,
        session: ResearchSession,
        analysis: dict[str, Any],
    ) -> dict[str, Any]:
        """Check citation completeness and accuracy.

        Args:
            session: Research session.
            analysis: Analysis results.

        Returns:
            Dictionary with citation check results.
        """
        # Check if sources are numbered correctly
        has_sources = len(session.sources) > 0

        # Check if analysis references sources
        findings = analysis.get("key_findings", [])
        has_citations = any(f.get("source") for f in findings)

        is_complete = has_sources and has_citations

        reason = ""
        if not is_complete:
            if not has_sources:
                reason = "No sources to cite"
            elif not has_citations:
                reason = "Findings lack source citations"

        return {
            "is_complete": is_complete,
            "reason": reason,
        }

    def _calculate_quality_score(
        self,
        issues: int,
        warnings: int,
        source_count: int,
        diversity_score: float,
    ) -> float:
        """Calculate overall quality score.

        Args:
            issues: Number of issues (blockers).
            warnings: Number of warnings.
            source_count: Total number of sources.
            diversity_score: Source diversity score (0-1).

        Returns:
            Quality score between 0.0 and 1.0.
        """
        # Base score from source count (diminishing returns)
        source_score = min(source_count / 20, 1.0)

        # Penalty for issues
        issue_penalty = 0.5 * min(issues, 2)

        # Penalty for warnings
        warning_penalty = 0.1 * min(warnings, 5)

        # Weighted components
        total_score = (
            (source_score * 0.4)
            + (diversity_score * 0.4)
            + (1.0 - issue_penalty) * 0.1
            + (1.0 - warning_penalty) * 0.1
        )

        # Ensure score is in valid range
        return max(0.0, min(total_score, 1.0))


__all__ = ["ValidatorAgent"]
