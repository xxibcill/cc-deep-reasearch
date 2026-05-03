"""Session HTTP API routes."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

from cc_deep_research.research_runs.models import (
    BulkSessionDeleteRequest,
    ResearchOutputFormat,
    SessionDeleteRequest,
)
from cc_deep_research.research_runs.session_purge import SessionPurgeService
from cc_deep_research.session_store import SessionStore
from cc_deep_research.telemetry import (
    get_default_dashboard_db_path,
    get_default_telemetry_dir,
    query_checkpoint_detail,
    query_checkpoint_lineage,
    query_latest_resumable_checkpoint,
    query_live_session_detail,
    query_live_sessions,
    query_session_checkpoints,
    query_session_detail,
    query_session_summaries,
)
from cc_deep_research.telemetry.tree import empty_decision_graph
from cc_deep_research.web_server_routes._shared import parse_timestamp, serialize_timestamp

STALE_LIVE_SESSION_AFTER = timedelta(minutes=15)
logger = logging.getLogger(__name__)


class SortOrder(StrEnum):
    """Sort order for session list queries."""

    ASC = "asc"
    DESC = "desc"


class SessionSortBy(StrEnum):
    """Fields available for sorting session lists."""

    CREATED_AT = "created_at"
    LAST_EVENT_AT = "last_event_at"
    TOTAL_TIME_MS = "total_time_ms"


def _normalize_live_session_state(session: dict[str, Any]) -> dict[str, Any]:
    """Mark abandoned live sessions as interrupted instead of running forever."""
    if not session.get("active"):
        return session

    last_activity = parse_timestamp(session.get("last_event_at")) or parse_timestamp(
        session.get("created_at")
    )
    if last_activity is None:
        return session

    if datetime.now(UTC) - last_activity <= STALE_LIVE_SESSION_AFTER:
        return session

    normalized = dict(session)
    normalized["active"] = False
    normalized["status"] = "interrupted"
    return normalized


def _normalize_optional_string(value: Any) -> str | None:
    """Return a trimmed string or explicit null."""
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split()).strip()
    return normalized or None


def _build_session_list_label(
    *,
    session_id: str,
    query: str | None,
    active: bool,
) -> str:
    """Return a human-meaningful session label for list views."""
    if query:
        return query
    prefix = "Active session" if active else "Session"
    return f"{prefix} {session_id[:8]}"


def _normalize_saved_session_summary(saved: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize saved-session metadata into explicit nullable fields."""
    saved = saved or {}
    return {
        "query": _normalize_optional_string(saved.get("query")),
        "depth": _normalize_optional_string(saved.get("depth")),
        "started_at": serialize_timestamp(saved.get("started_at")),
        "completed_at": serialize_timestamp(saved.get("completed_at")),
        "total_sources": saved.get("total_sources"),
        "has_session_payload": bool(saved.get("has_session_payload")),
        "has_report": bool(saved.get("has_report")),
        "label": _normalize_optional_string(saved.get("label")),
        "archived": bool(saved.get("archived")),
    }


