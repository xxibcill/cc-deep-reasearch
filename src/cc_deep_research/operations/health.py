"""Environment health checks for provider config, dashboard connectivity, and data paths."""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from cc_deep_research.config import get_default_config_path, load_config
from cc_deep_research.operations import (
    PathStatus,
    validate_all_data_paths,
    validate_data_path,
)
from cc_deep_research.telemetry import (
    get_default_dashboard_db_path,
    get_default_telemetry_dir,
)


class HealthCheckStatus(StrEnum):
    """Health check status constants."""

    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    SKIPPED = "skipped"


@dataclass
class HealthCheckResult:
    """Result of a single health check."""

    check_id: str
    label: str
    status: HealthCheckStatus
    reason: str | None = None
    remediation: str | None = None
    details: dict[str, Any] | None = None


@dataclass
class HealthReport:
    """Complete environment health report."""

    overall_status: HealthCheckStatus
    checks: list[HealthCheckResult]
    timestamp: str
    version: str | None = None


def _check_config_file() -> HealthCheckResult:
    """Check that the config file is present and readable."""
    config_path = get_default_config_path()
    result = validate_data_path(
        config_path,
        require_exists=False,
        require_readable=True,
        require_writable=False,
        check_permission_safety=True,
    )
    if result.status == PathStatus.FAIL:
        return HealthCheckResult(
            check_id="config_file",
            label="Config file",
            status=HealthCheckStatus.FAIL,
            reason=result.remediation or "Config file is in an unsafe location",
            remediation=result.remediation,
        )
    if result.status == PathStatus.SKIPPED:
        return HealthCheckResult(
            check_id="config_file",
            label="Config file",
            status=HealthCheckStatus.SKIPPED,
            reason="No config file found",
            remediation="Run setup wizard to create a config file",
        )
    if not result.readable:
        return HealthCheckResult(
            check_id="config_file",
            label="Config file",
            status=HealthCheckStatus.FAIL,
            reason="Config file is not readable",
            remediation="Check file permissions",
        )
    return HealthCheckResult(
        check_id="config_file",
        label="Config file",
        status=HealthCheckStatus.PASS,
        reason="Config file is present and readable",
        details={"path": str(config_path)},
    )


def _check_provider_credentials() -> HealthCheckResult:
    """Check that at least one provider has valid credentials configured."""
    config = load_config()

    providers_status: dict[str, Any] = {}
    has_any_provider = False

    # Check Tavily
    tavily_keys = config.tavily.api_keys
    tavily_from_env = bool(os.environ.get("TAVILY_API_KEYS"))
    providers_status["tavily"] = {
        "configured": len(tavily_keys) > 0,
        "from_env": tavily_from_env,
        "count": len(tavily_keys),
    }
    if tavily_keys or tavily_from_env:
        has_any_provider = True

    # Check OpenRouter
    openrouter_keys = config.llm.openrouter.get_api_keys()
    openrouter_from_env = bool(
        os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENROUTER_API_KEYS")
    )
    providers_status["openrouter"] = {
        "enabled": config.llm.openrouter.enabled,
        "configured": len(openrouter_keys) > 0,
        "from_env": openrouter_from_env,
        "count": len(openrouter_keys),
    }
    if config.llm.openrouter.enabled and (openrouter_keys or openrouter_from_env):
        has_any_provider = True

    # Check Cerebras
    cerebras_keys = config.llm.cerebras.get_api_keys()
    cerebras_from_env = bool(
        os.environ.get("CEREBRAS_API_KEY") or os.environ.get("CEREBRAS_API_KEYS")
    )
    providers_status["cerebras"] = {
        "enabled": config.llm.cerebras.enabled,
        "configured": len(cerebras_keys) > 0,
        "from_env": cerebras_from_env,
        "count": len(cerebras_keys),
    }
    if config.llm.cerebras.enabled and (cerebras_keys or cerebras_from_env):
        has_any_provider = True

    # Check Anthropic
    anthropic_keys = config.llm.anthropic.get_api_keys()
    anthropic_from_env = bool(
        os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEYS")
    )
    providers_status["anthropic"] = {
        "enabled": config.llm.anthropic.enabled,
        "configured": len(anthropic_keys) > 0,
        "from_env": anthropic_from_env,
        "count": len(anthropic_keys),
    }
    if config.llm.anthropic.enabled and (anthropic_keys or anthropic_from_env):
        has_any_provider = True

    # Check direct Kimi API
    kimi_keys = config.llm.kimi.get_api_keys()
    kimi_from_env = any(
        os.environ.get(name)
        for name in (
            "MOONSHOT_API_KEY",
            "MOONSHOT_API_KEYS",
            "KIMI_API_KEY",
            "KIMI_API_KEYS",
        )
    )
    providers_status["kimi"] = {
        "enabled": config.llm.kimi.enabled,
        "configured": len(kimi_keys) > 0,
        "from_env": kimi_from_env,
        "count": len(kimi_keys),
    }
    if config.llm.kimi.enabled and (kimi_keys or kimi_from_env):
        has_any_provider = True

    if not has_any_provider:
        return HealthCheckResult(
            check_id="provider_credentials",
            label="Provider credentials",
            status=HealthCheckStatus.FAIL,
            reason="No provider credentials configured",
            remediation="Add at least one API key via the setup wizard or environment variables",
            details={"providers": providers_status},
        )

    # Check for duplicate credentials (config file + env vars)
    conflicts: list[str] = []
    for name, info in providers_status.items():
        if info.get("from_env") and info.get("configured"):
            conflicts.append(name)

    if conflicts:
        return HealthCheckResult(
            check_id="provider_credentials",
            label="Provider credentials",
            status=HealthCheckStatus.WARNING,
            reason=f"Duplicate credentials detected for: {', '.join(conflicts)}",
            remediation="Credentials are set in both config file and environment variables. Environment wins at runtime.",
            details={"providers": providers_status, "conflicts": conflicts},
        )

    return HealthCheckResult(
        check_id="provider_credentials",
        label="Provider credentials",
        status=HealthCheckStatus.PASS,
        reason="At least one provider has credentials configured",
        details={"providers": providers_status},
    )


