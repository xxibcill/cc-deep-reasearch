"""Telemetry command registration."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import click

from cc_deep_research.telemetry import (
    get_default_dashboard_db_path,
    get_default_telemetry_dir,
    ingest_telemetry_to_duckdb,
)


def register_telemetry_commands(cli: click.Group) -> None:
    """Register telemetry and analytics commands."""

    @cli.group()
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
        except RuntimeError as error:
            raise click.ClickException(str(error)) from error
        click.echo(
            f"Ingested {result['sessions']} session summaries and {result['events']} events"
        )

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
        except RuntimeError as error:
            raise click.ClickException(str(error)) from error

        dashboard_script = Path(__file__).resolve().parent.parent / "dashboard_app.py"
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
        except FileNotFoundError as error:
            raise click.ClickException(
                'streamlit is not installed. Install with `pip install "cc-deep-research[dashboard]"`.'
            ) from error
        except subprocess.CalledProcessError as error:
            raise click.ClickException(f"Failed to start dashboard: {error}") from error


__all__ = ["ingest_telemetry_to_duckdb", "register_telemetry_commands", "subprocess"]
