"""Tests for TavilySearchProvider."""


import httpx
import pytest

from cc_deep_research.models import ResearchDepth, SearchOptions
from cc_deep_research.providers import AuthenticationError, NetworkError, RateLimitError
from cc_deep_research.providers.tavily import TavilySearchProvider


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
