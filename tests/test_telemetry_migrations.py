"""Migration tests for telemetry schema backward compatibility.

Tests cover:
- DuckDB schema versioning and migration
- JSONL event field rename migrations (eventName, type, seq, etc.)
- Metadata type coercion (non-dict -> {})
- Bundle format migration (v1.0.0, v1.1.0 -> v1.2.0)
- Session-level unified migration entry point
"""

from __future__ import annotations

import json

import pytest

from cc_deep_research.telemetry.ingest import (
    _ensure_metadata_table,
    ingest_telemetry_to_duckdb,
)
from cc_deep_research.telemetry.migrations import (
    CURRENT_BUNDLE_SCHEMA_VERSION,
    CURRENT_DUCKDB_SCHEMA_VERSION,
    MigrationScope,
    migrate_bundle,
    migrate_duckdb_schema,
    migrate_event_record,
    migrate_events_file,
    migrate_session,
)

# ---------------------------------------------------------------------------
# DuckDB Schema Migration Tests
# ---------------------------------------------------------------------------


def test_duckdb_schema_version_tracked(tmp_path):
    """DuckDB database tracks schema version in telemetry_metadata table."""
    pytest.importorskip("duckdb")

    import duckdb

    db_path = tmp_path / "telemetry.duckdb"
    conn = duckdb.connect(str(db_path))
    _ensure_metadata_table(conn)

    # Write a version
    conn.execute(
        "INSERT OR REPLACE INTO telemetry_metadata (key, value) VALUES (?, ?)",
        ["telemetry_schema_version", "0"],
    )
    conn.close()

    # Migration should detect v0 and upgrade
    result = migrate_duckdb_schema(db_path)
    assert result["upgraded"] is True
    assert result["from_version"] == 0
    assert result["to_version"] == CURRENT_DUCKDB_SCHEMA_VERSION


def test_duckdb_already_current_schema(tmp_path):
    """No-op when DuckDB schema is already at current version."""
    pytest.importorskip("duckdb")

    import duckdb

    db_path = tmp_path / "telemetry.duckdb"
    conn = duckdb.connect(str(db_path))
    _ensure_metadata_table(conn)
    conn.execute(
        "INSERT OR REPLACE INTO telemetry_metadata (key, value) VALUES (?, ?)",
        ["telemetry_schema_version", str(CURRENT_DUCKDB_SCHEMA_VERSION)],
    )
    conn.close()

    result = migrate_duckdb_schema(db_path)
    assert result["upgraded"] is False
    assert result["from_version"] == CURRENT_DUCKDB_SCHEMA_VERSION
    assert result["to_version"] == CURRENT_DUCKDB_SCHEMA_VERSION


def test_duckdb_no_metadata_table(tmp_path):
    """Databases created before schema versioning get version 0 on first migration."""
    pytest.importorskip("duckdb")

    import duckdb

    db_path = tmp_path / "telemetry.duckdb"
    conn = duckdb.connect(str(db_path))
    # Create tables but no metadata table
    conn.execute("CREATE TABLE IF NOT EXISTS telemetry_events (event_id VARCHAR)")
    conn.close()

    result = migrate_duckdb_schema(db_path)
    assert result["upgraded"] is True
    assert result["from_version"] == 0
    assert result["to_version"] == CURRENT_DUCKDB_SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Event Field Rename Migration Tests
# ---------------------------------------------------------------------------


def test_migrate_event_record_renames_old_field_names():
    """Event records with legacy field names get renamed to current names."""
    legacy_event = {
        "eventName": "search.query",
        "type": "search",
        "msg": "query",
        "sessionId": "sess-1",
        "seq": 5,
        "time": "2024-01-01T00:00:00Z",
        "parentId": "parent-1",
        "agentId": "agent-1",
        "duration": 1000,
        "status": "success",
        "metadata": {"query": "test"},
    }

    migrated = migrate_event_record(legacy_event)

    assert migrated["event_type"] == "search.query"
    assert migrated["category"] == "search"
    assert migrated["name"] == "query"
    assert migrated["session_id"] == "sess-1"
    assert migrated["sequence_number"] == 5
    assert migrated["timestamp"] == "2024-01-01T00:00:00Z"
    assert migrated["parent_event_id"] == "parent-1"
    assert migrated["agent_id"] == "agent-1"
    assert migrated["duration_ms"] == 1000
    assert migrated["metadata"] == {"query": "test"}