def _check_duckdb_access() -> HealthCheckResult:
    """Check that DuckDB analytics database is accessible."""
    db_path = get_default_dashboard_db_path()
    result = validate_data_path(
        db_path,
        require_exists=False,
        require_readable=True,
        require_writable=True,
        min_free_space_mb=100.0,
    )
    if result.status == PathStatus.FAIL:
        return HealthCheckResult(
            check_id="duckdb",
            label="DuckDB analytics",
            status=HealthCheckStatus.FAIL,
            reason=result.remediation or "DuckDB path is in an unsafe location",
            remediation=result.remediation,
        )
    if result.status == PathStatus.SKIPPED:
        return HealthCheckResult(
            check_id="duckdb",
            label="DuckDB analytics",
            status=HealthCheckStatus.SKIPPED,
            reason="DuckDB database not yet created",
            remediation="Run a research session to create the analytics database",
            details={"path": str(db_path)},
        )
    if result.status == PathStatus.WARNING and result.free_space_mb is not None:
        return HealthCheckResult(
            check_id="duckdb",
            label="DuckDB analytics",
            status=HealthCheckStatus.WARNING,
            reason=f"Low disk space for DuckDB: {result.free_space_mb:.1f} MB available",
            remediation=result.remediation,
            details={"path": str(db_path), "free_space_mb": result.free_space_mb},
        )
    return HealthCheckResult(
        check_id="duckdb",
        label="DuckDB analytics",
        status=HealthCheckStatus.PASS,
        reason="DuckDB database is accessible",
        details={"path": str(db_path)},
    )


def _check_telemetry_access() -> HealthCheckResult:
    """Check that telemetry directory is accessible."""
    telemetry_dir = get_default_telemetry_dir()
    result = validate_data_path(
        telemetry_dir,
        require_exists=False,
        require_readable=True,
        require_writable=True,
        min_free_space_mb=100.0,
    )
    if result.status == PathStatus.FAIL:
        return HealthCheckResult(
            check_id="telemetry",
            label="Telemetry storage",
            status=HealthCheckStatus.FAIL,
            reason=result.remediation or "Telemetry path is in an unsafe location",
            remediation=result.remediation,
        )
    if result.status == PathStatus.SKIPPED:
        return HealthCheckResult(
            check_id="telemetry",
            label="Telemetry storage",
            status=HealthCheckStatus.SKIPPED,
            reason="Telemetry directory not yet created",
            remediation="Run a research session to create telemetry storage",
            details={"path": str(telemetry_dir)},
        )
    return HealthCheckResult(
        check_id="telemetry",
        label="Telemetry storage",
        status=HealthCheckStatus.PASS,
        reason="Telemetry directory is accessible",
        details={"path": str(telemetry_dir), "free_space_mb": result.free_space_mb},
    )


