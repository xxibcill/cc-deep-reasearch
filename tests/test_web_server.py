"""Tests for FastAPI dashboard runtime state."""

from __future__ import annotations

import asyncio
import json
import threading
import time
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from cc_deep_research.config import Config
from cc_deep_research.content_gen.models import (
    IterationState,
    PipelineContext,
    PipelineStageTrace,
    QCResult,
    QualityEvaluation,
    SavedScriptRun,
    ScriptingContext,
    ScriptingLLMCallTrace,
    ScriptingStepTrace,
)
from cc_deep_research.event_router import EventRouter
from cc_deep_research.models import ResearchDepth, ResearchSession
from cc_deep_research.monitoring import ResearchMonitor
from cc_deep_research.research_runs import (
    ResearchOutputFormat,
    ResearchRunReport,
    ResearchRunRequest,
    ResearchRunResult,
    ResearchRunStatus,
)
from cc_deep_research.research_runs.jobs import (
    ResearchRunJobRegistry,
    ResearchRunJobStatus,
)
from cc_deep_research.research_runs.models import (
    BulkSessionDeleteRequest,
    MAX_BULK_DELETE_SESSION_IDS,
)
from cc_deep_research.session_store import SessionStore
from cc_deep_research.telemetry import ingest_telemetry_to_duckdb
from cc_deep_research.web_server import (
    create_app,
    get_event_router,
    get_job_registry,
    get_pipeline_job_registry,
)


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


def test_job_registry_can_mark_run_cancelled() -> None:
    """A single run stop request should be preserved as terminal job state."""
    registry = ResearchRunJobRegistry()
    job = registry.create_job(ResearchRunRequest(query="test query"))

    registry.request_cancel(job.run_id)
    registry.mark_cancelled(job.run_id)

    assert job.stop_requested is True
    assert job.status == ResearchRunStatus.CANCELLED
    assert job.completed_at is not None


