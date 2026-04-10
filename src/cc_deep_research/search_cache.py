"""Helpers for stable web-search cache identity, storage, and serialization."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cc_deep_research.models.search import SearchOptions, SearchResult

_CACHE_TABLE_NAME = "web_search_cache"


def _normalize_provider_name(provider_name: str) -> str:
    """Normalize provider identity for cache comparisons."""
    return " ".join(provider_name.strip().lower().split())


def _normalize_query_text(query: str) -> str:
    """Normalize query text while preserving meaningful punctuation."""
    return " ".join(query.strip().casefold().split())


def _normalize_timestamp(value: datetime) -> datetime:
    """Return a naive UTC timestamp for stable storage and comparisons."""
    if value.tzinfo is None:
        return value.replace(tzinfo=None)
    return value.astimezone(UTC).replace(tzinfo=None)


def _utcnow() -> datetime:
    """Return the current time as a naive UTC timestamp."""
    return datetime.now(UTC).replace(tzinfo=None)


def _serialize_timestamp(value: datetime) -> str:
    """Serialize timestamps in ISO format for SQLite storage."""
    return _normalize_timestamp(value).isoformat()


def _deserialize_timestamp(value: str) -> datetime:
    """Parse a stored ISO timestamp."""
    return _normalize_timestamp(datetime.fromisoformat(value))


def serialize_search_result(result: SearchResult) -> str:
    """Serialize a search result into a stable JSON payload."""
    payload = result.model_dump(mode="json")
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def deserialize_search_result(payload: str) -> SearchResult:
    """Deserialize a stored payload into a fresh SearchResult instance."""
    return SearchResult.model_validate(json.loads(payload))


@dataclass(frozen=True, slots=True)
class SearchCacheIdentity:
    """Deterministic cache identity for one web search request."""

    provider: str
    query: str
    search_depth: str
    max_results: int
    include_raw_content: bool

    def to_signature_payload(self) -> dict[str, str | int | bool]:
        """Return a serialized payload with normalized cache inputs."""
        return {
            "provider": self.provider,
            "query": self.query,
            "search_depth": self.search_depth,
            "max_results": self.max_results,
            "include_raw_content": self.include_raw_content,
        }

    def to_signature(self) -> str:
        """Return the stable serialized signature for cache lookups."""
        return json.dumps(
            self.to_signature_payload(),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )

    def to_cache_key(self) -> str:
        """Return a compact hashed cache key derived from the signature."""
        return hashlib.sha256(self.to_signature().encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class SearchCacheEntry:
    """One persisted cache entry reconstructed from storage."""

    cache_key: str
    provider: str
    normalized_query: str
    request_signature: str
    result: SearchResult
    created_at: datetime
    expires_at: datetime
    last_accessed_at: datetime
    hit_count: int

    def is_expired(self, *, now: datetime | None = None) -> bool:
        """Return whether the entry is expired at the provided time."""
        current_time = _normalize_timestamp(now) if now is not None else _utcnow()
        return self.expires_at <= current_time


def _entry_from_row(row: sqlite3.Row) -> SearchCacheEntry:
    """Convert a SQLite row into an immutable cache entry."""
    return SearchCacheEntry(
        cache_key=str(row["cache_key"]),
        provider=str(row["provider"]),
        normalized_query=str(row["normalized_query"]),
        request_signature=str(row["request_signature"]),
        result=deserialize_search_result(str(row["serialized_result"])),
        created_at=_deserialize_timestamp(str(row["created_at"])),
        expires_at=_deserialize_timestamp(str(row["expires_at"])),
        last_accessed_at=_deserialize_timestamp(str(row["last_accessed_at"])),
        hit_count=int(row["hit_count"]),
    )


class SearchCacheStore:
    """SQLite-backed persistent store for search cache entries."""

    def __init__(self, db_path: Path, *, max_entries: int | None = None) -> None:
        self._db_path = Path(db_path)
        self._max_entries = max_entries
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    @property
    def db_path(self) -> Path:
        """Return the backing SQLite database path."""
        return self._db_path

    def get(
        self,
        cache_key: str,
        *,
        include_expired: bool = False,
        now: datetime | None = None,
    ) -> SearchCacheEntry | None:
        """Return one cache entry and record a hit when it is still valid."""
        current_time = _normalize_timestamp(now) if now is not None else _utcnow()
        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT cache_key, provider, normalized_query, request_signature, serialized_result,
                       created_at, expires_at, last_accessed_at, hit_count
                FROM {_CACHE_TABLE_NAME}
                WHERE cache_key = ?
                """,
                (cache_key,),
            ).fetchone()
            if row is None:
                return None

            entry = _entry_from_row(row)
            if entry.is_expired(now=current_time):
                return entry if include_expired else None

            last_accessed_at = _serialize_timestamp(current_time)
            connection.execute(
                f"""
                UPDATE {_CACHE_TABLE_NAME}
                SET last_accessed_at = ?, hit_count = hit_count + 1
                WHERE cache_key = ?
                """,
                (last_accessed_at, cache_key),
            )
            connection.commit()

            refreshed_row = connection.execute(
                f"""
                SELECT cache_key, provider, normalized_query, request_signature, serialized_result,
                       created_at, expires_at, last_accessed_at, hit_count
                FROM {_CACHE_TABLE_NAME}
                WHERE cache_key = ?
                """,
                (cache_key,),
            ).fetchone()
            if refreshed_row is None:
                return None
            return _entry_from_row(refreshed_row)

    def put(
        self,
        *,
        identity: SearchCacheIdentity,
        result: SearchResult,
        ttl_seconds: int,
        now: datetime | None = None,
    ) -> SearchCacheEntry:
        """Insert or replace a cache entry for the provided identity."""
        current_time = _normalize_timestamp(now) if now is not None else _utcnow()
        expires_at = current_time + timedelta(seconds=ttl_seconds)
        cache_key = identity.to_cache_key()

        with self._connect() as connection:
            connection.execute(
                f"""
                INSERT INTO {_CACHE_TABLE_NAME} (
                    cache_key,
                    provider,
                    normalized_query,
                    request_signature,
                    serialized_result,
                    created_at,
                    expires_at,
                    last_accessed_at,
                    hit_count
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(cache_key) DO UPDATE SET
                    provider = excluded.provider,
                    normalized_query = excluded.normalized_query,
                    request_signature = excluded.request_signature,
                    serialized_result = excluded.serialized_result,
                    created_at = excluded.created_at,
                    expires_at = excluded.expires_at,
                    last_accessed_at = excluded.last_accessed_at,
                    hit_count = 0
                """,
                (
                    cache_key,
                    identity.provider,
                    identity.query,
                    identity.to_signature(),
                    serialize_search_result(result),
                    _serialize_timestamp(current_time),
                    _serialize_timestamp(expires_at),
                    _serialize_timestamp(current_time),
                ),
            )
            self._enforce_max_entries(connection=connection, now=current_time)
            connection.commit()

            row = connection.execute(
                f"""
                SELECT cache_key, provider, normalized_query, request_signature, serialized_result,
                       created_at, expires_at, last_accessed_at, hit_count
                FROM {_CACHE_TABLE_NAME}
                WHERE cache_key = ?
                """,
                (cache_key,),
            ).fetchone()
            if row is None:
                raise RuntimeError("Failed to reload inserted search cache entry")
            return _entry_from_row(row)

    def delete(self, cache_key: str) -> bool:
        """Delete one cache entry by key."""
        with self._connect() as connection:
            cursor = connection.execute(
                f"DELETE FROM {_CACHE_TABLE_NAME} WHERE cache_key = ?",
                (cache_key,),
            )
            connection.commit()
        return cursor.rowcount > 0

    def purge_expired(self, *, now: datetime | None = None) -> int:
        """Delete expired cache entries and return the number removed."""
        current_time = _normalize_timestamp(now) if now is not None else _utcnow()
        with self._connect() as connection:
            cursor = connection.execute(
                f"DELETE FROM {_CACHE_TABLE_NAME} WHERE expires_at <= ?",
                (_serialize_timestamp(current_time),),
            )
            connection.commit()
        return cursor.rowcount

    def list_entries(
        self,
        *,
        include_expired: bool = False,
        limit: int = 100,
        offset: int = 0,
        now: datetime | None = None,
    ) -> list[SearchCacheEntry]:
        """List cache entries with optional pagination."""
        current_time = _normalize_timestamp(now) if now is not None else _utcnow()
        with self._connect() as connection:
            if include_expired:
                rows = connection.execute(
                    f"""
                    SELECT cache_key, provider, normalized_query, request_signature, serialized_result,
                           created_at, expires_at, last_accessed_at, hit_count
                    FROM {_CACHE_TABLE_NAME}
                    ORDER BY last_accessed_at DESC, created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                ).fetchall()
            else:
                rows = connection.execute(
                    f"""
                    SELECT cache_key, provider, normalized_query, request_signature, serialized_result,
                           created_at, expires_at, last_accessed_at, hit_count
                    FROM {_CACHE_TABLE_NAME}
                    WHERE expires_at > ?
                    ORDER BY last_accessed_at DESC, created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (_serialize_timestamp(current_time), limit, offset),
                ).fetchall()
        return [_entry_from_row(row) for row in rows]

    def get_stats(self, *, now: datetime | None = None) -> dict[str, int]:
        """Return cache statistics for monitoring."""
        current_time = _normalize_timestamp(now) if now is not None else _utcnow()
        with self._connect() as connection:
            total_row = connection.execute(
                f"SELECT COUNT(*) AS count FROM {_CACHE_TABLE_NAME}"
            ).fetchone()
            active_row = connection.execute(
                f"SELECT COUNT(*) AS count FROM {_CACHE_TABLE_NAME} WHERE expires_at > ?",
                (_serialize_timestamp(current_time),),
            ).fetchone()
            expired_row = connection.execute(
                f"SELECT COUNT(*) AS count FROM {_CACHE_TABLE_NAME} WHERE expires_at <= ?",
                (_serialize_timestamp(current_time),),
            ).fetchone()
            hits_row = connection.execute(
                f"SELECT COALESCE(SUM(hit_count), 0) AS total_hits FROM {_CACHE_TABLE_NAME}"
            ).fetchone()
            size_row = connection.execute(
                f"SELECT COALESCE(SUM(LENGTH(serialized_result)), 0) AS total_size FROM {_CACHE_TABLE_NAME}"
            ).fetchone()

        return {
            "total_entries": int(total_row["count"]) if total_row else 0,
            "active_entries": int(active_row["count"]) if active_row else 0,
            "expired_entries": int(expired_row["count"]) if expired_row else 0,
            "total_hits": int(hits_row["total_hits"]) if hits_row else 0,
            "approximate_size_bytes": int(size_row["total_size"]) if size_row else 0,
        }

    def clear(self) -> int:
        """Delete all cache entries and return the count removed."""
        with self._connect() as connection:
            row = connection.execute(f"SELECT COUNT(*) AS count FROM {_CACHE_TABLE_NAME}").fetchone()
            count = int(row["count"]) if row else 0
            connection.execute(f"DELETE FROM {_CACHE_TABLE_NAME}")
            connection.commit()
        return count

    def _initialize_schema(self) -> None:
        """Create the backing cache schema when the database is first used."""
        with self._connect() as connection:
            connection.executescript(
                f"""
                CREATE TABLE IF NOT EXISTS {_CACHE_TABLE_NAME} (
                    cache_key TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    normalized_query TEXT NOT NULL,
                    request_signature TEXT NOT NULL,
                    serialized_result TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    last_accessed_at TEXT NOT NULL,
                    hit_count INTEGER NOT NULL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_{_CACHE_TABLE_NAME}_expires_at
                    ON {_CACHE_TABLE_NAME}(expires_at);

                CREATE INDEX IF NOT EXISTS idx_{_CACHE_TABLE_NAME}_provider_query
                    ON {_CACHE_TABLE_NAME}(provider, normalized_query);
                """
            )
            connection.commit()

    def _enforce_max_entries(
        self, *, connection: sqlite3.Connection, now: datetime | None = None
    ) -> None:
        """Trim least-recently-used entries when a max size is configured."""
        if self._max_entries is None:
            return

        current_time = _normalize_timestamp(now) if now is not None else _utcnow()
        self._purge_expired_with_connection(connection=connection, now=current_time)
        row = connection.execute(f"SELECT COUNT(*) AS count FROM {_CACHE_TABLE_NAME}").fetchone()
        if row is None:
            return

        overflow = int(row["count"]) - self._max_entries
        if overflow <= 0:
            return

        connection.execute(
            f"""
            DELETE FROM {_CACHE_TABLE_NAME}
            WHERE cache_key IN (
                SELECT cache_key
                FROM {_CACHE_TABLE_NAME}
                ORDER BY last_accessed_at ASC, created_at ASC
                LIMIT ?
            )
            """,
            (overflow,),
        )

    def _purge_expired_with_connection(
        self,
        *,
        connection: sqlite3.Connection,
        now: datetime,
    ) -> None:
        """Delete expired rows inside an existing transaction."""
        connection.execute(
            f"DELETE FROM {_CACHE_TABLE_NAME} WHERE expires_at <= ?",
            (_serialize_timestamp(now),),
        )

    def _connect(self) -> sqlite3.Connection:
        """Open one SQLite connection with row access by column name."""
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection


