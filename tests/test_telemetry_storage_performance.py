"""Storage performance gates for telemetry ingestion and queries."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from cc_deep_research.telemetry import ingest_telemetry_to_duckdb, query_session_detail


def _write_events_for_size(session_dir: Path, session_id: str, count: int, extra_metadata: bool = False) -> None:
    """Write events.jsonl with specified number of events.

    Args:
        session_dir: Session directory.
        session_id: Session ID.
        count: Number of events to write.
        extra_metadata: If True, include extra metadata fields to increase event size.
    """
    events = []
    for i in range(count):
        event = {
            "event_id": f"{session_id}-evt-{i}",
            "session_id": session_id,
            "sequence_number": i,
            "timestamp": "2026-01-01T00:00:00Z",
            "event_type": "test.event",
            "category": "test",
            "name": f"evt{i}",
            "status": "info",
            "metadata": {
                "key": f"value_{i}",
                "nested": {"a": i, "b": str(i)},
            },
        }
        if extra_metadata:
            event["parent_event_id"] = f"{session_id}-evt-{i - 1}" if i > 0 else None
            event["agent_id"] = f"agent-{i % 3}"
            event["duration_ms"] = (i * 10) % 500
            event["metadata"]["extra_data"] = "x" * 100
        events.append(json.dumps(event))

    (session_dir / "events.jsonl").write_text("\n".join(events) + "\n")


def _write_summary(session_dir: Path, session_id: str, providers: list[str] | None = None) -> None:
    """Write a summary.json file."""
    (session_dir / "summary.json").write_text(
        json.dumps({
            "session_id": session_id,
            "status": "completed",
            "total_sources": 5,
            "providers": providers or ["tavily", "openrouter"],
            "total_time_ms": 5000,
            "search_queries": 10,
            "tool_calls": 25,
            "llm_prompt_tokens": 15000,
            "llm_completion_tokens": 8000,
            "llm_total_tokens": 23000,
            "created_at": "2026-01-01T00:00:00Z",
        })
    )


def _time_it(fn, *args, **kwargs):
    """Time a function call and return (result, elapsed_seconds)."""
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    elapsed = time.perf_counter() - start
    return result, elapsed


# ─────────────────────────────────────────────────────────────────────────────
# Small dataset benchmarks (10 sessions, 50 events each)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.slow
def test_ingest_small_dataset(tmp_path):
    """Ingest 10 sessions with 50 events each - should be fast."""
    for i in range(10):
        session_dir = tmp_path / f"small-session-{i}"
        session_dir.mkdir()
        _write_events_for_size(session_dir, f"small-session-{i}", count=50)
        _write_summary(session_dir, f"small-session-{i}")

    db_path = tmp_path / "small.duckdb"
    _, elapsed = _time_it(ingest_telemetry_to_duckdb, tmp_path, db_path)

    assert elapsed < 5.0, f"Small dataset ingestion took {elapsed:.2f}s, expected <5s"
    assert db_path.exists()


@pytest.mark.slow
def test_query_session_list_small_dataset(tmp_path):
    """Session list query should return quickly for small dataset."""
    for i in range(10):
        session_dir = tmp_path / f"list-session-{i}"
        session_dir.mkdir()
        _write_events_for_size(session_dir, f"list-session-{i}", count=50)
        _write_summary(session_dir, f"list-session-{i}")

    db_path = tmp_path / "small.duckdb"
    ingest_telemetry_to_duckdb(tmp_path, db_path)

    from cc_deep_research.telemetry import query_session_summaries

    _, elapsed = _time_it(query_session_summaries, db_path=db_path)
    assert elapsed < 1.0, f"Session list query took {elapsed:.2f}s, expected <1s"


# ─────────────────────────────────────────────────────────────────────────────
# Medium dataset benchmarks (25 sessions, 200 events each)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.slow
def test_ingest_medium_dataset(tmp_path):
    """Ingest 25 sessions with 200 events each."""
    for i in range(25):
        session_dir = tmp_path / f"medium-session-{i}"
        session_dir.mkdir()
        _write_events_for_size(session_dir, f"medium-session-{i}", count=200)
        _write_summary(session_dir, f"medium-session-{i}")

    db_path = tmp_path / "medium.duckdb"
    _, elapsed = _time_it(ingest_telemetry_to_duckdb, tmp_path, db_path)

    assert elapsed < 20.0, f"Medium dataset ingestion took {elapsed:.2f}s, expected <20s"


@pytest.mark.slow
def test_query_session_detail_first_page_medium(tmp_path):
    """Session detail first page should be fast on medium dataset."""
    for i in range(25):
        session_dir = tmp_path / f"medium-detail-{i}"
        session_dir.mkdir()
        _write_events_for_size(session_dir, f"medium-detail-{i}", count=200)
        _write_summary(session_dir, f"medium-detail-{i}")

    db_path = tmp_path / "medium.duckdb"
    ingest_telemetry_to_duckdb(tmp_path, db_path)

    _, elapsed = _time_it(query_session_detail, "medium-detail-0", db_path=db_path, limit=50)
    assert elapsed < 2.0, f"Medium session detail (limit=50) took {elapsed:.2f}s, expected <2s"


# ─────────────────────────────────────────────────────────────────────────────
# Large dataset benchmarks (10 sessions, 500 events each) - regression gates
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.slow
def test_ingest_large_dataset(tmp_path):
    """Ingest 10 sessions with 500 events each - regression gate."""
    for i in range(10):
        session_dir = tmp_path / f"large-session-{i}"
        session_dir.mkdir()
        _write_events_for_size(session_dir, f"large-session-{i}", count=500, extra_metadata=True)
        _write_summary(session_dir, f"large-session-{i}")

    db_path = tmp_path / "large.duckdb"
    _, elapsed = _time_it(ingest_telemetry_to_duckdb, tmp_path, db_path)

    # Large dataset ingestion should complete in reasonable time
    assert elapsed < 60.0, f"Large dataset ingestion took {elapsed:.2f}s, expected <60s (baseline)"


@pytest.mark.slow
def test_query_large_session_paginated_detail(tmp_path):
    """Paginated query for large session should use LIMIT not full scan."""
    for i in range(10):
        session_dir = tmp_path / f"large-paged-{i}"
        session_dir.mkdir()
        _write_events_for_size(session_dir, f"large-paged-{i}", count=500)
        _write_summary(session_dir, f"large-paged-{i}")

    db_path = tmp_path / "large.duckdb"
    ingest_telemetry_to_duckdb(tmp_path, db_path)

    # Query with small limit - should use index and LIMIT, not load all 500 events
    _, elapsed = _time_it(query_session_detail, "large-paged-0", db_path=db_path, limit=10)
    assert elapsed < 2.0, f"Paginated large session (limit=10) took {elapsed:.2f}s, expected <2s"

    # Verify pagination metadata
    result, _ = _time_it(query_session_detail, "large-paged-0", db_path=db_path, limit=10)
    events_page = result.get("events_page", {})
    assert events_page.get("total", 0) >= 500, "Paginated query should know total count"
    assert events_page.get("has_more") is True, "Should have more events"
    assert len(events_page.get("events", [])) <= 10, "Should return at most limit events"


@pytest.mark.slow
def test_derived_summary_read_performance(tmp_path):
    """Cached derived summary read should be fast compared to full rebuild."""
    # Set up a session with many events
    session_dir = tmp_path / "summary-perf"
    session_dir.mkdir()
    _write_events_for_size(session_dir, "summary-perf", count=200)
    _write_summary(session_dir, "summary-perf")

    # First call - computes and caches
    from cc_deep_research.telemetry import get_or_compute_summary

    events_file = session_dir / "events.jsonl"
    events = []
    with open(events_file) as f:
        for line in f:
            if line.strip():
                e = json.loads(line)
                e["timestamp"] = "2026-01-01T00:00:00Z"
                e["status"] = "info"
                e["severity"] = "info"
                e["phase"] = "session"
                e["operation"] = e["name"]
                e["actor_type"] = "system"
                e["actor_id"] = None
                e["degraded"] = False
                e["trace_version"] = "0"
                e["run_id"] = None
                e["cause_event_id"] = None
                e["reason_code"] = None
                events.append(e)

    # First call computes and saves
    _, first_elapsed = _time_it(get_or_compute_summary, events, "summary-perf", session_dir)
    assert first_elapsed < 5.0, f"First summary compute took {first_elapsed:.2f}s, expected <5s"

    # Second call - should be cached and fast
    _, cached_elapsed = _time_it(get_or_compute_summary, events, "summary-perf", session_dir)
    assert cached_elapsed < 0.5, f"Cached summary read took {cached_elapsed:.2f}s, expected <0.5s"


# ─────────────────────────────────────────────────────────────────────────────
# Compaction / archive dry-run performance
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.slow
def test_retention_dry_run_performance(tmp_path):
    """Retention dry-run on 50 sessions should complete quickly."""
    # Create 50 sessions with varying ages
    for i in range(50):
        session_dir = tmp_path / f"retention-session-{i}"
        session_dir.mkdir()
        _write_events_for_size(session_dir, f"retention-session-{i}", count=50)
        _write_summary(session_dir, f"retention-session-{i}")

    from cc_deep_research.telemetry import RetentionPolicy, evaluate_retention_candidates

    policy = RetentionPolicy(max_age_days=90)
    _, elapsed = _time_it(evaluate_retention_candidates, policy, tmp_path)

    assert elapsed < 10.0, f"Retention evaluation on 50 sessions took {elapsed:.2f}s, expected <10s"


# ─────────────────────────────────────────────────────────────────────────────
# CI-friendly subset (skipped in normal runs, enabled with -m slow)
# ─────────────────────────────────────────────────────────────────────────────

pytestmark = pytest.mark.slow
