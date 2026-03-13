"""Telemetry ingestion and analytics utilities."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cc_deep_research.config import get_default_config_path


@dataclass
class _LiveSessionSnapshot:
    """Cached representation of a telemetry session directory."""

    events_key: tuple[int, int] | None
    summary_key: tuple[int, int] | None
    events: list[dict[str, Any]]
    summary: dict[str, Any] | None


_LIVE_SESSION_CACHE: dict[Path, _LiveSessionSnapshot] = {}
_DASHBOARD_INSTALL_COMMAND = 'pip install "cc-deep-research[dashboard]"'


def get_default_telemetry_dir() -> Path:
    """Return default telemetry directory."""
    return get_default_config_path().parent / "telemetry"


def get_default_dashboard_db_path() -> Path:
    """Return default DuckDB path for telemetry analytics."""
    return get_default_config_path().parent / "telemetry.duckdb"


def _missing_dashboard_dependency_message(feature: str) -> str:
    """Return a consistent install hint for optional analytics dependencies."""
    return (
        f"{feature} requires optional dashboard dependencies. "
        f"Install with `{_DASHBOARD_INSTALL_COMMAND}`."
    )


def _is_terminal_session_event(event: dict[str, Any]) -> bool:
    """Return whether an event represents the terminal session summary event."""
    return (
        event.get("category") == "session"
        and event.get("event_type") == "session.finished"
    )


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
        with open(events_file, encoding="utf-8") as f:
            for index, line in enumerate(f, start=1):
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
        with open(summary_file, encoding="utf-8") as f:
            loaded_summary = json.load(f)
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


def _build_event_tree(events: list[dict[str, Any]], *, max_depth: int = 10) -> dict[str, Any]:
    """Build a hierarchical event tree from normalized event records."""
    cloned_events: list[dict[str, Any]] = []
    children_by_parent: dict[str | None, list[dict[str, Any]]] = {}

    for event in events:
        cloned = {
            **event,
            "metadata": dict(event.get("metadata", {})),
            "children": [],
        }
        cloned_events.append(cloned)
        parent_id = cloned.get("parent_event_id")
        children_by_parent.setdefault(parent_id, []).append(cloned)

    def attach_children(parent_event: dict[str, Any], depth: int = 0) -> None:
        if depth >= max_depth:
            return
        child_events = children_by_parent.get(parent_event["event_id"], [])
        child_events.sort(
            key=lambda event: (
                event.get("sequence_number") or 0,
                event.get("timestamp") or "",
            )
        )
        parent_event["children"] = child_events
        for child in child_events:
            attach_children(child, depth + 1)

    root_events = [
        event for event in children_by_parent.get(None, []) if not _is_terminal_session_event(event)
    ]
    session_root = next(
        (
            event
            for event in root_events
            if event.get("category") == "session" and event.get("event_type") == "session.started"
        ),
        None,
    )
    if session_root is not None:
        session_children = children_by_parent.setdefault(session_root["event_id"], [])
        session_children.extend(
            event
            for event in children_by_parent.get(None, [])
            if _is_terminal_session_event(event)
        )
    root_events.sort(
        key=lambda event: (
            event.get("sequence_number") or 0,
            event.get("timestamp") or "",
        )
    )

    for root_event in root_events:
        attach_children(root_event)

    return {
        "root_events": root_events,
        "total_events": len(cloned_events),
    }


def _current_phase_from_events(events: list[dict[str, Any]]) -> str | None:
    """Return the in-flight phase name, if any."""
    active_phase: str | None = None
    for event in events:
        event_type = event.get("event_type")
        name = event.get("name")
        if event_type == "phase.started":
            active_phase = name
        elif event_type in {"phase.completed", "phase.failed"} and active_phase == name:
            active_phase = None
    return active_phase


def _build_subprocess_streams(
    events: list[dict[str, Any]],
    *,
    chunk_limit: int = 200,
) -> list[dict[str, Any]]:
    """Group Claude subprocess events into dashboard-friendly stream views."""
    groups: dict[str, dict[str, Any]] = {}

    for event in events:
        event_type = event.get("event_type", "")
        if not event_type.startswith("subprocess."):
            continue

        if event_type == "subprocess.scheduled":
            group_id = event["event_id"]
        else:
            group_id = event.get("parent_event_id") or event["event_id"]

        group = groups.setdefault(
            group_id,
            {
                "subprocess_id": group_id,
                "operation": None,
                "model": None,
                "executable": None,
                "status": "scheduled",
                "started_at": None,
                "updated_at": None,
                "duration_ms": None,
                "exit_code": None,
                "stdout_chunks": [],
                "stderr_chunks": [],
                "events": [],
            },
        )
        group["events"].append(event)

        metadata = event.get("metadata", {})
        if group["operation"] is None:
            group["operation"] = metadata.get("operation")
        if group["model"] is None:
            group["model"] = metadata.get("model")
        if group["executable"] is None:
            group["executable"] = metadata.get("executable")
        if group["started_at"] is None:
            group["started_at"] = event.get("timestamp")
        group["updated_at"] = event.get("timestamp")

        if event_type in {"subprocess.completed", "subprocess.failed", "subprocess.timeout"}:
            group["status"] = event.get("status", group["status"])
            group["duration_ms"] = event.get("duration_ms")
            group["exit_code"] = metadata.get("exit_code")
        elif event_type == "subprocess.failed_to_start":
            group["status"] = "failed"
        elif event_type == "subprocess.started":
            group["status"] = "started"

        if event_type == "subprocess.stdout_chunk":
            group["stdout_chunks"].append(
                {
                    "timestamp": event.get("timestamp"),
                    "chunk_index": metadata.get("chunk_index"),
                    "content": metadata.get("content", ""),
                    "content_length": metadata.get("content_length", 0),
                    "content_truncated": bool(metadata.get("content_truncated")),
                }
            )
        if event_type == "subprocess.stderr_chunk":
            group["stderr_chunks"].append(
                {
                    "timestamp": event.get("timestamp"),
                    "chunk_index": metadata.get("chunk_index"),
                    "content": metadata.get("content", ""),
                    "content_length": metadata.get("content_length", 0),
                    "content_truncated": bool(metadata.get("content_truncated")),
                }
            )

    grouped_streams: list[dict[str, Any]] = []
    for group in groups.values():
        group["events"].sort(key=lambda event: event.get("sequence_number") or 0)
        group["stdout_chunks"].sort(key=lambda chunk: chunk.get("chunk_index") or 0)
        group["stderr_chunks"].sort(key=lambda chunk: chunk.get("chunk_index") or 0)

        if len(group["stdout_chunks"]) > chunk_limit:
            dropped = len(group["stdout_chunks"]) - chunk_limit
            group["stdout_chunks"] = group["stdout_chunks"][-chunk_limit:]
            group["dropped_stdout_chunks"] = dropped
        else:
            group["dropped_stdout_chunks"] = 0

        if len(group["stderr_chunks"]) > chunk_limit:
            dropped = len(group["stderr_chunks"]) - chunk_limit
            group["stderr_chunks"] = group["stderr_chunks"][-chunk_limit:]
            group["dropped_stderr_chunks"] = dropped
        else:
            group["dropped_stderr_chunks"] = 0

        grouped_streams.append(group)

    grouped_streams.sort(key=lambda group: group.get("started_at") or "", reverse=True)
    return grouped_streams


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
    for session_dir in sorted(p for p in telemetry_dir.iterdir() if p.is_dir()):
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

    if limit is not None:
        return sessions[:limit]
    return sessions


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
    events = detail["events"]
    tree = _build_event_tree(events, max_depth=max_depth)
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
        "event_tree": {
            **_build_event_tree(events),
            "session_id": session_id,
        },
        "subprocess_streams": _build_subprocess_streams(
            events,
            chunk_limit=subprocess_chunk_limit,
        ),
        "active_phase": _current_phase_from_events(events),
    }


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

    for session_dir in sorted(p for p in telemetry_dir.iterdir() if p.is_dir()):
        session_id = session_dir.name
        events_file = session_dir / "events.jsonl"
        summary_file = session_dir / "summary.json"

        if events_file.exists():
            conn.execute("DELETE FROM telemetry_events WHERE session_id = ?", [session_id])
            with open(events_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    event = json.loads(line)
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
            with open(summary_file, encoding="utf-8") as f:
                summary = json.load(f)
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


def query_dashboard_data(db_path: Path | None = None) -> dict[str, Any]:
    """Return summary metrics and datasets used by dashboard views."""
    database_path = db_path or get_default_dashboard_db_path()
    if not database_path.exists():
        return {
            "kpis": {},
            "sessions": [],
            "events": [],
            "agent_timeline": [],
            "phase_durations": [],
        }

    try:
        import duckdb
    except ImportError as exc:  # pragma: no cover - import guard
        raise RuntimeError(_missing_dashboard_dependency_message("Dashboard queries")) from exc

    conn = duckdb.connect(str(database_path), read_only=True)

    kpi_row = conn.execute(
        """
        SELECT
            COUNT(*) AS sessions,
            COALESCE(AVG(total_time_ms), 0) AS avg_time_ms,
            COALESCE(AVG(llm_total_tokens), 0) AS avg_tokens,
            COALESCE(AVG(search_queries), 0) AS avg_searches,
            COALESCE(AVG(tool_calls), 0) AS avg_tool_calls
        FROM telemetry_sessions
        """
    ).fetchone()

    sessions = conn.execute(
        """
        SELECT
            session_id,
            created_at,
            total_time_ms,
            total_sources,
            instances_spawned,
            search_queries,
            tool_calls,
            llm_total_tokens,
            status
        FROM telemetry_sessions
        ORDER BY created_at DESC NULLS LAST
        """
    ).fetchall()

    events = conn.execute(
        """
        SELECT
            event_id,
            parent_event_id,
            sequence_number,
            session_id,
            timestamp,
            event_type,
            category,
            name,
            status,
            duration_ms,
            agent_id,
            metadata_json
        FROM telemetry_events
        ORDER BY sequence_number ASC, timestamp DESC NULLS LAST
        LIMIT 2000
        """
    ).fetchall()

    agent_timeline = conn.execute(
        """
        SELECT
            event_id,
            parent_event_id,
            sequence_number,
            session_id,
            agent_id,
            event_type,
            name,
            status,
            duration_ms,
            timestamp
        FROM telemetry_events
        WHERE category = 'agent' AND agent_id IS NOT NULL
        ORDER BY sequence_number ASC, timestamp DESC NULLS LAST
        """
    ).fetchall()

    phase_durations = conn.execute(
        """
        SELECT
            session_id,
            name AS phase,
            COALESCE(AVG(duration_ms), 0) AS avg_duration_ms,
            COUNT(*) AS events
        FROM telemetry_events
        WHERE category = 'phase'
        GROUP BY session_id, phase
        ORDER BY session_id, phase
        """
    ).fetchall()

    conn.close()

    return {
        "kpis": {
            "sessions": int(kpi_row[0]) if kpi_row else 0,
            "avg_time_ms": float(kpi_row[1]) if kpi_row else 0.0,
            "avg_tokens": float(kpi_row[2]) if kpi_row else 0.0,
            "avg_searches": float(kpi_row[3]) if kpi_row else 0.0,
            "avg_tool_calls": float(kpi_row[4]) if kpi_row else 0.0,
        },
        "sessions": sessions,
        "events": events,
        "agent_timeline": agent_timeline,
        "phase_durations": phase_durations,
    }


def query_session_detail(
    session_id: str,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Return detailed telemetry datasets for a single session."""
    database_path = db_path or get_default_dashboard_db_path()
    if not database_path.exists():
        return {
            "session": None,
            "events": [],
            "phase_durations": [],
            "agent_events": [],
            "reasoning_events": [],
            "tool_calls": [],
            "llm_usage": [],
        }

    try:
        import duckdb
    except ImportError as exc:  # pragma: no cover - import guard
        raise RuntimeError(_missing_dashboard_dependency_message("Dashboard queries")) from exc

    conn = duckdb.connect(str(database_path), read_only=True)

    session_row = conn.execute(
        """
        SELECT
            session_id,
            created_at,
            status,
            total_time_ms,
            total_sources,
            instances_spawned,
            search_queries,
            tool_calls,
            llm_prompt_tokens,
            llm_completion_tokens,
            llm_total_tokens,
            providers_json
        FROM telemetry_sessions
        WHERE session_id = ?
        """,
        [session_id],
    ).fetchone()

    events = conn.execute(
        """
        SELECT
            event_id,
            parent_event_id,
            sequence_number,
            timestamp,
            event_type,
            category,
            name,
            status,
            duration_ms,
            agent_id,
            metadata_json
        FROM telemetry_events
        WHERE session_id = ?
        ORDER BY sequence_number ASC, timestamp ASC NULLS LAST
        """,
        [session_id],
    ).fetchall()

    phase_durations = conn.execute(
        """
        SELECT
            name AS phase,
            COALESCE(AVG(duration_ms), 0) AS avg_duration_ms,
            COUNT(*) AS samples
        FROM telemetry_events
        WHERE session_id = ?
          AND event_type = 'operation.finished'
          AND category = 'phase'
          AND duration_ms IS NOT NULL
        GROUP BY phase
        ORDER BY avg_duration_ms DESC
        """,
        [session_id],
    ).fetchall()

    agent_events = conn.execute(
        """
        SELECT
            event_id,
            parent_event_id,
            sequence_number,
            timestamp,
            event_type,
            agent_id,
            name,
            status,
            duration_ms,
            metadata_json
        FROM telemetry_events
        WHERE session_id = ?
          AND category = 'agent'
        ORDER BY sequence_number ASC, timestamp ASC NULLS LAST
        """,
        [session_id],
    ).fetchall()

    reasoning_events = conn.execute(
        """
        SELECT
            event_id,
            parent_event_id,
            sequence_number,
            timestamp,
            name AS stage,
            metadata_json
        FROM telemetry_events
        WHERE session_id = ?
          AND event_type = 'reasoning.summary'
        ORDER BY sequence_number ASC, timestamp ASC NULLS LAST
        """,
        [session_id],
    ).fetchall()

    tool_calls = conn.execute(
        """
        SELECT
            event_id,
            parent_event_id,
            sequence_number,
            timestamp,
            name AS tool_name,
            status,
            duration_ms,
            agent_id,
            metadata_json
        FROM telemetry_events
        WHERE session_id = ?
          AND event_type = 'tool.call'
        ORDER BY sequence_number ASC, timestamp ASC NULLS LAST
        """,
        [session_id],
    ).fetchall()

    llm_usage = conn.execute(
        """
        SELECT
            event_id,
            parent_event_id,
            sequence_number,
            timestamp,
            name AS operation,
            duration_ms,
            metadata_json
        FROM telemetry_events
        WHERE session_id = ?
          AND event_type = 'llm.usage'
        ORDER BY sequence_number ASC, timestamp ASC NULLS LAST
        """,
        [session_id],
    ).fetchall()

    conn.close()

    return {
        "session": session_row,
        "events": events,
        "phase_durations": phase_durations,
        "agent_events": agent_events,
        "reasoning_events": reasoning_events,
        "tool_calls": tool_calls,
        "llm_usage": llm_usage,
    }


