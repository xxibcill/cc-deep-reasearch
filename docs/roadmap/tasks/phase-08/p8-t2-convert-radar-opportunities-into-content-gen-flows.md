# P8-T2 - Convert Radar Opportunities Into Content-Gen Flows

## Status

Proposed.

## Summary

Add the conversion paths that turn a Radar opportunity into content-generation entry points such as backlog items, briefs, or pipeline starts.

## Scope

- Support at least backlog or brief creation in V1.
- Reuse existing content-generation routes and stores.
- Persist workflow linkage back to the originating opportunity.

## Out Of Scope

- Publishing automation
- Advanced multi-step approval flows

## Read These Files First

- `src/cc_deep_research/content_gen/router.py`
- `src/cc_deep_research/content_gen/storage/backlog_store.py`
- `src/cc_deep_research/content_gen/storage/brief_store.py`
- `dashboard/src/lib/content-gen-api.ts`
- `dashboard/src/components/content-gen/`

## Suggested Files To Create Or Change

- `src/cc_deep_research/radar/service.py`
- `src/cc_deep_research/radar/router.py`
- `dashboard/src/components/radar/opportunity-detail.tsx`
- `dashboard/src/lib/content-gen-api.ts` or `dashboard/src/lib/api.ts`
- `tests/test_radar_content_conversion.py`

## Implementation Guide

1. Pick the smallest content target to support first. Recommended order:
   - backlog item
   - brief
   - pipeline start
2. Map Radar opportunity fields into the target content shape. Keep the mapping explicit in code so it is easy to review.
3. Use existing content-gen stores and route handlers where possible.
4. Persist an `OpportunityWorkflowLink` for each created content artifact.
5. Add UI actions only for the targets that are actually implemented.

## Guardrails For A Small Agent

- Do not invent a separate content storage format for Radar conversions.
- Do not claim full pipeline conversion if only backlog or brief creation is implemented.
- Keep the field mapping explicit and testable.

## Deliverables

- Backend conversion path for at least one content-gen flow
- UI action for launching that flow from Radar
- Workflow linkage persistence
- Conversion tests

## Dependencies

- P8-T1 is not strictly required, but the same workflow-link pattern should be reused
- Existing content-gen route and store behavior

## Verification

- Run `uv run pytest tests/test_radar_content_conversion.py -v`
- Manually create a backlog item or brief from a Radar opportunity and confirm the created artifact contains carried-forward context

## Acceptance Criteria

- Users can convert a Radar opportunity into at least one content-generation artifact.
- The created artifact reflects the source opportunity context clearly.
- Workflow linkage back to the originating opportunity is stored.
