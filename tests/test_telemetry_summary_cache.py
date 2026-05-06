"""Tests for persisted derived summary cache."""

from __future__ import annotations

import json
from pathlib import Path

from cc_deep_research.telemetry.summary_cache import (
    DERIVED_SUMMARY_FILENAME,
    DERIVED_SUMMARY_VERSION,
    DerivedSummary,
    DerivedSummaryMetadata,
    compute_derived_summary,
    get_or_compute_summary,
    invalidate_cached_summary,
    load_cached_summary,
    save_cached_summary,
)


def _write_events(session_dir: Path, session_id: str, count: int, start_seq: int = 1) -> None:
    """Write events.jsonl for a session."""
    events_file = session_dir / "events.jsonl"
    events_file.write_text(
        "\n".join(
            json.dumps({
                "event_id": f"{session_id}-evt-{i}",
                "session_id": session_id,
                "sequence_number": i,
                "timestamp": "2026-01-01T00:00:00Z",
                "event_type": "test.event",
                "category": "test",
                "name": f"evt{i}",
                "status": "info",
            })
            for i in range(start_seq, start_seq + count)
        )
        + "\n"
    )


def _write_summary(session_dir: Path, session_id: str) -> None:
    """Write summary.json for a session."""
    (session_dir / "summary.json").write_text(json.dumps({
        "session_id": session_id,
        "status": "completed",
        "total_sources": 0,
        "providers": [],
        "total_time_ms": 100,
        "created_at": "2026-01-01T00:00:00Z",
    }))


class TestDerivedSummarySerialization:
    """Test DerivedSummary serialization round-trip."""

    def test_to_dict_and_from_dict_roundtrip(self):
        """Summary serialized to dict and back should match original."""
        summary = DerivedSummary(
            metadata=DerivedSummaryMetadata(
                version=DERIVED_SUMMARY_VERSION,
                last_event_sequence=10,
                event_count=10,
                computed_at="2026-01-01T00:00:00Z",
                session_id="test-session",
            ),
            narrative=[{"event_id": "evt-1", "event_type": "test.event"}],
            critical_path={"path": [], "total_duration_ms": 100},
            state_changes=[{"event_id": "evt-2", "state_key": "phase"}],
            decisions=[{"event_id": "evt-3", "decision_type": "routing"}],
            degradations=[{"event_id": "evt-4", "severity": "warning"}],
            failures=[{"event_id": "evt-5", "severity": "error"}],
            decision_graph={"nodes": [], "edges": [], "summary": {"node_count": 0}},
            active_phase="analysis",
        )

        data = summary.to_dict()
        restored = DerivedSummary.from_dict(data)

        assert restored.metadata.version == summary.metadata.version
        assert restored.metadata.last_event_sequence == summary.metadata.last_event_sequence
        assert restored.metadata.event_count == summary.metadata.event_count
        assert restored.active_phase == summary.active_phase
        assert len(restored.narrative) == len(summary.narrative)

    def test_from_dict_handles_missing_fields(self):
        """from_dict should use defaults for missing fields."""
        minimal = DerivedSummary.from_dict({})

        assert minimal.metadata.version == DERIVED_SUMMARY_VERSION
        assert minimal.metadata.last_event_sequence == 0
        assert minimal.metadata.event_count == 0
        assert minimal.narrative == []


class TestComputeDerivedSummary:
    """Test derived summary computation from events."""

    def test_computes_all_derived_outputs(self, tmp_path):
        """compute_derived_summary produces all expected fields."""
        session_dir = tmp_path / "compute-session"
        session_dir.mkdir()
        _write_events(session_dir, "compute-session", 5)
        _write_summary(session_dir, "compute-session")

        # Load events
        events_file = session_dir / "events.jsonl"
        events = []
        with open(events_file) as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))

        # Add metadata to events (as they would be after normalization)
        for e in events:
            e["timestamp"] = "2026-01-01T00:00:00Z"
            e["status"] = "info"
            e["severity"] = "info"
            e["reason_code"] = None
            e["phase"] = "session"
            e["operation"] = e["name"]
            e["actor_type"] = "system"
            e["actor_id"] = None
            e["degraded"] = False
            e["trace_version"] = "0"
            e["run_id"] = None
            e["cause_event_id"] = None

        summary = compute_derived_summary(events, "compute-session")

        assert summary.metadata.event_count == 5
        assert summary.metadata.session_id == "compute-session"
        assert summary.metadata.version == DERIVED_SUMMARY_VERSION


