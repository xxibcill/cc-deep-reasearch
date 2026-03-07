"""Search provider implementations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from cc_deep_research.models import SearchOptions, SearchResult

if TYPE_CHECKING:
    from cc_deep_research.config import Config


@dataclass(frozen=True)
class ProviderSpec:
    """Normalized provider configuration used by the collector."""

    configured_name: str
    provider_type: str
    provider_name: str
    strategy: str | None = None


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


_SUPPORTED_PROVIDER_SPECS: dict[str, ProviderSpec] = {
    "tavily": ProviderSpec(
        configured_name="tavily",
        provider_type="tavily",
        provider_name="tavily",
        strategy="advanced",
    ),
    "tavily_advanced": ProviderSpec(
        configured_name="tavily_advanced",
        provider_type="tavily",
        provider_name="tavily_advanced",
        strategy="advanced",
    ),
    "tavily_basic": ProviderSpec(
        configured_name="tavily_basic",
        provider_type="tavily",
        provider_name="tavily_basic",
        strategy="basic",
    ),
}


def resolve_provider_specs(config: "Config") -> list[ProviderSpec]:
    """Resolve configured provider names into provider instances to initialize."""
    configured_names = list(config.search.providers or ["tavily"])
    resolved_names: list[str] = []

    for provider_name in configured_names:
        resolved_names.append(provider_name)
        if (
            provider_name == "tavily"
            and config.search.mode.value == "hybrid_parallel"
            and "tavily_basic" not in configured_names
        ):
            resolved_names.append("tavily_basic")

    resolved_specs: list[ProviderSpec] = []
    seen_provider_names: set[str] = set()
    for provider_name in resolved_names:
        spec = _SUPPORTED_PROVIDER_SPECS.get(provider_name)
        if spec is None:
            spec = ProviderSpec(
                configured_name=provider_name,
                provider_type=provider_name,
                provider_name=provider_name,
            )
        if spec.provider_name in seen_provider_names:
            continue
        seen_provider_names.add(spec.provider_name)
        resolved_specs.append(spec)

    return resolved_specs


__all__ = [
    "ProviderSpec",
    "resolve_provider_specs",
    "SearchProvider",
    "SearchProviderError",
    "RateLimitError",
    "AuthenticationError",
    "NetworkError",
    "ProviderUnavailableError",
]
