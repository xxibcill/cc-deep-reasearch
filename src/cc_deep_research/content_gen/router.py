"""FastAPI router for content generation pipeline endpoints."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator

from cc_deep_research.config import load_config
from cc_deep_research.content_gen.agents.backlog_chat import (
    BacklogChatAgent,
    apply_operations,
    build_apply_operations,
)
from cc_deep_research.content_gen.agents.backlog_triage import (
    BatchTriageAgent,
    apply_triage_operations,
)
from cc_deep_research.content_gen.agents.backlog_triage import (
    build_apply_operations as build_triage_apply_operations,
)
from cc_deep_research.content_gen.agents.execution_brief import ExecutionBriefAgent
from cc_deep_research.content_gen.agents.next_action import NextActionAgent
from cc_deep_research.content_gen.backlog_service import BacklogService
from cc_deep_research.content_gen.maintenance_workflow import (
    MaintenanceJobType,
    MaintenanceProposalStatus,
    MaintenanceScheduler,
    MaintenanceStore,
)
from cc_deep_research.content_gen.models import (
    PIPELINE_STAGE_LABELS,
    PIPELINE_STAGES,
    BacklogItem,
    PipelineContext,
    ScriptingContext,
    ScriptingIterations,
    ScriptingIterationSummary,
    ScriptingRunResult,
)
from cc_deep_research.content_gen.progress import (
    PipelineRunJob,
    PipelineRunJobRegistry,
)
from cc_deep_research.content_gen.storage import (
    AuditActor,
    AuditEventType,
    AuditStore,
    PublishQueueStore,
    ScriptingStore,
    StrategyStore,
)
from cc_deep_research.event_router import EventRouter, WebSocketConnection

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class StartPipelineRequest(BaseModel):
    """Request body for starting a pipeline run."""

    theme: str = Field(min_length=1)
    from_stage: int = Field(default=0, ge=0)
    to_stage: int | None = Field(default=None, ge=0)


class ResumePipelineRequest(BaseModel):
    """Request body for resuming a pipeline run."""

    from_stage: int = Field(default=0, ge=0)


class RunScriptingRequest(BaseModel):
    """Request body for standalone scripting runs."""

    idea: str = Field(min_length=1)
    iterative_mode: bool | None = None
    max_iterations: int | None = Field(default=None, ge=1, le=5)
    llm_route: Literal["openrouter", "cerebras", "anthropic", "heuristic"] | None = Field(
        default=None
    )


class UpdateStrategyRequest(BaseModel):
    """Request body for updating strategy memory."""

    patch: dict[str, Any] = Field(default_factory=dict)


class UpdateBacklogItemRequest(BaseModel):
    """Request body for updating one backlog item."""

    patch: dict[str, Any] = Field(default_factory=dict)


class CreateBacklogItemRequest(BaseModel):
    """Request body for creating a new backlog item."""

    title: str = ""
    one_line_summary: str = ""
    raw_idea: str = ""
    constraints: str = ""
    idea: str = ""
    category: str = ""
    audience: str = ""
    persona_detail: str = ""
    problem: str = ""
    emotional_driver: str = ""
    urgency_level: str = ""
    source: str = ""
    why_now: str = ""
    hook: str = ""
    content_type: str = ""
    format_duration: str = ""
    key_message: str = ""
    call_to_action: str = ""
    evidence: str = ""
    proof_gap_note: str = ""
    expertise_reason: str = ""
    genericity_risk: str = ""
    risk_level: str = "medium"
    source_theme: str = ""
    selection_reasoning: str = ""

    @model_validator(mode="after")
    def _require_title_or_idea(self) -> CreateBacklogItemRequest:
        if not (self.title or self.idea or self.raw_idea):
            raise ValueError("One of 'title', legacy 'idea', or 'raw_idea' is required")
        return self


class BacklogChatMessage(BaseModel):
    """A single message in the backlog chat conversation."""

    role: Literal["user", "assistant"]
    content: str


class BacklogChatOperationInput(BaseModel):
    """Operation proposed by the chat agent (used in apply request)."""

    kind: Literal["update_item", "create_item"]
    idea_id: str | None = None
    reason: str = ""
    fields: dict[str, Any] = Field(default_factory=dict)


class BacklogChatRespondRequest(BaseModel):
    """Request body for backlog-chat respond endpoint."""

    messages: list[BacklogChatMessage] = Field(default_factory=list)
    backlog_items: list[BacklogItem] = Field(default_factory=list)
    strategy: dict[str, Any] | None = None
    selected_idea_id: str | None = None
    mode: Literal["conversation", "edit"] = "edit"


class BacklogChatApplyRequest(BaseModel):
    """Request body for backlog-chat apply endpoint."""

    operations: list[BacklogChatOperationInput] = Field(default_factory=list)


class TriageOperationInput(BaseModel):
    """Triage operation proposed by the batch triage agent (used in apply request)."""

    kind: Literal[
        "batch_enrich",
        "batch_reframe",
        "dedupe_recommendation",
        "archive_recommendation",
        "priority_recommendation",
    ]
    idea_ids: list[str] = Field(default_factory=list)
    reason: str = ""
    fields: dict[str, Any] = Field(default_factory=dict)
    preferred_idea_id: str | None = None


class TriageRespondRequest(BaseModel):
    """Request body for backlog-ai triage respond endpoint."""

    backlog_items: list[BacklogItem] = Field(default_factory=list)
    strategy: dict[str, Any] | None = None


class TriageApplyRequest(BaseModel):
    """Request body for backlog-ai triage apply endpoint."""

    operations: list[TriageOperationInput] = Field(default_factory=list)


class NextActionRequest(BaseModel):
    """Request body for next-action recommendation endpoint."""

    idea_id: str = Field(min_length=1)
    strategy: dict[str, Any] | None = None


class ExecutionBriefRequest(BaseModel):
    """Request body for execution brief generation endpoint."""

    idea_id: str = Field(min_length=1)
    strategy: dict[str, Any] | None = None


def _build_scripting_iterations(iter_state: Any) -> ScriptingIterations | None:
    if iter_state is None:
        return None
    return ScriptingIterations(
        count=iter_state.current_iteration,
        max_iterations=iter_state.max_iterations,
        converged=iter_state.is_converged,
        quality_history=[
            ScriptingIterationSummary(
                iteration=q.iteration_number,
                score=q.overall_quality_score,
                passes=q.passes_threshold,
            )
            for q in iter_state.quality_history
        ],
    )


def _build_scripting_result(
    ctx: ScriptingContext,
    *,
    run_id: str | None = None,
    execution_mode: Literal["single_pass", "iterative"] = "single_pass",
    iterations: ScriptingIterations | None = None,
) -> ScriptingRunResult:
    script = ScriptingStore.extract_script(ctx)
    return ScriptingRunResult(
        run_id=run_id,
        raw_idea=ctx.raw_idea,
        script=script,
        word_count=len(script.split()) if script else 0,
        context=ctx,
        execution_mode=execution_mode,
        iterations=iterations,
    )


def _serialize_scripting_payload(result: ScriptingRunResult) -> dict[str, Any]:
    payload = result.model_dump(mode="json")
    if payload.get("iterations") is None:
        payload.pop("iterations", None)
    return payload


def _serialize_saved_script_run(run: Any) -> dict[str, Any]:
    payload = run.model_dump(mode="json")
    if payload.get("iterations") is None:
        payload.pop("iterations", None)
    return payload


# ---------------------------------------------------------------------------
# Router registration
# ---------------------------------------------------------------------------


def register_content_gen_routes(
    app: FastAPI,
    event_router: EventRouter,
    job_registry: PipelineRunJobRegistry,
) -> None:
    """Register all content-gen API and WebSocket routes on *app*."""

    @app.get("/api/content-gen/pipelines")
    async def list_pipelines() -> JSONResponse:
        jobs = job_registry.list_jobs()
        items = []
        for job in jobs:
            items.append(_job_summary(job))
        return JSONResponse(content={"items": items})

    @app.post("/api/content-gen/pipelines", status_code=202)
    async def start_pipeline(request: StartPipelineRequest) -> JSONResponse:
        config = load_config()
        end = request.to_stage if request.to_stage is not None else len(PIPELINE_STAGES) - 1

        job = job_registry.create_job(
            theme=request.theme,
            from_stage=request.from_stage,
            to_stage=end,
        )

        async def _run() -> None:
            from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator

            orch = ContentGenOrchestrator(config)
            job_registry.mark_running(job.pipeline_id)

            def _progress(stage_idx: int, label: str) -> None:
                if job.stop_requested:
                    raise _PipelineCancelled(job.pipeline_id)
                asyncio.get_running_loop().create_task(
                    event_router.publish(
                        job.pipeline_id,
                        {
                            "type": "pipeline_stage_started",
                            "stage_index": stage_idx,
                            "stage_label": label,
                            "timestamp": datetime.now(UTC).isoformat(),
                        },
                    )
                )

            def _stage_completed(stage_idx: int, status: str, detail: str, stage_ctx) -> None:
                # Update job registry with latest context after each stage
                job_registry.update_context(job.pipeline_id, stage_ctx)
                serialized_context = stage_ctx.model_dump(mode="json")

                if status == "failed":
                    asyncio.get_running_loop().create_task(
                        event_router.publish(
                            job.pipeline_id,
                            {
                                "type": "pipeline_stage_failed",
                                "stage_index": stage_idx,
                                "stage_label": PIPELINE_STAGE_LABELS.get(
                                    PIPELINE_STAGES[stage_idx], ""
                                ),
                                "error": detail,
                                "context": serialized_context,
                                "timestamp": datetime.now(UTC).isoformat(),
                            },
                        )
                    )
                elif status == "skipped":
                    asyncio.get_running_loop().create_task(
                        event_router.publish(
                            job.pipeline_id,
                            {
                                "type": "pipeline_stage_skipped",
                                "stage_index": stage_idx,
                                "stage_label": PIPELINE_STAGE_LABELS.get(
                                    PIPELINE_STAGES[stage_idx], ""
                                ),
                                "reason": detail,
                                "context": serialized_context,
                                "timestamp": datetime.now(UTC).isoformat(),
                            },
                        )
                    )
                else:
                    asyncio.get_running_loop().create_task(
                        event_router.publish(
                            job.pipeline_id,
                            {
                                "type": "pipeline_stage_completed",
                                "stage_index": stage_idx,
                                "stage_status": status,
                                "stage_detail": detail,
                                "context": serialized_context,
                                "timestamp": datetime.now(UTC).isoformat(),
                            },
                        )
                    )

            try:
                ctx = await orch.run_full_pipeline(
                    request.theme,
                    from_stage=request.from_stage,
                    to_stage=end,
                    progress_callback=_progress,
                    stage_completed_callback=_stage_completed,
                )

                job_registry.update_context(job.pipeline_id, ctx)
                job_registry.mark_completed(job.pipeline_id, context=ctx)

                await event_router.publish(
                    job.pipeline_id,
                    {
                        "type": "pipeline_completed",
                        "current_stage": ctx.current_stage,
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                )
            except _PipelineCancelled:
                job_registry.mark_cancelled(job.pipeline_id)
                await event_router.publish(
                    job.pipeline_id,
                    {"type": "pipeline_cancelled", "timestamp": datetime.now(UTC).isoformat()},
                )
            except Exception as exc:
                logger.exception("Pipeline %s failed", job.pipeline_id)
                job_registry.mark_failed(job.pipeline_id, error=str(exc))
                await event_router.publish(
                    job.pipeline_id,
                    {
                        "type": "pipeline_error",
                        "error": str(exc),
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                )

        task = asyncio.create_task(_run())
        job_registry.attach_task(job.pipeline_id, task)
        return JSONResponse(status_code=202, content=_job_summary(job))

    @app.get("/api/content-gen/pipelines/{pipeline_id}")
    async def get_pipeline(pipeline_id: str) -> JSONResponse:
        job = job_registry.get_job(pipeline_id)
        if job is None:
            return JSONResponse(status_code=404, content={"error": "Pipeline not found"})
        result = _job_summary(job)
        if job.pipeline_context is not None:
            result["context"] = json.loads(job.pipeline_context.model_dump_json())
        return JSONResponse(content=result)

    @app.post("/api/content-gen/pipelines/{pipeline_id}/stop")
    async def stop_pipeline(pipeline_id: str) -> JSONResponse:
        job = job_registry.get_job(pipeline_id)
        if job is None:
            return JSONResponse(status_code=404, content={"error": "Pipeline not found"})
        if not job.is_active:
            return JSONResponse(status_code=409, content={"error": "Pipeline is not active"})
        job_registry.request_cancel(pipeline_id)
        return JSONResponse(content={"pipeline_id": pipeline_id, "status": "cancelling"})

    @app.post("/api/content-gen/pipelines/{pipeline_id}/resume")
    async def resume_pipeline(pipeline_id: str, request: ResumePipelineRequest) -> JSONResponse:
        job = job_registry.get_job(pipeline_id)
        if job is None:
            return JSONResponse(status_code=404, content={"error": "Pipeline not found"})
        if job.is_active:
            return JSONResponse(status_code=409, content={"error": "Pipeline is already active"})

        config = load_config()
        ctx = job.pipeline_context
        if ctx is None:
            return JSONResponse(status_code=400, content={"error": "No saved context to resume"})

        end = job.to_stage if job.to_stage is not None else len(PIPELINE_STAGES) - 1
        from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator

        orch = ContentGenOrchestrator(config)
        resume_error = orch.validate_resume_context(from_stage=request.from_stage, ctx=ctx)
        if resume_error:
            return JSONResponse(status_code=400, content={"error": resume_error})

        # Create a distinct job for each resume attempt so concurrent retries
        # cannot overwrite one another in the registry.
        new_job = job_registry.create_resume_job(
            pipeline_id,
            theme=job.theme,
            from_stage=request.from_stage,
            to_stage=end,
        )
        # Carry forward existing context
        job_registry.update_context(new_job.pipeline_id, ctx)

        async def _run() -> None:
            job_registry.mark_running(new_job.pipeline_id)

            def _progress(stage_idx: int, label: str) -> None:
                if new_job.stop_requested:
                    raise _PipelineCancelled(new_job.pipeline_id)
                asyncio.get_running_loop().create_task(
                    event_router.publish(
                        new_job.pipeline_id,
                        {
                            "type": "pipeline_stage_started",
                            "stage_index": stage_idx,
                            "stage_label": label,
                            "timestamp": datetime.now(UTC).isoformat(),
                        },
                    )
                )

            def _stage_completed(stage_idx: int, status: str, detail: str, stage_ctx) -> None:
                # Update job registry with latest context after each stage
                job_registry.update_context(new_job.pipeline_id, stage_ctx)
                serialized_context = stage_ctx.model_dump(mode="json")

                if status == "failed":
                    asyncio.get_running_loop().create_task(
                        event_router.publish(
                            new_job.pipeline_id,
                            {
                                "type": "pipeline_stage_failed",
                                "stage_index": stage_idx,
                                "stage_label": PIPELINE_STAGE_LABELS.get(
                                    PIPELINE_STAGES[stage_idx], ""
                                ),
                                "error": detail,
                                "context": serialized_context,
                                "timestamp": datetime.now(UTC).isoformat(),
                            },
                        )
                    )
                elif status == "skipped":
                    asyncio.get_running_loop().create_task(
                        event_router.publish(
                            new_job.pipeline_id,
                            {
                                "type": "pipeline_stage_skipped",
                                "stage_index": stage_idx,
                                "stage_label": PIPELINE_STAGE_LABELS.get(
                                    PIPELINE_STAGES[stage_idx], ""
                                ),
                                "reason": detail,
                                "context": serialized_context,
                                "timestamp": datetime.now(UTC).isoformat(),
                            },
                        )
                    )
                else:
                    asyncio.get_running_loop().create_task(
                        event_router.publish(
                            new_job.pipeline_id,
                            {
                                "type": "pipeline_stage_completed",
                                "stage_index": stage_idx,
                                "stage_status": status,
                                "stage_detail": detail,
                                "context": serialized_context,
                                "timestamp": datetime.now(UTC).isoformat(),
                            },
                        )
                    )

            try:
                result_ctx = await orch.run_full_pipeline(
                    job.theme,
                    from_stage=request.from_stage,
                    to_stage=end,
                    initial_context=ctx,
                    progress_callback=_progress,
                    stage_completed_callback=_stage_completed,
                )
                job_registry.update_context(new_job.pipeline_id, result_ctx)
                job_registry.mark_completed(new_job.pipeline_id, context=result_ctx)
                await event_router.publish(
                    new_job.pipeline_id,
                    {"type": "pipeline_completed", "timestamp": datetime.now(UTC).isoformat()},
                )
            except _PipelineCancelled:
                job_registry.mark_cancelled(new_job.pipeline_id)
            except Exception as exc:
                logger.exception("Pipeline %s resume failed", new_job.pipeline_id)
                job_registry.mark_failed(new_job.pipeline_id, error=str(exc))

        task = asyncio.create_task(_run())
        job_registry.attach_task(new_job.pipeline_id, task)
        return JSONResponse(content=_job_summary(new_job))

    # ------------------------------------------------------------------
    # QC approve
    # ------------------------------------------------------------------

    @app.post("/api/content-gen/qc/{pipeline_id}/approve")
    async def approve_qc(pipeline_id: str) -> JSONResponse:
        job = job_registry.get_job(pipeline_id)
        if job is None:
            return JSONResponse(status_code=404, content={"error": "Pipeline not found"})
        ctx = job.pipeline_context
        if ctx is None or ctx.qc_gate is None:
            return JSONResponse(status_code=400, content={"error": "No QC gate found"})
        ctx.qc_gate.approved_for_publish = True
        job_registry.update_context(pipeline_id, ctx)
        return JSONResponse(content={"pipeline_id": pipeline_id, "approved": True})

    # ------------------------------------------------------------------
    # Standalone scripting
    # ------------------------------------------------------------------

    @app.post("/api/content-gen/scripting")
    async def run_scripting(request: RunScriptingRequest) -> JSONResponse:
        config = load_config()
        from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator

        orch = ContentGenOrchestrator(config)
        iter_state = None
        iterative_enabled = (
            config.content_gen.enable_iterative_mode
            if request.iterative_mode is None
            else request.iterative_mode
        )
        try:
            if iterative_enabled:
                ctx, iter_state = await orch.run_scripting_iterative(
                    request.idea,
                    llm_route=request.llm_route,
                    max_iterations=request.max_iterations,
                )
            else:
                ctx = await orch.run_scripting(request.idea, llm_route=request.llm_route)
        except Exception as exc:
            logger.exception("Scripting run failed")
            return JSONResponse(status_code=500, content={"error": str(exc)})

        store = ScriptingStore()
        execution_mode: Literal["single_pass", "iterative"] = (
            "iterative" if iter_state is not None else "single_pass"
        )
        iterations = _build_scripting_iterations(iter_state)
        saved = store.save(ctx, execution_mode=execution_mode, iterations=iterations)
        response_content = _build_scripting_result(
            ctx,
            run_id=saved.run_id,
            execution_mode=execution_mode,
            iterations=iterations,
        )
        return JSONResponse(content=_serialize_scripting_payload(response_content))

    # ------------------------------------------------------------------
    # Saved scripts history
    # ------------------------------------------------------------------

    @app.get("/api/content-gen/scripts")
    async def list_scripts() -> JSONResponse:
        store = ScriptingStore()
        runs = store.list_runs(limit=50)
        items = [_serialize_saved_script_run(r) for r in runs]
        return JSONResponse(content={"items": items})

    @app.get("/api/content-gen/scripts/{run_id}")
    async def get_script(run_id: str) -> JSONResponse:
        store = ScriptingStore()
        run = store.get(run_id)
        if run is None:
            return JSONResponse(status_code=404, content={"error": "Script run not found"})
        if run.result_path:
            result_text = ""
            with suppress(Exception):
                from pathlib import Path

                result_text = Path(run.result_path).read_text()
            if result_text:
                return JSONResponse(content=json.loads(result_text))

        script_text = ""
        with suppress(Exception):
            from pathlib import Path

            script_text = Path(run.script_path).read_text()
        context: ScriptingContext | None = None
        with suppress(Exception):
            from pathlib import Path

            context_text = Path(run.context_path).read_text()
            if context_text:
                context = ScriptingContext.model_validate_json(context_text)

        if context is None:
            context = ScriptingContext(raw_idea=run.raw_idea)

        response = _build_scripting_result(
            context,
            run_id=run.run_id,
            execution_mode=run.execution_mode,
            iterations=run.iterations,
        )
        if script_text:
            response.script = script_text
            response.word_count = len(script_text.split())
        return JSONResponse(content=json.loads(response.model_dump_json()))

    # ------------------------------------------------------------------
    # Backlog
    # ------------------------------------------------------------------

    @app.post("/api/content-gen/backlog")
    async def create_backlog_item(request: CreateBacklogItemRequest) -> JSONResponse:
        config = load_config()
        service = BacklogService(config)
        try:
            item = service.create_item(
                title=request.title,
                one_line_summary=request.one_line_summary,
                raw_idea=request.raw_idea,
                constraints=request.constraints,
                idea=request.idea,
                category=request.category,
                audience=request.audience,
                persona_detail=request.persona_detail,
                problem=request.problem,
                emotional_driver=request.emotional_driver,
                urgency_level=request.urgency_level,
                source=request.source,
                why_now=request.why_now,
                hook=request.hook,
                content_type=request.content_type,
                format_duration=request.format_duration,
                key_message=request.key_message,
                call_to_action=request.call_to_action,
                evidence=request.evidence,
                proof_gap_note=request.proof_gap_note,
                expertise_reason=request.expertise_reason,
                genericity_risk=request.genericity_risk,
                risk_level=request.risk_level,
                source_theme=request.source_theme,
                selection_reasoning=request.selection_reasoning,
            )
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)})
        return JSONResponse(content=json.loads(item.model_dump_json()), status_code=201)

    @app.get("/api/content-gen/backlog")
    async def list_backlog() -> JSONResponse:
        config = load_config()
        service = BacklogService(config)
        backlog = service.load()
        return JSONResponse(
            content={
                "path": str(service.path),
                "items": [json.loads(item.model_dump_json()) for item in backlog.items],
            }
        )

    @app.patch("/api/content-gen/backlog/{idea_id}")
    async def update_backlog_item(idea_id: str, request: UpdateBacklogItemRequest) -> JSONResponse:
        config = load_config()
        service = BacklogService(config)
        try:
            updated = service.update_item(idea_id, request.patch)
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)})
        if updated is None:
            return JSONResponse(status_code=404, content={"error": "Backlog item not found"})
        return JSONResponse(content=json.loads(updated.model_dump_json()))

    @app.post("/api/content-gen/backlog/{idea_id}/select")
    async def select_backlog_item(idea_id: str) -> JSONResponse:
        config = load_config()
        service = BacklogService(config)
        selected = service.select_item(idea_id)
        if selected is None:
            return JSONResponse(status_code=404, content={"error": "Backlog item not found"})
        return JSONResponse(content=json.loads(selected.model_dump_json()))

    @app.post("/api/content-gen/backlog/{idea_id}/archive")
    async def archive_backlog_item(idea_id: str) -> JSONResponse:
        config = load_config()
        service = BacklogService(config)
        archived = service.archive_item(idea_id)
        if archived is None:
            return JSONResponse(status_code=404, content={"error": "Backlog item not found"})
        return JSONResponse(content=json.loads(archived.model_dump_json()))

    @app.delete("/api/content-gen/backlog/{idea_id}")
    async def delete_backlog_item(idea_id: str) -> JSONResponse:
        config = load_config()
        service = BacklogService(config)
        removed = service.delete_item(idea_id)
        if not removed:
            return JSONResponse(status_code=404, content={"error": "Backlog item not found"})
        return JSONResponse(content={"removed": 1})

    @app.post("/api/content-gen/backlog/{idea_id}/start", status_code=202)
    async def start_backlog_item(idea_id: str) -> JSONResponse:
        config = load_config()
        service = BacklogService(config)
        backlog = service.load()

        item = next((i for i in backlog.items if i.idea_id == idea_id), None)
        if item is None:
            return JSONResponse(status_code=404, content={"error": "Backlog item not found"})

        # Check for duplicate active run
        for job in job_registry.active_jobs():
            if (
                job.pipeline_context is not None
                and job.pipeline_context.selected_idea_id == idea_id
            ):
                return JSONResponse(
                    status_code=409,
                    content={
                        "error": "Backlog item is already in an active pipeline",
                        "pipeline_id": job.pipeline_id,
                    },
                )

        from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator

        orch = ContentGenOrchestrator(config)

        # Create job starting at generate_angles (stage 4)
        end = len(PIPELINE_STAGES) - 1
        job = job_registry.create_job(
            theme=item.source_theme or item.title or item.idea,
            from_stage=4,
            to_stage=end,
        )

        # Build seeded context with the single backlog item as primary candidate
        ctx = _build_seeded_context_from_backlog_item(job.pipeline_id, item)
        job_registry.update_context(job.pipeline_id, ctx)

        async def _run() -> None:
            job_registry.mark_running(job.pipeline_id)

            def _progress(stage_idx: int, label: str) -> None:
                if job.stop_requested:
                    raise _PipelineCancelled(job.pipeline_id)
                asyncio.get_running_loop().create_task(
                    event_router.publish(
                        job.pipeline_id,
                        {
                            "type": "pipeline_stage_started",
                            "stage_index": stage_idx,
                            "stage_label": label,
                            "timestamp": datetime.now(UTC).isoformat(),
                        },
                    )
                )

            def _stage_completed(stage_idx: int, status: str, detail: str, stage_ctx) -> None:
                job_registry.update_context(job.pipeline_id, stage_ctx)
                serialized_context = stage_ctx.model_dump(mode="json")

                if status == "failed":
                    asyncio.get_running_loop().create_task(
                        event_router.publish(
                            job.pipeline_id,
                            {
                                "type": "pipeline_stage_failed",
                                "stage_index": stage_idx,
                                "stage_label": PIPELINE_STAGE_LABELS.get(
                                    PIPELINE_STAGES[stage_idx], ""
                                ),
                                "error": detail,
                                "context": serialized_context,
                                "timestamp": datetime.now(UTC).isoformat(),
                            },
                        )
                    )
                elif status == "skipped":
                    asyncio.get_running_loop().create_task(
                        event_router.publish(
                            job.pipeline_id,
                            {
                                "type": "pipeline_stage_skipped",
                                "stage_index": stage_idx,
                                "stage_label": PIPELINE_STAGE_LABELS.get(
                                    PIPELINE_STAGES[stage_idx], ""
                                ),
                                "reason": detail,
                                "context": serialized_context,
                                "timestamp": datetime.now(UTC).isoformat(),
                            },
                        )
                    )
                else:
                    asyncio.get_running_loop().create_task(
                        event_router.publish(
                            job.pipeline_id,
                            {
                                "type": "pipeline_stage_completed",
                                "stage_index": stage_idx,
                                "stage_status": status,
                                "stage_detail": detail,
                                "context": serialized_context,
                                "timestamp": datetime.now(UTC).isoformat(),
                            },
                        )
                    )

            try:
                result_ctx = await orch.run_full_pipeline(
                    ctx.theme,
                    from_stage=4,
                    to_stage=end,
                    initial_context=ctx,
                    progress_callback=_progress,
                    stage_completed_callback=_stage_completed,
                )
                job_registry.update_context(job.pipeline_id, result_ctx)
                job_registry.mark_completed(job.pipeline_id, context=result_ctx)
                await event_router.publish(
                    job.pipeline_id,
                    {
                        "type": "pipeline_completed",
                        "current_stage": result_ctx.current_stage,
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                )
            except _PipelineCancelled:
                job_registry.mark_cancelled(job.pipeline_id)
                await event_router.publish(
                    job.pipeline_id,
                    {"type": "pipeline_cancelled", "timestamp": datetime.now(UTC).isoformat()},
                )
            except Exception as exc:
                logger.exception("Pipeline %s failed", job.pipeline_id)
                job_registry.mark_failed(job.pipeline_id, error=str(exc))
                await event_router.publish(
                    job.pipeline_id,
                    {
                        "type": "pipeline_error",
                        "error": str(exc),
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                )

        task = asyncio.create_task(_run())
        job_registry.attach_task(job.pipeline_id, task)

        return JSONResponse(
            status_code=202,
            content={
                "pipeline_id": job.pipeline_id,
                "status": str(job.status),
                "idea_id": idea_id,
                "from_stage": 4,
                "to_stage": end,
            },
        )

    # ------------------------------------------------------------------
    # Backlog chat
    # ------------------------------------------------------------------

    @app.post("/api/content-gen/backlog-chat/respond")
    async def backlog_chat_respond(request: BacklogChatRespondRequest) -> JSONResponse:
        """Generate a conversational response with optional backlog operations.

        This endpoint is advisory only — it never writes to the backlog.
        Use /apply to persist any proposed operations.
        """
        config = load_config()
        service = BacklogService(config)

        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        backlog_items = request.backlog_items if request.backlog_items else service.load().items

        agent = BacklogChatAgent(config)
        response = await agent.respond(
            messages=messages,
            backlog_items=backlog_items,
            strategy=request.strategy,
            selected_idea_id=request.selected_idea_id,
            mode=request.mode,
        )

        return JSONResponse(content=json.loads(response.model_dump_json()))

    @app.post("/api/content-gen/backlog-chat/apply")
    async def backlog_chat_apply(request: BacklogChatApplyRequest) -> JSONResponse:
        """Apply a list of validated backlog operations.

        This is the only write path for chat-proposed operations.
        Returns structured errors instead of crashing on invalid operations.
        """
        config = load_config()
        service = BacklogService(config)

        backlog_items = service.load().items
        operations, errors = build_apply_operations(
            [op.model_dump(mode="python") for op in request.operations],
            backlog_items,
        )
        applied = 0
        items: list[BacklogItem] = []
        if operations:
            applied, items, apply_errors = await apply_operations(operations, service)
            errors.extend(apply_errors)

        return JSONResponse(
            content={
                "applied": applied,
                "items": [json.loads(item.model_dump_json()) for item in items],
                "errors": errors,
            }
        )

    # ------------------------------------------------------------------
    # Backlog AI Triage
    # ------------------------------------------------------------------

    @app.post("/api/content-gen/backlog-ai/triage/respond")
    async def backlog_triage_respond(request: TriageRespondRequest) -> JSONResponse:
        """Generate batch triage proposals for the backlog.

        This endpoint is advisory only — it never writes to the backlog.
        Use /apply to persist any proposed operations.
        """
        config = load_config()
        service = BacklogService(config)

        backlog_items = request.backlog_items if request.backlog_items else service.load().items

        agent = BatchTriageAgent(config)
        response = await agent.respond(
            backlog_items=backlog_items,
            strategy=request.strategy,
        )

        return JSONResponse(content=json.loads(response.model_dump_json()))

    @app.post("/api/content-gen/backlog-ai/triage/apply")
    async def backlog_triage_apply(request: TriageApplyRequest) -> JSONResponse:
        """Apply a list of validated triage operations.

        This is the only write path for triage-proposed operations.
        Returns structured errors instead of crashing on invalid operations.
        """
        config = load_config()
        service = BacklogService(config)

        backlog_items = service.load().items
        operations, errors = build_triage_apply_operations(
            [op.model_dump(mode="python") for op in request.operations],
            backlog_items,
        )
        applied = 0
        items: list[BacklogItem] = []
        if operations:
            applied, items, apply_errors = await apply_triage_operations(operations, service)
            errors.extend(apply_errors)

        return JSONResponse(
            content={
                "applied": applied,
                "items": [json.loads(item.model_dump_json()) for item in items],
                "errors": errors,
            }
        )

    # ------------------------------------------------------------------
    # Next-Action Recommendations
    # ------------------------------------------------------------------

    @app.post("/api/content-gen/backlog-ai/next-action")
    async def get_next_action(request: NextActionRequest) -> JSONResponse:
        """Get a next-action recommendation for a single backlog item.

        This endpoint is advisory only — it never writes to the backlog.
        """
        config = load_config()
        service = BacklogService(config)
        backlog = service.load()

        item = next((i for i in backlog.items if i.idea_id == request.idea_id), None)
        if item is None:
            return JSONResponse(status_code=404, content={"error": "Backlog item not found"})

        agent = NextActionAgent(config)
        response = await agent.recommend(
            item,
            strategy_context=request.strategy,
        )

        return JSONResponse(content=json.loads(response.model_dump_json()))

    @app.post("/api/content-gen/backlog-ai/next-action/batch")
    async def get_next_action_batch(
        request: TriageRespondRequest,
    ) -> JSONResponse:
        """Get next-action recommendations for multiple backlog items.

        Returns recommendations for all items in the request (or all items
        in the backlog if none provided).
        """
        config = load_config()
        service = BacklogService(config)

        backlog_items = request.backlog_items if request.backlog_items else service.load().items

        recommendations = []
        warnings: list[str] = []

        for item in backlog_items:
            agent = NextActionAgent(config)
            try:
                response = await agent.recommend(
                    item,
                    strategy_context=request.strategy,
                )
                recommendations.append(json.loads(response.model_dump_json()))
            except Exception as exc:
                warnings.append(f"{item.idea_id}: {exc}")

        return JSONResponse(content={"recommendations": recommendations, "warnings": warnings})

    # ------------------------------------------------------------------
    # Execution Brief
    # ------------------------------------------------------------------

    @app.post("/api/content-gen/backlog-ai/execution-brief")
    async def generate_execution_brief(request: ExecutionBriefRequest) -> JSONResponse:
        """Generate a production-readiness brief for a single backlog item.

        The brief is grounded in existing backlog metadata and AI-enriched context.
        It helps reduce manual setup work before the pipeline starts.
        """
        config = load_config()
        service = BacklogService(config)
        backlog = service.load()

        item = next((i for i in backlog.items if i.idea_id == request.idea_id), None)
        if item is None:
            return JSONResponse(status_code=404, content={"error": "Backlog item not found"})

        agent = ExecutionBriefAgent(config)
        response = await agent.generate_brief(
            item,
            strategy_context=request.strategy,
        )

        return JSONResponse(content=json.loads(response.model_dump_json()))

    # ------------------------------------------------------------------
    # Strategy
    # ------------------------------------------------------------------

    @app.get("/api/content-gen/strategy")
    async def get_strategy() -> JSONResponse:
        store = StrategyStore()
        memory = store.load()
        return JSONResponse(content=json.loads(memory.model_dump_json()))

    @app.put("/api/content-gen/strategy")
    async def update_strategy(request: UpdateStrategyRequest) -> JSONResponse:
        store = StrategyStore()
        updated = store.update(request.patch)
        return JSONResponse(content=json.loads(updated.model_dump_json()))

    # ------------------------------------------------------------------
    # Publish queue
    # ------------------------------------------------------------------

    @app.get("/api/content-gen/publish")
    async def list_publish_queue() -> JSONResponse:
        store = PublishQueueStore()
        items = store.load()
        return JSONResponse(content={"items": [json.loads(i.model_dump_json()) for i in items]})

    @app.delete("/api/content-gen/publish/{idea_id}/{platform}")
    async def remove_from_queue(idea_id: str, platform: str) -> JSONResponse:
        store = PublishQueueStore()
        items = store.load()
        filtered = [i for i in items if not (i.idea_id == idea_id and i.platform == platform)]
        store.save(filtered)
        removed = len(items) - len(filtered)
        return JSONResponse(content={"removed": removed})

    # ------------------------------------------------------------------
    # Audit history
    # ------------------------------------------------------------------

    @app.get("/api/content-gen/audit")
    async def list_audit_entries(
        idea_id: str | None = None,
        event_type: str | None = None,
        actor: str | None = None,
        limit: int = 100,
    ) -> JSONResponse:
        """List audit log entries with optional filtering.

        Query params:
        - idea_id: filter to entries for a specific backlog item
        - event_type: filter to a specific event type (proposal_created, item_updated, etc.)
        - actor: filter to entries from a specific actor (operator, ai_proposal, system, maintenance)
        - limit: max entries to return (default 100)
        """
        store = AuditStore()
        event_type_enum = AuditEventType(event_type) if event_type else None
        actor_enum = AuditActor(actor) if actor else None
        entries = store.load_entries(
            idea_id=idea_id,
            event_type=event_type_enum,
            actor=actor_enum,
            limit=limit,
        )
        return JSONResponse(
            content={
                "items": [entry.to_dict() for entry in entries],
                "count": len(entries),
            }
        )

    @app.get("/api/content-gen/audit/{idea_id}")
    async def get_audit_for_item(idea_id: str, limit: int = 50) -> JSONResponse:
        """Get audit history for a specific backlog item."""
        store = AuditStore()
        entries = store.load_entries(idea_id=idea_id, limit=limit)
        return JSONResponse(
            content={
                "idea_id": idea_id,
                "items": [entry.to_dict() for entry in entries],
                "count": len(entries),
            }
        )

    # ------------------------------------------------------------------
    # Maintenance workflows
    # ------------------------------------------------------------------

    @app.get("/api/content-gen/maintenance/proposals")
    async def list_maintenance_proposals(
        status: str | None = None,
        job_type: str | None = None,
        limit: int = 50,
    ) -> JSONResponse:
        """List maintenance proposals with optional filtering.

        Query params:
        - status: filter by status (pending, approved, rejected, applied, expired)
        - job_type: filter by job type (stale_item_review, gap_summary, duplicate_watchlist, rescoring_recommend)
        - limit: max proposals to return (default 50)
        """
        store = MaintenanceStore()
        status_enum = MaintenanceProposalStatus(status) if status else None
        job_type_enum = MaintenanceJobType(job_type) if job_type else None
        proposals = store.load_proposals(status=status_enum, job_type=job_type_enum, limit=limit)
        return JSONResponse(
            content={
                "items": [p.to_dict() for p in proposals],
                "count": len(proposals),
            }
        )

    @app.post("/api/content-gen/maintenance/proposals/{proposal_id}/resolve")
    async def resolve_maintenance_proposal(
        proposal_id: str,
        decision: str,  # "approved" | "rejected"
    ) -> JSONResponse:
        """Resolve a maintenance proposal (approve or reject).

        If approved, the suggested_patch is applied to the affected backlog items.
        If rejected, the proposal is marked as rejected.

        Query params:
        - decision: "approved" or "rejected"
        """
        store = MaintenanceStore()
        config = load_config()
        service = BacklogService(config)

        proposal = store.resolve_proposal(proposal_id, decision=decision)
        if proposal is None:
            return JSONResponse(status_code=404, content={"error": "Proposal not found"})

        # Apply approved proposals to backlog items
        if decision == "approved" and proposal.suggested_patch:
            for idea_id in proposal.affected_idea_ids:
                service.update_item(idea_id, dict(proposal.suggested_patch))

        # Log to audit
        audit_store = AuditStore(config=config)
        for idea_id in proposal.affected_idea_ids:
            audit_store.log_backlog_mutation(
                event_type=AuditEventType.MAINTENANCE_PROPOSAL,
                idea_id=idea_id,
                actor=AuditActor.OPERATOR,
                patch={"proposal_id": proposal_id, "decision": decision},
                outcome=decision,
            )

        return JSONResponse(content=proposal.to_dict())

    @app.post("/api/content-gen/maintenance/jobs/{job_type}/trigger")
    async def trigger_maintenance_job(request: Request, job_type: str) -> JSONResponse:
        """Trigger a maintenance job immediately (on-demand).

        Path params:
        - job_type: one of stale_item_review, gap_summary, duplicate_watchlist, rescoring_recommend
        """
        try:
            job_type_enum = MaintenanceJobType(job_type)
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"error": f"Unknown job type: {job_type}"},
            )

        # Use app-state scheduler if available (started with app lifecycle)
        runtime = getattr(request.app.state, "dashboard_runtime", None)
        scheduler: MaintenanceScheduler | None = None
        if runtime is not None:
            scheduler = getattr(runtime, "maintenance_scheduler", None)
        if scheduler is None:
            scheduler = MaintenanceScheduler()

        run = scheduler.trigger_job(job_type_enum)

        return JSONResponse(
            content={
                "run": run.to_dict(),
                "proposals_generated": run.proposals_count,
                "outcome": run.outcome,
                "error": run.error or None,
            }
        )

    @app.get("/api/content-gen/maintenance/runs")
    async def list_maintenance_runs(limit: int = 20) -> JSONResponse:
        """List recent maintenance run records."""
        store = MaintenanceStore()
        runs = store.load_runs(limit=limit)
        return JSONResponse(
            content={
                "items": [r.to_dict() for r in runs],
                "count": len(runs),
            }
        )

    # ------------------------------------------------------------------
    # WebSocket for pipeline progress
    # ------------------------------------------------------------------

    @app.websocket("/ws/content-gen/pipeline/{pipeline_id}")
    async def pipeline_websocket(websocket: WebSocket, pipeline_id: str) -> None:
        logger.info("Pipeline WS connecting pipeline_id=%s", pipeline_id)
        await websocket.accept()

        connection = WebSocketConnection(websocket, pipeline_id)
        await event_router.subscribe(pipeline_id, connection)

        # Send initial state
        job = job_registry.get_job(pipeline_id)
        if job is not None:
            initial: dict[str, Any] = {
                "type": "pipeline_status",
                "pipeline_id": pipeline_id,
                "status": str(job.status),
                "current_stage": (
                    job.pipeline_context.current_stage if job.pipeline_context else job.from_stage
                ),
            }
            if job.pipeline_context is not None:
                initial["context"] = json.loads(job.pipeline_context.model_dump_json())
            await connection.send_json(initial)

        try:
            while True:
                data = await websocket.receive_json()
                msg_type = data.get("type")
                if msg_type == "ping":
                    await connection.send_json({"type": "pong"})
                elif msg_type == "get_pipeline_status":
                    job = job_registry.get_job(pipeline_id)
                    if job is not None:
                        status_msg: dict[str, Any] = {
                            "type": "pipeline_status",
                            "pipeline_id": pipeline_id,
                            "status": str(job.status),
                        }
                        if job.pipeline_context is not None:
                            status_msg["context"] = json.loads(
                                job.pipeline_context.model_dump_json()
                            )
                        await connection.send_json(status_msg)
        except WebSocketDisconnect:
            logger.info("Pipeline WS disconnected pipeline_id=%s", pipeline_id)
        except Exception:
            logger.exception("Pipeline WS error pipeline_id=%s", pipeline_id)
        finally:
            await event_router.unsubscribe(pipeline_id, connection)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _job_summary(job: PipelineRunJob) -> dict[str, Any]:
    """Serialize a pipeline job into a JSON-friendly summary."""
    return {
        "pipeline_id": job.pipeline_id,
        "theme": job.theme,
        "from_stage": job.from_stage,
        "to_stage": job.to_stage,
        "status": str(job.status),
        "current_stage": (
            job.pipeline_context.current_stage if job.pipeline_context else job.from_stage
        ),
        "error": job.error,
        "created_at": job.created_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


def _build_seeded_context_from_backlog_item(pipeline_id: str, item: BacklogItem) -> PipelineContext:
    """Build a minimal valid PipelineContext seeded from one backlog item.

    The context is seeded so that the orchestrator can start at generate_angles
    (stage 4) without needing upstream scoring or backlog regeneration.
    """
    from cc_deep_research.content_gen.models import (
        BacklogOutput,
        PipelineCandidate,
        PipelineContext,
    )
    from cc_deep_research.content_gen.storage import StrategyStore

    strategy = StrategyStore().load()

    return PipelineContext(
        pipeline_id=pipeline_id,
        theme=item.source_theme or item.title or item.idea,
        created_at=datetime.now(tz=UTC).isoformat(),
        current_stage=4,
        strategy=strategy,
        backlog=BacklogOutput(items=[item]),
        selected_idea_id=item.idea_id,
        shortlist=[item.idea_id],
        selection_reasoning=(
            item.selection_reasoning
            if item.selection_reasoning
            else "Started explicitly by operator from backlog."
        ),
        runner_up_idea_ids=[],
        active_candidates=[
            PipelineCandidate(
                idea_id=item.idea_id,
                role="primary",
                status="selected",
            )
        ],
    )


class _PipelineCancelled(Exception):
    """Internal sentinel to break out of the orchestrator progress loop."""


__all__ = ["register_content_gen_routes"]
