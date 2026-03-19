"""Tests for FastAPI dashboard runtime state."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from cc_deep_research.event_router import EventRouter
from cc_deep_research.models import ResearchDepth, ResearchSession
from cc_deep_research.research_runs import (
    ResearchOutputFormat,
    ResearchRunReport,
    ResearchRunRequest,
    ResearchRunResult,
)
from cc_deep_research.research_runs.jobs import (
    ResearchRunJobRegistry,
    ResearchRunJobStatus,
)
from cc_deep_research.session_store import SessionStore
from cc_deep_research.web_server import create_app, get_event_router, get_job_registry


def test_create_app_uses_supplied_runtime_dependencies() -> None:
    """The app should expose one shared router and job registry through helpers."""
    event_router = EventRouter()
    registry = ResearchRunJobRegistry()

    app = create_app(event_router=event_router, job_registry=registry)

    assert get_event_router(app) is event_router
    assert get_job_registry(app) is registry


def test_job_registry_tracks_active_and_completed_runs() -> None:
    """The registry should keep in-process state for queued, running, and finished jobs."""
    registry = ResearchRunJobRegistry()
    request = ResearchRunRequest(query="test query")
    job = registry.create_job(request)

    assert job.status == ResearchRunJobStatus.QUEUED
    assert registry.active_jobs() == [job]

    registry.mark_running(job.run_id, session_id="session-123")
    assert job.status == ResearchRunJobStatus.RUNNING
    assert job.session_id == "session-123"

    result = ResearchRunResult(
        session=ResearchSession(session_id="session-123", query="test query"),
        report=ResearchRunReport(
            format=ResearchOutputFormat.MARKDOWN,
            content="# Report",
            media_type="text/markdown",
        ),
    )
    registry.mark_completed(job.run_id, result=result)

    assert job.status == ResearchRunJobStatus.COMPLETED
    assert job.result == result
    assert registry.active_jobs() == []
    assert registry.completed_jobs() == [job]


@pytest.mark.asyncio
async def test_job_registry_cancel_all_cancels_active_tasks() -> None:
    """Shutdown cleanup should cancel unfinished background tasks."""
    registry = ResearchRunJobRegistry()
    job = registry.create_job(ResearchRunRequest(query="test query"))

    task = asyncio.create_task(asyncio.sleep(60))
    registry.attach_task(job.run_id, task)
    registry.mark_running(job.run_id)

    await registry.cancel_all()

    assert task.cancelled() is True


def test_session_list_uses_historical_duckdb_and_deduplicates_live_rows(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The session list should read telemetry.duckdb and keep one row per session."""
    duckdb = pytest.importorskip("duckdb")

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "cc-deep-research"
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


def test_session_list_enriches_saved_and_telemetry_only_sessions(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The list API should expose explicit summary metadata for saved and telemetry-only rows."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "cc-deep-research"
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
    config_dir = tmp_path / "xdg" / "cc-deep-research"
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
    assert detail_response.json()["session"] == {
        "session_id": "research-history",
        "created_at": "2026-03-16T08:00:00",
        "status": "completed",
        "total_time_ms": 3200,
        "total_sources": 7,
        "active": False,
        "event_count": 1,
        "last_event_at": "2026-03-16T08:00:01",
    }

    events_response = client.get("/api/sessions/research-history/events")
    assert events_response.status_code == 200
    assert events_response.json() == {
        "events": [
            {
                "event_id": "event-1",
                "parent_event_id": None,
                "sequence_number": 1,
                "timestamp": "2026-03-16T08:00:01",
                "session_id": "research-history",
                "event_type": "phase.started",
                "category": "phase",
                "name": "planning",
                "status": "started",
                "duration_ms": None,
                "agent_id": None,
                "metadata": {"provider": "openrouter"},
            }
        ],
        "count": 1,
    }


def test_session_list_marks_old_no_summary_sessions_interrupted(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Abandoned telemetry directories should not remain running forever."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    session_dir = tmp_path / "xdg" / "cc-deep-research" / "telemetry" / "stale-session"
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
        }
    ]


def test_session_list_returns_paginated_response_with_total_and_next_cursor(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The session list should return total count and next_cursor for pagination."""
    duckdb = pytest.importorskip("duckdb")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "cc-deep-research"
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
    config_dir = tmp_path / "xdg" / "cc-deep-research"
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
    config_dir = tmp_path / "xdg" / "cc-deep-research"
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
    config_dir = tmp_path / "xdg" / "cc-deep-research"
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
    config_dir = tmp_path / "xdg" / "cc-deep-research"
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
