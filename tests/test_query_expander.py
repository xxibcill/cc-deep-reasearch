"""Tests for QueryExpanderAgent."""

import pytest

from cc_deep_research.agents.query_expander import QueryExpanderAgent
from cc_deep_research.models import QueryFamily, ResearchDepth


class TestQueryExpanderAgent:
    """Tests for QueryExpanderAgent query expansion logic."""

    @pytest.fixture
    def agent(self) -> QueryExpanderAgent:
        return QueryExpanderAgent(config={})

    def test_expand_query_includes_baseline(self, agent: QueryExpanderAgent) -> None:
        """Original query should appear as baseline family."""
        families = agent.expand_query(
            query="market structure analysis",
            depth=ResearchDepth.STANDARD,
        )
        assert any(f.query == "market structure analysis" for f in families)
        assert any(f.family == "baseline" for f in families)

    def test_expand_query_respects_max_variations(self, agent: QueryExpanderAgent) -> None:
        """Should limit families to max_variations."""
        families = agent.expand_query(
            query="market structure",
            depth=ResearchDepth.STANDARD,
            max_variations=2,
        )
        assert len(families) <= 2

    def test_expand_query_depth_mapping(self, agent: QueryExpanderAgent) -> None:
        """Depth should map to correct max_variations when not specified."""
        quick = agent.expand_query("test query", ResearchDepth.QUICK)
        assert len(quick) == 1

        standard = agent.expand_query("test query", ResearchDepth.STANDARD)
        assert len(standard) <= 3

        deep = agent.expand_query("test query", ResearchDepth.DEEP)
        assert len(deep) <= 5

    def test_expand_query_generates_multiple_family_types(self, agent: QueryExpanderAgent) -> None:
        """Should generate families beyond baseline for standard/deep queries."""
        families = agent.expand_query(
            query="blockchain supply chain tracking",
            depth=ResearchDepth.DEEP,
            max_variations=5,
        )
        family_names = {f.family for f in families}
        assert len(family_names) > 1

    def test_expand_query_primary_source_for_evidence_seeking(self, agent: QueryExpanderAgent) -> None:
        """Should generate primary-source family for evidence-seeking intent."""
        strategy = {
            "intent": "evidence-seeking",
            "key_terms": [],
            "target_source_classes": [],
        }
        families = agent.expand_query(
            query="climate change carbon footprint",
            depth=ResearchDepth.STANDARD,
            strategy=strategy,
        )
        assert any(f.family == "primary-source" for f in families)

    def test_expand_query_current_updates_for_time_sensitive(self, agent: QueryExpanderAgent) -> None:
        """Should generate current-updates family when query is time-sensitive."""
        strategy = {
            "intent": "informational",
            "time_sensitive": True,
            "key_terms": [],
            "target_source_classes": [],
        }
        families = agent.expand_query(
            query="federal reserve interest rate decision",
            depth=ResearchDepth.STANDARD,
            strategy=strategy,
        )
        assert any(f.family == "current-updates" for f in families)

    def test_expand_query_opposing_view_for_comparative(self, agent: QueryExpanderAgent) -> None:
        """Should generate opposing-view family for comparative intent when depth allows."""
        strategy = {
            "intent": "comparative",
            "key_terms": [],
            "target_source_classes": [],
        }
        # Need DEEP depth (max_variations=5) to fit all 4 candidate families
        families = agent.expand_query(
            query="nuclear power vs solar energy",
            depth=ResearchDepth.DEEP,
            max_variations=5,
            strategy=strategy,
        )
        assert any(f.family == "opposing-view" for f in families)

    def test_expand_query_tags_include_intent(self, agent: QueryExpanderAgent) -> None:
        """Family intent_tags should include the strategy intent."""
        strategy = {
            "intent": "informational",
            "time_sensitive": False,
            "key_terms": [],
            "target_source_classes": [],
        }
        families = agent.expand_query(
            query="machine learning algorithms",
            depth=ResearchDepth.STANDARD,
            strategy=strategy,
        )
        for family in families:
            assert "informational" in family.intent_tags

    def test_validate_relevance_keeps_baseline(self, agent: QueryExpanderAgent) -> None:
        """Baseline family should always pass relevance validation."""
        families = [
            QueryFamily(query="original query", family="baseline", intent_tags=["baseline"]),
        ]
        validated = agent.validate_relevance("original query", families)
        assert len(validated) == 1
        assert validated[0].family == "baseline"

    def test_validate_relevance_filters_low_overlap(self, agent: QueryExpanderAgent) -> None:
        """Families with insufficient term overlap should be filtered."""
        original = "market structure analysis"
        families = [
            QueryFamily(query="completely unrelated topic xyz", family="other", intent_tags=[]),
            QueryFamily(query=original, family="baseline", intent_tags=[]),
            QueryFamily(query="market analysis framework", family="analysis", intent_tags=[]),
        ]
        validated = agent.validate_relevance(original, families)
        assert any(f.family == "baseline" for f in validated)
        assert not any(f.family == "other" for f in validated)

    def test_deduplicate_families_removes_semantically_duplicate_non_baseline(self, agent: QueryExpanderAgent) -> None:
        """Semantically identical non-baseline families should be deduplicated; baseline always kept."""
        families = [
            QueryFamily(query="market structure analysis", family="baseline", intent_tags=["baseline"]),
            QueryFamily(query="market structure analysis report", family="expert-analysis", intent_tags=["analysis"]),
            QueryFamily(query="market structure analysis report", family="expert-analysis", intent_tags=["analysis"]),
        ]
        deduplicated = agent._deduplicate_families(families)
        assert len(deduplicated) == 2
        assert deduplicated[0].family == "baseline"

    def test_deduplicate_families_preserves_all_baselines(self, agent: QueryExpanderAgent) -> None:
        """All baseline families are preserved (deduplication skips baseline family type)."""
        families = [
            QueryFamily(query="same query", family="baseline", intent_tags=["baseline"]),
            QueryFamily(query="same query", family="baseline", intent_tags=["baseline"]),
        ]
        deduplicated = agent._deduplicate_families(families)
        # Code always keeps baseline regardless of signature
        assert len(deduplicated) == 2
        assert all(f.family == "baseline" for f in deduplicated)

    def test_significant_terms_extracts_content_words(self, agent: QueryExpanderAgent) -> None:
        """Should extract meaningful terms, excluding stop words."""
        terms = agent._significant_terms("the quantum computing algorithm")
        assert "quantum" in terms
        assert "computing" in terms
        assert "algorithm" in terms
        assert "the" not in terms
        assert "and" not in terms

    def test_significant_terms_normalizes_synonyms(self, agent: QueryExpanderAgent) -> None:
        """Should normalize known synonyms to canonical forms."""
        terms = agent._significant_terms("expert analysis report")
        assert "analysis" in terms
        assert "expert" not in terms  # normalized to "analysis"

    def test_semantic_signature_is_stable(self, agent: QueryExpanderAgent) -> None:
        """Same query should produce identical signature."""
        sig1 = agent._semantic_signature("market structure analysis")
        sig2 = agent._semantic_signature("market structure analysis")
        assert sig1 == sig2

    def test_semantic_signature_orders_terms(self, agent: QueryExpanderAgent) -> None:
        """Signature should be order-independent."""
        sig1 = agent._semantic_signature("analysis market structure")
        sig2 = agent._semantic_signature("structure market analysis")
        assert sig1 == sig2


