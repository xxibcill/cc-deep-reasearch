# AGENT.md

This file provides guidance to LLM agents when working with code in this repository.

Use Playwright as your eyes to inspect the UI, verify behavior, and fix frontend-side code issues based on what you observe in the browser.

## Project Overview

CC Deep Research is a CLI tool that performs comprehensive web research using multiple specialized AI agents working together. It combines Tavily's professional web search API with Claude Code's built-in search capabilities.

## Development Commands

### Primary Development Workflow (uv - Recommended)

```bash
# Install dependencies and sync environment (one-time)
uv sync

# Run CLI during development - changes reflect immediately
uv run cc-deep-research research "query"

# Run tests
uv run pytest

# Run specific test
uv run pytest tests/test_orchestrator.py

# Run linting
uv run ruff check src/ tests/

# Format code
uv run ruff format src/ tests/

# Type checking
uv run mypy src/

# Add a new dependency
uv add package-name

# Add a dev dependency
uv add --dev package-name
```

### Alternative Development Methods

```bash
# Editable install with pip
pip install -e .
cc-deep-research research "query"

# Run as Python module directly
python -m cc_deep_research.cli research "query"

# With uv
uv run python -m cc_deep_research.cli research "query"
```

## Architecture

### Core Components

1. **Orchestrator** ([orchestrator.py](src/cc_deep_research/orchestrator.py)) - `TeamResearchOrchestrator` coordinates the entire research workflow using specialized agents in phases:
   - Phase 1: Analyze query and determine strategy (ResearchLeadAgent)
   - Phase 2: Expand queries for comprehensive coverage (QueryExpanderAgent)
   - Phase 3: Collect sources from providers (SourceCollectorAgent)
   - Phase 4: Analyze findings (AnalyzerAgent)
   - Phase 5: Validate quality (ValidatorAgent)

2. **Agent System** ([agents/](src/cc_deep_research/agents/)) - Specialized research agents:
   - `ResearchLeadAgent`: Analyzes query complexity and determines research strategy
   - `SourceCollectorAgent`: Gathers sources from configured search providers (Tavily, Claude)
   - `QueryExpanderAgent`: Generates query variations for comprehensive coverage
   - `AnalyzerAgent`: Synthesizes and analyzes collected information
   - `ReporterAgent`: Generates final research reports
   - `ValidatorAgent`: Validates research quality and completeness

3. **Team Management** ([teams/research_team.py](src/cc_deep_research/teams/research_team.py)) - `ResearchTeam` wraps Claude's Agent Team functionality for coordinated parallel execution of agents.

4. **Configuration** ([config.py](src/cc_deep_research/config.py)) - Pydantic-based configuration with:
   - Environment variable support (e.g., `TAVILY_API_KEYS`)
   - YAML config file at `~/.config/cc-deep-research/config.yaml`
   - CLI command: `cc-deep-research config set/show/init`

5. **Search Providers** ([providers/](src/cc_deep_research/providers/)) - Abstracted search interfaces:
   - Tavily provider with API key rotation and rate limiting
   - Claude provider using WebSearch tool
   - Hybrid parallel mode runs both simultaneously

6. **Reporting** ([reporting.py](src/cc_deep_research/reporting.py)) - Generates markdown and JSON reports with citations, executive summaries, and cross-reference analysis.

7. **Monitoring** ([monitoring.py](src/cc_deep_research/monitoring.py)) - Internal workflow tracking with `--monitor` flag for debugging research execution.

### Research Modes

- **Quick**: 3-5 sources, 1-2 minutes - Fact-checking, basic queries
- **Standard**: 10-15 sources, 3-5 minutes - General research, overviews
- **Deep** (default): 20+ sources, 5-10 minutes - Thorough research, detailed understanding

### CLI Entry Point

[cli.py](src/cc_deep_research/cli.py) uses Click for command parsing:
- `cc-deep-research research "query"` - Main research command
- `cc-deep-research config set/show/init` - Configuration management

## Key Patterns

### Agent Execution Flow

Agents are instantiated in the orchestrator's `_initialize_team()` method and called sequentially in phases. Each agent has a specific interface (e.g., `analyze_query()`, `collect_sources()`, `validate_research()`).

### Async Operations

The orchestrator uses async/await throughout. Search operations, particularly in SourceCollectorAgent, are async to support parallel provider execution.

### Configuration Hierarchy

Configuration is loaded in this priority:
1. CLI flags (highest priority)
2. Environment variables (e.g., `TAVILY_API_KEYS`)
3. Config file (`~/.config/cc-deep-research/config.yaml`)
4. Defaults (lowest priority)

### Search Mode

`HYBRID_PARALLEL` mode (default) runs Tavily and Claude searches simultaneously. Use `--tavily-only` or `--claude-only` to restrict to single provider.

## Testing

Tests are located in [tests/](tests/). Run with:

```bash
uv run pytest
```

For async tests, pytest-asyncio is configured with `asyncio_mode = "auto"`.
