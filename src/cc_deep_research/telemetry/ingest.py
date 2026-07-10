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
_INGEST_STATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS telemetry_ingest_state (
        session_id VARCHAR PRIMARY KEY,
        events_offset BIGINT NOT NULL DEFAULT 0,
        events_size BIGINT NOT NULL DEFAULT 0,
        events_mtime_ns BIGINT NOT NULL DEFAULT 0,
        summary_size BIGINT NOT NULL DEFAULT 0,
        summary_mtime_ns BIGINT NOT NULL DEFAULT 0
    )
"""


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


def _ingest_state(conn: Any, session_id: str) -> tuple[int, int, int, int, int] | None:
    """Return the persisted incremental-ingest cursor for one session."""
    row = conn.execute(
        """
        SELECT events_offset, events_size, events_mtime_ns,
               summary_size, summary_mtime_ns
        FROM telemetry_ingest_state
        WHERE session_id = ?
        """,
        [session_id],
    ).fetchone()
    if row is None:
        return None
    return tuple(int(value or 0) for value in row)  # type: ignore[return-value]


def _ingest_event_rows(
    conn: Any,
    events_file: Path,
    session_id: str,
    *,
    start_offset: int,
) -> tuple[int, int]:
    """Read complete JSONL records after ``start_offset``.

    The returned offset never advances beyond an incomplete trailing line, so
    a concurrent writer can safely finish that line before the next refresh.
    """
    rows: list[tuple[Any, ...]] = []
    inserted = 0
    committed_offset = start_offset
    with open(events_file, "rb") as handle:
        handle.seek(start_offset)
        while raw_line := handle.readline():
            if not raw_line.endswith(b"\n"):
                break
            committed_offset = handle.tell()
            stripped = raw_line.strip()
            if not stripped:
                continue
            raw_event = json.loads(stripped.decode("utf-8"))
            event = migrate_event_record(raw_event)
            rows.append(_event_insert_row(event, session_id))
            if len(rows) >= _EVENT_INSERT_BATCH_SIZE:
                inserted += _flush_event_rows(conn, rows)
    inserted += _flush_event_rows(conn, rows)
    return inserted, committed_offset


def _write_ingest_state(
    conn: Any,
    session_id: str,
    *,
    events_offset: int,
    events_size: int,
    events_mtime_ns: int,
    summary_size: int,
    summary_mtime_ns: int,
) -> None:
    """Commit one session's source fingerprints and JSONL cursor."""
    conn.execute(
        """
        INSERT OR REPLACE INTO telemetry_ingest_state
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        [
            session_id,
            events_offset,
            events_size,
            events_mtime_ns,
            summary_size,
            summary_mtime_ns,
        ],
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
    conn.execute(_INGEST_STATE_TABLE_SQL)
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
        state = _ingest_state(conn, session_id)
        previous_offset, previous_size, previous_mtime, previous_summary_size, previous_summary_mtime = (
            state or (0, 0, 0, 0, 0)
        )

        events_stat = events_file.stat() if events_file.exists() else None
        summary_stat = summary_file.stat() if summary_file.exists() else None
        events_size = events_stat.st_size if events_stat else 0
        events_mtime_ns = events_stat.st_mtime_ns if events_stat else 0
        summary_size = summary_stat.st_size if summary_stat else 0
        summary_mtime_ns = summary_stat.st_mtime_ns if summary_stat else 0

        events_changed = (
            state is None
            or events_size != previous_size
            or events_mtime_ns != previous_mtime
        )
        summary_changed = (
            state is None
            or summary_size != previous_summary_size
            or summary_mtime_ns != previous_summary_mtime
        )
        if not events_changed and not summary_changed:
            continue

        # A file that shrank or changed without growing was replaced/rewritten;
        # rebuild only that session. A strictly larger file is append-only.
        rebuild_events = (
            state is None
            or events_size < previous_offset
            or (events_size <= previous_size and events_mtime_ns != previous_mtime)
        )
        start_offset = 0 if rebuild_events else previous_offset
        committed_offset = start_offset

        conn.execute("BEGIN TRANSACTION")
        try:
            if events_changed:
                if rebuild_events:
                    conn.execute(
                        "DELETE FROM telemetry_events WHERE session_id = ?",
                        [session_id],
                    )
                if events_stat is not None:
                    inserted, committed_offset = _ingest_event_rows(
                        conn,
                        events_file,
                        session_id,
                        start_offset=start_offset,
                    )
                    ingested_events += inserted

            if summary_changed:
                conn.execute(
                    "DELETE FROM telemetry_sessions WHERE session_id = ?",
                    [session_id],
                )
                if summary_stat is not None:
                    with open(summary_file, encoding="utf-8") as handle:
                        summary = json.load(handle)
                    conn.execute(
                        """
                        INSERT INTO telemetry_sessions
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

            _write_ingest_state(
                conn,
                session_id,
                events_offset=committed_offset,
                events_size=events_size,
                events_mtime_ns=events_mtime_ns,
                summary_size=summary_size,
                summary_mtime_ns=summary_mtime_ns,
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    for index_sql in [*_EVENT_INDEX_SQL, *_SESSION_INDEX_SQL]:
        conn.execute(index_sql)

    conn.close()
    return {"sessions": ingested_sessions, "events": ingested_events}


__all__ = [
    "delete_session_from_duckdb",
    "get_default_dashboard_db_path",
    "ingest_telemetry_to_duckdb",
]
