"""Monitoring infrastructure for research workflow visibility."""

import time
from dataclasses import dataclass, field
from typing import Any

import click


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
    """Monitor for research operations with structured output."""

    PREFIX = "[MONITOR]"

    def __init__(self, enabled: bool = False) -> None:
        """Initialize the monitor.

        Args:
            enabled: Whether monitoring is active.
        """
        self._enabled = enabled
        self._events: list[MonitorEvent] = []
        self._start_time = time.time()

    def is_enabled(self) -> bool:
        """Check if monitoring is enabled.

        Returns:
            True if monitoring is active, False otherwise.
        """
        return self._enabled

    def section(self, name: str) -> None:
        """Start a new section with a header.

        Args:
            name: Name of the section.
        """
        if not self._enabled:
            return
        click.echo(f"{self.PREFIX} === {name} ===")

    def log(self, message: str, indent: int = 0) -> None:
        """Log a message.

        Args:
            message: Message to log.
            indent: Number of spaces to indent (default: 0).
        """
        if not self._enabled:
            return
        prefix = " " * indent
        click.echo(f"{self.PREFIX} {prefix}{message}")

    def log_result(self, provider: str, count: int, duration_ms: int) -> None:
        """Log search results from a provider.

        Args:
            provider: Provider name (e.g., "tavily").
            count: Number of results received.
            duration_ms: Duration of the search in milliseconds.
        """
        if not self._enabled:
            return
        click.echo(f"{self.PREFIX} [{provider.upper()}] Response received: {count} results ({duration_ms}ms)")

    def log_aggregation(self, before: int, after: int) -> None:
        """Log aggregation deduplication statistics.

        Args:
            before: Number of results before deduplication.
            after: Number of results after deduplication.
        """
        if not self._enabled:
            return
        removed = before - after
        click.echo(
            f"{self.PREFIX} [AGGREGATOR] Deduplicated: {removed} duplicate(s) removed, "
            f"{after} unique result(s)"
        )

    def log_timing(self, operation: str, duration_ms: int) -> None:
        """Log timing information for an operation.

        Args:
            operation: Name of the operation.
            duration_ms: Duration in milliseconds.
        """
        if not self._enabled:
            return
        click.echo(f"{self.PREFIX} {operation} completed in {duration_ms}ms")

    def summary(self, total_sources: int, providers: list[str], total_time_ms: int) -> None:
        """Display final summary of the research session.

        Args:
            total_sources: Total number of unique sources.
            providers: List of providers used.
            total_time_ms: Total execution time in milliseconds.
        """
        if not self._enabled:
            return
        providers_str = ", ".join(providers) if providers else "none"
        total_time_sec = total_time_ms / 1000
        click.echo(f"{self.PREFIX} Total sources: {total_sources}")
        click.echo(f"{self.PREFIX} Providers used: {providers_str}")
        click.echo(f"{self.PREFIX} Total execution time: {total_time_sec:.1f}s")

    def start_operation(self, name: str, category: str, **metadata) -> MonitorEvent:
        """Start tracking an operation.

        Args:
            name: Name of the operation.
            category: Category for grouping (config, provider, aggregation, etc.).
            **metadata: Additional metadata to track.

        Returns:
            MonitorEvent for tracking.
        """
        event = MonitorEvent(
            name=name,
            category=category,
            start_time=time.time(),
            metadata=metadata,
        )
        if self._enabled:
            self._events.append(event)
        return event

    def end_operation(self, event: MonitorEvent, success: bool = True) -> None:
        """Mark an operation as complete.

        Args:
            event: The MonitorEvent to complete.
            success: Whether the operation succeeded.
        """
        event.end_time = time.time()
        event.status = "completed" if success else "failed"

    def record_metric(self, name: str, value: Any, category: str) -> None:
        """Record a metric value.

        Args:
            name: Metric name.
            value: Metric value.
            category: Category for grouping.
        """
        if not self._enabled:
            return
        event = MonitorEvent(
            name=name,
            category=category,
            start_time=time.time(),
            end_time=time.time(),
            metadata={"value": value},
            status="completed",
        )
        self._events.append(event)


__all__ = [
    "MonitorEvent",
    "ResearchMonitor",
]
