"""Cache-aware search provider wrapper."""

from __future__ import annotations

from datetime import datetime

from cc_deep_research.models import SearchOptions, SearchResult
from cc_deep_research.providers import SearchProvider
from cc_deep_research.search_cache import (
    InFlightSearchRegistry,
    SearchCacheEntry,
    SearchCacheIdentity,
    SearchCacheStore,
    build_search_cache_identity,
)


def _utcnow() -> datetime:
    """Return current UTC time without timezone info."""
    return datetime.utcnow()


class CachedSearchProvider(SearchProvider):
    """Wrap one provider with persistent caching and in-flight deduplication."""

    def __init__(
        self,
        provider: SearchProvider,
        *,
        store: SearchCacheStore,
        ttl_seconds: int,
        in_flight_registry: InFlightSearchRegistry,
        default_options: SearchOptions,
    ) -> None:
        self._provider = provider
        self._store = store
        self._ttl_seconds = ttl_seconds
        self._in_flight_registry = in_flight_registry
        self._default_options = default_options.model_copy(deep=True)

    async def search(self, query: str, options: SearchOptions | None = None) -> SearchResult:
        """Return a cached result when available, otherwise delegate and store."""
        resolved_options = self._resolve_options(options)
        identity = build_search_cache_identity(
            provider_name=self.get_provider_name(),
            query=query,
            options=resolved_options,
        )
        cache_key = identity.to_cache_key()

        cached_entry = self._store.get(cache_key)
        if cached_entry is not None:
            result = cached_entry.result.model_copy(deep=True)
            self._attach_cache_metadata(
                result=result,
                cache_key=cache_key,
                cached_entry=cached_entry,
                status="hit",
            )
            return result

        result = await self._in_flight_registry.run(
            cache_key,
            lambda: self._load_and_store(query, resolved_options, identity),
        )
        self._attach_cache_metadata(
            result=result,
            cache_key=cache_key,
            cached_entry=None,
            status="miss",
        )
        return result

    def _attach_cache_metadata(
        self,
        *,
        result: SearchResult,
        cache_key: str,
        cached_entry: SearchCacheEntry | None,
        status: str,
    ) -> None:
        """Attach cache telemetry metadata to a search result."""
        now = _utcnow()
        metadata = dict(result.metadata)
        metadata["cache_status"] = status
        metadata["cache_key"] = cache_key

        if cached_entry is not None:
            age_seconds = int((now - cached_entry.created_at).total_seconds())
            metadata["cache_age_seconds"] = age_seconds
            metadata["expires_at"] = cached_entry.expires_at.isoformat()
        else:
            metadata["cache_age_seconds"] = None
            metadata["expires_at"] = None

        result.metadata = metadata

    def get_provider_name(self) -> str:
        """Return the wrapped provider name."""
        return self._provider.get_provider_name()

    @property
    def is_available(self) -> bool:
        """Return whether the wrapped provider is available."""
        return self._provider.is_available

    async def close(self) -> None:
        """Close the wrapped provider."""
        await self._provider.close()

    def _resolve_options(self, options: SearchOptions | None) -> SearchOptions:
        """Return cache inputs that match the provider request shape."""
        if options is None:
            return self._default_options.model_copy(deep=True)
        return options.model_copy(deep=True)

    async def _load_and_store(
        self,
        query: str,
        options: SearchOptions,
        identity: SearchCacheIdentity,
    ) -> SearchResult:
        """Execute the provider call and persist successful responses only."""
        result = await self._provider.search(query, options)
        self._store.put(
            identity=identity,
            result=result,
            ttl_seconds=self._ttl_seconds,
        )
        return result


__all__ = ["CachedSearchProvider"]
