"""Theme-specific prompt templates for research agents."""

from __future__ import annotations

from .models import ResearchTheme


# Theme-specific prompt prefixes for the analyzer agent
ANALYZER_PROMPT_PREFIXES: dict[ResearchTheme, str] = {
    ResearchTheme.GENERAL: """You are analyzing research sources to extract comprehensive insights.
Focus on identifying key themes, findings, and knowledge gaps.
Provide balanced analysis with supporting evidence.""",
    ResearchTheme.RESOURCES_GATHERING: """You are categorizing and organizing research resources.
Focus on grouping resources by category, topic, and utility.
Highlight the most valuable resources and explain their relevance.""",
    ResearchTheme.TRIP_PLANNING: """You are analyzing travel information to help plan a trip.
Focus on practical logistics: transportation, accommodation, attractions, and timing.
Provide actionable recommendations with specific details.""",
    ResearchTheme.BUSINESS_DUE_DILIGENCE: """You are conducting business due diligence analysis.
Focus on financial health, risk factors, competitive position, and growth prospects.
Prioritize official sources and verify claims with evidence.""",
    ResearchTheme.MARKET_RESEARCH: """You are analyzing market and competitive landscape.
Focus on market size, trends, competitor positioning, and growth opportunities.
Include quantitative data where available and cite sources.""",
    ResearchTheme.BUSINESS_IDEA_GENERATION: """You are evaluating business opportunities and ideas.
Focus on market potential, feasibility, competitive advantages, and risks.
Provide practical insights on implementation and go-to-market strategy.""",
    ResearchTheme.CONTENT_CREATION: """You are researching to support content creation.
Focus on identifying content angles, audience interests, and trending topics.
Suggest hooks, structures, and key points for the content.""",
}

# Theme-specific prompt prefixes for the deep analyzer agent
DEEP_ANALYZER_PROMPT_PREFIXES: dict[ResearchTheme, str] = {
    ResearchTheme.GENERAL: """You are performing deep analysis to uncover nuanced insights.
Look for non-obvious patterns, connections, and implications.
Challenge assumptions and consider alternative interpretations.""",
    ResearchTheme.RESOURCES_GATHERING: """You are evaluating resource quality and relevance.
Assess the credibility and utility of each resource.
Identify gaps in the resource collection and suggest additions.""",
    ResearchTheme.TRIP_PLANNING: """You are refining travel recommendations with detailed insights.
Consider seasonal factors, local tips, and practical considerations.
Identify potential issues and provide contingency suggestions.""",
    ResearchTheme.BUSINESS_DUE_DILIGENCE: """You are performing deep risk and opportunity analysis.
Examine financial trends, competitive threats, and strategic risks.
Identify red flags and areas requiring further investigation.""",
    ResearchTheme.MARKET_RESEARCH: """You are synthesizing market intelligence into strategic insights.
Analyze competitive dynamics, market drivers, and future trends.
Provide actionable recommendations for market positioning.""",
    ResearchTheme.BUSINESS_IDEA_GENERATION: """You are validating and refining business concepts.
Assess market fit, scalability, and execution challenges.
Suggest pivots or improvements based on market evidence.""",
    ResearchTheme.CONTENT_CREATION: """You are developing content strategy and structure.
Identify the strongest angles and most engaging hooks.
Suggest content structure and key points to emphasize.""",
}

# Theme-specific system prompts (complete replacements)
ANALYZER_SYSTEM_PROMPTS: dict[ResearchTheme, str] = {
    ResearchTheme.TRIP_PLANNING: """You are a travel research analyst specializing in trip planning.
Your role is to synthesize travel information into actionable itineraries and recommendations.
Focus on practical details: logistics, timing, costs, and local insights.
Always consider traveler experience, safety, and value.""",
    ResearchTheme.BUSINESS_DUE_DILIGENCE: """You are a financial analyst conducting due diligence research.
Your role is to evaluate companies and investments for risk and opportunity.
Focus on financials, competitive position, management quality, and market dynamics.
Maintain objectivity and support all claims with evidence from credible sources.""",
    ResearchTheme.MARKET_RESEARCH: """You are a market research analyst specializing in competitive intelligence.
Your role is to analyze markets, competitors, and industry trends.
Provide quantitative insights where possible and strategic recommendations.
Support analysis with data from multiple credible sources.""",
}