class TestSaveAndLoadCachedSummary:
    """Test saving and loading cached summaries."""

    def test_save_and_load_roundtrip(self, tmp_path):
        """A saved summary can be loaded back identically."""
        session_dir = tmp_path / "cache-session"
        session_dir.mkdir()
        _write_events(session_dir, "cache-session", 3)
        _write_summary(session_dir, "cache-session")

        original = DerivedSummary(
            metadata=DerivedSummaryMetadata(
                version=DERIVED_SUMMARY_VERSION,
                last_event_sequence=3,
                event_count=3,
                computed_at="2026-01-01T12:00:00Z",
                session_id="cache-session",
            ),
            decisions=[{"event_type": "decision.made", "decision_type": "test"}],
            active_phase="analysis",
        )

        save_cached_summary(original, session_dir)
        loaded = load_cached_summary(session_dir)

        assert loaded is not None
        assert loaded.metadata.session_id == "cache-session"
        assert loaded.metadata.last_event_sequence == 3
        assert len(loaded.decisions) == 1
        assert loaded.active_phase == "analysis"

    def test_load_returns_none_for_missing_cache(self, tmp_path):
        """load_cached_summary returns None when no cache file exists."""
        session_dir = tmp_path / "no-cache"
        session_dir.mkdir()

        result = load_cached_summary(session_dir)
        assert result is None

    def test_cache_becomes_stale_after_new_events(self, tmp_path):
        """Cache with last_event_sequence lower than current is considered stale."""
        session_dir = tmp_path / "stale-cache"
        session_dir.mkdir()

        # Write 3 events and cache a summary with last_seq=3
        _write_events(session_dir, "stale-cache", 3)
        original = DerivedSummary(
            metadata=DerivedSummaryMetadata(
                version=DERIVED_SUMMARY_VERSION,
                last_event_sequence=3,
                event_count=3,
                computed_at="2026-01-01T00:00:00Z",
                session_id="stale-cache",
            ),
        )
        save_cached_summary(original, session_dir)

        # Now add more events (seq 4, 5)
        events_file = session_dir / "events.jsonl"
        events_file.write_text(
            events_file.read_text()
            + json.dumps({
                "event_id": "stale-cache-evt-4",
                "session_id": "stale-cache",
                "sequence_number": 4,
                "timestamp": "2026-01-02T00:00:00Z",
                "event_type": "test.event",
                "category": "test",
                "name": "evt4",
                "status": "info",
            })
            + "\n"
        )

        # Cache should now be stale
        result = load_cached_summary(session_dir)
        assert result is None, "Cache should be stale when new events added"


class TestInvalidateCachedSummary:
    """Test cache invalidation."""

    def test_invalidate_removes_cache_file(self, tmp_path):
        """invalidate_cached_summary removes the cache file."""
        session_dir = tmp_path / "invalidate-test"
        session_dir.mkdir()
        _write_events(session_dir, "invalidate-test", 3)
        _write_summary(session_dir, "invalidate-test")

        summary = DerivedSummary(metadata=DerivedSummaryMetadata(session_id="invalidate-test"))
        save_cached_summary(summary, session_dir)
        assert load_cached_summary(session_dir) is not None

        removed = invalidate_cached_summary(session_dir)
        assert removed is True
        assert load_cached_summary(session_dir) is None

    def test_invalidate_returns_false_when_no_cache(self, tmp_path):
        """invalidate_cached_summary returns False when no cache exists."""
        session_dir = tmp_path / "no-invalidate"
        session_dir.mkdir()

        removed = invalidate_cached_summary(session_dir)
        assert removed is False


