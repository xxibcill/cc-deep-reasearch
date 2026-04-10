"""Monitoring infrastructure for research workflow visibility."""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import click

from cc_deep_research.config import get_default_config_path
from cc_deep_research.models import QueryFamily, SearchResultItem

# Trace schema version
TRACE_VERSION = "1.0.0"

# Severity levels for events
SEVERITY_DEBUG = "debug"
SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_ERROR = "error"
SEVERITY_CRITICAL = "critical"

# Reason codes (stable, enumerable)
REASON_SUCCESS = "success"
REASON_FALLBACK = "fallback"
REASON_TIMEOUT = "timeout"
REASON_UNAVAILABLE = "unavailable"
REASON_LIMIT_REACHED = "limit_reached"
REASON_LOW_QUALITY = "low_quality"
REASON_DEGRADED = "degraded"
REASON_CANCELLED = "cancelled"
REASON_ERROR = "error"

# Stop reasons (legacy aliases)
STOP_REASON_SUCCESS = REASON_SUCCESS
STOP_REASON_LIMIT_REACHED = REASON_LIMIT_REACHED
STOP_REASON_LOW_QUALITY = REASON_LOW_QUALITY
STOP_REASON_DEGRADED_EXECUTION = REASON_DEGRADED

KNOWN_STOP_REASONS = {
    STOP_REASON_SUCCESS,
    STOP_REASON_LIMIT_REACHED,
    STOP_REASON_LOW_QUALITY,
    STOP_REASON_DEGRADED_EXECUTION,
}


@dataclass
class MonitorEvent:
    """Represents a single monitored operation."""

    name: str
    category: str  # config, provider, aggregation, deduplication, etc.
    start_time: float
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_event_id: str | None = None
    sequence_number: int = 0
    end_time: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    status: str = "in_progress"  # in_progress, completed, failed

    @property
    def duration_ms(self) -> int:
        """Get duration in milliseconds."""
        if self.end_time is None:
            return 0
        return int((self.end_time - self.start_time) * 1000)


