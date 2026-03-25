"""Research command registration."""

from __future__ import annotations

import click

from cc_deep_research.monitoring import ResearchMonitor
from cc_deep_research.research_runs import ResearchRunService, ResearchTheme
from cc_deep_research.tui import ResearchRunView, TerminalUI

from .shared import (
    TerminalResearchRunExecutionAdapter,
    build_research_run_request,
    describe_execution_mode,
    log_monitor_session_start,
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
    @click.option(
        "--workflow",
        type=click.Choice(["staged", "planner"], case_sensitive=False),
        default="staged",
        help="Research workflow to use: 'staged' (default) or 'planner'. "
        "Planner workflow uses hierarchical task decomposition for complex queries.",
    )
    @click.option(
        "--theme",
        type=click.Choice(
            ["general", "resources", "trip_planning", "due_diligence", "market_research", "business_ideas", "content_creation"],
            case_sensitive=False,
        ),
        default=None,
        help="Research theme for tailored workflow. If not specified, auto-detected from query.",
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
        workflow: str,
        theme: str | None,
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
                "workflow": workflow,
                "theme": theme,
            }
        )

        ui = TerminalUI(enabled=not quiet)
        research_monitor = ResearchMonitor(enabled=(monitor or show_timeline) and not quiet)

        try:
            from cc_deep_research.event_router import EventRouter
            from cc_deep_research.models import ResearchDepth

            request = build_research_run_request(
                query=query,
                depth=ResearchDepth(depth.lower()),
                min_sources=min_sources,
                output=output,
                output_format=output_format,
                no_cross_ref=no_cross_ref,
                tavily_only=tavily_only,
                claude_only=claude_only,
                no_team=no_team,
                team_size=team_size,
                parallel_mode=parallel_mode,
                num_researchers=num_researchers,
                enable_realtime=enable_realtime,
                pdf=pdf,
                workflow=workflow,
                theme=ResearchTheme(theme.lower()) if theme else None,
            )
            service = ResearchRunService()
            prepared_run = service.prepare(request)
            config = prepared_run.config

            if not quiet:
                team_mode = describe_execution_mode(config, request.parallel_mode)
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

            event_router = EventRouter() if request.realtime_enabled else None
            execution_adapter = TerminalResearchRunExecutionAdapter(
                progress=progress and not quiet,
                ui=ui,
            )
            result = service.run_prepared(
                prepared_run,
                monitor=research_monitor,
                execution_adapter=execution_adapter,
                event_router=event_router,
            )
            session = result.session

            if show_timeline and config.search_team.parallel_execution and not quiet:
                research_monitor.show_timeline()

            analysis = session.metadata.get("analysis", {})

            output_path = result.report.path
            if output_path is not None:
                if not quiet:
                    ui.show_report_saved(output_path)
            elif quiet:
                click.echo(result.report.content)
            else:
                ui.show_report(result.report.content, result.report.format.value)

            for artifact in result.artifacts:
                if artifact.kind.value != "pdf" or quiet:
                    continue
                ui.show_report_saved(artifact.path)

            for warning in result.warnings:
                if not quiet:
                    ui.show_error(warning)

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
            if not quiet:
                ui.show_error(str(error))
            if monitor and not quiet:
                research_monitor.section("Error")
                research_monitor.log(f"Research failed: {error}")
            raise click.Abort() from error


__all__ = ["register_research_commands"]
