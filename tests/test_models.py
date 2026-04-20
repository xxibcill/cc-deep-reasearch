"""Tests for core data structures."""

from datetime import datetime, timedelta

import pytest

from cc_deep_research.models import (
    AnalysisResult,
    APIKey,
    ClaimEvidence,
    ClaimFreshness,
    CrossReferenceClaim,
    EvidenceType,
    LLMPlanModel,
    LLMProviderType,
    LLMRouteModel,
    LLMTransportType,
    QualityScore,
    QueryProfile,
    QueryProvenance,
    ResearchDepth,
    ResearchSession,
    SearchMode,
    SearchOptions,
    SearchResult,
    SearchResultItem,
    StrategyPlan,
    StrategyResult,
)
from cc_deep_research.research_runs import (
    ResearchOutputFormat,
    ResearchRunArtifact,
    ResearchRunReport,
    ResearchRunRequest,
    ResearchRunResult,
)


class TestSearchResultItem:
    """Tests for SearchResultItem model."""

    def test_create_search_result_item(self) -> None:
        """Test creating a basic search result item."""
        item = SearchResultItem(
            url="https://example.com",
            title="Example Title",
            snippet="Example snippet",
            score=0.9,
        )
        assert item.url == "https://example.com"
        assert item.title == "Example Title"
        assert item.snippet == "Example snippet"
        assert item.score == 0.9
        assert item.content is None
        assert item.source_metadata == {}

    def test_search_result_item_defaults(self) -> None:
        """Test default values for SearchResultItem."""
        item = SearchResultItem(url="https://example.com")
        assert item.title == ""
        assert item.snippet == ""
        assert item.score == 0.0
        assert item.content is None
        assert item.source_metadata == {}

    def test_search_result_item_with_content(self) -> None:
        """Test SearchResultItem with content."""
        item = SearchResultItem(
            url="https://example.com",
            content="Full content here",
        )
        assert item.content == "Full content here"

    def test_search_result_item_serialization(self) -> None:
        """Test SearchResultItem can be serialized to dict."""
        item = SearchResultItem(
            url="https://example.com",
            title="Test",
            snippet="Snippet",
        )
        data = item.model_dump()
        assert data["url"] == "https://example.com"
        assert data["title"] == "Test"

    def test_search_result_item_normalizes_query_provenance(self) -> None:
        """Test query provenance is synchronized into source metadata."""
        item = SearchResultItem(
            url="https://example.com",
            query_provenance=[
                QueryProvenance(
                    query="market structure official guidance",
                    family="primary-source",
                    intent_tags=["primary-source", "evidence"],
                )
            ],
        )

        assert item.source_metadata["query"] == "market structure official guidance"
        assert item.source_metadata["query_family"] == "primary-source"
        assert item.source_metadata["queries"] == ["market structure official guidance"]
        assert item.source_metadata["query_families"] == ["primary-source"]

    def test_search_result_item_loads_query_provenance_from_metadata(self) -> None:
        """Test legacy metadata provenance is normalized to typed entries."""
        item = SearchResultItem(
            url="https://example.com",
            source_metadata={
                "query_provenance": [
                    {
                        "query": "market structure",
                        "family": "baseline",
                        "intent_tags": ["baseline", "informational"],
                    },
                    {
                        "query": "market structure official guidance",
                        "family": "primary-source",
                        "intent_tags": ["primary-source", "evidence"],
                    },
                ]
            },
        )

        assert [entry.family for entry in item.query_provenance] == [
            "baseline",
            "primary-source",
        ]
        assert item.source_metadata["query_families"] == ["baseline", "primary-source"]

    def test_search_result_item_score_validation(self) -> None:
        """Test score must be between 0 and 1."""
        with pytest.raises(ValueError):
            SearchResultItem(url="https://example.com", score=1.5)
        with pytest.raises(ValueError):
            SearchResultItem(url="https://example.com", score=-0.1)


