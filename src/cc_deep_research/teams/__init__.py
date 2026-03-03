"""Team management for CC Deep Research CLI.

This module provides team-based research orchestration using Claude's Agent Teams
functionality, enabling parallel research through multiple specialized agents.
"""

from cc_deep_research.teams.research_team import (
    AgentSpec,
    ResearchTeam,
    TeamConfig,
    TeamCreationError,
    TeamExecutionError,
)

__all__ = [
    "ResearchTeam",
    "AgentSpec",
    "TeamConfig",
    "TeamCreationError",
    "TeamExecutionError",
]