def _check_websocket_route(host: str, port: int) -> HealthCheckResult:
    """Check that the websocket route is available at the given host/port."""
    # Try to connect to the websocket endpoint
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result_code = sock.connect_ex((host, port))
        sock.close()
        if result_code == 0:
            return HealthCheckResult(
                check_id="websocket_route",
                label="WebSocket route",
                status=HealthCheckStatus.PASS,
                reason=f"Backend is reachable at {host}:{port}",
                details={"host": host, "port": port},
            )
        return HealthCheckResult(
            check_id="websocket_route",
            label="WebSocket route",
            status=HealthCheckStatus.FAIL,
            reason=f"Backend is not reachable at {host}:{port}",
            remediation="Check that the dashboard backend is running",
            details={"host": host, "port": port},
        )
    except OSError as e:
        return HealthCheckResult(
            check_id="websocket_route",
            label="WebSocket route",
            status=HealthCheckStatus.FAIL,
            reason=f"Could not reach backend: {e}",
            remediation="Check network configuration and firewall",
            details={"host": host, "port": port},
        )


def _check_port_availability(port: int) -> HealthCheckResult:
    """Check if a port is already in use."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result_code = sock.connect_ex(("localhost", port))
        sock.close()
        if result_code == 0:
            return HealthCheckResult(
                check_id=f"port_{port}",
                label=f"Port {port} availability",
                status=HealthCheckStatus.WARNING,
                reason=f"Port {port} is already in use",
                remediation="Choose a different port or stop the existing service",
                details={"port": port},
            )
        return HealthCheckResult(
            check_id=f"port_{port}",
            label=f"Port {port} availability",
            status=HealthCheckStatus.PASS,
            reason=f"Port {port} is available",
            details={"port": port},
        )
    except OSError:
        return HealthCheckResult(
            check_id=f"port_{port}",
            label=f"Port {port} availability",
            status=HealthCheckStatus.PASS,
            reason=f"Port {port} is available",
            details={"port": port},
        )


def _check_data_paths() -> HealthCheckResult:
    """Check all critical data paths."""
    validation = validate_all_data_paths()
    summary = validation["summary"]

    if summary["fail"] > 0:
        status = HealthCheckStatus.FAIL
    elif summary["warning"] > 0:
        status = HealthCheckStatus.WARNING
    else:
        status = HealthCheckStatus.PASS

    # Build per-path summary
    path_summary = []
    for name, info in validation["paths"].items():
        if info["status"] in (PathStatus.FAIL, PathStatus.WARNING):
            path_summary.append(
                {
                    "name": name,
                    "status": info["status"],
                    "remediation": info["remediation"],
                }
            )

    return HealthCheckResult(
        check_id="data_paths",
        label="Data paths",
        status=status,
        reason=f"{summary['pass']} paths OK, {summary['warning']} warnings, {summary['fail']} failures",
        remediation="Review path permissions in the settings panel"
        if summary["fail"] > 0 or summary["warning"] > 0
        else None,
        details={"paths": validation["paths"], "summary": summary},
    )


def run_health_checks(
    backend_host: str = "localhost",
    backend_port: int = 8000,
    include_websocket_check: bool = True,
) -> HealthReport:
    """Run all environment health checks.

    Args:
        backend_host: Host where the dashboard backend is expected.
        backend_port: Port where the dashboard backend is expected.
        include_websocket_check: Whether to check websocket route availability.

    Returns:
        HealthReport with all check results.
    """
    from cc_deep_research.__about__ import __version__

    checks: list[HealthCheckResult] = [
        _check_config_file(),
        _check_provider_credentials(),
        _check_data_paths(),
        _check_telemetry_access(),
        _check_duckdb_access(),
    ]

    if include_websocket_check:
        checks.append(_check_websocket_route(backend_host, backend_port))

    # Also check if the configured backend port is available
    checks.append(_check_port_availability(backend_port))

    # Determine overall status
    statuses = [c.status for c in checks]
    if any(s == HealthCheckStatus.FAIL for s in statuses):
        overall = HealthCheckStatus.FAIL
    elif any(s == HealthCheckStatus.WARNING for s in statuses):
        overall = HealthCheckStatus.WARNING
    else:
        overall = HealthCheckStatus.PASS

    from datetime import UTC, datetime

    return HealthReport(
        overall_status=overall,
        checks=checks,
        timestamp=datetime.now(UTC).isoformat(),
        version=__version__,
    )


# Re-export for convenience
__all__ = [
    "HealthCheckResult",
    "HealthCheckStatus",
    "HealthReport",
    "run_health_checks",
]