def query_events_by_parent(
    session_id: str,
    parent_event_id: str | None,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Return child events for a given parent event ID.

    Args:
        session_id: The session to query.
        parent_event_id: The parent event ID to filter by. Use None for root events.
        db_path: Optional path to the DuckDB database.

    Returns:
        List of child event dictionaries.
    """
    database_path = db_path or get_default_dashboard_db_path()
    if not database_path.exists():
        return []

    try:
        import duckdb
    except ImportError as exc:  # pragma: no cover - import guard
        raise RuntimeError(_missing_dashboard_dependency_message("Dashboard queries")) from exc

    conn = duckdb.connect(str(database_path), read_only=True)

    if parent_event_id is None:
        # Query root events (no parent)
        rows = conn.execute(
            """
            SELECT
                event_id,
                parent_event_id,
                sequence_number,
                timestamp,
                event_type,
                category,
                name,
                status,
                duration_ms,
                agent_id,
                metadata_json
            FROM telemetry_events
            WHERE session_id = ?
              AND parent_event_id IS NULL
            ORDER BY sequence_number ASC
            """,
            [session_id],
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT
                event_id,
                parent_event_id,
                sequence_number,
                timestamp,
                event_type,
                category,
                name,
                status,
                duration_ms,
                agent_id,
                metadata_json
            FROM telemetry_events
            WHERE session_id = ?
              AND parent_event_id = ?
            ORDER BY sequence_number ASC
            """,
            [session_id, parent_event_id],
        ).fetchall()

    conn.close()

    events = [
        {
            "event_id": row[0],
            "parent_event_id": row[1],
            "sequence_number": row[2],
            "timestamp": row[3],
            "event_type": row[4],
            "category": row[5],
            "name": row[6],
            "status": row[7],
            "duration_ms": row[8],
            "agent_id": row[9],
            "metadata": json.loads(row[10]) if row[10] else {},
        }
        for row in rows
    ]
    if parent_event_id is None:
        return [event for event in events if not _is_terminal_session_event(event)]
    return events


