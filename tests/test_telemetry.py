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
    query_live_llm_route_analytics,
    query_live_session_detail,
    query_live_sessions,
    query_live_subprocess_streams,
    query_session_detail,
)
from cc_deep_research.telemetry.tree import build_decision_graph


def query_live_session_detail(
    session_id: str,
    *,
    base_dir=None,
    tail_limit: int = 200,
    subprocess_chunk_limit: int = 200,
    cursor: int | None = None,
    before_cursor: int | None = None,
    limit: int | None = None,
    include_derived: bool = True,
) -> dict:
    """Helper wrapper for query_live_session_detail with derived outputs support."""
    from cc_deep_research.telemetry.live import query_live_session_detail as _query
    return _query(
        session_id,
        base_dir=base_dir,
        tail_limit=tail_limit,
        subprocess_chunk_limit=subprocess_chunk_limit,
        cursor=cursor,
        before_cursor=before_cursor,
        limit=limit,
        include_derived=include_derived,
    )


def _decision_graph_fixture_events() -> list[dict]:
    """Return a telemetry sample that exercises explicit and inferred graph links."""
    return [
        {
            "event_id": "route-request",
            "parent_event_id": None,
            "sequence_number": 1,
            "timestamp": "2026-03-20T00:00:01Z",
            "session_id": "fixture-session",
            "event_type": "llm.route_request",
            "category": "llm",
            "name": "route-request",
            "status": "started",
            "severity": "info",
            "reason_code": None,
            "phase": "analysis",
            "actor_id": "analyzer",
            "agent_id": "analyzer",
            "metadata": {"operation": "analysis"},
        },
        {
            "event_id": "route-decision",
            "parent_event_id": None,
            "sequence_number": 2,
            "timestamp": "2026-03-20T00:00:02Z",
            "session_id": "fixture-session",
            "event_type": "decision.made",
            "category": "decision",
            "name": "routing",
            "status": "decided",
            "severity": "info",
            "reason_code": "route_selected",
            "phase": "analysis",
            "actor_id": "analyzer",
            "agent_id": "analyzer",
            "metadata": {
                "decision_type": "routing",
                "chosen_option": "openrouter_api",
                "rejected_options": ["anthropic_api", "cerebras_api"],
                "inputs": {"operation": "analysis"},
                "cause_event_ids": ["route-request"],
                "confidence": 0.81,
            },
        },
        {
            "event_id": "route-state-change",
            "parent_event_id": None,
            "sequence_number": 3,
            "timestamp": "2026-03-20T00:00:03Z",
            "session_id": "fixture-session",
            "event_type": "state.changed",
            "category": "state",
            "name": "session.llm_route",
            "status": "changed",
            "severity": "info",
            "reason_code": None,
            "phase": "analysis",
            "actor_id": None,
            "agent_id": None,
            "metadata": {
                "state_scope": "session",
                "state_key": "llm_route",
                "before": "anthropic_api",
                "after": "openrouter_api",
                "change_type": "update",
                "caused_by_event_id": "route-decision",
            },
        },
        {
            "event_id": "transport-degradation",
            "parent_event_id": None,
            "sequence_number": 4,
            "timestamp": "2026-03-20T00:00:04Z",
            "session_id": "fixture-session",
            "event_type": "degradation.detected",
            "category": "execution",
            "name": "transport-fallback",
            "status": "degraded",
            "severity": "warning",
            "reason_code": "fallback",
            "phase": "analysis",
            "actor_id": "analyzer",
            "agent_id": "analyzer",
            "cause_event_id": "route-request",
            "metadata": {
                "reason_code": "fallback",
                "scope": "transport",
                "recoverable": True,
                "mitigation": "Switched routes",
                "impact": "Lower priority provider selected",
            },
        },
        {
            "event_id": "transport-failure",
            "parent_event_id": None,
            "sequence_number": 5,
            "timestamp": "2026-03-20T00:00:05Z",
            "session_id": "fixture-session",
            "event_type": "llm.route_failed",
            "category": "llm",
            "name": "route-failed",
            "status": "failed",
            "severity": "error",
            "reason_code": "transport_error",
            "phase": "analysis",
            "actor_id": "analyzer",
            "agent_id": "analyzer",
            "cause_event_id": "route-request",
            "metadata": {"error": "primary provider unavailable", "recoverable": True},
        },
    ]


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
    # Events are now normalized dicts, not raw tuples
    sequences = [e.get("sequence_number") for e in events if e.get("sequence_number") is not None]

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