DEEP_ANALYZER_SYSTEM_PROMPTS: dict[ResearchTheme, str] = {
    ResearchTheme.BUSINESS_DUE_DILIGENCE: """You are a senior investment analyst performing deep due diligence.
Your role is to identify risks, validate claims, and assess long-term prospects.
Look beyond surface-level information to uncover hidden issues and opportunities.
Maintain skepticism and verify all claims against multiple sources.""",
    ResearchTheme.MARKET_RESEARCH: """You are a senior market strategist conducting in-depth market analysis.
Your role is to synthesize market intelligence into strategic recommendations.
Identify emerging trends, competitive dynamics, and market opportunities.
Provide actionable insights backed by quantitative and qualitative evidence.""",
}


def get_theme_prompt_overrides(theme: ResearchTheme) -> dict[str, dict[str, str | None]]:
    """Get prompt overrides for a specific theme.

    Args:
        theme: The research theme.

    Returns:
        Dictionary of agent_id -> {system_prompt, prompt_prefix} overrides.
    """
    overrides: dict[str, dict[str, str | None]] = {}

    # Analyzer overrides
    analyzer_prefix = ANALYZER_PROMPT_PREFIXES.get(theme)
    analyzer_system = ANALYZER_SYSTEM_PROMPTS.get(theme)

    if analyzer_prefix or analyzer_system:
        overrides["analyzer"] = {
            "system_prompt": analyzer_system,
            "prompt_prefix": analyzer_prefix,
        }

    # Deep analyzer overrides
    deep_prefix = DEEP_ANALYZER_PROMPT_PREFIXES.get(theme)
    deep_system = DEEP_ANALYZER_SYSTEM_PROMPTS.get(theme)

    if deep_prefix or deep_system:
        overrides["deep_analyzer"] = {
            "system_prompt": deep_system,
            "prompt_prefix": deep_prefix,
        }

    return overrides


def get_analyzer_prompt_prefix(theme: ResearchTheme) -> str | None:
    """Get the analyzer prompt prefix for a theme.

    Args:
        theme: The research theme.

    Returns:
        The prompt prefix or None.
    """
    return ANALYZER_PROMPT_PREFIXES.get(theme)


def get_deep_analyzer_prompt_prefix(theme: ResearchTheme) -> str | None:
    """Get the deep analyzer prompt prefix for a theme.

    Args:
        theme: The research theme.

    Returns:
        The prompt prefix or None.
    """
    return DEEP_ANALYZER_PROMPT_PREFIXES.get(theme)


def get_analyzer_system_prompt(theme: ResearchTheme) -> str | None:
    """Get the analyzer system prompt for a theme.

    Args:
        theme: The research theme.

    Returns:
        The system prompt or None.
    """
    return ANALYZER_SYSTEM_PROMPTS.get(theme)


def get_deep_analyzer_system_prompt(theme: ResearchTheme) -> str | None:
    """Get the deep analyzer system prompt for a theme.

    Args:
        theme: The research theme.

    Returns:
        The system prompt or None.
    """
    return DEEP_ANALYZER_SYSTEM_PROMPTS.get(theme)


__all__ = [
    "ANALYZER_PROMPT_PREFIXES",
    "ANALYZER_SYSTEM_PROMPTS",
    "DEEP_ANALYZER_PROMPT_PREFIXES",
    "DEEP_ANALYZER_SYSTEM_PROMPTS",
    "get_theme_prompt_overrides",
    "get_analyzer_prompt_prefix",
    "get_deep_analyzer_prompt_prefix",
    "get_analyzer_system_prompt",
    "get_deep_analyzer_system_prompt",
]
