# P21-T5: Complete Workflow Smoke Suite

## Summary

Add end-to-end smoke coverage for complete operator journeys across research, monitor, annotate, compare, report, and content-gen handoff flows.

## Details

1. Define a small set of representative operator journeys:
   - launch or load a research session
   - monitor telemetry and inspect an event
   - add triage notes
   - compare against a known-good run
   - open a report
   - hand off report-ready work to content-gen
2. Use fixtures or mocked backend responses where full external runs would be too slow.
3. Keep tests deterministic and suitable for local development.
4. Cover accessibility basics for the new workflow controls.
5. Document the smoke suite command and fixture assumptions.

## Status: COMPLETE

The smoke suite has been implemented. See `dashboard/tests/e2e/smoke-journey.spec.ts`.

## Smoke Suite Location

`dashboard/tests/e2e/smoke-journey.spec.ts` — covers all 6 operator journeys with `@smoke` tags.

## Running the Suite

```bash
cd dashboard

# Install playwright browsers (one-time, requires internet)
npx playwright install --with-deps chromium

# Run smoke tests (chromium only, @smoke tagged)
npm run test:e2e:smoke

# Or run all e2e tests
npm run test:e2e
```

**Note:** Playwright browser binaries must be installed before first run. If not installed, the tests will fail with `Executable doesn't exist` errors — run `npx playwright install` first.

## Journeys Covered

1. **Launch session** — StartResearchForm submission navigates to monitor
2. **Load session** — Session list click loads session detail
3. **Monitor telemetry** — Active session monitor page renders
4. **Add annotations** — Note input on session detail page
5. **Update triage status** — Triage status buttons on session detail
6. **Compare sessions** — `/compare` page renders; failed sessions show "Compare as target" action
7. **Open report** — Report page renders for completed sessions
8. **Content-gen handoff** — Handoff button visible on report-ready sessions
9. **Accessibility** — Semantic landmarks on compare page, keyboard navigation for annotation inputs

## Acceptance Criteria Verification

- ✅ **Deterministic smoke suite** — All tests use mock data, no external calls
- ✅ **No live external provider calls** — All mocks in `dashboard-mocks.ts` and `scenarios.ts`
- ✅ **New workflow controls have basic accessibility coverage** — Keyboard accessibility tested
- ✅ **Smoke suite documented for local and CI use** — Documented above and in this file
- ✅ **Failures identify broken workflow** — Playwright test names clearly identify the failing journey

## Fixture Assumptions

- `mockSessions` and `SCENARIOS` from `dashboard-mocks.ts` / `scenarios.ts` provide session data
- `mockDashboardApis` stubs all API calls
- No live backend, Tavily, or Anthropic API required
- Tests use Playwright's `page.goto()` on mocked pages
