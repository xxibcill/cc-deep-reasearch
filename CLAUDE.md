# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CC Deep Research is a CLI tool for multi-stage web research using Tavily search, local specialist agents, session persistence, and telemetry analytics. It supports depth modes (quick, standard, deep), parallel source collection, LLM routing across multiple providers, and real-time dashboard monitoring.

## Development Commands

```bash
# Install dev dependencies
uv sync

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_orchestrator.py

# Run tests matching a pattern
uv run pytest -k "test_analyzer"

# Lint
uv run ruff check src/ tests/

# Format
uv run ruff format src/ tests/

# Type check
uv run mypy src/

# Run the full benchmark corpus
cc-deep-research benchmark run --depth standard --output-dir benchmark_runs/latest
```

## Architecture

### Core Workflow

The research pipeline is managed by two alternative orchestrators selected via `ResearchWorkflow`:

1. **`TeamResearchOrchestrator`** (`src/cc_deep_research/orchestrator.py`) - The **staged workflow** (default). Phases execute sequentially: strategy → query expansion → source collection → analysis → validation → report. Iterative follow-up collection can loop back based on validation.

2. **`PlannerResearchOrchestrator`** (`src/cc_deep_research/orchestration/planner_orchestrator.py`) - The **planner workflow**. Uses a Planner Agent to create a research plan with subtasks, then executes them via a TaskDispatcher.

The workflow is selected via `ResearchRunRequest.workflow` (defaults to `ResearchWorkflow.STAGED`). Both return a `ResearchSession`.

Key modules:
- `src/cc_deep_research/orchestrator.py` - `TeamResearchOrchestrator` (staged pipeline)
- `src/cc_deep_research/orchestration/planner_orchestrator.py` - `PlannerResearchOrchestrator` (planner-based pipeline)
- `src/cc_deep_research/orchestration/` - Phase execution services (phases.py, execution.py, runtime.py, session_state.py)
- `src/cc_deep_research/agents/` - Specialized agents (analyzer, deep_analyzer, reporter, validator, research_lead, query_expander, source_collector, planner)

### Concurrent Source Collection

Concurrent source collection (`concurrent_source_collection`) means **concurrent asyncio task execution in one process**, not spawned external agents. The `SourceCollectionService` fans out source collection to concurrent tasks when enabled.

### LLM Routing

Four transports: `anthropic_api`, `openrouter_api`, `cerebras_api`, `heuristic` (fallback). The route planner (`src/cc_deep_research/agents/llm_route_planner.py`) assigns routes per agent. Configuration lives in `~/.config/cc-deep-research/config.yaml` under `llm` section.

### Telemetry Architecture

`ResearchMonitor` is the telemetry sink. Events flow to:
- `~/.config/cc-deep-research/telemetry/<session_id>/events.jsonl` - Per-session JSONL
- `~/.config/cc-deep-research/telemetry/<session_id>/summary.json` - Session summary

Dashboards:
- `cc-deep-research telemetry dashboard` - Streamlit dashboard (requires `dashboard` extra)
- `cc-deep-research dashboard` + Next.js frontend - Real-time operator console

### Session Metadata Contract

`ResearchSession.metadata` has a stable structure with keys: `strategy`, `analysis`, `validation`, `iteration_history`, `providers`, `execution`, `deep_analysis`, `llm_routes`, `prompts`. This contract applies across all depth modes.

### Configuration

Config file: `~/.config/cc-deep-research/config.yaml`. Also supports env var overrides (e.g., `TAVILY_API_KEYS`, `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`, `CEREBRAS_API_KEY`). A `.env` file at project root is loaded without overwriting existing env vars.

### Content Generation

A separate content-gen workflow exists in `src/cc_deep_research/content_gen/` with its own telemetry store, models, and pipeline for short-form video content. This runs under a different entry point and is documented in `docs/content-generation/`. The `content_gen/` package is kept co-located within `cc_deep_research/` rather than split into a separate package because it shares the `llm/` routing infrastructure, `models/` data types, and `config/` schema with the research package. Splitting would duplicate these shared dependencies while providing no independent deployment benefit.

### Dashboard Frontend

The Next.js dashboard is in `dashboard/`. Start with `npm install && npm run dev` from that directory. It communicates with the FastAPI backend via `src/cc_deep_research/web_server.py`.

## Testing Conventions

- Tests live in `tests/`, mirroring the `src/cc_deep_research/` structure
- `pytest-asyncio` with `asyncio_mode = "auto"`
- `pythonpath = ["src"]` so imports use `cc_deep_research` package
- Key test files: `test_orchestrator.py`, `test_monitoring.py`, `test_telemetry.py`, `test_content_gen.py`, `test_llm_router.py`
