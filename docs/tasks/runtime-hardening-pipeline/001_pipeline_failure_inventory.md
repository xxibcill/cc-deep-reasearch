# Pipeline Boundary Inventory

**Status: Completed**

This document maps all pipeline stages from CLI request through report generation, identifying boundaries where untyped external data enters the system and classifying failure modes.

---

## Pipeline Overview

```
CLI Request
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. CLI Input Validation (cli/research.py)                                   │
│    - Input: Raw query string, depth enum, options dict                      │
│    - Output: ResearchRunRequest (typed)                                     │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ 2. Orchestrator Execution (orchestration/execution.py)                    │
│    - Input: query, depth, min_sources                                        │
│    - Output: ResearchSession                                                │
└─────────────────────────────────────────────────────────────────────────────┘
    │
    ├─ Phase 1: Team Init ────────────────────────────────────────────────────│
    ├─ Phase 2: Strategy (ResearchLeadAgent) ────────────────────────────────│
    ├─ Phase 3: Query Expansion (QueryExpanderAgent) ────────────────────────│
    ├─ Phase 4: Source Collection ────────────────────────────────────────────│
    │            ├─ Tavily Provider (providers/tavily.py)                     │
    │            └─ Claude Provider (llm/claude_cli.py)                       │
    ├─ Phase 5: Analysis (AnalyzerAgent) ─────────────────────────────────────│
    ├─ Phase 6: Validation (ValidatorAgent) ─────────────────────────────────│
    └─ Phase 7: Report Generation (reporting.py) ────────────────────────────│
```

---

## Boundary 1: CLI Input → ResearchRunRequest

**Location:** `cli/research.py:146-161`

| Attribute | Type | Required | Default |
|-----------|------|----------|---------|
| query | str | Yes | - |
| depth | ResearchDepth | Yes | deep |
| min_sources | int \| None | No | None |
| output | str \| None | No | None |
| output_format | OutputFormat | Yes | markdown |
| no_cross_ref | bool | Yes | False |
| tavily_only | bool | Yes | False |
| claude_only | bool | Yes | False |
| no_team | bool | Yes | False |
| team_size | int \| None | No | None |
| parallel_mode | bool | Yes | False |
| num_researchers | int \| None | No | None |
| enable_realtime | bool | Yes | False |
| pdf | bool | Yes | False |

### Failure Classification

| Failure Mode | Likelihood | Impact | Handling Strategy |
|--------------|------------|--------|-------------------|
| Empty query string | Low | High | **Strict validation** - reject before spend |
| Invalid depth value | Low | High | **Strict validation** - Click enum constraint |
| Malformed output path | Low | Medium | **Strict validation** - path validation |
| Invalid team_size (< 1 or > 8) | Low | Medium | **Strict validation** - range check |

### Handler

```python
# build_research_run_request() in cli/shared.py
# Uses Pydantic models for type coercion and validation
```

---

## Boundary 2: Strategy Analysis → StrategyResult

**Location:** `agents/research_lead.py:44-72`

### Input Shape

| Field | Type | Source |
|-------|------|--------|
| query | str | CLI input |
| depth | ResearchDepth | CLI input (converted from string) |

### Output Shape

```python
StrategyResult(
    query: str,                          # Original query
    complexity: str,                     # "simple" | "moderate" | "complex"
    depth: ResearchDepth,               # Input depth
    profile: QueryProfile,               # Derived profile
    strategy: StrategyPlan,              # Execution plan
    tasks_needed: list[str],             # Required tasks
    llm_plan: LLMPlanModel | None       # Per-agent LLM routing
)
```

### Failure Classification

| Failure Mode | Likelihood | Impact | Handling Strategy |
|--------------|------------|--------|-------------------|
| Empty query after normalization | Low | High | **Strict validation** - fail fast |
| Query complexity assessment fails | Low | Medium | **Tolerant normalization** - default to "moderate" |
| Strategy creation fails | Low | High | **Strict validation** - fallback to default strategy |
| LLM plan generation fails | Medium | Medium | **Fallback** - continue without routing |

