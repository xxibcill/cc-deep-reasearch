# P2-T2: Build Content Pillar Management

## Summary
Build first-class content pillar CRUD and ordering UI.

## Details
Content pillars are currently stored as `ContentPillar[]` in `StrategyMemory`, but the UI only exposes them as a comma-separated list. Build a dedicated content pillar editor that:
- Displays pillars as an ordered list with drag-to-reorder
- Allows add, edit, archive (not just delete) behavior
- Shows pillar name, description, and content_types for each
- Provides inline editing within the list without a modal
- Archives pillars (soft-delete) rather than hard-deleting to preserve history

## Exit Criteria
- Content pillars are managed via dedicated add/edit/reorder/archive UI
- Pillars can be reordered via drag-and-drop
- Archived pillars do not appear in active lists but are preserved in the data model
- The structured pillar editor replaces comma-separated text input for `content_pillars`

## Dependencies
- P2-T1 (workspace redesign) provides the section container for this UI