def query_event_tree(
    session_id: str,
    db_path: Path | None = None,
    max_depth: int = 10,
) -> dict[str, Any]:
    """Return a hierarchical event tree for a session.

    Args:
        session_id: The session to query.
        db_path: Optional path to the DuckDB database.
        max_depth: Maximum depth for tree traversal.

    Returns:
        Hierarchical event tree with children nested under parents.
    """
    database_path = db_path or get_default_dashboard_db_path()
    if not database_path.exists():
        return {"root_events": [], "total_events": 0}

    # Get all events for the session
    detail = query_session_detail(session_id, database_path)

    # Build event lookup and children map
    events_by_id: dict[str, dict[str, Any]] = {}
    children_by_parent: dict[str | None, list[dict[str, Any]]] = {}

    for row in detail["events"]:
        event = {
            "event_id": row[0],
            "parent_event_id": row[1],
            "sequence_number": row[2],
            "timestamp": row[3],
            "event_type": row[4],
            "category": row[5],
            "name": row[6],
            "status": row[7],
            "duration_ms": row[8],
            "agent_id": row[9],
            "metadata": json.loads(row[10]) if row[10] else {},
            "children": [],
        }
        events_by_id[event["event_id"]] = event
        parent_id = event["parent_event_id"]
        if parent_id not in children_by_parent:
            children_by_parent[parent_id] = []
        children_by_parent[parent_id].append(event)

    # Build tree by attaching children to parents
    def attach_children(parent_event: dict[str, Any], depth: int = 0) -> None:
        if depth >= max_depth:
            return
        parent_id = parent_event["event_id"]
        children = children_by_parent.get(parent_id, [])
        # Sort children by sequence number
        children.sort(key=lambda e: e.get("sequence_number", 0))
        parent_event["children"] = children
        for child in children:
            attach_children(child, depth + 1)

    # Treat the terminal session summary as a child of the session root for tree views.
    root_events = [
        event for event in children_by_parent.get(None, []) if not _is_terminal_session_event(event)
    ]
    session_root = next(
        (
            event
            for event in root_events
            if event.get("category") == "session" and event.get("event_type") == "session.started"
        ),
        None,
    )
    if session_root is not None:
        session_children = children_by_parent.setdefault(session_root["event_id"], [])
        session_children.extend(
            event
            for event in children_by_parent.get(None, [])
            if _is_terminal_session_event(event)
        )
    root_events.sort(key=lambda e: e.get("sequence_number", 0))

    # Attach children recursively
    for root in root_events:
        attach_children(root)

    return {
        "root_events": root_events,
        "total_events": len(events_by_id),
        "session_id": session_id,
    }


__all__ = [
    "get_default_dashboard_db_path",
    "get_default_telemetry_dir",
    "ingest_telemetry_to_duckdb",
    "query_dashboard_data",
    "query_events_by_parent",
    "query_event_tree",
    "query_live_agent_timeline",
    "query_live_event_tail",
    "query_live_event_tree",
    "query_live_session_detail",
    "query_live_sessions",
    "query_live_subprocess_streams",
    "query_session_detail",
]
