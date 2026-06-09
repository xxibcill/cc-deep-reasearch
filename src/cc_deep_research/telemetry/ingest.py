"""DuckDB ingestion helpers for persisted telemetry analytics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from cc_deep_research.config import get_default_config_path

from .live import get_default_telemetry_dir
from .migrations import (
    CURRENT_DUCKDB_SCHEMA_VERSION,
    DUCKDB_SCHEMA_VERSION_KEY,
    migrate_event_record,
)

if TYPE_CHECKING:
    pass

_DASHBOARD_INSTALL_COMMAND = 'pip install "inqulume-studio[dashboard]"'
_EVENT_INSERT_BATCH_SIZE = 1000
_EVENT_INSERT_SQL = """
    INSERT INTO telemetry_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""
_EVENT_INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_events_session_id ON telemetry_events(session_id)",
    "CREATE INDEX IF NOT EXISTS idx_events_timestamp ON telemetry_events(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_events_event_type ON telemetry_events(event_type)",
    "CREATE INDEX IF NOT EXISTS idx_events_category ON telemetry_events(category)",
    "CREATE INDEX IF NOT EXISTS idx_events_session_seq ON telemetry_events(session_id, sequence_number)",
]
_SESSION_INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON telemetry_sessions(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_sessions_status ON telemetry_sessions(status)",
    "CREATE INDEX IF NOT EXISTS idx_sessions_total_time ON telemetry_sessions(total_time_ms)",
]


def _event_insert_row(event: dict[str, Any], session_id: str) -> tuple[Any, ...]:
    """Convert a migrated event record into the DuckDB event table row shape."""
    return (
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
    )


def _flush_event_rows(conn: Any, rows: list[tuple[Any, ...]]) -> int:
    """Insert accumulated event rows in one DuckDB round trip."""
    if not rows:
        return 0
    conn.executemany(_EVENT_INSERT_SQL, rows)
    inserted = len(rows)
    rows.clear()
    return inserted


def _ensure_metadata_table(conn: Any) -> None:
    """Create the metadata table if it does not exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS telemetry_metadata (
            key VARCHAR PRIMARY KEY,
            value VARCHAR
        )
        """
    )


def _apply_schema_migration(conn: Any) -> None:
    """Apply DuckDB schema migrations if needed.

    Checks the installed schema version and writes the current version marker
    after ensuring the metadata table exists.
    """
    try:
        result = conn.execute(
            "SELECT value FROM telemetry_metadata WHERE key = ?",
            [DUCKDB_SCHEMA_VERSION_KEY],
        ).fetchone()
        current_version = int(result[0]) if result else 0
    except Exception:
        current_version = 0

    if current_version < CURRENT_DUCKDB_SCHEMA_VERSION:
        conn.execute(
            "INSERT OR REPLACE INTO telemetry_metadata (key, value) VALUES (?, ?)",
            [DUCKDB_SCHEMA_VERSION_KEY, str(CURRENT_DUCKDB_SCHEMA_VERSION)],
        )


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

    # Ensure metadata table and apply any needed schema migrations
    _ensure_metadata_table(conn)
    _apply_schema_migration(conn)

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
            event_rows: list[tuple[Any, ...]] = []
            with open(events_file, encoding="utf-8") as handle:
                for line in handle:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    raw_event = json.loads(stripped)
                    event = migrate_event_record(raw_event)
                    event_rows.append(_event_insert_row(event, session_id))
                    if len(event_rows) >= _EVENT_INSERT_BATCH_SIZE:
                        ingested_events += _flush_event_rows(conn, event_rows)
            ingested_events += _flush_event_rows(conn, event_rows)

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

    for index_sql in [*_EVENT_INDEX_SQL, *_SESSION_INDEX_SQL]:
        conn.execute(index_sql)

    conn.close()
    return {"sessions": ingested_sessions, "events": ingested_events}


__all__ = [
    "delete_session_from_duckdb",
    "get_default_dashboard_db_path",
    "ingest_telemetry_to_duckdb",
]
