"""Tests for TavilySearchProvider."""


import httpx
import pytest

from cc_deep_research.models import ResearchDepth, SearchOptions
from cc_deep_research.providers import (
    AuthenticationError,
    NetworkError,
    RateLimitError,
    SearchProviderError,
)
from cc_deep_research.providers.tavily import TavilySearchProvider
from tests.helpers.fixture_loader import (
    load_tavily_search_healthy,
    load_tavily_search_malformed,
)


class TestTavilySearchProvider:
    """Tests for TavilySearchProvider."""

    @pytest.fixture
    def provider(self) -> TavilySearchProvider:
        """Create a TavilySearchProvider instance."""
        return TavilySearchProvider(api_key="test-api-key")

    @pytest.fixture
    def mock_response(self) -> dict:
        """Create a mock Tavily API response."""
        return {
            "results": [
                {
                    "url": "https://example.com/1",
                    "title": "Result 1",
                    "content": "Content for result 1",
                    "score": 0.95,
                    "raw_content": "Full content here",
                },
                {
                    "url": "https://example.com/2",
                    "title": "Result 2",
                    "content": "Content for result 2",
                    "score": 0.85,
                },
            ],
            "response_id": "test-response-id",
            "images": ["https://example.com/image.jpg"],
        }

    def test_provider_name(self, provider: TavilySearchProvider) -> None:
        """Test provider name."""
        assert provider.get_provider_name() == "tavily"

    def test_provider_initialization(self) -> None:
        """Test provider initialization with custom values."""
        provider = TavilySearchProvider(
            api_key="custom-key",
            max_results=50,
            timeout=60.0,
            provider_name="tavily_basic",
            strategy="basic",
        )
        assert provider._api_key == "custom-key"
        assert provider._max_results == 50
        assert provider._timeout == 60.0
        assert provider.get_provider_name() == "tavily_basic"
        assert provider._strategy == "basic"

    def test_build_payload_uses_explicit_strategy(self, provider: TavilySearchProvider) -> None:
        """Explicit provider strategy should override depth-derived defaults."""
        provider._strategy = "basic"

        payload = provider._build_payload(
            "test query",
            SearchOptions(search_depth=ResearchDepth.DEEP),
        )

        assert payload["search_depth"] == "basic"

    @pytest.mark.asyncio
    async def test_search_returns_results(
        self,
        provider: TavilySearchProvider,
        mock_response: dict,
    ) -> None:
        """Test that search returns SearchResult."""
        mock_transport = httpx.MockTransport(
            lambda _: httpx.Response(200, json=mock_response)
        )

        provider._client = httpx.AsyncClient(transport=mock_transport)

        result = await provider.search("test query")

        assert result.query == "test query"
        assert result.provider == "tavily"
        assert len(result.results) == 2
        assert result.results[0].url == "https://example.com/1"
        assert result.results[0].title == "Result 1"
        assert result.results[0].score == 0.95

        await provider.close()

    @pytest.mark.asyncio
    async def test_search_with_options(
        self,
        provider: TavilySearchProvider,
        mock_response: dict,
    ) -> None:
        """Test search with custom options."""
        mock_transport = httpx.MockTransport(
            lambda _: httpx.Response(200, json=mock_response)
        )
        provider._client = httpx.AsyncClient(transport=mock_transport)

        options = SearchOptions(
            max_results=5,
            include_raw_content=True,
            search_depth=ResearchDepth.QUICK,
        )
        result = await provider.search("test", options)

        assert result.query == "test"
        assert result.provider == "tavily"

        await provider.close()

    @pytest.mark.asyncio
    async def test_search_includes_metadata(
        self,
        provider: TavilySearchProvider,
        mock_response: dict,
    ) -> None:
        """Test that search result includes metadata."""
        mock_transport = httpx.MockTransport(
            lambda _: httpx.Response(200, json=mock_response)
        )
        provider._client = httpx.AsyncClient(transport=mock_transport)

        result = await provider.search("test")

        assert "response_id" in result.metadata
        assert result.metadata["response_id"] == "test-response-id"
        assert "images" in result.metadata
        assert result.metadata["strategy"] == "advanced"

        await provider.close()

    @pytest.mark.asyncio
    async def test_search_handles_empty_results(
        self,
        provider: TavilySearchProvider,
    ) -> None:
        """Test handling of empty results."""
        mock_transport = httpx.MockTransport(
            lambda _: httpx.Response(200, json={"results": []})
        )
        provider._client = httpx.AsyncClient(transport=mock_transport)

        result = await provider.search("test")

        assert len(result.results) == 0

        await provider.close()

    @pytest.mark.asyncio
    async def test_authentication_error(self, provider: TavilySearchProvider) -> None:
        """Test handling of authentication error (401)."""
        mock_transport = httpx.MockTransport(
            lambda _: httpx.Response(
                401,
                json={"message": "Invalid API key"},
            )
        )
        provider._client = httpx.AsyncClient(transport=mock_transport)

        with pytest.raises(AuthenticationError) as exc_info:
            await provider.search("test")

        assert "Invalid API key" in str(exc_info.value)
        assert exc_info.value.provider == "tavily"

        await provider.close()

    @pytest.mark.asyncio
    async def test_rate_limit_error(self, provider: TavilySearchProvider) -> None:
        """Test handling of rate limit error (429)."""
        mock_transport = httpx.MockTransport(
            lambda _: httpx.Response(
                429,
                json={"message": "Rate limit exceeded"},
                headers={"Retry-After": "60"},
            )
        )
        provider._client = httpx.AsyncClient(transport=mock_transport)

        with pytest.raises(RateLimitError) as exc_info:
            await provider.search("test")

        assert exc_info.value.retry_after == 60
        assert exc_info.value.provider == "tavily"

        await provider.close()

    @pytest.mark.asyncio
    async def test_network_error_timeout(self, provider: TavilySearchProvider) -> None:
        """Test handling of network timeout."""
        # Create a mock that raises TimeoutException
        def raise_timeout(_: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("Connection timed out")

        mock_transport = httpx.MockTransport(raise_timeout)
        provider._client = httpx.AsyncClient(transport=mock_transport)

        with pytest.raises(NetworkError) as exc_info:
            await provider.search("test")

        assert "timed out" in str(exc_info.value).lower()
        assert exc_info.value.provider == "tavily"

        await provider.close()

    @pytest.mark.asyncio
    async def test_network_error_connect(self, provider: TavilySearchProvider) -> None:
        """Test handling of connection error."""
        def raise_connect(_: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection failed")

        mock_transport = httpx.MockTransport(raise_connect)
        provider._client = httpx.AsyncClient(transport=mock_transport)

        with pytest.raises(NetworkError) as exc_info:
            await provider.search("test")

        assert "connect" in str(exc_info.value).lower()

        await provider.close()

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        """Test using provider as async context manager."""
        mock_response = {"results": []}
        mock_transport = httpx.MockTransport(
            lambda _: httpx.Response(200, json=mock_response)
        )

        async with TavilySearchProvider(api_key="test") as provider:
            provider._client = httpx.AsyncClient(transport=mock_transport)
            result = await provider.search("test")
            assert result.query == "test"

    @pytest.mark.asyncio
    async def test_raw_content_included(self, provider: TavilySearchProvider) -> None:
        """Test that raw_content is included in results when present."""
        mock_response = {
            "results": [
                {
                    "url": "https://example.com",
                    "title": "Test",
                    "content": "Snippet",
                    "raw_content": "Full article content here",
                    "score": 0.9,
                }
            ]
        }
        mock_transport = httpx.MockTransport(
            lambda _: httpx.Response(200, json=mock_response)
        )
        provider._client = httpx.AsyncClient(transport=mock_transport)

        result = await provider.search("test")

        assert result.results[0].content == "Full article content here"

        await provider.close()

    @pytest.mark.asyncio
    async def test_published_date_in_metadata(
        self,
        provider: TavilySearchProvider,
    ) -> None:
        """Test that published_date is extracted to source_metadata."""
        mock_response = {
            "results": [
                {
                    "url": "https://example.com",
                    "title": "Test",
                    "content": "Snippet",
                    "score": 0.9,
                    "published_date": "2024-01-15",
                }
            ]
        }
        mock_transport = httpx.MockTransport(
            lambda _: httpx.Response(200, json=mock_response)
        )
        provider._client = httpx.AsyncClient(transport=mock_transport)

        result = await provider.search("test")

        assert result.results[0].source_metadata.get("published_date") == "2024-01-15"

        await provider.close()

    @pytest.mark.asyncio
    async def test_execution_time_tracked(
        self,
        provider: TavilySearchProvider,
        mock_response: dict,
    ) -> None:
        """Test that execution time is tracked."""
        mock_transport = httpx.MockTransport(
            lambda _: httpx.Response(200, json=mock_response)
        )
        provider._client = httpx.AsyncClient(transport=mock_transport)

        result = await provider.search("test")

        assert result.execution_time_ms >= 0

        await provider.close()


class TestTavilySearchProviderReplayTests:
    """Replay tests using fixture-backed responses."""

    @pytest.fixture
    def provider(self) -> TavilySearchProvider:
        """Create a TavilySearchProvider instance."""
        return TavilySearchProvider(api_key="test-api-key")

    @pytest.mark.asyncio
    async def test_replay_healthy_fixture_full_result_parsing(
        self,
        provider: TavilySearchProvider,
    ) -> None:
        """Replay healthy fixture - verify full result parsing with all metadata."""
        fixture = load_tavily_search_healthy()

        mock_transport = httpx.MockTransport(
            lambda _: httpx.Response(200, json=fixture)
        )
        provider._client = httpx.AsyncClient(transport=mock_transport)

        result = await provider.search("quantum computing")

        assert result.query == "quantum computing"
        assert result.provider == "tavily"
        assert len(result.results) == 5

        first = result.results[0]
        assert first.url == "https://www.nature.com/articles/d41586-023-01444-9"
        assert first.title == "What is quantum computing? - Nature"
        assert first.score == 0.95
        assert first.content is not None
        assert "quantum" in first.content.lower()
        assert first.source_metadata.get("published_date") == "2023-05-15"

        assert result.metadata["response_id"] == "test-response-001"
        assert result.metadata["images"] == ["https://example.com/quantum-diagram.jpg"]

        await provider.close()

    @pytest.mark.asyncio
    async def test_replay_healthy_fixture_raw_content_extraction(
        self,
        provider: TavilySearchProvider,
    ) -> None:
        """Replay healthy fixture - verify raw_content extraction."""
        fixture = load_tavily_search_healthy()

        mock_transport = httpx.MockTransport(
            lambda _: httpx.Response(200, json=fixture)
        )
        provider._client = httpx.AsyncClient(transport=mock_transport)

        result = await provider.search("quantum computing")

        results_with_raw_content = [r for r in result.results if r.content is not None]
        assert len(results_with_raw_content) >= 2

        first_with_content = results_with_raw_content[0]
        assert first_with_content.content is not None
        assert len(first_with_content.content) > 100

        await provider.close()

    @pytest.mark.asyncio
    async def test_replay_healthy_fixture_scores_preserved(
        self,
        provider: TavilySearchProvider,
    ) -> None:
        """Replay healthy fixture - verify score normalization."""
        fixture = load_tavily_search_healthy()

        mock_transport = httpx.MockTransport(
            lambda _: httpx.Response(200, json=fixture)
        )
        provider._client = httpx.AsyncClient(transport=mock_transport)

        result = await provider.search("quantum computing")

        scores = [r.score for r in result.results]
        assert scores == [0.95, 0.92, 0.89, 0.85, 0.82]
        assert scores == sorted(scores, reverse=True)

        await provider.close()

    @pytest.mark.asyncio
    async def test_replay_malformed_fixture_partial_metadata(
        self,
        provider: TavilySearchProvider,
    ) -> None:
        """Replay malformed fixture - verify graceful handling of partial metadata."""
        fixture = load_tavily_search_malformed()

        mock_transport = httpx.MockTransport(
            lambda _: httpx.Response(200, json=fixture)
        )
        provider._client = httpx.AsyncClient(transport=mock_transport)

        result = await provider.search("test query")

        assert len(result.results) == 3

        first = result.results[0]
        assert first.url == "https://example.com/incomplete-result"
        assert first.title == "Incomplete Result Without Score"
        assert first.score == 0.0

        second = result.results[1]
        assert second.url == "https://example.com/missing-content"
        assert second.snippet == ""

        third = result.results[2]
        assert third.score == 0.0

        await provider.close()

    @pytest.mark.asyncio
    async def test_replay_malformed_fixture_null_fields(
        self,
        provider: TavilySearchProvider,
    ) -> None:
        """Replay malformed fixture - verify null field handling."""
        fixture = load_tavily_search_malformed()

        mock_transport = httpx.MockTransport(
            lambda _: httpx.Response(200, json=fixture)
        )
        provider._client = httpx.AsyncClient(transport=mock_transport)

        result = await provider.search("test")

        third = result.results[2]
        assert third.score == 0.0
        assert third.content is None or third.snippet is not None

        await provider.close()

    @pytest.mark.asyncio
    async def test_replay_empty_results_fixture(
        self,
        provider: TavilySearchProvider,
    ) -> None:
        """Replay empty results - verify graceful handling."""
        empty_fixture = {"results": [], "response_id": "empty-response"}

        mock_transport = httpx.MockTransport(
            lambda _: httpx.Response(200, json=empty_fixture)
        )
        provider._client = httpx.AsyncClient(transport=mock_transport)

        result = await provider.search("no results query")

        assert len(result.results) == 0
        assert result.metadata["response_id"] == "empty-response"

        await provider.close()

    @pytest.mark.asyncio
    async def test_replay_degraded_results_only_required_fields(
        self,
        provider: TavilySearchProvider,
    ) -> None:
        """Replay degraded fixture - verify only URL and title are required."""
        degraded_fixture = {
            "results": [
                {"url": "https://example.com/minimal", "title": "Minimal Result"}
            ]
        }

        mock_transport = httpx.MockTransport(
            lambda _: httpx.Response(200, json=degraded_fixture)
        )
        provider._client = httpx.AsyncClient(transport=mock_transport)

        result = await provider.search("test")

        assert len(result.results) == 1
        assert result.results[0].url == "https://example.com/minimal"
        assert result.results[0].title == "Minimal Result"
        assert result.results[0].snippet == ""
        assert result.results[0].score == 0.0

        await provider.close()


class TestTavilySearchProviderErrorPayloadReplay:
    """Replay tests for provider-side error payloads."""

    @pytest.fixture
    def provider(self) -> TavilySearchProvider:
        """Create a TavilySearchProvider instance."""
        return TavilySearchProvider(api_key="test-api-key")

    @pytest.mark.asyncio
    async def test_error_401_invalid_api_key(self, provider: TavilySearchProvider) -> None:
        """Replay 401 error - verify AuthenticationError."""
        mock_transport = httpx.MockTransport(
            lambda _: httpx.Response(
                401,
                json={"message": "Invalid API key provided"},
            )
        )
        provider._client = httpx.AsyncClient(transport=mock_transport)

        with pytest.raises(AuthenticationError) as exc_info:
            await provider.search("test")

        assert "Invalid API key provided" in str(exc_info.value)
        assert exc_info.value.provider == "tavily"

        await provider.close()

    @pytest.mark.asyncio
    async def test_error_429_rate_limit(self, provider: TavilySearchProvider) -> None:
        """Replay 429 error - verify RateLimitError with retry-after."""
        mock_transport = httpx.MockTransport(
            lambda _: httpx.Response(
                429,
                json={"message": "Too many requests"},
                headers={"Retry-After": "30"},
            )
        )
        provider._client = httpx.AsyncClient(transport=mock_transport)

        with pytest.raises(RateLimitError) as exc_info:
            await provider.search("test")

        assert exc_info.value.retry_after == 30
        assert exc_info.value.provider == "tavily"

        await provider.close()

    @pytest.mark.asyncio
    async def test_error_429_rate_limit_no_retry_after(
        self,
        provider: TavilySearchProvider,
    ) -> None:
        """Replay 429 error without Retry-After header."""
        mock_transport = httpx.MockTransport(
            lambda _: httpx.Response(
                429,
                json={"message": "Rate limited"},
            )
        )
        provider._client = httpx.AsyncClient(transport=mock_transport)

        with pytest.raises(RateLimitError) as exc_info:
            await provider.search("test")

        assert exc_info.value.retry_after is None

        await provider.close()

    @pytest.mark.asyncio
    async def test_error_500_internal_server(
        self,
        provider: TavilySearchProvider,
    ) -> None:
        """Replay 500 error - verify SearchProviderError."""
        mock_transport = httpx.MockTransport(
            lambda _: httpx.Response(
                500,
                json={"message": "Internal server error"},
            )
        )
        provider._client = httpx.AsyncClient(transport=mock_transport)

        with pytest.raises(SearchProviderError) as exc_info:
            await provider.search("test")

        assert "500" in str(exc_info.value)
        assert exc_info.value.provider == "tavily"

        await provider.close()

    @pytest.mark.asyncio
    async def test_error_503_service_unavailable(
        self,
        provider: TavilySearchProvider,
    ) -> None:
        """Replay 503 error - verify SearchProviderError."""
        mock_transport = httpx.MockTransport(
            lambda _: httpx.Response(
                503,
                json={"message": "Service temporarily unavailable"},
            )
        )
        provider._client = httpx.AsyncClient(transport=mock_transport)

        with pytest.raises(SearchProviderError) as exc_info:
            await provider.search("test")

        assert "503" in str(exc_info.value)

        await provider.close()

    @pytest.mark.asyncio
    async def test_error_403_forbidden(self, provider: TavilySearchProvider) -> None:
        """Replay 403 error - verify SearchProviderError."""
        mock_transport = httpx.MockTransport(
            lambda _: httpx.Response(
                403,
                json={"message": "Access forbidden"},
            )
        )
        provider._client = httpx.AsyncClient(transport=mock_transport)

        with pytest.raises(SearchProviderError) as exc_info:
            await provider.search("test")

        assert "403" in str(exc_info.value)

        await provider.close()

    @pytest.mark.asyncio
    async def test_error_404_not_found(self, provider: TavilySearchProvider) -> None:
        """Replay 404 error - verify SearchProviderError."""
        mock_transport = httpx.MockTransport(
            lambda _: httpx.Response(
                404,
                json={"message": "Endpoint not found"},
            )
        )
        provider._client = httpx.AsyncClient(transport=mock_transport)

        with pytest.raises(SearchProviderError) as exc_info:
            await provider.search("test")

        assert "404" in str(exc_info.value)

        await provider.close()

    @pytest.mark.asyncio
    async def test_error_non_json_response(
        self,
        provider: TavilySearchProvider,
    ) -> None:
        """Replay non-JSON error response - verify error handling."""
        mock_transport = httpx.MockTransport(
            lambda _: httpx.Response(500, text="Internal Server Error")
        )
        provider._client = httpx.AsyncClient(transport=mock_transport)

        with pytest.raises(SearchProviderError) as exc_info:
            await provider.search("test")

        assert "500" in str(exc_info.value)

        await provider.close()