class TestSearchResult:
    """Tests for SearchResult model."""

    def test_create_search_result(self) -> None:
        """Test creating a basic search result."""
        items = [
            SearchResultItem(url="https://example.com/1", title="Result 1"),
            SearchResultItem(url="https://example.com/2", title="Result 2"),
        ]
        result = SearchResult(
            query="test query",
            results=items,
            provider="test_provider",
            execution_time_ms=150,
        )
        assert result.query == "test query"
        assert len(result.results) == 2
        assert result.provider == "test_provider"
        assert result.execution_time_ms == 150
        assert isinstance(result.timestamp, datetime)

    def test_search_result_defaults(self) -> None:
        """Test default values for SearchResult."""
        result = SearchResult(query="test", provider="test")
        assert result.results == []
        assert result.metadata == {}
        assert result.execution_time_ms == 0

    def test_search_result_with_metadata(self) -> None:
        """Test SearchResult with custom metadata."""
        result = SearchResult(
            query="test",
            provider="test",
            metadata={"page": 1, "total_pages": 5},
        )
        assert result.metadata["page"] == 1
        assert result.metadata["total_pages"] == 5


class TestAPIKey:
    """Tests for APIKey model."""

    def test_create_api_key(self) -> None:
        """Test creating an API key."""
        api_key = APIKey(key="test-key-123")
        assert api_key.key == "test-key-123"
        assert api_key.requests_used == 0
        assert api_key.requests_limit == 1000
        assert api_key.disabled is False
        assert api_key.last_used is None

    def test_api_key_is_available(self) -> None:
        """Test is_available property."""
        api_key = APIKey(key="test-key")
        assert api_key.is_available is True

        # Exhausted key
        api_key.requests_used = 1000
        assert api_key.is_available is False

        # Disabled key
        api_key.requests_used = 0
        api_key.disabled = True
        assert api_key.is_available is False

    def test_api_key_remaining_requests(self) -> None:
        """Test remaining_requests property."""
        api_key = APIKey(key="test-key", requests_limit=100)
        assert api_key.remaining_requests == 100

        api_key.requests_used = 25
        assert api_key.remaining_requests == 75

        api_key.requests_used = 100
        assert api_key.remaining_requests == 0

        api_key.requests_used = 150  # Over limit
        assert api_key.remaining_requests == 0


class TestResearchSession:
    """Tests for ResearchSession model."""

    def test_create_research_session(self) -> None:
        """Test creating a research session."""
        session = ResearchSession(
            session_id="test-session-123",
            query="test query",
        )
        assert session.session_id == "test-session-123"
        assert session.query == "test query"
        assert session.depth == ResearchDepth.DEEP
        assert isinstance(session.started_at, datetime)
        assert session.completed_at is None

    def test_research_session_execution_time(self) -> None:
        """Test execution_time_seconds property."""
        session = ResearchSession(
            session_id="test",
            query="test",
            started_at=datetime.utcnow() - timedelta(seconds=30),
            completed_at=datetime.utcnow(),
        )
        assert 29 < session.execution_time_seconds < 31

    def test_research_session_execution_time_not_completed(self) -> None:
        """Test execution_time_seconds when not completed."""
        session = ResearchSession(
            session_id="test",
            query="test",
        )
        assert session.execution_time_seconds == 0.0

    def test_research_session_total_sources(self) -> None:
        """Test total_sources property."""
        sources = [
            SearchResultItem(url="https://example.com/1"),
            SearchResultItem(url="https://example.com/2"),
            SearchResultItem(url="https://example.com/3"),
        ]
        session = ResearchSession(
            session_id="test",
            query="test",
            sources=sources,
        )
        assert session.total_sources == 3


