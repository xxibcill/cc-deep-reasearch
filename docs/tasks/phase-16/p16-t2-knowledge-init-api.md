# P16-T2: Add `/api/knowledge/init` Endpoint and Dashboard UI

## Summary

Add a dashboard API endpoint and UI for `knowledge init` so vault initialization is available from the browser instead of CLI.

## Details

- Add `POST /api/knowledge/init` endpoint in `knowledge_routes.py`
  - Accept optional `config_path` (Path) and `dry_run` (bool) query params
  - Call `init_vault(config_path, dry_run=dry_run)` from `cc_deep_research.knowledge.vault`
  - Return structured JSON response with created paths
- Add "Initialize Vault" button/panel in `dashboard/src/components/knowledge/knowledge-shell.tsx` or a dedicated init panel
- Handle uninitialized vault state gracefully in the knowledge page

## Acceptance Criteria

- `POST /api/knowledge/init` works and returns created paths
- Dashboard can initialize the vault without CLI
- Dry-run mode shows what would be created without creating it