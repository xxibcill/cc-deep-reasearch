# Task 05: Strengthen The Monitor And Report Panels Inside The Session Workspace

## Goal

Upgrade the monitor and report routes so they feel like coordinated panels of the same workspace, not isolated screens with their own visual language and state handling.

## Depends On

- Tasks 01 through 04 complete

## Primary Areas

- `dashboard/src/components/session-telemetry-workspace.tsx`
- `dashboard/src/components/session-details.tsx`
- `dashboard/src/components/session-report.tsx`
- `dashboard/src/app/session/[id]/monitor/page.tsx`
- `dashboard/src/app/session/[id]/report/page.tsx`

## Problem To Solve

The monitor is powerful but heavy, and the report page still feels like a separate artifact viewer. Both need to plug into the workspace model established in earlier tasks.

## Required Changes

1. Make monitor loading, empty, and partial-failure states consistent with the new session shell.
2. Improve the first screen of the monitor so it presents a useful operational summary before dropping the user into dense telemetry.
3. Improve the report page header and content framing so report access feels integrated with the same session context.
4. Remove remaining duplicated framing text between shell, monitor, and report panels.
5. Preserve existing graph, tool, LLM, derived-output, and prompt-inspection capabilities.

## Implementation Guidance

- Avoid rewriting the telemetry explorer internals unless necessary.
- Prefer improving composition, summaries, and state handling around the existing `SessionDetails` component.
- For the report, keep markdown, JSON, and HTML format switching, but make the presentation calmer and more integrated.
- If you introduce summary cards above telemetry, make them operational, not decorative.
- Keep error messages explicit and useful.

## Out Of Scope

- new telemetry-derived backend data
- saved telemetry filters
- new report export formats

## Acceptance Criteria

- Monitor and report pages feel like panels of the same session workspace.
- Loading and failure states are consistent with the rest of the app.
- Operators can orient themselves quickly before diving into detailed telemetry or report content.
- Existing detailed functionality still works.

## Verification

- Check monitor with:
  - no events yet
  - partial telemetry load failure
  - fully loaded historical session
- Check report with:
  - queued/running run
  - failed run
  - cancelled run
  - completed run with report
  - completed run without report
