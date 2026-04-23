# Refactor Regression Checklist

Use this checklist when making changes to refactored modules (Phase 01-06 boundary changes, service extraction, API route changes, model contract changes).

## Before submitting a PR

### Backend checks

```bash
# Lint must pass
uv run ruff check src/cc_deep_research/

# Type checks must pass for enabled modules
uv run mypy src/cc_deep_research/orchestration/
uv run mypy src/cc_deep_research/web_server.py src/cc_deep_research/web_server_routes/
uv run mypy src/cc_deep_research/research_runs/
uv run mypy src/cc_deep_research/telemetry/
uv run mypy src/cc_deep_research/monitoring.py
uv run mypy src/cc_deep_research/aggregation.py
uv run mypy src/cc_deep_research/text_normalization.py
uv run mypy src/cc_deep_research/session_store.py
uv run mypy src/cc_deep_research/post_validator.py

# Tests must pass
uv run pytest tests/test_orchestrator.py tests/test_telemetry.py tests/test_monitoring.py tests/test_web_server.py -x
```

### Dashboard checks

```bash
cd dashboard && npm run build && npm run lint  # must pass
```

### Contract fixtures (when models change)

If you changed a model that has a contract fixture in `tests/fixtures/`:
1. Update the fixture JSON to match the new model structure
2. Run `uv run pytest tests/test_content_gen_fixtures.py -x` to verify

If you added a new model or changed prompt output format:
1. Add or update the contract fixture in `tests/fixtures/`
2. Add or update `tests/helpers/fixture_loader.py` loader if needed
3. Add contract test coverage in `tests/test_content_gen_fixtures.py`

## What to check by boundary

### Content-gen pipeline (`content_gen/pipeline.py`, `content_gen/stages/`, `content_gen/agents/`)
- [ ] Pipeline stage order unchanged or deliberately modified
- [ ] `ContentGenPipeline` is the entry point, not `ContentGenOrchestrator` (legacy shim is for compat only)
- [ ] No new imports from `legacy_orchestrator.py` (except `_build_claim_ledger` and `_format_research_context` which are pending migration)
- [ ] Stage trace events are still emitted correctly
- [ ] Contract version bumped if prompt output format changed

### API routes (`content_gen/router.py`, `web_server_routes/`)
- [ ] Route path unchanged for existing endpoints
- [ ] Response model unchanged or deliberately modified
- [ ] New routes registered in correct router
- [ ] WebSocket events still streaming correctly

### Orchestration (`orchestration/`)
- [ ] `TeamResearchOrchestrator` and `PlannerResearchOrchestrator` both still work
- [ ] Phase order unchanged
- [ ] Session state serialization unchanged
- [ ] Source collection strategies (sequential/parallel) both still work

### Models and storage (`content_gen/models/`, `content_gen/storage/`)
- [ ] Model serialization/deserialization round-trips correctly
- [ ] YAML migration path still works for legacy data
- [ ] SQLite store schema unchanged or migration added
- [ ] Fixture tests pass after model change

### Dashboard (`dashboard/src/`)
- [ ] API client calls still match backend route paths
- [ ] Hook state updates still match pipeline stage events
- [ ] Build passes after API client changes

## When to run broader e2e coverage

Run the full benchmark or live test if:
- You changed the research or content-gen orchestrator core loop
- You changed the session state serialization format
- You modified LLM routing behavior
- You changed the telemetry event schema

```bash
# Full research pipeline test
cc-deep-research research "your query here" --depth quick --output-dir /tmp/test-run

# Full content-gen pipeline test
cc-deep-research content-gen pipeline --theme "test theme" --output /tmp/test-script.txt --save-context
```

## Documenting blocked checks

If a check above cannot be run (e.g., test infrastructure not yet available), add a comment in the PR describing:
1. What check is blocked
2. Why it's blocked
3. What manual verification was done instead
4. When the check should be enabled
