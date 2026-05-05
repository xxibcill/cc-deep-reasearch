"""Operations routes: health checks, backup, service management, and secrets."""

from __future__ import annotations

from ipaddress import ip_address
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from cc_deep_research.operations import (
    get_recommended_directory_layout,
    validate_all_data_paths,
)
from cc_deep_research.operations.backup import (
    BackupDryRunResult,
    BackupManifest,
    create_backup,
    plan_backup,
    validate_backup,
)
from cc_deep_research.operations.hardening import (
    get_startup_diagnostics,
    run_production_hardening_checks,
)
from cc_deep_research.operations.health import (
    run_health_checks,
)
from cc_deep_research.operations.runbooks import (
    get_runbook,
    get_support_checklist,
    list_runbooks,
)
from cc_deep_research.operations.secrets import (
    get_rotation_guidance,
    get_secrets_inventory,
)
from cc_deep_research.operations.service import (
    check_service_status,
    detect_startup_conflicts,
    stop_service,
)
from cc_deep_research.operations.service import (
    get_startup_diagnostics as get_service_diagnostics,
)
from cc_deep_research.operations.setup import (
    apply_profile,
    create_initial_config,
    list_profiles,
    run_setup_validation,
)
from cc_deep_research.operations.upgrade import (
    generate_upgrade_report,
    get_rollback_instructions,
    run_post_upgrade_validation,
    run_pre_upgrade_validation,
)


def _is_local_request(request: Request) -> bool:
    """Return True when the request originates from the local host."""
    host = request.client.host if request.client is not None else ""
    return _is_loopback_host(host)


def _is_loopback_host(host: str | None) -> bool:
    """Return True for localhost or loopback IP literals."""
    if host is None:
        return False
    normalized = host.strip("[]").lower()
    if normalized == "localhost":
        return True
    try:
        return ip_address(normalized).is_loopback
    except ValueError:
        return False


def _is_local_url(value: str) -> bool:
    """Return True when a URL has a loopback host."""
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        return False
    return _is_loopback_host(parsed.hostname)


def _has_local_origin(request: Request) -> bool:
    """Allow same-machine callers while rejecting browser cross-site POSTs."""
    origin = request.headers.get("origin")
    if origin:
        return _is_local_url(origin)

    referer = request.headers.get("referer")
    if referer:
        return _is_local_url(referer)

    return True


