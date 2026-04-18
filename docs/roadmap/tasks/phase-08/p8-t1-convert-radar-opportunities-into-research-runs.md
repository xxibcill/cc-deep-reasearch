# P8-T1 - Convert Radar Opportunities Into Research Runs

## Status

Proposed.

## Summary

Add the end-to-end bridge that turns a Radar opportunity into a prefilled research run with a traceable link back to the originating opportunity.

## Scope

- Add backend conversion logic for research runs.
- Add a dashboard action to launch research from an opportunity.
- Persist the workflow link back to the opportunity.

## Out Of Scope

- Content-generation conversions
- Feedback ranking updates beyond recording the conversion event

## Read These Files First

- `src/cc_deep_research/research_runs/service.py`
- `src/cc_deep_research/research_runs/models.py`
- `dashboard/src/components/start-research-form.tsx`
- `dashboard/src/lib/api.ts`

## Suggested Files To Create Or Change

- `src/cc_deep_research/radar/service.py`
- `src/cc_deep_research/radar/router.py`
- `dashboard/src/components/radar/opportunity-detail.tsx`
- `dashboard/src/lib/api.ts`
- `tests/test_radar_research_conversion.py`

## Implementation Guide

1. Add a backend service method that converts an opportunity into a `ResearchRunRequest` or equivalent typed input.
2. Preserve the important carry-forward context:
   - opportunity title
   - summary
   - why-it-matters explanation
   - source links or notes
3. Add a route like `POST /api/radar/opportunities/{id}/convert` if one does not already exist for conversion.
4. After the research run starts, store an `OpportunityWorkflowLink`.
5. Add a UI action in the detail view that launches the research run and handles loading or error states cleanly.

## Guardrails For A Small Agent

- Do not make users retype the opportunity into a blank form.
- Do not lose the link between the opportunity and the research session.
- Reuse existing research run APIs instead of building a separate execution path.

## Deliverables

- Backend conversion path for research runs
- UI action for launching research from Radar
- Workflow linkage persistence
- Conversion tests

## Dependencies

- Phase 05 service and API contracts
- Phase 07 detail view UI

## Verification

- Run `uv run pytest tests/test_radar_research_conversion.py -v`
- Manually launch a research run from a Radar opportunity and confirm linkage data is stored

## Acceptance Criteria

- Users can launch a research run directly from Radar.
- The new research run is traceable back to the opportunity.
- The launched run starts with prefilled context instead of a blank prompt.
