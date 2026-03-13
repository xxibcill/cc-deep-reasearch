"""Tests for workflow telemetry persistence and ingestion."""

import json

import pytest

from cc_deep_research.models import QueryFamily, SearchResultItem
from cc_deep_research.monitoring import ResearchMonitor
from cc_deep_research.telemetry import (
    ingest_telemetry_to_duckdb,
    query_dashboard_data,
    query_event_tree,
    query_events_by_parent,
    query_live_agent_timeline,
    query_live_event_tail,
    query_live_event_tree,
    query_live_session_detail,
    query_live_sessions,
    query_live_subprocess_streams,
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
    monitor.record_query_variations(
        original_query="test query",
        query_families=[QueryFamily(query="q1", family="baseline", intent_tags=["baseline"])],
        strategy_intent="informational",
    )
    source = SearchResultItem(url="https://agency.gov/report", title="Report", score=1.0)
    source.add_query_provenance(query="q1", family="baseline")
    monitor.record_source_provenance(
        query_families=[QueryFamily(query="q1", family="baseline", intent_tags=["baseline"])],
        sources=[source],
        stage="initial_collection",
    )
    monitor.record_follow_up_decision(
        iteration=1,
        reason="quality_sufficient",
        follow_up_queries=[],
        quality_score=0.9,
    )
    monitor.record_iteration_stop(
        iteration=1,
        stop_reason="success",
        detail="No follow-up queries were required",
        quality_score=0.9,
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
    assert any(e["event_type"] == "query.variations" for e in lines)
    assert any(e["event_type"] == "source.provenance" for e in lines)
    assert any(e["event_type"] == "iteration.stop" for e in lines)

    assert summary["instances_spawned"] == 1
    assert summary["search_queries"] == 1
    assert summary["tool_calls"] >= 2
    assert summary["llm_total_tokens"] == 150
    assert summary["stop_reason"] == "success"


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


def test_event_correlation_fields_persisted(tmp_path):
    """Event correlation fields should be persisted to telemetry files."""
    monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=tmp_path)

    monitor.set_session("session-corr", query="test query", depth="standard")

    # Get session event ID
    session_event_id = monitor.current_parent_id

    # Emit a child event
    child_id = monitor.emit_event(
        event_type="child.event",
        category="test",
        name="child",
    )

    monitor.finalize_session(total_sources=0, providers=[], total_time_ms=100)

    events_file = tmp_path / "session-corr" / "events.jsonl"
    with open(events_file, encoding="utf-8") as f:
        events = [json.loads(line) for line in f if line.strip()]

    # All events should have event_id
    assert all(e["event_id"] is not None for e in events)

    # All events should have sequence_number
    assert all(e["sequence_number"] is not None for e in events)

    # Find child event and verify parent relationship
    child_event = next(e for e in events if e["event_id"] == child_id)
    assert child_event["parent_event_id"] == session_event_id


def test_event_ordering_by_sequence(tmp_path):
    """Events should be queryable in sequence order."""
    pytest.importorskip("duckdb")

    monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=tmp_path)
    monitor.set_session("session-seq", query="test query", depth="standard")

    # Emit multiple events
    event_ids = []
    for i in range(5):
        event_id = monitor.emit_event(
            event_type=f"event.{i}",
            category="test",
            name=f"event{i}",
        )
        event_ids.append(event_id)

    monitor.finalize_session(total_sources=0, providers=[], total_time_ms=100)

    db_path = tmp_path / "telemetry.duckdb"
    ingest_telemetry_to_duckdb(base_dir=tmp_path, db_path=db_path)

    detail = query_session_detail("session-seq", db_path=db_path)

    # Events should be ordered by sequence_number
    events = detail["events"]
    sequences = [e[2] for e in events if e[2] is not None]  # index 2 is sequence_number

    assert sequences == sorted(sequences)


