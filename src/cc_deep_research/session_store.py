"""Session storage and management for CC Deep Research.

This module provides functionality to persist, retrieve, and manage
research sessions on disk.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cc_deep_research.config import get_default_config_path
from cc_deep_research.models.search import ResearchDepth, SearchResult, SearchResultItem
from cc_deep_research.models.session import (
    ResearchSession,
    normalize_session_metadata,
)

SESSION_SUMMARY_DIRNAME = ".summaries"
SESSION_LABEL_MAX_LENGTH = 120


class SessionArchiveStatus:
    """Archive status constants for saved sessions."""

    ACTIVE = "active"
    ARCHIVED = "archived"


def _get_audit_log_path() -> Path:
    """Get the path to the session audit log."""
    config_dir = get_default_config_path().parent
    audit_dir = config_dir / "sessions"
    audit_dir.mkdir(parents=True, exist_ok=True)
    return audit_dir / "audit.jsonl"


def log_audit_event(action: str, session_id: str, **details: Any) -> None:
    """Log an audit event for a session operation.

    Args:
        action: The action performed (e.g., 'archive', 'restore', 'delete').
        session_id: The session ID the action was performed on.
        **details: Additional details about the action.
    """
    try:
        audit_path = _get_audit_log_path()
        import json as json_module

        event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "action": action,
            "session_id": session_id,
            "details": details,
        }
        with open(audit_path, "a", encoding="utf-8") as f:
            f.write(json_module.dumps(event) + "\n")
    except Exception:
        pass


def get_default_session_dir() -> Path:
    """Get the default directory for session storage.

    Returns:
        Path to the session storage directory.
    """
    config_dir = get_default_config_path().parent
    return config_dir / "sessions"


@dataclass
class SessionDeletionResult:
    """Result of a session deletion operation.

    Attributes:
        deleted: True if the session file was successfully deleted.
        missing: True if the session file did not exist.
        error: Error message if deletion failed, None otherwise.
    """

    deleted: bool = False
    missing: bool = False
    error: str | None = None

    def __bool__(self) -> bool:
        """Return True for backward compatibility with boolean checks."""
        return self.deleted

    @property
    def success(self) -> bool:
        """Return True if deletion was successful or file was already missing."""
        return self.deleted or self.missing


class SessionStore:
    """Manages persistent storage of research sessions.

    This class provides:
    - Session persistence to JSON files
    - Session retrieval by ID
    - Session listing with metadata
    - Session deletion

    Sessions are stored as JSON files in a dedicated directory,
    with filenames based on session IDs.
    """

    def __init__(self, session_dir: Path | None = None) -> None:
        """Initialize the session store.

        Args:
            session_dir: Optional directory for session storage.
                        Uses default if not provided.
        """
        self._session_dir = Path(session_dir) if session_dir else get_default_session_dir()
        self._summary_dir = self._session_dir / SESSION_SUMMARY_DIRNAME
        self._ensure_session_dir()

    def _ensure_session_dir(self) -> None:
        """Ensure the session directory exists."""
        self._session_dir.mkdir(parents=True, exist_ok=True)
        self._summary_dir.mkdir(parents=True, exist_ok=True)

    def _session_path(self, session_id: str) -> Path:
        """Get the file path for a session.

        Args:
            session_id: Session identifier.

        Returns:
            Path to the session file.
        """
        safe_id = _safe_session_id(session_id)
        return self._session_dir / f"{safe_id}.json"

    def _session_summary_path(self, session_id: str) -> Path:
        """Return the lightweight summary path for a saved session."""
        safe_id = _safe_session_id(session_id)
        return self._summary_dir / f"{safe_id}.json"

    def get_session_path(self, session_id: str) -> Path:
        """Get the file path for a session (public accessor).

        Args:
            session_id: Session identifier.

        Returns:
            Path to the session file.
        """
        return self._session_path(session_id)

    def save_session(self, session: ResearchSession) -> Path:
        """Save a research session to disk.

        Args:
            session: Research session to save.

        Returns:
            Path to the saved session file.
        """
        path = self._session_path(session.session_id)
        data = _serialize_session(session)
        summary_path = self._session_summary_path(session.session_id)
        summary = _build_saved_session_summary(data, session_path=path)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=_json_serializer)

        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, default=_json_serializer)

        return path

    def load_session(self, session_id: str) -> ResearchSession | None:
        """Load a research session from disk.

        Args:
            session_id: Session identifier.

        Returns:
            ResearchSession if found, None otherwise.
        """
        path = self._session_path(session_id)

        if not path.exists():
            return None

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        return _deserialize_session(data)

    def list_sessions(
        self,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List all saved sessions with metadata.

        Args:
            limit: Maximum number of sessions to return.
            offset: Number of sessions to skip.

        Returns:
            List of session metadata dictionaries including saved-session
            metadata (query, depth, completed_at) and artifact state
            (has_session_payload, has_report).
        """
        sessions = []

        for path in sorted(
            self._session_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            summary = self._load_saved_session_summary(path)
            if summary is None:
                continue
            sessions.append(summary)

        if offset:
            sessions = sessions[offset:]

        if limit is not None:
            sessions = sessions[:limit]

        return sessions

    def _load_saved_session_summary(self, session_path: Path) -> dict[str, Any] | None:
        """Return the lightweight session summary for a saved payload."""
        summary_path = self._session_summary_path(session_path.stem)
        if summary_path.exists():
            try:
                with open(summary_path, encoding="utf-8") as f:
                    data = json.load(f)
                return _normalize_saved_session_summary(data, session_path=session_path)
            except (json.JSONDecodeError, KeyError, TypeError):
                pass

        try:
            with open(session_path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, KeyError):
            return None

        summary = _build_saved_session_summary(data, session_path=session_path)
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, default=_json_serializer)
        return summary

    def delete_session(self, session_id: str) -> SessionDeletionResult:
        """Delete a research session from disk.

        Args:
            session_id: Session identifier.

        Returns:
            SessionDeletionResult with deleted, missing, and error fields.
        """
        path = self._session_path(session_id)
        summary_path = self._session_summary_path(session_id)

        if not path.exists() and not summary_path.exists():
            return SessionDeletionResult(deleted=False, missing=True)

        try:
            deleted = False
            deleted_files = []
            if path.exists():
                path.unlink()
                deleted = True
                deleted_files.append("session")
            if summary_path.exists():
                summary_path.unlink()
                deleted = True
                deleted_files.append("summary")

            log_audit_event("delete", session_id, deleted_files=deleted_files)
            return SessionDeletionResult(deleted=deleted, missing=False)
        except OSError as e:
            return SessionDeletionResult(deleted=False, missing=False, error=str(e))

    def session_exists(self, session_id: str) -> bool:
        """Check if a session exists.

        Args:
            session_id: Session identifier.

        Returns:
            True if session exists, False otherwise.
        """
        return self._session_path(session_id).exists()

    def get_session_count(self) -> int:
        """Get the total number of saved sessions.

        Returns:
            Number of sessions in storage.
        """
        return len(list(self._session_dir.glob("*.json")))

    def get_archived_session_ids(self) -> set[str]:
        """Get the set of archived session IDs.

        Returns:
            Set of archived session IDs.
        """
        archived: set[str] = set()
        for path in self._summary_dir.glob("*.json"):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("archived"):
                    archived.add(path.stem)
            except (json.JSONDecodeError, OSError):
                continue
        return archived

    def archive_session(self, session_id: str) -> bool:
        """Archive a session, hiding it from the default list.

        Args:
            session_id: Session identifier.

        Returns:
            True if the session was archived, False if not found.
        """
        summary_path = self._session_summary_path(session_id)
        if not summary_path.exists():
            return False

        try:
            with open(summary_path, encoding="utf-8") as f:
                data = json.load(f)

            data["archived"] = True
            archived_at = datetime.now(UTC)
            data["archived_at"] = archived_at.isoformat()

            with open(summary_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=_json_serializer)

            log_audit_event("archive", session_id, archived_at=archived_at.isoformat())
            return True
        except (json.JSONDecodeError, OSError):
            return False

    def restore_session(self, session_id: str) -> bool:
        """Restore an archived session to the active list.

        Args:
            session_id: Session identifier.

        Returns:
            True if the session was restored, False if not found.
        """
        summary_path = self._session_summary_path(session_id)
        if not summary_path.exists():
            return False

        try:
            with open(summary_path, encoding="utf-8") as f:
                data = json.load(f)

            if not data.get("archived"):
                return False

            data["archived"] = False
            data["archived_at"] = None
            restored_at = datetime.now(UTC)
            data["restored_at"] = restored_at.isoformat()

            with open(summary_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=_json_serializer)

            log_audit_event("restore", session_id, restored_at=restored_at.isoformat())
            return True
        except (json.JSONDecodeError, OSError):
            return False

    def is_session_archived(self, session_id: str) -> bool:
        """Check if a session is archived.

        Args:
            session_id: Session identifier.

        Returns:
            True if the session is archived, False otherwise.
        """
        summary_path = self._session_summary_path(session_id)
        if not summary_path.exists():
            return False

        try:
            with open(summary_path, encoding="utf-8") as f:
                data = json.load(f)
            return bool(data.get("archived"))
        except (json.JSONDecodeError, OSError):
            return False