def test_query_live_event_tail_normalizes_legacy_event_shape(tmp_path):
    """Live tail queries should fill required fields for legacy event records."""
    session_dir = tmp_path / "legacy-live"
    session_dir.mkdir(parents=True)
    events_file = session_dir / "events.jsonl"
    with open(events_file, "w", encoding="utf-8") as f:
        f.write(json.dumps({
            "timestamp": "2024-01-01T00:00:00Z",
            "event_type": "legacy.event",
            "category": "legacy",
            "name": "event",
            "metadata": [],
        }))
        f.write("\n")

    event = query_live_event_tail("legacy-live", base_dir=tmp_path, limit=1)[0]

    assert event["event_id"] == "legacy-live-event-1"
    assert event["sequence_number"] == 1
    assert event["session_id"] == "legacy-live"
    assert event["status"] == "unknown"
    assert event["metadata"] == {}


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
        name="anthropic_api",
        status="scheduled",
        metadata={"operation": "extract_themes", "model": "claude-sonnet-4-6"},
    )
    monitor.emit_event(
        event_type="subprocess.stdout_chunk",
        category="llm",
        name="anthropic_api",
        status="streaming",
        parent_event_id=scheduled_id,
        metadata={"chunk_index": 0, "content": "first\n", "content_length": 6},
    )
    monitor.emit_event(
        event_type="subprocess.stdout_chunk",
        category="llm",
        name="anthropic_api",
        status="streaming",
        parent_event_id=scheduled_id,
        metadata={"chunk_index": 1, "content": "second\n", "content_length": 7},
    )
    monitor.emit_event(
        event_type="subprocess.stderr_chunk",
        category="llm",
        name="anthropic_api",
        status="streaming",
        parent_event_id=scheduled_id,
        metadata={"chunk_index": 0, "content": "warn\n", "content_length": 5},
    )
    monitor.emit_event(
        event_type="subprocess.completed",
        category="llm",
        name="anthropic_api",
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
        name="anthropic_api",
        status="scheduled",
        metadata={"operation": "identify_gaps"},
    )
    for index in range(5):
        monitor.emit_event(
            event_type="subprocess.stdout_chunk",
            category="llm",
            name="anthropic_api",
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


def test_query_live_llm_route_analytics(tmp_path):
    """Live LLM route analytics should aggregate route events by transport and provider."""
    from cc_deep_research.telemetry import query_live_llm_route_analytics

    monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=tmp_path)
    monitor.set_session("live-llm-route", query="test query", depth="standard")

    # Record route selections
    monitor.record_llm_route_selected(
        agent_id="analyzer",
        transport="openrouter_api",
        provider="openrouter",
        model="claude-sonnet-4-6",
        source="planner",
    )
    monitor.record_llm_route_selected(
        agent_id="validator",
        transport="cerebras_api",
        provider="cerebras",
        model="llama-3.3-70b",
        source="planner",
    )

    # Record route completions
    monitor.record_llm_route_completion(
        agent_id="analyzer",
        transport="openrouter_api",
        provider="openrouter",
        model="claude-sonnet-4-6",
        operation="analyze",
        duration_ms=1500,
        success=True,
        prompt_tokens=1000,
        completion_tokens=500,
    )
    monitor.record_llm_route_completion(
        agent_id="analyzer",
        transport="openrouter_api",
        provider="openrouter",
        model="claude-sonnet-4-6",
        operation="analyze",
        duration_ms=1200,
        success=True,
        prompt_tokens=500,
        completion_tokens=300,
    )
    # Record fallback
    monitor.record_llm_route_fallback(
        agent_id="researcher",
        original_transport="anthropic_api",
        fallback_transport="openrouter_api",
        reason="timeout",
    )

    monitor.finalize_session(total_sources=10, providers=["tavily"], total_time_ms=5000)

    # Query analytics
    analytics = query_live_llm_route_analytics("live-llm-route", base_dir=tmp_path)

    assert analytics["total_requests"] == 2
    assert analytics["fallback_count"] == 1
    assert "openrouter_api" in analytics["transport_summary"]
    assert analytics["transport_summary"]["openrouter_api"]["requests"] == 2
    assert analytics["transport_summary"]["openrouter_api"]["tokens"] == 2300
    assert "analyzer" in analytics["agent_summary"]
    assert analytics["agent_summary"]["analyzer"]["requests"] == 2
    assert analytics["agent_summary"]["analyzer"]["tokens"] == 2300
    assert analytics["agent_summary"]["analyzer"]["transports"] == ["openrouter_api"]
    assert "analyzer" in analytics["planned_routes"]
    assert analytics["planned_routes"]["analyzer"]["transport"] == "openrouter_api"
    assert analytics["planned_routes"]["validator"]["transport"] == "cerebras_api"
    assert len(analytics["route_fallbacks"]) == 1