def test_migrate_event_record_preserves_current_field_names():
    """Events using current field names pass through unchanged."""
    current_event = {
        "event_id": "evt-1",
        "event_type": "search.query",
        "category": "search",
        "name": "query",
        "session_id": "sess-1",
        "sequence_number": 1,
        "timestamp": "2024-01-01T00:00:00Z",
        "parent_event_id": None,
        "agent_id": "agent-1",
        "duration_ms": 500,
        "status": "success",
        "metadata": {"query": "test"},
    }

    migrated = migrate_event_record(current_event)
    assert migrated == current_event


def test_migrate_event_record_metadata_type_coercion():
    """Non-dict metadata is coerced to empty dict."""
    events = [
        {"metadata": []},  # list
        {"metadata": None},  # null
        {"metadata": "string"},  # string
        {"metadata": 42},  # number
    ]

    for event in events:
        migrated = migrate_event_record(event)
        assert isinstance(migrated["metadata"], dict), f"metadata type should be dict, got {type(migrated['metadata'])}"


def test_migrate_event_record_copies_unknown_fields():
    """Fields not in the rename map are copied as-is."""
    event = {
        "event_type": "test.event",
        "category": "test",
        "custom_field": "custom_value",
        "another_field": 42,
    }

    migrated = migrate_event_record(event)
    assert migrated["custom_field"] == "custom_value"
    assert migrated["another_field"] == 42
    assert migrated["event_type"] == "test.event"


# ---------------------------------------------------------------------------
# Events File Migration Tests
# ---------------------------------------------------------------------------


