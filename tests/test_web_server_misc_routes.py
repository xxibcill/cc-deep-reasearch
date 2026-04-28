"""Tests for FastAPI dashboard runtime state."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from cc_deep_research.web_server import (
    create_app,
)


def test_search_cache_stats_returns_disabled_when_cache_off(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cache stats should indicate when cache is disabled."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    client = TestClient(create_app())
    response = client.get("/api/search-cache/stats")

    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is False
    assert data["total_entries"] == 0
    assert data["active_entries"] == 0


def test_search_cache_list_returns_empty_when_disabled(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cache list should return empty when cache is disabled."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    client = TestClient(create_app())
    response = client.get("/api/search-cache")

    assert response.status_code == 200
    data = response.json()
    assert data["entries"] == []
    assert data["total"] == 0
    assert "disabled" in data.get("message", "").lower()


def test_search_cache_stats_returns_counts_when_enabled(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cache stats should return entry counts when cache is enabled."""
    from cc_deep_research.models import ResearchDepth, SearchOptions, SearchResult
    from cc_deep_research.search_cache import SearchCacheStore, build_search_cache_identity

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "cc-deep-research"
    config_dir.mkdir(parents=True)

    # Add an entry to the cache
    db_path = config_dir / "search-cache.sqlite3"

    # Create config with cache enabled and explicit db_path
    (config_dir / "config.yaml").write_text(
        f"search_cache:\n  enabled: true\n  ttl_seconds: 3600\n  max_entries: 1000\n  db_path: {db_path}\n",
        encoding="utf-8",
    )

    store = SearchCacheStore(db_path)
    identity = build_search_cache_identity(
        provider_name="tavily",
        query="test query",
        options=SearchOptions(search_depth=ResearchDepth.DEEP),
    )
    store.put(
        identity=identity,
        result=SearchResult(query="test query", provider="tavily"),
        ttl_seconds=3600,
    )

    client = TestClient(create_app())
    response = client.get("/api/search-cache/stats")

    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True
    assert data["total_entries"] == 1
    assert data["active_entries"] == 1
    assert data["expired_entries"] == 0
    assert data["db_exists"] is True


