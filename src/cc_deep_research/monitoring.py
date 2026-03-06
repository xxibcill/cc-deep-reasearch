"""Monitoring infrastructure for research workflow visibility."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click

from cc_deep_research.config import get_default_config_path


@dataclass
class MonitorEvent:
    """Represents a single monitored operation."""

    name: str
    category: str  # config, provider, aggregation, deduplication, etc.
    start_time: float
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
    ) -> None:
        """Initialize the monitor.

        Args:
            enabled: Whether console monitoring output is active.
            persist: Whether telemetry events should be persisted to disk.
            telemetry_dir: Base directory for telemetry session folders.
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

    def set_session(
        self,
        session_id: str,
        query: str,
        depth: str,
        **metadata: Any,
    ) -> None:
        """Set active session and initialize persistent telemetry files."""
        self._session_id = session_id

        if self._persist:
            self._session_dir = self._telemetry_dir / session_id
            self._session_dir.mkdir(parents=True, exist_ok=True)
            self._events_path = self._session_dir / "events.jsonl"
            self._summary_path = self._session_dir / "summary.json"

        self.emit_event(
            event_type="session.started",
            category="session",
            name="research-session",
            status="started",
            metadata={"query": query, "depth": depth, **metadata},
        )

    def emit_event(
        self,
        event_type: str,
        category: str,
        name: str,
        status: str = "info",
        duration_ms: int | None = None,
        agent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Emit a structured telemetry event and persist it when configured."""
        payload = {
            "timestamp": self._get_utc_timestamp(),
            "session_id": self._session_id,
            "event_type": event_type,
            "category": category,
            "name": name,
            "status": status,
            "duration_ms": duration_ms,
            "agent_id": agent_id,
            "metadata": metadata or {},
        }

        self._telemetry_events.append(payload)
        if self._persist and self._events_path is not None:
            with open(self._events_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=True))
                f.write("\n")

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
        event = MonitorEvent(
            name=name,
            category=category,
            start_time=time.time(),
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
            tool_name="anthropic.messages.create",
            status="success",
            duration_ms=duration_ms,
            agent_id=agent_id,
            operation=operation,
            model=model,
            tokens=total_tokens,
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

    def finalize_session(
        self,
        total_sources: int,
        providers: list[str],
        total_time_ms: int,
        status: str = "completed",
    ) -> dict[str, Any]:
        """Write summary metrics for the active session and return them."""
        summary = {
            "session_id": self._session_id,
            "status": status,
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
            "created_at": self._get_utc_timestamp(),
        }

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


__all__ = [
    "MonitorEvent",
    "ResearchMonitor",
]
