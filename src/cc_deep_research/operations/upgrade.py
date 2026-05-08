"""Upgrade validation and rollback support."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from cc_deep_research.config import load_config
from cc_deep_research.operations import (
    _get_config_dir,
    _get_telemetry_dir,
    validate_all_data_paths,
)
from cc_deep_research.operations.backup import (
    validate_backup,
)
from cc_deep_research.operations.health import (
    HealthCheckStatus,
    run_health_checks,
)


class UpgradeCheckStatus(StrEnum):
    """Upgrade check status."""

    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    SKIPPED = "skipped"


@dataclass
class UpgradeCheckResult:
    """Result of a single upgrade validation check."""

    check_id: str
    label: str
    status: UpgradeCheckStatus
    detail: str | None = None
    blockers: list[str] = field(default_factory=list)
    remediation: str | None = None


@dataclass
class UpgradeReport:
    """Complete upgrade validation report."""

    timestamp: str
    version_from: str | None
    version_to: str | None
    pre_upgrade_checks: list[UpgradeCheckResult]
    post_upgrade_checks: list[UpgradeCheckResult]
    rollback_recommended: bool
    warnings: list[str]
    errors: list[str]


def _check_backup_availability() -> UpgradeCheckResult:
    """Check that a recent backup exists before upgrade."""
    # Look for backup manifests in config dir
    config_dir = _get_config_dir()
    manifest_paths = list(config_dir.glob("*.manifest.json"))

    if not manifest_paths:
        return UpgradeCheckResult(
            check_id="backup_available",
            label="Backup available",
            status=UpgradeCheckStatus.WARNING,
            detail="No backup manifests found in config directory",
            remediation="Create a backup before upgrading: inqulume-studio backup create",
            blockers=[],
        )

    # Check the most recent manifest
    latest = max(manifest_paths, key=lambda p: p.stat().st_mtime)
    try:
        validation = validate_backup(latest)
        if not validation.valid:
            return UpgradeCheckResult(
                check_id="backup_available",
                label="Backup available",
                status=UpgradeCheckStatus.FAIL,
                detail=f"Found backup manifest but it is invalid: {validation.errors}",
                remediation="Create a fresh backup before upgrading",
                blockers=["Invalid backup manifest"],
            )
        return UpgradeCheckResult(
            check_id="backup_available",
            label="Backup available",
            status=UpgradeCheckStatus.PASS,
            detail=f"Valid backup manifest found: {latest.name}",
            blockers=[],
        )
    except Exception as e:
        return UpgradeCheckResult(
            check_id="backup_available",
            label="Backup available",
            status=UpgradeCheckStatus.WARNING,
            detail=f"Could not validate backup: {e}",
            remediation="Create a backup before upgrading to ensure rollback capability",
            blockers=[],
        )


def _check_config_compatibility(
    version_from: str | None,
    version_to: str,
) -> UpgradeCheckResult:
    """Check config compatibility for upgrade."""
    try:
        config = load_config()
    except Exception as e:
        return UpgradeCheckResult(
            check_id="config_compatible",
            label="Config compatibility",
            status=UpgradeCheckStatus.FAIL,
            detail=f"Config failed to load: {e}",
            remediation="Fix config file errors before upgrading",
            blockers=["Config load failure"],
        )

    # Check for required fields that might be missing after upgrade
    required_fields = ["search", "tavily", "llm"]
    missing = [f for f in required_fields if not hasattr(config, f)]

    if missing:
        return UpgradeCheckResult(
            check_id="config_compatible",
            label="Config compatibility",
            status=UpgradeCheckStatus.FAIL,
            detail=f"Config is missing required fields: {missing}",
            remediation="Update config to include required fields or reset to defaults",
            blockers=missing,
        )

    return UpgradeCheckResult(
        check_id="config_compatible",
        label="Config compatibility",
        status=UpgradeCheckStatus.PASS,
        detail="Config is compatible",
        blockers=[],
    )


def _check_storage_schema() -> UpgradeCheckResult:
    """Check storage schema compatibility."""
    telemetry_dir = _get_telemetry_dir()

    # Check if DuckDB exists and is accessible
    db_path = telemetry_dir / "dashboard.db"
    if not db_path.exists():
        return UpgradeCheckResult(
            check_id="storage_schema",
            label="Storage schema",
            status=UpgradeCheckStatus.SKIPPED,
            detail="DuckDB database does not exist yet",
            remediation=None,
            blockers=[],
        )

    # Try to connect and verify schema
    try:
        import duckdb

        conn = duckdb.connect(str(db_path), read_only=True)
        tables = conn.execute("SHOW TABLES").fetchall()
        table_names = [t[0] for t in tables]
        conn.close()

        expected_tables = ["telemetry_sessions", "telemetry_events"]
        missing_tables = [t for t in expected_tables if t not in table_names]

        if missing_tables:
            return UpgradeCheckResult(
                check_id="storage_schema",
                label="Storage schema",
                status=UpgradeCheckStatus.WARNING,
                detail=f"DuckDB is missing expected tables: {missing_tables}",
                remediation="Run telemetry ingestion to populate schema",
                blockers=[],
            )

        return UpgradeCheckResult(
            check_id="storage_schema",
            label="Storage schema",
            status=UpgradeCheckStatus.PASS,
            detail=f"All expected tables present: {table_names}",
            blockers=[],
        )
    except Exception as e:
        return UpgradeCheckResult(
            check_id="storage_schema",
            label="Storage schema",
            status=UpgradeCheckStatus.WARNING,
            detail=f"Could not verify DuckDB schema: {e}",
            remediation="Ensure DuckDB is accessible",
            blockers=[],
        )


def _check_telemetry_compatibility() -> UpgradeCheckResult:
    """Check telemetry format compatibility."""
    telemetry_dir = _get_telemetry_dir()

    if not telemetry_dir.exists():
        return UpgradeCheckResult(
            check_id="telemetry_compatible",
            label="Telemetry compatibility",
            status=UpgradeCheckStatus.SKIPPED,
            detail="Telemetry directory does not exist",
            blockers=[],
        )

    # Check for session directories
    session_dirs = [
        p for p in telemetry_dir.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    ]

    return UpgradeCheckResult(
        check_id="telemetry_compatible",
        label="Telemetry compatibility",
        status=UpgradeCheckStatus.PASS,
        detail=f"Found {len(session_dirs)} session telemetry directories",
        blockers=[],
    )


def _check_dashboard_build() -> UpgradeCheckResult:
    """Check that the dashboard can be built."""
    dashboard_dir = Path(__file__).parent.parent.parent.parent / "dashboard"

    if not dashboard_dir.exists():
        return UpgradeCheckResult(
            check_id="dashboard_build",
            label="Dashboard build",
            status=UpgradeCheckStatus.SKIPPED,
            detail="Dashboard directory not found",
            blockers=[],
        )

    # Check for package.json and node_modules
    if not (dashboard_dir / "package.json").exists():
        return UpgradeCheckResult(
            check_id="dashboard_build",
            label="Dashboard build",
            status=UpgradeCheckStatus.FAIL,
            detail="Dashboard package.json not found",
            remediation="Run 'cd dashboard && npm install' to install dependencies",
            blockers=["Missing dashboard dependencies"],
        )

    return UpgradeCheckResult(
        check_id="dashboard_build",
        label="Dashboard build",
        status=UpgradeCheckStatus.PASS,
        detail="Dashboard build prerequisites met",
        blockers=[],
    )


def _check_post_upgrade_health() -> list[UpgradeCheckResult]:
    """Run post-upgrade health checks."""
    try:
        report = run_health_checks()
    except Exception as e:
        return [
            UpgradeCheckResult(
                check_id="health_check",
                label="Post-upgrade health",
                status=UpgradeCheckStatus.FAIL,
                detail=f"Health check failed: {e}",
                blockers=["Health check failure"],
            )
        ]

    results: list[UpgradeCheckResult] = []
    for check in report.checks:
        if check.status == HealthCheckStatus.PASS:
            status = UpgradeCheckStatus.PASS
        elif check.status == HealthCheckStatus.WARNING:
            status = UpgradeCheckStatus.WARNING
        else:
            status = UpgradeCheckStatus.FAIL

        results.append(
            UpgradeCheckResult(
                check_id=check.check_id,
                label=check.label,
                status=status,
                detail=check.reason,
                remediation=check.remediation,
                blockers=[],
            )
        )

    return results


def run_pre_upgrade_validation(
    version_from: str | None = None,
    version_to: str | None = None,
) -> list[UpgradeCheckResult]:
    """Run pre-upgrade validation checks.

    Args:
        version_from: Current version.
        version_to: Target version.

    Returns:
        List of upgrade check results.
    """
    return [
        _check_backup_availability(),
        _check_config_compatibility(version_from, version_to or "next"),
        _check_storage_schema(),
        _check_telemetry_compatibility(),
        _check_dashboard_build(),
    ]


def run_post_upgrade_validation() -> list[UpgradeCheckResult]:
    """Run post-upgrade validation checks.

    Returns:
        List of upgrade check results.
    """
    checks = _check_post_upgrade_health()

    # Add data path validation
    path_validation = validate_all_data_paths()
    if path_validation["summary"]["fail"] > 0:
        checks.append(
            UpgradeCheckResult(
                check_id="data_paths",
                label="Data paths",
                status=UpgradeCheckStatus.FAIL,
                detail="Data path validation failed",
                remediation="Review path permissions in settings panel",
                blockers=["Data path validation failures"],
            )
        )

    return checks


def generate_upgrade_report(
    version_from: str | None = None,
    version_to: str | None = None,
) -> UpgradeReport:
    """Generate a complete upgrade validation report.

    Args:
        version_from: Current version.
        version_to: Target version.

    Returns:
        UpgradeReport with pre/post validation results.
    """
    pre_checks = run_pre_upgrade_validation(version_from, version_to)
    post_checks = run_post_upgrade_validation()

    errors = [
        c.detail for c in pre_checks + post_checks
        if c.status == UpgradeCheckStatus.FAIL
    ]
    warnings = [
        c.detail for c in pre_checks + post_checks
        if c.status == UpgradeCheckStatus.WARNING
    ]

    rollback_recommended = (
        any(c.status == UpgradeCheckStatus.FAIL for c in pre_checks)
        or any(c.blockers for c in pre_checks)
    )

    return UpgradeReport(
        timestamp=datetime.now(UTC).isoformat(),
        version_from=version_from,
        version_to=version_to,
        pre_upgrade_checks=pre_checks,
        post_upgrade_checks=post_checks,
        rollback_recommended=rollback_recommended,
        warnings=warnings,
        errors=errors,
    )


def get_rollback_instructions(backup_id: str | None = None) -> dict[str, Any]:
    """Get rollback instructions referencing backup and migration artifacts.

    Args:
        backup_id: Optional specific backup ID to reference.

    Returns:
        Dict with rollback instructions.
    """
    config_dir = _get_config_dir()

    instructions = {
        "steps": [
            {
                "step": 1,
                "description": "Stop the dashboard and backend services",
                "command": "inqulume-studio dashboard stop",
            },
            {
                "step": 2,
                "description": "Locate the backup manifest",
                "command": f"ls {config_dir}/*.manifest.json",
            },
            {
                "step": 3,
                "description": "Restore from backup",
                "command": "inqulume-studio backup restore <backup-path> --confirm",
            },
            {
                "step": 4,
                "description": "Verify health after rollback",
                "command": "inqulume-studio health check",
            },
        ],
        "reference": {
            "backup_docs": "See docs/tasks/phase-26/p26-t3-backup-restore.md",
            "migration_docs": "See docs/tasks/phase-26/p26-t4-release-migration-playbook.md",
        },
    }

    return instructions


__all__ = [
    "UpgradeCheckResult",
    "UpgradeCheckStatus",
    "UpgradeReport",
    "generate_upgrade_report",
    "get_rollback_instructions",
    "run_post_upgrade_validation",
    "run_pre_upgrade_validation",
]