class TestResearchRunRequest:
    """Tests for the shared research-run request contract."""

    def test_normalizes_provider_overrides(self) -> None:
        """Provider overrides should be normalized without CLI-specific names."""
        request = ResearchRunRequest(
            query="test query",
            search_providers=[" Tavily ", "claude", "TAVILY"],
        )

        assert request.search_providers == ["tavily", "claude"]

    def test_defaults_to_markdown_output(self) -> None:
        """Markdown should remain the default serialized report format."""
        request = ResearchRunRequest(query="test query")

        assert request.output_format == ResearchOutputFormat.MARKDOWN
        assert request.concurrent_source_collection is None
        assert request.cross_reference_enabled is None

    def test_normalizes_prompt_overrides(self) -> None:
        """Whitespace-only prompt values should be dropped and empty agents removed."""
        request = ResearchRunRequest(
            query="test query",
            agent_prompt_overrides={
                "analyzer": {
                    "prompt_prefix": "  Focus on earnings quality.  ",
                    "system_prompt": "   ",
                },
                "deep_analyzer": {
                    "prompt_prefix": "\n\t",
                    "system_prompt": "   ",
                },
            },
        )

        assert request.agent_prompt_overrides == {
            "analyzer": {
                "prompt_prefix": "Focus on earnings quality.",
                "system_prompt": None,
            }
        }

    def test_rejects_unknown_prompt_override_agents(self) -> None:
        """Unsupported prompt override agent ids should fail validation."""
        with pytest.raises(ValueError, match="Unknown agent_prompt_overrides keys"):
            ResearchRunRequest(
                query="test query",
                agent_prompt_overrides={
                    "validator": {
                        "prompt_prefix": "Do more.",
                    }
                },
            )


class TestResearchRunResult:
    """Tests for the shared research-run result contract."""

    def test_exposes_session_identity_and_report_metadata(self) -> None:
        """Completed run results should keep session identity and report metadata together."""
        session = ResearchSession(
            session_id="shared-run-session",
            query="test query",
        )

        result = ResearchRunResult(
            session=session,
            report=ResearchRunReport(
                format=ResearchOutputFormat.HTML,
                content="<html></html>",
                media_type="text/html",
            ),
            artifacts=[
                ResearchRunArtifact(
                    kind="session",
                    path="session.json",
                    format="json",
                    media_type="application/json",
                )
            ],
        )

        assert result.session_id == "shared-run-session"
        assert result.report.format == ResearchOutputFormat.HTML
        assert result.artifacts[0].format == "json"

    def test_research_session_normalizes_metadata_contract(self) -> None:
        """Test that session metadata always exposes the stable top-level contract."""
        session = ResearchSession(
            session_id="test-session-123",
            query="test query",
            depth=ResearchDepth.QUICK,
        )

        assert set(session.metadata) == {
            "strategy",
            "analysis",
            "validation",
            "iteration_history",
            "providers",
            "execution",
            "deep_analysis",
            "llm_routes",
            "prompts",
        }
        assert session.metadata["providers"]["status"] == "unavailable"
        assert session.metadata["deep_analysis"]["status"] == "not_requested"
        assert session.metadata["llm_routes"] == {}

    def test_research_session_preserves_legacy_metadata_and_normalizes_deep_state(self) -> None:
        """Test normalization of legacy metadata formats."""
        session = ResearchSession(
            session_id="test-session-123",
            query="test query",
            depth=ResearchDepth.DEEP,
            metadata={
                "analysis": {
                    "analysis_method": "shallow_keyword",
                    "deep_analysis_complete": True,
                },
                "providers": ["tavily"],
            },
        )

        assert session.metadata["providers"]["configured"] == ["tavily"]
        assert session.metadata["providers"]["status"] == "unavailable"
        assert session.metadata["deep_analysis"]["requested"] is True
        assert session.metadata["deep_analysis"]["status"] == "degraded"
        assert session.metadata["execution"]["degraded"] is True

    def test_research_session_preserves_llm_route_metadata(self) -> None:
        """LLM route metadata should survive session normalization."""
        session = ResearchSession(
            session_id="test-session-123",
            query="test query",
            depth=ResearchDepth.STANDARD,
            metadata={
                "llm_routes": {
                    "planned_routes": {
                        "analyzer": {
                            "transport": "openrouter_api",
                            "provider": "openrouter",
                            "model": "anthropic/claude-sonnet-4",
                        }
                    }
                }
            },
        )

        assert (
            session.metadata["llm_routes"]["planned_routes"]["analyzer"]["transport"]
            == "openrouter_api"
        )

    def test_domain_modules_preserve_root_compatibility(self) -> None:
        """Split model modules should preserve root imports for callers."""
        from cc_deep_research.models.analysis import AnalysisResult as AnalysisResultModel
        from cc_deep_research.models.search import (
            ResearchDepth as SearchResearchDepth,
        )
        from cc_deep_research.models.search import (
            SearchResultItem as SearchResultItemModel,
        )
        from cc_deep_research.models.session import (
            ResearchSession as SessionResearchSession,
        )
        from cc_deep_research.models.session import (
            normalize_session_metadata,
        )

        assert AnalysisResultModel is AnalysisResult
        assert SearchResearchDepth is ResearchDepth
        assert SearchResultItemModel is SearchResultItem
        assert SessionResearchSession is ResearchSession
        assert set(
            normalize_session_metadata({}, depth=ResearchDepth.STANDARD)
        ) == {
            "strategy",
            "analysis",
            "validation",
            "iteration_history",
            "providers",
            "execution",
            "deep_analysis",
            "llm_routes",
            "prompts",
        }


