"""CC Deep Research CLI - Comprehensive web research tool."""

__version__ = "0.1.0"
__author__ = "CC Deep Research Team"

from cc_deep_research.models import (
    APIKey,
    ResearchDepth,
    ResearchSession,
    SearchOptions,
    SearchResult,
    SearchResultItem,
)
from cc_deep_research.orchestrator import TeamResearchOrchestrator
from cc_deep_research.providers import SearchProvider
from cc_deep_research.teams import ResearchTeam

__all__ = [
    "__version__",
    "__author__",
    "APIKey",
    "ResearchDepth",
    "ResearchSession",
    "SearchResult",
    "SearchResultItem",
    "SearchOptions",
    "SearchProvider",
    "ResearchTeam",
    "TeamResearchOrchestrator",
]
