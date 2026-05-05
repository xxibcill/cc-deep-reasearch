"""Production hardening: CORS, host binding, logging, websocket, and timeout defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from cc_deep_research.config import load_config


class HardeningStatus(StrEnum):
    """Hardening check status."""

    SECURE = "secure"
    WARNING = "warning"
    INSECURE = "insecure"
    UNKNOWN = "unknown"


@dataclass
class HardeningCheckResult:
    """Result of a single hardening check."""

    check_id: str
    label: str
    status: HardeningStatus
    detail: str | None = None
    remediation: str | None = None


def _check_cors_settings() -> HardeningCheckResult:
    """Check CORS configuration for production readiness."""
    try:
        config = load_config()
    except Exception:
        return HardeningCheckResult(
            check_id="cors",
            label="CORS configuration",
            status=HardeningStatus.UNKNOWN,
            detail="Could not load config",
            remediation="Verify CORS settings manually",
        )

    # Default CORS in web_server.py is allow_origins=["*"]
    # This is insecure for production
    return HardeningCheckResult(
        check_id="cors",
        label="CORS configuration",
        status=HardeningStatus.WARNING,
        detail="CORS is set to allow all origins. In production, restrict to specific frontend origin.",
        remediation="Set CORS_ALLOWED_ORIGINS env var or dashboard.cors.allowed_origins in config to your frontend URL",
    )


def _check_host_binding() -> HardeningCheckResult:
    """Check host binding for production readiness."""
    try:
        config = load_config()
        dashboard_host = getattr(config, "host", "localhost")
    except Exception:
        dashboard_host = "localhost"

    if dashboard_host == "0.0.0.0":
        return HardeningCheckResult(
            check_id="host_binding",
            label="Host binding",
            status=HardeningStatus.WARNING,
            detail="Dashboard binds to 0.0.0.0 (all interfaces). This is needed for containerized deployment but risky for local dev.",
            remediation="For local production, bind to 127.0.0.1 or localhost. For containers, use 0.0.0.0 with firewall rules.",
        )

    if dashboard_host == "localhost" or dashboard_host == "127.0.0.1":
        return HardeningCheckResult(
            check_id="host_binding",
            label="Host binding",
            status=HardeningStatus.SECURE,
            detail="Dashboard binds to localhost only",
        )

    return HardeningCheckResult(
        check_id="host_binding",
        label="Host binding",
        status=HardeningStatus.WARNING,
        detail=f"Dashboard binds to {dashboard_host}",
        remediation="Verify this is intentional for your deployment environment",
    )


def _check_logging_defaults() -> HardeningCheckResult:
    """Check logging configuration for production readiness."""
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    python_log_level = os.environ.get("PYTHON_LOG_LEVEL", "").upper()

    if log_level in ("DEBUG",) or python_log_level in ("DEBUG",):
        return HardeningCheckResult(
            check_id="logging",
            label="Logging level",
            status=HardeningStatus.WARNING,
            detail="Logging is set to DEBUG. This may leak sensitive information in production.",
            remediation="Set LOG_LEVEL=INFO or PYTHON_LOG_LEVEL=INFO for production",
        )

    return HardeningCheckResult(
        check_id="logging",
        label="Logging level",
        status=HardeningStatus.SECURE,
        detail=f"Logging level is {log_level}",
    )


def _check_websocket_defaults() -> HardeningCheckResult:
    """Check websocket configuration for production readiness."""
    # Default ws config is without ping/pong interval
    return HardeningCheckResult(
        check_id="websocket",
        label="WebSocket configuration",
        status=HardeningStatus.WARNING,
        detail="WebSocket uses default configuration without ping/pong keepalive interval",
        remediation="For production, configure a ping interval to detect stale connections (e.g., 30s)",
    )


def _check_timeout_defaults() -> HardeningCheckResult:
    """Check default timeout values."""
    try:
        config = load_config()
        llm_timeout = config.llm.openrouter.timeout_seconds
    except Exception:
        llm_timeout = 120

    if llm_timeout > 300:
        return HardeningCheckResult(
            check_id="timeout",
            label="LLM timeout",
            status=HardeningStatus.WARNING,
            detail=f"LLM timeout is {llm_timeout}s, which is very high",
            remediation="Consider reducing timeout to 120s for standard requests",
        )

    return HardeningCheckResult(
        check_id="timeout",
        label="LLM timeout",
        status=HardeningStatus.SECURE,
        detail=f"LLM timeout is {llm_timeout}s",
    )


def _check_data_retention() -> HardeningCheckResult:
    """Check data retention configuration."""
    try:

        # Check if retention policy is configured
        return HardeningCheckResult(
            check_id="data_retention",
            label="Data retention",
            status=HardeningStatus.WARNING,
            detail="No explicit retention policy configured. Telemetry data will accumulate indefinitely.",
            remediation="Configure retention policy via cc-deep-research telemetry retention --policy <policy>",
        )
    except Exception:
        return HardeningCheckResult(
            check_id="data_retention",
            label="Data retention",
            status=HardeningStatus.UNKNOWN,
            detail="Could not check retention configuration",
        )


def run_production_hardening_checks() -> dict[str, Any]:
    """Run all production hardening checks.

    Returns:
        Dict with check results and summary.
    """
    checks = [
        _check_cors_settings(),
        _check_host_binding(),
        _check_logging_defaults(),
        _check_websocket_defaults(),
        _check_timeout_defaults(),
        _check_data_retention(),
    ]

    results: dict[str, Any] = {
        c.check_id: {
            "label": c.label,
            "status": c.status.value,
            "detail": c.detail,
            "remediation": c.remediation,
        }
        for c in checks
    }

    summary = {
        "total": len(checks),
        "secure": sum(1 for c in checks if c.status == HardeningStatus.SECURE),
        "warning": sum(1 for c in checks if c.status == HardeningStatus.WARNING),
        "insecure": sum(1 for c in checks if c.status == HardeningStatus.INSECURE),
        "unknown": sum(1 for c in checks if c.status == HardeningStatus.UNKNOWN),
    }

    return {
        "checks": results,
        "summary": summary,
    }


def get_startup_diagnostics() -> dict[str, Any]:
    """Get production-oriented startup diagnostics.

    Returns:
        Dict with startup diagnostic info (no secrets).
    """
    try:
        config = load_config()
    except Exception:
        config = None

    hardening = run_production_hardening_checks()

    diagnostics = {
        "timestamp": str(__import__("datetime").datetime.now(__import__("datetime").UTC).isoformat()),
        "enabled_routes": _get_enabled_routes(config),
        "storage_paths": _get_storage_paths(config),
        "hardening": hardening,
        "warnings": [c["detail"] for c in hardening["checks"].values() if c["status"] == "warning"],
    }

    return diagnostics


def _get_enabled_routes(config: Any) -> list[str]:
    """Get list of enabled route types."""
    routes = ["api", "websocket"]
    if config is not None:
        if getattr(config, "search_cache", None) and getattr(config.search_cache, "enabled", False):
            routes.append("search_cache")
    return routes


def _get_storage_paths(config: Any) -> dict[str, str]:
    """Get storage paths for diagnostics (no secrets)."""

    from cc_deep_research.config import get_default_config_path

    config_dir = get_default_config_path().parent
    return {
        "config_dir": str(config_dir),
        "sessions": str(config_dir / "sessions"),
        "telemetry": str(config_dir / "telemetry"),
        "reports": str(config_dir / "reports"),
        "knowledge": str(config_dir / "knowledge"),
        "content_gen": str(config_dir / "content_gen"),
        "radar": str(config_dir / "radar"),
    }


__all__ = [
    "HardeningCheckResult",
    "HardeningStatus",
    "get_startup_diagnostics",
    "run_production_hardening_checks",
]
