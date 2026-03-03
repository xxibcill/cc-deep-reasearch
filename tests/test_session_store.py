"""Tests for session storage functionality."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from cc_deep_research.models import (
    ResearchDepth,
    ResearchSession,
    SearchResult,
    SearchResultItem,
)
from cc_deep_research.session_store import (
    SessionStore,
    _deserialize_session,
    _serialize_session,
    get_default_session_dir,
)


@pytest.fixture
def temp_session_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for session storage."""
    session_dir = tmp_path / "sessions"
    session_dir.mkdir()
    return session_dir


@pytest.fixture
def session_store(temp_session_dir: Path) -> SessionStore:
    """Create a SessionStore with a temporary directory."""
    return SessionStore(session_dir=temp_session_dir)


@pytest.fixture
def sample_session() -> ResearchSession:
    """Create a sample ResearchSession for testing."""
    return ResearchSession(
        session_id="test-session-123",
        query="What is machine learning?",
        depth=ResearchDepth.DEEP,
        started_at=datetime(2024, 1, 15, 10, 30, 0),
        completed_at=datetime(2024, 1, 15, 10, 35, 0),
        sources=[
            SearchResultItem(
                url="https://example.com/ml",
                title="Introduction to Machine Learning",
                snippet="Machine learning is a subset of AI...",
                score=0.95,
            ),
        ],
        metadata={
            "analysis": {
                "key_findings": ["ML is popular", "Neural networks are powerful"],
                "themes": ["AI", "Data Science"],
                "gaps": ["Ethical considerations"],
            },
            "validation": {
                "quality_score": 0.85,
            },
        },
    )


@pytest.fixture
def sample_search_result() -> SearchResult:
    """Create a sample SearchResult for testing."""
    return SearchResult(
        query="machine learning",
        results=[
            SearchResultItem(
                url="https://example.com/ml",
                title="Introduction to Machine Learning",
                snippet="Machine learning is a subset of AI...",
                score=0.95,
            ),
        ],
        provider="tavily",
        execution_time_ms=150,
    )


class TestGetDefaultSessionDir:
    """Tests for get_default_session_dir function."""

    def test_returns_path(self) -> None:
        """Test that it returns a Path object."""
        result = get_default_session_dir()
        assert isinstance(result, Path)

    def test_includes_sessions(self) -> None:
        """Test that the path includes 'sessions'."""
        result = get_default_session_dir()
        assert "sessions" in str(result)


class TestSessionStore:
    """Tests for SessionStore class."""

    def test_init_creates_directory(self, temp_session_dir: Path) -> None:
        """Test that initialization creates the session directory."""
        new_dir = temp_session_dir / "new_sessions"
        assert not new_dir.exists()

        SessionStore(session_dir=new_dir)
        assert new_dir.exists()

    def test_save_session(self, session_store: SessionStore, sample_session: ResearchSession) -> None:
        """Test saving a session to disk."""
        path = session_store.save_session(sample_session)

        assert path.exists()
        assert sample_session.session_id in path.name

        # Verify content
        with open(path) as f:
            data = json.load(f)

        assert data["session_id"] == sample_session.session_id
        assert data["query"] == sample_session.query

    def test_load_session(self, session_store: SessionStore, sample_session: ResearchSession) -> None:
        """Test loading a session from disk."""
        # Save first
        session_store.save_session(sample_session)

        # Load
        loaded = session_store.load_session(sample_session.session_id)

        assert loaded is not None
        assert loaded.session_id == sample_session.session_id
        assert loaded.query == sample_session.query
        assert loaded.depth == sample_session.depth
        assert len(loaded.sources) == len(sample_session.sources)

    def test_load_session_not_found(self, session_store: SessionStore) -> None:
        """Test loading a non-existent session."""
        result = session_store.load_session("nonexistent")
        assert result is None

    def test_list_sessions_empty(self, session_store: SessionStore) -> None:
        """Test listing sessions when none exist."""
        sessions = session_store.list_sessions()
        assert sessions == []

    def test_list_sessions(self, session_store: SessionStore, sample_session: ResearchSession) -> None:
        """Test listing sessions."""
        # Save multiple sessions
        session_store.save_session(sample_session)

        session2 = ResearchSession(
            session_id="test-session-456",
            query="Another query",
            depth=ResearchDepth.QUICK,
        )
        session_store.save_session(session2)

        sessions = session_store.list_sessions()

        assert len(sessions) == 2
        assert any(s["session_id"] == sample_session.session_id for s in sessions)
        assert any(s["session_id"] == "test-session-456" for s in sessions)

    def test_list_sessions_with_limit(self, session_store: SessionStore) -> None:
        """Test listing sessions with limit."""
        # Create multiple sessions
        for i in range(5):
            session = ResearchSession(
                session_id=f"session-{i}",
                query=f"Query {i}",
                depth=ResearchDepth.STANDARD,
            )
            session_store.save_session(session)

        sessions = session_store.list_sessions(limit=3)
        assert len(sessions) == 3

    def test_list_sessions_with_offset(self, session_store: SessionStore) -> None:
        """Test listing sessions with offset."""
        # Create multiple sessions
        for i in range(5):
            session = ResearchSession(
                session_id=f"session-{i}",
                query=f"Query {i}",
                depth=ResearchDepth.STANDARD,
            )
            session_store.save_session(session)

        sessions = session_store.list_sessions(offset=2)
        assert len(sessions) == 3

    def test_delete_session(self, session_store: SessionStore, sample_session: ResearchSession) -> None:
        """Test deleting a session."""
        session_store.save_session(sample_session)
        assert session_store.session_exists(sample_session.session_id)

        result = session_store.delete_session(sample_session.session_id)
        assert result is True
        assert not session_store.session_exists(sample_session.session_id)

    def test_delete_session_not_found(self, session_store: SessionStore) -> None:
        """Test deleting a non-existent session."""
        result = session_store.delete_session("nonexistent")
        assert result is False

    def test_session_exists(self, session_store: SessionStore, sample_session: ResearchSession) -> None:
        """Test checking if a session exists."""
        assert not session_store.session_exists(sample_session.session_id)

        session_store.save_session(sample_session)
        assert session_store.session_exists(sample_session.session_id)

    def test_get_session_count(self, session_store: SessionStore) -> None:
        """Test getting session count."""
        assert session_store.get_session_count() == 0

        for i in range(3):
            session = ResearchSession(
                session_id=f"session-{i}",
                query=f"Query {i}",
                depth=ResearchDepth.QUICK,
            )
            session_store.save_session(session)

        assert session_store.get_session_count() == 3


