"""Tests for FastAPI dashboard runtime state."""

from __future__ import annotations

import json
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from cc_deep_research.models import ResearchSession
from cc_deep_research.research_runs import (
    ResearchOutputFormat,
    ResearchRunReport,
    ResearchRunRequest,
    ResearchRunResult,
    ResearchWorkflow,
)
from cc_deep_research.research_runs.jobs import (
    PersistentResearchRunJobRegistry,
    ResearchRunJobStore,
)
from cc_deep_research.web_server import (
    create_app,
    get_job_registry,
)


def _result_for_status(
    *,
    request: ResearchRunRequest,
    session_id: str,
    terminal_status: str,
) -> ResearchRunResult:
    """Build a compact research result for lifecycle tests."""
    return ResearchRunResult(
        session=ResearchSession(
            session_id=session_id,
            query=request.query,
            depth=request.depth,
            metadata={"execution": {"terminal_status": terminal_status}},
        ),
        report=ResearchRunReport(
            format=ResearchOutputFormat.MARKDOWN,
            content=f"# Report for {session_id}",
            media_type="text/markdown",
        ),
    )


def _wait_for_run_status(
    client: TestClient,
    run_id: str,
    *terminal_statuses: str,
) -> dict:
    """Poll one browser run until it reaches an expected terminal status."""
    payload: dict = {}
    for _ in range(150):
        response = client.get(f"/api/research-runs/{run_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload.get("status") in terminal_statuses:
            return payload
        time.sleep(0.01)
    return payload


def test_research_route_passes_app_owned_codex_runtime(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Browser-started generation should use the same runtime as auth routes."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
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


def test_provider_degraded_result_keeps_run_failed_and_resumable(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A materialized provider failure must not become a completed job."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    class ProviderFailedResearchRunService:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def run(
            self,
            request: ResearchRunRequest,
            *,
            on_session_started=None,
            **_kwargs,
        ) -> ResearchRunResult:
            session = ResearchSession(
                session_id="provider-failed-session",
                query=request.query,
                depth=request.depth,
                metadata={
                    "execution": {
                        "degraded": True,
                        "terminal_status": "failed",
                    }
                },
            )
            if on_session_started is not None:
                on_session_started(session.session_id)
            return ResearchRunResult(
                session=session,
                report=ResearchRunReport(
                    format=ResearchOutputFormat.MARKDOWN,
                    content="No sources were available.",
                    media_type="text/markdown",
                ),
            )

    monkeypatch.setattr(
        "cc_deep_research.web_server.ResearchRunService",
        ProviderFailedResearchRunService,
    )

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/research-runs",
            json={"query": "provider outage", "depth": "quick"},
        )
        assert response.status_code == 202
        run_id = response.json()["run_id"]

        payload = None
        for _ in range(100):
            payload = client.get(f"/api/research-runs/{run_id}").json()
            if payload["status"] == "failed":
                break
            time.sleep(0.01)

    assert payload is not None
    assert payload["status"] == "failed"
    assert payload["session_id"] == "provider-failed-session"


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


def test_terminal_provider_failure_retries_with_alternate_execution(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A no-source terminal result should retry once through a distinct execution path."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    requests: list[ResearchRunRequest] = []

    class AlternateExecutionService:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def run(
            self,
            request: ResearchRunRequest,
            *,
            on_session_started=None,
            **_kwargs,
        ) -> ResearchRunResult:
            requests.append(request)
            recovered = len(requests) == 2
            session_id = "alternate-success" if recovered else "provider-failed"
            if on_session_started is not None:
                on_session_started(session_id)
            return _result_for_status(
                request=request,
                session_id=session_id,
                terminal_status="completed" if recovered else "failed",
            )

        def resume(self, *_args, **_kwargs) -> ResearchRunResult:
            raise AssertionError("Terminal provider failures should use alternate fresh execution")

    monkeypatch.setattr(
        "cc_deep_research.web_server.ResearchRunService",
        AlternateExecutionService,
    )

    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/api/research-runs",
            json={
                "query": "provider recovery",
                "depth": "quick",
                "workflow": "staged",
                "search_providers": ["tavily"],
                "concurrent_source_collection": True,
            },
        )
        payload = _wait_for_run_status(client, response.json()["run_id"], "completed")

    assert payload["status"] == "completed"
    assert payload["session_id"] == "alternate-success"
    assert len(requests) == 2
    assert requests[1].workflow == ResearchWorkflow.PLANNER
    assert requests[1].search_providers == ["tavily_basic"]
    assert requests[1].concurrent_source_collection is False

    job = get_job_registry(app).get_job(payload["run_id"])
    assert job is not None and job.result is not None
    recovery = job.result.session.metadata["execution"]["automatic_recovery"]
    assert recovery["succeeded"] is True
    assert [attempt["strategy"] for attempt in recovery["attempts"]] == [
        "alternate_execution"
    ]


def test_transient_exception_automatically_resumes_latest_checkpoint(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A transient crash should resume from the latest executable checkpoint first."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    resume_state = object()
    calls = {"run": 0, "resume": 0}

    class CheckpointRecoveryService:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def run(
            self,
            request: ResearchRunRequest,
            *,
            on_session_started=None,
            **_kwargs,
        ) -> ResearchRunResult:
            calls["run"] += 1
            if on_session_started is not None:
                on_session_started("checkpoint-origin")
            raise RuntimeError("temporary transport failure")

        def resume(
            self,
            state: object,
            *,
            on_session_started=None,
            **_kwargs,
        ) -> ResearchRunResult:
            calls["resume"] += 1
            assert state is resume_state
            request = ResearchRunRequest(query="checkpoint recovery", depth="quick")
            if on_session_started is not None:
                on_session_started("checkpoint-success")
            return _result_for_status(
                request=request,
                session_id="checkpoint-success",
                terminal_status="completed",
            )

    monkeypatch.setattr(
        "cc_deep_research.web_server.ResearchRunService",
        CheckpointRecoveryService,
    )
    monkeypatch.setattr(
        "cc_deep_research.web_server_routes.research_run_routes.load_latest_recovery_checkpoint",
        lambda session_id: SimpleNamespace(
            checkpoint_id="cp-safe",
            state=resume_state,
            session_id=session_id,
        ),
    )

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/research-runs",
            json={"query": "checkpoint recovery", "depth": "quick"},
        )
        payload = _wait_for_run_status(client, response.json()["run_id"], "completed")

    assert payload["status"] == "completed"
    assert payload["session_id"] == "checkpoint-success"
    assert calls == {"run": 1, "resume": 1}


def test_backend_restart_automatically_queues_latest_checkpoint(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A persisted in-flight job should resume automatically when the app restarts."""
    store = ResearchRunJobStore(tmp_path / "runs")
    original_registry = PersistentResearchRunJobRegistry(store=store)
    original = original_registry.create_job(ResearchRunRequest(query="restart recovery"))
    original_registry.mark_running(original.run_id, session_id="restart-origin")
    restored_registry = PersistentResearchRunJobRegistry(store=store)
    resume_state = object()

    class RestartRecoveryService:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def resume(
            self,
            state: object,
            *,
            on_session_started=None,
            **_kwargs,
        ) -> ResearchRunResult:
            assert state is resume_state
            if on_session_started is not None:
                on_session_started("restart-success")
            return _result_for_status(
                request=original.request,
                session_id="restart-success",
                terminal_status="completed",
            )

        def run(self, *_args, **_kwargs) -> ResearchRunResult:
            raise AssertionError("Restart recovery must resume the checkpoint")

    monkeypatch.setattr(
        "cc_deep_research.web_server.ResearchRunService",
        RestartRecoveryService,
    )
    monkeypatch.setattr(
        "cc_deep_research.web_server_routes.research_run_routes.load_latest_recovery_checkpoint",
        lambda session_id: SimpleNamespace(
            checkpoint_id="cp-restart",
            state=resume_state,
            session_id=session_id,
        ),
    )

    with TestClient(create_app(job_registry=restored_registry)):
        recovered = None
        for _ in range(100):
            recovered = next(
                (
                    job
                    for job in restored_registry.list_jobs()
                    if job.original_run_id == original.run_id
                ),
                None,
            )
            if recovered is not None and recovered.status.value == "completed":
                break
            time.sleep(0.01)

    assert recovered is not None
    assert recovered.status.value == "completed"
    assert recovered.session_id == "restart-success"
    assert recovered.resumed_from_checkpoint_id == "cp-restart"


def test_backend_restart_without_checkpoint_materializes_failure_report(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An interrupted job without a checkpoint should still expose a final report."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    store = ResearchRunJobStore(tmp_path / "runs")
    original_registry = PersistentResearchRunJobRegistry(store=store)
    original = original_registry.create_job(ResearchRunRequest(query="restart without checkpoint"))
    original_registry.mark_running(original.run_id, session_id="restart-no-checkpoint")
    restored_registry = PersistentResearchRunJobRegistry(store=store)

    monkeypatch.setattr(
        "cc_deep_research.web_server_routes.research_run_routes.load_latest_recovery_checkpoint",
        lambda _session_id: None,
    )

    with TestClient(create_app(job_registry=restored_registry)) as client:
        payload = client.get(f"/api/research-runs/{original.run_id}").json()

    assert payload["status"] == "failed"
    assert payload["session_id"] == "restart-no-checkpoint"
    assert payload["result"]["session_id"] == "restart-no-checkpoint"
    assert payload["result"]["artifacts"]


def test_non_retriable_failure_still_materializes_final_report(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Invalid execution state should not retry, but should still return a failure report."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    calls = {"run": 0, "resume": 0, "failure_report": 0}

    class NonRetriableFailureService:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def run(
            self,
            request: ResearchRunRequest,
            *,
            on_session_started=None,
            **_kwargs,
        ) -> ResearchRunResult:
            calls["run"] += 1
            if on_session_started is not None:
                on_session_started("invalid-session")
            raise ValueError("invalid workflow state")

        def resume(self, *_args, **_kwargs) -> ResearchRunResult:
            calls["resume"] += 1
            raise AssertionError("Non-retriable errors must not resume")

        def materialize_failure_result(
            self,
            request: ResearchRunRequest,
            *,
            session_id: str | None,
            failure_reasons: list[str],
        ) -> ResearchRunResult:
            calls["failure_report"] += 1
            assert failure_reasons == ["Initial execution failed (ValueError)."]
            return _result_for_status(
                request=request,
                session_id=session_id or "failure-report",
                terminal_status="failed",
            )

    monkeypatch.setattr(
        "cc_deep_research.web_server.ResearchRunService",
        NonRetriableFailureService,
    )

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/research-runs",
            json={"query": "invalid state", "depth": "quick"},
        )
        payload = _wait_for_run_status(client, response.json()["run_id"], "failed")

    assert payload["status"] == "failed"
    assert payload["result"]["session_id"] == "invalid-session"
    assert calls == {"run": 1, "resume": 0, "failure_report": 1}


def test_automatic_recovery_is_bounded_before_failure_report(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Checkpoint and alternate retries should each run at most once."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    resume_state = object()
    calls = {"run": 0, "resume": 0, "failure_report": 0}

    class ExhaustedRecoveryService:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def run(
            self,
            request: ResearchRunRequest,
            *,
            on_session_started=None,
            **_kwargs,
        ) -> ResearchRunResult:
            calls["run"] += 1
            if on_session_started is not None:
                on_session_started(f"failed-attempt-{calls['run']}")
            raise RuntimeError("temporary failure")

        def resume(self, *_args, **_kwargs) -> ResearchRunResult:
            calls["resume"] += 1
            raise RuntimeError("resume failed")

        def materialize_failure_result(
            self,
            request: ResearchRunRequest,
            *,
            session_id: str | None,
            failure_reasons: list[str],
        ) -> ResearchRunResult:
            calls["failure_report"] += 1
            assert len(failure_reasons) == 3
            return _result_for_status(
                request=request,
                session_id=session_id or "exhausted-recovery",
                terminal_status="failed",
            )

    monkeypatch.setattr(
        "cc_deep_research.web_server.ResearchRunService",
        ExhaustedRecoveryService,
    )
    monkeypatch.setattr(
        "cc_deep_research.web_server_routes.research_run_routes.load_latest_recovery_checkpoint",
        lambda session_id: SimpleNamespace(
            checkpoint_id="cp-safe",
            state=resume_state,
            session_id=session_id,
        ),
    )

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/research-runs",
            json={"query": "bounded recovery", "depth": "quick"},
        )
        payload = _wait_for_run_status(client, response.json()["run_id"], "failed")

    assert payload["status"] == "failed"
    assert payload["result"]["session_id"] == "failed-attempt-2"
    assert calls == {"run": 2, "resume": 1, "failure_report": 1}
