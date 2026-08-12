"""Session API view models and storage-to-response adapters."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from cc_deep_research.session_store import SessionStore
from cc_deep_research.telemetry import (
    get_default_dashboard_db_path,
    get_default_telemetry_dir,
    query_live_session_detail,
    query_session_detail,
)
from cc_deep_research.telemetry.tree import empty_decision_graph
from cc_deep_research.web_server_routes._shared import parse_timestamp, serialize_timestamp

STALE_LIVE_SESSION_AFTER = timedelta(minutes=15)


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
        "triage_status": saved.get("triage_status"),
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
        "triage_status": saved_summary.get("triage_status"),
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
    saved_session = SessionStore().load_session(session_id)
    saved_payload = saved_session.model_dump(mode="json") if saved_session is not None else None
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
        live_session = _normalize_live_session_state(live_detail["session"])
        live_session.update(
            {
                "has_session_payload": saved_payload is not None,
                "has_report": False,
            }
        )
        if saved_payload is not None:
            saved_metadata = saved_payload.get("metadata", {})
            query = _normalize_optional_string(saved_payload.get("query"))
            live_session.update(
                {
                    "label": _build_session_list_label(
                        session_id=session_id,
                        query=query,
                        active=bool(live_session.get("active")),
                    ),
                    "query": query,
                    "depth": _normalize_optional_string(saved_payload.get("depth")),
                    "completed_at": serialize_timestamp(saved_payload.get("completed_at")),
                    "has_session_payload": True,
                    "has_report": bool(
                        isinstance(saved_metadata, dict) and saved_metadata.get("analysis")
                    ),
                }
            )
            telemetry_summary = live_detail.get("summary")
            live_detail["summary"] = {
                **(telemetry_summary if isinstance(telemetry_summary, dict) else {}),
                **saved_payload,
            }
        live_detail["session"] = live_session
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
    summary = saved_payload
    session = {
        "session_id": session_data.get("session_id"),
        "created_at": session_data.get("created_at"),
        "status": session_data.get("status"),
        "total_time_ms": session_data.get("total_time_ms"),
        "total_sources": session_data.get("total_sources", 0),
        "active": False,
        "event_count": len(events),
        "last_event_at": events[-1].get("timestamp") if events else None,
        "has_session_payload": saved_payload is not None,
        "has_report": bool(
            saved_payload is not None
            and isinstance(saved_payload.get("metadata"), dict)
            and saved_payload["metadata"].get("analysis")
        ),
    }
    return {
        "session": session,
        "summary": summary,
        "events": events,
        "event_tail": events[-tail_limit:],
        "events_page": historical.get(
            "events_page",
            {"events": [], "total": 0, "has_more": False, "next_cursor": None, "prev_cursor": None},
        ),
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
