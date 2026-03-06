# CC Deep Research CLI

CLI for multi-stage web research using Tavily search, agent orchestration, session persistence, and telemetry analytics.

Current codebase version: `0.1.0`

## Features

- Multi-stage research workflow (strategy, query expansion, source collection, analysis, validation, reporting)
- Depth modes: `quick`, `standard`, `deep` (default)
- Parallel researcher execution with optional timeline view
- Source quality scoring and cross-reference analysis
- Session persistence with list/show/export/delete commands
- Telemetry ingestion to DuckDB and Streamlit dashboard
- Markdown and JSON report output, optional PDF export
- Config file + environment-variable driven settings

## Installation

### With uv (recommended)

```bash
uv pip install cc-deep-research
```

### With pip

```bash
pip install cc-deep-research
```

## Quick Start

```bash
# 1) Configure Tavily API key(s)
export TAVILY_API_KEYS=your_api_key_here

# 2) Run research
cc-deep-research research "What are the latest developments in quantum computing?"
```

## Command Overview

```bash
cc-deep-research [COMMAND]
```

Available command groups:

- `research` - Run a research query and generate report output
- `config` - Manage configuration (`show`, `set`, `init`)
- `session` - Manage persisted sessions (`list`, `show`, `export`, `delete`)
- `telemetry` - Ingest telemetry and launch dashboard (`ingest`, `dashboard`)

## Research Examples

```bash
# Default deep research
cc-deep-research research "AI chip supply chain risks in 2026"

# Quick mode
cc-deep-research research -d quick "What is the capital of Australia?"

# Override source target
cc-deep-research research -s 30 "Topic"

# Save markdown report
cc-deep-research research -o reports/topic.md "Topic"

# JSON output
cc-deep-research research --format json "Topic" > result.json

# Disable team mode (sequential)
cc-deep-research research --no-team "Topic"

# Parallel controls
cc-deep-research research --parallel-mode --num-researchers 4 --show-timeline "Topic"

# Telemetry monitor output during run
cc-deep-research research --monitor "Topic"

# Generate PDF in addition to report output
cc-deep-research research --pdf "Topic"
```

## Research Flags (Current)

- `-d, --depth [quick|standard|deep]`
- `-s, --sources INTEGER`
- `-o, --output FILE`
- `--format [markdown|json]`
- `--no-cross-ref`
- `--tavily-only`
- `--claude-only` (present but marked not yet implemented)
- `--no-team`
- `--team-size INTEGER`
- `--progress`
- `--quiet`
- `--verbose`
- `--monitor`
- `--parallel-mode`
- `--num-researchers INTEGER`
- `--show-timeline`
- `--pdf`

## Telemetry Dashboard

Telemetry files are written under:

- `~/.config/cc-deep-research/telemetry/<session_id>/events.jsonl`
- `~/.config/cc-deep-research/telemetry/<session_id>/summary.json`

Ingest and launch dashboard:

```bash
# Install dashboard dependencies
pip install "cc-deep-research[dashboard]"

# Ingest telemetry into DuckDB
cc-deep-research telemetry ingest

# Launch Streamlit dashboard
cc-deep-research telemetry dashboard --port 8501
```

## Session Management

```bash
# List recent sessions
cc-deep-research session list

# Show one session
cc-deep-research session show <session_id>

# Export an existing session
cc-deep-research session export <session_id> -o exported.md --format markdown

# Delete a session
cc-deep-research session delete <session_id>
```

## Configuration

Configuration file path:

- `~/.config/cc-deep-research/config.yaml`

Initialize/show/set:

```bash
cc-deep-research config init
cc-deep-research config show
cc-deep-research config set tavily.api_keys key1,key2,key3
```

Default highlights from current code:

- `search.providers: ["tavily"]`
- `research.default_depth: "deep"`
- `research.min_sources.deep: 50`
- `search_team.enabled: true`
- `search_team.parallel_execution: true`
- `search_team.num_researchers: 3`
- `output.format: "markdown"`

## Development

```bash
# Install dev environment
uv sync

# Run tests
uv run pytest

# Lint + format + type check
uv run ruff check src/ tests/
uv run ruff format src/ tests/
uv run mypy src/
```

## Documentation

- [Usage Guide](docs/USAGE.md)
- [Examples](docs/EXAMPLES.md)

## Requirements

- Python 3.11+
- Tavily API key(s)

## License

MIT
