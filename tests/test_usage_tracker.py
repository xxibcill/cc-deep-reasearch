"""Tests for token usage tracking."""

from __future__ import annotations

import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from cc_deep_research.llm.usage_tracker import (
    TokenUsageEntry,
    append_usage_entry,
    calculate_average_tpm,
    calculate_rolling_tpm,
    get_lifetime_summary,
    read_usage_entries,
)

# Test fixtures


@pytest.fixture
def temp_log_path() -> Path:
    """Create a temporary log file path."""
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = Path(f.name)
    yield path
    # Cleanup
    if path.exists():
        path.unlink()


@pytest.fixture
def sample_entry() -> TokenUsageEntry:
    """Create a sample usage entry."""
    return TokenUsageEntry(
        timestamp=datetime.now(UTC).isoformat(),
        model="claude-sonnet-4-6",
        base_url="https://api.anthropic.com",
        request_id="req-123",
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
        max_tokens=512,
        latency_ms=1000,
    )


# Usage Log Persistence Tests


def test_append_and_read_entry(temp_log_path: Path, sample_entry: TokenUsageEntry) -> None:
    """Append and read a usage entry."""
    append_usage_entry(sample_entry, temp_log_path)

    entries = read_usage_entries(temp_log_path)

    assert len(entries) == 1
    assert entries[0].model == sample_entry.model
    assert entries[0].input_tokens == sample_entry.input_tokens
    assert entries[0].output_tokens == sample_entry.output_tokens
    assert entries[0].request_id == sample_entry.request_id


def test_read_empty_file(temp_log_path: Path) -> None:
    """Reading empty file returns empty list."""
    entries = read_usage_entries(temp_log_path)
    assert entries == []


def test_read_malformed_json_skipped(temp_log_path: Path) -> None:
    """Malformed JSON lines are skipped."""
    # Write valid entry followed by malformed line
    valid_entry = TokenUsageEntry(
        model="claude-sonnet-4-6",
        base_url="https://api.anthropic.com",
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        max_tokens=512,
        latency_ms=1000,
    )

    with open(temp_log_path, "w") as f:
        f.write(valid_entry.model_dump_json() + "\n")
        f.write("this is not valid json\n")
        f.write(valid_entry.model_dump_json() + "\n")

    entries = read_usage_entries(temp_log_path)

    # Should have 2 entries, malformed line skipped
    assert len(entries) == 2


# Rolling TPM Calculation Tests


def test_rolling_tpm_with_recent_entries(temp_log_path: Path) -> None:
    """Rolling TPM calculation with recent entries."""
    # Create entries with current timestamps
    now = time.time()
    for i in range(3):
        entry = TokenUsageEntry(
            timestamp=datetime.fromtimestamp(now - i * 10, tz=UTC).isoformat(),
            model="claude-sonnet-4-6",
            base_url="https://api.anthropic.com",
            input_tokens=100,
            output_tokens=100,  # 100 tokens each
            total_tokens=200,
            max_tokens=512,
            latency_ms=1000,
        )
        append_usage_entry(entry, temp_log_path)

    # Calculate rolling TPM over 60 seconds
    tpm = calculate_rolling_tpm(temp_log_path, window_seconds=60)

    # 3 entries * 100 output tokens each = 300 tokens in 60 seconds
    # TPM = (300 / 60) * 60 = 300
    assert tpm == 300.0


def test_rolling_tpm_empty_log(temp_log_path: Path) -> None:
    """Rolling TPM with empty log returns 0."""
    tpm = calculate_rolling_tpm(temp_log_path)
    assert tpm == 0.0


