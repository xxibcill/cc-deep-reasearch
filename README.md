# CC Deep Research CLI

CLI for multi-stage web research using Tavily search, a local specialist pipeline, session persistence, and telemetry analytics.

Current codebase version: `0.1.0`

## Features

- Multi-stage research workflow (strategy, query expansion, source collection, analysis, validation, reporting)
- Depth modes: `quick`, `standard`, `deep` (default)
- Parallel local researcher-task execution with optional timeline view
- Source quality scoring and cross-reference analysis
- Session persistence with list/show/export/delete commands
- Telemetry ingestion to DuckDB and Streamlit dashboard
- Markdown, HTML, and JSON report output, optional PDF export via HTML rendering
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

Available top-level commands and groups:

- `research` - Run a research query and generate report output
- `markdown-to-html` - Convert an existing markdown file into a styled HTML report
- `markdown-to-pdf` - Convert an existing markdown file into a styled PDF report
- `benchmark` - Run the versioned benchmark corpus (`run`)
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

# HTML output
cc-deep-research research --format html -o reports/topic.html "Topic"

# Disable team mode (sequential)
cc-deep-research research --no-team "Topic"

# Parallel controls
cc-deep-research research --parallel-mode --num-researchers 4 --show-timeline "Topic"

# Telemetry monitor output during run
cc-deep-research research --monitor "Topic"

# Generate PDF in addition to report output
cc-deep-research research --pdf "Topic"

# Convert an existing markdown report into HTML, then PDF
cc-deep-research markdown-to-html reports/topic.md
cc-deep-research markdown-to-pdf reports/topic.md
```

## Research Flags (Current)

- `-d, --depth [quick|standard|deep]`
- `-s, --sources INTEGER`
- `-o, --output FILE`
- `--format [markdown|json|html]`
- `--no-cross-ref`
- `--tavily-only`
- `--claude-only` (accepted but no Claude search provider is implemented yet)
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

Telemetry persistence is enabled for normal `research` runs. `--monitor` only turns on console monitoring output.

Recommended operator workflow:

```bash
# Install dashboard dependencies
pip install "cc-deep-research[dashboard]"

# Start a research run (add --monitor if you also want console logs)
cc-deep-research research "Topic"

# Launch the live dashboard
cc-deep-research telemetry dashboard --port 8501 --refresh-seconds 5 --tail-limit 200

# Optional: refresh historical analytics without opening the UI
cc-deep-research telemetry ingest
```

The dashboard now reads active `events.jsonl` sessions directly, so you can inspect:

- the current phase of an in-flight run
- recent event tail entries with filters
- agent activity
- Claude CLI stdout and stderr chunks with terminal status

Common failure modes:

- Missing dashboard dependencies: install `cc-deep-research[dashboard]`
- No telemetry yet: start a research run first, or point `telemetry dashboard` at a populated `--base-dir`
- Nested Claude session fallback: when running inside Claude Code, Claude CLI analysis is disabled and the workflow falls back to heuristic analysis
- Claude timeout or subprocess failure: inspect the Claude subprocess pane in the dashboard for `timeout`, `failed`, or `failed_to_start` events

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

## LLM Routing Configuration

CC Deep Research supports multiple LLM backends for agent-level routing. The system can route different agents to different LLM providers based on availability and configuration.

### Supported Transports

| Transport | Description | Best For |
|-----------|-------------|----------|
| `claude_cli` | Claude Code CLI subprocess | Full Claude capabilities, nested session detection |
| `openrouter_api` | OpenRouter API | Multi-model access, cost optimization |
| `cerebras_api` | Cerebras API | Fast inference, low latency |
| `heuristic` | Rule-based fallback | No external dependencies |

### Configuration

Configure LLM routing in `~/.config/cc-deep-research/config.yaml`:

```yaml
llm:
  # Claude CLI configuration
  claude_cli:
    enabled: true
    model: "claude-sonnet-4-6"
    timeout_seconds: 120

  # OpenRouter configuration
  openrouter:
    enabled: false
    api_key: "${OPENROUTER_API_KEY}"
    model: "anthropic/claude-sonnet-4"
    base_url: "https://openrouter.ai/api/v1"

  # Cerebras configuration
  cerebras:
    enabled: false
    api_key: "${CEREBRAS_API_KEY}"
    model: "llama-3.3-70b"
    base_url: "https://api.cerebras.ai/v1"

  # Fallback order when primary transport fails
  fallback_order:
    - "claude_cli"
    - "openrouter"
    - "cerebras"
    - "heuristic"

  # Per-agent route defaults (optional)
  route_defaults:
    analyzer: "openrouter"      # Use OpenRouter for analysis
    deep_analyzer: "cerebras"   # Use Cerebras for deep analysis
    report_quality_evaluator: "claude_cli"  # Use Claude CLI for report evaluation
    reporter: "claude_cli"      # Default route for report-generation helpers
    default: "claude_cli"