class TestSearchOptions:
    """Tests for SearchOptions model."""

    def test_default_search_options(self) -> None:
        """Test default SearchOptions values."""
        options = SearchOptions()
        assert options.max_results == 10
        assert options.include_raw_content is True  # Changed to enable content fetching by default
        assert options.search_depth == ResearchDepth.DEEP

    def test_custom_search_options(self) -> None:
        """Test custom SearchOptions values."""
        options = SearchOptions(
            max_results=50,
            include_raw_content=True,
            search_depth=ResearchDepth.QUICK,
        )
        assert options.max_results == 50
        assert options.include_raw_content is True
        assert options.search_depth == ResearchDepth.QUICK

    def test_max_results_validation(self) -> None:
        """Test max_results validation."""
        with pytest.raises(ValueError):
            SearchOptions(max_results=0)
        with pytest.raises(ValueError):
            SearchOptions(max_results=101)


class TestResearchDepth:
    """Tests for ResearchDepth enum."""

    def test_research_depth_values(self) -> None:
        """Test ResearchDepth enum values."""
        assert ResearchDepth.QUICK.value == "quick"
        assert ResearchDepth.STANDARD.value == "standard"
        assert ResearchDepth.DEEP.value == "deep"


class TestSearchMode:
    """Tests for SearchMode enum."""

    def test_search_mode_values(self) -> None:
        """Test SearchMode enum values."""
        assert SearchMode.HYBRID_PARALLEL.value == "hybrid_parallel"
        assert SearchMode.TAVILY_PRIMARY.value == "tavily_primary"
        assert SearchMode.CLAUDE_PRIMARY.value == "claude_primary"


class TestQualityScore:
    """Tests for QualityScore model."""

    def test_default_quality_score(self) -> None:
        """Test default QualityScore values."""
        score = QualityScore()
        assert score.credibility == 0.5
        assert score.relevance == 0.5
        assert score.freshness == 0.5
        assert score.diversity == 0.5
        assert score.overall == 0.5

    def test_quality_score_validation(self) -> None:
        """Test QualityScore validation."""
        with pytest.raises(ValueError):
            QualityScore(credibility=1.5)
        with pytest.raises(ValueError):
            QualityScore(relevance=-0.1)


