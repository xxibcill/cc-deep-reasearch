"""Local data path inventory and permission validation."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cc_deep_research.config import get_default_config_path


@dataclass
class PathValidationResult:
    """Result of validating a single path."""

    path: str
    status: PathStatus
    readable: bool | None = None
    writable: bool | None = None
    exists: bool | None = None
    is_symlink: bool | None = None
    free_space_mb: float | None = None
    remediation: str | None = None
    details: str | None = None


class PathStatus:
    """Path validation status constants."""

    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    SKIPPED = "skipped"


# Known safe project data directories under ~/.config/cc-deep-research/
KNOWN_DATA_DIRS = {
    "config": "Configuration directory",
    "sessions": "Research session storage",
    "telemetry": "Telemetry event storage",
    "reports": "Cached report output",
    "knowledge": "Knowledge graph storage",
    "content_gen": "Content generation artifacts",
    "radar": "Opportunity radar data",
    "duckdb": "DuckDB analytics database",
}


def _get_config_dir() -> Path:
    """Return the project config directory."""
    return get_default_config_path().parent


def _get_session_dir() -> Path:
    """Return the sessions directory."""
    return _get_config_dir() / "sessions"


def _get_telemetry_dir() -> Path:
    """Return the telemetry directory."""
    return _get_config_dir() / "telemetry"


def _get_reports_dir() -> Path:
    """Return the reports directory."""
    return _get_config_dir() / "reports"


def _get_knowledge_dir() -> Path:
    """Return the knowledge graph directory."""
    return _get_config_dir() / "knowledge"


def _get_content_gen_dir() -> Path:
    """Return the content generation directory."""
    return _get_config_dir() / "content_gen"


def _get_radar_dir() -> Path:
    """Return the radar directory."""
    return _get_config_dir() / "radar"


def _get_duckdb_path() -> Path:
    """Return the DuckDB analytics database path."""
    return _get_telemetry_dir() / "dashboard.db"


def _get_dashboard_dir() -> Path:
    """Return the dashboard backend directory."""
    return _get_config_dir() / "dashboard"


def _detect_symlink(p: Path) -> bool:
    """Detect if a path is a symlink, following it."""
    try:
        return p.is_symlink()
    except OSError:
        return False


def _is_safe_path(p: Path) -> tuple[bool, str]:
    """Detect whether a path is in a safe location.

    Returns (is_safe, reason).
    """
    resolved = p.resolve()

    # Block root-level directories
    if resolved.parent == resolved or resolved == Path("/"):
        return False, "Path is at filesystem root"

    # Block suspicious paths regardless of location
    suspicious_segments = [".ssh", ".gnupg", "/etc/passwd"]
    for seg in suspicious_segments:
        if seg in resolved.parts:
            return False, f"Path contains sensitive directory: {seg}"

    # Allow paths under home directory
    home = Path.home()
    if str(resolved).startswith(str(home)):
        return True, "ok"

    # Allow paths under /tmp that look like project/session temp directories
    tmp = Path("/tmp")
    if str(resolved).startswith(str(tmp)):
        # Accept /tmp subdirs that look like named project spaces
        # (e.g., pytest session dirs, project-specific tmp dirs)
        return True, "ok"

    return False, "Path is outside home directory and /tmp"


def validate_data_path(
    path: Path,
    require_exists: bool = False,
    require_readable: bool = False,
    require_writable: bool = False,
    min_free_space_mb: float | None = None,
    check_permission_safety: bool = True,
) -> PathValidationResult:
    """Validate a single data path for existence, permissions, and safety.

    Args:
        path: Path to validate.
        require_exists: Fail if path does not exist.
        require_readable: Warn if path is not readable.
        require_writable: Fail if path is not writable (for write operations).
        min_free_space_mb: Warn if available space is below this threshold.
        check_permission_safety: Check that path is in a safe project location.

    Returns:
        PathValidationResult with status and details.
    """
    path_str = str(path)

    # Symlink detection
    is_symlink = _detect_symlink(path)

    # Existence check
    exists = path.exists()

    # Safety check for non-existent paths
    if not exists:
        if check_permission_safety:
            safe, reason = _is_safe_path(path)
            if not safe:
                return PathValidationResult(
                    path=path_str,
                    status=PathStatus.FAIL,
                    exists=False,
                    remediation=f"Path is in an unsafe location: {reason}",
                    details=f"Resolved path: {path.resolve()}",
                )
        if require_exists:
            return PathValidationResult(
                path=path_str,
                status=PathStatus.WARNING,
                exists=False,
                remediation="Create this directory before proceeding",
                details="Directory does not exist yet",
            )
        return PathValidationResult(
            path=path_str,
            status=PathStatus.SKIPPED,
            exists=False,
            remediation=None,
            details="Skipped - path does not exist",
        )

    # If it exists, check if it's a symlink (potential security issue)
    if is_symlink:
        target = path.resolve()
        if check_permission_safety:
            safe, reason = _is_safe_path(path)
            if not safe:
                return PathValidationResult(
                    path=path_str,
                    status=PathStatus.FAIL,
                    exists=True,
                    is_symlink=True,
                    remediation=f"Symlink target is in an unsafe location: {reason}",
                    details=f"Target: {target}",
                )
        return PathValidationResult(
            path=path_str,
            status=PathStatus.WARNING,
            exists=True,
            is_symlink=True,
            remediation="Symlink detected - verify target is intentional",
            details=f"Points to: {target}",
        )

    # Safety check for existing paths
    if check_permission_safety:
        safe, reason = _is_safe_path(path)
        if not safe:
            return PathValidationResult(
                path=path_str,
                status=PathStatus.FAIL,
                exists=True,
                remediation=f"Path is in an unsafe location: {reason}",
                details=f"Resolved path: {path.resolve()}",
            )

    # Readable check
    readable = None
    if require_readable or exists:
        try:
            test_file = path / ".readable_test"
            path.mkdir(parents=True, exist_ok=True)
            test_file.write_text("test", encoding="utf-8")
            test_file.unlink()
            readable = True
        except OSError:
            readable = False

    # Writable check
    writable = None
    if require_writable or exists:
        try:
            test_file = path / ".writable_test"
            path.mkdir(parents=True, exist_ok=True)
            test_file.write_text("test", encoding="utf-8")
            test_file.unlink()
            writable = True
        except OSError:
            writable = False

    # Free space check
    free_space_mb = None
    if exists and path.is_dir():
        try:
            usage = shutil.disk_usage(path)
            free_space_mb = usage.free / (1024 * 1024)
        except OSError:
            pass

    # Check free space threshold
    if min_free_space_mb is not None and free_space_mb is not None:
        if free_space_mb < min_free_space_mb:
            return PathValidationResult(
                path=path_str,
                status=PathStatus.WARNING,
                exists=True,
                readable=readable,
                writable=writable,
                free_space_mb=round(free_space_mb, 1),
                remediation=f"Low disk space: {free_space_mb:.1f} MB available (threshold: {min_free_space_mb} MB)",
                details=None,
            )

    # Determine overall status
    if require_writable and not writable:
        return PathValidationResult(
            path=path_str,
            status=PathStatus.FAIL,
            exists=True,
            readable=readable,
            writable=False,
            remediation="Path is not writable - check directory permissions",
            details=None,
        )
    if require_readable and not readable:
        return PathValidationResult(
            path=path_str,
            status=PathStatus.WARNING,
            exists=True,
            readable=False,
            writable=writable,
            remediation="Path is not readable - check directory permissions",
            details=None,
        )

    return PathValidationResult(
        path=path_str,
        status=PathStatus.PASS,
        exists=True,
        readable=readable,
        writable=writable,
        free_space_mb=round(free_space_mb, 1) if free_space_mb is not None else None,
        remediation=None,
        details=None,
    )


def validate_all_data_paths() -> dict[str, Any]:
    """Validate all critical project data paths.

    Returns:
        Dict with per-path validation results and summary.
    """
    config_dir = _get_config_dir()
    session_dir = _get_session_dir()
    telemetry_dir = _get_telemetry_dir()
    reports_dir = _get_reports_dir()
    knowledge_dir = _get_knowledge_dir()
    content_gen_dir = _get_content_gen_dir()
    radar_dir = _get_radar_dir()
    duckdb_path = _get_duckdb_path()
    dashboard_dir = _get_dashboard_dir()

    paths = [
        ("config_dir", config_dir, True, True, True, 50.0),
        ("session_dir", session_dir, True, True, True, 100.0),
        ("telemetry_dir", telemetry_dir, True, True, True, 200.0),
        ("reports_dir", reports_dir, False, True, True, 100.0),
        ("knowledge_dir", knowledge_dir, False, True, True, 100.0),
        ("content_gen_dir", content_gen_dir, False, True, True, 100.0),
        ("radar_dir", radar_dir, False, True, True, 50.0),
        ("duckdb_path", duckdb_path, False, True, True, 200.0),
        ("dashboard_dir", dashboard_dir, False, True, True, 50.0),
    ]

    results: dict[str, Any] = {}
    fail_count = 0
    warn_count = 0

    for name, path, req_exists, req_readable, req_writable, min_space in paths:
        result = validate_data_path(
            path,
            require_exists=req_exists,
            require_readable=req_readable,
            require_writable=req_writable,
            min_free_space_mb=min_space,
        )
        results[name] = {
            "path": str(path),
            "status": result.status,
            "exists": result.exists,
            "readable": result.readable,
            "writable": result.writable,
            "free_space_mb": result.free_space_mb,
            "is_symlink": result.is_symlink,
            "remediation": result.remediation,
            "details": result.details,
        }
        if result.status == PathStatus.FAIL:
            fail_count += 1
        elif result.status == PathStatus.WARNING:
            warn_count += 1

    return {
        "paths": results,
        "summary": {
            "total": len(paths),
            "pass": len(paths) - fail_count - warn_count,
            "warning": warn_count,
            "fail": fail_count,
        },
    }


def get_recommended_directory_layout() -> dict[str, str]:
    """Return the recommended data directory layout for local production.

    Returns:
        Dict mapping directory name to its purpose.
    """
    return {
        str(_get_config_dir()): "Project configuration (config.yaml, credentials)",
        str(_get_session_dir()): "Research session files and summaries",
        str(_get_telemetry_dir()): "Per-session telemetry events and DuckDB analytics",
        str(_get_reports_dir()): "Cached rendered report output",
        str(_get_knowledge_dir()): "Knowledge graph claims and embeddings",
        str(_get_content_gen_dir()): "Content generation briefs, scripts, and artifacts",
        str(_get_radar_dir()): "Opportunity radar signals and opportunities",
    }
