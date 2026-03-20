"""Tests for session deletion API and SessionPurgeService."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from cc_deep_research.research_runs.models import (
    BulkSessionDeleteRequest,
    SessionDeleteRequest,
)
from cc_deep_research.research_runs.session_purge import SessionPurgeService
from cc_deep_research.session_store import SessionStore
from cc_deep_research.web_server import create_app


@pytest.fixture
def temp_config_dir(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """Set up temporary config directory with session store."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "cc-deep-research"
    config_dir.mkdir(parents=True)
    return config_dir


class TestSessionPurgeService:
    """Tests for the SessionPurgeService."""

    def test_full_delete_removes_all_layers(self, temp_config_dir) -> None:
        """Deleting an existing session should remove session file, telemetry, and DuckDB records."""
        session_id = "research-full-delete"
        session_dir = temp_config_dir / "telemetry" / session_id
        session_dir.mkdir(parents=True)
        (session_dir / "events.jsonl").write_text("", encoding="utf-8")
        (session_dir / "summary.json").write_text("{}", encoding="utf-8")

        sessions_dir = temp_config_dir / "sessions"
        sessions_dir.mkdir(parents=True)
        session_file = sessions_dir / f"{session_id}.json"
        session_file.write_text(
            json.dumps({"session_id": session_id, "query": "test"}),
            encoding="utf-8",
        )

        db_path = temp_config_dir / "telemetry.duckdb"
        import duckdb

        conn = duckdb.connect(str(db_path))
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS telemetry_sessions (
                session_id VARCHAR PRIMARY KEY,
                created_at TIMESTAMP,
                status VARCHAR,
                total_time_ms INTEGER,
                total_sources INTEGER
            )
            """
        )
        conn.execute(
            "INSERT INTO telemetry_sessions VALUES (?, TIMESTAMP '2026-01-01', 'completed', 1000, 5)",
            [session_id],
        )
        conn.close()

        service = SessionPurgeService(
            session_store=SessionStore(),
            telemetry_dir=temp_config_dir / "telemetry",
            db_path=db_path,
        )
        request = SessionDeleteRequest(session_id=session_id, force=False)
        response = service.delete_session(request)

        assert response.success is True
        assert response.active_conflict is False
        assert not session_file.exists()
        assert not session_dir.exists()

    def test_partial_delete_with_missing_layers(
        self, temp_config_dir
    ) -> None:
        """Deleting a session with only some artifacts present should report partial cleanup."""
        session_id = "research-partial-delete"

        sessions_dir = temp_config_dir / "sessions"
        sessions_dir.mkdir(parents=True)
        session_file = sessions_dir / f"{session_id}.json"
        session_file.write_text(
            json.dumps({"session_id": session_id, "query": "test"}),
            encoding="utf-8",
        )

        service = SessionPurgeService(
            session_store=SessionStore(),
            telemetry_dir=temp_config_dir / "telemetry",
            db_path=temp_config_dir / "nonexistent.duckdb",
        )
        request = SessionDeleteRequest(session_id=session_id, force=False)
        response = service.delete_session(request)

        assert response.success is True
        layer_results = {layer.layer: layer for layer in response.deleted_layers}
        assert layer_results["session"].deleted is True
        assert layer_results["telemetry"].missing is True
        assert layer_results["duckdb"].missing is True

    def test_missing_session_returns_not_found(self, temp_config_dir) -> None:
        """Deleting a nonexistent session should return success but indicate nothing was deleted."""
        session_id = "nonexistent-session"

        service = SessionPurgeService(
            session_store=SessionStore(),
            telemetry_dir=temp_config_dir / "telemetry",
            db_path=temp_config_dir / "telemetry.duckdb",
        )
        request = SessionDeleteRequest(session_id=session_id, force=False)
        response = service.delete_session(request)

        assert response.success is False
        layer_results = {layer.layer: layer for layer in response.deleted_layers}
        assert layer_results["session"].missing is True
        assert layer_results["telemetry"].missing is True

    def test_active_session_conflict_returns_409(
        self, temp_config_dir
    ) -> None:
        """Deleting an active session without force should return active_conflict=True."""
        session_id = "research-active-conflict"

        # Use a recent timestamp (1 minute ago) to simulate a truly active session
        recent_timestamp = (datetime.now(UTC) - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
        live_dir = temp_config_dir / "telemetry" / session_id
        live_dir.mkdir(parents=True)
        (live_dir / "events.jsonl").write_text(
            json.dumps(
                {
                    "event_id": "event-1",
                    "sequence_number": 1,
                    "timestamp": recent_timestamp,
                    "session_id": session_id,
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

        service = SessionPurgeService(
            session_store=SessionStore(),
            telemetry_dir=temp_config_dir / "telemetry",
            db_path=temp_config_dir / "telemetry.duckdb",
        )
        request = SessionDeleteRequest(session_id=session_id, force=False)
        response = service.delete_session(request)

        assert response.active_conflict is True
        assert response.success is False

    def test_force_delete_allows_active_session_deletion(
        self, temp_config_dir
    ) -> None:
        """Using force=true should allow deletion of active sessions."""
        session_id = "research-force-delete"

        # Use a recent timestamp (1 minute ago) to simulate a truly active session
        recent_timestamp = (datetime.now(UTC) - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
        live_dir = temp_config_dir / "telemetry" / session_id
        live_dir.mkdir(parents=True)
        (live_dir / "events.jsonl").write_text(
            json.dumps(
                {
                    "event_id": "event-1",
                    "sequence_number": 1,
                    "timestamp": recent_timestamp,
                    "session_id": session_id,
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

        sessions_dir = temp_config_dir / "sessions"
        sessions_dir.mkdir(parents=True)
        session_file = sessions_dir / f"{session_id}.json"
        session_file.write_text(
            json.dumps({"session_id": session_id, "query": "test"}),
            encoding="utf-8",
        )

        service = SessionPurgeService(
            session_store=SessionStore(),
            telemetry_dir=temp_config_dir / "telemetry",
            db_path=temp_config_dir / "telemetry.duckdb",
        )
        request = SessionDeleteRequest(session_id=session_id, force=True)
        response = service.delete_session(request)

        assert response.active_conflict is False
        assert response.success is True
        assert not session_file.exists()
        assert not live_dir.exists()

    def test_bulk_delete_isolates_outcomes_per_session(self, temp_config_dir) -> None:
        """Bulk delete should preserve per-session results when one item conflicts."""
        deleted_session_id = "bulk-service-deleted"
        active_session_id = "bulk-service-active"
        missing_session_id = "bulk-service-missing"

        sessions_dir = temp_config_dir / "sessions"
        sessions_dir.mkdir(parents=True)
        (sessions_dir / f"{deleted_session_id}.json").write_text(
            json.dumps({"session_id": deleted_session_id, "query": "test"}),
            encoding="utf-8",
        )

        # Use a recent timestamp (1 minute ago) to simulate a truly active session
        recent_timestamp = (datetime.now(UTC) - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
        active_dir = temp_config_dir / "telemetry" / active_session_id
        active_dir.mkdir(parents=True)
        (active_dir / "events.jsonl").write_text(
            json.dumps(
                {
                    "event_id": "event-1",
                    "sequence_number": 1,
                    "timestamp": recent_timestamp,
                    "session_id": active_session_id,
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

        service = SessionPurgeService(
            session_store=SessionStore(),
            telemetry_dir=temp_config_dir / "telemetry",
            db_path=temp_config_dir / "telemetry.duckdb",
        )
        response = service.delete_sessions(
            BulkSessionDeleteRequest(
                session_ids=[deleted_session_id, missing_session_id, active_session_id],
            )
        )

        assert response.success is False
        assert response.partial_success is True
        assert response.summary.requested_count == 3
        assert response.summary.deleted_count == 1
        assert response.summary.not_found_count == 1
        assert response.summary.active_conflict_count == 1
        assert [result.outcome.value for result in response.results] == [
            "deleted",
            "not_found",
            "active_conflict",
        ]

    def test_bulk_delete_marks_unexpected_session_failure_failed(
        self, temp_config_dir
    ) -> None:
        """Unexpected per-session exceptions should stay isolated and surface as failed."""

        class BrokenSessionPurgeService(SessionPurgeService):
            def delete_session(self, request: SessionDeleteRequest):
                if request.session_id == "bulk-service-exploded":
                    raise RuntimeError("boom")
                return super().delete_session(request)

        sessions_dir = temp_config_dir / "sessions"
        sessions_dir.mkdir(parents=True)
        (sessions_dir / "bulk-service-safe.json").write_text(
            json.dumps({"session_id": "bulk-service-safe", "query": "test"}),
            encoding="utf-8",
        )

        service = BrokenSessionPurgeService(
            session_store=SessionStore(),
            telemetry_dir=temp_config_dir / "telemetry",
            db_path=temp_config_dir / "telemetry.duckdb",
        )
        response = service.delete_sessions(
            BulkSessionDeleteRequest(
                session_ids=["bulk-service-exploded", "bulk-service-safe"],
            )
        )

        assert response.success is False
        assert response.partial_success is True
        assert response.summary.failed_count == 1
        assert response.summary.deleted_count == 1
        assert [result.outcome.value for result in response.results] == [
            "failed",
            "deleted",
        ]

    def test_bulk_delete_queries_live_sessions_once(self, temp_config_dir, monkeypatch) -> None:
        """Bulk delete should reuse one active-session snapshot for the full batch."""
        service = SessionPurgeService(
            session_store=SessionStore(),
            telemetry_dir=temp_config_dir / "telemetry",
            db_path=temp_config_dir / "telemetry.duckdb",
        )

        call_count = 0

        def fake_query_live_sessions(*, base_dir):
            nonlocal call_count
            del base_dir
            call_count += 1
            return [{"session_id": "bulk-service-active", "active": True}]

        monkeypatch.setattr(
            "cc_deep_research.research_runs.session_purge.query_live_sessions",
            fake_query_live_sessions,
        )

        response = service.delete_sessions(
            BulkSessionDeleteRequest(
                session_ids=["bulk-service-active", "bulk-service-missing"],
            )
        )

        assert call_count == 1
        assert [result.outcome.value for result in response.results] == [
            "active_conflict",
            "not_found",
        ]


class TestDeleteSessionAPI:
    """Tests for the DELETE /api/sessions/{session_id} endpoint."""

    def test_delete_session_returns_200_on_success(
        self, temp_config_dir
    ) -> None:
        """Successful deletion should return 200 with deletion results."""
        session_id = "api-delete-success"

        session_dir = temp_config_dir / "telemetry" / session_id
        session_dir.mkdir(parents=True)
        (session_dir / "events.jsonl").write_text("", encoding="utf-8")

        sessions_dir = temp_config_dir / "sessions"
        sessions_dir.mkdir(parents=True)
        session_file = sessions_dir / f"{session_id}.json"
        session_file.write_text(
            json.dumps({"session_id": session_id, "query": "test"}),
            encoding="utf-8",
        )

        client = TestClient(create_app())
        response = client.delete(f"/api/sessions/{session_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["active_conflict"] is False

    def test_delete_session_returns_409_on_active_conflict(
        self, temp_config_dir
    ) -> None:
        """Deleting an active session without force should return 409."""
        session_id = "api-delete-conflict"

        # Use a recent timestamp (1 minute ago) to simulate a truly active session
        recent_timestamp = (datetime.now(UTC) - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
        live_dir = temp_config_dir / "telemetry" / session_id
        live_dir.mkdir(parents=True)
        (live_dir / "events.jsonl").write_text(
            json.dumps(
                {
                    "event_id": "event-1",
                    "sequence_number": 1,
                    "timestamp": recent_timestamp,
                    "session_id": session_id,
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
        response = client.delete(f"/api/sessions/{session_id}")

        assert response.status_code == 409
        data = response.json()
        assert data["active_conflict"] is True

    def test_delete_session_force_bypasses_conflict(
        self, temp_config_dir
    ) -> None:
        """Using force=true query param should bypass active session check."""
        session_id = "api-delete-force"

        # Use a recent timestamp (1 minute ago) to simulate a truly active session
        recent_timestamp = (datetime.now(UTC) - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
        live_dir = temp_config_dir / "telemetry" / session_id
        live_dir.mkdir(parents=True)
        (live_dir / "events.jsonl").write_text(
            json.dumps(
                {
                    "event_id": "event-1",
                    "sequence_number": 1,
                    "timestamp": recent_timestamp,
                    "session_id": session_id,
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

        sessions_dir = temp_config_dir / "sessions"
        sessions_dir.mkdir(parents=True)
        session_file = sessions_dir / f"{session_id}.json"
        session_file.write_text(
            json.dumps({"session_id": session_id, "query": "test"}),
            encoding="utf-8",
        )

        client = TestClient(create_app())
        response = client.delete(f"/api/sessions/{session_id}?force=true")

        assert response.status_code == 200
        data = response.json()
        assert data["active_conflict"] is False
        assert data["success"] is True

    def test_delete_nonexistent_session_returns_200(
        self, temp_config_dir
    ) -> None:
        """Deleting a nonexistent session should return 200."""
        import duckdb

        db_path = temp_config_dir / "telemetry.duckdb"
        conn = duckdb.connect(str(db_path))
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS telemetry_sessions (
                session_id VARCHAR PRIMARY KEY,
                created_at TIMESTAMP,
                status VARCHAR,
                total_time_ms INTEGER,
                total_sources INTEGER
            )
            """
        )
        conn.close()

        client = TestClient(create_app())
        response = client.delete("/api/sessions/nonexistent-id-12345")

        assert response.status_code == 200

    def test_bulk_delete_sessions_rejects_invalid_batch(
        self, temp_config_dir
    ) -> None:
        """Oversized bulk delete requests should fail validation before any delete runs."""
        client = TestClient(create_app())
        response = client.post(
            "/api/sessions/bulk-delete",
            json={"session_ids": [f"session-{index}" for index in range(26)]},
        )

        assert response.status_code == 422
