# CC Deep Research CLI - Complete Usage Guide

## Table of Contents

1. [Introduction](#introduction)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Quick Start](#quick-start)
5. [Commands Reference](#commands-reference)
6. [Research Modes](#research-modes)
7. [Options and Flags](#options-and-flags)
8. [Output Formats](#output-formats)
9. [Execution Model](#execution-model)
10. [Advanced Usage](#advanced-usage)
11. [Examples](#examples)
12. [Troubleshooting](#troubleshooting)
13. [Best Practices](#best-practices)

---

## Introduction

### What is CC Deep Research?

CC Deep Research is a command-line tool for staged web research. The current runtime is a local Python pipeline with optional parallel source collection. It leverages:

- **Tavily Search API** - Professional web search with advanced filtering
- **Routed LLM Analysis** - Optional provider-backed analysis for synthesis phases
- **Specialist Components** - Lead, collector, analyzer, validator, and reporter roles coordinated locally
- **Quality Scoring** - Automated source evaluation and ranking
- **Cross-Reference Analysis** - Identifies consensus and contradictions

### Key Features

| Feature                                                          | Description                                                                     |
| ---------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| **Specialist Pipeline**                                          | Uses local planner, collector, analyzer, validator, and reporter components     |
| **Parallel Execution**                                           | Fans out source collection into local researcher tasks                          |
| **Provider Handling**                                            | Tavily is implemented; `claude` provider selection is not yet implemented       |
| **Query Expansion**                                              | Automatically generates search variations                                       |
| **Iterative Search**                                             | Analyzes gaps and performs follow-up searches                                   |
| **Quality Scoring**                                              | Evaluates sources by credibility, relevance, freshness, diversity               |
| **Cross-Reference Analysis**                                     | Identifies consensus points and contradictions                                  |
| **Multiple Formats**                                             | Markdown, JSON, and HTML output options                                         |
| **API Key Rotation** - Automatic failover with multiple API keys |
| **Progress Monitoring**                                          | Browser-based live monitoring, terminal monitor output, and telemetry analytics |

### Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    CC Deep Research CLI                   │
└─────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌───────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   Tavily API  │  │ Routed LLMs     │  │   Config File   │
└───────────────┘  └─────────────────┘  └─────────────────┘
        │                   │
        └─────────┬─────────┘
                  │
                  ▼
        ┌─────────────────┐
        │  Orchestrator   │
        └─────────────────┘
                  │
                  ▼
        ┌─────────────────┐
        │ Local Pipeline  │
        │ + task fan-out  │
        └─────────────────┘
                  │
        ┌─────────┼─────────┐
        ▼         ▼         ▼
┌──────────┐ ┌──────────┐ ┌──────────┐
│ Analysis │ │ Quality  │ │  Report  │
└──────────┘ └──────────┘ └──────────┘
```

### Python API Surface

The stable package-root API is intentionally small. Prefer:

- `from cc_deep_research import TeamResearchOrchestrator`
- `from cc_deep_research import ResearchDepth, ResearchSession, SearchOptions, SearchResult, SearchResultItem`
- `from cc_deep_research import SearchProvider`

For benchmark helpers, text normalization helpers, CLI commands, or telemetry internals, import from their direct modules instead of relying on `cc_deep_research.__init__`.

### Post-Refactor Layout

Contributor-facing module boundaries now follow the split package layout:

- CLI bootstrap and command registration: [`src/cc_deep_research/cli/main.py`](../src/cc_deep_research/cli/main.py)
- CLI command handlers: [`src/cc_deep_research/cli/`](../src/cc_deep_research/cli)
- config schema and file IO: [`src/cc_deep_research/config/`](../src/cc_deep_research/config)
- runtime models: [`src/cc_deep_research/models/`](../src/cc_deep_research/models)
- orchestration internals: [`src/cc_deep_research/orchestration/`](../src/cc_deep_research/orchestration)
- telemetry live readers and analytics: [`src/cc_deep_research/telemetry/`](../src/cc_deep_research/telemetry)

---

## Installation

### Prerequisites

- **Python 3.11 or higher**
- **Tavily API Key** - Get one at [https://tavily.com](https://tavily.com)
- **Claude Code** - Optional, for Claude-backed analysis features

### Installation Using uv (Recommended)

`uv` is a fast Python package manager that's recommended for this project.

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install cc-deep-research
uv pip install cc-deep-research
```

### Installation Using pip

```bash
# Install cc-deep-research
pip install cc-deep-research
```

### Installation from Source

```bash
# Clone the repository
git clone <repository-url>
cd cc-deep-research

# Using uv
uv sync
uv pip install -e .

# Or using pip
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
```

### Verification

Verify your installation:

```bash
# Check version
cc-deep-research --version

# Display help
cc-deep-research --help

# Display research command help
cc-deep-research research --help
```

If you are running the Next.js dashboard against a non-default backend host, set one of these before `npm run dev` or `npm run build` inside [`dashboard/`](../dashboard):

```bash
export NEXT_PUBLIC_CC_BACKEND_ORIGIN=http://localhost:8000
# optional explicit overrides
export NEXT_PUBLIC_CC_API_BASE_URL=http://localhost:8000/api
export NEXT_PUBLIC_CC_WS_BASE_URL=ws://localhost:8000/ws
```

---

## Configuration

### Getting Tavily API Keys

1. Visit [https://tavily.com](https://tavily.com)
2. Sign up for an account
3. Navigate to API Keys section
4. Copy your API key(s)

### Setting Up Environment Variables

The easiest way to configure the tool is using environment variables:

```bash
# Single API key
export TAVILY_API_KEYS=your_api_key_here

# Multiple API keys (comma-separated, for rotation)
export TAVILY_API_KEYS=key1,key2,key3

# Optional: Override default research depth
export CC_DEEP_RESEARCH_DEPTH=deep

# Optional: Override output format
export CC_DEEP_RESEARCH_FORMAT=markdown

# Optional: Disable colored output
export NO_COLOR=1

# Optional: Specify custom config file location
export CC_DEEP_RESEARCH_CONFIG=/path/to/config.yaml
```

### Configuration File Structure

Create a configuration file at `~/.config/cc-deep-research/config.yaml`:

```yaml
# Search Provider Configuration
search:
  providers: ['tavily'] # "claude" is accepted but not implemented as a search provider
  mode: 'tavily_primary' # Options: hybrid_parallel, tavily_primary, claude_primary
  depth: 'deep' # Options: quick, standard, deep

# Tavily-specific Configuration
tavily:
  api_keys: ['key1', 'key2'] # List of API keys for rotation
  rate_limit: 1000 # Requests per key per month
  max_results: 100 # Maximum results per search

# Claude-specific Configuration
claude:
  max_results: 50 # Reserved for future Claude search provider support

# Research Configuration
research:
  default_depth: 'deep' # Default research depth
  min_sources:
    quick: 3 # Minimum sources for quick mode
    standard: 10 # Minimum sources for standard mode
    deep: 50 # Minimum sources for deep mode
  enable_iterative_search: true # Perform follow-up searches
  max_iterations: 3 # Maximum follow-up iterations
  enable_cross_ref: true # Perform cross-reference analysis
  enable_quality_scoring: true # Score and rank sources

# Agent Configuration
research_agent:
  model: 'claude-sonnet-4-6' # Claude model to use
  max_turns: 10 # Maximum conversation turns
  mode: 'default' # Options: default, bypassPermissions, dontAsk

# Parallel Collection Configuration
search_team:
  enabled: true # Retained for compatibility with existing config
  team_size: 4 # Describes local specialist roster metadata
  parallel_execution: true # Run source collection in parallel local tasks
  timeout_seconds: 300 # Local parallel-task timeout (30-600 seconds)
  fallback_to_sequential: true # Fall back to sequential on error

# Output Configuration
output:
  format: 'markdown' # Options: markdown, json, html
  auto_save: true # Automatically save reports
  save_dir: './reports' # Directory for saved reports
  include_metadata: true # Include session metadata
  include_cross_ref_analysis: true # Include cross-reference analysis

# Display Configuration
display:
  color: 'auto' # Options: always, auto, never
  progress: 'auto' # Options: always, auto, never
  verbose: false # Enable verbose output
```

### Using the Config Command

```bash
# Show current configuration
cc-deep-research config show

# Initialize default config file
cc-deep-research config init

# Initialize config file at specific path
cc-deep-research config init --config-path /custom/path/config.yaml

# Set configuration values (using dot notation)
cc-deep-research config set tavily.api_keys key1,key2,key3
cc-deep-research config set search.mode tavily_primary
cc-deep-research config set search_team.team_size 6
cc-deep-research config set research.min_sources.deep 25
cc-deep-research config set output.format json

# Boolean values
cc-deep-research config set search_team.enabled true
cc-deep-research config set research.enable_iterative_search false

# Initialize with --force to overwrite existing config
cc-deep-research config init --force
```

### Default Configuration Values

| Configuration                      | Default Value         | Description                               |
| ---------------------------------- | --------------------- | ----------------------------------------- |
| `search.providers`                 | `["tavily"]`          | Active search providers                   |
| `search.mode`                      | `"tavily_primary"`    | Search execution mode                     |
| `search.depth`                     | `"deep"`              | Default research depth                    |
| `tavily.api_keys`                  | `[]`                  | Tavily API keys (set via env var)         |
| `tavily.rate_limit`                | `1000`                | Requests per key per month                |
| `tavily.max_results`               | `100`                 | Max results per search                    |
| `claude.max_results`               | `50`                  | Reserved for future Claude search support |
| `research.default_depth`           | `"deep"`              | Default research depth                    |
| `research.min_sources.quick`       | `3`                   | Quick mode minimum sources                |
| `research.min_sources.standard`    | `10`                  | Standard mode minimum sources             |
| `research.min_sources.deep`        | `50`                  | Deep mode minimum sources                 |
| `research.enable_iterative_search` | `true`                | Enable follow-up searches                 |
| `research.max_iterations`          | `3`                   | Max follow-up iterations                  |
| `research.enable_cross_ref`        | `true`                | Enable cross-reference analysis           |
| `research.enable_quality_scoring`  | `true`                | Enable source scoring                     |
| `research_agent.model`             | `"claude-sonnet-4-6"` | Claude model                              |
| `research_agent.max_turns`         | `10`                  | Max conversation turns                    |
| `search_team.enabled`              | `true`                | Compatibility flag for the local runtime  |
| `search_team.team_size`            | `4`                   | Specialist roster metadata size           |
| `search_team.parallel_execution`   | `true`                | Parallel local source collection          |
| `search_team.timeout_seconds`      | `300`                 | Local parallel-task timeout               |
| `output.format`                    | `"markdown"`          | Output format                             |
| `output.auto_save`                 | `true`                | Auto-save reports                         |
| `output.save_dir`                  | `"./reports"`         | Save directory                            |
| `display.color`                    | `"auto"`              | Color output                              |
| `display.progress`                 | `"auto"`              | Progress indicators                       |

### LLM Routing

The active runtime supports agent-level LLM routing for analysis and report-quality evaluation. Configure it under `llm` in the same config file:

```yaml
llm:
  anthropic:
    enabled: false
    api_key: '${ANTHROPIC_API_KEY}'
    model: 'claude-sonnet-4-6'

  openrouter:
    enabled: false
    api_key: '${OPENROUTER_API_KEY}'
    model: 'anthropic/claude-sonnet-4'

  cerebras:
    enabled: false
    api_key: '${CEREBRAS_API_KEY}'
    model: 'llama-3.3-70b'

  fallback_order:
    - 'anthropic'
    - 'openrouter'
    - 'cerebras'
    - 'heuristic'

  route_defaults:
    analyzer: 'openrouter'
    deep_analyzer: 'cerebras'
    report_quality_evaluator: 'anthropic'
    reporter: 'anthropic'
    default: 'anthropic'
```

Planner-selected routes are applied per session. In one run, `analyzer` can use OpenRouter, `deep_analyzer` can use Cerebras, and `report_quality_evaluator` can use Anthropic. If no configured transport is available, the runtime falls back to `heuristic`.

---

## Quick Start

### Your First Research Query

```bash
# Set your API key
export TAVILY_API_KEYS=your_api_key_here

# Run a simple research query
uv run cc-deep-research research "What are the latest developments in quantum computing?"
```

### Live Monitoring In The Browser

For the current monitoring workflow, start the combined dashboard launcher and run research from the browser home page:

```bash
cd dashboard
npm install
npm run dev
```

This starts:

- backend API on `http://localhost:8000`
- frontend dashboard on `http://localhost:3000`

Then open `http://localhost:3000`, submit a query from the home page, watch live progress, and open the final session report when the run completes.

### Understanding the Output

The tool generates a comprehensive report with the following structure:

```markdown
# Research Report: Latest Developments in Quantum Computing

## Executive Summary

[2-3 paragraph summary of key findings...]

## Key Findings

### 1. Recent Breakthroughs in Quantum Error Correction

[Detailed analysis with citations...]
[1] https://example.com/article1
[2] https://example.com/article2

### 2. Scaling Quantum Computers to 1000+ Qubits

[Detailed analysis with citations...]
[3] https://example.com/article3

## Cross-Reference Analysis

### Consensus Points

- [Agreed-upon facts from multiple sources...]

### Areas of Contention

- [Disagreements or conflicting information...]

## Sources

1. [Title](https://example.com/article1) - Description
2. [Title](https://example.com/article2) - Description

## Metadata

- **Query:** What are the latest developments in quantum computing?
- **Depth:** Deep
- **Sources:** 25
- **Execution Time:** 8.5 minutes
- **Providers:** tavily, claude
```

### Common Use Cases

```bash
# Quick fact-check
cc-deep-research research -d quick "What is the capital of Australia?"

# Standard research
cc-deep-research research -d standard "History of the Internet"

# Deep research with saved report
cc-deep-research research -o quantum_report.md "Quantum computing applications"

# JSON output for programmatic use
cc-deep-research research --format json "AI safety research" > results.json

# HTML output for browser review or downstream PDF conversion
cc-deep-research research --format html -o ai-safety.html "AI safety research"

# Research with sequential source collection (useful for simple queries)
cc-deep-research research --no-team "Simple question"

# Use only Tavily
cc-deep-research research --tavily-only "Web development trends 2024"
```

---

## Commands Reference

### `cc-deep-research research`

Execute a research query and generate a report.

**Usage:**

```bash
cc-deep-research research [QUERY] [OPTIONS]
```

**Required Argument:**

- `QUERY` - The research topic or question to investigate

**Options:**

| Option              | Short | Type   | Default       | Description                                                              |
| ------------------- | ----- | ------ | ------------- | ------------------------------------------------------------------------ |
| `--depth`           | `-d`  | choice | `deep`        | Research depth mode (`quick`, `standard`, `deep`)                        |
| `--sources`         | `-s`  | int    | (from config) | Minimum number of sources to gather                                      |
| `--output`          | `-o`  | path   | (stdout)      | Output file path for the report                                          |
| `--format`          |       | choice | `markdown`    | Output format (`markdown`, `json`, `html`)                               |
| `--no-cross-ref`    |       | flag   | false         | Disable cross-reference analysis                                         |
| `--tavily-only`     |       | flag   | false         | Use only Tavily provider                                                 |
| `--claude-only`     |       | flag   | false         | Select only the `claude` provider (currently emits provider warnings)    |
| `--no-team`         |       | flag   | false         | Run source collection sequentially instead of using parallel local tasks |
| `--team-size`       |       | int    | (from config) | Override local roster metadata size (compatibility only)                 |
| `--parallel-mode`   |       | flag   | false         | Force parallel local source collection for this run                      |
| `--num-researchers` |       | int    | (from config) | Override the number of parallel local collection tasks (1-8)             |
| `--progress`        |       | flag   | true          | Show progress indicators                                                 |
| `--quiet`           |       | flag   | false         | Suppress output                                                          |
| `--verbose`         |       | flag   | false         | Show detailed output                                                     |
| `--monitor`         |       | flag   | false         | Show terminal workflow monitoring output                                 |
| `--show-timeline`   |       | flag   | false         | Show the execution timeline after a parallel run                         |
| `--pdf`             |       | flag   | false         | Generate PDF output in addition to the selected report format            |
| `--enable-realtime` |       | flag   | false         | Enable the shared real-time event router used by dashboard-backed runs   |

**Examples:**

```bash
# Basic deep research
cc-deep-research research "Climate change impacts on agriculture"

# Quick research with specific output file
cc-deep-research research -d quick -o weather.md "Weather patterns in 2024"

# JSON output with custom sources
cc-deep-research research -s 30 --format json "Machine learning algorithms" > ml.json

# HTML output with custom sources
cc-deep-research research -s 30 --format html -o ml.html "Machine learning algorithms"

# Monitor workflow execution in the terminal
cc-deep-research research --monitor "Complex topic requiring deep analysis"

# Show a parallel execution timeline after the run completes
cc-deep-research research --parallel-mode --num-researchers 4 --show-timeline \
  "Complex topic requiring deep analysis"

# Generate PDF output alongside the main report
cc-deep-research research --pdf -o report.md "Complex topic requiring deep analysis"

# Quiet mode for scripts
cc-deep-research research --quiet -o report.md "Topic" > /dev/null
```

### `cc-deep-research config set`

Set a configuration value.

**Usage:**

```bash
cc-deep-research config set [KEY] [VALUE] [OPTIONS]
```

**Required Arguments:**

- `KEY` - Configuration key in dot notation (e.g., `tavily.api_keys`)
- `VALUE` - Value to set

**Options:**

| Option          | Type | Default   | Description         |
| --------------- | ---- | --------- | ------------------- |
| `--config-path` | path | (default) | Path to config file |

**Examples:**

```bash
# Set API keys
cc-deep-research config set tavily.api_keys key1,key2,key3

# Change search mode
cc-deep-research config set search.mode hybrid_parallel

# Adjust local roster metadata size
cc-deep-research config set search_team.team_size 6

# Disable cross-reference analysis
cc-deep-research config set research.enable_cross_ref false

# Set custom output directory
cc-deep-research config set output.save_dir ~/research/reports
```

### `cc-deep-research config show`

Display current configuration.

**Usage:**

```bash
cc-deep-research config show [OPTIONS]
```

**Options:**

| Option          | Type | Default   | Description         |
| --------------- | ---- | --------- | ------------------- |
| `--config-path` | path | (default) | Path to config file |

**Example:**

```bash
cc-deep-research config show
```

**Output:**

```
Current configuration:
  Search providers: tavily, claude
  Search mode: hybrid_parallel
  Search depth: deep
  Tavily API keys: 3 configured
  Output format: markdown
  Output directory: ./reports
```

### `cc-deep-research config init`

Create a default configuration file.

**Usage:**

```bash
cc-deep-research config init [OPTIONS]
```

**Options:**

| Option          | Type | Default   | Description                    |
| --------------- | ---- | --------- | ------------------------------ |
| `--config-path` | path | (default) | Path to config file            |
| `--force`       | flag | false     | Overwrite existing config file |

**Examples:**

```bash
# Initialize default config
cc-deep-research config init

# Initialize at custom path
cc-deep-research config init --config-path /custom/path/config.yaml

# Overwrite existing config
cc-deep-research config init --force
```

### `cc-deep-research telemetry ingest`

Ingest persisted telemetry JSONL into DuckDB tables for analytics.

**Usage:**

```bash
cc-deep-research telemetry ingest [OPTIONS]
```

**Options:**

| Option       | Type | Default       | Description                 |
| ------------ | ---- | ------------- | --------------------------- |
| `--base-dir` | path | telemetry dir | Telemetry session directory |
| `--db-path`  | path | dashboard DB  | DuckDB output path          |

**Examples:**

```bash
cc-deep-research telemetry ingest
cc-deep-research telemetry ingest --base-dir ~/.config/cc-deep-research/telemetry
cc-deep-research telemetry ingest --db-path ./tmp/dashboard.duckdb
```

### `cc-deep-research telemetry dashboard`

Launch the Streamlit telemetry dashboard for live tails and historical DuckDB analytics.

**Usage:**

```bash
cc-deep-research telemetry dashboard [OPTIONS]
```

**Options:**

| Option              | Type | Default       | Description                                  |
| ------------------- | ---- | ------------- | -------------------------------------------- |
| `--base-dir`        | path | telemetry dir | Telemetry session directory                  |
| `--db-path`         | path | dashboard DB  | DuckDB analytics path                        |
| `--port`            | int  | `8501`        | Streamlit dashboard port                     |
| `--refresh-seconds` | int  | `5`           | Auto-refresh interval (`0` disables refresh) |
| `--tail-limit`      | int  | `200`         | Max live events and subprocess chunks shown  |

**Example:**

```bash
cc-deep-research telemetry dashboard --port 8501 --refresh-seconds 5 --tail-limit 200
```

### `cc-deep-research dashboard`

Start the FastAPI backend used by the Next.js operator console in [`dashboard/`](../dashboard).

**Usage:**

```bash
cc-deep-research dashboard [OPTIONS]
```

**Options:**

| Option              | Type | Default     | Description                      |
| ------------------- | ---- | ----------- | -------------------------------- |
| `--host`            | text | `localhost` | Host to bind                     |
| `--port`            | int  | `8000`      | HTTP/WebSocket port              |
| `--enable-realtime` | flag | enabled     | Enable WebSocket event streaming |

**Example:**

```bash
cc-deep-research dashboard --host localhost --port 8000
```

### `cc-deep-research session`

Manage saved research sessions produced by completed runs.

**Subcommands:**

| Command                                   | Purpose                                     |
| ----------------------------------------- | ------------------------------------------- |
| `session list`                            | List saved sessions                         |
| `session show SESSION_ID`                 | Show one saved session                      |
| `session export SESSION_ID --output PATH` | Export a session as markdown, JSON, or HTML |
| `session delete SESSION_ID`               | Delete a saved session                      |

**Examples:**

```bash
cc-deep-research session list --limit 10
cc-deep-research session show research-abc123
cc-deep-research session export research-abc123 --format json --output ./session.json
```

#### Session Delete

Delete a saved research session:

```bash
cc-deep-research session delete SESSION_ID
```

**What gets deleted:**

When you delete a session, the following data is permanently removed:

- Session file (`~/.config/cc-deep-research/sessions/{session_id}.json`)
- Telemetry directory (`~/.config/cc-deep-research/telemetry/{session_id}/`)
- Historical analytics records in DuckDB

**Active session protection:**

If the session is currently running (active), the delete command will fail by default. Use the `--force` flag to override:

```bash
cc-deep-research session delete research-abc123 --force
```

**Dashboard deletion:**

You can also delete sessions from the browser dashboard:
- From the session list: click the delete button on a session card
- From the session page: use the delete action in the session details

The dashboard delete API (`DELETE /api/sessions/{session_id}`) removes the same data and supports the same `force` query parameter.

**Limitation:** No bulk delete is available - sessions must be deleted one at a time.

---

## Research Modes

### Quick Mode

**Use for:** Fast fact-checking, simple queries, quick overviews

- **Sources:** 3-5 (minimum 3)
- **Time:** 1-2 minutes
- **Features:** Basic search, minimal analysis
- **Best for:** Simple questions, quick lookups

**Example:**

```bash
cc-deep-research research -d quick "What is the population of Tokyo?"
```

### Standard Mode

**Use for:** General research, topic overviews, balanced depth

- **Sources:** 10-15 (minimum 10)
- **Time:** 3-5 minutes
- **Features:** Moderate analysis, some cross-referencing
- **Best for:** Learning about a topic, general research

**Example:**

```bash
cc-deep-research research -d standard "History of electric vehicles"
```

### Deep Mode (Default)

**Use for:** Comprehensive research, detailed understanding, academic work

- **Sources:** 50+ (minimum 50)
- **Time:** 5-10 minutes
- **Features:** Comprehensive analysis, full cross-referencing, quality scoring
- **Best for:** Thorough research, complex topics, reports

**Example:**

```bash
cc-deep-research research -d deep "Impact of AI on healthcare industry"
```

### Comparison Table

| Feature          | Quick         | Standard         | Deep              |
| ---------------- | ------------- | ---------------- | ----------------- |
| Minimum Sources  | 3             | 10               | 50                |
| Typical Sources  | 3-5           | 10-15            | 50+               |
| Execution Time   | 1-2 min       | 3-5 min          | 5-10 min          |
| Query Expansion  | Basic         | Moderate         | Comprehensive     |
| Iterative Search | No            | Yes              | Yes               |
| Cross-Reference  | No            | Basic            | Full              |
| Quality Scoring  | Basic         | Moderate         | Advanced          |
| Best For         | Fact-checking | General research | Thorough research |

---

## Options and Flags

### Research Options

#### `--depth`, `-d`

Set the research depth mode.

**Values:** `quick`, `standard`, `deep` (default)

**Examples:**

```bash
cc-deep-research research -d quick "Simple query"
cc-deep-research research -d standard "Moderate query"
cc-deep-research research -d deep "Complex query"
```

#### `--sources`, `-s`

Override the minimum number of sources to gather.

**Values:** Positive integer

**Example:**

```bash
cc-deep-research research -s 50 "Comprehensive topic"
```

#### `--output`, `-o`

Specify the output file path for the report.

**Values:** File path

**Example:**

```bash
cc-deep-research research -o ~/reports/quantum.md "Quantum computing"
```

#### `--format`

Set the output format.

**Values:** `markdown` (default), `json`, `html`

**Example:**

```bash
cc-deep-research research --format json "Topic" > results.json
cc-deep-research research --format html -o report.html "Topic"
```

### Provider Options

#### `--tavily-only`

Use only the Tavily search provider.

**Example:**

```bash
cc-deep-research research --tavily-only "Web search only"
```

#### `--claude-only`

Select only the `claude` provider.

Current status: no Claude search provider is implemented, so this configuration will only produce provider warnings.

**Example:**

```bash
cc-deep-research research --claude-only "Claude search only"
```

### Execution Mode Options

#### `--no-team`

Run source collection sequentially instead of using parallel local tasks.

This only changes how source collection is scheduled. The rest of the run still uses the same local orchestrator and specialist components.

**Use when:**

- Simple queries don't need parallel collection
- Troubleshooting parallel collection issues
- Reducing resource usage

**Example:**

```bash
cc-deep-research research --no-team "Simple question"
```

#### `--team-size`

Override the configured local roster size metadata. This is a compatibility setting and does not create remote workers.

**Values:** Integer between 2-8

**Example:**

```bash
cc-deep-research research --team-size 6 "Complex topic"
```

#### `--parallel-mode`

Force parallel local source collection for this run when you want to override the configured mode.

**Example:**

```bash
cc-deep-research research --parallel-mode "Complex topic"
```

#### `--num-researchers`

Override the number of parallel local collection tasks used during source collection.

**Values:** Integer between 1-8

**Example:**

```bash
cc-deep-research research --parallel-mode --num-researchers 4 "Complex topic"
```

### Display Options

#### `--progress`

Show progress indicators (default: enabled).

**Example:**

```bash
cc-deep-research research --progress "Topic"
cc-deep-research research --no-progress "Topic"
```

#### `--quiet`

Suppress all output (except errors and file save confirmation).

**Use when:**

- Running in scripts/cron jobs
- Redirecting output to file
- Automated workflows

**Example:**

```bash
cc-deep-research research --quiet -o report.md "Topic"
```

#### `--verbose`

Show detailed output including configuration and execution details.

**Example:**

```bash
cc-deep-research research --verbose "Topic"
```

**Sample verbose output:**

```
Research query: AI safety research
Depth: deep
Output format: markdown
Mode: Local pipeline (parallel source collection)
```

#### `--monitor`

Show internal workflow monitoring information in the terminal.

**Shows:**

- Research session details
- Configuration values
- Execution stages
- Local pipeline activity
- Performance metrics
- Summary statistics

This does not launch the browser dashboard. It only adds terminal monitor output.

**Example:**

```bash
cc-deep-research research --monitor "Complex topic"
```

#### `--show-timeline`

Show a terminal timeline after a parallel run completes.

Use this with `--parallel-mode` when you want a compact execution trace without opening the browser dashboard.

**Example:**

```bash
cc-deep-research research --parallel-mode --show-timeline "Complex topic"
```

#### `--enable-realtime`

Enable the shared event router used by the browser monitoring backend.

In normal browser-first usage you do not pass this yourself; runs started from the dashboard home page already use the backend's shared router. Keep this for integrations or advanced local development.

**Example:**

```bash
cc-deep-research research --enable-realtime "Topic"
```

#### `--pdf`

Generate a PDF artifact in addition to the main report output.

**Example:**

```bash
cc-deep-research research --pdf -o report.md "Topic"
```

### Cross-Reference Options

#### `--no-cross-ref`

Disable cross-reference analysis.

**Use when:**

- Faster execution needed
- Simple queries where cross-referencing isn't necessary
- Processing large result sets

**Example:**

```bash
cc-deep-research research --no-cross-ref "Simple topic"
```

---

## Output Formats

### Markdown Format (Default)

The default output format is Markdown, which provides:

- **Readable formatting** for human consumption
- **Citations** with numbered references
- **Structured sections** (Executive Summary, Key Findings, etc.)
- **Markdown syntax** compatible with most editors and viewers

**Sample output:**

```markdown
# Research Report: Quantum Computing Applications

## Executive Summary

Quantum computing has emerged as a transformative technology with applications across multiple industries...

## Key Findings

### 1. Pharmaceutical Research

Quantum computers are revolutionizing drug discovery by simulating molecular interactions...
[1] https://nature.com/quantum-drug-discovery
[2] https://science.org/quantum-simulations

### 2. Cryptography

Post-quantum cryptography is becoming essential as quantum computers threaten current encryption...
[3] https://nist.gov/post-quantum
[4] https://ieee.org/quantum-crypto

## Cross-Reference Analysis

### Consensus Points

- Quantum computing will disrupt cryptography within 10-15 years [1][3][4]
- Pharmaceutical applications are among the most promising near-term use cases [1][2]

### Areas of Contention

- Timeline for practical quantum advantage varies from 3-10 years [1] vs. 10-20 years [4]
- Commercial viability estimates differ significantly across sources

## Sources

1. [Quantum Drug Discovery Breakthroughs](https://nature.com/quantum-drug-discovery) - Nature Journal
2. [Molecular Simulation Advances](https://science.org/quantum-simulations) - Science Magazine
3. [Post-Quantum Cryptography Standards](https://nist.gov/post-quantum) - NIST
4. [Quantum Threat Timeline](https://ieee.org/quantum-crypto) - IEEE Spectrum

## Metadata

- **Query:** Quantum Computing Applications
- **Depth:** Deep
- **Sources:** 25
- **Execution Time:** 8.5 minutes
- **Providers:** tavily, claude
- **Generated:** 2024-03-03T12:34:56Z
```

### JSON Format

JSON output provides programmatic access to research data, suitable for:

- **Automated processing** in scripts and applications
- **Data integration** with other tools
- **Further analysis** with data processing tools
- **API responses** in web applications

**Sample output:**

```json
{
  "query": "Quantum Computing Applications",
  "depth": "deep",
  "executive_summary": "Quantum computing has emerged as a transformative technology...",
  "key_findings": [
    {
      "title": "Pharmaceutical Research",
      "content": "Quantum computers are revolutionizing drug discovery...",
      "citations": [
        {
          "id": 1,
          "url": "https://nature.com/quantum-drug-discovery"
        },
        {
          "id": 2,
          "url": "https://science.org/quantum-simulations"
        }
      ]
    }
  ],
  "cross_reference_analysis": {
    "consensus_points": ["Quantum computing will disrupt cryptography within 10-15 years"],
    "areas_of_contention": [
      "Timeline for practical quantum advantage varies from 3-10 years vs. 10-20 years"
    ]
  },
  "sources": [
    {
      "id": 1,
      "title": "Quantum Drug Discovery Breakthroughs",
      "url": "https://nature.com/quantum-drug-discovery",
      "snippet": "Recent advances in quantum computing...",
      "score": 0.95
    }
  ],
  "metadata": {
    "query": "Quantum Computing Applications",
    "depth": "deep",
    "sources": 25,
    "execution_time_seconds": 510.5,
    "providers": ["tavily", "claude"],
    "generated_at": "2024-03-03T12:34:56Z"
  }
}
```

### HTML Format

HTML output renders the same canonical report structure used by the PDF export
pipeline and is useful for:

- **Browser review** before generating a PDF
- **Debugging layout** and semantic section wrappers
- **Embedding reports** in systems that accept HTML documents
- **HTML-first workflows** where PDF is a later render step

**Example:**

```bash
cc-deep-research research --format html -o report.html "Quantum Computing Applications"
cc-deep-research markdown-to-html notes.md
```

HTML output includes the same major sections and uses the shared export
stylesheet that also drives PDF rendering.

### Output Structure

All report formats include the same logical sections:

1. **Executive Summary** - 2-3 paragraph overview
2. **Key Findings** - Organized sections with detailed analysis
3. **Cross-Reference Analysis** - Consensus and contradictions
4. **Sources** - Complete list with metadata
5. **Metadata** - Session information and statistics

---

## Execution Model

### How the Runtime Works

CC Deep Research runs a staged local pipeline. The orchestrator invokes specialist Python components directly and optionally fans out source collection into local researcher tasks:

```
┌─────────────────────────────────────────────────────────┐
│                 Local Runtime Architecture                │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
        ┌───────────────────────────────────────┐
        │         Orchestrator                 │
        │   (phase ordering & aggregation)     │
        └───────────────────────────────────────┘
                    │       │       │       │
        ┌───────────┴───┐   │   ┌───┴───────────┐
        ▼               ▼   ▼   ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Query        │ │ Source        │ │ Analyzer     │
│ Expander     │ │ Collector     │ │              │
└──────────────┘ └──────────────┘ └──────────────┘
        │               │               │
        └───────────────┴───────┬───────┘
                                ▼
                    ┌───────────────────┐
                    │  Results          │
                    │  Aggregator       │
                    └───────────────────┘
```

### Specialist Roles

| Agent                | Role                        | Responsibilities                                           |
| -------------------- | --------------------------- | ---------------------------------------------------------- |
| **Query Expander**   | Generates search variations | Creates related queries, explores different angles         |
| **Source Collector** | Gathers sources             | Searches multiple providers, collects URLs and content     |
| **Analyzer**         | Synthesizes information     | Analyzes content, extracts key points, identifies patterns |
| **Validator**        | Quality assurance           | Validates source credibility, checks completeness          |
| **Reporter**         | Creates reports             | Formats findings, generates citations, structures output   |
| **Orchestrator**     | Orchestrates workflow       | Orders phases, aggregates results, handles cleanup         |

### Runtime Configuration

Configure local pipeline and parallel collection behavior:

```yaml
# Parallel collection settings
search_team:
  enabled: true # Compatibility flag
  team_size: 4 # Specialist roster metadata
  parallel_execution: true # Run source collection in parallel local tasks
  timeout_seconds: 300 # Local source-collection timeout (30-600 seconds)
  fallback_to_sequential: true # Fall back on error
```

**Command-line overrides:**

```bash
# Force sequential source collection
cc-deep-research research --no-team "Simple query"

# Custom roster metadata size
cc-deep-research research --team-size 6 "Complex topic"
```

### Parallel vs. Sequential Execution

**Parallel Execution (Default):**

- Multiple local researcher tasks work simultaneously
- Faster for complex queries
- Requires more resources
- Better for deep research

**Sequential Execution:**

- Source collection runs in one local path
- Slower but uses fewer resources
- Better for simple queries
- Useful for debugging

### Team Size Guidelines

| Team Size | Use Case                                          | Performance                    |
| --------- | ------------------------------------------------- | ------------------------------ |
| 2-3       | Simple queries, resource-constrained environments | Fewer parallel tasks           |
| 4-5       | Standard research (default)                       | Balanced fan-out               |
| 6-7       | Complex topics, comprehensive research            | Higher fan-out, more overhead  |
| 8         | Maximum depth, very complex topics                | Highest fan-out, most overhead |

---

## Advanced Usage

### Custom Configuration

Create a custom configuration file for specific research needs:

```bash
# Create config file at custom location
cc-deep-research config init --config-path ~/research/custom-config.yaml

# Edit the file with your preferences
nano ~/research/custom-config.yaml

# Use the custom config
export CC_DEEP_RESEARCH_CONFIG=~/research/custom-config.yaml
cc-deep-research research "Your query"
```

### Dashboard Configuration Editing

If you use the browser dashboard, open `/settings` to edit the persisted YAML config used for future runs.

The settings page distinguishes:

- persisted values saved in `config.yaml`
- effective runtime values after environment-variable overrides

If a field is currently overridden by an environment variable, the dashboard shows the runtime source and treats that field as read-only. Saving config does not change active runs and does not beat an active env override.

Secret fields such as provider API keys are masked in API responses and in the UI. The dashboard only supports explicit replace or clear actions for those fields; it never round-trips the current secret value back to the browser.

### Dashboard Prompt Overrides

The dashboard start form includes an advanced prompt section for per-run prompt prefixes.

Current v1 support is intentionally limited to the LLM-backed agents that already consume prompts during execution:

- `analyzer`
- `deep_analyzer`
- `report_quality_evaluator`

These overrides apply only to the run you start from the browser. They do not mutate global defaults, and they are saved into session metadata so the monitor can show which prompt configuration was used later.

### Multiple API Keys Management

Set up multiple API keys for rotation and load balancing:

```bash
# Set multiple keys (comma-separated)
export TAVILY_API_KEYS=key1,key2,key3

# Or use config file
cc-deep-research config set tavily.api_keys key1,key2,key3
```

**Benefits:**

- **Load balancing** - Distributes requests across keys
- **Failover** - Automatically switches if one key fails
- **Rate limit management** - Each key has its own limit
- **Higher throughput** - More concurrent requests possible

### Iterative Search

The tool automatically performs follow-up searches when enabled:

```yaml
research:
  enable_iterative_search: true
  max_iterations: 3
```

**How it works:**

1. Initial search gathers sources
2. Analyzer identifies gaps or unclear areas
3. Generates follow-up queries
4. Performs additional searches (up to max_iterations)
5. Aggregates all findings

**Disable for speed:**

```bash
cc-deep-research research --no-iterative "Quick topic"
```

### Source Quality Scoring

Each source is scored based on multiple criteria:

```yaml
research:
  enable_quality_scoring: true
```

**Scoring criteria:**

- **Credibility** - Domain authority, source reputation
- **Relevance** - Match to query terms
- **Freshness** - Publication date recency
- **Diversity** - Unique information contribution
- **Overall** - Weighted composite score

**Scores range from 0.0 to 1.0, with higher scores indicating better quality.**

### Cross-Reference Analysis

Identify consensus and contradictions across sources:

```yaml
research:
  enable_cross_ref: true
```

**What it provides:**

- **Consensus Points** - Facts agreed upon by multiple sources
- **Areas of Contention** - Conflicting information or disagreements
- **Source Attribution** - Which sources support each point

**Disable for speed:**

```bash
cc-deep-research research --no-cross-ref "Simple topic"
```

### Search Provider Configuration

Choose which providers to use and their priority:

```yaml
search:
  providers: ['tavily'] # Active providers
  mode: 'tavily_primary' # Execution mode
```

**Search modes:**

| Mode              | Description                                              |
| ----------------- | -------------------------------------------------------- |
| `hybrid_parallel` | Configuration enum accepted by the model layer           |
| `tavily_primary`  | Matches the currently implemented provider path          |
| `claude_primary`  | Accepted by config, but Claude search is not implemented |

**Provider-specific configuration:**

```yaml
tavily:
  api_keys: ['key1', 'key2']
  rate_limit: 1000
  max_results: 100

claude:
  max_results: 50 # Reserved for future provider support
```

---

## Examples

### Basic Research Queries

**Simple fact-check:**

```bash
cc-deep-research research -d quick "What is the capital of Australia?"
```

**Topic overview:**

```bash
cc-deep-research research -d standard "History of electric vehicles"
```

**Comprehensive research:**

```bash
cc-deep-research research "Impact of AI on healthcare industry"
```

### Complex Research Scenarios

**Multi-faceted topic:**

```bash
cc-deep-research research --team-size 6 --sources 30 \
  "Economic, social, and environmental impacts of renewable energy transition"
```

**Technical deep-dive:**

```bash
cc-deep-research research --monitor --format json \
  "Latest breakthroughs in quantum error correction" > quantum_ec.json
```

**Comparative analysis:**

```bash
cc-deep-research research \
  "Comparison of cloud computing providers: AWS vs Azure vs Google Cloud"
```

### Saving and Exporting Reports

**Save to specific location:**

```bash
cc-deep-research research -o ~/reports/renewable-energy.md "Renewable energy trends"
```

**Multiple reports with timestamp:**

```bash
cc-deep-research research -o "reports/ai-$(date +%Y%m%d).md" "AI developments"
```

**JSON for automation:**

```bash
cc-deep-research research --format json "Machine learning trends" | \
  jq '.sources | length'  # Count sources using jq
```

### Using Different Output Formats

**Markdown for documentation:**

```bash
cc-deep-research research --format markdown -o docs/api.md "REST API best practices"
```

**JSON for data analysis:**

```bash
cc-deep-research research --format json "Climate data" | \
  python analyze_data.py
```

### Parallel Collection Configuration Examples

**Smaller local roster metadata for quick queries:**

```bash
cc-deep-research research --team-size 2 --no-cross-ref "Quick lookup"
```

**Larger local roster metadata for comprehensive research:**

```bash
cc-deep-research research --team-size 8 --sources 50 --depth deep \
  "Comprehensive analysis of global supply chains"
```

**Sequential source collection for debugging:**

```bash
cc-deep-research research --no-team --verbose "Test query"
```

### Monitoring and Debugging

For live operator visibility, prefer the browser dashboard. Use `--monitor` when you want extra terminal output during a CLI run.

**Terminal monitoring output:**

```bash
cc-deep-research research --monitor "Complex topic"
```

**Parallel timeline in the terminal:**

```bash
cc-deep-research research --parallel-mode --show-timeline "Complex topic"
```

**Verbose output for troubleshooting:**

```bash
cc-deep-research research --verbose --monitor "Problematic query"
```

**Quiet mode for automation:**

```bash
cc-deep-research research --quiet -o report.md "Automated research" > /dev/null
```

### Monitoring Dashboards

There are two operator-facing dashboard paths, and they serve different purposes.

Telemetry files are written for normal `research` runs. `--monitor` only adds console monitoring output.

```bash
# Recommended: start backend + frontend together
cd dashboard
npm install
npm run dev
```

Then open `http://localhost:3000` and start research from the home page. That browser-first flow gives you:

- live progress updates over WebSocket
- session and report views in the same UI
- no separate `research` terminal required

If you want to run backend and frontend separately for development:

```bash
# Terminal 1: backend API only
cc-deep-research dashboard --port 8000

# Terminal 2: frontend only
cd dashboard
npm run dev:frontend
```

If the backend is not on the default host, set one of these before `npm run dev` or `npm run build`:

```bash
export NEXT_PUBLIC_CC_BACKEND_ORIGIN=http://localhost:8000
export NEXT_PUBLIC_CC_API_BASE_URL=http://localhost:8000/api
export NEXT_PUBLIC_CC_WS_BASE_URL=ws://localhost:8000/ws
```

The separate Streamlit telemetry dashboard is still available for live tails and historical analytics:

```bash
# Start a research run from the CLI
cc-deep-research research "Complex topic"

# Open the telemetry dashboard in another terminal
cc-deep-research telemetry dashboard --port 8501 --refresh-seconds 5 --tail-limit 200
```

The Streamlit telemetry dashboard combines two data paths:

- live session reads from `events.jsonl` so active runs appear immediately
- historical DuckDB analytics for completed session trends and summaries

Use the dashboard to answer:

- what phase is running now
- what happened most recently
- which local component or researcher task is active
- recent routed LLM telemetry and fallback activity

Useful dashboard command options:

- `--refresh-seconds 0` disables auto-refresh
- `--tail-limit N` limits the event tail and subprocess chunk panes
- `--base-dir PATH` points the dashboard at a non-default telemetry directory
- `--db-path PATH` stores historical analytics in a custom DuckDB file

For the implementation-level architecture and event model, see [`docs/TELEMETRY.md`](TELEMETRY.md).

---

## Troubleshooting

### Common Issues and Solutions

#### Issue: "No Tavily API keys configured"

**Problem:** The tool cannot find Tavily API keys.

**Solutions:**

```bash
# Set environment variable
export TAVILY_API_KEYS=your_api_key_here

# Or set via config command
cc-deep-research config set tavily.api_keys your_api_key_here

# Verify configuration
cc-deep-research config show
```

#### Issue: "API key rate limit exceeded"

**Problem:** Tavily API key has reached its monthly limit.

**Solutions:**

```bash
# Add multiple API keys for rotation
export TAVILY_API_KEYS=key1,key2,key3

# Or use Claude-only mode
cc-deep-research research --claude-only "Your query"
```

#### Issue: "Research timeout"

**Problem:** Research takes too long and times out.

**Solutions:**

```bash
# Reduce research depth
cc-deep-research research -d quick "Your query"

# Reduce minimum sources
cc-deep-research research -s 10 "Your query"

# Use smaller team size
cc-deep-research research --team-size 2 "Your query"

# Disable iterative search
cc-deep-research config set research.enable_iterative_search false
```

#### Issue: "Dashboard dependencies are missing"

**Problem:** `telemetry dashboard` fails because Streamlit, pandas, or DuckDB are not installed.

**Solutions:**

```bash
pip install "cc-deep-research[dashboard]"
```

#### Issue: "Dashboard shows no telemetry yet"

**Problem:** The dashboard opens but there are no active or historical sessions to inspect.

**Solutions:**

```bash
# Browser-first monitoring: start the combined launcher
cd dashboard
npm run dev

# Then open http://localhost:3000 and launch a run from the home page

# Or, for the Streamlit telemetry dashboard, point it at an existing telemetry directory
cc-deep-research telemetry dashboard --base-dir /path/to/telemetry
```

Notes:

- the browser dashboard shows live runs started through its backend
- the Streamlit telemetry dashboard reads persisted telemetry from normal `research` runs
- `--monitor` adds terminal logs but is not required for telemetry persistence

#### Issue: "No LLM route available"

**Problem:** Claude-backed analysis falls back to heuristics because the run is already inside a Claude Code session.

**Solutions:**

```bash
# Use heuristic mode explicitly to avoid the fallback warning
cc-deep-research config set research.ai_integration_method heuristic
```

The dashboard will still show the failure or fallback events in the live session view.

#### Issue: "Parallel collection errors"

**Problem:** Parallel source collection encounters errors during execution.

**Solutions:**

```bash
# Use sequential source collection
cc-deep-research research --no-team "Your query"

# Use verbose output for debugging
cc-deep-research research --verbose --monitor "Your query"

# Reduce local roster metadata size
cc-deep-research research --team-size 2 "Your query"
```

#### Issue: "Configuration file not found"

**Problem:** Tool cannot locate configuration file.

**Solutions:**

```bash
# Initialize default config
cc-deep-research config init

# Or specify custom config path
export CC_DEEP_RESEARCH_CONFIG=/path/to/config.yaml

# Verify config file exists
cat ~/.config/cc-deep-research/config.yaml
```

### API Key Problems

#### Invalid API Key

```bash
# Verify your API key is correct
curl -X POST https://api.tavily.com/search \
  -H "Content-Type: application/json" \
  -d '{"api_key": "your_key", "query": "test"}'

# Update if needed
cc-deep-research config set tavily.api_keys correct_key_here
```

#### Expired API Key

```bash
# Replace with new key
export TAVILY_API_KEYS=new_api_key_here

# Or add to existing keys
cc-deep-research config set tavily.api_keys old_key,new_key
```

### Configuration Errors

#### Invalid Configuration Values

```bash
# Reset to default config
cc-deep-research config init --force

# Or manually edit config file
nano ~/.config/cc-deep-research/config.yaml
```

#### Type Mismatch in Config

```bash
# Ensure values match expected types
cc-deep-research config set search_team.team_size 4          # Integer, not string
cc-deep-research config set research.enable_cross_ref true   # Boolean, not string
```

### Network Issues

#### Connection Timeouts

```bash
# Check internet connection
ping tavily.com

# Increase timeout (edit config)
cc-deep-research config set search_team.timeout_seconds 600
```

#### Proxy Configuration

If behind a proxy, set environment variables:

```bash
export HTTP_PROXY=http://proxy.example.com:8080
export HTTPS_PROXY=http://proxy.example.com:8080
```

### Getting Help

**Display help:**

```bash
# General help
cc-deep-research --help

# Research command help
cc-deep-research research --help

# Config command help
cc-deep-research config --help
```

**Check version:**

```bash
cc-deep-research --version
```

**Verbose debugging:**

```bash
cc-deep-research research --verbose --monitor "Test query"
```

---

## Best Practices

### Choosing the Right Research Depth

| Use Case               | Recommended Depth | Reasoning                            |
| ---------------------- | ----------------- | ------------------------------------ |
| Quick fact-check       | Quick             | Fast, minimal overhead               |
| Simple questions       | Quick or Standard | Balance of speed and depth           |
| Topic overview         | Standard          | Good coverage without excessive time |
| Learning a new topic   | Standard          | Sufficient detail for understanding  |
| Comprehensive research | Deep              | Maximum depth and analysis           |
| Academic work          | Deep              | Full citations and cross-referencing |
| Competitive analysis   | Deep              | Thorough coverage of all aspects     |

### Optimizing for Speed vs. Depth

**For speed (fast results):**

```bash
cc-deep-research research -d quick --no-team --no-cross-ref "Simple query"
```

**For balanced performance:**

```bash
cc-deep-research research -d standard --team-size 4 "Moderate query"
```

**For depth (comprehensive results):**

```bash
cc-deep-research research -d deep --team-size 6 --sources 30 "Complex query"
```

### Managing Multiple Research Sessions

**Organize reports by topic:**

```bash
mkdir -p ~/research/{ai,quantum,climate}
cc-deep-research research -o ~/research/ai/report.md "AI topic"
cc-deep-research research -o ~/research/quantum/report.md "Quantum topic"
```

**Use timestamped filenames:**

```bash
cc-deep-research research -o "reports/$(date +%Y%m%d-%H%M%S).md" "Dynamic topic"
```

**Automate with scripts:**

```bash
#!/bin/bash
# research.sh
TOPIC="$1"
DATE=$(date +%Y%m%d)
OUTPUT="reports/$DATE-$TOPIC.md"
cc-deep-research research -o "$OUTPUT" "$TOPIC"
```

### Effective Query Formulation

**Be specific:**

```bash
# Better
cc-deep-research research "Impact of GPT-4 on software development productivity"

# Avoid
cc-deep-research research "AI and programming"
```

**Include context:**

```bash
cc-deep-research research "Python 3.11 performance improvements over Python 3.10"
```

**Use natural language:**

```bash
cc-deep-research research "What are the best practices for securing AWS S3 buckets?"
```

**Ask for comparisons:**

```bash
cc-deep-research research "PostgreSQL vs MongoDB: performance comparison for analytical workloads"
```

**Request examples:**

```bash
cc-deep-research research "Real-world applications of edge computing in manufacturing"
```

### Resource Management

**Limit concurrent sessions:**

```bash
# Avoid running multiple deep research sessions simultaneously
# Instead, queue them or use smaller teams
```

**Monitor API usage:**

```bash
# Check Tavily dashboard for API key usage
# Rotate keys before hitting limits
```

**Clean up old reports:**

```bash
# Remove old research reports
find reports/ -name "*.md" -mtime +30 -delete
```

### Integration with Workflows

**Use in CI/CD:**

```bash
# GitHub Actions example
- name: Research
  run: |
    export TAVILY_API_KEYS=${{ secrets.TAVILY_API_KEY }}
    cc-deep-research research --quiet -o research.md "${{ inputs.topic }}"
```

**Combine with other tools:**

```bash
# Research then analyze
cc-deep-research research --format json "Topic" | python analyze.py
```

**Automate periodic research:**

```bash
# Cron job for daily research
0 9 * * * /path/to/research.sh "Daily topic" >> ~/logs/research.log 2>&1
```

### Security Best Practices

**Protect API keys:**

```bash
# Never commit API keys to version control
echo "*.key" >> .gitignore
echo "api_keys.env" >> .gitignore
```

**Use environment variables:**

```bash
# Store in secure location
# Add to .bashrc or .zshrc with proper permissions
chmod 600 ~/.env/cc-deep-research
source ~/.env/cc-deep-research
```

**Rotate keys regularly:**

```bash
# Update API keys periodically
cc-deep-research config set tavily.api_keys new_key_1,new_key_2
```

---

## Additional Resources

- **Project Repository:** [GitHub Repository URL]
- **Tavily Documentation:** [https://docs.tavily.com](https://docs.tavily.com)
- **Claude Code Documentation:** [https://claude.ai/docs](https://claude.ai/docs)
- **Issue Tracker:** Report bugs and feature requests

---

## License

[Your License Here]

---

## Changelog

See [CHANGELOG.md](../CHANGELOG.md) for version history and [RELEASING.md](RELEASING.md) for the release workflow.