def test_create_app_restores_persisted_pipeline_jobs(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pipeline jobs should survive FastAPI app recreation."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    app = create_app()
    pipeline_jobs = get_pipeline_job_registry(app)
    job = pipeline_jobs.create_job(
        "pricing anchors",
        from_stage=0,
        to_stage=8,
        pipeline_id="cgp-restored",
    )
    ctx = PipelineContext(
        theme="pricing anchors",
        current_stage=4,
        selected_idea_id="idea-1",
    )
    pipeline_jobs.mark_running(job.pipeline_id)
    pipeline_jobs.update_context(job.pipeline_id, ctx)
    pipeline_jobs.mark_completed(job.pipeline_id, context=ctx)

    restored_app = create_app()
    restored_jobs = get_pipeline_job_registry(restored_app)
    restored_job = restored_jobs.get_job(job.pipeline_id)

    assert restored_job is not None
    assert restored_job.status.value == "completed"
    assert restored_job.pipeline_context is not None
    assert restored_job.pipeline_context.current_stage == 4
    assert restored_job.pipeline_context.selected_idea_id == "idea-1"


def test_run_scripting_endpoint_can_force_single_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The dashboard should be able to disable iterative scripting for one run."""
    config = Config()
    config.content_gen.enable_iterative_mode = True
    monkeypatch.setattr("cc_deep_research.content_gen.router.load_config", lambda: config)

    class FakeStore:
        def save(
            self,
            ctx: ScriptingContext,
            *,
            execution_mode: str = "single_pass",
            iterations=None,
        ) -> SavedScriptRun:
            del execution_mode, iterations
            return SavedScriptRun(
                run_id="run-123",
                saved_at="2026-03-30T00:00:00+00:00",
                raw_idea=ctx.raw_idea,
                word_count=2,
                script_path="/tmp/script.txt",
                context_path="/tmp/context.json",
            )

        @staticmethod
        def _extract_script(ctx: ScriptingContext) -> str:
            return ctx.qc.final_script if ctx.qc else ""

    class FakeOrchestrator:
        def __init__(self, _config: Config) -> None:
            self.single_pass_calls = 0

        async def run_scripting(
            self,
            raw_idea: str,
            progress_callback=None,
            *,
            llm_route=None,
        ) -> ScriptingContext:
            del progress_callback
            self.single_pass_calls += 1
            assert llm_route == "openrouter"
            return ScriptingContext(
                raw_idea=raw_idea,
                qc=QCResult(checks=[], weakest_parts=[], final_script="Single pass script"),
                step_traces=[
                    ScriptingStepTrace(
                        step_index=0,
                        step_name="define_core_inputs",
                        step_label="Defining core inputs",
                        iteration=1,
                        llm_calls=[
                            ScriptingLLMCallTrace(
                                call_index=1,
                                temperature=0.3,
                                system_prompt="system",
                                user_prompt="user",
                                raw_response="response",
                                provider="anthropic",
                                model="claude-test",
                                transport="anthropic_api",
                            )
                        ],
                        parsed_output={"topic": "Topic"},
                    )
                ],
            )

        async def run_scripting_iterative(self, raw_idea: str, progress_callback=None, max_iterations=None):
            del raw_idea, progress_callback, max_iterations
            raise AssertionError("Iterative path should not run")

    monkeypatch.setattr("cc_deep_research.content_gen.router.ScriptingStore", FakeStore)
    monkeypatch.setattr(
        "cc_deep_research.content_gen.orchestrator.ContentGenOrchestrator",
        FakeOrchestrator,
    )

    client = TestClient(create_app())
    response = client.post(
        "/api/content-gen/scripting",
        json={"idea": "test idea", "iterative_mode": False, "llm_route": "openrouter"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["script"] == "Single pass script"
    assert payload["execution_mode"] == "single_pass"
    assert "iterations" not in payload
    assert payload["context"]["step_traces"] == [
        {
            "step_index": 0,
            "step_name": "define_core_inputs",
            "step_label": "Defining core inputs",
            "iteration": 1,
            "llm_calls": [
                {
                    "call_index": 1,
                    "temperature": 0.3,
                    "system_prompt": "system",
                    "user_prompt": "user",
                    "raw_response": "response",
                    "provider": "anthropic",
                    "model": "claude-test",
                    "transport": "anthropic_api",
                    "latency_ms": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "finish_reason": None,
                }
            ],
            "parsed_output": {"topic": "Topic"},
        }
    ]


def test_run_scripting_endpoint_accepts_iteration_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The dashboard should be able to opt into iterative scripting with a custom pass cap."""
    config = Config()
    config.content_gen.enable_iterative_mode = False
    monkeypatch.setattr("cc_deep_research.content_gen.router.load_config", lambda: config)

    class FakeStore:
        def save(
            self,
            ctx: ScriptingContext,
            *,
            execution_mode: str = "single_pass",
            iterations=None,
        ) -> SavedScriptRun:
            del execution_mode, iterations
            return SavedScriptRun(
                run_id="run-123",
                saved_at="2026-03-30T00:00:00+00:00",
                raw_idea=ctx.raw_idea,
                word_count=2,
                script_path="/tmp/script.txt",
                context_path="/tmp/context.json",
            )

        @staticmethod
        def _extract_script(ctx: ScriptingContext) -> str:
            return ctx.qc.final_script if ctx.qc else ""

    class FakeOrchestrator:
        def __init__(self, _config: Config) -> None:
            pass

        async def run_scripting(self, raw_idea: str, progress_callback=None) -> ScriptingContext:
            del raw_idea, progress_callback
            raise AssertionError("Single-pass path should not run")

        async def run_scripting_iterative(
            self,
            raw_idea: str,
            progress_callback=None,
            max_iterations=None,
            *,
            llm_route=None,
        ) -> tuple[ScriptingContext, IterationState]:
            del progress_callback
            assert raw_idea == "test idea"
            assert max_iterations == 4
            assert llm_route == "cerebras"
            return (
                ScriptingContext(
                    raw_idea=raw_idea,
                    qc=QCResult(checks=[], weakest_parts=[], final_script="Iterative script"),
                ),
                IterationState(
                    current_iteration=3,
                    max_iterations=4,
                    quality_history=[
                        QualityEvaluation(
                            iteration_number=1,
                            overall_quality_score=0.55,
                            passes_threshold=False,
                        ),
                        QualityEvaluation(
                            iteration_number=2,
                            overall_quality_score=0.68,
                            passes_threshold=False,
                        ),
                        QualityEvaluation(
                            iteration_number=3,
                            overall_quality_score=0.81,
                            passes_threshold=True,
                        ),
                    ],
                    is_converged=True,
                    convergence_reason="Threshold reached",
                ),
            )

    monkeypatch.setattr("cc_deep_research.content_gen.router.ScriptingStore", FakeStore)
    monkeypatch.setattr(
        "cc_deep_research.content_gen.orchestrator.ContentGenOrchestrator",
        FakeOrchestrator,
    )

    client = TestClient(create_app())
    response = client.post(
        "/api/content-gen/scripting",
        json={
            "idea": "test idea",
            "iterative_mode": True,
            "max_iterations": 4,
            "llm_route": "cerebras",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["script"] == "Iterative script"
    assert payload["execution_mode"] == "iterative"
    assert payload["iterations"] == {
        "count": 3,
        "max_iterations": 4,
        "converged": True,
        "quality_history": [
            {"iteration": 1, "score": 0.55, "passes": False},
            {"iteration": 2, "score": 0.68, "passes": False},
            {"iteration": 3, "score": 0.81, "passes": True},
        ],
    }


def test_get_saved_script_returns_full_saved_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """Saved Quick Script history should return the persisted full result payload."""
    result_path = tmp_path / "result.json"
    result_path.write_text(
        json.dumps(
            {
                "run_id": "run-123",
                "raw_idea": "test idea",
                "script": "Saved script",
                "word_count": 2,
                "context": {
                    "raw_idea": "test idea",
                    "research_context": "",
                    "tone": "",
                    "cta": "",
                    "core_inputs": None,
                    "angle": None,
                    "structure": None,
                    "beat_intents": None,
                    "hooks": None,
                    "draft": None,
                    "retention_revised": None,
                    "tightened": None,
                    "annotated_script": None,
                    "visual_notes": None,
                    "qc": {"checks": [], "weakest_parts": [], "final_script": "Saved script"},
                    "step_traces": [],
                },
                "execution_mode": "iterative",
                "iterations": {
                    "count": 2,
                    "max_iterations": 4,
                    "converged": True,
                    "quality_history": [
                        {"iteration": 1, "score": 0.61, "passes": False},
                        {"iteration": 2, "score": 0.82, "passes": True},
                    ],
                },
            }
        )
    )

    class FakeStore:
        def get(self, run_id: str) -> SavedScriptRun | None:
            assert run_id == "run-123"
            return SavedScriptRun(
                run_id="run-123",
                saved_at="2026-03-30T00:00:00+00:00",
                raw_idea="test idea",
                word_count=2,
                script_path=str(tmp_path / "script.txt"),
                context_path=str(tmp_path / "context.json"),
                result_path=str(result_path),
                execution_mode="iterative",
            )

    monkeypatch.setattr("cc_deep_research.content_gen.router.ScriptingStore", FakeStore)

    client = TestClient(create_app())
    response = client.get("/api/content-gen/scripts/run-123")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "run-123"
    assert payload["script"] == "Saved script"
    assert payload["execution_mode"] == "iterative"
    assert payload["iterations"]["quality_history"] == [
        {"iteration": 1, "score": 0.61, "passes": False},
        {"iteration": 2, "score": 0.82, "passes": True},
    ]


def test_content_gen_pipeline_websocket_streams_live_stage_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Browser-started pipeline runs should stream per-stage progress live."""
    config = Config()
    monkeypatch.setattr("cc_deep_research.content_gen.router.load_config", lambda: config)
    allow_run = threading.Event()

    class FakeOrchestrator:
        def __init__(self, _config: Config) -> None:
            pass

        async def run_full_pipeline(
            self,
            theme: str,
            *,
            from_stage: int = 0,
            to_stage: int | None = None,
            progress_callback=None,
            stage_completed_callback=None,
        ) -> PipelineContext:
            assert theme == "pricing anchors"
            assert from_stage == 0
            assert to_stage == 2

            while not allow_run.is_set():
                await asyncio.sleep(0.001)

            if progress_callback is not None:
                progress_callback(0, "Loading strategy memory")
            await asyncio.sleep(0)
            if stage_completed_callback is not None:
                stage_completed_callback(
                    0,
                    "completed",
                    "",
                    PipelineContext(
                        theme=theme,
                        current_stage=0,
                        selected_idea_id="idea-alpha",
                        stage_traces=[
                            PipelineStageTrace(
                                stage_index=0,
                                stage_name="load_strategy",
                                stage_label="Loading strategy memory",
                            ),
                        ],
                    ),
                )
            await asyncio.sleep(0)
            if progress_callback is not None:
                progress_callback(1, "Planning opportunity brief")
            await asyncio.sleep(0)
            if stage_completed_callback is not None:
                stage_completed_callback(
                    1,
                    "skipped",
                    "already planned",
                    PipelineContext(
                        theme=theme,
                        current_stage=1,
                        selected_idea_id="idea-beta",
                        stage_traces=[
                            PipelineStageTrace(
                                stage_index=0,
                                stage_name="load_strategy",
                                stage_label="Loading strategy memory",
                            ),
                            PipelineStageTrace(
                                stage_index=1,
                                stage_name="plan_opportunity",
                                stage_label="Planning opportunity brief",
                                status="skipped",
                                output_summary="already planned",
                                decision_summary="Skipped: already planned",
                            ),
                        ],
                    ),
                )
            await asyncio.sleep(0)

            return PipelineContext(
                theme=theme,
                current_stage=1,
                selected_idea_id="idea-beta",
                stage_traces=[
                    PipelineStageTrace(
                        stage_index=0,
                        stage_name="load_strategy",
                        stage_label="Loading strategy memory",
                    ),
                    PipelineStageTrace(
                        stage_index=1,
                        stage_name="plan_opportunity",
                        stage_label="Planning opportunity brief",
                        status="skipped",
                        output_summary="already planned",
                    ),
                ],
            )

    monkeypatch.setattr(
        "cc_deep_research.content_gen.orchestrator.ContentGenOrchestrator",
        FakeOrchestrator,
    )

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/content-gen/pipelines",
            json={"theme": "pricing anchors", "from_stage": 0, "to_stage": 2},
        )

        assert response.status_code == 202
        pipeline_id = response.json()["pipeline_id"]

        with client.websocket_connect(f"/ws/content-gen/pipeline/{pipeline_id}") as websocket:
            initial = websocket.receive_json()
            assert initial["type"] == "pipeline_status"
            assert initial["pipeline_id"] == pipeline_id
            assert initial["status"] in {"queued", "running"}

            allow_run.set()

            started = websocket.receive_json()
            completed = websocket.receive_json()
            started_second = websocket.receive_json()
            skipped = websocket.receive_json()
            finished = websocket.receive_json()

        assert started == {
            "type": "pipeline_stage_started",
            "stage_index": 0,
            "stage_label": "Loading strategy memory",
            "timestamp": started["timestamp"],
        }
        assert completed == {
            "type": "pipeline_stage_completed",
            "stage_index": 0,
            "stage_status": "completed",
            "stage_detail": "",
            "context": completed["context"],
            "timestamp": completed["timestamp"],
        }
        assert completed["context"]["current_stage"] == 0
        assert completed["context"]["selected_idea_id"] == "idea-alpha"
        assert started_second == {
            "type": "pipeline_stage_started",
            "stage_index": 1,
            "stage_label": "Planning opportunity brief",
            "timestamp": started_second["timestamp"],
        }
        assert skipped == {
            "type": "pipeline_stage_skipped",
            "stage_index": 1,
            "stage_label": "Planning opportunity brief",
            "reason": "already planned",
            "context": skipped["context"],
            "timestamp": skipped["timestamp"],
        }
        assert skipped["context"]["current_stage"] == 1
        assert skipped["context"]["selected_idea_id"] == "idea-beta"
        assert finished["type"] == "pipeline_completed"
        assert finished["current_stage"] == 1

        status_response = client.get(f"/api/content-gen/pipelines/{pipeline_id}")
        assert status_response.status_code == 200
        payload = status_response.json()
        assert payload["status"] == "completed"
        assert payload["current_stage"] == 1
        assert payload["context"]["selected_idea_id"] == "idea-beta"


def test_content_gen_pipeline_websocket_streams_failed_stage_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stage failures should emit both the failed-stage event and terminal pipeline error."""
    config = Config()
    monkeypatch.setattr("cc_deep_research.content_gen.router.load_config", lambda: config)
    allow_run = threading.Event()

    class FakeOrchestrator:
        def __init__(self, _config: Config) -> None:
            pass

        async def run_full_pipeline(
            self,
            theme: str,
            *,
            from_stage: int = 0,
            to_stage: int | None = None,
            progress_callback=None,
            stage_completed_callback=None,
        ) -> PipelineContext:
            assert theme == "pricing anchors"
            assert from_stage == 0
            assert to_stage == 3

            while not allow_run.is_set():
                await asyncio.sleep(0.001)

            if progress_callback is not None:
                progress_callback(3, "Scoring ideas")
            await asyncio.sleep(0)
            if stage_completed_callback is not None:
                stage_completed_callback(
                    3,
                    "failed",
                    "Malformed scoring response",
                    PipelineContext(
                        theme=theme,
                        current_stage=3,
                        stage_traces=[
                            PipelineStageTrace(
                                stage_index=3,
                                stage_name="score_ideas",
                                stage_label="Scoring ideas",
                                status="failed",
                                output_summary="Malformed scoring response",
                                decision_summary="Stage failed: Malformed scoring response",
                            ),
                        ],
                    ),
                )
            await asyncio.sleep(0)
            raise ValueError("Malformed scoring response")

    monkeypatch.setattr(
        "cc_deep_research.content_gen.orchestrator.ContentGenOrchestrator",
        FakeOrchestrator,
    )

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/content-gen/pipelines",
            json={"theme": "pricing anchors", "from_stage": 0, "to_stage": 3},
        )

        assert response.status_code == 202
        pipeline_id = response.json()["pipeline_id"]

        with client.websocket_connect(f"/ws/content-gen/pipeline/{pipeline_id}") as websocket:
            initial = websocket.receive_json()
            assert initial["type"] == "pipeline_status"
            assert initial["pipeline_id"] == pipeline_id

            allow_run.set()

            started = websocket.receive_json()
            failed = websocket.receive_json()
            pipeline_error = websocket.receive_json()

        assert started == {
            "type": "pipeline_stage_started",
            "stage_index": 3,
            "stage_label": "Scoring ideas",
            "timestamp": started["timestamp"],
        }
        assert failed == {
            "type": "pipeline_stage_failed",
            "stage_index": 3,
            "stage_label": "Scoring ideas",
            "error": "Malformed scoring response",
            "context": failed["context"],
            "timestamp": failed["timestamp"],
        }
        assert failed["context"]["current_stage"] == 3
        assert pipeline_error == {
            "type": "pipeline_error",
            "error": "Malformed scoring response",
            "timestamp": pipeline_error["timestamp"],
        }

        status_response = client.get(f"/api/content-gen/pipelines/{pipeline_id}")
        assert status_response.status_code == 200
        payload = status_response.json()
        assert payload["status"] == "failed"
        assert payload["error"] == "Malformed scoring response"


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


def test_get_config_returns_masked_persisted_and_effective_state(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The config read endpoint should expose masked values and override metadata."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "cc-deep-research"
    config_dir.mkdir(parents=True)
    (config_dir / "config.yaml").write_text(
        "output:\n  format: markdown\nllm:\n  openrouter:\n    api_key: sk-test\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CC_DEEP_RESEARCH_FORMAT", "json")

    client = TestClient(create_app())
    response = client.get("/api/config")

    assert response.status_code == 200
    payload = response.json()
    assert payload["persisted_config"]["output"]["format"] == "markdown"
    assert payload["effective_config"]["output"]["format"] == "json"
    assert payload["persisted_config"]["llm"]["openrouter"]["api_key"] == "********"
    assert "output.format" in payload["overridden_fields"]


def test_patch_config_persists_updates_and_returns_refreshed_payload(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The config patch endpoint should save valid partial updates."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    client = TestClient(create_app())
    response = client.patch(
        "/api/config",
        json={
            "updates": {
                "output.save_dir": "./custom-reports",
                "research.enable_cross_ref": False,
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["persisted_config"]["output"]["save_dir"] == "./custom-reports"
    assert payload["persisted_config"]["research"]["enable_cross_ref"] is False


def test_patch_config_clears_secret_fields(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The config patch endpoint should support explicit secret clear actions."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEYS", raising=False)
    config_dir = tmp_path / "xdg" / "cc-deep-research"
    config_dir.mkdir(parents=True)
    (config_dir / "config.yaml").write_text(
        "llm:\n  openrouter:\n    api_key: sk-test\n",
        encoding="utf-8",
    )

    client = TestClient(create_app())
    response = client.patch(
        "/api/config",
        json={
            "updates": {
                "llm.openrouter.api_key": {
                    "action": "clear",
                }
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["persisted_config"]["llm"]["openrouter"]["api_key"] is None


def test_patch_config_returns_structured_field_errors(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Invalid field paths should return a 400 with field-level errors."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    client = TestClient(create_app())
    response = client.patch(
        "/api/config",
        json={"updates": {"search.invalid": "value"}},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["fields"][0]["field"] == "search.invalid"


def test_patch_config_returns_override_conflicts(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Patching an env-overridden field should return a 409 conflict."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("CC_DEEP_RESEARCH_FORMAT", "json")

    client = TestClient(create_app())
    response = client.patch(
        "/api/config",
        json={"updates": {"output.format": "html"}},
    )

    assert response.status_code == 409
    payload = response.json()
    assert payload["conflicts"][0]["field"] == "output.format"


def test_session_detail_summary_preserves_prompt_metadata(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Historical session detail should serialize prompt metadata for dashboard inspection."""
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
    config_dir = tmp_path / "xdg" / "cc-deep-research"
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
        "archived": False,
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


def test_live_session_detail_returns_decision_graph(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Live session detail should expose the derived decision graph."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    telemetry_dir = tmp_path / "xdg" / "cc-deep-research" / "telemetry"
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
    telemetry_dir = tmp_path / "xdg" / "cc-deep-research" / "telemetry"
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


def test_session_bundle_includes_decision_graph(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Trace bundle export should preserve the derived decision graph."""
    pytest.importorskip("duckdb")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    telemetry_dir = tmp_path / "xdg" / "cc-deep-research" / "telemetry"
    db_path = tmp_path / "xdg" / "cc-deep-research" / "telemetry.duckdb"
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
            "archived": False,
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


def test_session_includes_checkpoint_inventory(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Session detail should include checkpoint inventory when available."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "cc-deep-research"
    telemetry_dir = config_dir / "telemetry"
    session_dir = telemetry_dir / "checkpoint-session"
    session_dir.mkdir(parents=True)

    # Create events file
    (session_dir / "events.jsonl").write_text(
        json.dumps({
            "event_id": "event-1",
            "sequence_number": 1,
            "timestamp": "2026-03-18T10:00:00Z",
            "session_id": "checkpoint-session",
            "event_type": "session.started",
            "category": "session",
            "name": "session",
            "status": "started",
            "metadata": {},
        })
        + "\n",
        encoding="utf-8",
    )

    # Create checkpoint manifest
    checkpoints_dir = session_dir / "checkpoints"
    checkpoints_dir.mkdir()
    (checkpoints_dir / "manifest.json").write_text(
        json.dumps({
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
        }),
        encoding="utf-8",
    )

    client = TestClient(create_app())
    response = client.get("/api/sessions/checkpoint-session?include_checkpoints=true")

    assert response.status_code == 200
    data = response.json()
    assert "checkpoints" in data
    assert data["checkpoints"]["total"] == 1
    assert data["checkpoints"]["latest_checkpoint_id"] == "cp-abc123"
    assert data["checkpoints"]["resume_available"] is True


def test_checkpoint_list_endpoint(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The checkpoints list endpoint should return checkpoint manifest."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "cc-deep-research"
    telemetry_dir = config_dir / "telemetry"
    session_dir = telemetry_dir / "checkpoint-list-session"
    session_dir.mkdir(parents=True)

    # Create events file to make session "exist"
    (session_dir / "events.jsonl").write_text(
        json.dumps({
            "event_id": "event-1",
            "sequence_number": 1,
            "timestamp": "2026-03-18T10:00:00Z",
            "session_id": "checkpoint-list-session",
            "event_type": "session.started",
            "category": "session",
            "name": "session",
            "status": "started",
            "metadata": {},
        })
        + "\n",
        encoding="utf-8",
    )

    # Create checkpoint manifest
    checkpoints_dir = session_dir / "checkpoints"
    checkpoints_dir.mkdir()
    (checkpoints_dir / "manifest.json").write_text(
        json.dumps({
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
        }),
        encoding="utf-8",
    )

    client = TestClient(create_app())
    response = client.get("/api/sessions/checkpoint-list-session/checkpoints")

    assert response.status_code == 200
    data = response.json()
    assert len(data["checkpoints"]) == 2
    assert data["latest_checkpoint_id"] == "cp-strategy"
    assert data["latest_resume_safe_checkpoint_id"] == "cp-strategy"


def test_checkpoint_detail_endpoint(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The checkpoint detail endpoint should return checkpoint with lineage."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "cc-deep-research"
    telemetry_dir = config_dir / "telemetry"
    session_dir = telemetry_dir / "checkpoint-detail-session"
    session_dir.mkdir(parents=True)

    # Create events file to make session "exist"
    (session_dir / "events.jsonl").write_text(
        json.dumps({
            "event_id": "event-1",
            "sequence_number": 1,
            "timestamp": "2026-03-18T10:00:00Z",
            "session_id": "checkpoint-detail-session",
            "event_type": "session.started",
            "category": "session",
            "name": "session",
            "status": "started",
            "metadata": {},
        })
        + "\n",
        encoding="utf-8",
    )

    # Create checkpoint manifest with lineage
    checkpoints_dir = session_dir / "checkpoints"
    checkpoints_dir.mkdir()
    (checkpoints_dir / "manifest.json").write_text(
        json.dumps({
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
        }),
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


def test_checkpoint_lineage_endpoint(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The checkpoint lineage endpoint should return ordered checkpoint chain."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "cc-deep-research"
    telemetry_dir = config_dir / "telemetry"
    session_dir = telemetry_dir / "checkpoint-lineage-session"
    session_dir.mkdir(parents=True)

    # Create events file to make session "exist"
    (session_dir / "events.jsonl").write_text(
        json.dumps({
            "event_id": "event-1",
            "sequence_number": 1,
            "timestamp": "2026-03-18T10:00:00Z",
            "session_id": "checkpoint-lineage-session",
            "event_type": "session.started",
            "category": "session",
            "name": "session",
            "status": "started",
            "metadata": {},
        })
        + "\n",
        encoding="utf-8",
    )

    # Create checkpoint manifest with multi-level lineage
    checkpoints_dir = session_dir / "checkpoints"
    checkpoints_dir.mkdir()
    (checkpoints_dir / "manifest.json").write_text(
        json.dumps({
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
        }),
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


def test_resume_endpoint_returns_resume_info(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The resume endpoint should return resume information for valid checkpoint."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "cc-deep-research"
    telemetry_dir = config_dir / "telemetry"
    session_dir = telemetry_dir / "resume-session"
    session_dir.mkdir(parents=True)

    # Create events file to make session "exist"
    (session_dir / "events.jsonl").write_text(
        json.dumps({
            "event_id": "event-1",
            "sequence_number": 1,
            "timestamp": "2026-03-18T10:00:00Z",
            "session_id": "resume-session",
            "event_type": "session.started",
            "category": "session",
            "name": "session",
            "status": "started",
            "metadata": {},
        })
        + "\n",
        encoding="utf-8",
    )

    # Create checkpoint manifest with resume-safe checkpoint
    checkpoints_dir = session_dir / "checkpoints"
    checkpoints_dir.mkdir()
    (checkpoints_dir / "manifest.json").write_text(
        json.dumps({
            "checkpoints": [
                {
                    "checkpoint_id": "cp-resumable",
                    "phase": "source_collection",
                    "operation": "execute",
                    "resume_safe": True,
                    "replayable": True,
                    "input_ref": {"query": "test query"},
                },
            ],
            "latest_resume_safe_checkpoint_id": "cp-resumable",
        }),
        encoding="utf-8",
    )

    client = TestClient(create_app())
    response = client.post("/api/sessions/resume-session/resume")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["resumed_from_checkpoint_id"] == "cp-resumable"
    assert data["original_session_id"] == "resume-session"
    assert "checkpoint_lineage" in data


def test_resume_endpoint_rejects_non_resumable_checkpoint(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The resume endpoint should reject non-resume-safe checkpoints."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "cc-deep-research"
    telemetry_dir = config_dir / "telemetry"
    session_dir = telemetry_dir / "non-resumable-session"
    session_dir.mkdir(parents=True)

    # Create events file to make session "exist"
    (session_dir / "events.jsonl").write_text(
        json.dumps({
            "event_id": "event-1",
            "sequence_number": 1,
            "timestamp": "2026-03-18T10:00:00Z",
            "session_id": "non-resumable-session",
            "event_type": "session.started",
            "category": "session",
            "name": "session",
            "status": "started",
            "metadata": {},
        })
        + "\n",
        encoding="utf-8",
    )

    # Create checkpoint manifest with non-resumable checkpoint
    checkpoints_dir = session_dir / "checkpoints"
    checkpoints_dir.mkdir()
    (checkpoints_dir / "manifest.json").write_text(
        json.dumps({
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
        }),
        encoding="utf-8",
    )

    client = TestClient(create_app())
    response = client.post("/api/sessions/non-resumable-session/resume?checkpoint_id=cp-failed")

    assert response.status_code == 409  # Conflict
    assert "not safe to resume" in response.json()["error"]


def test_rerun_step_endpoint_returns_rerun_info(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The rerun-step endpoint should return rerun information for replayable checkpoint."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "cc-deep-research"
    telemetry_dir = config_dir / "telemetry"
    session_dir = telemetry_dir / "rerun-session"
    session_dir.mkdir(parents=True)

    # Create events file to make session "exist"
    (session_dir / "events.jsonl").write_text(
        json.dumps({
            "event_id": "event-1",
            "sequence_number": 1,
            "timestamp": "2026-03-18T10:00:00Z",
            "session_id": "rerun-session",
            "event_type": "session.started",
            "category": "session",
            "name": "session",
            "status": "started",
            "metadata": {},
        })
        + "\n",
        encoding="utf-8",
    )

    # Create checkpoint manifest with replayable checkpoint
    checkpoints_dir = session_dir / "checkpoints"
    checkpoints_dir.mkdir()
    (checkpoints_dir / "manifest.json").write_text(
        json.dumps({
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
        }),
        encoding="utf-8",
    )

    client = TestClient(create_app())
    response = client.post(
        "/api/sessions/rerun-session/rerun-step",
        json={"session_id": "rerun-session", "checkpoint_id": "cp-replayable"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["checkpoint_id"] == "cp-replayable"


def test_rerun_step_rejects_non_replayable_checkpoint(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The rerun-step endpoint should reject non-replayable checkpoints."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "cc-deep-research"
    telemetry_dir = config_dir / "telemetry"
    session_dir = telemetry_dir / "non-replayable-session"
    session_dir.mkdir(parents=True)

    # Create events file to make session "exist"
    (session_dir / "events.jsonl").write_text(
        json.dumps({
            "event_id": "event-1",
            "sequence_number": 1,
            "timestamp": "2026-03-18T10:00:00Z",
            "session_id": "non-replayable-session",
            "event_type": "session.started",
            "category": "session",
            "name": "session",
            "status": "started",
            "metadata": {},
        })
        + "\n",
        encoding="utf-8",
    )

    # Create checkpoint manifest with non-replayable checkpoint
    checkpoints_dir = session_dir / "checkpoints"
    checkpoints_dir.mkdir()
    (checkpoints_dir / "manifest.json").write_text(
        json.dumps({
            "checkpoints": [
                {
                    "checkpoint_id": "cp-non-replayable",
                    "phase": "source_collection",
                    "operation": "execute",
                    "replayable": False,
                    "replayable_reason": "External API call with non-deterministic result",
                },
            ],
        }),
        encoding="utf-8",
    )

    client = TestClient(create_app())
    response = client.post(
        "/api/sessions/non-replayable-session/rerun-step",
        json={"session_id": "non-replayable-session", "checkpoint_id": "cp-non-replayable"},
    )

    assert response.status_code == 409  # Conflict
    assert "not replayable" in response.json()["error"]


# Search Cache API Tests

def test_search_cache_stats_returns_disabled_when_cache_off(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cache stats should indicate when cache is disabled."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    client = TestClient(create_app())
    response = client.get("/api/search-cache/stats")

    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is False
    assert data["total_entries"] == 0
    assert data["active_entries"] == 0


def test_search_cache_list_returns_empty_when_disabled(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cache list should return empty when cache is disabled."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    client = TestClient(create_app())
    response = client.get("/api/search-cache")

    assert response.status_code == 200
    data = response.json()
    assert data["entries"] == []
    assert data["total"] == 0
    assert "disabled" in data.get("message", "").lower()


def test_search_cache_stats_returns_counts_when_enabled(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cache stats should return entry counts when cache is enabled."""
    from cc_deep_research.search_cache import SearchCacheStore, build_search_cache_identity
    from cc_deep_research.models import SearchOptions, ResearchDepth, SearchResult

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "cc-deep-research"
    config_dir.mkdir(parents=True)

    # Add an entry to the cache
    db_path = config_dir / "search-cache.sqlite3"

    # Create config with cache enabled and explicit db_path
    (config_dir / "config.yaml").write_text(
        f"search_cache:\n  enabled: true\n  ttl_seconds: 3600\n  max_entries: 1000\n  db_path: {db_path}\n",
        encoding="utf-8",
    )

    store = SearchCacheStore(db_path)
    identity = build_search_cache_identity(
        provider_name="tavily",
        query="test query",
        options=SearchOptions(search_depth=ResearchDepth.DEEP),
    )
    store.put(
        identity=identity,
        result=SearchResult(query="test query", provider="tavily"),
        ttl_seconds=3600,
    )

    client = TestClient(create_app())
    response = client.get("/api/search-cache/stats")

    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True
    assert data["total_entries"] == 1
    assert data["active_entries"] == 1
    assert data["expired_entries"] == 0
    assert data["db_exists"] is True


def test_search_cache_list_returns_entries_when_enabled(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cache list should return entries when cache is enabled."""
    from cc_deep_research.search_cache import SearchCacheStore, build_search_cache_identity
    from cc_deep_research.models import SearchOptions, ResearchDepth, SearchResult

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "cc-deep-research"
    config_dir.mkdir(parents=True)

    # Add an entry to the cache
    db_path = config_dir / "search-cache.sqlite3"

    # Create config with cache enabled and explicit db_path
    (config_dir / "config.yaml").write_text(
        f"search_cache:\n  enabled: true\n  ttl_seconds: 3600\n  max_entries: 1000\n  db_path: {db_path}\n",
        encoding="utf-8",
    )

    store = SearchCacheStore(db_path)
    identity = build_search_cache_identity(
        provider_name="tavily",
        query="cache list test",
        options=SearchOptions(search_depth=ResearchDepth.DEEP),
    )
    store.put(
        identity=identity,
        result=SearchResult(query="cache list test", provider="tavily"),
        ttl_seconds=3600,
    )

    client = TestClient(create_app())
    response = client.get("/api/search-cache")

    assert response.status_code == 200
    data = response.json()
    assert len(data["entries"]) == 1
    assert data["total"] == 1
    entry = data["entries"][0]
    assert entry["provider"] == "tavily"
    assert entry["normalized_query"] == "cache list test"
    assert entry["is_expired"] is False


def test_search_cache_purge_expired_removes_old_entries(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Purge expired should remove entries past their TTL."""
    from cc_deep_research.search_cache import SearchCacheStore, build_search_cache_identity
    from cc_deep_research.models import SearchOptions, ResearchDepth, SearchResult

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "cc-deep-research"
    config_dir.mkdir(parents=True)

    # Add an expired entry to the cache
    db_path = config_dir / "search-cache.sqlite3"

    # Create config with cache enabled and explicit db_path
    (config_dir / "config.yaml").write_text(
        f"search_cache:\n  enabled: true\n  ttl_seconds: 3600\n  max_entries: 1000\n  db_path: {db_path}\n",
        encoding="utf-8",
    )

    store = SearchCacheStore(db_path)
    identity = build_search_cache_identity(
        provider_name="tavily",
        query="expired query",
        options=SearchOptions(search_depth=ResearchDepth.DEEP),
    )
    store.put(
        identity=identity,
        result=SearchResult(query="expired query", provider="tavily"),
        ttl_seconds=-1,  # Already expired
    )

    client = TestClient(create_app())
    response = client.post("/api/search-cache/purge-expired")

    assert response.status_code == 200
    data = response.json()
    assert data["purged"] >= 1


def test_search_cache_delete_entry_removes_specific_entry(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Delete entry should remove a specific cache entry."""
    from cc_deep_research.search_cache import SearchCacheStore, build_search_cache_identity
    from cc_deep_research.models import SearchOptions, ResearchDepth, SearchResult

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "cc-deep-research"
    config_dir.mkdir(parents=True)

    # Add an entry to the cache
    db_path = config_dir / "search-cache.sqlite3"

    # Create config with cache enabled and explicit db_path
    (config_dir / "config.yaml").write_text(
        f"search_cache:\n  enabled: true\n  ttl_seconds: 3600\n  max_entries: 1000\n  db_path: {db_path}\n",
        encoding="utf-8",
    )

    store = SearchCacheStore(db_path)
    identity = build_search_cache_identity(
        provider_name="tavily",
        query="delete test query",
        options=SearchOptions(search_depth=ResearchDepth.DEEP),
    )
    store.put(
        identity=identity,
        result=SearchResult(query="delete test query", provider="tavily"),
        ttl_seconds=3600,
    )
    cache_key = identity.to_cache_key()

    client = TestClient(create_app())
    response = client.delete(f"/api/search-cache/{cache_key}")

    assert response.status_code == 200
    data = response.json()
    assert data["deleted"] is True
    assert data["cache_key"] == cache_key

    # Verify entry is gone
    stats_response = client.get("/api/search-cache/stats")
    assert stats_response.json()["total_entries"] == 0


def test_search_cache_clear_removes_all_entries(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Clear should remove all cache entries."""
    from cc_deep_research.search_cache import SearchCacheStore, build_search_cache_identity
    from cc_deep_research.models import SearchOptions, ResearchDepth, SearchResult

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    config_dir = tmp_path / "xdg" / "cc-deep-research"
    config_dir.mkdir(parents=True)

    # Add multiple entries to the cache
    db_path = config_dir / "search-cache.sqlite3"

    # Create config with cache enabled and explicit db_path
    (config_dir / "config.yaml").write_text(
        f"search_cache:\n  enabled: true\n  ttl_seconds: 3600\n  max_entries: 1000\n  db_path: {db_path}\n",
        encoding="utf-8",
    )

    store = SearchCacheStore(db_path)
    for i in range(3):
        identity = build_search_cache_identity(
            provider_name="tavily",
            query=f"clear test query {i}",
            options=SearchOptions(search_depth=ResearchDepth.DEEP),
        )
        store.put(
            identity=identity,
            result=SearchResult(query=f"clear test query {i}", provider="tavily"),
            ttl_seconds=3600,
        )

    client = TestClient(create_app())
    response = client.delete("/api/search-cache")

    assert response.status_code == 200
    data = response.json()
    assert data["cleared"] == 3

    # Verify all entries are gone
    stats_response = client.get("/api/search-cache/stats")
    assert stats_response.json()["total_entries"] == 0
