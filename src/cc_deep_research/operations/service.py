"""Local service management and startup diagnostics."""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from cc_deep_research.config import load_config


class ServiceStatus(StrEnum):
    """Service status constants."""

    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class ServiceInfo:
    """Information about a running service."""

    name: str
    status: ServiceStatus
    pid: int | None = None
    port: int | None = None
    frontend_url: str | None = None
    backend_url: str | None = None
    log_location: str | None = None
    started_at: str | None = None
    error: str | None = None


@dataclass
class ServiceStartResult:
    """Result of starting a service."""

    success: bool
    service: ServiceInfo | None = None
    message: str | None = None


def _get_dashboard_backend_port() -> int:
    """Get the configured dashboard backend port."""
    try:
        config = load_config()
        return getattr(config, "port", 8000)
    except Exception:
        return 8000


def _get_dashboard_frontend_port() -> int:
    """Get the configured dashboard frontend port."""
    try:
        config = load_config()
        return getattr(config, "dashboard", type("C", (), {"port": 3000}))  # type: ignore[arg-type]
    except Exception:
        return 3000


def _is_port_in_use(port: int) -> bool:
    """Check if a port is currently in use."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(("localhost", port))
        sock.close()
        return result == 0
    except OSError:
        return False


def _find_process_by_port(port: int) -> int | None:
    """Find the PID of the process using a given port."""
    try:
        result = subprocess.run(
            ["lsof", "-i", f":{port}", "-t"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(result.stdout.strip().split("\n")[0])
    except (OSError, subprocess.TimeoutExpired, ValueError):
        pass
    return None


def _get_log_locations() -> dict[str, Path]:
    """Return known log file locations."""
    config_dir = Path.home() / ".config" / "cc-deep-research"
    return {
        "config_dir": config_dir,
        "telemetry_dir": config_dir / "telemetry",
        "session_dir": config_dir / "sessions",
    }


def check_service_status(
    service_name: str = "dashboard",
    port: int | None = None,
) -> ServiceInfo:
    """Check the status of a named service.

    Args:
        service_name: Name of the service (e.g., 'dashboard', 'backend').
        port: Port to check. If not provided, uses default dashboard port.

    Returns:
        ServiceInfo with current status.
    """
    if port is None:
        port = _get_dashboard_backend_port()

    if _is_port_in_use(port):
        pid = _find_process_by_port(port)
        return ServiceInfo(
            name=service_name,
            status=ServiceStatus.RUNNING,
            pid=pid,
            port=port,
            backend_url=f"http://localhost:{port}",
            frontend_url="http://localhost:3000",
            log_location=str(_get_log_locations()),
            started_at=datetime.now(UTC).isoformat(),
        )

    return ServiceInfo(
        name=service_name,
        status=ServiceStatus.STOPPED,
        port=port,
        error=None,
    )


def detect_startup_conflicts() -> list[dict[str, Any]]:
    """Detect common startup conflicts before attempting to start services.

    Returns:
        List of detected conflicts with remediation info.
    """
    conflicts: list[dict[str, Any]] = []

    backend_port = _get_dashboard_backend_port()
    if _is_port_in_use(backend_port):
        pid = _find_process_by_port(backend_port)
        conflicts.append({
            "type": "port_occupied",
            "port": backend_port,
            "pid": pid,
            "message": f"Backend port {backend_port} is already in use",
            "remediation": f"Stop the existing process on port {backend_port} or choose a different port",
            "commands": [
                f"kill {pid}" if pid else None,
                f"lsof -i :{backend_port}",
            ],
        })

    frontend_port = _get_dashboard_frontend_port()
    if frontend_port != backend_port and _is_port_in_use(frontend_port):
        pid = _find_process_by_port(frontend_port)
        conflicts.append({
            "type": "port_occupied",
            "port": frontend_port,
            "pid": pid,
            "message": f"Frontend port {frontend_port} is already in use",
            "remediation": f"Stop the existing process on port {frontend_port} or choose a different port",
            "commands": [
                f"kill {pid}" if pid else None,
                f"lsof -i :{frontend_port}",
            ],
        })

    # Check Node.js availability
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            conflicts.append({
                "type": "missing_dependency",
                "dependency": "node",
                "message": "Node.js is not installed or not in PATH",
                "remediation": "Install Node.js 18+ from https://nodejs.org",
            })
    except OSError:
        conflicts.append({
            "type": "missing_dependency",
            "dependency": "node",
            "message": "Node.js is not installed or not in PATH",
            "remediation": "Install Node.js 18+ from https://nodejs.org",
        })

    # Check Python availability
    if sys.executable is None:
        conflicts.append({
            "type": "missing_dependency",
            "dependency": "python",
            "message": "Python is not accessible",
            "remediation": "Ensure Python 3.11+ is installed",
        })

    return conflicts


def get_startup_diagnostics() -> dict[str, Any]:
    """Get startup diagnostics for the dashboard and backend.

    Returns:
        Dict with diagnostics info.
    """
    backend_port = _get_dashboard_backend_port()
    frontend_port = _get_dashboard_frontend_port()
    config = load_config()

    log_locs = _get_log_locations()

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "backend": {
            "host": getattr(config, "host", "localhost"),
            "port": backend_port,
            "port_in_use": _is_port_in_use(backend_port),
            "websocket_enabled": True,
        },
        "frontend": {
            "port": frontend_port,
            "port_in_use": _is_port_in_use(frontend_port),
        },
        "routes": {
            "api_config": f"http://localhost:{backend_port}/api/config",
            "api_sessions": f"http://localhost:{backend_port}/sessions",
            "websocket": f"ws://localhost:{backend_port}/ws",
            "frontend": f"http://localhost:{frontend_port}",
        },
        "storage_paths": {
            "config_dir": str(log_locs["config_dir"]),
            "telemetry_dir": str(log_locs["telemetry_dir"]),
            "session_dir": str(log_locs["session_dir"]),
        },
        "conflicts": detect_startup_conflicts(),
    }


def start_dashboard_backend(
    host: str = "localhost",
    port: int | None = None,
    background: bool = False,
) -> ServiceStartResult:
    """Start the dashboard backend service.

    Args:
        host: Host to bind to.
        port: Port to use. Defaults to configured port.
        background: If True, start in background.

    Returns:
        ServiceStartResult with status.
    """
    if port is None:
        port = _get_dashboard_backend_port()

    conflicts = detect_startup_conflicts()
    if conflicts and any(c["type"] == "port_occupied" for c in conflicts):
        occupied = [c for c in conflicts if c["type"] == "port_occupied"][0]
        return ServiceStartResult(
            success=False,
            message=f"Cannot start: {occupied['message']}. Remediation: {occupied['remediation']}",
        )

    try:
        import cc_deep_research.web_server as ws

        if background:
            import multiprocessing
            proc = multiprocessing.Process(
                target=ws.start_server,
                kwargs={"host": host, "port": port},
                daemon=True,
            )
            proc.start()
            return ServiceStartResult(
                success=True,
                service=ServiceInfo(
                    name="dashboard_backend",
                    status=ServiceStatus.RUNNING,
                    pid=proc.pid,
                    port=port,
                    backend_url=f"http://{host}:{port}",
                    frontend_url=f"http://localhost:{_get_dashboard_frontend_port()}",
                    log_location=str(_get_log_locations()["config_dir"]),
                    started_at=datetime.now(UTC).isoformat(),
                ),
            )

        ws.start_server(host=host, port=port)
        return ServiceStartResult(
            success=True,
            service=ServiceInfo(
                name="dashboard_backend",
                status=ServiceStatus.RUNNING,
                port=port,
                backend_url=f"http://{host}:{port}",
            ),
        )
    except Exception as e:
        return ServiceStartResult(
            success=False,
            message=f"Failed to start backend: {e}",
        )


def stop_service(service_name: str = "dashboard", port: int | None = None) -> dict[str, Any]:
    """Stop a running service.

    Args:
        service_name: Name of the service to stop.
        port: Port the service is using.

    Returns:
        Dict with stop result and message.
    """
    if port is None:
        port = _get_dashboard_backend_port()

    pid = _find_process_by_port(port)
    if pid is None:
        return {
            "success": False,
            "message": f"No process found on port {port}",
        }

    try:
        os.kill(pid, signal.SIGTERM)
        return {
            "success": True,
            "message": f"Stopped service {service_name} (PID {pid})",
            "pid": pid,
        }
    except OSError as e:
        return {
            "success": False,
            "message": f"Failed to stop PID {pid}: {e}",
        }


__all__ = [
    "ServiceInfo",
    "ServiceStartResult",
    "ServiceStatus",
    "check_service_status",
    "detect_startup_conflicts",
    "get_startup_diagnostics",
    "start_dashboard_backend",
    "stop_service",
]
