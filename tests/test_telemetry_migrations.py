"""Migration fixtures for legacy telemetry formats.

Covers backward compatibility for:
- Multi-event JSONL sessions missing correlation fields (event_id, parent_event_id, sequence_number)
- Old derived_summary.json with outdated version
- Legacy metadata types (null, string)
"""

from __future__ import annotations

import json

import pytest

from cc_deep_research.telemetry.ingest import ingest_telemetry_to_duckdb
from cc_deep_research.telemetry.live import query_live_event_tail
from cc_deep_research.telemetry.query import query_dashboard_data
from cc_deep_research.telemetry.summary_cache import (
    DERIVED_SUMMARY_VERSION,
    load_cached_summary,
)


def test_legacy_multi_event_session_ingestion(tmp_path):
    """DuckDB ingestion handles a legacy session with 5 events missing correlation fields.

    Simulates pre-trace-contract JSONL: no event_id, parent_event_id, or sequence_number.
    Each event has different metadata types (dict, list, null, string) to test normalization.
    """
    pytest.importorskip("duckdb")

    session_dir = tmp_path / "legacy-multi-event"
    session_dir.mkdir(parents=True)
    events_file = session_dir / "events.jsonl"

    events = [
        {
            "session_id": "legacy-multi-event",
            "timestamp": "2024-01-01T00:00:00Z",
            "event_type": "session.started",
            "category": "session",
            "name": "started",
            "status": "started",
            "metadata": {},  # dict - current format
        },
        {
            "session_id": "legacy-multi-event",
            "timestamp": "2024-01-01T00:00:01Z",
            "event_type": "search.query",
            "category": "search",
            "name": "query",
            "status": "success",
            "metadata": [],  # list - wrong type, should coerce to {}
        },
        {
            "session_id": "legacy-multi-event",
            "timestamp": "2024-01-01T00:00:02Z",
            "event_type": "llm.usage",
            "category": "llm",
            "name": "usage",
            "status": "success",
            "metadata": None,  # null - should coerce to {}
        },
        {
            "session_id": "legacy-multi-event",
            "timestamp": "2024-01-01T00:00:03Z",
            "event_type": "analyzer.run",
            "category": "analysis",
            "name": "analyzer",
            "status": "success",
            "metadata": "untyped string",  # string - should coerce to {}
        },
        {
            "session_id": "legacy-multi-event",
            "timestamp": "2024-01-01T00:00:04Z",
            "event_type": "session.finished",
            "category": "session",
            "name": "finished",
            "status": "completed",
            "metadata": {"duration_ms": 4000},  # dict with actual data
        },
    ]

    with open(events_file, "w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event))
            f.write("\n")

    summary_file = session_dir / "summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump({
            "session_id": "legacy-multi-event",
            "status": "completed",
            "total_sources": 3,
            "providers": ["tavily"],
            "total_time_ms": 4000,
        }, f)

    db_path = tmp_path / "telemetry.duckdb"
    result = ingest_telemetry_to_duckdb(base_dir=tmp_path, db_path=db_path)

    assert result["sessions"] == 1
    assert result["events"] == 5

    data = query_dashboard_data(db_path=db_path)
    assert data["kpis"]["sessions"] == 1


def test_legacy_derived_summary_version_invalidation(tmp_path):
    """Cached summary with old version is treated as stale and recomputed.

    Simulates a persisted derived_summary.json from a prior version that
    used a different schema version number.
    """
    session_dir = tmp_path / "legacy-summary"
    session_dir.mkdir(parents=True)

    # Write events
    events_file = session_dir / "events.jsonl"
    events_file.write_text(
        "\n".join(
            json.dumps({
                "event_id": f"legacy-summary-evt-{i}",
                "session_id": "legacy-summary",
                "sequence_number": i,
                "timestamp": "2024-01-01T00:00:00Z",
                "event_type": "test.event",
                "category": "test",
                "name": f"evt{i}",
                "status": "info",
            })
            for i in range(1, 4)
        )
        + "\n"
    )

    # Write summary file
    summary_file = session_dir / "summary.json"
    summary_file.write_text(json.dumps({
        "session_id": "legacy-summary",
        "status": "completed",
        "total_sources": 0,
        "providers": [],
        "total_time_ms": 100,
    }))

    # Write a stale derived_summary with old version number
    old_version = DERIVED_SUMMARY_VERSION - 1
    stale_summary = {
        "metadata": {
            "version": old_version,  # outdated version
            "last_event_sequence": 2,
            "event_count": 3,
            "computed_at": "2024-01-01T00:00:00Z",
            "session_id": "legacy-summary",
        },
        "narrative": [],
        "critical_path": {},
        "state_changes": [],
        "decisions": [],
        "degradations": [],
        "failures": [],
        "decision_graph": {"nodes": [], "edges": [], "summary": {"node_count": 0}},
        "active_phase": "test",
    }

    cache_file = session_dir / "derived_summary.json"
    cache_file.write_text(json.dumps(stale_summary))

    # load_cached_summary should return None for stale version
    loaded = load_cached_summary(session_dir)
    assert loaded is None, "Cache with old version should be treated as stale"


def test_legacy_metadata_types_normalized_in_live_tail(tmp_path):
    """Live tail query normalizes legacy metadata of various wrong types.

    Covers: metadata as list, null, string, and empty string.
    """
    session_dir = tmp_path / "legacy-metadata-types"
    session_dir.mkdir(parents=True)
    events_file = session_dir / "events.jsonl"

    events = [
        # metadata as list (wrong type)
        {
            "timestamp": "2024-01-01T00:00:00Z",
            "event_type": "test.list_metadata",
            "category": "test",
            "name": "list_meta",
            "status": "info",
            "metadata": [],
        },
        # metadata as null
        {
            "timestamp": "2024-01-01T00:00:01Z",
            "event_type": "test.null_metadata",
            "category": "test",
            "name": "null_meta",
            "status": "info",
            "metadata": None,
        },
        # metadata as string
        {
            "timestamp": "2024-01-01T00:00:02Z",
            "event_type": "test.string_metadata",
            "category": "test",
            "name": "string_meta",
            "status": "info",
            "metadata": "untyped",
        },
        # metadata as empty string
        {
            "timestamp": "2024-01-01T00:00:03Z",
            "event_type": "test.empty_string_metadata",
            "category": "test",
            "name": "empty_str_meta",
            "status": "info",
            "metadata": "",
        },
    ]

    with open(events_file, "w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event))
            f.write("\n")

    tail = query_live_event_tail("legacy-metadata-types", base_dir=tmp_path, limit=4)

    assert len(tail) == 4

    # All metadata should be coerced to {}
    for event in tail:
        assert isinstance(event["metadata"], dict), f"metadata type should be dict, got {type(event['metadata'])}"
        assert event["event_id"] is not None
        assert event["sequence_number"] is not None
        assert event["session_id"] == "legacy-metadata-types"