class TestCrossReferenceClaim:
    """Tests for CrossReferenceClaim model."""

    def test_create_claim(self) -> None:
        """Test creating a cross-reference claim."""
        claim = CrossReferenceClaim(
            claim="Python is a programming language",
            supporting_sources=["https://python.org", "https://wikipedia.org"],
        )
        assert claim.claim == "Python is a programming language"
        assert len(claim.supporting_sources) == 2
        assert claim.contradicting_sources == []
        assert all(isinstance(source, ClaimEvidence) for source in claim.supporting_sources)
        assert claim.consensus_level == 0.0
        assert claim.confidence == "medium"

    def test_claim_with_contradictions(self) -> None:
        """Test claim with contradicting sources."""
        claim = CrossReferenceClaim(
            claim="The best programming language",
            supporting_sources=["https://a.com"],
            contradicting_sources=["https://b.com", "https://c.com"],
            consensus_level=0.33,
        )
        assert len(claim.contradicting_sources) == 2
        assert claim.consensus_level == 0.33
        assert claim.confidence == "low"

    def test_claim_evidence_preserves_source_provenance(self) -> None:
        """Test claim evidence keeps provenance and derives freshness metadata."""
        source = SearchResultItem(
            url="https://www.sec.gov/example-filing",
            title="Company Filing",
            snippet="Primary filing evidence",
            source_metadata={"published_date": "2026-02-20"},
            query_provenance=[
                QueryProvenance(
                    query="company filing revenue guidance",
                    family="primary-source",
                    intent_tags=["evidence", "primary-source"],
                )
            ],
        )

        claim = CrossReferenceClaim(
            claim="The company raised revenue guidance",
            supporting_sources=[source],
            contradicting_sources=["https://news.example.com/contrary-view"],
            consensus_level=0.8,
        )

        evidence = claim.supporting_sources[0]
        assert evidence.url == source.url
        assert evidence.query_provenance[0].family == "primary-source"
        assert evidence.freshness == ClaimFreshness.CURRENT
        assert evidence.evidence_type == EvidenceType.OFFICIAL
        assert claim.freshness == ClaimFreshness.CURRENT
        assert claim.evidence_type == EvidenceType.OFFICIAL
        assert claim.confidence == "low"

    def test_analysis_result_accepts_structured_claims_and_finding_links(self) -> None:
        """Test analysis result normalizes claims into typed models."""
        result = SearchResultItem(
            url="https://pubmed.gov/study-1",
            title="Clinical Trial",
            snippet="Randomized controlled trial evidence",
            source_metadata={"published_date": "2025-12-01"},
            query_provenance=[
                QueryProvenance(
                    query="clinical trial evidence",
                    family="primary-source",
                    intent_tags=["evidence"],
                )
            ],
        )

        analysis = {
            "key_findings": [
                {
                    "title": "Treatment improved outcomes",
                    "description": "Supported by a clinical trial",
                    "evidence": [result.url],
                    "claims": [
                        {
                            "claim": "Treatment improved outcomes",
                            "supporting_sources": [result],
                            "contradicting_sources": [],
                            "consensus_level": 0.7,
                        }
                    ],
                }
            ],
            "cross_reference_claims": [
                {
                    "claim": "Treatment improved outcomes",
                    "supporting_sources": [result],
                    "contradicting_sources": ["https://example.com/opinion"],
                    "consensus_level": 0.7,
                }
            ],
        }

        analysis_result = AnalysisResult.model_validate(analysis)

        assert len(analysis_result.cross_reference_claims) == 1
        assert analysis_result.cross_reference_claims[0].supporting_sources[0].query_provenance[0].query == (
            "clinical trial evidence"
        )
        assert analysis_result.cross_reference_claims[0].evidence_type == EvidenceType.RESEARCH
        assert analysis_result.key_findings[0].claims[0].claim == "Treatment improved outcomes"

    def test_analysis_result_normalizes_structured_cross_reference_points(self) -> None:
        """Structured Claude cross-reference payloads should coerce to strings."""
        analysis_result = AnalysisResult.model_validate(
            {
                "consensus_points": [
                    {
                        "claim": "Multiple vendors reported logical-qubit progress",
                        "strength": "moderate",
                        "supporting_sources": ["https://example.com/1"],
                    }
                ],
                "contention_points": [
                    {
                        "claim": "Commercial timelines remain disputed",
                        "perspectives": [
                            {"view": "Fault tolerance is near-term", "sources": ["https://example.com/2"]},
                            {"view": "Useful scale is still years away", "sources": ["https://example.com/3"]},
                        ],
                    }
                ],
                "disagreement_points": [
                    {
                        "perspectives": [
                            {"view": "Neutral-atom systems are advancing fastest"},
                            {"view": "Superconducting systems still lead in scale"},
                        ]
                    }
                ],
            }
        )

        assert analysis_result.consensus_points == [
            "Multiple vendors reported logical-qubit progress"
        ]
        assert analysis_result.contention_points == ["Commercial timelines remain disputed"]
        assert analysis_result.disagreement_points == [
            "Neutral-atom systems are advancing fastest vs. Superconducting systems still lead in scale"
        ]


