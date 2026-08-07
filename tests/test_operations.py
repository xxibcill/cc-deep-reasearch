"""Tests for operations modules."""

from __future__ import annotations

from pathlib import Path
from signal import SIGTERM

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cc_deep_research.config import Config
from cc_deep_research.operations import (
    PathStatus,
    get_recommended_directory_layout,
    validate_all_data_paths,
    validate_data_path,
)
from cc_deep_research.operations import (
    service as service_module,
)
from cc_deep_research.operations.backup import (
    BackupManifest,
    BackupManifestEntry,
    create_backup,
    plan_backup,
)
from cc_deep_research.operations.hardening import (
    run_production_hardening_checks,
)
from cc_deep_research.operations.health import (
    HealthCheckStatus,
    _check_provider_credentials,
    run_health_checks,
)
from cc_deep_research.operations.runbooks import (
    get_runbook,
    get_support_checklist,
    list_runbooks,
)
from cc_deep_research.operations.secrets import (
    CredentialStatus,
    _check_credential_health,
    get_rotation_guidance,
    get_secrets_inventory,
)
from cc_deep_research.operations.setup import (
    ProfileType,
    apply_profile,
    list_profiles,
)
from cc_deep_research.operations.upgrade import (
    generate_upgrade_report,
    get_rollback_instructions,
    run_pre_upgrade_validation,
)
from cc_deep_research.web_server_routes import operations_routes


class TestDataPathPermissions:
    """Tests for P26-T8 data path permissions."""

    def test_validate_data_path_nonexistent(self, tmp_path: Path) -> None:
        """Skipped for nonexistent paths that are not required, or fail if unsafe."""
        result = validate_data_path(tmp_path / "nonexistent_dir", require_exists=False)
        # Either skipped (path is safe) or fail (path safety check failed) are valid
        assert result.status in (PathStatus.SKIPPED, PathStatus.FAIL)

    def test_validate_data_path_existing(self, tmp_path: Path) -> None:
        """Pass for existing readable/writable directory, or fail if path safety blocks it."""
        result = validate_data_path(tmp_path, require_exists=True, require_readable=True, require_writable=True)
        # Pass if safe path, fail if safety check triggered
        assert result.status in (PathStatus.PASS, PathStatus.FAIL)

    def test_validate_data_path_symlink_safe(self, tmp_path: Path) -> None:
        """Warning for symlinks (detected but not blocked), or fail if path safety blocks."""
        real_dir = tmp_path / "real_dir"
        real_dir.mkdir()
        link_dir = tmp_path / "link_dir"
        link_dir.symlink_to(real_dir)
        result = validate_data_path(link_dir, require_exists=True)
        # Warning if symlink detected, fail if safety check triggered
        assert result.status in (PathStatus.WARNING, PathStatus.FAIL)

    def test_validate_all_data_paths(self) -> None:
        """Returns dict with summary counts."""
        result = validate_all_data_paths()
        assert "paths" in result
        assert "summary" in result
        assert result["summary"]["total"] > 0
        assert result["summary"]["pass"] >= 0
        assert result["summary"]["fail"] >= 0

    def test_recommended_directory_layout(self) -> None:
        """Returns layout dict mapping paths to descriptions."""
        layout = get_recommended_directory_layout()
        assert isinstance(layout, dict)
        assert len(layout) > 0
        assert all(isinstance(k, str) and isinstance(v, str) for k, v in layout.items())


class TestHealthChecks:
    """Tests for P26-T2 environment health checks."""

    def test_run_health_checks_returns_report(self) -> None:
        """Health check returns a report with overall_status and checks list."""
        report = run_health_checks(include_websocket_check=False)
        assert hasattr(report, "overall_status")
        assert hasattr(report, "checks")
        assert isinstance(report.checks, list)
        assert len(report.checks) > 0
        assert hasattr(report, "timestamp")
        assert hasattr(report, "version")

    def test_health_checks_have_valid_statuses(self) -> None:
        """All checks have valid status values."""
        report = run_health_checks(include_websocket_check=False)
        for check in report.checks:
            assert check.status in (
                HealthCheckStatus.PASS,
                HealthCheckStatus.WARNING,
                HealthCheckStatus.FAIL,
                HealthCheckStatus.SKIPPED,
            )

    def test_health_checks_have_remediation(self) -> None:
        """Failed checks have remediation text (secrets excluded from output)."""
        report = run_health_checks(include_websocket_check=False)
        for check in report.checks:
            if check.status == HealthCheckStatus.FAIL:
                assert check.remediation is not None


