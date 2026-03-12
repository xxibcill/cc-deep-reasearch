"""Local coordination helpers used by the orchestrator.

These types model a future coordination layer but currently operate as
in-process helpers around the local Python pipeline.
"""

from cc_deep_research.coordination.agent_pool import LocalAgentPool
from cc_deep_research.coordination.message_bus import LocalMessageBus
from cc_deep_research.coordination.state import Reflection, ResearchState

__all__ = [
    "LocalMessageBus",
    "ResearchState",
    "LocalAgentPool",
    "Reflection",
]
