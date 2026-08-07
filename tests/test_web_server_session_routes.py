"""Tests for FastAPI dashboard runtime state."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cc_deep_research.config import Config
from cc_deep_research.models import ResearchDepth, ResearchSession
from cc_deep_research.monitoring import ResearchMonitor
from cc_deep_research.research_runs import (
    ResearchOutputFormat,
)
from cc_deep_research.research_runs.jobs import ResearchRunJobRegistry
from cc_deep_research.research_runs.models import (
    MAX_BULK_DELETE_SESSION_IDS,
    BulkSessionDeleteRequest,
    ResearchRunRequest,
    ResearchWorkflow,
)
from cc_deep_research.research_runs.resume import (
    ResearchResumePhase,
    ResearchResumeState,
    ResearchResumeStore,
    build_config_fingerprint,
)
from cc_deep_research.research_runs.service import ResearchRunService
from cc_deep_research.session_store import SessionStore
from cc_deep_research.telemetry import ingest_telemetry_to_duckdb
from cc_deep_research.web_server import (
    create_app,
)


def test_bulk_delete_request_normalizes_duplicate_session_ids() -> None:
    """The bulk delete request should trim ids and keep first-seen order only once."""
    request = BulkSessionDeleteRequest(
        session_ids=["  session-a  ", "session-b", "session-a", "session-b", "session-c"],
    )

    assert request.session_ids == ["session-a", "session-b", "session-c"]


def test_bulk_delete_request_rejects_oversized_batches() -> None:
    """The bulk delete contract should enforce a conservative batch-size limit."""
    oversized_ids = [f"session-{index}" for index in range(MAX_BULK_DELETE_SESSION_IDS + 1)]

    with pytest.raises(ValueError, match="bulk delete is limited"):
        BulkSessionDeleteRequest(session_ids=oversized_ids)


def test_purge_summary_route_is_not_shadowed(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The static purge-summary endpoint should not route as a session id."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    client = TestClient(create_app())
    response = client.get("/api/sessions/purge-summary")

    assert response.status_code == 200
    payload = response.json()
    assert "archived_sessions_count" in payload
    assert "recommendations" in payload


def test_get_session_report_serves_cached_report_without_regeneration(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The report endpoint should return cached artifacts before invoking the generator."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    session = ResearchSession(
        session_id="cached-report-session",
        query="What changed?",
        depth=ResearchDepth.STANDARD,
        metadata={"analysis": {"key_findings": ["cached"]}},
    )
    store = SessionStore()
    store.save_session(session)
    store.save_report(
        session.session_id,
        ResearchOutputFormat.MARKDOWN,
        "# Cached report",
    )

    class FailingReportGenerator:
        def __init__(self, *_args, **_kwargs) -> None:
            raise AssertionError("Report generator should not run when cache is warm")

    monkeypatch.setattr(
        "cc_deep_research.web_server.ReportGenerator",
        FailingReportGenerator,
    )

    client = TestClient(create_app())
    response = client.get(f"/api/sessions/{session.session_id}/report?format=markdown")

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == session.session_id
    assert payload["format"] == "markdown"
    assert payload["media_type"] == "text/markdown"
    assert payload["content"] == "# Cached report"


def test_get_session_report_offloads_uncached_generation(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Uncached report generation must not block the app's runtime-owner loop."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    session = ResearchSession(
        session_id="uncached-report-session",
        query="What changed?",
        depth=ResearchDepth.STANDARD,
        metadata={"analysis": {"key_findings": ["new"]}},
    )
    SessionStore().save_session(session)
    generated_without_event_loop = False

    class ReportGeneratorStub:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def generate_markdown_report(self, *_args, **_kwargs) -> str:
            nonlocal generated_without_event_loop
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                generated_without_event_loop = True
            return "# Fresh report"

        async def generate_markdown_report_async(self, *args, **kwargs) -> str:
            return await asyncio.to_thread(self.generate_markdown_report, *args, **kwargs)

    monkeypatch.setattr(
        "cc_deep_research.reporting.ReportGenerator",
        ReportGeneratorStub,
    )

    client = TestClient(create_app())
    response = client.get(f"/api/sessions/{session.session_id}/report?format=markdown")

    assert response.status_code == 200
    assert response.json()["content"] == "# Fresh report"
    assert generated_without_event_loop is True


def test_session_detail_summary_preserves_prompt_metadata(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Historical session detail should serialize prompt metadata for dashboard inspection."""
    duckdb = pytest.importorskip("duckdb")

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "inqulume-studio"
    config_dir.mkdir(parents=True)

    db_path = config_dir / "telemetry.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE telemetry_sessions (
            session_id VARCHAR PRIMARY KEY,
            created_at TIMESTAMP,
            status VARCHAR,
            total_time_ms INTEGER,
            total_sources INTEGER,
            instances_spawned INTEGER,
            search_queries INTEGER,
            tool_calls INTEGER,
            llm_prompt_tokens INTEGER,
            llm_completion_tokens INTEGER,
            llm_total_tokens INTEGER,
            providers_json VARCHAR
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE telemetry_events (
            event_id VARCHAR,
            parent_event_id VARCHAR,
            sequence_number INTEGER,
            session_id VARCHAR,
            timestamp TIMESTAMP,
            event_type VARCHAR,
            category VARCHAR,
            name VARCHAR,
            status VARCHAR,
            duration_ms INTEGER,
            agent_id VARCHAR,
            metadata_json VARCHAR
        )
        """
    )
    conn.execute(
        """
        INSERT INTO telemetry_sessions VALUES
        (
            'prompt-session',
            TIMESTAMP '2026-03-25 00:00:00',
            'completed',
            1200,
            4,
            0,
            0,
            0,
            0,
            0,
            0,
            '[]'
        )
        """
    )
    conn.execute(
        """
        INSERT INTO telemetry_events VALUES
        (
            'event-1',
            NULL,
            1,
            'prompt-session',
            TIMESTAMP '2026-03-25 00:00:01',
            'session.started',
            'session',
            'session',
            'started',
            NULL,
            NULL,
            '{}'
        )
        """
    )
    conn.close()

    session = ResearchSession(
        session_id="prompt-session",
        query="What changed?",
        depth=ResearchDepth.STANDARD,
        metadata={
            "prompts": {
                "overrides_applied": True,
                "effective_overrides": {
                    "analyzer": {
                        "prompt_prefix": "Focus on management guidance.",
                        "system_prompt": None,
                    }
                },
                "default_prompts_used": ["deep_analyzer", "report_quality_evaluator"],
            }
        },
    )
    SessionStore().save_session(session)

    client = TestClient(create_app())
    response = client.get(f"/api/sessions/{session.session_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["metadata"]["prompts"]["overrides_applied"] is True
    assert payload["summary"]["metadata"]["prompts"]["effective_overrides"]["analyzer"] == {
        "prompt_prefix": "Focus on management guidance.",
        "system_prompt": None,
    }


def test_bulk_delete_route_returns_per_session_outcomes(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The bulk delete endpoint should return explicit mixed outcomes in request order."""
    from datetime import UTC, datetime

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "inqulume-studio"
    config_dir.mkdir(parents=True)

    SessionStore().save_session(
        ResearchSession(
            session_id="bulk-delete-saved",
            query="Delete me",
            depth=ResearchDepth.STANDARD,
        )
    )

    # Use a recent timestamp (1 minute ago) to simulate a truly active session
    recent_timestamp = (datetime.now(UTC) - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    active_session_dir = config_dir / "telemetry" / "bulk-delete-active"
    active_session_dir.mkdir(parents=True)
    (active_session_dir / "events.jsonl").write_text(
        json.dumps(
            {
                "event_id": "event-1",
                "sequence_number": 1,
                "timestamp": recent_timestamp,
                "session_id": "bulk-delete-active",
                "event_type": "session.started",
                "category": "session",
                "name": "session",
                "status": "running",
                "metadata": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    client = TestClient(create_app())
    response = client.post(
        "/api/sessions/bulk-delete",
        json={
            "session_ids": [
                "bulk-delete-saved",
                "bulk-delete-missing",
                "bulk-delete-active",
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["success"] is False
    assert payload["partial_success"] is True
    assert payload["summary"] == {
        "requested_count": 3,
        "deleted_count": 1,
        "not_found_count": 1,
        "active_conflict_count": 1,
        "partial_failure_count": 0,
        "failed_count": 0,
    }
    assert [result["session_id"] for result in payload["results"]] == [
        "bulk-delete-saved",
        "bulk-delete-missing",
        "bulk-delete-active",
    ]
    assert [result["outcome"] for result in payload["results"]] == [
        "deleted",
        "not_found",
        "active_conflict",
    ]


def test_session_list_uses_historical_duckdb_and_deduplicates_live_rows(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The session list should read telemetry.duckdb and keep one row per session."""
    duckdb = pytest.importorskip("duckdb")

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "inqulume-studio"
    telemetry_dir = config_dir / "telemetry"
    telemetry_dir.mkdir(parents=True)

    live_session_dir = telemetry_dir / "research-live"
    live_session_dir.mkdir()
    (live_session_dir / "events.jsonl").write_text(
        json.dumps(
            {
                "event_id": "event-1",
                "sequence_number": 1,
                "timestamp": "2026-03-18T10:00:00Z",
                "session_id": "research-live",
                "event_type": "session.started",
                "category": "session",
                "name": "session",
                "status": "running",
                "metadata": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    db_path = config_dir / "telemetry.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE telemetry_sessions (
            session_id VARCHAR PRIMARY KEY,
            created_at TIMESTAMP,
            total_time_ms INTEGER,
            total_sources INTEGER,
            instances_spawned INTEGER,
            search_queries INTEGER,
            tool_calls INTEGER,
            llm_total_tokens INTEGER,
            status VARCHAR
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE telemetry_events (
            event_id VARCHAR,
            parent_event_id VARCHAR,
            sequence_number INTEGER,
            session_id VARCHAR,
            timestamp TIMESTAMP,
            event_type VARCHAR,
            category VARCHAR,
            name VARCHAR,
            status VARCHAR,
            duration_ms INTEGER,
            agent_id VARCHAR,
            metadata_json VARCHAR
        )
        """
    )
    conn.execute(
        """
        INSERT INTO telemetry_sessions VALUES
        ('research-live', TIMESTAMP '2026-03-18 10:00:00', 1200, 3, 1, 1, 1, 0, 'completed'),
        ('research-archived', TIMESTAMP '2026-03-17 09:00:00', 2400, 5, 1, 2, 2, 0, 'completed')
        """
    )
    conn.close()

    client = TestClient(create_app())
    response = client.get("/api/sessions")

    assert response.status_code == 200
    sessions = response.json()["sessions"]
    assert [session["session_id"] for session in sessions].count("research-live") == 1
    assert {session["session_id"] for session in sessions} == {
        "research-live",
        "research-archived",
    }


def test_session_list_uses_lightweight_live_summaries(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The session list route should not load full live session snapshots."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    telemetry_dir = tmp_path / "xdg" / "inqulume-studio" / "telemetry"
    session_dir = telemetry_dir / "lightweight-summary"
    session_dir.mkdir(parents=True)
    (session_dir / "events.jsonl").write_text(
        json.dumps(
            {
                "event_id": "event-1",
                "sequence_number": 1,
                "timestamp": "2026-05-25T10:00:00Z",
                "session_id": "lightweight-summary",
                "event_type": "session.started",
                "category": "session",
                "name": "session",
                "status": "started",
                "metadata": {"payload": "x" * 10000},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    def fail_snapshot(*_args, **_kwargs):
        raise AssertionError("session list should not load full live snapshots")

    monkeypatch.setattr(
        "cc_deep_research.telemetry.live._read_live_session_snapshot",
        fail_snapshot,
    )

    client = TestClient(create_app())
    response = client.get("/api/sessions")

    assert response.status_code == 200
    sessions = response.json()["sessions"]
    assert [session["session_id"] for session in sessions] == ["lightweight-summary"]
    assert sessions[0]["event_count"] == 1


def test_session_list_enriches_saved_and_telemetry_only_sessions(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The list API should expose explicit summary metadata for saved and telemetry-only rows."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "inqulume-studio"
    config_dir.mkdir(parents=True)

    SessionStore().save_session(
        ResearchSession(
            session_id="saved-only-session",
            query="Assess green tea interactions with warfarin",
            depth=ResearchDepth.STANDARD,
            started_at=datetime(2026, 3, 18, 8, 0, 0),
            completed_at=datetime(2026, 3, 18, 8, 4, 0),
            metadata={"analysis": {"key_findings": ["Potential interaction"]}},
        )
    )

    telemetry_dir = config_dir / "telemetry"
    live_session_dir = telemetry_dir / "telemetry-only-session"
    live_session_dir.mkdir(parents=True)
    (live_session_dir / "events.jsonl").write_text(
        json.dumps(
            {
                "event_id": "event-1",
                "sequence_number": 1,
                "timestamp": "2026-03-18T10:00:00Z",
                "session_id": "telemetry-only-session",
                "event_type": "session.started",
                "category": "session",
                "name": "session",
                "status": "running",
                "metadata": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    client = TestClient(create_app())
    response = client.get("/api/sessions")

    assert response.status_code == 200
    sessions = {session["session_id"]: session for session in response.json()["sessions"]}

    assert sessions["saved-only-session"] == {
        "session_id": "saved-only-session",
        "label": "Assess green tea interactions with warfarin",
        "created_at": "2026-03-18T08:00:00",
        "total_time_ms": None,
        "total_sources": 0,
        "status": "completed",
        "active": False,
        "event_count": None,
        "last_event_at": "2026-03-18T08:04:00",
        "query": "Assess green tea interactions with warfarin",
        "depth": "standard",
        "completed_at": "2026-03-18T08:04:00",
        "has_session_payload": True,
        "has_report": True,
        "archived": False,
        "triage_status": None,
    }

    telemetry_only = sessions["telemetry-only-session"]
    assert telemetry_only["query"] is None
    assert telemetry_only["depth"] is None
    assert telemetry_only["completed_at"] is None
    assert telemetry_only["has_session_payload"] is False
    assert telemetry_only["has_report"] is False
    assert telemetry_only["label"] == "Session telemetr"


def test_session_detail_and_history_fall_back_to_historical_duckdb(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Historical sessions should load through REST and WebSocket history."""
    duckdb = pytest.importorskip("duckdb")

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "inqulume-studio"
    config_dir.mkdir(parents=True)

    db_path = config_dir / "telemetry.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE telemetry_sessions (
            session_id VARCHAR PRIMARY KEY,
            created_at TIMESTAMP,
            status VARCHAR,
            total_time_ms INTEGER,
            total_sources INTEGER,
            instances_spawned INTEGER,
            search_queries INTEGER,
            tool_calls INTEGER,
            llm_prompt_tokens INTEGER,
            llm_completion_tokens INTEGER,
            llm_total_tokens INTEGER,
            providers_json VARCHAR
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE telemetry_events (
            event_id VARCHAR,
            parent_event_id VARCHAR,
            sequence_number INTEGER,
            session_id VARCHAR,
            timestamp TIMESTAMP,
            event_type VARCHAR,
            category VARCHAR,
            name VARCHAR,
            status VARCHAR,
            duration_ms INTEGER,
            agent_id VARCHAR,
            metadata_json VARCHAR
        )
        """
    )
    conn.execute(
        """
        INSERT INTO telemetry_sessions VALUES
        (
            'research-history',
            TIMESTAMP '2026-03-16 08:00:00',
            'completed',
            3200,
            7,
            2,
            3,
            4,
            0,
            0,
            0,
            '[]'
        )
        """
    )
    conn.execute(
        """
        INSERT INTO telemetry_events VALUES
        (
            'event-1',
            NULL,
            1,
            'research-history',
            TIMESTAMP '2026-03-16 08:00:01',
            'phase.started',
            'phase',
            'planning',
            'started',
            NULL,
            NULL,
            '{"provider":"openrouter"}'
        )
        """
    )
    conn.close()

    client = TestClient(create_app())

    detail_response = client.get("/api/sessions/research-history")
    assert detail_response.status_code == 200
    # Check that session info is present
    session_data = detail_response.json()
    assert "session" in session_data
    session = session_data["session"]
    assert session["session_id"] == "research-history"
    assert session["status"] == "completed"
    # Check that derived outputs are present (even if empty)
    assert "narrative" in session_data
    assert "critical_path" in session_data
    assert "state_changes" in session_data
    assert "decisions" in session_data
    assert "degradations" in session_data
    assert "failures" in session_data
    assert "decision_graph" in session_data
    assert "active_phase" in session_data

    events_response = client.get("/api/sessions/research-history/events")
    assert events_response.status_code == 200
    events_data = events_response.json()
    assert "events" in events_data
    assert "count" in events_data
    # Check pagination metadata is present
    assert "has_more" in events_data or " next_cursor" in events_data
    "prev_cursor" in events_data


def test_live_session_events_route_skips_expensive_detail_builders(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The live events route should page JSONL events without full detail analytics."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    telemetry_dir = tmp_path / "xdg" / "inqulume-studio" / "telemetry"
    session_dir = telemetry_dir / "lightweight-live-events"
    session_dir.mkdir(parents=True)
    rows = []
    for sequence_number in range(1, 5):
        rows.append(
            json.dumps(
                {
                    "event_id": f"event-{sequence_number}",
                    "sequence_number": sequence_number,
                    "timestamp": f"2026-05-25T00:00:0{sequence_number}Z",
                    "event_type": "test.event",
                    "category": "test",
                    "name": f"event-{sequence_number}",
                    "status": "completed",
                    "metadata": {"payload": "x" * 100},
                }
            )
        )
    (session_dir / "events.jsonl").write_text("\n".join(rows) + "\n")

    def fail_builder(*_args, **_kwargs):
        raise AssertionError("full detail analytics should not be built")

    monkeypatch.setattr("cc_deep_research.telemetry.live.build_event_tree", fail_builder)
    monkeypatch.setattr("cc_deep_research.telemetry.live.build_subprocess_streams", fail_builder)
    monkeypatch.setattr("cc_deep_research.telemetry.live.build_llm_route_streams", fail_builder)

    client = TestClient(create_app())
    response = client.get("/api/sessions/lightweight-live-events/events?limit=2")

    assert response.status_code == 200
    payload = response.json()
    assert [event["sequence_number"] for event in payload["events"]] == [1, 2]
    assert payload["count"] == 2
    assert payload["total"] == 4
    assert payload["has_more"] is True
    assert payload["next_cursor"] == 2
    assert payload["prev_cursor"] is None


def test_live_session_detail_returns_decision_graph(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Live session detail should expose the derived decision graph."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    telemetry_dir = tmp_path / "xdg" / "inqulume-studio" / "telemetry"
    monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=telemetry_dir)
    monitor.set_session("live-graph-session", query="route choice", depth="standard")
    monitor.emit_event(
        event_type="decision.made",
        category="decision",
        name="routing",
        metadata={
            "decision_type": "routing",
            "chosen_option": "openrouter_api",
            "rejected_options": ["anthropic_api"],
            "inputs": {"operation": "analysis"},
        },
    )
    monitor.finalize_session(total_sources=1, providers=["tavily"], total_time_ms=120)

    client = TestClient(create_app())

    response = client.get("/api/sessions/live-graph-session")

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision_graph"]["summary"]["node_count"] >= 2
    assert payload["decision_graph"]["summary"]["explicit_edge_count"] >= 1


def test_session_detail_include_derived_false_returns_empty_decision_graph(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Disabling derived outputs should suppress graph derivation."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    telemetry_dir = tmp_path / "xdg" / "inqulume-studio" / "telemetry"
    monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=telemetry_dir)
    monitor.set_session("no-derived-graph", query="route choice", depth="standard")
    monitor.emit_event(
        event_type="decision.made",
        category="decision",
        name="routing",
        metadata={
            "decision_type": "routing",
            "chosen_option": "openrouter_api",
            "inputs": {"operation": "analysis"},
        },
    )
    monitor.finalize_session(total_sources=1, providers=["tavily"], total_time_ms=120)

    client = TestClient(create_app())

    response = client.get("/api/sessions/no-derived-graph?include_derived=false")

    assert response.status_code == 200
    assert response.json()["decision_graph"] == {
        "nodes": [],
        "edges": [],
        "summary": {
            "node_count": 0,
            "edge_count": 0,
            "explicit_edge_count": 0,
            "inferred_edge_count": 0,
        },
    }


def test_session_bundle_includes_decision_graph(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Trace bundle export should preserve the derived decision graph."""
    pytest.importorskip("duckdb")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    telemetry_dir = tmp_path / "xdg" / "inqulume-studio" / "telemetry"
    db_path = tmp_path / "xdg" / "inqulume-studio" / "telemetry.duckdb"
    monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=telemetry_dir)
    monitor.set_session("bundle-graph-session", query="bundle route", depth="standard")
    monitor.emit_event(
        event_type="decision.made",
        category="decision",
        name="routing",
        metadata={
            "decision_type": "routing",
            "chosen_option": "openrouter_api",
            "rejected_options": ["anthropic_api"],
            "inputs": {"operation": "analysis"},
        },
    )
    monitor.finalize_session(total_sources=1, providers=["tavily"], total_time_ms=120)
    ingest_telemetry_to_duckdb(base_dir=telemetry_dir, db_path=db_path)

    SessionStore().save_session(
        ResearchSession(
            session_id="bundle-graph-session",
            query="bundle route",
            depth=ResearchDepth.STANDARD,
            metadata={"analysis": {"key_findings": ["route selected"]}},
        )
    )

    client = TestClient(create_app())

    response = client.get("/api/sessions/bundle-graph-session/bundle")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "1.2.0"
    assert payload["derived_outputs"]["decision_graph"]["summary"]["node_count"] >= 2


def test_session_list_marks_old_no_summary_sessions_interrupted(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Abandoned telemetry directories should not remain running forever."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    session_dir = tmp_path / "xdg" / "inqulume-studio" / "telemetry" / "stale-session"
    session_dir.mkdir(parents=True)
    (session_dir / "events.jsonl").write_text(
        json.dumps(
            {
                "event_id": "event-1",
                "sequence_number": 1,
                "timestamp": "2026-03-17T00:00:00Z",
                "session_id": "stale-session",
                "event_type": "session.started",
                "category": "session",
                "name": "research-session",
                "status": "started",
                "metadata": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    client = TestClient(create_app())

    response = client.get("/api/sessions")
    assert response.status_code == 200
    assert response.json()["sessions"] == [
        {
            "session_id": "stale-session",
            "label": "Session stale-se",
            "created_at": "2026-03-17T00:00:00Z",
            "total_time_ms": None,
            "total_sources": 0,
            "status": "interrupted",
            "active": False,
            "event_count": 1,
            "last_event_at": "2026-03-17T00:00:00Z",
            "query": None,
            "depth": None,
            "completed_at": None,
            "has_session_payload": False,
            "has_report": False,
            "archived": False,
            "triage_status": None,
        }
    ]


def test_session_list_returns_paginated_response_with_total_and_next_cursor(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The session list should return total count and next_cursor for pagination."""
    duckdb = pytest.importorskip("duckdb")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "inqulume-studio"
    config_dir.mkdir(parents=True)

    db_path = config_dir / "telemetry.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE telemetry_sessions (
            session_id VARCHAR PRIMARY KEY,
            created_at TIMESTAMP,
            total_time_ms INTEGER,
            total_sources INTEGER,
            instances_spawned INTEGER,
            search_queries INTEGER,
            tool_calls INTEGER,
            llm_total_tokens INTEGER,
            status VARCHAR
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE telemetry_events (
            event_id VARCHAR,
            parent_event_id VARCHAR,
            sequence_number INTEGER,
            session_id VARCHAR,
            timestamp TIMESTAMP,
            event_type VARCHAR,
            category VARCHAR,
            name VARCHAR,
            status VARCHAR,
            duration_ms INTEGER,
            agent_id VARCHAR,
            metadata_json VARCHAR
        )
        """
    )
    conn.execute(
        """
        INSERT INTO telemetry_sessions VALUES
        ('session-1', TIMESTAMP '2026-03-18 10:00:00', 1000, 3, 1, 1, 1, 0, 'completed'),
        ('session-2', TIMESTAMP '2026-03-18 09:00:00', 2000, 5, 1, 2, 2, 0, 'completed'),
        ('session-3', TIMESTAMP '2026-03-18 08:00:00', 3000, 7, 1, 3, 3, 0, 'completed')
        """
    )
    conn.close()

    client = TestClient(create_app())

    response = client.get("/api/sessions?limit=2")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "next_cursor" in data
    assert len(data["sessions"]) == 2
    assert data["total"] == 3
    assert data["next_cursor"] == "session-2"


def test_session_list_filter_by_status(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The session list should filter by status when provided."""
    duckdb = pytest.importorskip("duckdb")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "inqulume-studio"
    config_dir.mkdir(parents=True)

    db_path = config_dir / "telemetry.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE telemetry_sessions (
            session_id VARCHAR PRIMARY KEY,
            created_at TIMESTAMP,
            total_time_ms INTEGER,
            total_sources INTEGER,
            instances_spawned INTEGER,
            search_queries INTEGER,
            tool_calls INTEGER,
            llm_total_tokens INTEGER,
            status VARCHAR
        )
        """
    )
    conn.execute(
        "CREATE TABLE telemetry_events (event_id VARCHAR, parent_event_id VARCHAR, sequence_number INTEGER, session_id VARCHAR, timestamp TIMESTAMP, event_type VARCHAR, category VARCHAR, name VARCHAR, status VARCHAR, duration_ms INTEGER, agent_id VARCHAR, metadata_json VARCHAR)"
    )
    conn.execute(
        """
        INSERT INTO telemetry_sessions VALUES
        ('session-completed', TIMESTAMP '2026-03-18 10:00:00', 1000, 3, 1, 1, 1, 0, 'completed'),
        ('session-failed', TIMESTAMP '2026-03-18 09:00:00', 2000, 5, 1, 2, 2, 0, 'failed')
        """
    )
    conn.close()

    client = TestClient(create_app())

    response = client.get("/api/sessions?status=completed")
    assert response.status_code == 200
    data = response.json()
    assert len(data["sessions"]) == 1
    assert data["sessions"][0]["session_id"] == "session-completed"

    response = client.get("/api/sessions?status=failed")
    assert response.status_code == 200
    data = response.json()
    assert len(data["sessions"]) == 1
    assert data["sessions"][0]["session_id"] == "session-failed"


def test_session_list_filter_by_search(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The session list should filter by search query when provided."""
    duckdb = pytest.importorskip("duckdb")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "inqulume-studio"
    telemetry_dir = config_dir / "telemetry"
    telemetry_dir.mkdir(parents=True)

    saved_sessions_dir = config_dir / "sessions"
    saved_sessions_dir.mkdir(parents=True)
    (saved_sessions_dir / "session-ai.json").write_text(
        json.dumps(
            {
                "session_id": "session-ai",
                "query": "What is artificial intelligence?",
                "started_at": "2026-03-18T10:00:00Z",
                "completed_at": "2026-03-18T10:10:00Z",
                "sources": [],
                "depth": "deep",
            }
        ),
        encoding="utf-8",
    )
    (saved_sessions_dir / "session-climate.json").write_text(
        json.dumps(
            {
                "session_id": "session-climate",
                "query": "Climate change effects",
                "started_at": "2026-03-18T09:00:00Z",
                "completed_at": "2026-03-18T09:10:00Z",
                "sources": [],
                "depth": "deep",
            }
        ),
        encoding="utf-8",
    )

    db_path = config_dir / "telemetry.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE telemetry_sessions (
            session_id VARCHAR PRIMARY KEY,
            created_at TIMESTAMP,
            total_time_ms INTEGER,
            total_sources INTEGER,
            instances_spawned INTEGER,
            search_queries INTEGER,
            tool_calls INTEGER,
            llm_total_tokens INTEGER,
            status VARCHAR
        )
        """
    )
    conn.execute(
        "CREATE TABLE telemetry_events (event_id VARCHAR, parent_event_id VARCHAR, sequence_number INTEGER, session_id VARCHAR, timestamp TIMESTAMP, event_type VARCHAR, category VARCHAR, name VARCHAR, status VARCHAR, duration_ms INTEGER, agent_id VARCHAR, metadata_json VARCHAR)"
    )
    conn.execute(
        """
        INSERT INTO telemetry_sessions VALUES
        ('session-ai', TIMESTAMP '2026-03-18 10:00:00', 1000, 3, 1, 1, 1, 0, 'completed'),
        ('session-climate', TIMESTAMP '2026-03-18 09:00:00', 2000, 5, 1, 2, 2, 0, 'completed')
        """
    )
    conn.close()

    client = TestClient(create_app())

    response = client.get("/api/sessions?search=artificial")
    assert response.status_code == 200
    data = response.json()
    assert len(data["sessions"]) == 1
    assert data["sessions"][0]["session_id"] == "session-ai"

    response = client.get("/api/sessions?search=climate")
    assert response.status_code == 200
    data = response.json()
    assert len(data["sessions"]) == 1
    assert data["sessions"][0]["session_id"] == "session-climate"


def test_session_list_sort_by_created_at(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The session list should sort by created_at when sort_by is specified."""
    duckdb = pytest.importorskip("duckdb")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "inqulume-studio"
    config_dir.mkdir(parents=True)

    db_path = config_dir / "telemetry.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE telemetry_sessions (
            session_id VARCHAR PRIMARY KEY,
            created_at TIMESTAMP,
            total_time_ms INTEGER,
            total_sources INTEGER,
            instances_spawned INTEGER,
            search_queries INTEGER,
            tool_calls INTEGER,
            llm_total_tokens INTEGER,
            status VARCHAR
        )
        """
    )
    conn.execute(
        "CREATE TABLE telemetry_events (event_id VARCHAR, parent_event_id VARCHAR, sequence_number INTEGER, session_id VARCHAR, timestamp TIMESTAMP, event_type VARCHAR, category VARCHAR, name VARCHAR, status VARCHAR, duration_ms INTEGER, agent_id VARCHAR, metadata_json VARCHAR)"
    )
    conn.execute(
        """
        INSERT INTO telemetry_sessions VALUES
        ('session-1', TIMESTAMP '2026-03-18 10:00:00', 1000, 3, 1, 1, 1, 0, 'completed'),
        ('session-2', TIMESTAMP '2026-03-18 11:00:00', 2000, 5, 1, 2, 2, 0, 'completed'),
        ('session-3', TIMESTAMP '2026-03-18 09:00:00', 3000, 7, 1, 3, 3, 0, 'completed')
        """
    )
    conn.close()

    client = TestClient(create_app())

    response = client.get("/api/sessions?sort_by=created_at&sort_order=asc")
    assert response.status_code == 200
    data = response.json()
    assert data["sessions"][0]["session_id"] == "session-3"
    assert data["sessions"][1]["session_id"] == "session-1"
    assert data["sessions"][2]["session_id"] == "session-2"

    response = client.get("/api/sessions?sort_by=created_at&sort_order=desc")
    assert response.status_code == 200
    data = response.json()
    assert data["sessions"][0]["session_id"] == "session-2"
    assert data["sessions"][1]["session_id"] == "session-1"
    assert data["sessions"][2]["session_id"] == "session-3"


def test_session_list_cursor_pagination(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The session list should use cursor for stable pagination."""
    duckdb = pytest.importorskip("duckdb")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "inqulume-studio"
    config_dir.mkdir(parents=True)

    db_path = config_dir / "telemetry.duckdb"
    conn = duckdb.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE telemetry_sessions (
            session_id VARCHAR PRIMARY KEY,
            created_at TIMESTAMP,
            total_time_ms INTEGER,
            total_sources INTEGER,
            instances_spawned INTEGER,
            search_queries INTEGER,
            tool_calls INTEGER,
            llm_total_tokens INTEGER,
            status VARCHAR
        )
        """
    )
    conn.execute(
        "CREATE TABLE telemetry_events (event_id VARCHAR, parent_event_id VARCHAR, sequence_number INTEGER, session_id VARCHAR, timestamp TIMESTAMP, event_type VARCHAR, category VARCHAR, name VARCHAR, status VARCHAR, duration_ms INTEGER, agent_id VARCHAR, metadata_json VARCHAR)"
    )
    conn.execute(
        """
        INSERT INTO telemetry_sessions VALUES
        ('session-1', TIMESTAMP '2026-03-18 10:00:00', 1000, 3, 1, 1, 1, 0, 'completed'),
        ('session-2', TIMESTAMP '2026-03-18 09:00:00', 2000, 5, 1, 2, 2, 0, 'completed'),
        ('session-3', TIMESTAMP '2026-03-18 08:00:00', 3000, 7, 1, 3, 3, 0, 'completed')
        """
    )
    conn.close()

    client = TestClient(create_app())

    response = client.get("/api/sessions?limit=2&sort_by=created_at&sort_order=desc")
    assert response.status_code == 200
    data = response.json()
    assert len(data["sessions"]) == 2
    assert data["sessions"][0]["session_id"] == "session-1"
    assert data["sessions"][1]["session_id"] == "session-2"
    assert data["next_cursor"] == "session-2"

    cursor = data["next_cursor"]
    response = client.get(
        f"/api/sessions?limit=2&cursor={cursor}&sort_by=created_at&sort_order=desc"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["sessions"]) == 1
    assert data["sessions"][0]["session_id"] == "session-3"
    assert data["next_cursor"] is None


def test_session_includes_checkpoint_inventory(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Session detail should include checkpoint inventory when available."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "inqulume-studio"
    telemetry_dir = config_dir / "telemetry"
    session_dir = telemetry_dir / "checkpoint-session"
    session_dir.mkdir(parents=True)

    # Create events file
    (session_dir / "events.jsonl").write_text(
        json.dumps(
            {
                "event_id": "event-1",
                "sequence_number": 1,
                "timestamp": "2026-03-18T10:00:00Z",
                "session_id": "checkpoint-session",
                "event_type": "session.started",
                "category": "session",
                "name": "session",
                "status": "started",
                "metadata": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    # Create checkpoint manifest
    checkpoints_dir = session_dir / "checkpoints"
    checkpoints_dir.mkdir()
    (checkpoints_dir / "manifest.json").write_text(
        json.dumps(
            {
                "checkpoints": [
                    {
                        "checkpoint_id": "cp-abc123",
                        "phase": "strategy",
                        "operation": "execute",
                        "sequence_number": 1,
                        "resume_safe": True,
                        "replayable": True,
                    }
                ],
                "latest_checkpoint_id": "cp-abc123",
                "latest_resume_safe_checkpoint_id": "cp-abc123",
            }
        ),
        encoding="utf-8",
    )

    client = TestClient(create_app())
    response = client.get("/api/sessions/checkpoint-session?include_checkpoints=true")

    assert response.status_code == 200
    data = response.json()
    assert "checkpoints" in data
    assert data["checkpoints"]["total"] == 1
    assert data["checkpoints"]["latest_checkpoint_id"] == "cp-abc123"
    assert data["checkpoints"]["resume_available"] is False


def test_checkpoint_list_endpoint(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The checkpoints list endpoint should return checkpoint manifest."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "inqulume-studio"
    telemetry_dir = config_dir / "telemetry"
    session_dir = telemetry_dir / "checkpoint-list-session"
    session_dir.mkdir(parents=True)

    # Create events file to make session "exist"
    (session_dir / "events.jsonl").write_text(
        json.dumps(
            {
                "event_id": "event-1",
                "sequence_number": 1,
                "timestamp": "2026-03-18T10:00:00Z",
                "session_id": "checkpoint-list-session",
                "event_type": "session.started",
                "category": "session",
                "name": "session",
                "status": "started",
                "metadata": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    # Create checkpoint manifest
    checkpoints_dir = session_dir / "checkpoints"
    checkpoints_dir.mkdir()
    (checkpoints_dir / "manifest.json").write_text(
        json.dumps(
            {
                "checkpoints": [
                    {
                        "checkpoint_id": "cp-start",
                        "phase": "session_start",
                        "operation": "initialize",
                        "sequence_number": 1,
                        "resume_safe": False,
                    },
                    {
                        "checkpoint_id": "cp-strategy",
                        "phase": "strategy",
                        "operation": "execute",
                        "sequence_number": 2,
                        "resume_safe": True,
                    },
                ],
                "latest_checkpoint_id": "cp-strategy",
                "latest_resume_safe_checkpoint_id": "cp-strategy",
            }
        ),
        encoding="utf-8",
    )

    client = TestClient(create_app())
    response = client.get("/api/sessions/checkpoint-list-session/checkpoints")

    assert response.status_code == 200
    data = response.json()
    assert len(data["checkpoints"]) == 2
    assert data["latest_checkpoint_id"] == "cp-strategy"
    assert data["latest_resume_safe_checkpoint_id"] == "cp-strategy"


def test_checkpoint_detail_endpoint(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The checkpoint detail endpoint should return checkpoint with lineage."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "inqulume-studio"
    telemetry_dir = config_dir / "telemetry"
    session_dir = telemetry_dir / "checkpoint-detail-session"
    session_dir.mkdir(parents=True)

    # Create events file to make session "exist"
    (session_dir / "events.jsonl").write_text(
        json.dumps(
            {
                "event_id": "event-1",
                "sequence_number": 1,
                "timestamp": "2026-03-18T10:00:00Z",
                "session_id": "checkpoint-detail-session",
                "event_type": "session.started",
                "category": "session",
                "name": "session",
                "status": "started",
                "metadata": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    # Create checkpoint manifest with lineage
    checkpoints_dir = session_dir / "checkpoints"
    checkpoints_dir.mkdir()
    (checkpoints_dir / "manifest.json").write_text(
        json.dumps(
            {
                "checkpoints": [
                    {
                        "checkpoint_id": "cp-parent",
                        "phase": "session_start",
                        "operation": "initialize",
                        "sequence_number": 1,
                        "parent_checkpoint_id": None,
                        "resume_safe": True,
                    },
                    {
                        "checkpoint_id": "cp-child",
                        "phase": "strategy",
                        "operation": "execute",
                        "sequence_number": 2,
                        "parent_checkpoint_id": "cp-parent",
                        "resume_safe": True,
                        "input_ref": {"query": "test"},
                        "output_ref": {"strategy": "comprehensive"},
                    },
                ],
                "latest_checkpoint_id": "cp-child",
                "latest_resume_safe_checkpoint_id": "cp-child",
            }
        ),
        encoding="utf-8",
    )

    client = TestClient(create_app())
    response = client.get("/api/sessions/checkpoint-detail-session/checkpoints/cp-child")

    assert response.status_code == 200
    data = response.json()
    assert data["checkpoint_id"] == "cp-child"
    assert data["phase"] == "strategy"
    assert data["input_ref"] == {"query": "test"}
    assert data["output_ref"] == {"strategy": "comprehensive"}
    assert "lineage" in data
    assert "cp-parent" in data["lineage"]


def test_checkpoint_lineage_endpoint(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The checkpoint lineage endpoint should return ordered checkpoint chain."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "inqulume-studio"
    telemetry_dir = config_dir / "telemetry"
    session_dir = telemetry_dir / "checkpoint-lineage-session"
    session_dir.mkdir(parents=True)

    # Create events file to make session "exist"
    (session_dir / "events.jsonl").write_text(
        json.dumps(
            {
                "event_id": "event-1",
                "sequence_number": 1,
                "timestamp": "2026-03-18T10:00:00Z",
                "session_id": "checkpoint-lineage-session",
                "event_type": "session.started",
                "category": "session",
                "name": "session",
                "status": "started",
                "metadata": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    # Create checkpoint manifest with multi-level lineage
    checkpoints_dir = session_dir / "checkpoints"
    checkpoints_dir.mkdir()
    (checkpoints_dir / "manifest.json").write_text(
        json.dumps(
            {
                "checkpoints": [
                    {
                        "checkpoint_id": "cp-1",
                        "phase": "session_start",
                        "parent_checkpoint_id": None,
                    },
                    {
                        "checkpoint_id": "cp-2",
                        "phase": "strategy",
                        "parent_checkpoint_id": "cp-1",
                    },
                    {
                        "checkpoint_id": "cp-3",
                        "phase": "source_collection",
                        "parent_checkpoint_id": "cp-2",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    client = TestClient(create_app())
    response = client.get("/api/sessions/checkpoint-lineage-session/checkpoints/cp-3/lineage")

    assert response.status_code == 200
    data = response.json()
    assert data["depth"] == 3
    assert len(data["lineage"]) == 3
    # Lineage should be ordered from start to target
    assert data["lineage"][0]["checkpoint_id"] == "cp-1"
    assert data["lineage"][1]["checkpoint_id"] == "cp-2"
    assert data["lineage"][2]["checkpoint_id"] == "cp-3"


def _write_resume_checkpoint(
    telemetry_dir: Path,
    *,
    session_id: str,
    config_fingerprint: str,
) -> None:
    session_dir = telemetry_dir / session_id
    session_dir.mkdir(parents=True)
    (session_dir / "events.jsonl").write_text(
        json.dumps(
            {
                "event_id": "event-1",
                "sequence_number": 1,
                "timestamp": "2026-03-18T10:00:00Z",
                "session_id": session_id,
                "event_type": "session.started",
                "category": "session",
                "name": "session",
                "status": "started",
                "metadata": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    request = ResearchRunRequest(query="test query", workflow=ResearchWorkflow.STAGED)
    snapshot = ResearchResumeStore(telemetry_dir).save(
        session_id,
        ResearchResumeState(
            workflow=ResearchWorkflow.STAGED,
            query=request.query,
            depth=request.depth,
            min_sources=request.min_sources,
            next_phase=ResearchResumePhase.STRATEGY,
            request=request,
            config_fingerprint=config_fingerprint,
            origin_session_id=session_id,
        ),
    )
    checkpoints_dir = session_dir / "checkpoints"
    checkpoints_dir.mkdir()
    (checkpoints_dir / "manifest.json").write_text(
        json.dumps(
            {
                "checkpoints": [
                    {
                        "checkpoint_id": "cp-resumable",
                        "phase": "strategy",
                        "operation": "finalize",
                        "resume_safe": True,
                        "replayable": True,
                        "state_ref": snapshot.path,
                        "metadata": {"execution_resume": True},
                    }
                ],
                "latest_resume_safe_checkpoint_id": "cp-resumable",
            }
        ),
        encoding="utf-8",
    )


def test_resume_endpoint_rejects_configuration_incompatible_checkpoint(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setattr(
        "cc_deep_research.web_server_routes.session_routes.queue_research_run",
        lambda *_args, **_kwargs: None,
    )
    telemetry_dir = tmp_path / "xdg" / "inqulume-studio" / "telemetry"
    incompatible_config = Config()
    incompatible_config.research.max_iterations += 1
    incompatible_prepared = ResearchRunService().prepare(
        ResearchRunRequest(query="test query", workflow=ResearchWorkflow.STAGED),
        config=incompatible_config,
    )
    assert incompatible_prepared.config_fingerprint is not None
    _write_resume_checkpoint(
        telemetry_dir,
        session_id="incompatible-resume-session",
        config_fingerprint=incompatible_prepared.config_fingerprint,
    )

    client = TestClient(create_app(job_registry=ResearchRunJobRegistry()))
    artifacts = client.get("/api/sessions/incompatible-resume-session/artifacts")
    response = client.post("/api/sessions/incompatible-resume-session/resume")

    assert artifacts.status_code == 200
    assert artifacts.json()["available"]["checkpoints"]["resume_available"] is False
    assert response.status_code == 409
    assert "configuration" in response.json()["error"].lower()


def test_resume_endpoint_rejects_completed_session(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setattr(
        "cc_deep_research.web_server_routes.session_routes.queue_research_run",
        lambda *_args, **_kwargs: None,
    )
    telemetry_dir = tmp_path / "xdg" / "inqulume-studio" / "telemetry"
    session_id = "completed-resume-session"
    _write_resume_checkpoint(
        telemetry_dir,
        session_id=session_id,
        config_fingerprint=build_config_fingerprint(Config()),
    )
    SessionStore().save_session(
        ResearchSession(
            session_id=session_id,
            query="test query",
            depth=ResearchDepth.DEEP,
        )
    )

    client = TestClient(create_app(job_registry=ResearchRunJobRegistry()))
    response = client.post(f"/api/sessions/{session_id}/resume")

    assert response.status_code == 409
    assert "completed" in response.json()["error"].lower()


def test_resume_endpoint_allows_failed_job_with_saved_session(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setattr(
        "cc_deep_research.web_server_routes.session_routes.queue_research_run",
        lambda *_args, **_kwargs: None,
    )
    telemetry_dir = tmp_path / "xdg" / "inqulume-studio" / "telemetry"
    session_id = "failed-saved-session"
    request = ResearchRunRequest(query="test query", workflow=ResearchWorkflow.STAGED)
    prepared = ResearchRunService().prepare(request)
    assert prepared.config_fingerprint is not None
    _write_resume_checkpoint(
        telemetry_dir,
        session_id=session_id,
        config_fingerprint=prepared.config_fingerprint,
    )
    SessionStore().save_session(
        ResearchSession(
            session_id=session_id,
            query=request.query,
            depth=request.depth,
        )
    )
    registry = ResearchRunJobRegistry()
    original = registry.create_job(request)
    registry.set_session_id(original.run_id, session_id=session_id)
    registry.mark_failed(original.run_id, error="report materialization failed")

    client = TestClient(create_app(job_registry=registry))
    response = client.post(f"/api/sessions/{session_id}/resume")

    assert response.status_code == 202


def test_resume_endpoint_returns_resume_info(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The resume endpoint should queue a child run from executable state."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "inqulume-studio"
    telemetry_dir = config_dir / "telemetry"
    session_dir = telemetry_dir / "resume-session"
    session_dir.mkdir(parents=True)

    # Create events file to make session "exist"
    (session_dir / "events.jsonl").write_text(
        json.dumps(
            {
                "event_id": "event-1",
                "sequence_number": 1,
                "timestamp": "2026-03-18T10:00:00Z",
                "session_id": "resume-session",
                "event_type": "session.started",
                "category": "session",
                "name": "session",
                "status": "started",
                "metadata": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    request = ResearchRunRequest(query="test query", workflow=ResearchWorkflow.STAGED)
    prepared = ResearchRunService().prepare(request)
    assert prepared.config_fingerprint is not None
    resume_store = ResearchResumeStore(telemetry_dir)
    snapshot = resume_store.save(
        "resume-session",
        ResearchResumeState(
            workflow=ResearchWorkflow.STAGED,
            query=request.query,
            depth=request.depth,
            min_sources=request.min_sources,
            next_phase=ResearchResumePhase.STRATEGY,
            request=request,
            config_fingerprint=prepared.config_fingerprint,
            origin_session_id="resume-session",
        ),
    )

    # Create checkpoint manifest with executable resume state.
    checkpoints_dir = session_dir / "checkpoints"
    checkpoints_dir.mkdir()
    (checkpoints_dir / "manifest.json").write_text(
        json.dumps(
            {
                "checkpoints": [
                    {
                        "checkpoint_id": "cp-resumable",
                        "phase": "source_collection",
                        "operation": "execute",
                        "resume_safe": True,
                        "replayable": True,
                        "input_ref": {"query": "test query"},
                        "output_ref": {"next_phase": "strategy"},
                        "state_ref": snapshot.path,
                        "metadata": {"execution_resume": True},
                    },
                ],
                "latest_resume_safe_checkpoint_id": "cp-resumable",
            }
        ),
        encoding="utf-8",
    )

    queued: dict[str, object] = {}

    def capture_queue(_app, job, *, resume_state=None) -> None:
        queued["job"] = job
        queued["state"] = resume_state

    monkeypatch.setattr(
        "cc_deep_research.web_server_routes.session_routes.queue_research_run",
        capture_queue,
    )
    registry = ResearchRunJobRegistry()
    client = TestClient(create_app(job_registry=registry))
    response = client.post(
        "/api/sessions/resume-session/resume",
        headers={"Idempotency-Key": "resume-once"},
    )

    assert response.status_code == 202
    data = response.json()
    assert data["resumed_from_checkpoint_id"] == "cp-resumable"
    assert data["original_session_id"] == "resume-session"
    assert data["resume_attempt"] == 1
    assert data["status"] == "queued"
    assert queued["state"].origin_checkpoint_id == "cp-resumable"
    assert registry.get_job(data["run_id"]) is queued["job"]


def test_resume_endpoint_rejects_non_resumable_checkpoint(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The resume endpoint should reject non-resume-safe checkpoints."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "inqulume-studio"
    telemetry_dir = config_dir / "telemetry"
    session_dir = telemetry_dir / "non-resumable-session"
    session_dir.mkdir(parents=True)

    # Create events file to make session "exist"
    (session_dir / "events.jsonl").write_text(
        json.dumps(
            {
                "event_id": "event-1",
                "sequence_number": 1,
                "timestamp": "2026-03-18T10:00:00Z",
                "session_id": "non-resumable-session",
                "event_type": "session.started",
                "category": "session",
                "name": "session",
                "status": "started",
                "metadata": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    # Create checkpoint manifest with non-resumable checkpoint
    checkpoints_dir = session_dir / "checkpoints"
    checkpoints_dir.mkdir()
    (checkpoints_dir / "manifest.json").write_text(
        json.dumps(
            {
                "checkpoints": [
                    {
                        "checkpoint_id": "cp-failed",
                        "phase": "analysis",
                        "operation": "execute",
                        "resume_safe": False,
                        "replayable": False,
                        "replayable_reason": "Phase failed: ValueError",
                    },
                ],
                "latest_resume_safe_checkpoint_id": None,
            }
        ),
        encoding="utf-8",
    )

    client = TestClient(create_app())
    response = client.post("/api/sessions/non-resumable-session/resume?checkpoint_id=cp-failed")

    assert response.status_code == 409  # Conflict
    assert "no valid executable resume state" in response.json()["error"]


def test_rerun_step_endpoint_reports_not_implemented_for_replayable_checkpoint(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Replayable checkpoints should not be reported as rerun successfully before execution exists."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "inqulume-studio"
    telemetry_dir = config_dir / "telemetry"
    session_dir = telemetry_dir / "rerun-session"
    session_dir.mkdir(parents=True)

    # Create events file to make session "exist"
    (session_dir / "events.jsonl").write_text(
        json.dumps(
            {
                "event_id": "event-1",
                "sequence_number": 1,
                "timestamp": "2026-03-18T10:00:00Z",
                "session_id": "rerun-session",
                "event_type": "session.started",
                "category": "session",
                "name": "session",
                "status": "started",
                "metadata": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    # Create checkpoint manifest with replayable checkpoint
    checkpoints_dir = session_dir / "checkpoints"
    checkpoints_dir.mkdir()
    (checkpoints_dir / "manifest.json").write_text(
        json.dumps(
            {
                "checkpoints": [
                    {
                        "checkpoint_id": "cp-replayable",
                        "phase": "strategy",
                        "operation": "execute",
                        "replayable": True,
                        "input_ref": {"query": "test query"},
                        "output_ref": {"strategy": "comprehensive"},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    client = TestClient(create_app())
    response = client.post(
        "/api/sessions/rerun-session/rerun-step",
        json={"session_id": "rerun-session", "checkpoint_id": "cp-replayable"},
    )

    assert response.status_code == 501
    data = response.json()
    assert data["success"] is False
    assert data["checkpoint_id"] == "cp-replayable"
    assert "not implemented yet" in data["error"]


def test_rerun_step_rejects_non_replayable_checkpoint(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The rerun-step endpoint should reject non-replayable checkpoints."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "inqulume-studio"
    telemetry_dir = config_dir / "telemetry"
    session_dir = telemetry_dir / "non-replayable-session"
    session_dir.mkdir(parents=True)

    # Create events file to make session "exist"
    (session_dir / "events.jsonl").write_text(
        json.dumps(
            {
                "event_id": "event-1",
                "sequence_number": 1,
                "timestamp": "2026-03-18T10:00:00Z",
                "session_id": "non-replayable-session",
                "event_type": "session.started",
                "category": "session",
                "name": "session",
                "status": "started",
                "metadata": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    # Create checkpoint manifest with non-replayable checkpoint
    checkpoints_dir = session_dir / "checkpoints"
    checkpoints_dir.mkdir()
    (checkpoints_dir / "manifest.json").write_text(
        json.dumps(
            {
                "checkpoints": [
                    {
                        "checkpoint_id": "cp-non-replayable",
                        "phase": "source_collection",
                        "operation": "execute",
                        "replayable": False,
                        "replayable_reason": "External API call with non-deterministic result",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    client = TestClient(create_app())
    response = client.post(
        "/api/sessions/non-replayable-session/rerun-step",
        json={"session_id": "non-replayable-session", "checkpoint_id": "cp-non-replayable"},
    )

    assert response.status_code == 409  # Conflict
    assert "not replayable" in response.json()["error"]


# Session Annotations and Triage Tests


def test_add_annotation_creates_annotation_on_session(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The annotations endpoint should create a note attached to the session."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    SessionStore().save_session(
        ResearchSession(
            session_id="annotate-session",
            query="Test query",
            depth=ResearchDepth.STANDARD,
        )
    )

    client = TestClient(create_app())
    response = client.post(
        "/api/sessions/annotate-session/annotations",
        json={"note": "Reviewed the analysis output", "author": "operator-1"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["annotation"]["note"] == "Reviewed the analysis output"
    assert payload["annotation"]["author"] == "operator-1"
    assert "created_at" in payload["annotation"]


def test_add_annotation_rejects_empty_note(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty or whitespace-only note should be rejected."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    SessionStore().save_session(
        ResearchSession(
            session_id="annotate-session",
            query="Test query",
            depth=ResearchDepth.STANDARD,
        )
    )

    client = TestClient(create_app())

    for bad_note in ["", "   ", "  \n  "]:
        response = client.post(
            "/api/sessions/annotate-session/annotations",
            json={"note": bad_note},
        )
        assert response.status_code == 400, f"Expected 400 for note: {repr(bad_note)}"


def test_add_annotation_returns_404_for_unknown_session(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Posting to a session that does not exist should return 404."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    client = TestClient(create_app())

    response = client.post(
        "/api/sessions/nonexistent-session/annotations",
        json={"note": "This should fail"},
    )

    assert response.status_code == 404


def test_update_annotation_modifies_existing_note(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PATCH should update the note text and set updated_at."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    session = ResearchSession(
        session_id="update-annotate-session",
        query="Test query",
        depth=ResearchDepth.STANDARD,
        metadata={
            "annotations": [
                {"note": "Original note", "author": "op", "created_at": "2026-03-01T00:00:00"}
            ]
        },
    )
    SessionStore().save_session(session)

    client = TestClient(create_app())
    response = client.patch(
        "/api/sessions/update-annotate-session/annotations/0",
        json={"note": "Updated note text"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["annotation"]["note"] == "Updated note text"
    assert payload["annotation"]["updated_at"] is not None


def test_update_annotation_returns_404_for_bad_index(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Updating an annotation index that does not exist should return 404."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    SessionStore().save_session(
        ResearchSession(
            session_id="update-annotate-session",
            query="Test query",
            depth=ResearchDepth.STANDARD,
        )
    )

    client = TestClient(create_app())
    response = client.patch(
        "/api/sessions/update-annotate-session/annotations/99",
        json={"note": "Will not exist"},
    )

    assert response.status_code == 404


def test_delete_annotation_removes_annotation(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """DELETE should remove the annotation at the given index."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    session = ResearchSession(
        session_id="delete-annotate-session",
        query="Test query",
        depth=ResearchDepth.STANDARD,
        metadata={
            "annotations": [
                {"note": "First", "author": "op", "created_at": "2026-03-01T00:00:00"},
                {"note": "Second", "author": "op", "created_at": "2026-03-01T00:01:00"},
            ]
        },
    )
    SessionStore().save_session(session)

    client = TestClient(create_app())
    response = client.delete(
        "/api/sessions/delete-annotate-session/annotations/0",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["deleted"] is True
    assert payload["remaining"] == 1

    # Verify GET now returns only the remaining annotation
    get_response = client.get("/api/sessions/delete-annotate-session/annotations")
    assert get_response.status_code == 200
    annotations = get_response.json()["annotations"]
    assert len(annotations) == 1
    assert annotations[0]["note"] == "Second"


def test_get_annotations_returns_empty_list_for_session_with_no_annotations(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A session with no annotations should return an empty annotations array."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    SessionStore().save_session(
        ResearchSession(
            session_id="no-annotation-session",
            query="Test query",
            depth=ResearchDepth.STANDARD,
        )
    )

    client = TestClient(create_app())
    response = client.get("/api/sessions/no-annotation-session/annotations")

    assert response.status_code == 200
    payload = response.json()
    assert payload["annotations"] == []
    assert payload["count"] == 0


def test_update_triage_sets_status_and_metadata(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """PATCH /triage should update triage_status, owner, handoff target, and last_reviewed_at."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    SessionStore().save_session(
        ResearchSession(
            session_id="triage-session",
            query="Test query",
            depth=ResearchDepth.STANDARD,
        )
    )

    client = TestClient(create_app())
    response = client.patch(
        "/api/sessions/triage-session/triage",
        json={
            "triage_status": "needs_review",
            "triage_owner": "analyst-a",
            "triage_handoff_target": "review-team",
            "last_reviewed_at": "2026-04-01T10:00:00Z",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["triage_status"] == "needs_review"
    assert payload["triage_owner"] == "analyst-a"
    assert payload["triage_handoff_target"] == "review-team"
    assert payload["last_reviewed_at"] is not None


def test_update_triage_rejects_invalid_status(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An invalid triage_status value should return 400."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    SessionStore().save_session(
        ResearchSession(
            session_id="triage-session",
            query="Test query",
            depth=ResearchDepth.STANDARD,
        )
    )

    client = TestClient(create_app())
    response = client.patch(
        "/api/sessions/triage-session/triage",
        json={"triage_status": "not_a_valid_status"},
    )

    assert response.status_code == 400
    assert "Invalid triage_status" in response.json()["error"]


def test_update_triage_returns_404_for_unknown_session(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PATCH /triage for a nonexistent session should return 404."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    client = TestClient(create_app())

    response = client.patch(
        "/api/sessions/nonexistent-session/triage",
        json={"triage_status": "ready"},
    )

    assert response.status_code == 404


def test_get_triage_returns_session_triage_metadata(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /triage should return the current triage metadata."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    SessionStore().save_session(
        ResearchSession(
            session_id="triage-session",
            query="Test query",
            depth=ResearchDepth.STANDARD,
            metadata={
                "triage_status": "investigated",
                "triage_owner": "analyst-b",
                "triage_handoff_target": None,
                "last_reviewed_at": "2026-04-03T14:30:00Z",
            },
        )
    )

    client = TestClient(create_app())
    response = client.get("/api/sessions/triage-session/triage")

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == "triage-session"
    assert payload["triage_status"] == "investigated"
    assert payload["triage_owner"] == "analyst-b"


def test_triage_status_surfaces_in_session_list(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sessions with triage_status should expose it in the session list rows."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    SessionStore().save_session(
        ResearchSession(
            session_id="triage-list-session",
            query="Needs triage check",
            depth=ResearchDepth.STANDARD,
            metadata={"triage_status": "blocked"},
        )
    )

    client = TestClient(create_app())
    response = client.get("/api/sessions")

    assert response.status_code == 200
    sessions = {s["session_id"]: s for s in response.json()["sessions"]}
    assert sessions["triage-list-session"]["triage_status"] == "blocked"


def test_annotations_persist_across_sessions_load(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Adding an annotation and reloading the session should preserve it."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    store = SessionStore()

    session = ResearchSession(
        session_id="persist-annotate-session",
        query="Test query",
        depth=ResearchDepth.STANDARD,
    )
    store.save_session(session)

    client = TestClient(create_app())
    client.post(
        "/api/sessions/persist-annotate-session/annotations",
        json={"note": "Persisted note", "author": "operator-x"},
    )

    # Reload via store
    reloaded = store.load_session("persist-annotate-session")
    assert reloaded is not None
    annotations = reloaded.metadata.get("annotations", [])
    assert len(annotations) == 1
    assert annotations[0]["note"] == "Persisted note"


# Search Cache API Tests