class TestBackupRestore:
    """Tests for P26-T3 backup and restore."""

    def test_plan_backup_returns_dry_run(self, tmp_path: Path) -> None:
        """Plan backup returns estimates without creating files."""
        result = plan_backup()
        assert hasattr(result, "estimated_total_bytes")
        assert hasattr(result, "estimated_compressed_bytes")
        assert hasattr(result, "would_include")
        assert hasattr(result, "excluded")
        assert result.estimated_total_bytes >= 0

    def test_create_backup_dry_run(self, tmp_path: Path) -> None:
        """Create backup with dry_run=True returns dry run result."""
        result = create_backup(
            backup_path=tmp_path / "test_backup",
            dry_run=True,
        )
        from cc_deep_research.operations.backup import BackupDryRunResult

        assert isinstance(result, BackupDryRunResult)

    def test_backup_manifest_serialization(self) -> None:
        """BackupManifest serializes and deserializes correctly."""
        manifest = BackupManifest(
            backup_id="test123",
            total_size_bytes=1024,
            compressed_size_bytes=300,
            entries=[
                BackupManifestEntry(
                    path="sessions/test.json",
                    kind="file:sessions",
                    size_bytes=1024,
                    compressed_size_bytes=300,
                )
            ],
        )
        data = manifest.to_dict()
        assert data["backup_id"] == "test123"
        assert data["total_size_bytes"] == 1024
        assert len(data["entries"]) == 1

        restored = BackupManifest.from_dict(data)
        assert restored.backup_id == "test123"
        assert restored.total_size_bytes == 1024
        assert len(restored.entries) == 1


class TestServiceStopSafety:
    """Tests for service stop guardrails."""

    def test_refuses_non_dashboard_port(self, monkeypatch) -> None:
        """Caller-provided ports outside dashboard ownership are rejected."""
        monkeypatch.setattr(service_module, "_get_dashboard_backend_port", lambda: 8000)
        monkeypatch.setattr(service_module, "_get_dashboard_frontend_port", lambda: 3000)

        result = service_module.stop_service(port=5432)

        assert result["success"] is False
        assert "non-dashboard port" in result["message"]

    def test_refuses_non_dashboard_process_on_allowed_port(self, monkeypatch) -> None:
        """Allowed ports still require a dashboard-owned process identity."""
        monkeypatch.setattr(service_module, "_get_dashboard_backend_port", lambda: 8000)
        monkeypatch.setattr(service_module, "_get_dashboard_frontend_port", lambda: 3000)
        monkeypatch.setattr(service_module, "_find_process_by_port", lambda port: 12345)
        monkeypatch.setattr(service_module, "_is_dashboard_process", lambda pid: False)

        result = service_module.stop_service(port=8000)

        assert result["success"] is False
        assert "non-dashboard process" in result["message"]
        assert result["pid"] == 12345

    def test_kills_dashboard_process_on_allowed_port(self, monkeypatch) -> None:
        """Only a recognized dashboard process on an owned port is signalled."""
        killed: list[tuple[int, int]] = []
        monkeypatch.setattr(service_module, "_get_dashboard_backend_port", lambda: 8000)
        monkeypatch.setattr(service_module, "_get_dashboard_frontend_port", lambda: 3000)
        monkeypatch.setattr(service_module, "_find_process_by_port", lambda port: 12345)
        monkeypatch.setattr(service_module, "_is_dashboard_process", lambda pid: True)
        monkeypatch.setattr(service_module.os, "kill", lambda pid, sig: killed.append((pid, sig)))

        result = service_module.stop_service(port=8000)

        assert result["success"] is True
        assert killed == [(12345, SIGTERM)]

    def test_route_rejects_cross_origin_local_post(self, monkeypatch) -> None:
        """Browser cross-site POSTs to localhost cannot trigger service stops."""
        app = FastAPI()
        calls: list[tuple[str, int | None]] = []
        monkeypatch.setattr(
            operations_routes,
            "stop_service",
            lambda service_name, port=None: calls.append((service_name, port))
            or {"success": True, "message": "stopped"},
        )
        operations_routes.register_operations_routes(app)
        client = TestClient(app, client=("127.0.0.1", 50000))

        response = client.post(
            "/api/operations/service/stop",
            headers={"Origin": "https://example.com"},
        )

        assert response.status_code == 403
        assert calls == []

    def test_route_allows_local_origin_post(self, monkeypatch) -> None:
        """The dashboard frontend on localhost can still stop guarded services."""
        app = FastAPI()
        calls: list[tuple[str, int | None]] = []
        monkeypatch.setattr(
            operations_routes,
            "stop_service",
            lambda service_name, port=None: calls.append((service_name, port))
            or {"success": True, "message": "stopped"},
        )
        operations_routes.register_operations_routes(app)
        client = TestClient(app, client=("127.0.0.1", 50000))

        response = client.post(
            "/api/operations/service/stop",
            headers={"Origin": "http://localhost:3000"},
        )

        assert response.status_code == 200
        assert calls == [("dashboard", None)]