class TestNormalizeQueryFamilies:
    """Tests for normalize_query_families helper."""

    def test_normalize_query_families_preserves_query_family_objects(self) -> None:
        """Already-typed QueryFamily objects should pass through unchanged."""
        from cc_deep_research.orchestration.helpers import normalize_query_families
        from cc_deep_research.models import StrategyResult, StrategyPlan

        strategy = StrategyResult(
            query="test query",
            complexity="simple",
            depth=ResearchDepth.QUICK,
            profile={},
            strategy=StrategyPlan(
                query_variations=1,
                max_sources=5,
                enable_cross_ref=False,
                enable_quality_scoring=False,
                tasks=[],
                intent="informational",
                time_sensitive=False,
                key_terms=[],
                target_source_classes=[],
            ),
            tasks_needed=[],
        )
        original = QueryFamily(query="test query", family="custom", intent_tags=["custom"])
        families = normalize_query_families(
            original_query="test query",
            strategy=strategy,
            raw_families=[original],
        )
        assert families[0] is original
        assert families[0].family == "custom"

    def test_normalize_query_families_labels_string_as_normalized(self) -> None:
        """Plain strings should be wrapped as 'normalized' family."""
        from cc_deep_research.orchestration.helpers import normalize_query_families
        from cc_deep_research.models import StrategyResult, StrategyPlan

        strategy = StrategyResult(
            query="test query",
            complexity="simple",
            depth=ResearchDepth.QUICK,
            profile={},
            strategy=StrategyPlan(
                query_variations=1,
                max_sources=5,
                enable_cross_ref=False,
                enable_quality_scoring=False,
                tasks=[],
                intent="informational",
                time_sensitive=False,
                key_terms=[],
                target_source_classes=[],
            ),
            tasks_needed=[],
        )
        families = normalize_query_families(
            original_query="test query",
            strategy=strategy,
            raw_families=["different query string"],
        )
        assert len(families) == 1
        assert families[0].family == "normalized"
        assert families[0].query == "different query string"

    def test_normalize_query_families_labels_original_query_as_baseline(self) -> None:
        """Strings matching original query should be labeled 'baseline'."""
        from cc_deep_research.orchestration.helpers import normalize_query_families
        from cc_deep_research.models import StrategyResult, StrategyPlan

        strategy = StrategyResult(
            query="original",
            complexity="simple",
            depth=ResearchDepth.QUICK,
            profile={},
            strategy=StrategyPlan(
                query_variations=1,
                max_sources=5,
                enable_cross_ref=False,
                enable_quality_scoring=False,
                tasks=[],
                intent="comparative",
                time_sensitive=False,
                key_terms=[],
                target_source_classes=[],
            ),
            tasks_needed=[],
        )
        families = normalize_query_families(
            original_query="original",
            strategy=strategy,
            raw_families=["original"],
        )
        assert families[0].family == "baseline"
