# Preflight Validation Guide

Use one command from the repository root before merging maintenance-sensitive changes:

```bash
./scripts/preflight
```

This is the canonical "necessary 80%" local preflight. It stays cheap enough for routine use and avoids live API calls.

## What It Runs

`./scripts/preflight` executes these phases in order:

1. Python fixture-backed preflight tests
2. Dashboard production build
3. Dashboard mocked smoke tests

The script currently runs these exact commands:

```bash
uv run pytest tests/test_llm_analysis_client.py tests/test_models.py tests/test_reporter.py tests/test_tavily_provider.py tests/test_providers.py tests/test_orchestrator.py tests/test_orchestration.py tests/test_cli_research.py tests/test_research_run_service.py -v --tb=short
cd dashboard && npm run build
cd dashboard && npm run test:e2e:smoke
```

## Why This Is the Canonical Path

- It covers the maintenance-critical Python contracts, orchestrator flow, and CLI smoke checks.
- It verifies the dashboard can still compile for production.
- It exercises the essential mocked dashboard smoke path without depending on live backend state.
- It fails fast if any required step regresses.
- It does not spend provider credits or make live API calls.

## Expected Runtime

- Python preflight: about 30 to 60 seconds
- Dashboard build: about 30 to 60 seconds
- Dashboard smoke tests: about 30 to 60 seconds
- Full canonical preflight: about 1 to 3 minutes on a typical dev machine

## Prerequisites

Install dependencies before relying on the preflight:

```bash
uv sync
cd dashboard && npm install
cd dashboard && npx playwright install --with-deps chromium
```

The Playwright browser install is typically a one-time setup per machine.

## Focused Variants

Use the script flags when you need a cheaper targeted pass during local iteration:

### Python Only

```bash
./scripts/preflight --python-only
```

Runs only the fixture-backed Python test subset.

### Dashboard Only

```bash
./scripts/preflight --dashboard-only
```

Runs the dashboard build and mocked smoke tests only.

### Quick Core Check

```bash
./scripts/preflight --quick
```

Runs the orchestrator-focused smoke subset:

```bash
uv run pytest tests/test_orchestrator.py tests/test_orchestration.py -v
```

## When To Run It

Run `./scripts/preflight` before merging changes that touch:

- orchestrator, provider, schema, or CLI behavior
- dashboard routes, components, or shared frontend types
- release, operator, or maintenance workflows that rely on these paths

If you changed only one area and need faster iteration, use one of the focused variants while developing, then rerun the full canonical preflight before you merge.
