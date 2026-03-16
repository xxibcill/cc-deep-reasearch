"""Research command registration."""

from __future__ import annotations

from pathlib import Path

import click

from cc_deep_research.monitoring import STOP_REASON_DEGRADED_EXECUTION, ResearchMonitor
from cc_deep_research.session_store import SessionStore
from cc_deep_research.tui import ResearchRunView, TerminalUI

from .shared import (
    describe_execution_mode,
    execute_research_run,
    log_monitor_session_start,
    resolve_parallel_mode_override,
)


def register_research_commands(cli: click.Group) -> None:
    """Register research execution commands."""

    @cli.command()
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
    @click.option(
        "--claude-only",
        is_flag=True,
        help="Use only Claude provider (not yet implemented)",
    )
    @click.option(
        "--no-team",
        is_flag=True,
        help="Run source collection sequentially instead of using parallel researchers",
    )
    @click.option(
        "--team-size",
        "team_size",
        type=int,
        default=None,
        help="Override default team size",
    )
    @click.option("--progress", is_flag=True, default=True, help="Show progress indicators")
    @click.option("--quiet", is_flag=True, help="Suppress output")
    @click.option("--verbose", is_flag=True, help="Show detailed output")
    @click.option("--monitor", is_flag=True, help="Show internal workflow monitoring information")
    @click.option("--parallel-mode", is_flag=True, help="Enable parallel researcher execution")
    @click.option(
        "--num-researchers",
        type=int,
        default=None,
        help="Number of parallel researchers (1-8)",
    )
    @click.option("--show-timeline", is_flag=True, help="Show execution timeline for parallel mode")
    @click.option("--pdf", is_flag=True, help="Generate PDF output in addition to markdown")
    @click.option(
        "--enable-realtime",
        is_flag=True,
        default=False,
        help="Enable real-time event streaming to dashboard",
    )
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
        enable_realtime: bool,
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
                "enable_realtime": enable_realtime,
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
            from cc_deep_research.config import load_config

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

            effective_parallel_mode = resolve_parallel_mode_override(
                no_team=no_team,
                parallel_mode=parallel_mode,
            )

            if not quiet:
                team_mode = describe_execution_mode(config, effective_parallel_mode)
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
                log_monitor_session_start(
                    research_monitor,
                    query=query,
                    depth=depth,
                    output_format=output_format,
                    config=config,
                )

            event_router = None
            if enable_realtime:
                import asyncio

                from cc_deep_research.event_router import EventRouter

                event_router = EventRouter()
                asyncio.create_task(event_router.start())

            orchestrator = TeamResearchOrchestrator(
                config=config,
                monitor=research_monitor,
                parallel_mode=effective_parallel_mode,
                num_researchers=num_researchers if num_researchers else None,
            )

            if event_router:
                research_monitor._event_router = event_router
            depth_enum = ResearchDepth(depth.lower())

            parallel_enabled = (
                effective_parallel_mode
                if effective_parallel_mode is not None
                else config.search_team.parallel_execution
            )

            session = execute_research_run(
                orchestrator=orchestrator,
                query=query,
                depth=depth_enum,
                min_sources=min_sources,
                progress=progress and not quiet,
                ui=ui,
            )

            if show_timeline and parallel_enabled and not quiet:
                research_monitor.show_timeline()

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
            elif quiet:
                click.echo(report)
            else:
                ui.show_report(report, output_format)

            if pdf:
                from cc_deep_research.pdf_generator import PDFGenerationError, PDFGenerator

                try:
                    pdf_gen = PDFGenerator()
                    if markdown_report is None:
                        markdown_report = reporter.generate_markdown_report(session, analysis)
                    html_report = reporter.render_html_report(markdown_report)
                    pdf_path = (
                        output_path.with_suffix(".pdf")
                        if output_path
                        else Path("research_report.pdf")
                    )
                    pdf_gen.generate_pdf_from_html(html_report, pdf_path)
                    if not quiet:
                        ui.show_report_saved(pdf_path)
                except PDFGenerationError as error:
                    if not quiet:
                        ui.show_error(str(error))
                except Exception as error:
                    if not quiet:
                        ui.show_error(f"Failed to generate PDF: {error}")

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


__all__ = ["register_research_commands"]
