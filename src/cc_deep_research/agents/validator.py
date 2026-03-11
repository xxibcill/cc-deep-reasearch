"""Validator agent implementation."""
from typing import Any
from urllib.parse import urlparse

from cc_deep_research.models import (
    AnalysisResult,
    ClaimEvidence,
    ClaimFreshness,
    CrossReferenceClaim,
    EvidenceType,
    ResearchSession,
    SearchResultItem,
    ValidationResult,
)


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

    def is_protocol_document(self, source: SearchResultItem) -> bool:
        """Detect if source is a clinical trial protocol without findings.

        Args:
            source: Source to check.

        Returns:
            True if source is a protocol document, False otherwise.
        """
        if not source.url and not source.content:
            return False

        url_lower = source.url.lower()
        if "clinicaltrials.gov" in url_lower:
            return True

        if source.content:
            content_lower = source.content.lower()
            protocol_indicators = [
                "protocol title:",
                "protocol #",
                "protocol document:",
                "study protocol:",
                "methods:",
            ]
            return any(indicator in content_lower for indicator in protocol_indicators)

        return False

    def validate_research(
        self,
        session: ResearchSession,
        analysis: AnalysisResult | dict[str, Any],
        query: str | None = None,
        min_sources_override: int | None = None,
    ) -> ValidationResult:
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
        analysis_result = AnalysisResult.model_validate(analysis)
        target_query = query or session.query
        issues: list[str] = []
        warnings: list[str] = []
        recommendations: list[str] = []
        failure_modes: list[str] = []

        min_sources = min_sources_override or self._min_sources
        evidence_scores = self._score_evidence(
            query=target_query,
            session=session,
            analysis=analysis_result,
        )

        if session.total_sources < min_sources:
            failure_modes.append("insufficient_source_quantity")
            issues.append(f"Insufficient sources: {session.total_sources} < {min_sources}")

        diversity_check = self._check_source_diversity(session.sources)
        if not diversity_check["is_diverse"]:
            failure_modes.append("limited_domain_diversity")
            warnings.append(diversity_check["reason"])

        depth_check = self._check_content_depth(session.sources)
        if not depth_check["has_depth"]:
            failure_modes.append("limited_content_depth")
            warnings.append(depth_check["reason"])

        # Check for high proportion of protocol documents
        protocol_count = sum(1 for s in session.sources if self.is_protocol_document(s))
        if protocol_count > 0:
            protocol_ratio = protocol_count / max(len(session.sources), 1)
            max_protocol_ratio = self._config.get("max_protocol_ratio", 0.3)
            if protocol_ratio > max_protocol_ratio:
                warnings.append(
                    f"High proportion of protocol documents ({protocol_count}/{len(session.sources)} = {protocol_ratio:.0%}) - "
                    f"these lack research findings"
                )

        gaps = analysis_result.normalized_gaps()
        if gaps:
            warnings.append(f"Analysis identified {len(gaps)} gap(s)")

        citation_check = self._check_citations(session, analysis_result)
        if not citation_check["is_complete"]:
            failure_modes.append("missing_citation_links")
            issues.append(citation_check["reason"])

        failure_modes.extend(self._collect_evidence_failure_modes(evidence_scores))
        failure_modes = list(dict.fromkeys(failure_modes))
        issues.extend(self._issue_messages_for_failure_modes(failure_modes))
        warnings.extend(self._warning_messages_for_failure_modes(failure_modes))

        evidence_diagnosis = self._diagnose_failure_pattern(
            failure_modes=failure_modes,
            source_count=session.total_sources,
            min_sources=min_sources,
        )
        recommendations = self._build_recommendations(
            failure_modes=failure_modes,
            evidence_diagnosis=evidence_diagnosis,
            diversity_check=diversity_check,
            depth_check=depth_check,
            has_gaps=bool(gaps),
        )

        quality_score = self._calculate_quality_score(
            source_count=session.total_sources,
            diversity_score=diversity_check["score"],
            content_depth_score=depth_check["score"],
            evidence_scores=evidence_scores,
            issue_count=len(issues),
            warning_count=len(warnings),
        )

        is_valid = len(issues) == 0
        follow_up_queries = self._build_follow_up_queries(
            query=target_query,
            analysis=analysis_result,
            failure_modes=failure_modes,
            evidence_diagnosis=evidence_diagnosis,
        )
        needs_follow_up = bool(issues or warnings) and bool(follow_up_queries)

        return ValidationResult(
            is_valid=is_valid,
            issues=issues,
            warnings=warnings,
            recommendations=recommendations,
            failure_modes=failure_modes,
            evidence_diagnosis=evidence_diagnosis,
            quality_score=quality_score,
            diversity_score=diversity_check["score"],
            content_depth_score=depth_check["score"],
            freshness_fitness_score=evidence_scores["freshness_fitness"],
            primary_source_coverage_score=evidence_scores["primary_source_coverage"],
            claim_support_density_score=evidence_scores["claim_support_density"],
            contradiction_pressure_score=evidence_scores["contradiction_pressure"],
            source_type_diversity_score=evidence_scores["source_type_diversity"],
            follow_up_queries=follow_up_queries,
            needs_follow_up=needs_follow_up,
            target_source_count=max(min_sources, session.total_sources),
        )

    def _build_follow_up_queries(
        self,
        query: str,
        analysis: AnalysisResult,
        failure_modes: list[str],
        evidence_diagnosis: str,
    ) -> list[str]:
        """Build follow-up queries that can improve weak research runs."""
        follow_up_queries: list[str] = []

        for gap in analysis.normalized_gaps():
            follow_up_queries.extend(gap.suggested_queries)
            follow_up_queries.append(f"{query} {gap.gap_description}")

        if evidence_diagnosis in {"needs_more_sources", "needs_more_and_better_sources"}:
            follow_up_queries.extend(
                [
                    f"{query} expert analysis",
                    f"{query} additional sources",
                ]
            )

        if "weak_primary_source_coverage" in failure_modes:
            follow_up_queries.extend(
                [
                    f"{query} primary sources official filings",
                    f"{query} official guidance source documents",
                ]
            )

        if "stale_evidence_for_time_sensitive_query" in failure_modes:
            follow_up_queries.extend(
                [
                    f"{query} latest updates current developments",
                    f"{query} timeline recent statements",
                ]
            )

        if "thin_claim_support" in failure_modes:
            follow_up_queries.extend(
                [
                    f"{query} evidence report pdf",
                    f"{query} study whitepaper dataset",
                ]
            )

        if "high_contradiction_pressure" in failure_modes:
            follow_up_queries.extend(
                [
                    f"{query} conflicting evidence rebuttal",
                    f"{query} methodology criticism response",
                ]
            )

        if "narrow_source_type_diversity" in failure_modes or "limited_domain_diversity" in failure_modes:
            follow_up_queries.extend(
                [
                    f"{query} independent review",
                    f"{query} academic analysis",
                ]
            )

        if "limited_content_depth" in failure_modes:
            follow_up_queries.extend(
                [
                    f"{query} report pdf",
                    f"{query} study whitepaper",
                ]
            )

        if "missing_citation_links" in failure_modes:
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

    def _score_evidence(
        self,
        *,
        query: str,
        session: ResearchSession,
        analysis: AnalysisResult,
    ) -> dict[str, float]:
        """Score evidence quality dimensions from sources and claims."""
        claims = self._collect_claims(analysis)
        evidence = self._collect_evidence(session.sources, claims)
        time_sensitive = self._is_time_sensitive(query, session.sources)

        return {
            "freshness_fitness": self._score_freshness_fitness(evidence, time_sensitive),
            "primary_source_coverage": self._score_primary_source_coverage(evidence),
            "claim_support_density": self._score_claim_support_density(analysis, claims),
            "contradiction_pressure": self._score_contradiction_pressure(claims),
            "source_type_diversity": self._score_source_type_diversity(evidence),
        }

    def _collect_claims(self, analysis: AnalysisResult) -> list[CrossReferenceClaim]:
        """Return all structured claims present in the analysis."""
        claims: list[CrossReferenceClaim] = list(analysis.cross_reference_claims)
        for finding in analysis.key_findings:
            if hasattr(finding, "claims"):
                claims.extend(finding.claims)
        return claims

    def _collect_evidence(
        self,
        sources: list[SearchResultItem],
        claims: list[CrossReferenceClaim],
    ) -> list[ClaimEvidence]:
        """Collect normalized evidence entries from claims or raw sources."""
        evidence: list[ClaimEvidence] = []
        for claim in claims:
            evidence.extend(claim.supporting_sources)
            evidence.extend(claim.contradicting_sources)
        if evidence:
            return evidence
        return [ClaimEvidence.model_validate(source) for source in sources]

    def _is_time_sensitive(self, query: str, sources: list[SearchResultItem]) -> bool:
        """Infer whether freshness should be weighted heavily."""
        lowered = query.lower()
        freshness_tokens = ("latest", "recent", "current", "today", "new", "updates", "2025", "2026")
        if any(token in lowered for token in freshness_tokens):
            return True
        return any(
            entry.family == "current-updates" or "freshness" in entry.intent_tags
            for source in sources
            for entry in source.query_provenance
        )

    def _score_freshness_fitness(
        self,
        evidence: list[ClaimEvidence],
        time_sensitive: bool,
    ) -> float:
        """Score how well evidence freshness matches the query needs."""
        if not evidence:
            return 0.0
        weights = {
            ClaimFreshness.CURRENT: 1.0,
            ClaimFreshness.RECENT: 0.7 if time_sensitive else 0.95,
            ClaimFreshness.DATED: 0.1 if time_sensitive else 0.65,
            ClaimFreshness.UNKNOWN: 0.2 if time_sensitive else 0.5,
        }
        total = sum(weights[item.freshness] for item in evidence)
        return max(0.0, min(total / len(evidence), 1.0))

    @staticmethod
    def _score_primary_source_coverage(evidence: list[ClaimEvidence]) -> float:
        """Score coverage from primary, official, or research evidence."""
        if not evidence:
            return 0.0
        preferred = {
            EvidenceType.PRIMARY,
            EvidenceType.OFFICIAL,
            EvidenceType.RESEARCH,
        }
        primary_like = sum(1 for item in evidence if item.evidence_type in preferred)
        return primary_like / len(evidence)

    @staticmethod
    def _score_claim_support_density(
        analysis: AnalysisResult,
        claims: list[CrossReferenceClaim],
    ) -> float:
        """Score how densely findings are backed by supporting evidence."""
        if claims:
            average_support = sum(len(claim.supporting_sources) for claim in claims) / len(claims)
            return min(average_support / 3, 1.0)

        findings = [finding for finding in analysis.key_findings if hasattr(finding, "evidence")]
        if not findings:
            return 0.0
        cited_findings = sum(1 for finding in findings if finding.evidence or getattr(finding, "source", None))
        return cited_findings / len(findings)

    @staticmethod
    def _score_contradiction_pressure(claims: list[CrossReferenceClaim]) -> float:
        """Score how much the evidence base is weighed down by contradictions."""
        if not claims:
            return 1.0
        support_count = sum(len(claim.supporting_sources) for claim in claims)
        contradiction_count = sum(len(claim.contradicting_sources) for claim in claims)
        total = support_count + contradiction_count
        if total == 0:
            return 0.0
        return max(0.0, min(1.0 - (contradiction_count / total), 1.0))

    @staticmethod
    def _score_source_type_diversity(evidence: list[ClaimEvidence]) -> float:
        """Score diversity across evidence classes."""
        if not evidence:
            return 0.0
        evidence_types = {
            item.evidence_type for item in evidence if item.evidence_type != EvidenceType.UNKNOWN
        }
        return min(len(evidence_types) / 4, 1.0)

    def _collect_evidence_failure_modes(self, scores: dict[str, float]) -> list[str]:
        """Map weak evidence scores to named failure modes."""
        failure_modes: list[str] = []
        if scores["freshness_fitness"] < 0.45:
            failure_modes.append("stale_evidence_for_time_sensitive_query")
        if scores["primary_source_coverage"] < 0.35:
            failure_modes.append("weak_primary_source_coverage")
        if scores["claim_support_density"] < 0.45:
            failure_modes.append("thin_claim_support")
        if scores["contradiction_pressure"] < 0.5:
            failure_modes.append("high_contradiction_pressure")
        if scores["source_type_diversity"] < 0.4:
            failure_modes.append("narrow_source_type_diversity")
        return failure_modes

    def _issue_messages_for_failure_modes(self, failure_modes: list[str]) -> list[str]:
        """Return issue-level messages for severe failure modes."""
        issues: list[str] = []
        if "high_contradiction_pressure" in failure_modes:
            issues.append("Evidence contains substantial contradiction pressure across core claims")
        return issues

    def _warning_messages_for_failure_modes(self, failure_modes: list[str]) -> list[str]:
        """Return warning-level messages for non-blocking quality failures."""
        mapping = {
            "weak_primary_source_coverage": "Primary-source coverage is too weak for confident synthesis",
            "thin_claim_support": "Claims are supported by too few independent evidence points",
            "stale_evidence_for_time_sensitive_query": "Evidence freshness does not match the query's time sensitivity",
            "narrow_source_type_diversity": "Evidence is concentrated in too few source types",
        }
        return [message for mode, message in mapping.items() if mode in failure_modes]

    def _diagnose_failure_pattern(
        self,
        *,
        failure_modes: list[str],
        source_count: int,
        min_sources: int,
    ) -> str:
        """Classify whether follow-up should seek more sources, better sources, or both."""
        quantity_failure = "insufficient_source_quantity" in failure_modes or source_count < min_sources
        quality_failures = set(failure_modes) - {"insufficient_source_quantity"}
        if quantity_failure and quality_failures:
            return "needs_more_and_better_sources"
        if quantity_failure:
            return "needs_more_sources"
        if quality_failures:
            return "needs_better_sources"
        return "sufficient"

    def _build_recommendations(
        self,
        *,
        failure_modes: list[str],
        evidence_diagnosis: str,
        diversity_check: dict[str, Any],
        depth_check: dict[str, Any],
        has_gaps: bool,
    ) -> list[str]:
        """Build targeted recommendations for the detected failure pattern."""
        recommendations: list[str] = []
        if evidence_diagnosis == "needs_more_sources":
            recommendations.append("Add more independent sources before finalizing the synthesis")
        elif evidence_diagnosis == "needs_better_sources":
            recommendations.append("Replace weak evidence with stronger primary and directly supporting sources")
        elif evidence_diagnosis == "needs_more_and_better_sources":
            recommendations.append("Expand coverage and raise evidence quality before relying on the conclusions")

        recommendation_map = {
            "weak_primary_source_coverage": "Prioritize official documents, filings, studies, or transcripts over commentary",
            "thin_claim_support": "Find at least two independent supporting sources for each major claim",
            "high_contradiction_pressure": "Resolve the strongest contradictions before presenting a confident conclusion",
            "stale_evidence_for_time_sensitive_query": "Refresh the evidence base with recent reporting or current source documents",
            "narrow_source_type_diversity": "Balance the evidence mix across official, research, news, and secondary context",
            "missing_citation_links": "Attach explicit source links to each finding and claim summary",
        }
        for failure_mode in failure_modes:
            recommendation = recommendation_map.get(failure_mode)
            if recommendation:
                recommendations.append(recommendation)

        if not diversity_check["is_diverse"] and diversity_check["recommendation"]:
            recommendations.append(diversity_check["recommendation"])
        if not depth_check["has_depth"] and depth_check["recommendation"]:
            recommendations.append(depth_check["recommendation"])
        if has_gaps:
            recommendations.append("Address identified gaps with follow-up research")
        return list(dict.fromkeys(recommendations))

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

        domains = set()
        for source in sources:
            domain = urlparse(source.url).netloc
            if domain:
                domains.add(domain)

        domain_count = len(domains)
        total_sources = len(sources)
        diversity_ratio = domain_count / max(total_sources, 1)
        is_diverse = diversity_ratio >= 0.3 or domain_count >= 3
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

        sources_with_content = sum(1 for s in sources if s.content and len(s.content) > 200)

        content_ratio = sources_with_content / max(len(sources), 1)
        has_depth = content_ratio >= 0.5
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
        analysis: AnalysisResult | dict[str, Any],
    ) -> dict[str, Any]:
        """Check citation completeness and accuracy.

        Args:
            session: Research session.
            analysis: Analysis results.

        Returns:
            Dictionary with citation check results.
        """
        analysis_result = AnalysisResult.model_validate(analysis)
        has_sources = len(session.sources) > 0
        has_citations = any(analysis_result.finding_sources())

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
        source_count: int,
        diversity_score: float,
        content_depth_score: float,
        evidence_scores: dict[str, float],
        issue_count: int,
        warning_count: int,
    ) -> float:
        """Calculate overall quality score.

        Args:
            source_count: Total number of sources.
            diversity_score: Source diversity score (0-1).
            content_depth_score: Depth score (0-1).
            evidence_scores: Evidence-aware component scores.
            issue_count: Number of blocking issues.
            warning_count: Number of warnings.

        Returns:
            Quality score between 0.0 and 1.0.
        """
        source_score = min(source_count / 20, 1.0)
        evidence_score = sum(evidence_scores.values()) / max(len(evidence_scores), 1)
        issue_penalty = 0.2 * min(issue_count, 3)
        warning_penalty = 0.05 * min(warning_count, 6)
        total_score = (
            (source_score * 0.15)
            + (diversity_score * 0.15)
            + (content_depth_score * 0.1)
            + (evidence_score * 0.6)
        )
        total_score -= issue_penalty
        total_score -= warning_penalty
        return max(0.0, min(total_score, 1.0))


__all__ = ["ValidatorAgent"]
