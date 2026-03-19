"""DuckDB-backed analytics queries for persisted telemetry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .ingest import _missing_dashboard_dependency_message, get_default_dashboard_db_path
from .live import get_default_telemetry_dir, query_live_llm_route_analytics
from .tree import (
    build_derived_summary,
    build_event_tree_from_rows,
    build_llm_route_streams,
    is_terminal_session_event,
)


def _load_dashboard_connection(database_path: Path):
    """Open a read-only DuckDB connection or raise a consistent dependency error."""
    try:
        import duckdb
    except ImportError as exc:  # pragma: no cover - import guard
        raise RuntimeError(_missing_dashboard_dependency_message("Dashboard queries")) from exc

    return duckdb.connect(str(database_path), read_only=True)


def _normalize_event_row(row: tuple[Any, ...]) -> dict[str, Any]:
    """Convert a DuckDB event row into the public event payload shape with trace contract fields."""
    # Basic fields (original schema)
    event_id = row[0]
    parent_event_id = row[1]
    sequence_number = row[2]
    timestamp = row[3]
    event_type = row[4]
    category = row[5]
    name = row[6]
    status = row[7]
    duration_ms = row[8]
    agent_id = row[9]
    metadata = json.loads(row[10]) if row[10] else {}

    # Infer additional trace contract fields
    actor_type = "agent" if agent_id else "system"
    degraded = (
        status in ("failed", "fallback", "degraded")
        or "fallback" in event_type
        or "degraded" in event_type
    )

    # Infer severity
    if status in ("failed", "error", "critical"):
        severity = "error"
    elif status in ("fallback", "degraded", "warning"):
        severity = "warning"
    elif "fallback" in event_type or "degraded" in event_type:
        severity = "warning"
    else:
        severity = "info"

    # Infer reason code
    reason_code = metadata.get("reason") or metadata.get("stop_reason")
    if not reason_code:
        if "fallback" in event_type:
            reason_code = "fallback"
        elif status == "failed":
            reason_code = "error"
        elif status == "completed":
            reason_code = "success"

    # Infer phase from event type/category
    phase = None
    if "session." in event_type:
        phase = "session"
    elif "phase." in event_type:
        phase = name
    elif category == "phase":
        phase = name
    elif "iteration." in event_type:
        phase = "iteration"
    elif "llm." in event_type:
        phase = "llm"

    return {
        # Core identity
        "event_id": event_id,
        "parent_event_id": parent_event_id,
        "sequence_number": sequence_number,
        "timestamp": _serialize_timestamp(timestamp),
        # Trace contract
        "trace_version": "0",  # Pre-contract events from DuckDB
        "run_id": None,
        "cause_event_id": None,
        # Event classification
        "event_type": event_type,
        "category": category,
        "name": name,
        "status": status,
        "severity": severity,
        "reason_code": reason_code,
        # Execution context
        "phase": phase,
        "operation": name,
        "attempt": 1,
        # Actor
        "actor_type": actor_type,
        "actor_id": agent_id,
        "agent_id": agent_id,  # Keep for backward compatibility
        # Metrics
        "duration_ms": duration_ms,
        "degraded": degraded,
        # Payload
        "metadata": metadata,
    }


def query_dashboard_data(db_path: Path | None = None) -> dict[str, Any]:
    """Return summary metrics and datasets used by dashboard views."""
    database_path = db_path or get_default_dashboard_db_path()
    if not database_path.exists():
        return {
            "kpis": {},
            "sessions": [],
            "events": [],
            "agent_timeline": [],
            "phase_durations": [],
        }

    conn = _load_dashboard_connection(database_path)
    kpi_row = conn.execute(
        """
        SELECT
            COUNT(*) AS sessions,
            COALESCE(AVG(total_time_ms), 0) AS avg_time_ms,
            COALESCE(AVG(llm_total_tokens), 0) AS avg_tokens,
            COALESCE(AVG(search_queries), 0) AS avg_searches,
            COALESCE(AVG(tool_calls), 0) AS avg_tool_calls
        FROM telemetry_sessions
        """
    ).fetchone()
    sessions = conn.execute(
        """
        SELECT
            session_id,
            created_at,
            total_time_ms,
            total_sources,
            instances_spawned,
            search_queries,
            tool_calls,
            llm_total_tokens,
            status
        FROM telemetry_sessions
        ORDER BY created_at DESC NULLS LAST
        """
    ).fetchall()
    events = conn.execute(
        """
        SELECT
            event_id,
            parent_event_id,
            sequence_number,
            session_id,
            timestamp,
            event_type,
            category,
            name,
            status,
            duration_ms,
            agent_id,
            metadata_json
        FROM telemetry_events
        ORDER BY sequence_number ASC, timestamp DESC NULLS LAST
        LIMIT 2000
        """
    ).fetchall()
    agent_timeline = conn.execute(
        """
        SELECT
            event_id,
            parent_event_id,
            sequence_number,
            session_id,
            agent_id,
            event_type,
            name,
            status,
            duration_ms,
            timestamp
        FROM telemetry_events
        WHERE category = 'agent' AND agent_id IS NOT NULL
        ORDER BY sequence_number ASC, timestamp DESC NULLS LAST
        """
    ).fetchall()
    phase_durations = conn.execute(
        """
        SELECT
            session_id,
            name AS phase,
            COALESCE(AVG(duration_ms), 0) AS avg_duration_ms,
            COUNT(*) AS events
        FROM telemetry_events
        WHERE category = 'phase'
        GROUP BY session_id, phase
        ORDER BY session_id, phase
        """
    ).fetchall()
    conn.close()

    return {
        "kpis": {
            "sessions": int(kpi_row[0]) if kpi_row else 0,
            "avg_time_ms": float(kpi_row[1]) if kpi_row else 0.0,
            "avg_tokens": float(kpi_row[2]) if kpi_row else 0.0,
            "avg_searches": float(kpi_row[3]) if kpi_row else 0.0,
            "avg_tool_calls": float(kpi_row[4]) if kpi_row else 0.0,
        },
        "sessions": sessions,
        "events": events,
        "agent_timeline": agent_timeline,
        "phase_durations": phase_durations,
    }


def query_session_detail(
    session_id: str,
    db_path: Path | None = None,
    *,
    cursor: int | None = None,
    before_cursor: int | None = None,
    limit: int = 1000,
    include_derived: bool = True,
) -> dict[str, Any]:
    """Return detailed telemetry datasets for a single session.

    Args:
        session_id: The session ID to query.
        db_path: Optional DuckDB database path.
        cursor: Sequence number to start after (forward pagination).
        before_cursor: Sequence number to end before (backward pagination).
        limit: Maximum events to return in paged slice.
        include_derived: Whether to include derived outputs.

    Returns:
        Dict with session info, events, and derived outputs.
    """
    database_path = db_path or get_default_dashboard_db_path()
    if not database_path.exists():
        return {
            "session": None,
            "events": [],
            "events_page": {"events": [], "total": 0, "has_more": False, "next_cursor": None, "prev_cursor": None},
            "phase_durations": [],
            "agent_events": [],
            "reasoning_events": [],
            "tool_calls": [],
            "llm_usage": [],
            "narrative": [],
            "critical_path": {},
            "state_changes": [],
            "decisions": [],
            "degradations": [],
            "failures": [],
        }

    conn = _load_dashboard_connection(database_path)
    session_row = conn.execute(
        """
        SELECT
            session_id,
            created_at,
            status,
            total_time_ms,
            total_sources,
            instances_spawned,
            search_queries,
            tool_calls,
            llm_prompt_tokens,
            llm_completion_tokens,
            llm_total_tokens,
            providers_json
        FROM telemetry_sessions
        WHERE session_id = ?
        """,
        [session_id],
    ).fetchone()
    events = conn.execute(
        """
        SELECT
            event_id,
            parent_event_id,
            sequence_number,
            timestamp,
            event_type,
            category,
            name,
            status,
            duration_ms,
            agent_id,
            metadata_json
        FROM telemetry_events
        WHERE session_id = ?
        ORDER BY sequence_number ASC, timestamp ASC NULLS LAST
        """,
        [session_id],
    ).fetchall()
    phase_durations = conn.execute(
        """
        SELECT
            name AS phase,
            COALESCE(AVG(duration_ms), 0) AS avg_duration_ms,
            COUNT(*) AS samples
        FROM telemetry_events
        WHERE session_id = ?
          AND event_type = 'operation.finished'
          AND category = 'phase'
          AND duration_ms IS NOT NULL
        GROUP BY phase
        ORDER BY avg_duration_ms DESC
        """,
        [session_id],
    ).fetchall()
    agent_events = conn.execute(
        """
        SELECT
            event_id,
            parent_event_id,
            sequence_number,
            timestamp,
            event_type,
            agent_id,
            name,
            status,
            duration_ms,
            metadata_json
        FROM telemetry_events
        WHERE session_id = ?
          AND category = 'agent'
        ORDER BY sequence_number ASC, timestamp ASC NULLS LAST
        """,
        [session_id],
    ).fetchall()
    reasoning_events = conn.execute(
        """
        SELECT
            event_id,
            parent_event_id,
            sequence_number,
            timestamp,
            name AS stage,
            metadata_json
        FROM telemetry_events
        WHERE session_id = ?
          AND event_type = 'reasoning.summary'
        ORDER BY sequence_number ASC, timestamp ASC NULLS LAST
        """,
        [session_id],
    ).fetchall()
    tool_calls = conn.execute(
        """
        SELECT
            event_id,
            parent_event_id,
            sequence_number,
            timestamp,
            name AS tool_name,
            status,
            duration_ms,
            agent_id,
            metadata_json
        FROM telemetry_events
        WHERE session_id = ?
          AND event_type = 'tool.call'
        ORDER BY sequence_number ASC, timestamp ASC NULLS LAST
        """,
        [session_id],
    ).fetchall()
    llm_usage = conn.execute(
        """
        SELECT
            event_id,
            parent_event_id,
            sequence_number,
            timestamp,
            name AS operation,
            duration_ms,
            metadata_json
        FROM telemetry_events
        WHERE session_id = ?
          AND event_type = 'llm.usage'
        ORDER BY sequence_number ASC, timestamp ASC NULLS LAST
        """,
        [session_id],
    ).fetchall()
    conn.close()

    # Normalize events to match live telemetry shape
    normalized_events = [_normalize_event_row(row) for row in events]

    # Build cursor-paginated events page
    events_page = _build_events_page(
        normalized_events,
        cursor=cursor,
        before_cursor=before_cursor,
        limit=limit,
    )

    # Build derived outputs using same builders as live
    derived = {}
    if include_derived:
        derived = build_derived_summary(normalized_events)

    # Normalize session row to be JSON-serializable
    normalized_session = None
    if session_row is not None:
        normalized_session = {
            "session_id": session_row[0],
            "created_at": _serialize_timestamp(session_row[1]),
            "status": session_row[2],
            "total_time_ms": session_row[3],
            "total_sources": session_row[4],
            "instances_spawned": session_row[5],
            "search_queries": session_row[6],
            "tool_calls": session_row[7],
            "llm_prompt_tokens": session_row[8],
            "llm_completion_tokens": session_row[9],
            "llm_total_tokens": session_row[10],
            "providers_json": session_row[11],
        }

    return {
        "session": normalized_session,
        "events": normalized_events,
        "events_page": events_page,
        "phase_durations": phase_durations,
        "agent_events": [_normalize_event_row(row) for row in agent_events],
        "reasoning_events": reasoning_events,
        "tool_calls": tool_calls,
        "llm_usage": llm_usage,
        # Derived outputs
        "narrative": derived.get("narrative", []),
        "critical_path": derived.get("critical_path", {}),
        "state_changes": derived.get("state_changes", []),
        "decisions": derived.get("decisions", []),
        "degradations": derived.get("degradations", []),
        "failures": derived.get("failures", []),
    }


def _serialize_timestamp(value: Any) -> str | None:
    """Serialize a timestamp value to ISO format string."""
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _build_events_page(
    events: list[dict[str, Any]],
    *,
    cursor: int | None = None,
    before_cursor: int | None = None,
    limit: int = 1000,
) -> dict[str, Any]:
    """Build a cursor-paginated slice of events.

    Args:
        events: All normalized events for the session.
        cursor: Sequence number to start after (forward pagination).
        before_cursor: Sequence number to end before (backward pagination).
        limit: Maximum events to return.

    Returns:
        Dict with events slice and pagination metadata.
    """
    total = len(events)

    if not events:
        return {
            "events": [],
            "total": 0,
            "has_more": False,
            "next_cursor": None,
            "prev_cursor": None,
        }

    # Get sequence numbers for cursor calculations
    first_seq = events[0].get("sequence_number", 0)
    last_seq = events[-1].get("sequence_number", total - 1)

    # Forward pagination: events after cursor
    if cursor is not None:
        start_idx = 0
        for i, event in enumerate(events):
            seq = event.get("sequence_number", i)
            if seq > cursor:
                start_idx = i
                break
        else:
            start_idx = len(events)

        sliced = events[start_idx:start_idx + limit]
    # Backward pagination: events before cursor
    elif before_cursor is not None:
        end_idx = len(events)
        for i in range(len(events) - 1, -1, -1):
            seq = events[i].get("sequence_number", i)
            if seq < before_cursor:
                end_idx = i + 1
                break
        else:
            end_idx = 0

        start_idx = max(0, end_idx - limit)
        sliced = events[start_idx:end_idx]
    # No cursor: return first page
    else:
        sliced = events[:limit]

    if not sliced:
        return {
            "events": [],
            "total": total,
            "has_more": False,
            "next_cursor": None,
            "prev_cursor": None,
        }

    # Calculate cursors for next/prev pages
    first_returned_seq = sliced[0].get("sequence_number", events.index(sliced[0]) if sliced[0] in events else 0)
    last_returned_seq = sliced[-1].get("sequence_number", events.index(sliced[-1]) if sliced[-1] in events else total - 1)

    has_more = last_returned_seq < last_seq
    has_prev = first_returned_seq > first_seq

    return {
        "events": sliced,
        "total": total,
        "has_more": has_more,
        "next_cursor": last_returned_seq if has_more else None,
        "prev_cursor": first_returned_seq - 1 if has_prev else None,
    }


def query_events_by_parent(
    session_id: str,
    parent_event_id: str | None,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Return child events for a given parent event ID."""
    database_path = db_path or get_default_dashboard_db_path()
    if not database_path.exists():
        return []

    conn = _load_dashboard_connection(database_path)
    if parent_event_id is None:
        rows = conn.execute(
            """
            SELECT
                event_id,
                parent_event_id,
                sequence_number,
                timestamp,
                event_type,
                category,
                name,
                status,
                duration_ms,
                agent_id,
                metadata_json
            FROM telemetry_events
            WHERE session_id = ?
              AND parent_event_id IS NULL
            ORDER BY sequence_number ASC
            """,
            [session_id],
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT
                event_id,
                parent_event_id,
                sequence_number,
                timestamp,
                event_type,
                category,
                name,
                status,
                duration_ms,
                agent_id,
                metadata_json
            FROM telemetry_events
            WHERE session_id = ?
              AND parent_event_id = ?
            ORDER BY sequence_number ASC
            """,
            [session_id, parent_event_id],
        ).fetchall()
    conn.close()

    events = [_normalize_event_row(row) for row in rows]
    if parent_event_id is None:
        return [event for event in events if not is_terminal_session_event(event)]
    return events


def query_event_tree(
    session_id: str,
    db_path: Path | None = None,
    max_depth: int = 10,
) -> dict[str, Any]:
    """Return a hierarchical event tree for a session."""
    from .tree import build_event_tree

    database_path = db_path or get_default_dashboard_db_path()
    if not database_path.exists():
        return {"root_events": [], "total_events": 0}

    detail = query_session_detail(session_id, database_path)
    # Events are now normalized dicts, so use build_event_tree instead of build_event_tree_from_rows
    tree = build_event_tree(detail["events"], max_depth=max_depth)
    tree["session_id"] = session_id
    return tree


def query_llm_route_analytics(
    session_id: str,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Return LLM route analytics from DuckDB for a session."""
    database_path = db_path or get_default_dashboard_db_path()
    if not database_path.exists():
        return build_llm_route_streams([])

    conn = _load_dashboard_connection(database_path)
    llm_events = conn.execute(
        """
        SELECT
            event_id,
            parent_event_id,
            sequence_number,
            timestamp,
            event_type,
            name,
            status,
            duration_ms,
            agent_id,
            metadata_json
        FROM telemetry_events
        WHERE session_id = ?
          AND category = 'llm'
          AND event_type IN ('llm.route_selected', 'llm.route_fallback',
                             'llm.route_request', 'llm.route_completion')
        ORDER BY sequence_number ASC, timestamp ASC NULLS LAST
        """,
        [session_id],
    ).fetchall()
    conn.close()

    events = [
        {
            "event_id": row[0],
            "parent_event_id": row[1],
            "sequence_number": row[2],
            "timestamp": row[3],
            "event_type": row[4],
            "name": row[5],
            "status": row[6],
            "duration_ms": row[7],
            "agent_id": row[8],
            "metadata": json.loads(row[9]) if row[9] else {},
        }
        for row in llm_events
    ]
    return build_llm_route_streams(events)


def query_llm_route_summary(
    session_id: str,
    *,
    base_dir: Path | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Return a summary of LLM route usage for a session."""
    telemetry_dir = base_dir or get_default_telemetry_dir()
    if (telemetry_dir / session_id).exists():
        return query_live_llm_route_analytics(session_id, base_dir=base_dir)
    return query_llm_route_analytics(session_id, db_path=db_path)


__all__ = [
    "query_dashboard_data",
    "query_event_tree",
    "query_events_by_parent",
    "query_llm_route_analytics",
    "query_llm_route_summary",
    "query_session_detail",
]
