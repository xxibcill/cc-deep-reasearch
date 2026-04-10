"""Live telemetry readers backed by JSONL session files."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from cc_deep_research.config import get_default_config_path

from .tree import (
    build_critical_path,
    build_decisions,
    build_degradations,
    build_derived_summary,
    build_event_tree,
    build_failures,
    build_llm_route_streams,
    build_narrative,
    build_state_changes,
    build_subprocess_streams,
    current_phase_from_events,
    empty_decision_graph,
)


@dataclass
class _LiveSessionSnapshot:
    """Cached representation of a telemetry session directory."""

    events_key: tuple[int, int] | None
    summary_key: tuple[int, int] | None
    events: list[dict[str, Any]]
    summary: dict[str, Any] | None


_LIVE_SESSION_CACHE: dict[Path, _LiveSessionSnapshot] = {}

# Sessions with no activity for this duration are considered stale/inactive
_STALE_SESSION_THRESHOLD = timedelta(minutes=5)


def get_default_telemetry_dir() -> Path:
    """Return default telemetry directory."""
    return get_default_config_path().parent / "telemetry"


def delete_telemetry_session(
    session_id: str,
    base_dir: Path | None = None,
) -> dict[str, bool]:
    """Delete a session's telemetry directory and files.

    Args:
        session_id: The session ID to delete.
        base_dir: Optional base telemetry directory.

    Returns:
        Dict with 'deleted' (bool) and 'missing' (bool) indicating results.
    """
    telemetry_dir = base_dir or get_default_telemetry_dir()
    session_dir = telemetry_dir / session_id

    if not session_dir.exists():
        return {"deleted": False, "missing": True}

    shutil.rmtree(session_dir)
    return {"deleted": True, "missing": False}


def _file_cache_key(path: Path) -> tuple[int, int] | None:
    """Return a stable cache key for a file, if it exists."""
    if not path.exists():
        return None
    stat = path.stat()
    return (stat.st_mtime_ns, stat.st_size)


def _infer_phase_from_event(event: dict[str, Any]) -> str | None:
    """Infer execution phase from event type or category."""
    event_type = event.get("event_type", "")
    category = event.get("category", "")

    # Map event_type prefixes to phases
    if "session." in event_type:
        return "session"
    if "planning." in event_type or event_type == "query.variations":
        return "planning"
    if "search." in event_type or event_type == "source.provenance":
        return "collection"
    if "analysis." in event_type or "analyzer" in str(event.get("agent_id", "")).lower():
        return "analysis"
    if "validation." in event_type or "validator" in str(event.get("agent_id", "")).lower():
        return "validation"
    if "iteration." in event_type:
        return "iteration"
    if "llm." in event_type:
        return "llm"
    if "tool." in event_type:
        return "tool"
    if category == "phase":
        return event.get("name")

    return None


def _infer_severity(status: str, event_type: str) -> str:
    """Infer severity from status and event type."""
    if status in ("failed", "error", "critical"):
        return "error"
    if status in ("fallback", "degraded", "warning"):
        return "warning"
    if "fallback" in event_type or "degraded" in event_type:
        return "warning"
    if "error" in event_type or "failed" in event_type:
        return "error"
    return "info"


def _infer_reason_code(event: dict[str, Any]) -> str | None:
    """Infer reason code from event data."""
    # Check explicit reason_code
    if event.get("reason_code"):
        return cast(str | None, event["reason_code"])

    # Check metadata for reason
    metadata = event.get("metadata", {})
    if isinstance(metadata, dict):
        if "reason" in metadata:
            return cast(str | None, metadata["reason"])
        if "stop_reason" in metadata:
            return cast(str | None, metadata["stop_reason"])

    # Infer from event_type patterns
    event_type = event.get("event_type", "")
    if "fallback" in event_type:
        return "fallback"
    if "timeout" in event_type:
        return "timeout"
    if "degraded" in event_type:
        return "degraded"

    status = event.get("status", "")
    if status == "failed":
        return "error"
    if status == "completed":
        return "success"

    return None


def _normalize_live_event(
    event: dict[str, Any],
    *,
    session_id: str,
    fallback_sequence: int,
) -> dict[str, Any]:
    """Fill required event fields for live file reads, including trace contract fields."""
    metadata = event.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}

    # Get or derive actor information
    actor_id = event.get("agent_id") or event.get("actor_id")
    event_type = event.get("event_type", "unknown")
    status = event.get("status", "unknown")

    # Determine if degraded
    degraded = event.get("degraded", False)
    if not degraded:
        degraded = (
            status in ("failed", "fallback", "degraded")
            or "fallback" in event_type
            or "degraded" in event_type
        )

    return {
        # Core identity
        "event_id": event.get("event_id") or f"{session_id}-event-{fallback_sequence}",
        "parent_event_id": event.get("parent_event_id"),
        "sequence_number": int(event.get("sequence_number") or fallback_sequence),
        "timestamp": event.get("timestamp"),
        "session_id": event.get("session_id") or session_id,
        # Trace contract fields
        "trace_version": event.get("trace_version", "0"),
        "run_id": event.get("run_id"),
        "cause_event_id": event.get("cause_event_id"),
        # Event classification
        "event_type": event_type,
        "category": event.get("category", "unknown"),
        "name": event.get("name", "unknown"),
        "status": status,
        "severity": event.get("severity") or _infer_severity(status, event_type),
        "reason_code": event.get("reason_code") or _infer_reason_code(event),
        # Execution context
        "phase": event.get("phase") or _infer_phase_from_event(event),
        "operation": event.get("operation") or event.get("name"),
        "attempt": event.get("attempt", 1),
        # Actor
        "actor_type": "agent" if actor_id else "system",
        "actor_id": actor_id,
        "agent_id": actor_id,  # Keep for backward compatibility
        # Metrics
        "duration_ms": event.get("duration_ms"),
        "degraded": degraded,
        # Payload
        "metadata": metadata,
    }


def _read_live_session_snapshot(session_dir: Path) -> _LiveSessionSnapshot:
    """Load or reuse a cached live session snapshot."""
    events_file = session_dir / "events.jsonl"
    summary_file = session_dir / "summary.json"
    events_key = _file_cache_key(events_file)
    summary_key = _file_cache_key(summary_file)
    cached = _LIVE_SESSION_CACHE.get(session_dir)

    if cached and cached.events_key == events_key and cached.summary_key == summary_key:
        return cached

    session_id = session_dir.name
    events: list[dict[str, Any]] = []
    if events_file.exists():
        with open(events_file, encoding="utf-8") as handle:
            for index, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                raw_event = json.loads(stripped)
                events.append(
                    _normalize_live_event(
                        raw_event,
                        session_id=session_id,
                        fallback_sequence=index,
                    )
                )

    events.sort(
        key=lambda event: (
            event.get("sequence_number") or 0,
            event.get("timestamp") or "",
            event.get("event_id") or "",
        )
    )

    summary: dict[str, Any] | None = None
    if summary_file.exists():
        with open(summary_file, encoding="utf-8") as handle:
            loaded_summary = json.load(handle)
        if isinstance(loaded_summary, dict):
            summary = loaded_summary

    snapshot = _LiveSessionSnapshot(
        events_key=events_key,
        summary_key=summary_key,
        events=events,
        summary=summary,
    )
    _LIVE_SESSION_CACHE[session_dir] = snapshot
    return snapshot


def _is_session_truly_active(
    session_id: str,
    *,
    has_summary: bool,
    session_finished: bool,
    last_event_at: str | None,
    telemetry_dir: Path,
) -> bool:
    """Determine if a session is truly active, considering multiple factors.

    A session is considered inactive if any of these conditions are true:
    1. It has a summary.json (session completed normally)
    2. It has a session.finished event (session terminated properly)
    3. It exists as a saved session file (persisted to sessions directory)
    4. It exists in DuckDB with completed status (historical session)
    5. It has been inactive for too long (stale/abandoned session)

    Args:
        session_id: The session ID to check.
        has_summary: Whether the session has a summary.json file.
        session_finished: Whether the session has a session.finished event.
        last_event_at: ISO timestamp of the last event, or None.
        telemetry_dir: Path to the telemetry directory.

    Returns:
        True if session is truly active, False otherwise.
    """
    # If session has summary or finished event, it's not active
    if has_summary or session_finished:
        return False

    # Check if session exists in saved sessions directory
    from cc_deep_research.session_store import get_default_session_dir

    sessions_dir = get_default_session_dir()
    session_file = sessions_dir / f"{session_id}.json"
    if session_file.exists():
        return False

    # Check if session exists in DuckDB (historical session)
    db_path = get_default_config_path().parent / "telemetry.duckdb"
    if db_path.exists():
        try:
            import duckdb

            conn = duckdb.connect(str(db_path), read_only=True)
            try:
                row = conn.execute(
                    "SELECT session_id FROM telemetry_sessions WHERE session_id = ?",
                    [session_id],
                ).fetchone()
                if row is not None:
                    return False
            finally:
                conn.close()
        except Exception:
            pass  # If DuckDB check fails, continue with other checks

    # Check if session is stale (no recent activity)
    if last_event_at:
        try:
            last_event_time = datetime.fromisoformat(last_event_at.replace("Z", "+00:00"))
            if last_event_time.tzinfo is None:
                last_event_time = last_event_time.replace(tzinfo=UTC)
            now = datetime.now(UTC)
            if now - last_event_time > _STALE_SESSION_THRESHOLD:
                return False
        except (ValueError, TypeError):
            pass  # If timestamp parsing fails, continue

    # Session appears to be truly active
    return True


def query_live_sessions(
    base_dir: Path | None = None,
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Return session summaries directly from telemetry files, including active runs."""
    telemetry_dir = base_dir or get_default_telemetry_dir()
    if not telemetry_dir.exists():
        return []

    sessions: list[dict[str, Any]] = []
    for session_dir in sorted(path for path in telemetry_dir.iterdir() if path.is_dir()):
        snapshot = _read_live_session_snapshot(session_dir)
        if not snapshot.events and snapshot.summary is None:
            continue

        session_finished = any(
            event.get("event_type") == "session.finished" for event in snapshot.events
        )
        first_timestamp = snapshot.events[0]["timestamp"] if snapshot.events else None
        last_timestamp = snapshot.events[-1]["timestamp"] if snapshot.events else None
        summary = snapshot.summary or {}
        is_active = _is_session_truly_active(
            session_dir.name,
            has_summary=snapshot.summary is not None,
            session_finished=session_finished,
            last_event_at=last_timestamp,
            telemetry_dir=telemetry_dir,
        )

        # Determine status:
        # - If summary exists: use summary status
        # - If session finished: completed
        # - If active: running
        # - Otherwise (stale): interrupted
        if snapshot.summary is not None:
            status = summary.get("status", "completed")
        elif session_finished:
            status = "completed"
        elif is_active:
            status = "running"
        else:
            status = "interrupted"

        sessions.append(
            {
                "session_id": session_dir.name,
                "created_at": summary.get("created_at") or first_timestamp,
                "last_event_at": last_timestamp,
                "status": status,
                "active": is_active,
                "event_count": len(snapshot.events),
                "total_sources": summary.get("total_sources", 0),
                "total_time_ms": summary.get("total_time_ms"),
                "summary": summary or None,
            }
        )

    sessions.sort(
        key=lambda session: (
            1 if session["active"] else 0,
            session.get("last_event_at") or session.get("created_at") or "",
        ),
        reverse=True,
    )
    return sessions[:limit] if limit is not None else sessions


