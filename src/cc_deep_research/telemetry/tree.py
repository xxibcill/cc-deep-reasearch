"""Telemetry event shaping helpers."""

from __future__ import annotations

import json
import re
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
            event for event in children_by_parent.get(None, []) if is_terminal_session_event(event)
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
    route_selections = [
        event for event in events if event.get("event_type") == "llm.route_selected"
    ]
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


# =============================================================================
# Derived Output Builders for Operator-Facing Summaries
# =============================================================================


def build_narrative(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build a human-readable narrative from ordered semantic events.

    Filters and orders events that contribute to a coherent story of what
    happened during a session, focusing on:
    - Session lifecycle (started, finished)
    - Phase transitions (started, completed, failed)
    - Agent actions (spawned, completed)
    - Decisions made
    - State changes
    - Degradations detected
    - Failures

    Args:
        events: Normalized event records with sequence_number ordering.

    Returns:
        List of narrative-ordered events with human-readable summaries.
    """
    narrative_event_types = {
        # Session lifecycle
        "session.started",
        "session.finished",
        # Phase lifecycle
        "phase.started",
        "phase.completed",
        "phase.failed",
        # Agent lifecycle
        "agent.spawned",
        "agent.completed",
        "agent.failed",
        # Semantic events from Task 001
        "decision.made",
        "state.changed",
        "degradation.detected",
        # Key operation events
        "operation.started",
        "operation.completed",
        "operation.failed",
        # Search and tool highlights
        "search.query",
        "tool.call",
    }

    narrative = []
    for event in events:
        event_type = event.get("event_type", "")
        category = event.get("category", "")

        # Include explicit semantic events
        if event_type in narrative_event_types:
            narrative.append(event)
            continue

        # Include error/failure status events
        status = event.get("status", "")
        severity = event.get("severity", "")
        if status in ("failed", "error", "critical") or severity == "error":
            narrative.append(event)
            continue

        # Include degraded events
        if event.get("degraded"):
            narrative.append(event)
            continue

        # Include category-level events for phases and agents
        if category in ("phase", "session") and event_type.endswith((".started", ".completed", ".failed")):
            narrative.append(event)

    return narrative


def build_critical_path(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Identify the longest-duration chain in the session.

    Analyzes phase, agent, and tool events to find the critical path -
    the sequence of operations that determined overall session duration.

    Args:
        events: Normalized event records with duration_ms fields.

    Returns:
        Dict with:
        - path: ordered list of critical path events
        - total_duration_ms: sum of durations along the path
        - bottleneck_event: the event with longest individual duration
        - bottleneck_duration_ms: duration of bottleneck event
    """
    # Track start events and match with completions
    pending_starts: dict[str, dict[str, Any]] = {}
    completed_chains: list[dict[str, Any]] = []

    for event in events:
        event_type = event.get("event_type", "")
        event_id = event.get("event_id")
        parent_id = event.get("parent_event_id")
        duration_ms = event.get("duration_ms")

        # Track started events
        if event_type.endswith(".started"):
            pending_starts[event_id] = {
                "start_event": event,
                "end_event": None,
                "duration_ms": None,
                "children": [],
            }

        # Match completed events
        if event_type.endswith((".completed", ".failed")) and duration_ms is not None:
            # Find matching start by parent or name
            matched_start = None
            for start_id, chain in pending_starts.items():
                start_event = chain["start_event"]
                if (start_event.get("name") == event.get("name") and
                    start_event.get("category") == event.get("category")):
                    matched_start = start_id
                    break

            if matched_start:
                pending_starts[matched_start]["end_event"] = event
                pending_starts[matched_start]["duration_ms"] = duration_ms

    # Find longest duration chains
    phase_events = []
    agent_events = []
    tool_events = []

    for chain in pending_starts.values():
        if chain["duration_ms"] is None:
            continue

        start_event = chain["start_event"]
        category = start_event.get("category", "")
        entry = {
            "start_event": start_event,
            "end_event": chain["end_event"],
            "duration_ms": chain["duration_ms"],
        }

        if category == "phase":
            phase_events.append(entry)
        elif category == "agent":
            agent_events.append(entry)
        elif "tool" in start_event.get("event_type", ""):
            tool_events.append(entry)

    # Sort by duration descending
    phase_events.sort(key=lambda x: x["duration_ms"] or 0, reverse=True)
    agent_events.sort(key=lambda x: x["duration_ms"] or 0, reverse=True)
    tool_events.sort(key=lambda x: x["duration_ms"] or 0, reverse=True)

    # Build critical path from longest chain
    path = []

    # Add longest phase if available
    if phase_events:
        phase = phase_events[0]
        path.append({
            "type": "phase",
            "name": phase["start_event"].get("name"),
            "duration_ms": phase["duration_ms"],
            "start_event_id": phase["start_event"].get("event_id"),
            "end_event_id": phase["end_event"].get("event_id") if phase["end_event"] else None,
        })

    # Add longest agent in that phase if available
    if agent_events:
        agent = agent_events[0]
        path.append({
            "type": "agent",
            "name": agent["start_event"].get("name") or agent["start_event"].get("agent_id"),
            "agent_id": agent["start_event"].get("agent_id"),
            "duration_ms": agent["duration_ms"],
            "start_event_id": agent["start_event"].get("event_id"),
            "end_event_id": agent["end_event"].get("event_id") if agent["end_event"] else None,
        })

    # Add longest tool call if available
    if tool_events:
        tool = tool_events[0]
        path.append({
            "type": "tool",
            "name": tool["start_event"].get("name"),
            "duration_ms": tool["duration_ms"],
            "start_event_id": tool["start_event"].get("event_id"),
            "end_event_id": tool["end_event"].get("event_id") if tool["end_event"] else None,
        })

    # Calculate total duration
    total_duration = sum(p.get("duration_ms", 0) or 0 for p in path)

    # Find bottleneck (longest single event)
    bottleneck = None
    bottleneck_duration = 0
    for event in events:
        duration = event.get("duration_ms")
        if duration is not None and duration > bottleneck_duration:
            bottleneck_duration = duration
            bottleneck = event

    return {
        "path": path,
        "total_duration_ms": total_duration,
        "bottleneck_event": {
            "event_id": bottleneck.get("event_id") if bottleneck else None,
            "event_type": bottleneck.get("event_type") if bottleneck else None,
            "name": bottleneck.get("name") if bottleneck else None,
            "duration_ms": bottleneck_duration,
        } if bottleneck else None,
        "phase_durations": [
            {
                "phase": p["start_event"].get("name"),
                "duration_ms": p["duration_ms"],
            }
            for p in phase_events[:5]  # Top 5 phases
        ],
    }


def build_state_changes(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract explicit state transition events.

    Collects state.changed events (from Task 001 contract) that represent
    before/after transitions, eliminating the need for session-store diffs.

    Args:
        events: Normalized event records.

    Returns:
        List of state change events with before/after values.
    """
    state_changes = []

    for event in events:
        event_type = event.get("event_type", "")

        # Explicit state.changed events from Task 001
        if event_type == "state.changed":
            metadata = event.get("metadata", {})
            state_changes.append({
                "event_id": event.get("event_id"),
                "sequence_number": event.get("sequence_number"),
                "timestamp": event.get("timestamp"),
                "state_scope": metadata.get("state_scope"),
                "state_key": metadata.get("state_key"),
                "before": metadata.get("before"),
                "after": metadata.get("after"),
                "change_type": metadata.get("change_type"),
                "caused_by_event_id": metadata.get("caused_by_event_id"),
            })
            continue

        # Infer state changes from phase transitions
        if event_type in ("phase.started", "phase.completed", "phase.failed"):
            phase_name = event.get("name")
            status = "running" if event_type == "phase.started" else event.get("status", "completed")

            state_changes.append({
                "event_id": event.get("event_id"),
                "sequence_number": event.get("sequence_number"),
                "timestamp": event.get("timestamp"),
                "state_scope": "phase",
                "state_key": phase_name,
                "before": None,  # Would need tracking
                "after": status,
                "change_type": "phase_transition",
                "caused_by_event_id": event.get("parent_event_id"),
            })

    return state_changes


def build_decisions(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract decision events from the session.

    Collects decision.made events (from Task 001 contract) that represent
    planner, routing, follow-up, and stop decisions.

    Args:
        events: Normalized event records.

    Returns:
        List of decision events with chosen options and reasoning.
    """
    decisions = []

    for event in events:
        event_type = event.get("event_type", "")

        # Explicit decision.made events from Task 001
        if event_type == "decision.made":
            metadata = event.get("metadata", {})
            decisions.append({
                "event_id": event.get("event_id"),
                "sequence_number": event.get("sequence_number"),
                "timestamp": event.get("timestamp"),
                "decision_type": metadata.get("decision_type"),
                "reason_code": event.get("reason_code") or metadata.get("reason_code"),
                "chosen_option": metadata.get("chosen_option"),
                "inputs": metadata.get("inputs"),
                "rejected_options": metadata.get("rejected_options"),
                "confidence": metadata.get("confidence"),
                "cause_event_ids": metadata.get("cause_event_ids"),
                "actor_id": event.get("actor_id") or event.get("agent_id"),
            })

    return decisions


def build_degradations(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract degradation events from the session.

    Collects degradation.detected events (from Task 001 contract) that represent
    successful-but-impaired execution and partial recovery paths.

    Args:
        events: Normalized event records.

    Returns:
        List of degradation events with severity and scope.
    """
    degradations = []

    for event in events:
        event_type = event.get("event_type", "")
        degraded = event.get("degraded", False)
        status = event.get("status", "")
        severity = event.get("severity", "")

        # Explicit degradation.detected events from Task 001
        if event_type == "degradation.detected":
            metadata = event.get("metadata", {})
            degradations.append({
                "event_id": event.get("event_id"),
                "sequence_number": event.get("sequence_number"),
                "timestamp": event.get("timestamp"),
                "reason_code": event.get("reason_code") or metadata.get("reason_code"),
                "severity": severity or metadata.get("severity"),
                "scope": metadata.get("scope"),
                "recoverable": metadata.get("recoverable"),
                "mitigation": metadata.get("mitigation"),
                "caused_by_event_id": metadata.get("caused_by_event_id"),
                "impact": metadata.get("impact"),
            })
            continue

        # Infer degradations from degraded status
        if degraded or status in ("fallback", "degraded") or severity == "warning":
            metadata = event.get("metadata", {})
            degradations.append({
                "event_id": event.get("event_id"),
                "sequence_number": event.get("sequence_number"),
                "timestamp": event.get("timestamp"),
                "reason_code": event.get("reason_code") or metadata.get("reason"),
                "severity": severity or "warning",
                "scope": event.get("phase") or metadata.get("scope"),
                "recoverable": status != "failed",
                "mitigation": None,
                "caused_by_event_id": event.get("cause_event_id"),
                "impact": None,
                "inferred": True,  # Mark as inferred
            })

    return degradations


def build_failures(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract failure and error events from the session.

    Collects events that represent failures, errors, and critical issues
    that affected session execution.

    Args:
        events: Normalized event records.

    Returns:
        List of failure events with error details.
    """
    failures = []

    for event in events:
        event_type = event.get("event_type", "")
        status = event.get("status", "")
        severity = event.get("severity", "")

        # Check for failure indicators
        is_failure = (
            event_type.endswith(".failed") or
            event_type.endswith(".error") or
            status in ("failed", "error", "critical") or
            severity == "error"
        )

        if is_failure:
            metadata = event.get("metadata", {})
            failures.append({
                "event_id": event.get("event_id"),
                "sequence_number": event.get("sequence_number"),
                "timestamp": event.get("timestamp"),
                "event_type": event_type,
                "category": event.get("category"),
                "name": event.get("name"),
                "status": status,
                "severity": severity,
                "reason_code": event.get("reason_code") or metadata.get("reason") or metadata.get("error"),
                "error_message": metadata.get("error") or metadata.get("message"),
                "phase": event.get("phase"),
                "actor_id": event.get("actor_id") or event.get("agent_id"),
                "duration_ms": event.get("duration_ms"),
                "recoverable": metadata.get("recoverable", False),
                "stack_trace": metadata.get("stack_trace"),
            })

    return failures


def empty_decision_graph() -> dict[str, Any]:
    """Return the stable empty graph payload used across APIs and bundles."""
    return {
        "nodes": [],
        "edges": [],
        "summary": {
            "node_count": 0,
            "edge_count": 0,
            "explicit_edge_count": 0,
            "inferred_edge_count": 0,
        },
    }


def _decision_graph_sort_key(event: dict[str, Any]) -> tuple[int, str, str]:
    """Return a stable ordering key for telemetry records."""
    return (
        int(event.get("sequence_number") or 0),
        str(event.get("timestamp") or ""),
        str(event.get("event_id") or ""),
    )


def _sanitize_graph_id(value: Any, *, fallback: str) -> str:
    """Return a stable identifier fragment safe to embed in node IDs."""
    text = str(value or "").strip().lower()
    if not text:
        return fallback
    normalized = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return normalized or fallback


def _is_failure_event(event: dict[str, Any]) -> bool:
    """Return whether the event should appear as a failure node."""
    event_type = str(event.get("event_type") or "")
    status = str(event.get("status") or "")
    severity = str(event.get("severity") or "")
    return (
        event_type.endswith(".failed")
        or event_type.endswith(".error")
        or status in {"failed", "error", "critical"}
        or severity == "error"
    )


def _decision_graph_primary_kind(event: dict[str, Any]) -> str | None:
    """Return the graph node kind for a first-class telemetry record."""
    event_type = str(event.get("event_type") or "")
    if event_type == "decision.made":
        return "decision"
    if event_type == "state.changed":
        return "state_change"
    if event_type == "degradation.detected":
        return "degradation"
    if _is_failure_event(event):
        return "failure"
    return None


def _decision_graph_label(event: dict[str, Any], *, kind: str) -> str:
    """Build a concise human-readable node label."""
    metadata = event.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}

    if kind == "decision":
        decision_type = metadata.get("decision_type") or event.get("name") or "decision"
        chosen_option = metadata.get("chosen_option")
        if chosen_option:
            return f"{decision_type}: {chosen_option}"
        return str(decision_type)

    if kind == "state_change":
        state_scope = metadata.get("state_scope") or "state"
        state_key = metadata.get("state_key") or event.get("name") or "change"
        after = metadata.get("after")
        if after is not None:
            return f"{state_scope}.{state_key} -> {after}"
        return f"{state_scope}.{state_key}"

    if kind == "degradation":
        scope = metadata.get("scope")
        reason = event.get("reason_code") or metadata.get("reason_code") or event.get("name")
        if scope and reason:
            return f"{scope}: {reason}"
        return str(reason or "degradation")

    if kind == "failure":
        return str(event.get("name") or event.get("event_type") or "failure")

    return str(event.get("name") or event.get("event_type") or event.get("event_id") or kind)


def _decision_graph_node_payload(
    *,
    node_id: str,
    kind: str,
    label: str,
    event: dict[str, Any] | None,
    inferred: bool = False,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the JSON-first node payload shared across graph kinds."""
    event_metadata = event.get("metadata", {}) if isinstance(event, dict) else {}
    merged_metadata = dict(event_metadata) if isinstance(event_metadata, dict) else {}
    if metadata:
        merged_metadata.update(metadata)

    return {
        "id": node_id,
        "kind": kind,
        "label": label,
        "event_id": event.get("event_id") if isinstance(event, dict) else None,
        "sequence_number": event.get("sequence_number") if isinstance(event, dict) else None,
        "timestamp": event.get("timestamp") if isinstance(event, dict) else None,
        "event_type": event.get("event_type") if isinstance(event, dict) else None,
        "actor_id": (
            event.get("actor_id") or event.get("agent_id")
            if isinstance(event, dict)
            else None
        ),
        "status": event.get("status") if isinstance(event, dict) else None,
        "severity": event.get("severity") if isinstance(event, dict) else None,
        "inferred": inferred,
        "metadata": merged_metadata,
    }


def _decision_graph_edge_payload(
    *,
    source: str,
    target: str,
    kind: str,
    inferred: bool,
) -> dict[str, Any]:
    """Build the portable edge payload."""
    relation = "inferred" if inferred else "explicit"
    return {
        "id": f"{kind}:{source}:{target}:{relation}",
        "source": source,
        "target": target,
        "kind": kind,
        "inferred": inferred,
    }


def _decision_graph_cause_ids(event: dict[str, Any]) -> list[str]:
    """Collect explicit cause references from a telemetry event."""
    metadata = event.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}

    candidate_values: list[Any] = [
        event.get("cause_event_id"),
        event.get("parent_event_id"),
        metadata.get("caused_by_event_id"),
    ]
    cause_event_ids = metadata.get("cause_event_ids")
    if isinstance(cause_event_ids, list):
        candidate_values.extend(cause_event_ids)

    causes: list[str] = []
    seen: set[str] = set()
    for value in candidate_values:
        if not isinstance(value, str):
            continue
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        causes.append(normalized)
    return causes


def build_decision_graph(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a causal decision graph from existing telemetry events.

    The graph favors correctness over density:
    - explicit `caused_by` edges come directly from telemetry fields
    - inferred edges are limited to deterministic domain links derived from
      those explicit cause references
    """
    if not events:
        return empty_decision_graph()

    sorted_events = sorted(events, key=_decision_graph_sort_key)
    events_by_id = {
        str(event.get("event_id")): event
        for event in sorted_events
        if isinstance(event.get("event_id"), str)
    }
    nodes: dict[str, dict[str, Any]] = {}
    event_node_ids: dict[str, str] = {}
    explicit_causes_by_node: dict[str, list[str]] = {}
    edges: dict[tuple[str, str, str, bool], dict[str, Any]] = {}

    def add_node(node: dict[str, Any]) -> None:
        nodes[node["id"]] = node

    def add_edge(*, source: str, target: str, kind: str, inferred: bool) -> None:
        if source == target:
            return
        key = (source, target, kind, inferred)
        if key in edges:
            return
        edges[key] = _decision_graph_edge_payload(
            source=source,
            target=target,
            kind=kind,
            inferred=inferred,
        )

    def ensure_event_node(event_id: str) -> str:
        primary_node_id = event_node_ids.get(event_id)
        if primary_node_id is not None:
            return primary_node_id

        cause_event = events_by_id.get(event_id)
        node_id = f"event:{event_id}"
        if node_id in nodes:
            event_node_ids[event_id] = node_id
            return node_id

        label = (
            _decision_graph_label(cause_event, kind="event")
            if cause_event is not None
            else event_id
        )
        add_node(
            _decision_graph_node_payload(
                node_id=node_id,
                kind="event",
                label=label,
                event=cause_event,
                metadata={"placeholder": cause_event is None},
            )
        )
        event_node_ids[event_id] = node_id
        return node_id

    for event in sorted_events:
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            continue

        kind = _decision_graph_primary_kind(event)
        if kind is None:
            continue

        node_id = f"{kind}:{event_id}"
        add_node(
            _decision_graph_node_payload(
                node_id=node_id,
                kind=kind,
                label=_decision_graph_label(event, kind=kind),
                event=event,
            )
        )
        event_node_ids[event_id] = node_id

        explicit_causes = _decision_graph_cause_ids(event)
        explicit_causes_by_node[node_id] = explicit_causes
        for cause_event_id in explicit_causes:
            add_edge(
                source=node_id,
                target=ensure_event_node(cause_event_id),
                kind="caused_by",
                inferred=False,
            )

        if kind != "decision":
            continue

        metadata = event.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        chosen_option = metadata.get("chosen_option")
        if isinstance(chosen_option, str) and chosen_option.strip():
            chosen_node_id = f"outcome:{event_id}:chosen"
            add_node(
                _decision_graph_node_payload(
                    node_id=chosen_node_id,
                    kind="outcome",
                    label=chosen_option.strip(),
                    event=event,
                    metadata={"decision_event_id": event_id, "outcome": "chosen"},
                )
            )
            add_edge(
                source=node_id,
                target=chosen_node_id,
                kind="produced",
                inferred=False,
            )

        rejected_options = metadata.get("rejected_options")
        if isinstance(rejected_options, list):
            for index, option in enumerate(rejected_options):
                if not isinstance(option, str) or not option.strip():
                    continue
                normalized_option = option.strip()
                rejected_node_id = (
                    f"outcome:{event_id}:rejected:{index}:"
                    f"{_sanitize_graph_id(normalized_option, fallback=str(index))}"
                )
                add_node(
                    _decision_graph_node_payload(
                        node_id=rejected_node_id,
                        kind="outcome",
                        label=normalized_option,
                        event=event,
                        metadata={
                            "decision_event_id": event_id,
                            "outcome": "rejected",
                        },
                    )
                )
                add_edge(
                    source=node_id,
                    target=rejected_node_id,
                    kind="rejected",
                    inferred=False,
                )

    degradation_candidates: list[dict[str, Any]] = []
    for node in nodes.values():
        if node["kind"] == "degradation":
            degradation_candidates.append(node)

    degradation_candidates.sort(
        key=lambda node: (
            int(node.get("sequence_number") or 0),
            str(node.get("timestamp") or ""),
            str(node.get("id") or ""),
        )
    )

    for node_id, cause_ids in explicit_causes_by_node.items():
        node = nodes.get(node_id)
        if node is None:
            continue

        if node["kind"] == "state_change":
            for cause_event_id in cause_ids:
                cause_node_id = event_node_ids.get(cause_event_id)
                cause_node = nodes.get(cause_node_id) if cause_node_id else None
                if cause_node is None or cause_node["kind"] != "decision":
                    continue
                add_edge(
                    source=cause_node["id"],
                    target=node_id,
                    kind="produced",
                    inferred=True,
                )

        if node["kind"] != "failure":
            continue

        linked_degradation_ids = [
            event_node_ids[cause_event_id]
            for cause_event_id in cause_ids
            if event_node_ids.get(cause_event_id) in nodes
            and nodes[event_node_ids[cause_event_id]]["kind"] == "degradation"
        ]
        if linked_degradation_ids:
            for degradation_node_id in linked_degradation_ids:
                add_edge(
                    source=degradation_node_id,
                    target=node_id,
                    kind="led_to",
                    inferred=True,
                )
            continue

        shared_degradation = next(
            (
                candidate
                for candidate in reversed(degradation_candidates)
                if int(candidate.get("sequence_number") or -1)
                < int(node.get("sequence_number") or -1)
                and set(explicit_causes_by_node.get(candidate["id"], [])) & set(cause_ids)
            ),
            None,
        )
        if shared_degradation is not None:
            add_edge(
                source=shared_degradation["id"],
                target=node_id,
                kind="led_to",
                inferred=True,
            )

    graph = {
        "nodes": sorted(
            nodes.values(),
            key=lambda node: (
                int(node.get("sequence_number") or 0),
                str(node.get("timestamp") or ""),
                str(node.get("id") or ""),
            ),
        ),
        "edges": sorted(
            edges.values(),
            key=lambda edge: (edge["source"], edge["target"], edge["kind"], edge["inferred"]),
        ),
    }
    graph["summary"] = {
        "node_count": len(graph["nodes"]),
        "edge_count": len(graph["edges"]),
        "explicit_edge_count": sum(1 for edge in graph["edges"] if not edge["inferred"]),
        "inferred_edge_count": sum(1 for edge in graph["edges"] if edge["inferred"]),
    }
    return graph


def build_derived_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Build all derived outputs for a session.

    Convenience function that computes all derived operator-facing
    summaries in a single call.

    Args:
        events: Normalized event records.

    Returns:
        Dict with all derived outputs:
        - narrative
        - critical_path
        - state_changes
        - decisions
        - degradations
        - failures
        - decision_graph
        - active_phase
    """
    return {
        "narrative": build_narrative(events),
        "critical_path": build_critical_path(events),
        "state_changes": build_state_changes(events),
        "decisions": build_decisions(events),
        "degradations": build_degradations(events),
        "failures": build_failures(events),
        "decision_graph": build_decision_graph(events),
        "active_phase": current_phase_from_events(events),
    }


__all__ = [
    "build_critical_path",
    "build_decisions",
    "build_degradations",
    "build_decision_graph",
    "build_derived_summary",
    "build_event_tree",
    "build_event_tree_from_rows",
    "build_failures",
    "build_llm_route_streams",
    "build_narrative",
    "build_state_changes",
    "build_subprocess_streams",
    "current_phase_from_events",
    "empty_decision_graph",
    "is_terminal_session_event",
]
