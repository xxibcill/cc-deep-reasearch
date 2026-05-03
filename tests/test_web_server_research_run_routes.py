"""Tests for FastAPI dashboard runtime state."""

from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

from cc_deep_research.research_runs import (
    ResearchRunRequest,
    ResearchRunResult,
)
from cc_deep_research.web_server import (
    create_app,
)


def test_stop_research_run_cancels_active_run_and_interrupts_session(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stopping a browser-started run should yield cancelled run status and interrupted session state."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    class BlockingResearchRunService:
        def run(
            self,
            request: ResearchRunRequest,
            *,
            cancellation_check=None,
            on_session_started=None,
            **_kwargs,
        ) -> ResearchRunResult:
            session_id = "research-cancelled"
            telemetry_dir = tmp_path / "xdg" / "cc-deep-research" / "telemetry" / session_id
            telemetry_dir.mkdir(parents=True, exist_ok=True)
            (telemetry_dir / "events.jsonl").write_text(
                json.dumps(
                    {
                        "event_id": "event-1",
                        "sequence_number": 1,
                        "timestamp": "2026-03-19T10:00:00Z",
                        "session_id": session_id,
                        "event_type": "session.started",
                        "category": "session",
                        "name": "research-session",
                        "status": "started",
                        "metadata": {"query": request.query, "depth": request.depth.value},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            if on_session_started is not None:
                on_session_started(session_id)

            while True:
                time.sleep(0.01)
                if cancellation_check is not None:
                    cancellation_check()

    monkeypatch.setattr(
        "cc_deep_research.web_server.ResearchRunService",
        BlockingResearchRunService,
    )

    with TestClient(create_app()) as client:
        start_response = client.post(
            "/api/research-runs",
            json={"query": "test query", "depth": "deep", "realtime_enabled": True},
        )
        assert start_response.status_code == 202
        run_id = start_response.json()["run_id"]

        session_id = None
        for _ in range(50):
            status_response = client.get(f"/api/research-runs/{run_id}")
            assert status_response.status_code == 200
            payload = status_response.json()
            session_id = payload.get("session_id")
            if session_id is not None:
                break
            time.sleep(0.01)

        assert session_id == "research-cancelled"

        stop_response = client.post(f"/api/research-runs/{run_id}/stop")
        assert stop_response.status_code == 202
        assert stop_response.json()["stop_requested"] is True

        cancelled_payload = None
        for _ in range(100):
            status_response = client.get(f"/api/research-runs/{run_id}")
            assert status_response.status_code == 200
            cancelled_payload = status_response.json()
            if cancelled_payload["status"] == "cancelled":
                break
            time.sleep(0.01)

        assert cancelled_payload is not None
        assert cancelled_payload["status"] == "cancelled"
        assert cancelled_payload["session_id"] == session_id
        assert cancelled_payload["stop_requested"] is True

        sessions_response = client.get("/api/sessions?status=interrupted")
        assert sessions_response.status_code == 200
        sessions = sessions_response.json()["sessions"]
        assert len(sessions) == 1
        assert sessions[0]["session_id"] == session_id
        assert sessions[0]["status"] == "interrupted"
        assert sessions[0]["active"] is False
