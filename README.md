# CC Deep Research

Deep research platform with real-time dashboard monitoring. Conduct multi-stage web research using Tavily search, session persistence, and telemetry analytics.

Current codebase version: `0.1.0`

## Features

- Multi-stage research workflow (strategy, query expansion, source collection, analysis, validation, reporting)
- Depth modes: `quick`, `standard`, `deep`
- Parallel local source-collection tasks with dashboard monitoring
- Source quality scoring and cross-reference analysis
- Session persistence with full audit trail
- Real-time WebSocket event streaming
- Next.js operator console dashboard

## Installation

```bash
# Install dependencies
uv sync

# Install with dashboard dependencies
uv sync --extra dashboard
```

## Quick Start

```bash
# 1) Configure API keys
export TAVILY_API_KEYS=your_api_key_here

# 2) Start the dashboard
cd dashboard && npm install && npm run dev
```

This starts both the FastAPI backend (port 8000) and Next.js frontend (port 3000).

## Running the Backend Only

```bash
# Using the module entry point
python -m cc_deep_research

# Or with uvicorn directly
uv run uvicorn cc_deep_research.web_server:create_app --factory --ws websockets-sansio --port 8000
```

## Configuration

Configuration file: `~/.config/cc-deep-research/config.yaml`

Default settings:
- `search.providers: ["tavily"]`
- `research.default_depth: "deep"`
- `research.min_sources.deep: 50`
- `search_team.enabled: true`
- `search_team.parallel_execution: true`
- `search_team.num_researchers: 3`

Environment variable overrides:
- `TAVILY_API_KEYS`
- `ANTHROPIC_API_KEY`
- `OPENROUTER_API_KEY`
- `CEREBRAS_API_KEY`
- `CC_DEEP_RESEARCH_CONFIG`

## LLM Routing

CC Deep Research supports multiple LLM backends:

| Transport | Description |
|-----------|-------------|
| `anthropic_api` | Direct Claude API access |
| `openrouter_api` | Multi-model access via OpenRouter |
| `cerebras_api` | Fast inference via Cerebras |
| `heuristic` | Rule-based fallback |

Configure in `~/.config/cc-deep-research/config.yaml` under `llm` section.

## Development

```bash
# Install dev dependencies
uv sync

# Run tests
uv run pytest

# Lint + format + type check
uv run ruff check src/ tests/
uv run ruff format src/ tests/
uv run mypy src/
```

## Documentation

- [Dashboard Guide](docs/DASHELOG_GUIDE.md)
- [Content-Generation Workflow](docs/content-generation/content-generation.md)
- [Telemetry Architecture](docs/TELEMETRY.md)

## Requirements

- Python 3.11+
- Node.js 18+ (for dashboard)
- Tavily API key

## License

MIT
