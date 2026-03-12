"""Local team metadata for the orchestrator runtime.

This module describes the specialist roles the orchestrator wires together for a
research run. The current implementation is local-only: the orchestrator calls
Python agent objects directly and uses this wrapper as lifecycle metadata rather
than as a distributed team runtime.
"""

from dataclasses import dataclass, field

from cc_deep_research.config import Config
from cc_deep_research.models import ResearchDepth


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
    specialist roster and session lifecycle state.
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

    async def create(self) -> None:
        """Mark the local team wrapper as active for the current session."""
        self._is_active = True

    async def execute_research(
        self,
        query: str,
        depth: ResearchDepth,
        _min_sources: int | None = None,
    ) -> None:
        """Reject direct execution through the team metadata wrapper.

        Args:
            query: Research query string.
            depth: Research depth mode.
            min_sources: Minimum number of sources to gather.

        Raises:
            NotImplementedError: Always. The real workflow lives in
                ``TeamResearchOrchestrator`` and the orchestration services.
        """
        msg = (
            "LocalResearchTeam.execute_research() is not a supported workflow entrypoint. "
            "Use TeamResearchOrchestrator.execute_research() instead."
        )
        raise NotImplementedError(msg)

    async def shutdown(self) -> None:
        """Shutdown the local team wrapper."""
        self._is_active = False


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
    "LocalResearchTeam",
    "AgentSpec",
    "TeamConfig",
    "TeamCreationError",
    "TeamExecutionError",
]
