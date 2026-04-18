# P8-T2: Convert Radar Opportunities Into Content-Gen Flows

## Summary

Add the bridge for launching backlog, brief, and content-generation entry points from Radar opportunities.

## Details

### What to implement

1. **API endpoint to launch brief from opportunity** (`POST /api/radar/opportunities/{opportunity_id}/launch-brief`)
   - Extract opportunity title, summary, why_it_matters as brief topic/context
   - Create a brief entry via BriefService
   - Record `converted_to_content` feedback with `sub_type: brief`
   - Create a `WorkflowLink` with `workflow_type=brief`
   - Return the created brief ID

2. **API endpoint to add to backlog** (`POST /api/radar/opportunities/{opportunity_id}/launch-backlog`)
   - Extract opportunity title and summary as backlog item content
   - Create a backlog item via BacklogService
   - Record `converted_to_content` feedback with `sub_type: backlog_item`
   - Create a `WorkflowLink` with `workflow_type=backlog_item`
   - Return the created backlog item ID

3. **API endpoint to launch content pipeline** (`POST /api/radar/opportunities/{opportunity_id}/launch-content-pipeline`)
   - Extract opportunity context for content pipeline
   - Record `converted_to_content` feedback with `sub_type: content_pipeline`
   - Create a `WorkflowLink` with `workflow_type=content_pipeline`
   - Note: Full pipeline launch may be stubbed for V1 (returns a placeholder ID)

4. **Frontend API helpers** in `dashboard/src/lib/api.ts`
   - `launchRadarOpportunityBrief(opportunityId: string): Promise<{ brief_id: string }>`
   - `launchRadarOpportunityBacklog(opportunityId: string): Promise<{ backlog_item_id: string }>`
   - `launchRadarOpportunityContentPipeline(opportunityId: string): Promise<{ pipeline_id: string }>`

5. **UI action buttons** in `dashboard/src/app/radar/opportunities/[id]/page.tsx`
   - Add "Create Brief", "Add to Backlog", "Start Pipeline" buttons
   - Show appropriate loading states
   - On success, show a toast/notification with the result

### Exit criteria

- All three endpoints are callable and persist WorkflowLinks
- Feedback entries are recorded with appropriate sub_types
- UI buttons trigger appropriate handlers and show feedback