class TestLLMTransportType:
    """Tests for LLMTransportType enum."""

    def test_transport_type_values(self) -> None:
        """Test LLMTransportType enum values."""
        assert LLMTransportType.ANTHROPIC_API.value == "anthropic_api"
        assert LLMTransportType.OPENROUTER_API.value == "openrouter_api"
        assert LLMTransportType.CEREBRAS_API.value == "cerebras_api"
        assert LLMTransportType.HEURISTIC.value == "heuristic"


class TestLLMProviderType:
    """Tests for LLMProviderType enum."""

    def test_provider_type_values(self) -> None:
        """Test LLMProviderType enum values."""
        assert LLMProviderType.ANTHROPIC.value == "anthropic"
        assert LLMProviderType.OPENROUTER.value == "openrouter"
        assert LLMProviderType.CEREBRAS.value == "cerebras"
        assert LLMProviderType.HEURISTIC.value == "heuristic"


class TestLLMRouteModel:
    """Tests for LLMRouteModel."""

    def test_default_route(self) -> None:
        """Test default LLMRouteModel values."""
        route = LLMRouteModel()
        assert route.transport == LLMTransportType.ANTHROPIC_API
        assert route.provider == LLMProviderType.ANTHROPIC
        assert route.model == "claude-sonnet-4-6"
        assert route.enabled is True

    def test_custom_route(self) -> None:
        """Test custom LLMRouteModel values."""
        route = LLMRouteModel(
            transport=LLMTransportType.OPENROUTER_API,
            provider=LLMProviderType.OPENROUTER,
            model="anthropic/claude-opus-4",
            enabled=False,
        )
        assert route.transport == LLMTransportType.OPENROUTER_API
        assert route.provider == LLMProviderType.OPENROUTER
        assert route.model == "anthropic/claude-opus-4"
        assert route.enabled is False

    def test_route_serialization(self) -> None:
        """Test LLMRouteModel serialization."""
        route = LLMRouteModel(
            transport=LLMTransportType.CEREBRAS_API,
            provider=LLMProviderType.CEREBRAS,
            model="llama-3.3-70b",
        )
        data = route.model_dump()
        assert data["transport"] == "cerebras_api"
        assert data["provider"] == "cerebras"
        assert data["model"] == "llama-3.3-70b"


class TestLLMPlanModel:
    """Tests for LLMPlanModel."""

    def test_default_plan(self) -> None:
        """Test default LLMPlanModel values."""
        plan = LLMPlanModel()
        assert plan.agent_routes == {}
        assert LLMTransportType.ANTHROPIC_API in plan.fallback_order
        assert isinstance(plan.default_route, LLMRouteModel)

    def test_get_route_for_agent_default(self) -> None:
        """Test get_route_for_agent returns default for unknown agent."""
        plan = LLMPlanModel()
        route = plan.get_route_for_agent("unknown_agent")
        assert route.transport == LLMTransportType.ANTHROPIC_API
        assert route.provider == LLMProviderType.ANTHROPIC

    def test_get_route_for_agent_assigned(self) -> None:
        """Test get_route_for_agent returns assigned route."""
        plan = LLMPlanModel(
            agent_routes={
                "analyzer": LLMRouteModel(
                    transport=LLMTransportType.OPENROUTER_API,
                    provider=LLMProviderType.OPENROUTER,
                    model="anthropic/claude-sonnet-4",
                )
            }
        )
        route = plan.get_route_for_agent("analyzer")
        assert route.transport == LLMTransportType.OPENROUTER_API
        assert route.provider == LLMProviderType.OPENROUTER

    def test_custom_fallback_order(self) -> None:
        """Test custom fallback order."""
        plan = LLMPlanModel(
            fallback_order=[
                LLMTransportType.CEREBRAS_API,
                LLMTransportType.OPENROUTER_API,
                LLMTransportType.HEURISTIC,
            ]
        )
        assert plan.fallback_order[0] == LLMTransportType.CEREBRAS_API
        assert LLMTransportType.ANTHROPIC_API not in plan.fallback_order

    def test_plan_serialization(self) -> None:
        """Test LLMPlanModel serialization."""
        plan = LLMPlanModel(
            agent_routes={
                "analyzer": LLMRouteModel(
                    transport=LLMTransportType.CEREBRAS_API,
                    provider=LLMProviderType.CEREBRAS,
                )
            }
        )
        data = plan.model_dump()
        assert "agent_routes" in data
        assert "analyzer" in data["agent_routes"]
        assert data["agent_routes"]["analyzer"]["transport"] == "cerebras_api"