class InFlightSearchRegistry:
    """Collapse concurrent misses onto one shared provider request."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._tasks: dict[str, asyncio.Task[SearchResult]] = {}

    async def run(
        self,
        cache_key: str,
        operation: Callable[[], Awaitable[SearchResult]],
    ) -> SearchResult:
        """Reuse one active lookup for matching concurrent cache misses."""
        async with self._lock:
            task = self._tasks.get(cache_key)
            if task is None:
                task = asyncio.create_task(operation())  # type: ignore[arg-type]
                self._tasks[cache_key] = task
                task.add_done_callback(lambda completed_task: self._discard(cache_key, completed_task))

        return await asyncio.shield(task)

    def _discard(self, cache_key: str, completed_task: asyncio.Task[SearchResult]) -> None:
        """Clear finished tasks so later misses can start a fresh lookup."""
        current_task = self._tasks.get(cache_key)
        if current_task is completed_task:
            self._tasks.pop(cache_key, None)


def build_search_cache_identity(
    *,
    provider_name: str,
    query: str,
    options: SearchOptions,
) -> SearchCacheIdentity:
    """Build the normalized cache identity for a search request."""
    return SearchCacheIdentity(
        provider=_normalize_provider_name(provider_name),
        query=_normalize_query_text(query),
        search_depth=options.search_depth.value,
        max_results=options.max_results,
        include_raw_content=options.include_raw_content,
    )


def build_search_cache_signature(
    *,
    provider_name: str,
    query: str,
    options: SearchOptions,
) -> str:
    """Return the deterministic signature for a search request."""
    return build_search_cache_identity(
        provider_name=provider_name,
        query=query,
        options=options,
    ).to_signature()


def build_search_cache_key(
    *,
    provider_name: str,
    query: str,
    options: SearchOptions,
) -> str:
    """Return the deterministic hashed cache key for a search request."""
    return build_search_cache_identity(
        provider_name=provider_name,
        query=query,
        options=options,
    ).to_cache_key()


__all__ = [
    "InFlightSearchRegistry",
    "SearchCacheEntry",
    "SearchCacheIdentity",
    "SearchCacheStore",
    "build_search_cache_identity",
    "build_search_cache_key",
    "build_search_cache_signature",
    "deserialize_search_result",
    "serialize_search_result",
]
