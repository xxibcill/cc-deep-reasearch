# P2-T4: Add Readiness and Import/Export UX

## Summary
Add readiness feedback, advanced import/export, and safer save flows.

## Details

### Readiness Feedback
- Before save, compute and display a "strategy completeness" score
- Show per-section status: complete / incomplete / warning
- Highlight fields that block pipeline execution (e.g., empty niche, no content pillars, no audience segments)
- Visual indicators: checkmarks for complete sections, warnings for partial, errors for missing required

### Import/Export UX
- Move import/export to an "Advanced" collapsible panel (collapsed by default)
- In the advanced panel: provide paste-to-import JSON editor with live validation feedback
- Export button downloads the full strategy JSON
- Copy-to-clipboard button
- Confirm dialog before importing new strategy (warns about overwrite)

### Safer Save Flows
- On save, compare current state vs. saved state; warn if no actual changes detected
- Provide "Discard changes" option if user edited but hasn't saved
- Show spinner during save with timeout handling
- After successful save, show brief success confirmation (auto-dismiss)

## Exit Criteria
- Strategy health/completeness is visible before the user attempts save
- Import/export is accessible but not the primary editing path (collapsed by default)
- Save flow includes change detection and confirmation when appropriate
- No save action occurs without user intent (no accidental saves)
