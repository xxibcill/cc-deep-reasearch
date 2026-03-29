"""FastAPI router for content generation pipeline endpoints."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from cc_deep_research.config import load_config
from cc_deep_research.content_gen.models import PIPELINE_STAGES, PipelineContext
from cc_deep_research.content_gen.progress import (
    PipelineRunJob,
    PipelineRunJobRegistry,
    PipelineRunStatus,
)
from cc_deep_research.content_gen.storage import (
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


class UpdateStrategyRequest(BaseModel):
    """Request body for updating strategy memory."""

    patch: dict[str, Any] = Field(default_factory=dict)


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

            try:
                ctx = await orch.run_full_pipeline(
                    request.theme,
                    from_stage=request.from_stage,
                    to_stage=end,
                    progress_callback=_progress,
                )

                # Broadcast completion for each stage
                for idx in range(request.from_stage, end + 1):
                    await event_router.publish(
                        job.pipeline_id,
                        {
                            "type": "pipeline_stage_completed",
                            "stage_index": idx,
                            "timestamp": datetime.now(UTC).isoformat(),
                        },
                    )

                job_registry.update_context(job.pipeline_id, ctx)
                job_registry.mark_completed(job.pipeline_id)

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
        return JSONResponse(content=_job_summary(job))

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

        # Create a new job for the resumed run
        new_job = job_registry.create_job(
            theme=job.theme,
            from_stage=request.from_stage,
            to_stage=end,
            pipeline_id=f"{pipeline_id}-resume",
        )
        # Carry forward existing context
        job_registry.update_context(new_job.pipeline_id, ctx)

        async def _run() -> None:
            from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator

            orch = ContentGenOrchestrator(config)
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

            try:
                result_ctx = await orch.run_full_pipeline(
                    job.theme,
                    from_stage=request.from_stage,
                    to_stage=end,
                    progress_callback=_progress,
                )
                job_registry.update_context(new_job.pipeline_id, result_ctx)
                job_registry.mark_completed(new_job.pipeline_id)
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
        return JSONResponse(
            content={"pipeline_id": pipeline_id, "approved": True}
        )

    # ------------------------------------------------------------------
    # Standalone scripting
    # ------------------------------------------------------------------

    @app.post("/api/content-gen/scripting")
    async def run_scripting(request: RunScriptingRequest) -> JSONResponse:
        config = load_config()
        from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator

        orch = ContentGenOrchestrator(config)
        try:
            ctx = await orch.run_scripting(request.idea)
        except Exception as exc:
            logger.exception("Scripting run failed")
            return JSONResponse(status_code=500, content={"error": str(exc)})

        store = ScriptingStore()
        saved = store.save(ctx)

        script = ScriptingStore._extract_script(ctx)
        return JSONResponse(
            content={
                "run_id": saved.run_id,
                "raw_idea": ctx.raw_idea,
                "script": script,
                "word_count": len(script.split()) if script else 0,
                "context": json.loads(ctx.model_dump_json()),
            }
        )

    # ------------------------------------------------------------------
    # Saved scripts history
    # ------------------------------------------------------------------

    @app.get("/api/content-gen/scripts")
    async def list_scripts() -> JSONResponse:
        store = ScriptingStore()
        runs = store.list_runs(limit=50)
        items = [json.loads(r.model_dump_json()) for r in runs]
        return JSONResponse(content={"items": items})

    @app.get("/api/content-gen/scripts/{run_id}")
    async def get_script(run_id: str) -> JSONResponse:
        store = ScriptingStore()
        run = store.get(run_id)
        if run is None:
            return JSONResponse(status_code=404, content={"error": "Script run not found"})
        script_path = run.script_path
        script_text = ""
        with suppress(Exception):
            from pathlib import Path

            script_text = Path(script_path).read_text()
        context_text = ""
        with suppress(Exception):
            from pathlib import Path

            context_text = Path(run.context_path).read_text()
        return JSONResponse(
            content={
                "run_id": run.run_id,
                "raw_idea": run.raw_idea,
                "word_count": run.word_count,
                "script": script_text,
                "context": json.loads(context_text) if context_text else None,
            }
        )

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
        return JSONResponse(
            content={"items": [json.loads(i.model_dump_json()) for i in items]}
        )

    @app.delete("/api/content-gen/publish/{idea_id}/{platform}")
    async def remove_from_queue(idea_id: str, platform: str) -> JSONResponse:
        store = PublishQueueStore()
        items = store.load()
        filtered = [
            i for i in items if not (i.idea_id == idea_id and i.platform == platform)
        ]
        store.save(filtered)
        removed = len(items) - len(filtered)
        return JSONResponse(content={"removed": removed})

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
                    job.pipeline_context.current_stage
                    if job.pipeline_context
                    else job.from_stage
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


class _PipelineCancelled(Exception):
    """Internal sentinel to break out of the orchestrator progress loop."""


__all__ = ["register_content_gen_routes"]
