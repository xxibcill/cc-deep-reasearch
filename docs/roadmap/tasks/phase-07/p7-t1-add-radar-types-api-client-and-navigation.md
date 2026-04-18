# P7-T1 - Add Radar Types, API Client, And Navigation

## Status

Proposed.

## Summary

Prepare the dashboard to consume Radar by adding TypeScript contracts, API helpers, hooks, and navigation entries.

## Scope

- Add Radar TypeScript types.
- Add API client methods for Radar routes.
- Add a top-level dashboard route and navigation entry.
- Create minimal page shells so later UI work has stable homes.

## Out Of Scope

- No detailed inbox UI yet
- No source management UI yet

## Read These Files First

- `dashboard/src/lib/api.ts`
- `dashboard/src/app/layout.tsx`
- `dashboard/src/app/page.tsx`
- `dashboard/src/components/app-shell.tsx`
- `dashboard/src/components/ui/nav-bar.tsx`

## Suggested Files To Create Or Change

- `dashboard/src/types/radar.ts`
- `dashboard/src/lib/api.ts`
- `dashboard/src/hooks/useRadar.ts`
- `dashboard/src/app/radar/page.tsx`
- `dashboard/src/app/radar/sources/page.tsx`
- `dashboard/src/components/app-shell.tsx` or the relevant nav component

## Implementation Guide

1. Define the TypeScript types to mirror the backend response contract exactly.
2. Add API helper functions to the existing `api.ts` unless there is already a clear reason to create a small Radar-specific API module.
3. Add a `useRadar` hook only if it clearly simplifies repeated fetch and mutation logic.
4. Create page shells that can render loading and empty placeholders even before the full UI exists.
5. Add a top-level `Radar` nav entry consistent with the rest of the dashboard.

## Guardrails For A Small Agent

- Do not hand-write approximate types that drift from backend contracts.
- Do not create a separate global state system if the existing fetch pattern is sufficient.
- Keep navigation changes minimal and consistent with the current dashboard shell.

## Deliverables

- Radar TypeScript types
- Radar API client methods
- Dashboard routes and navigation entries
- Minimal page shells

## Dependencies

- P5-T3 backend route contracts

## Verification

- Run `cd dashboard && npm run lint`
- Load the new Radar route and confirm it renders a page shell without runtime errors

## Acceptance Criteria

- The dashboard can call Radar APIs with typed request and response handling.
- A visible `Radar` route exists in navigation.
- Later UI tasks have stable route targets to build on.