class ResearchMonitor:
    """Monitor for research operations with structured output and telemetry."""

    def __init__(
        self,
        enabled: bool = False,
        persist: bool = True,
        telemetry_dir: Path | None = None,
        event_router: Any | None = None,
    ) -> None:
        """Initialize the monitor.

        Args:
            enabled: Whether console monitoring output is active.
            persist: Whether telemetry events should be persisted to disk.
            telemetry_dir: Base directory for telemetry session folders.
            event_router: Optional EventRouter for real-time event streaming.
        """
        self._enabled = enabled
        self._persist = persist
        self._events: list[MonitorEvent] = []
        self._telemetry_events: list[dict[str, Any]] = []
        self._start_time = time.time()

        self._session_id: str | None = None
        default_telemetry_dir = get_default_config_path().parent / "telemetry"
        self._telemetry_dir = Path(telemetry_dir) if telemetry_dir else default_telemetry_dir
        self._session_dir: Path | None = None
        self._events_path: Path | None = None
        self._summary_path: Path | None = None

        # Real-time event routing
        self._event_router = event_router

        # Event correlation support
        self._sequence_counter: int = 0
        self._parent_stack: list[str] = []  # Stack of parent event IDs
        self._emit_lock = threading.Lock()

    @staticmethod
    def normalize_stop_reason(stop_reason: str | None) -> str:
        """Return a supported stop-reason label."""
        normalized = (stop_reason or STOP_REASON_SUCCESS).strip().lower().replace("-", "_")
        if normalized in KNOWN_STOP_REASONS:
            return normalized
        return STOP_REASON_DEGRADED_EXECUTION

    def _get_timestamp(self) -> str:
        """Get formatted timestamp for log messages."""
        return datetime.now().strftime("%H:%M:%S")

    def _get_utc_timestamp(self) -> str:
        """Get UTC timestamp for telemetry payloads."""
        return datetime.now(UTC).isoformat()

    def is_enabled(self) -> bool:
        """Check if monitoring is enabled."""
        return self._enabled

    @property
    def session_id(self) -> str | None:
        """Return current session id if initialized."""
        return self._session_id

    @property
    def real_time_enabled(self) -> bool:
        """Check if real-time streaming is active."""
        return self._event_router is not None and self._event_router.is_active()

    def set_event_router(self, event_router: Any | None) -> None:
        """Attach or clear the event router used for real-time delivery."""
        self._event_router = event_router

    def set_session(
        self,
        session_id: str,
        query: str,
        depth: str,
        *,
        run_id: str | None = None,
        **metadata: Any,
    ) -> str:
        """Set active session and initialize persistent telemetry files.

        Args:
            session_id: Unique session identifier.
            query: The research query.
            depth: Research depth (quick, standard, deep).
            run_id: Optional run ID for grouping related sessions.
            **metadata: Additional session metadata.

        Returns:
            The session event ID for correlation purposes.
        """
        self._session_id = session_id
        self._run_id = run_id
        self._sequence_counter = 0  # Reset sequence for new session
        self._parent_stack = []  # Clear parent stack for new session

        if self._persist:
            self._session_dir = self._telemetry_dir / session_id
            self._session_dir.mkdir(parents=True, exist_ok=True)
            self._events_path = self._session_dir / "events.jsonl"
            self._summary_path = self._session_dir / "summary.json"

        session_event_id = self.emit_event(
            event_type="session.started",
            category="session",
            name="research-session",
            status="started",
            metadata={"query": query, "depth": depth, **metadata},
        )

        # Push session event as initial parent
        self.push_parent(session_event_id)

        return session_event_id

    def _generate_event_id(self) -> str:
        """Generate a unique event ID."""
        return str(uuid.uuid4())

    def _get_next_sequence(self) -> int:
        """Get the next sequence number for event ordering."""
        self._sequence_counter += 1
        return self._sequence_counter

    @property
    def current_parent_id(self) -> str | None:
        """Return the current parent event ID from the stack, if any."""
        return self._parent_stack[-1] if self._parent_stack else None

    def push_parent(self, event_id: str) -> None:
        """Push an event ID onto the parent stack for child event correlation."""
        self._parent_stack.append(event_id)

    def pop_parent(self) -> str | None:
        """Pop and return the current parent event ID from the stack."""
        return self._parent_stack.pop() if self._parent_stack else None

    def emit_event(
        self,
        event_type: str,
        category: str,
        name: str,
        status: str = "info",
        duration_ms: int | None = None,
        agent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        event_id: str | None = None,
        parent_event_id: str | None = None,
        *,
        cause_event_id: str | None = None,
        phase: str | None = None,
        operation: str | None = None,
        attempt: int = 1,
        severity: str = SEVERITY_INFO,
        reason_code: str | None = None,
        degraded: bool = False,
    ) -> str:
        """Emit a structured telemetry event and persist it when configured.

        Args:
            event_type: The type of event (e.g., 'session.started', 'phase.completed').
            category: The event category (e.g., 'session', 'phase', 'agent').
            name: A human-readable name for the event.
            status: The event status (e.g., 'started', 'completed', 'failed').
            duration_ms: Optional duration in milliseconds.
            agent_id: Optional agent identifier.
            metadata: Optional structured metadata payload.
            event_id: Optional explicit event ID (auto-generated if not provided).
            parent_event_id: Optional parent event ID for correlation.
                If not provided, uses the current parent from the stack.
            cause_event_id: Optional ID of the event that caused this event.
            phase: The current execution phase (e.g., 'planning', 'collection').
            operation: The specific operation name.
            attempt: Retry count (default 1).
            severity: Event severity level (default 'info').
            reason_code: Standardized reason code for the event.
            degraded: Whether this event indicates a degraded state.

        Returns:
            The event ID for correlation purposes.
        """
        # Use provided event_id or generate one
        actual_event_id = event_id or self._generate_event_id()

        # Use provided parent_event_id or the current stack top
        actual_parent_id = parent_event_id
        if actual_parent_id is None and self._parent_stack:
            actual_parent_id = self._parent_stack[-1]

        # Derive actor_type from agent_id presence
        actor_type = "agent" if agent_id else "system"

        # Auto-infer degraded from status patterns
        inferred_degraded = degraded or (
            status in ("failed", "fallback", "degraded")
            or "fallback" in event_type
            or "degraded" in event_type
        )

        with self._emit_lock:
            payload = {
                # Core identity
                "event_id": actual_event_id,
                "parent_event_id": actual_parent_id,
                "sequence_number": self._get_next_sequence(),
                "timestamp": self._get_utc_timestamp(),
                "session_id": self._session_id,
                # Trace contract
                "trace_version": TRACE_VERSION,
                "run_id": getattr(self, "_run_id", None),
                "cause_event_id": cause_event_id,
                # Event classification
                "event_type": event_type,
                "category": category,
                "name": name,
                "status": status,
                "severity": severity,
                "reason_code": reason_code,
                # Execution context
                "phase": phase,
                "operation": operation or name,
                "attempt": attempt,
                # Actor
                "actor_type": actor_type,
                "actor_id": agent_id,  # Renamed for consistency but keep agent_id for backward compat
                "agent_id": agent_id,  # Keep for backward compatibility
                # Metrics
                "duration_ms": duration_ms,
                "degraded": inferred_degraded,
                # Payload
                "metadata": metadata or {},
            }
            self._telemetry_events.append(payload)
            if self._persist and self._events_path is not None:
                with open(self._events_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(payload, ensure_ascii=True))
                    f.write("\n")

        # Publish to event router for real-time delivery
        if self._event_router and self._session_id:
            import asyncio

            # Create async task to publish (non-blocking)
            try:
                asyncio.get_running_loop()
                asyncio.create_task(self._event_router.publish(self._session_id, payload))
            except RuntimeError:
                # No event loop running, skip publishing
                pass

        return actual_event_id

    def emit_decision_made(
        self,
        *,
        decision_type: str,
        reason_code: str,
        chosen_option: str,
        inputs: dict[str, Any],
        rejected_options: list[str] | None = None,
        cause_event_ids: list[str] | None = None,
        confidence: float | None = None,
        phase: str | None = None,
        operation: str | None = None,
        actor_id: str | None = None,
    ) -> str:
        """Emit a structured decision event for routing, planning, or control decisions.

        Args:
            decision_type: Type of decision (routing, planning, follow_up, stop).
            reason_code: Standardized reason code for the decision.
            chosen_option: The option that was selected.
            inputs: The inputs that informed the decision.
            rejected_options: Options that were considered but not chosen.
            cause_event_ids: IDs of events that triggered this decision.
            confidence: Optional confidence score (0.0-1.0).
            phase: Current execution phase.
            operation: Specific operation name.
            actor_id: ID of the agent making the decision (if applicable).

        Returns:
            The event ID for correlation purposes.
        """
        # Use first cause_event_id as primary cause
        cause_event_id = cause_event_ids[0] if cause_event_ids else None

        return self.emit_event(
            event_type="decision.made",
            category="decision",
            name=decision_type,
            status="decided",
            agent_id=actor_id,
            cause_event_id=cause_event_id,
            phase=phase,
            operation=operation or f"decision.{decision_type}",
            severity=SEVERITY_INFO,
            reason_code=reason_code,
            metadata={
                "decision_type": decision_type,
                "chosen_option": chosen_option,
                "rejected_options": rejected_options or [],
                "inputs": inputs,
                "cause_event_ids": cause_event_ids or [],
                "confidence": confidence,
            },
        )

    def emit_state_changed(
        self,
        *,
        state_scope: str,
        state_key: str,
        before: Any,
        after: Any,
        change_type: str = "update",
        caused_by_event_id: str | None = None,
        checkpoint: str | None = None,
        phase: str | None = None,
    ) -> str:
        """Emit a state change event for tracking session/provider/route state transitions.

        Args:
            state_scope: Scope of the state (session, provider, route, collection).
            state_key: The specific state key that changed.
            before: The value before the change.
            after: The value after the change.
            change_type: Type of change (set, update, delete).
            caused_by_event_id: ID of the event that caused this state change.
            checkpoint: Optional checkpoint identifier for recovery.
            phase: Current execution phase.

        Returns:
            The event ID for correlation purposes.
        """
        return self.emit_event(
            event_type="state.changed",
            category="state",
            name=f"{state_scope}.{state_key}",
            status="changed",
            cause_event_id=caused_by_event_id,
            phase=phase,
            operation=f"state.{state_scope}.{change_type}",
            severity=SEVERITY_INFO,
            metadata={
                "state_scope": state_scope,
                "state_key": state_key,
                "before": before,
                "after": after,
                "change_type": change_type,
                "checkpoint": checkpoint,
            },
        )

    def emit_degradation_detected(
        self,
        *,
        reason_code: str,
        severity: str = SEVERITY_WARNING,
        scope: str = "execution",
        recoverable: bool = True,
        mitigation: str | None = None,
        caused_by_event_id: str | None = None,
        impact: str | None = None,
        phase: str | None = None,
        actor_id: str | None = None,
    ) -> str:
        """Emit a degradation event when execution quality or availability is compromised.

        Args:
            reason_code: Standardized reason code for the degradation.
            severity: Severity level (warning, error, critical).
            scope: Scope of degradation (transport, provider, analysis, collection).
            recoverable: Whether the degradation can be recovered from.
            mitigation: Description of mitigation action taken.
            caused_by_event_id: ID of the event that caused the degradation.
            impact: Description of the impact on execution.
            phase: Current execution phase.
            actor_id: ID of the affected agent (if applicable).

        Returns:
            The event ID for correlation purposes.
        """
        return self.emit_event(
            event_type="degradation.detected",
            category="degradation",
            name=f"{scope}.degraded",
            status="degraded",
            agent_id=actor_id,
            cause_event_id=caused_by_event_id,
            phase=phase,
            operation=f"degradation.{scope}",
            severity=severity,
            reason_code=reason_code,
            degraded=True,
            metadata={
                "scope": scope,
                "recoverable": recoverable,
                "mitigation": mitigation,
                "impact": impact,
            },
        )

    def record_timeout_policy(
        self,
        *,
        scope: str,
        timeout_seconds: float,
        actor_id: str | None = None,
        **metadata: Any,
    ) -> str:
        """Record the timeout policy used for a scoped orchestration step."""
        return self.emit_decision_made(
            decision_type="timeout_policy",
            reason_code="timeout_policy",
            chosen_option=f"{timeout_seconds:.3f}s",
            inputs={
                "scope": scope,
                "timeout_seconds": timeout_seconds,
                **metadata,
            },
            actor_id=actor_id,
        )

    def record_retry_decision(
        self,
        *,
        task_id: str,
        attempt: int,
        max_attempts: int,
        should_retry: bool,
        reason_code: str,
        actor_id: str | None = None,
        **metadata: Any,
    ) -> str:
        """Record the retry decision made after a task failure."""
        return self.emit_decision_made(
            decision_type="retry",
            reason_code=reason_code,
            chosen_option="retry" if should_retry else "stop",
            inputs={
                "task_id": task_id,
                "attempt": attempt,
                "max_attempts": max_attempts,
                "should_retry": should_retry,
                **metadata,
            },
            actor_id=actor_id,
        )

    def section(self, name: str) -> None:
        """Start a new section with a header."""
        if not self._enabled:
            return
        click.echo(f"[{self._get_timestamp()}] === {name} ===")

    def log(self, message: str, indent: int = 0) -> None:
        """Log a message."""
        if not self._enabled:
            return
        prefix = " " * indent
        click.echo(f"[{self._get_timestamp()}] {prefix}{message}")

    def log_result(self, provider: str, count: int, duration_ms: int) -> None:
        """Log search results from a provider."""
        if not self._enabled:
            return
        click.echo(
            f"[{self._get_timestamp()}] [{provider.upper()}] Response received: {count} results ({duration_ms}ms)"
        )

    def log_aggregation(self, before: int, after: int) -> None:
        """Log aggregation deduplication statistics."""
        if not self._enabled:
            return
        removed = before - after
        click.echo(
            f"[{self._get_timestamp()}] [AGGREGATOR] Deduplicated: {removed} duplicate(s) removed, "
            f"{after} unique result(s)"
        )

    def log_timing(self, operation: str, duration_ms: int) -> None:
        """Log timing information for an operation."""
        if not self._enabled:
            return
        click.echo(f"[{self._get_timestamp()}] {operation} completed in {duration_ms}ms")

    def summary(self, total_sources: int, providers: list[str], total_time_ms: int) -> None:
        """Display final summary of the research session."""
        if not self._enabled:
            return
        providers_str = ", ".join(providers) if providers else "none"
        total_time_sec = total_time_ms / 1000
        click.echo(f"[{self._get_timestamp()}] Total sources: {total_sources}")
        click.echo(f"[{self._get_timestamp()}] Providers used: {providers_str}")
        click.echo(f"[{self._get_timestamp()}] Total execution time: {total_time_sec:.1f}s")

    def start_operation(self, name: str, category: str, **metadata: Any) -> MonitorEvent:
        """Start tracking an operation."""
        event_id = self._generate_event_id()
        parent_id = self.current_parent_id

        event = MonitorEvent(
            name=name,
            category=category,
            start_time=time.time(),
            event_id=event_id,
            parent_event_id=parent_id,
            metadata=metadata,
        )
        if self._enabled:
            self._events.append(event)

        self.emit_event(
            event_type="operation.started",
            category=category,
            name=name,
            status="started",
            metadata=metadata,
            event_id=event_id,
            parent_event_id=parent_id,
        )
        return event

    def end_operation(self, event: MonitorEvent, success: bool = True) -> None:
        """Mark an operation as complete."""
        event.end_time = time.time()
        event.status = "completed" if success else "failed"
        self.emit_event(
            event_type="operation.finished",
            category=event.category,
            name=event.name,
            status=event.status,
            duration_ms=event.duration_ms,
            metadata=event.metadata,
            event_id=event.event_id,
            parent_event_id=event.parent_event_id,
        )

    def record_metric(self, name: str, value: Any, category: str) -> None:
        """Record a metric value."""
        if self._enabled:
            event = MonitorEvent(
                name=name,
                category=category,
                start_time=time.time(),
                end_time=time.time(),
                metadata={"value": value},
                status="completed",
            )
            self._events.append(event)

        self.emit_event(
            event_type="metric.recorded",
            category=category,
            name=name,
            status="completed",
            metadata={"value": value},
        )

    def record_search_query(
        self,
        query: str,
        provider: str,
        result_count: int,
        duration_ms: int,
        status: str,
        **metadata: Any,
    ) -> None:
        """Record search query usage for provider calls."""
        self.emit_event(
            event_type="search.query",
            category="search",
            name=provider,
            status=status,
            duration_ms=duration_ms,
            metadata={"query": query, "result_count": result_count, **metadata},
        )

    def record_query_variations(
        self,
        *,
        original_query: str,
        query_families: list[QueryFamily],
        strategy_intent: str | None = None,
    ) -> None:
        """Record the generated query-family set for a session."""
        self.emit_event(
            event_type="query.variations",
            category="planning",
            name="query-expansion",
            status="recorded",
            metadata={
                "original_query": original_query,
                "variation_count": len(query_families),
                "strategy_intent": strategy_intent,
                "query_families": [
                    {
                        "query": family.query,
                        "family": family.family,
                        "intent_tags": list(family.intent_tags),
                    }
                    for family in query_families
                ],
            },
        )

    def record_analysis_mode(
        self,
        *,
        depth: str,
        mode: str,
        deep_analysis_enabled: bool,
    ) -> None:
        """Record the selected analysis mode for the run."""
        self.emit_event(
            event_type="analysis.mode_selected",
            category="analysis",
            name=mode,
            status="selected",
            metadata={
                "depth": depth,
                "mode": mode,
                "deep_analysis_enabled": deep_analysis_enabled,
            },
        )

    def record_source_provenance(
        self,
        *,
        query_families: list[QueryFamily],
        sources: list[SearchResultItem],
        stage: str,
    ) -> None:
        """Record which query families produced retrievable sources."""
        counts_by_family = {family.family: 0 for family in query_families}
        counts_by_query = {family.query: 0 for family in query_families}
        domains_by_family: dict[str, set[str]] = {family.family: set() for family in query_families}

        for source in sources:
            for entry in source.query_provenance:
                counts_by_family[entry.family] = counts_by_family.get(entry.family, 0) + 1
                counts_by_query[entry.query] = counts_by_query.get(entry.query, 0) + 1
                domain = source.url.split("/")[2].removeprefix("www.") if "://" in source.url else ""
                if domain:
                    domains_by_family.setdefault(entry.family, set()).add(domain)

        self.emit_event(
            event_type="source.provenance",
            category="retrieval",
            name=stage,
            status="recorded",
            metadata={
                "query_count": len(query_families),
                "source_count": len(sources),
                "families": [
                    {
                        "query": family.query,
                        "family": family.family,
                        "intent_tags": list(family.intent_tags),
                        "source_count": counts_by_query.get(family.query, 0),
                        "unique_domains": sorted(domains_by_family.get(family.family, set())),
                    }
                    for family in query_families
                ],
                "family_totals": counts_by_family,
            },
        )

    def record_follow_up_decision(
        self,
        *,
        iteration: int,
        reason: str,
        follow_up_queries: list[str],
        failure_modes: list[str] | None = None,
        quality_score: float | None = None,
    ) -> None:
        """Record why the workflow did or did not schedule follow-up work."""
        self.emit_event(
            event_type="follow_up.decision",
            category="iteration",
            name=f"iteration-{iteration}",
            status="recorded",
            metadata={
                "iteration": iteration,
                "reason": reason,
                "follow_up_count": len(follow_up_queries),
                "follow_up_queries": list(follow_up_queries),
                "failure_modes": list(failure_modes or []),
                "quality_score": quality_score,
            },
        )

    def record_iteration_stop(
        self,
        *,
        iteration: int,
        stop_reason: str,
        detail: str,
        quality_score: float | None = None,
        follow_up_queries: list[str] | None = None,
    ) -> str:
        """Record a standardized iterative stop reason."""
        normalized = self.normalize_stop_reason(stop_reason)
        self.emit_event(
            event_type="iteration.stop",
            category="iteration",
            name=normalized,
            status=normalized,
            metadata={
                "iteration": iteration,
                "stop_reason": normalized,
                "detail": detail,
                "quality_score": quality_score,
                "follow_up_queries": list(follow_up_queries or []),
            },
        )
        return normalized

    def record_tool_call(
        self,
        tool_name: str,
        status: str,
        duration_ms: int,
        agent_id: str | None = None,
        **metadata: Any,
    ) -> None:
        """Record a tool invocation event."""
        self.emit_event(
            event_type="tool.call",
            category="tool",
            name=tool_name,
            status=status,
            duration_ms=duration_ms,
            agent_id=agent_id,
            metadata=metadata,
        )

    def record_reasoning_summary(
        self,
        stage: str,
        summary: str,
        agent_id: str | None = None,
        **metadata: Any,
    ) -> None:
        """Record an interpretable decision summary for observability."""
        self.emit_event(
            event_type="reasoning.summary",
            category="reasoning",
            name=stage,
            status="recorded",
            agent_id=agent_id,
            metadata={"summary": summary, **metadata},
        )

    def record_llm_usage(
        self,
        operation: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        duration_ms: int,
        agent_id: str | None = None,
        **metadata: Any,
    ) -> None:
        """Record LLM token usage and treat each request as a tool call."""
        total_tokens = prompt_tokens + completion_tokens
        self.emit_event(
            event_type="llm.usage",
            category="llm",
            name=operation,
            status="success",
            duration_ms=duration_ms,
            agent_id=agent_id,
            metadata={
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                **metadata,
            },
        )
        self.record_tool_call(
            tool_name="claude.cli.print",
            status="success",
            duration_ms=duration_ms,
            agent_id=agent_id,
            operation=operation,
            model=model,
            tokens=total_tokens,
        )

    def record_llm_route_selected(
        self,
        *,
        agent_id: str,
        transport: str,
        provider: str,
        model: str,
        source: str = "planner",
        **metadata: Any,
    ) -> None:
        """Record when an LLM route is selected for an agent.

        Args:
            agent_id: The agent identifier.
            transport: The transport type (anthropic_api, openrouter_api, cerebras_api, heuristic).
            provider: The provider type (claude, openrouter, cerebras, heuristic).
            model: The model identifier.
            source: Where the route came from (planner, config, fallback).
            **metadata: Additional route metadata.
        """
        self.emit_event(
            event_type="llm.route_selected",
            category="llm",
            name="route-selection",
            status="selected",
            agent_id=agent_id,
            metadata={
                "transport": transport,
                "provider": provider,
                "model": model,
                "source": source,
                **metadata,
            },
        )

    def record_llm_route_fallback(
        self,
        *,
        agent_id: str,
        original_transport: str,
        fallback_transport: str,
        reason: str,
        **metadata: Any,
    ) -> None:
        """Record when an LLM route fallback occurs.

        Args:
            agent_id: The agent identifier.
            original_transport: The transport that failed or was unavailable.
            fallback_transport: The fallback transport being used.
            reason: Reason for the fallback.
            **metadata: Additional fallback metadata.
        """
        self.emit_event(
            event_type="llm.route_fallback",
            category="llm",
            name="route-fallback",
            status="fallback",
            agent_id=agent_id,
            metadata={
                "original_transport": original_transport,
                "fallback_transport": fallback_transport,
                "reason": reason,
                **metadata,
            },
        )

    def record_llm_route_request(
        self,
        *,
        agent_id: str,
        transport: str,
        provider: str,
        model: str,
        operation: str,
        **metadata: Any,
    ) -> str:
        """Record the start of an LLM request through a specific route.

        Args:
            agent_id: The agent identifier.
            transport: The transport type being used.
            provider: The provider type being used.
            model: The model being used.
            operation: The operation name.
            **metadata: Additional request metadata.
        """
        return self.emit_event(
            event_type="llm.route_request",
            category="llm",
            name=operation,
            status="started",
            agent_id=agent_id,
            metadata={
                "transport": transport,
                "provider": provider,
                "model": model,
                "operation": operation,
                **metadata,
            },
        )

    def record_llm_route_completion(
        self,
        *,
        agent_id: str,
        transport: str,
        provider: str,
        model: str,
        operation: str,
        duration_ms: int,
        success: bool = True,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        **metadata: Any,
    ) -> None:
        """Record the completion of an LLM request through a specific route.

        Args:
            agent_id: The agent identifier.
            transport: The transport type that was used.
            provider: The provider type that was used.
            model: The model that was used.
            operation: The operation name.
            duration_ms: Request duration in milliseconds.
            success: Whether the request succeeded.
            prompt_tokens: Number of prompt tokens used.
            completion_tokens: Number of completion tokens generated.
            **metadata: Additional completion metadata.
        """
        self.emit_event(
            event_type="llm.route_completion",
            category="llm",
            name=operation,
            status="completed" if success else "failed",
            duration_ms=duration_ms,
            agent_id=agent_id,
            metadata={
                "transport": transport,
                "provider": provider,
                "model": model,
                "operation": operation,
                "success": success,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                **metadata,
            },
        )

    def log_researcher_event(
        self,
        event_type: str,
        agent_id: str,
        **metadata: Any,
    ) -> None:
        """Log and record researcher lifecycle events."""
        if event_type == "spawned":
            self.log(f"Researcher {agent_id} spawned")
        elif event_type == "started":
            self.log(f"Researcher {agent_id} started task")
        elif event_type == "completed":
            duration = metadata.get("duration_ms", 0)
            sources = metadata.get("source_count", 0)
            self.log(f"Researcher {agent_id} completed: {sources} sources ({duration:.0f}ms)")
        elif event_type == "failed":
            error = metadata.get("error", "Unknown error")
            self.log(f"Researcher {agent_id} failed: {error}")
        elif event_type == "timeout":
            self.log(f"Researcher {agent_id} timed out")

        mapped_type = {
            "spawned": "agent.spawned",
            "started": "agent.started",
            "completed": "agent.completed",
            "failed": "agent.failed",
            "timeout": "agent.timeout",
        }.get(event_type, "agent.event")

        # Create MonitorEvent for timeline display
        if self._enabled:
            current_time = time.time()
            # For completed events, calculate start_time from duration
            duration_ms = metadata.get("duration_ms", 0)
            if duration_ms and event_type == "completed":
                start_time = current_time - (duration_ms / 1000)
            else:
                start_time = current_time
            event = MonitorEvent(
                name=f"Researcher {agent_id}",
                category="parallel",
                start_time=start_time,
                end_time=current_time,
                metadata={"event_type": event_type, **metadata},
                status=metadata.get("status", "completed" if event_type == "completed" else event_type),
            )
            self._events.append(event)

        self.emit_event(
            event_type=mapped_type,
            category="agent",
            name=event_type,
            status=metadata.get("status", "info"),
            agent_id=agent_id,
            duration_ms=metadata.get("duration_ms"),
            metadata=metadata,
        )

    def log_reflection_point(
        self,
        stage: str,
        question: str,
    ) -> None:
        """Log a strategic reflection point."""
        if self._enabled:
            self.section(f"Reflection: {stage}")
            self.log(f"Question: {question}")

        self.emit_event(
            event_type="reflection.point",
            category="reasoning",
            name=stage,
            status="recorded",
            metadata={"question": question},
        )

    def show_timeline(self) -> None:
        """Display execution timeline of parallel operations."""
        if not self._enabled:
            return

        self.section("Execution Timeline")

        researcher_events = [
            e for e in self._events if "researcher" in e.name.lower() or e.category == "parallel"
        ]

        if not researcher_events:
            self.log("No parallel execution events recorded")
            return

        researcher_events.sort(key=lambda e: e.start_time)

        for event in researcher_events:
            duration = f"{event.duration_ms:.0f}ms" if event.duration_ms > 0 else "N/A"
            status_emoji = {
                "in_progress": "🔄",
                "completed": "✓",
                "failed": "✗",
            }.get(event.status, "?")

            self.log(f"{status_emoji} {event.name} ({duration}) - {event.metadata}")

    def _build_llm_route_summary(self) -> dict[str, Any]:
        """Build a summary of LLM route usage from telemetry events.

        Returns:
            Dictionary with route usage statistics by transport, provider, and agent.
        """
        route_selections = [
            e for e in self._telemetry_events if e["event_type"] == "llm.route_selected"
        ]
        route_fallbacks = [
            e for e in self._telemetry_events if e["event_type"] == "llm.route_fallback"
        ]
        route_completions = [
            e for e in self._telemetry_events if e["event_type"] == "llm.route_completion"
        ]

        # Count by transport
        transport_counts: dict[str, int] = {}
        transport_tokens: dict[str, int] = {}
        transport_errors: dict[str, int] = {}

        # Count by provider
        provider_counts: dict[str, int] = {}

        # Count by agent
        agent_routes: dict[str, dict[str, Any]] = {}

        for event in route_completions:
            metadata = event.get("metadata", {})
            transport = metadata.get("transport", "unknown")
            provider = metadata.get("provider", "unknown")
            agent_id = event.get("agent_id") or "unknown"
            success = metadata.get("success", True)
            tokens = metadata.get("total_tokens", 0)

            transport_counts[transport] = transport_counts.get(transport, 0) + 1
            provider_counts[provider] = provider_counts.get(provider, 0) + 1
            transport_tokens[transport] = transport_tokens.get(transport, 0) + tokens

            if not success:
                transport_errors[transport] = transport_errors.get(transport, 0) + 1

            if agent_id not in agent_routes:
                agent_routes[agent_id] = {
                    "transport": transport,
                    "provider": provider,
                    "model": metadata.get("model", "unknown"),
                    "request_count": 0,
                    "total_tokens": 0,
                    "errors": 0,
                }
            agent_routes[agent_id]["request_count"] += 1
            agent_routes[agent_id]["total_tokens"] += tokens
            if not success:
                agent_routes[agent_id]["errors"] += 1

        # Track planned routes
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
            "transports": {
                transport: {
                    "requests": transport_counts.get(transport, 0),
                    "tokens": transport_tokens.get(transport, 0),
                    "errors": transport_errors.get(transport, 0),
                }
                for transport in set(transport_counts) | set(transport_tokens)
            },
            "providers": {
                provider: {"requests": provider_counts.get(provider, 0)}
                for provider in provider_counts
            },
            "agents": agent_routes,
            "planned_routes": planned_routes,
            "fallback_count": len(route_fallbacks),
            "total_requests": len(route_completions),
        }

    def finalize_session(
        self,
        total_sources: int,
        providers: list[str],
        total_time_ms: int,
        status: str = "completed",
        stop_reason: str = STOP_REASON_SUCCESS,
    ) -> dict[str, Any]:
        """Write summary metrics for the active session and return them."""
        normalized_stop_reason = self.normalize_stop_reason(stop_reason)
        llm_route_summary = self._build_llm_route_summary()

        summary = {
            "session_id": self._session_id,
            "status": status,
            "stop_reason": normalized_stop_reason,
            "total_sources": total_sources,
            "providers": providers,
            "total_time_ms": total_time_ms,
            "instances_spawned": sum(
                1 for e in self._telemetry_events if e["event_type"] == "agent.spawned"
            ),
            "search_queries": sum(
                1 for e in self._telemetry_events if e["event_type"] == "search.query"
            ),
            "tool_calls": sum(1 for e in self._telemetry_events if e["event_type"] == "tool.call"),
            "llm_prompt_tokens": sum(
                int(e["metadata"].get("prompt_tokens", 0))
                for e in self._telemetry_events
                if e["event_type"] == "llm.usage"
            ),
            "llm_completion_tokens": sum(
                int(e["metadata"].get("completion_tokens", 0))
                for e in self._telemetry_events
                if e["event_type"] == "llm.usage"
            ),
            "llm_total_tokens": sum(
                int(e["metadata"].get("total_tokens", 0))
                for e in self._telemetry_events
                if e["event_type"] == "llm.usage"
            ),
            "llm_route": llm_route_summary,
            "event_count": len(self._telemetry_events),
            "created_at": self._get_utc_timestamp(),
        }

        # Pop session parent if it exists
        if self._parent_stack:
            self.pop_parent()

        self.emit_event(
            event_type="session.finished",
            category="session",
            name="research-session",
            status=status,
            duration_ms=total_time_ms,
            metadata=summary,
        )

        if self._persist and self._summary_path is not None:
            with open(self._summary_path, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2)

        return summary

    # ==================== Checkpoint Methods ====================

    def _get_checkpoints_dir(self) -> Path | None:
        """Get the checkpoints directory for the current session."""
        if not self._persist or self._session_dir is None:
            return None
        checkpoints_dir = self._session_dir / "checkpoints"
        checkpoints_dir.mkdir(parents=True, exist_ok=True)
        return checkpoints_dir

    def _get_manifest_path(self) -> Path | None:
        """Get the checkpoint manifest file path."""
        checkpoints_dir = self._get_checkpoints_dir()
        if checkpoints_dir is None:
            return None
        return checkpoints_dir / "manifest.json"

    def _load_checkpoint_manifest(self) -> dict[str, Any]:
        """Load existing checkpoint manifest or create new one."""
        manifest_path = self._get_manifest_path()
        if manifest_path is None:
            return {"checkpoints": [], "latest_checkpoint_id": None, "latest_resume_safe_checkpoint_id": None}
        if manifest_path.exists():
            try:
                with open(manifest_path, encoding="utf-8") as f:
                    return cast(dict[str, Any], json.load(f))
            except (json.JSONDecodeError, OSError):
                pass
        return {"checkpoints": [], "latest_checkpoint_id": None, "latest_resume_safe_checkpoint_id": None}

    def _save_checkpoint_manifest(self, manifest: dict[str, Any]) -> None:
        """Persist checkpoint manifest to disk."""
        manifest_path = self._get_manifest_path()
        if manifest_path is None:
            return
        manifest["updated_at"] = self._get_utc_timestamp()
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, default=str)

    def _save_checkpoint_file(self, checkpoint: dict[str, Any]) -> Path | None:
        """Save individual checkpoint file."""
        checkpoints_dir = self._get_checkpoints_dir()
        if checkpoints_dir is None:
            return None
        sequence = checkpoint.get("sequence_number", 0)
        phase = checkpoint.get("phase", "unknown")
        filename = f"{sequence:04d}_{phase}.json"
        checkpoint_path = checkpoints_dir / filename
        with open(checkpoint_path, "w", encoding="utf-8") as f:
            json.dump(checkpoint, f, indent=2, default=str)
        return checkpoint_path

    def emit_checkpoint(
        self,
        *,
        phase: str,
        operation: str,
        attempt: int = 1,
        iteration: int | None = None,
        input_ref: dict[str, Any] | None = None,
        output_ref: dict[str, Any] | None = None,
        state_ref: str | None = None,
        config_ref: str | None = None,
        artifact_refs: list[dict[str, Any]] | None = None,
        provider_fixture_refs: list[dict[str, Any]] | None = None,
        replayable: bool = True,
        replayable_reason: str | None = None,
        parent_checkpoint_id: str | None = None,
        cause_event_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Emit a durable checkpoint for the current workflow step.

        Creates a checkpoint that captures step inputs, outputs, and context
        for debugging and resume capabilities.

        Args:
            phase: Workflow phase (session_start, team_init, strategy, etc.)
            operation: Operation type (initialize, execute, iterate, finalize)
            attempt: Attempt number for retries
            iteration: Iteration number for iterative workflows
            input_ref: Reference to step inputs
            output_ref: Reference to step outputs
            state_ref: Reference to session state snapshot
            config_ref: Reference to config snapshot
            artifact_refs: References to persisted artifacts
            provider_fixture_refs: References to captured provider fixtures
            replayable: Whether this step can be replayed exactly
            replayable_reason: Reason if not replayable
            parent_checkpoint_id: Previous checkpoint in lineage
            cause_event_id: Event that triggered this checkpoint
            metadata: Additional checkpoint metadata

        Returns:
            The checkpoint ID for correlation purposes.
        """
        import hashlib

        from cc_deep_research.models.checkpoint import (
            CHECKPOINT_SCHEMA_VERSION,
            CheckpointStatus,
        )

        checkpoint_id = f"cp-{uuid.uuid4().hex[:12]}"
        sequence_number = self._get_next_sequence()

        # Build resume token from checkpoint ID and sequence
        resume_token = hashlib.sha256(
            f"{self._session_id}:{checkpoint_id}:{sequence_number}".encode()
        ).hexdigest()[:16]

        checkpoint = {
            "checkpoint_id": checkpoint_id,
            "session_id": self._session_id,
            "trace_version": TRACE_VERSION,
            "checkpoint_version": CHECKPOINT_SCHEMA_VERSION,
            "sequence_number": sequence_number,
            "timestamp": self._get_utc_timestamp(),
            "phase": phase,
            "operation": operation,
            "attempt": attempt,
            "iteration": iteration,
            "status": CheckpointStatus.PENDING.value,
            "resume_token": resume_token,
            "parent_checkpoint_id": parent_checkpoint_id or self._get_latest_checkpoint_id(),
            "cause_event_id": cause_event_id,
            "input_ref": input_ref,
            "output_ref": output_ref,
            "state_ref": state_ref,
            "config_ref": config_ref,
            "artifact_refs": artifact_refs or [],
            "provider_fixture_refs": provider_fixture_refs or [],
            "replayable": replayable,
            "replayable_reason": replayable_reason,
            "resume_safe": False,  # Will be marked safe after commit verification
            "resume_prerequisites": [],
            "metadata": metadata or {},
        }

        # Persist checkpoint file
        checkpoint_path = self._save_checkpoint_file(checkpoint)

        # Update manifest
        manifest = self._load_checkpoint_manifest()
        manifest["checkpoints"].append(checkpoint)
        manifest["latest_checkpoint_id"] = checkpoint_id

        # Verify persistence and mark committed
        if checkpoint_path and checkpoint_path.exists():
            checkpoint["status"] = CheckpointStatus.COMMITTED.value
            # Mark resume safe if we have required refs and no replay issues
            if output_ref is not None and replayable:
                checkpoint["resume_safe"] = True
                manifest["latest_resume_safe_checkpoint_id"] = checkpoint_id
            self._save_checkpoint_manifest(manifest)
        else:
            checkpoint["status"] = CheckpointStatus.FAILED.value
            checkpoint["replayable"] = False
            checkpoint["replayable_reason"] = "Failed to persist checkpoint file"

        # Emit telemetry event for checkpoint
        self.emit_event(
            event_type="checkpoint.created",
            category="checkpoint",
            name=phase,
            status=checkpoint["status"],
            metadata={
                "checkpoint_id": checkpoint_id,
                "phase": phase,
                "operation": operation,
                "attempt": attempt,
                "iteration": iteration,
                "replayable": checkpoint["replayable"],
                "resume_safe": checkpoint["resume_safe"],
                "parent_checkpoint_id": checkpoint["parent_checkpoint_id"],
            },
        )

        return checkpoint_id

    def _get_latest_checkpoint_id(self) -> str | None:
        """Get the latest checkpoint ID from the manifest."""
        manifest = self._load_checkpoint_manifest()
        return manifest.get("latest_checkpoint_id")

    def get_latest_resume_safe_checkpoint(self) -> dict[str, Any] | None:
        """Get the latest checkpoint that is safe to resume from."""
        manifest = self._load_checkpoint_manifest()
        checkpoint_id = manifest.get("latest_resume_safe_checkpoint_id")
        if not checkpoint_id:
            return None
        return self.get_checkpoint_by_id(checkpoint_id)

    def get_checkpoint_by_id(self, checkpoint_id: str) -> dict[str, Any] | None:
        """Get a checkpoint by its ID."""
        manifest = self._load_checkpoint_manifest()
        for checkpoint in manifest.get("checkpoints", []):
            if checkpoint.get("checkpoint_id") == checkpoint_id:
                return cast(dict[str, Any], checkpoint)
        return None

    def get_checkpoints_by_phase(self, phase: str) -> list[dict[str, Any]]:
        """Get all checkpoints for a specific phase."""
        manifest = self._load_checkpoint_manifest()
        return [
            cast(dict[str, Any], cp) for cp in manifest.get("checkpoints", [])
            if cp.get("phase") == phase
        ]

    def get_all_checkpoints(self) -> list[dict[str, Any]]:
        """Get all checkpoints for the current session."""
        manifest = self._load_checkpoint_manifest()
        return cast(list[dict[str, Any]], manifest.get("checkpoints", []))

    def get_checkpoint_manifest(self) -> dict[str, Any]:
        """Get the full checkpoint manifest for the current session."""
        return self._load_checkpoint_manifest()

    def finalize_checkpoint(
        self,
        checkpoint_id: str,
        *,
        output_ref: dict[str, Any] | None = None,
        replayable: bool = True,
        replayable_reason: str | None = None,
    ) -> bool:
        """Update a checkpoint with final output and mark resume-safe.

        Args:
            checkpoint_id: The checkpoint to finalize
            output_ref: Reference to step outputs
            replayable: Whether the step can be replayed
            replayable_reason: Reason if not replayable

        Returns:
            True if finalization succeeded, False otherwise.
        """
        from cc_deep_research.models.checkpoint import CheckpointStatus

        manifest = self._load_checkpoint_manifest()
        checkpoint = None
        checkpoint_index = None

        for i, cp in enumerate(manifest.get("checkpoints", [])):
            if cp.get("checkpoint_id") == checkpoint_id:
                checkpoint = cp
                checkpoint_index = i
                break

        if checkpoint is None:
            return False

        # Update checkpoint
        if output_ref is not None:
            checkpoint["output_ref"] = output_ref
        checkpoint["replayable"] = replayable
        if replayable_reason:
            checkpoint["replayable_reason"] = replayable_reason

        # Mark committed and resume-safe if replayable with output
        if checkpoint.get("status") == CheckpointStatus.COMMITTED.value and output_ref is not None and replayable:
            checkpoint["resume_safe"] = True
            manifest["latest_resume_safe_checkpoint_id"] = checkpoint_id

        manifest["checkpoints"][checkpoint_index] = checkpoint
        self._save_checkpoint_manifest(manifest)

        # Update checkpoint file
        self._save_checkpoint_file(checkpoint)

        return True


__all__ = [
    # Core classes
    "MonitorEvent",
    "ResearchMonitor",
    # Trace contract
    "TRACE_VERSION",
    # Severity levels
    "SEVERITY_CRITICAL",
    "SEVERITY_DEBUG",
    "SEVERITY_ERROR",
    "SEVERITY_INFO",
    "SEVERITY_WARNING",
    # Reason codes
    "REASON_CANCELLED",
    "REASON_DEGRADED",
    "REASON_ERROR",
    "REASON_FALLBACK",
    "REASON_LIMIT_REACHED",
    "REASON_LOW_QUALITY",
    "REASON_SUCCESS",
    "REASON_TIMEOUT",
    "REASON_UNAVAILABLE",
    # Stop reasons (legacy aliases)
    "KNOWN_STOP_REASONS",
    "STOP_REASON_DEGRADED_EXECUTION",
    "STOP_REASON_LIMIT_REACHED",
    "STOP_REASON_LOW_QUALITY",
    "STOP_REASON_SUCCESS",
]
