# CC Deep Research CLI

CLI for multi-stage web research using Tavily search, a local specialist pipeline, session persistence, and telemetry analytics.

Current codebase version: `0.1.0`

## Features

- Multi-stage research workflow (strategy, query expansion, source collection, analysis, validation, reporting)
- Depth modes: `quick`, `standard`, `deep` (default)
- Parallel local source-collection tasks with optional timeline view
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
cc-deep-research [OPTIONS] COMMAND [ARGS]...
```

Available top-level commands and groups:

- `research` - Run a research query and generate report output
- `markdown-to-html` - Convert an existing markdown file into a styled HTML report
- `markdown-to-pdf` - Convert an existing markdown file into a styled PDF report
- `benchmark` - Run the versioned benchmark corpus (`run`)
- `config` - Manage configuration (`show`, `set`, `init`)
- `session` - Manage persisted sessions (`list`, `show`, `export`, `delete`, `audit`, `bundle`, `checkpoints`, `reconcile`)
- `telemetry` - Ingest telemetry and launch dashboard (`ingest`, `dashboard`)
- `dashboard` - Start the real-time monitoring dashboard server
- `detect-theme` - Detect the research theme for a query
- `list-themes` - List all available research themes
- `content-gen` - Content generation workflow for short-form video
- `anthropic` - Anthropic API commands

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

# Force sequential source collection
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
- `--no-team` (force sequential local source collection)
- `--team-size INTEGER` (override compatibility metadata only)
- `--progress`
- `--quiet`
- `--verbose`
- `--monitor`
- `--parallel-mode`
- `--num-researchers INTEGER`
- `--show-timeline`
- `--pdf`
- `--enable-realtime`
- `--workflow [staged|planner]` (research workflow to use)
- `--theme [general|resources|trip_planning|due_diligence|market_research|business_ideas|content_creation]` (research theme for tailored workflow)

## Telemetry Dashboard

Telemetry files are written under:

- `~/.config/cc-deep-research/telemetry/<session_id>/events.jsonl`
- `~/.config/cc-deep-research/telemetry/<session_id>/summary.json`

Telemetry persistence is enabled for normal `research` runs. `--monitor` only turns on console monitoring output.

`--no-team` only disables parallel local source collection. The run still goes through the same local orchestrator and specialist components.

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

For the browser-based operator console, use the Next.js dashboard in [`dashboard/`](dashboard):

```bash
cd dashboard
npm install
npm run dev
```

That launcher starts the FastAPI backend on `http://localhost:8000` and the frontend on `http://localhost:3000`. If you only want the backend API, run `cc-deep-research dashboard --host localhost --port 8000`.

The dashboard now reads active `events.jsonl` sessions directly, so you can inspect:

- the current phase of an in-flight run
- recent event tail entries with filters
- agent activity
- routed LLM activity and fallback telemetry

Common failure modes:

- Missing dashboard dependencies: install `cc-deep-research[dashboard]`
- No telemetry yet: start a research run first, or point `telemetry dashboard` at a populated `--base-dir`
- No LLM route available: the workflow falls back to heuristic analysis
- Provider timeout or failure: inspect the LLM route analytics pane in the dashboard for fallback and failure events

## Execution Traces

CC Deep Research already has a practical execution-trace foundation. Each run writes structured telemetry to `events.jsonl` and `summary.json`, and every event can carry an `event_id`, `parent_event_id`, `sequence_number`, and timestamp. That gives the project enough structure to reconstruct ordered traces, parent/child relationships, event trees, subprocess streams, and timeline-oriented views in the dashboards.

What works well right now:

- traces are persistent by default for normal `research` runs
- live sessions can be inspected before the run finishes
- event ordering and parent/child correlation are explicit, not inferred from console text
- the UI already exposes a workflow graph, event table, critical-path summary, and compact execution-trace terminology via `--show-timeline`

How good it is today:

- good for operator visibility and post-run debugging
- good for understanding phase flow, agent activity, tool calls, and LLM route behavior
- not yet a full distributed-tracing style system with span semantics, trace search, or cross-run comparison built into the core UX

How it can improve:

- promote `operation.started` / `operation.finished` into more explicit span-style trace views
- add first-class trace IDs and trace summaries at the session and subtask level
- support trace diffing between runs to compare regressions, latency shifts, and fallback patterns
- expose richer subprocess and tool nesting so long chains are easier to inspect without opening raw events

## Agent-Level Logs

The project does have agent-level logs, but they are primarily implemented as structured telemetry events rather than a separate traditional log subsystem. Parallel researchers emit `agent.spawned`, `agent.started`, `agent.completed`, `agent.failed`, and `agent.timeout` events, and agent context also flows into tool, reasoning, and LLM-route events through `agent_id`.

What works well right now:

- agent lifecycle is visible in both raw events and the agent timeline
- tool calls and LLM route activity can be tied back to specific agents
- reasoning summaries can be attached to an agent for human-readable debugging
- the model-routing layer already captures agent-specific provider, transport, token, and fallback data

