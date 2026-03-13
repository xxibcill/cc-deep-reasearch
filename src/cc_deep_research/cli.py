"""CLI entry point for CC Deep Research."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path
from typing import Any

import click

from cc_deep_research.__about__ import __version__
from cc_deep_research.benchmark import load_benchmark_corpus, run_benchmark_corpus_sync
from cc_deep_research.config import (
    Config,
    create_default_config_file,
    get_default_config_path,
    load_config,
    save_config,
)
from cc_deep_research.monitoring import STOP_REASON_DEGRADED_EXECUTION, ResearchMonitor
from cc_deep_research.session_store import SessionStore
from cc_deep_research.telemetry import (
    get_default_dashboard_db_path,
    get_default_telemetry_dir,
    ingest_telemetry_to_duckdb,
)
from cc_deep_research.tui import ResearchRunView, TerminalUI

RESEARCH_PHASE_STEPS = 8


@click.group()
@click.version_option(version=__version__, prog_name="cc-deep-research")
@click.pass_context
def main(ctx: click.Context) -> None:
    """CC Deep Research - comprehensive web research CLI tool."""
    ctx.ensure_object(dict)


@main.command()
@click.argument("query", required=True)
@click.option(
    "-d",
    "--depth",
    type=click.Choice(["quick", "standard", "deep"], case_sensitive=False),
    default="deep",
    help="Research depth mode (default: deep). Deep mode performs multi-pass analysis with 50+ sources.",
)
@click.option(
    "-s",
    "--sources",
    "min_sources",
    type=int,
    default=None,
    help="Minimum number of sources to gather",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(dir_okay=False, writable=True),
    default=None,
    help="Output file path for the report",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["markdown", "json", "html"], case_sensitive=False),
    default="markdown",
    help="Output format (default: markdown)",
)
@click.option("--no-cross-ref", is_flag=True, help="Disable cross-reference analysis")
@click.option("--tavily-only", is_flag=True, help="Use only Tavily provider")
@click.option("--claude-only", is_flag=True, help="Use only Claude provider (not yet implemented)")
@click.option(
    "--no-team",
    is_flag=True,
    help="Run source collection sequentially instead of using parallel researchers",
)
@click.option("--team-size", "team_size", type=int, default=None, help="Override default team size")
@click.option("--progress", is_flag=True, default=True, help="Show progress indicators")
@click.option("--quiet", is_flag=True, help="Suppress output")
@click.option("--verbose", is_flag=True, help="Show detailed output")
@click.option("--monitor", is_flag=True, help="Show internal workflow monitoring information")
@click.option("--parallel-mode", is_flag=True, help="Enable parallel researcher execution")
@click.option(
    "--num-researchers", type=int, default=None, help="Number of parallel researchers (1-8)"
)
@click.option("--show-timeline", is_flag=True, help="Show execution timeline for parallel mode")
@click.option("--pdf", is_flag=True, help="Generate PDF output in addition to markdown")
@click.pass_context
def research(
    ctx: click.Context,
    query: str,
    depth: str,
    min_sources: int | None,
    output: str | None,
    output_format: str,
    no_cross_ref: bool,
    tavily_only: bool,
    claude_only: bool,
    no_team: bool,
    team_size: int | None,
    progress: bool,
    quiet: bool,
    verbose: bool,
    monitor: bool,
    parallel_mode: bool,
    num_researchers: int | None,
    show_timeline: bool,
    pdf: bool,
) -> None:
    """Execute a research query and generate a report."""
    ctx.obj.update(
        {
            "query": query,
            "depth": depth,
            "min_sources": min_sources,
            "output": output,
            "output_format": output_format,
            "no_cross_ref": no_cross_ref,
            "tavily_only": tavily_only,
            "claude_only": claude_only,
            "no_team": no_team,
            "team_size": team_size,
            "progress": progress,
            "quiet": quiet,
            "verbose": verbose,
            "monitor": monitor,
            "parallel_mode": parallel_mode,
            "num_researchers": num_researchers,
            "show_timeline": show_timeline,
            "pdf": pdf,
        }
    )

    ui = TerminalUI(enabled=not quiet)
    research_monitor = ResearchMonitor(enabled=(monitor or show_timeline) and not quiet)

    try:
        from cc_deep_research.models import ResearchDepth
        from cc_deep_research.orchestrator import TeamResearchOrchestrator
        from cc_deep_research.reporting import ReportGenerator

        config = load_config()
        if no_team:
            config.search_team.parallel_execution = False
        if team_size is not None:
            config.search_team.team_size = team_size
        if no_cross_ref:
            config.research.enable_cross_ref = False
        if tavily_only:
            config.search.providers = ["tavily"]
        if claude_only:
            config.search.providers = ["claude"]

        effective_parallel_mode = _resolve_parallel_mode_override(
            no_team=no_team,
            parallel_mode=parallel_mode,
        )

        if not quiet:
            team_mode = _describe_execution_mode(config, effective_parallel_mode)
            ui.show_research_header(
                ResearchRunView(
                    query=query,
                    depth=depth,
                    output_format=output_format,
                    providers=config.search.providers,
                    team_mode=team_mode,
                    monitor_enabled=monitor,
                )
            )
            if verbose:
                click.echo(
                    f"Min sources override: {min_sources if min_sources is not None else 'none'}"
                )

        if monitor and not quiet:
            _log_monitor_session_start(research_monitor, query, depth, output_format, config)

        orchestrator = TeamResearchOrchestrator(
            config=config,
            monitor=research_monitor,
            # Only pass parallel params if explicitly specified via CLI.
            # --no-team forces sequential collection, even if --parallel-mode is also set.
            parallel_mode=effective_parallel_mode,
            num_researchers=num_researchers if num_researchers else None,
        )
        depth_enum = ResearchDepth(depth.lower())

        parallel_enabled = (
            effective_parallel_mode
            if effective_parallel_mode is not None
            else config.search_team.parallel_execution
        )

        session = _execute_research_run(
            orchestrator=orchestrator,
            query=query,
            depth=depth_enum,
            min_sources=min_sources,
            progress=progress and not quiet,
            ui=ui,
        )

        # Show timeline if requested and parallel mode was enabled
        if show_timeline and parallel_enabled and not quiet:
            research_monitor.show_timeline()

        # Save session to store for later retrieval
        session_store = SessionStore()
        session_store.save_session(session)

        reporter = ReportGenerator(config)
        analysis = session.metadata.get("analysis", {})

        markdown_report: str | None = None
        if output_format == "json":
            report = reporter.generate_json_report(session, analysis)
        else:
            markdown_report = reporter.generate_markdown_report(session, analysis)
            if output_format == "html":
                report = reporter.render_html_report(markdown_report)
            else:
                report = markdown_report

        output_path = Path(output) if output else None
        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(report, encoding="utf-8")
            if not quiet:
                ui.show_report_saved(output_path)
        else:
            if quiet:
                click.echo(report)
            else:
                ui.show_report(report, output_format)

        # Generate PDF if requested
        if pdf:
            from cc_deep_research.pdf_generator import PDFGenerationError, PDFGenerator

            try:
                pdf_gen = PDFGenerator()
                if markdown_report is None:
                    markdown_report = reporter.generate_markdown_report(session, analysis)
                html_report = reporter.render_html_report(markdown_report)

                if output_path:
                    pdf_path = output_path.with_suffix(".pdf")
                else:
                    pdf_path = Path("research_report.pdf")

                pdf_gen.generate_pdf_from_html(html_report, pdf_path)
                if not quiet:
                    ui.show_report_saved(pdf_path)
            except PDFGenerationError as e:
                if not quiet:
                    ui.show_error(str(e))
            except Exception as e:
                if not quiet:
                    ui.show_error(f"Failed to generate PDF: {e}")

        if monitor and not quiet:
            research_monitor.section("Summary")
            research_monitor.summary(
                total_sources=session.total_sources,
                providers=config.search.providers,
                total_time_ms=int(session.execution_time_seconds * 1000),
            )

        if not quiet:
            ui.show_research_summary(
                source_count=session.total_sources,
                findings_count=len(analysis.get("key_findings", [])),
                theme_count=len(analysis.get("themes", [])),
                gap_count=len(analysis.get("gaps", [])),
                execution_seconds=session.execution_time_seconds,
                output_path=output_path,
            )

    except Exception as error:
        if research_monitor.session_id is not None:
            research_monitor.finalize_session(
                total_sources=0,
                providers=[],
                total_time_ms=0,
                status="failed",
                stop_reason=STOP_REASON_DEGRADED_EXECUTION,
            )
        if not quiet:
            ui.show_error(str(error))
        if monitor and not quiet:
            research_monitor.section("Error")
            research_monitor.log(f"Research failed: {error}")
        raise click.Abort() from error


@main.command("markdown-to-pdf")
@click.argument(
    "input_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "-o",
    "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Output PDF path (defaults to the input filename with a .pdf extension).",
)
@click.option(
    "--title",
    default=None,
    help="Optional report title override.",
)
def markdown_to_pdf(input_path: Path, output: Path | None, title: str | None) -> None:
    """Convert a markdown file into a formatted PDF report."""
    from cc_deep_research.pdf_generator import (
        PDFGenerationError,
        generate_pdf_report_from_markdown_file,
    )

    try:
        pdf_path = generate_pdf_report_from_markdown_file(
            input_path=input_path,
            output_path=output,
            title=title,
        )
    except PDFGenerationError as error:
        raise click.ClickException(str(error)) from error
    except OSError as error:
        raise click.ClickException(f"Failed to read markdown input: {error}") from error

    ui = TerminalUI(enabled=True)
    ui.show_report_saved(pdf_path)


@main.command("markdown-to-html")
@click.argument(
    "input_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "-o",
    "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Output HTML path (defaults to the input filename with a .html extension).",
)
@click.option(
    "--title",
    default=None,
    help="Optional report title override.",
)
def markdown_to_html(input_path: Path, output: Path | None, title: str | None) -> None:
    """Convert a markdown file into a formatted HTML report."""
    from cc_deep_research.html_report_renderer import (
        HTMLReportGenerationError,
        generate_html_report_from_markdown_file,
    )

    try:
        html_path = generate_html_report_from_markdown_file(
            input_path=input_path,
            output_path=output,
            title=title,
        )
    except HTMLReportGenerationError as error:
        raise click.ClickException(str(error)) from error
    except OSError as error:
        raise click.ClickException(f"Failed to read markdown input: {error}") from error

    ui = TerminalUI(enabled=True)
    ui.show_report_saved(html_path)


@main.group()
def benchmark() -> None:
    """Run the versioned benchmark corpus."""


@benchmark.command("run")
@click.option(
    "--corpus-path",
    type=click.Path(path_type=Path, dir_okay=False),
    default=None,
    help="Benchmark corpus JSON path.",
)
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path, file_okay=False),
    default=Path("benchmark_runs") / "latest",
    show_default=True,
    help="Directory for structured benchmark outputs.",
)
@click.option(
    "--depth",
    type=click.Choice(["quick", "standard", "deep"], case_sensitive=False),
    default="standard",
    show_default=True,
    help="Fixed research depth used for every benchmark case.",
)
@click.option(
    "--sources",
    "min_sources",
    type=int,
    default=None,
    help="Optional minimum source override applied to every case.",
)
@click.option("--monitor", is_flag=True, help="Enable monitor output during corpus execution.")
def benchmark_run(
    corpus_path: Path | None,
    output_dir: Path,
    depth: str,
    min_sources: int | None,
    monitor: bool,
) -> None:
    """Execute the whole benchmark corpus and persist a diffable report."""
    from cc_deep_research.models import ResearchDepth
    from cc_deep_research.orchestrator import TeamResearchOrchestrator

    corpus = load_benchmark_corpus(corpus_path)
    config = load_config()
    benchmark_monitor = ResearchMonitor(enabled=monitor)
    orchestrator = TeamResearchOrchestrator(config=config, monitor=benchmark_monitor)
    depth_enum = ResearchDepth(depth.lower())

    async def _run_case(case: Any) -> Any:
        return await orchestrator.execute_research(
            query=case.query,
            depth=depth_enum,
            min_sources=min_sources,
        )

    report = run_benchmark_corpus_sync(
        corpus,
        run_case=_run_case,
        output_dir=output_dir,
        configuration={
            "depth": depth_enum.value,
            "min_sources": min_sources,
            "providers": list(config.search.providers),
        },
    )
    click.echo(
        "Benchmark complete: "
        f"{report.scorecard.total_cases} cases, "
        f"avg score={report.scorecard.average_validation_score}, "
        f"output={output_dir}"
    )


@main.group()
def config() -> None:
    """Manage configuration settings."""


@main.group()
def telemetry() -> None:
    """Manage workflow telemetry and dashboard data."""


@telemetry.command("ingest")
@click.option(
    "--base-dir",
    type=click.Path(path_type=Path, file_okay=False),
    default=None,
    help="Telemetry events directory (defaults to ~/.config/cc-deep-research/telemetry).",
)
@click.option(
    "--db-path",
    type=click.Path(path_type=Path, dir_okay=False),
    default=None,
    help="DuckDB path for analytics output.",
)
def telemetry_ingest(base_dir: Path | None, db_path: Path | None) -> None:
    """Ingest session telemetry JSONL into DuckDB tables."""
    try:
        result = ingest_telemetry_to_duckdb(
            base_dir=base_dir or get_default_telemetry_dir(),
            db_path=db_path or get_default_dashboard_db_path(),
        )
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Ingested {result['sessions']} session summaries and {result['events']} events")


@telemetry.command("dashboard")
@click.option(
    "--base-dir",
    type=click.Path(path_type=Path, file_okay=False),
    default=None,
    help="Telemetry events directory.",
)
@click.option(
    "--db-path",
    type=click.Path(path_type=Path, dir_okay=False),
    default=None,
    help="DuckDB path for analytics output.",
)
@click.option(
    "--port",
    type=int,
    default=8501,
    show_default=True,
    help="Port for Streamlit dashboard.",
)
@click.option(
    "--refresh-seconds",
    type=int,
    default=5,
    show_default=True,
    help="Auto-refresh interval for the live dashboard (0 disables auto-refresh).",
)
@click.option(
    "--tail-limit",
    type=int,
    default=200,
    show_default=True,
    help="Maximum live events and subprocess chunks to display per session view.",
)
def telemetry_dashboard(
    base_dir: Path | None,
    db_path: Path | None,
    port: int,
    refresh_seconds: int,
    tail_limit: int,
) -> None:
    """Launch Streamlit dashboard for telemetry analytics."""
    resolved_base_dir = base_dir or get_default_telemetry_dir()
    resolved_db_path = db_path or get_default_dashboard_db_path()
    try:
        ingest_telemetry_to_duckdb(base_dir=resolved_base_dir, db_path=resolved_db_path)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc

    dashboard_script = Path(__file__).with_name("dashboard_app.py")
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(dashboard_script),
        "--server.port",
        str(port),
        "--",
        "--db-path",
        str(resolved_db_path),
        "--telemetry-dir",
        str(resolved_base_dir),
        "--refresh-seconds",
        str(refresh_seconds),
        "--tail-limit",
        str(tail_limit),
    ]
    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError as exc:
        raise click.ClickException(
            "streamlit is not installed. Install with `pip install \"cc-deep-research[dashboard]\"`."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise click.ClickException(f"Failed to start dashboard: {exc}") from exc


@config.command()
@click.argument("key", required=True)
@click.argument("value", required=True)
@click.option(
    "--config-path",
    type=click.Path(),
    default=None,
    help="Path to config file (uses default if not specified)",
)
def set(key: str, value: str, config_path: str | None) -> None:
    """Set a configuration value.

    KEY is the configuration key in dot notation (e.g., tavily.api_keys).
    VALUE is the value to set.
    """
    config_obj = _load_config_from_path(config_path)
    target, final_key = _resolve_config_target(config_obj, key)

    current_value = getattr(target, final_key)
    parsed_value = _parse_config_value(current_value, value, key)
    setattr(target, final_key, parsed_value)

    save_path = Path(config_path) if config_path else get_default_config_path()
    save_config(config_obj, save_path)

    ui = TerminalUI(enabled=True)
    ui.show_config_updated(key, str(parsed_value), save_path)


@config.command()
@click.option(
    "--config-path",
    type=click.Path(),
    default=None,
    help="Path to config file (uses default if not specified)",
)
def show(config_path: str | None) -> None:
    """Show current configuration."""
    config_obj = _load_config_from_path(config_path)

    rows = [
        ("search.providers", ", ".join(config_obj.search.providers)),
        ("search.mode", _format_config_value(config_obj.search.mode)),
        ("search.depth", _format_config_value(config_obj.search.depth)),
        ("tavily.api_keys", f"{len(config_obj.tavily.api_keys)} configured"),
        ("tavily.max_results", str(config_obj.tavily.max_results)),
        ("search_team.enabled", str(config_obj.search_team.enabled).lower()),
        ("search_team.team_size", str(config_obj.search_team.team_size)),
        ("output.format", config_obj.output.format),
        ("output.save_dir", config_obj.output.save_dir),
    ]

    ui = TerminalUI(enabled=True)
    ui.show_config(rows)


@config.command()
@click.option(
    "--config-path",
    type=click.Path(),
    default=None,
    help="Path to config file (uses default if not specified)",
)
@click.option("--force", is_flag=True, help="Overwrite existing config file")
def init(config_path: str | None, force: bool) -> None:
    """Create a default configuration file."""
    save_path = Path(config_path) if config_path else get_default_config_path()

    if save_path.exists() and not force:
        click.echo(
            f"Error: Config file already exists at {save_path}. Use --force to overwrite.",
            err=True,
        )
        raise click.Abort()

    created_path = create_default_config_file(save_path)
    ui = TerminalUI(enabled=True)
    ui.show_config_updated("config", "initialized", created_path)


# Session management commands
@main.group()
def session() -> None:
    """Manage research sessions."""


@session.command("list")
@click.option("--limit", type=int, default=20, help="Maximum number of sessions to show")
@click.option("--offset", type=int, default=0, help="Number of sessions to skip")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def session_list(limit: int, offset: int, as_json: bool) -> None:
    """List all saved research sessions.

    Shows session ID, query, depth, and timestamp for each session.
    """
    store = SessionStore()
    sessions = store.list_sessions(limit=limit, offset=offset)

    if not sessions:
        click.echo("No saved sessions found.")
        return

    if as_json:
        import json as json_module

        click.echo(json_module.dumps(sessions, indent=2))
        return

    ui = TerminalUI(enabled=True)
    ui.show_session_list(sessions)


@session.command("show")
@click.argument("session_id", required=True)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def session_show(session_id: str, as_json: bool) -> None:
    """Show details of a specific research session.

    SESSION_ID is the identifier of the session to display.
    """
    store = SessionStore()
    session_obj = store.load_session(session_id)

    if session_obj is None:
        click.echo(f"Error: Session '{session_id}' not found.", err=True)
        raise click.Abort()

    if as_json:
        from cc_deep_research.reporting import ReportGenerator

        config = load_config()
        reporter = ReportGenerator(config)
        analysis = session_obj.metadata.get("analysis", {})
        click.echo(reporter.generate_json_report(session_obj, analysis))
        return

    ui = TerminalUI(enabled=True)
    ui.show_session_details(session_obj)


@session.command("export")
@click.argument("session_id", required=True)
@click.option(
    "-o",
    "--output",
    type=click.Path(dir_okay=False, writable=True),
    required=True,
    help="Output file path",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["markdown", "json", "html"], case_sensitive=False),
    default="markdown",
    help="Output format (default: markdown)",
)
def session_export(session_id: str, output: str, output_format: str) -> None:
    """Export a research session to a file.

    SESSION_ID is the identifier of the session to export.
    """
    store = SessionStore()
    session_obj = store.load_session(session_id)

    if session_obj is None:
        click.echo(f"Error: Session '{session_id}' not found.", err=True)
        raise click.Abort()

    from cc_deep_research.reporting import ReportGenerator

    config = load_config()
    reporter = ReportGenerator(config)
    analysis = session_obj.metadata.get("analysis", {})

    if output_format == "json":
        report = reporter.generate_json_report(session_obj, analysis)
    elif output_format == "html":
        report = reporter.generate_html_report(session_obj, analysis)
    else:
        report = reporter.generate_markdown_report(session_obj, analysis)

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")

    ui = TerminalUI(enabled=True)
    ui.show_report_saved(output_path)


@session.command("delete")
@click.argument("session_id", required=True)
@click.option("--force", is_flag=True, help="Skip confirmation prompt")
def session_delete(session_id: str, force: bool) -> None:
    """Delete a research session.

    SESSION_ID is the identifier of the session to delete.
    """
    store = SessionStore()

    if not store.session_exists(session_id):
        click.echo(f"Error: Session '{session_id}' not found.", err=True)
        raise click.Abort()

    if not force and not click.confirm(f"Delete session '{session_id}'?"):
        click.echo("Aborted.")
        return

    if store.delete_session(session_id):
        click.echo(f"Session '{session_id}' deleted.")
    else:
        click.echo(f"Error: Failed to delete session '{session_id}'.", err=True)
        raise click.Abort()


def _execute_research_run(
    orchestrator: Any,
    query: str,
    depth: Any,
    min_sources: int | None,
    progress: bool,
    ui: TerminalUI,
) -> Any:
    """Run the orchestrator and optionally render phase progress."""
    if progress:
        with ui.create_phase_progress(RESEARCH_PHASE_STEPS) as tracker:
            session = asyncio.run(
                orchestrator.execute_research(
                    query=query,
                    depth=depth,
                    min_sources=min_sources,
                    phase_hook=tracker.on_phase,
                )
            )
            tracker.mark_complete()
            return session

    with ui.status("Running research workflow..."):
        return asyncio.run(
            orchestrator.execute_research(
                query=query,
                depth=depth,
                min_sources=min_sources,
            )
        )


def _resolve_parallel_mode_override(*, no_team: bool, parallel_mode: bool) -> bool | None:
    """Resolve the effective parallel override passed to the orchestrator."""
    if no_team:
        return False
    if parallel_mode:
        return True
    return None


def _describe_execution_mode(config: Config, parallel_mode_override: bool | None) -> str:
    """Describe execution mode for display."""
    parallel_enabled = (
        parallel_mode_override
        if parallel_mode_override is not None
        else config.search_team.parallel_execution
    )
    return "parallel" if parallel_enabled else "sequential"


def _log_monitor_session_start(
    research_monitor: ResearchMonitor,
    query: str,
    depth: str,
    output_format: str,
    config: Config,
) -> None:
    """Emit monitor startup metadata."""
    research_monitor.section("Research Session")
    research_monitor.log(f"Query: {query}")
    research_monitor.log(f"Depth: {depth}")
    research_monitor.log(f"Output format: {output_format}")

    research_monitor.section("Configuration")
    research_monitor.log(f"Providers: {', '.join(config.search.providers)}")
    research_monitor.log(f"Search depth: {config.search.depth}")
    research_monitor.log(f"Search mode: {config.search.mode}")
    research_monitor.log(
        "Source collection: "
        + ("parallel" if config.search_team.parallel_execution else "sequential")
    )

    research_monitor.section("Execution")


def _load_config_from_path(config_path: str | None) -> Config:
    """Load configuration from default location or a provided path."""
    if config_path is None:
        return load_config()
    return load_config(Path(config_path))


def _resolve_config_target(config_obj: Config, key: str) -> tuple[Any, str]:
    """Resolve object and attribute for a dot-notation configuration key."""
    key_parts = key.split(".")
    target: Any = config_obj

    for part in key_parts[:-1]:
        if not hasattr(target, part):
            click.echo(f"Error: Invalid configuration key: {key}", err=True)
            raise click.Abort()
        target = getattr(target, part)

    final_key = key_parts[-1]
    if not hasattr(target, final_key):
        click.echo(f"Error: Invalid configuration key: {key}", err=True)
        raise click.Abort()

    return target, final_key


def _parse_config_value(current_value: Any, value: str, key: str) -> Any:
    """Parse CLI string values into the target config field type."""
    if isinstance(current_value, list):
        return [item.strip() for item in value.split(",") if item.strip()]

    if isinstance(current_value, bool):
        return value.lower() in {"true", "1", "yes", "on"}

    if isinstance(current_value, int):
        try:
            return int(value)
        except ValueError as error:
            click.echo(f"Error: Expected integer value for {key}, got: {value}", err=True)
            raise click.Abort() from error

    return value


def _format_config_value(value: Any) -> str:
    """Format config values for display."""
    enum_value = getattr(value, "value", None)
    if enum_value is not None:
        return str(enum_value)
    return str(value)


if __name__ == "__main__":
    main()