### Handler

```python
# ResearchLeadAgent.analyze_query() in agents/research_lead.py
# Pure deterministic logic, no external data
```

---

## Boundary 3: Query Expansion → list[QueryFamily]

**Location:** `agents/query_expander.py:22-48`

### Input Shape

| Field | Type | Source |
|-------|------|--------|
| query | str | CLI input |
| depth | ResearchDepth | CLI input |
| strategy | StrategyPlan | From Boundary 2 |

### Output Shape

```python
list[QueryFamily]
# Each QueryFamily:
#   query: str              # Expanded query string
#   family: str             # Family label ("baseline", "primary-source", etc.)
#   intent_tags: list[str]  # Retrieval intent tags
```

### Failure Classification

| Failure Mode | Likelihood | Impact | Handling Strategy |
|--------------|------------|--------|-------------------|
| Empty query families returned | Low | High | **Strict validation** - ensure at least baseline |
| Duplicate families | Low | Medium | **Tolerant normalization** - deduplicate |
| All families filtered out | Low | High | **Strict validation** - keep baseline |
| Invalid intent tags | Low | Medium | **Tolerant normalization** - default to ["baseline"] |

### Handler

```python
# QueryExpanderAgent.expand_query() in agents/query_expander.py
# normalize_query_families() in orchestration/helpers.py
```

---

## Boundary 4: Query Families → Search Results (Provider Boundary)

**Location:** `providers/tavily.py:47-105`, `llm/claude_cli.py`

### Input Shape

| Field | Type | Source |
|-------|------|--------|
| query_families | list[QueryFamily] | From Boundary 3 |
| depth | ResearchDepth | CLI input |
| min_sources | int \| None | CLI input |

### Output Shape

```python
list[SearchResultItem]
# Each SearchResultItem:
#   url: str
#   title: str
#   snippet: str
#   content: str | None
#   score: float (0.0-1.0)
#   source_metadata: dict[str, Any]
#   query_provenance: list[QueryProvenance]
```

### Failure Classification

| Failure Mode | Likelihood | Impact | Handling Strategy |
|--------------|------------|--------|-------------------|
| API authentication failure (401) | Medium | High | **Fallback** - try alternate provider or fail gracefully |
| Rate limiting (429) | Medium | Medium | **Fallback** - retry with backoff, then alternate provider |
| Network timeout | Medium | Medium | **Fallback** - retry, then alternate provider |
| Empty results returned | Medium | Medium | **Fallback** - continue with empty, log warning |
| Malformed JSON response | Low | High | **Fallback** - treat as empty results |
| Partial provider degradation | Medium | Medium | **Fallback** - combine results from working providers |
| Invalid URL in results | Low | Medium | **Tolerant normalization** - skip invalid entries |
| Missing required fields | Low | Medium | **Tolerant normalization** - apply defaults |

### Handler

```python
# SourceCollectionService in orchestration/source_collection.py
# ParallelSourceCollectionStrategy / SequentialSourceCollectionStrategy
# Fallback chain: parallel → sequential → empty results
```

### Provider Errors

| Error Type | Source | Handling |
|------------|--------|----------|
| AuthenticationError | providers/__init__.py | Log error, continue with fallback |
| RateLimitError | providers/__init__.py | Backoff + retry, then fallback |
| NetworkError | providers/__init__.py | Retry once, then fallback |
| SearchProviderError | providers/__init__.py | Log error, continue with fallback |

---

## Boundary 5: Search Results → Analysis (LLM Boundary)

**Location:** `agents/analyzer.py:60-135`

### Input Shape

| Field | Type | Source |
|-------|------|--------|
| sources | list[SearchResultItem] | From Boundary 4 |
| query | str | CLI input |

### Output Shape