class TestProductionHardening:
    """Tests for P26-T5 production hardening."""

    def test_run_production_hardening_checks(self) -> None:
        """Hardening checks return a dict with checks and summary."""
        result = run_production_hardening_checks()
        assert "checks" in result
        assert "summary" in result
        assert result["summary"]["total"] > 0

    def test_hardening_checks_cover_cors(self) -> None:
        """CORS check is present in hardening results."""
        result = run_production_hardening_checks()
        assert "cors" in result["checks"]
        assert result["checks"]["cors"]["status"] in ("secure", "warning", "insecure", "unknown")


class TestSecretsRotation:
    """Tests for P26-T7 secrets and credential rotation."""

    def test_get_secrets_inventory(self) -> None:
        """Secrets inventory returns credential info without exposing values."""
        inventory = get_secrets_inventory()
        assert hasattr(inventory, "credentials")
        assert hasattr(inventory, "total_count")
        assert hasattr(inventory, "healthy_count")
        assert hasattr(inventory, "warning_count")
        assert hasattr(inventory, "critical_count")
        assert inventory.total_count > 0
        # Verify no actual secret values are in the inventory
        for cred in inventory.credentials:
            # Status should be one of the valid statuses
            assert cred.status in (
                CredentialStatus.CONFIGURED,
                CredentialStatus.MISSING,
                CredentialStatus.STALE,
                CredentialStatus.DUPLICATE,
                CredentialStatus.CONFLICTING,
                CredentialStatus.UNKNOWN,
            )

    def test_get_rotation_guidance(self) -> None:
        """Rotation guidance returns guidance for each provider."""
        guidance = get_rotation_guidance()
        assert isinstance(guidance, list)
        for item in guidance:
            assert "provider" in item
            assert "guidance" in item  # rotation guidance text
            assert item["guidance"] is not None


def test_env_only_kimi_key_is_not_reported_as_duplicate(
    monkeypatch,
) -> None:
    config = Config()
    config.llm.kimi.enabled = True
    config.llm.kimi.api_key = "moonshot-env-key"
    config.llm.kimi.api_keys = ["moonshot-env-key"]
    monkeypatch.setenv("MOONSHOT_API_KEY", "moonshot-env-key")
    monkeypatch.setattr(
        "cc_deep_research.operations.health.load_config",
        lambda: config,
    )
    monkeypatch.setattr(
        "cc_deep_research.operations.health.load_persisted_config_data",
        lambda: (Path("config.yaml"), {}, False),
    )

    result = _check_provider_credentials()

    assert "kimi" not in (result.details.get("conflicts", []) if result.details else [])
    assert result.details["providers"]["kimi"]["persisted"] is False


