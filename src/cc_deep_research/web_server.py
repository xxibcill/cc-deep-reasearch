"""FastAPI web server for real-time monitoring dashboard."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import cast

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from cc_deep_research.config import (
    ConfigOverrideError,
    ConfigPatchError,
    ConfigPatchErrorResponse,
    ConfigPatchRequest,
    build_config_response,
    load_config,
    update_config,
)
from cc_deep_research.content_gen._services import build_content_gen_services
from cc_deep_research.content_gen.maintenance_workflow import MaintenanceScheduler
from cc_deep_research.content_gen.progress import (
    PipelineRunJobRegistry,
)
from cc_deep_research.content_gen.router import register_content_gen_routes
from cc_deep_research.event_router import EventRouter
from cc_deep_research.llm.codex_runtime import CodexRuntime, get_shared_codex_runtime
from cc_deep_research.llm.runtime_context import LLMRuntimeContext
from cc_deep_research.radar.router import register_radar_routes
from cc_deep_research.reporting import ReportGenerator
from cc_deep_research.research_runs.jobs import (
    BackgroundJob,
    BackgroundJobRegistry,
    ResearchRunJobRegistry,
)
from cc_deep_research.research_runs.service import ResearchRunService
from cc_deep_research.web_server_routes import (
    register_knowledge_routes,
    register_misc_routes,
    register_research_run_routes,
    register_session_routes,
    register_websocket_routes,
)
from cc_deep_research.web_server_routes.codex_auth_routes import (
    register_codex_auth_routes,
    resolve_dashboard_cors_origins,
)
from cc_deep_research.web_server_routes.operations_routes import register_operations_routes

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DashboardBackendRuntime:
    """Process-local runtime dependencies owned by the FastAPI app."""

    event_router: EventRouter
    jobs: ResearchRunJobRegistry
    background_jobs: BackgroundJobRegistry
    pipeline_jobs: PipelineRunJobRegistry
    codex_runtime: CodexRuntime
    maintenance_scheduler: MaintenanceScheduler | None = None

    async def start(self) -> None:
        """Start shared realtime infrastructure."""
        await self.event_router.start()
        await self.codex_runtime.start()
        if self.maintenance_scheduler is not None:
            self.maintenance_scheduler.start()

    async def stop(self) -> None:
        """Stop shared infrastructure and cancel in-flight jobs."""
        await self.jobs.cancel_all()
        await self.background_jobs.cancel_all()
        await self.pipeline_jobs.cancel_all()
        if self.maintenance_scheduler is not None:
            self.maintenance_scheduler.stop()
        await self.codex_runtime.close()
        await self.event_router.stop()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifecycle."""
    runtime = get_backend_runtime(app)
    try:
        await runtime.start()
        yield
    finally:
        await runtime.stop()


