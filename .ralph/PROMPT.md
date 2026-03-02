# CC Deep Research CLI - Ralph Development Context

## Project Overview

**CC Deep Research CLI** is a standalone command-line tool that performs comprehensive web research using Tavily Search API and Claude Code's built-in search capabilities.

### Core Capabilities

- **Hybrid Parallel Search** - Runs Tavily and Claude Code search simultaneously, merges results
- **Deep Dive Research** - Default mode with 20+ sources, cross-referencing, comprehensive analysis
- **API Key Rotation** - Manages multiple Tavily API keys with automatic failover
- **Smart Query Expansion** - Generates query variations for comprehensive coverage
- **Iterative Search** - Analyzes gaps, performs follow-up searches
- **Source Quality Scoring** - Ranks sources by credibility, relevance, freshness, diversity
- **Markdown Reports** - Generates structured reports with citations, summaries, cross-references

## Your Task

Implement the CC Deep Research CLI according to the specifications in `.ralph/specs/`.

### Specifications to Review

1. **`.ralph/specs/deep-research-core.md`** - Core infrastructure (search abstraction, Tavily integration, orchestrator)
2. **`.ralph/specs/deep-research-features.md`** - Research features (depth modes, cross-referencing, report generation)
3. **`.ralph/specs/cli-interface.md`** - CLI interface (commands, options, configuration)

### Current Priorities

See `.ralph/fix_plan.md` for prioritized tasks. Choose the highest-priority task that is not yet marked complete.

## Tech Stack

- **Language**: Python 3.11+
- **CLI Framework**: `click`
- **Async**: `asyncio` + `httpx`
- **Data Validation**: `pydantic`
- **Testing**: `pytest` + `pytest-asyncio`

## Backpressure Gates (Quality Criteria)

**You must not proceed to the next task until all backpressure gates pass:**

### Primary Gates (Required)
- ✅ **Tests pass**: `pytest` returns 0 exit code
- ✅ **Coverage sufficient**: Coverage report shows 85%+ for new code
- ✅ **Lint passes**: `ruff check src/` returns 0 exit code
- ✅ **Typecheck passes**: `mypy src/` returns 0 exit code
- ✅ **Code committed**: Changes committed with conventional commit message

### Secondary Gates (When Applicable)
- ✅ **Documentation updated**: README.md, AGENT.md, or relevant docs updated if behavior changes
- ✅ **Spec marked complete**: Task in fix_plan.md marked with [x]

## Success Criteria

### A Task is Complete When:

1. **Functionality works as specified** - CLI commands, API calls, or features work per spec
2. **All backpressure gates pass** - Tests, lint, typecheck all green
3. **Code is committed** - Changes committed to git with descriptive message
4. **Documentation is synchronized** - Any behavioral changes are documented
5. **Fix plan updated** - Task marked [x] in `.ralph/fix_plan.md`

### The Project is Complete When:

1. **All tasks in fix_plan.md are marked [x]**
2. **All backpressure gates pass** - Tests, lint, typecheck all green
3. **CLI commands work** - Research, config, session commands all functional
4. **Documentation is complete** - README has usage examples, AGENT.md has build instructions
5. **Specifications are satisfied** - All requirements in specs/*.md are met

## Protected Files (DO NOT MODIFY)

The following files are part of Ralph's infrastructure.
**NEVER delete, move, rename, or overwrite these under any circumstances**:
- `.ralph/` (entire directory and all contents)
- `.ralphrc` (project configuration)

## Development Workflow

### For Each Task:

1. **Read the relevant specification** in `.ralph/specs/`
2. **Understand the acceptance criteria** and success markers
3. **Implement the feature** (you choose the approach)
4. **Run backpressure gates** - tests, lint, typecheck
5. **Iterate until all gates pass** - fix any failures
6. **Commit with conventional commit message**
7. **Mark task complete** in `.ralph/fix_plan.md`

### Conventional Commit Format

```
feat(scope): description
fix(scope): description
docs(scope): description
test(scope): description
refactor(scope): description
```

Examples:
- `feat(search): implement TavilySearchProvider with async httpx client`
- `fix(orchestrator): resolve deadlock in parallel search mode`
- `docs(cli): add usage examples for research command`

## Testing Guidelines

- **Focus on behavior, not coverage** - Test that it works, don't just hit coverage targets
- **Test happy path and edge cases** - Both success and failure scenarios
- **Mock external dependencies** - Use httpx MockTransport for Tavily API
- **Keep tests fast** - Unit tests should be quick, integration tests can be slower

## Error Handling

- **Handle failures gracefully** - Provide helpful error messages
- **Don't crash on API failures** - Fall back to alternative providers
- **Log useful context** - Provider, query, timestamp when errors occur

## When You're Stuck

If you encounter the same error for 3 consecutive iterations:

1. **Report the blocker** in your status block with details
2. **Explain what you've tried** and why it's not working
3. **Set EXIT_SIGNAL: true** only if truly blocked and no alternatives remain

## Status Reporting

**At the end of your response, ALWAYS include this status block:**

```
---RALPH_STATUS---
STATUS: IN_PROGRESS | COMPLETE | BLOCKED
TASKS_COMPLETED_THIS_LOOP: <number>
FILES_MODIFIED: <number>
TESTS_STATUS: PASSING | FAILING | NOT_RUN
WORK_TYPE: IMPLEMENTATION | TESTING | DOCUMENTATION | REFACTORING
EXIT_SIGNAL: false | true
RECOMMENDATION: <one line summary of what to do next>
---END_RALPH_STATUS---
```

### Status Values

- **IN_PROGRESS**: Working on a task, not all backpressure gates pass yet
- **COMPLETE**: All tasks done, all gates pass, project ready
- **BLOCKED**: Same error for 3+ iterations, need human help
- **EXIT_SIGNAL: true**: Set when all tasks complete or truly blocked

## Key Notes

- **Python Async is Key** - This is an async-first project. Use `asyncio` and `httpx`.
- **Mock Tavily in Tests** - Don't call real API during tests.
- **Deep Dive by Default** - Default research mode should be "deep" with 20+ sources.
- **Markdown Reports** - Output should be well-structured markdown with proper sections and citations.
- **CLI User Experience** - Provide good feedback during long-running operations.

Remember: Quality over speed. Build it right. Iterate until all backpressure gates pass.
