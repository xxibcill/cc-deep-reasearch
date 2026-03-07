"""Tests for ValidatorAgent follow-up behavior."""

from cc_deep_research.agents.validator import ValidatorAgent
from cc_deep_research.models import (
    AnalysisResult,
    ResearchDepth,
    ResearchSession,
    SearchResultItem,
)


class TestValidatorAgent:
    """Tests for validation remediation signals."""

    def test_validate_research_builds_follow_up_queries(self) -> None:
        """Validator should produce follow-up queries for weak runs."""
        agent = ValidatorAgent({"min_sources": 3})
        session = ResearchSession(
            session_id="session-1",
            query="test topic",
            depth=ResearchDepth.STANDARD,
            sources=[
                SearchResultItem(
                    url="https://example.com/article",
                    title="Article",
                    snippet="Short snippet",
                    score=0.4,
                )
            ],
        )
        analysis = AnalysisResult(
            key_findings=[{"title": "Finding", "description": "Desc"}],
            gaps=[
                {
                    "gap_description": "missing regulatory context",
                    "suggested_queries": ["test topic regulation"],
                }
            ],
        )

        validation = agent.validate_research(
            session,
            analysis,
            query="test topic",
            min_sources_override=4,
        )

        assert validation.needs_follow_up is True
        assert "test topic regulation" in validation.follow_up_queries
        assert "test topic expert analysis" in validation.follow_up_queries

    def test_validate_research_flags_weak_primary_source_coverage(self) -> None:
        """Validator should distinguish weak source quality from source quantity."""
        agent = ValidatorAgent({"min_sources": 2})
        session = ResearchSession(
            session_id="session-2",
            query="ai chip demand",
            depth=ResearchDepth.STANDARD,
            sources=[
                SearchResultItem(
                    url="https://opinion.example.com/1",
                    title="Commentary 1",
                    snippet="Analyst opinion",
                    content="x" * 500,
                ),
                SearchResultItem(
                    url="https://blog.example.com/2",
                    title="Commentary 2",
                    snippet="Blog summary",
                    content="x" * 500,
                ),
                SearchResultItem(
                    url="https://news.example.com/3",
                    title="News roundup",
                    snippet="News summary",
                    content="x" * 500,
                ),
            ],
        )
        analysis = AnalysisResult(
            key_findings=[
                {
                    "title": "Demand is rising",
                    "description": "Derived from commentary",
                    "evidence": ["https://news.example.com/3"],
                }
            ],
            cross_reference_claims=[
                {
                    "claim": "Demand is rising",
                    "supporting_sources": session.sources[:2],
                    "contradicting_sources": [],
                    "consensus_level": 0.6,
                }
            ],
        )

        validation = agent.validate_research(session, analysis)

        assert validation.evidence_diagnosis == "needs_better_sources"
        assert "weak_primary_source_coverage" in validation.failure_modes
        assert any("official" in recommendation.lower() for recommendation in validation.recommendations)
        assert "ai chip demand primary sources official filings" in validation.follow_up_queries

    def test_validate_research_flags_contradiction_heavy_claims(self) -> None:
        """Validator should surface contradiction-heavy evidence as a failure mode."""
        agent = ValidatorAgent({"min_sources": 2})
        supporting_source = SearchResultItem(
            url="https://www.sec.gov/company-filing",
            title="Company Filing",
            snippet="Official statement",
            content="x" * 500,
            source_metadata={"published_date": "2026-02-25"},
        )
        contradicting_a = SearchResultItem(
            url="https://news.example.com/dispute-1",
            title="Dispute 1",
            snippet="Contradicting report",
            content="x" * 500,
        )
        contradicting_b = SearchResultItem(
            url="https://analysis.example.com/dispute-2",
            title="Dispute 2",
            snippet="Another contradicting report",
            content="x" * 500,
        )
        session = ResearchSession(
            session_id="session-3",
            query="latest merger approval status",
            depth=ResearchDepth.STANDARD,
            sources=[supporting_source, contradicting_a, contradicting_b],
        )
        analysis = AnalysisResult(
            key_findings=[
                {
                    "title": "Approval is likely",
                    "description": "Conflicting evidence exists",
                    "evidence": [supporting_source.url, contradicting_a.url],
                }
            ],
            cross_reference_claims=[
                {
                    "claim": "Approval is likely",
                    "supporting_sources": [supporting_source],
                    "contradicting_sources": [contradicting_a, contradicting_b],
                    "consensus_level": 0.3,
                }
            ],
        )

        validation = agent.validate_research(session, analysis)

        assert validation.is_valid is False
        assert "high_contradiction_pressure" in validation.failure_modes
        assert validation.contradiction_pressure_score < 0.5
        assert "latest merger approval status conflicting evidence rebuttal" in validation.follow_up_queries