def _serialize_session(session: ResearchSession) -> dict[str, Any]:
    """Serialize a ResearchSession to a dictionary.

    Args:
        session: Research session to serialize.

    Returns:
        Dictionary representation of the session.
    """
    metadata = normalize_session_metadata(
        session.metadata,
        depth=session.depth,
    )
    return {
        "session_id": session.session_id,
        "query": session.query,
        "depth": session.depth.value,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "completed_at": (session.completed_at.isoformat() if session.completed_at else None),
        "searches": [_serialize_search_result(s) for s in session.searches],
        "sources": [_serialize_source(s) for s in session.sources],
        "metadata": metadata,
    }


def _serialize_search_result(result: SearchResult) -> dict[str, Any]:
    """Serialize a SearchResult to a dictionary."""
    return {
        "query": result.query,
        "results": [_serialize_source(s) for s in result.results],
        "provider": result.provider,
        "metadata": result.metadata,
        "timestamp": result.timestamp.isoformat() if result.timestamp else None,
        "execution_time_ms": result.execution_time_ms,
    }


def _safe_session_id(session_id: str) -> str:
    """Sanitize a session identifier for filesystem-safe filenames."""
    return session_id.replace("/", "_").replace("\\", "_")


def _normalize_optional_text(value: Any) -> str | None:
    """Normalize string-like values while keeping missing fields explicit."""
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split()).strip()
    return normalized or None


