"""SQLite-backed backlog persistence with safe concurrent access.

This module provides a thread-safe SQLite store that mirrors the BacklogStore
interface while supporting concurrent reads and writes safely. It is used as
the default store when the application is configured for multi-session or
AI-assisted usage.

Migration from YAML
===================
The YAML store (BacklogStore) remains fully functional. To migrate to SQLite:

1. Ensure the content-gen DB directory exists (same directory as backlog.yaml):
   ~/.config/cc-deep-research/content-gen/

2. SQLite data is stored at:
   ~/.config/cc-deep-research/content-gen/backlog.db

3. On first load, the SQLite store will attempt to import existing YAML data
   if the SQLite database is empty. This is a one-time migration.

4. Rollback: Simply use BacklogStore instead of SqliteBacklogStore.
   The YAML file is never modified by the SQLite store and remains intact.

Concurrency Model
=================
- All public operations acquire an exclusive threading lock.
- Multiple reader threads are supported via SQLite's WAL mode.
- The lock is a process-local reentrant lock; for multi-process access
  a database server (Postgres) would be required.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from cc_deep_research.content_gen.models import BacklogItem, BacklogOutput

if TYPE_CHECKING:
    from cc_deep_research.config import Config

# JSON encoder for list/dict fields stored in SQLite TEXT columns
_json_encoded = json.dumps
_json_decoded = json.loads


class SqliteBacklogStore:
    """SQLite-backed backlog store with thread-safe concurrent access.

    Implements the same load/save/update_item interface as BacklogStore
    but persists to a SQLite database instead of YAML.
    """

    def __init__(
        self,
        path: Path | None = None,
        *,
        config: Config | None = None,
        yaml_store_path: Path | None = None,
    ) -> None:
        from cc_deep_research.content_gen.storage._paths import resolve_content_gen_file_path

        if path is None:
            yaml_path = resolve_content_gen_file_path(
                explicit_path=yaml_store_path,
                config=config,
                config_attr="backlog_path",
                default_name="backlog.yaml",
            )
            db_path = resolve_content_gen_file_path(
                explicit_path=None,
                config=config,
                config_attr="backlog_path",
                default_name="backlog.db",
                use_config_parent=True,
            )
        else:
            db_path = path
            yaml_path = yaml_store_path
            if yaml_path is None:
                yaml_path = resolve_content_gen_file_path(
                    explicit_path=None,
                    config=config,
                    config_attr="backlog_path",
                    default_name="backlog.yaml",
                )

        self._db_path = db_path
        self._yaml_path = yaml_path
        self._initialized = False
        self._lock = threading.RLock()
        self._conn: sqlite3.Connection | None = None
        # Ensure parent directory exists before SQLite tries to create the database file
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._db_path

    # -------------------------------------------------------------------------
    # Public interface (matches BacklogStore)
    # -------------------------------------------------------------------------

    def load(self) -> BacklogOutput:
        """Load all backlog items from SQLite.

        If the database is empty and a YAML file exists at the legacy path,
        performs a one-time import from YAML.
        """
        with self._lock:
            self._ensure_initialized()
            conn = self._get_conn()
            cursor = conn.execute("SELECT idea_id, data FROM backlog_items ORDER BY created_at ASC")
            rows = cursor.fetchall()
            if not rows:
                # Try one-time YAML import
                imported = self._import_from_yaml()
                if imported is not None:
                    return imported
                return BacklogOutput()

            items: list[BacklogItem] = []
            for row in rows:
                data = _json_decoded(row[1])
                items.append(BacklogItem.model_validate(data))
            return BacklogOutput(items=items)

    def save(self, backlog: BacklogOutput) -> None:
        """Persist the full backlog to SQLite (replaces all rows)."""
        with self._lock:
            self._ensure_initialized()
            conn = self._get_conn()
            # Replace all rows transactionally
            existing_ids = {
                r[0] for r in conn.execute("SELECT idea_id FROM backlog_items").fetchall()
            }
            new_ids = {item.idea_id for item in backlog.items}

            to_delete = existing_ids - new_ids
            if to_delete:
                placeholders = ",".join("?" * len(to_delete))
                conn.execute(
                    f"DELETE FROM backlog_items WHERE idea_id IN ({placeholders})", tuple(to_delete)
                )

            for item in backlog.items:
                data = item.model_dump(exclude_none=True)
                json_data = _json_encoded(data)
                if item.idea_id in existing_ids:
                    conn.execute(
                        "UPDATE backlog_items SET data = ?, updated_at = ? WHERE idea_id = ?",
                        (json_data, _now_iso(), item.idea_id),
                    )
                else:
                    conn.execute(
                        "INSERT INTO backlog_items (idea_id, data, created_at, updated_at) VALUES (?, ?, ?, ?)",
                        (item.idea_id, json_data, item.created_at or _now_iso(), _now_iso()),
                    )
            conn.commit()

    def update_item(self, idea_id: str, patch: dict) -> BacklogItem | None:
        """Update a single item and return the updated item or None."""
        with self._lock:
            self._ensure_initialized()
            conn = self._get_conn()
            cursor = conn.execute("SELECT data FROM backlog_items WHERE idea_id = ?", (idea_id,))
            row = cursor.fetchone()
            if row is None:
                return None

            merged_item = _json_decoded(row[0])
            unsupported_fields = sorted(set(patch) - set(BacklogItem.model_fields))
            if unsupported_fields:
                raise ValueError("Unsupported backlog fields: " + ", ".join(unsupported_fields))
            merged_item.update(patch)
            updated = BacklogItem.model_validate(merged_item)
            json_data = _json_encoded(updated.model_dump(exclude_none=True))
            conn.execute(
                "UPDATE backlog_items SET data = ?, updated_at = ? WHERE idea_id = ?",
                (json_data, _now_iso(), idea_id),
            )
            conn.commit()
            return updated

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        """Return a cached connection (caller must hold lock)."""
        if self._conn is None:
            # WAL mode allows concurrent readers while one writer holds the lock
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
        return self._conn

    def _ensure_initialized(self) -> None:
        """Create schema if it doesn't exist (caller must hold lock)."""
        if self._initialized:
            return
        conn = self._get_conn()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS backlog_items (
                idea_id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_backlog_updated ON backlog_items(updated_at)")
        conn.commit()
        self._initialized = True

    def _import_from_yaml(self) -> BacklogOutput | None:
        """One-time import from YAML if YAML file exists and SQLite is empty."""
        yaml_path = self._yaml_path
        if yaml_path is None:
            from cc_deep_research.content_gen.storage._paths import (
                resolve_content_gen_file_path,
            )

            yaml_path = resolve_content_gen_file_path(
                explicit_path=None,
                config=None,
                config_attr="backlog_path",
                default_name="backlog.yaml",
            )

        if not yaml_path.exists():
            return None

        data = yaml.safe_load(yaml_path.read_text()) or {}
        backlog = BacklogOutput.model_validate(data)
        if not backlog.items:
            return None

        # Persist to SQLite
        conn = self._get_conn()
        for item in backlog.items:
            json_data = _json_encoded(item.model_dump(exclude_none=True))
            conn.execute(
                "INSERT OR IGNORE INTO backlog_items (idea_id, data, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (item.idea_id, json_data, item.created_at or _now_iso(), _now_iso()),
            )
        conn.commit()
        return backlog


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()