def create_app(
    event_router: EventRouter | None = None,
    job_registry: ResearchRunJobRegistry | None = None,
    codex_runtime: CodexRuntime | None = None,
    cors_origins: Sequence[str] | None = None,
) -> FastAPI:
    """Create FastAPI application.

    Args:
        event_router: Optional EventRouter for WebSocket broadcasting.
        job_registry: Optional in-process run registry for browser-started jobs.
        codex_runtime: Optional shared Codex runtime for provider and account operations.
        cors_origins: Exact browser origins allowed to access the dashboard API.

    Returns:
        Configured FastAPI application.
    """
    app = FastAPI(
        title="Inqulume Studio Monitoring",
        description="Real-time monitoring dashboard for Inqulume Studio",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.state.dashboard_runtime = DashboardBackendRuntime(
        event_router=event_router or EventRouter(),
        jobs=job_registry or ResearchRunJobRegistry(),
        background_jobs=BackgroundJobRegistry(),
        pipeline_jobs=PipelineRunJobRegistry(),
        codex_runtime=codex_runtime or get_shared_codex_runtime(),
    )

    # Initialize maintenance scheduler if configured
    maintenance_scheduler: MaintenanceScheduler | None = None
    try:
        config = load_config()
        interval_hours = getattr(config.content_gen, "maintenance_interval_hours", 0.0)
        if interval_hours > 0:
            maintenance_scheduler = MaintenanceScheduler(config=config, interval_hours=interval_hours)
            app.state.dashboard_runtime.maintenance_scheduler = maintenance_scheduler
    except Exception:
        logger.exception("Failed to initialize maintenance scheduler")

    # Configure CORS and use the same explicit list for sensitive auth routes.
    dashboard_cors_origins = resolve_dashboard_cors_origins(cors_origins)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(dashboard_cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register route modules
    register_routes(app, cors_origins=dashboard_cors_origins)

    # Content generation routes
    runtime = get_backend_runtime(app)
    config = load_config()
    services = build_content_gen_services(
        config=config,
        event_router=runtime.event_router,
        job_registry=runtime.pipeline_jobs,
        llm_runtime=LLMRuntimeContext(codex_runtime=runtime.codex_runtime),
    )
    app.state.content_gen_services = services
    register_content_gen_routes(app, runtime.event_router, runtime.pipeline_jobs, services)

    # Radar routes
    register_radar_routes(app, runtime.event_router)

    # Knowledge graph routes
    register_knowledge_routes(app)

    return app


# Global app instance
_app: FastAPI | None = None


def get_app() -> FastAPI:
    """Get or create the global FastAPI app instance."""
    global _app
    if _app is None:
        _app = create_app()
    return _app


def get_backend_runtime(app: FastAPI) -> DashboardBackendRuntime:
    """Return the typed dashboard runtime stored on the app."""
    return cast(DashboardBackendRuntime, app.state.dashboard_runtime)


def get_event_router(app: FastAPI) -> EventRouter:
    """Return the shared event router from app runtime state."""
    return get_backend_runtime(app).event_router


def get_job_registry(app: FastAPI) -> ResearchRunJobRegistry:
    """Return the shared job registry from app runtime state."""
    return get_backend_runtime(app).jobs


def get_background_job_registry(app: FastAPI) -> BackgroundJobRegistry:
    """Return the shared generic background job registry from app runtime state."""
    return get_backend_runtime(app).background_jobs


def get_pipeline_job_registry(app: FastAPI) -> PipelineRunJobRegistry:
    """Return the shared pipeline job registry from app runtime state."""
    return get_backend_runtime(app).pipeline_jobs


def _background_job_response(job: BackgroundJob) -> dict[str, object]:
    """Serialize a generic background job for HTTP polling."""
    response: dict[str, object] = {
        "job_id": job.job_id,
        "kind": job.kind,
        "status": job.status,
        "metadata": job.metadata,
        "created_at": job.created_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }
    if job.result is not None:
        response["result"] = job.result
    if job.error is not None:
        response["error"] = job.error
    return response


def register_routes(
    app: FastAPI,
    *,
    cors_origins: Sequence[str] | None = None,
) -> None:
    """Register all API routes.

    Args:
        app: The FastAPI application instance.
        cors_origins: Exact browser origins trusted by dashboard-only routes.
    """

    @app.get("/")
    async def root() -> dict[str, str]:
        """Root endpoint."""
        return {
            "message": "Inqulume Studio Monitoring API",
            "version": "1.0.0",
        }

    @app.get("/api/jobs")
    async def list_background_jobs() -> JSONResponse:
        """List generic background jobs started by dashboard routes."""
        registry = get_background_job_registry(app)
        jobs = [_background_job_response(job) for job in registry.list_jobs()]
        return JSONResponse(content={"jobs": jobs, "total": len(jobs)})

    @app.get("/api/jobs/{job_id}")
    async def get_background_job(job_id: str) -> JSONResponse:
        """Return status and result/error for a generic background job."""
        registry = get_background_job_registry(app)
        job = registry.get_job(job_id)
        if job is None:
            return JSONResponse(
                content={"error": f"Background job not found: {job_id}"},
                status_code=404,
            )
        return JSONResponse(content=_background_job_response(job))

    @app.get("/api/config")
    async def get_config() -> JSONResponse:
        """Return persisted and effective config for the settings page."""
        response = build_config_response()
        return JSONResponse(content=response.model_dump(mode="json"))

    @app.patch("/api/config")
    async def patch_config(request: ConfigPatchRequest) -> JSONResponse:
        """Apply and persist a partial config update."""
        try:
            response = update_config(
                request.updates,
                save_overridden_fields=request.save_overridden_fields,
            )
        except ConfigOverrideError as error:
            payload = ConfigPatchErrorResponse(
                error=error.message,
                conflicts=error.conflicts,
            )
            return JSONResponse(
                content=payload.model_dump(mode="json"),
                status_code=409,
            )
        except ConfigPatchError as error:
            payload = ConfigPatchErrorResponse(
                error=error.message,
                fields=error.fields,
            )
            return JSONResponse(
                content=payload.model_dump(mode="json"),
                status_code=400,
            )

        content_gen_services = getattr(app.state, "content_gen_services", None)
        if content_gen_services is not None:
            content_gen_services.refresh_llm_config(load_config())

        return JSONResponse(content=response.model_dump(mode="json"))

    # Register extracted route modules
    register_research_run_routes(app)
    register_session_routes(app)
    register_misc_routes(app)
    register_websocket_routes(app)
    register_operations_routes(app)
    register_codex_auth_routes(app, allowed_origins=cors_origins)


def start_server(
    host: str = "localhost",
    port: int = 8000,
    event_router: EventRouter | None = None,
    job_registry: ResearchRunJobRegistry | None = None,
) -> None:
    """Start the FastAPI server.

    Args:
        host: Host to bind to.
        port: Port to listen on.
        event_router: Optional EventRouter for WebSocket broadcasting.
        job_registry: Optional process-local registry for browser-started runs.
    """
    import uvicorn

    app = create_app(event_router=event_router, job_registry=job_registry)

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        ws="websockets-sansio",
    )


__all__ = [
    "DashboardBackendRuntime",
    "create_app",
    "get_backend_runtime",
    "get_app",
    "get_event_router",
    "get_background_job_registry",
    "get_job_registry",
    "get_pipeline_job_registry",
    "register_routes",
    "start_server",
    # Re-exported for backward compatibility with tests
    "ReportGenerator",
    "ResearchRunService",
]