class TestStrategyResultWithLLMPlan:
    """Tests for StrategyResult with LLM plan."""

    def test_strategy_result_without_llm_plan(self) -> None:
        """Test StrategyResult without LLM plan."""
        result = StrategyResult(
            query="test query",
            complexity="moderate",
            depth=ResearchDepth.DEEP,
            profile=QueryProfile(),
            strategy=StrategyPlan(),
        )
        assert result.llm_plan is None

    def test_strategy_result_with_llm_plan(self) -> None:
        """Test StrategyResult with LLM plan."""
        result = StrategyResult(
            query="test query",
            complexity="moderate",
            depth=ResearchDepth.DEEP,
            profile=QueryProfile(),
            strategy=StrategyPlan(),
            llm_plan=LLMPlanModel(
                agent_routes={
                    "analyzer": LLMRouteModel(
                        transport=LLMTransportType.OPENROUTER_API,
                        provider=LLMProviderType.OPENROUTER,
                    )
                }
            ),
        )
        assert result.llm_plan is not None
        assert result.llm_plan.get_route_for_agent("analyzer").transport == LLMTransportType.OPENROUTER_API

    def test_strategy_result_serialization_with_llm_plan(self) -> None:
        """Test StrategyResult serialization with LLM plan."""
        result = StrategyResult(
            query="test query",
            complexity="moderate",
            depth=ResearchDepth.DEEP,
            profile=QueryProfile(),
            strategy=StrategyPlan(),
            llm_plan=LLMPlanModel(),
        )
        data = result.model_dump()
        assert "llm_plan" in data
        assert "agent_routes" in data["llm_plan"]


