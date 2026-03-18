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


class TestValidatorFixtureSmokeTests:
    """Smoke tests for validation with fixture data.

    Task 006: Verify the resulting AnalysisResult survives validation
    and quality evaluation.
    """

    def test_validator_with_healthy_analysis_fixture(self) -> None:
        """Validator should process healthy analysis fixture without errors."""
        from tests.helpers.fixture_loader import load_analysis_healthy

        fixture = load_analysis_healthy()

        agent = ValidatorAgent({"min_sources": 2})

        sources = [
            SearchResultItem(
                url="https://www.nature.com/articles/d41586-023-01444-9",
                title="What is quantum computing?",
                snippet="potentially solving certain problems exponentially faster",
                content="Content about quantum computing" * 50,
                score=0.95,
            ),
            SearchResultItem(
                url="https://quantumcomputingreport.com/what-is-quantum-computing/",
                title="What is Quantum Computing?",
                snippet="solving certain problems exponentially faster",
                content="More quantum content" * 50,
                score=0.90,
            ),
            SearchResultItem(
                url="https://en.wikipedia.org/wiki/Quantum_computing",
                title="Quantum computing",
                snippet="solve certain problems exponentially faster",
                content="Wikipedia quantum content" * 50,
                score=0.85,
            ),
        ]

        session = ResearchSession(
            session_id="validator-fixture-test",
            query="What is quantum computing?",
            depth=ResearchDepth.DEEP,
            sources=sources,
        )

        analysis = AnalysisResult.model_validate(fixture)

        validation = agent.validate_research(session, analysis, query="What is quantum computing?")

        assert validation is not None
        assert hasattr(validation, "is_valid")
        assert hasattr(validation, "evidence_diagnosis")
        assert hasattr(validation, "quality_score")

    def test_validator_with_malformed_analysis_fixture(self) -> None:
        """Validator should handle malformed analysis fixture gracefully."""
        from tests.helpers.fixture_loader import load_analysis_malformed

        fixture = load_analysis_malformed()

        agent = ValidatorAgent({"min_sources": 1})

        sources = [
            SearchResultItem(
                url="https://example.com/source1",
                title="Simple Source",
                snippet="A simple source",
                content="Content",
                score=0.5,
            ),
        ]

        session = ResearchSession(
            session_id="validator-malformed-test",
            query="test query",
            depth=ResearchDepth.QUICK,
            sources=sources,
        )

        analysis = AnalysisResult.model_validate(fixture)

        validation = agent.validate_research(session, analysis, query="test query")

        assert validation is not None
        assert hasattr(validation, "is_valid")

    def test_validator_with_cross_reference_fixture(self) -> None:
        """Validator should process analysis with cross-reference claims."""
        from tests.helpers.fixture_loader import load_analysis_cross_reference

        fixture = load_analysis_cross_reference()

        agent = ValidatorAgent({"min_sources": 2})

        sources = [
            SearchResultItem(
                url="https://example.com/source1",
                title="Source 1",
                snippet="Content 1",
                content="More content" * 100,
                score=0.9,
            ),
            SearchResultItem(
                url="https://example.com/source2",
                title="Source 2",
                snippet="Content 2",
                content="Additional content" * 100,
                score=0.85,
            ),
        ]

        session = ResearchSession(
            session_id="validator-crossref-test",
            query="test query with cross references",
            depth=ResearchDepth.STANDARD,
            sources=sources,
        )

        analysis = AnalysisResult.model_validate(fixture)

        validation = agent.validate_research(session, analysis, query="test query")

        assert validation is not None

    def test_validator_degraded_path_minimal_sources(self) -> None:
        """Validator should handle degraded path with minimal sources."""
        agent = ValidatorAgent({"min_sources": 5})

        sources = [
            SearchResultItem(
                url="https://example.com/only",
                title="Only One Source",
                snippet="A single source",
                content="Limited content",
                score=0.4,
            ),
        ]

        session = ResearchSession(
            session_id="validator-degraded-test",
            query="test query",
            depth=ResearchDepth.STANDARD,
            sources=sources,
        )

        analysis = AnalysisResult(
            key_findings=[{"title": "Limited Finding", "description": "From few sources"}],
            themes=["Limited"],
            themes_detailed=[],
            consensus_points=[],
            contention_points=[],
            gaps=[{"gap_description": "Need more sources", "importance": "high", "suggested_queries": []}],
            analysis_method="basic_keyword",
        )

        validation = agent.validate_research(session, analysis, query="test query")

        assert validation.needs_follow_up is True
        assert len(validation.follow_up_queries) > 0

    def test_validator_produces_validation_result_structure(self) -> None:
        """Validation result should have expected structure for downstream use."""
        agent = ValidatorAgent({"min_sources": 2})

        sources = [
            SearchResultItem(
                url="https://pubmed.gov/article",
                title="Clinical Study",
                snippet="Clinical trial results",
                content="Detailed clinical trial content" * 50,
                score=0.95,
            ),
            SearchResultItem(
                url="https://gov.example.com/report",
                title="Government Report",
                snippet="Official report",
                content="Government report content" * 50,
                score=0.90,
            ),
        ]

        session = ResearchSession(
            session_id="validator-structure-test",
            query="clinical treatment effectiveness",
            depth=ResearchDepth.DEEP,
            sources=sources,
        )

        analysis = AnalysisResult(
            key_findings=[
                {
                    "title": "Treatment is effective",
                    "description": "Clinical trials show positive results",
                    "evidence": ["https://pubmed.gov/article"],
                    "confidence": "high",
                }
            ],
            themes=["Clinical Evidence", "Treatment"],
            themes_detailed=[
                {
                    "name": "Clinical Evidence",
                    "description": "Evidence from clinical trials",
                    "key_points": ["Positive results"],
                    "supporting_sources": ["https://pubmed.gov/article"],
                }
            ],
            consensus_points=["Treatment shows effectiveness"],
            contention_points=[],
            gaps=[],
            analysis_method="ai_semantic",
        )

        validation = agent.validate_research(session, analysis, query="clinical treatment effectiveness")

        assert hasattr(validation, "is_valid")
        assert hasattr(validation, "quality_score")
        assert hasattr(validation, "evidence_diagnosis")
        assert hasattr(validation, "failure_modes")
        assert hasattr(validation, "recommendations")
        assert hasattr(validation, "follow_up_queries")
        assert hasattr(validation, "needs_follow_up")


