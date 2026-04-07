# Task 24: Add An Artifact Explorer And Provenance Summary

## Status: Done

## Goal

Give operators one place to inspect what artifacts a session produced and where those artifacts came from.

## Depends On

- Tasks 11 through 23 complete

## Primary Areas

- `dashboard/src/components/session-report.tsx`
- session overview component from earlier tasks
- `dashboard/src/lib/api.ts`
- `dashboard/src/types/telemetry.ts`
- `src/cc_deep_research/web_server.py`
- `src/cc_deep_research/session_store.py`

## Problem To Solve

Operators can usually tell whether a report exists, but not necessarily what other artifacts exist or how to inspect them coherently.

## Required Changes

1. Add an artifact explorer section in the session workspace.
2. Surface artifact availability such as:
   - report formats
   - session payload
   - trace bundle
   - derived outputs where appropriate
3. Add lightweight provenance framing so the operator understands:
   - which artifacts are generated directly
   - which are derived or transformed
   - which are missing because the run failed or ended early
4. Make navigation between artifact views more coherent.

## Implementation Guidance

- Start from artifacts already exposed by the backend.
- If more artifact metadata is needed, add the minimum backend contract necessary.
- Keep provenance explanations compact and technical.

## Out Of Scope

- full file-browser UI
- arbitrary filesystem access
- editing artifacts in place

## Acceptance Criteria

- Operators can see what artifacts exist for a session and open the important ones quickly.
- Missing-artifact states are explicit and understandable.
- The artifact explorer integrates with the session workspace rather than feeling bolted on.

## Verification

- Test sessions with full artifacts, partial artifacts, and no report.
- Confirm the trace-bundle path from Task 20 integrates correctly.
