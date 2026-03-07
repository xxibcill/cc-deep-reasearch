"""Runtime lifecycle helpers for the local research orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cc_deep_research.agents import (
    AGENT_TYPE_ANALYZER,
    AGENT_TYPE_COLLECTOR,
    AGENT_TYPE_DEEP_ANALYZER,
    AGENT_TYPE_EXPANDER,
    AGENT_TYPE_LEAD,
    AGENT_TYPE_REPORTER,
    AGENT_TYPE_VALIDATOR,
    AnalyzerAgent,
    DeepAnalyzerAgent,
    QueryExpanderAgent,
    ReporterAgent,
    ResearchLeadAgent,
    SourceCollectorAgent,
    ValidatorAgent,
)
from cc_deep_research.config import Config
from cc_deep_research.coordination import LocalAgentPool, LocalMessageBus
from cc_deep_research.monitoring import ResearchMonitor
from cc_deep_research.teams import AgentSpec, LocalResearchTeam, TeamConfig


@dataclass
class RuntimeState:
    """Concrete runtime objects created for an orchestrator session."""

    team: LocalResearchTeam
    agents: dict[str, Any]
    message_bus: LocalMessageBus | None
    agent_pool: LocalAgentPool | None


class OrchestratorRuntime:
    """Build and tear down runtime dependencies for research execution."""

    def __init__(
        self,
        *,
        config: Config,
        monitor: ResearchMonitor,
        parallel_mode: bool,
        num_researchers: int,
    ) -> None:
        self._config = config
        self._monitor = monitor
        self._parallel_mode = parallel_mode
        self._num_researchers = num_researchers

    async def initialize(self, existing_team: LocalResearchTeam | None) -> RuntimeState | None:
        """Create runtime dependencies when no active team exists."""
        if existing_team is not None:
            return None

        self._monitor.section("Runtime Initialization")

        message_bus: LocalMessageBus | None = None
        agent_pool: LocalAgentPool | None = None
        if self._parallel_mode:
            message_bus = LocalMessageBus()
            agent_pool = LocalAgentPool(
                num_agents=self._num_researchers,
                config=self._config,
                timeout=self._config.search_team.timeout_seconds,
            )
            await agent_pool.initialize()
            self._monitor.log(
                f"Parallel local collection enabled: {self._num_researchers} researcher tasks"
            )
        else:
            self._monitor.log("Sequential local collection enabled")

        agent_specs = self._build_agent_specs()
        team = LocalResearchTeam(self._build_team_config(agent_specs), self._config)
        agents = self._build_agents()

        self._monitor.log(f"Created local specialist registry with {len(agent_specs)} roles")
        self._monitor.record_reasoning_summary(
            stage="team_init",
            summary=f"Initialized {len(agent_specs)} local specialist roles",
            agent_id="orchestrator",
            agent_types=[spec.agent_type for spec in agent_specs],
        )

        return RuntimeState(
            team=team,
            agents=agents,
            message_bus=message_bus,
            agent_pool=agent_pool,
        )

    async def shutdown(
        self,
        *,
        team: LocalResearchTeam | None,
        agents: dict[str, Any],
        message_bus: LocalMessageBus | None,
        agent_pool: LocalAgentPool | None,
    ) -> None:
        """Shutdown runtime dependencies and close external resources."""
        if self._parallel_mode:
            if message_bus is not None:
                await message_bus.shutdown()
            if agent_pool is not None:
                await agent_pool.shutdown()
            self._monitor.log("Local coordination helpers shut down")

        if team is not None:
            await team.shutdown()
            self._monitor.section("Runtime Shutdown")
            self._monitor.log("Local runtime shut down successfully")

        collector = agents.get(AGENT_TYPE_COLLECTOR)
        if isinstance(collector, SourceCollectorAgent):
            await collector.close_providers()

    def _build_agent_specs(self) -> list[AgentSpec]:
        """Build static agent specifications for the research team."""
        return [
            AgentSpec(
                name="research-lead",
                description="Orchestrates research strategy",
                agent_type=AGENT_TYPE_LEAD,
                model=self._config.research_agent.model,
            ),
            AgentSpec(
                name="source-collector",
                description="Collects sources from providers",
                agent_type=AGENT_TYPE_COLLECTOR,
                model=self._config.research_agent.model,
            ),
            AgentSpec(
                name="query-expander",
                description="Expands queries for coverage",
                agent_type=AGENT_TYPE_EXPANDER,
                model=self._config.research_agent.model,
            ),
            AgentSpec(
                name="analyzer",
                description="Analyzes collected information",
                agent_type=AGENT_TYPE_ANALYZER,
                model=self._config.research_agent.model,
            ),
            AgentSpec(
                name="reporter",
                description="Generates research reports",
                agent_type=AGENT_TYPE_REPORTER,
                model=self._config.research_agent.model,
            ),
            AgentSpec(
                name="validator",
                description="Validates research quality",
                agent_type=AGENT_TYPE_VALIDATOR,
                model=self._config.research_agent.model,
            ),
        ]

    def _build_team_config(self, agent_specs: list[AgentSpec]) -> TeamConfig:
        """Build team configuration for runtime initialization."""
        return TeamConfig(
            team_name="research-team",
            team_description="Team for coordinated web research",
            agents=agent_specs,
            timeout_seconds=self._config.search_team.timeout_seconds,
            parallel_execution=self._config.search_team.parallel_execution,
        )

    def _build_agents(self) -> dict[str, Any]:
        """Build local agent instances used by the orchestrator."""
        analyzer_config = {
            "ai_integration_method": self._config.research.ai_integration_method,
            "model": self._config.research_agent.model,
            "deep_analysis_tokens": self._config.research.deep_analysis_tokens,
            "ai_num_themes": self._config.research.ai_num_themes,
            "ai_deep_num_themes": self._config.research.ai_deep_num_themes,
            "ai_temperature": self._config.research.ai_temperature,
            "claude_cli_path": self._config.research.claude_cli_path,
            "claude_cli_timeout_seconds": self._config.research.claude_cli_timeout_seconds,
            "usage_callback": self._monitor.record_llm_usage,
        }

        return {
            AGENT_TYPE_LEAD: ResearchLeadAgent({}),
            AGENT_TYPE_COLLECTOR: SourceCollectorAgent(self._config, monitor=self._monitor),
            AGENT_TYPE_EXPANDER: QueryExpanderAgent({}),
            AGENT_TYPE_ANALYZER: AnalyzerAgent(analyzer_config),
            AGENT_TYPE_DEEP_ANALYZER: DeepAnalyzerAgent(
                {
                    **analyzer_config,
                    "deep_analysis_passes": self._config.research.deep_analysis_passes,
                }
            ),
            AGENT_TYPE_REPORTER: ReporterAgent({}),
            AGENT_TYPE_VALIDATOR: ValidatorAgent(
                {
                    "min_sources": self._config.research.min_sources.__dict__["deep"],
                    "require_diverse_domains": True,
                }
            ),
        }
