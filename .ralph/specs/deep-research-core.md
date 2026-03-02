# Deep Research Core - Requirements & Acceptance Criteria

## Overview
Core infrastructure for the CC Deep Research CLI tool, providing search abstraction, API integration, and result management.

## Requirements

### 1. SearchProvider Interface

**Requirement**: Abstract base class that defines the contract for all search providers.

**Acceptance Criteria**:
- [ ] Abstract base class `SearchProvider` exists
- [ ] Has abstract method `async search(query: str, options: SearchOptions) -> SearchResult`
- [ ] Has abstract method `get_provider_name() -> str`
- [ ] Concrete implementations can be created and used polymorphically
- [ ] Type hints are present for all methods

**Backpressure Gates**:
- Tests: pass (test that interface is abstract, can create mock subclass)
- Lint: pass
- Typecheck: pass

### 2. SearchResult Data Structures

**Requirement**: Unified data structures for search results using pydantic.

**Acceptance Criteria**:
- [ ] `SearchResult` dataclass/pydantic model with fields:
  - `query: str`
  - `results: List[SearchResultItem]`
  - `provider: str`
  - `metadata: Dict[str, Any]`
  - `timestamp: datetime`
  - `execution_time_ms: int`
- [ ] `SearchResultItem` dataclass/pydantic model with fields:
  - `url: str`
  - `title: str`
  - `snippet: str`
  - `content: Optional[str]`
  - `score: float`
  - `source_metadata: Dict[str, Any]`
- [ ] Validation works (pydantic validates types)
- [ ] Can serialize to JSON/dict

**Backpressure Gates**:
- Tests: pass (validation, serialization)
- Lint: pass
- Typecheck: pass

### 3. TavilySearchProvider

**Requirement**: Async client for Tavily Search API.

**Acceptance Criteria**:
- [ ] Implements `SearchProvider` interface
- [ ] `search()` method calls Tavily API using httpx
- [ ] Returns results in unified `SearchResult` format
- [ ] Handles rate limit errors gracefully (raises specific exception)
- [ ] Handles authentication errors gracefully (raises specific exception)
- [ ] Supports configurable max_results parameter
- [ ] Uses async/await properly

**Backpressure Gates**:
- Tests: pass (use httpx MockTransport to mock Tavily API)
- Lint: pass
- Typecheck: pass
- Committed: yes

### 4. KeyRotationManager

**Requirement**: Manages multiple Tavily API keys with automatic rotation.

**Acceptance Criteria**:
- [ ] `APIKey` dataclass with fields: key, requests_used, requests_limit, last_used, disabled
- [ ] `KeyRotationManager` can be initialized with list of API keys
- [ ] `get_available_key()` returns key that hasn't reached limit
- [ ] Rotates to next key when current reaches limit
- [ ] Marks key as disabled (temporarily) when exhausted
- [ ] Resets counters on request (e.g., daily reset)
- [ ] Logs rotation events
- [ ] Handles edge case: all keys exhausted

**Backpressure Gates**:
- Tests: pass (rotation logic, edge cases)
- Lint: pass
- Typecheck: pass
- Committed: yes

### 5. ClaudeSearchProvider

**Requirement**: Wraps Claude Code's built-in WebSearch tool.

**Acceptance Criteria**:
- [ ] Implements `SearchProvider` interface
- [ ] Integrates with Claude Code's WebSearch (via appropriate mechanism)
- [ ] Returns results in unified `SearchResult` format
- [ ] Provider name returns "claude" or similar
- [ ] Can be used alongside TavilySearchProvider

**Note**: Implementation depends on how Claude Code exposes WebSearch to external tools.

**Backpressure Gates**:
- Tests: pass (mock Claude Search interface)
- Lint: pass
- Typecheck: pass
- Committed: yes

### 6. Result Aggregation & Deduplication

**Requirement**: Merge results from multiple providers, remove duplicates.

**Acceptance Criteria**:
- [ ] Takes list of `SearchResult` from multiple providers
- [ ] Merges all `SearchResultItem` into single list
- [ ] Deduplicates by URL (exact match)
- [ ] Optional: deduplicates by content similarity
- [ ] Preserves provider attribution (each item knows which provider found it)
- [ ] Ranks merged results by score

**Backpressure Gates**:
- Tests: pass (merge, dedup, ranking)
- Lint: pass
- Typecheck: pass
- Committed: yes

### 7. ResearchOrchestrator

**Requirement**: Orchestrates research using configured search strategy.

