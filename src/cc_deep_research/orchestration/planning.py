"""Planning services for strategy analysis and query expansion."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from cc_deep_research.agents import QueryExpanderAgent, ResearchLeadAgent
from cc_deep_research.config import Config
from cc_deep_research.models import QueryFamily, ResearchDepth, StrategyResult
from cc_deep_research.monitoring import ResearchMonitor
from cc_deep_research.orchestration.helpers import normalize_query_families
from cc_deep_research.orchestration.llm_route_planner import (
    LLMRoutePlanner,
    create_llm_plan,
)

if TYPE_CHECKING:
    from cc_deep_research.llm.registry import LLMRouteRegistry
    from cc_deep_research.orchestration.session_state import OrchestratorSessionState


class ResearchPlanningService:
    """Handle strategy analysis and query-family expansion."""

    def __init__(
        self,
        *,
        monitor: ResearchMonitor,
        config: Config | None = None,
        registry: LLMRouteRegistry | None = None,
        session_state: OrchestratorSessionState | None = None,
    ) -> None:
        self._monitor = monitor
        self._config = config
        self._registry = registry
        self._session_state = session_state

    async def analyze_strategy(
        self,
        *,
        lead: ResearchLeadAgent,
        query: str,
        depth: ResearchDepth,
    ) -> StrategyResult:
        """Analyze the incoming query and return a research strategy."""
        self._monitor.section("Strategy Analysis")
        strategy = lead.analyze_query(query, depth)
        self._monitor.log(f"Complexity: {strategy.complexity}")
        self._monitor.log(f"Tasks: {len(strategy.tasks_needed)}")
        self._monitor.log(f"Query variations: {strategy.strategy.query_variations}")

        # Create LLM route plan if config is available
        if self._config is not None:
            llm_plan = create_llm_plan(self._config, strategy)
            strategy.llm_plan = llm_plan

            if self._registry is not None:
                planner = LLMRoutePlanner(self._config)
                planner.update_registry_from_plan(llm_plan, self._registry)
                self._monitor.log(
                    f"LLM routes: default={llm_plan.default_route.transport.value}"
                )
            self._record_planned_routes(llm_plan)

        self._monitor.record_reasoning_summary(
            stage="strategy",
            summary=(
                f"Complexity {strategy.complexity} with "
                f"{len(strategy.tasks_needed)} tasks and "
                f"{strategy.strategy.query_variations} query variations"
            ),
            agent_id="lead",
        )
        self._monitor.emit_decision_made(
            decision_type="planner_strategy",
            reason_code="strategy_profile_selected",
            chosen_option=strategy.complexity,
            rejected_options=[],
            inputs={
                "depth": depth.value,
                "query_variations": strategy.strategy.query_variations,
                "task_count": len(strategy.tasks_needed),
                "intent": strategy.strategy.intent,
            },
            actor_id="lead",
            phase="planning",
            operation="planner.strategy",
        )
        return strategy

    def _record_planned_routes(self, llm_plan: object) -> None:
        """Persist planned routes into telemetry and session metadata."""
        if not hasattr(llm_plan, "agent_routes") or not hasattr(llm_plan, "default_route"):
            return

        fallback_order = [
            transport.value
            for transport in getattr(llm_plan, "fallback_order", [])
            if hasattr(transport, "value")
        ]

        default_route = llm_plan.default_route
        self._monitor.record_llm_route_selected(
            agent_id="default",
            transport=default_route.transport.value,
            provider=default_route.provider.value,
            model=default_route.model,
            source="planner",
        )
        self._monitor.emit_decision_made(
            decision_type="routing",
            reason_code="planner_default_route",
            chosen_option=default_route.transport.value,
            rejected_options=[
                transport for transport in fallback_order if transport != default_route.transport.value
            ],
            inputs={
                "agent_id": "default",
                "provider": default_route.provider.value,
                "model": default_route.model,
                "source": "planner",
            },
            actor_id="planner",
            phase="planning",
            operation="planner.route.default",
        )
        if self._session_state is not None:
            self._session_state.set_llm_planned_route(
                agent_id="default",
                transport=default_route.transport.value,
                provider=default_route.provider.value,
                model=default_route.model,
            )

        for agent_id, route in llm_plan.agent_routes.items():
            self._monitor.record_llm_route_selected(
                agent_id=agent_id,
                transport=route.transport.value,
                provider=route.provider.value,
                model=route.model,
                source="planner",
            )
            self._monitor.emit_decision_made(
                decision_type="routing",
                reason_code="planner_agent_route",
                chosen_option=route.transport.value,
                rejected_options=[
                    transport for transport in fallback_order if transport != route.transport.value
                ],
                inputs={
                    "agent_id": agent_id,
                    "provider": route.provider.value,
                    "model": route.model,
                    "source": "planner",
                },
                actor_id="planner",
                phase="planning",
                operation="planner.route.agent",
            )
            if self._session_state is not None:
                self._session_state.set_llm_planned_route(
                    agent_id=agent_id,
                    transport=route.transport.value,
                    provider=route.provider.value,
                    model=route.model,
                )

    async def expand_queries(
        self,
        *,
        expander: QueryExpanderAgent,
        query: str,
        strategy: StrategyResult,
        depth: ResearchDepth,
    ) -> list[QueryFamily]:
        """Expand the strategy into query families for collection."""
        self._monitor.section("Query Expansion")

        variations = strategy.strategy.query_variations
        if variations <= 1:
            self._monitor.log("Query expansion not needed (quick mode)")
            query_families = [
                QueryFamily(
                    query=query,
                    family="baseline",
                    intent_tags=["baseline", strategy.strategy.intent],
                )
            ]
            strategy.strategy.query_families = query_families
            self._monitor.record_query_variations(
                original_query=query,
                query_families=query_families,
                strategy_intent=strategy.strategy.intent,
            )
            return query_families

        raw_families = expander.expand_query(
            query,
            depth,
            max_variations=variations,
            strategy=strategy.strategy.model_dump(mode="python"),
        )
        query_families = normalize_query_families(
            original_query=query,
            strategy=strategy,
            raw_families=cast(list[QueryFamily | str], raw_families),
        )
        strategy.strategy.query_families = query_families
        self._monitor.log(f"Generated {len(query_families)} query variations")
        self._monitor.record_reasoning_summary(
            stage="query_expansion",
            summary=f"Expanded to {len(query_families)} queries",
            agent_id="expander",
            queries=[family.query for family in query_families],
        )
        self._monitor.record_query_variations(
            original_query=query,
            query_families=query_families,
            strategy_intent=strategy.strategy.intent,
        )
        return query_families
