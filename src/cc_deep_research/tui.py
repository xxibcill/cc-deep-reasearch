"""Terminal UI components for the CC Deep Research CLI."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.syntax import Syntax
from rich.table import Table

from cc_deep_research.models import ResearchSession


@dataclass(frozen=True)
class ResearchRunView:
    """Display model for a research run."""

    query: str
    depth: str
    output_format: str
    providers: list[str]
    execution_mode: str
    monitor_enabled: bool


class PhaseProgressTracker:
    """Tracks and renders high-level workflow phases."""

    def __init__(self, console: Console, total_steps: int) -> None:
        self._console = console
        self._total_steps = max(1, total_steps)
        self._seen_phases: set[str] = set()
        self._completed_steps = 0
        self._progress = Progress(
            SpinnerColumn(style="cyan"),
            TextColumn("{task.description}"),
            BarColumn(bar_width=None),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
            transient=True,
        )
        self._task_id = self._progress.add_task(
            "[bold cyan]Preparing research workflow...",
            total=self._total_steps,
        )

    def __enter__(self) -> PhaseProgressTracker:
        self._progress.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self._progress.stop()

    def on_phase(self, phase_key: str, description: str) -> None:
        """Record a completed phase and update the progress display."""
        if phase_key in self._seen_phases:
            return

        self._seen_phases.add(phase_key)
        if self._completed_steps < self._total_steps:
            self._completed_steps += 1

        self._progress.update(
            self._task_id,
            completed=self._completed_steps,
            description=f"[bold cyan]{description}",
        )

    def mark_complete(self, message: str = "Research complete") -> None:
        """Mark progress as complete."""
        self._completed_steps = self._total_steps
        self._progress.update(
            self._task_id,
            completed=self._total_steps,
            description=f"[bold green]{message}",
        )


class TerminalUI:
    """Rich-backed terminal UI for CLI commands."""

    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled
        self._console = Console(highlight=False)
        self._error_console = Console(stderr=True, highlight=False)

    @property
    def enabled(self) -> bool:
        """Whether rich UI rendering is enabled."""
        return self._enabled

    def show_research_header(self, view: ResearchRunView) -> None:
        """Render a structured overview for a research run."""
        if not self._enabled:
            return

        details = Table.grid(padding=(0, 1))
        details.add_column(style="bold cyan", justify="right", no_wrap=True)
        details.add_column(style="white")
        details.add_row("Query", view.query)
        details.add_row("Depth", view.depth)
        details.add_row("Providers", ", ".join(view.providers) or "none")
        details.add_row("Output", view.output_format)
        details.add_row("Mode", view.execution_mode)
        details.add_row("Monitor", "enabled" if view.monitor_enabled else "disabled")

        self._console.print(
            Panel(
                details,
                title="[bold]CC Deep Research[/bold]",
                border_style="cyan",
                expand=False,
            )
        )

    def show_research_summary(
        self,
        *,
        source_count: int,
        findings_count: int,
        theme_count: int,
        gap_count: int,
        execution_seconds: float,
        output_path: Path | None,
    ) -> None:
        """Render summary metrics after a research run."""
        if not self._enabled:
            return

        summary = Table(box=box.SIMPLE_HEAVY)
        summary.add_column("Metric", style="bold cyan")
        summary.add_column("Value", style="white")
        summary.add_row("Sources", str(source_count))
        summary.add_row("Key findings", str(findings_count))
        summary.add_row("Themes", str(theme_count))
        summary.add_row("Gaps", str(gap_count))
        summary.add_row("Execution", f"{execution_seconds:.1f}s")
        if output_path is not None:
            summary.add_row("Saved report", str(output_path))

        self._console.print(
            Panel(summary, title="[bold]Research Summary[/bold]", border_style="green")
        )

    def show_report_saved(self, output_path: Path) -> None:
        """Render saved-report confirmation."""
        if not self._enabled:
            return
        self._console.print(f"[bold green]Saved report:[/bold green] {output_path}")

    def show_report(self, report: str, output_format: str) -> None:
        """Render report output in a readable terminal format."""
        if not self._enabled:
            self._console.print(report)
            return

        if not self._console.is_terminal:
            self._console.print(report)
            return

        if output_format == "markdown":
            self._console.print(Markdown(report))
            return

        if output_format == "json":
            self._console.print(Syntax(report, "json", word_wrap=True))
            return

        if output_format == "html":
            self._console.print(Syntax(report, "html", word_wrap=True))
            return

        self._console.print(report)

    def show_config(self, rows: list[tuple[str, str]]) -> None:
        """Render configuration values in a compact table."""
        if not self._enabled:
            for key, value in rows:
                self._console.print(f"{key}: {value}")
            return

        table = Table(title="Current Configuration", box=box.SIMPLE_HEAVY)
        table.add_column("Setting", style="bold cyan", no_wrap=True)
        table.add_column("Value", style="white")

        for key, value in rows:
            table.add_row(key, value)

        self._console.print(table)

    def show_config_updated(self, key: str, value: str, saved_path: Path) -> None:
        """Render confirmation for config updates."""
        if not self._enabled:
            self._console.print(f"Configuration updated: {key} = {value}")
            self._console.print(f"Saved to: {saved_path}")
            return

        details = Table.grid(padding=(0, 1))
        details.add_column(style="bold cyan", justify="right")
        details.add_column(style="white")
        details.add_row("Updated", f"{key} = {value}")
        details.add_row("Saved to", str(saved_path))

        self._console.print(
            Panel(
                details,
                title="[bold green]Configuration Updated[/bold green]",
                border_style="green",
                expand=False,
            )
        )

    def show_error(self, message: str) -> None:
        """Render a styled error panel."""
        if not self._enabled:
            self._error_console.print(f"Error: {message}")
            return

        self._error_console.print(
            Panel(message, title="[bold red]Error[/bold red]", border_style="red")
        )

    def create_phase_progress(self, total_steps: int) -> PhaseProgressTracker:
        """Create a tracker for workflow progress display."""
        return PhaseProgressTracker(self._console, total_steps)

    @contextmanager
    def status(self, message: str) -> Iterator[None]:
        """Render a temporary status spinner while work is running."""
        if not self._enabled:
            yield
            return

        with self._console.status(f"[bold cyan]{message}"):
            yield

    def show_session_list(self, sessions: list[dict[str, Any]]) -> None:
        """Render a list of research sessions.

        Args:
            sessions: List of session metadata dictionaries.
        """
        if not self._enabled:
            for s in sessions:
                self._console.print(
                    f"{s['session_id']}: {s['query']} ({s['depth']}) - {s['started_at']}"
                )
            return

        table = Table(title="Research Sessions", box=box.SIMPLE_HEAVY)
        table.add_column("Session ID", style="cyan", no_wrap=True)
        table.add_column("Query", style="white", max_width=40)
        table.add_column("Depth", style="yellow")
        table.add_column("Sources", style="green", justify="right")
        table.add_column("Started", style="dim")

        for s in sessions:
            # Truncate query if too long
            query = s.get("query", "Unknown")
            if len(query) > 40:
                query = query[:37] + "..."

            # Format timestamp
            started = s.get("started_at", "")
            if started:
                try:
                    from datetime import datetime

                    dt = datetime.fromisoformat(started)
                    started = dt.strftime("%Y-%m-%d %H:%M")
                except (ValueError, TypeError):
                    pass

            table.add_row(
                s.get("session_id", "unknown"),
                query,
                s.get("depth", "deep"),
                str(s.get("total_sources", 0)),
                started,
            )

        self._console.print(table)

    def show_session_details(self, session: ResearchSession) -> None:
        """Render details of a research session.

        Args:
            session: ResearchSession to display.
        """
        if not self._enabled:
            self._console.print(f"Session: {session.session_id}")
            self._console.print(f"Query: {session.query}")
            self._console.print(f"Depth: {session.depth.value}")
            self._console.print(f"Sources: {session.total_sources}")
            return

        # Session metadata table
        details = Table.grid(padding=(0, 1))
        details.add_column(style="bold cyan", justify="right", no_wrap=True)
        details.add_column(style="white")

        details.add_row("Session ID", session.session_id)
        details.add_row("Query", session.query)
        details.add_row("Depth", session.depth.value)
        details.add_row("Total Sources", str(session.total_sources))

        if session.started_at:
            details.add_row("Started", session.started_at.strftime("%Y-%m-%d %H:%M:%S"))
        if session.completed_at:
            details.add_row("Completed", session.completed_at.strftime("%Y-%m-%d %H:%M:%S"))
        if session.execution_time_seconds > 0:
            details.add_row("Duration", f"{session.execution_time_seconds:.1f}s")

        self._console.print(
            Panel(
                details,
                title="[bold]Session Details[/bold]",
                border_style="cyan",
                expand=False,
            )
        )

        # Analysis summary if available
        analysis = session.metadata.get("analysis", {})
        if analysis:
            self._console.print()

            summary = Table(box=box.SIMPLE_HEAVY)
            summary.add_column("Metric", style="bold cyan")
            summary.add_column("Value", style="white")

            key_findings = analysis.get("key_findings", [])
            themes = analysis.get("themes", [])
            gaps = analysis.get("gaps", [])

            summary.add_row("Key Findings", str(len(key_findings)))
            summary.add_row("Themes", str(len(themes)))
            summary.add_row("Gaps", str(len(gaps)))

            validation = session.metadata.get("validation", {})
            if validation:
                quality_score = validation.get("quality_score", 0)
                summary.add_row("Quality Score", f"{quality_score:.2f}")

            self._console.print(
                Panel(summary, title="[bold]Analysis Summary[/bold]", border_style="green")
            )

            # Show key findings
            if key_findings:
                self._console.print()
                findings_table = Table(box=box.SIMPLE_HEAVY)
                findings_table.add_column("#", style="dim", width=3)
                findings_table.add_column("Finding", style="white")

                for i, finding in enumerate(key_findings[:10], 1):
                    findings_table.add_row(str(i), finding[:100] + "..." if len(finding) > 100 else finding)

                self._console.print(
                    Panel(
                        findings_table,
                        title="[bold]Key Findings[/bold]",
                        border_style="blue",
                    )
                )

        # Sources list (truncated)
        if session.sources:
            self._console.print()
            sources_table = Table(box=box.SIMPLE_HEAVY)
            sources_table.add_column("#", style="dim", width=3)
            sources_table.add_column("Title", style="white", max_width=50)
            sources_table.add_column("URL", style="blue", max_width=40)

            for i, source in enumerate(session.sources[:10], 1):
                title = source.title[:47] + "..." if len(source.title) > 50 else source.title
                url = source.url[:37] + "..." if len(source.url) > 40 else source.url
                sources_table.add_row(str(i), title, url)

            if len(session.sources) > 10:
                sources_table.add_row("...", f"({len(session.sources) - 10} more)", "")

            self._console.print(
                Panel(
                    sources_table,
                    title="[bold]Sources[/bold]",
                    border_style="yellow",
                )
            )


__all__ = [
    "TerminalUI",
    "ResearchRunView",
    "PhaseProgressTracker",
]