**Acceptance Criteria**:
- [ ] `ResearchOrchestrator` can be initialized with list of SearchProvider instances
- [ ] `execute_research()` accepts query and search mode
- [ ] Supports modes: HYBRID_PARALLEL, TAVILY_PRIMARY, CLAUDE_PRIMARY
- [ ] HYBRID_PARALLEL runs all providers concurrently and merges results
- [ ] PRIMARY modes use primary provider, fall back to secondary if primary fails
- [ ] Returns `ResearchSession` with all results and metadata
- [ ] Handles provider failures gracefully (continues with others)
- [ ] Uses async properly (concurrent execution)

**Backpressure Gates**:
- Tests: pass (mock providers, test each mode)
- Lint: pass
- Typecheck: pass
- Committed: yes

### 8. QueryExpander

**Requirement**: Generate multiple query variations for comprehensive coverage.

**Acceptance Criteria**:
- [ ] `QueryExpander` expands single query into multiple variations
- [ ] Generates semantic variations (rephrasings)
- [ ] Adds related concepts if applicable
- [ ] Limits to 5-8 variations for deep mode, fewer for quick/standard
- [ ] Preserves original query in results
- [ ] Returns list of query strings

**Backpressure Gates**:
- Tests: pass (expansion logic, variation count)
- Lint: pass
- Typecheck: pass
- Committed: yes

### 9. IterativeSearchEngine

**Requirement**: Analyze gaps in results and perform follow-up searches.

**Acceptance Criteria**:
- [ ] `IterativeSearchEngine` accepts initial query and depth setting
- [ ] Performs initial search with expanded queries
- [ ] Analyzes results for gaps (areas with limited information)
- [ ] Generates follow-up queries for gaps
- [ ] Performs follow-up searches
- [ ] Continues until source count threshold reached or no gaps found
- [ ] Returns `ResearchSession` with all iterations

**Backpressure Gates**:
- Tests: pass (gap detection, iteration logic)
- Lint: pass
- Typecheck: pass
- Committed: yes

### 10. CrossReferenceAnalyzer

**Requirement**: Analyze relationships between sources (consensus, disagreement).

**Acceptance Criteria**:
- [ ] `CrossReferenceAnalyzer` accepts list of `SearchResultItem`
- [ ] Groups related claims across sources
- [ ] Identifies points where sources agree (consensus)
- [ ] Identifies points where sources disagree (contention)
- [ ] Tracks which sources support each claim
- [ ] Returns structured report with consensus and contention sections
- [ ] Optional: Detects citation chains (source A cites source B)

**Backpressure Gates**:
- Tests: pass (consensus detection, contention detection)
- Lint: pass
- Typecheck: pass
- Committed: yes

### 11. SourceQualityScorer

**Requirement**: Evaluate and rank sources by quality.

**Acceptance Criteria**:
- [ ] `SourceQualityScorer` evaluates list of `SearchResultItem`
- [ ] Scores each source on multiple dimensions:
  - Credibility (domain reputation, author credentials)
  - Relevance (content match to query)
  - Freshness (publication date)
  - Diversity (information uniqueness)
- [ ] Combines scores into overall quality score (0.0 - 1.0)
- [ ] Returns sorted list of sources by overall score
- [ ] Configurable weights for each dimension
- [ ] Filters sources below quality threshold (optional)

**Backpressure Gates**:
- Tests: pass (scoring logic, ranking)
- Lint: pass
- Typecheck: pass
- Committed: yes

## Configuration Requirements

### Environment Variables
- `TAVILY_API_KEYS` - Comma-separated list of Tavily API keys
- `TAVILY_RATE_LIMIT` - Requests per day per key (default: 1000)

### Config File Format (YAML)
```yaml
search:
  providers: [tavily, claude]
  mode: hybrid_parallel

tavily:
  api_keys: [key1, key2]
  rate_limit: 1000
  max_results: 100

claude:
  max_results: 50

research:
  default_depth: deep
  min_sources: 20
  enable_cross_ref: true
```

**Acceptance Criteria**:
- [ ] Config can be loaded from YAML file
- [ ] Config can be overridden by environment variables
- [ ] Default config exists when file not present
- [ ] Validation ensures required fields are present
- [ ] Type validation works on config values

**Backpressure Gates**:
- Tests: pass (load, override, validate)
- Lint: pass
- Typecheck: pass
- Committed: yes

## Error Handling Requirements

**Acceptance Criteria**:
- [ ] Provider failures raise specific exceptions with context
- [ ] Rate limit errors are caught and logged
- [ ] Authentication errors provide helpful messages
- [ ] Network errors are handled with retry logic (exponential backoff)
- [ ] Circuit breaker pattern for repeatedly failing providers
- [ ] All errors include context (provider, query, timestamp)

**Backpressure Gates**:
- Tests: pass (error scenarios, retry logic)
- Lint: pass
- Typecheck: pass
- Committed: yes
