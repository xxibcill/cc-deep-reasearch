"""Dashboard server command registration."""

from __future__ import annotations

import click


def register_dashboard_command(cli: click.Group) -> None:
    """Register the real-time dashboard server command."""

    @cli.command()
    @click.option(
        "--host",
        type=str,
        default="localhost",
        help="Host to bind to (default: localhost)",
    )
    @click.option(
        "--port",
        type=int,
        default=8000,
        help="Port to listen on (default: 8000)",
    )
    @click.option(
        "--enable-realtime",
        is_flag=True,
        default=True,
        help="Enable real-time WebSocket streaming",
    )
    def dashboard(host: str, port: int, enable_realtime: bool) -> None:
        """Start the real-time monitoring dashboard server."""
        from cc_deep_research.event_router import EventRouter
        from cc_deep_research.web_server import start_server

        click.echo(f"Starting monitoring dashboard on http://{host}:{port}")
        click.echo("Press Ctrl+C to stop the server")

        event_router = EventRouter() if enable_realtime else None
        try:
            start_server(host=host, port=port, event_router=event_router)
        except KeyboardInterrupt:
            click.echo("\nDashboard server stopped.")
        except Exception as error:
            click.echo(f"Error starting dashboard: {error}", err=True)
            raise click.Abort() from error


__all__ = ["register_dashboard_command"]
