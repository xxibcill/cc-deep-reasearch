"""Telemetry ingestion and analytics utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cc_deep_research.config import get_default_config_path


def get_default_telemetry_dir() -> Path:
    """Return default telemetry directory."""
    return get_default_config_path().parent / "telemetry"


def get_default_dashboard_db_path() -> Path:
    """Return default DuckDB path for telemetry analytics."""
    return get_default_config_path().parent / "telemetry.duckdb"


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
        raise RuntimeError(
            "duckdb is required for telemetry ingestion. Install with `pip install duckdb`."
        ) from exc

    database_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(database_path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS telemetry_events (
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

    for session_dir in sorted(p for p in telemetry_dir.iterdir() if p.is_dir()):
        session_id = session_dir.name
        events_file = session_dir / "events.jsonl"
        summary_file = session_dir / "summary.json"

        if events_file.exists():
            conn.execute("DELETE FROM telemetry_events WHERE session_id = ?", [session_id])
            with open(events_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    event = json.loads(line)
                    conn.execute(
                        """
                        INSERT INTO telemetry_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        [
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
            with open(summary_file, encoding="utf-8") as f:
                summary = json.load(f)
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
        raise RuntimeError(
            "duckdb is required for dashboard queries. Install with `pip install duckdb`."
        ) from exc

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
        ORDER BY timestamp DESC NULLS LAST
        LIMIT 2000
        """
    ).fetchall()

    agent_timeline = conn.execute(
        """
        SELECT
            session_id,
            agent_id,
            event_type,
            name,
            status,
            duration_ms,
            timestamp
        FROM telemetry_events
        WHERE category = 'agent' AND agent_id IS NOT NULL
        ORDER BY timestamp DESC NULLS LAST
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
        raise RuntimeError(
            "duckdb is required for dashboard queries. Install with `pip install duckdb`."
        ) from exc

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
        ORDER BY timestamp ASC NULLS LAST
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
        ORDER BY timestamp ASC NULLS LAST
        """,
        [session_id],
    ).fetchall()

    reasoning_events = conn.execute(
        """
        SELECT
            timestamp,
            name AS stage,
            metadata_json
        FROM telemetry_events
        WHERE session_id = ?
          AND event_type = 'reasoning.summary'
        ORDER BY timestamp ASC NULLS LAST
        """,
        [session_id],
    ).fetchall()

    tool_calls = conn.execute(
        """
        SELECT
            timestamp,
            name AS tool_name,
            status,
            duration_ms,
            agent_id,
            metadata_json
        FROM telemetry_events
        WHERE session_id = ?
          AND event_type = 'tool.call'
        ORDER BY timestamp ASC NULLS LAST
        """,
        [session_id],
    ).fetchall()

    llm_usage = conn.execute(
        """
        SELECT
            timestamp,
            name AS operation,
            duration_ms,
            metadata_json
        FROM telemetry_events
        WHERE session_id = ?
          AND event_type = 'llm.usage'
        ORDER BY timestamp ASC NULLS LAST
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


__all__ = [
    "get_default_dashboard_db_path",
    "get_default_telemetry_dir",
    "ingest_telemetry_to_duckdb",
    "query_dashboard_data",
    "query_session_detail",
]