def test_rolling_tpm_old_entries_excluded(temp_log_path: Path) -> None:
    """Old entries outside window are excluded from rolling TPM."""
    now = time.time()

    # Create old entry (120 seconds ago)
    old_entry = TokenUsageEntry(
        timestamp=datetime.fromtimestamp(now - 120, tz=UTC).isoformat(),
        model="claude-sonnet-4-6",
        base_url="https://api.anthropic.com",
        input_tokens=100,
        output_tokens=100,
        total_tokens=200,
        max_tokens=512,
        latency_ms=1000,
    )
    append_usage_entry(old_entry, temp_log_path)

    # Create recent entry (10 seconds ago)
    recent_entry = TokenUsageEntry(
        timestamp=datetime.fromtimestamp(now - 10, tz=UTC).isoformat(),
        model="claude-sonnet-4-6",
        base_url="https://api.anthropic.com",
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        max_tokens=512,
        latency_ms=1000,
    )
    append_usage_entry(recent_entry, temp_log_path)

    # Calculate rolling TPM over 60 seconds - only recent entry should count
    tpm = calculate_rolling_tpm(temp_log_path, window_seconds=60)

    # Only 50 output tokens from recent entry in 60 seconds
    # TPM = (50 / 60) * 60 = 50
    assert tpm == 50.0


# Average TPM Calculation Tests


def test_average_tpm_calculation(temp_log_path: Path) -> None:
    """Average TPM calculation: (output_tokens / latency_ms) * 60000."""
    # Create entries with known values
    entry1 = TokenUsageEntry(
        model="claude-sonnet-4-6",
        base_url="https://api.anthropic.com",
        input_tokens=100,
        output_tokens=1000,  # 1000 tokens
        total_tokens=1100,
        max_tokens=512,
        latency_ms=1000,  # 1000ms = 1 second
    )
    append_usage_entry(entry1, temp_log_path)

    # TPM = (1000 / 1000) * 60000 = 60000
    tpm = calculate_average_tpm(temp_log_path)
    assert tpm == 60000.0


def test_average_tpm_zero_latency(temp_log_path: Path) -> None:
    """Entries with zero latency are excluded from average TPM."""
    entry1 = TokenUsageEntry(
        model="claude-sonnet-4-6",
        base_url="https://api.anthropic.com",
        input_tokens=100,
        output_tokens=1000,
        total_tokens=1100,
        max_tokens=512,
        latency_ms=0,  # Zero latency - should be excluded
    )
    append_usage_entry(entry1, temp_log_path)

    tpm = calculate_average_tpm(temp_log_path)
    assert tpm == 0.0


def test_average_tpm_empty_log(temp_log_path: Path) -> None:
    """Average TPM with empty log returns 0."""
    tpm = calculate_average_tpm(temp_log_path)
    assert tpm == 0.0


# Lifetime Summary Tests


def test_lifetime_summary_aggregates_correctly(temp_log_path: Path) -> None:
    """Lifetime summary aggregates all entries correctly."""
    # Create multiple entries
    for i in range(3):
        entry = TokenUsageEntry(
            model="claude-sonnet-4-6",
            base_url="https://api.anthropic.com",
            input_tokens=100 + i * 10,  # 100, 110, 120
            output_tokens=50 + i * 10,  # 50, 60, 70
            total_tokens=150 + i * 20,  # 150, 170, 190
            cache_creation_input_tokens=10,
            cache_read_input_tokens=5,
            max_tokens=512,
            latency_ms=1000 + i * 100,  # 1000, 1100, 1200
        )
        append_usage_entry(entry, temp_log_path)

    summary = get_lifetime_summary(temp_log_path)

    assert summary.total_requests == 3
    assert summary.total_input_tokens == 330  # 100 + 110 + 120
    assert summary.total_output_tokens == 180  # 50 + 60 + 70
    assert summary.total_tokens == 510  # 150 + 170 + 190
    assert summary.total_cache_creation_tokens == 30  # 10 * 3
    assert summary.total_cache_read_tokens == 15  # 5 * 3
    assert summary.average_input_tokens == 110.0  # 330 / 3
    assert summary.average_output_tokens == 60.0  # 180 / 3
    assert summary.average_latency_ms == 1100.0  # (1000 + 1100 + 1200) / 3


def test_lifetime_summary_empty_log(temp_log_path: Path) -> None:
    """Lifetime summary with empty log returns zeros."""
    summary = get_lifetime_summary(temp_log_path)

    assert summary.total_requests == 0
    assert summary.total_input_tokens == 0
    assert summary.total_output_tokens == 0
    assert summary.total_tokens == 0
    assert summary.total_cache_creation_tokens == 0
    assert summary.total_cache_read_tokens == 0
    assert summary.average_input_tokens == 0.0
    assert summary.average_output_tokens == 0.0
    assert summary.average_latency_ms == 0.0
