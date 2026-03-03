# CC Deep Research CLI

A powerful deep research engine that builds on top of Claude Code, combining Tavily's professional web search API with Claude Code's built-in search capabilities.

## Features

- **Agent Team Research** - Uses multiple specialized AI agents working together for coordinated research
- **Parallel Agent Execution** - Agents work in parallel for faster, more comprehensive research
- **Hybrid Parallel Search** - Runs Tavily and Claude Code search simultaneously for comprehensive results
- **Deep Dive Research** - Default mode with 20+ sources, cross-referencing, and comprehensive analysis
- **API Key Rotation** - Automatic management of multiple Tavily API keys with graceful failover
- **Smart Query Expansion** - Automatically generates query variations for comprehensive coverage
- **Iterative Search** - Analyzes gaps in results and performs follow-up searches
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
- Save the report to your current directory

**Example Output:**
```
# Research Report: Latest Developments in Quantum Computing

## Executive Summary
[2-3 paragraph summary of key findings...]

## Key Findings
### 1. Recent Breakthroughs in Quantum Error Correction
[Analysis with citations...]
[1] https://example.com/article1

### 2. Scaling Quantum Computers to 1000+ Qubits
[Analysis with citations...]
[2] https://example.com/article2

## Sources
1. [Title](https://example.com/article1) - Description
2. [Title](https://example.com/article2) - Description
```

## Common Commands

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

## Installation
```
# Research Report: Latest Developments in Quantum Computing

## Executive Summary
[2-3 paragraph summary of key findings...]

## Key Findings
### 1. Recent Breakthroughs in Quantum Error Correction
[Analysis with citations...]
[1] https://example.com/article1

### 2. Scaling Quantum Computers to 1000+ Qubits
[Analysis with citations...]
[2] https://example.com/article2

## Sources
1. [Title](https://example.com/article1) - Description
2. [Title](https://example.com/article2) - Description
```

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

## Configuration

Set your Tavily API keys for web search:

```bash
export TAVILY_API_KEYS=key1,key2,key3
```

Or use the config command:

```bash
cc-deep-research config set tavily.api_keys key1,key2,key3
```

## Usage

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

# Use only Claude Code search
cc-deep-research research --claude-only "Machine learning trends"

# Specify minimum sources
cc-deep-research research -s 30 "Comprehensive topic"

# JSON output
cc-deep-research research --format json "Query" > results.json

# Custom team size
cc-deep-research research --team-size 6 "Complex topic"
```

### Configuration Management

```bash
# Show current configuration
cc-deep-research config show

# Set configuration value
cc-deep-research config set research.min_sources_deep 25

# Edit config file
cc-deep-research config edit
```

### Session Management

```bash
# List saved sessions
cc-deep-research session list

# Show session details
cc-deep-deep research session show <session-id>

# Export session
cc-deep-research session export <session-id> -o report.md
```

## Research Modes

| Mode | Sources | Time | Best For |
|------|---------|------|----------|
| Quick | 3-5 | 1-2 min | Fact-checking, basic queries |
| Standard | 10-15 | 3-5 min | General research, overviews |
| Deep (default) | 20+ | 5-10 min | Thorough research, detailed understanding |

## Output Format

The tool generates comprehensive markdown reports with:

- **Executive Summary** - 2-3 paragraph overview of key findings
- **Key Findings** - Organized sections with citations
- **Detailed Analysis** - Comprehensive analysis with cross-references
- **Cross-Reference Analysis** - Consensus points and areas of contention
- **Sources** - Numbered list of all sources with URLs
- **Metadata** - Research session information (time, sources used, etc.)

## Project Structure

```
cc-deep-research/
├── src/cc_deep_research/
│   ├── cli/              # CLI interface (click commands)
│   ├── search/           # Search provider implementations
│   ├── orchestrator/     # Research orchestration logic
│   ├── reporting/        # Report generation
│   └── config/           # Configuration management
├── tests/                # Test suite
├── .ralph/              # Ralph AI assistant configuration
└── README.md
```

## Development

This project uses the [Ralph Wiggum](https://github.com/anthropics/claude-code) AI assistant for autonomous development.

See `.ralph/specs/` for detailed specifications:
- `deep-research-core.md` - Core infrastructure
- `deep-research-features.md` - Research features
- `cli-interface.md` - CLI interface

## Requirements

- Python 3.11+
- Tavily API key(s)
- Claude Code (for built-in search integration)

## License

[Add your license here]
