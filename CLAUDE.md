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

## GitHub CI Fix Prompt

Use this prompt when asking Claude Code to repair the current GitHub Actions failures:

```text
Fix the failing GitHub CI on branch refactor-phase-2 for PR #24. Work from the
actual latest Actions logs first, then make the smallest code changes needed.

Start by checking the current failures:

gh run list --limit 5 --json databaseId,headBranch,headSha,status,conclusion,workflowName,displayTitle,createdAt,updatedAt,url
gh run view <latest-preflight-run-id> --log-failed
gh run view <latest-dashboard-run-id> --log-failed

As of May 2, 2026, the latest observed failures were:

- Preflight CI run 25255931107 on commit 0a100600eedc1df6457e6045a87371e07bd5f232.
  It failed at `uv run ruff check src/ tests/` with 10 fixable lint errors:
  `src/cc_deep_research/knowledge/ingest.py` imports `Callable` from `typing`
  instead of `collections.abc`; `tests/test_content_gen_contracts.py` has an
  unsorted import block, an unused `ContentGenStageContract` import, and no
  trailing newline; `tests/test_content_gen_lane_state.py` has unused
  `AsyncMock`/`patch` imports, two B009 `getattr(..., "constant")` cases, and
  unsorted local import blocks in fixtures.

- Dashboard CI run 25255931098 on the same commit.
  It passed install and lint, then failed during `npm run build` with a
  TypeScript error in `dashboard/src/components/knowledge/knowledge-graph.tsx`
  at `d3.forceLink(edgeData)`: the API edge objects have `source_id` and
  `target_id`, but D3 `SimulationLinkDatum` expects `source` and `target`.

Fix strategy:

1. Reproduce the Python failure locally:
   `uv sync`
   `uv run ruff check src/ tests/`
2. Apply the ruff-safe fixes. Prefer:
   `uv run ruff check src/ tests/ --fix`
   Then inspect the diff and make any remaining manual edits.
3. Fix the dashboard graph type mismatch by mapping API edges into a D3 link
   shape before passing them to `forceLink`, for example with local types that
   extend `d3.SimulationNodeDatum` and `d3.SimulationLinkDatum<GraphNode>`.
   Preserve the existing rendered behavior: edges still connect
   `source_id -> target_id`, node labels still render, selection still works,
   and the graph still has zoom.
4. Remove the loose `@ts-expect-error` in `getNodePositions` if the new local
   simulation node type makes it unnecessary.
5. Do not silence TypeScript or ruff, do not bypass CI steps, and do not treat
   the Node.js 20 action deprecation warning as the root cause. That warning is
   separate from the current failures.

Verify before finishing:

uv run ruff check src/ tests/
uv run mypy src/
uv run pytest tests/test_llm_analysis_client.py tests/test_models.py tests/test_reporter.py -v
uv run pytest tests/test_tavily_provider.py tests/test_providers.py -v
uv run pytest tests/test_orchestrator.py tests/test_orchestration.py -v
uv run pytest tests/test_research_run_service.py -v

cd dashboard
npm ci
npm run lint
npm run build
npx playwright install --with-deps chromium
npm run test:e2e:smoke
npm run test:a11y

If a later CI run shows a different first failure, update the diagnosis from
the latest logs and keep the same approach: reproduce locally, fix the root
cause, and rerun the workflow-equivalent commands.
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
