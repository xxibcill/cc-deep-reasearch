# CC Deep Research CLI - Examples

This document provides detailed examples for using the CC Deep Research CLI tool, from basic usage to advanced scenarios.

## Table of Contents

1. [Basic Examples](#basic-examples)
2. [Research Depth Examples](#research-depth-examples)
3. [Output Format Examples](#output-format-examples)
4. [Provider Selection Examples](#provider-selection-examples)
5. [Agent Team Configuration](#agent-team-configuration)
6. [Advanced Research Scenarios](#advanced-research-scenarios)
7. [Automation Examples](#automation-examples)
8. [Integration Examples](#integration-examples)

---

## Basic Examples

### Simple Fact-Checking

Quickly verify a fact with minimal overhead:

```bash
# Quick fact check about geography
cc-deep-research research -d quick "What is the population of Tokyo?"
```

**Output:**
```markdown
# Research Report: Population of Tokyo

## Executive Summary
Tokyo's population is approximately 14 million people within the 23 special wards, with the Greater Tokyo Area containing over 37 million residents, making it the world's most populous metropolitan area.

## Key Findings

### Current Population Estimates
- Tokyo proper (23 wards): ~14.0 million (2023 estimate)
- Tokyo Prefecture: ~14.1 million (2023 estimate)
- Greater Tokyo Area: ~37.4 million (2023 estimate)

## Sources
1. [Tokyo Metropolitan Government Population Statistics](https://www.metro.tokyo.lg.jp/english/about/population.html)
2. [Japan Statistics Bureau](https://www.stat.go.jp/english/data/jinsui/2023np/index.html)
3. [World Population Review](https://worldpopulationreview.com/world-cities/tokyo-population)
```

### Learning About a New Topic

Get a solid overview of a subject:

```bash
# Standard depth for topic overview
cc-deep-research research -d standard "History and development of electric vehicles"
```

### Comprehensive Research

Deep dive into complex topics:

```bash
# Deep research with default settings
cc-deep-research research "Impact of artificial intelligence on healthcare industry"
```

---

## Research Depth Examples

### Quick Mode

Use for fast fact-checking and simple queries:

```bash
# Quick weather information
cc-deep-research research -d quick "What is the weather like in Seattle in December?"

# Quick definition lookup
cc-deep-research research -d quick "What is quantum computing?"

# Quick statistics
cc-deep-research research -d quick "How many countries are in the European Union?"
```

**Characteristics:**
- 3-5 sources
- 1-2 minutes execution time
- Basic analysis
- Minimal cross-referencing

### Standard Mode

Balanced depth for general research:

```bash
# Learn about a technology
cc-deep-research research -d standard "Blockchain technology explained for beginners"

# Research a historical event
cc-deep-research research -d standard "Causes and consequences of the 2008 financial crisis"

# Understand a scientific concept
cc-deep-research research -d standard "How does CRISPR gene editing work?"
```

**Characteristics:**
- 10-15 sources
- 3-5 minutes execution time
- Moderate analysis
- Some cross-referencing

### Deep Mode

Comprehensive research for detailed understanding:

```bash
# Industry analysis
cc-deep-research research -d deep "Future of renewable energy: challenges and opportunities"

# Technical deep dive
cc-deep-research research -d deep "Advancements in quantum error correction algorithms"

# Academic-level research
cc-deep-research research -d deep "Ethical implications of AI in autonomous vehicles"
```

**Characteristics:**
- 20+ sources
- 5-10 minutes execution time
- Comprehensive analysis
- Full cross-referencing

### Custom Source Count

Override default minimum sources:

```bash
# Require exactly 10 sources
cc-deep-research research -s 10 "Topic requiring specific depth"

# Comprehensive research with 50+ sources
cc-deep-research research -s 50 "Extremely comprehensive topic"

# Light research with just 5 sources
cc-deep-research research -s 5 "Light overview"
```

---

## Output Format Examples

### Markdown Output (Default)

Generate human-readable markdown reports:

```bash
# Save markdown report to file
cc-deep-research research -o ~/reports/quantum.md "Quantum computing applications"

# Print to stdout
cc-deep-research research "Climate change effects on agriculture"
```

**Sample markdown output:**
```markdown
# Research Report: Climate Change Effects on Agriculture

## Executive Summary
Climate change poses significant challenges to global agriculture, affecting crop yields, water availability, and pest patterns. Adaptation strategies including crop diversification, improved irrigation, and climate-resilient varieties are being developed to mitigate these impacts.

## Key Findings

### 1. Crop Yield Changes
Studies show varying impacts across different crops and regions...

### 2. Water Resource Challenges
Changing precipitation patterns and increased evaporation...

## Sources
1. [IPCC Sixth Assessment Report](https://www.ipcc.ch/ar6/)
2. [FAO Climate-Smart Agriculture](https://www.fao.org/climate-smart-agriculture/)
3. [USDA Climate Adaptation](https://www.usda.gov/climate/adaptation)
```

### JSON Output

Generate structured JSON for programmatic use:

```bash
# Output to file
cc-deep-research research --format json -o results.json "Machine learning trends"

# Pipe to processing tool
cc-deep-research research --format json "Topic" | jq '.sources | length'

# Use in scripts
cc-deep-research research --format json "AI safety" | python analyze.py
```

**Sample JSON output:**
```json
{
  "query": "Machine learning trends",
  "depth": "deep",
  "executive_summary": "Machine learning continues to evolve with significant advancements in foundation models...",
  "key_findings": [
    {
      "title": "Foundation Models",
      "content": "Large language models like GPT-4 are transforming natural language processing...",
      "citations": [{"id": 1}, {"id": 3}]
    }
  ],
  "sources": [
    {
      "id": 1,
      "title": "Foundation Models: A New Paradigm",
      "url": "https://arxiv.org/abs/2101.06674",
      "score": 0.95
    }
  ]
}
```

### Combining Formats

Generate both formats for different uses:

```bash
# Generate both markdown and JSON
cc-deep-research research --format json -o results.json "Topic"
cc-deep-research research -o results.md "Topic"
```

Or use a script:

```bash
#!/bin/bash
QUERY="$1"
cc-deep-research research --format json -o "results/${QUERY}.json" "$QUERY"
cc-deep-research research -o "reports/${QUERY}.md" "$QUERY"
```

---

## Provider Selection Examples

### Using Tavily Only

Leverage Tavily's professional web search:

```bash
# Tavily-only search for web-focused topics
cc-deep-research research --tavily-only "Latest web development frameworks 2024"

# Use when you need current web content
cc-deep-research research --tavily-only "Breaking news about technology sector"
```

### Using Claude Only

Leverage Claude's knowledge base:

```bash
# Claude-only for conceptual topics
cc-deep-research research --claude-only "Philosophy of artificial intelligence"

# Use for well-established knowledge
cc-deep-research research --claude-only "Fundamental concepts in computer science"
```

### Hybrid Search (Default)

Combine both providers for comprehensive results:

```bash
# Default uses both providers
cc-deep-research research "Topic requiring both web and knowledge base"

# Explicitly specify hybrid mode
cc-deep-research research --tavily-only --claude-only "Comprehensive topic"
```

### Provider Configuration

Configure provider preferences:

```bash
# Set Tavily as primary
cc-deep-research config set search.mode tavily_primary

# Set Claude as primary
cc-deep-research config set search.mode claude_primary

# Use hybrid parallel (default)
cc-deep-research config set search.mode hybrid_parallel
```

---

## Agent Team Configuration

### Small Team (2-3 Agents)

Use for simple queries or resource-constrained environments:

```bash
# Minimal team for quick research
cc-deep-research research --team-size 2 "Simple lookup"

# Small team for moderate complexity
cc-deep-research research --team-size 3 "Moderate topic"
```

**Best for:**
- Fast execution
- Resource-constrained systems
- Simple queries
- Testing and debugging

### Standard Team (4-5 Agents)

Balanced team for most research tasks:

```bash
# Default team size
cc-deep-research research "Standard research query"

# Explicitly specify standard team
cc-deep-research research --team-size 4 "General topic"
```

**Best for:**
- General research
- Balanced performance
- Most use cases

### Large Team (6-8 Agents)

Maximum coverage for complex topics:

```bash
# Large team for comprehensive research
cc-deep-research research --team-size 6 "Complex multi-faceted topic"

# Maximum team size
cc-deep-research research --team-size 8 --sources 50 "Extremely complex topic"
```

**Best for:**
- Comprehensive research
- Multi-faceted topics
- Academic work
- When depth is critical

### Sequential Execution

Disable parallel execution for debugging or resource management:

```bash
# Use sequential mode
cc-deep-research research --no-team "Debugging query"

# Sequential with verbose output
cc-deep-research research --no-team --verbose "Test query"
```

**Best for:**
- Debugging
- Resource-constrained environments
- Understanding workflow
- Testing configurations

### Monitoring Agent Activity

See what agents are doing during execution:

```bash
# Monitor workflow execution
cc-deep-research research --monitor "Complex topic"

# Monitor with verbose output
cc-deep-research research --monitor --verbose "Debug topic"
```

---

## Advanced Research Scenarios

### Comparative Analysis

Research multiple aspects of a topic:

```bash
# Compare technologies
cc-deep-research research \
  "Comparison: Kubernetes vs Docker Swarm for container orchestration"

# Compare methodologies
cc-deep-research research \
  "Agile vs Waterfall: project management methodology comparison"

# Compare products/services
cc-deep-research research \
  "AWS vs Azure vs Google Cloud: comprehensive cloud provider comparison"
```

### Industry Analysis

Deep dive into specific industries:

```bash
# Tech industry trends
cc-deep-research research --team-size 6 --sources 40 \
  "Software development industry trends 2024: tools, practices, and salaries"

# Healthcare industry
cc-deep-research research --team-size 6 --sources 50 \
  "Digital transformation in healthcare: telemedicine, AI, and electronic records"

# Financial services
cc-deep-research research --team-size 5 --sources 35 \
  "Fintech innovations: blockchain, mobile banking, and AI in finance"
```

### Academic Research

Comprehensive research for academic purposes:

```bash
# Literature review
cc-deep-research research --depth deep --sources 30 \
  "Recent advances in natural language processing: transformer architectures"

# Theoretical foundations
cc-deep-research research --depth deep --sources 40 \
  "Theoretical foundations of quantum computing and quantum information theory"

# State-of-the-art survey
cc-deep-research research --depth deep --sources 50 \
  "State-of-the-art in computer vision: deep learning approaches and applications"
```

### Market Research

Research market trends and opportunities:

```bash
# Market sizing
cc-deep-research research \
  "Global electric vehicle market size, growth, and forecasts 2024-2030"

# Competitive landscape
cc-deep-research research --sources 30 \
  "Electric vehicle market: competitive analysis of Tesla, BYD, and traditional automakers"

# Consumer behavior
cc-deep-research research \
  "Consumer adoption of electric vehicles: barriers, incentives, and preferences"
```

### Technical Deep Dive

深入技术细节:

```bash
# Specific technology
cc-deep-research research --depth deep --sources 40 \
  "PostgreSQL performance tuning: indexing strategies, query optimization, and configuration"

# Development practices
cc-deep-research research --depth deep --sources 35 \
  "Best practices for microservices architecture: design patterns, and implementation"

# Security topics
cc-deep-research research --depth deep --sources 40 \
  "Application security: OWASP Top 10 vulnerabilities and mitigation strategies"
```

### Cross-Disciplinary Research

Research topics spanning multiple fields:

```bash
# AI and ethics
cc-deep-research research --team-size 6 --sources 45 \
  "Ethical considerations in artificial intelligence: bias, fairness, and transparency"

# Technology and society
cc-deep-research research --team-size 5 --sources 40 \
  "Social impact of social media: mental health, democracy, and communication patterns"

# Science and policy
cc-deep-research research --team-size 6 --sources 50 \
  "Climate change policy: international agreements, carbon pricing, and adaptation strategies"
```

---

## Automation Examples

### Batch Research

Automate multiple research queries:

```bash
#!/bin/bash
# research_batch.sh - Batch research script

TOPICS=(
    "AI in healthcare"
    "Quantum computing applications"
    "Blockchain technology"
    "Renewable energy trends"
    "Space exploration missions"
)

for topic in "${TOPICS[@]}"; do
    echo "Researching: $topic"
    filename=$(echo "$topic" | tr '[:upper:]' '[:lower:]' | tr ' ' '_')
    cc-deep-research research --quiet -o "reports/${filename}.md" "$topic"
    echo "Completed: $topic"
done

echo "Batch research completed"
```

### Scheduled Research

Use cron to run research periodically:

```bash
# Add to crontab for daily research at 9 AM
# 0 9 * * * /path/to/daily_research.sh >> ~/logs/research.log 2>&1

# daily_research.sh
#!/bin/bash
DATE=$(date +%Y%m%d)
cc-deep-research research --quiet -o "reports/daily_${DATE}.md" \
  "Latest developments in artificial intelligence"
```

### Conditional Research

Research based on conditions:

```bash
#!/bin/bash
# conditional_research.sh

# Check if research already exists for today
TODAY=$(date +%Y%m%d)
REPORT_FILE="reports/tech_trends_${TODAY}.md"

if [ ! -f "$REPORT_FILE" ]; then
    echo "Research not found for today. Conducting research..."
    cc-deep-research research --quiet -o "$REPORT_FILE" \
      "Technology trends and developments"
    echo "Research saved to $REPORT_FILE"
else
    echo "Research already exists for today: $REPORT_FILE"
fi
```

### Research with Notifications

Send notifications when research completes:

```bash
#!/bin/bash
# research_with_notification.sh

TOPIC="$1"
OUTPUT="reports/$(date +%Y%m%d-%H%M%S).md"

# Run research
cc-deep-research research --quiet -o "$OUTPUT" "$TOPIC"

# Send notification (macOS example)
osascript -e "display notification \"Research completed: $TOPIC\" with title \"CC Deep Research\""

# Or use terminal-notifier
# terminal-notifier -title "CC Deep Research" -message "Research completed: $TOPIC"
```

### Research Dashboard

Generate a summary of recent research:

```bash
#!/bin/bash
# research_dashboard.sh

echo "=== Recent Research Reports ==="
echo ""

# Find recent markdown files in reports directory
find reports/ -name "*.md" -mtime -7 -type f | while read -r file; do
    echo "File: $file"
    echo "Modified: $(stat -f "%Sm" -t "%Y-%m-%d %H:%M" "$file")"
    echo ""
done
```

---

## Integration Examples

### Integration with Note-Taking Tools

Research and organize in Obsidian/Notion:

```bash
#!/bin/bash
# obsidian_research.sh

VAULT_PATH="$HOME/Documents/ObsidianVault"
TOPIC="$1"
FILENAME=$(echo "$TOPIC" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')
REPORT_PATH="${VAULT_PATH}/Research/${FILENAME}.md"

# Ensure directory exists
mkdir -p "$(dirname "$REPORT_PATH")"

# Conduct research
cc-deep-research research -o "$REPORT_PATH" "$TOPIC"

echo "Research saved to Obsidian vault: $REPORT_PATH"
```

### Integration with Data Analysis Tools

Extract data from JSON output for analysis:

```python
#!/usr/bin/env python3
# analyze_research.py

import json
import sys
from collections import Counter

# Read JSON input
data = json.load(sys.stdin)

# Analyze sources
source_domains = []
for source in data.get('sources', []):
    domain = source['url'].split('/')[2]
    source_domains.append(domain)

# Print summary
print("=== Research Analysis ===")
print(f"Query: {data['query']}")
print(f"Depth: {data['depth']}")
print(f"Total Sources: {len(data['sources'])}")
print("")
print("Top Domains:")
for domain, count in Counter(source_domains).most_common(5):
    print(f"  {domain}: {count}")
```

Usage:
```bash
cc-deep-research research --format json "Topic" | python analyze_research.py
```

### Integration with Version Control

Track research over time:

```bash
#!/bin/bash
# track_research.sh

RESEARCH_DIR="research_reports"
git -C "$RESEARCH_DIR" init

# Conduct research
DATE=$(date +%Y%m%d)
cc-deep-research research -o "$RESEARCH_DIR/${DATE}_topic.md" "Your Topic"

# Commit to git
cd "$RESEARCH_DIR"
git add .
git commit -m "Research report for ${DATE}"
```

### Integration with Web Services

Upload research to a web service:

```bash
#!/bin/bash
# upload_research.sh

REPORT_FILE="$1"
API_KEY="your_api_key"

# Upload report (example using curl)
curl -X POST "https://api.example.com/reports" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"title\": \"$(basename "$REPORT_FILE" .md)\",
    \"content\": \"$(cat "$REPORT_FILE" | jq -Rs .)\"
  }"
```

### Integration with CI/CD

Automated research in GitHub Actions:

```yaml
# .github/workflows/research.yml
name: Automated Research

on:
  schedule:
    - cron: '0 9 * * *'  # Daily at 9 AM
  workflow_dispatch:

jobs:
  research:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install cc-deep-research
        run: pip install cc-deep-research

      - name: Run research
        env:
          TAVILY_API_KEYS: ${{ secrets.TAVILY_API_KEY }}
        run: |
          DATE=$(date +%Y%m%d)
          cc-deep-research research --quiet -o "reports/${DATE}_daily.md" \
            "Latest developments in artificial intelligence"

      - name: Commit report
        run: |
          git config --local user.email "action@github.com"
          git config --local user.name "GitHub Action"
          git add reports/
          git commit -m "Daily research report"
          git push
```

### Integration with Chat Applications

Send research results to Slack/Teams:

```bash
#!/bin/bash
# send_to_slack.sh

REPORT_FILE="$1"
SLACK_WEBHOOK="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

# Read report content
CONTENT=$(cat "$REPORT_FILE")

# Send to Slack (truncate if too long)
curl -X POST "$SLACK_WEBHOOK" \
  -H 'Content-Type: application/json' \
  -d "{
    \"text\": \"Research Report: $(basename "$REPORT_FILE" .md)\",
    \"blocks\": [
      {
        \"type\": \"section\",
        \"text\": {
          \"type\": \"mrkdwn\",
          \"text\": \"${CONTENT:0:3000}...\"
        }
      }
    ]
  }"
```

---

## Additional Tips

### Performance Optimization

```bash
# Fast research for quick answers
cc-deep-research research -d quick --no-team --no-cross-ref "Quick question"

# Balanced research
cc-deep-research research -d standard --team-size 4 "Standard question"

# Deep research
cc-deep-research research -d deep --team-size 6 --sources 30 "Deep question"
```

### Debugging

```bash
# Verbose output for troubleshooting
cc-deep-research research --verbose --monitor "Problematic query"

# Sequential mode to isolate issues
cc-deep-research research --no-team --verbose "Test query"

# Test with simple query
cc-deep-research research -d quick "Test query"
```

### Quality Assurance

```bash
# Research same topic with different depths
cc-deep-research research -d quick -o quick.md "Topic"
cc-deep-research research -d standard -o standard.md "Topic"
cc-deep-research research -d deep -o deep.md "Topic"

# Compare results
diff quick.md standard.md
```

---

For more information, see the [USAGE.md](USAGE.md) documentation.
