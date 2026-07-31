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
    get_job_registry,
)


def test_research_route_passes_app_owned_codex_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Browser-started generation should use the same runtime as auth routes."""
    captured: list[object] = []

    class FakeCodexRuntime:
        async def start(self) -> None:
            pass

        async def close(self) -> None:
            pass

    class CapturingResearchRunService:
        def __init__(self, *, codex_runtime: object) -> None:
            captured.append(codex_runtime)

        def run(self, *_args, **_kwargs) -> ResearchRunResult:
            raise RuntimeError("expected test stop")

    monkeypatch.setattr(
        "cc_deep_research.web_server.ResearchRunService",
        CapturingResearchRunService,
    )
    codex_runtime = FakeCodexRuntime()

    with TestClient(create_app(codex_runtime=codex_runtime)) as client:  # type: ignore[arg-type]
        response = client.post(
            "/api/research-runs",
            json={"query": "runtime identity", "depth": "quick"},
        )
        assert response.status_code == 202
        for _ in range(50):
            if captured:
                break
            time.sleep(0.01)

    assert captured == [codex_runtime]


def test_stop_research_run_cancels_active_run_and_interrupts_session(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stopping a browser-started run should yield cancelled run status and interrupted session state."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    class BlockingResearchRunService:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def run(
            self,
            request: ResearchRunRequest,
            *,
            cancellation_check=None,
            on_session_started=None,
            **_kwargs,
        ) -> ResearchRunResult:
            session_id = "research-cancelled"
            telemetry_dir = tmp_path / "xdg" / "inqulume-studio" / "telemetry" / session_id
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


def test_stop_research_run_cancels_matching_llm_scope() -> None:
    class RecordingCodexRuntime:
        def __init__(self) -> None:
            self.cancelled_scopes: list[str] = []

        async def start(self) -> None:
            pass

        async def close(self) -> None:
            pass

        def request_cancel_scope(self, scope_id: str) -> None:
            self.cancelled_scopes.append(scope_id)

    runtime = RecordingCodexRuntime()
    app = create_app(codex_runtime=runtime)  # type: ignore[arg-type]
    registry = get_job_registry(app)
    job = registry.create_job(ResearchRunRequest(query="cancel scope"))
    registry.mark_running(job.run_id)

    with TestClient(app) as client:
        response = client.post(f"/api/research-runs/{job.run_id}/stop")

    assert response.status_code == 202
    assert runtime.cancelled_scopes == [job.run_id]