```python
AnalysisResult(
    key_findings: list[AnalysisFinding | str],
    themes: list[str],
    themes_detailed: list[dict[str, Any]],
    consensus_points: list[str],
    contention_points: list[str],
    cross_reference_claims: list[CrossReferenceClaim],
    gaps: list[AnalysisGap | str],
    source_count: int,
    analysis_method: str,
    deep_analysis_complete: bool,
    analysis_passes: int,
    patterns: list[str],
    disagreement_points: list[str],
    implications: list[str],
    comprehensive_synthesis: str
)
```

### Failure Classification

| Failure Mode | Likelihood | Impact | Handling Strategy |
|--------------|------------|--------|-------------------|
| No sources provided | Low | High | **Strict validation** - return empty analysis |
| All sources lack content | Medium | Medium | **Fallback** - use basic_keyword analysis |
| LLM API failure | Medium | High | **Fallback** - use basic_keyword analysis |
| Malformed LLM response | Medium | High | **Fallback** - use partial results or basic analysis |
| Empty key_findings | Medium | Medium | **Tolerant normalization** - return empty list |
| Schema mismatch in claims | Medium | Medium | **Tolerant normalization** - coerce to valid structure |
| Truncated LLM output | Medium | Medium | **Tolerant normalization** - detect and repair common patterns |

### Handler

```python
# AnalyzerAgent.analyze_sources() in agents/analyzer.py
# Falls back to _basic_analysis() when AI unavailable
# Uses _build_claims(), _build_findings() for normalization
```

---

## Boundary 6: Deep Analysis (Multi-pass LLM)

**Location:** `agents/deep_analyzer.py`

### Input Shape

| Field | Type | Source |
|-------|------|--------|
| sources | list[SearchResultItem] | From Boundary 4 |
| query | str | CLI input |
| analysis | AnalysisResult | From Boundary 5 |

### Output Shape

Same as AnalysisResult with additional fields for deep analysis.

### Failure Classification

| Failure Mode | Likelihood | Impact | Handling Strategy |
|--------------|------------|--------|-------------------|
| LLM failure during deep analysis | Medium | Medium | **Fallback** - continue with single-pass results |
| Partial deep analysis results | Medium | Low | **Tolerant normalization** - merge available results |
| Multiple LLM failures | Low | High | **Fallback** - skip deep analysis |

### Handler

```python
# AnalysisWorkflow.deep_analysis() in orchestration/analysis_workflow.py
# DeepAnalyzerAgent.deep_analyze() in agents/deep_analyzer.py
```

---

## Boundary 7: Analysis → ValidationResult

**Location:** `agents/validator.py`

### Input Shape

| Field | Type | Source |
|-------|------|--------|
| query | str | CLI input |
| depth | ResearchDepth | CLI input |
| sources | list[SearchResultItem] | From Boundary 4 |
| analysis | AnalysisResult | From Boundary 5 |

### Output Shape

```python
ValidationResult(
    is_valid: bool,
    issues: list[str],
    warnings: list[str],
    recommendations: list[str],
    failure_modes: list[str],
    evidence_diagnosis: str,
    quality_score: float (0.0-1.0),
    diversity_score: float,
    content_depth_score: float,
    freshness_fitness_score: float,
    primary_source_coverage_score: float,
    claim_support_density_score: float,
    contradiction_pressure_score: float,
    source_type_diversity_score: float,
    follow_up_queries: list[str],
    needs_follow_up: bool,
    target_source_count: int
)
```

### Failure Classification

| Failure Mode | Likelihood | Impact | Handling Strategy |
|--------------|------------|--------|-------------------|
| No sources to validate | Low | Medium | **Strict validation** - is_valid=False |
| LLM validation failure | Medium | Medium | **Fallback** - use heuristic validation |
| Malformed validation response | Low | Medium | **Tolerant normalization** - default scores |
| Empty quality scores | Low | Medium | **Tolerant normalization** - default to 0.0 |

### Handler

```python
# ValidatorAgent.validate_research() in agents/validator.py
# Falls back to heuristic scoring when LLM unavailable
```

---

## Boundary 8: Session + Analysis → Report

