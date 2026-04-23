"""WebSocket connection handling for real-time event streaming."""

from __future__ import annotations

import logging
from typing import Any, cast

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from cc_deep_research.event_router import EventRouter, WebSocketConnection
from cc_deep_research.telemetry import (
    get_default_dashboard_db_path,
    get_default_telemetry_dir,
    query_live_session_detail,
    query_session_detail,
)
from cc_deep_research.telemetry.tree import empty_decision_graph

logger = logging.getLogger(__name__)


def _serialize_timestamp(value: Any) -> str | None:
    """Return a JSON-safe timestamp string."""
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _query_session_api_detail_for_websocket(
    session_id: str,
    *,
    tail_limit: int,
    subprocess_chunk_limit: int,
    cursor: int | None = None,
    before_cursor: int | None = None,
    limit: int | None = None,
    include_derived: bool = False,
) -> dict[str, Any]:
    """Return session detail for WebSocket event streaming."""
    from datetime import UTC, datetime, timedelta
    from cc_deep_research.telemetry import (
        get_default_dashboard_db_path,
        query_live_session_detail,
        query_session_detail,
    )
    from cc_deep_research.session_store import SessionStore

    STALE_LIVE_SESSION_AFTER = timedelta(minutes=15)

    def _parse_timestamp(value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        if not isinstance(value, str) or not value:
            return None
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)

    def _normalize_live_session_state(session: dict[str, Any]) -> dict[str, Any]:
        if not session.get("active"):
            return session
        last_activity = _parse_timestamp(session.get("last_event_at")) or _parse_timestamp(
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


def register_websocket_routes(app: FastAPI) -> None:
    """Register WebSocket routes for real-time event streaming.

    Args:
        app: The FastAPI application instance.
    """
    from contextlib import asynccontextmanager, suppress
    from cc_deep_research.web_server import get_event_router

    @app.websocket("/ws/session/{session_id}")
    async def websocket_endpoint(websocket: WebSocket, session_id: str) -> None:
        """WebSocket endpoint for real-time event streaming.

        Args:
            websocket: The WebSocket connection.
            session_id: The session ID to subscribe to.
        """
        logger.info(
            "Accepting session websocket session_id=%s client=%s url=%s",
            session_id,
            websocket.client,
            websocket.url,
        )
        await websocket.accept()

        # Create connection wrapper
        connection = WebSocketConnection(websocket, session_id)
        event_router = get_event_router(websocket.app)

        # Subscribe to session events
        await event_router.subscribe(session_id, connection)
        logger.info(
            "Subscribed websocket session_id=%s subscribers=%s",
            session_id,
            event_router.get_subscriber_count(session_id),
        )

        # Send history on connect
        detail = _query_session_api_detail_for_websocket(
            session_id,
            tail_limit=100,
            subprocess_chunk_limit=0,
        )

        # Send initial history
        await connection.send_json({"type": "history", "events": detail["event_tail"] or []})
        logger.info(
            "Sent websocket history session_id=%s event_count=%s",
            session_id,
            len(detail["event_tail"] or []),
        )

        # Listen for client messages
        try:
            while True:
                data = await websocket.receive_json()

                message_type = data.get("type")
                logger.debug(
                    "Received websocket message session_id=%s type=%s payload_keys=%s",
                    session_id,
                    message_type,
                    sorted(data.keys()),
                )

                if message_type == "ping":
                    await connection.send_json({"type": "pong"})
                elif message_type == "get_history":
                    cursor = data.get("cursor")
                    before_cursor = data.get("before_cursor")
                    limit = data.get("limit", 1000)
                    new_detail = _query_session_api_detail_for_websocket(
                        session_id,
                        tail_limit=limit * 2,
                        subprocess_chunk_limit=0,
                        cursor=cursor,
                        before_cursor=before_cursor,
                        limit=limit,
                    )
                    if cursor is not None or before_cursor is not None:
                        events_page = new_detail.get("events_page", {})
                        await connection.send_json(
                            {
                                "type": "history_page",
                                "events": events_page.get("events", []),
                                "total": events_page.get("total", 0),
                                "has_more": events_page.get("has_more", False),
                                "next_cursor": events_page.get("next_cursor"),
                                "prev_cursor": events_page.get("prev_cursor"),
                            }
                        )
                        logger.info(
                            "Served paginated websocket history session_id=%s limit=%s cursor=%s before_cursor=%s returned=%s",
                            session_id,
                            limit,
                            cursor,
                            before_cursor,
                            len(events_page.get("events", [])),
                        )
                    else:
                        await connection.send_json(
                            {
                                "type": "history",
                                "events": new_detail["event_tail"] or [],
                            }
                        )
                        logger.info(
                            "Served websocket history refresh session_id=%s limit=%s returned=%s",
                            session_id,
                            limit,
                            len(new_detail["event_tail"] or []),
                        )
                elif message_type == "subscribe":
                    await event_router.subscribe(session_id, connection)
                    logger.info("Received websocket subscribe session_id=%s", session_id)
                elif message_type == "unsubscribe":
                    await event_router.unsubscribe(session_id, connection)
                    logger.info("Received websocket unsubscribe session_id=%s", session_id)
                else:
                    logger.warning(
                        "Received unsupported websocket message session_id=%s type=%s payload=%s",
                        session_id,
                        message_type,
                        data,
                    )

        except WebSocketDisconnect as exc:
            logger.info(
                "WebSocket disconnected session_id=%s code=%s",
                session_id,
                exc.code,
            )
            await event_router.unsubscribe(session_id, connection)
        except Exception as e:
            logger.exception("WebSocket session handler failed session_id=%s", session_id)
            await event_router.unsubscribe(session_id, connection)
            with suppress(Exception):
                await connection.send_json({"type": "error", "error": str(e)})
        finally:
            logger.info(
                "WebSocket handler finished session_id=%s subscribers=%s",
                session_id,
                event_router.get_subscriber_count(session_id),
            )