def test_migrate_events_file(tmp_path):
    """migrate_events_file reads JSONL and returns fully migrated events."""
    session_dir = tmp_path / "migrate-test-session"
    session_dir.mkdir()
    events_file = session_dir / "events.jsonl"

    events = [
        {
            "eventName": "search.query",
            "type": "search",
            "msg": "query",
            "sessionId": "migrate-test-session",
            "seq": 1,
            "time": "2024-01-01T00:00:00Z",
            "status": "success",
            "metadata": None,
        },
        {
            "event_type": "llm.usage",  # current format mixed in
            "category": "llm",
            "name": "usage",
            "session_id": "migrate-test-session",
            "sequence_number": 2,
            "timestamp": "2024-01-01T00:00:01Z",
            "status": "success",
            "metadata": {"tokens": 100},
        },
    ]

    with open(events_file, "w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event))
            f.write("\n")

    migrated = migrate_events_file(events_file, "migrate-test-session")

    assert len(migrated) == 2

    # First event was migrated (legacy names)
    assert migrated[0]["event_type"] == "search.query"
    assert migrated[0]["category"] == "search"
    assert migrated[0]["name"] == "query"
    assert isinstance(migrated[0]["metadata"], dict)
    assert migrated[0]["sequence_number"] == 1
    assert migrated[0]["event_id"] is not None

    # Second event preserved (current format)
    assert migrated[1]["event_type"] == "llm.usage"
    assert migrated[1]["sequence_number"] == 2


# ---------------------------------------------------------------------------
# Bundle Migration Tests
# ---------------------------------------------------------------------------


def test_migrate_bundle_v1_0_0_to_v1_1_0():
    """Bundle v1.0.0 events get eventName renamed to event_type."""
    bundle = {
        "schema_version": "1.0.0",
        "session_id": "bundle-test",
        "events": [
            {
                "eventName": "search.query",
                "type": "search",
                "metadata": "bad metadata",
                "name": "query",
            },
            {
                "event_type": "llm.usage",  # already current
                "category": "llm",
            },
        ],
        "session_summary": {},
        "derived_outputs": {},
    }

    migrated = migrate_bundle(bundle)

    assert migrated["schema_version"] == CURRENT_BUNDLE_SCHEMA_VERSION
    assert migrated["events"][0]["event_type"] == "search.query"
    assert "eventName" not in migrated["events"][0]
    # Metadata normalized
    assert isinstance(migrated["events"][0]["metadata"], dict)


def test_migrate_bundle_v1_1_0_to_v1_2_0():
    """Bundle v1.1.0 events get trace_version and severity added."""
    bundle = {
        "schema_version": "1.1.0",
        "session_id": "bundle-test",
        "events": [
            {"event_type": "search.query", "status": "failed"},  # error severity
            {"event_type": "llm.usage", "status": "completed"},  # info severity
            {"event_type": "tool.call", "status": "fallback"},  # warning severity
        ],
        "session_summary": {},
        "derived_outputs": {},
    }

    migrated = migrate_bundle(bundle)

    assert migrated["schema_version"] == CURRENT_BUNDLE_SCHEMA_VERSION
    assert migrated["events"][0]["trace_version"] == "0"
    assert migrated["events"][0]["severity"] == "error"
    assert migrated["events"][1]["severity"] == "info"
    assert migrated["events"][2]["severity"] == "warning"


def test_migrate_bundle_already_current():
    """Current-version bundle passes through unchanged."""
    bundle = {
        "schema_version": CURRENT_BUNDLE_SCHEMA_VERSION,
        "session_id": "bundle-test",
        "events": [],
        "session_summary": {},
        "derived_outputs": {},
    }

    migrated = migrate_bundle(bundle)
    assert migrated is bundle


def test_migrate_bundle_unknown_version_passes_through():
    """Bundle with unknown future version does not crash."""
    bundle = {
        "schema_version": "99.0.0",
        "session_id": "bundle-test",
        "events": [],
        "session_summary": {},
        "derived_outputs": {},
    }

    migrated = migrate_bundle(bundle)
    # Should not crash, passes through unchanged
    assert migrated["schema_version"] == "99.0.0"


# ---------------------------------------------------------------------------
# Unified Migration Entry Point Tests
# ---------------------------------------------------------------------------


def test_migrate_session_duckdb(tmp_path):
    """migrate_session with DUCKDB scope upgrades DuckDB schema."""
    pytest.importorskip("duckdb")

    import duckdb

    from cc_deep_research.telemetry.ingest import (
        ingest_telemetry_to_duckdb,
    )

    telemetry_dir = tmp_path / "telemetry"
    telemetry_dir.mkdir()

    # Create a minimal session with events
    session_dir = telemetry_dir / "migrate-session"
    session_dir.mkdir()
    events_file = session_dir / "events.jsonl"
    events_file.write_text(
        json.dumps({
            "event_type": "test.event",
            "category": "test",
            "name": "test",
            "status": "info",
            "session_id": "migrate-session",
        }) + "\n"
    )

    # Ingest to create DB (this sets version to current)
    db_path_for_ingest = tmp_path / "telemetry.duckdb"
    ingest_telemetry_to_duckdb(base_dir=telemetry_dir, db_path=db_path_for_ingest)

    # Manually set version to 0 to simulate old DB
    conn = duckdb.connect(str(db_path_for_ingest))
    conn.execute("CREATE TABLE IF NOT EXISTS telemetry_metadata (key VARCHAR PRIMARY KEY, value VARCHAR)")
    conn.execute(
        "INSERT OR REPLACE INTO telemetry_metadata (key, value) VALUES (?, ?)",
        ["telemetry_schema_version", "0"],
    )
    conn.close()

    # Run migration
    report = migrate_session(
        "migrate-session",
        base_dir=telemetry_dir,
        scope=MigrationScope.DUCKDB,
        db_path=db_path_for_ingest,
    )

    assert report.duckdb_version == CURRENT_DUCKDB_SCHEMA_VERSION
    assert report.upgraded is True


def test_migrate_session_events(tmp_path):
    """migrate_session with EVENTS scope migrates events file."""
    telemetry_dir = tmp_path / "telemetry"
    telemetry_dir.mkdir()

    session_dir = telemetry_dir / "events-migrate-session"
    session_dir.mkdir()
    events_file = session_dir / "events.jsonl"
    events_file.write_text(
        json.dumps({
            "eventName": "search.query",
            "type": "search",
            "msg": "query",
            "sessionId": "events-migrate-session",
            "seq": 1,
            "time": "2024-01-01T00:00:00Z",
            "status": "success",
            "metadata": None,
        }) + "\n"
    )

    report = migrate_session(
        "events-migrate-session",
        base_dir=telemetry_dir,
        scope=MigrationScope.EVENTS,
    )

    assert report.events_migrated == 1
    assert report.upgraded is True


def test_migrate_session_bundle(tmp_path):
    """migrate_session with BUNDLE scope migrates bundle file."""
    telemetry_dir = tmp_path / "telemetry"
    telemetry_dir.mkdir()

    session_dir = telemetry_dir / "bundle-migrate-session"
    session_dir.mkdir()

    # Write a v1.0.0 bundle
    bundle_file = session_dir / "bundle.json"
    bundle = {
        "schema_version": "1.0.0",
        "session_id": "bundle-migrate-session",
        "events": [
            {"eventName": "test.event", "type": "test"},
        ],
        "session_summary": {},
        "derived_outputs": {},
    }
    bundle_file.write_text(json.dumps(bundle))

    report = migrate_session(
        "bundle-migrate-session",
        base_dir=telemetry_dir,
        scope=MigrationScope.BUNDLE,
    )

    assert report.bundle_version == CURRENT_BUNDLE_SCHEMA_VERSION


def test_migrate_session_all_scope(tmp_path):
    """migrate_session with ALL scope runs all migrations."""
    pytest.importorskip("duckdb")

    from cc_deep_research.telemetry.ingest import ingest_telemetry_to_duckdb

    telemetry_dir = tmp_path / "telemetry"
    telemetry_dir.mkdir()

    session_dir = telemetry_dir / "all-migrate-session"
    session_dir.mkdir()
    events_file = session_dir / "events.jsonl"
    events_file.write_text(
        json.dumps({
            "eventName": "test.event",
            "type": "test",
            "msg": "test",
            "sessionId": "all-migrate-session",
            "seq": 1,
            "status": "info",
        }) + "\n"
    )

    # Ingest to create DB
    ingest_telemetry_to_duckdb(base_dir=telemetry_dir)

    report = migrate_session(
        "all-migrate-session",
        base_dir=telemetry_dir,
        scope=MigrationScope.ALL,
    )

    assert report.upgraded is True
    assert report.events_migrated >= 0


def test_migrate_session_nonexistent(tmp_path):
    """migrate_session with non-existent session returns empty report."""
    report = migrate_session(
        "nonexistent-session",
        base_dir=tmp_path / "telemetry",
        scope=MigrationScope.ALL,
    )

    # Should not crash, returns empty report
    assert report.events_migrated == 0


# ---------------------------------------------------------------------------
# Ingestion Integration Tests
# ---------------------------------------------------------------------------


def test_ingest_applies_event_migration(tmp_path):
    """ingest_telemetry_to_duckdb applies field rename migration during ingestion."""
    pytest.importorskip("duckdb")

    telemetry_dir = tmp_path / "telemetry"
    telemetry_dir.mkdir()

    session_dir = telemetry_dir / "legacy-ingest-session"
    session_dir.mkdir()
    events_file = session_dir / "events.jsonl"

    # Write events with legacy field names
    events = [
        {
            "eventName": "search.query",
            "type": "search",
            "msg": "query",
            "sessionId": "legacy-ingest-session",
            "seq": 1,
            "time": "2024-01-01T00:00:00Z",
            "status": "success",
            "metadata": [],
        },
        {
            "event_type": "llm.usage",
            "category": "llm",
            "name": "usage",
            "session_id": "legacy-ingest-session",
            "sequence_number": 2,
            "timestamp": "2024-01-01T00:00:01Z",
            "status": "success",
            "metadata": {"tokens": 100},
        },
    ]

    with open(events_file, "w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event))
            f.write("\n")

    db_path = tmp_path / "telemetry.duckdb"
    result = ingest_telemetry_to_duckdb(base_dir=telemetry_dir, db_path=db_path)

    assert result["sessions"] == 0  # No summary file
    assert result["events"] == 2
