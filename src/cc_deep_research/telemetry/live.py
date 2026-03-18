"""Live telemetry readers backed by JSONL session files."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cc_deep_research.config import get_default_config_path

from .tree import (
    build_event_tree,
    build_llm_route_streams,
    build_subprocess_streams,
    current_phase_from_events,
)


@dataclass
class _LiveSessionSnapshot:
    """Cached representation of a telemetry session directory."""

    events_key: tuple[int, int] | None
    summary_key: tuple[int, int] | None
    events: list[dict[str, Any]]
    summary: dict[str, Any] | None


_LIVE_SESSION_CACHE: dict[Path, _LiveSessionSnapshot] = {}


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


def _normalize_live_event(
    event: dict[str, Any],
    *,
    session_id: str,
    fallback_sequence: int,
) -> dict[str, Any]:
    """Fill required event fields for live file reads."""
    metadata = event.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}

    return {
        "event_id": event.get("event_id") or f"{session_id}-event-{fallback_sequence}",
        "parent_event_id": event.get("parent_event_id"),
        "sequence_number": int(event.get("sequence_number") or fallback_sequence),
        "timestamp": event.get("timestamp"),
        "session_id": event.get("session_id") or session_id,
        "event_type": event.get("event_type", "unknown"),
        "category": event.get("category", "unknown"),
        "name": event.get("name", "unknown"),
        "status": event.get("status", "unknown"),
        "duration_ms": event.get("duration_ms"),
        "agent_id": event.get("agent_id"),
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
        is_active = snapshot.summary is None and not session_finished

        sessions.append(
            {
                "session_id": session_dir.name,
                "created_at": summary.get("created_at") or first_timestamp,
                "last_event_at": last_timestamp,
                "status": summary.get("status", "running" if is_active else "completed"),
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
    return detail["event_tail"]


def query_live_agent_timeline(
    session_id: str,
    *,
    base_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Return live agent events for a session."""
    detail = query_live_session_detail(session_id, base_dir=base_dir)
    return detail["agent_timeline"]


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
    return detail["subprocess_streams"]


def query_live_session_detail(
    session_id: str,
    *,
    base_dir: Path | None = None,
    tail_limit: int = 200,
    subprocess_chunk_limit: int = 200,
) -> dict[str, Any]:
    """Return detailed live telemetry for a session from JSON files."""
    telemetry_dir = base_dir or get_default_telemetry_dir()
    session_dir = telemetry_dir / session_id
    if not session_dir.exists():
        return {
            "session": None,
            "summary": None,
            "events": [],
            "event_tail": [],
            "agent_timeline": [],
            "event_tree": {"root_events": [], "total_events": 0, "session_id": session_id},
            "subprocess_streams": [],
            "llm_route_analytics": build_llm_route_streams([]),
            "active_phase": None,
        }

    snapshot = _read_live_session_snapshot(session_dir)
    events = list(snapshot.events)
    summary = snapshot.summary or None
    session_finished = any(event.get("event_type") == "session.finished" for event in events)
    created_at = (summary or {}).get("created_at") or (events[0]["timestamp"] if events else None)
    last_event_at = events[-1]["timestamp"] if events else None
    is_active = summary is None and not session_finished

    session = {
        "session_id": session_id,
        "created_at": created_at,
        "last_event_at": last_event_at,
        "status": (summary or {}).get("status", "running" if is_active else "completed"),
        "active": is_active,
        "event_count": len(events),
        "total_sources": (summary or {}).get("total_sources", 0),
        "total_time_ms": (summary or {}).get("total_time_ms"),
    }

    return {
        "session": session,
        "summary": summary,
        "events": events,
        "event_tail": events[-tail_limit:],
        "agent_timeline": [event for event in events if event.get("category") == "agent"],
        "event_tree": {**build_event_tree(events), "session_id": session_id},
        "subprocess_streams": build_subprocess_streams(
            events,
            chunk_limit=subprocess_chunk_limit,
        ),
        "llm_route_analytics": build_llm_route_streams(events),
        "active_phase": current_phase_from_events(events),
    }


def query_live_llm_route_analytics(
    session_id: str,
    *,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Return LLM route analytics for a live session."""
    detail = query_live_session_detail(session_id, base_dir=base_dir)
    return build_llm_route_streams(detail["events"])


__all__ = [
    "delete_telemetry_session",
    "get_default_telemetry_dir",
    "query_live_agent_timeline",
    "query_live_event_tail",
    "query_live_event_tree",
    "query_live_llm_route_analytics",
    "query_live_session_detail",
    "query_live_sessions",
    "query_live_subprocess_streams",
]
