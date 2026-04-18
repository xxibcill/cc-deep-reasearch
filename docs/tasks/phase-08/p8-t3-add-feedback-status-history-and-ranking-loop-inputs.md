# P8-T3: Add Feedback, Status History, and Ranking Loop Inputs

## Summary

Persist status history and feedback signals so the engine can learn from user behavior over time.

## Details

### What to implement

1. **StatusHistoryEntry model** in `radar/models.py`
   ```python
   class StatusHistoryEntry(BaseModel):
       id: str
       opportunity_id: str
       previous_status: OpportunityStatus
       new_status: OpportunityStatus
       changed_at: str
       reason: str | None = None
   ```

2. **StatusHistoryList container** in `radar/models.py`

3. **Storage operations** in `radar/storage.py`
   - `add_status_history_entry(entry: StatusHistoryEntry) -> None`
   - `get_status_history_for_opportunity(opportunity_id: str) -> list[StatusHistoryEntry]`

4. **Service layer** in `radar/service.py`
   - `record_status_change(opportunity_id, previous_status, new_status, reason=None)`
   - Call this in `update_opportunity_status()` before changing status
   - Link feedback to status changes for ranking signals

5. **Feedback metadata enrichment**
   - When recording feedback, capture: `opportunity_score_at_feedback`, `time_since_creation`
   - These become features for future ranking model

6. **API endpoint to get status history** (`GET /api/radar/opportunities/{opportunity_id}/history`)
   - Returns status history entries for an opportunity

7. **UI updates** in `dashboard/src/app/radar/opportunities/[id]/page.tsx`
   - Display status history timeline in the opportunity detail page
   - Show when status changed and by what action

### Exit criteria

- Every status change creates a StatusHistoryEntry
- Status history is retrievable via API and displayed in UI
- Feedback entries include scoring context at time of feedback
