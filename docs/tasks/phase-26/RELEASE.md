# Release and Migration Playbook

This playbook covers the release process, migration procedures, and rollback guidance for CC Deep Research upgrades.

## Release Checklist

Before cutting a release, verify the following:

### Build and Quality

- [ ] `uv run ruff check src/ tests/` — no errors
- [ ] `uv run mypy src/` — no type errors
- [ ] `uv run pytest` — all tests pass
- [ ] `cd dashboard && npm run lint` — no lint errors
- [ ] `cd dashboard && npm run build` — production build succeeds
- [ ] `cd dashboard && npx playwright install --with-deps chromium` — Playwright installed
- [ ] `cd dashboard && npm run test:e2e:smoke` — smoke tests pass

### Storage and Schema

- [ ] DuckDB schema is compatible with current version — run `duckdb ~/.config/cc-deep-research/telemetry/dashboard.db "SHOW TABLES"` and verify `telemetry_sessions` and `telemetry_events` exist
- [ ] Telemetry JSONL format is compatible — check that session event directories in `~/.config/cc-deep-research/telemetry/` parse correctly
- [ ] Config schema is backward-compatible — verify `load_config()` succeeds with the existing config file

### Dashboard Verification

- [ ] Health endpoint returns 200: `curl http://localhost:8000/api/health`
- [ ] WebSocket route is available: `curl -v -N -H "Connection: Upgrade" -H "Upgrade: websocket" http://localhost:8000/ws`
- [ ] All `/api/operations/*` routes respond correctly

### Backup

- [ ] A recent backup manifest exists in `~/.config/cc-deep-research/`
- [ ] Run backup dry-run to confirm coverage: `GET /api/operations/backup/plan`
- [ ] Verify backup integrity: `GET /api/operations/backup/validate/<path>`

### Documentation

- [ ] `CHANGELOG.md` updated with all user-visible changes under `[Unreleased]`
- [ ] Version bumped via `uv run python scripts/bump_version.py <bump>`
- [ ] This playbook is linked from the relevant phase docs

## Migration Notes Template

When preparing a migration (schema change, config change, telemetry format change), document:

```markdown
## Migration: <description>

### What changed
< concisely describe the change >

### Compatibility
< does this break old sessions, telemetry, config? >

### Required actions
< steps the operator must take before upgrading >

### Rollback
< how to revert if this upgrade fails >

### Verified on
< date and version this was tested against >
```

### Schema Migrations

When changing DuckDB schema:

1. Write migration SQL that is additive (add columns, never remove or rename)
2. Test migration against a copy of the production database
3. Add a version marker to the schema: `ALTER TABLE telemetry_sessions ADD COLUMN schema_version INTEGER DEFAULT 0`
4. Document in the migration notes which sessions need re-ingestion

### Config Migrations

When changing config schema:

1. Ensure new fields have safe defaults — don't break `load_config()` on old config files
2. Log a warning when loading old config with missing fields
3. Add validation in `run_setup_validation` for new required fields

### Telemetry Migrations

When changing event format:

1. Telemetry is append-only — old events never change
2. New event types must be ignorable by older readers (use optional fields)
3. Session replay must work with both old and new event sequences

## Rollback Guidance

### When to Roll Back

Roll back immediately if:

- Health checks return FAIL for `config_compatible` after upgrade
- Dashboard crashes on startup with a traceback
- Telemetry ingestion fails for all new events
- The `/api/operations/*` routes return 500 errors

### How to Roll Back

1. **Stop the dashboard and backend**:
   ```bash
   lsof -i :8000   # find PID
   kill <PID>
   lsof -i :3000   # find Node PID
   kill <Node PID>
   ```

2. **Locate the backup manifest**:
   ```bash
   ls ~/.config/cc-deep-research/*.manifest.json
   # Pick the most recent
   ```

3. **Restore from backup** (see [Backup and Restore](../tasks/phase-26/p26-t3-backup-restore.md)):
   ```bash
   # Validate first
   curl "http://localhost:8000/api/operations/backup/validate/<path>"

   # Then restore (requires explicit confirmation)
   curl -X POST "http://localhost:8000/api/operations/backup/restore?backup_path=<path>&confirm=true"
   ```

4. **Verify rollback**:
   ```bash
   curl http://localhost:8000/api/health
   # Should return overall_status: "pass"
   ```

### Rollback Decision Tree

```
Upgrade fails health checks?
├── YES → Is config_compatible check failing?
│   └── YES → Roll back: config file format is incompatible
├── YES → Is dashboard_build check failing?
│   └── YES → Reinstall dashboard deps: cd dashboard && npm ci && npm run build
├── YES → Is backup_available check failing?
│   └── YES → Do NOT roll back. Create a backup first, then proceed.
└── NO → Are post-upgrade checks passing?
    └── NO → Roll back: runtime state is broken
    └── YES → Monitor for 24h, roll back if issues persist
```

## Compatibility Expectations

### Session Format

- Sessions saved as JSON in `~/.config/cc-deep-research/sessions/` are forward-compatible within a minor version
- Major version changes may require a session migration step (documented at release time)

### Telemetry Format

- JSONL events are designed to be forward-compatible (new fields are ignored by old readers)
- DuckDB schema is backward-compatible (additive changes only)

### Config Format

- Config is backward-compatible within a minor version
- Major version changes will be documented with a config migration step

## Post-Upgrade Verification

After upgrading, run:

```bash
# 1. Health check
curl http://localhost:8000/api/health | jq '.overall_status'

# 2. Upgrade validation
curl "http://localhost:8000/api/operations/upgrade/validate?version_from=<old>&version_to=<new>" | jq '.checks[] | select(.status != "pass")'

# 3. Run a test research session
cc-deep-research research "test upgrade verification" --depth quick

# 4. Verify analytics query
curl "http://localhost:8000/api/analytics?days_back=1" | jq '.summary.total_runs'
```

## Future Phase Linkage

When a new phase requires operator action during upgrade:

1. Add a pre-upgrade check in `src/cc_deep_research/operations/upgrade.py`
2. Document the check in this playbook
3. Update the relevant phase task doc to link here
