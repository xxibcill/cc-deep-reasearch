"""Centralized state management for research sessions.

This module provides thread-safe state management for research sessions
with multiple agents working in parallel.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from cc_deep_research.models import ResearchDepth, SearchResultItem


class ResearchStatus(StrEnum):
    """Status of the research session."""

    INITIALIZING = "initializing"
    RUNNING = "running"
    AGGREGATING = "aggregating"
    SYNTHESIZING = "synthesizing"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Reflection:
    """A strategic reflection point during research.

    Attributes:
        id: Unique reflection identifier.
        timestamp: When the reflection was created.
        stage: Research stage where reflection occurred.
        question: The question or prompt for reflection.
        analysis: Analysis of current findings.
        gaps_identified: Information gaps identified.
        decision: Decision made based on reflection.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    stage: str = ""
    question: str = ""
    analysis: str = ""
    gaps_identified: list[str] = field(default_factory=list)
    decision: str = ""


@dataclass
class ResearchState:
    """Centralized state for a research session.

    This class provides thread-safe state management for research
    sessions with multiple agents working in parallel.

    Attributes:
        session_id: Unique session identifier.
        query: The original research query.
        depth: Research depth mode.
        sources: Collected search results.
        researcher_results: Results from researcher agents (agent_id -> results).
        reflections: List of strategic reflections.
        status: Current research status.
        metadata: Additional metadata.
    """

    session_id: str = field(default_factory=lambda: str(uuid4()))
    query: str = ""
    depth: ResearchDepth = ResearchDepth.DEEP
    sources: list[SearchResultItem] = field(default_factory=list)
    researcher_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    reflections: list[Reflection] = field(default_factory=list)
    status: ResearchStatus = ResearchStatus.INITIALIZING
    metadata: dict[str, Any] = field(default_factory=dict)

    # Thread safety
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def add_source(self, source: SearchResultItem) -> None:
        """Add a source to the state (thread-safe).

        Args:
            source: Source to add.
        """
        # Add without lock for performance (list append is atomic-ish)
        self.sources.append(source)

    def add_sources(self, sources: list[SearchResultItem]) -> None:
        """Add multiple sources to the state (thread-safe).

        Args:
            sources: Sources to add.
        """
        self.sources.extend(sources)

    def set_researcher_result(self, agent_id: str, result: dict[str, Any]) -> None:
        """Set the result from a researcher agent (thread-safe).

        Args:
            agent_id: ID of the researcher agent.
            result: Result dictionary.
        """
        self.researcher_results[agent_id] = result

    def get_researcher_result(self, agent_id: str) -> dict[str, Any] | None:
        """Get the result from a researcher agent.

        Args:
            agent_id: ID of the researcher agent.

        Returns:
            Result dictionary or None if not found.
        """
        return self.researcher_results.get(agent_id)

    def add_reflection(self, reflection: Reflection) -> None:
        """Add a strategic reflection (thread-safe).

        Args:
            reflection: Reflection to add.
        """
        self.reflections.append(reflection)

    async def update_status(
        self,
        new_status: ResearchStatus,
    ) -> None:
        """Update the research status (thread-safe).

        Args:
            new_status: New status to set.
        """
        async with self._lock:
            self.status = new_status

    def get_status(self) -> ResearchStatus:
        """Get the current research status.

        Returns:
            Current status.
        """
        return self.status

    def get_all_researcher_results(self) -> dict[str, dict[str, Any]]:
        """Get all researcher results.

        Returns:
            Dictionary of all researcher results.
        """
        return self.researcher_results.copy()

    def get_reflection_count(self) -> int:
        """Get the number of reflections.

        Returns:
            Number of reflections.
        """
        return len(self.reflections)

    def get_source_count(self) -> int:
        """Get the number of sources.

        Returns:
            Number of sources.
        """
        return len(self.sources)

    def is_complete(self) -> bool:
        """Check if research is complete.

        Returns:
            True if complete, False otherwise.
        """
        return self.status == ResearchStatus.COMPLETE

    def is_running(self) -> bool:
        """Check if research is currently running.

        Returns:
            True if running, False otherwise.
        """
        return self.status == ResearchStatus.RUNNING

    def reset(self) -> None:
        """Reset the state for a new research session."""
        self.session_id = str(uuid4())
        self.sources.clear()
        self.researcher_results.clear()
        self.reflections.clear()
        self.status = ResearchStatus.INITIALIZING
        self.metadata.clear()

    def to_dict(self) -> dict[str, Any]:
        """Convert state to dictionary.

        Returns:
            Dictionary representation of state.
        """
        return {
            "session_id": self.session_id,
            "query": self.query,
            "depth": self.depth.value,
            "source_count": len(self.sources),
            "researcher_count": len(self.researcher_results),
            "reflection_count": len(self.reflections),
            "status": self.status.value,
        }


__all__ = [
    "ResearchStatus",
    "Reflection",
    "ResearchState",
]