def _normalize_depth(value: Any) -> str | None:
    """Normalize depth values into their serialized string form."""
    if isinstance(value, ResearchDepth):
        return value.value
    return _normalize_optional_text(value)


def _build_session_label(query: str | None, *, session_id: str) -> str:
    """Create a compact operator-facing label for session list rows."""
    if query:
        if len(query) <= SESSION_LABEL_MAX_LENGTH:
            return query
        return f"{query[: SESSION_LABEL_MAX_LENGTH - 1].rstrip()}…"
    return f"Session {session_id[:8]}"


def _build_saved_session_summary(
    data: dict[str, Any],
    *,
    session_path: Path,
) -> dict[str, Any]:
    """Extract list-view metadata from a full saved-session payload."""
    session_id = _normalize_optional_text(data.get("session_id")) or session_path.stem
    query = _normalize_optional_text(data.get("query"))
    metadata = data.get("metadata", {})
    sources = data.get("sources", [])
    return {
        "session_id": session_id,
        "label": _build_session_label(query, session_id=session_id),
        "query": query,
        "depth": _normalize_depth(data.get("depth")),
        "started_at": _normalize_optional_text(data.get("started_at")),
        "completed_at": _normalize_optional_text(data.get("completed_at")),
        "total_sources": len(sources) if isinstance(sources, list) else 0,
        "path": str(session_path),
        "has_session_payload": True,
        "has_report": isinstance(metadata, dict) and bool(metadata.get("analysis")),
        "archived": False,
        "archived_at": None,
    }