def query_live_event_tail(
    session_id: str,
    *,
    base_dir: Path | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Return the latest N live events for a session."""
    detail = query_live_session_detail(session_id, base_dir=base_dir, tail_limit=limit)
    return cast(list[dict[str, Any]], detail["event_tail"])


def query_live_agent_timeline(
    session_id: str,
    *,
    base_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Return live agent events for a session."""
    detail = query_live_session_detail(session_id, base_dir=base_dir)
    return cast(list[dict[str, Any]], detail["agent_timeline"])


def query_live_event_tree(
    session_id: str,
    *,
    base_dir: Path | None = None,
    max_depth: int = 10,
) -> dict[str, Any]:
    """Return a hierarchical event tree directly from telemetry files."""
    detail = query_live_session_detail(session_id, base_dir=base_dir)
    tree = build_event_tree(detail["events"], max_depth=max_depth)
    tree["session_id"] = session_id
    return tree


def query_live_subprocess_streams(
    session_id: str,
    *,
    base_dir: Path | None = None,
    chunk_limit: int = 200,
) -> list[dict[str, Any]]:
    """Return grouped Claude subprocess streams for a session."""
    detail = query_live_session_detail(
        session_id,
        base_dir=base_dir,
        subprocess_chunk_limit=chunk_limit,
    )
    return cast(list[dict[str, Any]], detail["subprocess_streams"])


def query_live_session_detail(
    session_id: str,
    *,
    base_dir: Path | None = None,
    tail_limit: int = 200,
    subprocess_chunk_limit: int = 200,
    cursor: int | None = None,
    before_cursor: int | None = None,
    limit: int | None = None,
    include_derived: bool = True,
) -> dict[str, Any]:
    """Return detailed live telemetry for a session from JSON files.

    Args:
        session_id: The session ID to query.
        base_dir: Optional base telemetry directory.
        tail_limit: Maximum events to return in event_tail (for backward compat).
        subprocess_chunk_limit: Maximum chunks per subprocess stream.
        cursor: Sequence number to start after (forward pagination).
        before_cursor: Sequence number to end before (backward pagination).
        limit: Maximum number of events to return in paged slice.
        include_derived: Whether to include derived outputs (narrative, etc.).

    Returns:
        Dict with session info, events, and derived outputs.
    """
    telemetry_dir = base_dir or get_default_telemetry_dir()
    session_dir = telemetry_dir / session_id
    if not session_dir.exists():
        return {
            "session": None,
            "summary": None,
            "events": [],
            "event_tail": [],
            "events_page": {"events": [], "total": 0, "has_more": False, "next_cursor": None, "prev_cursor": None},
            "agent_timeline": [],
            "event_tree": {"root_events": [], "total_events": 0, "session_id": session_id},
            "subprocess_streams": [],
            "llm_route_analytics": build_llm_route_streams([]),
            "active_phase": None,
            "narrative": [],
            "critical_path": {"path": [], "total_duration_ms": 0, "bottleneck_event": None, "phase_durations": []},
            "state_changes": [],
            "decisions": [],
            "degradations": [],
            "failures": [],
            "decision_graph": empty_decision_graph(),
        }

    snapshot = _read_live_session_snapshot(session_dir)
    events = list(snapshot.events)
    summary = snapshot.summary or None
    session_finished = any(event.get("event_type") == "session.finished" for event in events)
    created_at = (summary or {}).get("created_at") or (events[0]["timestamp"] if events else None)
    last_event_at = events[-1]["timestamp"] if events else None
    is_active = _is_session_truly_active(
        session_id,
        has_summary=summary is not None,
        session_finished=session_finished,
        last_event_at=last_event_at,
        telemetry_dir=telemetry_dir,
    )

    # Determine status:
    # - If summary exists: use summary status
    # - If session finished: completed
    # - If active: running
    # - Otherwise (stale): interrupted
    if summary is not None:
        status = summary.get("status", "completed")
    elif session_finished:
        status = "completed"
    elif is_active:
        status = "running"
    else:
        status = "interrupted"

    session = {
        "session_id": session_id,
        "created_at": created_at,
        "last_event_at": last_event_at,
        "status": status,
        "active": is_active,
        "event_count": len(events),
        "total_sources": (summary or {}).get("total_sources", 0),
        "total_time_ms": (summary or {}).get("total_time_ms"),
    }

    # Build cursor-paginated events page
    events_page = _build_events_page(
        events,
        cursor=cursor,
        before_cursor=before_cursor,
        limit=limit or tail_limit,
    )

    # Build derived outputs
    derived = {}
    if include_derived:
        derived = build_derived_summary(events)

    return {
        "session": session,
        "summary": summary,
        "events": events,
        "event_tail": events[-tail_limit:],
        "events_page": events_page,
        "agent_timeline": [event for event in events if event.get("category") == "agent"],
        "event_tree": {**build_event_tree(events), "session_id": session_id},
        "subprocess_streams": build_subprocess_streams(
            events,
            chunk_limit=subprocess_chunk_limit,
        ),
        "llm_route_analytics": build_llm_route_streams(events),
        "active_phase": current_phase_from_events(events),
        # Derived outputs
        "narrative": derived.get("narrative", []),
        "critical_path": derived.get("critical_path", {}),
        "state_changes": derived.get("state_changes", []),
        "decisions": derived.get("decisions", []),
        "degradations": derived.get("degradations", []),
        "failures": derived.get("failures", []),
        "decision_graph": derived.get("decision_graph", empty_decision_graph()),
    }


def _build_events_page(
    events: list[dict[str, Any]],
    *,
    cursor: int | None = None,
    before_cursor: int | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    """Build a cursor-paginated slice of events.

    Args:
        events: All normalized events for the session.
        cursor: Sequence number to start after (forward pagination).
        before_cursor: Sequence number to end before (backward pagination).
        limit: Maximum events to return.

    Returns:
        Dict with events slice and pagination metadata.
    """
    total = len(events)

    if not events:
        return {
            "events": [],
            "total": 0,
            "has_more": False,
            "next_cursor": None,
            "prev_cursor": None,
        }

    # Get sequence numbers for cursor calculations
    first_seq = events[0].get("sequence_number", 0)
    last_seq = events[-1].get("sequence_number", total - 1)

    # Forward pagination: events after cursor
    if cursor is not None:
        start_idx = 0
        for i, event in enumerate(events):
            seq = event.get("sequence_number", i)
            if seq > cursor:
                start_idx = i
                break
        else:
            start_idx = len(events)

        sliced = events[start_idx:start_idx + limit]
    # Backward pagination: events before cursor
    elif before_cursor is not None:
        end_idx = len(events)
        for i in range(len(events) - 1, -1, -1):
            seq = events[i].get("sequence_number", i)
            if seq < before_cursor:
                end_idx = i + 1
                break
        else:
            end_idx = 0

        start_idx = max(0, end_idx - limit)
        sliced = events[start_idx:end_idx]
    # No cursor: return first page
    else:
        sliced = events[:limit]

    if not sliced:
        return {
            "events": [],
            "total": total,
            "has_more": False,
            "next_cursor": None,
            "prev_cursor": None,
        }

    # Calculate cursors for next/prev pages
    first_returned_seq = sliced[0].get("sequence_number", events.index(sliced[0]) if sliced[0] in events else 0)
    last_returned_seq = sliced[-1].get("sequence_number", events.index(sliced[-1]) if sliced[-1] in events else total - 1)

    has_more = last_returned_seq < last_seq
    has_prev = first_returned_seq > first_seq

    return {
        "events": sliced,
        "total": total,
        "has_more": has_more,
        "next_cursor": last_returned_seq if has_more else None,
        "prev_cursor": first_returned_seq - 1 if has_prev else None,
    }


def query_live_llm_route_analytics(
    session_id: str,
    *,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Return LLM route analytics for a live session."""
    detail = query_live_session_detail(session_id, base_dir=base_dir)
    return build_llm_route_streams(detail["events"])


def query_session_checkpoints(
    session_id: str,
    *,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Return checkpoint manifest for a session.

    Args:
        session_id: The session ID to query.
        base_dir: Optional base telemetry directory.

    Returns:
        Dict with checkpoint manifest including checkpoints list and metadata.
    """
    telemetry_dir = base_dir or get_default_telemetry_dir()
    session_dir = telemetry_dir / session_id
    manifest_path = session_dir / "checkpoints" / "manifest.json"

    if not manifest_path.exists():
        return {
            "session_id": session_id,
            "checkpoints": [],
            "latest_checkpoint_id": None,
            "latest_resume_safe_checkpoint_id": None,
        }

    try:
        with open(manifest_path, encoding="utf-8") as f:
            manifest = cast(dict[str, Any], json.load(f))
        manifest["session_id"] = session_id
        return manifest
    except (json.JSONDecodeError, OSError):
        return {
            "session_id": session_id,
            "checkpoints": [],
            "latest_checkpoint_id": None,
            "latest_resume_safe_checkpoint_id": None,
        }


def query_checkpoint_detail(
    session_id: str,
    checkpoint_id: str,
    *,
    base_dir: Path | None = None,
) -> dict[str, Any] | None:
    """Return detailed checkpoint information.

    Args:
        session_id: The session ID.
        checkpoint_id: The checkpoint ID to query.
        base_dir: Optional base telemetry directory.

    Returns:
        Checkpoint dict or None if not found.
    """
    manifest = query_session_checkpoints(session_id, base_dir=base_dir)
    for checkpoint in manifest.get("checkpoints", []):
        if checkpoint.get("checkpoint_id") == checkpoint_id:
            return cast(dict[str, Any], checkpoint)
    return None


def query_latest_resumable_checkpoint(
    session_id: str,
    *,
    base_dir: Path | None = None,
) -> dict[str, Any] | None:
    """Return the latest resume-safe checkpoint for a session.

    Args:
        session_id: The session ID.
        base_dir: Optional base telemetry directory.

    Returns:
        Latest resume-safe checkpoint or None if none available.
    """
    manifest = query_session_checkpoints(session_id, base_dir=base_dir)
    checkpoint_id = manifest.get("latest_resume_safe_checkpoint_id")
    if not checkpoint_id:
        return None

    for checkpoint in manifest.get("checkpoints", []):
        if checkpoint.get("checkpoint_id") == checkpoint_id:
            return cast(dict[str, Any], checkpoint)
    return None


def query_checkpoints_by_phase(
    session_id: str,
    phase: str,
    *,
    base_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Return all checkpoints for a specific phase.

    Args:
        session_id: The session ID.
        phase: Phase name to filter by.
        base_dir: Optional base telemetry directory.

    Returns:
        List of checkpoints for the phase.
    """
    manifest = query_session_checkpoints(session_id, base_dir=base_dir)
    return [
        cp for cp in manifest.get("checkpoints", [])
        if cp.get("phase") == phase
    ]


def query_checkpoint_lineage(
    session_id: str,
    checkpoint_id: str,
    *,
    base_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Return checkpoint lineage from start to specified checkpoint.

    Args:
        session_id: The session ID.
        checkpoint_id: The checkpoint ID to trace lineage for.
        base_dir: Optional base telemetry directory.

    Returns:
        List of checkpoints from start to specified checkpoint.
    """
    manifest = query_session_checkpoints(session_id, base_dir=base_dir)
    checkpoints_by_id = {
        cp.get("checkpoint_id"): cp
        for cp in manifest.get("checkpoints", [])
    }

    lineage = []
    current_id = checkpoint_id
    while current_id and current_id in checkpoints_by_id:
        lineage.append(checkpoints_by_id[current_id])
        current_id = checkpoints_by_id[current_id].get("parent_checkpoint_id")

    return list(reversed(lineage))


__all__ = [
    "delete_telemetry_session",
    "get_default_telemetry_dir",
    "query_checkpoint_detail",
    "query_checkpoint_lineage",
    "query_checkpoints_by_phase",
    "query_latest_resumable_checkpoint",
    "query_live_agent_timeline",
    "query_live_event_tail",
    "query_live_event_tree",
    "query_live_llm_route_analytics",
    "query_live_session_detail",
    "query_live_sessions",
    "query_live_subprocess_streams",
    "query_session_checkpoints",
]