def test_search_cache_list_returns_entries_when_enabled(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cache list should return entries when cache is enabled."""
    from cc_deep_research.models import ResearchDepth, SearchOptions, SearchResult
    from cc_deep_research.search_cache import SearchCacheStore, build_search_cache_identity

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "cc-deep-research"
    config_dir.mkdir(parents=True)

    # Add an entry to the cache
    db_path = config_dir / "search-cache.sqlite3"

    # Create config with cache enabled and explicit db_path
    (config_dir / "config.yaml").write_text(
        f"search_cache:\n  enabled: true\n  ttl_seconds: 3600\n  max_entries: 1000\n  db_path: {db_path}\n",
        encoding="utf-8",
    )

    store = SearchCacheStore(db_path)
    identity = build_search_cache_identity(
        provider_name="tavily",
        query="cache list test",
        options=SearchOptions(search_depth=ResearchDepth.DEEP),
    )
    store.put(
        identity=identity,
        result=SearchResult(query="cache list test", provider="tavily"),
        ttl_seconds=3600,
    )

    client = TestClient(create_app())
    response = client.get("/api/search-cache")

    assert response.status_code == 200
    data = response.json()
    assert len(data["entries"]) == 1
    assert data["total"] == 1
    entry = data["entries"][0]
    assert entry["provider"] == "tavily"
    assert entry["normalized_query"] == "cache list test"
    assert entry["is_expired"] is False


def test_search_cache_purge_expired_removes_old_entries(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Purge expired should remove entries past their TTL."""
    from cc_deep_research.models import ResearchDepth, SearchOptions, SearchResult
    from cc_deep_research.search_cache import SearchCacheStore, build_search_cache_identity

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "cc-deep-research"
    config_dir.mkdir(parents=True)

    # Add an expired entry to the cache
    db_path = config_dir / "search-cache.sqlite3"

    # Create config with cache enabled and explicit db_path
    (config_dir / "config.yaml").write_text(
        f"search_cache:\n  enabled: true\n  ttl_seconds: 3600\n  max_entries: 1000\n  db_path: {db_path}\n",
        encoding="utf-8",
    )

    store = SearchCacheStore(db_path)
    identity = build_search_cache_identity(
        provider_name="tavily",
        query="expired query",
        options=SearchOptions(search_depth=ResearchDepth.DEEP),
    )
    store.put(
        identity=identity,
        result=SearchResult(query="expired query", provider="tavily"),
        ttl_seconds=-1,  # Already expired
    )

    client = TestClient(create_app())
    response = client.post("/api/search-cache/purge-expired")

    assert response.status_code == 200
    data = response.json()
    assert data["purged"] >= 1


def test_search_cache_delete_entry_removes_specific_entry(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Delete entry should remove a specific cache entry."""
    from cc_deep_research.models import ResearchDepth, SearchOptions, SearchResult
    from cc_deep_research.search_cache import SearchCacheStore, build_search_cache_identity

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "cc-deep-research"
    config_dir.mkdir(parents=True)

    # Add an entry to the cache
    db_path = config_dir / "search-cache.sqlite3"

    # Create config with cache enabled and explicit db_path
    (config_dir / "config.yaml").write_text(
        f"search_cache:\n  enabled: true\n  ttl_seconds: 3600\n  max_entries: 1000\n  db_path: {db_path}\n",
        encoding="utf-8",
    )

    store = SearchCacheStore(db_path)
    identity = build_search_cache_identity(
        provider_name="tavily",
        query="delete test query",
        options=SearchOptions(search_depth=ResearchDepth.DEEP),
    )
    store.put(
        identity=identity,
        result=SearchResult(query="delete test query", provider="tavily"),
        ttl_seconds=3600,
    )
    cache_key = identity.to_cache_key()

    client = TestClient(create_app())
    response = client.delete(f"/api/search-cache/{cache_key}")

    assert response.status_code == 200
    data = response.json()
    assert data["deleted"] is True
    assert data["cache_key"] == cache_key

    # Verify entry is gone
    stats_response = client.get("/api/search-cache/stats")
    assert stats_response.json()["total_entries"] == 0


def test_search_cache_clear_removes_all_entries(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Clear should remove all cache entries."""
    from cc_deep_research.models import ResearchDepth, SearchOptions, SearchResult
    from cc_deep_research.search_cache import SearchCacheStore, build_search_cache_identity

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "cc-deep-research"
    config_dir.mkdir(parents=True)

    # Add multiple entries to the cache
    db_path = config_dir / "search-cache.sqlite3"

    # Create config with cache enabled and explicit db_path
    (config_dir / "config.yaml").write_text(
        f"search_cache:\n  enabled: true\n  ttl_seconds: 3600\n  max_entries: 1000\n  db_path: {db_path}\n",
        encoding="utf-8",
    )

    store = SearchCacheStore(db_path)
    for i in range(3):
        identity = build_search_cache_identity(
            provider_name="tavily",
            query=f"clear test query {i}",
            options=SearchOptions(search_depth=ResearchDepth.DEEP),
        )
        store.put(
            identity=identity,
            result=SearchResult(query=f"clear test query {i}", provider="tavily"),
            ttl_seconds=3600,
        )

    client = TestClient(create_app())
    response = client.delete("/api/search-cache")

    assert response.status_code == 200
    data = response.json()
    assert data["cleared"] == 3

    # Verify all entries are gone
    stats_response = client.get("/api/search-cache/stats")
    assert stats_response.json()["total_entries"] == 0


def test_benchmark_runs_endpoint_honors_env_override(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Benchmark run APIs should read from BENCHMARK_RUNS_DIR when it is set."""
    benchmark_runs_dir = tmp_path / "custom-benchmark-runs"
    run_dir = benchmark_runs_dir / "run-001"
    run_dir.mkdir(parents=True)

    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": "run-001",
                "corpus_version": "test-corpus",
                "generated_at": "2026-04-11T00:00:00+00:00",
                "configuration": {"mode": "smoke"},
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "scorecard.json").write_text(
        json.dumps(
            {
                "total_cases": 3,
                "average_validation_score": 0.91,
                "average_latency_ms": 1200,
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("BENCHMARK_RUNS_DIR", str(benchmark_runs_dir))

    client = TestClient(create_app())
    response = client.get("/api/benchmarks/runs")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["runs"][0]["run_id"] == "run-001"
    assert data["runs"][0]["corpus_version"] == "test-corpus"

    detail_response = client.get("/api/benchmarks/runs/run-001")
    assert detail_response.status_code == 200
    assert detail_response.json()["configuration"] == {"mode": "smoke"}


# Backlog API Tests
