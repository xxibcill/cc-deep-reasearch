"""Source requirements per theme for collection strategies."""

from __future__ import annotations

from .models import ResearchTheme, SourceRequirements

# Default source requirements per theme
THEME_SOURCE_REQUIREMENTS: dict[ResearchTheme, SourceRequirements] = {
    ResearchTheme.GENERAL: SourceRequirements(
        min_sources=10,
        preferred_source_types=["web", "academic", "news"],
        prioritize_official_sources=False,
        credibility_threshold=0.5,
    ),
    ResearchTheme.RESOURCES_GATHERING: SourceRequirements(
        min_sources=15,
        preferred_source_types=["web"],
        prioritize_official_sources=False,
        credibility_threshold=0.4,
    ),
    ResearchTheme.TRIP_PLANNING: SourceRequirements(
        min_sources=12,
        preferred_source_types=["web", "news"],
        prioritize_official_sources=False,
        credibility_threshold=0.5,
    ),
    ResearchTheme.BUSINESS_DUE_DILIGENCE: SourceRequirements(
        min_sources=15,
        preferred_source_types=["official", "news", "academic"],
        prioritize_official_sources=True,
        credibility_threshold=0.7,
    ),
    ResearchTheme.MARKET_RESEARCH: SourceRequirements(
        min_sources=20,
        preferred_source_types=["academic", "official", "news", "web"],
        prioritize_official_sources=False,
        credibility_threshold=0.6,
    ),
    ResearchTheme.BUSINESS_IDEA_GENERATION: SourceRequirements(
        min_sources=12,
        preferred_source_types=["web", "news"],
        prioritize_official_sources=False,
        credibility_threshold=0.4,
    ),
    ResearchTheme.CONTENT_CREATION: SourceRequirements(
        min_sources=8,
        preferred_source_types=["web", "social"],
        prioritize_official_sources=False,
        credibility_threshold=0.4,
    ),
}


def get_source_requirements(theme: ResearchTheme) -> SourceRequirements:
    """Get source requirements for a theme.

    Args:
        theme: The research theme.

    Returns:
        Source requirements configuration.
    """
    return THEME_SOURCE_REQUIREMENTS.get(
        theme,
        THEME_SOURCE_REQUIREMENTS[ResearchTheme.GENERAL],
    )


def adjust_for_depth(
    requirements: SourceRequirements,
    depth: str,
) -> SourceRequirements:
    """Adjust source requirements based on research depth.

    Args:
        requirements: Base source requirements.
        depth: Research depth (quick, standard, deep).

    Returns:
        Adjusted source requirements.
    """
    depth_multipliers = {
        "quick": 0.4,
        "standard": 0.7,
        "deep": 1.0,
    }

    multiplier = depth_multipliers.get(depth.lower(), 1.0)

    return SourceRequirements(
        min_sources=max(3, int(requirements.min_sources * multiplier)),
        preferred_source_types=requirements.preferred_source_types,
        prioritize_official_sources=requirements.prioritize_official_sources,
        credibility_threshold=requirements.credibility_threshold,
    )


__all__ = [
    "THEME_SOURCE_REQUIREMENTS",
    "get_source_requirements",
    "adjust_for_depth",
]
