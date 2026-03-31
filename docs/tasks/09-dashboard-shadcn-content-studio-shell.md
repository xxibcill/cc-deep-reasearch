# 09. Dashboard shadcn Content Studio Shell

Status: Done

## Goal

Standardize the content-studio frame, top navigation, dialogs, and quick-action surfaces so they use the same shared UI layer as the main dashboard.

## Scope

- `ContentGenShell`
- `content-gen/page.tsx`
- overview quick actions
- content-studio dialogs
- overview sidebar cards

## Non-Goals

- Refactoring all content-studio forms in the same task
- Changing the routing model

## Work

- Align top navigation and tab usage with the upgraded shared `Tabs`
- Replace raw CTA buttons on the overview page with shared `Button`
- Upgrade the new-pipeline and quick-script modal flows to the shared dialog model
- Normalize overview sidebar panels onto shared card sections
- Reduce local class duplication in the overview route

## Acceptance Criteria

- Content-studio shell reads like part of the same application as the session dashboard
- Top navigation, sidebar summaries, and quick-action buttons all use shared primitives
- Dialog usage is consistent across the dashboard

## Likely Files

- `dashboard/src/components/content-gen/content-gen-shell.tsx`
- `dashboard/src/app/content-gen/page.tsx`
- `dashboard/src/components/content-gen/overview-sidebar.tsx`
- `dashboard/src/components/ui/*`

## Depends On

- `01-dashboard-shadcn-foundation-primitives.md`
