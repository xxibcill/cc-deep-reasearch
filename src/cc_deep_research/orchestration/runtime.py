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
from cc_deep_research.coordination import LocalAgentPool, LocalMessageBus
from cc_deep_research.llm import LLMRouteRegistry, LLMRouter
from cc_deep_research.monitoring import ResearchMonitor
from cc_deep_research.prompts import PromptRegistry
from cc_deep_research.teams import AgentSpec, LocalResearchTeam, TeamConfig

from .resilience import build_orchestration_timeout_policy


@dataclass(slots=True)
class OrchestratorRuntimeState:
    """Explicit local runtime state owned by the orchestrator."""

    team: LocalResearchTeam
    agents: dict[str, Any]
    message_bus: LocalMessageBus
    agent_pool: LocalAgentPool | None
    llm_registry: LLMRouteRegistry | None = None
    llm_router: LLMRouter | None = None
    prompt_registry: PromptRegistry | None = None


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

    async def initialize(
        self,
        existing_team: LocalResearchTeam | None = None,
    ) -> OrchestratorRuntimeState:
        """Create the concrete local runtime once and return its state."""
        if self._state is not None:
            return self._state

        team = existing_team or LocalResearchTeam(
            config=self._build_team_config(),
            app_config=self._config,
        )
        await team.create()

        message_bus = LocalMessageBus()
        agent_pool = await self._initialize_agent_pool()
        llm_registry = LLMRouteRegistry(config=self._config.llm)
        llm_router = LLMRouter(
            llm_registry,
            monitor=self._monitor,
            telemetry_callback=self._llm_event_callback,
        )
        self._state = OrchestratorRuntimeState(
            team=team,
            agents=self._build_agents(llm_router=llm_router),
            message_bus=message_bus,
            agent_pool=agent_pool,
            llm_registry=llm_registry,
            llm_router=llm_router,
            prompt_registry=self._prompt_registry,
        )
        return self._state

    async def shutdown(self) -> None:
        """Tear down the concrete local runtime and clear cached state."""
        if self._state is None:
            return

        team = self._state.team
        agents = self._state.agents
        message_bus = self._state.message_bus
        agent_pool = self._state.agent_pool
        collector = agents.get(AGENT_TYPE_COLLECTOR)
        if isinstance(collector, SourceCollectorAgent):
            await collector.close_providers()

        if agent_pool is not None:
            await agent_pool.shutdown()

        if message_bus is not None:
            await message_bus.shutdown()

        if team is not None and team.is_active:
            await team.shutdown()

        self._state = None

    def current_state(self) -> OrchestratorRuntimeState | None:
        """Return the currently initialized runtime state, if any."""
        return self._state

    def _build_team_config(self) -> TeamConfig:
        """Describe the local specialist roster exposed by the runtime."""
        timeout_policy = build_orchestration_timeout_policy(self._config)
        return TeamConfig(
            team_name="local-research-runtime",
            team_description="Local orchestrator-managed specialist roster.",
            agents=[
                AgentSpec(
                    name="research-lead",
                    description="Plans the research workflow.",
                    agent_type=AGENT_TYPE_LEAD,
                    model=self._config.research_agent.model,
                ),
                AgentSpec(
                    name="source-collector",
                    description="Collects sources from configured providers.",
                    agent_type=AGENT_TYPE_COLLECTOR,
                    model=self._config.research_agent.model,
                ),
                AgentSpec(
                    name="query-expander",
                    description="Builds retrieval-oriented query families.",
                    agent_type=AGENT_TYPE_EXPANDER,
                    model=self._config.research_agent.model,
                ),
                AgentSpec(
                    name="planner",
                    description="Controls whether the research loop should continue.",
                    agent_type=AGENT_TYPE_PLANNER,
                    model=self._config.research_agent.model,
                ),
                AgentSpec(
                    name="analyzer",
                    description="Synthesizes findings from collected sources.",
                    agent_type=AGENT_TYPE_ANALYZER,
                    model=self._config.research_agent.model,
                ),
                AgentSpec(
                    name="deep-analyzer",
                    description="Runs the deep multi-pass analysis workflow.",
                    agent_type=AGENT_TYPE_DEEP_ANALYZER,
                    model=self._config.research_agent.model,
                ),
                AgentSpec(
                    name="validator",
                    description="Validates coverage and evidence quality.",
                    agent_type=AGENT_TYPE_VALIDATOR,
                    model=self._config.research_agent.model,
                ),
            ],
            timeout_seconds=int(timeout_policy.team_timeout_seconds),
            parallel_execution=self._parallel_mode,
        )

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

    async def _initialize_agent_pool(self) -> LocalAgentPool | None:
        """Create the optional local pool used for parallel source fan-out."""
        if not self._parallel_mode:
            return None

        timeout_policy = build_orchestration_timeout_policy(self._config)
        agent_pool = LocalAgentPool(
            num_agents=self._num_researchers,
            config=self._config,
            timeout=timeout_policy.researcher_timeout_seconds,
        )
        await agent_pool.initialize()
        return agent_pool


__all__ = [
    "OrchestratorRuntime",
    "OrchestratorRuntimeState",
]
