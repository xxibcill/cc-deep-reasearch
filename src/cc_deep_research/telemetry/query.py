"""DuckDB-backed analytics queries for persisted telemetry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .ingest import _missing_dashboard_dependency_message, get_default_dashboard_db_path
from .live import get_default_telemetry_dir, query_live_llm_route_analytics
from .tree import build_event_tree_from_rows, build_llm_route_streams, is_terminal_session_event


def _load_dashboard_connection(database_path: Path):
    """Open a read-only DuckDB connection or raise a consistent dependency error."""
    try:
        import duckdb
    except ImportError as exc:  # pragma: no cover - import guard
        raise RuntimeError(_missing_dashboard_dependency_message("Dashboard queries")) from exc

    return duckdb.connect(str(database_path), read_only=True)


def _normalize_event_row(row: tuple[Any, ...]) -> dict[str, Any]:
    """Convert a DuckDB event row into the public event payload shape."""
    return {
        "event_id": row[0],
        "parent_event_id": row[1],
        "sequence_number": row[2],
        "timestamp": row[3],
        "event_type": row[4],
        "category": row[5],
        "name": row[6],
        "status": row[7],
        "duration_ms": row[8],
        "agent_id": row[9],
        "metadata": json.loads(row[10]) if row[10] else {},
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
) -> dict[str, Any]:
    """Return detailed telemetry datasets for a single session."""
    database_path = db_path or get_default_dashboard_db_path()
    if not database_path.exists():
        return {
            "session": None,
            "events": [],
            "phase_durations": [],
            "agent_events": [],
            "reasoning_events": [],
            "tool_calls": [],
            "llm_usage": [],
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

    return {
        "session": session_row,
        "events": events,
        "phase_durations": phase_durations,
        "agent_events": agent_events,
        "reasoning_events": reasoning_events,
        "tool_calls": tool_calls,
        "llm_usage": llm_usage,
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
    database_path = db_path or get_default_dashboard_db_path()
    if not database_path.exists():
        return {"root_events": [], "total_events": 0}

    detail = query_session_detail(session_id, database_path)
    return build_event_tree_from_rows(detail["events"], session_id=session_id, max_depth=max_depth)


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
