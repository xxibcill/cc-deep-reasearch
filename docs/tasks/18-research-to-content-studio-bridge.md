# Task 18: Strengthen The Bridge Between Research Sessions And Content Studio

## Goal

Connect research outputs to downstream content-generation workflows so the product feels like one pipeline rather than two adjacent applications.

## Depends On

- Tasks 01 through 17 complete

## Primary Areas

- `dashboard/src/app/page.tsx`
- `dashboard/src/app/content-gen/page.tsx`
- `dashboard/src/components/session-report.tsx`
- `dashboard/src/components/session-static-details.tsx` or its replacement from earlier tasks
- `dashboard/src/components/content-gen/overview-sidebar.tsx`
- `dashboard/src/lib/content-gen-api.ts`

## Problem To Solve

Research and content generation already coexist, but the handoff is weak:

- a finished research session does not strongly guide the user toward the next content workflow
- content studio feels adjacent rather than downstream from research
- valuable reports and findings may not be easy to reuse

## Required Changes

1. Add clear handoff points from research to content work where appropriate:
   - from session overview
   - from session report
   - from home page for report-ready sessions
2. Improve content-studio entry cues so the user understands when a research output is ready to feed downstream workflows.
3. Keep the integration lightweight if backend support is limited; even a strong navigation and context bridge is useful.

## Implementation Guidance

- Prefer explicit operator affordances over hidden “smart” automation.
- If backend payload transfer is not yet supported, build a clean manual bridge with clear copy and routing.
- Do not weaken the independence of content-studio workflows that start without a research session.

## Out Of Scope

- full automatic conversion of research output into content pipelines
- backend schema changes unless already supported
- redesigning content studio itself

## Acceptance Criteria

- Users can move from a finished research session into relevant content workflows with much less friction.
- The connection between the two product areas is more obvious across the UI.
- Existing content-studio flows still work independently.

## Verification

- Test research-to-content entry points from home, session overview, and report screens.
- Verify behavior when a session has no report or incomplete artifacts.
