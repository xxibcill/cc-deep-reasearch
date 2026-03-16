"""CLI tests for monitoring and dashboard commands."""

from __future__ import annotations

import subprocess
from pathlib import Path

from click.testing import CliRunner

from cc_deep_research.cli import main


def test_telemetry_dashboard_passes_live_monitoring_args(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """The dashboard command should pass telemetry paths and live options to Streamlit."""
    captured: dict[str, object] = {}

    def fake_ingest(*, base_dir: Path | None = None, db_path: Path | None = None):
        captured["ingest_base_dir"] = base_dir
        captured["ingest_db_path"] = db_path
        return {"sessions": 0, "events": 0}

    def fake_run(command: list[str], check: bool) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured["check"] = check
        return subprocess.CompletedProcess(args=command, returncode=0)

    monkeypatch.setattr("cc_deep_research.cli.ingest_telemetry_to_duckdb", fake_ingest)
    monkeypatch.setattr("cc_deep_research.cli.subprocess.run", fake_run)

    runner = CliRunner()
    db_path = tmp_path / "telemetry.duckdb"
    result = runner.invoke(
        main,
        [
            "telemetry",
            "dashboard",
            "--base-dir",
            str(tmp_path),
            "--db-path",
            str(db_path),
            "--port",
            "9999",
            "--refresh-seconds",
            "7",
            "--tail-limit",
            "123",
        ],
    )

    assert result.exit_code == 0
    assert captured["ingest_base_dir"] == tmp_path
    assert captured["ingest_db_path"] == db_path
    assert captured["check"] is True

    command = captured["command"]
    assert isinstance(command, list)
    assert "--server.port" in command
    assert "--db-path" in command
    assert str(db_path) in command
    assert "--telemetry-dir" in command
    assert str(tmp_path) in command
    assert "--refresh-seconds" in command
    assert "7" in command
    assert "--tail-limit" in command
    assert "123" in command


def test_telemetry_ingest_reports_missing_dashboard_dependencies(
    monkeypatch,
) -> None:
    """The ingest command should surface a Click error for missing optional deps."""

    def fake_ingest(*, base_dir: Path | None = None, db_path: Path | None = None):
        del base_dir, db_path
        raise RuntimeError(
            'Telemetry ingestion requires optional dashboard dependencies. '
            'Install with `pip install "cc-deep-research[dashboard]"`.'
        )

    monkeypatch.setattr("cc_deep_research.cli.ingest_telemetry_to_duckdb", fake_ingest)

    runner = CliRunner()
    result = runner.invoke(main, ["telemetry", "ingest"])

    assert result.exit_code != 0
    assert "Telemetry ingestion requires optional dashboard dependencies." in result.output
    assert 'pip install "cc-deep-research[dashboard]"' in result.output


def test_telemetry_ingest_passes_paths_to_ingestion(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """The ingest command should pass explicit telemetry paths through unchanged."""
    captured: dict[str, object] = {}

    def fake_ingest(*, base_dir: Path | None = None, db_path: Path | None = None):
        captured["base_dir"] = base_dir
        captured["db_path"] = db_path
        return {"sessions": 2, "events": 5}

    monkeypatch.setattr("cc_deep_research.cli.ingest_telemetry_to_duckdb", fake_ingest)

    runner = CliRunner()
    db_path = tmp_path / "telemetry.duckdb"
    result = runner.invoke(
        main,
        [
            "telemetry",
            "ingest",
            "--base-dir",
            str(tmp_path),
            "--db-path",
            str(db_path),
        ],
    )

    assert result.exit_code == 0
    assert captured["base_dir"] == tmp_path
    assert captured["db_path"] == db_path


def test_telemetry_dashboard_reports_missing_dashboard_dependencies(
    monkeypatch,
) -> None:
    """The dashboard command should surface a Click error for missing optional deps."""

    def fake_ingest(*, base_dir: Path | None = None, db_path: Path | None = None):
        del base_dir, db_path
        raise RuntimeError(
            'Telemetry ingestion requires optional dashboard dependencies. '
            'Install with `pip install "cc-deep-research[dashboard]"`.'
        )

    monkeypatch.setattr("cc_deep_research.cli.ingest_telemetry_to_duckdb", fake_ingest)

    runner = CliRunner()
    result = runner.invoke(main, ["telemetry", "dashboard"])

    assert result.exit_code != 0
    assert "Telemetry ingestion requires optional dashboard dependencies." in result.output
    assert 'pip install "cc-deep-research[dashboard]"' in result.output