class TestGetOrComputeSummary:
    """Test the get-or-compute summary helper."""

    def test_returns_cached_if_valid(self, tmp_path):
        """get_or_compute_summary returns cached summary if not stale."""
        session_dir = tmp_path / "get-or-compute"
        session_dir.mkdir()
        _write_events(session_dir, "get-or-compute", 3)
        _write_summary(session_dir, "get-or-compute")

        # Pre-populate cache
        cached = DerivedSummary(
            metadata=DerivedSummaryMetadata(
                version=DERIVED_SUMMARY_VERSION,
                last_event_sequence=3,
                event_count=3,
                session_id="get-or-compute",
            ),
            active_phase="analysis",
        )
        save_cached_summary(cached, session_dir)

        events_file = session_dir / "events.jsonl"
        events = []
        with open(events_file) as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))

        result = get_or_compute_summary(events, "get-or-compute", session_dir)

        assert result.active_phase == "analysis"
        assert result.metadata.last_event_sequence == 3

    def test_recomputes_if_cache_stale(self, tmp_path):
        """get_or_compute_summary recomputes if cache is stale."""
        session_dir = tmp_path / "recompute-test"
        session_dir.mkdir()

        # Create events
        _write_events(session_dir, "recompute-test", 5)

        events_file = session_dir / "events.jsonl"
        events = []
        with open(events_file) as f:
            for line in f:
                if line.strip():
                    e = json.loads(line)
                    e["timestamp"] = "2026-01-01T00:00:00Z"
                    e["status"] = "info"
                    e["severity"] = "info"
                    e["phase"] = "session"
                    e["operation"] = e["name"]
                    e["actor_type"] = "system"
                    e["actor_id"] = None
                    e["degraded"] = False
                    e["trace_version"] = "0"
                    e["run_id"] = None
                    e["cause_event_id"] = None
                    e["reason_code"] = None
                    events.append(e)

        # No cache exists - first call computes and saves
        result1 = get_or_compute_summary(events, "recompute-test", session_dir)
        assert result1.metadata.event_count == 5
        assert (session_dir / DERIVED_SUMMARY_FILENAME).exists()

        # Cache is valid, returns same
        result2 = get_or_compute_summary(events, "recompute-test", session_dir)
        assert result2.metadata.last_event_sequence == result1.metadata.last_event_sequence

    def test_force_refresh_bypasses_cache(self, tmp_path):
        """force_refresh=True ignores cached summary."""
        session_dir = tmp_path / "force-refresh"
        session_dir.mkdir()
        _write_events(session_dir, "force-refresh", 3)
        _write_summary(session_dir, "force-refresh")

        events_file = session_dir / "events.jsonl"
        events = []
        with open(events_file) as f:
            for line in f:
                if line.strip():
                    e = json.loads(line)
                    e["timestamp"] = "2026-01-01T00:00:00Z"
                    e["status"] = "info"
                    e["severity"] = "info"
                    e["phase"] = "session"
                    e["operation"] = e["name"]
                    e["actor_type"] = "system"
                    e["actor_id"] = None
                    e["degraded"] = False
                    e["trace_version"] = "0"
                    e["run_id"] = None
                    e["cause_event_id"] = None
                    e["reason_code"] = None
                    events.append(e)

        # First call caches
        result1 = get_or_compute_summary(events, "force-refresh", session_dir)
        assert (session_dir / DERIVED_SUMMARY_FILENAME).exists()

        # Force refresh ignores cache
        result2 = get_or_compute_summary(events, "force-refresh", session_dir, force_refresh=True)
        # Both should have same result since events didn't change
        assert result2.metadata.last_event_sequence == result1.metadata.last_event_sequence


class TestDerivedOutputsMatchFullRebuild:
    """Test that cached summary matches what full rebuild produces."""

    def test_cached_matches_rebuild_for_stable_session(self, tmp_path):
        """For a session with no new events, cached and fresh rebuild match."""
        from cc_deep_research.monitoring import ResearchMonitor

        monitor = ResearchMonitor(enabled=False, persist=True, telemetry_dir=tmp_path)
        monitor.set_session("match-test", query="test", depth="standard")
        monitor.emit_event(event_type="phase.started", category="phase", name="analysis", status="started")
        monitor.emit_event(
            event_type="decision.made",
            category="planning",
            name="route_decision",
            metadata={"decision_type": "routing", "chosen_option": "openrouter"},
        )
        monitor.finalize_session(total_sources=5, providers=["tavily"], total_time_ms=1000)

        # Load events
        from cc_deep_research.telemetry.live import _read_live_session_snapshot

        session_dir = tmp_path / "match-test"
        snapshot = _read_live_session_snapshot(session_dir)
        events = snapshot.events

        # Fresh rebuild
        from cc_deep_research.telemetry.tree import build_derived_summary

        fresh = build_derived_summary(events)

        # Cached
        cached = get_or_compute_summary(events, "match-test", session_dir)

        # Compare key fields
        assert len(cached.narrative) == len(fresh.get("narrative", []))
        assert len(cached.decisions) == len(fresh.get("decisions", []))
        assert cached.active_phase == fresh.get("active_phase")
        assert cached.decision_graph["summary"]["node_count"] == fresh["decision_graph"]["summary"]["node_count"]
