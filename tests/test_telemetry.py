"""Tests for workflow telemetry persistence and ingestion."""

import json

import pytest

from cc_deep_research.monitoring import ResearchMonitor
from cc_deep_research.telemetry import (
    ingest_telemetry_to_duckdb,
    query_dashboard_data,
    query_session_detail,
)


def test_monitor_persists_session_logs(tmp_path):
    """Monitor should persist events.jsonl and summary.json per session."""
    monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=tmp_path)

    monitor.set_session("session-1", query="test query", depth="deep")
    monitor.log_researcher_event("spawned", "task-1", query="q1")
    monitor.record_search_query(
        query="q1",
        provider="tavily",
        result_count=3,
        duration_ms=120,
        status="success",
    )
    monitor.record_tool_call("tavily.search", "success", 120, query="q1")
    monitor.record_llm_usage(
        operation="extract_themes",
        model="claude-sonnet-4-6",
        prompt_tokens=100,
        completion_tokens=50,
        duration_ms=250,
    )

    summary = monitor.finalize_session(
        total_sources=3,
        providers=["tavily"],
        total_time_ms=2000,
    )

    events_file = tmp_path / "session-1" / "events.jsonl"
    summary_file = tmp_path / "session-1" / "summary.json"

    assert events_file.exists()
    assert summary_file.exists()

    with open(events_file, encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]

    assert any(e["event_type"] == "session.started" for e in lines)
    assert any(e["event_type"] == "search.query" for e in lines)
    assert any(e["event_type"] == "llm.usage" for e in lines)

    assert summary["instances_spawned"] == 1
    assert summary["search_queries"] == 1
    assert summary["tool_calls"] >= 2
    assert summary["llm_total_tokens"] == 150


def test_ingest_and_query_dashboard_data(tmp_path):
    """Telemetry files should be ingestible into DuckDB for dashboard use."""
    pytest.importorskip("duckdb")

    monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=tmp_path)
    monitor.set_session("session-2", query="test query", depth="quick")
    monitor.record_search_query(
        query="q2",
        provider="tavily",
        result_count=1,
        duration_ms=50,
        status="success",
    )
    monitor.record_tool_call("tavily.search", "success", 50)
    monitor.finalize_session(total_sources=1, providers=["tavily"], total_time_ms=500)

    db_path = tmp_path / "telemetry.duckdb"
    result = ingest_telemetry_to_duckdb(base_dir=tmp_path, db_path=db_path)

    assert result["sessions"] == 1
    assert result["events"] > 0

    data = query_dashboard_data(db_path=db_path)
    assert data["kpis"]["sessions"] == 1
    assert len(data["sessions"]) == 1

    detail = query_session_detail("session-2", db_path=db_path)
    assert detail["session"] is not None
    assert len(detail["events"]) > 0
    assert len(detail["tool_calls"]) >= 1
