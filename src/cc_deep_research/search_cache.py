"""Helpers for stable web-search cache identity."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from cc_deep_research.models.search import SearchOptions


def _normalize_provider_name(provider_name: str) -> str:
    """Normalize provider identity for cache comparisons."""
    return " ".join(provider_name.strip().lower().split())


def _normalize_query_text(query: str) -> str:
    """Normalize query text while preserving meaningful punctuation."""
    return " ".join(query.strip().casefold().split())


@dataclass(frozen=True, slots=True)
class SearchCacheIdentity:
    """Deterministic cache identity for one web search request."""

    provider: str
    query: str
    search_depth: str
    max_results: int
    include_raw_content: bool

    def to_signature_payload(self) -> dict[str, str | int | bool]:
        """Return a serialized payload with normalized cache inputs."""
        return {
            "provider": self.provider,
            "query": self.query,
            "search_depth": self.search_depth,
            "max_results": self.max_results,
            "include_raw_content": self.include_raw_content,
        }

    def to_signature(self) -> str:
        """Return the stable serialized signature for cache lookups."""
        return json.dumps(
            self.to_signature_payload(),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )

    def to_cache_key(self) -> str:
        """Return a compact hashed cache key derived from the signature."""
        return hashlib.sha256(self.to_signature().encode("utf-8")).hexdigest()


def build_search_cache_identity(
    *,
    provider_name: str,
    query: str,
    options: SearchOptions,
) -> SearchCacheIdentity:
    """Build the normalized cache identity for a search request."""
    return SearchCacheIdentity(
        provider=_normalize_provider_name(provider_name),
        query=_normalize_query_text(query),
        search_depth=options.search_depth.value,
        max_results=options.max_results,
        include_raw_content=options.include_raw_content,
    )


def build_search_cache_signature(
    *,
    provider_name: str,
    query: str,
    options: SearchOptions,
) -> str:
    """Return the deterministic signature for a search request."""
    return build_search_cache_identity(
        provider_name=provider_name,
        query=query,
        options=options,
    ).to_signature()


def build_search_cache_key(
    *,
    provider_name: str,
    query: str,
    options: SearchOptions,
) -> str:
    """Return the deterministic hashed cache key for a search request."""
    return build_search_cache_identity(
        provider_name=provider_name,
        query=query,
        options=options,
    ).to_cache_key()


__all__ = [
    "SearchCacheIdentity",
    "build_search_cache_identity",
    "build_search_cache_key",
    "build_search_cache_signature",
]
