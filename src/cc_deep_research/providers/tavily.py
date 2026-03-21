"""Tavily search provider implementation."""

import time
from datetime import datetime
from typing import Any

import click
import httpx

from cc_deep_research.key_rotation import AllKeysExhaustedError, KeyRotationManager
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
        api_key: str | None = None,
        max_results: int = 10,
        timeout: float = 30.0,
        provider_name: str = "tavily",
        strategy: str = "auto",
        key_manager: KeyRotationManager | None = None,
    ) -> None:
        """Initialize Tavily search provider.

        Args:
            api_key: Tavily API key.
            max_results: Default maximum number of results.
            timeout: Request timeout in seconds.
        """
        if api_key is None and key_manager is None:
            raise ValueError("TavilySearchProvider requires either api_key or key_manager")

        self._api_key = api_key
        self._max_results = max_results
        self._timeout = timeout
        self._provider_name = provider_name
        self._strategy = strategy
        self._key_manager = key_manager
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

        attempts_remaining = self._key_manager.total_count if self._key_manager else 1
        last_error: SearchProviderError | None = None

        while attempts_remaining > 0:
            api_key = self._get_api_key()
            payload = self._build_payload(query, options, api_key)

            try:
                response = await self._client.post(
                    self.API_URL,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                self._record_usage(api_key)
                self._check_response_errors(response, query, api_key)

                data = response.json()
                results = self._parse_results(data)

                execution_time_ms = int((time.time() - start_time) * 1000)

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

            except (RateLimitError, SearchProviderError) as error:
                if self._should_retry_with_next_key(error):
                    last_error = error
                    attempts_remaining -= 1
                    continue
                raise
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

        if last_error is not None:
            raise last_error
        raise SearchProviderError("No Tavily API keys available", self.get_provider_name(), query)

    def _build_payload(
        self,
        query: str,
        options: SearchOptions,
        api_key: str | None = None,
    ) -> dict[str, Any]:
        """Build the API request payload.

        Args:
            query: The search query.
            options: Search options.

        Returns:
            Dictionary payload for the API request.
        """
        if api_key is None:
            api_key = self._api_key
        if api_key is None:
            raise ValueError("An API key is required to build a Tavily request payload")
        return {
            "api_key": api_key,
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

    def _check_response_errors(self, response: httpx.Response, query: str, api_key: str) -> None:
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
            self._mark_key_unavailable(
                api_key,
                retry_after_seconds=int(retry_after) if retry_after else None,
            )
            raise RateLimitError(
                f"Rate limit exceeded: {error_message}",
                self.get_provider_name(),
                query,
                retry_after=int(retry_after) if retry_after else None,
            )
        elif self._is_plan_limit_error(response.status_code, error_message):
            self._mark_key_unavailable(api_key)
            raise SearchProviderError(
                f"API error ({response.status_code}): {error_message}",
                self.get_provider_name(),
                query,
            )
        else:
            raise SearchProviderError(
                f"API error ({response.status_code}): {error_message}",
                self.get_provider_name(),
                query,
            )

    def _get_api_key(self) -> str:
        if self._key_manager is not None:
            try:
                return self._key_manager.get_available_key()
            except AllKeysExhaustedError as error:
                raise RateLimitError(
                    str(error),
                    self.get_provider_name(),
                    retry_after=self._get_retry_after_from_exhaustion(error),
                ) from None
        assert self._api_key is not None
        return self._api_key

    def _record_usage(self, api_key: str) -> None:
        if self._key_manager is not None:
            self._key_manager.record_usage(api_key)

    def _mark_key_unavailable(
        self,
        api_key: str,
        *,
        retry_after_seconds: int | None = None,
    ) -> None:
        if self._key_manager is not None:
            self._key_manager.mark_rate_limited(
                api_key,
                retry_after_seconds=retry_after_seconds,
            )

    def _should_retry_with_next_key(self, error: SearchProviderError) -> bool:
        if self._key_manager is None or self._key_manager.available_count <= 0:
            return False
        if isinstance(error, RateLimitError):
            return True
        return self._is_plan_limit_message(str(error))

    def _is_plan_limit_error(self, status_code: int, error_message: str) -> bool:
        return status_code == 432 or self._is_plan_limit_message(error_message)

    def _is_plan_limit_message(self, error_message: str) -> bool:
        normalized_message = error_message.lower()
        return "usage limit" in normalized_message or "plan's set usage limit" in normalized_message

    def _get_retry_after_from_exhaustion(self, error: AllKeysExhaustedError) -> int | None:
        if error.reset_time is None:
            return None
        seconds_until_reset = int((error.reset_time - datetime.utcnow()).total_seconds())
        return max(seconds_until_reset, 0)

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
