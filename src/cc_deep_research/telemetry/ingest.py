"""DuckDB ingestion helpers for persisted telemetry analytics."""

from __future__ import annotations

import json
from pathlib import Path

from cc_deep_research.config import get_default_config_path

from .live import get_default_telemetry_dir

_DASHBOARD_INSTALL_COMMAND = 'pip install "cc-deep-research[dashboard]"'


def get_default_dashboard_db_path() -> Path:
    """Return the default DuckDB path for telemetry analytics."""
    return get_default_config_path().parent / "telemetry.duckdb"


def _missing_dashboard_dependency_message(feature: str) -> str:
    """Return a consistent install hint for optional analytics dependencies."""
    return (
        f"{feature} requires optional dashboard dependencies. "
        f"Install with `{_DASHBOARD_INSTALL_COMMAND}`."
    )


def delete_session_from_duckdb(
    session_id: str,
    db_path: Path | None = None,
) -> dict[str, bool]:
    """Delete a session's telemetry data from DuckDB.

    Args:
        session_id: The session ID to delete.
        db_path: Optional path to DuckDB database.

    Returns:
        Dict with 'deleted' (bool) and 'missing' (bool) indicating results.
    """
    database_path = db_path or get_default_dashboard_db_path()

    if not database_path.exists():
        return {"deleted": False, "missing": True}

    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError(
            _missing_dashboard_dependency_message("Delete session from DuckDB")
        ) from exc

    try:
        conn = duckdb.connect(str(database_path))
        try:
            conn.execute(
                "DELETE FROM telemetry_events WHERE session_id = ?",
                [session_id],
            )
            conn.execute(
                "DELETE FROM telemetry_sessions WHERE session_id = ?",
                [session_id],
            )
            return {"deleted": True, "missing": False}
        finally:
            conn.close()
    except Exception:
        return {"deleted": False, "missing": False}


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


__all__ = [
    "delete_session_from_duckdb",
    "get_default_dashboard_db_path",
    "ingest_telemetry_to_duckdb",
]
