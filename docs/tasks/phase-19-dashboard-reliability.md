# Phase 19 - Dashboard Reliability

## Functional Feature Outcome

Operators can trust the dashboard during messy real runs because failures, retries, websocket state, backend latency, and debug context are visible and actionable.

## Why This Phase Exists

After the dashboard is fast, the next product risk is trust. Research and content-generation runs depend on external APIs, long-lived websocket streams, persisted telemetry, background jobs, and generated artifacts. When any of those pieces degrade, the dashboard must explain what happened, what still works, and what the operator can do next instead of showing generic errors or stale state.

## Scope

- Add frontend error telemetry and backend request timing for dashboard workflows.
- Standardize loading, empty, retry, partial-failure, and degraded states across major pages.
- Add websocket health diagnostics and reconnect audit history.
- Make API errors actionable for monitor, content-gen, settings, benchmark, and export flows.
- Add an operator-facing debug export that captures dashboard state needed for incident review.

## Tasks

| Task | Summary |
| --- | --- |
| [P19-T1](phase-19/p19-t1-dashboard-observability.md) | Add dashboard error telemetry and backend request timing |
| [P19-T2](phase-19/p19-t2-async-state-patterns.md) | Standardize loading, empty, retry, and partial-failure states |
| [P19-T3](phase-19/p19-t3-websocket-health.md) | Add websocket health diagnostics and reconnect audit history |
| [P19-T4](phase-19/p19-t4-actionable-api-errors.md) | Make API errors actionable across critical dashboard workflows |
| [P19-T5](phase-19/p19-t5-debug-export.md) | Add dashboard incident/debug export for operators |

## Dependencies

- Phase 18 dashboard performance work is complete.
- Existing dashboard notification, error-boundary, API client, and websocket utilities remain available.
- FastAPI route modules can add timing headers, structured logs, or lightweight diagnostics without changing public behavior.
- Playwright smoke coverage from Phase 18 can be extended for reliability states.

## Exit Criteria

- Dashboard API calls expose enough timing and request context to diagnose slow or failed workflows.
- Major dashboard views use consistent retryable and non-retryable error patterns.
- Websocket state clearly distinguishes connecting, live, reconnecting, historical, failed, and manually disconnected states.
- API errors include workflow-specific guidance without leaking secrets.
- Operators can export a debug bundle containing dashboard state, route context, recent API failures, websocket status, and session identifiers.
- Reliability smoke tests cover at least one retry, one partial failure, one websocket reconnect, and one debug export path.