def test_query_live_session_detail_includes_llm_route_analytics(tmp_path):
    """Live session detail should include LLM route analytics."""
    monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=tmp_path)
    monitor.set_session("live-llm-detail", query="test query", depth="standard")

    monitor.record_llm_route_completion(
        agent_id="analyzer",
        transport="openrouter_api",
        provider="openrouter",
        model="claude-sonnet-4-6",
        operation="analyze",
        duration_ms=1500,
        success=True,
        prompt_tokens=1000,
        completion_tokens=500,
    )

    detail = query_live_session_detail("live-llm-detail", base_dir=tmp_path)

    assert "llm_route_analytics" in detail
    assert detail["llm_route_analytics"]["total_requests"] == 1
    assert detail["llm_route_analytics"]["transport_summary"]["openrouter_api"]["requests"] == 1


# =============================================================================
# Task 002: Derived Outputs Tests
# =============================================================================


def test_query_live_session_detail_includes_derived_outputs(tmp_path):
    """Live session detail should include derived operator-facing summaries."""
    monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=tmp_path)
    monitor.set_session("derived-session", query="test query", depth="standard")

    # Emit events that should appear in narrative
    monitor.emit_event(event_type="phase.started", category="phase", name="analysis", status="started")
    monitor.emit_event(
        event_type="agent.spawned",
        category="agent",
        name="spawned",
        status="started",
        agent_id="analyzer-1",
    )

    # Emit a decision event
    monitor.emit_event(
        event_type="decision.made",
        category="planning",
        name="route_decision",
        metadata={
            "decision_type": "routing",
            "chosen_option": "openrouter_api",
            "inputs": {"query": "test"},
        },
    )

    # Emit a state change event
    monitor.emit_event(
        event_type="state.changed",
        category="session",
        name="state_change",
        metadata={
            "state_scope": "session",
            "state_key": "phase",
            "before": "planning",
            "after": "analysis",
            "change_type": "phase_transition",
        },
    )

    # Emit a degradation event
    monitor.emit_event(
        event_type="degradation.detected",
        category="execution",
        name="slow_response",
        status="degraded",
        severity="warning",
        metadata={
            "reason_code": "high_latency",
            "scope": "llm",
            "recoverable": True,
        },
    )

    # Emit a failure event
    monitor.emit_event(
        event_type="tool.failed",
        category="tool",
        name="search_failed",
        status="failed",
        severity="error",
        metadata={"error": "Rate limit exceeded"},
    )

    monitor.finalize_session(total_sources=5, providers=["tavily"], total_time_ms=1000)

    detail = query_live_session_detail("derived-session", base_dir=tmp_path, include_derived=True)

    # Check derived outputs are present
    assert "narrative" in detail
    assert "critical_path" in detail
    assert "state_changes" in detail
    assert "decisions" in detail
    assert "degradations" in detail
    assert "failures" in detail
    assert "decision_graph" in detail

    # Check narrative includes key events
    narrative = detail["narrative"]
    narrative_types = {e.get("event_type") for e in narrative}
    assert "phase.started" in narrative_types

    # Check decisions are captured
    decisions = detail["decisions"]
    assert len(decisions) >= 1
    assert any(d.get("decision_type") == "routing" for d in decisions)

    # Check state changes are captured
    state_changes = detail["state_changes"]
    assert len(state_changes) >= 1

    # Check degradations are captured
    degradations = detail["degradations"]
    assert len(degradations) >= 1
    assert any(d.get("reason_code") == "high_latency" for d in degradations)

    # Check failures are captured
    failures = detail["failures"]
    assert len(failures) >= 1
    assert any(f.get("severity") == "error" for f in failures)
    assert detail["decision_graph"]["summary"]["node_count"] >= 1


