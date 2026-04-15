"""SQLite-backed brief persistence with safe concurrent access.

This module provides a thread-safe SQLite store that mirrors the BriefStore
interface while supporting concurrent reads and writes safely.

Migration from YAML
=================
The YAML store (BriefStore) remains fully functional. To migrate to SQLite:

1. Ensure the content-gen DB directory exists (same directory as briefs.yaml):
   ~/.config/cc-deep-research/content-gen/

2. SQLite data is stored at:
   ~/.config/cc-deep-research/content-gen/briefs.db

3. On first load, the SQLite store will attempt to import existing YAML data
   if the SQLite database is empty. This is a one-time migration.

4. Rollback: Simply use BriefStore instead of SqliteBriefStore.
   The YAML file is never modified by the SQLite store and remains intact.

Concurrency Model
================
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

from cc_deep_research.content_gen.models import ManagedBriefOutput, ManagedOpportunityBrief

if TYPE_CHECKING:
    from cc_deep_research.config import Config

# JSON encoder for list/dict fields stored in SQLite TEXT columns
_json_encoded = json.dumps
_json_decoded = json.loads


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


class SqliteBriefStore:
    """SQLite-backed brief store with thread-safe concurrent access.

    Implements the same load/save/update_brief interface as BriefStore
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
                config_attr="brief_path",
                default_name="briefs.yaml",
            )
            db_path = resolve_content_gen_file_path(
                explicit_path=None,
                config=config,
                config_attr="brief_path",
                default_name="briefs.db",
                use_config_parent=True,
            )
        else:
            db_path = path
            yaml_path = yaml_store_path
            if yaml_path is None:
                yaml_path = resolve_content_gen_file_path(
                    explicit_path=None,
                    config=config,
                    config_attr="brief_path",
                    default_name="briefs.yaml",
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
    # Public interface (matches BriefStore)
    # -------------------------------------------------------------------------

    def load(self) -> ManagedBriefOutput:
        """Load all managed briefs from SQLite.

        If the database is empty and a YAML file exists at the legacy path,
        performs a one-time import from YAML.
        """
        with self._lock:
            self._ensure_initialized()
            conn = self._get_conn()
            cursor = conn.execute("SELECT brief_id, data FROM briefs ORDER BY created_at ASC")
            rows = cursor.fetchall()
            if not rows:
                # Try one-time YAML import
                imported = self._import_from_yaml()
                if imported is not None:
                    return imported
                return ManagedBriefOutput()

            briefs: list[ManagedOpportunityBrief] = []
            for row in rows:
                data = _json_decoded(row[1])
                briefs.append(ManagedOpportunityBrief.model_validate(data))
            return ManagedBriefOutput(briefs=briefs)

    def save(self, output: ManagedBriefOutput) -> None:
        """Persist the full brief output to SQLite (replaces all rows)."""
        with self._lock:
            self._ensure_initialized()
            conn = self._get_conn()
            # Replace all rows transactionally
            existing_ids = {
                r[0] for r in conn.execute("SELECT brief_id FROM briefs").fetchall()
            }
            new_ids = {brief.brief_id for brief in output.briefs}

            to_delete = existing_ids - new_ids
            if to_delete:
                placeholders = ",".join("?" * len(to_delete))
                conn.execute(
                    f"DELETE FROM briefs WHERE brief_id IN ({placeholders})", tuple(to_delete)
                )

            for brief in output.briefs:
                data = brief.model_dump(exclude_none=True)
                json_data = _json_encoded(data)
                if brief.brief_id in existing_ids:
                    conn.execute(
                        "UPDATE briefs SET data = ?, updated_at = ? WHERE brief_id = ?",
                        (json_data, _now_iso(), brief.brief_id),
                    )
                else:
                    conn.execute(
                        "INSERT INTO briefs (brief_id, data, created_at, updated_at) VALUES (?, ?, ?, ?)",
                        (brief.brief_id, json_data, brief.created_at or _now_iso(), _now_iso()),
                    )
            conn.commit()

    def update_brief(self, brief_id: str, patch: dict) -> ManagedOpportunityBrief | None:
        """Update a single brief and return the updated brief or None."""
        with self._lock:
            self._ensure_initialized()
            conn = self._get_conn()
            cursor = conn.execute("SELECT data FROM briefs WHERE brief_id = ?", (brief_id,))
            row = cursor.fetchone()
            if row is None:
                return None

            merged = _json_decoded(row[0])
            unsupported_fields = sorted(set(patch) - set(ManagedOpportunityBrief.model_fields))
            if unsupported_fields:
                raise ValueError("Unsupported brief fields: " + ", ".join(unsupported_fields))
            merged.update(patch)
            updated = ManagedOpportunityBrief.model_validate(merged)
            json_data = _json_encoded(updated.model_dump(exclude_none=True))
            conn.execute(
                "UPDATE briefs SET data = ?, updated_at = ? WHERE brief_id = ?",
                (json_data, _now_iso(), brief_id),
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
            CREATE TABLE IF NOT EXISTS briefs (
                brief_id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_briefs_updated ON briefs(updated_at)")
        conn.commit()
        self._initialized = True

    def _import_from_yaml(self) -> ManagedBriefOutput | None:
        """One-time import from YAML if YAML file exists and SQLite is empty.

        Validates each brief record during import. Malformed records are skipped
        with a warning rather than crashing the entire import.
        """
        import logging

        logger = logging.getLogger(__name__)

        yaml_path = self._yaml_path
        if yaml_path is None:
            from cc_deep_research.content_gen.storage._paths import (
                resolve_content_gen_file_path,
            )

            yaml_path = resolve_content_gen_file_path(
                explicit_path=None,
                config=None,
                config_attr="brief_path",
                default_name="briefs.yaml",
            )

        if not yaml_path.exists():
            return None

        # Load and validate YAML structure
        raw_data: dict | list | None = None
        try:
            raw_data = yaml.safe_load(yaml_path.read_text())
        except yaml.YAMLError as exc:
            logger.error("Failed to parse YAML brief file %s: %s", yaml_path, exc)
            return None

        if raw_data is None:
            return None

        # Handle both dict with 'briefs' key and raw list
        if isinstance(raw_data, list):
            data = {"briefs": raw_data}
        elif isinstance(raw_data, dict):
            data = raw_data
        else:
            logger.error("Unexpected YAML structure in %s: expected dict or list, got %s", yaml_path, type(raw_data).__name__)
            return None

        # Validate the output structure
        try:
            output = ManagedBriefOutput.model_validate(data)
        except Exception as exc:
            logger.error("Failed to validate brief data from %s: %s", yaml_path, exc)
            return None

        if not output.briefs:
            return None

        # Persist to SQLite with validation per-record
        conn = self._get_conn()
        imported_count = 0
        skipped_count = 0
        valid_briefs: list[ManagedOpportunityBrief] = []

        for brief in output.briefs:
            # Validate brief has required fields
            if not brief.brief_id:
                logger.warning("Skipping brief with empty brief_id during YAML import")
                skipped_count += 1
                continue

            try:
                json_data = _json_encoded(brief.model_dump(exclude_none=True))
                conn.execute(
                    "INSERT OR IGNORE INTO briefs (brief_id, data, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (brief.brief_id, json_data, brief.created_at or _now_iso(), _now_iso()),
                )
                imported_count += 1
                valid_briefs.append(brief)
            except Exception as exc:
                logger.warning("Failed to import brief %s from YAML: %s", brief.brief_id, exc)
                skipped_count += 1

        conn.commit()

        if skipped_count > 0:
            logger.warning("YAML import: %d briefs imported, %d skipped", imported_count, skipped_count)

        # Return output containing only the briefs that were actually imported
        return ManagedBriefOutput(briefs=valid_briefs)