def register_operations_routes(app: FastAPI) -> None:
    """Register operations routes on the FastAPI app.

    Args:
        app: The FastAPI application instance.
    """

    # --- Health Checks ---
    @app.get("/api/health")
    async def get_health(
        host: str = "localhost",
        port: int = 8000,
        include_websocket: bool = True,
    ) -> JSONResponse:
        """Run environment health checks and return results."""
        try:
            report = run_health_checks(
                backend_host=host,
                backend_port=port,
                include_websocket_check=include_websocket,
            )
            return JSONResponse(content={
                "overall_status": report.overall_status,
                "timestamp": report.timestamp,
                "version": report.version,
                "checks": [
                    {
                        "check_id": c.check_id,
                        "label": c.label,
                        "status": c.status,
                        "reason": c.reason,
                        "remediation": c.remediation,
                        "details": c.details,
                    }
                    for c in report.checks
                ],
            })
        except Exception as e:
            return JSONResponse(
                content={"error": f"Health check failed: {e}"},
                status_code=500,
            )

    # --- Data Path Permissions ---
    @app.get("/api/operations/data-paths")
    async def get_data_paths() -> JSONResponse:
        """Validate all critical data paths."""
        validation = validate_all_data_paths()
        return JSONResponse(content=validation)

    @app.get("/api/operations/data-paths/layout")
    async def get_directory_layout() -> JSONResponse:
        """Return the recommended directory layout."""
        layout = get_recommended_directory_layout()
        return JSONResponse(content={"layout": layout})

    # --- Backup and Restore ---
    @app.get("/api/operations/backup/plan")
    async def plan_backup_route(
        include_sessions: bool = True,
        include_telemetry: bool = True,
        include_knowledge: bool = True,
        include_content_gen: bool = True,
        include_config: bool = True,
        include_radar: bool = True,
    ) -> JSONResponse:
        """Plan a backup without creating it."""
        result = plan_backup(
            include_sessions=include_sessions,
            include_telemetry=include_telemetry,
            include_knowledge=include_knowledge,
            include_content_gen=include_content_gen,
            include_config=include_config,
            include_radar=include_radar,
        )
        return JSONResponse(content={
            "estimated_total_bytes": result.estimated_total_bytes,
            "estimated_compressed_bytes": result.estimated_compressed_bytes,
            "would_include": result.would_include,
            "excluded": result.excluded,
            "warnings": result.warnings,
        })

    @app.post("/api/operations/backup/create")
    async def create_backup_route(
        backup_path: str,
        include_sessions: bool = True,
        include_telemetry: bool = True,
        include_knowledge: bool = True,
        include_content_gen: bool = True,
        include_config: bool = True,
        include_radar: bool = True,
        dry_run: bool = False,
    ) -> JSONResponse:
        """Create a backup archive."""
        from pathlib import Path

        result = create_backup(
            backup_path=Path(backup_path),
            include_sessions=include_sessions,
            include_telemetry=include_telemetry,
            include_knowledge=include_knowledge,
            include_content_gen=include_content_gen,
            include_config=include_config,
            include_radar=include_radar,
            dry_run=dry_run,
        )
        if dry_run:
            dr = result if isinstance(result, BackupDryRunResult) else None
            if dr:
                return JSONResponse(content={
                    "dry_run": True,
                    "estimated_total_bytes": dr.estimated_total_bytes,
                    "estimated_compressed_bytes": dr.estimated_compressed_bytes,
                    "would_include": dr.would_include,
                })
        manifest = result if isinstance(result, BackupManifest) else None
        if manifest:
            return JSONResponse(content=manifest.to_dict())
        return JSONResponse(content={"error": "Backup failed"}, status_code=500)

    @app.get("/api/operations/backup/validate/{backup_path:path}")
    async def validate_backup_route(backup_path: str) -> JSONResponse:
        """Validate a backup archive."""
        from pathlib import Path

        result = validate_backup(Path(backup_path))
        return JSONResponse(content={
            "valid": result.valid,
            "compatible": result.compatible,
            "errors": result.errors,
            "warnings": result.warnings,
            "manifest": result.manifest.to_dict() if result.manifest else None,
        })

    # --- Service Management ---
    @app.get("/api/operations/service/status")
    async def get_service_status(
        service_name: str = "dashboard",
        port: int | None = None,
    ) -> JSONResponse:
        """Check service status."""
        info = check_service_status(service_name, port=port)
        return JSONResponse(content={
            "name": info.name,
            "status": info.status,
            "pid": info.pid,
            "port": info.port,
            "backend_url": info.backend_url,
            "frontend_url": info.frontend_url,
            "log_location": info.log_location,
            "started_at": info.started_at,
            "error": info.error,
        })

    @app.get("/api/operations/service/conflicts")
    async def get_startup_conflicts() -> JSONResponse:
        """Detect startup conflicts."""
        conflicts = detect_startup_conflicts()
        return JSONResponse(content={"conflicts": conflicts})

    @app.get("/api/operations/service/diagnostics")
    async def get_service_diag() -> JSONResponse:
        """Get startup diagnostics."""
        diagnostics = get_service_diagnostics()
        return JSONResponse(content=diagnostics)

    @app.post("/api/operations/service/stop")
    async def stop_service_route(
        request: Request,
        service_name: str = "dashboard",
        port: int | None = None,
    ) -> JSONResponse:
        """Stop a running service."""
        if not _is_local_request(request) or not _has_local_origin(request):
            return JSONResponse(
                content={
                    "success": False,
                    "message": "Refusing non-local or cross-origin service stop request",
                },
                status_code=403,
            )
        result = stop_service(service_name, port=port)
        status_code = 403 if str(result.get("message", "")).startswith("Refusing") else 200
        return JSONResponse(content=result, status_code=status_code)

    # --- Secrets Inventory ---
    @app.get("/api/operations/secrets/inventory")
    async def get_secrets() -> JSONResponse:
        """Get secrets inventory without exposing values."""
        inventory = get_secrets_inventory()
        return JSONResponse(content={
            "timestamp": inventory.timestamp,
            "credentials": [
                {
                    "field": c.field,
                    "provider": c.provider,
                    "status": c.status,
                    "count": c.count,
                    "source": c.source,
                    "warnings": c.warnings,
                    "rotation_guidance": c.rotation_guidance,
                }
                for c in inventory.credentials
            ],
            "total_count": inventory.total_count,
            "healthy_count": inventory.healthy_count,
            "warning_count": inventory.warning_count,
            "critical_count": inventory.critical_count,
        })

    @app.get("/api/operations/secrets/rotation")
    async def get_rotation() -> JSONResponse:
        """Get credential rotation guidance."""
        guidance = get_rotation_guidance()
        return JSONResponse(content={"guidance": guidance})

    # --- Production Hardening ---
    @app.get("/api/operations/hardening")
    async def get_hardening() -> JSONResponse:
        """Run production hardening checks."""
        result = run_production_hardening_checks()
        return JSONResponse(content=result)

    @app.get("/api/operations/hardening/startup-diagnostics")
    async def get_hardening_startup_diagnostics() -> JSONResponse:
        """Get startup diagnostics (production-oriented)."""
        diagnostics = get_startup_diagnostics()
        return JSONResponse(content=diagnostics)

    # --- Setup Wizard ---
    @app.get("/api/operations/setup/profiles")
    async def get_setup_profiles() -> JSONResponse:
        """List available config profiles."""
        profiles = list_profiles()
        return JSONResponse(content={"profiles": profiles})

    @app.post("/api/operations/setup/profiles/{profile_type}/apply")
    async def apply_setup_profile(profile_type: str) -> JSONResponse:
        """Apply a config profile."""
        from cc_deep_research.operations.setup import ProfileType

        try:
            pt = ProfileType(profile_type)
        except ValueError:
            return JSONResponse(
                content={"error": f"Unknown profile type: {profile_type}"},
                status_code=400,
            )

        try:
            updated = apply_profile(pt)
            return JSONResponse(content={
                "success": True,
                "profile": profile_type,
                "config": updated.model_dump(mode="json"),
            })
        except Exception as e:
            return JSONResponse(
                content={"error": str(e)},
                status_code=400,
            )

    @app.get("/api/operations/setup/validation")
    async def get_setup_validation() -> JSONResponse:
        """Validate current setup state."""
        is_valid, steps = run_setup_validation()
        return JSONResponse(content={
            "valid": is_valid,
            "steps": [
                {
                    "step_id": s.step_id,
                    "label": s.label,
                    "description": s.description,
                    "required": s.required,
                    "validated": s.validated,
                    "skipped": s.skipped,
                    "error": s.error,
                }
                for s in steps
            ],
        })

    @app.post("/api/operations/setup/initial")
    async def create_initial_config_route(
        profile_type: str = "local_production",
    ) -> JSONResponse:
        """Create initial config file."""
        from cc_deep_research.operations.setup import ProfileType

        try:
            pt = ProfileType(profile_type)
        except ValueError:
            return JSONResponse(
                content={"error": f"Unknown profile type: {profile_type}"},
                status_code=400,
            )

        result = create_initial_config(profile_type=pt)
        return JSONResponse(content={
            "success": result.success,
            "profile_applied": result.profile_applied,
            "config_path": str(result.config_path) if result.config_path else None,
            "steps_completed": result.steps_completed,
            "steps_total": result.steps_total,
            "errors": result.errors,
        })

    # --- Upgrade Validation ---
    @app.get("/api/operations/upgrade/validate")
    async def get_upgrade_validation(
        version_from: str | None = None,
        version_to: str | None = None,
    ) -> JSONResponse:
        """Run pre-upgrade validation checks."""
        checks = run_pre_upgrade_validation(version_from, version_to)
        return JSONResponse(content={
            "checks": [
                {
                    "check_id": c.check_id,
                    "label": c.label,
                    "status": c.status,
                    "detail": c.detail,
                    "blockers": c.blockers,
                    "remediation": c.remediation,
                }
                for c in checks
            ],
        })

    @app.get("/api/operations/upgrade/report")
    async def get_upgrade_report(
        version_from: str | None = None,
        version_to: str | None = None,
    ) -> JSONResponse:
        """Generate complete upgrade report."""
        report = generate_upgrade_report(version_from, version_to)
        return JSONResponse(content={
            "timestamp": report.timestamp,
            "version_from": report.version_from,
            "version_to": report.version_to,
            "rollback_recommended": report.rollback_recommended,
            "warnings": report.warnings,
            "errors": report.errors,
            "pre_upgrade_checks": [
                {
                    "check_id": c.check_id,
                    "label": c.label,
                    "status": c.status,
                    "detail": c.detail,
                    "blockers": c.blockers,
                    "remediation": c.remediation,
                }
                for c in report.pre_upgrade_checks
            ],
            "post_upgrade_checks": [
                {
                    "check_id": c.check_id,
                    "label": c.label,
                    "status": c.status,
                    "detail": c.detail,
                    "blockers": c.blockers,
                    "remediation": c.remediation,
                }
                for c in report.post_upgrade_checks
            ],
        })

    @app.get("/api/operations/upgrade/rollback")
    async def get_rollback(backup_id: str | None = None) -> JSONResponse:
        """Get rollback instructions."""
        instructions = get_rollback_instructions(backup_id)
        return JSONResponse(content=instructions)

    @app.get("/api/operations/upgrade/post-validation")
    async def get_post_upgrade_validation() -> JSONResponse:
        """Run post-upgrade validation checks."""
        checks = run_post_upgrade_validation()
        return JSONResponse(content={
            "checks": [
                {
                    "check_id": c.check_id,
                    "label": c.label,
                    "status": c.status,
                    "detail": c.detail,
                    "blockers": c.blockers,
                    "remediation": c.remediation,
                }
                for c in checks
            ],
        })

    # --- Runbooks ---
    @app.get("/api/operations/runbooks")
    async def get_runbooks() -> JSONResponse:
        """List all available runbooks."""
        return JSONResponse(content={"runbooks": list_runbooks()})

    @app.get("/api/operations/runbooks/{runbook_id}")
    async def get_runbook_detail(runbook_id: str) -> JSONResponse:
        """Get a specific runbook."""
        rb = get_runbook(runbook_id)
        if not rb:
            return JSONResponse(
                content={"error": f"Runbook not found: {runbook_id}"},
                status_code=404,
            )
        return JSONResponse(content={
            "runbook_id": rb.runbook_id,
            "title": rb.title,
            "summary": rb.summary,
            "symptoms": rb.symptoms,
            "steps": [
                {
                    "step": s.step,
                    "description": s.description,
                    "command": s.command,
                    "expected_output": s.expected_output,
                    "escalation_criteria": s.escalation_criteria,
                }
                for s in rb.steps
            ],
            "related_checks": rb.related_checks,
            "related_runbooks": rb.related_runbooks,
        })

    @app.get("/api/operations/support/checklist")
    async def get_support() -> JSONResponse:
        """Get support checklist for incident response."""
        return JSONResponse(content=get_support_checklist())
