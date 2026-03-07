"""Tests and fixtures for search provider integrations."""

from typing import Any

import pytest

from cc_deep_research.models import SearchOptions, SearchResult, SearchResultItem
from cc_deep_research.providers import (
    AuthenticationError,
    NetworkError,
    RateLimitError,
    SearchProvider,
    SearchProviderError,
)


class MockSearchProvider(SearchProvider):
    """Mock implementation of SearchProvider for testing."""

    def __init__(
        self,
        name: str = "mock",
        should_fail: bool = False,
        fail_with: Exception | None = None,
    ) -> None:
        self._name = name
        self._should_fail = should_fail
        self._fail_with = fail_with
        self._is_available = True
        self.search_calls: list[tuple[str, SearchOptions | None]] = []

    async def search(self, query: str, options: SearchOptions | None = None) -> SearchResult:
        """Mock search implementation."""
        self.search_calls.append((query, options))

        if self._should_fail:
            if self._fail_with:
                raise self._fail_with
            raise SearchProviderError("Mock failure", self._name, query)

        max_results = options.max_results if options else 10
        items = [
            SearchResultItem(
                url=f"https://example.com/result/{i}",
                title=f"Result {i} for: {query}",
                snippet=f"Snippet {i}",
                score=max(0.0, 0.9 - (i * 0.1)),
            )
            for i in range(1, max_results + 1)
        ]

        return SearchResult(
            query=query,
            results=items,
            provider=self._name,
            execution_time_ms=100,
        )

    def get_provider_name(self) -> str:
        """Return mock provider name."""
        return self._name

    @property
    def is_available(self) -> bool:
        """Return mock availability."""
        return self._is_available

    def set_available(self, available: bool) -> None:
        """Set availability for testing."""
        self._is_available = available


def build_search_result_item(
    suffix: str,
    *,
    title: str | None = None,
    snippet: str | None = None,
    score: float = 0.9,
    content: str | None = None,
    source_metadata: dict[str, Any] | None = None,
) -> SearchResultItem:
    """Build a deterministic search result item for contract tests."""
    return SearchResultItem(
        url=f"https://example.com/{suffix}",
        title=title or f"Result for {suffix}",
        snippet=snippet or f"Snippet for {suffix}",
        score=score,
        content=content,
        source_metadata=source_metadata or {},
    )


class FixtureSearchProvider(SearchProvider):
    """Deterministic provider fixture for workflow contract tests."""

    def __init__(
        self,
        *,
        name: str = "fixture",
        results_by_query: dict[str, list[SearchResultItem]] | None = None,
        available: bool = True,
        fail_with: Exception | None = None,
    ) -> None:
        self._name = name
        self._results_by_query = results_by_query or {}
        self._is_available = available
        self._fail_with = fail_with
        self.search_calls: list[tuple[str, SearchOptions | None]] = []

    async def search(self, query: str, options: SearchOptions | None = None) -> SearchResult:
        """Return pre-seeded results or generate stable fallback items."""
        self.search_calls.append((query, options))

        if self._fail_with is not None:
            raise self._fail_with

        items = self._results_by_query.get(query)
        if items is None:
            max_results = options.max_results if options else 2
            slug = query.lower().replace(" ", "-")
            items = [
                build_search_result_item(
                    f"{slug}-{index}",
                    title=f"{query} result {index}",
                    score=max(0.1, 1.0 - (index * 0.1)),
                )
                for index in range(1, max_results + 1)
            ]

        return SearchResult(
            query=query,
            results=[item.model_copy(deep=True) for item in items],
            provider=self._name,
            execution_time_ms=25,
        )

    def get_provider_name(self) -> str:
        """Return provider name."""
        return self._name

    @property
    def is_available(self) -> bool:
        """Return whether the provider is available."""
        return self._is_available


