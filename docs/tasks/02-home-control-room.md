# Task 02: Rework The Home Page Into A True Control Room

## Goal

Shift the home page from a generic landing page into an operator-first control room focused on active work, attention-needed items, and recent outcomes.

## Depends On

- Task 01 complete

## Primary Areas

- `dashboard/src/app/page.tsx`
- `dashboard/src/components/session-list.tsx`
- `dashboard/src/components/start-research-form.tsx`
- `dashboard/src/components/app-shell.tsx`
- `dashboard/src/hooks/useDashboard.ts` if small state additions are needed

## Problem To Solve

The current home page has solid building blocks, but it still behaves like a hybrid landing page:

- launch flow and archive browsing compete for attention
- the most urgent operational signals are not clearly surfaced first
- session browsing is dense, but not obviously grouped around operator decisions

## Required Changes

1. Reframe the top of the page around operator priorities:
   - active runs
   - sessions needing attention
   - recent completed runs
   - archive and bulk actions
2. Keep the launch form present, but make it feel secondary to the operational overview unless there are zero sessions.
3. Improve home-page summaries so they answer immediate questions:
   - what is running now
   - what failed or stalled
   - what completed with a report
4. Revisit `SessionList` grouping, labels, and empty states so the list feels like a triage surface, not a raw card dump.
5. Reduce redundant copy and avoid repeating the same facts in multiple places.

## Implementation Guidance

- Do not remove the ability to start research from the home page.
- Consider splitting the session area into sections or clearly labeled modes instead of one long undifferentiated list.
- Preserve search, filters, pagination, compare selection, archive, restore, and delete actions.
- Improve information hierarchy before adding any new controls.
- If a metric block remains, make sure it is directly useful for triage rather than decorative.

## Suggested Breakdown

- update the hero and summary frame in `page.tsx`
- reorganize the home-page data summaries
- reshape `SessionList` presentation and section headings
- refine empty, loading, and filtered states

## Out Of Scope

- merging session details/monitor/report into one page
- new API endpoints
- saved filters or templates

## Acceptance Criteria

- A first-time operator can tell within a few seconds what is running, what needs attention, and what is ready.
- The launch form still works, but no longer dominates the page unnecessarily.
- Session browsing feels easier to scan and more clearly grouped by outcome.
- Existing session actions still work.

## Verification

- Run home-page Playwright smoke coverage.
- Manually test search, status filter, active-only filter, load-more, compare-mode, archive, restore, and delete flows.
- Check mobile and desktop layouts after the hierarchy changes.
