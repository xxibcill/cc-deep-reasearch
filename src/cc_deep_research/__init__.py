"""Stable package-root exports for CC Deep Research."""

from cc_deep_research.__about__ import __version__
from cc_deep_research.models import (
    ResearchDepth,
    ResearchSession,
    SearchOptions,
    SearchResult,
    SearchResultItem,
)
from cc_deep_research.orchestrator import TeamResearchOrchestrator
from cc_deep_research.providers import SearchProvider

__author__ = "CC Deep Research Team"

__all__ = [
    "__version__",
    "__author__",
    "ResearchDepth",
    "ResearchSession",
    "SearchResult",
    "SearchResultItem",
    "SearchOptions",
    "SearchProvider",
    "TeamResearchOrchestrator",
]
