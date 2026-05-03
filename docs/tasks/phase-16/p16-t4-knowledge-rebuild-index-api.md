# P16-T4: Add `/api/knowledge/rebuild-index` Endpoint and Dashboard UI

## Summary

Add a dashboard API endpoint and UI for `knowledge rebuild-index`.

## Details

- Add `POST /api/knowledge/rebuild-index` endpoint in `knowledge_routes.py`
  - Clear the graph index via `GraphIndex(db_path).clear()`
  - Return confirmation with db_path
- Add rebuild trigger in the dashboard (button in knowledge page settings/infrastructure section)
- Confirm action with user (modal or inline confirmation)

## Acceptance Criteria

- `POST /api/knowledge/rebuild-index` clears the graph index
- Dashboard has a UI button to trigger rebuild
- Clear messaging that this is a destructive operation