```

### Mixed-Route Sessions

The planner can assign different routes to different agents within the same session. For example:

- **Analyzer agent** → OpenRouter (cost-effective for large context)
- **Deep analyzer agent** → Cerebras (fast structured synthesis)
- **Report quality evaluator** → Claude CLI (high-quality final pass)

This allows operators to optimize for both cost and quality across one run. The active CLI path now routes analyzer, deep analyzer, and report-quality evaluation through the shared LLM layer, while preserving heuristic fallback when no external transport is available.

### Nested Session Detection

When running inside Claude Code, the system automatically detects the nested session and falls back to alternative transports or heuristic analysis. This prevents recursive Claude CLI calls.

### Telemetry and Route Tracking

Each session records LLM route usage in telemetry:

```bash
# View route analytics for a session
cc-deep-research telemetry dashboard
# Navigate to "LLM Route Analytics" section
```

Route telemetry includes:
- Transport used per agent
- Token counts by transport
- Fallback events and reasons
- Latency metrics per route

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

## Versioning

Project versions follow Semantic Versioning. Record user-visible changes in [`CHANGELOG.md`](CHANGELOG.md) under `Unreleased`, then cut the next version with:

```bash
uv run python scripts/bump_version.py patch
```

You can also pass an explicit version such as `uv run python scripts/bump_version.py 0.2.0`. The full release workflow is documented in [`docs/RELEASING.md`](docs/RELEASING.md).

## Documentation

- [Usage Guide](docs/USAGE.md)
- [Telemetry Architecture](docs/TELEMETRY.md)
- [Examples](docs/EXAMPLES.md)
- [Research Workflow Design](docs/RESEARCH_WORKFLOW.md)
- [Research Workflow and Agent Interactions](docs/RESEARCH_WORKFLOW_AGENT_INTERACTIONS.md)
- [Research Workflow Improvement Plan](docs/RESEARCH_WORKFLOW_IMPROVEMENT_PLAN.md)

## Benchmark Corpus

The repository includes a versioned benchmark query corpus at [`docs/benchmark_corpus.json`](docs/benchmark_corpus.json). It is designed to stay stable across workflow changes and currently covers:

- simple factual queries
- comparison queries
- time-sensitive queries
- evidence-heavy science or health queries
- market or policy queries

Each case includes a `case_id`, `category`, `rationale`, and `date_sensitive` flag so scripts can segment results and handle freshness-sensitive prompts explicitly.

Run the full corpus with one command:

```bash
cc-deep-research benchmark run --depth standard --output-dir benchmark_runs/latest
```

The harness writes deterministic JSON outputs for comparison:

- `benchmark_runs/latest/manifest.json`
- `benchmark_runs/latest/scorecard.json`
- `benchmark_runs/latest/cases/<case_id>.json`

Load it from Python with:

```python
from cc_deep_research.benchmark import load_benchmark_corpus

corpus = load_benchmark_corpus()
for case in corpus.cases:
    print(case.case_id, case.category, case.query)
```

## Requirements

- Python 3.11+
- Tavily API key(s)

## License

MIT
