"""Tests for FastAPI dashboard runtime state."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from cc_deep_research.web_server import (
    create_app,
)
from cc_deep_research.web_server_routes import misc_routes


def test_promoted_baseline_route_is_not_shadowed(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The promoted-baseline endpoint should not route as a baseline id."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    client = TestClient(create_app())
    response = client.get("/api/benchmarks/baselines/promoted")

    assert response.status_code == 200
    assert response.json() == {"baseline": None}


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
    config_dir = tmp_path / "xdg" / "inqulume-studio"
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
    config_dir = tmp_path / "xdg" / "inqulume-studio"
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
    config_dir = tmp_path / "xdg" / "inqulume-studio"
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
    config_dir = tmp_path / "xdg" / "inqulume-studio"
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


def test_search_cache_clear_removes_all_entries(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear should remove all cache entries."""
    from cc_deep_research.models import ResearchDepth, SearchOptions, SearchResult
    from cc_deep_research.search_cache import SearchCacheStore, build_search_cache_identity

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "inqulume-studio"
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


def test_benchmark_run_returns_background_job(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Benchmark runs should return immediately with a pollable background job."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("BENCHMARK_RUNS_DIR", str(tmp_path / "benchmark-runs"))

    def fail_if_inline(*_args, **_kwargs):
        raise AssertionError("benchmark execution should not happen inside the request")

    monkeypatch.setattr(
        "cc_deep_research.web_server_routes.misc_routes.run_benchmark_corpus_sync",
        fail_if_inline,
    )

    with TestClient(create_app()) as client:
        response = client.post("/api/benchmarks/run?workflow_mode=staged&depth=standard")

        assert response.status_code == 202
        payload = response.json()
        assert payload["kind"] == "benchmark.run"
        assert payload["status_url"] == f"/api/jobs/{payload['job_id']}"

        status_response = client.get(payload["status_url"])
        assert status_response.status_code == 200
        status_payload = status_response.json()
        assert status_payload["job_id"] == payload["job_id"]
        assert status_payload["kind"] == "benchmark.run"


def test_knowledge_long_running_routes_return_background_jobs(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Knowledge backfill and rebuild should be scheduled as background jobs."""
    from cc_deep_research.knowledge.vault import init_vault
    from cc_deep_research.session_store import get_default_session_dir

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    sessions_dir = get_default_session_dir()
    sessions_dir.mkdir(parents=True)
    (sessions_dir / "session-123.json").write_text("{}", encoding="utf-8")
    init_vault()

    with TestClient(create_app()) as client:
        backfill_response = client.post("/api/knowledge/backfill?limit=1")
        rebuild_response = client.post("/api/knowledge/rebuild-index")

        assert backfill_response.status_code == 202
        assert rebuild_response.status_code == 202

        backfill_payload = backfill_response.json()
        rebuild_payload = rebuild_response.json()
        assert backfill_payload["kind"] == "knowledge.backfill"
        assert rebuild_payload["kind"] == "knowledge.rebuild_index"

        backfill_status = client.get(backfill_payload["status_url"])
        rebuild_status = client.get(rebuild_payload["status_url"])
        assert backfill_status.status_code == 200
        assert rebuild_status.status_code == 200


def test_analytics_counts_archived_sessions_from_single_saved_summary_scan(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Analytics should not rescan saved-session summaries for archive counts."""
    db_path = tmp_path / "dashboard.duckdb"
    db_path.touch()
    query_day = datetime(2026, 6, 1, tzinfo=UTC)

    class FakeResult:
        def __init__(self, rows: list[tuple[object, ...]]):
            self._rows = rows

        def fetchone(self) -> tuple[object, ...] | None:
            return self._rows[0] if self._rows else None

        def fetchall(self) -> list[tuple[object, ...]]:
            return self._rows

    class FakeConnection:
        def __init__(self) -> None:
            self.execute_count = 0
            self.closed = False

        def execute(self, _query: str, _params: list[int]) -> FakeResult:
            self.execute_count += 1
            match self.execute_count:
                case 1:
                    return FakeResult([(3, 2, 1, 0, 1200.0, 5.0)])
                case 2:
                    return FakeResult([(2,)])
                case 3:
                    return FakeResult([("completed", 2), ("failed", 1)])
                case 4:
                    return FakeResult([("completed", 1200.0, 900, 1500, 2)])
                case 5:
                    return FakeResult([(query_day, 3, 5.0, 15)])
                case 6:
                    return FakeResult([(query_day, 3, 2, 1, 0)])
                case 7:
                    return FakeResult([("standard", 3, 1200.0)])
            raise AssertionError(f"unexpected analytics query #{self.execute_count}")

        def close(self) -> None:
            self.closed = True

    class FakeSessionStore:
        def __init__(self) -> None:
            self.list_sessions_calls = 0

        def list_sessions(self) -> list[dict[str, object]]:
            self.list_sessions_calls += 1
            return [
                {"session_id": "active-session", "archived": False},
                {"session_id": "archived-session", "archived": True},
            ]

        def get_archived_session_ids(self) -> set[str]:
            raise AssertionError("archive count should use the loaded saved-session summaries")

    connection = FakeConnection()
    session_store = FakeSessionStore()
    monkeypatch.setattr(misc_routes, "_load_dashboard_connection", lambda _path: connection)
    monkeypatch.setattr(misc_routes, "SessionStore", lambda: session_store)

    analytics = misc_routes._query_analytics_data(db_path=db_path)

    assert analytics["summary"]["archived_sessions"] == 1
    assert analytics["summary"]["active_sessions"] == 1
    assert session_store.list_sessions_calls == 1
    assert connection.closed is True


# Backlog API Tests
