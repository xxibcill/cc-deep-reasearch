"""Stable package-root exports for Inqulume Studio."""

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

__author__ = "Inqulume Studio Team"

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
