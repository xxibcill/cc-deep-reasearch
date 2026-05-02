"""Tests for FastAPI dashboard runtime state."""

from __future__ import annotations

import asyncio
import json
import threading
import time

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
from cc_deep_research.web_server import (
    create_app,
    get_pipeline_job_registry,
)


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


def test_resume_pipeline_creates_distinct_jobs_per_attempt(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repeated resume requests should not reuse the same pipeline job id."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    class FakeOrchestrator:
        def __init__(self, _config) -> None:
            pass

        def validate_resume_context(self, *, from_stage: int, ctx: PipelineContext) -> str | None:
            del from_stage, ctx
            return None

        async def run_full_pipeline(
            self,
            theme: str,
            *,
            from_stage: int = 0,
            to_stage: int | None = None,
            initial_context: PipelineContext | None = None,
            progress_callback=None,
            stage_completed_callback=None,
        ) -> PipelineContext:
            del theme, from_stage, to_stage, progress_callback, stage_completed_callback
            return initial_context or PipelineContext(theme="pricing anchors")

    import cc_deep_research.content_gen.pipeline as content_gen_pipeline_module
    import cc_deep_research.content_gen.router as content_gen_router_module

    monkeypatch.setattr(content_gen_router_module, "load_config", lambda: object())
    monkeypatch.setattr(
        content_gen_pipeline_module,
        "ContentGenPipeline",
        FakeOrchestrator,
    )

    app = create_app()
    pipeline_jobs = get_pipeline_job_registry(app)
    job = pipeline_jobs.create_job(
        "pricing anchors",
        from_stage=0,
        to_stage=8,
        pipeline_id="cgp-base",
    )
    ctx = PipelineContext(theme="pricing anchors", current_stage=4)
    pipeline_jobs.update_context(job.pipeline_id, ctx)
    pipeline_jobs.mark_failed(job.pipeline_id, error="interrupted")

    client = TestClient(app)
    first_response = client.post("/api/content-gen/pipelines/cgp-base/resume", json={"from_stage": 5})
    second_response = client.post("/api/content-gen/pipelines/cgp-base/resume", json={"from_stage": 5})

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first_job_id = first_response.json()["pipeline_id"]
    second_job_id = second_response.json()["pipeline_id"]

    assert first_job_id != second_job_id
    assert first_job_id.startswith("cgp-base-resume-")
    assert second_job_id.startswith("cgp-base-resume-")
    assert pipeline_jobs.get_job(first_job_id) is not None
    assert pipeline_jobs.get_job(second_job_id) is not None


def test_resume_context_isolation_from_original_failed_job(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resuming a failed pipeline must not mutate the original job's context snapshot.

    Regression test for: Resume jobs reuse the original PipelineContext object
    instead of cloning it, causing the failed run's saved state to change when
    the resumed run mutates current_stage or later stage outputs.
    """
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    class FakeOrchestrator:
        def __init__(self, _config) -> None:
            pass

        def validate_resume_context(self, *, from_stage: int, ctx: PipelineContext) -> str | None:
            del from_stage, ctx
            return None

        async def run_full_pipeline(
            self,
            theme: str,
            *,
            from_stage: int = 0,
            to_stage: int | None = None,
            initial_context: PipelineContext | None = None,
            progress_callback=None,
            stage_completed_callback=None,
        ) -> PipelineContext:
            # Clone like the real pipeline does before mutating resumed context.
            ctx = initial_context.model_copy(deep=True) if initial_context else PipelineContext(theme=theme)
            ctx.current_stage = 6
            if stage_completed_callback:
                stage_completed_callback(5, "completed", "stage 5 done", ctx)
            return ctx

    import cc_deep_research.content_gen.pipeline as content_gen_pipeline_module
    import cc_deep_research.content_gen.router as content_gen_router_module

    monkeypatch.setattr(content_gen_router_module, "load_config", lambda: object())
    monkeypatch.setattr(
        content_gen_pipeline_module,
        "ContentGenPipeline",
        FakeOrchestrator,
    )

    app = create_app()
    pipeline_jobs = get_pipeline_job_registry(app)

    # Create a failed job with a saved context
    failed_job = pipeline_jobs.create_job(
        "pricing anchors",
        from_stage=0,
        to_stage=8,
        pipeline_id="cgp-isolate-test",
    )
    original_ctx = PipelineContext(theme="pricing anchors", current_stage=4)
    pipeline_jobs.update_context(failed_job.pipeline_id, original_ctx)
    pipeline_jobs.mark_failed(failed_job.pipeline_id, error="interrupted at stage 4")

    # Capture the original context's current_stage before resume
    original_stage_before_resume = failed_job.pipeline_context.current_stage

    client = TestClient(app)
    resume_response = client.post(
        "/api/content-gen/pipelines/cgp-isolate-test/resume",
        json={"from_stage": 5},
    )
    assert resume_response.status_code == 200

    # Wait for the async task to complete
    resume_job_id = resume_response.json()["pipeline_id"]
    for _ in range(50):
        resumed_job = pipeline_jobs.get_job(resume_job_id)
        if resumed_job and resumed_job.status in {"completed", "failed"}:
            break
        time.sleep(0.05)

    # The original failed job's context must NOT reflect mutations made by the resume run
    refreshed_failed_job = pipeline_jobs.get_job("cgp-isolate-test")
    assert refreshed_failed_job is not None
    assert refreshed_failed_job.pipeline_context is not None
    assert (
        refreshed_failed_job.pipeline_context.current_stage == original_stage_before_resume
    ), "Original failed job's context was mutated by the resumed run"


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
        def extract_script(ctx: ScriptingContext) -> str:
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

    monkeypatch.setattr("cc_deep_research.content_gen.scripting_api_service.ScriptingStore", FakeStore)
    monkeypatch.setattr(
        "cc_deep_research.content_gen.scripting_api_service.ScriptingRunService",
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
        def extract_script(ctx: ScriptingContext) -> str:
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

    monkeypatch.setattr("cc_deep_research.content_gen.scripting_api_service.ScriptingStore", FakeStore)
    monkeypatch.setattr(
        "cc_deep_research.content_gen.scripting_api_service.ScriptingRunService",
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

    monkeypatch.setattr("cc_deep_research.content_gen.scripting_api_service.ScriptingStore", FakeStore)

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
            initial_context=None,
            bypass_ideation=False,
            progress_callback=None,
            stage_completed_callback=None,
            brief_id=None,
            brief_snapshot=None,
            run_constraints=None,
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
        "cc_deep_research.content_gen.pipeline.ContentGenPipeline",
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
            initial_context=None,
            bypass_ideation=False,
            progress_callback=None,
            stage_completed_callback=None,
            brief_id=None,
            brief_snapshot=None,
            run_constraints=None,
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
        "cc_deep_research.content_gen.pipeline.ContentGenPipeline",
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


def test_backlog_list_returns_empty_on_fresh_store(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /api/content-gen/backlog should return empty items list on fresh store."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    client = TestClient(create_app())
    response = client.get("/api/content-gen/backlog")

    assert response.status_code == 200
    data = response.json()
    assert "path" in data
    assert data["items"] == []


def test_backlog_create_item_returns_201_with_valid_input(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /api/content-gen/backlog should create item and return 201."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    client = TestClient(create_app())
    response = client.post(
        "/api/content-gen/backlog",
        json={
            "idea": "Test idea for backlog",
            "category": "trend-responsive",
            "audience": "Tech executives",
            "problem": "AI adoption challenges",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["idea"] == "Test idea for backlog"
    assert data["category"] == "trend-responsive"
    assert data["status"] == "backlog"
    assert "idea_id" in data
    assert data["created_at"] != ""


def test_backlog_create_with_minimal_input(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /api/content-gen/backlog should accept idea-only input."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    client = TestClient(create_app())
    response = client.post(
        "/api/content-gen/backlog",
        json={"idea": "Simple idea"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["idea"] == "Simple idea"
    assert data["idea_id"] != ""


def test_backlog_create_with_invalid_input_returns_422(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /api/content-gen/backlog should return 422 for missing idea."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    client = TestClient(create_app())
    response = client.post(
        "/api/content-gen/backlog",
        json={},
    )

    assert response.status_code == 422


def test_backlog_list_returns_created_items(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /api/content-gen/backlog should return items created via POST."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    client = TestClient(create_app())

    # Create two items
    client.post(
        "/api/content-gen/backlog",
        json={"idea": "First idea", "category": "evergreen"},
    )
    client.post(
        "/api/content-gen/backlog",
        json={"idea": "Second idea", "category": "authority-building"},
    )

    response = client.get("/api/content-gen/backlog")

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    ideas = {item["idea"] for item in data["items"]}
    assert "First idea" in ideas
    assert "Second idea" in ideas


def test_backlog_update_item_returns_updated_fields(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PATCH /api/content-gen/backlog/{idea_id} should update and return item."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    client = TestClient(create_app())

    # Create an item
    create_response = client.post(
        "/api/content-gen/backlog",
        json={"idea": "Update me"},
    )
    idea_id = create_response.json()["idea_id"]

    # Update it (patch key wraps the fields per API contract)
    response = client.patch(
        f"/api/content-gen/backlog/{idea_id}",
        json={"patch": {"idea": "Updated idea", "risk_level": "high"}},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["idea"] == "Updated idea"
    assert data["risk_level"] == "high"
    assert data["idea_id"] == idea_id


def test_backlog_update_item_returns_404_for_unknown_id(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PATCH /api/content-gen/backlog/{idea_id} should return 404 for unknown ID."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    client = TestClient(create_app())
    response = client.patch(
        "/api/content-gen/backlog/unknown-id-123",
        json={"idea": "Should fail"},
    )

    assert response.status_code == 404
    assert "not found" in response.json()["error"].lower()


def test_backlog_select_item_returns_selected_item(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /api/content-gen/backlog/{idea_id}/select should select the item."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    client = TestClient(create_app())

    # Create two items
    first_response = client.post(
        "/api/content-gen/backlog",
        json={"idea": "First item"},
    )
    second_response = client.post(
        "/api/content-gen/backlog",
        json={"idea": "Second item"},
    )
    first_id = first_response.json()["idea_id"]
    second_id = second_response.json()["idea_id"]

    # Select the first item
    response = client.post(f"/api/content-gen/backlog/{first_id}/select")

    assert response.status_code == 200
    data = response.json()
    assert data["idea_id"] == first_id
    assert data["status"] == "selected"

    # Verify the second item is still in backlog
    list_response = client.get("/api/content-gen/backlog")
    items = {item["idea_id"]: item for item in list_response.json()["items"]}
    assert items[second_id]["status"] == "backlog"


def test_backlog_select_item_returns_404_for_unknown_id(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /api/content-gen/backlog/{idea_id}/select should return 404 for unknown ID."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    client = TestClient(create_app())
    response = client.post("/api/content-gen/backlog/unknown-id/select")

    assert response.status_code == 404
    assert "not found" in response.json()["error"].lower()


def test_backlog_archive_item_returns_archived_item(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /api/content-gen/backlog/{idea_id}/archive should archive the item."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    client = TestClient(create_app())

    # Create an item
    create_response = client.post(
        "/api/content-gen/backlog",
        json={"idea": "Archive me"},
    )
    idea_id = create_response.json()["idea_id"]

    # Archive it
    response = client.post(f"/api/content-gen/backlog/{idea_id}/archive")

    assert response.status_code == 200
    data = response.json()
    assert data["idea_id"] == idea_id
    assert data["status"] == "archived"


def test_backlog_archive_item_returns_404_for_unknown_id(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /api/content-gen/backlog/{idea_id}/archive should return 404 for unknown ID."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    client = TestClient(create_app())
    response = client.post("/api/content-gen/backlog/unknown-id/archive")

    assert response.status_code == 404
    assert "not found" in response.json()["error"].lower()


def test_backlog_delete_item_returns_removed(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DELETE /api/content-gen/backlog/{idea_id} should remove the item."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    client = TestClient(create_app())

    # Create an item
    create_response = client.post(
        "/api/content-gen/backlog",
        json={"idea": "Delete me"},
    )
    idea_id = create_response.json()["idea_id"]

    # Delete it
    response = client.delete(f"/api/content-gen/backlog/{idea_id}")

    assert response.status_code == 200
    assert response.json()["removed"] == 1

    # Verify it's gone from list
    list_response = client.get("/api/content-gen/backlog")
    items = list_response.json()["items"]
    assert not any(item["idea_id"] == idea_id for item in items)


def test_backlog_delete_item_returns_404_for_unknown_id(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DELETE /api/content-gen/backlog/{idea_id} should return 404 for unknown ID."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    client = TestClient(create_app())
    response = client.delete("/api/content-gen/backlog/unknown-id")

    assert response.status_code == 404
    assert "not found" in response.json()["error"].lower()


def test_backlog_mutations_persist_through_store(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backlog mutations should persist through the managed backlog store."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    client = TestClient(create_app())

    # Create item
    create_response = client.post(
        "/api/content-gen/backlog",
        json={"idea": "Persistent idea"},
    )
    idea_id = create_response.json()["idea_id"]

    # Update item (patch key wraps the fields per API contract)
    client.patch(
        f"/api/content-gen/backlog/{idea_id}",
        json={"patch": {"idea": "Updated persistent idea"}},
    )

    # Select item
    client.post(f"/api/content-gen/backlog/{idea_id}/select")

    # List should show updated state
    list_response = client.get("/api/content-gen/backlog")
    items = list_response.json()["items"]
    item = next(i for i in items if i["idea_id"] == idea_id)
    assert item["idea"] == "Updated persistent idea"
    assert item["status"] == "selected"


def test_start_backlog_item_returns_202_with_pipeline_id(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /api/content-gen/backlog/{idea_id}/start returns 202 and pipeline_id."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    from cc_deep_research.content_gen.models import PipelineContext

    class FakeOrchestrator:
        def __init__(self, _config) -> None:
            pass

        async def run_full_pipeline(
            self,
            theme,
            *,
            from_stage: int = 0,
            to_stage: int | None = None,
            initial_context: PipelineContext | None = None,
            bypass_ideation=False,
            progress_callback=None,
            stage_completed_callback=None,
            brief_id=None,
            brief_snapshot=None,
            run_constraints=None,
        ) -> PipelineContext:
            return initial_context or PipelineContext(theme=theme)

    import cc_deep_research.content_gen.pipeline as content_gen_pipeline_module
    import cc_deep_research.content_gen.router as content_gen_router_module

    monkeypatch.setattr(content_gen_router_module, "load_config", lambda: object())
    monkeypatch.setattr(
        content_gen_pipeline_module,
        "ContentGenPipeline",
        FakeOrchestrator,
    )

    client = TestClient(create_app())

    # Create a backlog item
    create_response = client.post(
        "/api/content-gen/backlog",
        json={"idea": "Test start item"},
    )
    idea_id = create_response.json()["idea_id"]

    # Start production
    response = client.post(f"/api/content-gen/backlog/{idea_id}/start")

    assert response.status_code == 202
    data = response.json()
    assert "pipeline_id" in data
    assert data["idea_id"] == idea_id
    assert data["from_stage"] == 4
    assert data["to_stage"] == 13  # last stage index (14 stages, 0-indexed)


def test_start_backlog_item_returns_404_for_unknown_id(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /api/content-gen/backlog/{idea_id}/start returns 404 for unknown ID."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    client = TestClient(create_app())
    response = client.post("/api/content-gen/backlog/nonexistent-id/start")

    assert response.status_code == 404
    assert "not found" in response.json()["error"].lower()


def test_start_backlog_item_returns_409_on_duplicate_active_run(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Starting an item that already has an active pipeline returns 409."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))


    class FakeOrchestrator:
        def __init__(self, _config) -> None:
            pass

        async def run_full_pipeline(
            self,
            theme,
            *,
            from_stage: int = 0,
            to_stage: int | None = None,
            initial_context: PipelineContext | None = None,
            bypass_ideation=False,
            progress_callback=None,
            stage_completed_callback=None,
            brief_id=None,
            brief_snapshot=None,
            run_constraints=None,
        ) -> PipelineContext:
            # Wait forever so the job stays "running"
            await asyncio.Future()

    import cc_deep_research.content_gen.pipeline as content_gen_pipeline_module
    import cc_deep_research.content_gen.router as content_gen_router_module

    monkeypatch.setattr(content_gen_router_module, "load_config", lambda: object())
    monkeypatch.setattr(
        content_gen_pipeline_module,
        "ContentGenPipeline",
        FakeOrchestrator,
    )

    client = TestClient(create_app())

    # Create a backlog item
    create_response = client.post(
        "/api/content-gen/backlog",
        json={"idea": "Duplicate test item"},
    )
    idea_id = create_response.json()["idea_id"]

    # Start first production run
    first_response = client.post(f"/api/content-gen/backlog/{idea_id}/start")
    assert first_response.status_code == 202
    first_pipeline_id = first_response.json()["pipeline_id"]

    # Attempt to start second time — should get 409
    second_response = client.post(f"/api/content-gen/backlog/{idea_id}/start")
    assert second_response.status_code == 409
    data = second_response.json()
    assert "pipeline_id" in data
    assert data["pipeline_id"] == first_pipeline_id


def test_start_backlog_item_seeds_context_with_selected_idea_id(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The started job's context is seeded with the item as primary selected candidate."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    from cc_deep_research.content_gen.models import PipelineContext

    captured_context: dict | None = None

    class FakeOrchestrator:
        def __init__(self, _config) -> None:
            pass

        async def run_full_pipeline(
            self,
            theme,
            *,
            from_stage: int = 0,
            to_stage: int | None = None,
            initial_context: PipelineContext | None = None,
            bypass_ideation=False,
            progress_callback=None,
            stage_completed_callback=None,
            brief_id=None,
            brief_snapshot=None,
            run_constraints=None,
        ) -> PipelineContext:
            nonlocal captured_context
            captured_context = initial_context
            return initial_context or PipelineContext(theme=theme)

    import cc_deep_research.content_gen.pipeline as content_gen_pipeline_module
    import cc_deep_research.content_gen.router as content_gen_router_module

    monkeypatch.setattr(content_gen_router_module, "load_config", lambda: object())
    monkeypatch.setattr(
        content_gen_pipeline_module,
        "ContentGenPipeline",
        FakeOrchestrator,
    )

    client = TestClient(create_app())

    # Create a backlog item
    create_response = client.post(
        "/api/content-gen/backlog",
        json={"idea": "Context seed test item", "selection_reasoning": "My reasoning"},
    )
    idea_id = create_response.json()["idea_id"]

    # Start production
    response = client.post(f"/api/content-gen/backlog/{idea_id}/start")
    assert response.status_code == 202

    # Verify captured context
    assert captured_context is not None
    assert captured_context.selected_idea_id == idea_id
    assert captured_context.shortlist == [idea_id]
    assert captured_context.backlog is not None
    assert len(captured_context.backlog.items) == 1
    assert captured_context.backlog.items[0].idea_id == idea_id
    assert len(captured_context.active_candidates) == 1
    assert captured_context.active_candidates[0].idea_id == idea_id
    assert captured_context.active_candidates[0].role == "primary"
    assert captured_context.active_candidates[0].status == "selected"
    assert captured_context.selection_reasoning == "My reasoning"
    assert captured_context.current_stage == 4  # starts at generate_angles


def test_start_backlog_item_respects_from_stage_4(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The started run uses from_stage=4 (generate_angles)."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    from cc_deep_research.content_gen.models import PipelineContext

    captured_from_stage: int | None = None

    class FakeOrchestrator:
        def __init__(self, _config) -> None:
            pass

        async def run_full_pipeline(
            self,
            theme,
            *,
            from_stage: int = 0,
            to_stage: int | None = None,
            initial_context: PipelineContext | None = None,
            bypass_ideation=False,
            progress_callback=None,
            stage_completed_callback=None,
            brief_id=None,
            brief_snapshot=None,
            run_constraints=None,
        ) -> PipelineContext:
            nonlocal captured_from_stage
            captured_from_stage = from_stage
            return initial_context or PipelineContext(theme=theme)

    import cc_deep_research.content_gen.pipeline as content_gen_pipeline_module
    import cc_deep_research.content_gen.router as content_gen_router_module

    monkeypatch.setattr(content_gen_router_module, "load_config", lambda: object())
    monkeypatch.setattr(
        content_gen_pipeline_module,
        "ContentGenPipeline",
        FakeOrchestrator,
    )

    client = TestClient(create_app())

    # Create a backlog item
    create_response = client.post(
        "/api/content-gen/backlog",
        json={"idea": "Stage index test item"},
    )
    idea_id = create_response.json()["idea_id"]

    # Start production
    response = client.post(f"/api/content-gen/backlog/{idea_id}/start")
    assert response.status_code == 202

    assert captured_from_stage == 4
    assert response.json()["from_stage"] == 4
