"""Local team metadata for the orchestrator runtime.

This module describes the specialist roles the orchestrator wires together for a
research run. The current implementation is local-only: the orchestrator calls
Python agent objects directly and uses this wrapper as lifecycle metadata rather
than as a distributed team runtime.
"""

from dataclasses import dataclass, field
from typing import Any

from cc_deep_research.config import Config
from cc_deep_research.models import ResearchDepth, ResearchSession


@dataclass
class AgentSpec:
    """Specification for a research agent.

    Args:
        name: Agent name (used for identification)
        description: Brief description of agent's role
        agent_type: Type of agent (lead, collector, analyzer, reporter, etc.)
        model: Claude model to use for this agent
    """

    name: str
    description: str
    agent_type: str
    model: str = "claude-sonnet-4-6"


@dataclass
class TeamConfig:
    """Configuration for a research team.

    Args:
        team_name: Name for the team
        team_description: Description of team's purpose
        agents: List of agent specifications
        timeout_seconds: Default timeout for team operations
        parallel_execution: Whether agents work in parallel
    """

    team_name: str
    team_description: str
    agents: list[AgentSpec] = field(default_factory=list)
    timeout_seconds: int = 300
    parallel_execution: bool = True


class LocalResearchTeam:
    """Hold local specialist-role metadata for one orchestrator session.

    The orchestrator owns execution. This class only tracks the configured
    specialist roster and a small in-memory placeholder state used by tests and
    future runtime experiments.
    """

    def __init__(
        self,
        config: TeamConfig,
        app_config: Config,
    ) -> None:
        """Initialize the research team.

        Args:
            config: Team configuration.
            app_config: Application configuration.
        """
        self._config = config
        self._app_config = app_config
        self._is_active: bool = False
        self._agent_instances: dict[str, Any] = {}

    @property
    def is_active(self) -> bool:
        """Check if the team is currently active.

        Returns:
            True if team is active, False otherwise.
        """
        return self._is_active

    @property
    def team_name(self) -> str:
        """Get the team name.

        Returns:
            Team name string.
        """
        return self._config.team_name

    def get_agent_specs(self) -> list[AgentSpec]:
        """Get specifications for all agents in the team.

        Returns:
            List of agent specifications.
        """
        return self._config.agents

    def get_agent_by_type(self, agent_type: str) -> AgentSpec | None:
        """Get agent specification by type.

        Args:
            agent_type: Type of agent to find.

        Returns:
            AgentSpec if found, None otherwise.
        """
        for agent in self._config.agents:
            if agent.agent_type == agent_type:
                return agent
        return None

    # Placeholder methods for actual Agent tool integration
    # These would be implemented using Claude's Agent, TeamCreate, SendMessage tools

    async def spawn_researcher(
        self,
        researcher_name: str,
        task: dict[str, Any],
    ) -> str:
        """Spawn a researcher agent with a task.

        Args:
            researcher_name: Name for the researcher agent.
            task: Task dictionary to assign to the researcher.

        Returns:
            Agent ID of the spawned researcher.

        Note:
            This is a placeholder. In a real implementation, this would use
            the Agent tool to spawn a Claude Code instance.
        """
        import uuid

        agent_id = f"{researcher_name}-{uuid.uuid4().hex[:8]}"

        self._agent_instances[agent_id] = {
            "name": researcher_name,
            "task": task,
            "status": "active",
        }

        return agent_id

    async def send_message(
        self,
        recipient: str,
        content: str,
        message_type: str = "task",
    ) -> None:
        """Send a message to a specific agent.

        Args:
            recipient: Agent ID of the recipient.
            content: Message content.
            message_type: Type of message (task, result, status, etc.).

        Note:
            This is a placeholder. In a real implementation, this would use
            the SendMessage tool to communicate with spawned agents.
        """
        if recipient in self._agent_instances:
            # Store message in agent's instance for later retrieval
            if "messages" not in self._agent_instances[recipient]:
                self._agent_instances[recipient]["messages"] = []
            self._agent_instances[recipient]["messages"].append({
                "type": message_type,
                "content": content,
            })

    async def collect_results(self, agent_ids: list[str]) -> dict[str, Any]:
        """Collect results from multiple agents.

        Args:
            agent_ids: List of agent IDs to collect results from.

        Returns:
            Dictionary mapping agent IDs to their results.
        """
        results = {}
        for agent_id in agent_ids:
            if agent_id in self._agent_instances:
                results[agent_id] = self._agent_instances[agent_id].get("results")

        return results

    async def create(self) -> None:
        """Mark the local team wrapper as active for the current session."""
        self._is_active = True

    async def execute_research(
        self,
        query: str,
        depth: ResearchDepth,
        _min_sources: int | None = None,
    ) -> ResearchSession:
        """Return a placeholder session for compatibility tests.

        Args:
            query: Research query string.
            depth: Research depth mode.
            min_sources: Minimum number of sources to gather.

        Returns:
            ResearchSession with results from all agents.

        The real research workflow lives in ``TeamResearchOrchestrator`` and its
        service objects. This method remains as a compatibility stub until the
        project either removes the wrapper or introduces a real external team
        runtime.
        """
        return ResearchSession(
            session_id="placeholder",
            query=query,
            depth=depth,
        )

    async def shutdown(self) -> None:
        """Shutdown the local team wrapper and clear placeholder state."""
        for _agent_id, agent_data in self._agent_instances.items():
            agent_data["status"] = "shutdown"

        self._agent_instances.clear()
        self._is_active = False


ResearchTeam = LocalResearchTeam


class TeamCreationError(Exception):
    """Exception raised when team creation fails."""

    def __init__(
        self,
        message: str,
        team_name: str | None = None,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.team_name = team_name
        self.original_error = original_error


class TeamExecutionError(Exception):
    """Exception raised when team execution fails."""

    def __init__(
        self,
        message: str,
        query: str | None = None,
        original_error: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.query = query
        self.original_error = original_error


__all__ = [
    "ResearchTeam",
    "LocalResearchTeam",
    "AgentSpec",
    "TeamConfig",
    "TeamCreationError",
    "TeamExecutionError",
]
