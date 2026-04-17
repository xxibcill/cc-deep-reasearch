# P2-T1: Redesign Strategy Workspace

## Summary
Redesign the strategy page into a sectioned workspace with clear editing domains.

## Details
The current `StrategyEditor` in `dashboard/src/components/content-gen/strategy-editor.tsx` is a flat single-panel form with all fields rendered uniformly. It forces list editing through comma-separated text inputs and does not surface any health/readiness feedback before save.

Transform it into a sectioned operator workspace with:
- A dashboard overview tab showing strategy health (completeness indicators, missing required fields)
- Individual section tabs/panels for each editing domain (Niche, Content Pillars, Audience, Platforms, Proof/Claims, Past Examples)
- Tabbed or accordion navigation between editing domains
- Inline validation and completeness feedback per section before save
- Preserve import/export as an "Advanced" panel that is collapsed by default

## Exit Criteria
- Strategy page uses tabbed/accordion navigation between editing domains
- Each domain (niche, pillars, audience, platforms, proof/claims, examples) has its own structured editor
- A dashboard health view shows completeness before save
- Import/export is available but not the primary editing path
- No comma-separated string editing for structured list fields

## Dependencies
- P2-T2 (content pillar CRUD) should use shared UI primitives from this task
- Phase 01 types and API responses must be stable
