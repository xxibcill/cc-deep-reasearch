"""Built-in theme configuration presets."""

from __future__ import annotations

from .models import PhaseConfig, ResearchTheme, SourceRequirements, WorkflowConfig


def get_general_workflow() -> WorkflowConfig:
    """Get the general research workflow configuration.

    This is the default full pipeline with all phases enabled.
    """
    return WorkflowConfig(
        theme=ResearchTheme.GENERAL,
        display_name="General Research",
        description="Comprehensive research with full analysis pipeline",
        phases=["strategy", "expand", "collect", "analyze", "validate", "report"],
        source_requirements=SourceRequirements(
            min_sources=10,
            preferred_source_types=["web", "academic", "news"],
            prioritize_official_sources=False,
            credibility_threshold=0.5,
        ),
        skip_deep_analysis=False,
        skip_validation=False,
    )


def get_resources_workflow() -> WorkflowConfig:
    """Get the resources gathering workflow configuration.

    Focuses on collecting links and tools with minimal analysis.
    """
    return WorkflowConfig(
        theme=ResearchTheme.RESOURCES_GATHERING,
        display_name="Resources Gathering",
        description="Collect links, tools, and resources with categorization",
        phases=["strategy", "expand", "collect", "categorize", "report"],
        phase_configs={
            "analyze": PhaseConfig(enabled=False),
            "validate": PhaseConfig(enabled=False),
            "categorize": PhaseConfig(
                enabled=True,
                weight=1.5,
                additional_params={"focus": "resource_categorization"},
            ),
        },
        source_requirements=SourceRequirements(
            min_sources=15,
            preferred_source_types=["web"],
            prioritize_official_sources=False,
            credibility_threshold=0.4,
        ),
        skip_deep_analysis=True,
        skip_validation=True,
        output_template="resources_report",
    )


def get_trip_planning_workflow() -> WorkflowConfig:
    """Get the trip planning workflow configuration.

    Location/time-aware with practical logistics focus.
    """
    return WorkflowConfig(
        theme=ResearchTheme.TRIP_PLANNING,
        display_name="Trip Planning",
        description="Plan travel with logistics, attractions, and practical tips",
        phases=["strategy", "expand", "collect", "analyze", "report"],
        phase_configs={
            "collect": PhaseConfig(
                enabled=True,
                weight=1.3,
                additional_params={
                    "focus_areas": ["logistics", "attractions", "accommodation", "transportation"],
                },
            ),
            "analyze": PhaseConfig(
                enabled=True,
                weight=1.2,
                additional_params={
                    "output_format": "itinerary",
                    "include_practical_tips": True,
                },
            ),
            "validate": PhaseConfig(enabled=False),
        },
        source_requirements=SourceRequirements(
            min_sources=12,
            preferred_source_types=["web", "news"],
            prioritize_official_sources=False,
            credibility_threshold=0.5,
        ),
        agent_configs={
            "expander": {
                "additional_query_types": [
                    "hotels in",
                    "restaurants in",
                    "things to do",
                    "best time to visit",
                    "transportation options",
                ],
            },
        },
        skip_deep_analysis=True,
        skip_validation=True,
        output_template="trip_planning_report",
    )


def get_due_diligence_workflow() -> WorkflowConfig:
    """Get the business due diligence workflow configuration.

    Prioritizes official sources with risk analysis focus.
    """
    return WorkflowConfig(
        theme=ResearchTheme.BUSINESS_DUE_DILIGENCE,
        display_name="Business Due Diligence",
        description="Research companies and investments with risk analysis",
        phases=["strategy", "collect", "analyze", "validate", "report"],
        phase_configs={
            "collect": PhaseConfig(
                enabled=True,
                weight=1.4,
                additional_params={
                    "prioritize_official": True,
                    "include_filings": True,
                },
            ),
            "analyze": PhaseConfig(
                enabled=True,
                weight=1.5,
                additional_params={
                    "focus": "risk_analysis",
                    "include_financial_metrics": True,
                },
            ),
            "validate": PhaseConfig(
                enabled=True,
                weight=1.3,
                additional_params={"check_credibility": True},
            ),
        },
        source_requirements=SourceRequirements(
            min_sources=15,
            preferred_source_types=["official", "news", "academic"],
            prioritize_official_sources=True,
            credibility_threshold=0.7,
        ),
        agent_configs={
            "expander": {
                "additional_query_types": [
                    "financial statements",
                    "SEC filings",
                    "annual report",
                    "company profile",
                    "executive team",
                ],
            },
            "analyzer": {
                "analysis_focus": ["financials", "risks", "competitive_position", "management"],
            },
        },
        skip_deep_analysis=False,
        skip_validation=False,
        output_template="due_diligence_report",
    )


