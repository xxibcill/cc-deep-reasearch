"""Session command registration."""

from __future__ import annotations

from pathlib import Path

import click

from cc_deep_research.config import load_config
from cc_deep_research.session_store import (
    SessionStore,
    get_default_session_dir,
)
from cc_deep_research.telemetry import (
    get_default_dashboard_db_path,
    get_default_telemetry_dir,
    query_checkpoint_detail,
    query_checkpoint_lineage,
    query_dashboard_data,
    query_latest_resumable_checkpoint,
    query_session_checkpoints,
)
from cc_deep_research.tui import TerminalUI


def get_default_config_path() -> Path:
    """Get the default configuration path."""
    return get_default_session_dir().parent


def register_session_commands(cli: click.Group) -> None:
    """Register saved-session management commands."""

    @cli.group()
    def session() -> None:
        """Manage research sessions."""

    @session.command("list")
    @click.option("--limit", type=int, default=20, help="Maximum number of sessions to show")
    @click.option("--offset", type=int, default=0, help="Number of sessions to skip")
    @click.option("--json", "as_json", is_flag=True, help="Output as JSON")
    @click.option("--archived", is_flag=True, help="Show archived sessions")
    def session_list(limit: int, offset: int, as_json: bool, archived: bool) -> None:
        """List all saved research sessions."""
        store = SessionStore()
        if archived:
            archived_ids = store.get_archived_session_ids()
            all_sessions = store.list_sessions(limit=None)
            sessions = [s for s in all_sessions if s.get("session_id") in archived_ids]
            sessions = sessions[offset:offset + limit] if limit else sessions[offset:]
        else:
            sessions = store.list_sessions(limit=limit, offset=offset)
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

    @session.command("reconcile")
    @click.option("--dry-run", is_flag=True, help="Show what would be cleaned up without making changes")
    @click.option("--json", "as_json", is_flag=True, help="Output as JSON")
    def session_reconcile(dry_run: bool, as_json: bool) -> None:
        """Detect drift between saved sessions, telemetry, and DuckDB."""
        store = SessionStore()
        telemetry_dir = get_default_telemetry_dir()
        db_path = get_default_dashboard_db_path()

        saved_sessions = {s["session_id"] for s in store.list_sessions(limit=None)}
        saved_sessions.update(store.get_archived_session_ids())

        telemetry_sessions: set[str] = set()
        if telemetry_dir.exists():
            for item in telemetry_dir.iterdir():
                if item.is_dir():
                    telemetry_sessions.add(item.name)

        duckdb_sessions: set[str] = set()
        try:
            historical = query_dashboard_data(db_path)
            duckdb_sessions = {row[0] for row in historical.get("sessions", [])}
        except Exception:
            pass

        drift: dict[str, list[str]] = {
            "orphan_telemetry": [],
            "orphan_duckdb": [],
            "missing_telemetry": [],
            "missing_duckdb": [],
        }

        drift["orphan_telemetry"] = sorted(telemetry_sessions - saved_sessions)
        drift["orphan_duckdb"] = sorted(duckdb_sessions - saved_sessions)

        drift["missing_telemetry"] = sorted(saved_sessions - telemetry_sessions)
        drift["missing_duckdb"] = sorted(saved_sessions - duckdb_sessions)

        if as_json:
            import json as json_module

            result = {
                "saved_count": len(saved_sessions),
                "telemetry_count": len(telemetry_sessions),
                "duckdb_count": len(duckdb_sessions),
                "drift": drift,
                "dry_run": dry_run,
            }
            click.echo(json_module.dumps(result, indent=2))
            return

        click.echo("=== Session Storage Reconciliation ===\n")
        click.echo(f"Saved sessions: {len(saved_sessions)}")
        click.echo(f"Telemetry directories: {len(telemetry_sessions)}")
        click.echo(f"DuckDB records: {len(duckdb_sessions)}\n")

        has_issues = False
        for key, value in drift.items():
            if value:
                has_issues = True
                click.echo(f"{key.replace('_', ' ').title()}: {len(value)}")
                for item in value[:10]:
                    click.echo(f"  - {item}")
                if len(value) > 10:
                    click.echo(f"  ... and {len(value) - 10} more")
                click.echo()

        if not has_issues:
            click.echo("No storage drift detected. All storage layers are in sync.")

        if dry_run:
            click.echo("\n[DRY RUN] No changes were made.")
        elif has_issues:
            click.echo("\nRun with --dry-run to preview changes before applying.")

    @session.command("audit")
    @click.option("--limit", type=int, default=50, help="Maximum number of entries to show")
    @click.option("--json", "as_json", is_flag=True, help="Output as JSON")
    def session_audit(limit: int, as_json: bool) -> None:
        """Show audit log of session operations."""
        config_dir = get_default_config_path().parent
        audit_path = config_dir / "sessions" / "audit.jsonl"

        if not audit_path.exists():
            click.echo("No audit log found.")
            return

        entries = []
        try:
            with open(audit_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        import json as json_module
                        entries.append(json_module.loads(line))
        except Exception as e:
            click.echo(f"Error reading audit log: {e}", err=True)
            return

        entries = entries[-limit:] if limit else entries
        entries.reverse()

        if as_json:
            import json as json_module
            click.echo(json_module.dumps(entries, indent=2))
            return

        click.echo("=== Session Audit Log ===\n")
        for entry in entries:
            timestamp = entry.get("timestamp", "unknown")
            action = entry.get("action", "unknown")
            session_id = entry.get("session_id", "unknown")
            details = entry.get("details", "")
            click.echo(f"[{timestamp}] {action}: {session_id}")
            if details:
                click.echo(f"  {details}")
            click.echo()

    @session.command("bundle")
    @click.argument("session_id", required=True)
    @click.option(
        "-o",
        "--output",
        type=click.Path(dir_okay=False, writable=True),
        required=True,
        help="Output file path for the bundle",
    )
    @click.option(
        "--include-payload",
        is_flag=True,
        help="Include full session payload in the bundle",
    )
    @click.option(
        "--include-report",
        is_flag=True,
        help="Include report content in the bundle",
    )
    def session_bundle(
        session_id: str,
        output: str,
        include_payload: bool,
        include_report: bool,
    ) -> None:
        """Export a session as a portable trace bundle.

        The bundle contains events, derived outputs, and optional artifacts
        in a self-contained JSON format suitable for replay and analysis.
        """
        import json as json_module

        store = SessionStore()

        if not store.session_exists(session_id):
            click.echo(f"Error: Session '{session_id}' not found.", err=True)
            raise click.Abort()

        bundle = store.export_trace_bundle(
            session_id,
            include_payload=include_payload,
            include_report=include_report,
        )

        if bundle is None:
            click.echo(f"Error: Failed to export bundle for session '{session_id}'.", err=True)
            raise click.Abort()

        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json_module.dumps(bundle, indent=2, default=str),
            encoding="utf-8",
        )

        event_count = len(bundle.get("events", []))
        click.echo(f"Exported trace bundle for session '{session_id}':")
        click.echo(f"  Schema version: {bundle.get('schema_version')}")
        click.echo(f"  Events: {event_count}")
        click.echo(f"  Output: {output_path}")

    @session.group("checkpoints")
    def checkpoints() -> None:
        """Manage session checkpoints for resume and replay."""

    @checkpoints.command("list")
    @click.argument("session_id", required=True)
    @click.option("--json", "as_json", is_flag=True, help="Output as JSON")
    @click.option("--phase", help="Filter by checkpoint phase")
    def checkpoints_list(session_id: str, as_json: bool, phase: str | None) -> None:
        """List all checkpoints for a session."""
        telemetry_dir = get_default_telemetry_dir()
        session_dir = telemetry_dir / session_id

        if not session_dir.exists():
            click.echo(f"Error: Session '{session_id}' not found.", err=True)
            raise click.Abort()

        manifest = query_session_checkpoints(session_id, base_dir=telemetry_dir)
        checkpoints_list_data = manifest.get("checkpoints", [])

        if phase:
            checkpoints_list_data = [
                cp for cp in checkpoints_list_data
                if cp.get("phase") == phase
            ]

        if not checkpoints_list_data:
            click.echo(f"No checkpoints found for session '{session_id}'.")
            return

        if as_json:
            import json as json_module
            click.echo(json_module.dumps(manifest, indent=2))
            return

        click.echo(f"=== Checkpoints for {session_id} ===\n")
        click.echo(f"Total: {len(checkpoints_list_data)}")
        if manifest.get("latest_checkpoint_id"):
            click.echo(f"Latest: {manifest['latest_checkpoint_id']}")
        if manifest.get("latest_resume_safe_checkpoint_id"):
            click.echo(f"Resume-safe: {manifest['latest_resume_safe_checkpoint_id']}")
        click.echo()

        for cp in checkpoints_list_data:
            status_marker = "✓" if cp.get("resume_safe") else "○"
            replayable_marker = "R" if cp.get("replayable") else "-"
            click.echo(
                f"  {status_marker} {replayable_marker} {cp.get('sequence_number', 0):3d} "
                f"[{cp.get('phase', 'unknown')}] {cp.get('checkpoint_id', 'unknown')[:16]}..."
            )
        click.echo()
        click.echo("Legend: ✓=resume-safe ○=not-safe R=replayable")

    @checkpoints.command("show")
    @click.argument("session_id", required=True)
    @click.argument("checkpoint_id", required=True)
    @click.option("--json", "as_json", is_flag=True, help="Output as JSON")
    @click.option("--lineage", is_flag=True, help="Show checkpoint lineage")
    def checkpoints_show(
        session_id: str,
        checkpoint_id: str,
        as_json: bool,
        lineage: bool,
    ) -> None:
        """Show details for a specific checkpoint."""
        telemetry_dir = get_default_telemetry_dir()

        checkpoint = query_checkpoint_detail(session_id, checkpoint_id, base_dir=telemetry_dir)
        if checkpoint is None:
            click.echo(f"Error: Checkpoint '{checkpoint_id}' not found.", err=True)
            raise click.Abort()

        if lineage:
            lineage_data = query_checkpoint_lineage(session_id, checkpoint_id, base_dir=telemetry_dir)
            checkpoint["lineage"] = [cp.get("checkpoint_id") for cp in lineage_data]

        if as_json:
            import json as json_module
            click.echo(json_module.dumps(checkpoint, indent=2, default=str))
            return

        click.echo(f"=== Checkpoint {checkpoint_id} ===\n")
        click.echo(f"Session: {checkpoint.get('session_id')}")
        click.echo(f"Phase: {checkpoint.get('phase')}")
        click.echo(f"Operation: {checkpoint.get('operation')}")
        click.echo(f"Sequence: {checkpoint.get('sequence_number')}")
        click.echo(f"Status: {checkpoint.get('status')}")
        click.echo(f"Timestamp: {checkpoint.get('timestamp')}")
        click.echo(f"Resume-safe: {checkpoint.get('resume_safe')}")
        click.echo(f"Replayable: {checkpoint.get('replayable')}")

        if checkpoint.get("replayable_reason"):
            click.echo(f"Replayable reason: {checkpoint['replayable_reason']}")

        if checkpoint.get("parent_checkpoint_id"):
            click.echo(f"Parent: {checkpoint['parent_checkpoint_id']}")

        input_ref = checkpoint.get("input_ref")
        if input_ref:
            click.echo("\nInput refs:")
            for key, value in input_ref.items():
                if isinstance(value, dict):
                    click.echo(f"  {key}: <dict>")
                elif isinstance(value, list):
                    click.echo(f"  {key}: [{len(value)} items]")
                else:
                    click.echo(f"  {key}: {value}")

        output_ref = checkpoint.get("output_ref")
        if output_ref:
            click.echo("\nOutput refs:")
            for key, value in output_ref.items():
                if isinstance(value, dict):
                    click.echo(f"  {key}: <dict>")
                elif isinstance(value, list):
                    click.echo(f"  {key}: [{len(value)} items]")
                else:
                    click.echo(f"  {key}: {value}")

        if lineage and checkpoint.get("lineage"):
            click.echo(f"\nLineage ({len(checkpoint['lineage'])} ancestors):")
            for cp_id in checkpoint["lineage"]:
                marker = "→" if cp_id == checkpoint_id else " "
                click.echo(f"  {marker} {cp_id}")

    @checkpoints.command("resume")
    @click.argument("session_id", required=True)
    @click.option("--checkpoint-id", help="Specific checkpoint to resume from")
    @click.option("--json", "as_json", is_flag=True, help="Output as JSON")
    def checkpoints_resume(
        session_id: str,
        checkpoint_id: str | None,
        as_json: bool,
    ) -> None:
        """Get resume information for a session from a checkpoint."""
        telemetry_dir = get_default_telemetry_dir()
        session_dir = telemetry_dir / session_id

        if not session_dir.exists():
            click.echo(f"Error: Session '{session_id}' not found.", err=True)
            raise click.Abort()

        # Get the checkpoint to resume from
        if checkpoint_id is None:
            checkpoint = query_latest_resumable_checkpoint(session_id, base_dir=telemetry_dir)
            if checkpoint is None:
                click.echo(f"Error: No resumable checkpoint available for session '{session_id}'.", err=True)
                raise click.Abort()
            checkpoint_id = checkpoint["checkpoint_id"]
        else:
            checkpoint = query_checkpoint_detail(session_id, checkpoint_id, base_dir=telemetry_dir)
            if checkpoint is None:
                click.echo(f"Error: Checkpoint '{checkpoint_id}' not found.", err=True)
                raise click.Abort()
            if not checkpoint.get("resume_safe"):
                click.echo(f"Error: Checkpoint '{checkpoint_id}' is not safe to resume from.", err=True)
                raise click.Abort()

        lineage = query_checkpoint_lineage(session_id, checkpoint_id, base_dir=telemetry_dir)
        lineage_ids = [cp.get("checkpoint_id") for cp in lineage]

        result = {
            "session_id": session_id,
            "resumed_from_checkpoint_id": checkpoint_id,
            "checkpoint_phase": checkpoint.get("phase"),
            "checkpoint_operation": checkpoint.get("operation"),
            "lineage_depth": len(lineage_ids),
            "input_ref": checkpoint.get("input_ref"),
        }

        if as_json:
            import json as json_module
            click.echo(json_module.dumps(result, indent=2))
            return

        click.echo(f"=== Resume Information ===\n")
        click.echo(f"Session: {session_id}")
        click.echo(f"Resume from: {checkpoint_id}")
        click.echo(f"Phase: {checkpoint.get('phase')}")
        click.echo(f"Operation: {checkpoint.get('operation')}")
        click.echo(f"Lineage depth: {len(lineage_ids)}")

        input_ref = checkpoint.get("input_ref")
        if input_ref:
            click.echo("\nInput refs available:")
            for key in input_ref.keys():
                click.echo(f"  - {key}")

        click.echo("\nNote: Use the API endpoint POST /api/sessions/{session_id}/resume to execute resume.")

    @checkpoints.command("rerun")
    @click.argument("session_id", required=True)
    @click.argument("checkpoint_id", required=True)
    @click.option("--json", "as_json", is_flag=True, help="Output as JSON")
    def checkpoints_rerun(
        session_id: str,
        checkpoint_id: str,
        as_json: bool,
    ) -> None:
        """Get rerun information for a specific checkpoint step."""
        telemetry_dir = get_default_telemetry_dir()

        checkpoint = query_checkpoint_detail(session_id, checkpoint_id, base_dir=telemetry_dir)
        if checkpoint is None:
            click.echo(f"Error: Checkpoint '{checkpoint_id}' not found.", err=True)
            raise click.Abort()

        if not checkpoint.get("replayable"):
            reason = checkpoint.get("replayable_reason", "Unknown reason")
            click.echo(f"Error: Checkpoint is not replayable: {reason}", err=True)
            raise click.Abort()

        result = {
            "session_id": session_id,
            "checkpoint_id": checkpoint_id,
            "phase": checkpoint.get("phase"),
            "operation": checkpoint.get("operation"),
            "input_ref": checkpoint.get("input_ref"),
            "output_ref": checkpoint.get("output_ref"),
        }

        if as_json:
            import json as json_module
            click.echo(json_module.dumps(result, indent=2))
            return

        click.echo(f"=== Rerun Information ===\n")
        click.echo(f"Session: {session_id}")
        click.echo(f"Checkpoint: {checkpoint_id}")
        click.echo(f"Phase: {checkpoint.get('phase')}")
        click.echo(f"Operation: {checkpoint.get('operation')}")

        input_ref = checkpoint.get("input_ref")
        if input_ref:
            click.echo("\nInput refs:")
            for key, value in input_ref.items():
                if isinstance(value, dict):
                    click.echo(f"  {key}: <dict>")
                elif isinstance(value, list):
                    click.echo(f"  {key}: [{len(value)} items]")
                else:
                    click.echo(f"  {key}: {value}")

        output_ref = checkpoint.get("output_ref")
        if output_ref:
            click.echo("\nOutput refs (from original run):")
            for key, value in output_ref.items():
                if isinstance(value, dict):
                    click.echo(f"  {key}: <dict>")
                elif isinstance(value, list):
                    click.echo(f"  {key}: [{len(value)} items]")
                else:
                    click.echo(f"  {key}: {value}")

        click.echo("\nNote: Use the API endpoint POST /api/sessions/{session_id}/rerun-step to execute rerun.")


__all__ = ["register_session_commands"]