def _normalize_saved_session_summary(
    data: dict[str, Any],
    *,
    session_path: Path,
) -> dict[str, Any]:
    """Normalize a saved-session sidecar into the public list shape."""
    session_id = _normalize_optional_text(data.get("session_id")) or session_path.stem
    query = _normalize_optional_text(data.get("query"))
    total_sources = data.get("total_sources")
    return {
        "session_id": session_id,
        "label": _normalize_optional_text(data.get("label"))
        or _build_session_label(query, session_id=session_id),
        "query": query,
        "depth": _normalize_depth(data.get("depth")),
        "started_at": _normalize_optional_text(data.get("started_at")),
        "completed_at": _normalize_optional_text(data.get("completed_at")),
        "total_sources": total_sources if isinstance(total_sources, int) else 0,
        "path": str(session_path),
        "has_session_payload": session_path.exists(),
        "has_report": bool(data.get("has_report")),
        "archived": bool(data.get("archived")),
        "archived_at": _normalize_optional_text(data.get("archived_at")),
    }


def _serialize_source(source: SearchResultItem) -> dict[str, Any]:
    """Serialize a SearchResultItem to a dictionary."""
    return {
        "url": source.url,
        "title": source.title,
        "snippet": source.snippet,
        "content": source.content,
        "score": source.score,
        "source_metadata": source.source_metadata,
        "query_provenance": [entry.model_dump(mode="python") for entry in source.query_provenance],
    }


def _deserialize_session(data: dict[str, Any]) -> ResearchSession:
    """Deserialize a dictionary to a ResearchSession.

    Args:
        data: Dictionary representation of a session.

    Returns:
        ResearchSession object.
    """
    depth = ResearchDepth(data.get("depth", "deep"))
    metadata = normalize_session_metadata(
        data.get("metadata", {}),
        depth=depth,
    )

    return ResearchSession(
        session_id=data["session_id"],
        query=data["query"],
        depth=depth,
        started_at=(
            datetime.fromisoformat(data["started_at"])
            if data.get("started_at")
            else datetime.utcnow()
        ),
        completed_at=(
            datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None
        ),
        searches=[_deserialize_search_result(s) for s in data.get("searches", [])],
        sources=[_deserialize_source(s) for s in data.get("sources", [])],
        metadata=metadata,
    )


def _deserialize_search_result(data: dict[str, Any]) -> SearchResult:
    """Deserialize a dictionary to a SearchResult."""
    return SearchResult(
        query=data["query"],
        results=[_deserialize_source(s) for s in data.get("results", [])],
        provider=data["provider"],
        metadata=data.get("metadata", {}),
        timestamp=(datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else None),
        execution_time_ms=data.get("execution_time_ms", 0),
    )


def _deserialize_source(data: dict[str, Any]) -> SearchResultItem:
    """Deserialize a dictionary to a SearchResultItem."""
    return SearchResultItem(
        url=data["url"],
        title=data.get("title", ""),
        snippet=data.get("snippet", ""),
        content=data.get("content"),
        score=data.get("score", 0.0),
        source_metadata=data.get("source_metadata", {}),
        query_provenance=data.get("query_provenance", []),
    )


def _json_serializer(obj: Any) -> Any:
    """Custom JSON serializer for non-standard types.

    Args:
        obj: Object to serialize.

    Returns:
        Serializable representation of the object.
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


__all__ = [
    "SessionArchiveStatus",
    "SessionDeletionResult",
    "SessionStore",
    "get_default_session_dir",
]
