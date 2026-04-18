# P8-T1: Convert Radar Opportunities Into Research Runs

## Summary

Add the backend API endpoint and UI bridge for launching research runs directly from Radar opportunities with prefilled context from the opportunity.

## Details

### What to implement

1. **API endpoint to launch research run from opportunity** (`POST /api/radar/opportunities/{opportunity_id}/launch-research`)
   - Extract context from the opportunity: title, summary, why_it_matters, recommended_action, linked signals
   - Create a research run request with the opportunity context pre-filled
   - Record a `converted_to_research` feedback entry
   - Create a `WorkflowLink` connecting the opportunity to the new research run
   - Return the created research run ID so the UI can redirect

2. **Frontend API helper** in `dashboard/src/lib/api.ts`
   - `launchRadarOpportunityResearch(opportunityId: string): Promise<{ research_run_id: string }>`
   - Calls the new backend endpoint

3. **UI "Launch Research" button** in `dashboard/src/app/radar/opportunities/[id]/page.tsx`
   - Add a "Launch Research" button in the Actions card (when opportunity is in a convertible state)
   - Show a loading state while the launch is in progress
   - On success, redirect to the new research run session page

### Exit criteria

- Clicking "Launch Research" on an opportunity creates a research run with the opportunity's title and context pre-filled
- A `converted_to_research` feedback entry is recorded
- A `WorkflowLink` with `workflow_type=research_run` is persisted
- The UI redirects to the new research run session
