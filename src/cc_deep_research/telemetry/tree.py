"""Telemetry event shaping helpers."""

from __future__ import annotations

import json
from typing import Any


def is_terminal_session_event(event: dict[str, Any]) -> bool:
    """Return whether an event represents the terminal session summary event."""
    return event.get("category") == "session" and event.get("event_type") == "session.finished"


def build_event_tree(events: list[dict[str, Any]], *, max_depth: int = 10) -> dict[str, Any]:
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
        event for event in children_by_parent.get(None, []) if not is_terminal_session_event(event)
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
            if is_terminal_session_event(event)
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


def build_event_tree_from_rows(
    rows: list[tuple[Any, ...]],
    *,
    session_id: str,
    max_depth: int = 10,
) -> dict[str, Any]:
    """Build an event tree from DuckDB telemetry rows."""
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
    tree = build_event_tree(events, max_depth=max_depth)
    tree["session_id"] = session_id
    return tree


def current_phase_from_events(events: list[dict[str, Any]]) -> str | None:
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


def build_subprocess_streams(
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

        group_id = (
            event["event_id"]
            if event_type == "subprocess.scheduled"
            else event.get("parent_event_id") or event["event_id"]
        )
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


def build_llm_route_streams(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Build LLM route analytics from normalized telemetry events."""
    route_selections = [event for event in events if event.get("event_type") == "llm.route_selected"]
    route_fallbacks = [event for event in events if event.get("event_type") == "llm.route_fallback"]
    route_completions = [
        event for event in events if event.get("event_type") == "llm.route_completion"
    ]
    route_requests = [event for event in events if event.get("event_type") == "llm.route_request"]

    transport_summary: dict[str, dict[str, Any]] = {}
    for event in route_completions:
        metadata = event.get("metadata", {})
        transport = metadata.get("transport", "unknown")
        if transport not in transport_summary:
            transport_summary[transport] = {
                "requests": 0,
                "tokens": 0,
                "errors": 0,
                "total_latency_ms": 0,
            }
        transport_summary[transport]["requests"] += 1
        transport_summary[transport]["tokens"] += metadata.get("total_tokens", 0)
        transport_summary[transport]["total_latency_ms"] += event.get("duration_ms", 0)
        if not metadata.get("success", True):
            transport_summary[transport]["errors"] += 1

    for stats in transport_summary.values():
        stats["avg_latency_ms"] = (
            stats["total_latency_ms"] // stats["requests"] if stats["requests"] else 0
        )

    provider_summary: dict[str, dict[str, Any]] = {}
    for event in route_completions:
        metadata = event.get("metadata", {})
        provider = metadata.get("provider", "unknown")
        if provider not in provider_summary:
            provider_summary[provider] = {
                "requests": 0,
                "tokens": 0,
                "errors": 0,
            }
        provider_summary[provider]["requests"] += 1
        provider_summary[provider]["tokens"] += metadata.get("total_tokens", 0)
        if not metadata.get("success", True):
            provider_summary[provider]["errors"] += 1

    agent_summary: dict[str, dict[str, Any]] = {}
    for event in route_completions:
        metadata = event.get("metadata", {})
        agent_id = event.get("agent_id") or "unknown"
        if agent_id not in agent_summary:
            agent_summary[agent_id] = {
                "requests": 0,
                "tokens": 0,
                "errors": 0,
                "transports": set(),
                "providers": set(),
            }
        agent_summary[agent_id]["requests"] += 1
        agent_summary[agent_id]["tokens"] += metadata.get("total_tokens", 0)
        agent_summary[agent_id]["transports"].add(metadata.get("transport", "unknown"))
        agent_summary[agent_id]["providers"].add(metadata.get("provider", "unknown"))
        if not metadata.get("success", True):
            agent_summary[agent_id]["errors"] += 1

    for stats in agent_summary.values():
        stats["transports"] = sorted(stats["transports"])
        stats["providers"] = sorted(stats["providers"])

    planned_routes: dict[str, dict[str, str]] = {}
    for event in route_selections:
        metadata = event.get("metadata", {})
        agent_id = event.get("agent_id") or "unknown"
        planned_routes[agent_id] = {
            "transport": metadata.get("transport", "unknown"),
            "provider": metadata.get("provider", "unknown"),
            "model": metadata.get("model", "unknown"),
            "source": metadata.get("source", "unknown"),
        }

    return {
        "route_selections": route_selections,
        "route_fallbacks": route_fallbacks,
        "route_completions": route_completions,
        "route_requests": route_requests,
        "transport_summary": transport_summary,
        "provider_summary": provider_summary,
        "agent_summary": agent_summary,
        "planned_routes": planned_routes,
        "fallback_count": len(route_fallbacks),
        "total_requests": len(route_completions),
    }


__all__ = [
    "build_event_tree",
    "build_event_tree_from_rows",
    "build_llm_route_streams",
    "build_subprocess_streams",
    "current_phase_from_events",
    "is_terminal_session_event",
]
