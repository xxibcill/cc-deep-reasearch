# CC Deep Research CLI

A powerful deep research engine that builds on top of Claude Code, combining Tavily's professional web search API with Claude Code's built-in search capabilities.

## Features

- **Agent-Orchestrated Research** - Uses specialized workflow stages for planning, collection, analysis, validation, and reporting
- **Parallel Query Execution** - Runs independent research queries in parallel for faster source collection
- **Deep Dive Research** - Default mode with 20+ sources, cross-referencing, and comprehensive analysis
- **API Key Rotation** - Automatic management of multiple Tavily API keys with graceful failover
- **Smart Query Expansion** - Automatically generates query variations for comprehensive coverage
- **Iterative Search** - Analyzes gaps in results and performs validation-driven follow-up searches
- **Source Quality Scoring** - Evaluates and ranks sources by credibility, relevance, freshness, and diversity
- **Markdown Reports** - Generates structured reports with citations, executive summaries, and cross-reference analysis
- **Interactive CLI** - User-friendly command-line interface with progress indicators

## Quick Start

Get up and running in less than 5 minutes:

### Using uv (Recommended)

```bash
# 1. Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install the package
uv pip install cc-deep-research

# 3. Set your Tavily API key (get one at https://tavily.com)
export TAVILY_API_KEYS=your_api_key_here

# 4. Run your first research query
cc-deep-research research "What are the latest developments in quantum computing?"
```

### Using pip

```bash
# 1. Install the package
pip install cc-deep-research

# 2. Set your Tavily API key (get one at https://tavily.com)
export TAVILY_API_KEYS=your_api_key_here

# 3. Run your first research query
cc-deep-research research "What are the latest developments in quantum computing?"
```

That's it! The tool will automatically:
- Run comprehensive searches across multiple sources
- Generate a detailed markdown report
- Display the results in your terminal

## Usage Examples

### Basic Research

```bash
# Deep dive research (default) with agent teams
cc-deep-research research "What are the latest developments in quantum computing?"

# Quick research
cc-deep-research research -d quick "What is the capital of Australia?"

# Save to specific file
cc-deep-research research -o report.md "Climate change statistics 2024"

# Research without agent teams (sequential mode)
cc-deep-research research --no-team "Simple query"
```

### Advanced Options

```bash
# Use only Tavily search
cc-deep-research research --tavily-only "AI safety research"

# Use only Claude provider (reserved for future provider support)
cc-deep-research research --claude-only "Machine learning trends"

# Specify minimum sources
cc-deep-research research -s 30 "Comprehensive topic"

# JSON output
cc-deep-research research --format json "Query" > results.json

# Custom team size
cc-deep-research research --team-size 6 "Complex topic"

# Enable workflow telemetry (events + session summary persisted by default)
cc-deep-research research --monitor "Complex topic"
```

### Monitoring Dashboard

The CLI now persists per-session telemetry logs to:

- `~/.config/cc-deep-research/telemetry/<session_id>/events.jsonl`
- `~/.config/cc-deep-research/telemetry/<session_id>/summary.json`

Build analytics tables and launch the dashboard:

```bash
# Ingest telemetry logs into DuckDB
cc-deep-research telemetry ingest

# Launch Streamlit dashboard
cc-deep-research telemetry dashboard --port 8501
```

Dashboard package requirements:

```bash
pip install \"cc-deep-research[dashboard]\"
```

### Configuration Management

```bash
# Show current configuration
cc-deep-research config show

# Set configuration value
cc-deep-research config set tavily.api_keys key1,key2,key3

# Create default configuration file
cc-deep-research config init
```

## Research Modes

| Mode | Sources | Time | Best For |
|------|---------|------|----------|
| Quick | 3-5 | 1-2 min | Fact-checking, basic queries |
| Standard | 10-15 | 3-5 min | General research, overviews |
| Deep (default) | 20+ | 5-10 min | Thorough research, detailed understanding |

## Documentation

- **[USAGE.md](USAGE.md)** - Complete usage guide with detailed documentation
- **[EXAMPLES.md](EXAMPLES.md)** - Comprehensive examples for common and advanced use cases

## Installation

For development or to install from source:

### Using uv (Recommended)

```bash
# Clone the repository
git clone <repository-url>
cd cc-deep-research

# Sync with uv (creates virtual environment and installs dependencies)
uv sync

# Run commands with uv
uv run cc-deep-research research "What are the latest developments in quantum computing?"
```

### Using pip

```bash
# Clone the repository
git clone <repository-url>
cd cc-deep-research

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .
```

## Development Commands

### Testing CLI Without Installation

During development, you can test the CLI without reinstalling the package each time. Here are the available methods:

**Method 1: Using `uv run` (Recommended)**
```bash
# Setup (one-time)
uv sync

# Run CLI directly - changes reflect immediately
uv run cc-deep-research research "query"
uv run cc-deep-research config show
uv run cc-deep-research config init
```

**Method 2: Editable Install with pip**
```bash
# Install in editable mode (one-time setup)
pip install -e .

# Run CLI directly - changes reflect immediately
cc-deep-research research "query"
```

**Method 3: Run as Python Module**
```bash
# Run as module without installation
python -m cc_deep_research.cli research "query"

# Or with uv
uv run python -m cc_deep_research.cli research "query"
```

**Method 4: Direct File Execution**
```bash
# Set PYTHONPATH to include src directory
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

# Run the CLI file directly
python src/cc_deep_research/cli.py research "query"
```

### uv (Recommended)

```bash
# Install dependencies
uv sync

# Run the CLI
uv run cc-deep-research research "query"

# Run tests
uv run pytest

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

### pip

```bash
# Run tests
pytest

# Run linting
ruff check src/ tests/

# Format code
ruff format src/ tests/

# Type checking
mypy src/
```

## Configuration

Set your Tavily API keys for web search:

```bash
export TAVILY_API_KEYS=key1,key2,key3
```

Or use the config command:

```bash
cc-deep-research config set tavily.api_keys key1,key2,key3
```

### Configuration File

Create a configuration file at `~/.config/cc-deep-research/config.yaml`:

```yaml
search:
  providers: ["tavily", "claude"]
  mode: "hybrid_parallel"
  depth: "deep"

tavily:
  api_keys: ["key1", "key2"]
  rate_limit: 1000
  max_results: 100

research:
  default_depth: "deep"
  min_sources:
    quick: 3
    standard: 10
    deep: 20
  enable_iterative_search: true
  enable_cross_ref: true

search_team:
  enabled: true
  team_size: 4
  parallel_execution: true
  timeout_seconds: 300

output:
  format: "markdown"
  auto_save: true
  save_dir: "./reports"
```

## Project Structure

```
cc-deep-research/
├── src/cc_deep_research/
│   ├── __init__.py
│   ├── cli.py              # CLI entry point
│   ├── config.py           # Configuration management
│   ├── models.py           # Data models and schemas
│   ├── orchestrator.py     # Research orchestration
│   ├── monitoring.py       # Monitoring and logging
│   ├── reporting.py        # Report generation
│   ├── providers/          # Search provider implementations
│   ├── agents/             # Specialized research agents
│   └── teams/             # Team management and coordination
├── tests/                  # Test suite
├── USAGE.md                # Complete usage guide
├── EXAMPLES.md             # Detailed examples
└── README.md               # This file
```

## Requirements

- Python 3.11+
- Tavily API key(s)
- Claude Code (for built-in search integration)

## License

[Add your license here]

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
