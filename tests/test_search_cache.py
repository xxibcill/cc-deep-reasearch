"""Tests for web search cache identity, storage, and serialization."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from cc_deep_research.models import QueryProvenance, ResearchDepth, SearchOptions, SearchResult
from cc_deep_research.models.search import SearchResultItem
from cc_deep_research.search_cache import (
    SearchCacheStore,
    build_search_cache_identity,
    build_search_cache_key,
    build_search_cache_signature,
    deserialize_search_result,
    serialize_search_result,
)


def _build_sample_result() -> SearchResult:
    """Create one representative provider result for cache tests."""
    return SearchResult(
        query="OpenAI GPT-5",
        provider="tavily",
        execution_time_ms=175,
        metadata={
            "request_id": "req-123",
            "provider_metadata": {
                "region": "us",
                "safesearch": "moderate",
            },
        },
        results=[
            SearchResultItem(
                url="https://example.com/openai-gpt-5",
                title="OpenAI GPT-5 overview",
                snippet="Model release details",
                content="Detailed article body",
                score=0.97,
                source_metadata={
                    "rank": 1,
                    "published_at": "2026-03-20T10:00:00",
                },
                query_provenance=[
                    QueryProvenance(
                        query="OpenAI GPT-5",
                        family="baseline",
                        intent_tags=["official", "release"],
                    )
                ],
            )
        ],
        timestamp=datetime(2026, 3, 20, 10, 30, 0),
    )


def test_equivalent_requests_share_the_same_cache_identity() -> None:
    """Whitespace and casing differences should normalize to one cache signature."""
    first = build_search_cache_identity(
        provider_name=" Tavily ",
        query="  OpenAI   GPT-5  ",
        options=SearchOptions(
            max_results=10,
            include_raw_content=True,
            search_depth=ResearchDepth.DEEP,
        ),
    )
    second = build_search_cache_identity(
        provider_name="tavily",
        query="openai gpt-5",
        options=SearchOptions(
            max_results=10,
            include_raw_content=True,
            search_depth=ResearchDepth.DEEP,
        ),
    )

    assert first == second
    assert first.to_signature() == second.to_signature()
    assert first.to_cache_key() == second.to_cache_key()


def test_different_provider_strategies_generate_different_keys() -> None:
    """Configured provider strategies should not collide in the cache."""
    tavily_advanced = build_search_cache_key(
        provider_name="tavily",
        query="OpenAI GPT-5",
        options=SearchOptions(search_depth=ResearchDepth.DEEP),
    )
    tavily_basic = build_search_cache_key(
        provider_name="tavily_basic",
        query="OpenAI GPT-5",
        options=SearchOptions(search_depth=ResearchDepth.DEEP),
    )

    assert tavily_advanced != tavily_basic


def test_material_option_changes_change_the_signature() -> None:
    """Options that affect the result set should produce distinct identities."""
    base_signature = build_search_cache_signature(
        provider_name="tavily",
        query="OpenAI GPT-5",
        options=SearchOptions(
            max_results=10,
            include_raw_content=True,
            search_depth=ResearchDepth.DEEP,
        ),
    )

    assert base_signature != build_search_cache_signature(
        provider_name="tavily",
        query="OpenAI GPT-5",
        options=SearchOptions(
            max_results=5,
            include_raw_content=True,
            search_depth=ResearchDepth.DEEP,
        ),
    )
    assert base_signature != build_search_cache_signature(
        provider_name="tavily",
        query="OpenAI GPT-5",
        options=SearchOptions(
            max_results=10,
            include_raw_content=False,
            search_depth=ResearchDepth.DEEP,
        ),
    )
    assert base_signature != build_search_cache_signature(
        provider_name="tavily",
        query="OpenAI GPT-5",
        options=SearchOptions(
            max_results=10,
            include_raw_content=True,
            search_depth=ResearchDepth.QUICK,
        ),
    )


def test_search_result_serialization_round_trips() -> None:
    """Serialized cache payloads should reconstruct valid search results."""
    result = _build_sample_result()

    restored = deserialize_search_result(serialize_search_result(result))

    assert restored == result
    assert restored.results[0] is not result.results[0]
    assert restored.results[0].query_provenance[0].query == "OpenAI GPT-5"


def test_store_persists_entries_across_instances(tmp_path: Path) -> None:
    """Cache rows should remain readable after reopening the database."""
    db_path = tmp_path / "search-cache.sqlite3"
    identity = build_search_cache_identity(
        provider_name="tavily",
        query="OpenAI GPT-5",
        options=SearchOptions(search_depth=ResearchDepth.DEEP),
    )
    created_at = datetime(2026, 3, 20, 12, 0, 0)

    first_store = SearchCacheStore(db_path)
    stored = first_store.put(
        identity=identity,
        result=_build_sample_result(),
        ttl_seconds=300,
        now=created_at,
    )

    second_store = SearchCacheStore(db_path)
    loaded = second_store.get(identity.to_cache_key(), now=created_at + timedelta(seconds=30))

    assert loaded is not None
    assert loaded.cache_key == stored.cache_key
    assert loaded.provider == "tavily"
    assert loaded.normalized_query == "openai gpt-5"
    assert loaded.request_signature == identity.to_signature()
    assert loaded.result.query == "OpenAI GPT-5"
    assert loaded.hit_count == 1
    assert loaded.last_accessed_at == created_at + timedelta(seconds=30)


def test_store_returns_none_for_expired_entries_and_can_expose_them(tmp_path: Path) -> None:
    """Expired rows should read as misses unless explicitly requested."""
    store = SearchCacheStore(tmp_path / "search-cache.sqlite3")
    identity = build_search_cache_identity(
        provider_name="tavily",
        query="OpenAI GPT-5",
        options=SearchOptions(search_depth=ResearchDepth.DEEP),
    )
    created_at = datetime(2026, 3, 20, 12, 0, 0)
    store.put(identity=identity, result=_build_sample_result(), ttl_seconds=60, now=created_at)

    assert store.get(identity.to_cache_key(), now=created_at + timedelta(seconds=61)) is None

    expired = store.get(
        identity.to_cache_key(),
        include_expired=True,
        now=created_at + timedelta(seconds=61),
    )

    assert expired is not None
    assert expired.is_expired(now=created_at + timedelta(seconds=61)) is True
    assert expired.hit_count == 0


def test_store_returns_fresh_instances_for_each_cache_hit(tmp_path: Path) -> None:
    """Mutating one cache-hit result should not affect later reads."""
    store = SearchCacheStore(tmp_path / "search-cache.sqlite3")
    identity = build_search_cache_identity(
        provider_name="tavily",
        query="OpenAI GPT-5",
        options=SearchOptions(search_depth=ResearchDepth.DEEP),
    )
    created_at = datetime(2026, 3, 20, 12, 0, 0)
    store.put(identity=identity, result=_build_sample_result(), ttl_seconds=300, now=created_at)

    first_hit = store.get(identity.to_cache_key(), now=created_at + timedelta(seconds=5))
    assert first_hit is not None
    first_hit.result.results[0].source_metadata["rank"] = 99

    second_hit = store.get(identity.to_cache_key(), now=created_at + timedelta(seconds=10))
    assert second_hit is not None
    assert second_hit.result.results[0].source_metadata["rank"] == 1
    assert second_hit.hit_count == 2


def test_store_delete_and_purge_expired_entries(tmp_path: Path) -> None:
    """Store helpers should delete specific keys and purge expired rows."""
    store = SearchCacheStore(tmp_path / "search-cache.sqlite3")
    active_identity = build_search_cache_identity(
        provider_name="tavily",
        query="OpenAI GPT-5",
        options=SearchOptions(search_depth=ResearchDepth.DEEP),
    )
    expired_identity = build_search_cache_identity(
        provider_name="tavily",
        query="OpenAI GPT-4",
        options=SearchOptions(search_depth=ResearchDepth.DEEP),
    )
    now = datetime(2026, 3, 20, 12, 0, 0)

    store.put(identity=active_identity, result=_build_sample_result(), ttl_seconds=300, now=now)
    store.put(identity=expired_identity, result=_build_sample_result(), ttl_seconds=10, now=now)

    assert store.delete(active_identity.to_cache_key()) is True
    assert store.delete(active_identity.to_cache_key()) is False

    purged = store.purge_expired(now=now + timedelta(seconds=20))
    assert purged == 1
    assert store.get(expired_identity.to_cache_key(), include_expired=True, now=now) is None


def test_store_enforces_max_entries_by_last_accessed_time(tmp_path: Path) -> None:
    """Configured store limits should keep the most recently used entries."""
    store = SearchCacheStore(tmp_path / "search-cache.sqlite3", max_entries=2)
    oldest = build_search_cache_identity(
        provider_name="tavily",
        query="first query",
        options=SearchOptions(search_depth=ResearchDepth.DEEP),
    )
    middle = build_search_cache_identity(
        provider_name="tavily",
        query="second query",
        options=SearchOptions(search_depth=ResearchDepth.DEEP),
    )
    newest = build_search_cache_identity(
        provider_name="tavily",
        query="third query",
        options=SearchOptions(search_depth=ResearchDepth.DEEP),
    )
    now = datetime(2026, 3, 20, 12, 0, 0)

    store.put(identity=oldest, result=_build_sample_result(), ttl_seconds=300, now=now)
    store.put(identity=middle, result=_build_sample_result(), ttl_seconds=300, now=now + timedelta(seconds=5))
    store.get(middle.to_cache_key(), now=now + timedelta(seconds=10))
    store.put(identity=newest, result=_build_sample_result(), ttl_seconds=300, now=now + timedelta(seconds=15))

    assert store.get(oldest.to_cache_key(), include_expired=True, now=now + timedelta(seconds=20)) is None
    assert store.get(middle.to_cache_key(), now=now + timedelta(seconds=20)) is not None
    assert store.get(newest.to_cache_key(), now=now + timedelta(seconds=20)) is not None
