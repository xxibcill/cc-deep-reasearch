# Task 07: Add Regression Coverage And Refresh Docs

## Goal

Lock in the dashboard-detail upgrade with focused tests and documentation updates after the implementation tasks land.

## Why This Task Is Last

Earlier tasks will change the rendering surface and websocket behavior. Writing the final regression coverage and docs after those changes land keeps the assertions aligned with the actual shipped UI and protocol.

## Files To Inspect

- `dashboard/tests/e2e/content-gen-observability.spec.ts`
- `dashboard/tests/e2e/content-gen.spec.ts`
- any additional frontend test files that fit the new coverage
- `docs/content-generation.md`
- `docs/REALTIME_MONITORING.md`
- `docs/DASHBOARD_GUIDE.md`

## Expected Deliverables

1. Expand Playwright coverage for:
   - richer ideation-stage details
   - richer downstream-stage details
   - scripting trace visibility inside pipeline detail
   - live context updates during active runs
2. Update product docs to explain:
   - what the pipeline detail page now shows
   - how live operator visibility behaves during a run
   - any new trace metadata that operators should expect
3. If the websocket message contract changed, document that clearly in the relevant dashboard or monitoring docs.

## Testing Guidance

- Prefer a few durable end-to-end assertions over many fragile DOM-structure checks.
- Mock API and websocket payloads with realistic `PipelineContext` objects.
- Keep the test fixtures readable. The content-gen observability fixture is already a good starting point.

## Acceptance Criteria

- New dashboard detail behavior is covered by automated tests.
- The docs reflect the actual operator experience after the implementation changes.
- No stale documentation remains that implies the page is only a compact summary view.

## Out Of Scope

- new product planning
- unrelated dashboard cleanup
