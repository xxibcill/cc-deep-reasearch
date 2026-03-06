"""Search provider implementations."""

from abc import ABC, abstractmethod

from cc_deep_research.models import SearchOptions, SearchResult


class SearchProvider(ABC):
    """Abstract base class for search providers."""

    @abstractmethod
    async def search(self, query: str, options: SearchOptions | None = None) -> SearchResult:
        """Execute a search query.

        Args:
            query: The search query string.
            options: Optional search options.

        Returns:
            SearchResult containing the search results.

        Raises:
            SearchProviderError: If the search fails.
            RateLimitError: If rate limit is exceeded.
            AuthenticationError: If authentication fails.
        """
        ...

    @abstractmethod
    def get_provider_name(self) -> str:
        """Get the name of this provider.

        Returns:
            Provider name string.
        """
        ...

    @property
    def is_available(self) -> bool:
        """Check if this provider is available for use.

        Returns:
            True if provider is available, False otherwise.
        """
        return True

    async def close(self) -> None:
        """Release any provider resources."""
        return None


class SearchProviderError(Exception):
    """Base exception for search provider errors."""

    def __init__(self, message: str, provider: str, query: str | None = None) -> None:
        super().__init__(message)
        self.provider = provider
        self.query = query


class RateLimitError(SearchProviderError):
    """Exception raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str,
        provider: str,
        query: str | None = None,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(message, provider, query)
        self.retry_after = retry_after


class AuthenticationError(SearchProviderError):
    """Exception raised when authentication fails."""

    def __init__(
        self,
        message: str,
        provider: str,
        query: str | None = None,
    ) -> None:
        super().__init__(message, provider, query)


class NetworkError(SearchProviderError):
    """Exception raised for network-related errors."""

    def __init__(
        self,
        message: str,
        provider: str,
        query: str | None = None,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message, provider, query)
        self.original_error = original_error


class ProviderUnavailableError(SearchProviderError):
    """Exception raised when a configured provider is unavailable."""

    def __init__(
        self,
        message: str,
        provider: str,
        query: str | None = None,
        reason: str | None = None,
    ) -> None:
        super().__init__(message, provider, query)
        self.reason = reason


__all__ = [
    "SearchProvider",
    "SearchProviderError",
    "RateLimitError",
    "AuthenticationError",
    "NetworkError",
    "ProviderUnavailableError",
]
