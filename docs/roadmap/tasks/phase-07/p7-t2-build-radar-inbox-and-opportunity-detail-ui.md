# P7-T2 - Build Radar Inbox And Opportunity Detail UI

## Status

Proposed.

## Summary

Build the main Radar experience: a ranked inbox and an opportunity detail surface that explain what changed, why it matters, and what action to take.

## Scope

- Build the Radar opportunity list.
- Support filtering and sorting.
- Build the opportunity detail surface.
- Add status and lightweight feedback controls.

## Out Of Scope

- Source management UI
- Workflow conversion buttons can be placeholders if Phase 08 APIs do not exist yet

## Read These Files First

- `dashboard/src/app/page.tsx`
- `dashboard/src/components/session-list.tsx`
- `dashboard/src/components/ui/card.tsx`
- `dashboard/src/components/ui/empty-state.tsx`
- `dashboard/src/types/radar.ts`

## Suggested Files To Create Or Change

- `dashboard/src/components/radar/radar-inbox.tsx`
- `dashboard/src/components/radar/opportunity-card.tsx`
- `dashboard/src/components/radar/opportunity-detail.tsx`
- `dashboard/src/app/radar/page.tsx`

## Implementation Guide

1. Start with the card shape. Make sure one opportunity card is understandable in under ten seconds.
2. Show the fields that matter most:
   - title
   - summary
   - priority label
   - why-it-matters snippet
   - freshness
   - evidence count
3. Add sorting and filtering only after the basic list renders correctly.
4. Build the detail panel or page to answer:
   - what changed
   - why this is ranked highly
   - what evidence supports it
   - what action is recommended
5. Reuse the existing UI primitives. Do not introduce a separate design system.
6. Keep the visual style aligned with the current dashboard instead of inventing a radically different surface.

## Guardrails For A Small Agent

- Do not dump raw JSON into the UI.
- Do not show every field on the card; prioritize decision-making fields.
- If the backend data is missing, show an honest empty or error state instead of hiding the issue.

## Deliverables

- Radar inbox UI
- Opportunity detail UI
- Basic filter and status interactions

## Dependencies

- P7-T1 dashboard wiring
- P6-T3 score explanations

## Verification

- Run `cd dashboard && npm run lint`
- Manually inspect the Radar page with mock or real API data

## Acceptance Criteria

- Users can scan a ranked list of opportunities.
- Users can open an opportunity and inspect evidence and rationale.
- The experience feels like a curated decision surface, not a raw feed.