def test_query_events_by_parent(tmp_path):
    """query_events_by_parent should return child events."""
    pytest.importorskip("duckdb")

    monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=tmp_path)
    monitor.set_session("session-parent", query="test query", depth="standard")

    # Session event is the parent
    session_event_id = monitor.current_parent_id

    # Emit child events
    child_ids = []
    for i in range(3):
        child_id = monitor.emit_event(
            event_type=f"child.{i}",
            category="test",
            name=f"child{i}",
        )
        child_ids.append(child_id)

    monitor.finalize_session(total_sources=0, providers=[], total_time_ms=100)

    db_path = tmp_path / "telemetry.duckdb"
    ingest_telemetry_to_duckdb(base_dir=tmp_path, db_path=db_path)

    # Query children of session event
    children = query_events_by_parent("session-parent", session_event_id, db_path=db_path)

    assert len(children) == 3
    child_event_ids = [c["event_id"] for c in children]
    assert set(child_event_ids) == set(child_ids)


def test_query_events_by_parent_root_events(tmp_path):
    """query_events_by_parent with None should return root events."""
    pytest.importorskip("duckdb")

    monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=tmp_path)
    monitor.set_session("session-root", query="test query", depth="standard")
    session_event_id = monitor.current_parent_id

    monitor.finalize_session(total_sources=0, providers=[], total_time_ms=100)

    db_path = tmp_path / "telemetry.duckdb"
    ingest_telemetry_to_duckdb(base_dir=tmp_path, db_path=db_path)

    # Query root events (no parent)
    root_events = query_events_by_parent("session-root", None, db_path=db_path)

    assert len(root_events) == 1
    assert root_events[0]["event_id"] == session_event_id


def test_query_event_tree(tmp_path):
    """query_event_tree should return hierarchical event structure."""
    pytest.importorskip("duckdb")

    monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=tmp_path)
    session_event_id = monitor.set_session("session-tree", query="test query", depth="standard")

    # Emit child events
    for i in range(3):
        monitor.emit_event(
            event_type=f"child.{i}",
            category="test",
            name=f"child{i}",
        )

    monitor.finalize_session(total_sources=0, providers=[], total_time_ms=100)

    db_path = tmp_path / "telemetry.duckdb"
    ingest_telemetry_to_duckdb(base_dir=tmp_path, db_path=db_path)

    tree = query_event_tree("session-tree", db_path=db_path)

    assert tree["total_events"] == 5  # session.started + 3 children + session.finished
    assert len(tree["root_events"]) == 1

    # Root event should be the session started event
    root = tree["root_events"][0]
    assert root["event_id"] == session_event_id

    # Root should have children
    assert len(root["children"]) >= 3


def test_backward_compatibility_missing_fields(tmp_path):
    """Dashboard queries should handle older events missing correlation fields."""
    pytest.importorskip("duckdb")

    # Create an events file with minimal fields (simulating old format)
    session_dir = tmp_path / "session-old"
    session_dir.mkdir(parents=True)
    events_file = session_dir / "events.jsonl"

    # Write event in old format (no event_id, parent_event_id, sequence_number)
    with open(events_file, "w", encoding="utf-8") as f:
        f.write(json.dumps({
            "session_id": "session-old",
            "timestamp": "2024-01-01T00:00:00Z",
            "event_type": "test.event",
            "category": "test",
            "name": "test",
            "status": "success",
            "metadata": {},
        }))
        f.write("\n")

    # Write summary file
    summary_file = session_dir / "summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump({
            "session_id": "session-old",
            "status": "completed",
            "total_sources": 0,
            "providers": [],
            "total_time_ms": 100,
        }, f)

    db_path = tmp_path / "telemetry.duckdb"
    result = ingest_telemetry_to_duckdb(base_dir=tmp_path, db_path=db_path)

    # Should not crash
    assert result["sessions"] == 1
    assert result["events"] == 1

    # Dashboard queries should still work
    data = query_dashboard_data(db_path=db_path)
    assert data["kpis"]["sessions"] == 1


def test_query_live_sessions_reports_active_run(tmp_path):
    """Live session listing should include sessions without a summary file yet."""
    monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=tmp_path)
    monitor.set_session("live-session", query="test query", depth="standard")
    monitor.emit_event(event_type="phase.started", category="phase", name="analysis", status="started")

    sessions = query_live_sessions(base_dir=tmp_path)

    assert len(sessions) == 1
    assert sessions[0]["session_id"] == "live-session"
    assert sessions[0]["active"] is True
    assert sessions[0]["status"] == "running"


