"""FastAPI router for Opportunity Radar API endpoints."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from cc_deep_research.event_router import EventRouter
from cc_deep_research.radar.api_models import (
    ConversionFunnelResponse,
    CreateSourceRequest,
    FeedbackTrendsResponse,
    LaunchBacklogResponse,
    LaunchBriefResponse,
    LaunchContentPipelineResponse,
    LaunchResearchResponse,
    OpportunityDetailResponse,
    OpportunityListResponse,
    RadarAnalyticsResponse,
    RecordFeedbackRequest,
    ScoreDistributionResponse,
    SourceListResponse,
    SourceResponse,
    StatusHistoryResponse,
    UpdateOpportunityStatusRequest,
)
from cc_deep_research.radar.models import (
    FreshnessState,
    OpportunityStatus,
    OpportunityType,
    SourceStatus,
)
from cc_deep_research.radar.service import RadarService
from cc_deep_research.radar.telemetry import RadarTelemetryStore

logger = logging.getLogger(__name__)
RUN_CANCELLED_MESSAGE = "Research run was cancelled by the operator."


def _get_service(request: Request) -> RadarService:
    """Get the RadarService from app state or create a default one."""
    if hasattr(request.app.state, "radar_service") and request.app.state.radar_service is not None:
        return request.app.state.radar_service
    return RadarService()


def _get_runtime_component(request: Request, attr_name: str, component_label: str) -> Any:
    """Return a dashboard runtime component or raise when unavailable."""
    runtime = getattr(request.app.state, "dashboard_runtime", None)
    component = getattr(runtime, attr_name, None) if runtime is not None else None
    if component is None:
        raise RuntimeError(f"{component_label} is unavailable on this server")
    return component


def _raise_if_run_cancelled(job: Any) -> None:
    """Raise the shared cancellation error when a stop has been requested."""
    from cc_deep_research.research_runs.models import ResearchRunCancelled

    if job.stop_requested:
        raise ResearchRunCancelled(RUN_CANCELLED_MESSAGE)


async def _publish_progress_event(
    event_router: EventRouter | None,
    channel: str,
    payload: dict[str, Any],
) -> None:
    """Publish a progress event when the router exposes an async publish method."""
    if event_router is None:
        return
    result = event_router.publish(channel, payload)
    if asyncio.iscoroutine(result):
        await result


def register_radar_routes(
    app: FastAPI,
    event_router: EventRouter,
    service: RadarService | None = None,
) -> None:
    """Register all Radar API routes on *app*."""

    # Store the service in app state for access in route handlers
    app.state.radar_service = service

    # Get monitor emit function from app state if available
    monitor_emit = getattr(app.state, "monitor_emit", None)

    def _emit_radar_event(
        event_type: str,
        category: str,
        name: str,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Emit a telemetry event for Radar operations.

        Non-blocking: runs in background without affecting request latency.
        """
        if event_router is None or not event_router.is_active():
            return

        payload = {
            "type": "radar_event",
            "event_type": event_type,
            "category": category,
            "name": name,
            "status": status,
            "timestamp": datetime.now(UTC).isoformat(),
            "metadata": metadata or {},
        }

        # Schedule publish as background task (non-blocking)
        try:
            loop = asyncio.get_running_loop()
            coro = event_router.publish("radar", payload)
            if asyncio.iscoroutine(coro):
                asyncio.create_task(coro)
        except Exception:
            pass

        # Also call monitor emit if available (for persistence)
        if monitor_emit is not None:
            try:
                monitor_emit(
                    event_type=event_type,
                    category=category,
                    name=name,
                    status=status,
                    metadata=metadata,
                )
            except Exception:
                logger.exception("Failed to emit monitor event for radar")

    @app.get("/api/radar/sources", response_model=SourceListResponse)
    async def list_sources(
        request: Request,
        status: SourceStatus | None = None,
    ) -> JSONResponse:
        """List all Radar sources, optionally filtered by status."""
        svc = _get_service(request)
        sources = svc.list_sources(status=status)
        return JSONResponse(content={
            "items": [json.loads(s.model_dump_json()) for s in sources],
            "count": len(sources),
        })

    @app.post("/api/radar/sources", status_code=201, response_model=SourceResponse)
    async def create_source(
        request: Request,
        body: CreateSourceRequest,
    ) -> JSONResponse:
        """Create a new Radar source."""
        svc = _get_service(request)
        source = svc.create_source(
            source_type=body.source_type,
            label=body.label,
            url_or_identifier=body.url_or_identifier,
            scan_cadence=body.scan_cadence,
            metadata=body.metadata,
        )

        _emit_radar_event(
            event_type="radar.source_created",
            category="radar",
            name="source_created",
            status="created",
            metadata={
                "source_id": source.id,
                "source_type": source.source_type.value,
                "label": source.label,
            },
        )

        return JSONResponse(content=json.loads(source.model_dump_json()), status_code=201)

    @app.get("/api/radar/opportunities", response_model=OpportunityListResponse)
    async def list_opportunities(
        request: Request,
        status: OpportunityStatus | None = None,
        opportunity_type: OpportunityType | None = None,
        freshness: FreshnessState | None = None,
        limit: int | None = None,
    ) -> JSONResponse:
        """List all opportunities with optional filtering."""
        svc = _get_service(request)
        opportunities = svc.list_opportunities(
            status=status,
            opportunity_type=opportunity_type,
            freshness=freshness,
            limit=limit,
        )
        return JSONResponse(content={
            "items": [json.loads(o.model_dump_json()) for o in opportunities],
            "count": len(opportunities),
        })

    @app.get("/api/radar/opportunities/{opportunity_id}", response_model=OpportunityDetailResponse)
    async def get_opportunity_detail(
        request: Request,
        opportunity_id: str,
    ) -> JSONResponse:
        """Get full detail for an opportunity including signals, score, and feedback."""
        svc = _get_service(request)
        detail = svc.get_opportunity_detail(opportunity_id)

        if detail is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Opportunity not found"},
            )

        return JSONResponse(content={
            "opportunity": json.loads(detail["opportunity"].model_dump_json()),
            "score": json.loads(detail["score"].model_dump_json()) if detail["score"] else None,
            "signals": [json.loads(s.model_dump_json()) for s in detail["signals"]],
            "feedback": [json.loads(f.model_dump_json()) for f in detail["feedback"]],
            "workflow_links": [json.loads(w.model_dump_json()) for w in detail["workflow_links"]],
        })

    @app.post("/api/radar/opportunities/{opportunity_id}/status")
    async def update_opportunity_status(
        request: Request,
        opportunity_id: str,
        body: UpdateOpportunityStatusRequest,
    ) -> JSONResponse:
        """Update the status of an opportunity."""
        svc = _get_service(request)

        # Get current status for telemetry
        current = svc.get_opportunity_detail(opportunity_id)
        if current is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Opportunity not found"},
            )

        previous_status = current["opportunity"].status.value

        updated = svc.update_opportunity_status(opportunity_id, body.status)
        if updated is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Opportunity not found"},
            )

        _emit_radar_event(
            event_type="radar.opportunity_status_updated",
            category="radar",
            name="opportunity_status_updated",
            status="updated",
            metadata={
                "opportunity_id": opportunity_id,
                "previous_status": previous_status,
                "new_status": updated.status.value,
            },
        )

        return JSONResponse(content=json.loads(updated.model_dump_json()))

    @app.post("/api/radar/opportunities/{opportunity_id}/feedback")
    async def record_opportunity_feedback(
        request: Request,
        opportunity_id: str,
        body: RecordFeedbackRequest,
    ) -> JSONResponse:
        """Record feedback on an opportunity."""
        svc = _get_service(request)

        # Verify opportunity exists
        detail = svc.get_opportunity_detail(opportunity_id)
        if detail is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Opportunity not found"},
            )

        feedback = svc.record_feedback(
            opportunity_id=opportunity_id,
            feedback_type=body.feedback_type,
            metadata=body.metadata,
        )

        _emit_radar_event(
            event_type="radar.feedback_recorded",
            category="radar",
            name="feedback_recorded",
            status="recorded",
            metadata={
                "opportunity_id": opportunity_id,
                "feedback_type": feedback.feedback_type.value,
                "feedback_id": feedback.id,
            },
        )

        return JSONResponse(content=json.loads(feedback.model_dump_json()), status_code=201)

    @app.get("/api/radar/opportunities/{opportunity_id}/history", response_model=StatusHistoryResponse)
    async def get_opportunity_history(
        request: Request,
        opportunity_id: str,
    ) -> JSONResponse:
        """Get the status history for an opportunity."""
        svc = _get_service(request)

        # Verify opportunity exists
        detail = svc.get_opportunity_detail(opportunity_id)
        if detail is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Opportunity not found"},
            )

        history = svc.get_status_history(opportunity_id)
        return JSONResponse(content={
            "entries": [json.loads(e.model_dump_json()) for e in history],
            "count": len(history),
        })

    @app.post("/api/radar/opportunities/{opportunity_id}/launch-research", response_model=LaunchResearchResponse)
    async def launch_research_from_opportunity(
        request: Request,
        opportunity_id: str,
    ) -> JSONResponse:
        """Launch a research run from a Radar opportunity.

        Extracts context from the opportunity (title, summary, why_it_matters)
        to pre-fill the research query. Records feedback and creates a workflow link.
        """
        svc = _get_service(request)

        # Get opportunity context
        context = svc.get_opportunity_context_for_research(opportunity_id)
        if context is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Opportunity not found"},
            )

        opp = svc._store.get_opportunity(opportunity_id)

        try:
            job_registry = _get_runtime_component(request, "jobs", "Research job registry")
        except RuntimeError as exc:
            return JSONResponse(status_code=503, content={"error": str(exc)})

        # Start a real research run in the shared registry
        from cc_deep_research.research_runs.models import (
            ResearchDepth,
            ResearchOutputFormat,
            ResearchRunCancelled,
            ResearchRunRequest,
        )
        from cc_deep_research.research_runs.service import ResearchRunService

        req = ResearchRunRequest(
            query=context["query"],
            depth=ResearchDepth.STANDARD,
            output_format=ResearchOutputFormat.MARKDOWN,
        )
        job = job_registry.create_job(req)
        research_run_id = job.run_id

        async def execute_research_run() -> None:
            run_svc = ResearchRunService()

            try:
                if job.stop_requested:
                    job_registry.mark_cancelled(job.run_id, error=RUN_CANCELLED_MESSAGE)
                    return
                job_registry.mark_running(job.run_id)
                result = await asyncio.to_thread(
                    run_svc.run,
                    job.request,
                    event_router=event_router,
                    cancellation_check=lambda: _raise_if_run_cancelled(job),
                    on_session_started=lambda session_id: job_registry.set_session_id(
                        job.run_id,
                        session_id=session_id,
                    ),
                )
                job_registry.mark_completed(job.run_id, result=result)
            except ResearchRunCancelled:
                job_registry.mark_cancelled(job.run_id, error=RUN_CANCELLED_MESSAGE)
            except asyncio.CancelledError:
                job_registry.mark_cancelled(job.run_id, error=RUN_CANCELLED_MESSAGE)
            except Exception as exc:
                job_registry.mark_failed(job.run_id, error=str(exc))

        task = asyncio.create_task(execute_research_run())
        job_registry.attach_task(job.run_id, task)

        # Link the workflow
        svc.link_workflow(
            opportunity_id=opportunity_id,
            workflow_type="research_run",
            workflow_id=research_run_id,
        )

        # Record feedback with real workflow metadata
        feedback_metadata = {
            "research_run_id": research_run_id,
            "query": context["query"],
            "opportunity_score": context["total_score"],
            "opportunity_type": opp.opportunity_type.value if opp else None,
        }
        svc.record_feedback(
            opportunity_id=opportunity_id,
            feedback_type="converted_to_research",
            metadata=feedback_metadata,
        )

        # Update status to acted_on
        svc.update_opportunity_status(
            opportunity_id,
            "acted_on",
            reason="converted_to_research",
        )

        _emit_radar_event(
            event_type="radar.research_launched",
            category="radar",
            name="research_launched",
            status="launched",
            metadata={
                "opportunity_id": opportunity_id,
                "research_run_id": research_run_id,
                "query": context["query"],
            },
        )

        return JSONResponse(content={
            "research_run_id": research_run_id,
            "opportunity_id": opportunity_id,
            "status": str(job.status),
            "session_id": None,
        }, status_code=202)

    @app.post("/api/radar/opportunities/{opportunity_id}/launch-brief", response_model=LaunchBriefResponse)
    async def launch_brief_from_opportunity(
        request: Request,
        opportunity_id: str,
    ) -> JSONResponse:
        """Launch a brief from a Radar opportunity.

        Extracts title, summary, and context to create a brief entry.
        Records feedback and creates a workflow link.
        """
        svc = _get_service(request)

        # Get opportunity context
        context = svc.get_opportunity_context_for_brief(opportunity_id)
        if context is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Opportunity not found"},
            )

        opp = svc._store.get_opportunity(opportunity_id)

        # Create a real brief via BriefService
        from cc_deep_research.content_gen.brief_service import BriefService
        from cc_deep_research.content_gen.models import OpportunityBrief

        brief_id = f"brief_{uuid.uuid4().hex[:12]}"
        opp_brief = OpportunityBrief(
            brief_id=brief_id,
            theme=context["title"],
            goal=context["topic"] or "",
            content_objective=context["context"] or "",
            primary_audience_segment="",
            problem_statements=[context["topic"]] if context["topic"] else [],
            research_hypotheses=[context["recommended_action"]] if context["recommended_action"] else [],
        )

        brief_svc = BriefService()
        brief = brief_svc.create_from_opportunity(opp_brief)
        managed_brief_id = brief.brief_id

        # Link the workflow
        svc.link_workflow(
            opportunity_id=opportunity_id,
            workflow_type="brief",
            workflow_id=managed_brief_id,
        )

        # Record feedback with real workflow metadata
        feedback_metadata = {
            "sub_type": "brief",
            "brief_id": managed_brief_id,
            "opportunity_title": context["title"],
            "opportunity_type": opp.opportunity_type.value if opp else None,
        }
        svc.record_feedback(
            opportunity_id=opportunity_id,
            feedback_type="converted_to_content",
            metadata=feedback_metadata,
        )

        svc.update_opportunity_status(
            opportunity_id,
            "acted_on",
            reason="converted_to_brief",
        )

        _emit_radar_event(
            event_type="radar.brief_launched",
            category="radar",
            name="brief_launched",
            status="launched",
            metadata={
                "opportunity_id": opportunity_id,
                "brief_id": managed_brief_id,
            },
        )

        return JSONResponse(content={
            "brief_id": managed_brief_id,
            "opportunity_id": opportunity_id,
        }, status_code=201)

    @app.post("/api/radar/opportunities/{opportunity_id}/launch-backlog", response_model=LaunchBacklogResponse)
    async def launch_backlog_from_opportunity(
        request: Request,
        opportunity_id: str,
    ) -> JSONResponse:
        """Add a Radar opportunity to the backlog.

        Extracts title and summary to create a backlog item.
        Records feedback and creates a workflow link.
        """
        svc = _get_service(request)

        # Get opportunity context
        context = svc.get_opportunity_context_for_backlog(opportunity_id)
        if context is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Opportunity not found"},
            )

        opp = svc._store.get_opportunity(opportunity_id)

        # Create a real backlog item via BacklogService
        from cc_deep_research.content_gen.backlog_service import BacklogService

        backlog_svc = BacklogService()
        item = backlog_svc.create_item(
            title=context["title"],
            one_line_summary=context["one_liner"] or "",
            raw_idea=context["raw_idea"] or "",
            source=f"radar:{opportunity_id}",
            source_theme=str(opp.opportunity_type.value) if opp and opp.opportunity_type else "",
            selection_reasoning=f"From Radar: {context.get('raw_idea', '')}",
        )
        backlog_item_id = item.idea_id

        # Link the workflow
        svc.link_workflow(
            opportunity_id=opportunity_id,
            workflow_type="backlog_item",
            workflow_id=backlog_item_id,
        )

        # Record feedback with real workflow metadata
        feedback_metadata = {
            "sub_type": "backlog_item",
            "backlog_item_id": backlog_item_id,
            "opportunity_title": context["title"],
            "opportunity_type": opp.opportunity_type.value if opp and opp.opportunity_type else None,
        }
        svc.record_feedback(
            opportunity_id=opportunity_id,
            feedback_type="converted_to_content",
            metadata=feedback_metadata,
        )

        svc.update_opportunity_status(
            opportunity_id,
            "acted_on",
            reason="converted_to_backlog_item",
        )

        _emit_radar_event(
            event_type="radar.backlog_added",
            category="radar",
            name="backlog_added",
            status="added",
            metadata={
                "opportunity_id": opportunity_id,
                "backlog_item_id": backlog_item_id,
            },
        )

        return JSONResponse(content={
            "backlog_item_id": backlog_item_id,
            "opportunity_id": opportunity_id,
        }, status_code=201)

    @app.post("/api/radar/opportunities/{opportunity_id}/launch-content-pipeline", response_model=LaunchContentPipelineResponse)
    async def launch_content_pipeline_from_opportunity(
        request: Request,
        opportunity_id: str,
    ) -> JSONResponse:
        """Launch a content pipeline from a Radar opportunity.

        Starts a real content pipeline job in the shared pipeline registry.
        """
        svc = _get_service(request)

        context = svc.get_opportunity_context_for_brief(opportunity_id)
        if context is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Opportunity not found"},
            )

        opp = svc._store.get_opportunity(opportunity_id)
        try:
            job_registry = _get_runtime_component(request, "pipeline_jobs", "Pipeline job registry")
        except RuntimeError as exc:
            return JSONResponse(status_code=503, content={"error": str(exc)})

        from cc_deep_research.config import load_config
        from cc_deep_research.content_gen.models import PIPELINE_STAGE_LABELS, PIPELINE_STAGES
        from cc_deep_research.content_gen.orchestrator import ContentGenOrchestrator, RunConstraints

        config = load_config()
        end = len(PIPELINE_STAGES) - 1
        job = job_registry.create_job(
            theme=context["title"],
            from_stage=0,
            to_stage=end,
        )
        pipeline_id = job.pipeline_id

        async def run_content_pipeline() -> None:
            orch = ContentGenOrchestrator(config)
            job_registry.mark_running(job.pipeline_id)

            def _progress(stage_idx: int, label: str) -> None:
                if job.stop_requested:
                    raise RuntimeError(f"Pipeline {job.pipeline_id} was cancelled")
                asyncio.get_running_loop().create_task(
                    _publish_progress_event(
                        event_router,
                        job.pipeline_id,
                        {
                            "type": "pipeline_stage_started",
                            "stage_index": stage_idx,
                            "stage_label": label,
                            "timestamp": datetime.now(UTC).isoformat(),
                        },
                    )
                )

            def _stage_completed(stage_idx: int, status: str, detail: str, stage_ctx: Any) -> None:
                job_registry.update_context(job.pipeline_id, stage_ctx)
                payload: dict[str, Any] = {
                    "stage_index": stage_idx,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "context": stage_ctx.model_dump(mode="json"),
                }
                if status == "failed":
                    payload.update({
                        "type": "pipeline_stage_failed",
                        "stage_label": PIPELINE_STAGE_LABELS.get(PIPELINE_STAGES[stage_idx], ""),
                        "error": detail,
                    })
                elif status == "skipped":
                    payload.update({
                        "type": "pipeline_stage_skipped",
                        "stage_label": PIPELINE_STAGE_LABELS.get(PIPELINE_STAGES[stage_idx], ""),
                        "reason": detail,
                    })
                else:
                    payload.update({
                        "type": "pipeline_stage_completed",
                        "stage_status": status,
                        "stage_detail": detail,
                    })

                asyncio.get_running_loop().create_task(
                    _publish_progress_event(event_router, job.pipeline_id, payload)
                )

            try:
                ctx = await orch.run_full_pipeline(
                    context["title"],
                    from_stage=0,
                    to_stage=end,
                    progress_callback=_progress,
                    stage_completed_callback=_stage_completed,
                    run_constraints=RunConstraints(),
                )
                job_registry.update_context(job.pipeline_id, ctx)
                job_registry.mark_completed(job.pipeline_id, context=ctx)
                await _publish_progress_event(
                    event_router,
                    job.pipeline_id,
                    {
                        "type": "pipeline_completed",
                        "current_stage": ctx.current_stage,
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                )
            except Exception as exc:
                logger.exception("Pipeline %s failed", job.pipeline_id)
                job_registry.mark_failed(job.pipeline_id, error=str(exc))
                await _publish_progress_event(
                    event_router,
                    job.pipeline_id,
                    {
                        "type": "pipeline_error",
                        "error": str(exc),
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                )

        task = asyncio.create_task(run_content_pipeline())
        job_registry.attach_task(job.pipeline_id, task)

        # Link the workflow
        svc.link_workflow(
            opportunity_id=opportunity_id,
            workflow_type="content_pipeline",
            workflow_id=pipeline_id,
        )

        svc.record_feedback(
            opportunity_id=opportunity_id,
            feedback_type="converted_to_content",
            metadata={
                "sub_type": "content_pipeline",
                "pipeline_id": pipeline_id,
                "opportunity_title": context["title"],
                "opportunity_type": opp.opportunity_type.value if opp else None,
            },
        )

        svc.update_opportunity_status(
            opportunity_id,
            "acted_on",
            reason="converted_to_content_pipeline",
        )

        _emit_radar_event(
            event_type="radar.content_pipeline_launched",
            category="radar",
            name="content_pipeline_launched",
            status="launched",
            metadata={
                "opportunity_id": opportunity_id,
                "pipeline_id": pipeline_id,
            },
        )

        return JSONResponse(content={
            "pipeline_id": pipeline_id,
            "opportunity_id": opportunity_id,
            "status": str(job.status),
        }, status_code=202)

    # -- Analytics endpoints ---------------------------------------------------

    @app.get("/api/radar/analytics", response_model=RadarAnalyticsResponse)
    async def get_radar_analytics(request: Request) -> JSONResponse:
        """Get aggregated analytics for the Radar feature.

        Returns summary statistics including opportunity counts by status and type,
        feedback counts, conversion rates, and average time to action.
        """
        svc = _get_service(request)
        telemetry = RadarTelemetryStore(store=svc._store)
        analytics = telemetry.get_analytics()

        return JSONResponse(content={
            "total_opportunities": analytics.total_opportunities,
            "opportunities_by_status": analytics.opportunities_by_status,
            "opportunities_by_type": analytics.opportunities_by_type,
            "feedback_counts": analytics.feedback_counts,
            "conversion_rates": analytics.conversion_rates,
            "avg_time_to_action_hours": analytics.avg_time_to_action_hours,
            "top_opportunity_types": analytics.top_opportunity_types,
        })

    @app.get("/api/radar/analytics/funnel", response_model=ConversionFunnelResponse)
    async def get_radar_conversion_funnel(request: Request) -> JSONResponse:
        """Get conversion funnel data for the Radar feature.

        Returns counts at each funnel stage: new → saved → monitoring → acted_on.
        """
        svc = _get_service(request)
        telemetry = RadarTelemetryStore(store=svc._store)
        funnel_data = telemetry.get_conversion_funnel()

        return JSONResponse(content=funnel_data)

    @app.get("/api/radar/analytics/feedback-trends", response_model=FeedbackTrendsResponse)
    async def get_radar_feedback_trends(
        request: Request,
        days_back: int = 30,
    ) -> JSONResponse:
        """Get feedback trends over time.

        Args:
            days_back: Number of days to look back (default 30).
        """
        svc = _get_service(request)
        telemetry = RadarTelemetryStore(store=svc._store)
        trends = telemetry.get_feedback_trends(days_back)

        # Convert Counter to dict for JSON serialization
        daily_counts = {
            day: dict(counts) for day, counts in trends["daily_counts"].items()
        }

        return JSONResponse(content={
            "daily_counts": daily_counts,
            "days_back": days_back,
        })

    @app.get("/api/radar/analytics/score-distribution", response_model=ScoreDistributionResponse)
    async def get_radar_score_distribution(request: Request) -> JSONResponse:
        """Get the distribution of opportunity scores."""
        svc = _get_service(request)
        telemetry = RadarTelemetryStore(store=svc._store)
        dist = telemetry.get_score_distribution()

        return JSONResponse(content=dist)


__all__ = ["register_radar_routes"]
