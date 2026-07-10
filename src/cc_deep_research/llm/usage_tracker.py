"""Provider-neutral token usage ledger with JSONL compatibility.

This module provides utilities for tracking Anthropic API token usage,
persisting entries to JSONL files, and calculating TPM metrics.
"""

from __future__ import annotations

import hashlib
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from cc_deep_research.config import get_default_config_path

# Default path for token usage log
DEFAULT_USAGE_LOG_PATH = get_default_config_path().parent / "token_usage.jsonl"
LEGACY_USAGE_LOG_PATH = Path("data/token_usage.jsonl")


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
    provider: str = Field(default="anthropic", description="Provider identity")
    transport: str = Field(default="anthropic_api", description="Transport identity")
    operation: str = Field(default="unknown", description="Logical operation")
    session_id: str | None = Field(default=None, description="Research session identity")
    agent_id: str | None = Field(default=None, description="Agent identity")


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


def _ledger_path(log_path: Path) -> Path:
    return log_path.with_suffix(log_path.suffix + ".sqlite3")


def _event_key(
    entry: TokenUsageEntry,
    *,
    source_path: str = "",
    byte_offset: int = 0,
) -> str:
    if entry.request_id:
        return f"{entry.provider}:{entry.request_id}"
    payload = f"{source_path}:{byte_offset}:{entry.model_dump_json()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS usage_entries (
            event_key TEXT PRIMARY KEY,
            source_path TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            input_tokens INTEGER NOT NULL,
            output_tokens INTEGER NOT NULL,
            total_tokens INTEGER NOT NULL,
            cache_creation_tokens INTEGER NOT NULL,
            cache_read_tokens INTEGER NOT NULL,
            latency_ms INTEGER NOT NULL,
            payload TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS usage_sources (
            source_path TEXT PRIMARY KEY,
            byte_offset INTEGER NOT NULL,
            file_size INTEGER NOT NULL,
            mtime_ns INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_usage_timestamp ON usage_entries(timestamp)"
    )


def _sync_source(conn: sqlite3.Connection, source: Path) -> None:
    """Incrementally index one compatibility JSONL source."""
    source_key = str(source.resolve())
    if not source.exists():
        return
    stat = source.stat()
    state = conn.execute(
        """
        SELECT byte_offset, file_size, mtime_ns
        FROM usage_sources WHERE source_path = ?
        """,
        (source_key,),
    ).fetchone()
    offset, previous_size, previous_mtime = state or (0, 0, 0)
    if stat.st_size == previous_size and stat.st_mtime_ns == previous_mtime:
        return

    rewritten = (
        state is None
        or stat.st_size < offset
        or (stat.st_size <= previous_size and stat.st_mtime_ns != previous_mtime)
    )
    if rewritten:
        conn.execute("DELETE FROM usage_entries WHERE source_path = ?", (source_key,))
        offset = 0

    committed_offset = offset
    with open(source, "rb") as handle:
        handle.seek(offset)
        while raw_line := handle.readline():
            line_start = committed_offset
            if not raw_line.endswith(b"\n"):
                break
            committed_offset = handle.tell()
            try:
                entry = TokenUsageEntry.model_validate_json(raw_line)
            except Exception:
                continue
            conn.execute(
                """
                INSERT OR IGNORE INTO usage_entries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _event_key(
                        entry,
                        source_path=source_key,
                        byte_offset=line_start,
                    ),
                    source_key,
                    entry.timestamp,
                    entry.input_tokens,
                    entry.output_tokens,
                    entry.total_tokens,
                    entry.cache_creation_input_tokens,
                    entry.cache_read_input_tokens,
                    entry.latency_ms,
                    entry.model_dump_json(),
                ),
            )

    conn.execute(
        """
        INSERT OR REPLACE INTO usage_sources VALUES (?, ?, ?, ?)
        """,
        (source_key, committed_offset, stat.st_size, stat.st_mtime_ns),
    )


def _connect_synced(log_path: Path | None) -> sqlite3.Connection:
    """Open the ledger and synchronize new JSONL records."""
    primary = log_path or DEFAULT_USAGE_LOG_PATH
    primary.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_ledger_path(primary))
    _ensure_schema(conn)
    if log_path is None and primary != LEGACY_USAGE_LOG_PATH:
        _sync_source(conn, LEGACY_USAGE_LOG_PATH)
    _sync_source(conn, primary)
    conn.commit()
    return conn


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

    with open(path, "a", encoding="utf-8") as f:
        f.write(entry.model_dump_json() + "\n")
        f.flush()

    with _connect_synced(log_path):
        pass


def read_usage_entries(log_path: Path | None = None) -> list[TokenUsageEntry]:
    """Read all entries from the JSONL log file.

    Args:
        log_path: Path to the JSONL file, defaults to data/token_usage.jsonl.

    Returns:
        List of token usage entries.
    """
    with _connect_synced(log_path) as conn:
        rows = conn.execute(
            "SELECT payload FROM usage_entries ORDER BY timestamp ASC, event_key ASC"
        ).fetchall()
    return [TokenUsageEntry.model_validate_json(row[0]) for row in rows]


def get_lifetime_summary(log_path: Path | None = None) -> LifetimeSummary:
    """Get aggregated lifetime usage summary.

    Args:
        log_path: Path to the JSONL file, defaults to data/token_usage.jsonl.

    Returns:
        Lifetime summary with totals and averages.
    """
    with _connect_synced(log_path) as conn:
        row = conn.execute(
            """
            SELECT COUNT(*), COALESCE(SUM(input_tokens), 0),
                   COALESCE(SUM(output_tokens), 0), COALESCE(SUM(total_tokens), 0),
                   COALESCE(SUM(cache_creation_tokens), 0),
                   COALESCE(SUM(cache_read_tokens), 0), COALESCE(SUM(latency_ms), 0)
            FROM usage_entries
            """
        ).fetchone()
    total_requests, total_input, total_output, total, total_cache_creation, total_cache_read, total_latency = row
    if total_requests == 0:
        return LifetimeSummary()

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
    now = time.time()
    cutoff = now - window_seconds
    cutoff_iso = datetime.fromtimestamp(cutoff, tz=UTC).isoformat()
    with _connect_synced(log_path) as conn:
        recent_tokens = int(
            conn.execute(
                """
                SELECT COALESCE(SUM(output_tokens), 0)
                FROM usage_entries WHERE timestamp >= ?
                """,
                (cutoff_iso,),
            ).fetchone()[0]
        )

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
    with _connect_synced(log_path) as conn:
        row = conn.execute(
            """
            SELECT AVG((CAST(output_tokens AS REAL) / latency_ms) * 60000.0)
            FROM usage_entries WHERE latency_ms > 0
            """
        ).fetchone()
    return float(row[0]) if row and row[0] is not None else 0.0


__all__ = [
    "TokenUsageEntry",
    "LifetimeSummary",
    "append_usage_entry",
    "read_usage_entries",
    "get_lifetime_summary",
    "calculate_rolling_tpm",
    "calculate_average_tpm",
    "DEFAULT_USAGE_LOG_PATH",
    "LEGACY_USAGE_LOG_PATH",
]
