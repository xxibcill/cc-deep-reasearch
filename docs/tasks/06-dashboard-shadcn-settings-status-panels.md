# 06. Dashboard shadcn Settings Status Panels

Status: Planned

## Goal

Standardize the non-form settings panels so alerts, stats cards, confirmation flows, and navigation surfaces match the shared component layer.

## Scope

- `SearchCachePanel`
- settings-page wrapper cards and callouts
- remaining settings feedback blocks

## Non-Goals

- Refactoring the underlying cache actions
- Rewriting settings-page layout from scratch

## Work

- Convert search-cache status blocks to shared cards, badges, and alerts
- Use shared destructive confirmation patterns instead of inline confirm rows where practical
- Normalize stats tiles onto shared card sections or compact cards
- Remove remaining hard-coded success, warning, and error block styles where shared patterns exist

## Acceptance Criteria

- Search-cache UI uses the same feedback patterns as the rest of the dashboard
- Settings page no longer mixes custom one-off panel patterns with shared ones
- Confirmation flows remain clear and accessible

## Likely Files

- `dashboard/src/components/search-cache-panel.tsx`
- `dashboard/src/app/settings/page.tsx`
- `dashboard/src/components/ui/*`

## Depends On

- `01-dashboard-shadcn-foundation-primitives.md`
- `05-dashboard-shadcn-settings-forms.md`
