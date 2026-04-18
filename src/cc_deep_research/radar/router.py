"""FastAPI router for Opportunity Radar API endpoints."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from cc_deep_research.event_router import EventRouter
from cc_deep_research.radar.api_models import (
    CreateSourceRequest,
    OpportunityDetailResponse,
    OpportunityListResponse,
    RecordFeedbackRequest,
    SourceListResponse,
    SourceResponse,
    UpdateOpportunityStatusRequest,
)
from cc_deep_research.radar.service import RadarService

logger = logging.getLogger(__name__)


def _get_service(request: Request) -> RadarService:
    """Get the RadarService from app state or create a default one."""
    if hasattr(request.app.state, "radar_service") and request.app.state.radar_service is not None:
        return request.app.state.radar_service
    return RadarService()


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
                loop.call_soon(lambda: asyncio.create_task(coro))
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
        status: str | None = None,
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
        status: str | None = None,
        opportunity_type: str | None = None,
        freshness: str | None = None,
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


__all__ = ["register_radar_routes"]