def test_query_live_session_detail_can_disable_derived(tmp_path):
    """Live session detail should support disabling derived outputs for performance."""
    monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=tmp_path)
    monitor.set_session("no-derived", query="test", depth="quick")
    monitor.finalize_session(total_sources=0, providers=[], total_time_ms=100)

    detail = query_live_session_detail("no-derived", base_dir=tmp_path, include_derived=False)

    # Derived outputs should be empty when disabled
    assert detail.get("narrative") == []
    assert detail.get("critical_path") == {}
    assert detail.get("decisions") == []
    assert detail.get("decision_graph") == {
        "nodes": [],
        "edges": [],
        "summary": {
            "node_count": 0,
            "edge_count": 0,
            "explicit_edge_count": 0,
            "inferred_edge_count": 0,
        },
    }


def test_build_decision_graph_preserves_explicit_and_inferred_links():
    """Decision graph derivation should keep explicit links separate from inferred domain edges."""
    graph = build_decision_graph(_decision_graph_fixture_events())

    assert graph["summary"] == {
        "node_count": 8,
        "edge_count": 9,
        "explicit_edge_count": 7,
        "inferred_edge_count": 2,
    }
    assert {node["kind"] for node in graph["nodes"]} == {
        "decision",
        "state_change",
        "degradation",
        "failure",
        "event",
        "outcome",
    }

    explicit_edges = {
        (edge["source"], edge["target"], edge["kind"])
        for edge in graph["edges"]
        if not edge["inferred"]
    }
    inferred_edges = {
        (edge["source"], edge["target"], edge["kind"])
        for edge in graph["edges"]
        if edge["inferred"]
    }
    assert (
        "decision:route-decision",
        "event:route-request",
        "caused_by",
    ) in explicit_edges
    assert (
        "decision:route-decision",
        "outcome:route-decision:chosen",
        "produced",
    ) in explicit_edges
    assert (
        "decision:route-decision",
        "outcome:route-decision:rejected:0:anthropic_api",
        "rejected",
    ) in explicit_edges
    assert (
        "decision:route-decision",
        "state_change:route-state-change",
        "produced",
    ) in inferred_edges
    assert (
        "degradation:transport-degradation",
        "failure:transport-failure",
        "led_to",
    ) in inferred_edges


def test_build_decision_graph_returns_stable_empty_shape():
    """Empty sessions should return a JSON-safe graph payload instead of null."""
    assert build_decision_graph([]) == {
        "nodes": [],
        "edges": [],
        "summary": {
            "node_count": 0,
            "edge_count": 0,
            "explicit_edge_count": 0,
            "inferred_edge_count": 0,
        },
    }


