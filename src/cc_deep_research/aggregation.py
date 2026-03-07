"""Result aggregation and deduplication utilities."""

from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import click

from cc_deep_research.models import SearchResult, SearchResultItem


def normalize_url(url: str) -> str:
    """Normalize a URL for comparison.

    Args:
        url: URL to normalize.

    Returns:
        Normalized URL string.
    """
    parsed = urlparse(url.lower())

    # Remove common tracking parameters
    netloc = parsed.netloc
    path = parsed.path.rstrip("/")

    # Remove www prefix
    if netloc.startswith("www."):
        netloc = netloc[4:]

    return f"{parsed.scheme}://{netloc}{path}"


def deduplicate_by_url(
    results: list[SearchResultItem],
    keep_highest_score: bool = True,
) -> list[SearchResultItem]:
    """Deduplicate results by URL.

    Args:
        results: List of search result items.
        keep_highest_score: If True, keep the result with highest score for duplicates.

    Returns:
        Deduplicated list of search result items.
    """
    seen_urls: dict[str, SearchResultItem] = {}

    for result in results:
        normalized = normalize_url(result.url)
        existing = seen_urls.get(normalized)
        if existing is None:
            seen_urls[normalized] = result
            continue

        if keep_highest_score and result.score > existing.score:
            seen_urls[normalized] = _merge_duplicate_items(result, existing)
            continue

        seen_urls[normalized] = _merge_duplicate_items(existing, result)

    return list(seen_urls.values())


def _merge_duplicate_items(
    primary: SearchResultItem,
    secondary: SearchResultItem,
) -> SearchResultItem:
    """Merge duplicate items while preserving query provenance."""
    payload = primary.model_dump(mode="python")
    payload["score"] = max(primary.score, secondary.score)
    payload["title"] = primary.title or secondary.title
    payload["snippet"] = _prefer_longer_text(primary.snippet, secondary.snippet)
    payload["content"] = _prefer_longer_text(primary.content, secondary.content)
    payload["source_metadata"] = _merge_source_metadata(
        primary.source_metadata,
        secondary.source_metadata,
    )
    payload["query_provenance"] = [
        *primary.model_dump(mode="python").get("query_provenance", []),
        *secondary.model_dump(mode="python").get("query_provenance", []),
    ]
    return SearchResultItem.model_validate(payload)


def _prefer_longer_text(primary: str | None, secondary: str | None) -> str | None:
    """Keep the more informative text value when merging duplicates."""
    if not primary:
        return secondary
    if not secondary:
        return primary
    return primary if len(primary) >= len(secondary) else secondary


def _merge_source_metadata(
    primary: dict[str, Any],
    secondary: dict[str, Any],
) -> dict[str, Any]:
    """Merge metadata dictionaries while preserving provenance lists."""
    merged = dict(secondary)
    merged.update(primary)
    merged["queries"] = _merge_string_lists(primary.get("queries"), secondary.get("queries"))
    merged["query_families"] = _merge_string_lists(
        primary.get("query_families"),
        secondary.get("query_families"),
    )
    merged["query_provenance"] = _merge_mapping_lists(
        primary.get("query_provenance"),
        secondary.get("query_provenance"),
    )
    return merged


def _merge_string_lists(primary: Any, secondary: Any) -> list[str]:
    """Merge list-like string payloads without duplicates."""
    values: list[str] = []
    for candidate in (primary, secondary):
        if isinstance(candidate, list):
            values.extend(str(item) for item in candidate if item)
    return list(dict.fromkeys(values))


def _merge_mapping_lists(primary: Any, secondary: Any) -> list[dict[str, Any]]:
    """Merge list-like mapping payloads without duplicate entries."""
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    for candidate in (primary, secondary):
        if not isinstance(candidate, list):
            continue
        for item in candidate:
            if not isinstance(item, dict):
                continue
            query = str(item.get("query", ""))
            family = str(item.get("family", "baseline"))
            intent_tags = tuple(str(tag) for tag in item.get("intent_tags", []) if tag)
            key = (query, family, intent_tags)
            if not query or key in seen:
                continue
            seen.add(key)
            merged.append(
                {
                    "query": query,
                    "family": family,
                    "intent_tags": list(intent_tags),
                }
            )
    return merged