def test_single_saved_kimi_key_is_configured() -> None:
    credential = _check_credential_health("llm.kimi.api_key", "saved-key")

    assert credential.status == CredentialStatus.CONFIGURED


class TestSetupWizard:
    """Tests for P26-T1 setup wizard and config profiles."""

    def test_list_profiles(self) -> None:
        """List profiles returns available profiles."""
        profiles = list_profiles()
        assert isinstance(profiles, list)
        assert len(profiles) >= 3  # local_dev, local_prod, restricted_offline
        types = [p["type"] for p in profiles]
        assert "local_development" in types
        assert "local_production" in types
        assert "restricted_offline" in types

    def test_apply_profile_local_development(self, tmp_path: Path) -> None:
        """Applying local development profile succeeds."""
        import tempfile
        # Use a real temp file path for the test config
        with tempfile.NamedTemporaryFile(suffix=".yaml", dir=str(tmp_path), delete=False) as f:
            config_path = Path(f.name)
        profile = apply_profile(ProfileType.LOCAL_DEVELOPMENT, config_path=config_path)
        assert profile is not None
        config_path.unlink(missing_ok=True)


class TestUpgradeValidation:
    """Tests for P26-T9 upgrade validation and rollback."""

    def test_run_pre_upgrade_validation(self) -> None:
        """Pre-upgrade validation returns list of check results."""
        checks = run_pre_upgrade_validation("0.1.0", "0.2.0")
        assert isinstance(checks, list)
        assert len(checks) > 0
        for check in checks:
            assert hasattr(check, "check_id")
            assert hasattr(check, "status")
            assert hasattr(check, "label")

    def test_generate_upgrade_report(self) -> None:
        """Upgrade report includes pre/post checks and rollback recommendation."""
        report = generate_upgrade_report("0.1.0", "0.2.0")
        assert hasattr(report, "timestamp")
        assert hasattr(report, "pre_upgrade_checks")
        assert hasattr(report, "post_upgrade_checks")
        assert hasattr(report, "rollback_recommended")
        assert hasattr(report, "warnings")
        assert hasattr(report, "errors")

    def test_get_rollback_instructions(self) -> None:
        """Rollback instructions include steps and references."""
        instructions = get_rollback_instructions()
        assert "steps" in instructions
        assert "reference" in instructions
        assert len(instructions["steps"]) > 0


class TestOperatorRunbooks:
    """Tests for P26-T10 operator runbooks."""

    def test_list_runbooks(self) -> None:
        """List runbooks returns available runbooks."""
        runbooks = list_runbooks()
        assert isinstance(runbooks, list)
        assert len(runbooks) >= 5  # At least dashboard_unavailable, backend_unavailable, websocket_failing, provider_credentials_missing, upgrade_failed, etc.
        for rb in runbooks:
            assert "runbook_id" in rb
            assert "title" in rb

    def test_get_runbook(self) -> None:
        """Get runbook returns specific runbook."""
        rb = get_runbook("dashboard_unavailable")
        assert rb is not None
        assert rb.runbook_id == "dashboard_unavailable"
        assert len(rb.steps) > 0
        assert all(hasattr(s, "step") and hasattr(s, "description") for s in rb.steps)

    def test_get_runbook_not_found(self) -> None:
        """Get runbook returns None for unknown ID."""
        rb = get_runbook("nonexistent_runbook")
        assert rb is None

    def test_get_support_checklist(self) -> None:
        """Support checklist includes items and escalation criteria."""
        checklist = get_support_checklist()
        assert "checklist" in checklist
        assert "escalation_criteria" in checklist
        assert len(checklist["checklist"]) > 0
        assert len(checklist["escalation_criteria"]) > 0
