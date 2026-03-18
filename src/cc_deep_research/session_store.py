"""Session storage and management for CC Deep Research.

This module provides functionality to persist, retrieve, and manage
research sessions on disk.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from cc_deep_research.config import get_default_config_path
from cc_deep_research.models.search import ResearchDepth, SearchResult, SearchResultItem
from cc_deep_research.models.session import (
    ResearchSession,
    normalize_session_metadata,
)


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
        self._ensure_session_dir()

    def _ensure_session_dir(self) -> None:
        """Ensure the session directory exists."""
        self._session_dir.mkdir(parents=True, exist_ok=True)

    def _session_path(self, session_id: str) -> Path:
        """Get the file path for a session.

        Args:
            session_id: Session identifier.

        Returns:
            Path to the session file.
        """
        safe_id = session_id.replace("/", "_").replace("\\", "_")
        return self._session_dir / f"{safe_id}.json"

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

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=_json_serializer)

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
            List of session metadata dictionaries.
        """
        sessions = []

        for path in sorted(
            self._session_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)

                sessions.append(
                    {
                        "session_id": data.get("session_id", path.stem),
                        "query": data.get("query", "Unknown"),
                        "depth": data.get("depth", "deep"),
                        "started_at": data.get("started_at"),
                        "completed_at": data.get("completed_at"),
                        "total_sources": len(data.get("sources", [])),
                        "path": str(path),
                    }
                )
            except (json.JSONDecodeError, KeyError):
                continue

        if offset:
            sessions = sessions[offset:]

        if limit is not None:
            sessions = sessions[:limit]

        return sessions

    def delete_session(self, session_id: str) -> SessionDeletionResult:
        """Delete a research session from disk.

        Args:
            session_id: Session identifier.

        Returns:
            SessionDeletionResult with deleted, missing, and error fields.
        """
        path = self._session_path(session_id)

        if not path.exists():
            return SessionDeletionResult(deleted=False, missing=True)

        try:
            path.unlink()
            return SessionDeletionResult(deleted=True, missing=False)
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
    "SessionDeletionResult",
    "SessionStore",
    "get_default_session_dir",
]
