"""Theme-based research system for tailored workflows.

This module provides theme detection and workflow configuration for
different types of research queries. Each theme has its own optimized
workflow with specific phases, source requirements, and prompts.

Usage:
    from cc_deep_research.themes import (
        ResearchTheme,
        ThemeDetector,
        ThemeRegistry,
        get_workflow_config,
    )

    # Detect theme from query
    detector = ThemeDetector()
    result = detector.detect("trip to Japan")
    print(result.detected_theme)  # ResearchTheme.TRIP_PLANNING

    # Get workflow configuration
    config = get_workflow_config(ResearchTheme.TRIP_PLANNING)
    print(config.phases)  # ['strategy', 'expand', 'collect', 'analyze', 'report']
"""

from .detector import ThemeDetector
from .models import DetectionResult, PhaseConfig, ResearchTheme, SourceRequirements, WorkflowConfig
from .presets import (
    BUILTIN_PRESETS,
    get_business_ideas_workflow,
    get_content_creation_workflow,
    get_due_diligence_workflow,
    get_general_workflow,
    get_market_research_workflow,
    get_preset,
    get_resources_workflow,
    get_trip_planning_workflow,
    list_presets,
)
from .prompts import (
    ANALYZER_PROMPT_PREFIXES,
    ANALYZER_SYSTEM_PROMPTS,
    DEEP_ANALYZER_PROMPT_PREFIXES,
    DEEP_ANALYZER_SYSTEM_PROMPTS,
    get_analyzer_prompt_prefix,
    get_analyzer_system_prompt,
    get_deep_analyzer_prompt_prefix,
    get_deep_analyzer_system_prompt,
    get_theme_prompt_overrides,
)
from .registry import ThemeRegistry, get_theme_registry
from .source_requirements import (
    THEME_SOURCE_REQUIREMENTS,
    adjust_for_depth,
    get_source_requirements,
)
from .workflow_adapter import ThemeWorkflowAdapter


def get_workflow_config(theme: ResearchTheme) -> WorkflowConfig:
    """Get workflow configuration for a theme.

    Convenience function using the global registry.

    Args:
        theme: The research theme.

    Returns:
        The workflow configuration.
    """
    registry = get_theme_registry()
    return registry.get_config(theme)


def detect_theme(query: str) -> DetectionResult:
    """Detect theme from a research query.

    Convenience function using a default detector.

    Args:
        query: The research query.

    Returns:
        Detection result with theme and confidence.
    """
    detector = ThemeDetector()
    return detector.detect(query)


__all__ = [
    # Models
    "ResearchTheme",
    "SourceRequirements",
    "PhaseConfig",
    "WorkflowConfig",
    "DetectionResult",
    # Detector
    "ThemeDetector",
    # Registry
    "ThemeRegistry",
    "get_theme_registry",
    # Presets
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
    # Prompts
    "ANALYZER_PROMPT_PREFIXES",
    "ANALYZER_SYSTEM_PROMPTS",
    "DEEP_ANALYZER_PROMPT_PREFIXES",
    "DEEP_ANALYZER_SYSTEM_PROMPTS",
    "get_theme_prompt_overrides",
    "get_analyzer_prompt_prefix",
    "get_deep_analyzer_prompt_prefix",
    "get_analyzer_system_prompt",
    "get_deep_analyzer_system_prompt",
    # Source requirements
    "THEME_SOURCE_REQUIREMENTS",
    "get_source_requirements",
    "adjust_for_depth",
    # Workflow adapter
    "ThemeWorkflowAdapter",
    # Convenience functions
    "get_workflow_config",
    "detect_theme",
]
