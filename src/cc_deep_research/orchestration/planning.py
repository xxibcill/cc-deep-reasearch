"""Planning services for strategy analysis and query expansion."""

from __future__ import annotations

from cc_deep_research.agents import QueryExpanderAgent, ResearchLeadAgent
from cc_deep_research.models import QueryFamily, ResearchDepth, StrategyResult
from cc_deep_research.monitoring import ResearchMonitor
from cc_deep_research.orchestration.helpers import normalize_query_families


class ResearchPlanningService:
    """Handle strategy analysis and query-family expansion."""

    def __init__(self, *, monitor: ResearchMonitor) -> None:
        self._monitor = monitor

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
        self._monitor.record_reasoning_summary(
            stage="strategy",
            summary=(
                f"Complexity {strategy.complexity} with "
                f"{len(strategy.tasks_needed)} tasks and "
                f"{strategy.strategy.query_variations} query variations"
            ),
            agent_id="lead",
        )
        return strategy

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
            raw_families=raw_families,
        )
        strategy.strategy.query_families = query_families
        self._monitor.log(f"Generated {len(query_families)} query variations")
        self._monitor.record_reasoning_summary(
            stage="query_expansion",
            summary=f"Expanded to {len(query_families)} queries",
            agent_id="expander",
            queries=[family.query for family in query_families],
        )
        return query_families