def get_market_research_workflow() -> WorkflowConfig:
    """Get the market research workflow configuration.

    Focus on competitive landscape and market sizing.
    """
    return WorkflowConfig(
        theme=ResearchTheme.MARKET_RESEARCH,
        display_name="Market Research",
        description="Analyze markets, competitors, and industry trends",
        phases=["strategy", "expand", "collect", "analyze", "validate", "report"],
        phase_configs={
            "collect": PhaseConfig(
                enabled=True,
                weight=1.3,
                additional_params={
                    "focus_areas": ["competitors", "market_size", "trends", "customers"],
                },
            ),
            "analyze": PhaseConfig(
                enabled=True,
                weight=1.5,
                additional_params={
                    "include_competitive_analysis": True,
                    "include_market_sizing": True,
                    "include_trend_analysis": True,
                },
            ),
            "validate": PhaseConfig(
                enabled=True,
                additional_params={"cross_reference_sources": True},
            ),
        },
        source_requirements=SourceRequirements(
            min_sources=20,
            preferred_source_types=["academic", "official", "news", "web"],
            prioritize_official_sources=False,
            credibility_threshold=0.6,
        ),
        agent_configs={
            "expander": {
                "additional_query_types": [
                    "market size",
                    "market share",
                    "industry report",
                    "competitive landscape",
                    "growth rate",
                ],
            },
        },
        skip_deep_analysis=False,
        skip_validation=False,
        output_template="market_research_report",
    )


def get_business_ideas_workflow() -> WorkflowConfig:
    """Get the business idea generation workflow configuration.

    Brainstorming focus with opportunity analysis.
    """
    return WorkflowConfig(
        theme=ResearchTheme.BUSINESS_IDEA_GENERATION,
        display_name="Business Idea Generation",
        description="Generate and evaluate business opportunities",
        phases=["strategy", "expand", "collect", "analyze", "report"],
        phase_configs={
            "expand": PhaseConfig(
                enabled=True,
                weight=1.4,
                additional_params={"creative_mode": True},
            ),
            "collect": PhaseConfig(
                enabled=True,
                additional_params={
                    "focus_areas": ["trends", "pain_points", "opportunities", "successful_models"],
                },
            ),
            "analyze": PhaseConfig(
                enabled=True,
                weight=1.5,
                additional_params={
                    "output_format": "idea_evaluation",
                    "include_feasibility": True,
                    "include_market_potential": True,
                },
            ),
            "validate": PhaseConfig(enabled=False),
        },
        source_requirements=SourceRequirements(
            min_sources=12,
            preferred_source_types=["web", "news"],
            prioritize_official_sources=False,
            credibility_threshold=0.4,
        ),
        agent_configs={
            "expander": {
                "additional_query_types": [
                    "successful startups",
                    "emerging trends",
                    "market gaps",
                    "profitable niches",
                ],
            },
        },
        skip_deep_analysis=True,
        skip_validation=True,
        output_template="business_ideas_report",
    )


def get_content_creation_workflow() -> WorkflowConfig:
    """Get the content creation workflow configuration.

    Content structure and strategy output.
    """
    return WorkflowConfig(
        theme=ResearchTheme.CONTENT_CREATION,
        display_name="Content Creation",
        description="Research for creating content with structure and strategy",
        phases=["strategy", "collect", "analyze", "report"],
        phase_configs={
            "expand": PhaseConfig(enabled=False),
            "collect": PhaseConfig(
                enabled=True,
                additional_params={
                    "focus_areas": ["inspiration", "competitor_content", "trending_topics"],
                },
            ),
            "analyze": PhaseConfig(
                enabled=True,
                weight=1.5,
                additional_params={
                    "output_format": "content_outline",
                    "include_angles": True,
                    "include_hooks": True,
                },
            ),
            "validate": PhaseConfig(enabled=False),
        },
        source_requirements=SourceRequirements(
            min_sources=8,
            preferred_source_types=["web", "social"],
            prioritize_official_sources=False,
            credibility_threshold=0.4,
        ),
        agent_configs={
            "analyzer": {
                "analysis_focus": ["content_angles", "audience_insights", "seo_opportunities"],
            },
        },
        skip_deep_analysis=True,
        skip_validation=True,
        output_template="content_creation_report",
    )


# Registry of all built-in presets
BUILTIN_PRESETS: dict[ResearchTheme, WorkflowConfig] = {
    ResearchTheme.GENERAL: get_general_workflow(),
    ResearchTheme.RESOURCES_GATHERING: get_resources_workflow(),
    ResearchTheme.TRIP_PLANNING: get_trip_planning_workflow(),
    ResearchTheme.BUSINESS_DUE_DILIGENCE: get_due_diligence_workflow(),
    ResearchTheme.MARKET_RESEARCH: get_market_research_workflow(),
    ResearchTheme.BUSINESS_IDEA_GENERATION: get_business_ideas_workflow(),
    ResearchTheme.CONTENT_CREATION: get_content_creation_workflow(),
}


def get_preset(theme: ResearchTheme) -> WorkflowConfig | None:
    """Get a built-in preset by theme.

    Args:
        theme: The theme to get the preset for.

    Returns:
        The workflow config preset, or None if not found.
    """
    return BUILTIN_PRESETS.get(theme)


def list_presets() -> list[dict[str, str]]:
    """List all available presets with metadata.

    Returns:
        List of dictionaries with theme info.
    """
    return [
        {
            "theme": config.theme.value,
            "display_name": config.display_name,
            "description": config.description,
        }
        for config in BUILTIN_PRESETS.values()
    ]


__all__ = [
    "BUILTIN_PRESETS",
    "get_general_workflow",
    "get_resources_workflow",
    "get_trip_planning_workflow",
    "get_due_diligence_workflow",
    "get_market_research_workflow",
    "get_business_ideas_workflow",
    "get_content_creation_workflow",
    "get_preset",
    "list_presets",
]
