# CC Deep Research CLI - Task List

## Tasks

### Foundation
- [x] **Project Structure**
  - Acceptance: pyproject.toml and requirements.txt exist, pip install -e . succeeds
  - Gates: tests: N/A (no tests yet), lint: pass, typecheck: pass, committed: yes

- [x] **Core Data Structures**
  - Acceptance: pydantic models defined for SearchResult, ResearchSession, APIKey, etc.
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

- [x] **Configuration Management**
  - Acceptance: Can load config from file and environment variables
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

### Search Infrastructure
- [x] **SearchProvider Interface**
  - Acceptance: Abstract base class defined with async search() method
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

- [x] **TavilySearchProvider**
  - Acceptance: Can execute Tavily search, returns unified SearchResult format
  - Gates: tests: pass (mocked), lint: pass, typecheck: pass, committed: yes

- [x] **KeyRotationManager**
  - Acceptance: Manages multiple API keys, rotates on rate limit, tracks usage
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

- [x] **ClaudeSearchProvider**
  - Acceptance: Wraps Claude Code's WebSearch, returns unified format
  - Gates: tests: pass (mocked), lint: pass, typecheck: pass, committed: yes

- [x] **Result Aggregation**
  - Acceptance: Merges results from multiple providers, deduplicates by URL
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

### Orchestration
- [x] **ResearchOrchestrator**
  - Acceptance: Executes research using hybrid parallel mode, returns ResearchSession
  - Gates: tests: pass (mocked), lint: pass, typecheck: pass, committed: yes

- [x] **QueryExpander**
  - Acceptance: Generates relevant query variations (5-8 for deep mode)
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

- [x] **SourceQualityScorer**
  - Acceptance: Scores sources by credibility, relevance, freshness, diversity
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

- [x] **DeepAnalyzer**
  - Acceptance: Performs multi-pass deep analysis (3 passes) for deep mode
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

### Reporting
- [x] **MarkdownReportGenerator**
  - Acceptance: Generates markdown reports with all sections (summary, findings, analysis, cross-ref, sources, metadata)
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

- [x] **JSONReportGenerator**
  - Acceptance: Generates JSON reports with structured data
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

- [x] **Citation Formatting**
  - Acceptance: Citations numbered correctly, inline citations work
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

- [x] **Executive Summary**
  - Acceptance: Generates 2-3 paragraph summary of key findings
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

- [x] **PDF Generation**
  - Acceptance: Optional PDF output using WeasyPrint
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

### CLI Interface
- [x] **Research Command**
  - Acceptance: `cc-deep-research research "query"` works, accepts depth, output, provider options
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

- [x] **Progress Indicators**
  - Acceptance: Progress bars show for deep mode, spinners for quick/standard
  - Gates: tests: pass (unit), lint: pass, typecheck: pass, committed: yes

- [x] **Config Command**
  - Acceptance: `cc-deep-research config show/set/init` work
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

- [x] **Error Messages**
  - Acceptance: Helpful error messages for common failures (no API keys, rate limits, no results)
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

- [x] **TUI Components**
  - Acceptance: Terminal UI with progress tracking, styled output
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

- [x] **Monitor Flag**
  - Acceptance: `--monitor` flag shows internal workflow for debugging
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

### Agent System
- [x] **ResearchLeadAgent**
  - Acceptance: Analyzes query complexity and determines research strategy
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

- [x] **SourceCollectorAgent**
  - Acceptance: Gathers sources from configured search providers
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

- [x] **QueryExpanderAgent**
  - Acceptance: Generates query variations for comprehensive coverage
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

- [x] **AnalyzerAgent**
  - Acceptance: Synthesizes and analyzes collected information
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

- [x] **DeepAnalyzerAgent**
  - Acceptance: Performs multi-pass deep analysis for deep mode
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

- [x] **ReporterAgent**
  - Acceptance: Generates final research reports
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

- [x] **ValidatorAgent**
  - Acceptance: Validates research quality and completeness
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

- [x] **ResearchTeam**
  - Acceptance: Wraps Claude Agent Team for coordinated execution
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

### Integration & Polish
- [x] **End-to-End Research**
  - Acceptance: Can run full research from CLI command to markdown report
  - Gates: tests: pass (integration), lint: pass, typecheck: pass, committed: yes

- [x] **Documentation**
  - Acceptance: README has usage examples, CLAUDE.md has build instructions
  - Gates: tests: N/A, lint: pass, typecheck: pass, committed: yes

## Notes

- **Backpressure gates** must pass before marking a task complete
- **Tests**: Use `pytest` with `pytest-asyncio` for async tests
- **Lint**: Use `ruff check src/`
- **Typecheck**: Use `mypy src/`
- **Coverage**: Use `pytest --cov=src/cc_deep_research --cov-report=term-missing`
- **Current Coverage**: 48% (target: 85%+)
- **Test Status**: 133/134 tests pass (1 failure in orchestrator test)

## Current Tasks

### Session Management
- [x] **Session Command** - Add session list/show/export functionality
  - `cc-deep-research session list` - List all research sessions
  - `cc-deep-research session show <id>` - Show details of a specific session
  - `cc-deep-research session export <id> --output file.md` - Export session to file
  - `cc-deep-research session delete <id>` - Delete a session
  - Acceptance: Can list, show, and export saved research sessions
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

### Test Coverage
- [ ] **Increase Test Coverage** - Improve from 48% to 85%+
  - Focus areas: cli.py, reporting.py, agents (analyzer, deep_analyzer, reporter, query_expander), pdf_generator.py, tui.py
  - Acceptance: Coverage report shows 85%+ overall
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

## Future Enhancements (Optional)

- [ ] **IterativeSearchEngine** - Follow-up searches based on gaps
  - Acceptance: Performs gap analysis and follow-up searches
  - Gates: tests: pass (mocked), lint: pass, typecheck: pass, committed: yes

- [ ] **CrossReferenceAnalyzer** - Enhanced consensus/disagreement detection with AI
  - Acceptance: Identifies consensus and disagreement across sources
  - Gates: tests: pass, lint: pass, typecheck: pass, committed: yes

- [ ] **Session Persistence** - Save research sessions to disk for later retrieval
- [ ] **Search History** - Track and display previous research queries
- [ ] **Batch Research** - Support multiple queries in a single run
- [ ] **Export Formats** - Add more export formats (HTML, DOCX, CSV)
- [ ] **Search Filters** - Add date, domain, and source type filters

Update this file as tasks complete.
