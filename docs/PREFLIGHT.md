# Preflight Validation Guide

This guide provides contributors with a repeatable, low-cost workflow to validate the pipeline before running live research queries. Use these commands to catch regressions early and avoid wasting provider credits on failing runs.

## Quick Preflight Sequence

Run this sequence before any significant pipeline change:

```bash
# 1. Schema validation (LLM analysis contracts)
uv run pytest tests/test_llm_analysis_client.py tests/test_models.py tests/test_reporter.py -v

# 2. Provider response parsing
uv run pytest tests/test_tavily_provider.py tests/test_providers.py -v

# 3. Orchestrator smoke (full fixture-backed pipeline)
uv run pytest tests/test_orchestrator.py tests/test_orchestration.py -v

# 4. CLI smoke (command entrypoint)
uv run pytest tests/test_cli_research.py tests/test_research_run_service.py -v
```

All four steps make **no live API calls**. The provider, orchestrator, and CLI smoke paths use deterministic fixture-backed or stubbed dependencies to validate the runtime contract cheaply.

## Test Categories

### 1. Schema Tests (LLM Analysis Contracts)

**Command:**
```bash
uv run pytest tests/test_llm_analysis_client.py tests/test_models.py tests/test_reporter.py -v
```

**Covers:**
- Theme extraction parsing
- Cross-reference analysis schema
- Gap detection schema
- Synthesized findings schema
- Downstream model validation behavior
- Malformed payload regression tests

**Time cost:** ~5-10 seconds

**Run before:** Any change to analysis models, parsing logic, or LLM response handling

---

### 2. Provider Response Replay Tests

**Command:**
```bash
uv run pytest tests/test_tavily_provider.py tests/test_providers.py -v
```

**Covers:**
- Tavily search response parsing
- Empty results handling
- Partial metadata handling
- Degraded but valid results
- Provider-side error payloads (auth, rate limit, network)
- Search result normalization

**Time cost:** ~5-10 seconds

**Run before:** Any change to provider integration, search result handling, or provider error mapping

---

### 3. Orchestrator Smoke Tests

**Command:**
```bash
uv run pytest tests/test_orchestrator.py tests/test_orchestration.py -v
```

**Covers:**
- Full `TeamResearchOrchestrator.execute_research()` flow
- Planning, collection, analysis, validation, and session assembly phases
- Standard depth mode smoke path
- Deep analysis mode smoke path
- Cross-phase schema contract validation
- Session metadata contract (strategy, analysis, validation, providers, execution, deep_analysis, llm_routes)

**Time cost:** ~10-20 seconds

**Run before:** Any change to orchestrator logic, phase coordination, or session assembly

---

### 4. CLI Smoke Tests

**Command:**
```bash
uv run pytest tests/test_cli_research.py tests/test_research_run_service.py -v
```

**Covers:**
- CLI entrypoint parsing and delegation
- Fixture-backed command completion through the shared run service
- Session persistence and report materialization
- Help text validation (depth options, format options, provider options)
- Service layer integration

**Time cost:** ~5-10 seconds

**Run before:** Any change to CLI commands, argument parsing, or result formatting

---

## Optional: Failure Path Tests

For additional regression coverage on known failure modes:

```bash
uv run pytest tests/test_validator.py tests/test_analyzer.py tests/test_llm_router.py -v
```

This covers:
- Malformed LLM JSON handling
- Partial deep-analysis payloads
- Empty findings handling
- Incompatible report inputs
- Provider unavailability and fallback
- Session metadata degradation recording

**Time cost:** ~10-15 seconds

---

## Confidence Levels

### Fixture-Backed Confidence

The preflight tests above provide **high confidence** for:
- Schema contract correctness between phases
- CLI argument parsing and delegation
- Provider response parsing logic
- Orchestrator phase coordination
- Error handling and fallback paths

These tests replay realistic payload shapes stored in `tests/fixtures/` without making any live network calls.

### Live-Provider Confidence Required

The following aspects **still require live-provider validation**:

| Gap | Why | How to Validate |
|-----|-----|-----------------|
| Real API rate limiting behavior | Fixtures cannot reproduce live rate limits | Run a small test query, monitor for 429 errors |
| Cross-reference analysis quality | Fixture payloads are static, real analysis is non-deterministic | Compare fixture output vs live output for same query |
| Report generation edge cases | Real user queries surface unexpected content combinations | Run a few real research queries |
| Session persistence under load | Race conditions only appear with concurrent operations | Run multiple queries in parallel |
| LLM model behavior drift | Models may change response format subtly | Compare schema validation against live responses |
| End-to-end credential flow | Auth errors only reproduce with real credentials | Test with invalid API key |

---

## When to Run Preflight

### Run Before Every Change
- Any modification to orchestrator, agents, or provider integration
- CLI command changes
- Model schema changes

### Run After CI Passes
- Before deploying to production
- Before running expensive benchmark corpus

### Skip Preamble, Run Directly
- When iterating rapidly on a single component (e.g., fixing a parser bug)
- When running specific unit tests during development

---

## One-Liner Preflight

For maximum convenience, combine all preflight checks:

```bash
uv run pytest tests/test_llm_analysis_client.py tests/test_models.py tests/test_reporter.py tests/test_tavily_provider.py tests/test_providers.py tests/test_orchestrator.py tests/test_orchestration.py tests/test_cli_research.py tests/test_research_run_service.py -v --tb=short
```

Expected runtime: **~30-60 seconds** with zero provider costs.
