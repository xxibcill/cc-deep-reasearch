# CC Deep Research CLI

A powerful deep research engine that builds on top of Claude Code, combining Tavily's professional web search API with Claude Code's built-in search capabilities.

## Features

- **Hybrid Parallel Search** - Runs Tavily and Claude Code search simultaneously for comprehensive results
- **Deep Dive Research** - Default mode with 20+ sources, cross-referencing, and comprehensive analysis
- **API Key Rotation** - Automatic management of multiple Tavily API keys with graceful failover
- **Smart Query Expansion** - Automatically generates query variations for comprehensive coverage
- **Iterative Search** - Analyzes gaps in results and performs follow-up searches
- **Source Quality Scoring** - Evaluates and ranks sources by credibility, relevance, freshness, and diversity
- **Markdown Reports** - Generates structured reports with citations, executive summaries, and cross-reference analysis
- **Interactive CLI** - User-friendly command-line interface with progress indicators

## Installation

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
# Deep dive research (default)
cc-deep-research research "What are the latest developments in quantum computing?"

# Quick research
cc-deep-research research -d quick "What is the capital of Australia?"

# Save to specific file
cc-deep-research research -o report.md "Climate change statistics 2024"
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
