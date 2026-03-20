"""Tests for web search cache identity helpers."""

from cc_deep_research.models import ResearchDepth, SearchOptions
from cc_deep_research.search_cache import (
    build_search_cache_identity,
    build_search_cache_key,
    build_search_cache_signature,
)


def test_equivalent_requests_share_the_same_cache_identity() -> None:
    """Whitespace and casing differences should normalize to one cache signature."""
    first = build_search_cache_identity(
        provider_name=" Tavily ",
        query="  OpenAI   GPT-5  ",
        options=SearchOptions(
            max_results=10,
            include_raw_content=True,
            search_depth=ResearchDepth.DEEP,
        ),
    )
    second = build_search_cache_identity(
        provider_name="tavily",
        query="openai gpt-5",
        options=SearchOptions(
            max_results=10,
            include_raw_content=True,
            search_depth=ResearchDepth.DEEP,
        ),
    )

    assert first == second
    assert first.to_signature() == second.to_signature()
    assert first.to_cache_key() == second.to_cache_key()


def test_different_provider_strategies_generate_different_keys() -> None:
    """Configured provider strategies should not collide in the cache."""
    tavily_advanced = build_search_cache_key(
        provider_name="tavily",
        query="OpenAI GPT-5",
        options=SearchOptions(search_depth=ResearchDepth.DEEP),
    )
    tavily_basic = build_search_cache_key(
        provider_name="tavily_basic",
        query="OpenAI GPT-5",
        options=SearchOptions(search_depth=ResearchDepth.DEEP),
    )

    assert tavily_advanced != tavily_basic


def test_material_option_changes_change_the_signature() -> None:
    """Options that affect the result set should produce distinct identities."""
    base_signature = build_search_cache_signature(
        provider_name="tavily",
        query="OpenAI GPT-5",
        options=SearchOptions(
            max_results=10,
            include_raw_content=True,
            search_depth=ResearchDepth.DEEP,
        ),
    )

    assert base_signature != build_search_cache_signature(
        provider_name="tavily",
        query="OpenAI GPT-5",
        options=SearchOptions(
            max_results=5,
            include_raw_content=True,
            search_depth=ResearchDepth.DEEP,
        ),
    )
    assert base_signature != build_search_cache_signature(
        provider_name="tavily",
        query="OpenAI GPT-5",
        options=SearchOptions(
            max_results=10,
            include_raw_content=False,
            search_depth=ResearchDepth.DEEP,
        ),
    )
    assert base_signature != build_search_cache_signature(
        provider_name="tavily",
        query="OpenAI GPT-5",
        options=SearchOptions(
            max_results=10,
            include_raw_content=True,
            search_depth=ResearchDepth.QUICK,
        ),
    )
