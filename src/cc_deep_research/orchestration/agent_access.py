"""Typed accessors for orchestrator-managed agent instances."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from cc_deep_research.agents import (
    AGENT_TYPE_ANALYZER,
    AGENT_TYPE_COLLECTOR,
    AGENT_TYPE_DEEP_ANALYZER,
    AGENT_TYPE_EXPANDER,
    AGENT_TYPE_LEAD,
    AGENT_TYPE_VALIDATOR,
    AnalyzerAgent,
    DeepAnalyzerAgent,
    QueryExpanderAgent,
    ResearchLeadAgent,
    SourceCollectorAgent,
    ValidatorAgent,
)


class AgentAccess:
    """Provide typed access to the current orchestrator agent mapping."""

    def __init__(self, mapping_provider: Callable[[], dict[str, Any]]) -> None:
        self._mapping_provider = mapping_provider

    def lead(self) -> ResearchLeadAgent:
        """Return the lead agent."""
        return cast(ResearchLeadAgent, self._mapping_provider()[AGENT_TYPE_LEAD])

    def expander(self) -> QueryExpanderAgent:
        """Return the query-expander agent."""
        return cast(QueryExpanderAgent, self._mapping_provider()[AGENT_TYPE_EXPANDER])

    def collector(self) -> SourceCollectorAgent:
        """Return the source-collector agent."""
        return cast(SourceCollectorAgent, self._mapping_provider()[AGENT_TYPE_COLLECTOR])

    def analyzer(self) -> AnalyzerAgent:
        """Return the analyzer agent."""
        return cast(AnalyzerAgent, self._mapping_provider()[AGENT_TYPE_ANALYZER])

    def deep_analyzer(self) -> DeepAnalyzerAgent:
        """Return the deep-analyzer agent."""
        return cast(DeepAnalyzerAgent, self._mapping_provider()[AGENT_TYPE_DEEP_ANALYZER])

    def validator(self) -> ValidatorAgent:
        """Return the validator agent."""
        return cast(ValidatorAgent, self._mapping_provider()[AGENT_TYPE_VALIDATOR])
