"""Tests for core data structures."""

from datetime import datetime, timedelta

import pytest

from cc_deep_research.models import (
    APIKey,
    CrossReferenceClaim,
    QualityScore,
    ResearchDepth,
    ResearchSession,
    SearchMode,
    SearchOptions,
    SearchResult,
    SearchResultItem,
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


class TestSearchOptions:
    """Tests for SearchOptions model."""

    def test_default_search_options(self) -> None:
        """Test default SearchOptions values."""
        options = SearchOptions()
        assert options.max_results == 10
        assert options.include_raw_content is False
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
        assert claim.consensus_level == 0.0

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