class TestSearchProviderInterface:
    """Tests for SearchProvider abstract interface."""

    @pytest.mark.asyncio
    async def test_provider_can_be_implemented(self) -> None:
        """Test that SearchProvider can be subclassed."""
        provider = MockSearchProvider()
        assert provider.get_provider_name() == "mock"

    @pytest.mark.asyncio
    async def test_search_returns_search_result(self) -> None:
        """Test that search returns SearchResult."""
        provider = MockSearchProvider()
        result = await provider.search("test query")

        assert isinstance(result, SearchResult)
        assert result.query == "test query"
        assert result.provider == "mock"
        assert len(result.results) == 10

    @pytest.mark.asyncio
    async def test_search_with_options(self) -> None:
        """Test search with custom options."""
        provider = MockSearchProvider()
        options = SearchOptions(max_results=5)
        result = await provider.search("test", options)

        assert len(result.results) == 5

    @pytest.mark.asyncio
    async def test_provider_tracks_calls(self) -> None:
        """Test that provider tracks search calls."""
        provider = MockSearchProvider()
        await provider.search("query 1")
        await provider.search("query 2")

        assert len(provider.search_calls) == 2
        assert provider.search_calls[0][0] == "query 1"
        assert provider.search_calls[1][0] == "query 2"

    def test_is_available_property(self) -> None:
        """Test is_available property."""
        provider = MockSearchProvider()
        assert provider.is_available is True

        provider.set_available(False)
        assert provider.is_available is False


class TestSearchProviderErrors:
    """Tests for search provider exceptions."""

    def test_search_provider_error(self) -> None:
        """Test SearchProviderError basics."""
        error = SearchProviderError("Test error", "test_provider", "test_query")
        assert str(error) == "Test error"
        assert error.provider == "test_provider"
        assert error.query == "test_query"

    def test_rate_limit_error(self) -> None:
        """Test RateLimitError with retry_after."""
        error = RateLimitError(
            "Rate limit exceeded",
            "tavily",
            "test query",
            retry_after=60,
        )
        assert error.provider == "tavily"
        assert error.retry_after == 60

    def test_authentication_error(self) -> None:
        """Test AuthenticationError."""
        error = AuthenticationError(
            "Invalid API key",
            "tavily",
            "test query",
        )
        assert error.provider == "tavily"
        assert isinstance(error, SearchProviderError)

    def test_network_error(self) -> None:
        """Test NetworkError with original error."""
        original = ConnectionError("Connection refused")
        error = NetworkError(
            "Network failure",
            "tavily",
            "test query",
            original_error=original,
        )
        assert error.provider == "tavily"
        assert error.original_error is original

    @pytest.mark.asyncio
    async def test_provider_can_raise_rate_limit_error(self) -> None:
        """Test provider raising RateLimitError."""
        provider = MockSearchProvider(
            should_fail=True,
            fail_with=RateLimitError("Rate limited", "mock", "test"),
        )

        with pytest.raises(RateLimitError) as exc_info:
            await provider.search("test")

        assert exc_info.value.retry_after is None

    @pytest.mark.asyncio
    async def test_provider_can_raise_authentication_error(self) -> None:
        """Test provider raising AuthenticationError."""
        provider = MockSearchProvider(
            should_fail=True,
            fail_with=AuthenticationError("Invalid key", "mock"),
        )

        with pytest.raises(AuthenticationError):
            await provider.search("test")


class TestSearchProviderPolymorphism:
    """Tests for polymorphic usage of SearchProvider."""

    @pytest.mark.asyncio
    async def test_multiple_providers_can_be_used_together(self) -> None:
        """Test using multiple providers polymorphically."""
        providers = [
            MockSearchProvider(name="provider_a"),
            MockSearchProvider(name="provider_b"),
            MockSearchProvider(name="provider_c"),
        ]

        results = []
        for provider in providers:
            result = await provider.search("test")
            results.append(result)

        assert len(results) == 3
        assert results[0].provider == "provider_a"
        assert results[1].provider == "provider_b"
        assert results[2].provider == "provider_c"

    @pytest.mark.asyncio
    async def test_provider_interface_contract(self) -> None:
        """Test that all providers follow the same contract."""
        provider: SearchProvider = MockSearchProvider()

        # Test required methods exist
        assert hasattr(provider, "search")
        assert hasattr(provider, "get_provider_name")
        assert hasattr(provider, "is_available")

        # Test search is async
        import inspect

        assert inspect.iscoroutinefunction(provider.search)

        # Test get_provider_name returns string
        name = provider.get_provider_name()
        assert isinstance(name, str)
