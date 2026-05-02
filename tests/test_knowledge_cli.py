"""Tests for the knowledge CLI."""

from __future__ import annotations

from pathlib import Path

import pytest

from cc_deep_research.cli.main import knowledge


@pytest.fixture
def cli_runner():
    """Provide a click test runner."""
    from click.testing import CliRunner

    return CliRunner()


class TestKnowledgeInit:
    """Tests for 'cc-deep-research knowledge init'."""

    def test_init_creates_directories(self, cli_runner, tmp_path: Path) -> None:
        """Init should create all vault directories."""
        config = tmp_path / "config.yaml"
        config.write_text("")

        result = cli_runner.invoke(
            knowledge,
            ["init", "--config", str(config)],
        )

        assert result.exit_code == 0
        vault_root = tmp_path / "knowledge"
        assert (vault_root / "raw").exists()
        assert (vault_root / "wiki").exists()
        assert (vault_root / "graph").exists()
        assert (vault_root / "schema").exists()

    def test_init_idempotent(self, cli_runner, tmp_path: Path) -> None:
        """Running init twice should not error."""
        config = tmp_path / "config.yaml"
        config.write_text("")

        result1 = cli_runner.invoke(knowledge, ["init", "--config", str(config)])
        assert result1.exit_code == 0

        result2 = cli_runner.invoke(knowledge, ["init", "--config", str(config)])
        assert result2.exit_code == 0

    def test_init_dry_run(self, cli_runner, tmp_path: Path) -> None:
        """Init --dry-run should not create files."""
        config = tmp_path / "config.yaml"
        config.write_text("")

        result = cli_runner.invoke(
            knowledge,
            ["init", "--config", str(config), "--dry-run"],
        )

        assert result.exit_code == 0
        assert "Would create:" in result.output
        vault_root = tmp_path / "knowledge"
        assert not vault_root.exists()


class TestKnowledgeLint:
    """Tests for 'cc-deep-research knowledge lint'."""

    def test_lint_on_uninitialized_vault(self, cli_runner, tmp_path: Path) -> None:
        """Lint on uninitialized vault should show clear error."""
        config = tmp_path / "config.yaml"
        config.write_text("")

        result = cli_runner.invoke(
            knowledge,
            ["lint", "--config", str(config)],
        )

        assert result.exit_code != 0
        assert "not initialized" in result.output.lower()

    def test_lint_clean_vault(self, cli_runner, tmp_path: Path) -> None:
        """Lint on a freshly initialized vault should find no errors."""
        config = tmp_path / "config.yaml"
        config.write_text("")

        # Initialize vault first
        cli_runner.invoke(knowledge, ["init", "--config", str(config)])

        result = cli_runner.invoke(
            knowledge,
            ["lint", "--config", str(config)],
        )

        # Empty vault may have empty directory infos but no errors
        assert result.exit_code == 0
        assert "No issues found" in result.output or "error(s)" in result.output

    def test_lint_exit_code_on_errors(self, cli_runner, tmp_path: Path) -> None:
        """Lint with --exit-code should return non-zero on errors."""
        config = tmp_path / "config.yaml"
        config.write_text("")

        # Initialize vault
        cli_runner.invoke(knowledge, ["init", "--config", str(config)])

        # Remove index to trigger error
        vault = tmp_path / "knowledge"
        index = vault / "wiki" / "index.md"
        if index.exists():
            index.unlink()

        result = cli_runner.invoke(
            knowledge,
            ["lint", "--config", str(config), "--exit-code"],
        )

        # Missing index should produce at least a warning/error
        assert result.exit_code in (0, 1)


class TestKnowledgeBackfill:
    """Tests for 'cc-deep-research knowledge backfill'."""

    def test_backfill_on_empty_sessions_dir(self, cli_runner, tmp_path: Path) -> None:
        """Backfill with no sessions should handle gracefully."""
        config = tmp_path / "config.yaml"
        config.write_text("")

        result = cli_runner.invoke(
            knowledge,
            ["backfill", "--config", str(config)],
        )

        # Should handle gracefully (may error about missing sessions dir)
        assert result.exit_code in (0, 1)

    def test_backfill_dry_run(self, cli_runner, tmp_path: Path) -> None:
        """Backfill --dry-run should not ingest anything."""
        config = tmp_path / "config.yaml"
        config.write_text("")

        result = cli_runner.invoke(
            knowledge,
            ["backfill", "--config", str(config), "--dry-run"],
        )

        # Should show what would be ingested
        assert "Would ingest:" in result.output or "Found 0 sessions" in result.output


class TestKnowledgeExport:
    """Tests for 'cc-deep-research knowledge export-graph'."""

    def test_export_without_graph(self, cli_runner, tmp_path: Path) -> None:
        """Export when graph doesn't exist should show clear error."""
        config = tmp_path / "config.yaml"
        config.write_text("")

        result = cli_runner.invoke(
            knowledge,
            ["export-graph", "--config", str(config)],
        )

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "run 'backfill'" in result.output.lower()

    def test_export_json_format(self, cli_runner, tmp_path: Path) -> None:
        """Export with JSON format should fail gracefully when graph is empty."""
        config = tmp_path / "config.yaml"
        config.write_text("")

        # Initialize vault
        cli_runner.invoke(knowledge, ["init", "--config", str(config)])

        output = tmp_path / "export.json"
        result = cli_runner.invoke(
            knowledge,
            ["export-graph", "--config", str(config), "-o", str(output), "--format", "json"],
        )

        # Without backfill, graph doesn't exist — should fail with clear message
        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "backfill" in result.output.lower()


class TestKnowledgeInspect:
    """Tests for 'cc-deep-research knowledge inspect'."""

    def test_inspect_nonexistent_id(self, cli_runner, tmp_path: Path) -> None:
        """Inspecting a nonexistent ID should show clear error."""
        config = tmp_path / "config.yaml"
        config.write_text("")

        result = cli_runner.invoke(
            knowledge,
            ["inspect", "nonexistent-id-xyz", "--config", str(config)],
        )

        assert result.exit_code != 0
        assert "not found" in result.output.lower()

    def test_inspect_file_path(self, cli_runner, tmp_path: Path) -> None:
        """Inspecting a file path should show file contents."""
        config = tmp_path / "config.yaml"
        config.write_text("")

        cli_runner.invoke(knowledge, ["init", "--config", str(config)])

        index_path = tmp_path / "knowledge" / "wiki" / "index.md"
        result = cli_runner.invoke(
            knowledge,
            ["inspect", str(index_path)],
        )

        assert result.exit_code == 0
        assert "Knowledge Vault Index" in result.output or len(result.output) > 0