def _build_session_list_row(
    *,
    session_id: str,
    created_at: Any = None,
    total_time_ms: Any = None,
    total_sources: Any = None,
    status: Any = None,
    active: bool = False,
    event_count: Any = None,
    last_event_at: Any = None,
    saved: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the normalized session-list payload shared across storage layers."""
    saved_summary = _normalize_saved_session_summary(saved)
    query = saved_summary["query"]
    created_at_value = serialize_timestamp(created_at) or saved_summary["started_at"]
    completed_at_value = saved_summary["completed_at"]
    last_event_value = serialize_timestamp(last_event_at) or completed_at_value or created_at_value
    total_sources_value = total_sources
    if total_sources_value is None:
        total_sources_value = saved_summary["total_sources"]

    return {
        "session_id": session_id,
        "label": saved_summary["label"]
        or _build_session_list_label(session_id=session_id, query=query, active=active),
        "created_at": created_at_value,
        "total_time_ms": total_time_ms,
        "total_sources": total_sources_value,
        "status": _normalize_optional_string(status)
        or ("completed" if completed_at_value else "unknown"),
        "active": active,
        "event_count": event_count,
        "last_event_at": last_event_value,
        "query": query,
        "depth": saved_summary["depth"],
        "completed_at": completed_at_value,
        "has_session_payload": saved_summary["has_session_payload"],
        "has_report": saved_summary["has_report"],
        "archived": saved_summary["archived"],
    }


def _query_session_api_detail(
    session_id: str,
    *,
    tail_limit: int,
    subprocess_chunk_limit: int,
    cursor: int | None = None,
    before_cursor: int | None = None,
    limit: int | None = None,
    include_derived: bool = True,
) -> dict[str, Any]:
    """Return session detail from live telemetry, or DuckDB when only historical data exists."""
    telemetry_dir = get_default_telemetry_dir()
    live_detail = query_live_session_detail(
        session_id,
        base_dir=telemetry_dir,
        tail_limit=tail_limit,
        subprocess_chunk_limit=subprocess_chunk_limit,
        cursor=cursor,
        before_cursor=before_cursor,
        limit=limit,
        include_derived=include_derived,
    )
    if live_detail["session"]:
        live_detail["session"] = _normalize_live_session_state(live_detail["session"])
        return live_detail

    historical = query_session_detail(
        session_id,
        db_path=get_default_dashboard_db_path(),
        cursor=cursor,
        before_cursor=before_cursor,
        limit=limit or tail_limit,
        include_derived=include_derived,
    )
    session_data = historical.get("session")
    if session_data is None:
        return live_detail

    events = historical.get("events", [])
    saved_session = SessionStore().load_session(session_id)
    summary = saved_session.model_dump(mode="json") if saved_session is not None else None
    session = {
        "session_id": session_data.get("session_id"),
        "created_at": session_data.get("created_at"),
        "status": session_data.get("status"),
        "total_time_ms": session_data.get("total_time_ms"),
        "total_sources": session_data.get("total_sources", 0),
        "active": False,
        "event_count": len(events),
        "last_event_at": events[-1].get("timestamp") if events else None,
    }
    return {
        "session": session,
        "summary": summary,
        "events": events,
        "event_tail": events[-tail_limit:],
        "events_page": historical.get("events_page", {"events": [], "total": 0, "has_more": False, "next_cursor": None, "prev_cursor": None}),
        "agent_timeline": [event for event in events if event.get("category") == "agent"],
        "event_tree": {"root_events": [], "total_events": len(events), "session_id": session_id},
        "subprocess_streams": [],
        "llm_route_analytics": {},
        "active_phase": historical.get("active_phase"),
        "narrative": historical.get("narrative", []),
        "critical_path": historical.get("critical_path", {}),
        "state_changes": historical.get("state_changes", []),
        "decisions": historical.get("decisions", []),
        "degradations": historical.get("degradations", []),
        "failures": historical.get("failures", []),
        "decision_graph": historical.get("decision_graph", empty_decision_graph()),
    }


def _normalize_historical_session(
    row: tuple[Any, ...],
    *,
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Convert a persisted telemetry row into the public API session shape."""
    return {
        "session_id": row[0],
        "created_at": serialize_timestamp(row[1]),
        "status": row[2],
        "total_time_ms": row[3],
        "total_sources": row[4],
        "active": False,
        "event_count": len(events),
        "last_event_at": events[-1]["timestamp"] if events else None,
    }


def _normalize_historical_event(row: tuple[Any, ...], *, session_id: str) -> dict[str, Any]:
    """Convert a persisted telemetry row into the public API event shape."""
    metadata = json.loads(row[10]) if row[10] else {}
    return {
        "event_id": row[0],
        "parent_event_id": row[1],
        "sequence_number": row[2],
        "timestamp": serialize_timestamp(row[3]),
        "session_id": session_id,
        "event_type": row[4],
        "category": row[5],
        "name": row[6],
        "status": row[7],
        "duration_ms": row[8],
        "agent_id": row[9],
        "metadata": metadata if isinstance(metadata, dict) else {},
    }


def register_session_routes(app: FastAPI) -> None:
    """Register session HTTP API routes.

    Args:
        app: The FastAPI application instance.
    """

    @app.get("/api/sessions")
    async def list_sessions(
        active_only: bool = False,
        archived_only: bool = False,
        limit: int = Query(default=100, ge=1, le=500),
        cursor: str | None = Query(
            default=None, description="Session ID to start after for stable pagination"
        ),
        search: str | None = Query(default=None, description="Search text for session query"),
        status: str | None = Query(default=None, description="Filter by session status"),
        sort_by: SessionSortBy = Query(
            default=SessionSortBy.LAST_EVENT_AT, description="Sort field"
        ),
        sort_order: SortOrder = Query(default=SortOrder.DESC, description="Sort order"),
    ) -> JSONResponse:
        """List research sessions with query, filter, sort, and pagination support."""
        telemetry_dir = get_default_telemetry_dir()
        live_sessions = query_live_sessions(base_dir=telemetry_dir)
        session_store = SessionStore()
        saved_sessions = session_store.list_sessions()
        archived_session_ids = session_store.get_archived_session_ids() if archived_only else set()
        saved_by_id = {s["session_id"]: s for s in saved_sessions}

        sessions_by_id: dict[str, dict[str, Any]] = {}

        for session in live_sessions:
            if active_only and not session.get("active"):
                continue
            normalized_session = _normalize_live_session_state(session)
            if active_only and not normalized_session.get("active"):
                continue
            session_id = normalized_session["session_id"]
            sessions_by_id[session_id] = _build_session_list_row(
                session_id=session_id,
                created_at=normalized_session.get("created_at"),
                total_time_ms=normalized_session.get("total_time_ms"),
                total_sources=normalized_session.get("total_sources", 0),
                status=normalized_session.get("status", "unknown"),
                active=bool(normalized_session.get("active", False)),
                event_count=normalized_session.get("event_count"),
                last_event_at=normalized_session.get("last_event_at"),
                saved=saved_by_id.get(session_id),
            )

        # Use focused session summary query instead of query_dashboard_data()
        # to avoid loading global events, agent timeline, and phase-duration datasets
        db_summaries = query_session_summaries(
            get_default_dashboard_db_path(),
            limit=limit * 3,
            cursor=cursor,
            search=search if not search or len(search) < 2 else None,
            status=status if status else None,
            archived_only=archived_only,
            sort_by=sort_by.value,
            sort_order=sort_order.value,
        )
        for session_data in db_summaries.get("sessions", []):
            if active_only:
                continue
            session_id = session_data["session_id"]
            if session_id in sessions_by_id:
                existing = sessions_by_id[session_id]
                if not existing.get("active"):
                    existing["status"] = session_data.get("status")
                if existing.get("total_time_ms") is None:
                    existing["total_time_ms"] = session_data.get("total_time_ms")
                if existing.get("total_sources") in (None, 0):
                    existing["total_sources"] = session_data.get("total_sources")
                if existing.get("created_at") is None:
                    existing["created_at"] = session_data.get("created_at")
                if existing.get("last_event_at") is None:
                    existing["last_event_at"] = existing.get("completed_at") or existing.get("created_at")
                continue
            sessions_by_id[session_id] = _build_session_list_row(
                session_id=session_id,
                created_at=session_data.get("created_at"),
                total_time_ms=session_data.get("total_time_ms"),
                total_sources=session_data.get("total_sources"),
                status=session_data.get("status"),
                active=False,
                event_count=None,
                last_event_at=None,
                saved=saved_by_id.get(session_id),
            )

        for saved in saved_sessions:
            session_id = saved["session_id"]
            if session_id in sessions_by_id:
                continue
            if active_only:
                continue
            is_archived = session_id in archived_session_ids or saved.get("archived", False)
            if is_archived and not archived_only:
                continue
            sessions_by_id[session_id] = _build_session_list_row(
                session_id=session_id,
                created_at=saved.get("started_at"),
                total_time_ms=None,
                total_sources=saved.get("total_sources"),
                status=None,
                active=False,
                event_count=None,
                last_event_at=saved.get("completed_at") or saved.get("started_at"),
                saved=saved,
            )

        sessions = list(sessions_by_id.values())

        if search and len(search) >= 2:
            search_lower = search.lower()
            sessions = [
                s
                for s in sessions
                if search_lower in (s.get("query") or "").lower()
                or search_lower in (s.get("label") or "").lower()
                or search_lower in s["session_id"].lower()
            ]

        if status:
            sessions = [s for s in sessions if s.get("status") == status]

        sessions = [s for s in sessions if archived_only == (s.get("archived") or session_store.is_session_archived(s.get("session_id", "")))]

        def sort_key(s: dict[str, Any]) -> Any:
            sort_field_value = s.get(sort_by.value)
            if sort_by == SessionSortBy.TOTAL_TIME_MS:
                return sort_field_value if isinstance(sort_field_value, (int, float)) else -1
            return sort_field_value if isinstance(sort_field_value, str) else ""

        reverse = sort_order == SortOrder.DESC
        sessions.sort(key=sort_key, reverse=reverse)
        sessions.sort(key=lambda session: 0 if session.get("active") else 1)

        total = len(sessions)

        if cursor:
            cursor_index = None
            for i, s in enumerate(sessions):
                if s["session_id"] == cursor:
                    cursor_index = i + 1
                    break
            if cursor_index is not None:
                sessions = sessions[cursor_index:]

        remaining_sessions = len(sessions)
        sessions = sessions[:limit]

        next_cursor = None
        if len(sessions) == limit and remaining_sessions > limit:
            next_cursor = sessions[-1]["session_id"]

        return JSONResponse(
            content={
                "sessions": sessions,
                "total": total,
                "next_cursor": next_cursor,
            }
        )

    @app.get("/api/sessions/{session_id}")
    async def get_session(
        session_id: str,
        cursor: int | None = Query(default=None, description="Sequence number to start after"),
        before_cursor: int | None = Query(default=None, description="Sequence number to end before"),
        limit: int = Query(default=1000, ge=1, le=5000, description="Maximum events to return"),
        include_derived: bool = Query(default=True, description="Include derived outputs"),
        include_checkpoints: bool = Query(default=True, description="Include checkpoint inventory"),
    ) -> JSONResponse:
        """Get details for a specific session."""
        detail = _query_session_api_detail(
            session_id,
            tail_limit=1000,
            subprocess_chunk_limit=100,
            cursor=cursor,
            before_cursor=before_cursor,
            limit=limit,
            include_derived=include_derived,
        )

        if not detail["session"]:
            return JSONResponse(content={"error": "Session not found"}, status_code=404)

        response_content = {
            "session": detail["session"],
            "summary": detail.get("summary"),
            "events_page": detail.get("events_page", {
                "events": detail.get("events", [])[:limit],
                "total": len(detail.get("events", [])),
                "has_more": False,
                "next_cursor": None,
                "prev_cursor": None,
            }),
            "event_tail": detail.get("event_tail", []),
            "agent_timeline": detail.get("agent_timeline", []),
            "active_phase": detail.get("active_phase"),
            "narrative": detail.get("narrative", []),
            "critical_path": detail.get("critical_path", {}),
            "state_changes": detail.get("state_changes", []),
            "decisions": detail.get("decisions", []),
            "degradations": detail.get("degradations", []),
            "failures": detail.get("failures", []),
            "decision_graph": detail.get("decision_graph", empty_decision_graph()),
        }

        if include_checkpoints:
            telemetry_dir = get_default_telemetry_dir()
            checkpoint_manifest = query_session_checkpoints(session_id, base_dir=telemetry_dir)
            response_content["checkpoints"] = {
                "total": len(checkpoint_manifest.get("checkpoints", [])),
                "latest_checkpoint_id": checkpoint_manifest.get("latest_checkpoint_id"),
                "latest_resume_safe_checkpoint_id": checkpoint_manifest.get("latest_resume_safe_checkpoint_id"),
                "resume_available": checkpoint_manifest.get("latest_resume_safe_checkpoint_id") is not None,
            }

        return JSONResponse(content=response_content)

    @app.delete("/api/sessions/{session_id}")
    async def delete_session(
        session_id: str,
        force: bool = False,
    ) -> JSONResponse:
        """Delete a research session from all storage layers."""
        request = SessionDeleteRequest(session_id=session_id, force=force)
        service = SessionPurgeService()
        response = service.delete_session(request)

        status_code = 409 if response.active_conflict else 200
        return JSONResponse(
            content=response.model_dump(mode="json"),
            status_code=status_code,
        )

    @app.post("/api/sessions/bulk-delete")
    async def bulk_delete_sessions(request: BulkSessionDeleteRequest) -> JSONResponse:
        """Delete multiple research sessions with explicit per-session outcomes."""
        service = SessionPurgeService()
        response = service.delete_sessions(request)
        return JSONResponse(content=response.model_dump(mode="json"))

    @app.get("/api/sessions/purge-summary")
    async def get_purge_summary() -> JSONResponse:
        """Return summary of sessions that could be purged."""
        telemetry_dir = get_default_telemetry_dir()
        session_store = SessionStore()

        archived_ids = session_store.get_archived_session_ids()
        all_saved = session_store.list_sessions()

        archived_sessions = []
        no_artifacts_sessions = []
        active_session_ids: set[str] = set()

        live_sessions = query_live_sessions(base_dir=telemetry_dir)
        for session in live_sessions:
            if session.get("active"):
                active_session_ids.add(session.get("session_id", ""))

        for saved in all_saved:
            session_id = saved.get("session_id", "")
            is_archived = session_id in archived_ids or saved.get("archived", False)
            has_payload = saved.get("has_session_payload", False)
            has_report = saved.get("has_report", False)

            if session_id in active_session_ids:
                continue

            if is_archived:
                archived_sessions.append({
                    "session_id": session_id,
                    "has_payload": has_payload,
                    "has_report": has_report,
                    "completed_at": saved.get("completed_at"),
                })
            elif not has_payload and not has_report:
                no_artifacts_sessions.append({
                    "session_id": session_id,
                    "completed_at": saved.get("completed_at"),
                })

        recommendations = []
        if archived_sessions:
            recommendations.append({
                "category": "archived",
                "description": f"{len(archived_sessions)} archived session(s) are safe to purge",
                "action": "bulk-purge-archived",
                "count": len(archived_sessions),
            })
        if no_artifacts_sessions:
            recommendations.append({
                "category": "no-artifacts",
                "description": f"{len(no_artifacts_sessions)} session(s) have no payload or report",
                "action": "review-no-artifacts",
                "count": len(no_artifacts_sessions),
            })

        return JSONResponse(content={
            "archived_sessions_count": len(archived_sessions),
            "no_artifacts_count": len(no_artifacts_sessions),
            "active_count": len(active_session_ids),
            "recommendations": recommendations,
        })

    @app.post("/api/sessions/purge-archived")
    async def purge_archived_sessions(
        dry_run: bool = Query(default=True, description="If true, only return what would be deleted"),
        force: bool = Query(default=False, description="Delete even if sessions are active"),
    ) -> JSONResponse:
        """Purge all archived sessions."""
        session_store = SessionStore()
        service = SessionPurgeService()

        archived_ids = list(session_store.get_archived_session_ids())

        if dry_run:
            return JSONResponse(content={
                "dry_run": True,
                "would_delete": len(archived_ids),
                "session_ids": archived_ids,
                "message": f"Would delete {len(archived_ids)} archived session(s)",
            })

        if not archived_ids:
            return JSONResponse(content={
                "deleted": 0,
                "session_ids": [],
                "message": "No archived sessions to purge",
            })

        request = BulkSessionDeleteRequest(session_ids=archived_ids, force=force)
        response = service.delete_sessions(request)

        return JSONResponse(content={
            "dry_run": False,
            "deleted": response.summary.deleted_count,
            "failed": response.summary.failed_count,
            "session_ids": archived_ids,
            "results": response.model_dump(mode="json"),
        })

    @app.post("/api/sessions/{session_id}/archive")
    async def archive_session(session_id: str) -> JSONResponse:
        """Archive a session, hiding it from the default session list."""
        store = SessionStore()
        if not store.session_exists(session_id):
            return JSONResponse(
                content={"error": f"Session not found: {session_id}"},
                status_code=404,
            )

        success = store.archive_session(session_id)
        if success:
            return JSONResponse(
                content={
                    "session_id": session_id,
                    "archived": True,
                }
            )
        return JSONResponse(
            content={"error": f"Failed to archive session: {session_id}"},
            status_code=500,
        )

    @app.post("/api/sessions/{session_id}/restore")
    async def restore_session(session_id: str) -> JSONResponse:
        """Restore an archived session to the active list."""
        store = SessionStore()
        if not store.session_exists(session_id):
            return JSONResponse(
                content={"error": f"Session not found: {session_id}"},
                status_code=404,
            )

        success = store.restore_session(session_id)
        if success:
            return JSONResponse(
                content={
                    "session_id": session_id,
                    "archived": False,
                }
            )
        return JSONResponse(
            content={"error": f"Failed to restore session: {session_id}"},
            status_code=500,
        )

    @app.get("/api/sessions/{session_id}/events")
    async def get_session_events(
        session_id: str,
        limit: int = Query(default=1000, ge=1, le=5000, description="Maximum events to return"),
        cursor: int | None = Query(default=None, description="Sequence number to start after"),
        before_cursor: int | None = Query(default=None, description="Sequence number to end before"),
        offset: int = Query(default=0, ge=0, description="Number of events to skip (deprecated, use cursor)"),
    ) -> JSONResponse:
        """Get events for a specific session with cursor-based pagination."""
        detail = _query_session_api_detail(
            session_id,
            tail_limit=limit * 2,
            subprocess_chunk_limit=0,
            cursor=cursor,
            before_cursor=before_cursor,
            limit=limit,
            include_derived=False,
        )

        events_page = detail.get("events_page", {})

        if not events_page.get("events"):
            events = detail.get("event_tail") or detail.get("events") or []
            if offset > 0:
                events = events[offset : offset + limit]
            else:
                events = events[:limit]

            return JSONResponse(content={
                "events": events,
                "count": len(events),
                "total": len(detail.get("events", [])),
                "has_more": False,
                "next_cursor": None,
                "prev_cursor": None,
            })

        return JSONResponse(content={
            "events": events_page["events"],
            "count": len(events_page["events"]),
            "total": events_page["total"],
            "has_more": events_page["has_more"],
            "next_cursor": events_page["next_cursor"],
            "prev_cursor": events_page["prev_cursor"],
        })

    @app.get("/api/sessions/{session_id}/report")
    async def get_session_report(
        session_id: str,
        format: str = "markdown",
    ) -> JSONResponse:
        """Get the rendered report for a completed session."""
        try:
            output_format = ResearchOutputFormat(format.lower())
        except ValueError:
            return JSONResponse(
                content={"error": f"Invalid format: {format}. Supported: markdown, json, html"},
                status_code=400,
            )

        store = SessionStore()
        session = store.load_session(session_id)

        if session is None:
            return JSONResponse(
                content={"error": f"Session not found: {session_id}"},
                status_code=404,
            )

        cached_report = store.load_report(session_id, output_format)
        if cached_report is not None:
            return JSONResponse(
                content={
                    "session_id": session_id,
                    "format": output_format.value,
                    "media_type": _media_type_for_report(output_format),
                    "content": cached_report,
                }
            )

        from cc_deep_research.config import load_config
        from cc_deep_research.reporting import ReportGenerator

        analysis = session.metadata.get("analysis", {})
        if not analysis:
            return JSONResponse(
                content={"error": "Session has no analysis data yet"},
                status_code=404,
            )

        config = load_config()
        reporter = ReportGenerator(config)

        if output_format == ResearchOutputFormat.JSON:
            content = reporter.generate_json_report(session, analysis)
        elif output_format == ResearchOutputFormat.HTML:
            markdown = store.load_report(session_id, ResearchOutputFormat.MARKDOWN)
            if markdown is None:
                markdown = reporter.generate_markdown_report(session, analysis)
                store.save_report(session_id, ResearchOutputFormat.MARKDOWN, markdown)
            content = reporter.render_html_report(markdown)
        else:
            content = reporter.generate_markdown_report(session, analysis)
        store.save_report(session_id, output_format, content)

        return JSONResponse(
            content={
                "session_id": session_id,
                "format": output_format.value,
                "media_type": _media_type_for_report(output_format),
                "content": content,
            }
        )

    @app.get("/api/sessions/{session_id}/bundle")
    async def get_session_bundle(
        session_id: str,
        include_payload: bool = Query(default=False, description="Include full session payload"),
        include_report: bool = Query(default=False, description="Include report content"),
    ) -> JSONResponse:
        """Get a portable trace bundle for a session."""
        store = SessionStore()

        if not store.session_exists(session_id):
            return JSONResponse(
                content={"error": f"Session not found: {session_id}"},
                status_code=404,
            )

        bundle = store.export_trace_bundle(
            session_id,
            include_payload=include_payload,
            include_report=include_report,
        )

        if bundle is None:
            return JSONResponse(
                content={"error": f"Failed to export bundle for session: {session_id}"},
                status_code=500,
            )

        return JSONResponse(content=bundle)

    @app.get("/api/sessions/{session_id}/artifacts")
    async def get_session_artifacts(session_id: str) -> JSONResponse:
        """Get artifact inventory with provenance metadata for a session."""
        store = SessionStore()
        session = store.load_session(session_id)

        if session is None:
            return JSONResponse(
                content={"error": f"Session not found: {session_id}"},
                status_code=404,
            )

        artifacts: dict[str, Any] = {
            "session_id": session_id,
            "provenance": {},
            "available": {},
            "missing": {},
        }

        has_report = bool(session.metadata.get("analysis"))
        has_payload = True

        artifacts["available"]["session_payload"] = {
            "present": has_payload,
            "provenance": "direct",
            "description": "Full research session data including sources and collected content",
        }

        if has_report:
            report_formats = []
            for fmt in [ResearchOutputFormat.MARKDOWN, ResearchOutputFormat.JSON, ResearchOutputFormat.HTML]:
                if store.load_report(session_id, fmt) is not None:
                    report_formats.append(fmt.value)
                else:
                    path = store._report_path(session_id, fmt)
                    if path.exists():
                        report_formats.append(fmt.value)

            artifacts["available"]["reports"] = {
                "present": True,
                "provenance": "derived",
                "formats": report_formats,
                "description": "Generated research report in various formats",
            }
            del artifacts["missing"]
        else:
            artifacts["missing"]["reports"] = {
                "present": False,
                "provenance": "derived",
                "reason": "Run did not complete or analysis data is not available",
                "description": "Research report generated from analysis data",
            }

        artifacts["available"]["trace_bundle"] = {
            "present": True,
            "provenance": "derived",
            "description": "Portable trace bundle with telemetry events and derived outputs",
        }

        telemetry_dir = get_default_telemetry_dir()
        checkpoint_manifest = query_session_checkpoints(session_id, base_dir=telemetry_dir)
        has_checkpoints = len(checkpoint_manifest.get("checkpoints", [])) > 0

        if has_checkpoints:
            artifacts["available"]["checkpoints"] = {
                "present": True,
                "provenance": "derived",
                "count": len(checkpoint_manifest.get("checkpoints", [])),
                "latest_checkpoint_id": checkpoint_manifest.get("latest_checkpoint_id"),
                "resume_available": checkpoint_manifest.get("latest_resume_safe_checkpoint_id") is not None,
                "description": "Session checkpoints for potential resume",
            }
        else:
            artifacts["missing"]["checkpoints"] = {
                "present": False,
                "provenance": "derived",
                "reason": "No checkpoints were captured during this session",
                "description": "Session checkpoints for potential resume",
            }

        return JSONResponse(content=artifacts)

    @app.get("/api/sessions/{session_id}/checkpoints")
    async def get_session_checkpoints(session_id: str) -> JSONResponse:
        """Get checkpoint inventory for a session."""
        telemetry_dir = get_default_telemetry_dir()
        session_dir = telemetry_dir / session_id

        if not session_dir.exists():
            return JSONResponse(
                content={"error": f"Session not found: {session_id}"},
                status_code=404,
            )

        manifest = query_session_checkpoints(session_id, base_dir=telemetry_dir)
        return JSONResponse(content=manifest)

    @app.get("/api/sessions/{session_id}/checkpoints/{checkpoint_id}")
    async def get_checkpoint_detail(session_id: str, checkpoint_id: str) -> JSONResponse:
        """Get detailed information for a specific checkpoint."""
        telemetry_dir = get_default_telemetry_dir()
        checkpoint = query_checkpoint_detail(session_id, checkpoint_id, base_dir=telemetry_dir)

        if checkpoint is None:
            return JSONResponse(
                content={"error": f"Checkpoint not found: {checkpoint_id}"},
                status_code=404,
            )

        lineage = query_checkpoint_lineage(session_id, checkpoint_id, base_dir=telemetry_dir)
        checkpoint["lineage"] = [cp.get("checkpoint_id") for cp in lineage]

        return JSONResponse(content=checkpoint)

    @app.get("/api/sessions/{session_id}/checkpoints/{checkpoint_id}/lineage")
    async def get_checkpoint_lineage_endpoint(session_id: str, checkpoint_id: str) -> JSONResponse:
        """Get checkpoint lineage from start to specified checkpoint."""
        telemetry_dir = get_default_telemetry_dir()
        lineage = query_checkpoint_lineage(session_id, checkpoint_id, base_dir=telemetry_dir)

        return JSONResponse(content={
            "session_id": session_id,
            "checkpoint_id": checkpoint_id,
            "lineage": lineage,
            "depth": len(lineage),
        })

    @app.post("/api/sessions/{session_id}/resume")
    async def resume_session(
        session_id: str,
        checkpoint_id: str | None = Query(default=None, description="Checkpoint to resume from"),
        mode: str = Query(default="resume_latest", description="Resume mode"),
    ) -> JSONResponse:
        """Resume a session from a checkpoint."""
        from cc_deep_research.models.checkpoint import ResumeResult

        telemetry_dir = get_default_telemetry_dir()
        session_dir = telemetry_dir / session_id

        if not session_dir.exists():
            return JSONResponse(
                content={"error": f"Session not found: {session_id}"},
                status_code=404,
            )

        if checkpoint_id is None:
            checkpoint = query_latest_resumable_checkpoint(session_id, base_dir=telemetry_dir)
            if checkpoint is None:
                return JSONResponse(
                    content={"error": "No resumable checkpoint available"},
                    status_code=404,
                )
            checkpoint_id = checkpoint["checkpoint_id"]
        else:
            checkpoint = query_checkpoint_detail(session_id, checkpoint_id, base_dir=telemetry_dir)
            if checkpoint is None:
                return JSONResponse(
                    content={"error": f"Checkpoint not found: {checkpoint_id}"},
                    status_code=404,
                )
            if not checkpoint.get("resume_safe"):
                return JSONResponse(
                    content={"error": f"Checkpoint {checkpoint_id} is not safe to resume from"},
                    status_code=409,
                )

        lineage = query_checkpoint_lineage(session_id, checkpoint_id, base_dir=telemetry_dir)
        lineage_ids = [cp.get("checkpoint_id") for cp in lineage]

        result = ResumeResult(
            success=True,
            session_id=f"{session_id}-resumed",
            original_session_id=session_id,
            resumed_from_checkpoint_id=checkpoint_id,
            resume_mode=mode,
            checkpoint_lineage=lineage_ids,
            message=f"Ready to resume from checkpoint {checkpoint_id}. Use the checkpoint info to start a new run.",
        )

        return JSONResponse(content=result.model_dump(mode="json"))

    @app.post("/api/sessions/{session_id}/rerun-step")
    async def rerun_step(request: dict) -> JSONResponse:
        """Rerun a single step from a checkpoint in debug mode."""
        from pydantic import ValidationError

        from cc_deep_research.models.checkpoint import RerunStepRequest, RerunStepResult

        try:
            rerun_request = RerunStepRequest.model_validate(request)
        except ValidationError:
            return JSONResponse(
                content={"error": "session_id and checkpoint_id are required"},
                status_code=400,
            )

        telemetry_dir = get_default_telemetry_dir()
        checkpoint = query_checkpoint_detail(
            rerun_request.session_id,
            rerun_request.checkpoint_id,
            base_dir=telemetry_dir,
        )

        if checkpoint is None:
            return JSONResponse(
                content={"error": f"Checkpoint not found: {rerun_request.checkpoint_id}"},
                status_code=404,
            )

        if not checkpoint.get("replayable"):
            reason = checkpoint.get("replayable_reason", "Unknown reason")
            return JSONResponse(
                content={"error": f"Checkpoint is not replayable: {reason}"},
                status_code=409,
            )

        result = RerunStepResult(
            success=False,
            session_id=rerun_request.session_id,
            checkpoint_id=rerun_request.checkpoint_id,
            output_match=None,
            message=(
                f"Checkpoint {rerun_request.checkpoint_id} is replayable, "
                "but step rerun execution is not implemented yet."
            ),
            error="Step rerun execution is not implemented yet.",
        )

        return JSONResponse(content=result.model_dump(mode="json"), status_code=501)


def _media_type_for_report(output_format: ResearchOutputFormat) -> str:
    """Return the response media type for one report format."""
    if output_format == ResearchOutputFormat.JSON:
        return "application/json"
    if output_format == ResearchOutputFormat.HTML:
        return "text/html"
    return "text/markdown"