def test_query_live_session_detail_cursor_pagination(tmp_path):
    """Live session detail should support cursor-based pagination for events."""
    monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=tmp_path)
    monitor.set_session("paged-session", query="test", depth="standard")

    # Emit many events with explicit sequence numbers
    for i in range(10):
        monitor.emit_event(
            event_type=f"event.{i}",
            category="test",
            name=f"event{i}",
        )

    monitor.finalize_session(total_sources=0, providers=[], total_time_ms=100)

    # Get first page
    detail = query_live_session_detail(
        "paged-session",
        base_dir=tmp_path,
        limit=5,
        cursor=None,
        include_derived=False,
    )

    events_page = detail.get("events_page", {})
    assert "events" in events_page
    assert len(events_page["events"]) == 5
    assert events_page["total"] >= 10
    assert events_page["has_more"] is True
    assert events_page["next_cursor"] is not None

    # Get next page using cursor
    next_cursor = events_page["next_cursor"]
    detail2 = query_live_session_detail(
        "paged-session",
        base_dir=tmp_path,
        limit=5,
        cursor=next_cursor,
        include_derived=False,
    )

    events_page2 = detail2.get("events_page", {})
    assert len(events_page2["events"]) >= 1
    # Verify events are different from first page
    first_page_ids = {e.get("event_id") for e in events_page["events"]}
    second_page_ids = {e.get("event_id") for e in events_page2["events"]}
    assert first_page_ids.isdisjoint(second_page_ids)


def test_query_session_detail_historical_includes_derived(tmp_path):
    """Historical session detail from DuckDB should include derived outputs."""
    pytest.importorskip("duckdb")

    monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=tmp_path)
    monitor.set_session("historical-derived", query="test query", depth="standard")

    monitor.emit_event(event_type="phase.started", category="phase", name="analysis", status="started")
    monitor.emit_event(
        event_type="decision.made",
        category="planning",
        name="decision",
        metadata={"decision_type": "strategy", "chosen_option": "deep"},
    )
    monitor.emit_event(
        event_type="degradation.detected",
        category="execution",
        name="degraded",
        status="degraded",
        severity="warning",
        metadata={"reason_code": "partial_failure", "scope": "search"},
    )

    monitor.finalize_session(total_sources=5, providers=["tavily"], total_time_ms=1000)

    # Ingest to DuckDB
    db_path = tmp_path / "telemetry.duckdb"
    ingest_telemetry_to_duckdb(base_dir=tmp_path, db_path=db_path)

    # Remove live files to force historical query
    import shutil
    shutil.rmtree(tmp_path / "historical-derived")

    # Query historical detail
    from cc_deep_research.telemetry import query_session_detail

    detail = query_session_detail(
        "historical-derived",
        db_path=db_path,
        include_derived=True,
    )

    # Check derived outputs
    assert "narrative" in detail
    assert "decisions" in detail
    assert "degradations" in detail
    assert "decision_graph" in detail
    assert len(detail["decisions"]) >= 1
    assert len(detail["degradations"]) >= 1
    assert detail["decision_graph"]["summary"]["node_count"] >= 1


def test_query_session_detail_cursor_pagination_historical(tmp_path):
    """Historical session detail should support cursor-based pagination."""
    pytest.importorskip("duckdb")

    monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=tmp_path)
    monitor.set_session("historical-paged", query="test", depth="standard")

    for i in range(15):
        monitor.emit_event(
            event_type=f"event.{i}",
            category="test",
            name=f"event{i}",
        )

    monitor.finalize_session(total_sources=0, providers=[], total_time_ms=100)

    # Ingest to DuckDB
    db_path = tmp_path / "telemetry.duckdb"
    ingest_telemetry_to_duckdb(base_dir=tmp_path, db_path=db_path)

    # Remove live files
    import shutil
    shutil.rmtree(tmp_path / "historical-paged")

    from cc_deep_research.telemetry import query_session_detail

    # Query with limit
    detail = query_session_detail(
        "historical-paged",
        db_path=db_path,
        limit=5,
        include_derived=False,
    )

    events_page = detail.get("events_page", {})
    assert len(events_page.get("events", [])) <= 5
    assert events_page.get("has_more") is True