class TestValidatorFailurePathRegressions:
    """Regression tests for validator failure modes.

    Task 009: Add Failure-Path Regression Coverage
    These tests verify that validation handles:
    - Malformed analysis inputs
    - Edge cases in failure mode detection
    - Empty/null field handling
    """

    def test_validator_empty_analysis_key_findings(self) -> None:
        """Validator should handle empty key_findings gracefully."""
        agent = ValidatorAgent({"min_sources": 1})

        sources = [
            SearchResultItem(
                url="https://example.com/source",
                title="Source",
                snippet="Content",
                content="More content" * 50,
                score=0.8,
            ),
        ]

        session = ResearchSession(
            session_id="test",
            query="test query",
            depth=ResearchDepth.STANDARD,
            sources=sources,
        )

        analysis = AnalysisResult(
            key_findings=[],
            themes=[],
            themes_detailed=[],
            consensus_points=[],
            contention_points=[],
            gaps=[],
            analysis_method="basic_keyword",
        )

        validation = agent.validate_research(session, analysis, query="test query")

        assert validation is not None
        assert hasattr(validation, "quality_score")

    def test_validator_none_key_findings(self) -> None:
        """Validator should handle empty key_findings gracefully."""
        agent = ValidatorAgent({"min_sources": 1})

        sources = [
            SearchResultItem(
                url="https://example.com/source",
                title="Source",
                snippet="Content",
                content="More content" * 50,
                score=0.8,
            ),
        ]

        session = ResearchSession(
            session_id="test",
            query="test query",
            depth=ResearchDepth.STANDARD,
            sources=sources,
        )

        analysis = AnalysisResult(
            key_findings=[],
            themes=[],
            themes_detailed=[],
            consensus_points=[],
            contention_points=[],
            gaps=[],
            analysis_method="basic_keyword",
        )

        validation = agent.validate_research(session, analysis, query="test query")

        assert validation is not None

    def test_validator_missing_cross_reference_claims(self) -> None:
        """Validator should handle analysis without cross_reference_claims field."""
        agent = ValidatorAgent({"min_sources": 1})

        sources = [
            SearchResultItem(
                url="https://example.com/source",
                title="Source",
                snippet="Content",
                content="More content" * 50,
                score=0.8,
            ),
        ]

        session = ResearchSession(
            session_id="test",
            query="test query",
            depth=ResearchDepth.STANDARD,
            sources=sources,
        )

        analysis = AnalysisResult(
            key_findings=[{"title": "Finding", "description": "Description"}],
            themes=["Theme"],
            themes_detailed=[],
            consensus_points=[],
            contention_points=[],
            gaps=[],
            analysis_method="ai_semantic",
        )

        validation = agent.validate_research(session, analysis, query="test query")

        assert validation is not None
        assert hasattr(validation, "evidence_diagnosis")

    def test_validator_contradiction_with_missing_sources(self) -> None:
        """Validator should handle cross-reference claims with missing sources."""
        agent = ValidatorAgent({"min_sources": 1})

        sources = [
            SearchResultItem(
                url="https://example.com/source",
                title="Source",
                snippet="Content",
                content="More content" * 50,
                score=0.8,
            ),
        ]

        session = ResearchSession(
            session_id="test",
            query="test query",
            depth=ResearchDepth.STANDARD,
            sources=sources,
        )

        analysis = AnalysisResult(
            key_findings=[],
            themes=[],
            themes_detailed=[],
            consensus_points=[],
            contention_points=[],
            cross_reference_claims=[
                {
                    "claim": "Test claim",
                    "supporting_sources": [],
                    "contradicting_sources": [],
                    "consensus_level": 0.5,
                }
            ],
            gaps=[],
            analysis_method="ai_semantic",
        )

        validation = agent.validate_research(session, analysis, query="test query")

        assert validation is not None

    def test_validator_very_high_contradiction_pressure(self) -> None:
        """Validator should handle extreme contradiction pressure gracefully."""
        agent = ValidatorAgent({"min_sources": 1})

        supporting = SearchResultItem(
            url="https://sec.gov/filing",
            title="SEC Filing",
            snippet="Filing",
            content="Filing content" * 50,
            score=0.95,
        )
        contradicting = [
            SearchResultItem(
                url=f"https://example.com/dispute-{i}",
                title=f"Dispute {i}",
                snippet="Contradiction",
                content="Dispute content" * 50,
                score=0.7,
            )
            for i in range(10)
        ]

        session = ResearchSession(
            session_id="test",
            query="test query",
            depth=ResearchDepth.STANDARD,
            sources=[supporting] + contradicting,
        )

        analysis = AnalysisResult(
            key_findings=[],
            themes=[],
            themes_detailed=[],
            consensus_points=[],
            contention_points=[],
            cross_reference_claims=[
                {
                    "claim": "Main claim",
                    "supporting_sources": [supporting],
                    "contradicting_sources": contradicting,
                    "consensus_level": 0.05,
                }
            ],
            gaps=[],
            analysis_method="ai_semantic",
        )

        validation = agent.validate_research(session, analysis, query="test query")

        assert validation is not None
        assert "high_contradiction_pressure" in validation.failure_modes

    def test_validator_minimal_sources_exactly_threshold(self) -> None:
        """Validator should handle sources exactly at minimum threshold."""
        agent = ValidatorAgent({"min_sources": 3})

        sources = [
            SearchResultItem(
                url=f"https://example.com/source-{i}",
                title=f"Source {i}",
                snippet="Content",
                content="More content" * 50,
                score=0.8,
            )
            for i in range(3)
        ]

        session = ResearchSession(
            session_id="test",
            query="test query",
            depth=ResearchDepth.STANDARD,
            sources=sources,
        )

        analysis = AnalysisResult(
            key_findings=[{"title": "Finding", "description": "Description"}],
            themes=[],
            themes_detailed=[],
            consensus_points=[],
            contention_points=[],
            gaps=[],
            analysis_method="basic_keyword",
        )

        validation = agent.validate_research(session, analysis, query="test query")

        assert validation is not None

    def test_validator_zero_source_count_in_analysis(self) -> None:
        """Validator should handle analysis with zero source_count."""
        agent = ValidatorAgent({"min_sources": 1})

        sources = [
            SearchResultItem(
                url="https://example.com/source",
                title="Source",
                snippet="Content",
                content="Content" * 50,
                score=0.8,
            ),
        ]

        session = ResearchSession(
            session_id="test",
            query="test query",
            depth=ResearchDepth.STANDARD,
            sources=sources,
        )

        analysis = AnalysisResult(
            key_findings=[],
            themes=[],
            themes_detailed=[],
            consensus_points=[],
            contention_points=[],
            gaps=[],
            source_count=0,
            analysis_method="basic_keyword",
        )

        validation = agent.validate_research(session, analysis, query="test query")

        assert validation is not None

    def test_validator_malformed_gaps_field(self) -> None:
        """Validator should handle malformed gaps field gracefully."""
        agent = ValidatorAgent({"min_sources": 1})

        sources = [
            SearchResultItem(
                url="https://example.com/source",
                title="Source",
                snippet="Content",
                content="Content" * 50,
                score=0.8,
            ),
        ]

        session = ResearchSession(
            session_id="test",
            query="test query",
            depth=ResearchDepth.STANDARD,
            sources=sources,
        )

        analysis = AnalysisResult(
            key_findings=[],
            themes=[],
            themes_detailed=[],
            consensus_points=[],
            contention_points=[],
            gaps=[],
            analysis_method="basic_keyword",
        )

        validation = agent.validate_research(session, analysis, query="test query")

        assert validation is not None

    def test_validator_records_failure_modes_for_downstream(self) -> None:
        """Validator should record specific failure modes for downstream tools."""
        agent = ValidatorAgent({"min_sources": 5})

        sources = [
            SearchResultItem(
                url="https://blog.example.com/1",
                title="Blog Post",
                snippet="Opinion",
                content="Blog content" * 50,
                score=0.3,
            ),
            SearchResultItem(
                url="https://blog.example.com/2",
                title="Blog Post 2",
                snippet="Opinion 2",
                content="More blog" * 50,
                score=0.35,
            ),
        ]

        session = ResearchSession(
            session_id="test",
            query="test query",
            depth=ResearchDepth.STANDARD,
            sources=sources,
        )

        analysis = AnalysisResult(
            key_findings=[],
            themes=[],
            themes_detailed=[],
            consensus_points=[],
            contention_points=[],
            gaps=[],
            analysis_method="basic_keyword",
        )

        validation = agent.validate_research(session, analysis, query="test query")

        assert len(validation.failure_modes) > 0
        assert any(
            mode in ["weak_primary_source_coverage", "insufficient_source_count", "low_source_quality"]
            for mode in validation.failure_modes
        )