class TestSessionSerialization:
    """Tests for session serialization/deserialization."""

    def test_serialize_session(self, sample_session: ResearchSession) -> None:
        """Test serializing a session to dict."""
        data = _serialize_session(sample_session)

        assert data["session_id"] == sample_session.session_id
        assert data["query"] == sample_session.query
        assert data["depth"] == "deep"
        assert "started_at" in data
        assert "sources" in data
        assert len(data["sources"]) == 1

    def test_deserialize_session(self, sample_session: ResearchSession) -> None:
        """Test deserializing a dict to session."""
        data = _serialize_session(sample_session)
        session = _deserialize_session(data)

        assert session.session_id == sample_session.session_id
        assert session.query == sample_session.query
        assert session.depth == sample_session.depth
        assert len(session.sources) == len(sample_session.sources)

    def test_roundtrip_preserves_data(self, sample_session: ResearchSession) -> None:
        """Test that serialize/deserialize preserves all data."""
        data = _serialize_session(sample_session)
        restored = _deserialize_session(data)

        assert restored.session_id == sample_session.session_id
        assert restored.query == sample_session.query
        assert restored.depth == sample_session.depth
        assert restored.started_at == sample_session.started_at
        assert restored.completed_at == sample_session.completed_at
        assert len(restored.sources) == len(sample_session.sources)
        assert restored.metadata == sample_session.metadata

    def test_serialize_with_searches(
        self,
        sample_session: ResearchSession,
        sample_search_result: SearchResult,
    ) -> None:
        """Test serializing a session with search results."""
        sample_session.searches = [sample_search_result]

        data = _serialize_session(sample_session)
        assert len(data["searches"]) == 1
        assert data["searches"][0]["query"] == sample_search_result.query

    def test_deserialize_with_minimal_data(self) -> None:
        """Test deserializing with minimal required data."""
        data = {
            "session_id": "minimal",
            "query": "Test query",
        }

        session = _deserialize_session(data)

        assert session.session_id == "minimal"
        assert session.query == "Test query"
        assert session.depth == ResearchDepth.DEEP  # default
        assert session.sources == []
        assert session.searches == []

    def test_session_path_sanitization(self, session_store: SessionStore) -> None:
        """Test that session IDs with path separators are sanitized."""
        # Session ID with path traversal attempt
        malicious_id = "../../../etc/passwd"
        path = session_store._session_path(malicious_id)

        # Path should still be within the session directory
        # The sanitization replaces / and \ with _, preventing path traversal
        assert path.parent == session_store._session_dir
        # Verify no directory separators in the filename
        assert "/" not in path.name
        assert "\\" not in path.name


class TestSessionStoreEdgeCases:
    """Edge case tests for SessionStore."""

    def test_handle_corrupted_json(self, session_store: SessionStore) -> None:
        """Test handling of corrupted JSON files."""
        # Create a corrupted file
        corrupted_path = session_store._session_dir / "corrupted.json"
        corrupted_path.write_text("{ invalid json }")

        # List sessions should skip corrupted files
        sessions = session_store.list_sessions()
        assert sessions == []

    def test_handle_missing_required_fields(self, session_store: SessionStore) -> None:
        """Test handling of files with missing required fields."""
        # Create a file with missing required fields
        incomplete_path = session_store._session_dir / "incomplete.json"
        incomplete_path.write_text('{"depth": "deep"}')

        # List sessions should handle gracefully
        sessions = session_store.list_sessions()
        # Should still return something, with defaults for missing fields
        assert isinstance(sessions, list)

    def test_empty_session_dir(self, temp_session_dir: Path) -> None:
        """Test operations on an empty session directory."""
        store = SessionStore(session_dir=temp_session_dir)

        assert store.get_session_count() == 0
        assert store.list_sessions() == []
        assert store.load_session("any") is None
