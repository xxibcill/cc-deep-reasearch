# Preflight Validation Guide

Use one command from the repository root before merging maintenance-sensitive changes:

```bash
./scripts/preflight
```

This is the canonical local preflight. It runs the complete offline test and
build surface while avoiding live provider calls.

## What It Runs

`./scripts/preflight` executes these phases in order:

1. Locked Python dependency validation
2. Python lint, type checks, and the complete fixture-backed test suite
3. Dashboard lint and unit tests
4. Dashboard production build
5. Dashboard mocked smoke and accessibility tests

The script currently runs these exact commands:

```bash
uv lock --check
uv run --frozen ruff check src/ tests/
uv run --frozen mypy src/
uv run --frozen pytest
cd dashboard && npm run lint
cd dashboard && npm test
cd dashboard && npm run build
cd dashboard && npm run test:e2e:smoke
cd dashboard && npm run test:a11y
```

## Why This Is the Canonical Path

- It covers every offline Python contract and orchestration path.
- It checks dashboard unit behavior before the heavier browser checks.
- It verifies the dashboard can still compile for production.
- It exercises the essential mocked dashboard smoke path without depending on live backend state.
- It fails fast if any required step regresses.
- It does not spend provider credits or make live API calls.

## Expected Runtime

- Python preflight: about 20 to 60 seconds
- Dashboard build: about 30 to 60 seconds
- Dashboard smoke tests: about 30 to 60 seconds
- Full canonical preflight: about 1 to 3 minutes on a typical dev machine

## Prerequisites

Install dependencies before relying on the preflight:

```bash
uv sync
cd dashboard && npm ci
cd dashboard && npx playwright install --with-deps chromium
```

The Playwright browser install is typically a one-time setup per machine.

## Focused Variants

Use the script flags when you need a cheaper targeted pass during local iteration:

### Python Only

```bash
./scripts/preflight --python-only
```

Runs the locked-dependency check, Python lint and type checks, and the complete
fixture-backed Python test suite.

### Dashboard Only

```bash
./scripts/preflight --dashboard-only
```

Runs dashboard lint, unit tests, the production build, mocked smoke tests, and
the accessibility baseline.

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

- orchestrator, provider, schema, service, or API behavior
- dashboard routes, components, or shared frontend types
- release, operator, or maintenance workflows that rely on these paths

If you changed only one area and need faster iteration, use one of the focused variants while developing, then rerun the full canonical preflight before you merge.
