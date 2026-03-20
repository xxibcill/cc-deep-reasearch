# Dashboard Web Search Cache Tasks 05: Dashboard UI

## Goal

Expose cache settings and cache-management controls in the dashboard using the existing frontend API and settings surfaces.

## Task Breakdown

### 12. Add dashboard API helpers and types

**Why**
The frontend already centralizes HTTP calls and should treat cache management the same way.

**Work**
- Add TypeScript types for cache entry rows and stats
- Add API helpers for listing and mutating cache state
- Normalize backend errors into the current dashboard error pattern

**Acceptance criteria**
- Frontend code can fetch cache stats and entry lists through shared helpers
- Cache actions do not require direct `fetch` calls inside components

**Likely files**
- `dashboard/src/lib/api.ts`
- new: `dashboard/src/types/search-cache.ts`

### 13. Add cache settings controls to the dashboard settings page

**Why**
Operators need to configure the cache without editing YAML manually.

**Work**
- Extend the existing config editor with fields for:
  - enabled
  - TTL
  - max entries
  - optional path display
- Add helper copy explaining expiry behavior and cost tradeoffs

**Acceptance criteria**
- Cache settings are editable through the dashboard
- Saved values round-trip through the config API correctly
- Validation errors appear inline with the rest of the settings form

**Likely files**
- `dashboard/src/components/config-editor.tsx`
- `dashboard/src/types/config.ts`

### 14. Add a cache-management panel in the dashboard

**Why**
Configuration alone is not enough. Operators also need visibility into what is stored and a way to clean it up.

**Work**
- Add a cache section to the settings page or a dedicated sub-panel
- Show:
  - total entries
  - active entries
  - expired entries
  - approximate size
  - hit and miss counters if available
- Add actions for:
  - purge expired
  - delete one entry
  - clear all

**Acceptance criteria**
- Operators can inspect cache state without using the CLI
- High-risk actions require clear confirmation
- The panel remains usable on smaller screens

**Likely files**
- `dashboard/src/app/settings/page.tsx`
- new: `dashboard/src/components/search-cache-panel.tsx`
- `dashboard/src/components/ui/*`
