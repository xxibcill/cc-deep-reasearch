"""Tavily search provider implementation."""

import time
from datetime import datetime
from typing import Any

import click
import httpx

from cc_deep_research.models import SearchOptions, SearchResult, SearchResultItem
from cc_deep_research.providers import (
    AuthenticationError,
    NetworkError,
    RateLimitError,
    SearchProvider,
    SearchProviderError,
)


class TavilySearchProvider(SearchProvider):
    """Search provider using Tavily Search API."""

    API_URL = "https://api.tavily.com/search"

    def __init__(
        self,
        api_key: str,
        max_results: int = 10,
        timeout: float = 30.0,
        provider_name: str = "tavily",
        strategy: str = "auto",
    ) -> None:
        """Initialize Tavily search provider.

        Args:
            api_key: Tavily API key.
            max_results: Default maximum number of results.
            timeout: Request timeout in seconds.
        """
        self._api_key = api_key
        self._max_results = max_results
        self._timeout = timeout
        self._provider_name = provider_name
        self._strategy = strategy
        self._client = httpx.AsyncClient(timeout=timeout)

    async def search(self, query: str, options: SearchOptions | None = None) -> SearchResult:
        """Execute a search using Tavily API.

        Args:
            query: The search query string.
            options: Optional search options.

        Returns:
            SearchResult containing the search results.

        Raises:
            RateLimitError: If rate limit is exceeded.
            AuthenticationError: If API key is invalid.
            NetworkError: If network error occurs.
            SearchProviderError: For other API errors.
        """
        options = options or SearchOptions(max_results=self._max_results)
        start_time = time.time()

        # Monitor: Start of operation
        monitor = getattr(options, "monitor", False) if options else False
        if monitor:
            timestamp = datetime.now().strftime("%H:%M:%S")
            click.echo(f"[{timestamp}] [TAVILY] Starting search: {query}")

        payload = self._build_payload(query, options)

        try:
            response = await self._client.post(
                self.API_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
            )

            self._check_response_errors(response, query)

            data = response.json()
            results = self._parse_results(data)

            execution_time_ms = int((time.time() - start_time) * 1000)

            # Monitor: Log results
            if monitor:
                timestamp = datetime.now().strftime("%H:%M:%S")
                click.echo(
                    f"[{timestamp}] [TAVILY] Response received: {len(results)} results ({execution_time_ms}ms)"
                )

            return SearchResult(
                query=query,
                results=results,
                provider=self.get_provider_name(),
                metadata={
                    "response_id": data.get("response_id"),
                    "images": data.get("images", []),
                    "strategy": self._resolve_search_depth(options),
                },
                execution_time_ms=execution_time_ms,
            )

        except httpx.TimeoutException as e:
            raise NetworkError(
                "Request timed out",
                self.get_provider_name(),
                query,
                original_error=e,
            ) from None
        except httpx.ConnectError as e:
            raise NetworkError(
                "Failed to connect to Tavily API",
                self.get_provider_name(),
                query,
                original_error=e,
            ) from None
        except httpx.HTTPStatusError as e:
            raise NetworkError(
                f"HTTP error: {e.response.status_code}",
                self.get_provider_name(),
                query,
                original_error=e,
            ) from None

    def _build_payload(self, query: str, options: SearchOptions) -> dict[str, Any]:
        """Build the API request payload.

        Args:
            query: The search query.
            options: Search options.

        Returns:
            Dictionary payload for the API request.
        """
        return {
            "api_key": self._api_key,
            "query": query,
            "max_results": options.max_results,
            "include_raw_content": options.include_raw_content,
            "search_depth": self._resolve_search_depth(options),
        }

    def _resolve_search_depth(self, options: SearchOptions) -> str:
        """Resolve the Tavily search depth for the current request."""
        if self._strategy in {"advanced", "basic"}:
            return self._strategy
        return "advanced" if options.search_depth.value == "deep" else "basic"

    def _check_response_errors(self, response: httpx.Response, query: str) -> None:
        """Check response for errors and raise appropriate exceptions.

        Args:
            response: HTTP response.
            query: Original query.

        Raises:
            RateLimitError: If rate limited.
            AuthenticationError: If authentication failed.
            SearchProviderError: For other errors.
        """
        if response.status_code == 200:
            return

        try:
            error_data = response.json()
            error_message = error_data.get("message", response.text)
        except Exception:
            error_message = response.text or f"HTTP {response.status_code}"

        if response.status_code == 401:
            raise AuthenticationError(
                f"Invalid API key: {error_message}",
                self.get_provider_name(),
                query,
            )
        elif response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(
                f"Rate limit exceeded: {error_message}",
                self.get_provider_name(),
                query,
                retry_after=int(retry_after) if retry_after else None,
            )
        else:
            raise SearchProviderError(
                f"API error ({response.status_code}): {error_message}",
                self.get_provider_name(),
                query,
            )

    def _parse_results(self, data: dict[str, Any]) -> list[SearchResultItem]:
        """Parse API response into SearchResultItem list.

        Args:
            data: API response data.

        Returns:
            List of SearchResultItem objects.
        """
        results = []
        for item in data.get("results", []):
            score = item.get("score")
            if score is None:
                score = 0.0

            result = SearchResultItem(
                url=item.get("url", ""),
                title=item.get("title", ""),
                snippet=item.get("content", ""),
                content=item.get("raw_content"),
                score=score,
                source_metadata={
                    "published_date": item.get("published_date"),
                },
            )
            results.append(result)
        return results

    def get_provider_name(self) -> str:
        """Get the provider name.

        Returns:
            "tavily"
        """
        return self._provider_name

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "TavilySearchProvider":
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.close()


__all__ = ["TavilySearchProvider"]
