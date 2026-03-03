"""Coordination layer for parallel agent execution.

This module provides the infrastructure for coordinating multiple
researcher agents working in parallel.

Classes:
    MessageBus: Async queue-based message passing between agents.
    ResearchState: Centralized state management for research sessions.
    AgentPool: Lifecycle management for spawned researcher agents.
    Reflection: Strategic reflection point during research.
"""

from cc_deep_research.coordination.agent_pool import AgentPool
from cc_deep_research.coordination.message_bus import MessageBus
from cc_deep_research.coordination.state import Reflection, ResearchState

__all__ = [
    "MessageBus",
    "ResearchState",
    "AgentPool",
    "Reflection",
]
