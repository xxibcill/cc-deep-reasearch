# Task 03: Build A Unified Session Workspace Shell

## Goal

Turn the session area into one coherent workspace shell that can host overview, telemetry, and report views without feeling like three separate products.

## Depends On

- Task 01 complete
- Task 02 complete

## Primary Areas

- `dashboard/src/components/session-page-frame.tsx`
- `dashboard/src/app/session/[id]/page.tsx`
- `dashboard/src/app/session/[id]/monitor/page.tsx`
- `dashboard/src/app/session/[id]/report/page.tsx`
- `dashboard/src/hooks/useSessionRoute.ts`
- `dashboard/src/components/run-status-summary.tsx`

## Problem To Solve

The current routing model is clean in code, but fragmented in use:

- overview, monitor, and report are separate routes with separate context resets
- the user repeatedly re-orients instead of staying in one session workspace
- the shell does not yet make the session feel like a single persistent object

## Required Changes

1. Refactor `SessionPageFrame` so it behaves like a stable session workspace shell with:
   - persistent high-level session header
   - stronger route-switching affordances
   - room for embedded overview/monitor/report content
2. Align the three session routes around one shared mental model:
   - Overview
   - Monitor
   - Report
3. Improve route-level loading and resolution behavior while the session ID is being resolved from a run ID.
4. Make route switching feel lighter and more deliberate, even if separate routes remain under the hood.

## Implementation Guidance

- You do not need to collapse everything into a single Next.js page in this task.
- It is acceptable to keep separate routes as long as the shell makes them feel like facets of one workspace.
- Preserve direct deep-linking to `/session/[id]`, `/session/[id]/monitor`, and `/session/[id]/report`.
- Keep breadcrumbs and status visibility, but reduce duplicated framing text.
- Make the session shell visually closer to an IDE or observability workspace than a stack of generic cards.

## Out Of Scope

- redesigning the internal content of overview, monitor, or report panels
- new telemetry features
- new comparison features

## Acceptance Criteria

- Switching between Overview, Monitor, and Report feels like staying inside one workspace.
- The shell communicates session status, identity, artifact availability, and route context clearly.
- Run-to-session resolution states are clearer and less awkward.
- Deep links still work.

## Verification

- Manually test navigation from:
  - home page to session overview
  - home page to session monitor
  - overview to monitor to report
  - run ID route resolving to session ID
- Check route-level loading and missing-report states.
