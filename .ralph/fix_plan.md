# CC Deep Research CLI - Task List

## Tasks

### Foundation
- [ ] **Project Structure**
  - Acceptance: pyproject.toml and requirements.txt exist, pip install -e . succeeds
  - Gates: tests: N/A (no tests yet), lint: pass, typecheck: pass, committed: yes

- [ ] **Core Data Structures**
  - Acceptance: pydantic models defined for SearchResult, ResearchSession, APIKey, etc.
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

- [ ] **Configuration Management**
  - Acceptance: Can load config from file and environment variables
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

### Search Infrastructure
- [ ] **SearchProvider Interface**
  - Acceptance: Abstract base class defined with async search() method
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

- [ ] **TavilySearchProvider**
  - Acceptance: Can execute Tavily search, returns unified SearchResult format
  - Gates: tests: pass (mocked), lint: pass, typecheck: pass, committed: yes

- [ ] **KeyRotationManager**
  - Acceptance: Manages multiple API keys, rotates on rate limit, tracks usage
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

- [ ] **ClaudeSearchProvider**
  - Acceptance: Wraps Claude Code's WebSearch, returns unified format
  - Gates: tests: pass (mocked), lint: pass, typecheck: pass, committed: yes

- [ ] **Result Aggregation**
  - Acceptance: Merges results from multiple providers, deduplicates by URL
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

### Orchestration
- [ ] **ResearchOrchestrator**
  - Acceptance: Executes research using hybrid parallel mode, returns ResearchSession
  - Gates: tests: pass (mocked), lint: pass, typecheck: pass, committed: yes

- [ ] **QueryExpander**
  - Acceptance: Generates relevant query variations (5-8 for deep mode)
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

- [ ] **IterativeSearchEngine**
  - Acceptance: Performs gap analysis and follow-up searches
  - Gates: tests: pass (mocked), lint: pass, typecheck: pass, committed: yes

- [ ] **CrossReferenceAnalyzer**
  - Acceptance: Identifies consensus and disagreement across sources
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

- [ ] **SourceQualityScorer**
  - Acceptance: Scores sources by credibility, relevance, freshness, diversity
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

### Reporting
- [ ] **MarkdownReportGenerator**
  - Acceptance: Generates markdown reports with all sections (summary, findings, analysis, cross-ref, sources, metadata)
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

- [ ] **Citation Formatting**
  - Acceptance: Citations numbered correctly, inline citations work
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

- [ ] **Executive Summary**
  - Acceptance: Generates 2-3 paragraph summary of key findings
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

### CLI Interface
- [ ] **Research Command**
  - Acceptance: `cc-deep-research research "query"` works, accepts depth, output, provider options
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

- [ ] **Progress Indicators**
  - Acceptance: Progress bars show for deep mode, spinners for quick/standard
  - Gates: tests: pass (unit), lint: pass, typecheck: pass, committed: yes

- [ ] **Config Command**
  - Acceptance: `cc-deep-research config show/set/unset/edit` work
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

- [ ] **Session Command**
  - Acceptance: `cc-deep-research session list/show/export` work
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

- [ ] **Error Messages**
  - Acceptance: Helpful error messages for common failures (no API keys, rate limits, no results)
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

### Integration & Polish
- [ ] **End-to-End Research**
  - Acceptance: Can run full research from CLI command to markdown report
  - Gates: tests: pass (integration), lint: pass, typecheck: pass, committed: yes

- [ ] **Coverage Threshold**
  - Acceptance: Coverage report shows 85%+ for all code
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

- [ ] **Documentation**
  - Acceptance: README has usage examples, AGENT.md has build instructions
  - Gates: tests: N/A, lint: pass, typecheck: pass, committed: yes

## Completed
- [x] Project initialization with Ralph
- [x] Specification documents created

## Notes

- **Backpressure gates** must pass before marking a task complete
- **Tests**: Use `pytest` with `pytest-asyncio` for async tests
- **Lint**: Use `ruff check src/`
- **Typecheck**: Use `mypy src/`
- **Coverage**: Use `pytest --cov=src/cc_deep_research --cov-report=term-missing`

Update this file as tasks complete.
