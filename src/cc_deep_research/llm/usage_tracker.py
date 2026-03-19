"""Token usage tracking with JSONL persistence.

This module provides utilities for tracking Anthropic API token usage,
persisting entries to JSONL files, and calculating TPM metrics.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

# Default path for token usage log
DEFAULT_USAGE_LOG_PATH = Path("data/token_usage.jsonl")


class TokenUsageEntry(BaseModel):
    """Token usage entry for a single API call."""

    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="UTC ISO format timestamp",
    )
    model: str = Field(description="Model used")
    base_url: str = Field(description="API base URL")
    request_id: str | None = Field(default=None, description="Request ID from response")
    input_tokens: int = Field(default=0, ge=0, description="Input token count")
    output_tokens: int = Field(default=0, ge=0, description="Output token count")
    total_tokens: int = Field(default=0, ge=0, description="Total tokens")
    cache_creation_input_tokens: int = Field(default=0, ge=0, description="Cache creation tokens")
    cache_read_input_tokens: int = Field(default=0, ge=0, description="Cache read tokens")
    max_tokens: int = Field(default=0, ge=0, description="Max tokens configured")
    latency_ms: int = Field(default=0, ge=0, description="Request latency in ms")


class LifetimeSummary(BaseModel):
    """Lifetime usage summary."""

    total_requests: int = Field(default=0, description="Total number of requests")
    total_input_tokens: int = Field(default=0, description="Total input tokens")
    total_output_tokens: int = Field(default=0, description="Total output tokens")
    total_tokens: int = Field(default=0, description="Total tokens")
    total_cache_creation_tokens: int = Field(default=0, description="Total cache creation tokens")
    total_cache_read_tokens: int = Field(default=0, description="Total cache read tokens")
    average_input_tokens: float = Field(default=0.0, description="Average input tokens per request")
    average_output_tokens: float = Field(
        default=0.0, description="Average output tokens per request"
    )
    average_latency_ms: float = Field(default=0.0, description="Average latency in ms")


def append_usage_entry(
    entry: TokenUsageEntry,
    log_path: Path | None = None,
) -> None:
    """Append a usage entry to the JSONL log file.

    Args:
        entry: The token usage entry to append.
        log_path: Path to the JSONL file, defaults to data/token_usage.jsonl.
    """
    path = log_path or DEFAULT_USAGE_LOG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "a") as f:
        f.write(entry.model_dump_json() + "\n")


def read_usage_entries(log_path: Path | None = None) -> list[TokenUsageEntry]:
    """Read all entries from the JSONL log file.

    Args:
        log_path: Path to the JSONL file, defaults to data/token_usage.jsonl.

    Returns:
        List of token usage entries.
    """
    path = log_path or DEFAULT_USAGE_LOG_PATH
    if not path.exists():
        return []

    entries: list[TokenUsageEntry] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                entries.append(TokenUsageEntry(**data))
            except (json.JSONDecodeError, Exception):
                # Skip malformed entries
                continue

    return entries


def get_lifetime_summary(log_path: Path | None = None) -> LifetimeSummary:
    """Get aggregated lifetime usage summary.

    Args:
        log_path: Path to the JSONL file, defaults to data/token_usage.jsonl.

    Returns:
        Lifetime summary with totals and averages.
    """
    entries = read_usage_entries(log_path)

    if not entries:
        return LifetimeSummary()

    total_requests = len(entries)
    total_input = sum(e.input_tokens for e in entries)
    total_output = sum(e.output_tokens for e in entries)
    total = sum(e.total_tokens for e in entries)
    total_cache_creation = sum(e.cache_creation_input_tokens for e in entries)
    total_cache_read = sum(e.cache_read_input_tokens for e in entries)
    total_latency = sum(e.latency_ms for e in entries)

    return LifetimeSummary(
        total_requests=total_requests,
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        total_tokens=total,
        total_cache_creation_tokens=total_cache_creation,
        total_cache_read_tokens=total_cache_read,
        average_input_tokens=total_input / total_requests if total_requests > 0 else 0.0,
        average_output_tokens=total_output / total_requests if total_requests > 0 else 0.0,
        average_latency_ms=total_latency / total_requests if total_requests > 0 else 0.0,
    )


def calculate_rolling_tpm(
    log_path: Path | None = None,
    window_seconds: int = 60,
) -> float:
    """Calculate rolling tokens per minute over the last window_seconds.

    Args:
        log_path: Path to the JSONL file, defaults to data/token_usage.jsonl.
        window_seconds: Time window in seconds, defaults to 60.

    Returns:
        Tokens per minute over the window, or 0.0 if no recent entries.
    """
    entries = read_usage_entries(log_path)

    if not entries:
        return 0.0

    now = time.time()
    cutoff = now - window_seconds

    recent_tokens = 0
    for entry in entries:
        try:
            entry_time = datetime.fromisoformat(entry.timestamp).timestamp()
            if entry_time >= cutoff:
                recent_tokens += entry.output_tokens
        except (ValueError, TypeError):
            continue

    # Convert to tokens per minute
    if window_seconds > 0:
        return (recent_tokens / window_seconds) * 60.0
    return 0.0


def calculate_average_tpm(log_path: Path | None = None) -> float:
    """Calculate average output TPM per call.

    Formula: (output_tokens / latency_ms) * 60000

    Args:
        log_path: Path to the JSONL file, defaults to data/token_usage.jsonl.

    Returns:
        Average output TPM per call, or 0.0 if no entries.
    """
    entries = read_usage_entries(log_path)

    if not entries:
        return 0.0

    total_tpm = 0.0
    valid_count = 0

    for entry in entries:
        if entry.latency_ms > 0:
            tpm = (entry.output_tokens / entry.latency_ms) * 60000
            total_tpm += tpm
            valid_count += 1

    return total_tpm / valid_count if valid_count > 0 else 0.0


__all__ = [
    "TokenUsageEntry",
    "LifetimeSummary",
    "append_usage_entry",
    "read_usage_entries",
    "get_lifetime_summary",
    "calculate_rolling_tpm",
    "calculate_average_tpm",
    "DEFAULT_USAGE_LOG_PATH",
]
