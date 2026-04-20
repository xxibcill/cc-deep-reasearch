"""Concrete local runtime boundary for the research orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cc_deep_research.agents import (
    AGENT_TYPE_ANALYZER,
    AGENT_TYPE_COLLECTOR,
    AGENT_TYPE_DEEP_ANALYZER,
    AGENT_TYPE_EXPANDER,
    AGENT_TYPE_LEAD,
    AGENT_TYPE_PLANNER,
    AGENT_TYPE_VALIDATOR,
    AnalyzerAgent,
    DeepAnalyzerAgent,
    PlannerAgent,
    QueryExpanderAgent,
    ResearchLeadAgent,
    SourceCollectorAgent,
    ValidatorAgent,
)
from cc_deep_research.config import Config
from cc_deep_research.llm import LLMRouter, LLMRouteRegistry
from cc_deep_research.monitoring import ResearchMonitor
from cc_deep_research.prompts import PromptRegistry

from .resilience import build_orchestration_timeout_policy


@dataclass(slots=True)
class OrchestratorRuntimeState:
    """Explicit local runtime state owned by the orchestrator."""

    agents: dict[str, Any]
    llm_registry: LLMRouteRegistry | None = None
    llm_router: LLMRouter | None = None
    prompt_registry: PromptRegistry | None = None
    parallel_pool_initialized: bool = False


class OrchestratorRuntime:
    """Build and tear down the local runtime used by the orchestrator."""

    def __init__(
        self,
        *,
        config: Config,
        monitor: ResearchMonitor,
        parallel_mode: bool,
        num_researchers: int,
        llm_event_callback: Any = None,
        prompt_registry: PromptRegistry | None = None,
    ) -> None:
        self._config = config
        self._monitor = monitor
        self._parallel_mode = parallel_mode
        self._num_researchers = num_researchers
        self._llm_event_callback = llm_event_callback
        self._prompt_registry = prompt_registry or PromptRegistry()
        self._state: OrchestratorRuntimeState | None = None

    async def initialize(self) -> OrchestratorRuntimeState:
        """Create the concrete local runtime once and return its state."""
        if self._state is not None:
            return self._state

        llm_registry = LLMRouteRegistry(config=self._config.llm)
        llm_router = LLMRouter(
            llm_registry,
            monitor=self._monitor,
            telemetry_callback=self._llm_event_callback,
        )
        self._state = OrchestratorRuntimeState(
            agents=self._build_agents(llm_router=llm_router),
            llm_registry=llm_registry,
            llm_router=llm_router,
            prompt_registry=self._prompt_registry,
            parallel_pool_initialized=self._parallel_mode,
        )
        return self._state

    async def shutdown(self) -> None:
        """Tear down the concrete local runtime and clear cached state."""
        if self._state is None:
            return

        agents = self._state.agents
        collector = agents.get(AGENT_TYPE_COLLECTOR)
        if isinstance(collector, SourceCollectorAgent):
            await collector.close_providers()

        self._state = None

    def current_state(self) -> OrchestratorRuntimeState | None:
        """Return the currently initialized runtime state, if any."""
        return self._state

    def _build_agents(self, *, llm_router: LLMRouter) -> dict[str, Any]:
        """Instantiate the local specialist objects used by the workflow."""
        research_settings = self._config.research.model_dump(mode="python")
        return {
            AGENT_TYPE_LEAD: ResearchLeadAgent({}),
            AGENT_TYPE_COLLECTOR: SourceCollectorAgent(
                self._config,
                monitor=self._monitor,
            ),
            AGENT_TYPE_EXPANDER: QueryExpanderAgent({}),
            AGENT_TYPE_PLANNER: PlannerAgent(research_settings),
            AGENT_TYPE_ANALYZER: AnalyzerAgent(
                research_settings,
                monitor=self._monitor,
                llm_router=llm_router,
                prompt_registry=self._prompt_registry,
            ),
            AGENT_TYPE_DEEP_ANALYZER: DeepAnalyzerAgent(
                research_settings,
                monitor=self._monitor,
                llm_router=llm_router,
                prompt_registry=self._prompt_registry,
            ),
            AGENT_TYPE_VALIDATOR: ValidatorAgent(research_settings),
        }


__all__ = [
    "OrchestratorRuntime",
    "OrchestratorRuntimeState",
]
