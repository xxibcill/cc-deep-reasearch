"""Specialized research agents for CC Deep Research CLI.

This module provides agent implementations for different aspects of research:
- ResearchLead: Orchestrates overall research strategy
- SourceCollector: Gathers sources from configured providers
- QueryExpander: Expands queries for comprehensive coverage
- Analyzer: Analyzes and synthesizes collected information
- DeepAnalyzer: Performs multi-pass deep analysis with extended token usage
- Reporter: Generates final research reports
- Validator: Validates research quality and completeness
- AIAnalysisService: Provides AI-powered semantic analysis capabilities
"""

from cc_deep_research.agents.research_lead import ResearchLeadAgent
from cc_deep_research.agents.source_collector import SourceCollectorAgent
from cc_deep_research.agents.query_expander import QueryExpanderAgent
from cc_deep_research.agents.analyzer import AnalyzerAgent
from cc_deep_research.agents.deep_analyzer import DeepAnalyzerAgent
from cc_deep_research.agents.reporter import ReporterAgent
from cc_deep_research.agents.validator import ValidatorAgent
from cc_deep_research.agents.ai_analysis_service import AIAnalysisService

# Agent type constants
AGENT_TYPE_LEAD = "lead"
AGENT_TYPE_COLLECTOR = "collector"
AGENT_TYPE_EXPANDER = "expander"
AGENT_TYPE_ANALYZER = "analyzer"
AGENT_TYPE_DEEP_ANALYZER = "deep_analyzer"
AGENT_TYPE_REPORTER = "reporter"
AGENT_TYPE_VALIDATOR = "validator"

# Agent factory
AGENT_REGISTRY: dict[str, type] = {
    AGENT_TYPE_LEAD: ResearchLeadAgent,
    AGENT_TYPE_COLLECTOR: SourceCollectorAgent,
    AGENT_TYPE_EXPANDER: QueryExpanderAgent,
    AGENT_TYPE_ANALYZER: AnalyzerAgent,
    AGENT_TYPE_DEEP_ANALYZER: DeepAnalyzerAgent,
    AGENT_TYPE_REPORTER: ReporterAgent,
    AGENT_TYPE_VALIDATOR: ValidatorAgent,
}


def get_agent_class(agent_type: str) -> type | None:
    """Get agent class by type.

    Args:
        agent_type: Type identifier for the agent.

    Returns:
        Agent class if found, None otherwise.
    """
    return AGENT_REGISTRY.get(agent_type)


__all__ = [
    "ResearchLeadAgent",
    "SourceCollectorAgent",
    "QueryExpanderAgent",
    "AnalyzerAgent",
    "DeepAnalyzerAgent",
    "ReporterAgent",
    "ValidatorAgent",
    "AIAnalysisService",
    "AGENT_TYPE_LEAD",
    "AGENT_TYPE_COLLECTOR",
    "AGENT_TYPE_EXPANDER",
    "AGENT_TYPE_ANALYZER",
    "AGENT_TYPE_DEEP_ANALYZER",
    "AGENT_TYPE_REPORTER",
    "AGENT_TYPE_VALIDATOR",
    "get_agent_class",
]
