# Inqulume Studio Dashboard

The dashboard is the supported interface for research, telemetry, analytics,
benchmarks, opportunity radar, knowledge, settings, and content generation.
It is a Next.js 16 application backed by the project FastAPI server.

## Start the Full Stack

From the repository root:

```bash
./scripts/dashboard-dev
```

Or from this directory:

```bash
npm run dev
```

Both commands start the backend and frontend together. The launchers discover
available ports beginning at 8000 and 3000 and print the selected URLs.

## Production-Style Startup

From the repository root:

```bash
./scripts/dashboard-start
```

From this directory:

```bash
npm run start:stack
```

This builds the frontend before starting FastAPI and `next start`.

## Frontend Only

```bash
npm run dev:frontend
```

Override backend locations with `.env.local` or environment variables:

```bash
NEXT_PUBLIC_CC_BACKEND_ORIGIN=http://localhost:8000
NEXT_PUBLIC_CC_API_BASE_URL=http://localhost:8000/api
NEXT_PUBLIC_CC_WS_BASE_URL=ws://localhost:8000/ws
```

## Backend Only

Run from the repository root:

```bash
uv run uvicorn cc_deep_research.web_server:create_app \
  --factory \
  --ws websockets-sansio \
  --host 127.0.0.1 \
  --port 8000
```

## Validation

```bash
npm run audit
npm run lint
npm test
npm run build
npm run test:e2e:smoke
npm run test:a11y
```

Install the browser used by local Playwright checks once:

```bash
npx playwright install chromium
```

The repository-level `./scripts/preflight` command runs all of these checks
plus the complete Python suite.

## Structure

```text
src/app/         App Router pages
src/components/  Operator workflows and shared UI
src/hooks/       Shared dashboard state
src/lib/         API, WebSocket, runtime config, and transformers
src/types/       Frontend contracts for backend payloads
tests/e2e/       Mocked smoke and accessibility journeys
```

The project uses React 19, TypeScript, Tailwind CSS, Radix primitives, Zustand,
D3, Vitest, and Playwright.