def aggregate_results(
    search_results: list[SearchResult],
    deduplicate: bool = True,
    sort_by_score: bool = True,
    monitor: bool = False,
) -> list[SearchResultItem]:
    """Aggregate results from multiple search providers.

    Args:
        search_results: List of SearchResult objects from different providers.
        deduplicate: If True, remove duplicate URLs.
        sort_by_score: If True, sort results by score descending.
        monitor: If True, log monitoring information.

    Returns:
        Aggregated list of search result items.
    """
    all_items: list[SearchResultItem] = []

    for search_result in search_results:
        all_items.extend(search_result.results)

    if monitor:
        timestamp = datetime.now().strftime("%H:%M:%S")
        click.echo(
            f"[{timestamp}] [AGGREGATOR] Processing {len(all_items)} results from "
            f"{len(search_results)} provider(s)"
        )

    if deduplicate:
        original_count = len(all_items)
        all_items = deduplicate_by_url(all_items)
        if monitor:
            removed = original_count - len(all_items)
            timestamp = datetime.now().strftime("%H:%M:%S")
            click.echo(
                f"[{timestamp}] [AGGREGATOR] Deduplicated: {removed} duplicate(s) removed, "
                f"{len(all_items)} unique result(s)"
            )

    if sort_by_score:
        all_items.sort(key=lambda x: x.score, reverse=True)
        if monitor:
            timestamp = datetime.now().strftime("%H:%M:%S")
            click.echo(f"[{timestamp}] [AGGREGATOR] Sorted by score (descending)")

    return all_items


def merge_search_results(
    search_results: list[SearchResult],
    query: str,
) -> SearchResult:
    """Merge multiple SearchResult objects into one.

    Args:
        search_results: List of SearchResult objects to merge.
        query: The original query.

    Returns:
        Merged SearchResult object.
    """
    aggregated_items = aggregate_results(search_results)

    # Combine metadata from all providers
    combined_metadata: dict[str, list[str]] = {"providers": []}
    total_execution_time = 0

    for sr in search_results:
        combined_metadata["providers"].append(sr.provider)
        total_execution_time += sr.execution_time_ms

    return SearchResult(
        query=query,
        results=aggregated_items,
        provider="aggregated",
        metadata=combined_metadata,
        execution_time_ms=total_execution_time,
    )


class ResultAggregator:
    """Aggregator for combining and deduplicating search results."""

    def __init__(
        self,
        deduplicate: bool = True,
        sort_by_score: bool = True,
        monitor: bool = False,
    ) -> None:
        """Initialize the aggregator.

        Args:
            deduplicate: Whether to deduplicate results.
            sort_by_score: Whether to sort by score.
            monitor: Whether to enable monitoring.
        """
        self._deduplicate = deduplicate
        self._sort_by_score = sort_by_score
        self._monitor = monitor
        self._all_results: list[SearchResult] = []

    def add_result(self, result: SearchResult) -> None:
        """Add a search result to the aggregator.

        Args:
            result: SearchResult to add.
        """
        self._all_results.append(result)

    def get_aggregated(self) -> list[SearchResultItem]:
        """Get aggregated results.

        Returns:
            Aggregated and optionally deduplicated list of items.
        """
        return aggregate_results(
            self._all_results,
            deduplicate=self._deduplicate,
            sort_by_score=self._sort_by_score,
            monitor=self._monitor,
        )

    def get_merged(self, query: str) -> SearchResult:
        """Get merged SearchResult.

        Args:
            query: Original query string.

        Returns:
            Merged SearchResult.
        """
        return merge_search_results(self._all_results, query)

    def clear(self) -> None:
        """Clear all stored results."""
        self._all_results = []

    @property
    def result_count(self) -> int:
        """Get total number of results (before deduplication)."""
        return sum(len(r.results) for r in self._all_results)

    @property
    def provider_count(self) -> int:
        """Get number of providers."""
        return len(self._all_results)


__all__ = [
    "normalize_url",
    "deduplicate_by_url",
    "aggregate_results",
    "merge_search_results",
    "ResultAggregator",
]
