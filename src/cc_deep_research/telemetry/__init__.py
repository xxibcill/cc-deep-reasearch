"""Telemetry ingestion and analytics utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cc_deep_research.config import get_default_config_path

from .live import (
    get_default_telemetry_dir,
    query_live_agent_timeline,
    query_live_event_tail,
    query_live_event_tree,
    query_live_llm_route_analytics,
    query_live_session_detail,
    query_live_sessions,
    query_live_subprocess_streams,
)
from .tree import build_event_tree_from_rows, build_llm_route_streams, is_terminal_session_event

_DASHBOARD_INSTALL_COMMAND = 'pip install "cc-deep-research[dashboard]"'


def get_default_dashboard_db_path() -> Path:
    """Return default DuckDB path for telemetry analytics."""
    return get_default_config_path().parent / "telemetry.duckdb"


def _missing_dashboard_dependency_message(feature: str) -> str:
    """Return a consistent install hint for optional analytics dependencies."""
    return (
        f"{feature} requires optional dashboard dependencies. "
        f"Install with `{_DASHBOARD_INSTALL_COMMAND}`."
    )


def ingest_telemetry_to_duckdb(
    base_dir: Path | None = None,
    db_path: Path | None = None,
) -> dict[str, int]:
    """Ingest JSONL telemetry sessions into DuckDB tables."""
    telemetry_dir = base_dir or get_default_telemetry_dir()
    database_path = db_path or get_default_dashboard_db_path()

    if not telemetry_dir.exists():
        return {"sessions": 0, "events": 0}

    try:
        import duckdb
    except ImportError as exc:  # pragma: no cover - import guard
        raise RuntimeError(_missing_dashboard_dependency_message("Telemetry ingestion")) from exc

    database_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(database_path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS telemetry_events (
            event_id VARCHAR,
            parent_event_id VARCHAR,
            sequence_number INTEGER,
            session_id VARCHAR,
            timestamp TIMESTAMP,
            event_type VARCHAR,
            category VARCHAR,
            name VARCHAR,
            status VARCHAR,
            duration_ms INTEGER,
            agent_id VARCHAR,
            metadata_json VARCHAR
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS telemetry_sessions (
            session_id VARCHAR PRIMARY KEY,
            status VARCHAR,
            total_sources INTEGER,
            total_time_ms INTEGER,
            instances_spawned INTEGER,
            search_queries INTEGER,
            tool_calls INTEGER,
            llm_prompt_tokens INTEGER,
            llm_completion_tokens INTEGER,
            llm_total_tokens INTEGER,
            providers_json VARCHAR,
            created_at TIMESTAMP,
            summary_json VARCHAR
        )
        """
    )

    ingested_sessions = 0
    ingested_events = 0

    for session_dir in sorted(path for path in telemetry_dir.iterdir() if path.is_dir()):
        session_id = session_dir.name
        events_file = session_dir / "events.jsonl"
        summary_file = session_dir / "summary.json"

        if events_file.exists():
            conn.execute("DELETE FROM telemetry_events WHERE session_id = ?", [session_id])
            with open(events_file, encoding="utf-8") as handle:
                for line in handle:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    event = json.loads(stripped)
                    conn.execute(
                        """
                        INSERT INTO telemetry_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        [
                            event.get("event_id"),
                            event.get("parent_event_id"),
                            event.get("sequence_number"),
                            event.get("session_id") or session_id,
                            event.get("timestamp"),
                            event.get("event_type"),
                            event.get("category"),
                            event.get("name"),
                            event.get("status"),
                            event.get("duration_ms"),
                            event.get("agent_id"),
                            json.dumps(event.get("metadata", {}), ensure_ascii=True),
                        ],
                    )
                    ingested_events += 1

        if summary_file.exists():
            with open(summary_file, encoding="utf-8") as handle:
                summary = json.load(handle)
            conn.execute("DELETE FROM telemetry_sessions WHERE session_id = ?", [session_id])
            conn.execute(
                """
                INSERT INTO telemetry_sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    summary.get("session_id") or session_id,
                    summary.get("status", "completed"),
                    summary.get("total_sources", 0),
                    summary.get("total_time_ms", 0),
                    summary.get("instances_spawned", 0),
                    summary.get("search_queries", 0),
                    summary.get("tool_calls", 0),
                    summary.get("llm_prompt_tokens", 0),
                    summary.get("llm_completion_tokens", 0),
                    summary.get("llm_total_tokens", 0),
                    json.dumps(summary.get("providers", []), ensure_ascii=True),
                    summary.get("created_at"),
                    json.dumps(summary, ensure_ascii=True),
                ],
            )
            ingested_sessions += 1

    conn.close()
    return {"sessions": ingested_sessions, "events": ingested_events}


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

    try:
        import duckdb
    except ImportError as exc:  # pragma: no cover - import guard
        raise RuntimeError(_missing_dashboard_dependency_message("Dashboard queries")) from exc

    conn = duckdb.connect(str(database_path), read_only=True)
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

    try:
        import duckdb
    except ImportError as exc:  # pragma: no cover - import guard
        raise RuntimeError(_missing_dashboard_dependency_message("Dashboard queries")) from exc

    conn = duckdb.connect(str(database_path), read_only=True)
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

    try:
        import duckdb
    except ImportError as exc:  # pragma: no cover - import guard
        raise RuntimeError(_missing_dashboard_dependency_message("Dashboard queries")) from exc

    conn = duckdb.connect(str(database_path), read_only=True)
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

    events = [
        {
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
        for row in rows
    ]
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

    try:
        import duckdb
    except ImportError as exc:  # pragma: no cover - import guard
        raise RuntimeError(_missing_dashboard_dependency_message("LLM route analytics")) from exc

    conn = duckdb.connect(str(database_path), read_only=True)
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
    "get_default_dashboard_db_path",
    "get_default_telemetry_dir",
    "ingest_telemetry_to_duckdb",
    "query_dashboard_data",
    "query_event_tree",
    "query_events_by_parent",
    "query_live_agent_timeline",
    "query_live_event_tail",
    "query_live_event_tree",
    "query_live_llm_route_analytics",
    "query_live_session_detail",
    "query_live_sessions",
    "query_live_subprocess_streams",
    "query_llm_route_analytics",
    "query_llm_route_summary",
    "query_session_detail",
]
