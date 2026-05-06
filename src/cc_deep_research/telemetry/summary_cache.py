"""Persisted derived telemetry summaries with incremental invalidation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cc_deep_research.telemetry.tree import (
    build_derived_summary,
    empty_decision_graph,
)

DERIVED_SUMMARY_FILENAME = "derived_summary.json"
DERIVED_SUMMARY_VERSION = 1


@dataclass
class DerivedSummaryMetadata:
    """Metadata for a persisted derived summary."""

    version: int = DERIVED_SUMMARY_VERSION
    last_event_sequence: int = 0
    event_count: int = 0
    computed_at: str | None = None
    session_id: str = ""


@dataclass
class DerivedSummary:
    """A complete derived summary with metadata and outputs."""

    metadata: DerivedSummaryMetadata
    narrative: list[dict[str, Any]] = field(default_factory=list)
    critical_path: dict[str, Any] = field(default_factory=dict)
    state_changes: list[dict[str, Any]] = field(default_factory=list)
    decisions: list[dict[str, Any]] = field(default_factory=list)
    degradations: list[dict[str, Any]] = field(default_factory=list)
    failures: list[dict[str, Any]] = field(default_factory=list)
    decision_graph: dict[str, Any] = field(default_factory=empty_decision_graph)
    active_phase: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary for JSON storage."""
        return {
            "metadata": {
                "version": self.metadata.version,
                "last_event_sequence": self.metadata.last_event_sequence,
                "event_count": self.metadata.event_count,
                "computed_at": self.metadata.computed_at,
                "session_id": self.metadata.session_id,
            },
            "narrative": self.narrative,
            "critical_path": self.critical_path,
            "state_changes": self.state_changes,
            "decisions": self.decisions,
            "degradations": self.degradations,
            "failures": self.failures,
            "decision_graph": self.decision_graph,
            "active_phase": self.active_phase,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DerivedSummary:
        """Deserialize from a dictionary."""
        meta = data.get("metadata", {})
        return cls(
            metadata=DerivedSummaryMetadata(
                version=meta.get("version", DERIVED_SUMMARY_VERSION),
                last_event_sequence=meta.get("last_event_sequence", 0),
                event_count=meta.get("event_count", 0),
                computed_at=meta.get("computed_at"),
                session_id=meta.get("session_id", ""),
            ),
            narrative=data.get("narrative", []),
            critical_path=data.get("critical_path", {}),
            state_changes=data.get("state_changes", []),
            decisions=data.get("decisions", []),
            degradations=data.get("degradations", []),
            failures=data.get("failures", []),
            decision_graph=data.get("decision_graph", empty_decision_graph()),
            active_phase=data.get("active_phase"),
        )


def _get_summary_cache_path(session_dir: Path) -> Path:
    """Return the path to the derived summary cache file for a session."""
    return session_dir / DERIVED_SUMMARY_FILENAME


def _get_last_event_sequence(session_dir: Path) -> int:
    """Return the sequence number of the last event in a session's events.jsonl."""
    events_file = session_dir / "events.jsonl"
    if not events_file.exists():
        return 0

    try:
        with open(events_file, encoding="utf-8") as f:
            last_seq = 0
            last_line = None
            for line in f:
                stripped = line.strip()
                if stripped:
                    last_line = stripped
            if last_line:
                event = json.loads(last_line)
                last_seq = int(event.get("sequence_number", 0))
        return last_seq
    except (ValueError, json.JSONDecodeError, OSError):
        return 0


def compute_derived_summary(
    events: list[dict[str, Any]],
    session_id: str,
) -> DerivedSummary:
    """Compute derived summary from a list of events.

    Args:
        events: Normalized event records.
        session_id: The session ID.

    Returns:
        DerivedSummary with all computed outputs.
    """
    last_seq = 0
    if events:
        last_seq = max((e.get("sequence_number") or 0 for e in events), default=0)

    derived = build_derived_summary(events)

    return DerivedSummary(
        metadata=DerivedSummaryMetadata(
            version=DERIVED_SUMMARY_VERSION,
            last_event_sequence=last_seq,
            event_count=len(events),
            computed_at=datetime.now(UTC).isoformat(),
            session_id=session_id,
        ),
        narrative=derived.get("narrative", []),
        critical_path=derived.get("critical_path", {}),
        state_changes=derived.get("state_changes", []),
        decisions=derived.get("decisions", []),
        degradations=derived.get("degradations", []),
        failures=derived.get("failures", []),
        decision_graph=derived.get("decision_graph", empty_decision_graph()),
        active_phase=derived.get("active_phase"),
    )


def load_cached_summary(session_dir: Path) -> DerivedSummary | None:
    """Load a cached derived summary from disk if it exists and is valid.

    Args:
        session_dir: Path to the session's telemetry directory.

    Returns:
        DerivedSummary if cache exists and is not stale, None otherwise.
    """
    cache_path = _get_summary_cache_path(session_dir)
    if not cache_path.exists():
        return None

    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        cached = DerivedSummary.from_dict(data)

        # Check version compatibility
        if cached.metadata.version != DERIVED_SUMMARY_VERSION:
            return None

        # Check if cache is stale by comparing last_event_sequence.
        # A sequence of 0 means the summary was created without recording
        # sequence info (e.g. empty session), so we treat it as valid to avoid
        # incorrectly invalidating caches for edge cases. Only invalidate when
        # the cached sequence is definitively behind the current events.
        cached_seq = cached.metadata.last_event_sequence
        current_last_seq = _get_last_event_sequence(session_dir)
        if cached_seq > 0 and cached_seq < current_last_seq:
            return None

        return cached
    except (ValueError, json.JSONDecodeError, OSError):
        return None


def save_cached_summary(summary: DerivedSummary, session_dir: Path) -> None:
    """Persist a derived summary to disk.

    Args:
        summary: The derived summary to cache.
        session_dir: Path to the session's telemetry directory.
    """
    cache_path = _get_summary_cache_path(session_dir)
    try:
        cache_path.write_text(
            json.dumps(summary.to_dict(), indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def invalidate_cached_summary(session_dir: Path) -> bool:
    """Delete the cached derived summary if it exists.

    Args:
        session_dir: Path to the session's telemetry directory.

    Returns:
        True if a cache was deleted, False if none existed.
    """
    cache_path = _get_summary_cache_path(session_dir)
    if cache_path.exists():
        cache_path.unlink()
        return True
    return False


def get_or_compute_summary(
    events: list[dict[str, Any]],
    session_id: str,
    session_dir: Path,
    force_refresh: bool = False,
) -> DerivedSummary:
    """Return cached summary if valid, otherwise compute and cache.

    Args:
        events: Normalized event records.
        session_id: The session ID.
        session_dir: Path to the session's telemetry directory.
        force_refresh: If True, ignore cache and recompute.

    Returns:
        DerivedSummary (cached or freshly computed).
    """
    if not force_refresh:
        cached = load_cached_summary(session_dir)
        if cached is not None:
            return cached

    summary = compute_derived_summary(events, session_id)
    save_cached_summary(summary, session_dir)
    return summary


def refresh_summary_after_ingestion(
    session_id: str,
    session_dir: Path,
    new_event_count: int,
) -> DerivedSummary | None:
    """Refresh the cached summary after new events are ingested.

    Call this after appending events to events.jsonl to keep the summary
    in sync. If the session_dir does not have a cached summary yet, this
    is a no-op and returns None.

    Args:
        session_id: The session ID.
        session_dir: Path to the session's telemetry directory.
        new_event_count: Number of events that were added.

    Returns:
        The updated DerivedSummary, or None if no cache existed to refresh.
    """
    cached = load_cached_summary(session_dir)
    if cached is None:
        return None

    # Invalidate stale cache
    invalidate_cached_summary(session_dir)
    return None


__all__ = [
    "DerivedSummary",
    "DerivedSummaryMetadata",
    "compute_derived_summary",
    "get_or_compute_summary",
    "invalidate_cached_summary",
    "load_cached_summary",
    "refresh_summary_after_ingestion",
    "save_cached_summary",
]