def test_query_live_session_detail_returns_tail_and_phase(tmp_path):
    """Live session detail should expose event tails, agent timeline, and active phase."""
    monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=tmp_path)
    monitor.set_session("live-detail", query="test query", depth="standard")
    monitor.emit_event(event_type="phase.started", category="phase", name="analysis", status="started")
    monitor.emit_event(
        event_type="agent.started",
        category="agent",
        name="started",
        status="started",
        agent_id="analyzer-1",
    )
    monitor.emit_event(event_type="reasoning.summary", category="reasoning", name="analysis", status="recorded")

    detail = query_live_session_detail("live-detail", base_dir=tmp_path, tail_limit=2)

    assert detail["session"]["active"] is True
    assert detail["active_phase"] == "analysis"
    assert len(detail["event_tail"]) == 2
    assert len(detail["agent_timeline"]) == 1
    assert query_live_event_tail("live-detail", base_dir=tmp_path, limit=1)[0]["event_type"] == "reasoning.summary"
    assert query_live_agent_timeline("live-detail", base_dir=tmp_path)[0]["agent_id"] == "analyzer-1"
    assert query_live_event_tree("live-detail", base_dir=tmp_path)["total_events"] == 4


def test_query_live_subprocess_streams_groups_chunk_events(tmp_path):
    """Live subprocess query should group stdout/stderr chunk streams by subprocess."""
    monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=tmp_path)
    monitor.set_session("live-subprocess", query="test query", depth="standard")

    scheduled_id = monitor.emit_event(
        event_type="subprocess.scheduled",
        category="llm",
        name="claude_cli",
        status="scheduled",
        metadata={"operation": "extract_themes", "model": "claude-sonnet-4-6"},
    )
    monitor.emit_event(
        event_type="subprocess.stdout_chunk",
        category="llm",
        name="claude_cli",
        status="streaming",
        parent_event_id=scheduled_id,
        metadata={"chunk_index": 0, "content": "first\n", "content_length": 6},
    )
    monitor.emit_event(
        event_type="subprocess.stdout_chunk",
        category="llm",
        name="claude_cli",
        status="streaming",
        parent_event_id=scheduled_id,
        metadata={"chunk_index": 1, "content": "second\n", "content_length": 7},
    )
    monitor.emit_event(
        event_type="subprocess.stderr_chunk",
        category="llm",
        name="claude_cli",
        status="streaming",
        parent_event_id=scheduled_id,
        metadata={"chunk_index": 0, "content": "warn\n", "content_length": 5},
    )
    monitor.emit_event(
        event_type="subprocess.completed",
        category="llm",
        name="claude_cli",
        status="completed",
        parent_event_id=scheduled_id,
        duration_ms=125,
        metadata={"operation": "extract_themes", "exit_code": 0},
    )

    streams = query_live_subprocess_streams("live-subprocess", base_dir=tmp_path, chunk_limit=10)

    assert len(streams) == 1
    assert streams[0]["operation"] == "extract_themes"
    assert streams[0]["status"] == "completed"
    assert [chunk["content"] for chunk in streams[0]["stdout_chunks"]] == ["first\n", "second\n"]
    assert [chunk["content"] for chunk in streams[0]["stderr_chunks"]] == ["warn\n"]


def test_query_live_subprocess_streams_enforces_chunk_limit(tmp_path):
    """Live subprocess query should retain only the most recent chunks per subprocess."""
    monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=tmp_path)
    monitor.set_session("live-subprocess-limit", query="test query", depth="standard")

    scheduled_id = monitor.emit_event(
        event_type="subprocess.scheduled",
        category="llm",
        name="claude_cli",
        status="scheduled",
        metadata={"operation": "identify_gaps"},
    )
    for index in range(5):
        monitor.emit_event(
            event_type="subprocess.stdout_chunk",
            category="llm",
            name="claude_cli",
            status="streaming",
            parent_event_id=scheduled_id,
            metadata={
                "chunk_index": index,
                "content": f"chunk-{index}\n",
                "content_length": 8,
            },
        )

    streams = query_live_subprocess_streams(
        "live-subprocess-limit",
        base_dir=tmp_path,
        chunk_limit=2,
    )

    assert len(streams[0]["stdout_chunks"]) == 2
    assert streams[0]["dropped_stdout_chunks"] == 3
    assert [chunk["content"] for chunk in streams[0]["stdout_chunks"]] == ["chunk-3\n", "chunk-4\n"]