class TestAnalysisResultContractTests:
    """Contract tests for AnalysisResult model validation and normalization."""

    def test_analysis_result_accepts_string_findings(self) -> None:
        """AnalysisResult should accept string items in key_findings for backward compatibility."""
        result = AnalysisResult(
            key_findings=["Finding 1", "Finding 2"],
            themes=["Theme 1"],
            source_count=2,
        )
        assert result.key_findings == ["Finding 1", "Finding 2"]

    def test_analysis_result_accepts_dict_findings(self) -> None:
        """AnalysisResult should accept dict items in key_findings."""
        result = AnalysisResult(
            key_findings=[
                {"title": "Finding 1", "description": "Description", "evidence": [], "confidence": "high"}
            ],
            themes=["Theme 1"],
            source_count=1,
        )
        assert len(result.key_findings) == 1

    def test_analysis_result_accepts_analysis_finding_objects(self) -> None:
        """AnalysisResult should accept AnalysisFinding objects."""
        from cc_deep_research.models.analysis import AnalysisFinding

        finding = AnalysisFinding(
            title="Test Finding",
            description="Test description",
            evidence=["https://example.com"],
            confidence="high",
        )
        result = AnalysisResult(
            key_findings=[finding],
            source_count=1,
        )
        assert isinstance(result.key_findings[0], AnalysisFinding)

    def test_analysis_result_stringify_claim_object_consensus(self) -> None:
        """AnalysisResult should coerce claim objects in consensus_points to strings."""
        result = AnalysisResult.model_validate(
            {
                "consensus_points": [
                    {
                        "claim": "Treatment is effective",
                        "supporting_sources": ["https://a.com"],
                        "strength": "strong",
                    }
                ],
                "contention_points": [],
                "disagreement_points": [],
            }
        )
        assert result.consensus_points == ["Treatment is effective"]

    def test_analysis_result_stringify_claim_with_perspectives(self) -> None:
        """AnalysisResult should stringify claim with perspectives field."""
        result = AnalysisResult.model_validate(
            {
                "consensus_points": [],
                "contention_points": [
                    {
                        "claim": "Dosage debate",
                        "perspectives": [
                            {"view": "Low dose works", "sources": ["https://a.com"]},
                            {"view": "High dose needed", "sources": ["https://b.com"]},
                        ],
                    }
                ],
                "disagreement_points": [],
            }
        )
        assert result.contention_points == ["Dosage debate"]

    def test_analysis_result_stringify_disagreement_with_views(self) -> None:
        """AnalysisResult should stringify disagreement_points with multiple perspectives."""
        result = AnalysisResult.model_validate(
            {
                "consensus_points": [],
                "contention_points": [],
                "disagreement_points": [
                    {
                        "perspectives": [
                            {"view": "Neutral-atom is best"},
                            {"view": "Superconducting leads"},
                        ]
                    }
                ],
            }
        )
        assert result.disagreement_points == ["Neutral-atom is best vs. Superconducting leads"]

    def test_analysis_result_handles_mixed_consensus_types(self) -> None:
        """AnalysisResult should handle mixed string and object types in consensus_points."""
        result = AnalysisResult.model_validate(
            {
                "consensus_points": [
                    "Simple string claim",
                    {"claim": "Object claim", "supporting_sources": ["https://a.com"]},
                    {"title": "Title claim"},
                ],
                "contention_points": [],
                "disagreement_points": [],
            }
        )
        assert "Simple string claim" in result.consensus_points
        assert "Object claim" in result.consensus_points
        assert "Title claim" in result.consensus_points

    def test_analysis_result_gaps_accepts_strings(self) -> None:
        """AnalysisResult gaps should accept string items."""
        result = AnalysisResult(
            gaps=["Gap 1", "Gap 2"],
        )
        assert result.gaps == ["Gap 1", "Gap 2"]

    def test_analysis_result_gaps_accepts_dicts(self) -> None:
        """AnalysisResult gaps should accept dict items."""
        result = AnalysisResult(
            gaps=[
                {"gap_description": "Missing data", "importance": "high"},
            ],
        )
        assert len(result.gaps) == 1

    def test_analysis_result_normalized_gaps_returns_objects(self) -> None:
        """normalized_gaps() should return AnalysisGap objects."""
        from cc_deep_research.models.analysis import AnalysisGap

        result = AnalysisResult(
            gaps=[
                "String gap",
                {"gap_description": "Dict gap", "importance": "high"},
            ]
        )
        normalized = result.normalized_gaps()
        assert len(normalized) == 2
        assert isinstance(normalized[0], AnalysisGap)
        assert normalized[0].gap_description == "String gap"
        assert isinstance(normalized[1], AnalysisGap)
        assert normalized[1].gap_description == "Dict gap"

    def test_analysis_result_finding_sources_extracts_urls(self) -> None:
        """finding_sources() should extract source URLs from findings."""
        result = AnalysisResult(
            key_findings=[
                {
                    "title": "Finding 1",
                    "source": "https://source1.com",
                    "evidence": ["https://source2.com", "https://source3.com"],
                },
                {
                    "title": "Finding 2",
                    "evidence": ["https://source4.com"],
                },
            ]
        )
        sources = result.finding_sources()
        assert "https://source1.com" in sources
        assert "https://source2.com" in sources
        assert "https://source3.com" in sources
        assert "https://source4.com" in sources

    def test_analysis_result_validates_consensus_points_type(self) -> None:
        """Consensus points should be coerced to list if not already."""
        result = AnalysisResult(consensus_points="single item")
        assert result.consensus_points == ["single item"]

    def test_analysis_result_handles_none_consensus_points(self) -> None:
        """None consensus_points should become empty list."""
        result = AnalysisResult(consensus_points=None)
        assert result.consensus_points == []

    def test_analysis_result_extra_fields_allowed(self) -> None:
        """AnalysisResult should allow extra fields due to extra='allow'."""
        result = AnalysisResult.model_validate(
            {
                "key_findings": [],
                "unknown_field": "should be allowed",
                "another_unknown": 123,
            }
        )
        assert result.model_dump().get("unknown_field") == "should be allowed"