How good it is today:

- good for understanding what each agent did and when it did it
- good for debugging parallel local task execution and route selection
- weaker if you want rich per-agent narrative logs, stdout-style transcripts, or a complete "agent journal" in one place

How it can improve:

- add a dedicated per-agent log view that merges lifecycle, reasoning, tools, state changes, and failures into one ordered stream
- standardize more agent event names and metadata contracts across all orchestration paths
- capture more structured intermediate outputs from agents, not only completion summaries
- distinguish system events from agent-authored events more clearly in the UI and exported telemetry

## Decision Graphs

Decision graphs now exist as a first-class derived output in the dashboard, session-detail API, and trace-bundle export. The telemetry layer builds a graph from explicit `decision.made`, `state.changed`, `degradation.detected`, and failure/error events, then adds a small set of deterministic inferred links for operator review.

What works well right now:

- decisions can be recorded with chosen option, rejected options, confidence, inputs, and cause event IDs
- the dashboard has a dedicated decision-graph view separate from the workflow graph
- the derived outputs panel can jump directly into the graph for deeper inspection
- critical path and issue extraction help connect decisions to execution bottlenecks and degraded states

How good it is today:

- good for operator review when sessions emit the relevant telemetry
- good enough to inspect routing, fallback, provider-state, mitigation, and iteration-control decisions in one place
- still bounded by telemetry coverage and deliberately conservative inference rules

How it can improve:

- expand explicit decision coverage across more orchestration branches and long-tail recovery paths
- expose richer graph export and offline review tools
- add run-to-run comparison once graph density and stability are strong enough
- support export of decision graphs for incident review, benchmark comparisons, and design analysis

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

`session delete` removes the saved session record, saved summary, and saved report artifacts from the local session store. To purge telemetry directories and DuckDB analytics records as well, use the browser dashboard delete flow or the backend session-delete API.

## Configuration

Configuration file path:

- `~/.config/cc-deep-research/config.yaml`

Initialize/show/set:

```bash
cc-deep-research config init
cc-deep-research config show
cc-deep-research config set tavily.api_keys key1,key2,key3
```

Common environment-variable overrides:

- `TAVILY_API_KEYS`
- `CC_DEEP_RESEARCH_CONFIG`
- `CC_DEEP_RESEARCH_DEPTH`
- `CC_DEEP_RESEARCH_FORMAT`
- `NO_COLOR`
- `OPENROUTER_API_KEY` or `OPENROUTER_API_KEYS`
- `CEREBRAS_API_KEY` or `CEREBRAS_API_KEYS`
- `ANTHROPIC_API_KEY` or `ANTHROPIC_API_KEYS`

The CLI also loads a project-root `.env` file at startup without overwriting env vars that are already set in your shell.

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
| `anthropic_api` | Anthropic API | Direct Claude API access without the CLI |
| `openrouter_api` | OpenRouter API | Multi-model access, cost optimization |
| `cerebras_api` | Cerebras API | Fast inference, low latency |
| `heuristic` | Rule-based fallback | No external dependencies |

### Configuration

Configure LLM routing in `~/.config/cc-deep-research/config.yaml`:

```yaml
llm:
  # Anthropic configuration
  anthropic:
    enabled: false
    api_key: "${ANTHROPIC_API_KEY}"
    model: "claude-sonnet-4-6"
    base_url: "https://api.anthropic.com"

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
    - "anthropic"
    - "openrouter"
    - "cerebras"
    - "heuristic"

  # Per-agent route defaults (optional)
  route_defaults:
    analyzer: "openrouter"      # Use OpenRouter for analysis
    deep_analyzer: "cerebras"   # Use Cerebras for deep analysis
    report_quality_evaluator: "anthropic"   # Use Anthropic for report evaluation
    reporter: "anthropic"       # Default route for report-generation helpers
    default: "anthropic"
```

The provider sections above can also be populated from env vars. The runtime accepts both single-key and comma-separated multi-key forms for OpenRouter, Cerebras, and Anthropic.

### Mixed-Route Sessions

The planner can assign different routes to different agents within the same session. For example:

- **Analyzer agent** → OpenRouter (cost-effective for large context)
- **Deep analyzer agent** → Cerebras (fast structured synthesis)
- **Report quality evaluator** → Anthropic API (high-quality final pass)

This allows operators to optimize for both cost and quality across one run while preserving heuristic fallback when no external transport is available.

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
- [Research Workflow Design](docs/RESEARCH_WORKFLOW.md)
- [Research Workflow and Agent Interactions](docs/RESEARCH_WORKFLOW_AGENT_INTERACTIONS.md)
- [Dashboard Guide](docs/DASHBOARD_GUIDE.md)
- [Content-Generation Workflow](docs/content-generation/content-generation.md)
- [Documentation Index](docs/README.md)

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