**Location:** `reporting.py:54-140`

### Input Shape

| Field | Type | Source |
|-------|------|--------|
| session | ResearchSession | From Orchestrator |
| analysis | AnalysisResult | From Boundary 5/6 |

### Output Shape

| Format | Type |
|--------|------|
| Markdown | str |
| JSON | str |
| HTML | str |

### Failure Classification

| Failure Mode | Likelihood | Impact | Handling Strategy |
|--------------|------------|--------|-------------------|
| Empty analysis results | Medium | Medium | **Tolerant normalization** - generate placeholder report |
| Missing key_findings | Medium | Medium | **Tolerant normalization** - skip section |
| Report quality evaluation fails | Medium | Low | **Fallback** - skip quality check |
| Report refinement fails | Low | Low | **Fallback** - use unrefined report |
| LLM report generation fails | Low | High | **Fallback** - use template-based generation |
| Invalid markdown in findings | Low | Medium | **Tolerant normalization** - escape content |

### Handler

```python
# ReportGenerator.generate_markdown_report() in reporting.py
# Uses ReporterAgent, ReportQualityEvaluatorAgent, PostReportValidator, ReportRefinerAgent
```

---

## Boundary 9: Source Content Fetching (Web Reader)

**Location:** `orchestration/source_collection.py:91-255`

### Input Shape

| Field | Type | Source |
|-------|------|--------|
| sources | list[SearchResultItem] | From provider |
| depth | ResearchDepth | CLI input |

### Output Shape

Sources with populated `content` field (if fetch successful).

### Failure Classification

| Failure Mode | Likelihood | Impact | Handling Strategy |
|--------------|------------|--------|-------------------|
| MCP web_reader unavailable | Medium | Low | **Fallback** - continue without full content |
| URL fetch timeout | Medium | Low | **Fallback** - skip content, keep snippet |
| Invalid URL | Low | Low | **Fallback** - skip, log warning |
| Malformed HTML response | Low | Low | **Fallback** - skip content |

### Handler

```python
# SourceContentHydrator.fetch_content_for_top_sources() in orchestration/source_collection.py
# Catches all exceptions, returns partial results
```

---

## Summary: Failure Handling Strategies

### Strict Schema Validation
Boundaries where failures should cause immediate rejection (before provider spend):

1. **Boundary 1**: CLI input validation - reject invalid queries, paths, options
2. **Boundary 2**: Strategy analysis - fail if no valid strategy can be created

### Tolerant Normalization
Boundaries where failures should be normalized to valid defaults:

1. **Boundary 3**: Query family normalization - deduplicate, ensure baseline
2. **Boundary 4**: Provider response normalization - handle missing fields
3. **Boundary 5**: Analysis normalization - coerce claims, fix truncations
4. **Boundary 9**: Content fetching - skip failed fetches gracefully

### Fallback-Only
Boundaries where failures should trigger alternative execution paths:

1. **Boundary 4**: Provider fallback - Tavily → Claude → empty results
2. **Boundary 5**: AI → heuristic fallback when LLM unavailable
3. **Boundary 6**: Deep analysis → single-pass when LLM fails
4. **Boundary 7**: LLM validation → heuristic when LLM unavailable
5. **Boundary 8**: Report refinement - skip when fails

---

## Partial Provider Degradation Handling

When a search provider partially fails (e.g., returns some results but fewer than expected):

| Scenario | Handling |
|----------|----------|
| Some queries fail, others succeed | Continue with successful queries, log failures |
| Provider returns fewer results than max | Accept available results, no retry |
| Provider is slow but succeeds | Accept results, log performance warning |
| Mixed success across query families | Aggregate successful results, note gaps |

---

## Iterative Search Failure Handling

When iterative follow-up search is enabled:

| Scenario | Handling |
|----------|----------|
| Follow-up collection produces no new sources | Stop iterations, log reason |
| Follow-up validation still fails after max iterations | Stop with degraded execution status |
| No follow-up queries generated but validation needed | Stop with low_quality status |
