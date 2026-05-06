"""Telemetry schema migrations for backward compatibility.

Covers migration paths for:
- DuckDB telemetry table schemas (telemetry_events, telemetry_sessions)
- JSONL event formats with legacy field names/structure
- Trace bundle exports (BUNDLE_SCHEMA_VERSION)

The migration system uses schema version tracking to determine whether
migration is needed. DuckDB databases store a schema_version marker so
subsequent ingest calls can detect when upgrade is required.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Schema Versions
# ---------------------------------------------------------------------------

# DuckDB telemetry table schema version.
# Increment when adding columns or changing types in telemetry_events/telemetry_sessions.
CURRENT_DUCKDB_SCHEMA_VERSION = 1
DUCKDB_SCHEMA_VERSION_KEY = "telemetry_schema_version"

# JSONL event format schema version.
# Increment when changing the normalized event shape returned by _normalize_live_event().
CURRENT_EVENT_SCHEMA_VERSION = 1
EVENT_SCHEMA_VERSION_KEY = "event_schema_version"

# Bundle format schema version (tracks BUNDLE_SCHEMA_VERSION from bundle.py).
CURRENT_BUNDLE_SCHEMA_VERSION = "1.2.0"
BUNDLE_SCHEMA_VERSION_KEY = "schema_version"


class MigrationScope(IntEnum):
    """Scopes for targeted migration runs."""

    ALL = 0
    DUCKDB = 1
    EVENTS = 2
    BUNDLE = 3


# ---------------------------------------------------------------------------
# DuckDB Schema Migration
# ---------------------------------------------------------------------------


def _get_duckdb_schema_version(conn: Any) -> int:
    """Read the current DuckDB schema version from the metadata table.

    Returns 0 if the metadata table or version row does not exist
    (meaning the database was created before schema versioning).
    """
    try:
        result = conn.execute(
            "SELECT value FROM telemetry_metadata WHERE key = ?",
            [DUCKDB_SCHEMA_VERSION_KEY],
        ).fetchone()
        if result is not None:
            return int(result[0])
    except Exception:
        pass
    return 0


def _write_duckdb_schema_version(conn: Any, version: int) -> None:
    """Write the current schema version to the metadata table."""
    conn.execute(
        "INSERT OR REPLACE INTO telemetry_metadata (key, value) VALUES (?, ?)",
        [DUCKDB_SCHEMA_VERSION_KEY, str(version)],
    )


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


def _migrate_duckdb_schema_v0_to_v1(conn: Any) -> None:
    """Migrate from schema v0 (pre-versioning) to v1.

    v0: No schema_version tracking, tables created without version markers.
    v1: Adds telemetry_metadata table and schema_version tracking.
         No structural table changes — the v1 milestone is the versioning itself.
    """
    _ensure_metadata_table(conn)
    _write_duckdb_schema_version(conn, CURRENT_DUCKDB_SCHEMA_VERSION)


def migrate_duckdb_schema(db_path: Path) -> dict[str, Any]:
    """Migrate the DuckDB telemetry database to the current schema version.

    Detects the installed schema version and applies sequential migrations
    up to CURRENT_DUCKDB_SCHEMA_VERSION.

    Args:
        db_path: Path to the DuckDB database file.

    Returns:
        Dict with 'upgraded' (bool), 'from_version', 'to_version', and 'errors'.
    """
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError(
            "DuckDB is required for schema migration. "
            'Install with `pip install "cc-deep-research[dashboard]"`.'
        ) from exc

    if not db_path.exists():
        return {"upgraded": False, "from_version": 0, "to_version": CURRENT_DUCKDB_SCHEMA_VERSION, "errors": ["Database does not exist"]}

    conn = duckdb.connect(str(db_path))
    try:
        _ensure_metadata_table(conn)
        current = _get_duckdb_schema_version(conn)

        if current >= CURRENT_DUCKDB_SCHEMA_VERSION:
            return {"upgraded": False, "from_version": current, "to_version": CURRENT_DUCKDB_SCHEMA_VERSION, "errors": []}

        migrations: list[tuple[str, Callable[[], None]]] = [
            ("0_to_1", lambda: _migrate_duckdb_schema_v0_to_v1(conn)),
        ]

        for label, migrate_fn in migrations:
            ver = int(label.split("_")[0])
            if ver < current:
                continue
            migrate_fn()

        final_version = _get_duckdb_schema_version(conn)
        return {
            "upgraded": final_version > current,
            "from_version": current,
            "to_version": final_version,
            "errors": [],
        }
    except Exception as e:
        return {"upgraded": False, "from_version": -1, "to_version": CURRENT_DUCKDB_SCHEMA_VERSION, "errors": [str(e)]}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Event Format Migration
# ---------------------------------------------------------------------------

# Legacy event field name mappings.
# Old name -> new name. Events with old names are renamed during normalization.
_FIELD_RENAME_MAP: dict[str, str] = {
    "eventName": "event_type",
    "event_type": "event_type",  # identity, no change needed
    "type": "category",
    "category": "category",  # identity
    "msg": "name",
    "name": "name",  # identity
    "sessionId": "session_id",
    "session_id": "session_id",  # identity
    "seq": "sequence_number",
    "sequence": "sequence_number",
    "time": "timestamp",
    "timestamp": "timestamp",  # identity
    "parentId": "parent_event_id",
    "parent_id": "parent_event_id",
    "parentEventId": "parent_event_id",
    "agentId": "agent_id",
    "agent_id": "agent_id",  # identity
    "status": "status",  # identity
    "duration": "duration_ms",
    "duration_ms": "duration_ms",  # identity
    "metadata": "metadata",  # identity
}


def migrate_event_record(event: dict[str, Any]) -> dict[str, Any]:
    """Apply all migration transforms to a single event record.

    Transforms applied in order:
    1. Field renames (old names -> current names)
    2. Metadata type coercion (non-dict -> {})
    3. Required field injection (fill in missing trace contract fields)

    Args:
        event: Raw event dict, possibly from a legacy format.

    Returns:
        Migrated event record with current field names and shapes.
    """
    # Step 1: Rename legacy field names
    migrated: dict[str, Any] = {}
    for old_name, new_name in _FIELD_RENAME_MAP.items():
        if old_name in event:
            migrated[new_name] = event[old_name]

    # Copy remaining fields not in the rename map
    for key, value in event.items():
        if key not in _FIELD_RENAME_MAP:
            migrated[key] = value

    # Step 2: Metadata type coercion
    metadata = migrated.get("metadata", {})
    if not isinstance(metadata, dict):
        migrated["metadata"] = {}

    # Step 3: Ensure required fields exist
    if "event_id" not in migrated or migrated["event_id"] is None:
        # Will be filled by caller with fallback_sequence
        pass

    return migrated


def migrate_events_file(events_file: Path, session_id: str) -> list[dict[str, Any]]:
    """Read a JSONL events file and return a list of fully migrated event records.

    Each event is normalized using migrate_event_record(), then augmented with
    sequence numbers (fallback to line index) and event_id values.

    Args:
        events_file: Path to the events.jsonl file.
        session_id: Session ID for fallback event_id generation.

    Returns:
        List of migrated event dicts in ingestion-ready shape.
    """
    migrated_events: list[dict[str, Any]] = []
    with open(events_file, encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            raw = json.loads(stripped)
            event = migrate_event_record(raw)
            # Fill in sequence_number from line index if missing
            if "sequence_number" not in event or event["sequence_number"] is None:
                event["sequence_number"] = idx
            # Generate event_id if missing
            if not event.get("event_id"):
                event["event_id"] = f"{session_id}-event-{idx}"
            migrated_events.append(event)
    return migrated_events


# ---------------------------------------------------------------------------
# Bundle Format Migration
# ---------------------------------------------------------------------------

# Known older bundle schema versions and their migration functions.
# Each entry describes the transformation needed to go from that version to the next.
_BUNDLE_MIGRATIONS: dict[str, dict[str, Any]] = {
    "1.0.0": {
        "next": "1.1.0",
        "transforms": ["rename_eventName_to_event_type", "normalize_metadata"],
    },
    "1.1.0": {
        "next": "1.2.0",
        "transforms": ["add_trace_version", "normalize_severity"],
    },
}


def _migrate_bundle_v1_0_0(bundle: dict[str, Any]) -> dict[str, Any]:
    """Migrate a v1.0.0 bundle to v1.1.0."""
    migrated = dict(bundle)
    migrated["schema_version"] = "1.1.0"

    # Rename eventName -> event_type in all events
    if "events" in migrated and isinstance(migrated["events"], list):
        migrated_events = []
        for event in migrated["events"]:
            e = dict(event)
            if "eventName" in e:
                e["event_type"] = e.pop("eventName")
            migrated_events.append(e)
        migrated["events"] = migrated_events

    # Normalize metadata types
    if "events" in migrated and isinstance(migrated["events"], list):
        migrated_events = []
        for event in migrated["events"]:
            e = dict(event)
            if "metadata" in e and not isinstance(e["metadata"], dict):
                e["metadata"] = {}
            migrated_events.append(e)
        migrated["events"] = migrated_events

    return migrated


def _migrate_bundle_v1_1_0(bundle: dict[str, Any]) -> dict[str, Any]:
    """Migrate a v1.1.0 bundle to v1.2.0."""
    migrated = dict(bundle)
    migrated["schema_version"] = "1.2.0"

    # Add trace_version field to events
    if "events" in migrated and isinstance(migrated["events"], list):
        migrated_events = []
        for event in migrated["events"]:
            e = dict(event)
            if "trace_version" not in e:
                e["trace_version"] = "0"
            # Normalize severity field
            status = e.get("status", "")
            if status in ("failed", "error", "critical"):
                e["severity"] = "error"
            elif status in ("fallback", "degraded", "warning"):
                e["severity"] = "warning"
            else:
                e["severity"] = "info"
            migrated_events.append(e)
        migrated["events"] = migrated_events

    return migrated


_BUNDLE_MIGRATION_FUNCTIONS: dict[str, Any] = {
    "1.0.0": _migrate_bundle_v1_0_0,
    "1.1.0": _migrate_bundle_v1_1_0,
}


def migrate_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    """Migrate a trace bundle to the current schema version.

    Applies sequential migrations from the bundle's current schema_version
    up to CURRENT_BUNDLE_SCHEMA_VERSION.

    Args:
        bundle: Trace bundle dict with a "schema_version" key.

    Returns:
        Migrated bundle dict.
    """
    current_version = bundle.get("schema_version", "0.0.0")
    if current_version == CURRENT_BUNDLE_SCHEMA_VERSION:
        return bundle

    migrated = dict(bundle)
    while current_version != CURRENT_BUNDLE_SCHEMA_VERSION:
        migrate_fn = _BUNDLE_MIGRATION_FUNCTIONS.get(current_version)
        if migrate_fn is None:
            break
        migrated = migrate_fn(migrated)
        current_version = migrated.get("schema_version", current_version)

    return migrated


# ---------------------------------------------------------------------------
# Unified Migration Entry Point
# ---------------------------------------------------------------------------


@dataclass
class MigrationReport:
    """Result of a migration run."""

    upgraded: bool
    duckdb_version: int | None
    events_migrated: int
    bundle_version: str | None
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "upgraded": self.upgraded,
            "duckdb_version": self.duckdb_version,
            "events_migrated": self.events_migrated,
            "bundle_version": self.bundle_version,
            "errors": self.errors,
        }


def get_default_dashboard_db_path() -> Path:
    """Return the default DuckDB path for telemetry analytics."""
    from cc_deep_research.config import get_default_config_path
    return get_default_config_path().parent / "telemetry.duckdb"


def migrate_session(
    session_id: str,
    base_dir: Path | None = None,
    *,
    scope: MigrationScope = MigrationScope.ALL,
    db_path: Path | None = None,
) -> MigrationReport:
    """Run all migrations for a session.

    Args:
        session_id: The session ID to migrate.
        base_dir: Optional telemetry base directory.
        scope: Which migration scopes to run (ALL, DUCKDB, EVENTS, BUNDLE).
        db_path: Optional explicit DuckDB path.

    Returns:
        MigrationReport with per-scope results.
    """
    from cc_deep_research.telemetry.live import get_default_telemetry_dir

    telemetry_dir = base_dir or get_default_telemetry_dir()
    session_dir = telemetry_dir / session_id
    events_file = session_dir / "events.jsonl"
    bundle_file = session_dir / "bundle.json"

    errors: list[str] = []
    duckdb_version: int | None = None
    events_migrated = 0
    bundle_version: str | None = None
    upgraded = False

    # DuckDB migration
    if scope in (MigrationScope.ALL, MigrationScope.DUCKDB):
        database_path = db_path or get_default_dashboard_db_path()
        if database_path.exists():
            try:
                result = migrate_duckdb_schema(database_path)
                if result["errors"]:
                    errors.extend(result["errors"])
                duckdb_version = result["to_version"]
                upgraded = upgraded or result["upgraded"]
            except Exception as e:
                errors.append(f"DuckDB migration failed: {e}")

    # Events file migration
    if scope in (MigrationScope.ALL, MigrationScope.EVENTS):
        if events_file.exists():
            try:
                migrated = migrate_events_file(events_file, session_id)
                events_migrated = len(migrated)
                upgraded = True
            except Exception as e:
                errors.append(f"Events migration failed: {e}")

    # Bundle migration
    if scope in (MigrationScope.ALL, MigrationScope.BUNDLE):
        if bundle_file.exists():
            try:
                bundle = json.loads(bundle_file.read_text(encoding="utf-8"))
                migrated_bundle = migrate_bundle(bundle)
                bundle_version = migrated_bundle.get("schema_version")
                if bundle_version != bundle.get("schema_version"):
                    upgraded = True
            except Exception as e:
                errors.append(f"Bundle migration failed: {e}")

    return MigrationReport(
        upgraded=upgraded,
        duckdb_version=duckdb_version,
        events_migrated=events_migrated,
        bundle_version=bundle_version,
        errors=errors,
    )


__all__ = [
    "CURRENT_BUNDLE_SCHEMA_VERSION",
    "CURRENT_DUCKDB_SCHEMA_VERSION",
    "CURRENT_EVENT_SCHEMA_VERSION",
    "MigrationReport",
    "MigrationScope",
    "migrate_bundle",
    "migrate_duckdb_schema",
    "migrate_event_record",
    "migrate_events_file",
    "migrate_session",
]
