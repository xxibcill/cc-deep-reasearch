"""Agent pool for managing researcher agents.

This module provides lifecycle management for spawned researcher agents.
"""

import asyncio
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4

from cc_deep_research.config import Config


class AgentStatus(StrEnum):
    """Status of a researcher agent."""

    SPAWNING = "spawning"
    IDLE = "idle"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SHUTDOWN = "shutdown"


@dataclass
class AgentInstance:
    """An instance of a spawned researcher agent.

    Attributes:
        id: Unique agent identifier.
        name: Agent name.
        status: Current agent status.
        task: Task assigned to the agent.
        result: Result from the agent (if completed).
        error: Error from the agent (if failed).
        spawned_at: Unix timestamp when agent was spawned.
        completed_at: Unix timestamp when agent completed (if applicable).
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    status: AgentStatus = AgentStatus.SPAWNING
    task: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error: Exception | None = None
    spawned_at: float = field(default_factory=asyncio.get_event_loop().time)
    completed_at: float | None = None

    @property
    def duration_ms(self) -> float | None:
        """Get the agent execution duration in milliseconds.

        Returns:
            Duration in milliseconds, or None if not completed.
        """
        if self.completed_at is None:
            return None
        return (self.completed_at - self.spawned_at) * 1000

    def mark_completed(self, result: dict[str, Any]) -> None:
        """Mark the agent as completed with a result.

        Args:
            result: The result from the agent.
        """
        self.status = AgentStatus.COMPLETED
        self.result = result
        self.completed_at = asyncio.get_event_loop().time()

    def mark_failed(self, error: Exception) -> None:
        """Mark the agent as failed with an error.

        Args:
            error: The error that caused failure.
        """
        self.status = AgentStatus.FAILED
        self.error = error
        self.completed_at = asyncio.get_event_loop().time()

    def mark_timeout(self) -> None:
        """Mark the agent as timed out."""
        self.status = AgentStatus.TIMEOUT
        self.completed_at = asyncio.get_event_loop().time()

    def mark_active(self) -> None:
        """Mark the agent as active (executing a task)."""
        self.status = AgentStatus.ACTIVE

    def mark_shutdown(self) -> None:
        """Mark the agent as shut down."""
        self.status = AgentStatus.SHUTDOWN


class AgentPool:
    """Pool for managing researcher agents.

    This class manages the lifecycle of researcher agents spawned
    via the Agent tool. It tracks agent status, results, and
    provides methods for spawning and shutting down agents.

    Example:
        >>> pool = AgentPool(num_agents=3, config=config)
        >>> # Spawn agents
        >>> agent_ids = await pool.spawn_agents(["task1", "task2", "task3"])
        >>> # Wait for completion
        >>> results = await pool.wait_for_completion(timeout=120)
        >>> # Shutdown
        >>> await pool.shutdown()
    """

    def __init__(
        self,
        num_agents: int,
        config: Config,
        timeout: float = 120.0,
    ) -> None:
        """Initialize the agent pool.

        Args:
            num_agents: Number of agents to spawn.
            config: Application configuration.
            timeout: Default timeout for agent execution (seconds).
        """
        self._num_agents = num_agents
        self._config = config
        self._timeout = timeout
        self._agents: dict[str, AgentInstance] = {}
        self._lock: asyncio.Lock = asyncio.Lock()
        self._active = False

    @property
    def is_active(self) -> bool:
        """Check if the pool is active.

        Returns:
            True if active, False otherwise.
        """
        return self._active

    @property
    def num_agents(self) -> int:
        """Get the number of agents in the pool.

        Returns:
            Number of agents.
        """
        return len(self._agents)

    @property
    def active_count(self) -> int:
        """Get the number of active agents.

        Returns:
            Number of active agents.
        """
        return sum(
            1 for a in self._agents.values()
            if a.status == AgentStatus.ACTIVE
        )

    @property
    def completed_count(self) -> int:
        """Get the number of completed agents.

        Returns:
            Number of completed agents.
        """
        return sum(
            1 for a in self._agents.values()
            if a.status == AgentStatus.COMPLETED
        )

    @property
    def failed_count(self) -> int:
        """Get the number of failed agents.

        Returns:
            Number of failed agents.
        """
        return sum(
            1 for a in self._agents.values()
            if a.status in (AgentStatus.FAILED, AgentStatus.TIMEOUT)
        )

    async def initialize(self) -> None:
        """Initialize the agent pool."""
        self._active = True
        self._agents.clear()

    async def spawn_agent(
        self,
        name: str,
        task: dict[str, Any],
    ) -> str:
        """Spawn a single researcher agent.

        Args:
            name: Name for the agent.
            task: Task to assign to the agent.

        Returns:
            Agent ID.

        Note:
            This is a placeholder. Actual Agent tool integration
            would use the Agent tool to spawn real agents.
        """
        if not self._active:
            msg = "Cannot spawn agent: pool is not active"
            raise RuntimeError(msg)

        # Create agent instance
        agent = AgentInstance(
            name=name,
            status=AgentStatus.SPAWNING,
            task=task,
        )

        # Add to pool
        async with self._lock:
            self._agents[agent.id] = agent

        # In a real implementation, this would use the Agent tool
        # to spawn a Claude Code instance
        # For now, we simulate spawning
        agent.status = AgentStatus.IDLE

        return agent.id

    async def spawn_agents(
        self,
        tasks: list[dict[str, Any]],
    ) -> list[str]:
        """Spawn multiple researcher agents.

        Args:
            tasks: List of tasks to assign to agents.

        Returns:
            List of agent IDs.
        """
        agent_ids: list[str] = []

        for i, task in enumerate(tasks):
            name = f"researcher-{i + 1}"
            agent_id = await self.spawn_agent(name, task)
            agent_ids.append(agent_id)

        return agent_ids

    def get_agent(self, agent_id: str) -> AgentInstance | None:
        """Get an agent by ID.

        Args:
            agent_id: Agent ID.

        Returns:
            Agent instance or None if not found.
        """
        return self._agents.get(agent_id)

    def get_all_agents(self) -> list[AgentInstance]:
        """Get all agents in the pool.

        Returns:
            List of all agent instances.
        """
        return list(self._agents.values())

    def get_agents_by_status(
        self,
        status: AgentStatus,
    ) -> list[AgentInstance]:
        """Get agents by status.

        Args:
            status: Status to filter by.

        Returns:
            List of agents with the specified status.
        """
        return [a for a in self._agents.values() if a.status == status]

    async def wait_for_completion(
        self,
        timeout: float | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Wait for all agents to complete.

        Args:
            timeout: Optional timeout in seconds. If None, uses pool default.

        Returns:
            Dictionary mapping agent IDs to results.

        Raises:
            asyncio.TimeoutError: If timeout is exceeded.
        """
        timeout = timeout or self._timeout
        deadline = asyncio.get_event_loop().time() + timeout

        while self._active:
            completed = self.completed_count
            total = self.num_agents

            if completed >= total:
                # All agents completed
                return {
                    agent_id: agent.result
                    for agent_id, agent in self._agents.items()
                    if agent.result is not None
                }

            # Check for timeout
            if asyncio.get_event_loop().time() > deadline:
                msg = f"Agent pool timeout after {timeout}s"
                raise TimeoutError(msg)

            # Wait a bit before checking again
            await asyncio.sleep(0.5)

        msg = "Cannot wait for completion: pool is not active"
        raise RuntimeError(msg)

    async def shutdown(self) -> None:
        """Shutdown the agent pool.

        Marks all agents as shutdown and clears the pool.
        """
        async with self._lock:
            for agent in self._agents.values():
                agent.mark_shutdown()

            self._agents.clear()
            self._active = False

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the pool state.

        Returns:
            Dictionary with pool statistics.
        """
        return {
            "total": self.num_agents,
            "active": self.active_count,
            "completed": self.completed_count,
            "failed": self.failed_count,
            "agents": [
                {
                    "id": a.id,
                    "name": a.name,
                    "status": a.status.value,
                    "duration_ms": a.duration_ms,
                }
                for a in self._agents.values()
            ],
        }


__all__ = [
    "AgentStatus",
    "AgentInstance",
    "AgentPool",
]
