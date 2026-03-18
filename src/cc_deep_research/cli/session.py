"""Session command registration."""

from __future__ import annotations

from pathlib import Path

import click

from cc_deep_research.config import load_config
from cc_deep_research.session_store import SessionStore
from cc_deep_research.tui import TerminalUI


def register_session_commands(cli: click.Group) -> None:
    """Register saved-session management commands."""

    @cli.group()
    def session() -> None:
        """Manage research sessions."""

    @session.command("list")
    @click.option("--limit", type=int, default=20, help="Maximum number of sessions to show")
    @click.option("--offset", type=int, default=0, help="Number of sessions to skip")
    @click.option("--json", "as_json", is_flag=True, help="Output as JSON")
    def session_list(limit: int, offset: int, as_json: bool) -> None:
        """List all saved research sessions."""
        sessions = SessionStore().list_sessions(limit=limit, offset=offset)
        if not sessions:
            click.echo("No saved sessions found.")
            return

        if as_json:
            import json as json_module

            click.echo(json_module.dumps(sessions, indent=2))
            return

        TerminalUI(enabled=True).show_session_list(sessions)

    @session.command("show")
    @click.argument("session_id", required=True)
    @click.option("--json", "as_json", is_flag=True, help="Output as JSON")
    def session_show(session_id: str, as_json: bool) -> None:
        """Show details of a specific research session."""
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

        TerminalUI(enabled=True).show_session_details(session_obj)

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
        """Export a research session to a file."""
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
        TerminalUI(enabled=True).show_report_saved(output_path)

    @session.command("delete")
    @click.argument("session_id", required=True)
    @click.option("--force", is_flag=True, help="Skip confirmation prompt")
    def session_delete(session_id: str, force: bool) -> None:
        """Delete a research session."""
        store = SessionStore()
        if not store.session_exists(session_id):
            click.echo(f"Error: Session '{session_id}' not found.", err=True)
            raise click.Abort()

        if not force and not click.confirm(f"Delete session '{session_id}'?"):
            click.echo("Aborted.")
            return

        result = store.delete_session(session_id)
        if result.deleted:
            click.echo(f"Session '{session_id}' deleted.")
        elif result.missing:
            click.echo(f"Error: Session '{session_id}' not found.", err=True)
            raise click.Abort()
        else:
            click.echo(f"Error: Failed to delete session '{session_id}': {result.error}", err=True)
            raise click.Abort()


__all__ = ["register_session_commands"]
