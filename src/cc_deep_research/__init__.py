"""CC Deep Research CLI - Comprehensive web research tool."""

from cc_deep_research.__about__ import __version__
from cc_deep_research.benchmark import (
    BenchmarkCase,
    BenchmarkCaseMetrics,
    BenchmarkCaseReport,
    BenchmarkCorpus,
    BenchmarkRunReport,
    BenchmarkScorecard,
    build_benchmark_case_report,
    build_benchmark_scorecard,
    default_benchmark_corpus_path,
    load_benchmark_corpus,
    run_benchmark_corpus,
    run_benchmark_corpus_sync,
    write_benchmark_report,
)
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
from cc_deep_research.text_normalization import (
    extract_full_sentence_around_keyword,
    is_complete_sentence,
    normalize_content,
)

__author__ = "CC Deep Research Team"

__all__ = [
    "__version__",
    "__author__",
    "BenchmarkCase",
    "BenchmarkCaseMetrics",
    "BenchmarkCaseReport",
    "BenchmarkCorpus",
    "BenchmarkRunReport",
    "BenchmarkScorecard",
    "APIKey",
    "ResearchDepth",
    "ResearchSession",
    "SearchResult",
    "SearchResultItem",
    "SearchOptions",
    "default_benchmark_corpus_path",
    "build_benchmark_case_report",
    "build_benchmark_scorecard",
    "load_benchmark_corpus",
    "run_benchmark_corpus",
    "run_benchmark_corpus_sync",
    "write_benchmark_report",
    "SearchProvider",
    "ResearchTeam",
    "TeamResearchOrchestrator",
    "extract_full_sentence_around_keyword",
    "is_complete_sentence",
    "normalize_content",
]
